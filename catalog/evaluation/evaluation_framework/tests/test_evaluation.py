"""Tests for core evaluation protocols, aggregation, suites, and trace integration."""

from __future__ import annotations

import sys
import tempfile
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
    sys.path.insert(0, _p)

import pytest  # noqa: E402
from basic_rag_pipeline import Citation, RagAnswer  # noqa: E402
from evaluation_framework import (  # noqa: E402
    EvaluationResult,
    EvaluationSuite,
    Evaluator,
    agent_evaluation_suite,
    evaluate_rag,
    evaluate_steps,
    evaluate_trace,
    exact_match_suite,
    length_suite,
    max_score,
    min_score,
    pass_fail,
    rag_evaluation_suite,
    schema_validation_suite,
    tool_call_suite,
    weighted_average,
)
from evaluation_framework.evaluators.deterministic import (  # noqa: E402
    CitationCoverage,
    ExactMatch,
    LengthValidator,
    SchemaValidator,
    ToolCallValidator,
)
from vector_store import SearchResult  # noqa: E402

# ---------------------------------------------------------------------------
# EvaluationResult Tests
# ---------------------------------------------------------------------------


class TestEvaluationResult:
    def test_valid_result(self) -> None:
        result = EvaluationResult(name="test", score=0.8, passed=True, threshold=0.5)
        assert result.score == 0.8
        assert result.passed
        assert result.threshold == 0.5

    def test_score_bounds(self) -> None:
        with pytest.raises(ValueError):
            EvaluationResult(name="test", score=1.5, passed=True)
        with pytest.raises(ValueError):
            EvaluationResult(name="test", score=-0.1, passed=True)

    def test_threshold_bounds(self) -> None:
        with pytest.raises(ValueError):
            EvaluationResult(name="test", score=0.5, passed=True, threshold=1.5)


# ---------------------------------------------------------------------------
# Aggregation Tests
# ---------------------------------------------------------------------------


class TestAggregation:
    def test_weighted_average(self) -> None:
        results = [
            (EvaluationResult(name="a", score=1.0, passed=True), 1.0),
            (EvaluationResult(name="b", score=0.5, passed=False), 1.0),
        ]
        assert weighted_average(results) == 0.75

    def test_weighted_average_zero_weight(self) -> None:
        results = [(EvaluationResult(name="a", score=1.0, passed=True), 0.0)]
        assert weighted_average(results) == 0.0

    def test_pass_fail_all_pass(self) -> None:
        results = [
            EvaluationResult(name="a", score=0.8, passed=True),
            EvaluationResult(name="b", score=0.9, passed=True),
        ]
        assert pass_fail(results)

    def test_pass_fail_one_fail(self) -> None:
        results = [
            EvaluationResult(name="a", score=0.8, passed=True),
            EvaluationResult(name="b", score=0.3, passed=False),
        ]
        assert not pass_fail(results)

    def test_min_score(self) -> None:
        results = [
            EvaluationResult(name="a", score=1.0, passed=True),
            EvaluationResult(name="b", score=0.3, passed=False),
        ]
        assert min_score(results) == 0.3

    def test_max_score(self) -> None:
        results = [
            EvaluationResult(name="a", score=1.0, passed=True),
            EvaluationResult(name="b", score=0.3, passed=False),
        ]
        assert max_score(results) == 1.0

    def test_empty_results(self) -> None:
        assert min_score([]) == 0.0
        assert max_score([]) == 0.0
        assert weighted_average([]) == 0.0


# ---------------------------------------------------------------------------
# EvaluationSuite Tests
# ---------------------------------------------------------------------------


