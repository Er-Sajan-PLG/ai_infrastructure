"""In-memory Memory implementation composing the vector store."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from vector_store import VectorStore

from .protocols import (
    Embedder,
    Extractor,
    HashEmbedder,
    MemoryItem,
    WholeTextExtractor,
    cosine,
)


@dataclass(slots=True)
class InMemoryMemory:
    """Memory over an injected ``VectorStore``.

    Composes the store for retrieval; extraction and embedding are injected.
    """

    extractor: Extractor = field(default_factory=WholeTextExtractor)
    embedder: Embedder = field(default_factory=HashEmbedder)
    store: VectorStore | None = None
    _items: dict[str, MemoryItem] = field(default_factory=dict)
    _counter: int = 0

    def __post_init__(self) -> None:
        if self.store is None:
            self.store = VectorStore()

    def _next_id(self, scope: str) -> str:
        self._counter += 1
        return f"{scope}::{self._counter}"

    def add(
        self,
        text: str,
        scope: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        sc = scope or "default"
        meta = dict(metadata or {})
        facts = self.extractor.extract(text)
        if not facts:
            facts = (text,)
        # Store each fact as its own memory item; return the first id.
        first_id: str | None = None
        for fact in facts:
            mid = self._next_id(sc)
            embedding = self.embedder.embed(fact)
            item = MemoryItem(
                id=mid,
                text=fact,
                embedding=tuple(embedding),
                metadata=meta,
                scope=sc,
                created_at=time.time(),
            )
            self._items[mid] = item
            assert self.store is not None
            self.store.add(mid, tuple(embedding), {"text": fact, "scope": sc, **meta})
            if first_id is None:
                first_id = mid
        assert first_id is not None
        return first_id

    def search(
        self, query: str, scope: str | None = None, k: int = 5
    ) -> tuple[MemoryItem, ...]:
        if not query:
            return ()
        sc = scope or "default"
        assert self.store is not None
        vec = self.embedder.embed(query)
        results = self.store.search(list(vec), k=max(k * 4, k))
        out: list[MemoryItem] = []
        for r in results:
            item = self._items.get(r.id)
            if item is None:
                continue
            if item.scope != sc:
                continue
            out.append(item)
            if len(out) >= k:
                break
        return tuple(out)

    def consolidate(self, threshold: float = 0.95) -> int:
        # Group items by scope; within each, merge pairs above threshold.
        removed = 0
        to_remove: set[str] = set()
        scopes: set[str] = {it.scope for it in self._items.values()}
        for sc in scopes:
            items = [
                it
                for it in self._items.values()
                if it.scope == sc and it.id not in to_remove
            ]
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    a, b = items[i], items[j]
                    if a.id in to_remove or b.id in to_remove:
                        continue
                    if cosine(a.embedding, b.embedding) >= threshold:
                        # Keep the older one (a), drop b.
                        to_remove.add(b.id)
                        removed += 1
        for mid in to_remove:
            self._items.pop(mid, None)
            if self.store is not None:
                self.store.delete(mid)
        return removed

    def evict(self, policy: Any, capacity: int) -> int:
        items = list(self._items.values())
        if len(items) <= capacity:
            return 0
        ids = policy.select(items, capacity)
        count = 0
        for mid in ids:
            if mid in self._items:
                del self._items[mid]
                if self.store is not None:
                    self.store.delete(mid)
                count += 1
        return count

    def clear(self, scope: str | None = None) -> None:
        if scope is None:
            ids = list(self._items)
            self._items.clear()
            if self.store is not None:
                for mid in ids:
                    self.store.delete(mid)
            return
        sc = scope
        for mid in [m for m, it in self._items.items() if it.scope == sc]:
            del self._items[mid]
            if self.store is not None:
                self.store.delete(mid)

    def __len__(self) -> int:
        return len(self._items)
