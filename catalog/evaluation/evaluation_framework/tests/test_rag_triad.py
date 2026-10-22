"""Tests for RAG triad evaluators (with mock ModelCaller)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The entry lives at catalog/evaluation/, so the importable parent is catalog/ -- tests/ -> evaluation/ -> catalog/.
# Must be done BEFORE any other imports to make catalog subdirectories discoverable.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Now add all catalog subdirectories to path
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
):
    _p = str(_catalog_root / _cat)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402
from evaluation_framework.evaluators.rag_triad import (  # noqa: E402
    AnswerRelevance,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)
from vector_store import SearchResult  # noqa: E402

# ---------------------------------------------------------------------------
# Mock ModelCaller
# ---------------------------------------------------------------------------


@dataclass
class MockChatResponse:
    text: str
    blocks: tuple[Any, ...] = ()
    tool_calls: tuple[Any, ...] = ()
    usage: None = None
    model: str = "mock"
    provider: str = "mock"
    finish_reason: str = "stop"
    raw_finish_reason: str = "stop"


class MockModelCaller:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0
        self.calls: list[Any] = []

    def call(self, messages: Any, *, system: Any = None, tools: Any = ()) -> Any:
        self.calls.append({"messages": messages, "system": system, "tools": tools})
        if self.index >= len(self.responses):
            return MockChatResponse(text="SCORE: 0.5\nREASONING: Default")
        response_text = self.responses[self.index]
        self.index += 1
        return MockChatResponse(text=response_text)


# ---------------------------------------------------------------------------
# Faithfulness Tests
# ---------------------------------------------------------------------------


class TestFaithfulness:
    def test_high_score(self) -> None:
        caller = MockModelCaller(["SCORE: 0.9\nREASONING: Fully faithful"])
        evaluator = Faithfulness(caller, threshold=0.7)
        chunks = [
            SearchResult(
                id="doc#0", score=0.9, metadata={"text": "AI provides verification"}
            )
        ]
        result = evaluator.evaluate(
            input="What is AI?", output="AI provides verification", context=chunks
        )
        assert result.score == 0.9
        assert result.passed
        assert len(caller.calls) == 1

    def test_low_score(self) -> None:
        caller = MockModelCaller(["SCORE: 0.2\nREASONING: Hallucinated"])
        evaluator = Faithfulness(caller, threshold=0.7)
        chunks = [
            SearchResult(
                id="doc#0", score=0.9, metadata={"text": "AI provides verification"}
            )
        ]
        result = evaluator.evaluate(
            input="What is AI?", output="AI cooks pasta", context=chunks
        )
        assert result.score == 0.2
        assert not result.passed

    def test_threshold_boundary(self) -> None:
        caller = MockModelCaller(["SCORE: 0.7\nREASONING: Borderline"])
        evaluator = Faithfulness(caller, threshold=0.7)
        chunks = [SearchResult(id="doc#0", score=0.9, metadata={"text": "..."})]
        result = evaluator.evaluate(input="?", output="...", context=chunks)
        assert result.passed  # score >= threshold

    def test_invalid_threshold(self) -> None:
        caller = MockModelCaller([])
        with pytest.raises(ValueError):
            Faithfulness(caller, threshold=1.5)


# ---------------------------------------------------------------------------
# AnswerRelevance Tests
# ---------------------------------------------------------------------------


class TestAnswerRelevance:
    def test_relevant(self) -> None:
        caller = MockModelCaller(["SCORE: 0.9\nREASONING: Directly answers"])
        evaluator = AnswerRelevance(caller, threshold=0.7)
        result = evaluator.evaluate(input="What is 2+2?", output="4", context=None)
        assert result.score == 0.9
        assert result.passed

    def test_irrelevant(self) -> None:
        caller = MockModelCaller(["SCORE: 0.1\nREASONING: Unrelated"])
        evaluator = AnswerRelevance(caller, threshold=0.7)
        result = evaluator.evaluate(
            input="What is 2+2?", output="The sky is blue", context=None
        )
        assert result.score == 0.1
        assert not result.passed


# ---------------------------------------------------------------------------
# ContextPrecision Tests
# ---------------------------------------------------------------------------


class TestContextPrecision:
    def test_high_precision(self) -> None:
        caller = MockModelCaller(["SCORE: 0.8\nREASONING: Most chunks relevant"])
        evaluator = ContextPrecision(caller, threshold=0.7)
        chunks = [
            SearchResult(id="doc#0", score=0.9, metadata={"text": "AI infrastructure"}),
            SearchResult(id="doc#1", score=0.7, metadata={"text": "Verification"}),
        ]
        result = evaluator.evaluate(input="What is AI?", output="", context=chunks)
        assert result.score == 0.8
        assert result.passed

    def test_no_chunks(self) -> None:
        caller = MockModelCaller(["SCORE: 0.0\nREASONING: No context"])
        evaluator = ContextPrecision(caller, threshold=0.7)
        result = evaluator.evaluate(input="What is AI?", output="", context=[])
        assert result.score == 0.0
        assert not result.passed


# ---------------------------------------------------------------------------
# ContextRecall Tests
# ---------------------------------------------------------------------------


class TestContextRecall:
    def test_complete(self) -> None:
        caller = MockModelCaller(["SCORE: 0.9\nREASONING: All info present"])
        evaluator = ContextRecall(caller, threshold=0.7)
        chunks = [
            SearchResult(
                id="doc#0",
                score=0.9,
                metadata={"text": "AI infrastructure provides verification"},
            ),
            SearchResult(id="doc#1", score=0.7, metadata={"text": "Modularity is key"}),
        ]
        result = evaluator.evaluate(
            input="What is AI infra?",
            output="AI infra provides verification and modularity",
            context=chunks,
        )
        assert result.score == 0.9
        assert result.passed

    def test_missing_info(self) -> None:
        caller = MockModelCaller(["SCORE: 0.3\nREASONING: Critical info missing"])
        evaluator = ContextRecall(caller, threshold=0.7)
        chunks = [SearchResult(id="doc#0", score=0.9, metadata={"text": "Unrelated"})]
        result = evaluator.evaluate(
            input="What is AI?", output="AI provides verification", context=chunks
        )
        assert result.score == 0.3
        assert not result.passed
