# ADR-0002 — License Selection Is Deferred to Human Decision

- **Status:** Proposed
- **Date:** 2026-01-01
- **Supersedes:** —

## Context

The repository currently has **no `LICENSE` file**. Charter §22 makes licensing a human review gate, and charter §11 requires that reuse and attribution be tracked precisely. Two facts force this ADR now:

1. Charter §13's proposed layout includes a `LICENSE`, but the charter does not say which license.
2. Phase-1 capabilities will study licensed external projects (`docs/registry/RESEARCH_REGISTRY.md`). The license this repository carries constrains — and is constrained by — what can lawfully be adapted from projects under copyleft licenses, and determines the attribution obligations recorded with `code_reused: true`.

Choosing a license unilaterally would resolve a high-impact ambiguity silently, which charter §22 forbids.

## Decision

**Do not create a `LICENSE` file in this session.** Record the decision as pending human review, and make the absence explicit in `README.md` so no one assumes permissive reuse.

Until a license is chosen, the standing rule for contributors and agents is:

- **Study freely, copy nothing.** Reading documentation and source for architectural understanding is fine and is the point of the research plane.
- **No source code, text, or assets from any external project may be copied into `catalog/`.** Reimplementations must be written from understanding, following `UNDERSTAND → ABSTRACT → DESIGN → IMPLEMENT → TEST` (charter §9).
- **`code_reused: true` is not to be set on any registry entry** while this ADR is Proposed — there is no lawful basis for reuse until the repository's own licensing position is settled.
- Flag any study that appears to require code-level derivation for human review before proceeding.

## Consequences

- The repository is not legally reusable by third parties yet; `README.md` says so plainly.
- Copyleft-heavy candidates (e.g. AGPL projects) can be studied, but their patterns cannot be adapted into this repository until the license question is answered and the compatibility of the chosen license with theirs is assessed.
- The license choice must land before any capability reaches BENCHMARKED/INTEGRATED in a way that embeds third-party-derived logic, and before any external contribution is accepted.
- A follow-up ADR (expected `NNNN-license-selection.md`) will supersede this one and add the `LICENSE` file; until then, this ADR stays Proposed and visible.

## Alternatives considered

- **Pick MIT now** — rejected: it is a plausible default, but it is precisely a §22 gate and would prejudice derivative-work options the maintainer may want (e.g. copyleft compatibility). Not an agent's call.
- **Pick Apache-2.0 now** — rejected for the same reason, plus its patent grant is a deliberate legal position.
- **Pick a copyleft license now to match likely study targets** — rejected: constrains downstream consumers (charter §31 expects many systems to build on this) and is a major compatibility commitment (§22).
- **Ship no license and say nothing** — rejected: absence would be read as "public domain" by some consumers. The gap is now documented and linked from `README.md`.

## Charter references

§11 Research Registry, Attribution & Intellectual Property; §22 Human Review Gates; §28 Failure & Uncertainty Policy ("licensing is unclear → stop and request human review").

## Taxonomy impact

None. Blocks future `license:` field values and any registry entry setting `code_reused: true`.