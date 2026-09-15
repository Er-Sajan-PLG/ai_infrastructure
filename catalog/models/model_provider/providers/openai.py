"""OpenAI Chat Completions adapter.

Wire facts this adapter encodes, each verified against OpenAI's published
OpenAPI specification:

* Completion text lives at ``choices[0].message.content``; tool calls at
  ``choices[0].message.tool_calls[]``.
* Tool-call ``arguments`` is ``type: string`` -- "A JSON string of the arguments"
  -- and is fragmented across stream chunks, so it must be reassembled before it
  can be parsed.
* Streaming usage is **opt-in**: without
  ``stream_options: {"include_usage": true}`` the stream carries no usage at all,
  and with it, usage arrives on an extra final chunk whose ``choices`` array is
  **empty**. A parser that assumes ``choices[0]`` exists will crash on exactly
  the chunk that carries the numbers.
* The stream terminates with a literal ``data: [DONE]`` sentinel, which is not
  JSON.
"""

from __future__ import annotations

import json
from typing import Any

from ..errors import (
    ContextLengthError,
    ErrorSignals,
    ProviderError,
    RateLimitError,
    TranslationError,
)
from ..provider import classify_status
from ..request import ChatRequest
from ..types import (
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

NAME = "openai"
DEFAULT_BASE_URL = "https://api.openai.com/v1"

# Markers that identify a context-length failure. Checked against the error
# *code* field rather than the message where possible.
_CONTEXT_MARKERS = ("context_length_exceeded", "max_tokens", "too many tokens")

_FINISH_MAP = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "tool_calls": FinishReason.TOOL_USE,
    "function_call": FinishReason.TOOL_USE,
    "content_filter": FinishReason.CONTENT_FILTER,
}


def _encode_message(message: Message) -> dict[str, Any]:
    role = message.role.value
    blocks = message.content

    # OpenAI carries assistant tool calls on the message, and tool results as
    # their own role with a tool_call_id.
    if message.role is Role.TOOL:
        results = [b for b in blocks if isinstance(b, ToolResultBlock)]
        if len(results) == 1:
            result = results[0]
            return {
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "content": result.content,
            }

    calls = [b for b in blocks if isinstance(b, ToolCallBlock)]
    if calls:
        return {
            "role": role,
            "content": message.text() or None,
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {
                        "name": c.name,
                        # OpenAI wants arguments as a JSON *string*.
                        "arguments": json.dumps(c.arguments),
                    },
                }
                for c in calls
            ],
        }

    return {"role": role, "content": message.text()}


