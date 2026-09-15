"""Google Gemini GenerateContent adapter.

Wire facts this adapter encodes, verified against Google's REST reference and the
official SDK type definitions:

* Roles are ``user`` and ``model`` -- not ``assistant``.
* Completion text lives in ``candidates[0].content.parts[]``.
* The system prompt is a top-level ``systemInstruction`` object.
* Generation parameters are nested under ``generationConfig``.
* Errors use the **Google Cloud** shape -- ``{"error": {"code", "message",
  "status", "details"}}`` with a *string* status such as ``RESOURCE_EXHAUSTED``
  -- not a flat ``type`` field.
* ``finishReason`` has 18+ values, far more than the other two providers, which
  is precisely why the neutral model keeps the raw value as well (D-6).
* Tool ``args`` is a parsed object, not a JSON string.
* The stream has **no** terminator sentinel: it simply ends.
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

NAME = "gemini"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Gemini's finish reasons, mapped onto the closed neutral set. Any value absent
# here becomes UNKNOWN with the raw string preserved, which is deliberate: this
# enum grows, and an unknown value must not be silently read as "stopped".
_FINISH_MAP = {
    "STOP": FinishReason.STOP,
    "MAX_TOKENS": FinishReason.LENGTH,
    "SAFETY": FinishReason.CONTENT_FILTER,
    "RECITATION": FinishReason.CONTENT_FILTER,
    "PROHIBITED_CONTENT": FinishReason.CONTENT_FILTER,
    "BLOCKLIST": FinishReason.CONTENT_FILTER,
    "SPII": FinishReason.CONTENT_FILTER,
    "IMAGE_SAFETY": FinishReason.CONTENT_FILTER,
    "LANGUAGE": FinishReason.CONTENT_FILTER,
    "MALFORMED_FUNCTION_CALL": FinishReason.ERROR,
    "UNEXPECTED_TOOL_CALL": FinishReason.ERROR,
    "TOO_MANY_TOOL_CALLS": FinishReason.ERROR,
    "OTHER": FinishReason.UNKNOWN,
}

# Google Cloud status strings, which carry the real meaning more reliably than
# the HTTP code in some paths.
_STATUS_MAP = {
    "RESOURCE_EXHAUSTED": "rate_limit",
    "UNAVAILABLE": "server",
    "DEADLINE_EXCEEDED": "timeout",
    "UNAUTHENTICATED": "auth",
    "PERMISSION_DENIED": "auth",
    "INVALID_ARGUMENT": "bad_request",
    "FAILED_PRECONDITION": "bad_request",
    "NOT_FOUND": "bad_request",
}


def _encode_parts(message: Message) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append({"text": block.text})
        elif isinstance(block, ToolCallBlock):
            parts.append(
                {
                    "functionCall": {
                        "name": block.name,
                        # Gemini takes a parsed object, like Anthropic.
                        "args": block.arguments,
                        "id": block.id,
                    }
                }
            )
        elif isinstance(block, ToolResultBlock):
            parts.append(
                {
                    "functionResponse": {
                        "name": "",
                        "response": {"output": block.content},
                        "id": block.tool_call_id,
                    }
                }
            )
    if not parts:
        # Gemini rejects an empty parts array; an empty text part is the
        # documented way to send a turn with no content.
        parts.append({"text": ""})
    return parts


class GeminiProvider:
    """Adapter for Google's Gemini GenerateContent API."""

    name = NAME

    def __init__(self, *, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    # ----------------------------------------------------------------- #
    # Request
    # ----------------------------------------------------------------- #

    def build_request(self, request: ChatRequest, *, api_key: str) -> WireRequest:
        if request.system_messages():
            raise TranslationError(
                "Gemini has no system role; pass the text as ChatRequest.system",
                provider=NAME,
                feature="message.role=system",
                remedy="pass the text as ChatRequest(system=...)",
            )

        contents: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role is Role.TOOL:
                # Function results are sent as a user turn in this API.
                contents.append({"role": "user", "parts": _encode_parts(message)})
                continue
            role = "model" if message.role is Role.ASSISTANT else "user"
            contents.append({"role": role, "parts": _encode_parts(message)})

        body: dict[str, Any] = {"contents": contents}

        generation: dict[str, Any] = {}
        if request.max_output_tokens is not None:
            generation["maxOutputTokens"] = request.max_output_tokens
        if request.temperature is not None:
            generation["temperature"] = request.temperature
        if generation:
            body["generationConfig"] = generation

        if request.system is not None:
            body["systemInstruction"] = {"parts": [{"text": request.system}]}

        if request.tools:
            body["tools"] = [
                {"functionDeclarations": [_tool_definition(t) for t in request.tools]}
            ]

        for key, value in request.extra.items():
            body.setdefault(key, value)

        # alt=sse is REQUIRED for streaming. Without it the response is a JSON
        # array, not an event stream.
        url = f"{self.base_url}/models/{request.model}"
        method = "streamGenerateContent" if request.stream else "generateContent"
        suffix = "?alt=sse" if request.stream else ""

        return WireRequest(
            method="POST",
            url=f"{url}:{method}{suffix}",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            body=json.dumps(body).encode("utf-8"),
        )

    # ----------------------------------------------------------------- #
    # Response
    # ----------------------------------------------------------------- #

    def parse_response(self, response: WireResponse) -> ChatResponse:
        if response.status_code >= 400:
            raise self.classify_error(_signals_from(response, model=""))

        payload = _decode(response.body, "response")

        # A prompt-level block produces no candidate at all.
        feedback = payload.get("promptFeedback") or {}
        if feedback.get("blockReason"):
            return ChatResponse.build(
                blocks=(),
                finish_reason=FinishReason.CONTENT_FILTER,
                raw_finish_reason=str(feedback.get("blockReason")),
                usage=_usage_from(payload.get("usageMetadata")),
                model=str(payload.get("modelVersion", "")),
                provider=NAME,
            )

        candidates = payload.get("candidates") or []
        if not candidates:
            raise ProviderError(
                "response contained no candidates",
                provider=NAME,
                status_code=response.status_code,
            )

        candidate = candidates[0]
        blocks = tuple(
            _blocks_from_parts((candidate.get("content") or {}).get("parts") or [])
        )
        finish = _finish_reason(candidate.get("finishReason"))

        return ChatResponse.build(
            blocks=blocks,
            finish_reason=finish[0],
            raw_finish_reason=finish[1],
            usage=_usage_from(payload.get("usageMetadata")),
            model=str(payload.get("modelVersion", "")),
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
        # Gemini sends no terminator; the transport's EOF ends the stream.
        if is_done or not data.strip():
            return None

        payload = _decode(data.encode("utf-8"), "stream chunk")

        candidates = payload.get("candidates") or []
        usage = _usage_from(payload.get("usageMetadata"))

        if not candidates:
            return UsageDelta(usage=usage) if usage is not None else None

        candidate = candidates[0]
        parts = (candidate.get("content") or {}).get("parts") or []

        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                return TextDelta(text=text)
            call = part.get("functionCall")
            if isinstance(call, dict):
                # Gemini sends complete function calls, not fragments, so the
                # whole argument object arrives as one fragment.
                return ToolCallDelta(
                    index=0,
                    id=str(call.get("id") or ""),
                    name=str(call.get("name") or ""),
                    arguments_fragment=json.dumps(call.get("args") or {}),
                )

        if candidate.get("finishReason"):
            reason, raw = _finish_reason(candidate["finishReason"])
            return FinishDelta(finish_reason=reason, raw_finish_reason=raw)

        return UsageDelta(usage=usage) if usage is not None else None

    # ----------------------------------------------------------------- #
    # Errors
    # ----------------------------------------------------------------- #

    def classify_error(self, signals: ErrorSignals) -> ProviderError:
        body = signals.body
        status_text = ""
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                status_text = str(error.get("status") or "")

        kind = _STATUS_MAP.get(status_text, "")

        if kind == "rate_limit" or signals.status_code == 429:
            return RateLimitError(
                _message_from(body) or "quota exhausted",
                provider=NAME,
                model=signals.model,
                status_code=signals.status_code,
                retry_after=signals.retry_after,
                # RESOURCE_EXHAUSTED may be a hard quota; without a retry hint
                # this is not safely retryable.
                retryable=signals.retry_after is not None,
            )

        if kind == "bad_request" and _looks_like_context(signals):
            return ContextLengthError(
                _message_from(body) or "input exceeds the model's context window",
                provider=NAME,
                model=signals.model,
                status_code=signals.status_code,
                retryable=False,
            )

        return classify_status(NAME, signals.model, signals)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _tool_definition(tool: Mapping[str, Any]) -> dict[str, Any]:
    """Gemini uses the same name/description/parameters keys, so this is close to
    a pass-through -- but it still copies rather than aliasing caller data."""
    return dict(tool)


def _looks_like_context(signals: ErrorSignals) -> bool:
    body = signals.body
    if not isinstance(body, dict):
        return False
    error = body.get("error")
    if not isinstance(error, dict):
        return False
    message = error.get("message")
    if not isinstance(message, str):
        return False
    lowered = message.lower()
    return "token" in lowered and ("exceed" in lowered or "too long" in lowered)


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


def _blocks_from_parts(parts: list[Any]) -> list[Any]:
    blocks: list[Any] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text:
            blocks.append(TextBlock(text=text))
        call = part.get("functionCall")
        if isinstance(call, dict):
            args = call.get("args")
            blocks.append(
                ToolCallBlock(
                    id=str(call.get("id") or ""),
                    name=str(call.get("name") or ""),
                    arguments=args if isinstance(args, dict) else {},
                )
            )
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
        input_tokens=_as_int(raw.get("promptTokenCount")),
        output_tokens=_as_int(raw.get("candidatesTokenCount")),
        total_tokens=_as_int(raw.get("totalTokenCount")),
        reasoning_tokens=_as_int(raw.get("thoughtsTokenCount")),
    )
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
