"""Failure taxonomy for the tool registry.

Failures are divided by **whether the model can act on them**, not by severity.
This is the one design rule that OpenAI function calling, LangChain/LangGraph,
and the Model Context Protocol arrived at independently; MCP states the rationale
normatively:

    Any errors that originate from the tool SHOULD be reported inside the result
    object, with ``isError`` set to true, *not* as an MCP protocol-level error
    response. Otherwise, the LLM would not be able to see that an error occurred
    and self-correct.

The registry *records* whether a failure is model-visible. It does not *send*
anything: deciding what enters a prompt remains the caller's job.

See ``specifications/tool-registry.md`` §7.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "DuplicateToolError",
    "FailureKind",
    "InvalidSchemaError",
    "ToolFailure",
    "ToolNotFoundError",
    "ToolRegistryError",
]


class ToolRegistryError(Exception):
    """Base class for every error this package raises.

    These are *programming* errors: a caller registered an invalid schema, or
    asked for a tool that was never registered. They are not failures of a tool
    body (see :class:`ToolFailure`), and they are never model-visible.

    Catching this base class must never accidentally swallow a tool body's own
    exception: tool exceptions are caught at the invocation boundary and
    converted into a :class:`ToolFailure`, and unexpected exceptions from this
    package's own code propagate as themselves (spec §7).
    """


class InvalidSchemaError(ToolRegistryError):
    """A schema is malformed, unsupported, or outside the documented subset.

    Unsupported keywords are rejected **loudly and by name**, never ignored. A
    validator that skips what it does not understand reports ``valid`` for input
    it never checked, which converts an unverified boundary into an
    apparently-verified one (spec §5).
    """


class DuplicateToolError(ToolRegistryError):
    """A tool id is already registered.

    Rejected rather than silently overwriting: last-write-wins would hide a real
    bug behind a plausible-looking result (spec D-8).
    """


class ToolNotFoundError(ToolRegistryError):
    """No tool is registered under the requested id.

    Raised directly by :meth:`ToolRegistry.invoke` for a *local* lookup miss.
    Note the deliberate asymmetry with the failure taxonomy: this is a caller
    bug, so it does not become a model-visible :class:`ToolFailure`.
    """


class FailureKind(StrEnum):
    """Why a tool call failed, and whether a model could act on it."""

    NOT_FOUND = "not_found"
    """No tool with that id is registered.

    A caller bug, or a name a model hallucinated. A hallucinated name cannot be
    corrected by the model that produced it: the model has no view of the
    registry it failed to match against. ``model_visible`` is ``False``.
    """

    INVALID_ARGUMENTS = "invalid_arguments"
    """The arguments violated the tool's schema.

    The model produced these arguments and *can* correct them.
    ``model_visible`` is ``True``.
    """

    EXECUTION_FAILED = "execution_failed"
    """The tool ran and raised.

    The model should be told the action failed, so it does not assume success.
    ``model_visible`` is ``True``.
    """

    @property
    def model_visible(self) -> bool:
        """Whether a caller should show this failure to a model."""
        return self is not FailureKind.NOT_FOUND


@dataclass(frozen=True, slots=True)
class ToolFailure:
    """A tool call that did not produce a value.

    Attributes:
        kind: Why it failed.
        message: A short, sanitised description **safe to place in a prompt**.
            It must not contain stack traces, file paths, environment detail, or
            the representation of an internal exception (spec §7).
        tool_id: The id that was called, as ``namespace:name`` for display.
        cause: The original exception, when a tool body raised. Retained so the
            cause is never masked; it is **not** part of the model-visible
            message.
    """

    kind: FailureKind
    message: str
    tool_id: str
    cause: BaseException | None = None

    @property
    def model_visible(self) -> bool:
        """Whether this failure may be shown to a model."""
        return self.kind.model_visible

    def __str__(self) -> str:
        return f"{self.tool_id}: {self.kind.value}: {self.message}"
