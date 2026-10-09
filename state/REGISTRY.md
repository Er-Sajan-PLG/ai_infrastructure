# REGISTRY — Active Agents & File Ownership

> Every active agent must register here. Update your status in real-time.

---

## Active Agents

| Agent ID | Model | Branch | Task | Started | Status | Files Owned |
|---|---|---|---|---|---|---|
| R001 | opencode session | `master` (was `feat/branch-enforcement`; merged 2026-10-08) | Branch state reconciliation + V16 gate (see session file) | 2026-10-08 03:34 UTC | Active | `state/`, `STATE.md`, gate files |
| HERMES | longcat-2.5-preview-free | `master` | Phase 4: benchmarks | 2026-10-08 23:30 UTC | Active | `benchmarks/` |
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
