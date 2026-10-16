# Specification: `response-cache`

- **Capability id:** `response-cache`
- **Name:** Response Caching
- **Lifecycle status:** `DECIDED` — **DEFER** ([ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md), [DW-015](../docs/DEFERRED.md))
- **Date:** 2026-10-16

> **This is a deferral specification.** It exists because the lifecycle model
> requires a DESIGNED artifact before a DECIDE-stage claim, and because the
> deferral's trigger is only actionable if the design questions are already
> pinned. It deliberately does **not** design interfaces for consumers that
> do not exist (charter §24).

## Problem statement and who needs it

An identical request billed twice is pure waste; a cache keyed on the wrong
inputs silently returns a wrong answer for a different prompt. The consumer
is the first code path making real metered model calls, or the first workload
that repeats an identical request (for example an eval harness re-running the
same prompt). Today no code path makes a metered or remote call at all — every
model interaction under test is a scripted double — which is why the
capability is deferred.

## Interfaces and data flow

**No interfaces are designed at this stage.** When the trigger fires, the
design must answer these questions first:

1. **Key inputs** — which fields of a request can change the answer (model,
   messages, parameters, tool set, system prompt, and what else)? The key is
   a canonical hash of *exactly* that set, plus a namespace version so a
   behavior change invalidates old entries.
2. **Scope and lifetime** — in-process LRU first; TTL as an explicit policy
   parameter, not a default; persistent storage only after cross-process
   repetition is measured.
3. **Observability** — a hit/miss counter so the cache's value is observable,
   not assumed.
4. **Retention boundary** — who may share a cache instance? Cross-tenant
   sharing is a leak; the key derivation cannot repair a wrong sharing
   boundary.

Data flow (sketch, not a design): request → canonical key → lookup →
hit: return cached response / miss: call provider, store, return.

## Invariants and failure modes

- The key includes **every** input that changes the answer; a missing input
  is a correctness bug and a security bug at once (taxonomy security note).
- A cached response is returned only for a request whose canonical key is
  identical — no fuzzy or semantic matching.
- Failure modes to design against: partial key (stale or wrong answer),
  unbounded growth (eviction must exist from day one), and TTL-of-never
  (retention must have an explicit boundary).

## Security implications and trust boundaries

The cache is a data-retention boundary: a prompt cached across tenants leaks
one tenant's content to another. Key derivation is the correctness and the
security property alike. Entries must never be logged with their content, and
the hit/miss counter must carry no payload.

## Dependencies and standards

- `depends_on`: none.
- Standards: none claimed. HTTP cache semantics (RFC 9111) are not adopted —
  this is an in-process request cache, not an HTTP intermediary.

## Testing strategy (§18) and benchmark plan (§19)

When built:

- Correctness tests: same request hits; every single-field variation of a
  request misses (one test per key input — this is the security test).
- Eviction and TTL tests with a controllable clock.
- Counter tests: hits and misses are counted; counter carries no content.
- Benchmark: meaningful only against a counted fake provider — measure hit
  path overhead and avoided provider calls, not wall-clock alone.

## Out of scope

- Semantic/embedding-similarity caching (an evaluation concern, per ADR-0023).
- Persistent or cross-process caches (until measured repetition demands it).
- CDN/HTTP caching and cache invalidation across machines.

## References

- [Research record](../research/caching/response-cache.md)
- [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [ADR-0023](../docs/decisions/0023-caching-taxonomy-category.md) — taxonomy category
