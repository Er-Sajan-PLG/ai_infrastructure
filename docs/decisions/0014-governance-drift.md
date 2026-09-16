# ADR-0014 — Governance Drift: An Accepted-Risk Register and Scheduled Reminders

- **Status:** Accepted
- **Date:** 2026-09-16
- **Supersedes:** —

## Context

This repository has two ways of recording a known problem, and neither is a register.

The first is **inline prose in roadmap notes**: `SUP-002` (unfrozen installs), `SUP-005` (dependency scanning) and `SUP-006` (Bandit) were identified in earlier sessions and written into `docs/roadmap.md` and audit documents as narrative findings. They have no owner field, no severity, no accepted date, and no review date. Nothing reports them as outstanding, and nothing notices if they are never closed. `SUP-005` is closed by [ADR-0013](0013-verification-breadth.md); the other two will be closed by Phase 1.5 — but the *pattern* is the problem, not these three instances.

The second is **explicit inline suppression** in code and configuration, which works correctly and is governed by §28 (never weaken a check to obtain a pass). This ADR does not change it.

Phase 1.5 adds scanners (ADR-0013). Scanners produce findings. Some findings will be real and fixed; some will be accepted as known, bounded, and not worth fixing now. Without a register, "accepted" is indistinguishable from "forgotten", and the survey showed exactly where that leads: **JARVIS tolerates 485 strict mypy errors behind a ceiling file** and warns "DOWN, lower the baseline to lock the gain" when the number improves — a ratchet that cannot converge on zero because nothing tracks which errors are *deliberately* accepted. USA documents a complexity budget as a hard cap while its linter only warns, so a breach exits 0.

The survey also found the strongest single artifact in any of the three siblings: **JARVIS's `docs/ACCEPTED_RISKS.md`** — a register where every entry carries an identifier, severity, status, rationale, an accepted date, a **review date**, and a named owner, with the governance rule that **a lapsed review date is itself a failure**. That is the mechanism this repository lacks: it converts a pile of findings into a governed, expiring set.

There is a second, smaller gap in the same area. Several things must be checked on a cadence rather than on a commit: whether a pinned scanner version has fallen behind, whether links have rotted, whether a review date has passed. No workflow runs on a schedule here. USA runs six cron workflows; JARVIS runs n8n schedules. The division of labour the survey named — **cron reminds, CI gates** — is the one that fits: a scheduled job opens or updates a visible issue, and the *gate* stays in CI where a failure blocks.

## Decision

**1. An accepted-risk register exists at `docs/risks/ACCEPTED_RISKS.md`.**

Every entry has: `id`, `severity`, `status`, `rationale`, `accepted` (date), `review_by` (date), `owner`. Statuses are `accepted`, `mitigated`, `closed`. An entry whose `review_by` has passed is **out of policy** and must be re-decided, closed, or re-dated in that session.

The register is **the only home for an accepted risk**. A finding recorded only in roadmap prose or an audit document is not accepted; it is unowned.

**2. A check enforces the register's own rules.**

`scripts/check_risks.py` validates:

- every entry has all required fields, with `accepted` and `review_by` as real ISO dates (`YYYY-MM-DD`, parsed, not merely matched);
- `id` values are unique and sequential;
- `status` is one of the three allowed values;
- `review_by` is not in the past — **an out-of-policy entry fails the check**, which is the rule that gives the register teeth;
- a `closed` entry records a closing note.

