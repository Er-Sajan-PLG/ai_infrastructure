"""Anthropic Messages adapter.

Wire facts this adapter encodes, each verified against the Anthropic SDK source:

* **There is no ``system`` role.** The system prompt is a top-level ``system``
  parameter, so a neutral system message is a translation error, not something
  to silently move.
* Text lives in ``content[]`` as typed blocks; a response is flattened by
  concatenating ``text`` blocks.
* **Usage is split across two events**: ``message_start`` carries
  ``input_tokens`` and the final ``message_delta`` carries a *cumulative*
  ``output_tokens``. There is **no** ``total_tokens`` field at all.
* Usage counts are billing-oriented; the SDK documents that they "will not match
  one-to-one" with response content.
* The stream terminates on the ``message_stop`` event -- there is no
  ``[DONE]`` sentinel.
* **529 ``overloaded_error``** is a non-standard status that means "retry", and a
  spend-cap 429 carries no ``retry-after`` and can never succeed. Both are
  handled explicitly, because a naive 429/5xx rule gets the second one wrong and
  turns one error into a retry loop.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..errors import (
    ContextLengthError,
    ErrorSignals,
    ProviderError,
    RateLimitError,
    ServerError,
    TranslationError,
)
from ..provider import classify_status
from ..request import ChatRequest
from ..types import (
    ChatResponse,
    FinishDelta,
    FinishReason,
    Message,
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

NAME = "anthropic"
DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"

# Anthropic's non-standard overload signal. Not a standard HTTP status; a client
# that only special-cases 500/502/503 will treat it as an opaque server error.
OVERLOADED = 529

_FINISH_MAP = {
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "max_tokens": FinishReason.LENGTH,
    "tool_use": FinishReason.TOOL_USE,
    "refusal": FinishReason.CONTENT_FILTER,
}
# pause_turn is deliberately NOT mapped to STOP: the turn was paused, not
# finished, and mapping it to STOP would tell a caller the answer was complete.

# Models that reject non-default sampling parameters. Verified against the
# deprecation notice; used to declare an incompatibility rather than drop a
# setting the caller asked for.
_TEMPERATURE_REJECTING_PREFIXES = (
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-5",
)


def _is_temperature_rejecting(model: str) -> bool:
    lowered = model.lower()
    return any(lowered.startswith(p) for p in _TEMPERATURE_REJECTING_PREFIXES)


def _encode_content(message: Message) -> str | list[dict[str, Any]]:
    """Encode a message's blocks into Anthropic's content shape."""
    parts: list[dict[str, Any]] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append({"type": "text", "text": block.text})
        elif isinstance(block, ToolCallBlock):
            parts.append(
                {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    # Anthropic takes a parsed object, unlike OpenAI's string.
                    "input": block.arguments,
                }
            )
        elif isinstance(block, ToolResultBlock):
            parts.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.tool_call_id,
                    "content": block.content,
                }
            )

    if len(parts) == 1 and parts[0].get("type") == "text":
        return str(parts[0]["text"])
    return parts


class AnthropicProvider:
    """Adapter for Anthropic's Messages API."""

    name = NAME

    def __init__(self, *, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    # ----------------------------------------------------------------- #
    # Request
    # ----------------------------------------------------------------- #

    def build_request(self, request: ChatRequest, *, api_key: str) -> WireRequest:
        if request.system_messages():
            raise TranslationError(
                "Anthropic's Messages API has no system role; pass the text as "
                "ChatRequest.system",
                provider=NAME,
                feature="message.role=system",
                remedy="pass the text as ChatRequest(system=...)",
            )

        # max_tokens is REQUIRED by this API. Defaulting it silently would change
        # the caller's cost and truncation behaviour, so it is refused loudly.
        if request.max_output_tokens is None:
            raise TranslationError(
                "Anthropic requires max_output_tokens",
                provider=NAME,
                feature="max_output_tokens",
                remedy="set ChatRequest(max_output_tokens=...)",
            )

        if request.temperature is not None and _is_temperature_rejecting(request.model):
            raise TranslationError(
                f"model {request.model!r} rejects a custom temperature",
                provider=NAME,
                feature="temperature",
                remedy="omit temperature for this model",
            )

        messages = [
            {"role": m.role.value, "content": _encode_content(m)}
            for m in request.messages
        ]

        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
        }
        if request.system is not None:
            body["system"] = request.system
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.tools:
            body["tools"] = [_tool_definition(t) for t in request.tools]
        if request.stream:
            body["stream"] = True

        for key, value in request.extra.items():
            body.setdefault(key, value)

        return WireRequest(
            method="POST",
            url=f"{self.base_url}/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
            },
            body=json.dumps(body).encode("utf-8"),
        )

    # ----------------------------------------------------------------- #
    # Response
    # ----------------------------------------------------------------- #

    def parse_response(self, response: WireResponse) -> ChatResponse:
        if response.status_code >= 400:
            raise self.classify_error(_signals_from(response, model=""))

        payload = _decode(response.body, "response")
        blocks = tuple(_blocks_from_content(payload.get("content") or []))
        finish = _finish_reason(payload.get("stop_reason"))

        return ChatResponse.build(
            blocks=blocks,
            finish_reason=finish[0],
            raw_finish_reason=finish[1],
            usage=_usage_from(payload.get("usage")),
            model=str(payload.get("model", "")),
            provider=NAME,
        )

    # ----------------------------------------------------------------- #
    # Streaming
    # ----------------------------------------------------------------- #

    def parse_stream_line(
        self, *, event: str | None, data: str, is_done: bool
    ) -> StreamDelta | None:
        if is_done or not data.strip():
            return None

        payload = _decode(data.encode("utf-8"), "stream event")
        # The event name appears both as the SSE `event:` field and inside the
        # JSON payload; the payload is authoritative when present.
        kind = str(payload.get("type") or event or "")

        if kind == "content_block_delta":
            delta = payload.get("delta") or {}
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                text = delta.get("text")
                return TextDelta(text=text) if isinstance(text, str) and text else None
            if delta_type == "input_json_delta":
                partial = delta.get("partial_json")
                return ToolCallDelta(
                    index=int(payload.get("index", 0)),
                    arguments_fragment=partial if isinstance(partial, str) else "",
                )
            return None

        if kind == "content_block_start":
            # Carries the tool id and name; the arguments arrive as fragments.
            block = payload.get("content_block") or {}
            if block.get("type") == "tool_use":
                return ToolCallDelta(
                    index=int(payload.get("index", 0)),
                    id=str(block.get("id") or ""),
                    name=str(block.get("name") or ""),
                )
            return None

        if kind == "message_start":
            # Input tokens arrive here; output tokens are still unknown.
            message = payload.get("message") or {}
            usage = _usage_from(message.get("usage"))
            return UsageDelta(usage=usage) if usage is not None else None

        if kind == "message_delta":
            # The final one carries cumulative output tokens.
            usage = _usage_from(payload.get("usage"))
            stop = payload.get("delta", {}).get("stop_reason")
            if stop:
                reason, raw = _finish_reason(stop)
                return FinishDelta(finish_reason=reason, raw_finish_reason=raw)
            return UsageDelta(usage=usage) if usage is not None else None

        if kind == "message_stop":
            # No payload; the finish reason came on message_delta.
            return None

        if kind == "error":
            error = payload.get("error") or {}
            raise ProviderError(
                str(error.get("message") or "stream error")[:300],
                provider=NAME,
                model="",
                retryable=False,
            )

        # ping, content_block_stop and anything unknown carry no delta.
        return None

    # ----------------------------------------------------------------- #
    # Errors
    # ----------------------------------------------------------------- #

    def classify_error(self, signals: ErrorSignals) -> ProviderError:
        if signals.status_code == OVERLOADED:
            # Non-standard, and explicitly retryable.
            return ServerError(
                "provider overloaded",
                provider=NAME,
                model=signals.model,
                status_code=OVERLOADED,
                retryable=True,
                request_id=_request_id(signals.body),
            )

        if signals.status_code == 429:
            # A spend-cap 429 has no retry-after and will never succeed.
            # Retrying it produces an unbounded loop.
            retryable = signals.retry_after is not None
            return RateLimitError(
                "rate limited" if retryable else "spend cap reached",
                provider=NAME,
                model=signals.model,
                status_code=429,
                retry_after=signals.retry_after,
                retryable=retryable,
                request_id=_request_id(signals.body),
            )

        if signals.status_code == 400:
            body = signals.body
            error_type = ""
            if isinstance(body, dict):
                error = body.get("error")
                if isinstance(error, dict):
                    error_type = str(error.get("type") or "")
            if "too_long" in error_type or "context" in error_type:
                return ContextLengthError(
                    "input exceeds the model's context window",
                    provider=NAME,
                    model=signals.model,
                    status_code=400,
                    retryable=False,
                    request_id=_request_id(body),
                )

        classified = classify_status(NAME, signals.model, signals)
        if classified.request_id is None:
            classified.request_id = _request_id(signals.body)
        return classified


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _tool_definition(tool: Mapping[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI-shaped tool definition to Anthropic's shape.

    The neutral form is OpenAI-shaped (name/description/parameters); Anthropic
    wants ``input_schema`` instead of ``parameters``. Any other keys are passed
    through untouched rather than dropped, so an unrecognised field surfaces as
    a provider error instead of vanishing.
    """
    definition: dict[str, Any] = {}
    for key, value in tool.items():
        if key == "parameters":
            definition["input_schema"] = value
        else:
            definition[key] = value
    return definition


def _decode(raw: bytes, what: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError(
            f"could not decode {what} as JSON", provider=NAME, retryable=False
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderError(
            f"{what} was {type(payload).__name__}, expected object",
            provider=NAME,
            retryable=False,
        )
    return payload


def _blocks_from_content(content: list[Any]) -> list[Any]:
    blocks: list[Any] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        if kind == "text":
            text = part.get("text")
            if isinstance(text, str) and text:
                blocks.append(TextBlock(text=text))
        elif kind == "tool_use":
            arguments = part.get("input")
            blocks.append(
                ToolCallBlock(
                    id=str(part.get("id") or ""),
                    name=str(part.get("name") or ""),
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )
        # thinking / redacted_thinking are not represented in the neutral model
        # yet; they are skipped rather than mapped onto text, because mapping
        # reasoning into output text would corrupt the transcript.
    return blocks


def _finish_reason(raw: Any) -> tuple[FinishReason, str]:
    if raw is None:
        return FinishReason.UNKNOWN, ""
    text = str(raw)
    return _FINISH_MAP.get(text, FinishReason.UNKNOWN), text


def _usage_from(raw: Any) -> Usage | None:
    if not isinstance(raw, dict):
        return None
    usage = Usage(
        input_tokens=_as_int(raw.get("input_tokens")),
        output_tokens=_as_int(raw.get("output_tokens")),
        total_tokens=_as_int(raw.get("total_tokens")),
        cache_read_tokens=_as_int(raw.get("cache_read_input_tokens")),
        cache_write_tokens=_as_int(raw.get("cache_creation_input_tokens")),
    )
    # Anthropic has no total field, so it is derived when both parts are known.
    return usage.derive_total()


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _request_id(body: Any) -> str | None:
    if isinstance(body, dict):
        value = body.get("request_id")
        if isinstance(value, str) and value:
            return value
    return None


def _signals_from(response: WireResponse, model: str) -> ErrorSignals:
    body: Any
    try:
        body = json.loads(response.body.decode("utf-8")) if response.body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = None
    retry_after = None
    for key in ("retry-after", "Retry-After"):
        raw = response.headers.get(key)
        if raw:
            try:
                retry_after = float(raw)
            except ValueError:
                retry_after = None
            break
    return ErrorSignals(
        provider=NAME,
        model=model,
        status_code=response.status_code,
        body=body,
        retry_after=retry_after,
    )
