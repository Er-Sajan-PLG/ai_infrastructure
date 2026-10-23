"""Quickstart demonstration of the Rate Limiting capability."""

from __future__ import annotations

from rate_limiting import ResilientExecutor, RetryPolicy, TokenBucket


def main() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay=0.1, jitter=0.25)
    bucket = TokenBucket(capacity=5, refill_rate=2.0)
    executor = ResilientExecutor(policy=policy, limiter=bucket)

    def call() -> str:
        return "ok"

    print(executor.run(call))


if __name__ == "__main__":
    main()
