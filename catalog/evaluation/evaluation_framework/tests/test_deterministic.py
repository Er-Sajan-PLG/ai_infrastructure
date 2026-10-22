"""Tests for deterministic evaluators."""

from __future__ import annotations

import sys
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
from evaluation_framework.evaluators.deterministic import (  # noqa: E402
    CitationCoverage,
    ExactMatch,
    LengthValidator,
    SchemaValidator,
    ToolCallValidator,
)
from vector_store import SearchResult  # noqa: E402

# ---------------------------------------------------------------------------
# SchemaValidator Tests
# ---------------------------------------------------------------------------


class TestSchemaValidator:
    def test_valid_object(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
            "additionalProperties": False,
        }
        validator = SchemaValidator(schema)
        result = validator.evaluate(input={}, output={"name": "Alice", "age": 30})
        assert result.score == 1.0
        assert result.passed

    def test_missing_required(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        }
        validator = SchemaValidator(schema)
        result = validator.evaluate(input={}, output={"age": 30})
        assert result.score == 0.0
        assert not result.passed
        assert "name" in (result.reasoning or "")

    def test_additional_properties_rejected(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
        validator = SchemaValidator(schema)
        result = validator.evaluate(
            input={}, output={"name": "Alice", "extra": "not allowed"}
        )
        assert result.score == 0.0
        assert not result.passed

    def test_type_mismatch(self) -> None:
        schema = {"type": "object", "properties": {"age": {"type": "integer"}}}
        validator = SchemaValidator(schema)
        result = validator.evaluate(input={}, output={"age": "thirty"})
        assert result.score == 0.0
        assert not result.passed

    def test_threshold(self) -> None:
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        validator = SchemaValidator(schema, threshold=0.5)
        result = validator.evaluate(input={}, output={"name": "Alice"})
        assert result.threshold == 0.5
        assert result.passed


# ---------------------------------------------------------------------------
# LengthValidator Tests
# ---------------------------------------------------------------------------


class TestLengthValidator:
    def test_char_bounds_valid(self) -> None:
        validator = LengthValidator(min_chars=5, max_chars=20)
        result = validator.evaluate(input="", output="Hello World")
        assert result.score == 1.0
        assert result.passed

    def test_char_too_short(self) -> None:
        validator = LengthValidator(min_chars=10)
        result = validator.evaluate(input="", output="Short")
        assert result.score == 0.0
        assert not result.passed
        assert "min_chars" in (result.reasoning or "")

    def test_char_too_long(self) -> None:
        validator = LengthValidator(max_chars=5)
        result = validator.evaluate(input="", output="This is too long")
        assert result.score == 0.0
        assert not result.passed
        assert "max_chars" in (result.reasoning or "")

    def test_token_bounds(self) -> None:
        # Use simple tokenizer: split by space
        validator = LengthValidator(
            min_tokens=3, max_tokens=5, tokenizer=lambda t: t.split()
        )
        result = validator.evaluate(input="", output="one two three four")
        assert result.score == 1.0
        assert result.passed

    def test_token_too_few(self) -> None:
        validator = LengthValidator(min_tokens=5, tokenizer=lambda t: t.split())
        result = validator.evaluate(input="", output="one two")
        assert result.score == 0.0
        assert not result.passed

    def test_non_string_output(self) -> None:
        validator = LengthValidator(min_chars=1)
        result = validator.evaluate(input="", output=123)
        assert result.score == 0.0
        assert not result.passed

    def test_both_char_and_token(self) -> None:
        validator = LengthValidator(
            min_chars=5, max_chars=50, min_tokens=2, max_tokens=10
        )
        result = validator.evaluate(input="", output="valid text here")
        assert result.score == 1.0

    def test_invalid_config(self) -> None:
        with pytest.raises(ValueError):
            LengthValidator(min_chars=10, max_chars=5)


# ---------------------------------------------------------------------------
# CitationCoverage Tests
# ---------------------------------------------------------------------------


class TestCitationCoverage:
    def test_sufficient_citations(self) -> None:
        validator = CitationCoverage(min_citations=2)
        citations = (
            Citation(chunk_id="doc#0", doc_id="doc", score=0.9),
            Citation(chunk_id="doc#1", doc_id="doc", score=0.8),
        )
        output = RagAnswer(text="Answer", citations=citations)
        result = validator.evaluate(input="query", output=output)
        assert result.score == 1.0
        assert result.passed

    def test_insufficient_citations(self) -> None:
        validator = CitationCoverage(min_citations=3)
        citations = (Citation(chunk_id="doc#0", doc_id="doc", score=0.9),)
        output = RagAnswer(text="Answer", citations=citations)
        result = validator.evaluate(input="query", output=output)
        assert result.score == pytest.approx(1 / 3)
        assert not result.passed

    def test_zero_citations_required(self) -> None:
        validator = CitationCoverage(min_citations=0)
        output = RagAnswer(text="Answer", citations=())
        result = validator.evaluate(input="query", output=output)
        assert result.score == 1.0
        assert result.passed

    def test_no_citations_attribute(self) -> None:
        validator = CitationCoverage(min_citations=1)
        result = validator.evaluate(input="query", output="plain string")
        assert result.score == 0.0
        assert not result.passed

    def test_context_metadata(self) -> None:
        validator = CitationCoverage(min_citations=1)
        citations = (Citation(chunk_id="doc#0", doc_id="doc", score=0.9),)
        output = RagAnswer(text="Answer", citations=citations)
        context = [
            SearchResult(id="doc#0", score=0.9, metadata={"text": "..."}),
            SearchResult(id="doc#1", score=0.5, metadata={"text": "..."}),
        ]
        result = validator.evaluate(input="query", output=output, context=context)
        assert "available_ids" in (result.metadata or {})


# ---------------------------------------------------------------------------
# ExactMatch Tests
# ---------------------------------------------------------------------------


class TestExactMatch:
    def test_exact_match(self) -> None:
        validator = ExactMatch("hello world")
        result = validator.evaluate(input="", output="hello world")
        assert result.score == 1.0
        assert result.passed

    def test_mismatch(self) -> None:
        validator = ExactMatch("hello world")
        result = validator.evaluate(input="", output="hello there")
        assert result.score == 0.0
        assert not result.passed

    def test_normalize_function(self) -> None:
        validator = ExactMatch("HELLO WORLD", normalize=str.lower)
        result = validator.evaluate(input="", output="hello world")
        assert result.score == 1.0
        assert result.passed

    def test_case_sensitive_by_default(self) -> None:
        validator = ExactMatch("Hello")
        result = validator.evaluate(input="", output="hello")
        assert result.score == 0.0

    def test_non_string_output(self) -> None:
        validator = ExactMatch("test")
        result = validator.evaluate(input="", output=123)
        assert result.score == 0.0
        assert not result.passed


# ---------------------------------------------------------------------------
# ToolCallValidator Tests
# ---------------------------------------------------------------------------


class TestToolCallValidator:
    def _make_call(self, name: str, args: dict[str, Any]) -> Any:
        class Call:
            def __init__(self, name: str, arguments: dict[str, Any]) -> None:
                self.name = name
                self.arguments = arguments

        return Call(name, args)

    def _make_step(self, calls: list[Any]) -> Any:
        class Step:
            def __init__(self, calls: list[Any]) -> None:
                self.tool_calls = tuple(calls)

        return Step(calls)

    def _make_output(self, steps: list[Any]) -> Any:
        class Output:
            def __init__(self, steps: list[Any]) -> None:
                self.steps = tuple(steps)

        return Output(steps)

    def test_ordered_match(self) -> None:
        validator = ToolCallValidator(
            expected_calls=[("add", {"a": 1, "b": 2}), ("mul", {"x": 3, "y": 4})],
            order_matters=True,
        )
        calls = [
            self._make_call("add", {"a": 1, "b": 2}),
            self._make_call("mul", {"x": 3, "y": 4}),
        ]
        output = self._make_output([self._make_step(calls)])
        result = validator.evaluate(input="", output=output)
        assert result.score == 1.0
        assert result.passed

    def test_ordered_partial_match(self) -> None:
        validator = ToolCallValidator(
            expected_calls=[("add", {"a": 1, "b": 2}), ("mul", {"x": 3, "y": 4})],
            order_matters=True,
        )
        calls = [self._make_call("add", {"a": 1, "b": 2})]
        output = self._make_output([self._make_step(calls)])
        result = validator.evaluate(input="", output=output)
        assert result.score == 0.5
        assert not result.passed

    def test_unordered_match(self) -> None:
        validator = ToolCallValidator(
            expected_calls=[("add", {"a": 1}), ("mul", {"x": 2})],
            order_matters=False,
        )
        calls = [self._make_call("mul", {"x": 2}), self._make_call("add", {"a": 1})]
        output = self._make_output([self._make_step(calls)])
        result = validator.evaluate(input="", output=output)
        assert result.score == 1.0
        assert result.passed

    def test_wrong_arguments(self) -> None:
        validator = ToolCallValidator(
            expected_calls=[("add", {"a": 1, "b": 2})],
            order_matters=True,
        )
        calls = [self._make_call("add", {"a": 1, "b": 3})]  # Wrong arg
        output = self._make_output([self._make_step(calls)])
        result = validator.evaluate(input="", output=output)
        assert result.score == 0.0
        assert not result.passed

    def test_no_calls_expected(self) -> None:
        validator = ToolCallValidator(expected_calls=[], order_matters=True)
        output = self._make_output([self._make_step([])])
        result = validator.evaluate(input="", output=output)
        assert result.score == 1.0
        assert result.passed

    def test_calls_unexpected(self) -> None:
        validator = ToolCallValidator(expected_calls=[], order_matters=True)
        calls = [self._make_call("add", {"a": 1})]
        output = self._make_output([self._make_step(calls)])
        result = validator.evaluate(input="", output=output)
        assert result.score == 0.0
        assert not result.passed

    def test_no_steps_attribute(self) -> None:
        validator = ToolCallValidator(expected_calls=[("add", {})])
        result = validator.evaluate(input="", output="not an agent result")
        assert result.score == 0.0
        assert not result.passed


class TestDeterministicCoverage:
    def test_schema_threshold(self) -> None:
        with pytest.raises(ValueError):
            SchemaValidator({"type": "object"}, threshold=2.0)

    def test_length_validations(self) -> None:
        with pytest.raises(ValueError):
            LengthValidator(min_chars=-1)
        with pytest.raises(ValueError):
            LengthValidator(max_chars=-1)
        with pytest.raises(ValueError):
            LengthValidator(min_tokens=-1)
        with pytest.raises(ValueError):
            LengthValidator(max_tokens=-1)
        with pytest.raises(ValueError):
            LengthValidator(min_chars=5, max_chars=3)
        with pytest.raises(ValueError):
            LengthValidator(min_tokens=5, max_tokens=3)
        with pytest.raises(ValueError):
            LengthValidator(threshold=2.0)

    def test_length_max_tokens_violation(self) -> None:
        v = LengthValidator(max_tokens=1)
        r = v.evaluate(input=None, output="a" * 100)
        assert not r.passed

    def test_citation_coverage_validations(self) -> None:
        with pytest.raises(ValueError):
            CitationCoverage(min_citations=-1)
        with pytest.raises(ValueError):
            CitationCoverage(threshold=2.0)

    def test_exact_match_threshold(self) -> None:
        with pytest.raises(ValueError):
            ExactMatch("x", threshold=2.0)

    def test_tool_call_validator_threshold(self) -> None:
        with pytest.raises(ValueError):
            ToolCallValidator(expected_calls=[], threshold=2.0)
