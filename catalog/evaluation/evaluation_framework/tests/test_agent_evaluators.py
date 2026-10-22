"""Tests for agent evaluators (with mock ModelCaller)."""

from __future__ import annotations

import sys
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
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402
from evaluation_framework.evaluators.agent import (  # noqa: E402
    ExecutionEfficiency,
    LogicalConsistency,
    PlanAdherence,
    ToolCalling,
    ToolSelection,
)
from model_provider import ToolCallBlock  # noqa: E402
from react_agent_loop import AgentResult, Step, StopReason  # noqa: E402
from tool_registry import ToolDescriptor, ToolId, ToolRegistry  # noqa: E402

# ---------------------------------------------------------------------------
# Mock ModelCaller
# ---------------------------------------------------------------------------


@dataclass
class MockChatResponse:
    text: str
    blocks: tuple[Any, ...] = ()
    tool_calls: tuple[Any, ...] = ()
    usage: None = None
    model: str = "mock"
    provider: str = "mock"
    finish_reason: str = "stop"
    raw_finish_reason: str = "stop"


class MockModelCaller:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0
        self.calls: list[Any] = []

    def call(self, messages: Any, *, system: Any = None, tools: Any = ()) -> Any:
        self.calls.append({"messages": messages, "system": system, "tools": tools})
        if self.index >= len(self.responses):
            return MockChatResponse(text="SCORE: 0.5\nREASONING: Default")
        response_text = self.responses[self.index]
        self.index += 1
        return MockChatResponse(text=response_text)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _make_tool_call(id: str, name: str, args: dict[str, Any]) -> ToolCallBlock:
    return ToolCallBlock(id=id, name=name, arguments=args)


def _make_step(index: int, text: str, tool_calls: tuple[Any, ...] = ()) -> Step:
    return Step(index=index, text=text, tool_calls=tool_calls, dispatches=())


def _make_agent_result(
    steps: list[Step], reason: StopReason = StopReason.FINAL_ANSWER
) -> AgentResult:
    return AgentResult(
        reason=reason,
        final_text="Done",
        steps=tuple(steps),
        usage=None,
        messages=(),
    )


# ---------------------------------------------------------------------------
# LogicalConsistency Tests
# ---------------------------------------------------------------------------


class TestLogicalConsistency:
    def test_consistent(self) -> None:
        caller = MockModelCaller(["SCORE: 0.9\nREASONING: Coherent"])
        evaluator = LogicalConsistency(caller, threshold=0.7)
        steps = [
            _make_step(
                1,
                "I need to add numbers",
                (_make_tool_call("1", "add", {"a": 1, "b": 2}),),
            ),
            _make_step(2, "The result is 3", ()),
        ]
        result = evaluator.evaluate(input="Add 1+2", output=_make_agent_result(steps))
        assert result.score == 0.9
        assert result.passed

    def test_inconsistent(self) -> None:
        caller = MockModelCaller(["SCORE: 0.2\nREASONING: Contradiction"])
        evaluator = LogicalConsistency(caller, threshold=0.7)
        steps = [
            _make_step(1, "I'll add", (_make_tool_call("1", "add", {"a": 1, "b": 2}),)),
            _make_step(
                2,
                "Actually I'll subtract",
                (_make_tool_call("2", "sub", {"a": 5, "b": 3}),),
            ),
        ]
        result = evaluator.evaluate(input="Add 1+2", output=_make_agent_result(steps))
        assert result.score == 0.2
        assert not result.passed


# ---------------------------------------------------------------------------
# ExecutionEfficiency Tests
# ---------------------------------------------------------------------------


class TestExecutionEfficiency:
    def test_optimal_steps_known(self) -> None:
        evaluator = ExecutionEfficiency(optimal_steps=2, threshold=0.7)
        # 2 steps, optimal is 2 -> score 1.0
        steps = [_make_step(1, "Add", ()), _make_step(2, "Done", ())]
        result = evaluator.evaluate(input="Add", output=_make_agent_result(steps))
        assert result.score == 1.0
        assert result.passed

    def test_more_steps_than_optimal(self) -> None:
        evaluator = ExecutionEfficiency(optimal_steps=2, threshold=0.7)
        # 4 steps, optimal is 2 -> score 0.5
        steps = [
            _make_step(1, "Add", ()),
            _make_step(2, "Check", ()),
            _make_step(3, "Retry", ()),
            _make_step(4, "Done", ()),
        ]
        result = evaluator.evaluate(input="Add", output=_make_agent_result(steps))
        assert result.score == 0.5
        assert not result.passed

    def test_with_model_caller(self) -> None:
        caller = MockModelCaller(["SCORE: 0.8\nREASONING: Efficient"])
        evaluator = ExecutionEfficiency(model_caller=caller, threshold=0.7)
        steps = [_make_step(1, "Add", ()), _make_step(2, "Done", ())]
        result = evaluator.evaluate(input="Add", output=_make_agent_result(steps))
        assert result.score == 0.8
        assert result.passed

    def test_heuristic_fallback(self) -> None:
        evaluator = ExecutionEfficiency(threshold=0.7)
        steps = [_make_step(1, "Add", ()), _make_step(2, "Done", ())]
        result = evaluator.evaluate(input="Add", output=_make_agent_result(steps))
        assert result.score == 1.0  # No repetition, heuristic gives 1.0

    def test_repetition_penalty_not_supported(self) -> None:
        """Test that repetition heuristic is not supported (Step has no repeated field)."""
        evaluator = ExecutionEfficiency(threshold=0.7)
        steps = [
            _make_step(1, "Add", ()),
            _make_step(2, "Add again", ()),
        ]
        result = evaluator.evaluate(input="Add", output=_make_agent_result(steps))
        # Without repeated field, heuristic gives 1.0 (no penalty)
        assert result.score == 1.0
        assert result.passed


