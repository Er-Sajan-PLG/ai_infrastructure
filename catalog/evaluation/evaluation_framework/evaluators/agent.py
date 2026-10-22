"""Agent evaluators — require injected ModelCaller for LLM-as-judge.

Includes LogicalConsistency, ExecutionEfficiency, PlanAdherence, ToolSelection, ToolCalling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from react_agent_loop import AgentResult, Step
from react_agent_loop.protocols import ModelCaller
from tool_registry import ToolDescriptor, ToolRegistry
from tool_registry.schema import validate_arguments

from ..protocols import EvaluationResult

_LOGICAL_CONSISTENCY_PROMPT = """You are evaluating the logical consistency of an agent's reasoning trace.

Task:
{task}

Agent steps:
{steps}

Question: Is the reasoning coherent? Are there contradictions between steps?
Respond with a score from 0 to 1 where:
- 1.0 = fully consistent, no contradictions
- 0.5 = minor inconsistencies
- 0.0 = major contradictions, incoherent reasoning

Then provide brief reasoning.

Format:
SCORE: <number>
REASONING: <text>"""

_EXECUTION_EFFICIENCY_PROMPT = """You are evaluating the execution efficiency of an agent.

Task:
{task}

Agent steps ({num_steps} steps):
{steps}

Question: Did the agent take unnecessary steps? Were there redundant tool calls or backtracking?
Respond with a score from 0 to 1 where:
- 1.0 = optimal, no wasted steps
- 0.5 = some redundancy but reasonable
- 0.0 = highly inefficient, many redundant steps

Then provide brief reasoning.

Format:
SCORE: <number>
REASONING: <text>"""

_PLAN_ADHERENCE_PROMPT = """You are evaluating whether an agent followed its plan.

Task:
{task}

Plan (extracted from first steps or provided):
{plan}

Actual execution:
{steps}

Question: Did the agent follow the plan? Did it deviate without reason?
Respond with a score from 0 to 1 where:
- 1.0 = fully adhered to plan
- 0.5 = partially adhered, minor deviations
- 0.0 = ignored plan entirely

Then provide brief reasoning.

Format:
SCORE: <number>
REASONING: <text>"""

_TOOL_SELECTION_PROMPT = """You are evaluating whether an agent chose appropriate tools.

Task:
{task}

Available tools:
{tools}

Agent tool calls:
{calls}

Question: For each tool call, was it the right choice for that step?
Respond with a score from 0 to 1 representing the fraction of appropriate tool choices.
Then provide brief reasoning.

Format:
SCORE: <number>
REASONING: <text>"""

_TOOL_CALLING_PROMPT = """You are evaluating whether an agent called tools correctly and used results appropriately.

Task:
{task}

Agent steps with tool calls and results:
{steps}

Question: Were tool arguments valid? Were results used appropriately in subsequent steps?
Respond with a score from 0 to 1 where:
- 1.0 = all calls valid, results used well
- 0.5 = minor issues with arguments or result usage
- 0.0 = invalid arguments or ignored results

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


def _format_steps(steps: tuple[Step, ...]) -> str:
    """Format agent steps for prompt."""
    lines = []
    for step in steps:
        lines.append(f"Step {step.index}:")
        if step.text:
            lines.append(f"  Reasoning: {step.text[:500]}")
        if step.tool_calls:
            for call in step.tool_calls:
                lines.append(f"  Tool: {call.name}({call.arguments})")
        if step.dispatches:
            for disp in step.dispatches:
                status = "OK" if disp.ok else f"FAILED ({disp.kind})"
                lines.append(f"  Result: {status} - {disp.observation_chars} chars")
    return "\n".join(lines)


def _format_tools(tools: list[ToolDescriptor]) -> str:
    """Format tool descriptors for prompt."""
    lines = []
    for tool in tools:
        lines.append(f"- {tool.id}: {tool.description}")
    return "\n".join(lines) or "(no tools available)"


def _format_tool_calls(steps: tuple[Step, ...]) -> str:
    """Format tool calls for prompt."""
    lines = []
    for step in steps:
        for call in step.tool_calls:
            lines.append(f"- Step {step.index}: {call.name}({call.arguments})")
    return "\n".join(lines) or "(no tool calls)"


@dataclass(frozen=True, slots=True)
class LogicalConsistency:
    """LLM-as-judge: reasoning steps should be coherent."""

    model_caller: ModelCaller
    threshold: float = 0.7
    prompt_template: str = _LOGICAL_CONSISTENCY_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "logical_consistency"

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: Any = None,
    ) -> EvaluationResult:
        steps_text = _format_steps(output.steps)
        prompt = self.prompt_template.format(task=input, steps=steps_text)
        response = self.model_caller.call(messages=[], system=prompt, tools=())
        score, reasoning = _parse_judge_response(response.text)

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=reasoning,
            threshold=self.threshold,
        )


