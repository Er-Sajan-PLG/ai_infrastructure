"""Tests for the basic RAG pipeline.

Every test runs against deterministic doubles -- a dictionary embedder, a
real ``VectorStore`` (it has no external dependencies) and a scripted
generator -- so no network, no model and no API key are required. That is
the point of the injected seams (ADR-0034 D-3..D-5): every stage boundary
is reachable and assertable.
"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path

import pytest

# The entry lives at catalog/retrieval/basic_rag_pipeline/, so the importable
# parents are catalog/retrieval/ (this entry), catalog/memory/ (the store) and
# catalog/models/ (model_provider, imported by the package __init__).
_CATALOG = Path(__file__).resolve().parents[3]
for _sub in ("retrieval", "memory", "models"):
    sys.path.insert(0, str(_CATALOG / _sub))

from basic_rag_pipeline import (  # noqa: E402
    BasicRagPipeline,
    Chunk,
    Citation,
    RagAnswer,
    build_prompt,
    chunk_text,
)
from vector_store import SearchResult, VectorStore  # noqa: E402

# --------------------------------------------------------------------------- #
# Doubles
# --------------------------------------------------------------------------- #


class DictEmbedder:
    """Maps exact texts to fixed vectors; unknown text gets a stable default.

    Deterministic by construction, so rankings are exact assertions rather
    than approximate ones.
    """

    def __init__(self, table: dict[str, list[float]] | None = None) -> None:
        self.table = table or {}
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return self.table.get(text, [1.0, 1.0, 1.0])


class ScriptedGenerator:
    """Returns queued responses and records every prompt it was given."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = (
            list(responses) if responses is not None else ["scripted answer"]
        )
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("generator called more times than scripted")
        return self.responses.pop(0)


PARAGRAPH = (
    "Retrieval augmented generation grounds answers in documents. "
    "A pipeline chunks documents into windows, embeds each window, stores "
    "the vectors, and retrieves the nearest windows for a query. "
    "The retrieved text is then placed into the prompt for one model call."
)


def make_pipeline(
    *,
    size: int = 800,
    overlap: int = 200,
    table: dict[str, list[float]] | None = None,
    responses: list[str] | None = None,
) -> tuple[BasicRagPipeline, DictEmbedder, VectorStore, ScriptedGenerator]:
    embedder = DictEmbedder(table)
    store = VectorStore(max_size=1000)
    generator = ScriptedGenerator(responses)
    pipeline = BasicRagPipeline(
        embedder=embedder, store=store, generator=generator, size=size, overlap=overlap
    )
    return pipeline, embedder, store, generator


# --------------------------------------------------------------------------- #
# chunk_text
# --------------------------------------------------------------------------- #


class TestChunkText:
    def test_empty_text_gives_no_chunks(self) -> None:
        assert chunk_text("", doc_id="d") == []

    def test_short_text_is_one_chunk_with_offsets(self) -> None:
        chunks = chunk_text("hello world", doc_id="d", size=100, overlap=10)
        assert chunks == [
            Chunk(
                id="d#0",
                doc_id="d",
                index=0,
                text="hello world",
                start=0,
                end=11,
            )
        ]

    def test_rejects_bad_size(self) -> None:
        with pytest.raises(ValueError, match="size"):
            chunk_text("text", doc_id="d", size=0)

    def test_rejects_negative_overlap(self) -> None:
        with pytest.raises(ValueError, match="overlap"):
            chunk_text("text", doc_id="d", overlap=-1)

    def test_rejects_overlap_not_smaller_than_size(self) -> None:
        with pytest.raises(ValueError, match="smaller than size"):
            chunk_text("text", doc_id="d", size=10, overlap=10)
        with pytest.raises(ValueError, match="smaller than size"):
            chunk_text("text", doc_id="d", size=10, overlap=11)

    def test_rejects_empty_doc_id(self) -> None:
        with pytest.raises(ValueError, match="doc_id"):
            chunk_text("text", doc_id="")

    def test_chunks_cover_text_and_offsets_slice_exactly(self) -> None:
        chunks = chunk_text(PARAGRAPH, doc_id="doc", size=80, overlap=20)
        assert len(chunks) > 1
        assert chunks[0].start == 0
        assert chunks[-1].end == len(PARAGRAPH)
        for i, chunk in enumerate(chunks):
            assert chunk.id == f"doc#{i}"
            assert chunk.index == i
            assert PARAGRAPH[chunk.start : chunk.end] == chunk.text

    def test_neighbouring_windows_overlap_and_progress(self) -> None:
        chunks = chunk_text(PARAGRAPH, doc_id="doc", size=80, overlap=20)
        for previous, current in pairwise(chunks):
            assert current.start < previous.end  # overlap > 0
            assert current.end > previous.end  # forward progress

    def test_cut_lands_on_whitespace_when_available(self) -> None:
        text = "aaaa bbbb cccc dddd eeee ffff"
        chunks = chunk_text(text, doc_id="d", size=11, overlap=2)
        for chunk in chunks[:-1]:
            assert text[chunk.end] in " \n\t"

    def test_unbroken_text_still_progresses(self) -> None:
        text = "x" * 50
        chunks = chunk_text(text, doc_id="d", size=10, overlap=3)
        # No whitespace to snap to: every window is exactly `size` long and
        # the next starts at end - overlap. Starts: 0,7,...,42 -> 7 windows.
        assert len(chunks) == 7
        for previous, current in pairwise(chunks):
            assert len(previous.text) == 10
            assert current.start == previous.start + 7

    def test_zero_overlap_gives_disjoint_windows(self) -> None:
        chunks = chunk_text("abcdefghij", doc_id="d", size=5, overlap=0)
        assert [c.text for c in chunks] == ["abcde", "fghij"]
        assert [c.start for c in chunks] == [0, 5]

    def test_chunking_is_deterministic(self) -> None:
        first = chunk_text(PARAGRAPH, doc_id="doc", size=70, overlap=15)
        second = chunk_text(PARAGRAPH, doc_id="doc", size=70, overlap=15)
        assert first == second


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #


