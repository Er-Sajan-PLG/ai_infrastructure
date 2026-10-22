"""Pre-built evaluation suites for common use cases."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from react_agent_loop.protocols import ModelCaller

from .evaluators.agent import (
    ExecutionEfficiency,
    LogicalConsistency,
    PlanAdherence,
    ToolCalling,
    ToolSelection,
)
from .evaluators.deterministic import (
    CitationCoverage,
    ExactMatch,
    LengthValidator,
    SchemaValidator,
    ToolCallValidator,
)
from .evaluators.rag_triad import (
    AnswerRelevance,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)
from .protocols import EvaluationSuite, Evaluator


def rag_evaluation_suite(
    model_caller: ModelCaller | None = None,
    *,
    min_citations: int = 1,
    citation_weight: float = 0.3,
    faithfulness_weight: float = 0.25,
    relevance_weight: float = 0.25,
    precision_weight: float = 0.1,
    recall_weight: float = 0.1,
) -> EvaluationSuite:
    """Standard RAG evaluation: citation coverage + RAG triad (if model_caller)."""
    evaluators: list[tuple[Evaluator, float]] = [
        (CitationCoverage(min_citations=min_citations), citation_weight),
    ]
    if model_caller:
        evaluators.append((Faithfulness(model_caller), faithfulness_weight))
        evaluators.append((AnswerRelevance(model_caller), relevance_weight))
        evaluators.append((ContextPrecision(model_caller), precision_weight))
        evaluators.append((ContextRecall(model_caller), recall_weight))
    return EvaluationSuite("rag_standard", tuple(evaluators))


def agent_evaluation_suite(
    model_caller: ModelCaller | None = None,
    optimal_steps: int | None = None,
    efficiency_weight: float = 0.2,
    tool_calling_weight: float = 0.2,
    consistency_weight: float = 0.2,
    adherence_weight: float = 0.2,
    selection_weight: float = 0.2,
) -> EvaluationSuite:
    """Standard agent evaluation."""
    evaluators: list[tuple[Evaluator, float]] = [
        (
            ExecutionEfficiency(optimal_steps=optimal_steps, model_caller=model_caller),
            efficiency_weight,
        ),
        (ToolCalling(model_caller=model_caller, threshold=0.5), tool_calling_weight),
    ]
    if model_caller:
        evaluators.append((LogicalConsistency(model_caller), consistency_weight))
        evaluators.append((PlanAdherence(model_caller), adherence_weight))
        evaluators.append((ToolSelection(model_caller), selection_weight))
    return EvaluationSuite("agent_standard", tuple(evaluators))


def schema_validation_suite(
    schema: Mapping[str, Any],
    threshold: float = 1.0,
) -> EvaluationSuite:
    """Schema-only validation suite."""
    return EvaluationSuite(
        "schema_validation",
        ((SchemaValidator(schema, threshold=threshold), 1.0),),
    )


def exact_match_suite(
    expected: str,
    normalize: Callable[[str], str] | None = None,
    threshold: float = 1.0,
) -> EvaluationSuite:
    """Exact match regression suite."""
    return EvaluationSuite(
        "exact_match",
        ((ExactMatch(expected, normalize=normalize, threshold=threshold), 1.0),),
    )


def tool_call_suite(
    expected_calls: Sequence[tuple[str, Mapping[str, Any]]],
    order_matters: bool = True,
    threshold: float = 1.0,
) -> EvaluationSuite:
    """Tool call sequence validation suite."""
    return EvaluationSuite(
        "tool_call_validation",
        (
            (
                ToolCallValidator(
                    expected_calls=list(expected_calls),
                    order_matters=order_matters,
                    threshold=threshold,
                ),
                1.0,
            ),
        ),
    )


def length_suite(
    min_chars: int | None = None,
    max_chars: int | None = None,
    min_tokens: int | None = None,
    max_tokens: int | None = None,
    tokenizer: Callable[[str], list[int]] | None = None,
    threshold: float = 1.0,
) -> EvaluationSuite:
    """Length validation suite."""
    return EvaluationSuite(
        "length_validation",
        (
            (
                LengthValidator(
                    min_chars=min_chars,
                    max_chars=max_chars,
                    min_tokens=min_tokens,
                    max_tokens=max_tokens,
                    tokenizer=tokenizer,
                    threshold=threshold,
                ),
                1.0,
            ),
        ),
    )
