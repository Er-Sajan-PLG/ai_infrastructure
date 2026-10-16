# Plan: agent-OC1 — Complete the in-flight work and reconcile the repository

## Objective

Finish the repository's declared in-flight work and leave it production-ready:
all gates green (locally and in CI), all state/docs consistent with git
reality, Phase 3 and Phase 4 exit criteria genuinely met and closed, and the
remaining Phase 1 capability queue emptied (`basic-rag-pipeline`). Resolve the
five DISCOVERED capability proposals with recorded decisions.

## Verified starting state (2026-10-16 07:55 UTC, master @ 397fd5e)

- `make check` **RED**: `check_integrations` fails (`system_b_mixed` not
  listed in `integrations/README.md`).
- `make check-strict` (what CI runs) does **not** include `check_integrations`
  — CI is green while the documented `make check` gate fails. Root cause is a
  Makefile prerequisite divergence, not just content drift.
- State files (`DASHBOARD.md`, `STATE.md`, `DEBT.md`, `state/DECISIONS.md`,
  `state/ARCHITECTURE.md`) predate the Phase 3/4 merge train (PRs #5–#11,
  2026-10-09) and are stale.
- Phase docs: `phase-3-discover.md` partial, `phase-4-compose.md` says
  "Not started" though Systems A/B/C and a benchmark exist.
- Taxonomy: 7 TESTED, 6 DISCOVERED (`basic-rag-pipeline` + 5 Phase 2/3
  discoveries). `basic-rag-pipeline` is the only remaining Phase 1 queue item.
- Remote: CI green at 397fd5e; two dependabot PRs (#1, #3) open, green.

## Scope

- `Makefile`, `tests/test_ci_parity.py` — gate divergence fix + regression test
- `integrations/README.md`, `benchmarks/README.md`, `benchmarks/` — truth
- `docs/phases/phase-3-discover.md`, `phase-4-compose.md` — close with evidence
- `docs/roadmap.md`, `state/` (DASHBOARD, STATE.md, DEBT, BLOCKERS, INDEX,
  DECISIONS, ARCHITECTURE, REGISTRY, sessions/, plans/), `STATE.md`
- `research/retrieval/basic-rag-pipeline.md`, `docs/decisions/0034-*.md`,
  `specifications/basic-rag-pipeline.md`, `catalog/retrieval/rag_pipeline/`
  (+ tests, README, PROVENANCE, example), `TAXONOMY.md`,
  `docs/registry/RESEARCH_REGISTRY.md`
- Discovery review decisions: `docs/discovery/review/*.md`
- DEBT-005 scanner cleanup (`catalog/deployment/scanner/`)

## Approach

Ordered, committed in save points; each work package ends with gates green.

1. **WP1 — Restore green.** Add `check_integrations` to `check-strict`; add a
   parity regression test asserting every checker script reachable from
   `make check` is reachable from `check-strict`. Fix `integrations/README.md`
   (add `system_b_mixed`, correct count to 5).
2. **WP2 — Reconcile.** Truth-up phase docs, roadmap, state files, benchmarks
   README, DEBT (close DEBT-003), ARCHITECTURE (stale paths), DECISIONS
   (add ADR-0033). Close Phase 3 (all exit criteria evidenced).
3. **WP3 — Close Phase 4 honestly.** Extend the benchmark to compare against
   ≥2 distinct monolithic baselines, re-run, record environment; evaluate the
   "no component was modified" exit criterion; update the phase doc and
   results.
4. **WP4 — `basic-rag-pipeline` lifecycle.** Research (primary sources, web)
   → UNDERSTOOD → DESIGNED (spec) → DECIDED (ADR) → IMPLEMENTED → TESTED.
   Zero runtime dependencies; embedder and provider stay injected.
5. **WP5 — Discovery decisions.** Record ADOPT/DEFER/REJECT for the five
   proposals with rationale; implement the medium-priority ones if the
   post-WP4 budget allows, else DEFER with triggers (charter §24).
6. **WP6 — DEBT-005.** Remove or honor the ignored `model_provider` parameter.
7. **WP7 — Shutdown.** `make ci` + `make status` green; MACP end-of-session
   updates; terminal re-read; push to origin.

## Risks

- Scope creep in WP5 — mitigated by charter §24 (priority reasoning) and the
  DEFERRED register: low-priority proposals get triggers, not code.
- The 14-update dependabot dev-toolchain PR could change gate behavior if
  merged — not merged in this session; left for the maintainer.
- Research for WP4 must cite primary sources; if the network is unavailable,
  fall back to the already-studied 25 local reports (recorded honestly).

## Rollback

Every work package is a separate commit; `git revert` of a package restores
the prior state. No destructive operations, no history rewrites.

## Success criteria

- `make check`, `make check-strict`, `make ci`, `make status` all exit 0.
- CI green on `master` after push.
- `make status` reports zero governance drift; every status claim backed by
  artifacts on disk.
- Phase 3 and Phase 4 closed with evidence; Phase 5 standing activities
  documented as the live phase.
- `basic-rag-pipeline` either TESTED with the full artifact set, or explicitly
  re-blocked with a recorded reason (no silent partial claims).
- All state files reconcile with `git log` at the final commit.
