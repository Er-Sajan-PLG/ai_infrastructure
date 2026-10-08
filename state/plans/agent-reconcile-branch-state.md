# Plan: agent-reconcile-branch-state

- **Objective:** Reconcile MACP state files with git reality on `feat/branch-enforcement`.
- **Scope:** `state/DASHBOARD.md` (prose), `STATE.md`, `state/DEBT.md`, `state/BLOCKERS.md`, `state/INDEX.md`, `state/REGISTRY.md` (register/release).
- **Approach:** Baseline gates → `make sync-state` → prose-only edits → re-verify gates → close session.
- **Risks:** Touching `<!-- AUTO-* -->` blocks (forbidden); breaking Markdown links (covered by `make check`'s link gate).
- **Rollback:** `git checkout -- state/ STATE.md` — no commit without explicit user request.
- **Success criteria:** `make check` + `make status` green; all state claims command-verifiable.
