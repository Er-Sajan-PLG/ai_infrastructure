"""Tests for System C — entirely internal composition.

Composes three TESTED capabilities:
- tool-registry
- model-provider-abstraction
- react-agent-loop

All consumed through public interfaces. No component is modified.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _sub in (
    "catalog/models",
    "catalog/tools",
    "catalog/agents",
    "integrations",
):
    sys.path.insert(0, str(_ROOT / _sub))

from agent_loop_end_to_end.scripted_transport import (  # noqa: E402
    MODEL,
    ScriptedTransport,
    openai_response,
)
from model_provider import ProviderError, WireResponse  # noqa: E402
from react_agent_loop import StopReason  # noqa: E402
from system_c_internal.system import build_registry, build_system_c  # noqa: E402


def _tool_response(name: str, arguments: dict[str, object]) -> WireResponse:
    """Build a scripted tool-call response."""
    return openai_response(
        tool_calls=[("call_1", f"math:{name}", arguments)],
    )


def _text_response(text: str) -> WireResponse:
    """Build a scripted text response."""
    return openai_response(text=text)


class TestSystemCComposition:
    def test_all_three_components_wired(self) -> None:
        system = build_system_c()
        assert system.registry is not None
        assert system.provider is not None
        assert system.caller is not None
        assert system.dispatcher is not None
        assert system.agent is not None

    def test_registry_has_three_tools(self) -> None:
        registry = build_registry()
        tools = registry.ids()
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert "add" in names
        assert "multiply" in names
        assert "lookup" in names

    def test_run_reaches_final_answer(self) -> None:
        system = build_system_c(
            responses=[_text_response("The answer is 42.")],
        )
        result = system.run("What is the answer?")
        assert result.reason == StopReason.FINAL_ANSWER
        assert result.final_text is not None

    def test_run_with_tool_call(self) -> None:
        system = build_system_c(
            responses=[
                _tool_response("add", {"a": 2, "b": 3}),
                _text_response("The sum is 5."),
            ],
        )
        result = system.run("Add 2 and 3.")
        assert result.reason == StopReason.FINAL_ANSWER
        assert result.final_text is not None

    def test_direct_chat_works(self) -> None:
        system = build_system_c(
            responses=[_text_response("direct answer")],
        )
        response = system.direct_chat("Hello")
        assert response is not None

    def test_transport_records_requests(self) -> None:
        system = build_system_c(
            responses=[_text_response("ok")],
        )
        system.run("test")
        assert len(system.transport.requests) >= 1

    def test_repetition_detection(self) -> None:
        # Same tool call twice → repetition brake stops the loop
        system = build_system_c(
            responses=[
                _tool_response("add", {"a": 1, "b": 2}),
                _tool_response("add", {"a": 1, "b": 2}),
                _tool_response("add", {"a": 1, "b": 2}),
            ],
        )
        result = system.run("Add 1 and 2 repeatedly.")
        # Should stop due to repetition, not FINAL_ANSWER
        assert result.reason != StopReason.FINAL_ANSWER

    def test_provider_error_propagates(self) -> None:
        system = build_system_c(
            responses=[
                WireResponse(status_code=429, body=b'{"error": "rate limited"}')
            ],
        )
        with pytest.raises(ProviderError):
            system.run("test")

    def test_step_limit(self) -> None:
        # Model keeps calling tools → loop hits step limit
        system = build_system_c(
            responses=[
                _tool_response("add", {"a": 1, "b": 2}),
                _tool_response("add", {"a": 2, "b": 3}),
                _tool_response("add", {"a": 3, "b": 4}),
            ],
        )
        result = system.run("test", max_steps=1)
        assert result.reason == StopReason.STEP_LIMIT

    def test_no_network(self) -> None:
        """Verify no test touches the network."""
        system = build_system_c(
            responses=[_text_response("ok")],
        )
        # ScriptedTransport never opens a socket
        assert isinstance(system.transport, ScriptedTransport)

    def test_model_name_matches(self) -> None:
        system = build_system_c()
        assert system.agent.model == MODEL

    def test_dispatcher_has_schemas(self) -> None:
        system = build_system_c()
        schemas = system.dispatcher.schemas()
        assert len(schemas) == 3
