"""In-memory vector store with cosine similarity search.

Zero runtime dependencies (stdlib only). Exact search, LRU eviction,
caller-assigned IDs. The seam for later pluggable vector backends.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One search result: ID, similarity score, and metadata."""

    id: str
    score: float
    metadata: Mapping[str, Any]


class VectorStore:
    """In-memory vector store with cosine similarity search.

    Exact search (not ANN). LRU eviction when max_size is set.
    Caller-assigned IDs; re-adding with the same ID overwrites.

    Zero runtime dependencies — pure Python.
    """

    def __init__(self, max_size: int | None = None) -> None:
        """Initialize the store.

        Args:
            max_size: Maximum number of items. When exceeded, the oldest
                item is evicted. None means unbounded.
        """
        if max_size is not None and max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        self._max_size = max_size
        # OrderedDict maintains insertion order for LRU eviction
        self._items: OrderedDict[str, tuple[Sequence[float], dict[str, Any]]] = (
            OrderedDict()
        )

    def add(
        self,
        id: str,
        embedding: Sequence[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add or update an item.

        Args:
            id: Caller-assigned unique identifier.
            embedding: Vector representation.
            metadata: Optional metadata dict.

        Raises:
            ValueError: If embedding is empty.
        """
        if not embedding:
            raise ValueError("embedding must not be empty")
        # Move to end if already exists (LRU: most recently used)
        if id in self._items:
            del self._items[id]
        self._items[id] = (list(embedding), metadata or {})
        # Evict oldest if over capacity
        if self._max_size is not None and len(self._items) > self._max_size:
            self._items.popitem(last=False)

    def search(self, query: Sequence[float], k: int = 5) -> list[SearchResult]:
        """Search for the k most similar items.

        Args:
            query: Query vector.
            k: Number of results to return.

        Returns:
            Up to k SearchResult objects, sorted by score descending.

        Raises:
            ValueError: If query is empty or k <= 0.
        """
        if not query:
            raise ValueError("query must not be empty")
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")

        if not self._items:
            return []

        query_list = list(query)
        results: list[SearchResult] = []
        for id, (embedding, metadata) in self._items.items():
            score = _cosine_similarity(query_list, embedding)
            results.append(SearchResult(id=id, score=score, metadata=metadata))

        # Sort by score descending, then by ID for stability
        results.sort(key=lambda r: (-r.score, r.id))
        return results[:k]

    def delete(self, id: str) -> bool:
        """Delete an item by ID.

        Returns:
            True if the item existed and was deleted, False otherwise.
        """
        if id in self._items:
            del self._items[id]
            return True
        return False

    def __len__(self) -> int:
        return len(self._items)


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns a value in [-1, 1]. If either vector has zero magnitude,
    returns 0.0 (cosine similarity is undefined for zero vectors).
    """
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")

    dot_product = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)
