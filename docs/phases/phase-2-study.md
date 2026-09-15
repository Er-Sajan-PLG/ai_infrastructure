# Phase 2 — Study

**Status:** ⬜ Not started
**Charter basis:** §29 (automated study system), §30 — *"Build the study pipeline; point it at 20–30 major repos."*
**Depends on:** [Phase 1](phase-1-seed.md) complete

## Goal

Build the automated repository-study subsystem and use it to study 20–30 major
AI frameworks, turning `study_pipeline/` from a stub into tested infrastructure.

## Exit criteria

- [ ] `scripts/study_repo.sh <github_url>` works end-to-end
- [ ] Pipeline components exist and are tested: `clone_and_analyze.py`, `pattern_extractor.py`, `classifier.py`, `recreator.py`, `report_generator.py`
- [ ] ≥20 repositories studied with reports in `study_pipeline/studied_repos/`
- [ ] Every studied repo registered in `docs/registry/RESEARCH_REGISTRY.md`
- [ ] ≥3 **new** patterns discovered that were not in the taxonomy — proposed as new `DISCOVERED` entries
- [ ] The pipeline itself has tests (charter §29: it is infrastructure too)

## Method

1. **Clone & analyze** — structural map: top-level layout, entry points, dependency graph, test layout.
2. **Extract** — identify candidate infrastructure patterns and their boundaries.
3. **Understand** — what problem it solves, why built that way, trade-offs.
4. **Recreate** — propose a clean standalone version. *Proposes only* — never auto-commits copied code (charter §9; ADR-0002).
5. **Classify** — map to a taxonomy category, or propose a new one.
6. **Cite** — `PROVENANCE.md` per charter §11.
7. **Log** — study report: found, extracted, skipped and why.

## Target repositories

LangChain, LlamaIndex, AutoGen, CrewAI, DSPy, Haystack, MemGPT/Letta, OpenDevin,
SWE-agent, Semantic Kernel, OpenAI Swarm, Phidata, Mastra, Vercel AI SDK, plus
any that Phase 1 research surfaced.

## Risks

| Risk | Mitigation |
|---|---|
| Laundering copied code as "extraction" | Human review gate before anything enters `catalog/`; `code_reused` tracked honestly |
| Studying breadth-first and understanding nothing | Each report must state trade-offs and what to *avoid*, not just what exists |
| Pipeline becomes the project | Cap effort; the deliverable is knowledge, not tooling |
| License contamination | Registry records license at the studied version before any reuse |

## Next action

After Phase 1 exit criteria are met: design the pipeline's interfaces
(`specifications/study-pipeline.md`) and decide build-vs-adapt.
