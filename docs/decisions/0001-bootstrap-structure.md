# ADR-0001 — Bootstrap the Repository as a Knowledge/Code Plane Split

- **Status:** Accepted
- **Date:** 2026-01-01
- **Supersedes:** —

## Context

The `ai_infrastructure` charter (CHARTER.md) defines a long-lived laboratory: research, architecture knowledge, independent implementations, interoperability, evaluation, and composition. The repository did not exist; this session bootstraps it. The charter's §13 layout is explicitly provisional, and §21 requires honest lifecycle status, so the initial structure must make the *stage* of every capability visible from the paths alone.

Two questions had to be settled before writing files:

1. Which directories exist on day one, given zero implementations?
2. What prevents the repository from degenerating into "a pile of code with research scattered in comments"?

## Decision

Bootstrap the layout as described in `docs/architecture.md`, with these specific choices:

1. **A knowledge plane and a code plane, separated by path.** Research (`research/`, `specifications/`, `TAXONOMY.md`, `docs/decisions/`, `docs/registry/`) carries no executable code; the code plane (`catalog/`, `integrations/`, `benchmarks/`, `examples/`) contains only artifacts at IMPLEMENTED or later. A reader can infer stage from location.
2. **Create the full category directory set now**, including categories with no planned Phase-1 work, each with a `README.md` stub that states its status honestly. Empty categories with explicit "no entries yet" text are honest; a missing directory invites ad-hoc placement.
3. **Seed the taxonomy before the code, with seven DISCOVERED capabilities and `decision: pending`.** No capability in `TAXONOMY.md` claims status beyond DISCOVERED, and every implementation-related field is `""`.
4. **`specifications/` holds DESIGNED-stage artifacts**, keeping design documents out of `catalog/` until implementation begins.
5. **`scripts/validate_catalog.py` exists from day one** so the entry contract (README + PROVENANCE for every catalog entry) is enforced mechanically rather than by memory.
6. **Directory naming discrepancies between planes are intentional and recorded** in `TAXONOMY.md` §1: `research/harnesses` vs `catalog/harness`, `research/mcp` vs `catalog/protocols`, `research/development` vs no catalog peer yet.

## Consequences

- Phase-1 capability work follows the sequence in `docs/roadmap.md`; nothing else is built first.
- Adding a category is an explicit taxonomy edit plus directory creation, never an incidental `mkdir`.
- The validator must be kept in sync if the entry contract changes.
- The layout is still provisional: changing it requires a superseding ADR (charter §13).

## Alternatives considered

- **Create only directories that will be used in Phase 1** — rejected: pushes categories to ad-hoc locations later, and loses the honest "declared but empty" signal.
- **Populate `catalog/` with placeholder skeletons per capability** — rejected: a placeholder file looks like implementation progress and is exactly the research-presented-as-implementation failure of charter §10.
- **Flat `capabilities/` directory with everything in it** — rejected: loses the connection to the §2 category taxonomy that `TAXONOMY.md` is built on.
- **Start the study pipeline first (Phase 2)** — rejected: charter §24 sequences dependency and verifiability first; a validator and two foundational capabilities are verifiable with current resources, the pipeline is not yet.

## Charter references

§13 Repository Architecture; §4 Capability Lifecycle; §10 Wrappers Are Not Reimplementations; §14 Infrastructure Taxonomy; §24 Prioritization & Sequencing.

## Taxonomy impact

Establishes paths for all seeded entries in `TAXONOMY.md` §4: `tool-registry`, `model-provider-abstraction`, `react-agent-loop`, `vector-memory-store`, `basic-rag-pipeline`, `mcp-client`, `execution-trace-recorder`. No entry changes status.