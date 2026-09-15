"""Consecutive-duplicate detection (ADR-0008 D-5).

The ReAct paper documents repetition as its most common ReAct-specific failure
and ships no mechanism against it; no surveyed framework ships a first-class
duplicate-action detector either.

Honest limitation: this detects consecutive duplicates only. A two-cycle
(A -> B -> A -> B) evades it, because detecting that needs a window and a policy
for what to do on a hit. The README states this rather than implying coverage it
does not have.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from model_provider import ToolCallBlock

__all__ = ["CallSignature", "RepetitionTracker", "canonical_arguments"]


def canonical_arguments(arguments: Mapping[str, Any]) -> str:
    """Render arguments so key order cannot defeat comparison.

    Comparing raw dicts, or their repr, would let a model evade the detector by
    reordering keys. ``default=str`` rather than a raise: the arguments arrived as
    parsed JSON, so an exotic value should not crash the loop.
    """
    return json.dumps(
        dict(arguments), sort_keys=True, separators=(",", ":"), default=str
    )


@dataclass(frozen=True, slots=True)
class CallSignature:
    """The identity of a tool call, ignoring its provider-assigned id."""

    name: str
    canonical_arguments: str

    @classmethod
    def of(cls, call: ToolCallBlock) -> CallSignature:
        """Derive a call's signature.

        The call id is deliberately excluded: providers mint a fresh id per call,
        so including it would make every repeat look novel and the detector would
        never fire.
        """
        return cls(
            name=call.name, canonical_arguments=canonical_arguments(call.arguments)
        )

    def render(self) -> str:
        """A short name(args) form, so a caller need not diff the trace."""
        return f"{self.name}({self.canonical_arguments})"


class RepetitionTracker:
    """Counts consecutive identical calls.

    ``limit`` is how many consecutive identical calls stop the run; ``None``
    disables detection for a workload that legitimately repeats a call.
    """

    def __init__(self, limit: int | None) -> None:
        if limit is not None and limit < 2:
            raise ValueError(
                f"repeat_limit must be at least 2 (or None to disable), got {limit}: "
                "a single call is not a repetition"
            )
        self._limit = limit
        self._last: CallSignature | None = None
        self._count = 0
        self._tripped: CallSignature | None = None

    @property
    def repeat_count(self) -> int:
        """How many consecutive identical calls have been seen."""
        return self._count

    @property
    def tripped(self) -> CallSignature | None:
        """The signature that tripped the detector, for the result's detail."""
        return self._tripped

    def record(self, call: ToolCallBlock) -> bool:
        """Fold one call in; True when the consecutive run reaches the limit.

        The caller must then stop without dispatching this call: the brake exists
        to avoid the work, not to do it once more and notice.
        """
        if self._limit is None:
            return False
        signature = CallSignature.of(call)
        if signature == self._last:
            self._count += 1
        else:
            self._last = signature
            self._count = 1
        if self._count >= self._limit:
            self._tripped = signature
            return True
        return False
