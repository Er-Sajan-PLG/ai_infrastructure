"""Failure taxonomy for the trace recorder.

One error class, and a deliberate asymmetry in how it is used.

:class:`TraceRecorderError` is raised for *programming* errors: an unusable sink,
a call settled twice, a record written after ``close()``. These are bugs in the
caller and they should be loud.

A **write failure mid-run is not one of these.** ADR-0010 D-9 draws the line: a
recorder that raises on a failed write can kill the run it was observing, and one
that swallows the failure loses the evidence silently. So a write failure is
caught, counted, and exposed as :attr:`~.recorder.TraceRecorder.write_failures` —
never raised, never hidden.

See ``specifications/execution-trace-recorder.md`` §8.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["TraceRecorderError", "WriteFailures"]


class TraceRecorderError(Exception):
    """A programming error in how the recorder is used.

    Raised at construction for an unusable sink, and during a run for a
    misuse such as settling one call twice. Never raised for a failed write —
    see the module docstring.
    """


@dataclass(frozen=True, slots=True)
class WriteFailures:
    """What went wrong when writing, accumulated across the run.

    Attributes:
        count: How many records could not be written. Zero means none.
        first_message: The message from the first failure, or ``None`` when
            ``count`` is zero. Kept because the first failure is usually the
            cause; later ones are often the same cause repeating.
    """

    count: int = 0
    first_message: str | None = None

    @property
    def any(self) -> bool:
        """True when at least one record was lost."""
        return self.count > 0

    def __str__(self) -> str:
        if not self.any:
            return "no write failures"
        return f"{self.count} record(s) lost; first: {self.first_message}"