@dataclass(frozen=True, slots=True)
class ExecutionEfficiency:
    """Measures step efficiency vs optimal."""

    model_caller: ModelCaller | None = None
    optimal_steps: int | None = None
    threshold: float = 0.7
    prompt_template: str = _EXECUTION_EFFICIENCY_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "execution_efficiency"

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: Any = None,
    ) -> EvaluationResult:
        actual_steps = len(output.steps)

        # If optimal_steps known, use ratio
        if self.optimal_steps is not None and self.optimal_steps > 0:
            score = min(1.0, self.optimal_steps / actual_steps)
            reasoning = f"Optimal: {self.optimal_steps}, Actual: {actual_steps}, Ratio: {score:.2f}"
            return EvaluationResult(
                name=self.name,
                score=score,
                passed=score >= self.threshold,
                reasoning=reasoning,
                threshold=self.threshold,
            )

        # Otherwise use LLM judge if available
        if self.model_caller is not None:
            steps_text = _format_steps(output.steps)
            prompt = self.prompt_template.format(
                task=input, num_steps=actual_steps, steps=steps_text
            )
            response = self.model_caller.call(messages=[], system=prompt, tools=())
            score, reasoning = _parse_judge_response(response.text)
            return EvaluationResult(
                name=self.name,
                score=score,
                passed=score >= self.threshold,
                reasoning=reasoning,
                threshold=self.threshold,
            )

        # Fallback: heuristic based on repetition
        repeated = sum(1 for step in output.steps if getattr(step, "repeated", False))
        score = max(0.0, 1.0 - (repeated * 0.2))
        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=f"Heuristic: {actual_steps} steps, {repeated} repeated",
            threshold=self.threshold,
        )


@dataclass(frozen=True, slots=True)
class PlanAdherence:
    """LLM-as-judge: execution should follow plan."""

    model_caller: ModelCaller
    threshold: float = 0.7
    prompt_template: str = _PLAN_ADHERENCE_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "plan_adherence"

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: str | None = None,
    ) -> EvaluationResult:
        steps_text = _format_steps(output.steps)
        plan = context or (output.steps[0].text if output.steps else "(no plan)")
        prompt = self.prompt_template.format(task=input, plan=plan, steps=steps_text)
        response = self.model_caller.call(messages=[], system=prompt, tools=())
        score, reasoning = _parse_judge_response(response.text)

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=reasoning,
            threshold=self.threshold,
        )


@dataclass(frozen=True, slots=True)
class ToolSelection:
    """LLM-as-judge: tool choice should be appropriate."""

    model_caller: ModelCaller
    threshold: float = 0.7
    prompt_template: str = _TOOL_SELECTION_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "tool_selection"

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: list[ToolDescriptor] | None = None,
    ) -> EvaluationResult:
        tools = context or []
        tools_text = _format_tools(tools)
        calls_text = _format_tool_calls(output.steps)
        prompt = self.prompt_template.format(
            task=input, tools=tools_text, calls=calls_text
        )
        response = self.model_caller.call(messages=[], system=prompt, tools=())
        score, reasoning = _parse_judge_response(response.text)

        return EvaluationResult(
            name=self.name,
            score=score,
            passed=score >= self.threshold,
            reasoning=reasoning,
            threshold=self.threshold,
        )


@dataclass(frozen=True, slots=True)
class ToolCalling:
    """Validates tool call arguments and result interpretation."""

    model_caller: ModelCaller | None = None
    threshold: float = 0.7
    prompt_template: str = _TOOL_CALLING_PROMPT

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold must be in [0, 1], got {self.threshold}")

    @property
    def name(self) -> str:
        return "tool_calling"

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: ToolRegistry | None = None,
    ) -> EvaluationResult:
        # First: deterministic schema validation if ToolRegistry provided
        schema_violations = 0
        total_calls = 0
        if context is not None:
            for step in output.steps:
                for call in step.tool_calls:
                    total_calls += 1
                    # Find tool by name (namespace-agnostic lookup)
                    tool = None
                    for tool_id in context.ids():
                        if tool_id.name == call.name:
                            tool = context.get(tool_id)
                            break
                    if tool:
                        problems = validate_arguments(
                            tool.validation_schema, call.arguments
                        )
                        if problems:
                            schema_violations += 1

            if total_calls > 0:
                schema_score = 1.0 - (schema_violations / total_calls)
            else:
                schema_score = 1.0
        else:
            schema_score = 1.0

        # Second: LLM judge for result usage if available
        if self.model_caller is not None:
            steps_text = _format_steps(output.steps)
            prompt = self.prompt_template.format(task=input, steps=steps_text)
            response = self.model_caller.call(messages=[], system=prompt, tools=())
            judge_score, reasoning = _parse_judge_response(response.text)
            # Combine: average of schema score and judge score
            combined_score = (schema_score + judge_score) / 2
            return EvaluationResult(
                name=self.name,
                score=combined_score,
                passed=combined_score >= self.threshold,
                reasoning=f"Schema: {schema_score:.2f}, Judge: {judge_score:.2f}. {reasoning}",
                threshold=self.threshold,
            )

        return EvaluationResult(
            name=self.name,
            score=schema_score,
            passed=schema_score >= self.threshold,
            reasoning=f"Schema validation: {schema_score:.2f} ({schema_violations}/{total_calls} violations)",
            threshold=self.threshold,
        )
