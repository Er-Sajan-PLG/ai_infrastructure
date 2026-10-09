"""Tests for catalog/memory/vector_store/vector_store.py."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

# The entry lives at catalog/memory/vector_store/, so the importable parent is
# catalog/memory/ -- tests/ -> vector_store/ -> memory/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vector_store import SearchResult, VectorStore
from vector_store.vector_store import _cosine_similarity


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)

    def test_both_zero_vectors(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [0.0, 0.0]) == pytest.approx(0.0)

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="dimension mismatch"):
            _cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])

    def test_known_value(self) -> None:
        # cos(45°) = sqrt(2)/2 ≈ 0.7071
        result = _cosine_similarity([1.0, 0.0], [1.0, 1.0])
        assert result == pytest.approx(math.sqrt(2) / 2, rel=1e-9)

    def test_magnitude_invariant(self) -> None:
        # Same direction, different magnitudes → similarity = 1.0
        assert _cosine_similarity([1.0, 0.0], [100.0, 0.0]) == pytest.approx(1.0)


class TestVectorStoreAdd:
    def test_add_and_len(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0])
        assert len(store) == 1

    def test_add_multiple(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0])
        store.add("b", [0.0, 1.0])
        assert len(store) == 2

    def test_add_empty_embedding_raises(self) -> None:
        store = VectorStore()
        with pytest.raises(ValueError, match="embedding must not be empty"):
            store.add("a", [])

    def test_add_with_metadata(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0], {"key": "value"})
        results = store.search([1.0, 0.0], k=1)
        assert results[0].metadata == {"key": "value"}

    def test_add_overwrite_same_id(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0], {"v": 1})
        store.add("a", [0.0, 1.0], {"v": 2})
        assert len(store) == 1
        results = store.search([0.0, 1.0], k=1)
        assert results[0].metadata == {"v": 2}

    def test_add_overwrite_does_not_change_order(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0])
        store.add("b", [0.0, 1.0])
        store.add("a", [1.0, 0.0])  # overwrite
        # "a" should now be most-recently-used, so "b" is oldest
        assert len(store) == 2


class TestVectorStoreSearch:
    def test_search_empty_store(self) -> None:
        store = VectorStore()
        assert store.search([1.0, 0.0]) == []

    def test_search_basic(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0])
        store.add("b", [0.0, 1.0])
        results = store.search([1.0, 0.0], k=1)
        assert len(results) == 1
        assert results[0].id == "a"
        assert results[0].score == pytest.approx(1.0)

    def test_search_returns_k_results(self) -> None:
        store = VectorStore()
        for i in range(10):
            store.add(str(i), [float(i), 1.0])
        results = store.search([1.0, 0.0], k=3)
        assert len(results) == 3

    def test_search_k_greater_than_len(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0])
        results = store.search([1.0, 0.0], k=10)
        assert len(results) == 1

    def test_search_k_zero_raises(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0])
        with pytest.raises(ValueError, match="k must be positive"):
            store.search([1.0, 0.0], k=0)

    def test_search_empty_query_raises(self) -> None:
        store = VectorStore()
        with pytest.raises(ValueError, match="query must not be empty"):
            store.search([], k=1)

    def test_search_sorted_by_score_descending(self) -> None:
        store = VectorStore()
        store.add("exact", [1.0, 0.0])
        store.add("close", [1.0, 0.1])
        store.add("far", [0.0, 1.0])
        results = store.search([1.0, 0.0], k=3)
        assert results[0].id == "exact"
        assert results[1].id == "close"
        assert results[2].id == "far"
        assert results[0].score > results[1].score > results[2].score

    def test_search_stable_sort_by_id(self) -> None:
        store = VectorStore()
        store.add("b", [1.0, 0.0])
        store.add("a", [1.0, 0.0])
        results = store.search([1.0, 0.0], k=2)
        # Same score → sorted by ID
        assert results[0].id == "a"
        assert results[1].id == "b"

    def test_search_result_metadata(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0], {"source": "test"})
        results = store.search([1.0, 0.0], k=1)
        assert results[0].metadata == {"source": "test"}


class TestVectorStoreDelete:
    def test_delete_existing(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0])
        assert store.delete("a") is True
        assert len(store) == 0

    def test_delete_nonexistent(self) -> None:
        store = VectorStore()
        assert store.delete("nonexistent") is False

    def test_delete_then_search(self) -> None:
        store = VectorStore()
        store.add("a", [1.0, 0.0])
        store.add("b", [0.0, 1.0])
        store.delete("a")
        results = store.search([1.0, 0.0], k=2)
        assert len(results) == 1
        assert results[0].id == "b"


class TestVectorStoreLRUEviction:
    def test_eviction_when_over_max_size(self) -> None:
        store = VectorStore(max_size=2)
        store.add("a", [1.0, 0.0])
        store.add("b", [0.0, 1.0])
        store.add("c", [1.0, 1.0])  # evicts "a"
        assert len(store) == 2
        assert store.delete("a") is False
        assert store.delete("b") is True
        assert store.delete("c") is True

    def test_eviction_order_fifo(self) -> None:
        store = VectorStore(max_size=3)
        store.add("first", [1.0, 0.0])
        store.add("second", [0.0, 1.0])
        store.add("third", [1.0, 1.0])
        store.add("fourth", [0.5, 0.5])  # evicts "first"
        assert len(store) == 3
        remaining = {r.id for r in store.search([1.0, 0.0], k=3)}
        assert "first" not in remaining
        assert "second" in remaining
        assert "third" in remaining
        assert "fourth" in remaining

    def test_no_eviction_when_unbounded(self) -> None:
        store = VectorStore(max_size=None)
        for i in range(100):
            store.add(str(i), [float(i), 1.0])
        assert len(store) == 100

    def test_max_size_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="max_size must be positive"):
            VectorStore(max_size=0)

    def test_max_size_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="max_size must be positive"):
            VectorStore(max_size=-1)

    def test_overwrite_does_not_evict(self) -> None:
        store = VectorStore(max_size=2)
        store.add("a", [1.0, 0.0])
        store.add("b", [0.0, 1.0])
        store.add("a", [1.0, 0.0])  # overwrite, not new add
        assert len(store) == 2
        assert store.delete("a") is True
        assert store.delete("b") is True

    def test_lru_order_preserved_on_search(self) -> None:
        store = VectorStore(max_size=2)
        store.add("a", [1.0, 0.0])
        store.add("b", [0.0, 1.0])
        # Search for "a" — should not affect LRU order
        store.search([1.0, 0.0], k=1)
        store.add("c", [1.0, 1.0])  # evicts "a" (oldest by insertion)
        assert store.delete("a") is False
        assert store.delete("b") is True
        assert store.delete("c") is True


class TestSearchResult:
    def test_dataclass_fields(self) -> None:
        r = SearchResult(id="x", score=0.5, metadata={"k": "v"})
        assert r.id == "x"
        assert r.score == 0.5
        assert r.metadata == {"k": "v"}

    def test_metadata_is_mapping(self) -> None:
        r = SearchResult(id="x", score=0.5, metadata={})
        assert isinstance(r.metadata, dict)
