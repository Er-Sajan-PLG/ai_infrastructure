# Phase 1.5 — Hardening

**Status:** 📋 Planned (approved 2026-09-16, not started)
**Charter basis:** §18 (testing and verification), §20 (standards are enforced), §22 (dependency and review gates), §30 (growth model — added by [ADR-0011](../decisions/0011-phase-1-5-hardening.md))
**Depends on:** [Phase 1](phase-1-seed.md) ✅ complete (5 of 5 categories `TESTED`, no drift)
**Blocks:** [Phase 2](phase-2-study.md) — do not start Phase 2 while these exit criteria are unmet

**This plan adds no capability.** It changes gates, configuration and governance documents only. `TAXONOMY.md` is not touched by this phase, and `make status` is the check that keeps that true.

## Why this phase exists

Phase 1 met its exit criteria. A peer survey on 2026-09-16 read three sibling repositories in full and asked what fundamental engineering machinery was missing here. The report is [`../audits/2026-09-16-peer-infrastructure-report.md`](../audits/2026-09-16-peer-infrastructure-report.md); the decisions it produced are [ADR-0011](../decisions/0011-phase-1-5-hardening.md)–[ADR-0014](../decisions/0014-governance-drift.md).

It found two things:

1. **Two defects in coverage we already claim** — `integrations/` is type-checked locally but never in CI, and `status` is in no aggregate Makefile target, so `make check` can pass while `TAXONOMY.md` overclaims. `Makefile:115` asserts CI runs the Makefile's targets; CI runs no `make` target at all.
2. **A missing verification layer** — no risk register, no coverage threshold, no SAST/SCA/licence/dependency-update automation, no commit-message validation, no workflow linting or action pinning, no scheduled reminders.

The reason to do this **now** rather than at Phase 3: all three siblings accumulated debt that their ratchets now merely cap (JARVIS: 485 tolerated mypy errors; USA: a warn-only complexity budget documented as a hard cap; PROFESSOR-J: coverage enforced in one layer, aspirational elsewhere). This repository has **none of that debt** — mypy strict is clean across 59 files. A ratchet installed against a clean tree prevents debt; installed later, it only measures it.

Phase 2 multiplies the repositories and artifacts in play. Entering it with a false CI claim and no supply-chain verification would put the study pipeline's output behind weaker gates than the five capabilities before it.

## Exit criteria

Phase 1.5 is complete when all of the following hold, each demonstrated by a run rather than asserted:

- [ ] **Gate equivalence is asserted by a test.** A test parses both `Makefile` and `ci.yml` and fails when a gate exists in one and not the other, except for explicitly named and commented CI-only exemptions.
- [ ] **CI runs the Makefile's gates.** `ci.yml` invokes `make` targets for the gates that have them; no step hand-repeats a command that a target already defines. The `## What CI runs` comment is true.
- [ ] **`integrations/` is type-checked in CI** — demonstrated by a CI run, or by the equivalence test failing before the fix and passing after.
- [ ] **`status` is in `make check`** (or a documented aggregate that CI also runs), demonstrated by `make check` exiting non-zero on a deliberately introduced drift.
- [ ] **Coverage is enforced** by `fail_under` with a comment recording the measured figure and the raise-never-lower rule. Demonstrated by the suite failing below the floor.
- [ ] **Dead `noqa` codes are live or gone** — ruff's `S` family enabled, and the `S101`/`BLE001` suppressions either meaningful or removed (§28, charter §3).
- [ ] **SAST runs**: `bandit` and ruff `S`, with findings fixed rather than suppressed. Any accepted finding is in the register.
- [ ] **SCA runs**: `pip-audit` against the pinned dev requirements, clean or registered.
- [ ] **Licence check runs**: a deny-list over installed distributions, passing.
- [ ] **Dependabot is configured** for `pip` (and `github-actions`), with a stated update cadence.
- [ ] **Commit messages are validated** by `scripts/check_commit_msg.py` with unit tests, wired as a `commit-msg` hook and a CI step, and demonstrably rejecting a malformed header.
- [ ] **Workflows are linted**: `actionlint` and `zizmor` pass, with `zizmor` findings fixed or explicitly accepted in the register.
- [ ] **All `uses:` are SHA-pinned** with the version as a trailing comment.
- [ ] **Structural entry checks** exist: catalog entries cannot import another entry's production modules, and each entry's tests are collectable — both demonstrated by failing on a deliberately introduced violation.
- [ ] **The accepted-risk register exists, is seeded with real entries, and its check runs in `make check`.** Demonstrated by the check failing on an out-of-policy (past `review_by`) entry.
- [ ] **The reminder workflow exists** and opens deduplicated issues for due risk reviews, stale pins and link rot.
- [ ] **`docs/standards.md` is updated** so every rule that is now enforced is in the normative tables, and nothing remains in the planned section that is not still planned.
- [ ] **`make check` and `make status` pass**, and the CI run is green.

**Not a criterion:** coverage percentage beyond the floor, test count, or any capability status. This phase is measured by the existence and demonstrable bite of its checks.

## Work queue

Ordered so that each item is verifiable on its own, and so that a failure early does not invalidate later work. One item per session where practical; the phase may take two to four sessions.

