"""Newline-delimited JSON framing for MCP over a byte stream.

The specification states the rule as a **prohibition**, not an encoding:

    Messages are delimited by newlines, and MUST NOT contain embedded newlines.

That sentence is byte-identical in both MCP eras (research §3.1.1), which is why
this module is the safe place to start: its correctness does not depend on the
era decision.

JSON *permits* a literal newline inside a string, so an encoder that
pretty-prints, or a ``default`` callback returning a string containing a newline,
corrupts the stream silently. This module therefore serialises compactly **and
asserts the result is newline-free**, rather than assuming it. Asserting is the
whole point: a check that runs is worth more than a convention that is documented.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .errors import MCPProtocolError

__all__ = ["MAX_LINE_BYTES", "decode_message", "encode_message"]

# A single framed line is bounded. The specification gives no limit; this is the
# client's own guard against a server that never emits a newline. It is a
# transport-level protection, not a protocol value, and it is documented as ours
# (ADR-0009 D-7's pattern: state the numbers we chose).
MAX_LINE_BYTES = 10 * 1024 * 1024


def encode_message(message: Mapping[str, Any]) -> bytes:
    """Serialise one JSON-RPC message to a single newline-terminated line.

    Args:
        message: The JSON-RPC envelope. Must be JSON-serialisable as-is.

    Returns:
        The encoded line, including the trailing ``b"\\n"``.

    Raises:
        MCPProtocolError: The encoded body contains a newline or carriage return.
            This is not defensive padding: pretty-printing, or a ``default``
            hook that stringifies an object with a newline in it, produces exactly
            this and would otherwise split one message into two frames.
    """
    # Compact separators and no `indent`. Python's default `(', ', ': ')` is
    # harmless but wasteful here; `indent=` is the real hazard.
    body = json.dumps(message, separators=(",", ":"), ensure_ascii=False)

    if "\n" in body or "\r" in body:
        raise MCPProtocolError(
            "encoded message contains an embedded newline or carriage return; "
            "one JSON-RPC message must be exactly one line"
        )

    encoded = body.encode("utf-8")
    if len(encoded) > MAX_LINE_BYTES:
        raise MCPProtocolError(
            f"encoded message is {len(encoded)} bytes, over the "
            f"{MAX_LINE_BYTES}-byte line bound"
        )
    return encoded + b"\n"


def decode_message(line: bytes) -> dict[str, Any]:
    """Parse one framed line into a JSON-RPC message.

    Args:
        line: A line *without* the trailing newline, as read from the stream.

    Returns:
        The parsed message.

    Raises:
        MCPProtocolError: The line is not valid UTF-8, not valid JSON, or not a
            JSON object. Any of these means the peer wrote something that is not
            an MCP message to stdout, which the specification forbids on the
            server side and does not address on the client side (research
            §3.1.2). This client terminates the session; see ADR-0009 D-6.
    """
    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MCPProtocolError(
            "stdout line is not valid UTF-8", line=line[:200].decode("latin-1")
        ) from exc

    try:
        message = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MCPProtocolError(
            "stdout line is not valid JSON", line=text[:200]
        ) from exc

    if not isinstance(message, dict):
        raise MCPProtocolError(
            f"JSON-RPC message must be an object, got {type(message).__name__}",
            line=text[:200],
        )
    return message
