"""Tests for the Rate Limiting capability."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

_catalog_root = Path(__file__).resolve().parents[3]
for _cat in (
    "tools",
    "models",
    "agents",
    "observability",
    "protocols",
    "deployment",
    "memory",
    "retrieval",
    "evaluation",
    "guardrails",
    "reliability",
):
    _p = str(_catalog_root / _cat)
    sys.path.insert(0, _p)

import pytest  # noqa: E402
from rate_limiting import (  # noqa: E402
    RateLimitError,
    ResilientExecutor,
    RetryPolicy,
    SystemClock,
    TokenBucket,
    is_retryable,
    retry,
    retry_after,
)
from rate_limiting.protocols import _default_sleep  # noqa: E402


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_retry_policy_validates() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay=-1)
    with pytest.raises(ValueError):
        RetryPolicy(max_delay=-1)
    with pytest.raises(ValueError):
        RetryPolicy(jitter=-1)


def test_retry_policy_backoff() -> None:
    p = RetryPolicy(base_delay=0.1, max_delay=1.0, jitter=0.0)
    assert p.delay_for(1) == pytest.approx(0.1)
    assert p.delay_for(2) == pytest.approx(0.2)
    assert p.delay_for(10) == pytest.approx(1.0)


def test_retry_policy_jitter() -> None:
    p = RetryPolicy(base_delay=1.0, jitter=0.5)
    assert p.delay_for(1, rng=lambda: 1.0) == pytest.approx(1.5)


def test_retry_success_first_try() -> None:
    calls = {"n": 0}

    def f() -> str:
        calls["n"] += 1
        return "ok"

    assert retry(f, RetryPolicy()) == "ok"
    assert calls["n"] == 1


def test_retry_retries_then_succeeds() -> None:
    calls = {"n": 0}

    class RetryableError(Exception):
        retryable = True

    def f() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RetryableError("boom")
        return "ok"

    assert retry(f, RetryPolicy(max_attempts=3, base_delay=0, jitter=0)) == "ok"
    assert calls["n"] == 3


def test_retry_non_retryable_raises() -> None:
    class PermanentError(Exception):
        retryable = False

    def f() -> str:
        raise PermanentError("nope")

    with pytest.raises(PermanentError):
        retry(f, RetryPolicy(max_attempts=3, base_delay=0))


def test_retry_exhausted_raises() -> None:
    class RetryableError(Exception):
        retryable = True

    def f() -> str:
        raise RetryableError("boom")

    with pytest.raises(RetryableError):
        retry(f, RetryPolicy(max_attempts=2, base_delay=0))


def test_retry_honors_retry_after() -> None:
    slept: list[float] = []

    class RetryableError(Exception):
        retryable = True
        retry_after = 2.5

    calls = {"n": 0}

    def f() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RetryableError("boom")
        return "ok"

    assert (
        retry(f, RetryPolicy(max_attempts=2, base_delay=0), sleep=slept.append) == "ok"
    )
    assert slept == [2.5]


def test_retry_no_attempts_unreachable() -> None:
    # max_attempts >=1 always; sanity.
    assert RetryPolicy(max_attempts=1).max_attempts == 1


def test_is_retryable() -> None:
    class RError(Exception):
        retryable = True

    class PError(Exception):
        retryable = False

    class NError(Exception):
        pass

    assert is_retryable(RError()) is True
    assert is_retryable(PError()) is False
    assert is_retryable(NError()) is False


def test_retry_after_helper() -> None:
    class EError(Exception):
        retry_after = 1.5

    class FError(Exception):
        pass

    assert retry_after(EError()) == 1.5
    assert retry_after(FError()) is None


def test_token_bucket_acquire() -> None:
    clock = FakeClock(0.0)
    b = TokenBucket(capacity=2, refill_rate=1.0, clock=clock)
    assert b.acquire() is True
    assert b.acquire() is True
    assert b.acquire() is False


def test_token_bucket_refill() -> None:
    clock = FakeClock(0.0)
    b = TokenBucket(capacity=2, refill_rate=1.0, clock=clock)
    b.acquire()
    b.acquire()
    clock.advance(2.0)
    assert b.acquire() is True


def test_token_bucket_validation() -> None:
    with pytest.raises(ValueError):
        TokenBucket(capacity=0, refill_rate=1.0)
    with pytest.raises(ValueError):
        TokenBucket(capacity=1, refill_rate=-1)


def test_token_bucket_available_and_wait_time() -> None:
    clock = FakeClock(0.0)
    b = TokenBucket(capacity=2, refill_rate=1.0, clock=clock)
    b.acquire()
    b.acquire()
    assert b.available() == 0
    assert b.wait_time() == pytest.approx(1.0)
    assert b.wait_time(0) == 0.0


def test_token_bucket_acquire_zero_cost() -> None:
    b = TokenBucket(capacity=1, refill_rate=1.0, clock=FakeClock())
    assert b.acquire(0) is True


def test_token_bucket_wait_time_inf() -> None:
    clock = FakeClock(0.0)
    b = TokenBucket(capacity=2, refill_rate=0.0, clock=clock)
    b.acquire()
    b.acquire()
    assert b.wait_time() == float("inf")


def test_resilient_executor_runs() -> None:
    clock = FakeClock(0.0)
    bucket = TokenBucket(capacity=10, refill_rate=10.0, clock=clock)
    executor = ResilientExecutor(
        policy=RetryPolicy(max_attempts=1, base_delay=0), limiter=bucket, clock=clock
    )
    assert executor.run(lambda: "ok") == "ok"


def test_resilient_executor_no_limiter() -> None:
    executor = ResilientExecutor(policy=RetryPolicy(max_attempts=1, base_delay=0))
    assert executor.run(lambda: 42) == 42


def test_resilient_executor_rate_limit_error() -> None:
    clock = FakeClock(0.0)
    bucket = TokenBucket(capacity=1, refill_rate=0.0, clock=clock)
    bucket.acquire()  # exhaust
    executor = ResilientExecutor(
        policy=RetryPolicy(max_attempts=1, base_delay=0, max_delay=0),
        limiter=bucket,
        clock=clock,
    )
    with pytest.raises(RateLimitError):
        executor.run(lambda: "ok")


def test_default_sleep_zero() -> None:
    _default_sleep(0)


def test_retry_delay_for_zero_attempt() -> None:
    p = RetryPolicy(base_delay=0.1, jitter=0.0)
    assert p.delay_for(0) == pytest.approx(0.1)


def test_token_bucket_clock_backwards() -> None:
    class BackwardsClock:
        def __init__(self) -> None:
            self.t = 5.0

        def now(self) -> float:
            return self.t

    clock = BackwardsClock()
    b = TokenBucket(capacity=2, refill_rate=1.0, clock=clock)
    b._last = 10.0  # force backwards
    clock.t = 5.0
    # _refill should clamp elapsed to 0
    assert b.available() >= 0


def test_resilient_executor_rate_limit_wait_exceeds() -> None:
    # capacity 0 impossible (must >0); use refill 0 and exhausted bucket with max_delay 0
    clock = FakeClock(0.0)
    bucket = TokenBucket(capacity=1, refill_rate=0.0, clock=clock)
    bucket.acquire()
    executor = ResilientExecutor(
        policy=RetryPolicy(max_attempts=1, base_delay=0, max_delay=0),
        limiter=bucket,
        clock=clock,
    )
    with pytest.raises(RateLimitError):
        executor.run(lambda: "ok")


def test_resilient_executor_rate_limit_retry_acquire_fails() -> None:
    clock = FakeClock(0.0)
    bucket = TokenBucket(capacity=1, refill_rate=100.0, clock=clock)
    bucket.acquire()
    executor = ResilientExecutor(
        policy=RetryPolicy(max_attempts=1, base_delay=0, max_delay=5),
        limiter=bucket,
        clock=clock,
    )
    with pytest.raises(RateLimitError):
        executor.run(lambda: "ok")


def test_system_clock() -> None:
    c = SystemClock()
    assert c.now() >= 0


def test_resilient_executor_waits_and_succeeds() -> None:
    bucket = TokenBucket(capacity=1, refill_rate=100.0)  # SystemClock
    bucket.acquire()  # exhaust
    executor = ResilientExecutor(
        policy=RetryPolicy(max_attempts=1, base_delay=0, max_delay=5), limiter=bucket
    )
    assert executor.run(lambda: "ok") == "ok"


def test_resilient_executor_retryable_rate_limit() -> None:
    # RateLimitError is retryable by default (retryable=True)
    assert RateLimitError().retryable is True
