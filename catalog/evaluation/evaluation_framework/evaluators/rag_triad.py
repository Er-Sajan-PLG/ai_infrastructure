"""RAG Triad evaluators — require injected ModelCaller for LLM-as-judge.

Includes Faithfulness, AnswerRelevance, ContextPrecision, ContextRecall.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from react_agent_loop.protocols import ModelCaller

from ..protocols import EvaluationResult

# Shared prompt templates
_FAITHFULNESS_PROMPT = """You are evaluating whether an answer stays faithful to the provided context.

Context:
{context}

Answer:
{answer}

Question: Does the answer contain claims not supported by the context?
Respond with a score from 0 to 1 where:
- 1.0 = fully faithful, no hallucinations
- 0.5 = partially faithful, minor unsupported claims
- 0.0 = major hallucinations, contradicts context

Then provide brief reasoning.

Format:
SCORE: <number>
REASONING: <text>"""

_ANSWER_RELEVANCE_PROMPT = """You are evaluating whether an answer addresses the query.

Query:
{query}

Answer:
{answer}

Question: Does this answer address the question?
Respond with a score from 0 to 1 where:
- 1.0 = directly and completely answers the question
- 0.5 = partially answers, missing key aspects
- 0.0 = irrelevant or does not answer

Then provide brief reasoning.

Format:
SCORE: <number>
REASONING: <text>"""

_CONTEXT_PRECISION_PROMPT = """You are evaluating whether retrieved chunks are relevant to the query.

Query:
{query}

Retrieved chunks:
{chunks}

Question: For each chunk, is it relevant to answering the query?
Respond with a score from 0 to 1 representing the fraction of relevant chunks.
Then provide brief reasoning.

Format:
SCORE: <number>
REASONING: <text>"""

_CONTEXT_RECALL_PROMPT = """You are evaluating whether the retrieved context contains all information needed for the answer.

Query:
{query}

Answer:
{answer}

Retrieved chunks:
{chunks}

Question: Can the answer be derived from the context? Is critical information missing?
Respond with a score from 0 to 1 where:
- 1.0 = all necessary information present in context
- 0.5 = most information present, some gaps
- 0.0 = critical information missing

Then provide brief reasoning.

Format:
SCORE: <number>
REASONING: <text>"""


def _parse_judge_response(response: str) -> tuple[float, str]:
    """Parse LLM judge response into (score, reasoning)."""
    score = 0.0
    reasoning = ""
    for line in response.strip().splitlines():
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                score = float(line.split(":", 1)[1].strip())
                score = max(0.0, min(1.0, score))
            except ValueError:
                pass
        elif line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()
    return score, reasoning


@dataclass(frozen=True, slots=True)
class Faithfulness:
    """LLM-as-judge: answer should not hallucinate beyond context."""

    model_caller: ModelCaller
    threshold: float = 0.7
    prompt_template: str = _FAITHFULNESS_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "faithfulness"

    def evaluate(
        self,
        *,
        input: str,
        output: str,
        context: list[Any] | None = None,
    ) -> EvaluationResult:
        context_text = (
            "\n\n".join(
                f"[{getattr(r, 'id', 'chunk')}] {getattr(r, 'metadata', {}).get('text', str(r))}"
                for r in (context or [])
            )
            or "(no context retrieved)"
        )

        prompt = self.prompt_template.format(context=context_text, answer=output)
        response = self.model_caller.call(
            messages=[],  # The prompt is self-contained
            system=prompt,
            tools=(),
        )
        score, reasoning = _parse_judge_response(response.text)

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=reasoning,
            threshold=self.threshold,
        )


@dataclass(frozen=True, slots=True)
class AnswerRelevance:
    """LLM-as-judge: answer should be relevant to the query."""

    model_caller: ModelCaller
    threshold: float = 0.7
    prompt_template: str = _ANSWER_RELEVANCE_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "answer_relevance"

    def evaluate(
        self,
        *,
        input: str,
        output: str,
        context: Any = None,
    ) -> EvaluationResult:
        prompt = self.prompt_template.format(query=input, answer=output)
        response = self.model_caller.call(
            messages=[],
            system=prompt,
            tools=(),
        )
        score, reasoning = _parse_judge_response(response.text)

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=reasoning,
            threshold=self.threshold,
        )


@dataclass(frozen=True, slots=True)
class ContextPrecision:
    """LLM-as-judge: top chunks should be relevant."""

    model_caller: ModelCaller
    threshold: float = 0.7
    prompt_template: str = _CONTEXT_PRECISION_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "context_precision"

    def evaluate(
        self,
        *,
        input: str,
        output: Any,
        context: list[Any] | None = None,
    ) -> EvaluationResult:
        chunks_text = (
            "\n\n".join(
                f"[{getattr(r, 'id', 'chunk')}] {getattr(r, 'metadata', {}).get('text', str(r))}"
                for r in (context or [])
            )
            or "(no chunks retrieved)"
        )

        prompt = self.prompt_template.format(query=input, chunks=chunks_text)
        response = self.model_caller.call(
            messages=[],
            system=prompt,
            tools=(),
        )
        score, reasoning = _parse_judge_response(response.text)

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=reasoning,
            threshold=self.threshold,
        )


@dataclass(frozen=True, slots=True)
class ContextRecall:
    """LLM-as-judge: context should contain all info needed for answer."""

    model_caller: ModelCaller
    threshold: float = 0.7
    prompt_template: str = _CONTEXT_RECALL_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "context_recall"

    def evaluate(
        self,
        *,
        input: str,
        output: str,
        context: list[Any] | None = None,
    ) -> EvaluationResult:
        chunks_text = (
            "\n\n".join(
                f"[{getattr(r, 'id', 'chunk')}] {getattr(r, 'metadata', {}).get('text', str(r))}"
                for r in (context or [])
            )
            or "(no chunks retrieved)"
        )

        prompt = self.prompt_template.format(
            query=input, answer=output, chunks=chunks_text
        )
        response = self.model_caller.call(
            messages=[],
            system=prompt,
            tools=(),
        )
        score, reasoning = _parse_judge_response(response.text)

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=reasoning,
            threshold=self.threshold,
        )
