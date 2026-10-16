"""Optional binding to model-provider-abstraction (ADR-0034 D-5).

This is the only module in the entry that imports ``model_provider``.
Everything else runs against the ``Generator`` protocol, which is what lets
the test suite drive every path with a scripted double -- no network, no
model, no API key.

The adapter is small. That is the whole cost of the seam, and it mirrors
``react_agent_loop.adapters.ProviderCaller`` for the same reason: owning the
call shape here keeps provider wire formats out of the capability.
"""

from __future__ import annotations

from model_provider import (
    ChatRequest,
    Message,
    Provider,
    Role,
    TextBlock,
    Transport,
    chat,
)

from .rag_pipeline import Generator

__all__ = ["ProviderGenerator"]


class ProviderGenerator(Generator):
    """Adapts a provider plus transport to the ``Generator`` protocol.

    Holds the model settings because the protocol's call receives only the
    prompt: the pipeline is not a place to configure a provider. Synchronous
    and non-streaming, matching model-provider-abstraction and D-8.
    """

    def __init__(
        self,
        *,
        provider: Provider,
        transport: Transport,
        api_key: str,
        model: str,
        system: str | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        """Bind a provider, transport and model settings.

        Args:
            provider: The adapter translating to a provider wire format.
            transport: Performs HTTP; not called by this class directly.
            api_key: Sent to the transport by ``model_provider.chat``.
            model: Provider-specific model name.
            system: Optional system prompt. ``None`` sends none -- a pipeline
                does not silently inject persona.
            max_output_tokens: Optional cap on generated tokens.
            temperature: Optional sampling temperature.
        """
        self._provider = provider
        self._transport = transport
        self._api_key = api_key
        self._model = model
        self._system = system
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def generate(self, prompt: str) -> str:
        """Encode and send one non-streaming chat request; return its text."""
        request = ChatRequest(
            model=self._model,
            messages=(Message(Role.USER, (TextBlock(prompt),)),),
            system=self._system,
            max_output_tokens=self._max_output_tokens,
            temperature=self._temperature,
        )
        response = chat(
            request,
            provider=self._provider,
            transport=self._transport,
            api_key=self._api_key,
        )
        return response.text
