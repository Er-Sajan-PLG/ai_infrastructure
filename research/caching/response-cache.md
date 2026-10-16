# Research Record: Response Caching

- **Capability:** `response-cache` (category: caching)
- **Status:** `RESEARCHED` — convergence-level evidence only; no deep per-implementation study (§3 explains why that is sufficient for a deferral)
- **Date:** 2026-10-16
- **Decision:** see [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) *(DEFER, DW-015)*
- **Sources:** [ADR-0023](../../docs/decisions/0023-caching-taxonomy-category.md), [convergence report](../../docs/discovery/2026-10-08-convergence.md), study pipeline reports (`study_pipeline/studied_repos/`), [TAXONOMY.md](../../TAXONOMY.md) §4

Claims are labelled per charter §6:
**FACT** (verified, cited) · **OBSERVATION** (inferred from docs/structure) ·
**INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice, not a fact).

---

## 1. Evidence from the study corpus

**FACT.** 14 of 25 studied repositories proposed `caching`, counted after the
`store` false-positive fix that had inflated the first pass
([ADR-0023](../../docs/decisions/0023-caching-taxonomy-category.md),
[convergence report](../../docs/discovery/2026-10-08-convergence.md)). Named:
`agno`, `autogen`, `crewAI`, `dspy`, `haystack`, plus 9 more.

**OBSERVATION.** Caching in general is ordinary software infrastructure; the
convergence is only meaningful because of its AI-specific form — keying a
cache on prompt + model + parameters to avoid a re-billed API call. ADR-0023
constrains the category to that form and excludes semantic caching as a
quality technique and CDN/HTTP caching.

**OBSERVATION.** The taxonomy entry's security note is the crux: a cache is a
data-retention boundary, so key derivation is simultaneously the correctness
property and the security property.

## 2. The problem, stated without reference to any implementation

> Return a previous result for a repeated request — without ever returning a
> previous result for a *different* request, and without retaining content
> beyond its boundary.

**DESIGN OPINION.** That phrasing makes the hard part explicit: everything
else (eviction, TTL, storage tier) is tuning, while the key definition is
correctness.

## 3. What was not studied, and why that is acceptable here

**OBSERVATION.** This record does not review any implementation's key
derivation, eviction strategy, or persistence format in depth.

**INFERENCE.** That depth is not owed for a deferral, and here it would be
actively misleading: key design depends on what actually varies between
requests to *our* future callers. There are no such callers — no code path in
this repository makes a metered or remote model call; every model interaction
under test is a scripted double, and `integrations/llm_http_transport` is
documented as offline-verified ([DW-015](../../docs/DEFERRED.md)).

## 4. Why the decision is DEFER

See [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) §Decision 2.
The trigger: the first code path making real metered model calls, or the first
workload that repeats an identical request (for example an eval harness
re-running the same prompt).

**DESIGN OPINION.** When the trigger fires, the first design questions are
pinned in [the specification](../../specifications/response-cache.md):
the complete key-input list, the hit/miss observability counter, and the
retention boundary.

## 5. References

- [Specification: response-cache](../../specifications/response-cache.md)
- [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [DW-015](../../docs/DEFERRED.md) — trigger and reversal
