"""The MCP client: legacy-era handshake, ``tools/list``, and ``tools/call``.

This is the only module that knows which era we speak (ADR-0009 D-1). Framing,
correlation, the error mapping, and the projection are era-independent — the
specification's own compatibility note is that the stdio framing rule is
byte-identical across the fork — so if the modern era is ever added, it is a new
handshake step here and nothing else.

Two behaviours are worth naming before the code:

* **A server-initiated request is refused, not ignored.** We declare no client
  capabilities, so a conforming server sends none. A non-conforming one that
  sends ``sampling/createMessage`` anyway would otherwise wait forever for a reply
  that never comes, so we answer it with ``-32601`` and keep reading. Ignoring it
  would hang; crashing on it would let a chatty server end the session.
* **Notifications are dropped.** They carry no ``id`` and expect no reply, which
  is exactly why the handshake's second half is a notification.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Never

from .approvals import (
    ApprovalPolicy,
    ApprovalRequest,
    DenyAllApprovals,
)
from .errors import (
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    MCPProtocolError,
    MCPServerDiedError,
    MCPTimeoutError,
    MCPToolFailure,
    MCPTransportError,
)
from .framing import decode_message, encode_message
from .jsonrpc import (
    failure_from_error,
    failure_from_result,
    make_error,
    make_notification,
    make_request,
    validate_envelope,
)
from .transport import Transport

__all__ = [
    "CLIENT_NAME",
    "CLIENT_VERSION",
    "LEGACY_PROTOCOL_VERSION",
    "LEGACY_PROTOCOL_VERSIONS",
    "REJECTED_SERVER_REQUEST",
    "MCPClient",
    "ToolCallOutcome",
    "ToolDescriptorView",
]

# The revision this client *asks* for. Legacy era: the handshake exists.
LEGACY_PROTOCOL_VERSION = "2025-06-18"

# Every legacy revision the specification defines, newest first. A server may
# answer `initialize` with any of these; the handshake is what makes them one era
# (ADR-0009 D-1, research §2.3).
LEGACY_PROTOCOL_VERSIONS: frozenset[str] = frozenset(
    {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
)

CLIENT_NAME = "ai_infrastructure"
CLIENT_VERSION = "0.1.0"

# The one code we answer a server-initiated request with. We support none.
REJECTED_SERVER_REQUEST = METHOD_NOT_FOUND


@dataclass(frozen=True, slots=True)
class ToolDescriptorView:
    """A remote tool as the server described it.

    Deliberately a *view*: it holds only the leaves the client needs, not the
    server's message. The raw ``input_schema`` is kept because the projection
    must validate it against the registry's subset before accepting the tool.
    """

    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCallOutcome:
    """What one ``tools/call`` produced.

    Attributes:
        text: The result's text, or the failure's message. Always a string so a
            caller never has to branch before putting it in a prompt.
        failure: ``None`` on success. When set, ``failure.kind`` carries the
            registry's taxonomy and ``failure.model_visible`` says whether a
            caller may show it to a model.
    """

    text: str
    failure: MCPToolFailure | None = None

    @property
    def ok(self) -> bool:
        """True when the call produced a value."""
        return self.failure is None


class MCPClient:
    """Speaks the legacy MCP handshake over an injected transport.

    The transport is injected rather than constructed (ADR-0009 D-2) so every
    protocol path is testable with no child process. Use
    :meth:`from_command` to build the stdio one.
    """

    __slots__ = (
        "_approvals",
        "_closed",
        "_namespace",
        "_next_id",
        "_protocol_version",
        "_request_timeout",
        "_server_info",
        "_shutdown_grace",
        "_transport",
    )

    def __init__(
        self,
        transport: Transport,
        *,
        namespace: str,
        approvals: ApprovalPolicy | None = None,
        request_timeout_seconds: float = 30.0,
        shutdown_grace_seconds: float = 2.0,
    ) -> None:
        """Bind a transport and a client-minted namespace.

        Args:
            transport: The framed channel to the server.
            namespace: The registry namespace remote tools are projected under.
                **Client-minted by construction** — it is an argument, never read
                from ``serverInfo.name``, because the specification warns that
                the server's self-reported name is neither unique nor trustworthy
                (ADR-0009 D-4).
            approvals: The policy consulted before every ``tools/call``.
                ``None`` becomes :class:`~.approvals.DenyAllApprovals` — the
                default refuses (ADR-0009 D-3).
            request_timeout_seconds: Per-request timeout. The specification
                requires timeouts and supplies no number (ADR-0009 D-7).
            shutdown_grace_seconds: How long to wait for a polite exit.
        """
        if not namespace:
            raise ValueError("namespace must not be empty")

        self._transport = transport
        self._namespace = namespace
        self._approvals: ApprovalPolicy = (
            approvals if approvals is not None else DenyAllApprovals()
        )
        self._request_timeout = request_timeout_seconds
        self._shutdown_grace = shutdown_grace_seconds
        self._next_id = 1
        self._server_info: dict[str, Any] = {}
        self._protocol_version: str | None = None
        self._closed = False

    # -- construction helpers ------------------------------------------------ #

    @classmethod
    def from_command(
        cls,
        command: str,
        args: Sequence[str] = (),
        *,
        namespace: str,
        approvals: ApprovalPolicy | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        request_timeout_seconds: float = 30.0,
        shutdown_grace_seconds: float = 2.0,
    ) -> MCPClient:
        """Spawn a stdio server and return a client bound to it.

        The import is local so this module does not drag ``subprocess`` into a
        caller that only wants the protocol.
        """
        from .transport import StdioTransport

        transport = StdioTransport(command, args, cwd=cwd, env=env)
        return cls(
            transport,
            namespace=namespace,
            approvals=approvals,
            request_timeout_seconds=request_timeout_seconds,
            shutdown_grace_seconds=shutdown_grace_seconds,
        )

    # -- properties ---------------------------------------------------------- #

    @property
    def namespace(self) -> str:
        """The client-minted namespace remote tools are projected under."""
        return self._namespace

    @property
    def protocol_version(self) -> str | None:
        """The version the server agreed to, once the handshake has run."""
        return self._protocol_version

    @property
    def server_info(self) -> Mapping[str, Any]:
        """What the server said about itself. Informational only — never trusted."""
        return dict(self._server_info)

    @property
    def approvals(self) -> ApprovalPolicy:
        """The policy consulted before every dispatch."""
        return self._approvals

    # -- the protocol -------------------------------------------------------- #

    def initialize(self) -> Mapping[str, Any]:
        """Run the legacy handshake and return the server's ``initialize`` result.

        Raises:
            MCPProtocolError: The server answered with a protocol version outside
                the legacy set. This client speaks legacy only; the specification
                says a mismatch fails rather than degrades, so it is reported as
                a named error instead of being retried.
        """
        params = {
            "protocolVersion": LEGACY_PROTOCOL_VERSION,
            # We declare NOTHING. Declaring a capability we do not implement
            # would invite the server to use it.
            "capabilities": {},
            "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
        }
        result = self._request("initialize", params)

        negotiated = result.get("protocolVersion")
        if (
            not isinstance(negotiated, str)
            or negotiated not in LEGACY_PROTOCOL_VERSIONS
        ):
            raise MCPProtocolError(
                f"server negotiated protocol version {negotiated!r}, which is not "
                f"one of the legacy revisions this client implements "
                f"({', '.join(sorted(LEGACY_PROTOCOL_VERSIONS))}); the modern era "
                f"is not implemented (ADR-0009 D-1)"
            )

        self._protocol_version = negotiated
        raw_info = result.get("serverInfo")
        self._server_info = dict(raw_info) if isinstance(raw_info, Mapping) else {}

        self._notify("notifications/initialized")
        return result

    def list_tools(self) -> tuple[ToolDescriptorView, ...]:
        """Return every tool the server advertises, following ``nextCursor``.

        Pagination is followed to exhaustion rather than returning one page: a
        caller asking "what tools exist" that silently receives the first page
        would build an incomplete policy from an incomplete list.
        """
        collected: list[ToolDescriptorView] = []
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {} if cursor is None else {"cursor": cursor}
            result = self._request("tools/list", params)

            raw_tools = result.get("tools")
            if not isinstance(raw_tools, list):
                raise MCPProtocolError(
                    "tools/list result has no 'tools' array", line=str(result)[:200]
                )

            for entry in raw_tools:
                if not isinstance(entry, Mapping):
                    continue
                name = entry.get("name")
                if not isinstance(name, str):
                    continue
                schema = entry.get("inputSchema")
                collected.append(
                    ToolDescriptorView(
                        name=name,
                        description=str(entry.get("description", "")),
                        input_schema=(
                            dict(schema) if isinstance(schema, Mapping) else {}
                        ),
                    )
                )

            next_cursor = result.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                return tuple(collected)
            cursor = next_cursor

    def call_tool(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> ToolCallOutcome:
        """Ask the server to run ``name``.

        The approval policy is consulted **before** the frame is written
        (ADR-0009 D-3). A denial never reaches the server.

        Returns:
            The outcome. A refused call and a failed call are both
            :class:`ToolCallOutcome` values with ``failure`` set, because both are
            things a model may act on.
        """
        args = dict(arguments) if arguments is not None else {}

        decision = self._approvals.decide(
            ApprovalRequest(
                tool_name=name,
                arguments=_frozen(args),
                namespace=self._namespace,
            )
        )
        if not decision:
            return ToolCallOutcome(
                text=f"{name} was denied by the approval policy",
                failure=MCPToolFailure(
                    kind=_execution_failed(),
                    message=(
                        f"the call to {name!r} was denied by the approval policy "
                        f"({self._approvals!r}) before it was sent"
                    ),
                    tool_name=name,
                ),
            )

        response = self._exchange("tools/call", {"name": name, "arguments": args})

        if "error" in response:
            error = response["error"]
            if not isinstance(error, Mapping):
                raise MCPProtocolError(
                    "JSON-RPC error member must be an object",
                    line=str(response)[:200],
                )
            failure = failure_from_error(name, error)
            return ToolCallOutcome(text=failure.message, failure=failure)

        raw_result = response.get("result")
        if not isinstance(raw_result, Mapping):
            raise MCPProtocolError(
                "tools/call result must be an object", line=str(response)[:200]
            )
        # isinstance narrows to Mapping[Any, Any]; the helpers are declared over
        # Mapping[str, Any]. A JSON object's keys are strings by construction, so
        # this is a type-level statement rather than a transformation.
        result: Mapping[str, Any] = dict(raw_result)

        # A distinct name from the protocol-error branch above: reusing
        # `failure` would narrow it to the non-optional MCPToolFailure bound at
        # line 353, making this `MCPToolFailure | None` an assignment error and
        # the success path below unreachable.
        result_failure = failure_from_result(name, result)
        if result_failure is not None:
            return ToolCallOutcome(text=result_failure.message, failure=result_failure)

        return ToolCallOutcome(text=_render_result(result))

    def close(self) -> None:
        """Shut the transport down. Idempotent."""
        if self._closed:
            return
        self._closed = True
        self._transport.close(grace=self._shutdown_grace)

    def __enter__(self) -> MCPClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals ----------------------------------------------------------- #

    def _request(self, method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        """Send a request and return its ``result``, raising on an error member."""
        response = self._exchange(method, params)

        if "error" in response:
            error = response["error"]
            code = error.get("code") if isinstance(error, Mapping) else None
            message = error.get("message") if isinstance(error, Mapping) else None
            raise MCPProtocolError(
                f"{method} failed during the handshake or listing: "
                f"{message!r} (code {code})",
                line=str(response)[:200],
            )

        result = response.get("result")
        if not isinstance(result, Mapping):
            raise MCPProtocolError(
                f"{method} result must be an object", line=str(response)[:200]
            )
        return result

    def _exchange(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        """Send a request and read until its response arrives.

        Server notifications are dropped; server *requests* are answered with
        ``-32601`` so a non-conforming server cannot hang waiting for a reply.
        A response carrying an unknown ``id`` is a protocol violation and ends
        the session — silently skipping it would desynchronise the stream
        (ADR-0009 D-6).
        """
        request_id = self._next_id
        self._next_id += 1
        self._transport.send(encode_message(make_request(request_id, method, params)))

        while True:
            line = self._transport.receive(self._request_timeout)
            if line is None:
                self._raise_after_no_line()

            message = decode_message(line)
            validate_envelope(message)

            if "method" in message:
                if "id" in message:
                    # A server-initiated request. We implement none, so refuse it
                    # rather than leave the server waiting.
                    self._transport.send(
                        encode_message(
                            make_error(
                                message["id"],
                                REJECTED_SERVER_REQUEST,
                                f"{message.get('method')!r} is not supported by this client",
                            )
                        )
                    )
                # A notification needs no reply.
                continue

            if message.get("id") != request_id:
                raise MCPProtocolError(
                    f"response id {message.get('id')!r} does not match the "
                    f"outstanding request id {request_id!r}",
                    line=str(message)[:200],
                )
            return message

    def _notify(self, method: str) -> None:
        """Send a notification. No response is expected or read."""
        self._transport.send(encode_message(make_notification(method)))

    def _raise_after_no_line(self) -> Never:
        """Turn a ``None`` read into the right exception.

        ``None`` means *no complete line within the timeout*. Whether that is a
        timeout or a death is decided here, by asking the transport, so the two
        failures do not collapse into one.

        Returns ``Never`` because every path raises. That annotation is
        load-bearing rather than decorative: without it the type checker must
        assume the caller continues with ``line`` still ``None``, which makes
        the following ``decode_message(line)`` call ill-typed and the code after
        the guard unreachable. The runtime behaviour was always correct; only
        the claim about it was missing.
        """
        died = getattr(self._transport, "died", None)
        if callable(died) and died():
            returncode = getattr(self._transport, "returncode", None)
            raise MCPServerDiedError(
                f"the server exited with status {returncode!r} while a request "
                f"was outstanding",
                returncode=returncode if isinstance(returncode, int) else None,
                stderr_tail=self._transport.stderr_tail(),
            )
        raise MCPTimeoutError(
            f"no response within {self._request_timeout}s; the server is not "
            f"replying. The timeout is this client's own choice — the "
            f"specification supplies no number (ADR-0009 D-7)"
        )


def _frozen(arguments: Mapping[str, Any]) -> Mapping[str, object]:
    """Wrap arguments read-only for the approval request."""
    from types import MappingProxyType

    return MappingProxyType(dict(arguments))


def _execution_failed() -> Any:
    """Return ``FailureKind.EXECUTION_FAILED`` without a module-level import.

    Keeps ``client`` importable for its protocol surface even where the registry
    is absent, which matters because the approval denial is the one failure this
    module *constructs* rather than receives.
    """
    from tool_registry import FailureKind

    return FailureKind.EXECUTION_FAILED


def _render_result(result: Mapping[str, Any]) -> str:
    """Render a successful ``CallToolResult`` as text for a prompt.

    Text blocks are joined. When there are none but ``structuredContent`` is
    present, the structured value is compactly encoded — a caller that asked for
    structured output should not receive an empty string. Anything else renders
    as the empty string, and the caller can see the result was contentless rather
    than being handed an invented placeholder.
    """
    blocks = result.get("content")
    parts: list[str] = []
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, Mapping) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
    if parts:
        return "\n".join(parts)

    if "structuredContent" in result:
        return json.dumps(
            result["structuredContent"], separators=(",", ":"), sort_keys=True
        )
    return ""


# Re-exported so a caller can catch the transport failure this module may raise
# without importing the transport module.
_TRANSPORT_ERROR = MCPTransportError
_INVALID_REQUEST = INVALID_REQUEST
