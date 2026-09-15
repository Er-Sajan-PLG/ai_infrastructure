# Phase 4 — Compose

**Status:** ⬜ Not started
**Charter basis:** §30 — *"Build integration examples showing how components compose into complete AI systems (System A/B/C from §31). Benchmark composed systems against monolithic frameworks."*
**Depends on:** [Phase 1](phase-1-seed.md) (needs components), [Phase 2](phase-2-study.md) (needs baselines)

## Goal

Prove the components compose — and honestly measure where the independent
implementations are better, worse, simpler, or more constrained than the
monolithic frameworks (charter §19).

## Exit criteria

- [ ] `integrations/` contains three working systems mirroring charter §31:
  - **System A** — partial adoption: our runtime + our memory + external provider + external vector DB
  - **System B** — mixed: external runtime + our harness/eval/safety/observability
  - **System C** — entirely composed from `ai_infrastructure`
- [ ] Each integration has tests and a documented reproduce command
- [ ] Benchmarks exist with recorded methodology and environment (charter §19)
- [ ] Benchmark comparison against ≥2 monolithic frameworks
- [ ] Results report **where we are worse**, not only better
- [ ] No component was modified to make an integration work — that would mean the boundary is wrong

## Method

Build the smallest honest version of each system. Measure correctness, latency,
token usage, cost, recovery behavior, and developer ergonomics. Record the
environment. A benchmark that only confirms the choice already made is not being
run correctly.

## Risks

| Risk | Mitigation |
|---|---|
| Integrations become a framework | Charter §17: components stay independent; composition lives in `integrations/` only |
| Benchmarking is unfair to baselines | Pin versions, record environment, publish methodology |
| Benchmarks gamed toward our design | Publish unfavorable results too (charter §19) |

## Next action

Deferred. Reassess once Phase 1 delivers ≥4 TESTED capabilities.
