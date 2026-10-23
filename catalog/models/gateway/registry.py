"""Provider registry implementation for the Model Gateway."""

from __future__ import annotations

from threading import Lock

from .protocols import ProviderEntry, ProviderRegistry


class InMemoryProviderRegistry:
    """Thread-safe in-memory provider registry with alias support."""

    def __init__(self) -> None:
        self._entries: dict[str, ProviderEntry] = {}
        self._aliases: dict[str, str] = {}
        self._lock = Lock()

    def register(self, entry: ProviderEntry) -> None:
        with self._lock:
            self._entries[entry.name] = entry

    def unregister(self, name: str) -> None:
        with self._lock:
            self._entries.pop(name, None)
            # Remove aliases pointing at it.
            for k in [k for k, v in self._aliases.items() if v == name]:
                del self._aliases[k]

    def entries_for(self, model: str) -> tuple[ProviderEntry, ...]:
        target = self.resolve(model)
        with self._lock:
            return tuple(e for e in self._entries.values() if e.model == target)

    def alias(self, name: str, target: str) -> None:
        with self._lock:
            self._aliases[name] = target

    def resolve(self, model: str) -> str:
        # Follow alias chain (with cycle guard).
        seen: set[str] = set()
        cur = model
        with self._lock:
            while cur in self._aliases and cur not in seen:
                seen.add(cur)
                cur = self._aliases[cur]
        return cur

    def all_entries(self) -> tuple[ProviderEntry, ...]:
        with self._lock:
            return tuple(self._entries.values())

    def get(self, name: str) -> ProviderEntry | None:
        with self._lock:
            return self._entries.get(name)


def create_registry() -> ProviderRegistry:
    """Factory returning a fresh in-memory registry."""
    return InMemoryProviderRegistry()
