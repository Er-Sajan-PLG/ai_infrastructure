# Specification: `memory-framework`

- **Capability id:** `memory-framework`
- **Name:** Memory Framework (API Class)
- **Lifecycle status:** `DECIDED` — **IMPLEMENT** ([ADR-0040](../docs/decisions/0040-memory-framework.md))
- **Date:** 2026-10-23

## Problem statement and who needs it

`vector-memory-store` (ADR-0033) answers "what is similar to this query?" but
owns none of the memory lifecycle. Components that need memory re-implement
extraction, deduplication, consolidation, eviction and scoping ad hoc. The
consumer is any agent or pipeline that needs durable, scoped memory.

## Interfaces and data flow

```
text (str) + scope
  -> Extractor.extract(text) -> tuple[str, ...]   (injected)
  -> Embedder.embed(fact) -> tuple[float, ...]    (injected)
  -> VectorStore.add(id, embedding, metadata)     (composed)
  -> Memory.add(...) -> MemoryId

query (str) + scope
  -> Embedder.embed(query) -> vector
  -> VectorStore.search(vector, k)
  -> filter by scope -> tuple[MemoryItem, ...]
```

Key types:

- `MemoryId` — a `str` namespace-qualified id.
- `MemoryItem(id, text, embedding, metadata, scope, created_at)` — one stored fact.
- `Memory` — protocol with `add(text, scope=None, metadata=None) -> MemoryId`,
  `search(query, scope=None, k=5) -> tuple[MemoryItem, ...]`,
  `consolidate(threshold=0.95) -> int`, `evict(policy) -> int`,
  `clear(scope=None) -> None`, `__len__() -> int`.
- `Extractor` — protocol: `extract(text: str) -> tuple[str, ...]`.
- `Embedder` — protocol: `embed(text: str) -> tuple[float, ...]`.
- `EvictionPolicy` — protocol: `select(items, capacity) -> tuple[MemoryId, ...]`.

## Invariants

- Retrieval is the vector store's job; the framework only translates text to a
  vector and delegates to `VectorStore.search`.
- Extraction and embedding are injected; the framework has no model dependency.
- Consolidation is explicit (`consolidate()`), not automatic.
- Eviction is a policy the caller chooses; default is none (unbounded store).
- Scoping is a namespace: the `scope` keys every id and filters every search.
- Zero runtime dependencies; stdlib only.

## Error and failure modes

- Empty extraction: `add` stores the raw text as a single fact (so nothing is lost).
- Empty query: `search` returns an empty tuple.
- Non-positive `k`: `ValueError` (delegated to the store).
- Unknown scope: treated as a fresh namespace (no error).

## Concurrency / thread safety

- `InMemoryMemory` is not thread-safe; callers serialise or use one memory per thread.

## Test strategy

- Unit tests: extraction (scripted), embedding (scripted), scoping, consolidation
  dedup, eviction policies (LRU/TTL/importance), search filtering.
- Integration: memory over a real `VectorStore`.
- Coverage floor: ≥90% on changed lines.

## Dependencies

- `vector-memory-store` (composes `VectorStore`).
- `model-provider-abstraction` (injected `ModelCaller` for extraction in production).

## Out of scope

- Contradiction detection (needs a model call).
- Graph substrate / bi-temporal windows.
- Persistence.
- Async API.
