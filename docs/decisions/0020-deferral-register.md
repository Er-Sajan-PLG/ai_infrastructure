# ADR-0020: What is deferred to scale, and the register that holds it

- **Status:** Accepted
- **Date:** 2026-09-17
- **Phase:** 1.5 (Hardening)
- **Related:** [ADR-0014](0014-governance-drift.md), [ADR-0018](0018-security-tooling.md), [`../DEFERRED.md`](../DEFERRED.md)

## Context

The SOTA comparison produced recommendations that are **correct for a large
system and wrong for this one right now** — SBOM generation when there are zero
runtime dependencies; a merge queue when there is one contributor and no
remote; signed releases when there are no releases; mutation testing when the
suite runs in one second.

The usual outcomes for such a recommendation are both bad:

- **adopt early** — the cost lands immediately, the benefit never arrives, and
  the tooling must be maintained regardless; or
- **drop it in conversation** — and it is rediscovered from scratch months
  later, usually by someone who repeats the original research.

There is a third option, and it is the subject of this ADR: record it with the
**fact that makes it premature** and the **trigger that would change that**.

## Decision

**Create `docs/DEFERRED.md`, a machine-checked register of work deliberately not
done yet**, and `scripts/check_deferred.py` to enforce its structure.

Each entry records five things:

1. `current_fact` — the measurable present-day fact that justifies deferral;
2. `why_now_wrong` — why doing it today would cost more than it returns;
3. `trigger` — the condition that makes it worth doing;
4. `reversal` — the concrete first step when the trigger fires;
5. `effort` — the upgrade cost, honestly estimated.

Twelve entries were recorded at adoption, spanning seven categories (security,
scale, operability, governance, tooling, performance, quality).

### Why a structured register rather than a prose section

A prose list of "things we might do later" decays into a wish list, because
nothing distinguishes an item someone thought hard about from one added in
passing. Requiring `current_fact` and `trigger` to be **specific and
non-empty** (a length floor is enforced) is the mechanical difference between a
register and a list of good intentions.

The `reversal` field is the field with the least obvious value and the most
practical: it means that when a trigger fires, work starts from a **planned
first step** rather than a re-run of the original research.

### The register is not two other things

This distinction is what keeps all three registers useful:

| Artefact | Records | Subject |
|---|---|---|
| ADR "Options considered" | a **rejected** option and why | a decision already made |
| [`ACCEPTED_RISKS.md`](../risks/ACCEPTED_RISKS.md) | a **defect we live with** | risk currently borne |
| `DEFERRED.md` (this) | **work that will become valuable** | a future trigger |

A reader who conflates them will either implement a rejected option or treat a
live risk as a planned feature.

### What the checker does, and honestly does not

**Enforces:**

- the schema — every field present, `id` of the form `DW-NNN`, `category` and
  `effort` from closed enums, `adr` citing a real decision record;
- **specificity** — `current_fact`, `trigger` and `reversal` must exceed a
  minimum length, so a stub like `trigger: soon` is refused;
- **expiry** — no entry past `review_by`;
- **no re-dating without review** — `review_by` may not advance while
  `current_fact` and `trigger` are unchanged. This is the same anti-gaming
  control as ADR-0014, and for the same reason: **bumping a date is the
  cheapest way to make a gate green, and it is more likely still when an
  automated session is asked to fix a red build.** Verified: bumping a date
  alone fails; bumping it with a genuine revision passes;
- **an anti-silent-skip floor** — parsing fewer than eight entries is a
  failure, so a broken parser cannot masquerade as "everything was
  implemented".

**Does NOT enforce, deliberately:** whether a trigger has fired. Triggers are
prose describing observable conditions, and several are not mechanically
readable — "a defect was found that the tests missed" is not in the repository.
Claiming a check over prose would be precisely the dishonesty charter §4
forbids.

Instead the checker does the honest version: for the triggers it *can* observe,
it prints a **`POSSIBLE TRIGGER FIRE`** advisory for a human to adjudicate.
Two probes exist today (`a git tag exists`, `a runtime dependency was added`),
both reported as advisories, never as failures.

