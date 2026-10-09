"""System C — entirely composed from ai_infrastructure components.

Composes three TESTED capabilities:
- tool-registry (tools)
- model-provider-abstraction (models)
- react-agent-loop (agents)

All components are consumed through their public interfaces only.
No component is modified, subclassed, or monkey-patched.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from agent_loop_end_to_end.scripted_transport import (
    MODEL,
    ScriptedTransport,
    openai_response,
)
from model_provider import (
    ChatRequest,
    ChatResponse,
    Message,
    Provider,
    Role,
    TextBlock,
    chat,
)
from model_provider.providers import OpenAIProvider
from react_agent_loop import (
    Agent,
    AgentResult,
    ProviderCaller,
    RegistryDispatcher,
    run,
)
from tool_registry import ToolId, ToolRegistry


def build_registry() -> ToolRegistry:
    """Build a registry with tools that demonstrate composition."""
    registry = ToolRegistry()

    registry.register(
        tool_id=ToolId("math", "add"),
        description="Add two integers and return the sum.",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        callable_=lambda *, a, b: str(a + b),
    )

    registry.register(
        tool_id=ToolId("math", "multiply"),
        description="Multiply two integers and return the product.",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        callable_=lambda *, a, b: str(a * b),
    )

    facts = {"capital_of_france": "Paris", "capital_of_japan": "Tokyo"}
    registry.register(
        tool_id=ToolId("facts", "lookup"),
        description="Look up a fact by key.",
        input_schema={
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
            "additionalProperties": False,
        },
        callable_=lambda *, key: facts.get(key, "unknown"),
    )

    return registry


@dataclass
class SystemC:
    """A wired system: tool-registry + model-provider + react-agent-loop."""

    registry: ToolRegistry
    transport: ScriptedTransport
    provider: Provider
    caller: ProviderCaller
    dispatcher: RegistryDispatcher
    agent: Agent

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        """Run the agent loop."""
        return run(
            task,
            agent=self.agent,
            model_caller=self.caller,
            dispatcher=self.dispatcher,
            **kwargs,
        )

    def direct_chat(self, task: str, *, system: str | None = None) -> ChatResponse:
        """Call the provider directly, with no loop and no registry."""
        return chat(
            ChatRequest(
                model=MODEL,
                messages=[Message(role=Role.USER, content=(TextBlock(text=task),))],
                system=system,
                tools=self.dispatcher.schemas(),
            ),
            provider=self.provider,
            transport=self.transport,
            api_key="scripted-key",
        )


def build_system_c(
    responses: Sequence[Any] | None = None,
) -> SystemC:
    """Assemble System C with a scripted transport.

    Args:
        responses: WireResponse objects to return, one per model call.

    Returns:
        A SystemC whose parts a test can inspect.
    """
    scripted = (
        list(responses) if responses is not None else [openai_response(text="ok")]
    )

    registry = build_registry()
    transport = ScriptedTransport(scripted)
    provider = OpenAIProvider()

    return SystemC(
        registry=registry,
        transport=transport,
        provider=provider,
        caller=ProviderCaller(
            provider=provider,
            transport=transport,
            api_key="scripted-key",
            model=MODEL,
        ),
        dispatcher=RegistryDispatcher(registry),
        agent=Agent(model=MODEL, system="You are a helpful assistant."),
    )
