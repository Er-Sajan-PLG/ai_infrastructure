"""The neutral chat request."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .types import Message, Role


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """A provider-independent chat request.

    Attributes:
        model: The model name to request. Provider-specific spelling; the caller
            knows which provider it selected.
        messages: The conversation. Must not contain :attr:`Role.SYSTEM` messages
            -- use ``system`` instead, which adapters translate per provider.
        system: The system prompt. A **separate field** because providers differ
            fundamentally: OpenAI wants a ``system`` role message, Anthropic
            wants a top-level parameter and has no system role at all, and Gemini
            wants a ``systemInstruction`` object.
        max_output_tokens: Cap on generated tokens.
        temperature: Sampling temperature. Not portable: some Anthropic models
            reject non-default values, which adapters declare rather than drop.
        tools: Tool definitions as opaque JSON Schema mappings (D-8). This
            module does not validate them and does not depend on
            ``tool-registry``; a caller composes the two if it wants validation.
        stream: Whether the caller intends to stream. Adapters use this to select
            the streaming wire format.
        extra: Provider-specific escape hatch, merged into the request body
            **after** adapter fields, so callers cannot accidentally overwrite
            the model or messages. Explicitly unvalidated.
    """

    model: str
    messages: Sequence[Message]
    system: str | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    tools: Sequence[Mapping[str, Any]] = ()
    stream: bool = False
    extra: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        # Normalise sequences to tuples so the request is genuinely immutable and
        # safe to share; a caller passing a list would otherwise retain a handle
        # to mutate it after construction.
        object.__setattr__(self, "messages", tuple(self.messages))
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "extra", MappingProxyType(dict(self.extra)))

    def system_messages(self) -> tuple[Message, ...]:
        """Return any system-role messages in ``messages``.

        Adapters call this to raise :class:`~model_provider.errors.TranslationError`
        rather than silently dropping or reordering a system prompt the caller
        put in the wrong place.
        """
        return tuple(m for m in self.messages if m.role is Role.SYSTEM)