class TestEvaluationSuite:
    def test_weighted_average_suite(self) -> None:
        class MockEvaluator:
            def __init__(self, score: float, name: str):
                self._score = score
                self._name = name

            @property
            def name(self) -> str:
                return self._name  # pragma: no cover

            def evaluate(
                self, *, input: Any, output: Any, context: Any = None
            ) -> EvaluationResult:
                return EvaluationResult(
                    name=self._name, score=self._score, passed=self._score >= 0.5
                )

        suite = EvaluationSuite(
            name="test",
            evaluators=((MockEvaluator(1.0, "a"), 1.0), (MockEvaluator(0.5, "b"), 1.0)),
            aggregation="weighted_average",
        )
        result = suite.run(input="", output="")
        assert result.overall_score == 0.75
        assert result.overall_passed  # 0.75 >= 0.5

    def test_pass_fail_suite(self) -> None:
        class MockEvaluator:
            def __init__(self, score: float, name: str):
                self._score = score
                self._name = name

            @property
            def name(self) -> str:
                return self._name  # pragma: no cover

            def evaluate(
                self, *, input: Any, output: Any, context: Any = None
            ) -> EvaluationResult:
                return EvaluationResult(
                    name=self._name, score=self._score, passed=self._score >= 0.5
                )

        suite = EvaluationSuite(
            name="test",
            evaluators=((MockEvaluator(0.8, "a"), 1.0), (MockEvaluator(0.9, "b"), 1.0)),
            aggregation="pass_fail",
            pass_threshold=0.5,
        )
        result = suite.run(input="", output="")
        assert result.overall_score == 1.0  # All pass
        assert result.overall_passed

    def test_min_suite(self) -> None:
        class MockEvaluator:
            def __init__(self, score: float, name: str):
                self._score = score
                self._name = name

            @property
            def name(self) -> str:
                return self._name  # pragma: no cover

            def evaluate(
                self, *, input: Any, output: Any, context: Any = None
            ) -> EvaluationResult:
                return EvaluationResult(
                    name=self._name, score=self._score, passed=self._score >= 0.5
                )

        suite = EvaluationSuite(
            name="test",
            evaluators=((MockEvaluator(1.0, "a"), 1.0), (MockEvaluator(0.3, "b"), 1.0)),
            aggregation="min",
        )
        result = suite.run(input="", output="")
        assert result.overall_score == 0.3

    def test_max_suite(self) -> None:
        class MockEvaluator:
            def __init__(self, score: float, name: str):
                self._score = score
                self._name = name

            @property
            def name(self) -> str:
                return self._name  # pragma: no cover

            def evaluate(
                self, *, input: Any, output: Any, context: Any = None
            ) -> EvaluationResult:
                return EvaluationResult(
                    name=self._name, score=self._score, passed=self._score >= 0.5
                )

        suite = EvaluationSuite(
            name="test",
            evaluators=((MockEvaluator(1.0, "a"), 1.0), (MockEvaluator(0.3, "b"), 1.0)),
            aggregation="max",
        )
        result = suite.run(input="", output="")
        assert result.overall_score == 1.0

    def test_empty_evaluators_rejected(self) -> None:
        with pytest.raises(ValueError):
            EvaluationSuite(name="test", evaluators=())

    def test_negative_weight_rejected(self) -> None:
        class MockEvaluator:
            @property
            def name(self) -> str:
                return "a"  # pragma: no cover

            def evaluate(
                self, *, input: Any, output: Any, context: Any = None
            ) -> EvaluationResult:
                return EvaluationResult(
                    name="a", score=1.0, passed=True
                )  # pragma: no cover

        with pytest.raises(ValueError):
            EvaluationSuite(name="test", evaluators=((MockEvaluator(), -1.0),))


# ---------------------------------------------------------------------------
# Suite Factory Tests
# ---------------------------------------------------------------------------


class TestSuiteFactories:
    def test_rag_evaluation_suite_deterministic_only(self) -> None:
        suite = rag_evaluation_suite(model_caller=None, min_citations=1)
        assert suite.name == "rag_standard"
        assert len(suite.evaluators) == 1
        assert isinstance(suite.evaluators[0][0], CitationCoverage)

    def test_rag_evaluation_suite_with_model(self) -> None:
        class MockModelCaller:
            def call(
                self, messages: Any, *, system: Any = None, tools: Any = ()
            ) -> Any:
                from dataclasses import dataclass  # pragma: no cover

                @dataclass
                class Resp:
                    text: str = "SCORE: 0.8\nREASONING: test"
                    blocks: tuple[Any, ...] = ()
                    tool_calls: tuple[Any, ...] = ()
                    usage: None = None

                return Resp()

        caller = MockModelCaller()
        suite = rag_evaluation_suite(caller, min_citations=1)
        caller.call([], system=None, tools=())
        assert len(suite.evaluators) == 5  # CitationCoverage + 4 RAG triad

    def test_agent_evaluation_suite(self) -> None:
        suite = agent_evaluation_suite(model_caller=None, optimal_steps=3)
        assert suite.name == "agent_standard"
        assert len(suite.evaluators) == 2  # ExecutionEfficiency + ToolCalling

    def test_schema_validation_suite(self) -> None:
        suite = schema_validation_suite(
            {"type": "object", "properties": {"name": {"type": "string"}}}
        )
        assert suite.name == "schema_validation"
        assert len(suite.evaluators) == 1
        assert isinstance(suite.evaluators[0][0], SchemaValidator)

    def test_exact_match_suite(self) -> None:
        suite = exact_match_suite("expected", normalize=str.strip)
        assert suite.name == "exact_match"
        assert len(suite.evaluators) == 1
        assert isinstance(suite.evaluators[0][0], ExactMatch)

    def test_tool_call_suite(self) -> None:
        suite = tool_call_suite([("add", {"a": 1})], order_matters=True)
        assert suite.name == "tool_call_validation"
        assert len(suite.evaluators) == 1
        assert isinstance(suite.evaluators[0][0], ToolCallValidator)

    def test_length_suite(self) -> None:
        suite = length_suite(min_chars=5, max_chars=100)
        assert suite.name == "length_validation"
        assert len(suite.evaluators) == 1
        assert isinstance(suite.evaluators[0][0], LengthValidator)


