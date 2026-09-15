"""Model provider abstraction -- a vendor-neutral chat interface.

Owns the *shape* of a model interaction (messages, responses, usage, finish
reasons, errors, stream deltas) and delegates the *socket* to an injected
transport. Zero runtime dependencies (ADR-0007).

    from model_provider import ChatRequest, Message, Role, TextBlock, OpenAIProvider
    from model_provider.transport import RecordingTransport

    provider = OpenAIProvider()
    transport = RecordingTransport(response=...)
    response = chat(
        ChatRequest(model="gpt-4o-mini", messages=[Message(Role.USER, (TextBlock("hi"),))]),
        provider=provider,
        transport=transport,
        api_key="...",
    )
"""

from __future__ import annotations

from collections.abc import Iterator

from .errors import (
    AuthenticationError,
    BadRequestError,
    ContentPolicyError,
    ContextLengthError,
    ErrorKind,
    ErrorSignals,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    ServerError,
    TranslationError,
    TransportError,
)
from .provider import Provider, collect_stream
from .request import ChatRequest
from .stream import (
    AccumulatedToolCall,
    ProviderStream,
    SSEEvent,
    ToolCallAccumulator,
    iter_sse_events,
)
from .transport import RecordingTransport, Transport
from .types import (
    Block,
    ChatResponse,
    FinishDelta,
    FinishReason,
    Message,
    Role,
    StreamDelta,
    TextBlock,
    TextDelta,
    ToolCallBlock,
    ToolCallDelta,
    ToolResultBlock,
    Usage,
    UsageDelta,
    WireRequest,
    WireResponse,
)

__all__ = [
    "AccumulatedToolCall",
    "AuthenticationError",
    "BadRequestError",
    "Block",
    "ChatRequest",
    "ChatResponse",
    "ContentPolicyError",
    "ContextLengthError",
    "ErrorKind",
    "ErrorSignals",
    "FinishDelta",
    "FinishReason",
    "Message",
    "Provider",
    "ProviderError",
    "ProviderStream",
    "ProviderTimeoutError",
    "RateLimitError",
    "RecordingTransport",
    "Role",
    "SSEEvent",
    "ServerError",
    "StreamDelta",
    "TextBlock",
    "TextDelta",
    "ToolCallAccumulator",
    "ToolCallBlock",
    "ToolCallDelta",
    "ToolResultBlock",
    "TranslationError",
    "Transport",
    "TransportError",
    "Usage",
    "UsageDelta",
    "WireRequest",
    "WireResponse",
    "chat",
    "collect_stream",
    "iter_sse_events",
    "stream",
]


def chat(
    request: ChatRequest,
    *,
    provider: Provider,
    transport: Transport,
    api_key: str,
) -> ChatResponse:
    """Make one non-streaming call.

    Raises:
        TranslationError: The request cannot be expressed on this provider (D-7).
        ProviderError: Any provider failure, classified. Subclasses carry the
            actionable distinction; ``retryable`` carries the caller's decision.
    """
    wire = provider.build_request(request, api_key=api_key)
    response = transport.send(wire)
    return provider.parse_response(response)


def stream(
    request: ChatRequest,
    *,
    provider: Provider,
    transport: Transport,
    api_key: str,
) -> Iterator[StreamDelta]:
    """Make one streaming call, yielding neutral deltas.

    The returned iterator **may raise mid-iteration** with a ``ProviderError``
    (ADR-0007 D-9), because both OpenAI and Anthropic can fail after a 200. A
    caller therefore needs one handler for pre- and post-first-chunk failures.

    Tool-call argument fragments are yielded as fragments; use
    :class:`ToolCallAccumulator` (or ``collect_stream``) to reassemble them,
    because a partial JSON string is not parseable.
    """
    streaming_request = (
        request
        if request.stream
        else ChatRequest(
            model=request.model,
            messages=request.messages,
            system=request.system,
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
            tools=request.tools,
            stream=True,
            extra=request.extra,
        )
    )
    wire = provider.build_request(streaming_request, api_key=api_key)
    lines = transport.stream(wire)

    def _deltas() -> Iterator[StreamDelta]:
        for event in iter_sse_events(lines):
            delta = provider.parse_stream_line(
                event=event.event, data=event.data, is_done=event.is_done
            )
            if delta is not None:
                yield delta

    return ProviderStream(_deltas(), provider=provider.name, model=request.model)
