#!/usr/bin/env python3
"""A runnable tour of the provider abstraction -- three providers, no network.

Every call below goes through a canned transport, so this program makes no
network requests, needs no API key, and costs nothing. That is the point of the
transport seam: provider quirks are exercised deterministically.

Run::

    python catalog/models/model_provider/examples/quickstart.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from model_provider import (
    ChatRequest,
    Message,
    Role,
    TextBlock,
    TranslationError,
    WireResponse,
    collect_stream,
    stream,
)
from model_provider.providers import (
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
)
from model_provider.transport import RecordingTransport

ASK = "What is the capital of France?"


def wire(status: int, payload: object) -> WireResponse:
    return WireResponse(status_code=status, body=json.dumps(payload).encode())


def user(text: str) -> Message:
    return Message(Role.USER, (TextBlock(text),))


def main() -> None:
    print("=" * 72)
    print("1. ONE REQUEST SHAPE -> THREE DIFFERENT WIRE FORMATS")
    print("=" * 72)

    request = ChatRequest(model="demo", messages=[user(ASK)], system="Be brief.")
    for label, provider in (
        ("OpenAI", OpenAIProvider()),
        ("Anthropic", AnthropicProvider()),
        ("Gemini", GeminiProvider()),
    ):
        # Anthropic requires max_output_tokens and has no system role.
        adapted = ChatRequest(
            model="demo",
            messages=[user(ASK)],
            system="Be brief.",
            max_output_tokens=64,
        )
        # OpenAI wants a system message; the others want their own shapes.
        try:
            built = provider.build_request(request, api_key="DEMO")
        except TranslationError as exc:
            built = provider.build_request(adapted, api_key="DEMO")
            print(f"\n{label}: declared incompatibility, then adapted")
            print(f"  {exc}")
        else:
            print(f"\n{label}: encoded directly")

        body = json.loads(built.body)
        print(f"  url     : {built.url}")
        print(f"  system  : {_system_shape(body)}")

    print()
    print("=" * 72)
    print("2. THREE RESPONSE SHAPES -> ONE NEUTRAL TYPE")
    print("=" * 72)

    # Each provider puts the completion text somewhere different.
    payloads: dict[str, tuple[Any, Any]] = {
        "OpenAI": (
            OpenAIProvider(),
            {
                "model": "m",
                "choices": [{"message": {"content": "Paris"}, "finish_reason": "stop"}],
            },
        ),
        "Anthropic": (
            AnthropicProvider(),
            {
                "model": "m",
                "content": [{"type": "text", "text": "Paris"}],
                "stop_reason": "end_turn",
            },
        ),
        "Gemini": (
            GeminiProvider(),
            {
                "modelVersion": "m",
                "candidates": [
                    {"content": {"parts": [{"text": "Paris"}]}, "finishReason": "STOP"}
                ],
            },
        ),
    }

    for label, (provider, payload) in payloads.items():
        response = provider.parse_response(wire(200, payload))
        print(
            f"  {label:<10} text={response.text!r:<10} finish={response.finish_reason.value}"
        )

    print("\n  All three produced the same neutral ChatResponse.")

    print()
    print("=" * 72)
    print("3. STREAMING: FRAGMENTED TOOL ARGUMENTS ARE REASSEMBLED")
    print("=" * 72)

    # OpenAI sends tool arguments as a JSON *string*, split across chunks.
    lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
        '"function":{"name":"read_file","arguments":"{\\"pa"}}]}}]}',
        "",
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        '"function":{"arguments":"th\\": \\"notes"}}]}}]}',
        "",
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        '"function":{"arguments":".txt\\"}"}}]}}]}',
        "",
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        "",
        "data: [DONE]",
        "",
    ]
    transport = RecordingTransport(lines=tuple(lines))
    assembled = collect_stream(
        stream(
            ChatRequest(model="m", messages=[user(ASK)]),
            provider=OpenAIProvider(),
            transport=transport,
            api_key="DEMO",
        ),
        provider="openai",
        model="m",
    )
    print("  wire fragments (each individually unparseable):")
    for line in lines:
        if "arguments" in line:
            print(f"    {_arguments_of(line)}")
    print(
        f"\n  reassembled -> {assembled.tool_calls[0].name}({assembled.tool_calls[0].arguments})"
    )
    print(f"  finish      -> {assembled.finish_reason.value}")
    assert assembled.tool_calls[0].arguments == {"path": "notes.txt"}

    print()
    print("=" * 72)
    print("4. USAGE: THREE ACCESS STRATEGIES, AND THE ABSENT CASE")
    print("=" * 72)

    openai_usage = OpenAIProvider().parse_response(
        wire(
            200,
            {
                "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            },
        )
    )
    print(f"  OpenAI    total={openai_usage.usage.total_tokens}")  # type: ignore[union-attr]

    anthropic_usage = AnthropicProvider().parse_response(
        wire(
            200,
            {
                "content": [{"type": "text", "text": "x"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 4},  # no total field
            },
        )
    )
    print(
        f"  Anthropic total={anthropic_usage.usage.total_tokens} "  # type: ignore[union-attr]
        f"(derived from {anthropic_usage.usage.input_tokens}+"  # type: ignore[union-attr]
        f"{anthropic_usage.usage.output_tokens})"  # type: ignore[union-attr]
    )

    streamed = OpenAIProvider().parse_stream_line(
        event=None,
        data='{"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}',
        is_done=False,
    )
    print(f"  Streamed  arrives on a chunk with EMPTY choices: total={streamed.usage.total_tokens}")  # type: ignore[union-attr]

    absent = OpenAIProvider().parse_response(
        wire(
            200, {"choices": [{"message": {"content": "x"}, "finish_reason": "length"}]}
        )
    )
    print(f"  Absent    usage={absent.usage}  <- None, not a zero that looks measured")

    print()
    print("=" * 72)
    print("5. FAILURES ARE CLASSIFIED STRUCTURALLY, NOT BY MESSAGE TEXT")
    print("=" * 72)

    cases: list[tuple[str, Any, int, dict[str, Any], float | None]] = [
        (
            "Anthropic 529 (non-standard overload)",
            AnthropicProvider(),
            529,
            {"type": "error", "error": {"type": "overloaded_error"}},
            None,
        ),
        (
            "Anthropic 429 spend cap (no retry-after)",
            AnthropicProvider(),
            429,
            {"type": "error", "error": {"type": "rate_limit_error"}},
            None,
        ),
        (
            "OpenAI 429 with retry-after",
            OpenAIProvider(),
            429,
            {"error": {"message": "slow down"}},
            2.0,
        ),
        (
            "OpenAI 400 context length (by code)",
            OpenAIProvider(),
            400,
            {"error": {"message": "nope", "code": "context_length_exceeded"}},
            None,
        ),
    ]

    from model_provider import ErrorSignals

    for label, provider, status, body, retry_after in cases:
        error = provider.classify_error(
            ErrorSignals(
                provider=provider.name,
                model="m",
                status_code=status,
                body=body,
                retry_after=retry_after,
            )
        )
        verdict = "RETRY  " if error.retryable else "DO NOT "
        print(f"  {verdict} {label}")
        print(f"           -> {type(error).__name__}: {error.retry_hint}")

    print()
    print("  Note the 429 pair: same status, opposite verdicts, decided by")
    print("  whether the provider offered a retry delay -- never by its wording.")

    print()
    print("=" * 72)
    print("6. A STREAM CAN FAIL AFTER ALREADY YIELDING TOKENS")
    print("=" * 72)

    from model_provider import ProviderError

    partial = RecordingTransport(
        lines=('data: {"choices":[{"delta":{"content":"The answer "}}]}', ""),
        stream_error=ProviderError("connection dropped", provider="openai"),
        stream_error_after=2,
    )
    received: list[str] = []
    try:
        for delta in stream(
            ChatRequest(model="m", messages=[user(ASK)]),
            provider=OpenAIProvider(),
            transport=partial,
            api_key="DEMO",
        ):
            received.append(getattr(delta, "text", ""))
    except ProviderError as exc:
        print(f"  yielded {received!r} and then raised: {exc}")
        print("  A truncated answer is an exception, never a shorter reply.")

    print()
    print("=" * 72)
    print("7. LOSSY TRANSLATION IS DECLARED, NEVER SILENT")
    print("=" * 72)

    for label, provider, request in (
        (
            "Anthropic without max_output_tokens",
            AnthropicProvider(),
            ChatRequest(model="m", messages=[user(ASK)]),
        ),
        (
            "temperature on a model that rejects it",
            AnthropicProvider(),
            ChatRequest(
                model="claude-opus-4-6",
                messages=[user(ASK)],
                max_output_tokens=8,
                temperature=0.5,
            ),
        ),
    ):
        try:
            provider.build_request(request, api_key="DEMO")
            print(f"  {label}: accepted")
        except TranslationError as exc:
            print(f"  {label}:")
            print(f"    {exc}")

    print()
    print("Done. No network was used.")


def _system_shape(body: dict[str, Any]) -> str:
    if "system" in body:
        return f"top-level 'system' param = {body['system']!r}"
    if "systemInstruction" in body:
        return f"top-level 'systemInstruction' = {body['systemInstruction']!r}"
    for message in body.get("messages", []):
        if message.get("role") == "system":
            return f"a 'system' role message = {message['content']!r}"
    return "none"


def _arguments_of(line: str) -> str:
    try:
        payload = json.loads(line.removeprefix("data: "))
        frag = payload["choices"][0]["delta"]["tool_calls"][0]["function"].get(
            "arguments", ""
        )
    except (json.JSONDecodeError, KeyError, IndexError):
        return "?"
    return f"arguments += {frag!r}"


if __name__ == "__main__":
    main()