# ---------------------------------------------------------------------------
# Trace Integration Tests
# ---------------------------------------------------------------------------


class TestTraceIntegration:
    def test_evaluate_rag(self) -> None:
        class MockModelCaller:
            def call(
                self, messages: Any, *, system: Any = None, tools: Any = ()
            ) -> Any:
                from dataclasses import dataclass  # pragma: no cover

                @dataclass
                class Resp:
                    text: str = "SCORE: 0.8\nREASONING: test"
                    blocks: tuple[Any, ...] = ()
                    tool_calls: tuple[Any, ...] = ()
                    usage: None = None

                return Resp()

        chunks = [
            SearchResult(id="doc#0", score=0.9, metadata={"text": "AI infrastructure"})
        ]
        citations = (Citation(chunk_id="doc#0", doc_id="doc", score=0.9),)
        rag_answer = RagAnswer(text="AI provides verification", citations=citations)

        suite = rag_evaluation_suite(MockModelCaller())
        evaluators = [e for e, _ in suite.evaluators]

        results = evaluate_rag(
            query="What is AI?",
            answer=rag_answer.text,
            citations=list(citations),
            retrieved_chunks=chunks,
            evaluators=evaluators,
        )
        assert len(results) == 5

    def test_evaluate_steps(self) -> None:
        @dataclass
        class MockStep:
            index: int
            text: str
            tool_calls: tuple[Any, ...] = ()

        steps = [MockStep(index=1, text="Add"), MockStep(index=2, text="Done")]
        evaluators = [
            type(
                "Eval",
                (),
                {
                    "name": "test",
                    "threshold": 0.5,
                    "evaluate": lambda self, input, output, context=None: EvaluationResult(
                        name="test", score=0.8, passed=True
                    ),
                },
            )()
        ]

        results = evaluate_steps(steps, evaluators, task="Add")
        assert len(results) == 1
        assert results[0].score == 0.8

    def test_evaluate_trace_file_not_found(self) -> None:
        results = evaluate_trace(Path("/nonexistent.jsonl"), [])
        assert results == []

    def test_evaluate_trace_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            path = Path(f.name)
        try:
            results = evaluate_trace(path, [])
            assert results == []
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# Protocol Compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_evaluator_protocol(self) -> None:
        """Verify Evaluator protocol can be implemented structurally."""

        class MyEvaluator:
            @property
            def name(self) -> str:
                return "mine"  # pragma: no cover

            def evaluate(
                self, *, input: Any, output: Any, context: Any = None
            ) -> EvaluationResult:
                return EvaluationResult(name="mine", score=1.0, passed=True)

        evaluator = MyEvaluator()
        assert isinstance(evaluator, Evaluator)
        result = evaluator.evaluate(input="", output="")
        assert result.name == "mine"


class TestLLMJudgeCoverage:
    def test_threshold(self) -> None:

        class MC:
            def call(
                self, messages: Any, *, system: Any = None, tools: Any = ()
            ) -> Any:
                return type(
                    "R", (), {"text": "SCORE: 1.0\nREASONING: ok"}
                )()  # pragma: no cover

        from evaluation_framework.llm_judge import LLMJudgeAdapter

        with pytest.raises(ValueError):
            LLMJudgeAdapter(
                model_caller=MC(),
                judge_prompt="p {input} {output} {context}",
                parse_fn=lambda s: (1.0, "r"),
                threshold=2.0,
            )

    def test_evaluate(self) -> None:
        class MC:
            def call(
                self, messages: Any, *, system: Any = None, tools: Any = ()
            ) -> Any:
                return type("R", (), {"text": "SCORE: 0.9\nREASONING: good"})()

        from evaluation_framework.llm_judge import LLMJudgeAdapter

        adapter = LLMJudgeAdapter(
            model_caller=MC(),
            judge_prompt="{input} {output} {context}",
            parse_fn=lambda s: (0.9, "good"),
            threshold=0.5,
        )
        res = adapter.evaluate(input="i", output="o", context="c")
        assert res.score == 0.9
        assert res.passed


