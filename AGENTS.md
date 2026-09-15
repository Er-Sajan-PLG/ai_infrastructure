# AGENTS.md — Instructions for AI Agent Sessions

This repository operates under a charter. These are the Level-2 instructions for this repository (see the workspace scope-discipline rules); the charter is the constitution.

## Before you write any code

1. Read [`CHARTER.md`](CHARTER.md) §25 (Session Protocol) and §27 (Output Contract). Skim the rest as needed.
2. Open [`TAXONOMY.md`](TAXONOMY.md). Find the highest-priority capability that is not MATURE. Read its entry: `status`, `depends_on`, `priority`, linked ADRs and registry entries.
3. **Verify actual state, do not trust labels.** If the taxonomy says `TESTED` but no test file exists, that inconsistency is your first bug to fix (charter §4).
4. Do the **next** lifecycle stage only. Not a stage already done, not one three steps ahead.

## Hard rules (violations are bugs)

- Never claim a lifecycle status without the artifacts existing and passing (charter §4, §18).
- Never begin work with "what should we copy" — begin with capability/problem/analysis (§1).
- Decide IMPLEMENT / ADAPT / COMPATIBILITY / PROTOTYPE / DOCUMENT / DEFER / REJECT **before** building (§8), and record the decision as an ADR in `docs/decisions/` in the same session (§12).
- Distinguish *inspired-by* from *derived-from* in `docs/registry/RESEARCH_REGISTRY.md` (§11). Conflation is a licensing risk.
- Licensing uncertainty, major dependency additions, trust-boundary changes, deletions of mature infrastructure → **stop and request human review** (§22).
- Primary implementation language: Python, type-hinted, ruff/black styled (§13).

## End of session (leave the repo resumable)

1. Update the taxonomy entry: `status`, `priority`, new `depends_on` links.
2. Update `docs/registry/RESEARCH_REGISTRY.md` for anything newly studied.
3. Add 1–2 lines to `docs/roadmap.md` under "Latest session notes": what happened, what's next and why.
4. Run `python scripts/validate_catalog.py` if you touched `catalog/`.

## Verification

There is no package-level test runner yet (Phase 1, skeleton only). When implementations exist, each catalog entry must carry its own tests, and cross-cutting suites live in `tests/`. Do not claim success without a demonstrated run (charter §18, §28).
