"""Deterministic evaluators — zero model calls, stdlib only.

Includes SchemaValidator, LengthValidator, CitationCoverage, ExactMatch, ToolCallValidator.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from tool_registry.schema import check_schema, validate_arguments

from ..protocols import EvaluationResult

# ---------------------------------------------------------------------------
# SchemaValidator
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SchemaValidator:
    """Validates output against a JSON Schema (using tool_registry's subset)."""

    schema: Mapping[str, Any]
    threshold: float = 1.0

    def __post_init__(self) -> None:
        check_schema(self.schema, where="SchemaValidator.schema")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "schema_validator"

    def evaluate(
        self,
        *,
        input: Any,
        output: Any,
        context: Any = None,
    ) -> EvaluationResult:
        problems = validate_arguments(self.schema, output)
        if problems:
            return EvaluationResult(
                name=self.name,
                score=0.0,
                passed=False,
                reasoning="; ".join(str(p) for p in problems),
                threshold=self.threshold,
            )
        return EvaluationResult(
            name=self.name,
            score=1.0,
            passed=True,
            reasoning="Output conforms to schema",
            threshold=self.threshold,
        )


# ---------------------------------------------------------------------------
# LengthValidator
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LengthValidator:
    """Validates output length in characters or tokens."""

    min_chars: int | None = None
    max_chars: int | None = None
    min_tokens: int | None = None
    max_tokens: int | None = None
    tokenizer: Callable[[str], list[Any]] | None = None
    threshold: float = 1.0

    def __post_init__(self) -> None:
        if self.min_chars is not None and self.min_chars < 0:
            raise ValueError(f"min_chars must be non-negative, got {self.min_chars}")
        if self.max_chars is not None and self.max_chars < 0:
            raise ValueError(f"max_chars must be non-negative, got {self.max_chars}")
        if self.min_tokens is not None and self.min_tokens < 0:
            raise ValueError(f"min_tokens must be non-negative, got {self.min_tokens}")
        if self.max_tokens is not None and self.max_tokens < 0:
            raise ValueError(f"max_tokens must be non-negative, got {self.max_tokens}")
        if (
            self.min_chars is not None
            and self.max_chars is not None
            and self.min_chars > self.max_chars
        ):
            raise ValueError("min_chars > max_chars")
        if (
            self.min_tokens is not None
            and self.max_tokens is not None
            and self.min_tokens > self.max_tokens
        ):
            raise ValueError("min_tokens > max_tokens")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "length_validator"

    def _count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return len(self.tokenizer(text))
        # Rough approximation: 4 chars per token
        return len(text) // 4 + 1

    def evaluate(
        self,
        *,
        input: Any,
        output: Any,
        context: Any = None,
    ) -> EvaluationResult:
        if not isinstance(output, str):
            return EvaluationResult(
                name=self.name,
                score=0.0,
                passed=False,
                reasoning="Output is not a string",
                threshold=self.threshold,
            )

        char_count = len(output)
        token_count = self._count_tokens(output)

        violations = []
        if self.min_chars is not None and char_count < self.min_chars:
            violations.append(f"char_count {char_count} < min_chars {self.min_chars}")
        if self.max_chars is not None and char_count > self.max_chars:
            violations.append(f"char_count {char_count} > max_chars {self.max_chars}")
        if self.min_tokens is not None and token_count < self.min_tokens:
            violations.append(
                f"token_count {token_count} < min_tokens {self.min_tokens}"
            )
        if self.max_tokens is not None and token_count > self.max_tokens:
            violations.append(
                f"token_count {token_count} > max_tokens {self.max_tokens}"
            )

        if violations:
            return EvaluationResult(
                name=self.name,
                score=0.0,
                passed=False,
                reasoning="; ".join(violations),
                threshold=self.threshold,
                metadata={"char_count": char_count, "token_count": token_count},
            )

        return EvaluationResult(
            name=self.name,
            score=1.0,
            passed=True,
            reasoning="Length within bounds",
            threshold=self.threshold,
            metadata={"char_count": char_count, "token_count": token_count},
        )


# ---------------------------------------------------------------------------
# CitationCoverage
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CitationCoverage:
    """Checks that RAG answers cite retrieved sources."""

    min_citations: int = 1
    threshold: float = 0.5

    def __post_init__(self) -> None:
        if self.min_citations < 0:
            raise ValueError(
                f"min_citations must be non-negative, got {self.min_citations}"
            )
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "citation_coverage"

    def evaluate(
        self,
        *,
        input: str,
        output: Any,
        context: list[Any] | None = None,
    ) -> EvaluationResult:
        # Expect output to have .citations attribute (tuple of Citation)
        citations = getattr(output, "citations", None)
        if citations is None:
            return EvaluationResult(
                name=self.name,
                score=0.0,
                passed=False,
                reasoning="Output has no citations attribute",
                threshold=self.threshold,
            )

        actual = len(citations)
        if actual == 0 and self.min_citations == 0:
            return EvaluationResult(
                name=self.name,
                score=1.0,
                passed=True,
                reasoning="No citations required",
                threshold=self.threshold,
            )

        score = min(1.0, actual / self.min_citations) if self.min_citations > 0 else 1.0
        passed = score >= self.threshold

        cited_ids = [getattr(c, "chunk_id", str(c)) for c in citations]
        available_ids = [getattr(r, "id", str(r)) for r in (context or [])]

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=passed,
            reasoning=f"Cited {actual}/{self.min_citations} required: {cited_ids}",
            threshold=self.threshold,
            metadata={
                "actual_citations": actual,
                "min_citations": self.min_citations,
                "cited_ids": cited_ids,
                "available_ids": available_ids,
            },
        )


