# Session: 2026-10-08 — Phase 3 Discover (HERMES)

- **Agent:** HERMES (longcat-2.5-preview-free)
- **Branch:** `master`
- **Task:** Build cross-repo convergence detection engine (Phase 3: Discover)
- **Started:** 2026-10-08 16:45 UTC
- **Status:** Active

## Objective

Build `study_pipeline/discover.py` — a module that reads all study reports,
extracts proposed categories, and ranks them by convergence (how many
independent repositories proposed the same category).

## Scope

- `study_pipeline/discover.py` — new module
- `study_pipeline/tests/test_discover.py` — 14 tests
- `Makefile` — `make discover` target
- `docs/phases/phase-3-discover.md` — update exit criteria

## Approach

1. Parse each report's "Proposed new categories" table
2. Group proposals by `proposed_id`
3. Rank by convergence count (descending)
4. Render as Markdown document for human review
5. NEVER write to TAXONOMY.md (ADR-0021 Decision 2)

## Risks

- Report format changes break the parser → mitigated by tests
- False convergence (same pattern, different meaning) → mitigated by human review

## Rollback

- Remove `study_pipeline/discover.py` and `make discover` target

## Success Criteria

- `make check` passes (including new tests)
- `make discover` produces a readable proposal document
- Convergent patterns (≥3 repos) are correctly identified
