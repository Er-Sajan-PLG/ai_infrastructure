# Context & Memory

> **Status: 2 studies.** `vector-memory-store` is `TESTED` ([ADR-0033](../../docs/decisions/0033-vector-memory-store.md)); `memory-framework` is `DECIDED` ([ADR-0040](../../docs/decisions/0040-memory-framework.md)). See their research records below.

## What it is

Context management, compression, selection, conversation state, working/long-term/episodic/semantic/procedural memory, retrieval, consolidation, forgetting, persistence.

## Why it exists

Context windows are finite and state must outlive a single call. How a system decides what to remember, recall, and forget is a core architectural choice.

## How it works

Research artifacts live at `research/memory/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6). The first record found that vector stores are the most common infrastructure component across studied repositories: every major framework has one, and they vary widely in interface and backend support.

## Variants & types

- **Vector memory store** (`vector-memory-store`) — in-memory cosine similarity over injected embeddings, stdlib-only, LRU eviction.
- **Memory framework** (`memory-framework`) — lifecycle over the store: extraction, consolidation, eviction policies, scoping.

## Landscape

External projects surveyed via the study pipeline (structural analysis only, no code executed or reused): agno (`libs/agno/agno/vectordb/` — cassandra, chroma, qdrant, pgvector, milvus, redis backends), pydantic-ai (embeddings), ragas (evaluation-focused), among others. Registered in [`../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) with the charter §11 schema.

## Our implementations

- [`vector-memory-store`](../../catalog/memory/vector_store/) — `TESTED` (ADR-0033). See [`../TAXONOMY.md`](../../TAXONOMY.md) §4 for lifecycle status.

## When to use / When not to use

- **Use** when an in-process, dependency-free similarity index suffices and embeddings are supplied by the caller.
- **Do not use** when persistence across processes, approximate-nearest-neighbour scale, or rich metadata filtering is required — none is implemented.

## References & citations

- [Research record: vector-memory-store](vector-memory-store.md)
- [Specification: vector-memory-store](../../specifications/vector-memory-store.md)
- [ADR-0033](../../docs/decisions/0033-vector-memory-store.md)
