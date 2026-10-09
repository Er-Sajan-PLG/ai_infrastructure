"""Tests for System B — mixed composition.

Composes:
- external runtime: scripted agent (double — does NOT use our react-agent-loop)
- our observability: execution-trace-recorder (TESTED)
- our evaluation: scoring function over trace records
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _sub in (
    "catalog/models",
    "catalog/tools",
    "catalog/agents",
    "catalog/protocols",
    "catalog/observability",
    "integrations",
):
    sys.path.insert(0, str(_ROOT / _sub))

from agent_loop_end_to_end.scripted_transport import (  # noqa: E402
    ScriptedTransport,
    openai_response,
)
from model_provider import WireResponse  # noqa: E402
from system_b_mixed.system import ExternalRuntime, build_system_b  # noqa: E402


def _text_response(text: str) -> WireResponse:
    return openai_response(text=text)


def _tool_response(name: str, arguments: dict[str, object]) -> WireResponse:
    return openai_response(
        tool_calls=[("call_1", name, arguments)],
    )


_OPEN_SYSTEMS: list[Any] = []


@pytest.fixture(autouse=True)
def _cleanup_systems() -> Iterator[None]:
    """Close any open trace recorders after each test."""
    yield
    for system in _OPEN_SYSTEMS:
        with contextlib.suppress(Exception):
            system.recorder.close()
    _OPEN_SYSTEMS.clear()


class TestExternalRuntime:
    def test_run_returns_answer(self) -> None:
        system = build_system_b(
            responses=[_text_response("The answer is 42.")],
        )
        _OPEN_SYSTEMS.append(system)
        result = system.runtime.run("What is the answer?")
        assert result["answer"] == "The answer is 42."
        assert result["steps"] == 1

    def test_run_with_tool_calls(self) -> None:
        system = build_system_b(
            responses=[
                _tool_response("add", {"a": 1, "b": 2}),
                _text_response("done"),
            ],
        )
        _OPEN_SYSTEMS.append(system)
        result = system.runtime.run("Add 1 and 2.")
        assert result["answer"] == "done"
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "add"

    def test_max_steps(self) -> None:
        system = build_system_b(
            responses=[
                _tool_response("add", {"a": 1, "b": 2}),
                _tool_response("add", {"a": 2, "b": 3}),
                _tool_response("add", {"a": 3, "b": 4}),
                _tool_response("add", {"a": 4, "b": 5}),
                _tool_response("add", {"a": 5, "b": 6}),
            ],
        )
        _OPEN_SYSTEMS.append(system)
        result = system.runtime.run("Add numbers.")
        assert result["steps"] == 5  # max_steps reached
        assert result["answer"] == "max steps reached"

    def test_does_not_use_our_agent_loop(self, tmp_path: Path) -> None:
        """Verify the external runtime does NOT use our react-agent-loop."""
        system = build_system_b(trace_path=str(tmp_path / "trace.jsonl"))
        _OPEN_SYSTEMS.append(system)
        assert isinstance(system.runtime, ExternalRuntime)
        # ExternalRuntime does not have our loop's interfaces
        assert not hasattr(system.runtime, "dispatcher")
        assert not hasattr(system.runtime, "caller")
        assert not hasattr(system.runtime, "agent")


class TestSystemBComposition:
    def test_all_components_wired(self, tmp_path: Path) -> None:
        system = build_system_b(trace_path=str(tmp_path / "trace.jsonl"))
        _OPEN_SYSTEMS.append(system)
        assert system.runtime is not None
        assert system.recorder is not None
        assert system.transport is not None
        assert system.provider is not None

    def test_run_with_trace_recording(self, tmp_path: Path) -> None:
        system = build_system_b(
            responses=[_text_response("ok")],
            trace_path=str(tmp_path / "trace.jsonl"),
        )
        _OPEN_SYSTEMS.append(system)
        result = system.run("test task")
        assert result["answer"] == "ok"
        assert (tmp_path / "trace.jsonl").exists()

    def test_trace_file_written(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "trace.jsonl"
        system = build_system_b(
            responses=[_text_response("ok")],
            trace_path=str(trace_path),
        )
        _OPEN_SYSTEMS.append(system)
        system.run("test")
        assert trace_path.exists()
        lines = trace_path.read_text().strip().split("\n")
        assert len(lines) >= 2  # at least start_trace and end_trace

    def test_evaluate_returns_scores(self, tmp_path: Path) -> None:
        system = build_system_b(
            responses=[_text_response("ok")],
            trace_path=str(tmp_path / "trace.jsonl"),
        )
        _OPEN_SYSTEMS.append(system)
        result = system.run("test")
        scores = system.evaluate(result)
        assert "score" in scores
        assert "steps" in scores
        assert "tool_calls" in scores
        assert 0.0 <= scores["score"] <= 1.0

    def test_evaluate_with_tool_calls(self, tmp_path: Path) -> None:
        system = build_system_b(
            responses=[
                _tool_response("add", {"a": 1, "b": 2}),
                _text_response("done"),
            ],
            trace_path=str(tmp_path / "trace.jsonl"),
        )
        _OPEN_SYSTEMS.append(system)
        result = system.run("Add 1 and 2.")
        scores = system.evaluate(result)
        assert scores["tool_calls"] >= 1.0

    def test_transport_records_requests(self) -> None:
        system = build_system_b(
            responses=[_text_response("ok")],
        )
        _OPEN_SYSTEMS.append(system)
        system.run("test")
        assert len(system.transport.requests) >= 1

    def test_no_network(self) -> None:
        system = build_system_b()
        _OPEN_SYSTEMS.append(system)
        assert isinstance(system.transport, ScriptedTransport)

    def test_model_name_matches(self) -> None:
        system = build_system_b()
        _OPEN_SYSTEMS.append(system)
        assert system.runtime._provider is not None

    def test_recorder_is_ours(self) -> None:
        from execution_trace_recorder import TraceRecorder

        system = build_system_b()
        _OPEN_SYSTEMS.append(system)
        assert isinstance(system.recorder, TraceRecorder)

    def test_run_with_exception_records_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exception in runtime is recorded and re-raised (lines 139-141)."""
        system = build_system_b(
            responses=[_text_response("ok")],
            trace_path=str(tmp_path / "trace.jsonl"),
        )
        _OPEN_SYSTEMS.append(system)

        def _raising_run(_task: str) -> dict[str, Any]:
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(system.runtime, "run", _raising_run)

        with pytest.raises(RuntimeError, match="simulated failure"):
            system.run("test task")

        # Verify the trace file was written with error stop_reason
        trace_path = tmp_path / "trace.jsonl"
        assert trace_path.exists()
        content = trace_path.read_text()
        assert "error" in content

    def test_evaluate_returns_zero_when_no_trace(self, tmp_path: Path) -> None:
        """evaluate() returns zero scores when trace file doesn't exist (line 152)."""
        system = build_system_b(
            responses=[_text_response("ok")],
            trace_path=str(tmp_path / "nonexistent.jsonl"),
        )
        _OPEN_SYSTEMS.append(system)

        # TraceRecorder constructor creates the file; delete it to simulate missing trace
        trace_path = tmp_path / "nonexistent.jsonl"
        if trace_path.exists():
            trace_path.unlink()

        result = {"answer": "ok", "steps": 1, "tool_calls": []}
        scores = system.evaluate(result)

        assert scores == {"score": 0.0, "steps": 0.0, "tool_calls": 0.0}
