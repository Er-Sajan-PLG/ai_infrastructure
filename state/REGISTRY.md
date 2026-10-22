# REGISTRY — Active Agents & File Ownership

> Every active agent must register here. Update your status in real-time.

---

## Active Agents

| Agent ID | Model | Branch | Task | Started | Status | Files Owned |
|---|---|---|---|---|---|---|
| SU1 | gemini-3.8-flash | `feat/package-examples-and-sustain` | Package quickstart examples and sustainment operations | 2026-10-21 07:30 UTC | Active | `examples/`, `pyproject.toml`, `tests/test_ai_infrastructure_api.py` |
| PR1 | gemini-3.8-flash | `master` | Complete ai_infrastructure and make it production-ready | 2026-10-21 01:05 UTC | Completed (production readiness achieved; claims released) | _(released)_ |
| OC1 | opencode session | `master` | Complete in-flight work + repository reconciliation (WP1–7, see plan) | 2026-10-16 07:55 UTC | Completed (session closed with maintainer authorization; claims released) | _(released)_ |
| R001 | opencode session | `master` (was `feat/branch-enforcement`; merged 2026-10-08) | Branch state reconciliation + V16 gate (see session file) | 2026-10-08 03:34 UTC | Inactive (>24h; superseded — merge-or-discard decision resolved by merge) | _(released)_ |
| HERMES | longcat-2.5-preview-free | `master` | Phase 3: cross-repo convergence detection | 2026-10-08 16:45 UTC | Inactive (>24h; work landed 2026-10-09 via PRs #5–#11; state files never reconciled) | _(released)_ |
| A001 | opencode/longcat-2.5-preview-free | `session/2026-10-01-state-autosync` | Full session incl. auto-sync (see session file) | 2026-10-01 11:13 UTC | Completed (session closed by user; claims released) | _(released)_ |

---

## File Ownership Rules

1. **If another ACTIVE agent owns files you need to modify** → STOP. Coordinate first.
2. **If owner is INACTIVE (>24h)** → You may claim ownership.
3. **Shared files** (config, package.json, etc.) require a `[COORDINATION]` note in both session files.

---

## Ownership Claims

| Agent ID | Files/Directories | Claimed At | Status |
|---|---|---|---|
| SU1 | `examples/`, `pyproject.toml`, `tests/test_ai_infrastructure_api.py` | 2026-10-21 07:30 UTC | Active |

---

## Coordination Notes

_(Shared-file coordination notes go here.)_
