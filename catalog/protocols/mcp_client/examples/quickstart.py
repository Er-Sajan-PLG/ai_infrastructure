#!/usr/bin/env python3
"""Runnable tour of ``mcp_client`` — no network, no real MCP server.

Why a scripted transport rather than a real child process
--------------------------------------------------------
This example is meant to be run by a reader. Spawning a server would require one
to be installed, and the interesting behaviour here is the *protocol*, not the
process management — the process path has its own tests, which do spawn a real
child.

So the transport is a double: it replays canned replies in order and records
what the client wrote, which is exactly what makes the approval denial below
inspectable.

Run it::

    .venv/bin/python catalog/protocols/mcp_client/examples/quickstart.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# The catalog convention: a consumer adds catalog/<category>/ to sys.path and
# imports the package by name (see pyproject.toml's ruff notes). This keeps the
# entry importable without coupling it to this repository's structure.
_CATALOG = Path(__file__).resolve().parents[3]
for _sub in ("tools", "protocols"):
    sys.path.insert(0, str(_CATALOG / _sub))

from mcp_client import (  # noqa: E402
    AllowAllApprovals,
    CallableApprovals,
    MCPClient,
    MCPProtocolError,
    project_tools,
)
from mcp_client.approvals import ApprovalRequest  # noqa: E402
from tool_registry import ToolId, ToolRegistry  # noqa: E402


class ScriptedTransport:
    """An in-memory ``Transport`` that replies from a queue.

    Implements the protocol from *outside* the package, which is the point: it
    proves the seam is usable without a subprocess, an SDK, or a running server.
    """

    def __init__(self, *replies: str | None) -> None:
        self._replies = list(replies)
        self.sent: list[bytes] = []
        self._dead = False

    def send(self, line: bytes) -> None:
        self.sent.append(line)

    # `timeout` is part of the Transport protocol. A scripted double answers
    # immediately, so it has nothing to time out on -- but the parameter has to
    # stay for the class to satisfy the protocol structurally.
    def receive(self, timeout: float) -> bytes | None:  # noqa: ARG002
        if not self._replies:
            return None
        reply = self._replies.pop(0)
        return None if reply is None else reply.encode("utf-8")

    def stderr_tail(self) -> str:
        return ""

    def close(self, *, grace: float) -> None:
        pass

    def died(self) -> bool:
        return self._dead


def response(request_id: int, result: dict[str, Any]) -> str:
    """A JSON-RPC success reply as one line."""
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result})


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> int:
    # ------------------------------------------------------------------ #
    rule("1. The handshake, and the era this client speaks")

    transport = ScriptedTransport(
        response(
            1,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "demo-server", "version": "1.0"},
            },
        ),
        # The listing: id 2, because initialize took id 1.
        response(
            2,
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo the given text.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                        },
                    },
                    {
                        # Uppercase: legal in MCP, not representable as a
                        # ToolId name. Excluded, not downcased.
                        "name": "GetWeather",
                        "description": "A tool this registry cannot hold.",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        ),
        # The echo call.
        response(3, {"content": [{"type": "text", "text": "echo:hello"}]}),
    )
    client = MCPClient(transport, namespace="demo", approvals=AllowAllApprovals())
    client.initialize()

    print(f"negotiated protocol version : {client.protocol_version}")
    print(f"server self-report          : {client.server_info}")
    print("  ^ informational only. The spec warns serverInfo is neither unique")
    print("    nor trustworthy, so it never becomes an identifier.")

    sent = json.loads(transport.sent[0])
    print(f"\nhandshake method            : {sent['method']}")
    print(f"client capabilities declared: {sent['params']['capabilities']}")
    print("  ^ empty on purpose. Declaring a capability we do not implement")
    print("    would invite the server to use it.")

    # ------------------------------------------------------------------ #
    rule("2. Projection — and what gets excluded, with the reason")

    registry = ToolRegistry()
    report = project_tools(client, registry)

    print(f"registered: {[str(i) for i in report.registered]}")
    print(f"excluded  : {report.excluded_count}")
    for entry in report.excluded:
        print(f"  - {entry.name}: {entry.reason}")

    print("\n  ^ 'GetWeather' is uppercase. MCP allows that; ToolId does not.")
    print("    Downcasing would let two distinct remote tools collide, so the")
    print("    registry is the authority and the tool is excluded by name.")

    # ------------------------------------------------------------------ #
    rule("3. A projected tool is an ordinary registry tool")

    result = registry.invoke(ToolId("demo", "echo"), {"text": "hello"})
    print(f"invoke ok : {result.ok}")
    print(f"value     : {result.value!r}")

    call_frame = json.loads(transport.sent[2])
    print(f"\nwire method: {call_frame['method']}")
    print(f"wire params: {call_frame['params']}")

    # ------------------------------------------------------------------ #
    rule("4. The approval seam — the default DENIES")

    denying = MCPClient(ScriptedTransport(), namespace="demo")  # no approvals
    outcome = denying.call_tool("dangerous", {"amount": 100})

    print(f"denied?        : {not outcome.ok}")
    print(
        f"model_visible? : {outcome.failure.model_visible if outcome.failure else None}"
    )
    print(f"message        : {outcome.failure.message if outcome.failure else ''}")
    print("\n  ^ Nothing was sent. A refusal that still wrote the frame would")
    print("    be a refusal in name only.")

    # ------------------------------------------------------------------ #
    rule("5. A selective policy reasons about the arguments")

    seen: list[str] = []

    def policy(request: ApprovalRequest) -> bool:
        seen.append(request.tool_name)
        return request.arguments.get("safe") is True

    selective = ScriptedTransport(
        response(1, {"content": [{"type": "text", "text": "ran"}]})
    )
    guarded = MCPClient(
        selective, namespace="demo", approvals=CallableApprovals(policy)
    )

    refused = guarded.call_tool("delete", {"safe": False})
    allowed = guarded.call_tool("read", {"safe": True})

    print(f"policy saw   : {seen}")
    print(f"refused ok?  : {refused.ok}")
    print(f"allowed ok?  : {allowed.ok}")
    print(f"frames sent  : {len(selective.sent)}  (only the permitted one)")

    # ------------------------------------------------------------------ #
    rule("6. A mismatch fails loudly: the modern era is not implemented")

    modern = ScriptedTransport(
        response(
            1,
            {
                "protocolVersion": "2026-07-28",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "modern", "version": "2.0"},
            },
        )
    )
    try:
        MCPClient(modern, namespace="demo").initialize()
    except MCPProtocolError as exc:
        print(f"MCPProtocolError: {exc}")
        print("\n  ^ The spec says a modern/legacy mismatch FAILS rather than")
        print("    degrades, so it is a named error and is not retried.")

    rule("Done — no network, no server process, no third-party package.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
