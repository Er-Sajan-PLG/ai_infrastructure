"""Core protocols and types for the Memory Framework capability.

The framework owns the memory *lifecycle* — extraction, deduplication,
consolidation, eviction and scoping — and composes ``vector-memory-store``
(ADR-0033) for retrieval. It never replaces the store and never owns the
extraction model call (ADR-0040).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """One stored fact."""

    id: str
    text: str
    embedding: tuple[float, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    scope: str = "default"
    created_at: float = 0.0


@runtime_checkable
class Extractor(Protocol):
    """Turns raw text into facts to remember."""

    def extract(self, text: str) -> tuple[str, ...]:
        """Return the facts found in ``text``."""
        ...


@runtime_checkable
class Embedder(Protocol):
    """Turns text into a vector."""

    def embed(self, text: str) -> tuple[float, ...]:
        """Return the embedding for ``text``."""
        ...


@runtime_checkable
class EvictionPolicy(Protocol):
    """Chooses which memories to drop when capacity is hit."""

    def select(self, items: Sequence[MemoryItem], capacity: int) -> tuple[str, ...]:
        """Return the ids to evict so that at most ``capacity`` remain."""
        ...


@runtime_checkable
class Memory(Protocol):
    """The memory surface."""

    def add(
        self,
        text: str,
        scope: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Extract facts from ``text`` and store each as a memory item."""
        ...

    def search(
        self, query: str, scope: str | None = None, k: int = 5
    ) -> tuple[MemoryItem, ...]:
        """Return up to ``k`` items relevant to ``query`` in ``scope``."""
        ...

    def consolidate(self, threshold: float = 0.95) -> int:
        """Merge near-duplicate items; return the number removed."""
        ...

    def evict(self, policy: EvictionPolicy, capacity: int) -> int:
        """Evict per ``policy`` until at most ``capacity`` remain."""
        ...

    def clear(self, scope: str | None = None) -> None:
        """Remove items in ``scope`` (all scopes if ``None``)."""
        ...


class WholeTextExtractor:
    """Extractor that treats the whole input as one fact (no model call)."""

    def extract(self, text: str) -> tuple[str, ...]:
        return (text,)


class HashEmbedder:
    """Non-semantic bag-of-words embedder for tests and simple use.

    Documented as *not* semantic: it hashes tokens into a fixed-width vector.
    Production callers inject a real embedder.
    """

    def __init__(self, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError(f"dimensions must be positive, got {dimensions}")
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            # Deterministic, order-sensitive hash into the bucket space.
            bucket = hash(token) % self.dimensions
            vector[bucket] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return tuple(v / norm for v in vector)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two vectors (0.0 for empty)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = float(sum(x * y for x, y in zip(a, b, strict=False)))
    na = float(sum(x * x for x in a) ** 0.5)
    nb = float(sum(y * y for y in b) ** 0.5)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot) / (na * nb)