class OpenAIProvider:
    """Adapter for OpenAI's Chat Completions API."""

    name = NAME

    def __init__(self, *, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    # ----------------------------------------------------------------- #
    # Request
    # ----------------------------------------------------------------- #

    def build_request(self, request: ChatRequest, *, api_key: str) -> WireRequest:
        if request.system_messages():
            raise TranslationError(
                "system prompt must use ChatRequest.system, not a message with "
                "role=system",
                provider=NAME,
                feature="message.role=system",
                remedy="pass the text as ChatRequest(system=...)",
            )

        messages: list[dict[str, Any]] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        messages.extend(_encode_message(m) for m in request.messages)

        body: dict[str, Any] = {"model": request.model, "messages": messages}
        if request.max_output_tokens is not None:
            body["max_completion_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.tools:
            body["tools"] = [
                {"type": "function", "function": dict(t)} for t in request.tools
            ]
        if request.stream:
            body["stream"] = True
            # Without this the stream carries NO usage. Asking for it is the only
            # way to know what a streamed call cost.
            body["stream_options"] = {"include_usage": True}

        # Caller extras last would let them overwrite model/messages, so the
        # adapter's own fields win and extras fill the gaps.
        for key, value in request.extra.items():
            body.setdefault(key, value)

        return WireRequest(
            method="POST",
            url=f"{self.base_url}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
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
        model = str(payload.get("model", ""))
        choices = payload.get("choices") or []
        if not choices:
            raise ProviderError(
                "response contained no choices",
                provider=NAME,
                model=model,
                status_code=response.status_code,
            )

        choice = choices[0]
        message = choice.get("message") or {}
        blocks = _blocks_from_message(message)
        finish = _finish_reason(choice.get("finish_reason"))
        usage = _usage_from(payload.get("usage"))

        return ChatResponse.build(
            blocks=blocks,
            finish_reason=finish[0],
            raw_finish_reason=finish[1],
            usage=usage,
            model=model,
            provider=NAME,
        )

    # ----------------------------------------------------------------- #
    # Streaming
    # ----------------------------------------------------------------- #

    def parse_stream_line(
        # `event` is part of the Provider protocol contract even though this
        # provider does not name its SSE events.
        self,
        *,
        event: str | None,  # noqa: ARG002 -- required by the protocol
        data: str,
        is_done: bool,
    ) -> StreamDelta | None:
        if is_done:
            # The sentinel is not JSON and carries no payload; the real terminal
            # signal is the finish_reason on the preceding chunk.
            return None
        if not data.strip():
            return None

        payload = _decode(data.encode("utf-8"), "stream chunk")
        choices = payload.get("choices") or []

        if not choices:
            # The usage chunk: an empty choices array. This is exactly where
            # OpenAI puts the token counts when include_usage is set.
            usage = _usage_from(payload.get("usage"))
            return UsageDelta(usage=usage) if usage is not None else None

        choice = choices[0]
        delta = choice.get("delta") or {}

        # A finish_reason can accompany content, so check content first and let
        # the next call surface the finish. Only one delta per event, matching
        # the Provider protocol.
        content = delta.get("content")
        if isinstance(content, str) and content:
            return TextDelta(text=content)

        tool_calls = delta.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            call = tool_calls[0]
            function = call.get("function") or {}
            return ToolCallDelta(
                index=int(call.get("index", 0)),
                id=call.get("id"),
                name=function.get("name"),
                arguments_fragment=function.get("arguments") or "",
            )

        if choice.get("finish_reason"):
            reason, raw = _finish_reason(choice["finish_reason"])
            return FinishDelta(finish_reason=reason, raw_finish_reason=raw)

        return None

    # ----------------------------------------------------------------- #
    # Errors
    # ----------------------------------------------------------------- #

    def classify_error(self, signals: ErrorSignals) -> ProviderError:
        body = signals.body
        code = ""
        status_text = ""
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                code = str(error.get("code") or "")
                status_text = str(error.get("type") or "")

        if signals.status_code == 429:
            # A spend-cap 429 carries no retry-after and can never succeed;
            # retrying it turns one error into a loop.
            retryable = signals.retry_after is not None
            return RateLimitError(
                _message_from(body) or "rate limited",
                provider=NAME,
                model=signals.model,
                status_code=429,
                retry_after=signals.retry_after,
                retryable=retryable,
            )

        if signals.status_code == 400:
            haystack = f"{code} {status_text}".lower()
            if any(marker in haystack for marker in _CONTEXT_MARKERS):
                return ContextLengthError(
                    _message_from(body) or "context length exceeded",
                    provider=NAME,
                    model=signals.model,
                    status_code=400,
                    retryable=False,
                )

        return classify_status(NAME, signals.model, signals)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


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


def _blocks_from_message(message: dict[str, Any]) -> tuple[Any, ...]:
    blocks: list[Any] = []
    content = message.get("content")
    if isinstance(content, str) and content:
        blocks.append(TextBlock(text=content))

    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        raw_args = function.get("arguments") or ""
        blocks.append(
            ToolCallBlock(
                id=str(call.get("id") or ""),
                name=str(function.get("name") or ""),
                arguments=_parse_arguments(raw_args),
            )
        )
    return tuple(blocks)


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Parse tool arguments, which OpenAI sends as a JSON string.

    A malformed string yields ``{}`` **and** is deliberately not an error here:
    the failure surfaces downstream as a validation failure against the tool's
    own schema, which produces a better message than this layer could.
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _finish_reason(raw: Any) -> tuple[FinishReason, str]:
    if raw is None:
        return FinishReason.UNKNOWN, ""
    text = str(raw)
    return _FINISH_MAP.get(text, FinishReason.UNKNOWN), text


def _usage_from(raw: Any) -> Usage | None:
    if not isinstance(raw, dict):
        return None
    details = raw.get("completion_tokens_details")
    reasoning = None
    if isinstance(details, dict):
        value = details.get("reasoning_tokens")
        reasoning = value if isinstance(value, int) else None

    prompt_details = raw.get("prompt_tokens_details")
    cached = None
    if isinstance(prompt_details, dict):
        value = prompt_details.get("cached_tokens")
        cached = value if isinstance(value, int) else None

    usage = Usage(
        input_tokens=_as_int(raw.get("prompt_tokens")),
        output_tokens=_as_int(raw.get("completion_tokens")),
        total_tokens=_as_int(raw.get("total_tokens")),
        reasoning_tokens=reasoning,
        cache_read_tokens=cached,
    )
    # OpenAI omits the total in some streaming payloads; deriving it here is
    # safe because both parts are present.
    return usage.derive_total()


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _message_from(body: Any) -> str:
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message[:300]
    return ""


def _signals_from(response: WireResponse, model: str) -> ErrorSignals:
    body: Any
    try:
        body = json.loads(response.body.decode("utf-8")) if response.body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = None
    retry_after = None
    raw_retry = response.headers.get("retry-after") or response.headers.get(
        "Retry-After"
    )
    if raw_retry:
        try:
            retry_after = float(raw_retry)
        except ValueError:
            retry_after = None
    return ErrorSignals(
        provider=NAME,
        model=model,
        status_code=response.status_code,
        body=body,
        retry_after=retry_after,
    )
