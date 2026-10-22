"""LLM-as-Judge Adapter — wraps any LLM-backed evaluator with standard interface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from react_agent_loop.protocols import ModelCaller

from .protocols import EvaluationResult


@dataclass(frozen=True, slots=True)
class LLMJudgeAdapter:
    """Wraps any LLM-backed evaluator with a standard interface.

    Allows swapping judge models without changing evaluator code.
    """

    model_caller: ModelCaller
    judge_prompt: str
    parse_fn: Callable[[str], tuple[float, str]]  # output -> (score, reasoning)
    threshold: float = 0.5
    name: str = "llm_judge"

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    def evaluate(
        self,
        *,
        input: Any,
        output: Any,
        context: Any = None,
    ) -> EvaluationResult:
        # Build prompt with input/output/context
        prompt = self.judge_prompt.format(
            input=input,
            output=output,
            context=context,
        )
        response = self.model_caller.call(
            messages=[],
            system=prompt,
            tools=(),
        )
        score, reasoning = self.parse_fn(response.text)

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=reasoning,
            threshold=self.threshold,
        )
