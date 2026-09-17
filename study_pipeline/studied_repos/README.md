# studied_repos

One report per studied repository, named `<project>.md` (e.g. `langchain.md`),
produced by the study pipeline or written by hand during a research session.

## What a generated report contains

A pipeline report is a **structural map**: file names, paths and manifests. It
records the repository, the exact commit studied, and `code_reused`, and it
gives every candidate pattern its evidence paths, an evidence-based confidence,
and a stated limitation. It does **not** read every source file and does not
execute anything.

## What a generated report does NOT contain

A pipeline report deliberately stops short of four things, because a script
cannot do them honestly:

| Required here | Why the pipeline cannot supply it |
|---|---|
| **License at the studied version** | Reading a licence file and deciding compatibility is a human review gate (charter §22). The pipeline does not read `LICENSE`. |
| **Trade-offs — what to adopt or avoid** | This is a `DESIGN OPINION` requiring someone to read the code and understand the problem it solves (charter §6). |
| **What was deliberately skipped, and why** | The pipeline skips nothing by choice; it reports what it found. |
| **How the original implements each pattern** | Establishing that requires reading the source. The pipeline establishes only that a directory or dependency is present. |

**A pipeline report alone therefore does not satisfy this README.** It is the
*evidence*, and a session must complete it. The pipeline's own report ends with
"Open questions for the next session" for exactly this reason.

## The two-part convention

When a pipeline report is completed by a session, the additions go in the
research registry under `docs/registry/RESEARCH_REGISTRY.md` — licence, trade-offs,
adopt/avoid, §6 evidence labels — and the report is linked from that entry. This
keeps verified claims separate from generated ones instead of blending them into
one document where a reader cannot tell which is which.

Each report should record:

- Repository, authors, license, and the exact version/commit studied
- What was studied and what was deliberately skipped, with reasons
- Extracted patterns, each mapped to a taxonomy category or flagged as a proposed new category
- For each pattern: what it does, how the original implements it, trade-offs, and what should be adopted or avoided
- Evidence classification for non-obvious claims: FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6)
- Whether any code was reused (currently must be `false` — see [ADR-0002](../../docs/decisions/0002-license-selection.md))
- Link to the corresponding entry in [`docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md)

## Status

Not empty. `llama_index.md` is the Track 2A exit evidence — the first
end-to-end study, of [run-llama/llama_index](https://github.com/run-llama/llama_index)
at commit `fd4a517ad6490f0c8464a13fdf133760b696434a`, completed by a session in
[`RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md).

Track 2B adds reports here; they are read by sessions, not adopted by them.
