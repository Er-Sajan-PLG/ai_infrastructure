# ADR-0041: Rate Limiting (IMPLEMENT)

**Status:** Accepted
**Date:** 2026-10-23
**Drivers:** Charter §18 (honest evaluation), Phase 5B.4 of the implementation plan, ADR-0007 (model-provider-abstraction), ADR-0032 (reliability category), ADR-0035 (original deferral, DW-017)

## Context

`rate-limiting` was deferred in ADR-0035 (DW-017) because no remote provider
calls existed to protect: `model-provider-abstraction` was protocol-only and
every transport under test was a scripted double. The trigger recorded there —
the first real (network or metered) provider call path — has now fired:
`model-gateway` (ADR-0039) is TESTED and wraps remote provider calls with
fallback chains. The provider error taxonomy already carries `retryable`
distinctions precisely so a future policy consumes them (ADR-0007 D-4), and
`basic-rag-pipeline` D-4 assigns retry responsibility to the caller. The
deferral is therefore lifted and the capability implemented.

## Decision

**IMPLEMENT** a `rate-limiting` capability as a stdlib-only library component:

1. **Protocol-first design** — `Clock` protocol for monotonic time; `is_retryable`
   consults `exc.retryable` (never string-matches).
2. **Token bucket** — `TokenBucket` paced by a clock; non-blocking `acquire`,
   `wait_time` for pacing, `available`.
3. **Retry with backoff + jitter** — `RetryPolicy` (max_attempts, base_delay,
   max_delay, jitter); `retry()` runs a callable, retries on retryable
   exceptions, honors `Retry-After` when present, re-raises on exhaustion or
   non-retryable errors.
4. **Resilient executor** — `ResilientExecutor` combines limiting + retry;
   limiting is applied before each attempt.
5. **Caller-invoked** — per `basic-rag-pipeline` D-4, retry is never woven into
   providers; a provider that retries internally cannot be bounded by its caller.
6. **Zero runtime dependencies** — stdlib only; `time.sleep` is the default sleep
   and is injectable for tests.
7. **Bounded** — retry attempts and limiter waits are capped by `max_delay`;
   unbounded retry is a self-inflicted outage.
8. **Sync-first** — matches the rest of the repository.

## Options Considered

| Option | Verdict | Reason |
|---|---|---|
| Weave retry into providers | Rejected | Cannot be bounded by caller (basic-rag D-4) |
| Circuit breaker now | Deferred | Added only after retry+limiting prove insufficient |
| Async-first | Rejected | Repository is sync-first |

## Consequences

- `catalog/reliability/rate_limiting/` package; `reliability` category added to
  `validate_catalog.py` CATEGORIES.
- `ai_infrastructure` exports the public surface.
- DW-017 resolved.
