# ADR-0012 — Gate Architecture: CI Runs the Same Gates as Local

- **Status:** Accepted
- **Date:** 2026-09-16
- **Supersedes:** —

## Context

This repository documents its gates in three places: `Makefile` targets, `.github/workflows/ci.yml`, and `scripts/hooks/pre-commit`. The Makefile's `ci` target carries the comment `## What CI runs` (`Makefile:115`).

That comment is false. **CI invokes no `make` target at all** — `ci.yml` hand-repeats thirteen commands. The two lists were maintained by hand and have already diverged in two ways, both verified on 2026-09-16 by reading the files and running the commands:

1. **`integrations/` is type-checked locally but not in CI.**
   ```
   .github/workflows/ci.yml:66   targets=$(find catalog scripts tests study_pipeline -name '*.py' ...
   Makefile:72                   targets=$$(find catalog integrations scripts tests study_pipeline -name '*.py' ...
   ```
   Integration code carries 25 tests and is the only end-to-end composition in the repository. It has been passing mypy locally and has never been checked in CI.

2. **`status` is in no aggregate target.** `make check` is `lint typecheck validate links test` (`Makefile:109`) and `make check-strict` adds only `validate-strict` and `phase-plan` (`Makefile:112`). The governance drift detector — the check that refuses a lifecycle claim exceeding artifacts on disk, and the repository's flagship mechanism — runs only in CI and in the path-conditional pre-commit hook. A session following `AGENTS.md` ("`make check` … must pass") can therefore be green while `TAXONOMY.md` overclaims.

The guard that should have caught the first divergence already exists and cannot see it. `tests/test_gate_coverage.py` asserts that the directories holding source are traversed by the gates; at `:224` it parses **the Makefile's** `find` list. It verifies that the Makefile is internally complete — it has no knowledge of `ci.yml`. The test was written for the right bug class (its docstring lists six prior instances) and is blind to this instance because it reads one of the two lists.

This is the same defect class the repository has now closed seven times: *something was assumed to be covered, and nothing asserted the coverage.* The difference is that this time the unasserted thing is the **equivalence of two gate definitions**, not the presence of a directory.

A second, smaller gap sits in the same area. `scripts/validate_catalog.py` requires a `tests/` directory to exist and be non-empty (`--strict`), but nothing requires the tests to be *collected and run*, and nothing prevents a future entry from importing another entry's internals — a direct violation of the component-independence rule (§31) that no check currently observes.

## Decision

**1. The Makefile is the single source of truth for the gate list, and CI runs it.**

`ci.yml` is rewritten so that each gate step invokes the corresponding `make` target rather than repeating its command. CI keeps only the steps that cannot be a Makefile target — installing the pinned toolchain, installing the pinned scanner binary, and the steps that need a `make`-external environment. The `## What CI runs` comment becomes true or is deleted; it must not survive as a claim.

**2. A test asserts equivalence rather than trusting it.**

`tests/test_gate_coverage.py` is extended (or a sibling test added) to parse **both** `Makefile` and `.github/workflows/ci.yml` and fail when:

- a directory containing first-party Python is traversed by the Makefile's mypy target but not by CI's (and vice versa);
- a Makefile aggregate target that CI claims to run is absent from `ci.yml`'s steps;
- a gate present in one definition is absent from the other, unless it is listed in an explicit, commented exemption set.

The test parses configuration as text, in the same style as the existing test. The exemption set exists so that deliberate differences (a scanner CI installs and a developer may not have) are **named rather than silent**.

**3. `status` joins the aggregate gate.**

`make check` includes `status`, so the documented pre-commit command and the enforcement agree. The cost is that `make check` now fails on taxonomy drift, which is the intended behaviour: drift is a defect, not a warning.

**4. Coverage is enforced as a ratchet, not a target.**

`pyproject.toml`'s `[tool.coverage.report]` gains `fail_under`, set just below the currently measured value, with a comment recording the measured figure and the rule: **raise it when it goes green by a margin; never lower it, and never exclude files to pass.** The comment currently in the file — *"Set `fail_under` when the first catalog entry lands"* — has been overtaken by events: five entries have landed.

