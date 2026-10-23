"""Resilient executor combining a limiter and retry policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .limiter import TokenBucket
from .protocols import RetryPolicy, SystemClock, is_retryable, retry


@dataclass(slots=True)
class RateLimitError(Exception):
    """Raised when a limiter cannot grant a token within budget."""

    retryable: bool = True


@dataclass(slots=True)
class ResilientExecutor:
    """Wraps a callable with limiting + retry.

    Limiting is applied before each attempt. Retry honors the policy.
    """

    policy: RetryPolicy = field(default_factory=RetryPolicy)
    limiter: TokenBucket | None = None
    clock: Any = None

    def __post_init__(self) -> None:
        if self.clock is None:
            self.clock = SystemClock()

    def run(self, func: Callable[[], Any]) -> Any:
        def attempt() -> Any:
            if self.limiter is not None and not self.limiter.acquire():
                # Wait for capacity, bounded by policy.max_delay.
                wait = self.limiter.wait_time()
                if wait == float("inf") or wait > self.policy.max_delay:
                    raise RateLimitError()
                # busy-wait using clock is avoided; sleep via policy base.
                import time as _t

                _t.sleep(wait)
                if not self.limiter.acquire():
                    raise RateLimitError()
            return func()

        return retry(
            attempt, self.policy, clock=self.clock, is_retryable_fn=is_retryable
        )
