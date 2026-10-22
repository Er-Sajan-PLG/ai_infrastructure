"""Evaluation Framework — Protocol-first, composable evaluation system.

Provides Evaluator protocol, EvaluationSuite for aggregation, deterministic evaluators
(schema, length, citation coverage, exact match, tool call validation), RAG triad
evaluators (faithfulness, answer relevance, context precision/recall), agent evaluators
(logical consistency, execution efficiency, plan adherence, tool selection, tool calling),
and LLM-as-judge adapter for model-backed evaluation.

Zero runtime dependencies — standard library only. All model calls injected.

See specifications/evaluation-framework.md for the design and
docs/decisions/0037-evaluation-framework.md for the decision.
"""

from __future__ import annotations

from .aggregation import (
    max_score,
    min_score,
    pass_fail,
    weighted_average,
)
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
from .llm_judge import LLMJudgeAdapter
from .protocols import (
    EvaluationResult,
    EvaluationSuite,
    Evaluator,
    SuiteResult,
)
from .suites import (
    agent_evaluation_suite,
    exact_match_suite,
    length_suite,
    rag_evaluation_suite,
    schema_validation_suite,
    tool_call_suite,
)
from .trace_integration import (
    evaluate_rag,
    evaluate_steps,
    evaluate_trace,
)

__all__ = [
    "AnswerRelevance",
    "CitationCoverage",
    "ContextPrecision",
    "ContextRecall",
    "EvaluationResult",
    "EvaluationSuite",
    "Evaluator",
    "ExactMatch",
    "ExecutionEfficiency",
    "Faithfulness",
    "LLMJudgeAdapter",
    "LengthValidator",
    "LogicalConsistency",
    "PlanAdherence",
    "SchemaValidator",
    "SuiteResult",
    "ToolCallValidator",
    "ToolCalling",
    "ToolSelection",
    "agent_evaluation_suite",
    "evaluate_rag",
    "evaluate_steps",
    "evaluate_trace",
    "exact_match_suite",
    "length_suite",
    "max_score",
    "min_score",
    "pass_fail",
    "rag_evaluation_suite",
    "schema_validation_suite",
    "tool_call_suite",
    "weighted_average",
]