Adopted from `Universal_Software_Auditor`'s `vitest.config.ts:17-21`, which states the doctrine inline, and from `JARVIS`'s `gate_mypy`, which prints **"DOWN, lower the baseline to lock the gain"** when a count improves. The second half is the part that makes a ratchet converge.

**5. Structural checks for entry independence and test collection.**

Two checks are added to `scripts/validate_catalog.py` (or a new checker if that keeps the script single-purpose):

- **Import independence:** parse each entry's Python with `ast` and fail if it imports another catalog entry's modules. First-party imports within the entry itself remain allowed. This makes §31's independence rule mechanically visible instead of a review instruction.
- **Test collectability:** the entry's `tests/` must be collected by pytest's configured `testpaths`. The existing `test_gate_coverage.py` already proves this approach works for directories; this applies it per entry.

Both checks are structural and cheap; neither judges test quality, which stays a human-gate item (charter §18, `docs/standards.md` §7).

**6. Workflow files are linted, and actions are pinned.**

`actionlint` (workflow syntax, expressions, runner labels) and `zizmor` (security: template injection, credential persistence, excessive permissions) run against `.github/workflows/`. Every `uses:` is pinned to a full commit SHA with the version in a trailing comment, so a tag cannot move beneath the pipeline.

## Consequences

- Adding a gate becomes a one-file change. The divergence class of §Context cannot recur silently; if it recurs, a test names it.
- CI becomes slightly slower (an extra `make` process per step) and slightly less transparent in the GitHub UI (a step named `make typecheck` shows the target's output rather than an inline command). Accepted: correctness over log aesthetics.
- `make check` grows a failure mode. Sessions that previously passed `make check` with drift present will now fail — which is the point, and is why the change lands with the phase rather than opportunistically.
- `fail_under` introduces a number that must be maintained. It is deliberately a floor with headroom, and the test suite is expected to fail when coverage drops rather than when it plateaus.
- The independence check constrains future entries: an entry may not reach into another. That is already the rule; the check only makes it real.
- `zizmor`/`actionlint` become part of the pinned dev toolchain and must be installed in CI. Both are single binaries, pinned by version like `gitleaks` already is.

## Alternatives considered

- **Delete the `## What CI runs` comment and leave both lists hand-maintained** — rejected: the comment is the only place the equivalence was asserted, and the divergence it hid is real. Removing the claim would remove the evidence that the two must agree.
- **Generate `ci.yml` from the Makefile** — rejected as disproportionate: a code generator for thirteen steps adds a build artifact and a failure mode, where a test that compares two lists adds neither.
- **Make CI call `make ci` only** — rejected as insufficient: `ci.yml` legitimately does more than `make ci` (toolchain install, pinned scanner download, strict validation). The goal is named, asserted differences, not one script.
- **Assert equivalence only in the pre-commit hook** — rejected: the hook is local, path-conditional, and skippable by design. CI is the backstop.
- **Set `fail_under` to a high absolute target immediately** — rejected: an aspirational floor either fails immediately or gets lowered, and lowering it destroys the ratchet's meaning. A floor just below measured, raised on improvement, is the version that survives contact.
- **Adopt a coverage service (Codecov/Coveralls)** — rejected in ADR-0013: it adds a network dependency and a third-party status check to enforce a number the local suite already computes.
- **Enforce independence by review only** — rejected: it is already a review item and has never been checked; §31 is a structural claim and structures are checkable.
- **Ban all cross-entry imports including test helpers** — rejected: a shared test helper is not a production dependency and banning it would push duplication. The check targets production modules.

## Charter references

§3 (no cargo-cult engineering — the checks are added because the defects are demonstrated); §4 (claims must match artifacts; `status` in the aggregate); §13 (catalog entry contract); §18 (testing and verification); §20 (standards are enforced); §21 (definition of done); §28 (never weaken a check to obtain a pass — `fail_under` is raised, never lowered); §31 (component independence).

## Taxonomy impact

None. This ADR changes how existing claims are enforced; it advances no capability and alters no lifecycle status.
