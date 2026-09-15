"""Wire the three capabilities into one working system.

This module is the whole integration: it builds a real
:class:`~tool_registry.ToolRegistry` with real tools, a real OpenAI adapter over a
scripted transport, and runs the real agent loop across them. Nothing is
mocked except the socket.

**It consumes catalog components through their public interfaces only.** Three
imports, all of them package roots::

    from model_provider import ...          # catalog/models/model_provider
    from react_agent_loop import ...        # catalog/agents/react_agent_loop
    from tool_registry import ...           # catalog/tools/tool_registry

No module imports another capability's internals, subclasses its types, or
monkey-patches it. If the composition only worked by reaching inside one of
them, that would be the defect this integration exists to expose.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

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

from .scripted_transport import MODEL, ScriptedTransport, openai_response

__all__ = ["Demo", "build_demo", "build_registry"]


def build_registry() -> ToolRegistry:
    """Build a registry with three real tools.

    The tools are deliberately different in kind, because a composition that only
    works for one shape of tool is not much of a demonstration:

    * ``demo:add`` -- pure computation, always succeeds.
    * ``demo:lookup`` -- returns a value the model must then use, exercising the
      observe-then-act half of the loop.
    * ``demo:fail`` -- raises on demand, exercising the ``EXECUTION_FAILED`` path
      where the registry returns a *model-visible* failure rather than raising.

    Returns:
        A registry holding exactly these three tools.
    """
    registry = ToolRegistry()

    registry.register(
        tool_id=ToolId("demo", "add"),
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

    facts = {"capital_of_france": "Paris", "capital_of_japan": "Tokyo"}

    registry.register(
        tool_id=ToolId("demo", "lookup"),
        description="Look up a fact by key.",
        input_schema={
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
            "additionalProperties": False,
        },
        callable_=lambda *, key: facts.get(key, "unknown"),
    )

    def _always_raises(*, reason: str) -> str:
        raise ValueError(f"tool refused: {reason}")

    registry.register(
        tool_id=ToolId("demo", "fail"),
        description="Always raises. Used to exercise the failure path.",
        input_schema={
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
            "additionalProperties": False,
        },
        callable_=_always_raises,
    )

    return registry


@dataclass
class Demo:
    """A wired system, held together so a test can inspect every part.

    Attributes:
        registry: The real registry.
        transport: The scripted transport, whose ``requests`` record what the
            loop actually sent.
        provider: The real OpenAI adapter.
        caller: The loop's ``ModelCaller`` adapter over the provider.
        dispatcher: The loop's ``ToolDispatcher`` adapter over the registry.
        agent: The agent configuration handed to the loop.
    """

    registry: ToolRegistry
    transport: ScriptedTransport
    provider: Provider
    caller: ProviderCaller
    dispatcher: RegistryDispatcher
    agent: Agent

    def run(self, task: str, **kwargs: Any) -> AgentResult:
        """Run the loop against this system.

        Thin pass-through, so a test reads ``demo.run("...")`` rather than
        restating the four injected arguments every time -- and so there is
        exactly one place where the wiring could be wrong.
        """
        return run(
            task,
            agent=self.agent,
            model_caller=self.caller,
            dispatcher=self.dispatcher,
            **kwargs,
        )

    def direct_chat(self, task: str, *, system: str | None = None) -> ChatResponse:
        """Call the provider directly, with no loop and no registry.

        Exists to prove the provider layer works *independently* of the loop. If
        the only evidence that ``model-provider-abstraction`` functions were
        mediated by ``react-agent-loop``, a defect in either would be
        indistinguishable from a defect in the composition.
        """
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


def build_demo(responses: Sequence[Any] | None = None, **transport_kwargs: Any) -> Demo:
    """Assemble the full system with a scripted transport.

    Args:
        responses: The :class:`~model_provider.WireResponse` objects to return,
            one per model call. Defaults to a single plain text answer, which is
            the smallest runnable system.
        **transport_kwargs: Forwarded to
            :class:`ScriptedTransport`. Unused by this integration and accepted
            only so a future caller is not forced to change this signature.

    Returns:
        A :class:`Demo` whose parts a test can inspect.

    Raises:
        ValueError: ``transport_kwargs`` is non-empty. Accepting and ignoring
            unknown arguments would let a caller believe they had configured
            something when they had not.
    """
    if transport_kwargs:
        raise ValueError(
            f"unexpected transport argument(s): {', '.join(sorted(transport_kwargs))}"
        )

    scripted = (
        list(responses) if responses is not None else [openai_response(text="ok")]
    )

    registry = build_registry()
    transport = ScriptedTransport(scripted)
    provider = OpenAIProvider()
    return Demo(
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
        agent=Agent(model=MODEL, system="You are a demonstration agent."),
    )
