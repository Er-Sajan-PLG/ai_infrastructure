# ADR-0022 — Configuration & Settings Infrastructure (new taxonomy category)

- **Status:** Accepted
- **Date:** 2026-09-17
- **Supersedes:** —
- **Superseded by:** —

## Context

Phase 2 Track 2B studied **25 AI infrastructure repositories** at pinned commits
using the study pipeline ([ADR-0021](0021-study-pipeline-architecture.md)).
Each report proposes patterns whose category is absent from the taxonomy tree.

The pipeline proposed `config` in **15 of 25 repositories** — the single most
common proposal, and the classifier found no taxonomy category to map it onto.
Charter §2 says a category list is *"for navigation, not strict partitioning"*
and that when something does not fit, *"that's a signal to extend the taxonomy
(§14), not to drop the item."*

**Verified against §2's own text rather than the category-name list.** §2
enumerates what each category covers, and none covers configuration:
`development` covers *"AI coding environments, repository analysis, code
intelligence, patch generation"*; `primitives` covers *"shared low-level
building blocks"* but is a `catalog/`-only container, not a subject area;
`deployment` covers *"containers, sandboxes, model serving, API gateways"*.
Loading settings from environment and files is none of these.

## Decision

Add **`config/` — Configuration & Settings Infrastructure** as a taxonomy
category, and record the evidence as a `DISCOVERED` capability entry.

The category covers: settings objects and their validation, environment-variable
loading and precedence, layered/overridden configuration, secret *referencing*
(not secret storage), per-environment profiles, and configuration schema
declaration.

**Out of scope for this category:** secret management and rotation (that is
`deployment` or a future `secrets` category — storing a credential is not
configuring a program), and feature-flag evaluation *services* (runtime
behaviour control at scale is closer to `orchestration`).

## Options considered and rejected

1. **Map `config` onto `primitives`.** Rejected: `primitives` is an explicitly
   `catalog/`-only container for shared low-level code in *this* repository,
   not a statement about what the studied projects do. Mapping onto it would
   conflate "we put small shared code here" with "configuration is a subject
   area", and the taxonomy would stop describing the field.
2. **Map `config` onto `development`.** Rejected: verified against §2, which
   scopes `development` to AI coding environments and repository analysis.
3. **Add it to `emerging/`.** Rejected as a category error: `emerging/` is for
   *"when a new class appears, evaluate whether it deserves its own category"*.
   This evaluation happened and the answer is yes — with 15/25 convergence it is
   not emerging, it is ubiquitous.
4. **Not create a capability entry, only a category.** Rejected: the charter
   requires a category directory *and* the taxonomy tree to agree, and an empty
   category with no tracked capability is a stub the next session must
   re-derive (charter §24).
5. **Defer entirely to a later phase.** Rejected: the finding is *evidence from
   this phase*. Dropping it discards the phase's own deliverable and would make
   "study 20 repos" produce reports nobody acts on — the rubber-stamp risk named
   in the phase plan.

## Consequences

**Positive.** The taxonomy now names something 60% of major AI frameworks build
and that no existing category covered. The study phase produced a concrete,
evidenced change rather than only documents.

**Negative, stated plainly.**

- **Ubiquity is not importance.** At 15/25 the signal is partly *convention*:
  almost every Python project has a settings module, so this may say more about
  Python packaging than about AI infrastructure. The difficulty rating below
  reflects that — this is likely a small capability, and it is recorded as
  `DISCOVERED` with `decision: pending` precisely so the ubiquity is not
  mistaken for a mandate to build.
- **Category-count growth.** The taxonomy is now 25 top-level entries (22 before this phase, three ADRs each adding one). Each
  addition makes the tree slightly harder to hold in mind, and this ADR accepts
  that cost for one category.
- The pipeline's own `patterns.py` maps `config` to category `tooling`, a name
  that exists in neither the taxonomy nor this new category. **That is a
  known inconsistency**: it produces a proposal rather than a mapping, which is
  the safe direction, but the rule's category should be corrected to `config`
  when the pipeline is next changed for report-quality reasons (ADR-0021's 2B
  rule permits exactly that).

## Evidence

- 15 of 25 studied repositories proposed `config`; see
  [`study_pipeline/studied_repos/`](../../study_pipeline/studied_repos/).
- Taxonomy entry added: `config-and-settings` (`DISCOVERED`, `decision: pending`).
- Criterion: charter §14 (machine-readable taxonomy), §2 (extend rather than
  drop), §24 (priority from evidence).
