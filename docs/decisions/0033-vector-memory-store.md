# ADR-0033: Vector Memory Store

**Status:** Accepted
**Date:** 2026-10-08
**Drivers:** Phase 4 Compose — System A needs a vector store; Phase 1 queue has `vector-memory-store` as DISCOVERED

## Context

Phase 4 System A requires a vector memory store. The taxonomy has `vector-memory-store` as DISCOVERED since Phase 1. The study pipeline found vector stores ubiquitous across 25 studied repos (agno has `vectordb/` with 5+ backends, pydantic-ai has `embeddings/`, ragas has `embeddings/`).

The repo's charter requires zero runtime dependencies. This rules out numpy, faiss, chromadb, etc. The implementation must be stdlib-only.

## Decision

Implement `catalog/memory/vector_store/` — an in-memory vector store with:
- Cosine similarity (pure Python)
- LRU eviction with configurable `max_size`
- Caller-assigned IDs (overwrite on duplicate)
- Metadata preservation (not searchable)
- Exact search (no ANN)

## Consequences

- Unblocks `basic-rag-pipeline` (depends on vector-memory-store)
- Unblocks Phase 4 System A (partial adoption)
- Zero runtime dependency maintained
- Performance is O(n*d) per search — fine for <10k items, document the limit

## Evidence

From study pipeline reports (25 repos):
- `agno`: `libs/agno/agno/vectordb/` with cassandra, chroma, qdrant, etc.
- `pydantic-ai`: `pydantic_ai_slim/pydantic_ai/embeddings/`
- `ragas`: `src/ragas/embeddings/`
- `ai`: `packages/openai-compatible/src/embedding/`

## Rejected alternatives

- **numpy**: Rejected — runtime dependency (charter §20)
- **ChromaDB/FAISS/Qdrant**: Rejected — external services, runtime deps
- **Defer**: Rejected — blocks Phase 4 System A and basic-rag-pipeline
