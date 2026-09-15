"""MCP Client (stdio transport).

Connect to an MCP server over stdio, list its tools, call them, and project the
results into the local tool registry — with an approval decision taken **before**
any call is dispatched.

This is the first capability whose subject is another system's protocol. It
implements the **legacy** era (`initialize` handshake, revision `2025-06-18` and
earlier), because the installed base is legacy and the specification's
compatibility matrix says a modern client against a legacy server fails rather
than degrades (ADR-0009 D-1).

Zero runtime dependencies — standard library only::

    from mcp_client import AllowAllApprovals, MCPClient, project_tools
    from tool_registry import ToolRegistry

    registry = ToolRegistry()
    client = MCPClient.from_command(
        "python", ["-m", "some_mcp_server"], namespace="remote",
        approvals=AllowAllApprovals(),   # the decision is spelled out
    )
    try:
        client.initialize()
        report = project_tools(client, registry)
        print(report.registered_count, "registered;", report.excluded_count, "excluded")
    finally:
        client.close()

``approvals=None`` — the default — **denies every call**. The seam exists so a
caller can decide; it does not decide for them.

See ``specifications/mcp-client.md`` for the design and
``docs/decisions/0009-mcp-client.md`` for the decision.
"""

from __future__ import annotations

from .approvals import (
    AllowAllApprovals,
    ApprovalPolicy,
    ApprovalRequest,
    CallableApprovals,
    DenyAllApprovals,
)
from .client import (
    CLIENT_NAME,
    CLIENT_VERSION,
    LEGACY_PROTOCOL_VERSION,
    LEGACY_PROTOCOL_VERSIONS,
    MCPClient,
    ToolCallOutcome,
    ToolDescriptorView,
)
from .errors import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    LEGACY_RESOURCE_NOT_FOUND,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    MCPError,
    MCPProtocolError,
    MCPServerDiedError,
    MCPTimeoutError,
    MCPToolFailure,
    MCPTransportError,
)
from .framing import decode_message, encode_message
from .projection import (
    ExcludedTool,
    ProjectionReport,
    is_legal_tool_name,
    project_tools,
)
from .transport import STDERR_RING_BYTES, StdioTransport, Transport

__all__ = [
    "CLIENT_NAME",
    "CLIENT_VERSION",
    "INTERNAL_ERROR",
    "INVALID_PARAMS",
    "INVALID_REQUEST",
    "LEGACY_PROTOCOL_VERSION",
    "LEGACY_PROTOCOL_VERSIONS",
    "LEGACY_RESOURCE_NOT_FOUND",
    "METHOD_NOT_FOUND",
    "PARSE_ERROR",
    "STDERR_RING_BYTES",
    "AllowAllApprovals",
    # approvals
    "ApprovalPolicy",
    "ApprovalRequest",
    "CallableApprovals",
    "DenyAllApprovals",
    # projection
    "ExcludedTool",
    # client
    "MCPClient",
    # errors
    "MCPError",
    "MCPProtocolError",
    "MCPServerDiedError",
    "MCPTimeoutError",
    "MCPToolFailure",
    "MCPTransportError",
    "ProjectionReport",
    # transport
    "StdioTransport",
    "ToolCallOutcome",
    "ToolDescriptorView",
    "Transport",
    "decode_message",
    # framing
    "encode_message",
    "is_legal_tool_name",
    "project_tools",
]
