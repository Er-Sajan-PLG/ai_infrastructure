"""The two seams the loop depends on (ADR-0008 D-1).

The loop imports neither capability's behaviour. It defines these protocols and
ships optional adapters, so it can be driven entirely by scripted doubles -- which
is what makes every failure path reachable with no network, no model and no
registry (charter section 31).

It does consume model-provider-abstraction's neutral types (Message,
ToolCallBlock, ChatResponse). That coupling is deliberate and narrow: a loop with
its own parallel message type would force every adapter to convert, which is
exactly the cost LangChain and LlamaIndex pay. The dependency is in the signature
rather than the import graph.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from model_provider import ChatResponse, Message, ToolCallBlock

__all__ = ["DispatchOutcome", "ModelCaller", "ToolDispatcher"]


@runtime_checkable
class ModelCaller(Protocol):
    """Makes one model call. Owns credentials, transport and provider choice."""

    def call(
        self,
        messages: Sequence[Message],
        *,
        system: str | None,
        tools: Sequence[Mapping[str, Any]],
    ) -> ChatResponse:
        """Return the model's response to the conversation.

        Args:
            messages: The conversation so far, in neutral types.
            system: The caller's system prompt, passed through untouched. The
                loop never constructs one (D-7); it only forwards it, which is
                why it appears here rather than inside messages.
            tools: Tool definitions to advertise. Empty means advertise nothing.

        Raises:
            ProviderError: Any provider failure. It propagates out of the loop
                unchanged: a loop that swallowed a provider outage and reported
                "finished" would be lying.
        """
        ...


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    """What a dispatcher did with one tool call.

    Attributes:
        ok: Whether the tool produced a value.
        text: The observation text, already sanitised by the adapter. The loop
            still bounds it, because a caller-written adapter must not be able to
            bypass D-6.
        model_visible: Whether the failure may be shown to a model. Consulted only
            when ok is False. False raises out of the loop (D-9): a failure the
            model cannot act on is a caller or harness bug, and feeding it back
            invites another hallucination of the same name.
        kind: A short machine-readable label for the trace, e.g.
            "execution_failed". Never shown to the model.
        tool_id: The tool that was called, for the trace and the raised error.
    """

    ok: bool
    text: str | None
    model_visible: bool
    kind: str
    tool_id: str


@runtime_checkable
class ToolDispatcher(Protocol):
    """Turns a model's tool call into a result. Owns the registry."""

    def schemas(self) -> Sequence[Mapping[str, Any]]:
        """Tool definitions to advertise to the model.

        The loop does not invent these and does not edit them; it passes them
        through, in the neutral OpenAI-shaped form (name, description, parameters)
        that every provider adapter accepts.
        """
        ...

    def dispatch(self, call: ToolCallBlock) -> DispatchOutcome:
        """Invoke one tool call and describe the outcome.

        Must not raise for a tool failure; that is what DispatchOutcome is for.
        May raise for a broken registry, which propagates.
        """
        ...
