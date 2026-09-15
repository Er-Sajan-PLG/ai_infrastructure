# Documentation Index

How to navigate this repository's documentation. Read in this order when you are new; jump directly when you are not.

## Orientation

| Document | Read it when |
|---|---|
| [`../README.md`](../README.md) | First — orientation and current status |
| [`../CHARTER.md`](../CHARTER.md) | You need the *reasoning* behind a rule. The constitution |
| [`standards.md`](standards.md) | You are about to do work and want the enforceable rules |
| [`development.md`](development.md) | You need to set up or run the environment |
| [`roadmap.md`](roadmap.md) | You want to know what's next and why |
| [`phases/`](phases/) | You want the executable plan for the current (or next) phase |
| [`architecture.md`](architecture.md) | You need to know where something belongs |
| [`philosophy.md`](philosophy.md) | You need the engineering attitude behind the rules |

## Reference

| Document | Contents |
|---|---|
| [`../TAXONOMY.md`](../TAXONOMY.md) | Capability registry: status, priority, dependencies, artifacts |
| [`../AGENTS.md`](../AGENTS.md) | Agent session instructions (start/end-of-session protocol) |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | How to add a capability |
| [`decisions/`](decisions/) | ADRs — why decisions were taken |
| [`registry/RESEARCH_REGISTRY.md`](registry/RESEARCH_REGISTRY.md) | External projects studied; licensing and attribution |

## Documentation rules

- A document states its status when it could be mistaken for something else
  ("not implemented", "normative", "proposal").
- The charter is the source of truth. If another document disagrees with it,
  the other document is the bug.
- Evidence class is labelled for non-obvious claims: FACT / OBSERVATION /
  INFERENCE / DESIGN OPINION / EXPERIMENTAL RESULT (charter §6).
- Do not duplicate the charter. Summarize it and link to the section — a second
  copy is a second thing to drift (charter §23).