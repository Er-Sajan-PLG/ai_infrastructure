# Phase 4 — Compose

**Status:** 🟨 In progress (Systems A/B/C landed 2026-10-09 via PRs #8–#10; benchmark + first baseline via PR #11; one exit criterion open — comparison against ≥2 monolithic baselines, tracked as WP3 of session OC1)
**Charter basis:** §30 — *"Integration examples; benchmark composed systems against monolithic frameworks."* (The System A/B/C sketches are this plan's own design.)
**Depends on:** [Phase 1](phase-1-seed.md) (needs components), [Phase 2](phase-2-study.md) (needs baselines)

## Goal

Prove the components compose — and honestly measure where the independent
implementations are better, worse, simpler, or more constrained than the
monolithic frameworks (charter §19).

## Exit criteria

- [x] `integrations/` contains three working systems mirroring charter §31:
  - **System A** — partial adoption: our runtime + our memory + external provider + external vector DB — `integrations/system_a_partial/`
  - **System B** — mixed: external runtime + our harness/eval/safety/observability — `integrations/system_b_mixed/`
  - **System C** — entirely composed from `ai_infrastructure` — `integrations/system_c_internal/`
- [x] Each integration has tests and a documented reproduce command (per-integration READMEs; suite green in `make check`)
- [x] Benchmarks exist with recorded methodology and environment (charter §19) — `benchmarks/README.md` (methodology) + `benchmarks/results.md` (recorded run)
- [ ] Benchmark comparison against ≥2 monolithic frameworks — 1 of 2 present (hand-written monolithic baseline); second baseline pending (WP3, session OC1)
- [x] Results report **where we are worse**, not only better — see "Where the composed system loses" in `benchmarks/results.md`
- [x] No component was modified to make an integration work — that would mean the boundary is wrong (verified: integration PRs #8–#10 touched `integrations/` only)

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
