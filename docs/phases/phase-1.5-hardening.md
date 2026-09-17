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

> **Status 2026-09-17: complete, except one deliberate refusal.** All criteria
> below are demonstrated by a run. Two were deliberately changed from this
> plan's original text, and two were **added** after the plan because items
> marked done were not; the changes are noted inline with the reason, because a
> plan that is silently edited to match outcomes stops being a plan (§4).
>
> The two additions are worth reading as a pair: the coverage gate measured the
> phase's own new checkers at 0%, and the workflow gate was marked done while
> never having executed an audit. Both were **phase items that passed
> inspection and failed reality.**

Phase 1.5 is complete when all of the following hold, each demonstrated by a run rather than asserted:

- [x] **Gate equivalence is asserted by a test.** `tests/test_ci_parity.py` parses the workflow with `yaml.safe_load` and derives the gate list from `make print-gates`, so it cannot disagree with the Makefile about what the Makefile says. It fails in both directions; the one asymmetry (`diff-coverage`) is named in `_PR_ONLY_GATES` with its reason.
- [x] **CI runs the Makefile's gates.** Every gate step is `run: make <target>`. The `## What CI runs` claim is now true — it was false (CI ran `repo_status.py`; `make ci` omitted `status`).
- [x] **`integrations/` is type-checked in CI** — the Makefile target list includes it, and CI runs that target rather than repeating the command.
- [x] **`status` is in the aggregate CI and `AGENTS.md` runs** — `check-strict` now includes it; `make check-strict` is a CI step.
- [x] **Coverage is enforced** by `--cov-fail-under=85`, an integer with margin. The plan asked for a comment recording the measured figure; ADR-0016 goes further and records *why an integer with margin* — coverage displays a rounded figure (90%) while `fail_under` compares the raw float (89.79%), so a floor at the displayed value fails while showing that same number.
- [x] **Dead `noqa` codes are live or gone** — ruff's `S` family enabled; the stale `noqa: PLC0415`/`B603`/`S603` directives this work introduced were caught by ruff's own `RUF100` and removed (§28).
- [x] **SAST runs**: bandit **and** ruff `S`, both, because they are measurably not equivalent. Noise reduced 558 → 0 by path-scoping production code rather than suppressing findings; the scoping is documented in ADR-0018 and AR-001/AR-002.
- [x] **SCA runs**: `pip-audit` against **two** sources (`-s pypi`, `-s osv`), per the ESEM'21 finding that counts ranged 17–332 on identical projects.
- [x] **Licence check runs, passing.** **CHANGED FROM THE PLAN:** an **allow-list with fail-on-unknown**, not a deny-list. GitHub deprecated `deny-licenses` in `dependency-review-action` (issue #938) because a deny-list only rejects what someone enumerated; and an unknown licence must fail rather than pass, since "we could not determine it" must not be indistinguishable from "we checked". The check resolves genuinely ambiguous metadata by reading the licence text the package ships — three packages (`Jinja2`, `colorama`, `prompt_toolkit`) declare only the clause-agnostic `License :: OSI Approved :: BSD License`.
- [x] **Dependabot is configured** for `github-actions` (weekly) and `pip` (monthly), with a 7-day cooldown, grouped updates, `open-pull-requests-limit: 2`, and **no auto-merge**. The cooldown addresses the window CVE-2026-33634 and the Shai-Hulud worm both exploited.
- [x] **Commit messages are validated** by `scripts/check_commit_msg.py`, wired as a `commit-msg` hook, and demonstrably rejecting a malformed header (verified against a real attempt). **CHANGED FROM THE PLAN:** it validates the **header only**. The specification is genuinely ambiguous about body and footer structure, so enforcing more would encode an interpretation; recorded as AR-003.
- [x] **Workflows are linted**: `actionlint` + `zizmor` wired as `make workflows` and a CI step. An absent binary prints `SKIPPED (CI always runs it)` rather than passing silently. **ADDED AFTER THE PLAN:** the tools were installed and the audit actually executed, which found **two real defects in this phase's own `ci.yml`** — a HIGH-confidence template injection (`${{ github.base_ref }}` expanded into a `run:` block, which actionlint cannot see because it is syntactically valid) and persisted credentials in `.git/config`. Both fixed; `make workflows` now reports "No findings to report."
- [x] **All `uses:` are SHA-pinned** with the version as a trailing comment. **Extended beyond the plan:** tool versions are pinned *inside* the workflow too (`GITLEAKS_VERSION`, `ACTIONLINT_VERSION`), because CVE-2026-33634's compromise arrived through an unpinned `apt install` in a shell step — which SHA-pinning `uses:` would not have prevented.
- [x] **Structural entry checks exist**: `import-linter` for independence and `scripts/check_collectability.py` for test collectability. **Both proven to bite** by introducing real violations (a leaf-to-leaf import; an entry with an empty `tests/`).
- [x] **The accepted-risk register exists**, seeded with five real entries, and `scripts/check_risks.py` runs in `make check-strict`. Demonstrated failing on a past `review_by` **and** on a re-dated entry whose rationale did not change.
- [ ] **The reminder workflow** — **NOT IMPLEMENTED, deliberately.** See "Deviation" below.
- [x] **`docs/standards.md` is updated**: §8 is now normative with V1–V15, each mapped to its check, and a separate table lists the three rules that are deliberately *not* enforced.
- [x] **The checkers are themselves tested.** **ADDED AFTER THE PLAN.** The coverage gate measured the four new `scripts/check_*.py` files at **0%** — coverage fell 90.03% → 77.47% on this phase's own work. Tests for all five checkers brought the suite 415 → **601 tests** and coverage back to **90.03%**. Writing them found three real bugs in code already marked done, the worst being a guard in `check_collectability.py` that short-circuited *before* itself and so did not cover total discovery collapse.
- [x] **Every gate has been observed failing.** Each check in this phase was deliberately violated and confirmed to fail before being trusted: a leaf-to-leaf import, an entry with an empty `tests/`, a removed workflow step, a date-only re-date, a stub `trigger`, a disallowed licence, and a malformed commit header. A gate never seen to fail is a gate that cannot be trusted to be running.
- [x] **`make check` and `make status` pass.**

**Added beyond the original plan**, because the SOTA comparison surfaced it after the plan was written:

- [x] **A deferred-work register** (`docs/DEFERRED.md`, `scripts/check_deferred.py`, `make deferred`) recording work that is correct for a large system but premature here, each with the fact that defers it, its trigger, and its reversal step. This is the register the user explicitly asked for. ADR-0020.
- [x] **Makefile shell hardening** (ADR-0015) — the highest-severity finding of the entire Phase 1.5 effort, and not in the original plan.

### Deviation: the reminder workflow was not built

Item 15 planned a scheduled workflow opening issues for due risk reviews, stale
pins and link rot. It is **not implemented**, and the reasons are recorded here
rather than the item being quietly re-scoped:

1. **GitHub automatically disables scheduled workflows** in a public repository
   after 60 days of inactivity. A cron-driven reminder therefore stops firing
   precisely when a quiet repository most needs it — the opposite of the
   intended behaviour.
2. **The repository has no remote.** The workflow could not run, be tested, or
   be observed to work. Committing an untestable workflow that claims to
   enforce a maintenance policy is exactly the class of unverified claim
   charter §4 forbids.
3. **The reminder's job is already done, better, by checks that cannot be
   disabled.** `scripts/check_risks.py` reports entries within 30 days of
   `review_by` on *every* run; `scripts/check_deferred.py` does the same and
   additionally reports observable triggers that may have fired. Both run on
   every push and pull request as part of `make ci`.

The 60-day-disabling and no-remote findings are recorded in ADR-0014. If a
remote is added, this item can be revisited; the in-band warnings make it
unnecessary meanwhile, and the `workflow_dispatch` trigger is already present
so any job can be run by hand.

**Not a criterion:** coverage percentage beyond the floor, test count, or any
capability status. This phase is measured by the existence and demonstrable bite of its checks.

## Work queue

Ordered so that each item is verifiable on its own, and so that a failure early does not invalidate later work. One item per session where practical; the phase may take two to four sessions.

| # | Item | ADR | Depends on | Done when | Status |
|---|---|---|---|---|---|
| 1 | **Fix the two coverage defects** — add `integrations/` to CI's mypy targets; add `status` to the aggregate; correct the `## What CI runs` claim | 0012 | — | CI green with the wider target; `make check` fails on introduced drift | **DONE** |
| 2 | **Equivalence test** — parse both gate definitions, fail on divergence | 0015 | 1 | Test fails when a gate is removed from either side | **DONE** — caught a missing `secrets` step during authoring |
| 3 | **CI delegates to `make`** for the gates that have targets | 0015 | 2 | No duplicated command remains; CI green | **DONE** |
| 4 | **Coverage ratchet** — floor below measured, with the doctrine comment | 0016 | 1 | Suite fails below the floor | **DONE** — floor 85 vs raw 89.79% |
| 5 | **Structural entry checks** — import independence; test collectability | 0017 | — | Both fail on introduced violations; 411+ tests still pass | **DONE** — both proven to bite; 415 tests |
| 6 | **Enable ruff `S`; resolve dead `noqa`s** | 0018 | 5 | No dead `noqa`; findings fixed, not suppressed | **DONE** |
| 7 | **Bandit** in the pinned dev toolchain and CI | 0018 | 6 | Findings fixed or registered; gate blocking | **DONE** — 558 → 0 by path scoping |
| 8 | **`pip-audit`** against pinned dev requirements | 0018 | — | Clean, or findings registered with review dates | **DONE** — two sources |
| 9 | **Licence check** | 0018 | 8 | Passing over the installed set | **DONE** — allow-list, not deny-list |
| 10 | **Dependabot** for pip and github-actions | 0020 | — | Config committed; cadence stated | **DONE** — with cooldown, grouped, no auto-merge |
| 11 | **`scripts/check_commit_msg.py`** + `commit-msg` hook | 0019 | — | Rejects a malformed header; accepts `Merge`/`Revert` | **DONE** — header-only, AR-003 |
| 12 | **`actionlint` + `zizmor`** in CI | 0018 | 3 | Passing; findings fixed or registered | **DONE** |
| 13 | **SHA-pin all `uses:`** with version comments | 0018 | 12 | No floating tag remains | **DONE** — plus in-workflow tool pins |
| 14 | **Accepted-risk register** + `scripts/check_risks.py`, in `make check` | 0014 | — | Check fails on a past `review_by`; register holds real entries | **DONE** — 5 entries; re-dating check proven |
| 15 | **Reminder workflow** | 0014 | 14 | Runs on schedule; one issue per kind | **NOT DONE — see Deviation** |
| 16 | **Documentation close-out** — `docs/standards.md` normative tables, phase status, roadmap | 0011–0020 | all | No planned rule remains unenforced, and none is claimed that is not | **DONE** |
| 17 | **Makefile shell hardening** (added after the plan) | 0015 | — | A failing recipe reports failure | **DONE** — reproduced both before and after |
| 18 | **Deferred-work register** (added after the plan) | 0020 | — | Every entry has a fact, a trigger and a reversal; stubs refused | **DONE** — 12 entries |
| 19 | **Unit tests for the checkers** (added after the plan) | — | 4, 6, 8, 10, 11, 14 | Each checker has tests; coverage floor still met | **DONE** — 415 → 601 tests, 77.47% → 90.03% |
| 20 | **Run the workflow linters for real** (added after the plan) | 0018 | 12 | `make workflows` executes its audits, not SKIP | **DONE** — found and fixed 2 real defects |

**Items 19 and 20 were added because items that were marked DONE were not.**

Item 19 exists because the coverage gate — itself an item in this phase — measured
the four checkers added by items 8, 10, 11 and 14 at **0% coverage**. They were
runnable, reviewed and in the aggregate gate, and no test imported any of them.
Writing the tests found three real bugs in code already marked done, including a
guard in `check_collectability.py` that did not cover the case it was written for.
The lesson generalises: **"the gate runs and passes" is not the same claim as
"the gate is correct", and only a test of the gate distinguishes them.**

Item 20 exists because item 12 was marked **DONE** while `make workflows` was
printing `SKIPPED (CI always runs it)` — neither tool was installed, so the audit
had never executed. Installing them produced two findings in the `ci.yml` written
during this phase, one of them a **HIGH-confidence template injection** that
actionlint does not detect because the code is syntactically valid. A phase item
whose evidence is "the target exists" rather than "the check ran and its findings
were resolved" is not done, and both items are recorded here rather than quietly
folded into the ones they correct.

Item 15 remains the only open item, and it is a deliberate refusal, not an
omission — see "Deviation" above.

**Item 1 is first deliberately.** It is the only work here that fixes a claim that is currently false, and it is small. Item 2 before item 3 so the guarantee exists before the refactor it protects.

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
