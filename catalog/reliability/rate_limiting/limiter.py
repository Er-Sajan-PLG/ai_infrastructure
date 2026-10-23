"""Token-bucket rate limiter for the rate-limiting capability."""

from __future__ import annotations

from dataclasses import dataclass, field

from .protocols import Clock, SystemClock


@dataclass(slots=True)
class TokenBucket:
    """Token bucket paced by a clock.

    ``capacity`` is the max tokens; ``refill_rate`` tokens per second are
    added. ``acquire`` is non-blocking and returns ``True`` if granted.
    """

    capacity: float
    refill_rate: float
    clock: Clock = field(default_factory=SystemClock)
    _tokens: float = field(default=0.0, init=False)
    _last: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be > 0")
        if self.refill_rate < 0:
            raise ValueError("refill_rate must be >= 0")
        self._tokens = self.capacity

    def _refill(self) -> None:
        now = self.clock.now()
        if self._last is None:
            self._last = now
            return
        elapsed = now - self._last
        if elapsed < 0:
            elapsed = 0.0
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last = now

    def available(self) -> float:
        self._refill()
        return self._tokens

    def acquire(self, cost: float = 1.0) -> bool:
        """Try to take ``cost`` tokens. Returns True on success."""
        if cost <= 0:
            return True
        self._refill()
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False

    def wait_time(self, cost: float = 1.0) -> float:
        """Seconds until ``cost`` tokens are available (0 if already)."""
        self._refill()
        if self._tokens >= cost:
            return 0.0
        deficit = cost - self._tokens
        if self.refill_rate <= 0:
            return float("inf")
        return deficit / self.refill_rate
