# Specification: In-Memory Vector Memory Store

## 1. Purpose

A minimal, in-memory vector store for embedding-based similarity search. Zero runtime dependencies (stdlib only). The seam for later pluggable vector backends.

## 2. Interface

```python
class VectorStore:
    def add(self, id: str, embedding: Sequence[float], metadata: dict[str, Any] | None = None) -> None: ...
    def search(self, query: Sequence[float], k: int = 5) -> list[SearchResult]: ...
    def delete(self, id: str) -> bool: ...
    def __len__(self) -> int: ...

@dataclass(frozen=True)
class SearchResult:
    id: str
    score: float  # cosine similarity, -1.0 to 1.0
    metadata: Mapping[str, Any]
```

## 3. Design Decisions

### D-1: Cosine similarity, not dot product
Cosine similarity is bounded [-1, 1] and magnitude-invariant. Dot product is unbounded and favors longer vectors. For text embeddings, cosine is the standard.

### D-2: Pure Python, no numpy
Zero runtime dependency (charter §20). Cosine similarity is O(d) per comparison where d is embedding dimension. For in-memory stores with <10k items, this is fast enough. If performance matters, the caller should use a real vector DB.

### D-3: LRU eviction with configurable max_size
When `max_size` is set and exceeded, the oldest-inserted item is evicted. This bounds memory usage. `max_size=None` means unbounded.

### D-4: Metadata is preserved but not searchable
Metadata is stored and returned with results, but similarity search is embedding-only. Metadata filtering is a future enhancement.

### D-5: IDs are caller-assigned, not generated
The store does not generate IDs. The caller provides a unique `id` for each item. Re-adding with the same ID overwrites.

## 4. Non-Goals

- Persistence (in-memory only)
- Metadata filtering
- Batch operations
- Async interface
- Approximate nearest neighbor (ANN) — exact search only
- Distributed operation

## 5. Error Handling

- Empty query vector → `ValueError`
- k <= 0 → `ValueError`
- k > len(store) → return all items, sorted by score
- Duplicate ID → overwrite (last write wins)
- Empty store → return empty list

## 6. Testing Strategy

- Cosine similarity correctness (orthogonal, identical, opposite vectors)
- LRU eviction order
- Metadata preservation
- Overwrite behavior
- Edge cases (empty store, k > len, k=0)
- Zero vectors (cosine similarity undefined → return 0.0)
