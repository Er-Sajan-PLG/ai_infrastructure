# ADR-0011 — Name the Pre-Phase-2 Hardening Work "Phase 1.5"

- **Status:** Accepted
- **Date:** 2026-09-16
- **Supersedes:** —

## Context

Phase 1's exit criteria are met: five of five required categories contain a `TESTED` capability, `make status` reports no drift, and `integrations/` holds a working end-to-end composition. The next charter phase (§30) is Phase 2 — build the study pipeline and study 20–30 repositories.

A peer survey on 2026-09-16 read three sibling repositories in this workspace end to end (`JARVIS`, `Universal_Software_Auditor`, `PROFESSOR-J`) and asked whether any fundamental engineering machinery was missing. The report is [`../audits/2026-09-16-peer-infrastructure-report.md`](../audits/2026-09-16-peer-infrastructure-report.md). It found two classes of problem:

1. **Two defects in coverage this repository already claims.** `ci.yml` omits `integrations/` from its mypy target list while the Makefile includes it, so integration code is type-checked locally and never in CI. `status` appears in no aggregate Makefile target, so `make check` can pass while `TAXONOMY.md` overclaims. And `Makefile:115` asserts that CI runs the Makefile's targets when CI invokes no `make` target at all.
2. **A missing verification layer.** No risk register, no enforced coverage threshold, no SAST/SCA/licence/dependency-update automation, no commit-message validation, no workflow linting or action pinning, and no scheduled drift reminders. All three sibling repositories have most of this; none of them started with it.

The survey also established the *reason to do this now rather than later*: each sibling accumulated debt that its ratchets now merely cap — JARVIS tolerates 485 strict mypy errors behind a ceiling, USA documents a complexity budget its linter only warns about, PROFESSOR-J enforces coverage in one layer and calls the rest aspirational. This repository currently has **no such debt**: mypy strict is clean across 59 files, ruff carries two global ignores, and coverage claims are honest. A ratchet installed against a clean tree prevents debt; the same ratchet installed later only measures it.

Phase 2 doubles the number of repositories and artifacts in play. Entering it with a false CI claim and no supply-chain verification would put the study pipeline's output behind weaker gates than the five capabilities that preceded it.

## Decision

The work is named **Phase 1.5 — Hardening**, and is planned in [`../phases/phase-1.5-hardening.md`](../phases/phase-1.5-hardening.md).

It is a phase, not a chore list, for three reasons:

- It has **entry criteria** (Phase 1 complete), **exit criteria**, and an ordered work queue like every other phase plan.
- It is **not part of Phase 2** — Phase 2's goal is study throughput, and this work is verification breadth. Folding it into Phase 2 would make Phase 2's progress unmeasurable.
- It is **not part of Phase 0** — Phase 0 established the environment, taxonomy, enforcement layer and licence, and was declared complete in ADR-0005. Reopening a completed phase would falsify that record (charter §4: a status must match artifacts).

The phase is **bounded**: it changes gates, configuration and governance documents. It adds **no capability**, advances **no taxonomy entry**, and implements **no new infrastructure**. Everything it touches is verification machinery.

Precedence for naming real work as a phase follows [ADR-0005](0005-phase-model-and-plans.md), which added Phase 0 because the charter's phase list otherwise left foundation work uncounted.

Four ADRs record the substantive decisions this phase executes:

| ADR | Decides |
|---|---|
| [ADR-0012](0012-gate-architecture.md) | CI runs the same gates as local; coverage threshold as a ratchet; CI/Makefile divergence is a defect class |
| [ADR-0013](0013-verification-breadth.md) | Which new checks are added, deferred, or rejected — each with its reason |
| [ADR-0014](0014-governance-drift.md) | Accepted-risk register with expiry, and scheduled drift reminders |

## Consequences

- `docs/phases/README.md` gains a Phase 1.5 row, and the phase table stays the single place a reader learns what is in progress.
- Phase 2 does not start until Phase 1.5's exit criteria are met. This delays Phase 2 by one to three sessions, which is the cost of the decision and is accepted deliberately.
- The two coverage defects are fixed as part of this phase, so the "no drift" claim in `make status` becomes true of CI as well as of the local tree.
- Because the phase adds no capability, `TAXONOMY.md`'s capability table must not change. `make status` is the check that keeps that true.
- New dev dependencies (scanners) are added to `requirements-dev.txt`, which is fully pinned; the zero-runtime-dependency rule (charter §22) is unaffected because none of them ship in `catalog/`.

## Alternatives considered

- **Fix the two defects and skip the rest** — rejected: the defects are symptoms of having no single source of truth for the gate list (ADR-0012), and fixing them without that guarantee invites the same drift again.
- **Fold the work into Phase 2 as "pipeline setup"** — rejected: Phase 2's exit criteria measure studied repositories, and gate work would be invisible in that count. It also puts the study pipeline's own output behind the weaker gate.
- **Reopen Phase 0** — rejected: Phase 0 was completed and recorded; reopening it would make ADR-0005's completion claim false.
- **Do nothing until Phase 2 needs it** — rejected on the evidence above: every sibling that deferred this now caps debt instead of preventing it, and the clean-tree moment is unrepeatable.
- **Adopt a sibling's full stack wholesale** — rejected: the survey documented that all three have a red or inert verification surface (JARVIS's enforcement is "process, not policy"; PROFESSOR-J's OTel check passes on string-presence greps; USA's own fact docs are stale). ADR-0013 takes the *ideas* and rejects several specific implementations, each with its reason.

## Charter references

§4 (a status must match artifacts — the reason the two defects are defects); §8 (decide before building); §12 (decision records); §18 (testing and verification); §20 (engineering standards are enforced, not asserted); §22 (human review gates, dependency addition); §24 (prioritisation — verification before scale); §25 (session protocol); §26 step 4 (present rejected options); §30 (growth model and phases).

## Taxonomy impact

None. This phase adds no capability and changes no lifecycle status. `TAXONOMY.md` is deliberately untouched; if a later change to this phase advances a capability, that change needs its own ADR.
