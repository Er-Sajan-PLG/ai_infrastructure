"""The one failure the loop itself raises.

Deliberately tiny: the loop classifies *outcomes* (three stop reasons) and
*propagates* failures. It does not invent a failure taxonomy.

This module closes a gap between ADR-0008 and its specification, found while
implementing:

* D-9 says a failure the model cannot act on must stop the loop rather than being
  fed back as an observation.
* D-2 and the spec's section 6 say the stop-reason set is exactly three values:
  FINAL_ANSWER, STEP_LIMIT, REPEATED_ACTION.
* The spec's definition of done says "all three stop reasons reachable and
  tested".

A fourth stop reason would contradict D-2 and falsify the definition of done; a
non-model-visible failure silently swallowed would contradict D-9. Raising
satisfies both: the loop stops, and the closed set stays closed.

The layer below already says the same thing. ToolNotFoundError's docstring is
explicit that a hallucinated name "is a caller bug, so it does not become a
model-visible ToolFailure", and D-2's design note says failures propagate as
exceptions. Both agree independently; the loop obeys them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from model_provider import Message

    from .loop import Step

__all__ = ["UnactionableToolError"]


class UnactionableToolError(RuntimeError):
    """A tool failed in a way the model cannot act on.

    The caller's remedy is to fix the wiring, not to re-prompt the model: the
    model has no view of the registry it failed to match against, so showing it
    the failure would only invite a second hallucination of the same name.

    Attributes:
        tool_id: The tool that failed, as the dispatcher named it.
        kind: The dispatcher's short label, e.g. "not_found".
        steps: The trace up to and including the failing dispatch. Attached
            because the trace is the useful artefact even on this path; a raise
            that discarded it would throw away the run's evidence.
        messages: The conversation at the point of failure, for the same reason.
    """

    def __init__(
        self,
        *,
        tool_id: str,
        kind: str,
        message: str,
        steps: tuple[Step, ...] = (),
        messages: tuple[Message, ...] = (),
    ) -> None:
        super().__init__(message)
        self.tool_id = tool_id
        self.kind = kind
        self.steps = steps
        self.messages = messages

    def __str__(self) -> str:
        return f"unactionable tool failure [{self.kind}] on {self.tool_id!r}"

    def detail(self) -> dict[str, Any]:
        """A small, JSON-safe summary for logging.

        Deliberately does not dump messages or steps: the caller already holds
        them, and serialising a transcript into a log line is how prompts end up
        in log aggregation.
        """
        return {
            "tool_id": self.tool_id,
            "kind": self.kind,
            "steps": len(self.steps),
            "messages": len(self.messages),
        }