The check runs in `make check` (via ADR-0012's aggregate) and in CI. It is a first-party script with unit tests, matching the existing pattern of `check_links.py`, `check_phase_plan.py` and `validate_catalog.py`.

**3. The register is seeded from the findings that already exist.**

Phase 1.5 opens the register with the known outstanding items — `SUP-002` (unfrozen installs) and `SUP-006` (Bandit, closed by this phase's SAST work) — and any finding the new scanners accept rather than fix. Seeding it is part of the phase, not a follow-up, so the register begins with real entries rather than as an empty framework.

**4. Scheduled reminders are added, and they remind rather than gate.**

A single workflow `.github/workflows/reminders.yml` runs monthly and opens or updates **one** issue per reminder kind, deduplicated by label, covering:

- **Risk reviews due within 30 days**, and any already overdue (source: the register).
- **Pinned tool versions** — `gitleaks` and the ADR-0013 scanners are pinned by version, and Dependabot cannot see a binary's version. USA's `gitleaks-pin.yml` is the reference: it opens an issue rather than failing a build, which is the correct severity for "a scanner is stale".
- **Link rot**, reusing the existing `scripts/check_links.py`.

The workflow uses `issues: write` and nothing else, and it never pushes to a branch. It does not fail the build; a stale pin is not a broken commit, and a red build that a human learns to ignore is worse than an issue. The gate that matters stays in CI.

## Consequences

- An accepted risk now has an owner and an expiry, so "we know about it" becomes a dated, reviewable claim. The register can be reported on: `make status` can later surface the count, and a reviewer can see everything deliberately not fixed.
- A new obligation exists: risks must be re-reviewed on their date, and the check fails if they are not. This is deliberate friction, and it is the mechanism that prevents the register from becoming a list of permanent excuses. The cost is real — a session that touches nothing else may still have to re-decide a risk.
- `make check` gains another failure mode (an overdue review). It is bundled into the aggregate gate rather than run separately, so it cannot be skipped by running the documented command.
- The reminder workflow creates one issue per kind; noise is bounded by deduplication by label.
- Nothing is suppressed by the register. A gate's verdict never depends on prose: §28 suppressions stay explicit and inline. This is a deliberate rejection of JARVIS's runtime suppression (ADR-0013).
- The register is a governance document, not a capability, so `TAXONOMY.md` is untouched and `make status` is unaffected.

## Alternatives considered

- **Keep recording findings in roadmap prose** — rejected: it is what produced the current state, where `SUP-002` and `SUP-006` existed as narrative with no owner, severity or expiry, and nothing reported them as outstanding.
- **Adopt a machine-readable risk file (`risks.yaml`) instead of a Markdown table** — rejected as the primary home, though the checker parses either. Markdown is readable in the repository UI, matches `ACCEPTED_RISKS.md` in the reference implementation, and a risk register is read by humans. The check parses it as text, exactly as `validate_catalog.py` and `check_phase_plan.py` already parse Markdown.
- **Have the checker suppress gate findings, as JARVIS does** — rejected: the survey found JARVIS's version over-harvests identifiers from prose (`` `app` ``, `` `dict` ``, `` `user` `` parse as package names), so a gate's verdict depends on backtick placement in a document. Suppression stays inline and explicit (§28).
- **Make a stale pin fail CI instead of filing an issue** — rejected: a pin is stale from the moment upstream tags a release, so failing on it would produce a permanently red build unrelated to the change under test. USA separates these for the same reason.
- **Run reminders as a local cron/systemd job like JARVIS** — rejected: it depends on one machine being up, is invisible to anyone else, and JARVIS's own bridge concedes it "cannot gate a merge regardless". GitHub's scheduler needs no host we operate.
- **Use a single catch-all monthly "maintenance" issue** — rejected: distinct kinds have distinct owners and distinct fixes, and a merged thread gets closed without resolving everything in it.
- **Add the register without a check** — rejected: an unchecked register is a preference (§20), and the whole point of the reference implementation's review date is that something enforces it.
- **Adopt a third-party risk tool or a CVE database subscription** — rejected: disproportionate for a repository with no runtime dependencies and no users. The register's value is governance, not incidence tracking.

## Charter references

§4 (a claim must match artifacts — a lapsed review is a claim that no longer holds); §6 (claim labels — findings in the register are labelled FACT or OBSERVATION); §12 (decision records); §18 (verification); §20 (enforced standards); §21 (definition of done); §22 (human-review gates — severity and acceptance of a risk is a maintainer decision); §26 step 4 (rejected options); §28 (never weaken a check, and suppression stays explicit).

## Taxonomy impact

None. Governance machinery only; no capability is added, advanced, or deprecated.

## What was verified, and what was assumed

**Verified:** JARVIS's `docs/ACCEPTED_RISKS.md` field set and its lapsed-review-is-a-failure rule; the mypy ceiling of 485 errors and the "lower the baseline" behaviour; USA's warn-only complexity budget; USA's `gitleaks-pin.yml` filing an issue rather than failing; the absence of any scheduled workflow in this repository; that `SUP-002`, `SUP-005` and `SUP-006` currently exist only as roadmap/audit prose.

**Assumed:** that a monthly cadence is the right interval for link rot and pin freshness here. It is a starting value, revisable without an ADR — the interval is a tuning constant, not a structural decision; the structure is the register, its expiry rule, and the remind-versus-gate split.
