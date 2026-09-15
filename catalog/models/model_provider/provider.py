"""The provider adapter contract.

An adapter's only job is translation between neutral types and one provider's
wire format. It never opens a socket, never sleeps, never retries.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Protocol, runtime_checkable

from .errors import ErrorSignals, ProviderError
from .request import ChatRequest
from .types import ChatResponse, StreamDelta, WireRequest, WireResponse


@runtime_checkable
class Provider(Protocol):
    """Translates a neutral request into one provider's wire format and back."""

    @property
    def name(self) -> str:
        """The provider's identifier, e.g. ``"openai"``."""
        ...

    def build_request(self, request: ChatRequest, *, api_key: str) -> WireRequest:
        """Encode a request.

        Raises:
            TranslationError: When the neutral request uses a feature this
                provider cannot express. This is D-7 in action: the lossy case is
                declared up front rather than silently dropped or approximated.

        The API key is passed in rather than read from the environment: the
        abstraction has no business reading credentials, and a test should not
        need to fake an environment variable.
        """
        ...

    def parse_response(self, response: WireResponse) -> ChatResponse:
        """Decode a non-streaming response.

        Raises:
            ProviderError: Classified via :meth:`classify_error` for non-2xx, or
                when a 2xx body cannot be understood.
        """
        ...

    def parse_stream_line(
        self, *, event: str | None, data: str, is_done: bool
    ) -> StreamDelta | None:
        """Decode one SSE event into zero or one delta.

        Returning ``None`` means "this event carries no delta" (a ``ping``, a
        ``message_start``) -- it does **not** mean end of stream. Termination is
        signalled by :class:`~model_provider.types.FinishDelta` or by the
        transport's EOF.
        """
        ...

    def classify_error(self, signals: ErrorSignals) -> ProviderError:
        """Map a failure onto the neutral taxonomy using structured signal only.

        Implementations must not consult message text (D-4).
        """
        ...


@runtime_checkable
class StreamableProvider(Provider, Protocol):
    """A provider whose streaming responses can carry usage."""

    def stream_end_usage(self) -> bool:
        """Whether usage arrives during streaming at all.

        False for providers where usage is unavailable unless opted in, so a
        caller can decide whether to request it. Documented rather than guessed.
        """
        ...


def classify_status(provider: str, model: str, signals: ErrorSignals) -> ProviderError:
    """Shared structural classification, used by adapters as a baseline.

    Providers subclass this with their own rules (Anthropic's 529, Gemini's
    string status codes). Kept here so the common cases cannot drift apart
    between three adapters.
    """
    from .errors import (
        AuthenticationError,
        BadRequestError,
        ProviderTimeoutError,
        RateLimitError,
        ServerError,
        TransportError,
    )

    if signals.timed_out:
        return ProviderTimeoutError(
            "request timed out", provider=provider, model=model, retryable=True
        )
    if signals.transport_failed:
        return TransportError(
            "connection failed", provider=provider, model=model, retryable=True
        )

    status = signals.status_code
    message = _extract_message(signals.body)
    common: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "status_code": status,
        "retry_after": signals.retry_after,
        "request_id": _extract_request_id(signals.body),
    }

    if status is None:
        return ProviderError(message or "unclassified failure", **common)
    if status == 401 or status == 403:
        return AuthenticationError(message or "credentials rejected", **common)
    if status == 429:
        # A 429 with no retry hint may be a spend cap, which can never succeed.
        # Adapters that know better override; the baseline is conservative.
        return RateLimitError(message or "rate limited", **common)
    if status == 408:
        return ProviderTimeoutError(message or "request timeout", **common)
    if status >= 500:
        return ServerError(message or "provider error", **common)
    if status >= 400:
        return BadRequestError(message or "bad request", **common)
    return ProviderError(message or f"unexpected status {status}", **common)


def _extract_message(body: Any) -> str:
    """Pull a short message out of a provider error body, without dumping it.

    Deliberately narrow: only known message fields are read, and the result is
    truncated. A raw body can echo request content, so it never reaches a
    message that might be placed in a prompt.
    """
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, dict):
        for key in ("message", "detail"):
            value = error.get(key)
            if isinstance(value, str) and value:
                return value[:300]
    if isinstance(error, str) and error:
        return error[:300]
    return ""


def _extract_request_id(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in ("request_id", "requestId"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def collect_stream(
    deltas: Iterator[StreamDelta],
    *,
    provider: str,
    model: str,
    on_error: Callable[[str, str], ProviderError] | None = None,
) -> ChatResponse:
    """Fold a delta stream into a complete response.

    Useful when a caller wants streaming semantics (fail-fast, incremental
    progress) but also the final assembled result. Tool-call arguments are
    reassembled, because fragments are not parseable individually.
    """
    from .stream import ToolCallAccumulator
    from .types import (
        ChatResponse as _ChatResponse,
    )
    from .types import (
        FinishDelta,
        FinishReason,
        TextBlock,
        TextDelta,
        ToolCallBlock,
        ToolCallDelta,
        Usage,
        UsageDelta,
    )

    accumulator = ToolCallAccumulator()
    chunks: list[str] = []
    usage: Usage | None = None
    finish = FinishReason.UNKNOWN
    raw_finish = ""

    for delta in deltas:
        if isinstance(delta, TextDelta):
            chunks.append(delta.text)
        elif isinstance(delta, ToolCallDelta):
            accumulator.add(delta)
        elif isinstance(delta, UsageDelta):
            usage = delta.usage
        elif isinstance(delta, FinishDelta):
            finish = delta.finish_reason
            raw_finish = delta.raw_finish_reason

    blocks: list[Any] = []
    text = "".join(chunks)
    if text:
        blocks.append(TextBlock(text=text))
    # AccumulatedToolCall is the accumulator's own record; the neutral model
    # needs ToolCallBlock. Passing the former would produce a response whose
    # `tool_calls` is silently empty, because ChatResponse.build filters on the
    # neutral type.
    for call in accumulator.finish(on_parse_error=on_error):
        blocks.append(
            ToolCallBlock(id=call.id, name=call.name, arguments=call.arguments)
        )

    return _ChatResponse.build(
        blocks=tuple(blocks),
        finish_reason=finish,
        raw_finish_reason=raw_finish,
        usage=usage.derive_total() if usage is not None else None,
        model=model,
        provider=provider,
    )
