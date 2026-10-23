"""Protocols and helpers for the rate-limiting capability."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


class Clock(Protocol):
    """Monotonic time source for limiters and backoff."""

    def now(self) -> float: ...


class SystemClock:
    """Default clock backed by ``time.monotonic``."""

    def now(self) -> float:
        return time.monotonic()


def is_retryable(exc: BaseException) -> bool:
    """Whether ``exc`` should be retried.

    Consults ``exc.retryable`` when present (the model-provider error taxonomy
    carries this flag, ADR-0007 D-4); otherwise ``False``. Never string-matches.
    """
    value = getattr(exc, "retryable", None)
    if isinstance(value, bool):
        return value
    return False


def retry_after(exc: BaseException) -> float | None:
    """Optional server-suggested delay (Retry-After), if present."""
    value = getattr(exc, "retry_after", None)
    if isinstance(value, (int, float)):
        return float(value)
    return None


@dataclass(slots=True)
class RetryPolicy:
    """Bounded retry with exponential backoff and jitter.

    ``max_attempts`` includes the first attempt. ``jitter`` is a fraction of
    the computed delay added on top (0.0 disables jitter).
    """

    max_attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 10.0
    jitter: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be >= 0")
        if self.max_delay < 0:
            raise ValueError("max_delay must be >= 0")
        if self.jitter < 0:
            raise ValueError("jitter must be >= 0")

    def delay_for(self, attempt: int, rng: Callable[[], float] | None = None) -> float:
        """Delay before retry ``attempt`` (1-indexed attempt that just failed)."""
        if attempt < 1:
            attempt = 1
        raw = self.base_delay * (2 ** (attempt - 1))
        capped = float(min(raw, self.max_delay) if self.max_delay > 0 else raw)
        if self.jitter > 0:
            r = rng() if rng is not None else 0.0
            capped = float(capped * (1.0 + self.jitter * r))
        return float(capped)


def _default_sleep(seconds: float) -> None:
    time.sleep(seconds)


def retry(
    func: Callable[[], Any],
    policy: RetryPolicy,
    *,
    clock: Clock | None = None,
    sleep: Callable[[float], None] | None = None,
    is_retryable_fn: Callable[[BaseException], bool] = is_retryable,
    rng: Callable[[], float] | None = None,
) -> Any:
    """Run ``func`` with bounded retry on retryable exceptions.

    Returns the first successful result. Re-raises the last exception if all
    attempts are exhausted or a non-retryable error occurs. Honors
    ``Retry-After`` when present on the exception.
    """
    if clock is None:
        clock = SystemClock()
    if sleep is None:
        sleep = _default_sleep
    last_exc: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return func()
        except BaseException as exc:
            last_exc = exc
            if attempt >= policy.max_attempts:
                raise
            if not is_retryable_fn(exc):
                raise
            delay = retry_after(exc)
            if delay is None:
                delay = policy.delay_for(attempt, rng)
            if delay > 0:
                sleep(delay)
    # Unreachable: max_attempts >= 1 guarantees the loop runs. pragma: no cover
    if last_exc is not None:  # pragma: no cover
        raise last_exc  # pragma: no cover
    raise RuntimeError("retry: no attempts made")  # pragma: no cover
