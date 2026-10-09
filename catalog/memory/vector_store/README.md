# In-Memory Vector Memory Store

> **Status: `TESTED`.** In-memory vector store with cosine similarity search. Zero runtime dependencies — standard library only.

| | |
|---|---|
| **Capability** | [`vector-memory-store`](../../../TAXONOMY.md) (category: memory) |
| **Specification** | [`specifications/vector-memory-store.md`](../../../specifications/vector-memory-store.md) |
| **Decision** | [ADR-0033](../../../docs/decisions/0033-vector-memory-store.md) — `IMPLEMENT` |
| **Research** | [`research/memory/vector-memory-store.md`](../../../research/memory/vector-memory-store.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — original, inspired-by |

## What it is

A minimal, in-memory vector store for embedding-based similarity search. It stores
caller-provided embeddings, searches by cosine similarity, and evicts oldest items
when a size limit is set. Zero runtime dependencies — pure Python.

## How it works

```python
from vector_store import VectorStore

store = VectorStore(max_size=1000)
store.add("doc1", [0.1, 0.2, 0.3], {"source": "file1.txt"})
store.add("doc2", [0.4, 0.5, 0.6], {"source": "file2.txt"})

results = store.search([0.1, 0.2, 0.3], k=5)
for r in results:
    print(f"{r.id}: {r.score:.4f} — {r.metadata}")
```

**Design decisions:**

- **Cosine similarity** — bounded [-1, 1], magnitude-invariant. Standard for text embeddings.
- **Pure Python** — no numpy. O(n*d) per search, fine for <10k items.
- **LRU eviction** — `max_size` bounds memory; oldest-inserted item evicted first.
- **Caller-assigned IDs** — re-adding with the same ID overwrites.
- **Metadata preserved** — stored and returned with results, not searchable.

## Our implementations

| Implementation | Language | Notes |
|---|---|---|
| [`vector_store.py`](vector_store.py) | Python | In-memory, cosine similarity, LRU eviction |

## References

- [ChromaDB](https://www.trychroma.com/) — open-source vector database
- [FAISS](https://github.com/facebookresearch/faiss) — Facebook AI Similarity Search
- [Qdrant](https://qdrant.tech/) — vector database
- [agno vectordb](https://github.com/agno-agi/agno) — multi-backend vector store abstraction
- [pydantic-ai embeddings](https://ai.pydantic.dev/) — provider-agnostic embeddings
