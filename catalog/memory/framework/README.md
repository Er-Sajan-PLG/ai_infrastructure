# Memory Framework

> **Status: `TESTED`.** Memory lifecycle over the vector store: extraction, consolidation, eviction policies, scoping. Zero runtime dependencies — standard library only; composes `vector-memory-store` (ADR-0033).

| | |
|---|---|
| **Capability** | [`memory-framework`](../../../TAXONOMY.md) (category: memory) |
| **Specification** | [`specifications/memory-framework.md`](../../../specifications/memory-framework.md) |
| **Decision** | [ADR-0040](../../../docs/decisions/0040-memory-framework.md) — `IMPLEMENT` |
| **Research** | [`research/memory/memory-framework.md`](../../../research/memory/memory-framework.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — original |

## What it is

A stdlib-only memory framework: a `Memory` protocol (add, search, consolidate,
evict), injected `Extractor` / `Embedder` / `EvictionPolicy` seams, an
`InMemoryMemory` implementation composing `vector-memory-store`, default
extractors/embedders/policies, and scoping. Extraction and embedding are
injected; the framework owns no model calls.

## How it works

```python
from framework import InMemoryMemory, WholeTextExtractor, HashEmbedder

mem = InMemoryMemory()
mem.add("Priya is my manager.", scope="user_priya")
results = mem.search("Who manages me?", scope="user_priya", k=3)
```

**Design decisions:**

- **Composes, doesn't replace** — delegates retrieval to `VectorStore`.
- **Extraction is injected** — `Extractor` protocol; no model in core.
- **Embedding is injected** — `Embedder` protocol.
- **Consolidation is explicit** — `consolidate()` dedupes by cosine similarity.
- **Eviction is a policy** — LRU / TTL / importance; caller chooses.
- **Scoping is a namespace** — `scope` keys every id and filters every search.
- **Zero runtime dependencies** — stdlib only.

## Our implementations

| Implementation | Language | Notes |
|---|---|---|
| [`protocols.py`](protocols.py) | Python | `Memory`, `MemoryItem`, `Extractor`, `Embedder`, `EvictionPolicy`, defaults |
| [`memory.py`](memory.py) | Python | `InMemoryMemory` |
| [`eviction.py`](eviction.py) | Python | `LRUEviction`, `TTLEviction`, `ImportanceEviction` |

## References

- [Mem0](https://github.com/mem0ai/mem0) — fact extraction, ADD-only
- [Zep / Graphiti](https://github.com/getzep/graphiti) — temporal graph, no LLM in read path
- [Letta / MemGPT](https://github.com/letta-ai/letta) — hierarchical tiers
- [LangMem](https://github.com/langchain-ai/langmem) — background consolidation
- [Cognee](https://github.com/topoteretes/cognee) — remember/recall/improve/forget
