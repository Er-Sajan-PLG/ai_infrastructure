# Research Record: Vector Memory Store

**Date:** 2026-10-08
**Status:** Complete
**Sources:** Study pipeline reports (25 repos), taxonomy analysis

## Summary

Vector stores are the most common infrastructure component across studied AI repositories. Every major framework has one, but they vary widely in interface and capability.

## Evidence from Study Pipeline

| Repository | Vector Store Location | Backends/Notes |
|---|---|---|
| agno | `libs/agno/agno/vectordb/` | cassandra, chroma, qdrant, pgvector, milvus, redis |
| pydantic-ai | `pydantic_ai_slim/pydantic_ai/embeddings/` | OpenAI, Gemini, Cohere, Mistral |
| ragas | `src/ragas/embeddings/` | evaluation-focused |
| ai | `packages/openai-compatible/src/embedding/` | OpenAI-compatible |
| haystack | `haystack/components/retrievers/` | in-memory, elasticsearch, opensearch |
| llama_index | `llama-index-core/llama_index/core/vector_stores/` | 50+ integrations |

## Key Findings

1. **Interface convergence**: All implementations share `add`, `search`, `delete` as core operations. Some use `query` instead of `search`.

2. **Similarity metric**: Cosine similarity is the standard. Some support euclidean and dot product as alternatives.

3. **ID management**: Most use caller-assigned IDs. Some auto-generate (UUID).

4. **Metadata**: All support metadata storage. Some support metadata filtering at query time.

5. **Persistence**: In-memory is common for testing/dev. Production systems use external DBs.

6. **Performance**: All production systems use numpy or native code for similarity computation. Pure Python is rare but sufficient for small datasets.

## Design Implications

- **Cosine similarity** is the right default (bounded, magnitude-invariant)
- **Caller-assigned IDs** is simpler and more predictable
- **Pure Python** is acceptable for <10k items (our use case)
- **LRU eviction** is needed to bound memory usage
- **Metadata preservation** without filtering is the minimum viable feature

## Rejected Approaches

- **numpy**: Runtime dependency (charter §20)
- **ANN (HNSW, IVF)**: Overkill for in-memory, adds complexity
- **Metadata filtering**: Future enhancement, not MVP
- **Async interface**: Sync-only matches model-provider-abstraction
