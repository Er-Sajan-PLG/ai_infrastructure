"""Eviction policies for the Memory Framework."""

from __future__ import annotations

from collections.abc import Sequence

from .protocols import MemoryItem


class LRUEviction:
    """Evict least-recently-added items first.

    ``created_at`` is the insertion stamp; the framework's ``evict`` passes
    items ordered oldest-first, so the policy takes the first overflow.
    """

    def select(self, items: Sequence[MemoryItem], capacity: int) -> tuple[str, ...]:
        overflow = max(0, len(items) - capacity)
        if overflow == 0:
            return ()
        ordered = sorted(items, key=lambda it: (it.created_at, it.id))
        return tuple(it.id for it in ordered[:overflow])


class TTLEviction:
    """Evict items whose TTL has expired (``metadata["expires_at"]``)."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def select(self, items: Sequence[MemoryItem], capacity: int) -> tuple[str, ...]:
        expired = [
            it.id
            for it in items
            if it.metadata.get("expires_at") is not None
            and float(it.metadata["expires_at"]) <= self.now
        ]
        if not expired:
            return ()
        # Only drop as many as needed to reach capacity.
        overflow = max(0, len(items) - capacity)
        return tuple(expired[:overflow])


class ImportanceEviction:
    """Evict the least important items first (``metadata["importance"]``)."""

    def __init__(self, default: float = 0.0) -> None:
        self.default = default

    def select(self, items: Sequence[MemoryItem], capacity: int) -> tuple[str, ...]:
        overflow = max(0, len(items) - capacity)
        if overflow == 0:
            return ()
        ordered = sorted(
            items,
            key=lambda it: (
                float(it.metadata.get("importance", self.default)),
                it.id,
            ),
        )
        return tuple(it.id for it in ordered[:overflow])