class TestIndex:
    def test_returns_chunk_count_and_stores_chunks(self) -> None:
        pipeline, embedder, store, _ = make_pipeline()
        count = pipeline.index({"a": "first doc", "b": "second doc"})
        assert count == 2
        assert len(store) == 2
        assert sorted(embedder.calls) == ["first doc", "second doc"]

    def test_stores_text_and_metadata(self) -> None:
        pipeline, _, store, _ = make_pipeline()
        pipeline.index({"doc-1": "retrieval text"})
        result = store.search([1.0, 1.0, 1.0], k=1)[0]
        assert result.id == "doc-1#0"
        assert result.metadata["doc_id"] == "doc-1"
        assert result.metadata["chunk_index"] == 0
        assert result.metadata["text"] == "retrieval text"

    def test_empty_mapping_is_a_noop(self) -> None:
        pipeline, _, store, _ = make_pipeline()
        assert pipeline.index({}) == 0
        assert len(store) == 0

    def test_empty_document_text_contributes_no_chunks(self) -> None:
        pipeline, _, store, _ = make_pipeline()
        assert pipeline.index({"doc-1": ""}) == 0
        assert len(store) == 0

    def test_configured_chunking_is_applied(self) -> None:
        pipeline, _, store, _ = make_pipeline(size=5, overlap=0)
        assert pipeline.index({"d": "abcdefghij"}) == 2
        assert len(store) == 2

    def test_reindexing_same_document_overwrites(self) -> None:
        pipeline, _, store, _ = make_pipeline()
        pipeline.index({"doc-1": "original text"})
        pipeline.index({"doc-1": "original text"})
        assert len(store) == 1

    def test_rejects_empty_doc_id(self) -> None:
        pipeline, _, _, _ = make_pipeline()
        with pytest.raises(ValueError, match="doc_id"):
            pipeline.index({"": "text"})


# --------------------------------------------------------------------------- #
# retrieve
# --------------------------------------------------------------------------- #


class TestRetrieve:
    def _indexed(
        self,
    ) -> tuple[BasicRagPipeline, DictEmbedder, VectorStore, ScriptedGenerator]:
        table = {
            "apple doc": [1.0, 0.0, 0.0],
            "banana doc": [0.0, 1.0, 0.0],
            "carrot doc": [0.0, 0.0, 1.0],
            "q321": [3.0, 2.0, 1.0],
        }
        pipeline, embedder, store, generator = make_pipeline(table=table)
        pipeline.index(
            {"apple": "apple doc", "banana": "banana doc", "carrot": "carrot doc"}
        )
        return pipeline, embedder, store, generator

    def test_ranked_by_similarity(self) -> None:
        pipeline, _, _, _ = self._indexed()
        results = pipeline.retrieve("q321", k=3)
        assert [r.id for r in results] == ["apple#0", "banana#0", "carrot#0"]
        assert results[0].score > results[1].score > results[2].score

    def test_k_limits_results(self) -> None:
        pipeline, _, _, _ = self._indexed()
        assert len(pipeline.retrieve("q321", k=1)) == 1

    def test_k_over_size_returns_everything(self) -> None:
        pipeline, _, _, _ = self._indexed()
        assert len(pipeline.retrieve("q321", k=99)) == 3

    def test_k_must_be_positive(self) -> None:
        pipeline, _, _, _ = self._indexed()
        with pytest.raises(ValueError):
            pipeline.retrieve("q321", k=0)

    def test_whitespace_query_is_rejected(self) -> None:
        pipeline, _, _, _ = self._indexed()
        with pytest.raises(ValueError, match="query"):
            pipeline.retrieve("   ")

    def test_empty_query_is_rejected(self) -> None:
        pipeline, _, _, _ = self._indexed()
        with pytest.raises(ValueError, match="query"):
            pipeline.retrieve("")

    def test_empty_store_returns_no_results(self) -> None:
        pipeline, _, _, _ = make_pipeline()
        assert pipeline.retrieve("anything") == []


