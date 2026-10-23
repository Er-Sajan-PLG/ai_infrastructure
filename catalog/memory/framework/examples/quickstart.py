"""Quickstart demonstration of the Memory Framework capability.

Zero network calls in this example.
"""

from __future__ import annotations

from framework import (
    InMemoryMemory,
    LRUEviction,
)


def main() -> None:
    print("=" * 60)
    print("1. Add + search")
    print("=" * 60)
    mem = InMemoryMemory()
    mem.add("Priya is my manager.", scope="u")
    mem.add("I like pizza.", scope="u")
    for r in mem.search("Who manages me?", scope="u", k=2):
        print(f"  {r.text}")

    print("\n" + "=" * 60)
    print("2. Consolidation")
    print("=" * 60)
    mem2 = InMemoryMemory()
    mem2.add("hello world", scope="u")
    mem2.add("hello world", scope="u")
    print(
        f"  before: {len(mem2)}, removed: {mem2.consolidate(threshold=0.99)}, after: {len(mem2)}"
    )

    print("\n" + "=" * 60)
    print("3. Eviction")
    print("=" * 60)
    mem3 = InMemoryMemory()
    for t in ("a", "b", "c"):
        mem3.add(t, scope="u")
    print(
        f"  before: {len(mem3)}, evicted: {mem3.evict(LRUEviction(), capacity=2)}, after: {len(mem3)}"
    )

    print("\nAll demos completed.")


if __name__ == "__main__":
    main()
