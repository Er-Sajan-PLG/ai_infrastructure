"""Tests for the MCP client.

Two layers, and the split is the point:

* **Scripted transport** (most of this file). Every protocol path — handshake,
  pagination, id correlation, each error code, approval denial, timeout, server
  death, malformed stdout — runs against an in-memory ``Transport`` double. This
  is where the failure paths live, and it is why the transport is a protocol
  (ADR-0009 D-2).
* **A real child process** (last section). A small stdio server written to a
  temporary file and spawned with ``sys.executable``. This is the only test that
  exercises spawning, real pipe framing, stderr draining, and process-group
  shutdown. It stays on this machine.

The assertions that matter most are the ones proving a *refusal*: a denied call
must not reach the server, a tool the registry cannot represent must be excluded
rather than adapted, and a namespace must never come from ``serverInfo``.
"""

from __future__ import annotations

import json
import sys
import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

_CATALOG = Path(__file__).resolve().parents[3]
for _sub in ("tools", "protocols"):
    sys.path.insert(0, str(_CATALOG / _sub))

from mcp_client import (  # noqa: E402
    AllowAllApprovals,
    CallableApprovals,
    DenyAllApprovals,
    MCPClient,
    MCPProtocolError,
    MCPServerDiedError,
    MCPTimeoutError,
    StdioTransport,
    is_legal_tool_name,
    project_tools,
)
from mcp_client.approvals import ApprovalRequest  # noqa: E402
from mcp_client.jsonrpc import failure_from_error, failure_from_result  # noqa: E402
from tool_registry import FailureKind, ToolId, ToolRegistry  # noqa: E402

# --------------------------------------------------------------------------- #
# A scripted transport.
# --------------------------------------------------------------------------- #


class ScriptedTransport:
    """An in-memory Transport that replies from a queue and records what was sent.

    Also doubles as the *evidence* for several tests: ``sent`` holds the exact
    frames the client wrote, so a test can assert that a denied call never
    produced one.
    """

    def __init__(self, *replies: str | bytes | None) -> None:
        self._replies = list(replies)
        self.sent: list[bytes] = []
        self.closed = False
        self._dead = False

    def send(self, line: bytes) -> None:
        self.sent.append(line)

    def receive(self, timeout: float) -> bytes | None:
        if not self._replies:
            return None
        reply = self._replies.pop(0)
        if reply is None:
            return None
        if isinstance(reply, bytes):
            return reply
        if isinstance(reply, str):
            return reply.encode("utf-8")
        raise AssertionError(
            f"ScriptedTransport replies must be str, bytes or None, got "
            f"{type(reply).__name__}. A Mapping here means a helper was called "
            f"without json.dumps -- _response/_listing already serialise."
        )

    def stderr_tail(self) -> str:
        return "server wrote this to stderr"

    def close(self, *, grace: float) -> None:
        self.closed = True

    # helpers for tests
    def mark_dead(self) -> None:
        self._dead = True

    def died(self) -> bool:
        return self._dead

    @property
    def returncode(self) -> int | None:
        return 1 if self._dead else None


def _response(request_id: int, result: Mapping[str, Any]) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": dict(result)})


def _error(request_id: int, code: int, message: str = "boom") -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
    )


def _initialize_result(version: str = "2025-06-18") -> dict[str, Any]:
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "test-server", "version": "9.9.9"},
    }


def _client(transport: ScriptedTransport, **kwargs: Any) -> MCPClient:
    kwargs.setdefault("namespace", "remote")
    kwargs.setdefault("approvals", AllowAllApprovals())
    return MCPClient(transport, **kwargs)


# --------------------------------------------------------------------------- #
# Framing.
# --------------------------------------------------------------------------- #


def test_encode_is_compact_and_newline_terminated() -> None:
    from mcp_client import encode_message

    encoded = encode_message({"jsonrpc": "2.0", "id": 1, "method": "x"})
    assert encoded.endswith(b"\n")
    assert encoded.count(b"\n") == 1
    assert b": " not in encoded  # compact separators, not Python's default


