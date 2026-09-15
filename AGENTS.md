# AGENTS.md — Instructions for AI Agent Sessions

This repository operates under a charter. These are the Level-2 instructions for this repository (see the workspace scope-discipline rules); the charter is the constitution.

## Before you write any code

1. Read [`CHARTER.md`](CHARTER.md) §25 (Session Protocol) and §27 (Output Contract). Skim the rest as needed.
2. Open [`TAXONOMY.md`](TAXONOMY.md). Find the highest-priority capability that is not MATURE. Read its entry: `status`, `depends_on`, `priority`, linked ADRs and registry entries.
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
- Distinguish *inspired-by* from *derived-from* in `docs/registry/RESEARCH_REGISTRY.md` (§11). Conflation is a licensing risk. `code_reused: true` is currently blocked by ADR-0002.
- Licensing uncertainty, major dependency additions, trust-boundary changes, deletions of mature infrastructure → **stop and request human review** (§22).
- Never weaken a check to obtain a pass, and never commit with `--no-verify` (§28).
- Primary implementation language: Python, type-hinted (mypy strict), ruff-linted, black-formatted (§13).
- No runtime dependency without an ADR (§22).

## End of session (leave the repo resumable)

1. Update the taxonomy entry: `status`, `priority`, new `depends_on` links.
2. Update `docs/registry/RESEARCH_REGISTRY.md` for anything newly studied.
3. Add 1–2 lines to `docs/roadmap.md` under "Latest session notes": what happened, what's next and why.
4. Run `make check` and `make status`. Both must pass before you report success.

## Verification

`make check` is the package-level runner (lint, mypy strict, catalog contract, tests). Capability tests live with their catalog entry; repository-wide tests live in `tests/`. Do not claim success without a demonstrated run (charter §18, §28) — and never resolve a failing gate by weakening the check.
