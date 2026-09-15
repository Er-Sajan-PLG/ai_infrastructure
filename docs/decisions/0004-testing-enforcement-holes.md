# ADR-0004 — Close the Testing-Enforcement Holes

- **Status:** Accepted
- **Date:** 2026-09-15
- **Supersedes:** —

## Context

Charter §13 requires every catalog entry to ship tests, §18 requires every
implemented capability to be verifiable, and §4 forbids claiming a lifecycle
stage the artifacts do not support. The environment ADR-0003 built *appeared* to
enforce this: `validate_catalog.py --strict` requires a `tests/` directory in
every entry, and `make check` runs pytest.

Both mechanisms had holes, found when the maintainer asked the obvious question
— *"doesn't testing belong to setting up the environment?"* — and the answer was
checked rather than asserted.

**Hole 1 — an empty `tests/` directory passed every gate.**
`validate_catalog.py` tested `(entry / "tests").is_dir()`. A directory that
exists but contains nothing satisfied it. Demonstrated: an entry with an empty
`tests/` and an empty `examples/` returned **0 errors, exit 0 in `--strict`
mode**.

**Hole 2 — pytest never looked inside `catalog/` at all.**
`pyproject.toml` set `testpaths = ["tests"]`. Capability tests live at
`catalog/<category>/<entry>/tests/` per charter §13. So a capability could ship
a full, passing test suite that **no gate ever ran**, while `make check`
reported green.

Together these meant the repository could satisfy its own testing contract
while testing nothing — precisely the failure mode charter §4 names and the
drift detector exists to prevent. The irony is specific: the enforcement
machinery had the defect it was built to catch.

## Decision

**1. An empty `tests/` directory is an error in every mode.**
`validate_catalog.py` now requires at least one `test_*.py` file (matched
recursively, so `tests/unit/test_x.py` counts). This is an error in normal *and*
strict mode, because "the directory is there" is never evidence and a
placeholder should not survive a lenient run either. The glob is deliberately
permissive — the goal is to reject empty directories and placeholder junk, not
to dictate a naming convention beyond Python's own discovery rules.

**2. An empty `examples/` directory is an error.**
Same reasoning: charter §13 requires examples, and an empty `examples/` is a
placeholder.

**3. `pytest` now collects `catalog/`.**
`testpaths = ["tests", "catalog"]`, with `norecursedirs` covering `.venv`,
`.uv-cache` and `study_pipeline`. Capability tests now actually run under
`make test` and `make ci`.

**4. CI runs the catalog contract in `--strict` mode.**
Local pre-commit stays lenient so a half-built entry can still be committed
mid-work; CI is the backstop that cannot be skipped.

**5. Regression tests pin all of it.**
Six new tests cover the empty-`tests/` and empty-`examples/` cases, nested test
discovery, and a guard asserting `catalog` remains in `testpaths`. The suite
went from 34 to 40 tests.

## Consequences

- A catalog entry can no longer claim `TESTED` while shipping no tests that run. The gap between the charter's rule and its enforcement is closed.
- `make check` gets slower as capability tests accumulate — the intended cost.
- Local commits remain possible with an incomplete entry (warning, not error), but CI will fail until `tests/` and `examples/` are populated. This split is deliberate: local flexibility, remote strictness.
- The `--strict` flag is now meaningful in CI rather than decorative.
- Any future change to `testpaths` is guarded by a test, so this hole cannot silently reopen.

## Alternatives considered

- **Make the empty-`tests/` check strict-only** — rejected: an entry with an empty `tests/` is not "work in progress", it is a false claim. Normal mode still warns for a *missing* directory, which is the genuine in-progress state.
- **Require a minimum test count or coverage threshold** — rejected as premature and cargo-culting (charter §3). A count cannot distinguish one meaningful test from ten trivial ones; coverage thresholds reward line-hitting. `minCoverage` stays 0 until the first real capability exists, as recorded in `.usa/foundation.yaml`.
- **Enforce tests only via the drift detector (`repo_status.py`)** — rejected: the drift detector validates the *taxonomy's* claims against paths; the entry contract is a different concern and belongs in `validate_catalog.py`.
- **Leave `testpaths = ["tests"]` and document the convention** — rejected outright: this was the actual hole, and documentation is not enforcement (charter §20 — a rule with no check is a preference).
- **Add a coverage `fail_under` now** — rejected: there is nothing to measure. Revisit when the first capability lands.

## Charter references

§4 (honest status), §13 (implementation standards — tests per entry), §18
(testing & verification), §20 (a rule with no check is a preference), §21
(definition of done), §28 (never weaken a check to obtain a pass).

## Taxonomy impact

None. All seven capabilities remain `DISCOVERED`. The change strengthens what a
future `IMPLEMENTED → TESTED` transition will require of them.