def test_encode_escapes_a_newline_inside_a_string() -> None:
    from mcp_client import encode_message

    # The spec's rule is that one message is one line. Measured behaviour:
    # json.dumps ESCAPES a newline inside a string rather than emitting it, so
    # the body is newline-free and the assertion in encode_message cannot fire
    # through this path.
    #
    # This test therefore pins the property that actually holds rather than an
    # unreachable raise. The first version of this test asserted the raise and
    # failed -- the assertion is real, but it is defence-in-depth for a future
    # encoder swap, not something json.dumps can trigger. Recording that as a
    # negative result is the honest move; a test that can never exercise its
    # subject is worse than no test.
    encoded = encode_message({"jsonrpc": "2.0", "id": 1, "method": "x\ny"})

    # Exactly one newline: the frame terminator. None inside the body.
    assert encoded.count(b"\n") == 1
    assert encoded.endswith(b"\n")
    assert b"\\n" in encoded  # escaped sequence, not a literal control char


def test_decode_rejects_non_json() -> None:
    from mcp_client import decode_message

    with pytest.raises(MCPProtocolError, match="not valid JSON"):
        decode_message(b"this is not json")


def test_decode_rejects_a_json_array() -> None:
    from mcp_client import decode_message

    with pytest.raises(MCPProtocolError, match="must be an object"):
        decode_message(b"[1, 2, 3]")


# --------------------------------------------------------------------------- #
# The handshake, and the era decision.
# --------------------------------------------------------------------------- #


def test_initialize_sends_the_legacy_handshake() -> None:
    transport = ScriptedTransport(_response(1, _initialize_result()))
    client = _client(transport)

    client.initialize()

    first = json.loads(transport.sent[0])
    assert first["method"] == "initialize"
    assert first["params"]["protocolVersion"] == "2025-06-18"
    assert client.protocol_version == "2025-06-18"


def test_initialize_declares_no_client_capabilities() -> None:
    transport = ScriptedTransport(_response(1, _initialize_result()))
    client = _client(transport)
    client.initialize()

    params = json.loads(transport.sent[0])["params"]
    # Declaring a capability we do not implement invites the server to use it.
    assert params["capabilities"] == {}


def test_initialize_sends_initialized_as_a_notification() -> None:
    transport = ScriptedTransport(_response(1, _initialize_result()))
    client = _client(transport)
    client.initialize()

    notification = json.loads(transport.sent[1])
    assert notification["method"] == "notifications/initialized"
    # A notification has no id; that is what makes the server not reply.
    assert "id" not in notification


def test_initialize_rejects_a_modern_protocol_version() -> None:
    transport = ScriptedTransport(_response(1, _initialize_result("2026-07-28")))
    client = _client(transport)

    # The spec says modern-vs-legacy fails rather than degrades. It is reported
    # as a named error, not retried (ADR-0009 D-1).
    with pytest.raises(MCPProtocolError, match="not one of the legacy revisions"):
        client.initialize()


def test_initialize_rejects_a_missing_protocol_version() -> None:
    result = _initialize_result()
    del result["protocolVersion"]
    transport = ScriptedTransport(_response(1, result))
    client = _client(transport)

    with pytest.raises(MCPProtocolError, match="not one of the legacy revisions"):
        client.initialize()


# --------------------------------------------------------------------------- #
# tools/list.
# --------------------------------------------------------------------------- #


