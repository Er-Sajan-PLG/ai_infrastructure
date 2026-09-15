# ADR-0005 — Name the Foundation Work "Phase 0", and a Phase-Plan Process

- **Status:** Accepted
- **Date:** 2026-09-15
- **Supersedes:** —

## Context

Charter §30 defines five growth phases, beginning with **Phase 1 — Seed**: *"5–10 categories with foundational patterns; establish the taxonomy, registry, documentation standards."*

Five sessions were spent establishing the taxonomy, registry, and documentation
standards — but also an environment, an enforcement layer, a drift detector, a
license, and a security policy. None of those artifacts is a *capability*. When
asked "what is done?", the honest answer was: **the scaffolding, not Phase 1.**

The charter's phase model had no name for that scaffolding work, and two
problems followed from the omission:

1. **Progress was unmeasurable.** `docs/roadmap.md` said "Phase 1 — in progress"
   while `catalog/` was empty, which made Phase 1 look stalled rather than
   unstarted.
2. **The work risked being repeated or dismissed.** Undocumented prerequisites
   get rebuilt badly by the next session or skipped by one that assumes they
   exist.

There was also no *working* plan for the phases — the roadmap listed a queue but
did not say what "done" meant per phase, what the per-capability workflow was,
or what was deliberately excluded.

## Decision

**1. Record the completed work as "Phase 0 — Foundation."**
`docs/phases/phase-0-foundation.md` documents what was built, why it was a
prerequisite, its exit criteria (all met), and — importantly — the known gaps it
passes forward (unchecked ADR prose references, no secret/dependency scanning in
CI, no coverage threshold, 6 documented USA pattern gaps).

The charter's five phases are unchanged. Phase 0 is an addition, named so the
model describes reality rather than hiding a phase.

**2. Create `docs/phases/` with a plan per phase.**
Each plan carries: charter basis, dependencies, **exit criteria**, method,
deliverable per lifecyle stage, risks with mitigations, and a next action. Phase
1 is detailed enough to execute from; Phases 2–5 are deliberately lighter —
enough to guide, not so much that they rot before use (charter §3).

**3. Adopt a fixed per-capability session pattern for Phase 1.**
Four stages across 2–4 sessions: research → decide → design → implement+test.
Stages may merge for genuinely small work; the ADR-before-code rule may not be
skipped (charter §8).

**4. State the Phase 1 exit criteria as measurable conditions**, including one
end-to-end composition, so the phase cannot be declared complete on vibes.

## Consequences

- **Phase 1 has now actually started.** It had not before this ADR; the prior
  sessions were Phase 0.
- Progress is measurable: 7 capabilities across 7 categories, each with a
  defined per-capability definition of done.
- The phase plans will drift from reality. That is expected and acceptable —
  they are working documents, revised with evidence, and architectural changes
  to them require an ADR.
- Phase 0's known gaps are now explicit and inherited, rather than forgotten:
  most consequentially, **ADR references in prose are not mechanically checked**
  (found by hand: the roadmap pointed the next session at an existing ADR number).

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Call the completed work Phase 1 and extend its criteria** | Rewrites the charter's definition. Phase 1 means *capabilities seeded*; renaming it would make "5–10 categories with patterns" unmeasurable. |
| **Amend charter §30 to add a sixth phase permanently** | The charter is the constitution and should change rarely. An ADR + a phase doc records this adequately; if Phase 0 becomes a recurring concept, amend the charter then. |
| **Leave the phase model alone and just note the discrepancy** | That is what caused the confusion. A note is not a structure. |
| **Write fully-detailed plans for all five phases** | Charter §3 and the scope-discipline rules: planning detail beyond what can be acted on is speculative. Phases 2–5 are lighter by design. |
| **Skip formal exit criteria and work the queue directly** | Rejected: without exit criteria a phase cannot be completed, only abandoned — and "is Phase 1 done?" became unanswerable. |

## Charter references

§3 (complexity earns its place), §4 (honest status), §8 (decide before
building), §12 (decision records), §24 (prioritization), §25 (session protocol),
§30 (growth model).

## Taxonomy impact

None. All 7 capabilities remain `DISCOVERED`. This ADR changes *process*, not
capability status.