"""JSON-RPC 2.0 envelopes, correlation, and the MCP error-code mapping.

Three things live here and nowhere else:

1. **Envelope construction** — request, response, notification. Small, and the
   only place a ``jsonrpc: "2.0"`` string is written.
2. **Correlation** — matching a response to its request by ``id``. An unknown id
   is a protocol violation, not something to skip: silently dropping it would let
   the stream desynchronise, which is the failure mode ADR-0009 D-6 rejects.
3. **The error-code mapping** — the one place ``-32601`` becomes ``NOT_FOUND`` and
   ``-32602`` becomes ``INVALID_ARGUMENTS``. Putting it here rather than in the
   client means the mapping is testable without a server.

The reserved-range handling is deliberately two-sided. ``2026-07-28`` forbids
emitting ``-32002`` and requires clients to keep *accepting* it; this client
emits no MCP-specific codes at all and treats ``-32002`` as "not found" on the
way in (research §5.3).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tool_registry import FailureKind

from .errors import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    LEGACY_RESOURCE_NOT_FOUND,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    MCPProtocolError,
    MCPToolFailure,
)

__all__ = [
    "RequestId",
    "failure_from_error",
    "failure_from_result",
    "is_notification",
    "is_request",
    "is_response",
    "make_error",
    "make_notification",
    "make_request",
    "make_response",
    "validate_envelope",
]

RequestId = int | str

# JSON-RPC error codes we may legitimately *receive* from a server.
_KNOWN_CODES: frozenset[int] = frozenset(
    {
        PARSE_ERROR,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        INVALID_PARAMS,
        INTERNAL_ERROR,
        LEGACY_RESOURCE_NOT_FOUND,
    }
)


def make_request(
    request_id: RequestId, method: str, params: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Build a JSON-RPC request envelope."""
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = dict(params)
    return message


def make_notification(
    method: str, params: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Build a JSON-RPC notification — a request with no ``id``.

    A notification has no response. ``notifications/initialized`` is the one this
    client sends, and getting the absence of ``id`` right is what makes the
    server not reply.
    """
    message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        message["params"] = dict(params)
    return message


def make_response(request_id: RequestId, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC success response."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error(request_id: RequestId, code: int, message: str) -> dict[str, Any]:
    """Build a JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def is_response(message: Mapping[str, Any]) -> bool:
    """True when ``message`` is a response: it has an ``id`` and no ``method``."""
    return "id" in message and "method" not in message


def is_request(message: Mapping[str, Any]) -> bool:
    """True when ``message`` is a request: it has both ``method`` and ``id``."""
    return "method" in message and "id" in message


def is_notification(message: Mapping[str, Any]) -> bool:
    """True when ``message`` is a notification: ``method`` with no ``id``."""
    return "method" in message and "id" not in message


def validate_envelope(message: Mapping[str, Any]) -> None:
    """Raise when a message is not a well-formed JSON-RPC 2.0 envelope."""
    if message.get("jsonrpc") != "2.0":
        raise MCPProtocolError(
            "message is missing jsonrpc='2.0'", line=str(message)[:200]
        )
    if "method" not in message and "id" not in message:
        raise MCPProtocolError(
            "message is neither a request, a notification, nor a response",
            line=str(message)[:200],
        )


def failure_from_error(tool_name: str, error: Mapping[str, Any]) -> MCPToolFailure:
    """Map a JSON-RPC error to a tool failure, by model-actionability.

    The mapping is ADR-0009 D-5 and it is the registry's axis, not JSON-RPC's:

    ==========================================  ====================  ==============
    Code                                        Kind                  Model-visible?
    ==========================================  ====================  ==============
    ``-32601`` method not found (unknown tool)   ``NOT_FOUND``         no
    ``-32002`` legacy resource not found         ``NOT_FOUND``         no
    ``-32602`` invalid params                    ``INVALID_ARGUMENTS`` **yes**
    anything else                                ``EXECUTION_FAILED``  yes
    ==========================================  ====================  ==============

    The ``-32602`` row is the divergence the ADR records: MCP files invalid
    arguments as a protocol error, we treat them as something the model can fix.
    """
    raw_code = error.get("code")
    code = raw_code if isinstance(raw_code, int) else None
    message = str(error.get("message", "unknown error"))

    if code in (METHOD_NOT_FOUND, LEGACY_RESOURCE_NOT_FOUND):
        kind = FailureKind.NOT_FOUND
    elif code == INVALID_PARAMS:
        kind = FailureKind.INVALID_ARGUMENTS
    else:
        kind = FailureKind.EXECUTION_FAILED

    return MCPToolFailure(kind=kind, message=message, tool_name=tool_name, code=code)


def failure_from_result(
    tool_name: str, result: Mapping[str, Any]
) -> MCPToolFailure | None:
    """Return a failure when a ``tools/call`` result sets ``isError``.

    ``None`` means the call succeeded. The specification is explicit that tool
    errors belong *inside* the result — *"otherwise the LLM would not be able to
    see that an error occurred and self-correct"* — so this is the model-visible
    path, and ``EXECUTION_FAILED`` is the kind for exactly that reason.
    """
    if not result.get("isError", False):
        return None

    text = _extract_text(result)
    return MCPToolFailure(
        kind=FailureKind.EXECUTION_FAILED,
        message=text or "the tool reported an error",
        tool_name=tool_name,
    )


def _extract_text(result: Mapping[str, Any]) -> str:
    """Join the text of every ``text`` content block in a result.

    Only ``text`` blocks contribute. An image or audio block has no string form
    worth placing in a prompt, and inventing one would put bytes where the model
    expects words.
    """
    blocks = result.get("content")
    if not isinstance(blocks, list):
        return ""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, Mapping) and block.get("type") == "text":
            value = block.get("text")
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)