# --------------------------------------------------------------------------- #
# build_prompt
# --------------------------------------------------------------------------- #


class TestBuildPrompt:
    def test_includes_query_chunk_ids_and_context_text(self) -> None:
        results = [
            SearchResult(id="doc#0", score=0.9, metadata={"text": "alpha text"}),
            SearchResult(id="doc#1", score=0.5, metadata={"text": "beta text"}),
        ]
        prompt = build_prompt("what?", results)
        assert "Question: what?" in prompt
        assert "[doc#0] alpha text" in prompt
        assert "[doc#1] beta text" in prompt

    def test_empty_results_state_no_documents_retrieved(self) -> None:
        prompt = build_prompt("what?", [])
        assert "(no documents retrieved)" in prompt
        assert "Question: what?" in prompt


# --------------------------------------------------------------------------- #
# answer
# --------------------------------------------------------------------------- #


class TestAnswer:
    def _indexed(
        self, responses: list[str] | None = None
    ) -> tuple[BasicRagPipeline, DictEmbedder, VectorStore, ScriptedGenerator]:
        table = {
            "apple doc": [1.0, 0.0, 0.0],
            "banana doc": [0.0, 1.0, 0.0],
            "q321": [3.0, 2.0, 1.0],
        }
        pipeline, embedder, store, generator = make_pipeline(
            table=table, responses=responses
        )
        pipeline.index({"apple": "apple doc", "banana": "banana doc"})
        return pipeline, embedder, store, generator

    def test_generates_once_and_reports_citations(self) -> None:
        pipeline, _, _, generator = self._indexed(["the answer"])
        answer = pipeline.answer("q321", k=2)
        assert isinstance(answer, RagAnswer)
        assert answer.text == "the answer"
        assert len(generator.prompts) == 1
        assert [c.chunk_id for c in answer.citations] == ["apple#0", "banana#0"]
        assert [c.doc_id for c in answer.citations] == ["apple", "banana"]

    def test_citations_match_retrieval_scores_and_order(self) -> None:
        pipeline, _, _, _ = self._indexed()
        results = pipeline.retrieve("q321", k=2)
        answer = pipeline.answer("q321", k=2)
        assert answer.citations == tuple(
            Citation(
                chunk_id=r.id,
                doc_id=str(r.metadata["doc_id"]),
                score=r.score,
            )
            for r in results
        )

    def test_prompt_seen_by_generator_contains_context_and_question(self) -> None:
        pipeline, _, _, generator = self._indexed()
        pipeline.answer("q321", k=1)
        prompt = generator.prompts[0]
        assert "[apple#0] apple doc" in prompt
        assert "Question: q321" in prompt

    def test_empty_store_still_generates_with_no_citations(self) -> None:
        pipeline, _, _, generator = make_pipeline(responses=["ungrounded"])
        answer = pipeline.answer("anything")
        assert answer.text == "ungrounded"
        assert answer.citations == ()
        assert "(no documents retrieved)" in generator.prompts[0]

    def test_k_is_passed_through(self) -> None:
        pipeline, _, _, _ = self._indexed()
        assert len(pipeline.answer("q321", k=1).citations) == 1

    def test_generator_errors_propagate(self) -> None:
        class ExplodingGenerator:
            def generate(self, prompt: str) -> str:
                raise RuntimeError("provider down")

        failing = BasicRagPipeline(
            embedder=DictEmbedder({"q321": [3.0, 2.0, 1.0]}),
            store=VectorStore(max_size=10),
            generator=ExplodingGenerator(),
        )
        with pytest.raises(RuntimeError, match="provider down"):
            failing.answer("q321")

    def test_answer_rejects_whitespace_query(self) -> None:
        pipeline, _, _, _ = self._indexed()
        with pytest.raises(ValueError, match="query"):
            pipeline.answer("  ")
