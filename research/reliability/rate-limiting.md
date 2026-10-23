# Research Record: Rate Limiting & Retry Infrastructure

- **Capability:** `rate-limiting` (category: reliability)
- **Status:** `IMPLEMENTED` — trigger fired (model-gateway TESTED); re-decided from DEFER to IMPLEMENT (ADR-0041)
- **Date:** 2026-10-16
- **Decision:** see [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) *(DEFER, DW-017)*
- **Sources:** [ADR-0032](../../docs/decisions/0032-reliability-category.md), [convergence report](../../docs/discovery/2026-10-08-convergence.md), [ADR-0007](../../docs/decisions/0007-model-provider-abstraction.md), study pipeline reports (`study_pipeline/studied_repos/`)

Claims are labelled per charter §6:
**FACT** (verified, cited) · **OBSERVATION** (inferred from docs/structure) ·
**INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice, not a fact).

---

## 1. Evidence from the study corpus

**FACT.** 6 of 25 studied repositories independently proposed `rate-limiting`
(24%) — named: `SWE-agent`, `dspy`, `haystack`, `langchain`, `langfuse`,
`litellm` ([ADR-0032](../../docs/decisions/0032-reliability-category.md),
[convergence report](../../docs/discovery/2026-10-08-convergence.md)).

**FACT.** The category was adopted with an explicit exclusion: error handling
*within* a model response stays with the provider, surfaced through
`model-provider-abstraction` (ADR-0032). The boundary between the two is
already recorded, which is unusually clean for a converged pattern.

## 2. The problem, stated without reference to any implementation

> When a remote dependency limits, fails, or degrades, bound the damage to
> the caller's budget and deadlines — not with hope, but with a policy.

**DESIGN OPINION.** Every parameter of such a policy (window size, retry
budget, breaker thresholds) is a statement about a specific remote
dependency's observed behaviour. That is the reason this cannot be designed
in the absence of a remote dependency: the numbers would be fiction.

## 3. What was not studied, and why that is acceptable here

**OBSERVATION.** No implementation's backoff curve, limiter algorithm, or
breaker state machine was reviewed in depth.

**INFERENCE.** Not owed for a deferral, and the repository already contains
the decision-relevant facts: the provider error taxonomy carries `retryable`
distinctions precisely so a future policy consumes them
([ADR-0007](../../docs/decisions/0007-model-provider-abstraction.md) D-4),
and `specifications/basic-rag-pipeline.md` D-4 assigns retry responsibility
to the caller. Deep study would inform tuning, not the decision to defer.

**FACT.** No remote calls exist to protect: `model-provider-abstraction` is
protocol-only, every transport and generator exercised in tests is a
scripted double, and the `retryable` flags are consumed by no policy
([DW-017](../../docs/DEFERRED.md)).

## 4. Why the decision is DEFER

See [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) §Decision 5.
Trigger: the first real (network or metered) provider call path, the first
scheduled multi-call workload, or the first live 429/5xx response observed.

**DESIGN OPINION.** When the trigger fires, the order is pinned in
[the specification](../../specifications/rate-limiting.md): retry honoring
the existing flags first, then a token-bucket limiter, then a circuit breaker
only if the first two prove insufficient — all caller-invoked per D-4, never
woven into providers.

## 5. References

- [Specification: rate-limiting](../../specifications/rate-limiting.md)
- [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [DW-017](../../docs/DEFERRED.md) — trigger and reversal
