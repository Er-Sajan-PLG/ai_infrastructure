"""Memory Framework — lifecycle over the vector store.

Provides the ``Memory`` protocol (add, search, consolidate, evict), injected
``Extractor`` / ``Embedder`` / ``EvictionPolicy`` seams, an ``InMemoryMemory``
implementation composing ``vector-memory-store``, and default extractors /
embedders / eviction policies.

Zero runtime dependencies — standard library only. Extraction and embedding
are injected; the framework owns no model calls.

See specifications/memory-framework.md for the design and
docs/decisions/0040-memory-framework.md for the decision.
"""

from __future__ import annotations

from .eviction import ImportanceEviction, LRUEviction, TTLEviction
from .memory import InMemoryMemory
from .protocols import (
    Embedder,
    EvictionPolicy,
    Extractor,
    HashEmbedder,
    Memory,
    MemoryItem,
    WholeTextExtractor,
    cosine,
)

__all__ = [
    "Embedder",
    "EvictionPolicy",
    "Extractor",
    "HashEmbedder",
    "ImportanceEviction",
    "InMemoryMemory",
    "LRUEviction",
    "Memory",
    "MemoryItem",
    "TTLEviction",
    "WholeTextExtractor",
    "cosine",
]
