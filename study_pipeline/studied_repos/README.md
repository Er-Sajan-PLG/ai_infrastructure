# studied_repos

One report per studied repository, named `<project>.md` (e.g. `langchain.md`), produced by the study pipeline or written by hand during a research session.

Each report must record:

- Repository, authors, license, and the exact version/commit studied
- What was studied and what was deliberately skipped, with reasons
- Extracted patterns, each mapped to a taxonomy category or flagged as a proposed new category
- For each pattern: what it does, how the original implements it, trade-offs, and what should be adopted or avoided
- Evidence classification for non-obvious claims: FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6)
- Whether any code was reused (currently must be `false` — see [ADR-0002](../../docs/decisions/0002-license-selection.md))
- Link to the corresponding entry in [`../../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md)

## Status

Empty — no repository has been studied yet. Do not create speculative reports.