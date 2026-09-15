# ADR-0002 — License Selection

- **Status:** Accepted (supersedes the Proposed state of this ADR)
- **Date:** 2026-01-01
- **Supersedes:** —
- **Superseded by:** —

## Context

This ADR was originally raised as **Proposed** to block code reuse while the
repository had no `LICENSE` file. Charter §22 makes licensing a human review
gate; charter §11 requires reuse and attribution to be tracked precisely, and
the obligations that tracking creates depend on the license this repository
carries.

The maintainer's stated position: the repository is primarily for personal use;
the future is unknown; commercialization (possibly as a product) remains a
possibility; and open-sourcing is plausible if the project matures. There is no
settled position on whether downstream users should be obliged to keep
derivatives open.

That combination — undecided future, explicit possibility of commercialization —
makes **optionality** the governing requirement, not the expression of a value
that has not yet been chosen.

## Decision

**License this repository under Apache-2.0.** `LICENSE` contains the canonical
Apache License, Version 2.0 text; `NOTICE` carries the copyright statement and
the third-party-notices scaffolding.

Reasoning, in the order that decided it:

1. **Permissive does not foreclose commercialization.** The maintainer can build
   a proprietary product on their own Apache-2.0 code without friction, and the
   license does not make the maintainer compete with their own terms.
2. **Permission is the reversible direction.** As sole copyright holder, the
   maintainer may license *future versions* under different terms. The reverse
   move — restrictive to permissive — is not credibly available once the work is
   out under copyleft. Choosing permissive preserves the decision; choosing
   restrictive makes it.
3. **The patent grant matters for infrastructure.** This repository targets a
   patent-dense field (agent orchestration, retrieval, model routing).
   Apache-2.0's express patent grant and retaliation clause protects downstream
   users in a way MIT does not address. For a foundation intended to be built
   upon, that is the substantive difference from MIT.
4. **Compatibility with every current study target.** LangChain, LlamaIndex,
   AutoGen, CrewAI, DSPy, SWE-agent, Semantic Kernel and OpenAI Swarm are MIT;
   Haystack and MemGPT/Letta are Apache-2.0. All are permissive, so Apache-2.0
   keeps `code_reused: true` available for all of them should a future session
   need it. Copyleft here would have constrained charter §29's pipeline.
5. **Contribution clarity.** Apache-2.0 §5's inbound=outbound default permits
   accepting outside contributions without a bespoke CLA mechanism.

### Charter §22 gate satisfied

This decision was escalated to the maintainer and explicitly approved
("Apache-2.0") in the session that produced this ADR. It was not made
unilaterally by an agent.

### Consequence now in force

`docs/registry/RESEARCH_REGISTRY.md` no longer prohibits `code_reused: true`.
The rule that replaces the block is the original charter §11 requirement: any
entry setting `code_reused: true` must record `attribution_requirements`, and
the required notice text must be added to `NOTICE` in the same change. Copying
code remains subject to the charter §9 rule that independent implementations are
written from understanding (`UNDERSTAND → ABSTRACT → DESIGN → IMPLEMENT → TEST`),
not `COPY → RENAME → MODIFY`.

### Explicit non-decision: contribution policy

Commercial optionality depends on retaining the ability to relicense the whole
work later — for example to a source-available license such as BSL 1.1 if a
hosted product emerges. **That ability is destroyed by the first outside
contribution accepted without a relicense grant**, because every contributor's
code would carry Apache-2.0.

This ADR therefore records a deliberate, temporary restriction: **no external
contributions are accepted until a contribution policy (DCO sign-off plus a
relicense grant, or a CLA) is adopted.** This is stated in `CONTRIBUTING.md`.
It costs nothing while the project has one maintainer and preserves the option.

## Consequences

- The repository is legally reusable by third parties under Apache-2.0 terms.
- `code_reused: true` is unblocked, subject to `attribution_requirements` and a
  `NOTICE` update in the same change.
- The maintainer keeps open the option to relicense future versions, provided
  the contribution restriction above holds.
- Choosing Apache-2.0 does **not** and cannot control how the software is used.
  A license governs redistribution, not intent; the maintainer's stated concern
  about downstream intent is not addressable by any open-source license. This is
  recorded so a future session does not misread the license as a safety control.
- If a hosted product emerges, BSL 1.1 or similar remains an option for future
  versions; that would be a new ADR superseding this one.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **MIT** | Simpler, and the common default. Rejected because it is silent on patents in a patent-dense domain; Apache-2.0's grant protects downstream users for a small amount of extra notice obligation. |
| **AGPL-3.0** | Would express "derivatives must stay open." Rejected because it directly conflicts with charter §31's goal of components being adoptable piecemeal (including partial adoption by proprietary systems), and it would constrain reuse from AGPL study targets. Also rejected because it does **not** achieve the maintainer's stated goal — AGPL regulates redistribution, not use, so it cannot control downstream intent while imposing real costs on legitimate adopters. |
| **BSL 1.1 / Elastic License** | Best protection for a future hosted service, but is not OSI open source, is banned by many prospective users, and would forfeit the open-source credibility the project is built on. Recorded as a future option for a mature product, not a starting point. |
| **Defer indefinitely (keep no LICENSE)** | Rejected: absence is read as "public domain" by some consumers, and it blocks all reuse including legitimate reuse. Deferring also removed pressure to settle the contribution-policy question, which is the decision that actually matters. |
| **Dual licensing (Apache-2.0 + commercial)** | Premature: requires a CLA and a product to sell. Available later from this position. |

## Charter references

§11 (Research Registry, Attribution & Intellectual Property), §22 (Human Review
Gates), §28 (Failure & Uncertainty Policy — "licensing is unclear → stop and
request human review"), §29 (study pipeline), §31 (long-term composability goal).

## Taxonomy impact

None directly. Unblocks the `license:` field and the `code_reused` registry
rule; no capability status changes.