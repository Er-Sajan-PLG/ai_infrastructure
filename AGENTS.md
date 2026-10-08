# AGENTS.md — Instructions for AI Agent Sessions

This repository operates under a charter and the **MACP (Multi-Agent Coordination Protocol)**. The charter is the constitution; MACP is the coordination layer. Canonical protocol text: [`docs/macp-protocol.md`](docs/macp-protocol.md) — this file is a digest; on any conflict the canonical text wins.

## First thing to read

1. **[`state/DASHBOARD.md`](state/DASHBOARD.md)** — executive summary. Read this first, always.
2. **[`state/REGISTRY.md`](state/REGISTRY.md)** — who's active and what they own.
3. **[`state/BLOCKERS.md`](state/BLOCKERS.md)** — what's blocking work.
4. **[`CHARTER.md`](CHARTER.md)** §25 (Session Protocol) and §27 (Output Contract).

## MACP Startup Sequence (mandatory before any work)

1. **Git reconnaissance** — `git status`, `git branch -vva`, `git log --oneline -10`
2. **Read `state/DASHBOARD.md`** — check "Last Reconciled" timestamp; confirm the checked-out branch matches its Branch field, HALT on mismatch
3. **Read `state/REGISTRY.md`** — check for active agents and file ownership conflicts
4. **Read `state/BLOCKERS.md`** — confirm your task isn't blocked
5. **Search `state/INDEX.md`** — find relevant past sessions
6. **Read `state/ARCHITECTURE.md`** and **`state/DECISIONS.md`** — if touching structure or making design choices
7. **Register yourself** — create `state/sessions/YYYYMMDD-HHMM-<AGENT-ID>-<slug>.md` and add to REGISTRY.md
8. **Create a plan** — add `state/plans/agent-<ID>-<slug>.md` with objective, scope, approach, risks, rollback, success criteria
9. **Only then start work**

## Before you write any code

1. Read [`state/DASHBOARD.md`](state/DASHBOARD.md) and [`state/REGISTRY.md`](state/REGISTRY.md) first.
2. Open [`TAXONOMY.md`](TAXONOMY.md). Find the highest-priority capability that is not MATURE.
3. **Verify actual state, do not trust labels.** If the taxonomy says `TESTED` but no test file exists, that inconsistency is your first bug to fix (charter §4).
4. Do the **next** lifecycle stage only. Not a stage already done, not one three steps ahead.

## Environment and gates (run these; they are enforced)

```bash
make setup            # once per clone: creates .venv with the pinned toolchain
make install-hooks    # once per clone: enforces gates on every commit
make check            # lint + typecheck + catalog contract + tests  ← must pass
make status           # taxonomy drift vs. artifacts on disk         ← must pass
make ci               # what CI runs (check-strict + coverage)
```

Full rule-to-check map: [`docs/standards.md`](docs/standards.md). Environment details: [`docs/development.md`](docs/development.md).

## Hard rules (violations are bugs)

- Never claim a lifecycle status without the artifacts existing and passing (charter §4). **`make status` enforces this** — it exits 1 when a claim exceeds what is on disk.
- Never begin work with "what should we copy" — begin with capability/problem/analysis (§1).
- Decide IMPLEMENT / ADAPT / COMPATIBILITY / PROTOTYPE / DOCUMENT / DEFER / REJECT **before** building (§8), and record the decision as an ADR in `docs/decisions/` in the same session (§12).
- Distinguish *inspired-by* from *derived-from* in `docs/registry/RESEARCH_REGISTRY.md` (§11). Conflation is a licensing risk. This repository is Apache-2.0; `code_reused: true` requires `attribution_requirements` plus a `NOTICE` update in the same change.
- External contributions are **not accepted** (see `CONTRIBUTING.md`) — do not merge outside PRs; it would forfeit the maintainer's relicense option.
- Licensing uncertainty, major dependency additions, trust-boundary changes, deletions of mature infrastructure → **stop and request human review** (§22).
- Never weaken a check to obtain a pass, and never commit with `--no-verify` (§28).
- Primary implementation language: Python, type-hinted (mypy strict), ruff-linted, black-formatted (§13).
- No runtime dependency without an ADR (§22).

## End of session (leave the repo resumable)

0. **Stop working first.** After finalizing your session file, only shutdown mechanics are allowed. Any new finding aborts shutdown back to work mode (max 3 restarts, then halt with `[NEEDS HUMAN]`). Typo fixes to the file being written don't count.
1. Update the taxonomy entry: `status`, `priority`, new `depends_on` links.
2. Update `docs/registry/RESEARCH_REGISTRY.md` for anything newly studied.
3. Add 1–2 lines to `docs/roadmap.md` under "Latest session notes": what happened, what's next and why.
4. Update `state/DASHBOARD.md` — reconcile status, update "Last Reconciled" timestamp.
5. Update your session file in `state/sessions/` — what was done, what's next.
6. Update `state/REGISTRY.md` — mark yourself inactive or remove your entry.
   Never mark Completed/Closed without an explicit maintainer close directive
   recorded as `Close-Authorized-By:` in your session file — finishing your
   checklist is not authorization. `make sessions` enforces this (V16, ADR-0030).
7. Run `make check` and `make status`. Both must pass before you report success.
8. **Terminal re-read (after the final commit):** re-read DASHBOARD.md and your session file against `git log` — fix anything found, commit, repeat until a read surfaces nothing. Resuming work after a completed shutdown is a **re-open**: status back to Active, dated reason entry, full shutdown again.
9. Write claims reproducibly: counts as deltas/history, current-state claims paired with their verifying command — never bare totals (see protocol §2, reproducibility principle).
10. Commit often on session branches (save points welcome) — the pre-commit hook regenerates git-derived state blocks via `make sync-state`; prose and judgments stay yours. Never hand-edit inside `<!-- AUTO-* -->` markers.

## Verification

`make check` is the package-level runner (lint, mypy strict, catalog contract, tests). Capability tests live with their catalog entry; repository-wide tests live in `tests/`. Do not claim success without a demonstrated run (charter §18, §28) — and never resolve a failing gate by weakening the check.
