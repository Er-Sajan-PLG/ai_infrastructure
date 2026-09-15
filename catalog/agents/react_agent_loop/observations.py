"""Observation bounding (ADR-0008 D-6).

Nothing in the surveyed implementations bounds an observation inside the loop,
and unbounded growth ends in an opaque provider ``ContextLengthError``. Bounding
on arrival converts that into a bounded, visible outcome.

Head-and-tail is chosen because tool output is informative at both ends, and the
marker makes the loss visible rather than silent. The loop does not summarise:
that needs a model call and an anti-injection posture.
"""

from __future__ import annotations

__all__ = ["TOTAL_BUDGET_MARKER", "bound_observation"]

TOTAL_BUDGET_MARKER = "[observation omitted: total observation budget exhausted]"


def bound_observation(text: str, limit: int) -> tuple[str, int]:
    """Bound text to limit characters, keeping the head and the tail.

    Returns (bounded, original_length) so the step trace can record how much was
    dropped; a truncation the caller cannot see is a silent loss.

    The marker is not counted against the limit, matching the spec's worked
    example. A string at or under the limit is returned unchanged.
    """
    if limit < 1:
        raise ValueError(f"limit must be positive, got {limit}")
    if len(text) <= limit:
        return text, len(text)
    head = limit // 2
    tail = limit - head
    removed = len(text) - head - tail
    marker = f"\n... [truncated {removed} of {len(text)} characters] ...\n"
    return text[:head] + marker + text[-tail:], len(text)
