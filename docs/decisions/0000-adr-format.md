# ADR-0000 — ADR Format

- **Status:** Accepted
- **Date:** 2026-01-01
- **Supersedes:** —

## Context

Charter §12 requires significant architectural decisions to be recorded in lightweight Architecture Decision Records, linked to the taxonomy entries they affect, so that architecture is explainable from repository history rather than only from its current state.

## Decision

Every ADR in `docs/decisions/` uses the format below and the filename `NNNN-<kebab-slug>.md`, numbered sequentially from `0001`. ADRs are immutable once Accepted: a later ADR supersedes an earlier one, and the earlier one records `Superseded by: NNNN`.

Required sections: **Status**, **Date**, **Context**, **Decision**, **Consequences**, **Alternatives considered**, **Charter references**, **Taxonomy impact**.

Allowed statuses: `Proposed`, `Accepted`, `Superseded by NNNN`, `Rejected`, `Deprecated`.

## Consequences

- Decisions must present the options that were rejected, not only the chosen path (charter §26 step 4).
- A capability's taxonomy entry links to every ADR affecting it.
- ADR-0000 is the format reference for all later ADRs.

## Alternatives considered

- **Informal design notes in `research/`** — rejected: no stable numbers, no supersession trail, no link target for taxonomy entries.
- **A single growing `DECISIONS.md`** — rejected: merge conflicts and no immutability boundary per decision.
- **External wiki** — rejected: the repository must be self-contained and machine-readable.

## Charter references

§12 Decision Records; §26 step 10 (documentation updates).

## Taxonomy impact

None directly. Establishes the record type referenced by all future entries.