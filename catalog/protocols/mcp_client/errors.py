"""Failure taxonomy for the MCP client.

Two families, and the split is the point:

* :class:`MCPError` and its subclasses are **transport and protocol** failures.
  They are raised, never returned. A caller cannot fix a server that writes
  garbage to stdout, and a model cannot fix a broken pipe.
* :class:`MCPToolFailure` is a **tool call that did not produce a value**. It is
  returned in a result, and it carries a
  :class:`~tool_registry.FailureKind` so that the mapping onto the registry's
  taxonomy is explicit rather than reconstructed by every caller.

``-32602`` (invalid params) from ``tools/call`` maps to
``FailureKind.INVALID_ARGUMENTS`` and is model-visible, which is *not* what the
specification says. The divergence is deliberate and recorded in ADR-0009 D-5:
MCP files invalid arguments as a protocol error while our registry treats them as
something the model can act on. The registry's axis is the one that survives
contact with a loop.

See ``specifications/mcp-client.md`` §6 and §7.
"""

from __future__ import annotations

from dataclasses import dataclass

from tool_registry import FailureKind

__all__ = [
    "INTERNAL_ERROR",
    "INVALID_PARAMS",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "PARSE_ERROR",
    "MCPError",
    "MCPProtocolError",
    "MCPServerDiedError",
    "MCPTimeoutError",
    "MCPToolFailure",
    "MCPTransportError",
]

# JSON-RPC 2.0 reserved codes. Identical in both MCP eras (research §5.3).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# The one MCP-specific code this client must still *accept*. `-32002` was
# meaningful in 2025-11-25 and earlier; `2026-07-28` forbids emitting it and
# requires clients to keep accepting it. A client that read only one revision
# would drop this (research §5.3).
LEGACY_RESOURCE_NOT_FOUND = -32002


class MCPError(Exception):
    """Base class for every error this package raises.

    These are transport and protocol failures. They propagate to the caller
    rather than being converted into a tool result, because a loop that swallowed
    a dead server and reported "finished" would be lying.
    """


class MCPTransportError(MCPError):
    """The child process could not be spawned, written to, or read from."""


class MCPProtocolError(MCPError):
    """The peer violated the protocol.

    Raised for a non-JSON stdout line, a response with an unknown ``id``, a
    JSON-RPC envelope missing required members, or a failure during the
    handshake. The session is unusable afterwards and the client terminates it —
    see ADR-0009 D-6 and the three-way implementation divergence that forced the
    choice (research §3.1.2, §12.5).
    """

    def __init__(self, message: str, *, line: str | None = None) -> None:
        super().__init__(message)
        self.line = line


class MCPTimeoutError(MCPError):
    """No response arrived within the request timeout.

    The specification requires timeouts and supplies no number; the default is
    the client's own choice and is documented (ADR-0009 D-7).
    """


class MCPServerDiedError(MCPError):
    """The child exited while a request was outstanding.

    Carries the bounded ``stderr`` tail so a death can be *explained*. The tail
    is diagnostic only: ``stderr`` is never an error signal (ADR-0009 D-10).
    """

    def __init__(
        self, message: str, *, returncode: int | None, stderr_tail: str
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr_tail = stderr_tail


@dataclass(frozen=True, slots=True)
class MCPToolFailure:
    """A ``tools/call`` that did not produce a value.

    Attributes:
        kind: The registry's failure kind. Chosen here so the mapping is decided
            once, in one place, rather than by every caller.
        message: A short, sanitised description safe to place in a prompt.
        tool_name: The remote tool name, as the server reported it.
        code: The JSON-RPC error code, when the failure was a protocol error.
    """

    kind: FailureKind
    message: str
    tool_name: str
    code: int | None = None

    @property
    def model_visible(self) -> bool:
        """Whether a caller may show this failure to a model.

        Delegates to the registry's own rule rather than re-deriving it, so the
        two cannot drift (ADR-0006 D-4).
        """
        return self.kind.model_visible

    def __str__(self) -> str:
        where = f" (code {self.code})" if self.code is not None else ""
        return f"{self.tool_name}: {self.kind.value}{where}: {self.message}"
