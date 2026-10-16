# DASHBOARD — Executive Summary

> **Last Reconciled:** 2026-10-16 (session OC1 — WP1 gate parity fix on `master` (`248f618`); phase docs, roadmap, STATE.md and this dashboard reconciled with git reality after the 2026-10-09 Phase 3/4 merge train; `make check` 1284 passed, `make status` green)
> **Protocol:** MACP (Multi-Agent Coordination Protocol)

---

## Project: ai_infrastructure

An independent AI infrastructure laboratory — research repository, architectural knowledge base, implementation library, interoperability layer, evaluation environment, and reusable engineering foundation for AI systems.

## Current Status

| Field | Value |
|---|---|
| **Phase** | Phase 4 (Compose) in progress — Systems A/B/C + benchmark landed; second monolithic baseline open. Phase 3 closed. |
| **Branch** | `master` (remote CI green at `397fd5e`; local ahead: `248f618` parity fix + OC1 reconciliation) |
| **Tests** | 1284 passing, 3 deselected (verified via `make check`, 2026-10-16) |
| **Coverage** | ≥85% floor enforced, green |
| **ADRs** | 34 (0000–0033 contiguous, counted from disk) |
| **Capabilities** | 7 TESTED, 6 DISCOVERED (verified via `make status`) |
| **Runtime deps** | Zero (stdlib only) |

## Active Agents

| Agent ID | Model | Branch | Task | Status |
|---|---|---|---|---|
| OC1 | opencode session | `master` | Complete in-flight work + repository reconciliation (WP1–7) | Active — see [`sessions/20261016-0755-OC1-complete-repository.md`](sessions/20261016-0755-OC1-complete-repository.md) |

## Critical Alerts

- The parity bug fixed in `248f618` was the class CI cannot see: `check-strict` (what CI runs) was missing `check_integrations` (reachable from `make check`), so master was red locally and green remotely. A regression test now asserts every checker reachable from `make check` is reachable from `check-strict`.
- Dependabot PRs #1 (actions) and #3 (dev toolchain, 14 updates) are open and green — left for the maintainer to merge.
- Six `DISCOVERED` capabilities have no adoption decision yet (review docs exist); Phase 4's ≥2-baseline exit criterion is 1 short.

## Recently Completed

- `make check` ↔ `check-strict` parity gap closed — master was red on `check_integrations` while remote CI stayed green; regression test added (`248f618`, 2026-10-16)
- Test hygiene: study-pipeline review test and three System B tests wrote artifacts into the repo tree; both now use `tmp_path` (2026-10-16)
- Reconciled phase docs/roadmap/state with reality: phase 1.5/3 statuses, missing `make deprecations` target added, charter's stale "Current phase" stamp replaced (2026-10-16)
- `vector-memory-store` → TESTED (ADR-0033; `catalog/memory/vector_store/`; 7th capability) — merged 2026-10-09 (PR #7)
- Phase 4 Systems A/B/C in `integrations/` (PRs #8–#10, 2026-10-09); benchmark harness + first monolithic baseline (`benchmarks/results.md`, PR #11)
- Phase 3 — Discover closed: convergence detection, review workflow, deprecation flagging; `guardrails` + `reliability` categories adopted (ADR-0031/0032)
- MACP protocol bootstrapped + trial-run (`state/`, AGENTS.md, STATE.md)
- `infrastructure-scanner` completed to TESTED (spec, research, ADR-0029)
- Repo-wide mypy repaired (226→0 errors; 313 suppressions removed)
- Study-pipeline stack/dependency extraction; integration consistency checker
- MACP amendments P1–P6 implemented (`docs/macp-protocol.md` canonical + `docs/macp-protocol-review.md` rationale, AGENTS.md repointed; P7 deferred)
- Phase 0 — Foundation (charter, taxonomy, registry, ADR process)
- Phase 1 — Seed (5 capabilities TESTED: tool-registry, model-provider-abstraction, react-agent-loop, mcp-client, execution-trace-recorder)
- Phase 1.5 — Hardening (all gates enforced, 601 tests, 90.03% coverage)
- Phase 2 — Study (25 repos studied, 18 trade-offs, 6 new categories: ADR-0022–0027)

## Next Up

1. Phase 4 exit criterion: second monolithic baseline comparison (WP3, session OC1)
2. `basic-rag-pipeline` lifecycle (last Phase 1 queue item; WP4)
3. Resolve the 6 `DISCOVERED` capabilities (review docs → ADOPT/DEFER decisions; WP5)
4. DEBT-005: scanner `model_provider` API wart (WP6)
5. State-rot prevention P7 (machine-checked drift): deferred until P1–P6 have run long enough to reveal residual failures

## Key Files

| File | Purpose |
|---|---|
| [`state/REGISTRY.md`](REGISTRY.md) | Active agents and file ownership |
| [`state/INDEX.md`](INDEX.md) | Searchable log of all past sessions |
| [`state/ARCHITECTURE.md`](ARCHITECTURE.md) | Current system architecture |
| [`state/DECISIONS.md`](DECISIONS.md) | Architecture Decision Records |
| [`state/DEBT.md`](DEBT.md) | Technical debt tracker |
| [`state/BLOCKERS.md`](BLOCKERS.md) | Active blockers |
| [`CHARTER.md`](../CHARTER.md) | Repository constitution |
| [`TAXONOMY.md`](../TAXONOMY.md) | Capability registry |
| [`docs/roadmap.md`](../docs/roadmap.md) | Phase status and session notes |

<!-- AUTO-SYNC:START -->
> Branched reality check (auto-synced, git-derived — do not hand-edit):
> branch `master` at `2d68b01`; session commits not on master: 0 (see `git log master..HEAD --oneline`).
> working tree dirty at sync time — see `git status`.
<!-- AUTO-SYNC:END -->
