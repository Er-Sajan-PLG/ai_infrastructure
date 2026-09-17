# ADR-0016: Coverage measurement — a regression floor plus change-scoped gating

- **Status:** Accepted
- **Date:** 2026-09-17
- **Phase:** 1.5 (Hardening)
- **Related:** [ADR-0013](0013-verification-breadth.md), [ADR-0018](0018-security-tooling.md)

## Context

Phase 1.5 introduces a coverage gate. Before choosing a policy, the SOTA
comparison examined what mature projects actually do, and what the research
literature says about whether a percentage means anything.

### What the research says

- **Inozemtseva & Holmes, ICSE 2014** — the largest study on this question
  (31,000 test suites, five real projects, two coverage criteria). Finding:
  coverage's correlation with fault detection is largely explained by
  **test-suite size**, and "using a fixed coverage value as a quality target is
  unlikely to produce an effective test suite."
- **Kochhar, Lo, Grunske & Thung, IEEE TR 2017** — 100 projects. Finding: no
  significant file-level correlation between coverage and post-release bugs.
- **coverage.py's own documentation**, which sets `fail_under = 90` for itself
  and describes it as "a very crude check that nothing catastrophic has
  happened."

The literature is consistent: a global percentage is a weak quality signal but
a reasonable **catastrophe detector**.

### What mature projects do

Of 22 mature Python projects surveyed, **17 enforce no threshold at all**.
CPython is "not tracking coverage overall"; Django has no overall minimum (it
gates *new* code); scikit-learn and Astropy use absolute floors for specific
test types; NumPy dropped its 100% target. The projects with real gates mostly
gate what changed, not the whole repository.

### The measurement that decided the floor value

`--cov-fail-under` compares the **raw float**. The terminal report displays a
**rounded** percentage. Measured on this repository:

```
TOTAL   5119   362   90%      ← displayed
raw float: 89.79%             ← what fail_under compares
```

A floor of `90` would therefore **FAIL** while printing "90%" next to it. The
gate would be correct and look broken, and the natural response to that — lower
the number until it stops complaining — is the behaviour this ADR is meant to
prevent.

## Decision

**1. Keep a global floor, as an integer with margin:**

```make
COVERAGE_FLOOR := 85
```

`85` is at least one full point below the measured `89.79%`, so it cannot land
in the rounding gap above. It is a **regression floor**, documented in the
Makefile as the crude catastrophe check coverage.py itself describes, not a
quality target.

**2. Add change-scoped gating as the real quality signal:**

`make diff-coverage` requires that lines **this change touched** are covered,
using `diff-cover` against a base branch. It runs only on pull requests, since
it is meaningless on the default branch.

**3. Provide a deliberate escape hatch:** the `missing-coverage-ok` PR label
reports without failing. A label is reviewable and visible; a silent skip is
not.

## Why both, and why this shape

The floor and the diff gate fail differently, which is why both are needed:

- The floor catches **catastrophe** — a module deleted, a whole suite no longer
  collected, a refactor that orphaned tests. It is insensitive but cheap.
- The diff gate catches the thing that actually matters on a change. A global
  percentage can be *maintained while quality falls*, because untouched,
  well-tested code props it up and new untested code is diluted by it. "Every
  line this PR added is exercised" cannot be gamed that way.

This split matches the field: Google's guidance endorses gating on new code,
SonarQube's default quality gate is entirely new-code, and coverage.py applies
`fail_under` to its own codebase while gating new code separately.

## Options considered

| Option | Verdict | Why |
|---|---|---|
| No threshold at all | **Rejected, but respected** | What 17/22 mature projects do, and defensible given the literature. Rejected here because this repository's whole premise is that claims must be enforced, and "coverage is tracked" would then be a claim with no check. The floor is the cheapest way to make it real. |
| Floor at `90` (the displayed value) | **Rejected** | Reproduced failure: compares `89.79 < 90` while displaying "90%". A gate that fails on unchanged code is the fastest way to get every gate deleted. |
| Floor at `89` | **Rejected** | Only `0.79` points of margin. Any single untested function on a normal change trips it, making it a change-blocker rather than a catastrophe detector. |
| Integer `85` (chosen) | **Accepted** | ≥1 point of margin from the raw figure, immune to the rounding gap, and low enough that crossing it means something broke. |
| `diff-coverage` only, no floor | **Rejected** | Would leave the repository with no defence against a whole-suite collection failure — precisely the failure `make collectability` exists for at entry level. |
| Line AND branch coverage | **Rejected for now** | Branch coverage is a better signal, but the charter's testing requirement is line-based and mixing criteria mid-phase would make the number non-comparable to itself. Recorded as future work. |
| Gate the floor per-file | **Rejected** | Per-file floors fail on correct code constantly (a small, fully-covered file plus a large, thin one averages into a useless number). |

## Consequences

**Positive.** Catastrophic coverage loss fails the build. The real quality
signal is scoped to the change. The floor's rationale is written where an
editor will see it, so the next person to find it inconvenient knows why it is
`85` rather than assuming it is arbitrary.

**Negative / accepted costs.**

- The floor will occasionally require a follow-up commit rather than allowing a
  change to land with reduced coverage. That is intended, and the margin
  ensures it happens rarely.
- `diff-cover` is a new dev dependency (`10.5.1`), pinned in
  `[project.optional-dependencies].dev` and the lock file.
- `diff-coverage` is not in `CI_GATES` because it needs a base branch. That
  asymmetry is explicit in `tests/test_ci_parity.py::_PR_ONLY_GATES` rather
  than left as an unexplained difference.
- A developer who has never pushed has no `origin/main`, and the target skips
  with a clear message rather than failing.

## Compliance

- [`CHARTER.md`](../../CHARTER.md) §18 — testing standards. This makes the
  testing claim enforceable.
- §20 — a rule with no check is a preference. Coverage was tracked but not
  enforced; now it is both.
- §28 — never weaken a check. The escape hatch is a label, which is visible in
  the PR record, rather than a code path that silently disables the gate.
- Enforced by: `make coverage` (floor), `make diff-coverage` (PRs),
  `tests/test_ci_parity.py` (that CI actually runs the floor).