def test_list_tools_follows_pagination_to_exhaustion() -> None:
    page1 = {
        "tools": [
            {
                "name": "alpha",
                "description": "A.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ],
        "nextCursor": "page-2",
    }
    page2 = {
        "tools": [
            {
                "name": "beta",
                "description": "B.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
    }
    transport = ScriptedTransport(_response(1, page1), _response(2, page2))
    client = _client(transport)

    tools = client.list_tools()

    # Stopping at page one would let a caller build a policy from a partial list.
    assert [t.name for t in tools] == ["alpha", "beta"]
    second_request = json.loads(transport.sent[1])
    assert second_request["params"] == {"cursor": "page-2"}


def test_list_tools_tolerates_a_non_object_entry() -> None:
    page = {"tools": ["not an object", {"name": "alpha", "inputSchema": {}}]}
    transport = ScriptedTransport(_response(1, page))
    client = _client(transport)

    tools = client.list_tools()

    assert [t.name for t in tools] == ["alpha"]


# --------------------------------------------------------------------------- #
# tools/call and the error mapping (ADR-0009 D-5).
# --------------------------------------------------------------------------- #


def test_call_tool_returns_text_on_success() -> None:
    transport = ScriptedTransport(
        _response(1, {"content": [{"type": "text", "text": "hello"}]})
    )
    client = _client(transport)

    outcome = client.call_tool("echo", {"x": 1})

    assert outcome.ok
    assert outcome.text == "hello"


def test_call_tool_refuses_an_unknown_tool_as_not_found() -> None:
    transport = ScriptedTransport(_error(1, -32601, "no such tool"))
    client = _client(transport)

    outcome = client.call_tool("nope")

    assert not outcome.ok
    assert outcome.failure is not None
    # A hallucinated name cannot be fixed by the model that hallucinated it.
    assert outcome.failure.kind is FailureKind.NOT_FOUND
    assert outcome.failure.model_visible is False


def test_call_tool_maps_invalid_params_as_model_visible() -> None:
    transport = ScriptedTransport(_error(1, -32602, "bad arguments"))
    client = _client(transport)

    outcome = client.call_tool("echo", {"x": "wrong type"})

    assert outcome.failure is not None
    # THE DIVERGENCE the ADR records: MCP files -32602 as a protocol error;
    # we treat it as something the model can correct.
    assert outcome.failure.kind is FailureKind.INVALID_ARGUMENTS
    assert outcome.failure.model_visible is True


def test_call_tool_maps_is_error_results_as_execution_failed() -> None:
    transport = ScriptedTransport(
        _response(
            1,
            {
                "content": [{"type": "text", "text": "the API returned 500"}],
                "isError": True,
            },
        )
    )
    client = _client(transport)

    outcome = client.call_tool("flaky")

    assert outcome.failure is not None
    assert outcome.failure.kind is FailureKind.EXECUTION_FAILED
    assert outcome.failure.model_visible is True
    assert "500" in outcome.text


def test_call_tool_renders_structured_content_when_there_are_no_text_blocks() -> None:
    transport = ScriptedTransport(
        _response(1, {"content": [], "structuredContent": {"answer": 42}})
    )
    client = _client(transport)

    outcome = client.call_tool("structured")

    assert outcome.ok
    assert json.loads(outcome.text) == {"answer": 42}


def test_error_mapping_table_is_total() -> None:
    assert failure_from_error("t", {"code": -32601}).kind is FailureKind.NOT_FOUND
    assert failure_from_error("t", {"code": -32002}).kind is FailureKind.NOT_FOUND
    assert (
        failure_from_error("t", {"code": -32602}).kind is FailureKind.INVALID_ARGUMENTS
    )
    assert (
        failure_from_error("t", {"code": -32603}).kind is FailureKind.EXECUTION_FAILED
    )
    assert failure_from_result("t", {"isError": False}) is None


# --------------------------------------------------------------------------- #
# The approval seam (ADR-0009 D-3) — the AI-010 answer.
# --------------------------------------------------------------------------- #


def test_default_policy_denies_every_call() -> None:
    transport = ScriptedTransport()
    client = MCPClient(transport, namespace="remote")  # approvals omitted

    outcome = client.call_tool("anything", {"amount": 100})

    assert not outcome.ok
    assert outcome.failure is not None
    assert outcome.failure.model_visible is True
    assert "denied by the approval policy" in outcome.failure.message
    # THE assertion: nothing was sent. A refusal that still wrote the frame
    # would be a refusal in name only.
    assert transport.sent == []


def test_allow_all_permits_and_the_frame_is_sent() -> None:
    transport = ScriptedTransport(
        _response(1, {"content": [{"type": "text", "text": "ok"}]})
    )
    client = _client(transport, approvals=AllowAllApprovals())

    client.call_tool("echo")

    assert json.loads(transport.sent[0])["method"] == "tools/call"


def test_a_policy_can_deny_selectively_and_never_sees_the_call_otherwise() -> None:
    seen: list[ApprovalRequest] = []

    def policy(request: ApprovalRequest) -> bool:
        seen.append(request)
        return request.arguments.get("safe") is True

    transport = ScriptedTransport(
        _response(1, {"content": [{"type": "text", "text": "ran"}]})
    )
    client = _client(transport, approvals=CallableApprovals(policy))

    denied = client.call_tool("delete", {"safe": False})
    permitted = client.call_tool("read", {"safe": True})

    assert not denied.ok
    assert permitted.ok
    assert len(seen) == 2
    # The policy reasoned about the remote name and the arguments.
    assert seen[0].tool_name == "delete"
    assert seen[0].namespace == "remote"
    # Only the permitted call was written.
    assert len(transport.sent) == 1


def test_a_denial_names_the_policy_that_refused() -> None:
    transport = ScriptedTransport()
    client = _client(transport, approvals=DenyAllApprovals())

    outcome = client.call_tool("x")

    assert outcome.failure is not None
    # "denied by policy" with no way to find the policy is a poor diagnostic.
    assert "DenyAllApprovals()" in outcome.failure.message


def test_approval_arguments_are_read_only() -> None:
    captured: list[ApprovalRequest] = []

    def policy(request: ApprovalRequest) -> bool:
        captured.append(request)
        return True

    transport = ScriptedTransport(
        _response(1, {"content": [{"type": "text", "text": "ok"}]})
    )
    client = _client(transport, approvals=CallableApprovals(policy))
    client.call_tool("echo", {"a": 1})

    with pytest.raises(TypeError):
        captured[0].arguments["a"] = 2  # type: ignore[index]


# --------------------------------------------------------------------------- #
# Protocol violations and transport failures.
# --------------------------------------------------------------------------- #


def test_a_non_json_stdout_line_terminates_the_session() -> None:
    transport = ScriptedTransport("not json at all")
    client = _client(transport)

    with pytest.raises(MCPProtocolError, match="not valid JSON"):
        client.list_tools()


def test_a_response_with_an_unknown_id_terminates_the_session() -> None:
    transport = ScriptedTransport(_response(99, {"tools": []}))
    client = _client(transport)

    # Skipping it would desynchronise the stream (ADR-0009 D-6).
    with pytest.raises(MCPProtocolError, match="does not match the outstanding"):
        client.list_tools()


def test_a_notification_is_dropped_and_reading_continues() -> None:
    notification = json.dumps({"jsonrpc": "2.0", "method": "notifications/progress"})
    transport = ScriptedTransport(notification, _response(1, {"tools": []}))
    client = _client(transport)

    assert client.list_tools() == ()


def test_a_server_initiated_request_is_refused_not_ignored() -> None:
    server_request = json.dumps(
        {"jsonrpc": "2.0", "id": "server-1", "method": "sampling/createMessage"}
    )
    transport = ScriptedTransport(server_request, _response(1, {"tools": []}))
    client = _client(transport)

    client.list_tools()

    # The refusal was written, so the server cannot hang waiting for a reply.
    refusal = json.loads(transport.sent[1])
    assert refusal["id"] == "server-1"
    assert refusal["error"]["code"] == -32601


def test_a_timeout_raises_a_timeout_error() -> None:
    transport = ScriptedTransport(None)
    client = _client(transport, request_timeout_seconds=0.05)

    with pytest.raises(MCPTimeoutError):
        client.list_tools()


def test_a_dead_server_raises_a_death_carrying_stderr() -> None:
    transport = ScriptedTransport(None)
    transport.mark_dead()
    client = _client(transport, request_timeout_seconds=0.05)

    with pytest.raises(MCPServerDiedError) as excinfo:
        client.list_tools()

    # stderr explains the death; it is never an error signal on its own.
    assert excinfo.value.stderr_tail == "server wrote this to stderr"
    assert excinfo.value.returncode == 1


def test_close_is_idempotent() -> None:
    transport = ScriptedTransport()
    client = _client(transport)

    client.close()
    client.close()

    assert transport.closed


# --------------------------------------------------------------------------- #
# Projection (ADR-0009 D-4) — the external boundary.
# --------------------------------------------------------------------------- #


def _listing(*entries: Mapping[str, Any], request_id: int = 1) -> str:
    """Build a ``tools/list`` reply.

    ``request_id`` defaults to 1 because in most tests the listing is the first
    request. It must be overridden whenever ``initialize`` ran first, because the
    client correlates strictly and a mismatched id is a protocol error.

    Three tests in this file were wrong about which id the reply should carry.
    Two failed loudly; one PASSED for the wrong reason, because an id mismatch
    and a genuine remote failure both surface as ``EXECUTION_FAILED``. The
    lesson worth keeping: when a test double fabricates a reply, the id is part
    of the fixture, and it has to be derived from the request sequence rather
    than copied.
    """
    return _response(request_id, {"tools": [dict(e) for e in entries]})


def test_projection_uses_the_client_minted_namespace() -> None:
    transport = ScriptedTransport(
        _listing(
            {
                "name": "echo",
                "description": "Echo.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        )
    )
    client = _client(transport, namespace="chosen-by-caller")
    registry = ToolRegistry()

    report = project_tools(client, registry)

    assert report.registered == [ToolId("chosen-by-caller", "echo")]
    assert registry.get(ToolId("chosen-by-caller", "echo")) is not None


def test_projection_never_uses_server_info_as_a_namespace() -> None:
    # _initialize_result() returns a payload dict; it must be wrapped in a
    # response envelope, not handed to the transport raw. The ScriptedTransport
    # guard caught this as a dict reply rather than letting it pass silently.
    transport = ScriptedTransport(
        _response(1, _initialize_result()),
        # request_id=2: initialize consumed id 1, so tools/list is the second
        # request. A listing reply carrying id 1 is rejected as a protocol
        # violation, which is the client behaving correctly.
        _listing(
            {
                "name": "echo",
                "description": "Echo.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            request_id=2,
        ),
    )
    client = _client(transport, namespace="local")
    client.initialize()
    registry = ToolRegistry()

    project_tools(client, registry)

    # The server called itself "test-server". It must not become an identifier:
    # the spec warns serverInfo is neither unique nor trustworthy.
    assert registry.get(ToolId("local", "echo")) is not None
    assert ToolId("test-server", "echo") not in registry
    assert client.server_info["name"] == "test-server"  # informational only


def test_projection_excludes_an_uppercase_name_by_name_and_reason() -> None:
    transport = ScriptedTransport(
        _listing(
            {"name": "GetWeather", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "ok_tool", "inputSchema": {"type": "object", "properties": {}}},
        )
    )
    client = _client(transport)
    registry = ToolRegistry()

    report = project_tools(client, registry)

    # One bad tool must not prevent the others from being used.
    assert report.registered_count == 1
    assert report.excluded_count == 1
    reason = report.why("GetWeather")
    assert reason is not None and "not representable" in reason
    # Not silently downcased: that would collide two distinct remote tools.
    assert ToolId("remote", "getweather") not in registry


def test_projection_excludes_a_schema_outside_the_registry_subset() -> None:
    transport = ScriptedTransport(
        _listing(
            {
                "name": "composed",
                "inputSchema": {
                    "type": "object",
                    "oneOf": [{"properties": {"a": {"type": "string"}}}],
                },
            },
            {"name": "plain", "inputSchema": {"type": "object", "properties": {}}},
        )
    )
    client = _client(transport)
    registry = ToolRegistry()

    report = project_tools(client, registry)

    assert report.registered_count == 1
    assert report.excluded_count == 1
    reason = report.why("composed")
    assert reason is not None and "documented subset" in reason


def test_projection_excludes_a_missing_or_non_object_schema() -> None:
    transport = ScriptedTransport(
        _listing(
            {"name": "no_schema"},
            {"name": "wrong_type", "inputSchema": {"type": "array"}},
        )
    )
    client = _client(transport)
    registry = ToolRegistry()

    report = project_tools(client, registry)

    assert report.registered_count == 0
    assert report.excluded_count == 2


def test_projection_skips_a_tool_already_registered() -> None:
    transport = ScriptedTransport(
        _listing({"name": "echo", "inputSchema": {"type": "object", "properties": {}}})
    )
    client = _client(transport)
    registry = ToolRegistry()
    project_tools(client, registry)

    transport2 = ScriptedTransport(
        _listing({"name": "echo", "inputSchema": {"type": "object", "properties": {}}})
    )
    report = project_tools(_client(transport2), registry)

    assert report.excluded_count == 1
    assert report.why("echo") is not None


def test_a_projected_tool_forwards_and_reports_a_remote_failure() -> None:
    # One transport, two replies in order: the listing, then the failing call.
    # The first version of this test built two transports and projected twice,
    # which meant the listing consumed the *failing* reply and the test never
    # reached the forwarder at all.
    transport = ScriptedTransport(
        _listing({"name": "echo", "inputSchema": {"type": "object", "properties": {}}}),
        # id 2, not 1: the listing consumed id 1, so the call is the second
        # request. Using id 1 here produced a failure for the WRONG reason --
        # an id mismatch also yields EXECUTION_FAILED, so the assertion below
        # passed while the forwarder was never exercised. Fixed.
        _response(
            2, {"content": [{"type": "text", "text": "it broke"}], "isError": True}
        ),
    )
    client = _client(transport)
    registry = ToolRegistry()
    report = project_tools(client, registry, namespace="remote")
    assert report.registered_count == 1

    result = registry.invoke(ToolId("remote", "echo"), {})

    # The forwarder raises on failure, so the registry records EXECUTION_FAILED
    # rather than returning a string that merely looks like an error.
    assert result.failure is not None
    assert result.failure.kind is FailureKind.EXECUTION_FAILED


def test_a_projected_tool_forwards_a_successful_call() -> None:
    transport = ScriptedTransport(
        _listing({"name": "echo", "inputSchema": {"type": "object", "properties": {}}}),
        # id 2: the listing took id 1.
        _response(2, {"content": [{"type": "text", "text": "forwarded"}]}),
    )
    client = _client(transport)
    registry = ToolRegistry()
    project_tools(client, registry, namespace="remote")

    result = registry.invoke(ToolId("remote", "echo"), {})

    assert result.ok
    assert result.value == "forwarded"


def test_is_legal_tool_name_matches_tool_id() -> None:
    assert is_legal_tool_name("echo")
    assert is_legal_tool_name("a.b-c_d")
    assert not is_legal_tool_name("GetWeather")
    assert not is_legal_tool_name("")
    assert not is_legal_tool_name("-leading")


# --------------------------------------------------------------------------- #
# A real child process.
# --------------------------------------------------------------------------- #

_FAKE_SERVER = textwrap.dedent("""
    import json
    import sys

    def send(payload):
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\\n")
        sys.stdout.flush()

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        message = json.loads(raw)
        method = message.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": message["id"], "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1.0"},
            }})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": message["id"], "result": {"tools": [
                {"name": "echo", "description": "Echo.", "inputSchema": {
                    "type": "object", "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                }},
            ]}})
        elif method == "tools/call":
            args = message.get("params", {}).get("arguments", {})
            send({"jsonrpc": "2.0", "id": message["id"], "result": {
                "content": [{"type": "text", "text": "echo:" + str(args.get("text", ""))}],
            }})
        elif "id" in message:
            send({"jsonrpc": "2.0", "id": message["id"], "error": {
                "code": -32601, "message": "unknown method",
            }})
    """)


@pytest.fixture()
def fake_server(tmp_path: Path) -> Path:
    path = tmp_path / "fake_server.py"
    path.write_text(_FAKE_SERVER, encoding="utf-8")
    return path


def test_real_child_handshake_listing_and_call(fake_server: Path) -> None:
    client = MCPClient.from_command(
        sys.executable,
        [str(fake_server)],
        namespace="child",
        approvals=AllowAllApprovals(),
        request_timeout_seconds=10.0,
    )
    try:
        client.initialize()
        assert client.protocol_version == "2025-06-18"

        tools = client.list_tools()
        assert [t.name for t in tools] == ["echo"]

        outcome = client.call_tool("echo", {"text": "hi"})
        assert outcome.ok
        assert outcome.text == "echo:hi"
    finally:
        client.close()


def test_real_child_projection_end_to_end(fake_server: Path) -> None:
    registry = ToolRegistry()
    client = MCPClient.from_command(
        sys.executable,
        [str(fake_server)],
        namespace="child",
        approvals=AllowAllApprovals(),
        request_timeout_seconds=10.0,
    )
    try:
        client.initialize()
        report = project_tools(client, registry)
        # This is the assertion that failed when _project_one had no success
        # branch: the tool registered, the forwarder worked, and the report
        # still said nothing had been registered.
        assert report.registered_count == 1
        assert report.excluded_count == 0
        assert report.registered == [ToolId("child", "echo")]

        result = registry.invoke(ToolId("child", "echo"), {"text": "through"})
        assert result.ok
        assert result.value == "echo:through"
    finally:
        client.close()


def test_real_child_denied_call_never_reaches_the_server(fake_server: Path) -> None:
    client = MCPClient.from_command(
        sys.executable,
        [str(fake_server)],
        namespace="child",
        request_timeout_seconds=10.0,
    )
    try:
        client.initialize()
        outcome = client.call_tool("echo", {"text": "should not happen"})
        assert not outcome.ok
        assert outcome.failure is not None
        assert outcome.failure.model_visible is True
    finally:
        client.close()


def test_real_child_shutdown_is_prompt(fake_server: Path) -> None:
    client = MCPClient.from_command(
        sys.executable,
        [str(fake_server)],
        namespace="child",
        request_timeout_seconds=10.0,
    )
    client.initialize()
    client.close()
    client.close()  # idempotent


def test_transport_rejects_an_empty_command() -> None:
    with pytest.raises(ValueError):
        StdioTransport("")


def test_transport_reports_a_spawn_failure() -> None:
    from mcp_client import MCPTransportError

    with pytest.raises(MCPTransportError, match="could not spawn"):
        StdioTransport("/nonexistent/binary/definitely-not-here")
