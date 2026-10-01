# REGISTRY — Active Agents & File Ownership

> Every active agent must register here. Update your status in real-time.

---

## Active Agents

| Agent ID | Model | Branch | Task | Started | Status | Files Owned |
|---|---|---|---|---|---|---|
| A001 | opencode/longcat-2.5-preview-free | `session/2026-10-01-state-autosync` | State auto-sync (sync_state.py + hook + tests) | 2026-10-01 11:13 UTC | Active | `scripts/sync_state.py`, `scripts/hooks/pre-commit`, `tests/test_sync_state.py`, `Makefile`, `docs/macp-protocol.md`, `state/sessions/20261001-1113-A001-mcp-trial.md` |

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
