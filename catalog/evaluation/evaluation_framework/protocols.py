"""Core protocols for the Evaluation Framework.

Defines Evaluator protocol, EvaluationResult, and related types.
All implementations compose these protocols — no inheritance required.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


def weighted_average(results: list[tuple[EvaluationResult, float]]) -> float:
    """Weighted average of scores."""
    total_weight = sum(w for _, w in results)
    if total_weight == 0:
        return 0.0
    return sum(r.score * w for r, w in results) / total_weight


def pass_fail(
    results: list[EvaluationResult],
) -> bool:
    """All must pass."""
    return all(r.passed for r in results)


def min_score(results: list[EvaluationResult]) -> float:
    """Worst score."""
    return min(r.score for r in results) if results else 0.0


def max_score(results: list[EvaluationResult]) -> float:
    """Best score."""
    return max(r.score for r in results) if results else 0.0


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """The result of a single evaluation.

    Attributes:
        name: The evaluator's name.
        score: Normalized score in [0, 1]. 1 = perfect, 0 = complete failure.
        passed: Whether the evaluation passes the threshold.
        reasoning: Human-readable explanation (optional).
        metadata: Additional structured data (optional).
        threshold: The pass/fail threshold used.
    """

    name: str
    score: float
    passed: bool
    reasoning: str | None = None
    metadata: Mapping[str, Any] | None = None
    threshold: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score}")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")


@runtime_checkable
class Evaluator(Protocol):
    """A single evaluation criterion.

    Implementations must be pure functions of their inputs — no hidden state,
    no network calls, no model calls unless explicitly injected via constructor.
    """

    @property
    def name(self) -> str:
        """Unique evaluator identifier."""

    def evaluate(
        self,
        *,
        input: Any,  # The input to the system (query, task, etc.)
        output: Any,  # The system's output (answer, tool result, etc.)
        context: Any | None = None,  # Additional context (retrieved docs, trace, etc.)
    ) -> EvaluationResult:
        """Evaluate the output against the input and context."""


@dataclass(frozen=True, slots=True)
class EvaluationSuite:
    """A named collection of evaluators with aggregation.

    Attributes:
        name: Suite identifier.
        evaluators: Ordered list of (evaluator, weight) pairs.
        aggregation: How to combine scores — "weighted_average", "pass_fail", "min", "max".
        pass_threshold: Overall pass threshold for the suite.
    """

    name: str
    evaluators: tuple[tuple[Evaluator, float], ...]
    aggregation: Literal["weighted_average", "pass_fail", "min", "max"] = (
        "weighted_average"
    )
    pass_threshold: float = 0.5

    def __post_init__(self) -> None:
        if not self.evaluators:
            raise ValueError("evaluators must not be empty")
        for _evaluator, weight in self.evaluators:
            if weight < 0:
                raise ValueError(f"weight must be non-negative, got {weight}")
        if not 0.0 <= self.pass_threshold <= 1.0:
            raise ValueError(
                f"pass_threshold must be in [0, 1], got {self.pass_threshold}"
            )

    def run(
        self,
        *,
        input: Any,
        output: Any,
        context: Any | None = None,
    ) -> SuiteResult:
        """Run all evaluators and aggregate."""
        results = [
            evaluator.evaluate(input=input, output=output, context=context)
            for evaluator, _ in self.evaluators
        ]
        weights = [w for _, w in self.evaluators]

        if self.aggregation == "weighted_average":
            overall = weighted_average(list(zip(results, weights, strict=False)))
        elif self.aggregation == "pass_fail":
            overall = 1.0 if pass_fail(results) else 0.0
        elif self.aggregation == "min":
            overall = min_score(results)
        elif self.aggregation == "max":
            overall = max_score(results)
        else:
            raise ValueError(f"unknown aggregation: {self.aggregation}")

        overall_passed = overall >= self.pass_threshold
        return SuiteResult(
            suite_name=self.name,
            overall_score=overall,
            overall_passed=overall_passed,
            results=tuple(results),
        )


@dataclass(frozen=True, slots=True)
class SuiteResult:
    """Aggregated result of an evaluation suite."""

    suite_name: str
    overall_score: float
    overall_passed: bool
    results: tuple[EvaluationResult, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
