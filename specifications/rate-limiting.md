# Specification: `rate-limiting`

- **Capability id:** `rate-limiting`
- **Name:** Rate Limiting & Retry Infrastructure
- **Lifecycle status:** `DECIDED` — **DEFER** ([ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md), [DW-017](../docs/DEFERRED.md))
- **Date:** 2026-10-16

> **This is a deferral specification.** It exists because the lifecycle model
> requires a DESIGNED artifact before a DECIDE-stage claim, and because the
> deferral's trigger is only actionable if the design questions are already
> pinned. It deliberately does **not** design interfaces for consumers that
> do not exist (charter §24).

## Problem statement and who needs it

When a remote dependency limits, fails, or degrades, bound the damage to the
caller's budget and deadlines — with a policy, not hope. The consumer is the
first real (network or metered) provider call path. Today no remote calls
exist: `model-provider-abstraction` is protocol-only and every transport
under test is a scripted double, which is why the capability is deferred.

## Interfaces and data flow

**No interfaces are designed at this stage.** When the trigger fires, the
design must answer these questions first:

1. **Ownership** — retry is caller-invoked (per `specifications/basic-rag-pipeline.md`
   D-4), never woven into providers; a provider that retries internally
   cannot be bounded by its caller.
2. **Retry policy** — exponential backoff with jitter, consuming the
   provider error taxonomy's existing `retryable` flags (ADR-0007 D-4);
   what is the retry budget and where does it come from (caller parameter)?
3. **Limiting** — a token-bucket limiter paced per provider quota; what is
   the window source (declared parameter, not a hardcoded vendor table)?
4. **Breaker** — added only after retry and limiting prove insufficient;
   what observable state opens it (consecutive classified failures) and what
   closes it (half-open probe)?

Data flow (sketch, not a design): caller → policy wrapper (limiter → attempt
→ classify → backoff/retry or surface) → provider. Deadlines propagate;
a caller that cannot wait must be able to say so.

## Invariants and failure modes

- Retry decisions consume the provider's error classification
  (`retryable`), never string matching — the taxonomy already exists
  precisely for this.
- Retry is bounded (attempts and/or budget) and jittered; unbounded retry is
  a self-inflicted outage.
- The policy layer never mutates requests: an attempt is the same request,
  byte-for-byte.
- Failure modes to design against: retry amplification across nested layers
  (two layers each retrying 3× is 9 attempts), thundering herd on recovery
  (jitter is the mitigation), and classifying a permanent error as
  retryable (respect the flags).

## Security implications and trust boundaries

No new trust boundary is introduced: requests and keys already crossed the
provider seam. The failure mode specific to this capability is resource
exhaustion (amplified retries, hammering an open breaker), which is
availability rather than confidentiality — bounded budgets and jitter are
the mitigations.

## Dependencies and standards

- `depends_on`: none (the error taxonomy it consumes ships in `model-provider-abstraction`).
- Standards: the Retry-After header (RFC 9110) is the relevant reference for
  throttling signals when a transport surfaces it.

## Testing strategy (§18) and benchmark plan (§19)

When built:

- Policy tests with a controllable clock: backoff intervals, jitter bounds,
  retry budget exhaustion, non-retryable errors surfacing immediately.
- Limiter tests: token accounting over windows, saturation behavior.
- Breaker tests (if built): open on threshold, half-open probe, close.
- Composition test: the composed call path honors caller deadlines.
- Benchmark: measure attempts per failure mode with a failing fake
  transport; wall-clock only against a delayed fake.

## Out of scope

- Provider-internal error handling (ADR-0032 exclusion: surfaced through the
  provider abstraction).
- Cross-process or distributed limiting (single-process scope first).
- Circuit breaker in the first implementation (explicitly last, per ADR-0035).
- Model-output validation (that is `guardrails`, DW-016).

## References

- [Research record](../research/reliability/rate-limiting.md)
- [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [ADR-0032](../docs/decisions/0032-reliability-category.md) — taxonomy category