| # | Item | ADR | Depends on | Done when |
|---|---|---|---|---|
| 1 | **Fix the two coverage defects** — add `integrations/` to CI's mypy targets; add `status` to the aggregate; correct the `## What CI runs` claim | 0012 | — | CI green with the wider target; `make check` fails on introduced drift |
| 2 | **Equivalence test** — parse both gate definitions, fail on divergence | 0012 | 1 | Test fails when a gate is removed from either side |
| 3 | **CI delegates to `make`** for the gates that have targets | 0012 | 2 | No duplicated command remains; CI green |
| 4 | **Coverage ratchet** — `fail_under` below measured, with the doctrine comment | 0012 | 1 | Suite fails below the floor |
| 5 | **Structural entry checks** — import independence; test collectability | 0012 | — | Both fail on introduced violations; 411+ tests still pass |
| 6 | **Enable ruff `S`; resolve dead `noqa`s** | 0013 | 5 | No dead `noqa`; findings fixed, not suppressed |
| 7 | **Bandit** in the pinned dev toolchain and CI | 0013 | 6 | Findings fixed or registered; gate blocking |
| 8 | **`pip-audit`** against pinned dev requirements | 0013 | — | Clean, or findings registered with review dates |
| 9 | **Licence deny-list check** | 0013 | 8 | Passing over the installed set |
| 10 | **Dependabot** for pip and github-actions | 0013 | — | Config committed; cadence stated |
| 11 | **`scripts/check_commit_msg.py`** + tests + `commit-msg` hook + CI step | 0013 | — | Rejects a malformed header; accepts `Merge`/`fixup!`/`squash!`; unit tests pass |
| 12 | **`actionlint` + `zizmor`** in CI | 0013 | 3 | Passing; findings fixed or registered |
| 13 | **SHA-pin all `uses:`** with version comments | 0013 | 12 | No floating tag remains |
| 14 | **Accepted-risk register** — `docs/risks/ACCEPTED_RISKS.md`, seeded, plus `scripts/check_risks.py` + tests, in `make check` | 0014 | — | Check fails on a past `review_by`; register holds real entries |
| 15 | **Reminder workflow** — monthly, deduplicated issues for due reviews, stale pins, link rot | 0014 | 14 | Runs on schedule; one issue per kind, no duplicates |
| 16 | **Documentation close-out** — `docs/standards.md` normative tables, `docs/development.md` toolchain, phase status, roadmap | 0011–0014 | all | No planned rule remains unenforced, and none is claimed that is not |

**Items 1 is first deliberately.** It is the only work here that fixes a claim that is currently false, and it is small. Item 2 before item 3 so the guarantee exists before the refactor it protects.

## Risks to this plan

| Risk | Response |
|---|---|
| **Bandit/`S` findings are numerous** and the fix is large (the count is unknown until item 6 runs). | The finding count is measured at item 6 before the gate is made blocking. If it is large, findings are triaged into fixed-now and registered, and the gate lands blocking with the register carrying the remainder. §28 forbids the alternative (suppressing to pass). |
| **Refactoring `ci.yml` to call `make` breaks CI** in a way the local runner cannot reproduce (toolchain, cache, runner labels differ). | Item 3 keeps the change mechanical and lands it with item 12's linters green on a branch. Any step that genuinely cannot be a target stays explicit and is named in the equivalence test's exemption set. |
| **`fail_under` becomes a number people lower.** | The doctrine comment sits beside the value and `docs/standards.md` states it; §28 makes lowering it a rule violation, not a judgement call. |
| **The equivalence test becomes brittle** — a legitimate new CI-only step fails it. | Exemptions are explicit, commented and few; adding one is a deliberate act recorded in the test, which is the visibility wanted. |
| **Commit-message checker differs from commitlint** in edge cases. | Stated plainly in ADR-0013 as an accepted cost. The checker's rule set is the subset actually used, and it carries unit tests for merge/fixup/squash and scopes. |
| **The register becomes a graveyard** of permanently re-dated entries. | A re-dated entry must record why it is not being fixed. If a risk is re-dated twice, the honest outcome is to fix it or narrow it. |
| **Scope creep** — this phase adds no capability, and a "while we're here" feature is out of scope by definition. | Any capability work discovered during this phase goes to the Phase 2 queue or the register, not into the phase. |

## Explicitly out of scope

Recorded so a future session does not have to re-derive these refusals; each is argued in [ADR-0013](../decisions/0013-verification-breadth.md):

SBOM generation; provenance/attestation (in-toto, Sigstore, cosign); containerization and hadolint; mutation testing; doc-fact inlining; catalog interface contract tests; `osv-scanner` and `trivy`; a complexity budget; a coverage service (Codecov/Coveralls); a Node toolchain (commitlint/husky/lint-staged); branch protection as code; and any workspace-level governance coupling across the sibling repositories.

Deferred items are **conditions, not permissions to forget** — each has a stated reversal condition in ADR-0013 and is revisited when that condition is met.

## Session protocol for this phase

1. Take the next unstarted item from the queue. Verify current state before trusting this document (charter §4) — this plan is a working document, and if it disagrees with the repository, the repository wins and this file is the bug.
2. Implement the item with its tests in the same session.
3. Run `make check` and `make status`; both must pass (charter §18, §28).
4. Update `docs/standards.md` for any rule that became enforced, and `docs/roadmap.md` with 1–2 lines.
5. When all exit criteria are met, mark this phase complete and proceed to Phase 2.
