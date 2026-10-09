"""Tests for System A — partial adoption composition.

Composes:
- our runtime: react-agent-loop (TESTED)
- our memory: vector-memory-store (TESTED)
- external provider: scripted OpenAI-shaped LLM (double)
- external embedder: hashing embedder (double)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _sub in (
    "catalog/models",
    "catalog/tools",
    "catalog/agents",
    "catalog/memory",
    "integrations",
):
    sys.path.insert(0, str(_ROOT / _sub))

from agent_loop_end_to_end.scripted_transport import (  # noqa: E402
    MODEL,
    ScriptedTransport,
    openai_response,
)
from model_provider import WireResponse  # noqa: E402
from react_agent_loop import StopReason  # noqa: E402
from system_a_partial.system import HashingEmbedder, build_system_a  # noqa: E402


def _text_response(text: str) -> WireResponse:
    return openai_response(text=text)


class TestHashingEmbedder:
    def test_deterministic(self) -> None:
        embedder = HashingEmbedder(dim=64)
        v1 = embedder.embed("hello world")
        v2 = embedder.embed("hello world")
        assert v1 == v2

    def test_different_text_different_vectors(self) -> None:
        embedder = HashingEmbedder(dim=64)
        v1 = embedder.embed("hello world")
        v2 = embedder.embed("goodbye world")
        assert v1 != v2

    def test_output_dimension(self) -> None:
        embedder = HashingEmbedder(dim=128)
        v = embedder.embed("test")
        assert len(v) == 128

    def test_normalized(self) -> None:
        import math

        embedder = HashingEmbedder(dim=64)
        v = embedder.embed("hello world")
        mag = math.sqrt(sum(x * x for x in v))
        assert mag == pytest.approx(1.0)


class TestSystemAComposition:
    def test_all_components_wired(self) -> None:
        system = build_system_a()
        assert system.vector_store is not None
        assert system.embedder is not None
        assert system.provider is not None
        assert system.caller is not None
        assert system.dispatcher is not None
        assert system.agent is not None

    def test_index_documents(self) -> None:
        system = build_system_a()
        system.index_documents({"doc1": "hello world", "doc2": "goodbye world"})
        assert len(system.vector_store) == 2

    def test_retrieve_returns_results(self) -> None:
        system = build_system_a()
        system.index_documents({"doc1": "hello world", "doc2": "goodbye world"})
        results = system.retrieve("hello")
        assert len(results) >= 1
        assert results[0].id == "doc1"

    def test_retrieve_respects_k(self) -> None:
        system = build_system_a()
        for i in range(10):
            system.index_documents({f"doc{i}": f"document number {i}"})
        results = system.retrieve("document", k=3)
        assert len(results) == 3

    def test_answer_reaches_final_answer(self) -> None:
        system = build_system_a(
            responses=[_text_response("The answer is 42.")],
            documents={"doc1": "The answer to everything is 42."},
        )
        result = system.answer("What is the answer?")
        assert result.reason == StopReason.FINAL_ANSWER
        assert result.final_text is not None

    def test_answer_with_tool_call(self) -> None:
        system = build_system_a(
            responses=[
                openai_response(
                    tool_calls=[("call_1", "rag:retrieve", {"query": "test"})],
                ),
                _text_response("Based on the retrieved documents, the answer is X."),
            ],
            documents={"doc1": "Some content"},
        )
        result = system.answer("test query")
        assert result.reason == StopReason.FINAL_ANSWER

    def test_transport_records_requests(self) -> None:
        system = build_system_a(
            responses=[_text_response("ok")],
            documents={"doc1": "content"},
        )
        system.answer("test")
        assert len(system.transport.requests) >= 1

    def test_no_network(self) -> None:
        system = build_system_a()
        assert isinstance(system.transport, ScriptedTransport)

    def test_model_name_matches(self) -> None:
        system = build_system_a()
        assert system.agent.model == MODEL

    def test_vector_store_is_ours(self) -> None:
        from vector_store import VectorStore

        system = build_system_a()
        assert isinstance(system.vector_store, VectorStore)

    def test_embedder_is_external_double(self) -> None:
        system = build_system_a()
        assert isinstance(system.embedder, HashingEmbedder)
