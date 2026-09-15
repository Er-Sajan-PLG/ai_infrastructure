# Phase 0 — Foundation

**Status:** ✅ Complete (sessions 1–5)
**Charter basis:** implicit — the prerequisites for §30 Phase 1
**Recorded by:** ADR-0005

## Goal

Make it possible to build capabilities *honestly*: a taxonomy that can't lie, standards that are enforced rather than described, a working environment, and a settled license.

## Why this existed

Charter §30 begins at "Seed", but seed work assumes a repository that can already
record a decision, run a test, and refuse a false status claim. Without that,
every later capability would have been built on unverifiable ground. The charter
did not name this work; ADR-0005 names it retroactively so the phase model
reflects reality.

## Deliverables

| Area | Artifact | Status |
|---|---|---|
| Governance | `CHARTER.md`, `AGENTS.md`, `CONTRIBUTING.md` | ✅ |
| Standards | `docs/standards.md` — every rule mapped to its check | ✅ |
| Taxonomy | `TAXONOMY.md` — 7 capabilities seeded at honest status | ✅ |
| Registry | `docs/registry/RESEARCH_REGISTRY.md` (empty, honestly) | ✅ |
| Decisions | ADR-0000 format + ADR-0001..0005 | ✅ |
| Environment | `pyproject.toml`, `requirements-dev.txt`, `Makefile` | ✅ |
| Enforcement | pre-commit hook, CI, `validate_catalog.py` | ✅ |
| Drift detection | `scripts/repo_status.py` | ✅ |
| Testing | 40 tests, `testpaths` includes `catalog/` | ✅ |
| License | Apache-2.0 + `NOTICE` + contribution restriction | ✅ |
| Security | `SECURITY.md` with threat model | ✅ |
| Audit | 2 USA runs, adjudicated | ✅ |

## Exit criteria — all met

- [x] `make check` passes from a fresh clone
- [x] `make status` detects a deliberately false status claim (exit 1)
- [x] An empty `tests/` directory is rejected
- [x] `catalog/` tests are actually collected by pytest
- [x] License chosen and recorded (ADR-0002)
- [x] Intent declared machine-readably (`.usa/foundation.yaml`)
- [x] External audit run and adjudicated

## What this phase did NOT do

- Build any capability. `catalog/` is empty by design.
- Produce research records. The registry is empty because nothing was studied.
- Establish benchmarks. Nothing exists to benchmark.

## Known gaps carried forward

These are real and Phase 1 inherits them:

1. **ADR references in prose are unchecked.** A wrong `ADR-NNNN` in a roadmap note is invisible to tooling. (Found and fixed by hand once — see session 4 notes.)
2. **No dependency vulnerability scanning in CI.** Mitigated by zero runtime dependencies; becomes real at the first one.
3. **No secret scanning in CI** (`gitleaks`). The CRITICAL `REPO-003` was verified by manual grep, not a scanner.
4. **No `minCoverage` threshold.** Deliberate — nothing to measure. Set it when the first capability lands.
5. **The drift detector validates structure, not quality.** It cannot tell a meaningful test from a trivial one.
6. **USA pattern gaps** (6 documented in `docs/audits/2026-09-15-usa-audit-foundation.md`) — most notably that a declared `stage` does not override the auto-detected maturity profile.

## Carried into Phase 1

The rule that matters: **keep status honest.** Phase 0's whole purpose was to make it hard to lie about progress. Use that.