class TestProtocolsCoverage:
    def test_pass_threshold_validation(self) -> None:
        class E:
            @property
            def name(self) -> str:
                return "e"  # pragma: no cover

            def evaluate(self, *, input: Any, output: Any, context: Any = None) -> Any:
                from evaluation_framework.protocols import (
                    EvaluationResult,  # pragma: no cover
                )

                return EvaluationResult(
                    name="e", score=1.0, passed=True
                )  # pragma: no cover

        with pytest.raises(ValueError):
            from evaluation_framework.protocols import EvaluationSuite

            EvaluationSuite(name="s", evaluators=((E(), 1.0),), pass_threshold=2.0)

    def test_unknown_aggregation(self) -> None:
        class E:
            @property
            def name(self) -> str:
                return "e"  # pragma: no cover

            def evaluate(self, *, input: Any, output: Any, context: Any = None) -> Any:
                from evaluation_framework.protocols import (
                    EvaluationResult,  # pragma: no cover
                )

                return EvaluationResult(
                    name="e", score=1.0, passed=True
                )  # pragma: no cover

        from evaluation_framework.protocols import EvaluationSuite

        suite = EvaluationSuite(
            name="s", evaluators=((E(), 1.0),), aggregation="nope"  # type: ignore[arg-type]
        )
        with pytest.raises(ValueError):
            suite.run(input=1, output=2)


class TestSuitesCoverage:
    def test_agent_evaluation_suite_with_model(self) -> None:
        class MC:
            def call(
                self, messages: Any, *, system: Any = None, tools: Any = ()
            ) -> Any:
                return type(
                    "R", (), {"text": "SCORE: 0.8\nREASONING: test"}
                )()  # pragma: no cover

        from evaluation_framework.suites import agent_evaluation_suite

        suite = agent_evaluation_suite(model_caller=MC(), optimal_steps=2)
        assert len(suite.evaluators) == 5


class TestTraceIntegrationCoverage:
    def test_parse_trace_file_and_evaluate_trace_agent(self, tmp_path: Any) -> None:
        trace = tmp_path / "trace.jsonl"
        trace.write_text(
            '{"kind": "model_call"}\n\n{"kind": "tool_call"}\n', encoding="utf-8"
        )

        class E:
            @property
            def name(self) -> str:
                return "e"  # pragma: no cover

            def evaluate(self, *, input: Any, output: Any, context: Any = None) -> Any:
                from evaluation_framework.protocols import (
                    EvaluationResult,  # pragma: no cover
                )

                return EvaluationResult(
                    name="e", score=1.0, passed=True
                )  # pragma: no cover

        res = evaluate_trace(trace, [E()])
        assert isinstance(res, list)

    def test_evaluate_trace_rag(self, tmp_path: Any) -> None:
        trace = tmp_path / "trace.jsonl"
        trace.write_text('{"kind": "model_call"}\n', encoding="utf-8")

        class E:
            @property
            def name(self) -> str:
                return "e"  # pragma: no cover

            def evaluate(self, *, input: Any, output: Any, context: Any = None) -> Any:
                from evaluation_framework.protocols import (
                    EvaluationResult,  # pragma: no cover
                )

                return EvaluationResult(
                    name="e", score=1.0, passed=True
                )  # pragma: no cover

        res = evaluate_trace(trace, [E()])
        assert isinstance(res, list)

    def test_evaluate_trace_missing_file(self, tmp_path: Any) -> None:
        trace = tmp_path / "nope.jsonl"
        res = evaluate_trace(trace, [])
        assert res == []

    def test_evaluate_steps_error_branch(self) -> None:
        class BoomEval:
            @property
            def name(self) -> str:
                return "boom"

            def evaluate(self, *, input: Any, output: Any, context: Any = None) -> Any:
                raise RuntimeError("boom")

        res = evaluate_steps([], [BoomEval()], task="t")
        assert len(res) == 1
        assert not res[0].passed

    def test_evaluate_rag_error_branch(self) -> None:
        class BoomEval:
            @property
            def name(self) -> str:
                return "boom"

            def evaluate(self, *, input: Any, output: Any, context: Any = None) -> Any:
                raise RuntimeError("boom")

        res = evaluate_rag("q", "a", [], [], [BoomEval()])
        assert len(res) == 1
        assert not res[0].passed


class TestTraceIntegrationCoverage2:
    def test_reconstruct_empty(self) -> None:
        from evaluation_framework.trace_integration import (
            _reconstruct_agent_result,
            _reconstruct_rag_answer,
        )

        assert _reconstruct_agent_result([]) is None
        assert _reconstruct_rag_answer([]) is None
