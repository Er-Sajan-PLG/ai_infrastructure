"""The injectable clock, and why it has two methods.

ADR-0010 D-4: a duration must come from a **monotonic** source, or a wall-clock
adjustment (NTP, a daylight-saving jump, a suspended laptop) can make a duration
negative. A timestamp must be **wall-clock**, or it is meaningless to a human
reading the trace.

Two methods, because they answer different questions — and one method returning
"the time" cannot answer both correctly.

Research §8 is the evidence: six surveyed systems use at least four different
unit conventions, and **MLflow disagrees with itself within one object** (span
times in nanoseconds, trace duration in milliseconds). Injecting the clock is
also what makes every timing assertion in the tests exact rather than tolerant of
a real clock.
"""

from __future__ import annotations

import datetime
import time
from typing import Protocol, runtime_checkable

__all__ = ["Clock", "SystemClock"]


@runtime_checkable
class Clock(Protocol):
    """A source of monotonic durations and wall-clock timestamps."""

    def now_ns(self) -> int:
        """A monotonic reading in nanoseconds, for measuring durations.

        Only differences between two readings are meaningful. The absolute
        value has no relation to wall-clock time.
        """
        ...

    def now_utc(self) -> str:
        """The current wall-clock time as an ISO 8601 string with an offset."""
        ...


class SystemClock:
    """The real clock. Used when a caller does not inject one."""

    __slots__ = ()

    def now_ns(self) -> int:
        """``time.monotonic_ns`` — immune to wall-clock adjustment."""
        return time.monotonic_ns()

    def now_utc(self) -> str:
        """The current UTC time, ISO 8601, with an explicit ``+00:00`` offset.

        ``datetime.UTC`` is passed explicitly rather than using ``utcnow()``,
        so the string carries its offset and cannot be misread as local time.
        """
        return datetime.datetime.now(datetime.UTC).isoformat()

    def __repr__(self) -> str:
        return "SystemClock()"
