# Rate Limiting

> **Status: `TESTED`.** Token bucket, retry with backoff + jitter, resilient executor. Zero runtime dependencies — standard library only. Caller-invoked; never woven into providers.

## What it is

Policy machinery for bounding damage when a remote dependency limits, fails, or degrades: a token bucket for pacing, bounded retry with exponential backoff and jitter, and a resilient executor combining both. Retry decisions consume a caller-supplied `retryable` predicate (defaults to the provider error taxonomy's `retryable` flag, ADR-0007 D-4).

## How it works

```python
from rate_limiting import RetryPolicy, TokenBucket, ResilientExecutor

policy = RetryPolicy(max_attempts=3, base_delay=0.1, jitter=0.25)
bucket = TokenBucket(capacity=10, refill_rate=5)
executor = ResilientExecutor(policy=policy, limiter=bucket)
result = executor.run(lambda: call_provider())
```

## Our implementations

- `catalog/reliability/rate_limiting/` — TokenBucket, RetryPolicy, ResilientExecutor, Clock protocols.

## References

- ADR-0032 (reliability category), ADR-0035 (original deferral, DW-017), ADR-0041 (implementation).
