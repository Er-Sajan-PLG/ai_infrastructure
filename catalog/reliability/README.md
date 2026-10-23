# Reliability

## What it is

Rate limiting, retry with backoff, and resilience patterns for AI API calls.

## Why it exists

Production AI systems must handle rate limits, transient failures, and provider outages gracefully. This category holds the policy machinery that wraps remote calls — caller-invoked, never woven into providers.

## Our implementations

- `rate_limiting/` — token bucket, retry with backoff+jitter, resilient executor (TESTED, ADR-0041).

## References

- ADR-0032 (reliability category), ADR-0035 (deferral), ADR-0041 (implementation).