# ---------------------------------------------------------------------------
# PlanAdherence Tests
# ---------------------------------------------------------------------------


class TestPlanAdherence:
    def test_adhered(self) -> None:
        caller = MockModelCaller(["SCORE: 0.9\nREASONING: Followed plan"])
        evaluator = PlanAdherence(caller, threshold=0.7)
        steps = [
            _make_step(
                1,
                "Plan: add then multiply",
                (_make_tool_call("1", "add", {"a": 1, "b": 2}),),
            ),
            _make_step(
                2, "Multiply result", (_make_tool_call("2", "mul", {"x": 3, "y": 4}),)
            ),
        ]
        result = evaluator.evaluate(
            input="Compute",
            output=_make_agent_result(steps),
            context="Plan: add then multiply",
        )
        assert result.score == 0.9
        assert result.passed

    def test_deviated(self) -> None:
        caller = MockModelCaller(["SCORE: 0.3\nREASONING: Deviated from plan"])
        evaluator = PlanAdherence(caller, threshold=0.7)
        steps = [
            _make_step(
                1, "Plan: add", (_make_tool_call("1", "add", {"a": 1, "b": 2}),)
            ),
            _make_step(
                2, "Actually subtract", (_make_tool_call("2", "sub", {"a": 5, "b": 3}),)
            ),
        ]
        result = evaluator.evaluate(
            input="Compute", output=_make_agent_result(steps), context="Plan: add only"
        )
        assert result.score == 0.3
        assert not result.passed


# ---------------------------------------------------------------------------
# ToolSelection Tests
# ---------------------------------------------------------------------------


class TestToolSelection:
    def test_appropriate(self) -> None:
        caller = MockModelCaller(["SCORE: 0.9\nREASONING: Right tools"])
        evaluator = ToolSelection(caller, threshold=0.7)
        tools = [
            ToolDescriptor(
                id=ToolId("math", "add"),
                description="Add numbers",
                input_schema={
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
                injected=frozenset(),
            ),
        ]
        steps = [_make_step(1, "Add", (_make_tool_call("1", "add", {"a": 1, "b": 2}),))]
        result = evaluator.evaluate(
            input="Add 1+2", output=_make_agent_result(steps), context=tools
        )
        assert result.score == 0.9
        assert result.passed

    def test_inappropriate(self) -> None:
        caller = MockModelCaller(["SCORE: 0.2\nREASONING: Wrong tool"])
        evaluator = ToolSelection(caller, threshold=0.7)
        tools = [
            ToolDescriptor(
                id=ToolId("math", "add"),
                description="Add numbers",
                input_schema={
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
                injected=frozenset(),
            ),
        ]
        steps = [
            _make_step(1, "Multiply", (_make_tool_call("1", "mul", {"x": 2, "y": 3}),))
        ]
        result = evaluator.evaluate(
            input="Add 1+2", output=_make_agent_result(steps), context=tools
        )
        assert result.score == 0.2
        assert not result.passed


# ---------------------------------------------------------------------------
# ToolCalling Tests
# ---------------------------------------------------------------------------


class TestToolCalling:
    def test_with_registry_valid(self) -> None:
        registry = ToolRegistry()
        registry.register(
            tool_id=ToolId("test", "add"),
            description="Add",
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
            callable_=lambda *, a, b: a + b,
        )
        evaluator = ToolCalling(threshold=0.7)
        steps = [_make_step(1, "Add", (_make_tool_call("1", "add", {"a": 1, "b": 2}),))]
        result = evaluator.evaluate(
            input="Add", output=_make_agent_result(steps), context=registry
        )
        assert result.score == 1.0
        assert result.passed

    def test_with_registry_invalid_args(self) -> None:
        registry = ToolRegistry()
        registry.register(
            tool_id=ToolId("test", "add"),
            description="Add",
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
            callable_=lambda *, a, b: a + b,
        )
        evaluator = ToolCalling(threshold=0.7)
        steps = [
            _make_step(1, "Add", (_make_tool_call("1", "add", {"a": "one", "b": 2}),))
        ]  # Invalid type
        result = evaluator.evaluate(
            input="Add", output=_make_agent_result(steps), context=registry
        )
        assert result.score == 0.0  # Schema violation
        assert not result.passed

    def test_with_model_caller(self) -> None:
        registry = ToolRegistry()
        registry.register(
            tool_id=ToolId("test", "add"),
            description="Add",
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
            callable_=lambda *, a, b: a + b,
        )
        caller = MockModelCaller(["SCORE: 0.9\nREASONING: Good usage"])
        evaluator = ToolCalling(model_caller=caller, threshold=0.7)
        steps = [_make_step(1, "Add", (_make_tool_call("1", "add", {"a": 1, "b": 2}),))]
        result = evaluator.evaluate(
            input="Add", output=_make_agent_result(steps), context=registry
        )
        # Combined: (1.0 + 0.9) / 2 = 0.95
        assert result.score == pytest.approx(0.95)
        assert result.passed

    def test_no_registry_no_model(self) -> None:
        evaluator = ToolCalling(threshold=0.7)
        steps = [_make_step(1, "Add", (_make_tool_call("1", "add", {"a": 1, "b": 2}),))]
        result = evaluator.evaluate(
            input="Add", output=_make_agent_result(steps), context=None
        )
        assert result.score == 1.0  # No validation possible, defaults to pass
        assert result.passed