# ---------------------------------------------------------------------------
# ExactMatch
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExactMatch:
    """Exact or normalized string matching for regression testing."""

    expected: str
    normalize: Callable[[str], str] | None = None
    threshold: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "exact_match"

    def evaluate(
        self,
        *,
        input: Any,
        output: Any,
        context: Any = None,
    ) -> EvaluationResult:
        if not isinstance(output, str):
            return EvaluationResult(
                name=self.name,
                score=0.0,
                passed=False,
                reasoning="Output is not a string",
                threshold=self.threshold,
            )

        exp = self.normalize(self.expected) if self.normalize else self.expected
        got = self.normalize(output) if self.normalize else output

        if exp == got:
            return EvaluationResult(
                name=self.name,
                score=1.0,
                passed=True,
                reasoning="Exact match",
                threshold=self.threshold,
            )

        return EvaluationResult(
            name=self.name,
            score=0.0,
            passed=False,
            reasoning=f"Mismatch: expected {exp!r}, got {got!r}",
            threshold=self.threshold,
        )


# ---------------------------------------------------------------------------
# ToolCallValidator
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolCallValidator:
    """Validates tool call sequence against expected calls."""

    expected_calls: list[tuple[str, Mapping[str, Any]]]  # (tool_name, args)
    order_matters: bool = True
    threshold: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "tool_call_validator"

    def evaluate(
        self,
        *,
        input: Any,
        output: Any,
        context: Any = None,
    ) -> EvaluationResult:
        # Expect output to be AgentResult with steps containing tool_calls
        steps = getattr(output, "steps", None)
        if steps is None:
            return EvaluationResult(
                name=self.name,
                score=0.0,
                passed=False,
                reasoning="Output has no steps attribute",
                threshold=self.threshold,
            )

        actual_calls = []
        for step in steps:
            for call in getattr(step, "tool_calls", ()):
                actual_calls.append((call.name, dict(call.arguments)))

        if not self.expected_calls and not actual_calls:
            return EvaluationResult(
                name=self.name,
                score=1.0,
                passed=True,
                reasoning="No calls expected, none made",
                threshold=self.threshold,
            )

        if not self.expected_calls:
            return EvaluationResult(
                name=self.name,
                score=0.0,
                passed=False,
                reasoning=f"Expected no calls, got {len(actual_calls)}",
                threshold=self.threshold,
            )

        if self.order_matters:
            matched = 0
            for exp_name, exp_args in self.expected_calls:
                if matched < len(actual_calls):
                    act_name, act_args = actual_calls[matched]
                    if exp_name == act_name and exp_args == act_args:
                        matched += 1
            score = matched / len(self.expected_calls)
        else:
            # Order doesn't matter: check if all expected calls appear in actual
            matched = 0
            used = set()
            for exp_name, exp_args in self.expected_calls:
                for i, (act_name, act_args) in enumerate(actual_calls):
                    if i not in used and exp_name == act_name and exp_args == act_args:
                        matched += 1
                        used.add(i)
                        break
            score = matched / len(self.expected_calls)

        passed = score >= self.threshold
        return EvaluationResult(
            name=self.name,
            score=score,
            passed=passed,
            reasoning=f"Matched {matched}/{len(self.expected_calls)} expected calls",
            threshold=self.threshold,
            metadata={
                "expected": self.expected_calls,
                "actual": actual_calls,
                "matched": matched,
            },
        )
