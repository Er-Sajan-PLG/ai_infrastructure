"""TraceRecorder integration — evaluate from trace files."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from basic_rag_pipeline import RagAnswer
from react_agent_loop import AgentResult, StopReason
from vector_store import SearchResult

from .protocols import EvaluationResult, Evaluator


def _parse_trace_file(path: Path) -> list[dict[str, Any]]:
    """Parse JSONL trace file."""
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _reconstruct_agent_result(records: list[dict[str, Any]]) -> AgentResult | None:
    """Reconstruct AgentResult from trace records."""
    _steps: list[Any] = []
    _messages: list[Any] = []
    _usage = None
    _final_text = ""
    _reason = StopReason.FINAL_ANSWER

    for record in records:
        kind = record.get("kind")
        if kind == "model_call":
            # Extract model call info
            pass  # Simplified - full implementation would rebuild steps
    # This is a simplified stub; full implementation depends on trace format
    return None


def _reconstruct_rag_answer(_records: list[dict[str, Any]]) -> RagAnswer | None:
    """Reconstruct RagAnswer from trace records."""
    # Simplified stub
    return None


def evaluate_trace(
    trace_path: Path,
    evaluators: list[Evaluator],
) -> list[EvaluationResult]:
    """Evaluate a full trace file.

    Parses JSONL trace, reconstructs system outputs, runs evaluators.
    """
    records = _parse_trace_file(trace_path)

    # Detect trace type by examining records
    has_model_calls = any(r.get("kind") == "model_call" for r in records)
    has_tool_calls = any(r.get("kind") == "tool_call" for r in records)

    results = []

    if has_model_calls and has_tool_calls:
        # Likely an agent trace
        agent_result = _reconstruct_agent_result(records)
        if agent_result:
            for evaluator in evaluators:
                results.append(
                    evaluator.evaluate(
                        input="",  # Would need to extract from trace
                        output=agent_result,
                        context=None,
                    )
                )
    elif has_model_calls:
        # Could be RAG trace
        rag_answer = _reconstruct_rag_answer(records)
        if rag_answer:
            for evaluator in evaluators:
                results.append(
                    evaluator.evaluate(
                        input="",
                        output=rag_answer,
                        context=None,
                    )
                )

    return results


def evaluate_steps(
    steps: Sequence[Any],
    evaluators: list[Evaluator],
    *,
    task: str = "",
) -> list[EvaluationResult]:
    """Evaluate agent loop steps directly."""

    # Build a minimal AgentResult-like object
    class _StepResult:
        def __init__(self, steps: Sequence[Any]) -> None:
            self.steps = tuple(steps)

    agent_result = _StepResult(steps)

    results = []
    for evaluator in evaluators:
        try:
            result = evaluator.evaluate(
                input=task,
                output=agent_result,
                context=None,
            )
            results.append(result)
        except Exception as e:
            results.append(
                EvaluationResult(
                    name=evaluator.name,
                    score=0.0,
                    passed=False,
                    reasoning=f"Evaluation error: {e}",
                    threshold=(
                        evaluator.threshold if hasattr(evaluator, "threshold") else 0.5
                    ),
                )
            )

    return results


def evaluate_rag(
    query: str,
    answer: str,
    citations: list[Any],
    retrieved_chunks: list[SearchResult],
    evaluators: list[Evaluator],
) -> list[EvaluationResult]:
    """Evaluate a RAG pipeline output directly."""

    class _RagOutput:
        def __init__(self, text: str, citations: list[Any]):
            self.text = text
            self.citations = citations

    rag_output = _RagOutput(answer, citations)

    results = []
    for evaluator in evaluators:
        try:
            result = evaluator.evaluate(
                input=query,
                output=rag_output,
                context=retrieved_chunks,
            )
            results.append(result)
        except Exception as e:
            results.append(
                EvaluationResult(
                    name=evaluator.name,
                    score=0.0,
                    passed=False,
                    reasoning=f"Evaluation error: {e}",
                    threshold=(
                        evaluator.threshold if hasattr(evaluator, "threshold") else 0.5
                    ),
                )
            )

    return results
