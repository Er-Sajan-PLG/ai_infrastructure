"""Tests for the Memory Framework capability."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pathlib import Path as _Path

_catalog_root = _Path(__file__).resolve().parents[3]
for _cat in (
    "tools",
    "models",
    "agents",
    "observability",
    "protocols",
    "deployment",
    "memory",
    "retrieval",
    "evaluation",
    "guardrails",
):
    _p = str(_catalog_root / _cat)
    sys.path.insert(0, _p)

import pytest  # noqa: E402
from framework import (  # noqa: E402
    HashEmbedder,
    ImportanceEviction,
    InMemoryMemory,
    LRUEviction,
    MemoryItem,
    TTLEviction,
    WholeTextExtractor,
    cosine,
)


def test_add_whole_text_stores_one_item() -> None:
    mem = InMemoryMemory()
    mid = mem.add("Priya is my manager.", scope="u")
    assert mid.startswith("u::")
    assert len(mem) == 1


def test_search_returns_relevant_item() -> None:
    mem = InMemoryMemory()
    mem.add("Priya is my manager.", scope="u")
    mem.add("I like pizza.", scope="u")
    results = mem.search("Who manages me?", scope="u", k=2)
    assert len(results) >= 1
    assert any("Priya" in r.text for r in results)


def test_search_filters_by_scope() -> None:
    mem = InMemoryMemory()
    mem.add("secret", scope="a")
    mem.add("public", scope="b")
    assert len(mem.search("x", scope="a", k=5)) == 1
    assert len(mem.search("x", scope="b", k=5)) == 1


def test_search_empty_query_returns_empty() -> None:
    mem = InMemoryMemory()
    mem.add("hello", scope="u")
    assert mem.search("", scope="u") == ()


def test_extractor_splits_facts() -> None:
    class SplitExtractor:
        def extract(self, text: str) -> tuple[str, ...]:
            return tuple(s.strip() for s in text.split(";") if s.strip())

    mem = InMemoryMemory(extractor=SplitExtractor())
    mem.add("fact one; fact two", scope="u")
    assert len(mem) == 2


def test_extractor_empty_falls_back_to_raw() -> None:
    class EmptyExtractor:
        def extract(self, text: str) -> tuple[str, ...]:
            return ()

    mem = InMemoryMemory(extractor=EmptyExtractor())
    mem.add("raw text", scope="u")
    assert len(mem) == 1
    assert mem.search("raw", scope="u")[0].text == "raw text"


def test_consolidate_removes_duplicates() -> None:
    mem = InMemoryMemory()
    mem.add("hello world", scope="u")
    mem.add("hello world", scope="u")
    removed = mem.consolidate(threshold=0.99)
    assert removed == 1
    assert len(mem) == 1


def test_evict_lru() -> None:
    mem = InMemoryMemory()
    mem.add("a", scope="u")
    mem.add("b", scope="u")
    mem.add("c", scope="u")
    evicted = mem.evict(LRUEviction(), capacity=2)
    assert evicted == 1
    assert len(mem) == 2


def test_evict_importance() -> None:
    mem = InMemoryMemory()
    mem.add("low", scope="u", metadata={"importance": 0.1})
    mem.add("high", scope="u", metadata={"importance": 0.9})
    mem.add("mid", scope="u", metadata={"importance": 0.5})
    evicted = mem.evict(ImportanceEviction(), capacity=2)
    assert evicted == 1
    texts = {it.text for it in mem.search("x", scope="u", k=5)}
    assert "low" not in texts


def test_clear_scope() -> None:
    mem = InMemoryMemory()
    mem.add("a", scope="x")
    mem.add("b", scope="y")
    mem.clear(scope="x")
    assert len(mem) == 1
    mem.clear()
    assert len(mem) == 0


def test_hash_embedder_deterministic() -> None:
    e = HashEmbedder(dimensions=8)
    assert e.embed("hello") == e.embed("hello")
    assert len(e.embed("hello")) == 8


def test_cosine() -> None:
    assert cosine((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine((), (1.0,)) == 0.0


def test_whole_text_extractor() -> None:
    assert WholeTextExtractor().extract("hi") == ("hi",)


def test_lru_policy_select() -> None:
    items = [
        MemoryItem(id="1", text="a", created_at=1.0, scope="s"),
        MemoryItem(id="2", text="b", created_at=2.0, scope="s"),
        MemoryItem(id="3", text="c", created_at=3.0, scope="s"),
    ]
    assert LRUEviction().select(items, 2) == ("1",)


def test_lru_policy_no_overflow() -> None:
    items = [MemoryItem(id="1", text="a", created_at=1.0, scope="s")]
    assert LRUEviction().select(items, 5) == ()


def test_ttl_policy_no_expired() -> None:
    items = [
        MemoryItem(
            id="1", text="a", created_at=1.0, scope="s", metadata={"expires_at": 100.0}
        )
    ]
    assert TTLEviction(now=1.0).select(items, 1) == ()


def test_importance_policy_no_overflow() -> None:
    items = [MemoryItem(id="1", text="a", created_at=1.0, scope="s")]
    assert ImportanceEviction().select(items, 5) == ()


def test_hash_embedder_validates_dimensions() -> None:
    with pytest.raises(ValueError):
        HashEmbedder(dimensions=0)


def test_cosine_zero_vector() -> None:
    assert cosine((0.0, 0.0), (1.0, 0.0)) == 0.0


def test_ttl_eviction() -> None:
    mem = InMemoryMemory()
    mem.add("expired", scope="u", metadata={"expires_at": 1.0})
    mem.add("fresh", scope="u", metadata={"expires_at": 100.0})
    mem.add("extra", scope="u", metadata={"expires_at": 100.0})
    evicted = mem.evict(TTLEviction(now=50.0), capacity=2)
    assert evicted == 1


def test_ttl_eviction_none_expired() -> None:
    mem = InMemoryMemory()
    mem.add("a", scope="u", metadata={"expires_at": 100.0})
    assert mem.evict(TTLEviction(now=1.0), capacity=2) == 0


def test_search_skips_unknown_store_ids() -> None:
    mem = InMemoryMemory()
    mid = mem.add("hello", scope="u")
    # Simulate store returning an id absent from _items.
    del mem._items[mid]
    assert mem.search("hello", scope="u", k=2) == ()


def test_consolidate_skips_already_removed() -> None:
    mem = InMemoryMemory()
    mem.add("dup", scope="u")
    mem.add("dup", scope="u")
    mem.add("dup", scope="u")
    removed = mem.consolidate(threshold=0.0)
    assert removed >= 2


def test_clear_scope_with_store() -> None:
    mem = InMemoryMemory()
    mem.add("a", scope="x")
    mem.clear(scope="x")
    assert len(mem) == 0
    assert mem.search("a", scope="x") == ()


def test_clear_all_clears_store() -> None:
    mem = InMemoryMemory()
    mem.add("a", scope="u")
    mem.clear()
    assert len(mem) == 0
    assert mem.search("a", scope="u") == ()


def test_evict_no_overflow() -> None:
    mem = InMemoryMemory()
    mem.add("a", scope="u")
    assert mem.evict(LRUEviction(), capacity=5) == 0