### The deferrals recorded, and the single fact behind each

Every entry rests on a measurable present-day fact. Representative examples:

| Item | The fact that defers it |
|---|---|
| Signed releases / provenance (DW-001) | **0 git tags.** Nothing is distributed, so there is no artifact integrity to attest. |
| SBOM (DW-002) | **Zero runtime dependencies.** A generated SBOM would describe an empty graph. |
| Merge queue (DW-005) | **One contributor, no remote.** A merge queue solves a concurrency problem that cannot occur. |
| Branch protection (DW-006) | **No remote.** There is no server-side configuration to apply or verify. |
| Renovate over Dependabot (DW-007) | **No remote.** Renovate is strictly more capable, but needs an installed GitHub App — and Dependabot already covers `pip` and `github-actions`, the two ecosystems present. |
| Mutation testing (DW-004) | **415 tests, ~1s suite.** Mutation testing's cost scales badly and the signal is not yet worth the wall-clock. |
| Property-based testing (DW-003) | **415 targeted tests with hand-built payloads** already cover the parsing surfaces. |
| Operational dashboards (DW-008) | **Zero CI runs.** A trend line needs history. |

Where a capability was **rejected outright** rather than deferred, it is in the
relevant ADR's "Options considered" section — not here. The distinction matters:
deferred means "when the trigger fires", rejected means "no".

## Options considered

| Option | Verdict | Why |
|---|---|---|
| Prose "future work" section in the roadmap | **Rejected** | No structure, no triggers, no review date. Decays into a wish list; this is the failure mode the register exists to avoid. |
| Put deferrals in TAXONOMY.md | **Rejected** | The taxonomy tracks **capability lifecycle** (charter §4), and `make status` enforces that its claims match artifacts on disk. Deferred work has no artifact, so it would corrupt that check or be exempted from it. |
| Put deferrals in `ACCEPTED_RISKS.md` | **Rejected** | Different subject: that register is about defects currently borne. Mixing them would make it impossible to answer "what are we living with?" separately from "what are we planning?". |
| One register entry per SOTA recommendation | **Rejected** | Most recommendations were adopted or rejected in ADRs. Duplicating them would create two sources of truth that drift. |
| Check whether triggers have fired automatically | **Rejected as impossible** | Triggers are prose; several are not repository-observable. The advisory approach is the honest subset. |
| No checker, register by convention | **Rejected** | An unchecked register is a document, not infrastructure (charter §20). The checker is why entries stay specific. |
| Review date only, no re-dating rule | **Rejected** | One-keystroke fix. See ADR-0014 for the full argument. |
| Delete an entry when its trigger fires, without implementing | **Rejected** | Loses the reversal and source. Entries are removed in the **same change that implements them**. |

## Consequences

**Positive.** Twelve recommendations are preserved with their reasoning and a
planned first step, instead of being lost or adopted prematurely. The register
is checked by the same gate machinery as everything else, and its anti-gaming
control is proven.

**Negative / accepted costs.**

- Another register to maintain, and another review date per entry. Mitigated by
  a 400-day ceiling and a 30-day warning horizon, and by batching reviews at
  phase gates.
- A stale `current_fact` is possible if a trigger fires and nobody notices. The
  observable probes reduce but do not eliminate this; the register is honest
  about the limit rather than implying full coverage.
- 12 entries is a non-trivial document. The alternative — no record — was
  rejected because the research that produced them would have to be repeated.

## Compliance

- [`CHARTER.md`](../../CHARTER.md) §8 — DEFER is one of the seven decisions and
  must be recorded as such. This register is that record.
- §26 step 4 — rejected and deferred options must be recorded.
- §30 — phases. Almost every trigger here is a **phase** transition, so the
  register doubles as a checklist for what each phase unlocks.
- §20 — a rule with no check is a preference; the checker is the check.
- Enforced by: `make deferred`, `make check-strict`, `make ci` (via
  `CI_GATES`), `tests/test_ci_parity.py`, and the pre-commit hook.
