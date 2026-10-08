# STATE.md — Session State & Audit

> **This file is the entry point for the MACP (Multi-Agent Coordination Protocol).**
> The full coordination state lives in [`state/`](state/) — read `state/DASHBOARD.md` first.
> Every agent session MUST read `state/DASHBOARD.md` before doing any work.

---

## Quick Navigation

| File | Purpose |
|---|---|
| [`state/DASHBOARD.md`](state/DASHBOARD.md) | **READ FIRST** — executive summary |
| [`state/REGISTRY.md`](state/REGISTRY.md) | Active agents & file ownership |
| [`state/INDEX.md`](state/INDEX.md) | Searchable session log |
| [`state/ARCHITECTURE.md`](state/ARCHITECTURE.md) | System architecture |
| [`state/DECISIONS.md`](state/DECISIONS.md) | Architecture decisions |
| [`state/DEBT.md`](state/DEBT.md) | Technical debt tracker |
| [`state/BLOCKERS.md`](state/BLOCKERS.md) | Active blockers |
| [`state/sessions/`](state/sessions/) | Per-agent session files |
| [`state/plans/`](state/plans/) | Active plans |

---

## Current Status (2026-10-08)

- **Phase:** Phase 2 complete; Phase 3 (Discover) not started
- **Branch:** `feat/branch-enforcement` (3 commits ahead of `master`; merge decision pending)
- **Tests:** 1141 passing, 3 deselected (verified via `make check` on this branch); `make status` green, no drift
- **Capabilities:** 6 TESTED, 5 DISCOVERED (verified via `make status`)
- **Uncommitted work:** none committed-but-unmerged — see branch note above; worktree holds only this session's state-file reconciliation (uncommitted)

---

## Session: 2026-10-01 — MACP Bootstrap

### What was done

1. Created `state/` directory structure with all required files
2. Bootstrapped DASHBOARD.md, REGISTRY.md, INDEX.md, ARCHITECTURE.md, DECISIONS.md, DEBT.md, BLOCKERS.md
3. Updated AGENTS.md with MACP startup sequence
4. Created branch `session/2026-10-01-state-convention`

### What's next

1. Merge-or-discard decision on `feat/branch-enforcement` (branch guard + `verification-package/`, 3 commits ahead of `master`)
2. Phase 3 — Discover (automate taxonomy discovery)
3. Remaining Phase 1 capabilities: vector-memory-store, basic-rag-pipeline

---

## End of Session Notes

_(To be filled when work is complete)_
