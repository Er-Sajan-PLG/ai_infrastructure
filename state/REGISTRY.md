# REGISTRY — Active Agents & File Ownership

> Every active agent must register here. Update your status in real-time.

---

## Active Agents

| Agent ID | Model | Branch | Task | Started | Status | Files Owned |
|---|---|---|---|---|---|---|
| OC1 | opencode session | `master` | Complete in-flight work + repository reconciliation (WP1–7, see plan) | 2026-10-16 07:55 UTC | Active — WP1–WP6 committed (`248f618`..`065b2a6`); WP7 shutdown in progress; awaiting maintainer `Close-Authorized-By` (ADR-0030) | repo-wide for this session (see plan); ownership released at close |
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
| — | — | — | — |

---

## Coordination Notes

_(Shared-file coordination notes go here.)_
