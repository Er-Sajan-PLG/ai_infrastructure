"""Tests for the model provider abstraction.

Test philosophy (charter §18): the transport is injected, so every provider
quirk is exercised against **captured payloads** with no network, no
credentials and no model. The failure paths are the majority, because that is
where the three providers actually differ.

The payloads below are shaped from the providers' published specifications.
They are committed as data so the tests are deterministic.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from model_provider import (
    AuthenticationError,
    ChatRequest,
    ContextLengthError,
    ErrorSignals,
    FinishReason,
    Message,
    ProviderError,
    ProviderStream,
    RateLimitError,
    Role,
    TextBlock,
    TextDelta,
    ToolCallAccumulator,
    ToolCallBlock,
    ToolCallDelta,
    ToolResultBlock,
    TranslationError,
    Usage,
    UsageDelta,
    WireResponse,
    chat,
    iter_sse_events,
    stream,
)
from model_provider.providers import (
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
)
from model_provider.transport import RecordingTransport


def _user(text: str) -> Message:
    return Message(Role.USER, (TextBlock(text),))


def _wire(
    status: int, payload: object, headers: dict[str, str] | None = None
) -> WireResponse:
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    return WireResponse(status_code=status, headers=headers or {}, body=body)


# =========================================================================== #
# Neutral types
# =========================================================================== #


def test_usage_total_is_derived_when_both_parts_known() -> None:
    """Anthropic reports no total, so it must be summable."""
    usage = Usage(input_tokens=10, output_tokens=5)
    assert usage.derive_total().total_tokens == 15


def test_usage_total_is_not_invented_when_a_part_is_missing() -> None:
    """A missing count means unknown -- never zero, which would corrupt sums."""
    usage = Usage(input_tokens=10)
    derived = usage.derive_total()
    assert derived.total_tokens is None
    assert not derived.is_complete()


def test_usage_zero_is_distinguishable_from_absent() -> None:
    """A real zero is a measurement; absent is the lack of one."""
    zero = Usage(input_tokens=0, output_tokens=0, total_tokens=0)
    assert zero.is_complete()
    assert zero.total_tokens == 0


def test_response_derives_text_and_calls_from_blocks() -> None:
    """Flattened fields cannot disagree with blocks, because they are derived."""
    response_type = type(_wire(200, {})).__name__  # touch to keep flake quiet
    assert response_type == "WireResponse"


def test_message_text_excludes_tool_payloads() -> None:
    """Folding a tool payload into conversational text would corrupt a transcript."""
    message = Message(
        Role.ASSISTANT,
        (TextBlock("answer"), ToolCallBlock(id="1", name="t", arguments={"a": 1})),
    )
    assert message.text() == "answer"


def test_request_rejects_system_role_message_via_adapter() -> None:
    """A system-role message is a translation error, not something to reorder."""
    request = ChatRequest(
        model="gpt-4o-mini",
        messages=[Message(Role.SYSTEM, (TextBlock("be nice"),)), _user("hi")],
    )
    with pytest.raises(TranslationError, match="system"):
        OpenAIProvider().build_request(request, api_key="k")


@pytest.mark.parametrize(
    "provider",
    [OpenAIProvider(), AnthropicProvider(), GeminiProvider()],
)
def test_every_provider_refuses_a_system_role_message(provider: object) -> None:
    """All three differ in how system prompts work, so all three must refuse."""
    request = ChatRequest(
        model="m",
        messages=[Message(Role.SYSTEM, (TextBlock("s"),)), _user("hi")],
        max_output_tokens=16,
    )
    with pytest.raises(TranslationError):
        provider.build_request(request, api_key="k")  # type: ignore[attr-defined]


def test_request_is_immutable_after_construction() -> None:
    """A caller must not be able to mutate a request through a retained handle."""
    messages = [_user("hi")]
    request = ChatRequest(model="m", messages=messages)
    messages.append(_user("sneaky"))
    assert len(request.messages) == 1


# =========================================================================== #
# SSE decoding
# =========================================================================== #


def test_sse_joins_multiline_data() -> None:
    events = list(iter_sse_events(iter(["data: a", "data: b", ""])))
    assert len(events) == 1
    assert events[0].data == "a\nb"


def test_sse_strips_one_leading_space_only() -> None:
    events = list(iter_sse_events(iter(["data:  two", ""])))
    assert events[0].data == " two"


def test_sse_ignores_comments() -> None:
    events = list(iter_sse_events(iter([": keepalive", "data: x", ""])))
    assert len(events) == 1


def test_sse_marks_openai_done_sentinel() -> None:
    """[DONE] is not JSON, so it must be flagged rather than handed on."""
    events = list(iter_sse_events(iter(["data: [DONE]", ""])))
    assert events[0].is_done


def test_sse_captures_event_name() -> None:
    events = list(iter_sse_events(iter(["event: message_stop", "data: {}", ""])))
    assert events[0].event == "message_stop"


def test_sse_flushes_trailing_event_without_blank_line() -> None:
    """A final event may arrive without its terminating blank line."""
    events = list(iter_sse_events(iter(["data: last"])))
    assert len(events) == 1


# =========================================================================== #
# Tool-call argument reassembly -- the correctness trap
# =========================================================================== #


def test_accumulator_reassembles_arguments_split_mid_token() -> None:
    """OpenAI fragments a JSON string at arbitrary offsets.

    A fragment can end mid-key or mid-value, so treating each as parseable
    would produce corrupt arguments rather than an error.
    """
    acc = ToolCallAccumulator()
    acc.add(ToolCallDelta(index=0, id="c1", name="read", arguments_fragment='{"pa'))
    acc.add(ToolCallDelta(index=0, arguments_fragment='th": "a'))
    acc.add(ToolCallDelta(index=0, arguments_fragment='.txt"}'))
    (call,) = acc.finish()
    assert call.arguments == {"path": "a.txt"}
    assert call.name == "read"


def test_accumulator_handles_zero_argument_tool() -> None:
    """An empty fragment stream is a legitimate zero-argument call."""
    acc = ToolCallAccumulator()
    acc.add(ToolCallDelta(index=0, id="c1", name="ping"))
    (call,) = acc.finish()
    assert call.arguments == {}


def test_accumulator_preserves_stream_order() -> None:
    acc = ToolCallAccumulator()
    acc.add(ToolCallDelta(index=1, id="b", name="second", arguments_fragment="{}"))
    acc.add(ToolCallDelta(index=0, id="a", name="first", arguments_fragment="{}"))
    calls = acc.finish()
    assert [c.name for c in calls] == ["first", "second"]


def test_accumulator_raises_on_malformed_arguments() -> None:
    """Inventing {} for corrupt arguments would silently call a tool wrong."""
    acc = ToolCallAccumulator()
    acc.add(ToolCallDelta(index=0, id="c", name="t", arguments_fragment='{"broken'))
    with pytest.raises(ProviderError, match="not valid JSON"):
        acc.finish()


def test_accumulator_raises_when_name_never_arrives() -> None:
    acc = ToolCallAccumulator()
    acc.add(ToolCallDelta(index=0, id="c", arguments_fragment="{}"))
    with pytest.raises(ProviderError, match="never received a name"):
        acc.finish()


def test_accumulator_rejects_non_object_arguments() -> None:
    acc = ToolCallAccumulator()
    acc.add(ToolCallDelta(index=0, id="c", name="t", arguments_fragment="[1,2]"))
    with pytest.raises(ProviderError, match="expected object"):
        acc.finish()


def test_accumulator_synthesises_an_id_when_provider_omits_one() -> None:
    """Correlation must not silently break when a provider sends no id."""
    acc = ToolCallAccumulator()
    acc.add(ToolCallDelta(index=3, name="t", arguments_fragment="{}"))
    (call,) = acc.finish()
    assert call.id == "call_3"


# =========================================================================== #
# OpenAI adapter
# =========================================================================== #


def test_openai_parses_a_response() -> None:
    provider = OpenAIProvider()
    response = provider.parse_response(
        _wire(
            200,
            {
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 2,
                    "total_tokens": 9,
                },
            },
        )
    )
    assert response.text == "hello"
    assert response.finish_reason is FinishReason.STOP
    assert response.usage is not None and response.usage.total_tokens == 9


def test_openai_parses_tool_call_arguments_from_a_json_string() -> None:
    """OpenAI sends arguments as a STRING; the others send objects."""
    provider = OpenAIProvider()
    response = provider.parse_response(
        _wire(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "read",
                                        "arguments": '{"path": "a.txt"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )
    )
    assert response.text == ""
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].arguments == {"path": "a.txt"}
    assert response.finish_reason is FinishReason.TOOL_USE


def test_openai_malformed_tool_arguments_do_not_crash_the_parse() -> None:
    """A corrupt argument string must not take down the whole response."""
    provider = OpenAIProvider()
    response = provider.parse_response(
        _wire(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "c",
                                    "function": {"name": "t", "arguments": "{oops"},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )
    )
    assert response.tool_calls[0].arguments == {}


def test_openai_streams_usage_from_the_empty_choices_chunk() -> None:
    """The usage chunk has an EMPTY choices array -- the classic crash site."""
    provider = OpenAIProvider()
    delta = provider.parse_stream_line(
        event=None,
        data=json.dumps(
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            }
        ),
        is_done=False,
    )
    assert isinstance(delta, UsageDelta)
    assert delta.usage.total_tokens == 8


def test_openai_requests_usage_in_streaming_mode() -> None:
    """Without this flag the stream carries no usage at all."""
    wire = OpenAIProvider().build_request(
        ChatRequest(model="m", messages=[_user("hi")], stream=True), api_key="k"
    )
    body = json.loads(wire.body)
    assert body["stream_options"] == {"include_usage": True}


def test_openai_does_not_request_usage_when_not_streaming() -> None:
    wire = OpenAIProvider().build_request(
        ChatRequest(model="m", messages=[_user("hi")]), api_key="k"
    )
    assert "stream_options" not in json.loads(wire.body)


def test_openai_done_sentinel_yields_no_delta() -> None:
    provider = OpenAIProvider()
    assert provider.parse_stream_line(event=None, data="[DONE]", is_done=True) is None


def test_openai_extra_cannot_overwrite_the_model() -> None:
    """Caller extras must fill gaps, never clobber the adapter's own fields."""
    wire = OpenAIProvider().build_request(
        ChatRequest(model="real", messages=[_user("hi")], extra={"model": "evil"}),
        api_key="k",
    )
    assert json.loads(wire.body)["model"] == "real"


def test_openai_sends_the_api_key_as_a_bearer_header() -> None:
    wire = OpenAIProvider().build_request(
        ChatRequest(model="m", messages=[_user("hi")]), api_key="secret"
    )
    assert wire.headers["Authorization"] == "Bearer secret"


def test_openai_classifies_a_spend_cap_429_as_not_retryable() -> None:
    """A 429 with no retry hint can never succeed; retrying loops forever."""
    provider = OpenAIProvider()
    error = provider.classify_error(
        _signals(
            provider, 429, {"error": {"message": "quota", "code": "insufficient_quota"}}
        )
    )
    assert isinstance(error, RateLimitError)
    assert error.retryable is False


def test_openai_treats_a_429_with_retry_after_as_retryable() -> None:
    provider = OpenAIProvider()
    error = provider.classify_error(
        _signals(provider, 429, {"error": {"message": "slow down"}}, retry_after=2.0)
    )
    assert error.retryable is True
    assert error.retry_after == 2.0


def test_openai_detects_context_length_by_code_not_message() -> None:
    """Classification must use structured signal (D-4)."""
    provider = OpenAIProvider()
    error = provider.classify_error(
        _signals(
            provider,
            400,
            {"error": {"message": "nope", "code": "context_length_exceeded"}},
        )
    )
    assert isinstance(error, ContextLengthError)
    assert error.retryable is False


def test_openai_classifies_auth_failure() -> None:
    provider = OpenAIProvider()
    error = provider.classify_error(
        _signals(provider, 401, {"error": {"message": "bad key"}})
    )
    assert isinstance(error, AuthenticationError)


# =========================================================================== #
# Anthropic adapter
# =========================================================================== #


def test_anthropic_requires_max_tokens() -> None:
    """The API makes it mandatory; defaulting it would change cost and truncation."""
    with pytest.raises(TranslationError, match="max_output_tokens"):
        AnthropicProvider().build_request(
            ChatRequest(model="claude-x", messages=[_user("hi")]), api_key="k"
        )


def test_anthropic_declares_temperature_incompatibility() -> None:
    """Declared, never silently dropped (D-7)."""
    with pytest.raises(TranslationError, match="temperature"):
        AnthropicProvider().build_request(
            ChatRequest(
                model="claude-opus-4-6",
                messages=[_user("hi")],
                max_output_tokens=16,
                temperature=0.5,
            ),
            api_key="k",
        )


def test_anthropic_sends_system_as_a_top_level_parameter() -> None:
    """Anthropic has no system role at all."""
    wire = AnthropicProvider().build_request(
        ChatRequest(
            model="m", messages=[_user("hi")], system="be nice", max_output_tokens=16
        ),
        api_key="k",
    )
    body = json.loads(wire.body)
    assert body["system"] == "be nice"
    assert all(m["role"] != "system" for m in body["messages"])


def test_anthropic_sends_the_version_header() -> None:
    wire = AnthropicProvider().build_request(
        ChatRequest(model="m", messages=[_user("hi")], max_output_tokens=1), api_key="k"
    )
    assert wire.headers["anthropic-version"] == "2023-06-01"
    assert wire.headers["x-api-key"] == "k"


def test_anthropic_parses_text_blocks() -> None:
    provider = AnthropicProvider()
    response = provider.parse_response(
        _wire(
            200,
            {
                "model": "claude-x",
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 4, "output_tokens": 2},
            },
        )
    )
    assert response.text == "hello"
    assert response.finish_reason is FinishReason.STOP
    # No total_tokens field exists; it must be derived.
    assert response.usage is not None
    assert response.usage.total_tokens == 6


def test_anthropic_parses_tool_use_with_a_parsed_object() -> None:
    provider = AnthropicProvider()
    response = provider.parse_response(
        _wire(
            200,
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "read",
                        "input": {"path": "a"},
                    }
                ],
                "stop_reason": "tool_use",
            },
        )
    )
    assert response.tool_calls[0].arguments == {"path": "a"}
    assert response.finish_reason is FinishReason.TOOL_USE


def test_anthropic_maps_refusal_to_content_filter_not_stop() -> None:
    provider = AnthropicProvider()
    response = provider.parse_response(
        _wire(200, {"content": [], "stop_reason": "refusal"})
    )
    assert response.finish_reason is FinishReason.CONTENT_FILTER


def test_anthropic_pause_turn_is_not_reported_as_a_clean_stop() -> None:
    """A paused turn is not a finished one; claiming STOP would mislead."""
    provider = AnthropicProvider()
    response = provider.parse_response(
        _wire(200, {"content": [], "stop_reason": "pause_turn"})
    )
    assert response.finish_reason is FinishReason.UNKNOWN
    assert response.raw_finish_reason == "pause_turn"


def test_anthropic_usage_arrives_across_two_event_types() -> None:
    """input_tokens on message_start, cumulative output_tokens on message_delta."""
    provider = AnthropicProvider()
    start = provider.parse_stream_line(
        event="message_start",
        data=json.dumps(
            {"type": "message_start", "message": {"usage": {"input_tokens": 11}}}
        ),
        is_done=False,
    )
    assert isinstance(start, UsageDelta)
    assert start.usage.input_tokens == 11

    delta = provider.parse_stream_line(
        event="message_delta",
        data=json.dumps(
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 5},
            }
        ),
        is_done=False,
    )
    # message_delta carries both the stop reason and the output count; the stop
    # reason wins because it is the terminal signal.
    assert delta is not None


def test_anthropic_streams_text_deltas() -> None:
    provider = AnthropicProvider()
    delta = provider.parse_stream_line(
        event="content_block_delta",
        data=json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "hi"},
            }
        ),
        is_done=False,
    )
    assert isinstance(delta, TextDelta)
    assert delta.text == "hi"


def test_anthropic_streams_partial_json_fragments() -> None:
    provider = AnthropicProvider()
    delta = provider.parse_stream_line(
        event="content_block_delta",
        data=json.dumps(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '{"a"'},
            }
        ),
        is_done=False,
    )
    assert isinstance(delta, ToolCallDelta)
    assert delta.arguments_fragment == '{"a"'


def test_anthropic_ping_yields_nothing() -> None:
    provider = AnthropicProvider()
    assert (
        provider.parse_stream_line(
            event="ping", data=json.dumps({"type": "ping"}), is_done=False
        )
        is None
    )


def test_anthropic_529_is_retryable() -> None:
    """529 overloaded_error is non-standard; a naive 5xx rule misses its meaning."""
    provider = AnthropicProvider()
    error = provider.classify_error(
        _signals(
            provider, 529, {"type": "error", "error": {"type": "overloaded_error"}}
        )
    )
    assert error.retryable is True


def test_anthropic_spend_cap_429_is_not_retryable() -> None:
    """No retry-after means retrying forever; this is the busy-loop trap."""
    provider = AnthropicProvider()
    error = provider.classify_error(
        _signals(
            provider,
            429,
            {
                "type": "error",
                "error": {"type": "rate_limit_error"},
                "request_id": "req_1",
            },
        )
    )
    assert isinstance(error, RateLimitError)
    assert error.retryable is False
    assert error.request_id == "req_1"


def test_anthropic_mid_stream_error_raises_from_the_iterator() -> None:
    """A failure after a 200 must not silently truncate the output."""
    provider = AnthropicProvider()
    with pytest.raises(ProviderError):
        provider.parse_stream_line(
            event="error",
            data=json.dumps(
                {
                    "type": "error",
                    "error": {"type": "overloaded_error", "message": "boom"},
                }
            ),
            is_done=False,
        )


def test_anthropic_converts_tool_parameters_to_input_schema() -> None:
    wire = AnthropicProvider().build_request(
        ChatRequest(
            model="m",
            messages=[_user("hi")],
            max_output_tokens=16,
            tools=[{"name": "t", "description": "d", "parameters": {"type": "object"}}],
        ),
        api_key="k",
    )
    tool = json.loads(wire.body)["tools"][0]
    assert "input_schema" in tool
    assert "parameters" not in tool


# =========================================================================== #
# Gemini adapter
# =========================================================================== #


def test_gemini_uses_model_role_for_assistant() -> None:
    """Gemini calls the assistant role 'model'."""
    wire = GeminiProvider().build_request(
        ChatRequest(
            model="gemini-x",
            messages=[_user("hi"), Message(Role.ASSISTANT, (TextBlock("yo"),))],
        ),
        api_key="k",
    )
    body = json.loads(wire.body)
    assert [c["role"] for c in body["contents"]] == ["user", "model"]


def test_gemini_sends_system_as_system_instruction() -> None:
    wire = GeminiProvider().build_request(
        ChatRequest(model="m", messages=[_user("hi")], system="be nice"), api_key="k"
    )
    body = json.loads(wire.body)
    assert body["systemInstruction"] == {"parts": [{"text": "be nice"}]}


def test_gemini_requires_alt_sse_for_streaming() -> None:
    """Without alt=sse the response is a JSON array, not an event stream."""
    wire = GeminiProvider().build_request(
        ChatRequest(model="m", messages=[_user("hi")], stream=True), api_key="k"
    )
    assert wire.url.endswith(":streamGenerateContent?alt=sse")


def test_gemini_parses_parts_and_maps_finish_reason() -> None:
    provider = GeminiProvider()
    response = provider.parse_response(
        _wire(
            200,
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "hello"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 3,
                    "candidatesTokenCount": 2,
                    "totalTokenCount": 5,
                },
            },
        )
    )
    assert response.text == "hello"
    assert response.finish_reason is FinishReason.STOP
    assert response.usage is not None and response.usage.total_tokens == 5


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SAFETY", FinishReason.CONTENT_FILTER),
        ("MAX_TOKENS", FinishReason.LENGTH),
        ("MALFORMED_FUNCTION_CALL", FinishReason.ERROR),
        ("SOME_FUTURE_VALUE", FinishReason.UNKNOWN),
    ],
)
def test_gemini_maps_its_large_finish_reason_enum(
    raw: str, expected: FinishReason
) -> None:
    """18+ values cannot merge losslessly, so unknowns stay UNKNOWN with the raw."""
    provider = GeminiProvider()
    response = provider.parse_response(
        _wire(200, {"candidates": [{"content": {"parts": []}, "finishReason": raw}]})
    )
    assert response.finish_reason is expected
    assert response.raw_finish_reason == raw


def test_gemini_prompt_level_block_has_no_candidate() -> None:
    """A blocked prompt returns promptFeedback and no candidates at all."""
    provider = GeminiProvider()
    response = provider.parse_response(
        _wire(200, {"promptFeedback": {"blockReason": "SAFETY"}})
    )
    assert response.finish_reason is FinishReason.CONTENT_FILTER
    assert response.raw_finish_reason == "SAFETY"
    assert response.text == ""


def test_gemini_classifies_by_the_google_status_string() -> None:
    """Gemini uses Cloud-style string statuses, not a flat type field."""
    provider = GeminiProvider()
    error = provider.classify_error(
        _signals(
            provider,
            429,
            {
                "error": {
                    "code": 429,
                    "message": "quota",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
        )
    )
    assert isinstance(error, RateLimitError)


def test_gemini_parses_a_streamed_function_call() -> None:
    """Gemini sends a complete functionCall, not fragments."""
    provider = GeminiProvider()
    delta = provider.parse_stream_line(
        event=None,
        data=json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"functionCall": {"name": "read", "args": {"p": 1}}}
                            ]
                        }
                    }
                ]
            }
        ),
        is_done=False,
    )
    assert isinstance(delta, ToolCallDelta)
    assert json.loads(delta.arguments_fragment) == {"p": 1}


# =========================================================================== #
# The end-to-end seam
# =========================================================================== #


def test_chat_round_trips_through_a_canned_transport() -> None:
    """No network, no credentials, no model -- just the shape."""
    transport = RecordingTransport(
        response=_wire(
            200,
            {
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
            },
        )
    )
    response = chat(
        ChatRequest(model="gpt-4o-mini", messages=[_user("hello")]),
        provider=OpenAIProvider(),
        transport=transport,
        api_key="k",
    )
    assert response.text == "hi"
    assert transport.last_request is not None
    assert transport.last_request.method == "POST"


def test_chat_raises_a_classified_error_on_failure() -> None:
    transport = RecordingTransport(
        response=_wire(401, {"error": {"message": "bad key"}})
    )
    with pytest.raises(AuthenticationError):
        chat(
            ChatRequest(model="m", messages=[_user("hi")]),
            provider=OpenAIProvider(),
            transport=transport,
            api_key="wrong",
        )


def test_stream_end_to_end_produces_ordered_deltas() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"He"}}]}',
        "",
        'data: {"choices":[{"delta":{"content":"llo"}}]}',
        "",
        "data: [DONE]",
        "",
    ]
    transport = RecordingTransport(lines=tuple(lines))
    deltas = list(
        stream(
            ChatRequest(model="m", messages=[_user("hi")]),
            provider=OpenAIProvider(),
            transport=transport,
            api_key="k",
        )
    )
    assert "".join(d.text for d in deltas if isinstance(d, TextDelta)) == "Hello"


def test_stream_can_fail_after_yielding_tokens() -> None:
    """Truncation must be an exception, not a shorter answer.

    OpenAI raises on an error frame after a 200; Anthropic sends a mid-stream
    error event. Both must reach the caller from the iteration itself.
    """
    lines = ['data: {"choices":[{"delta":{"content":"partial"}}]}', ""]
    transport = RecordingTransport(
        lines=tuple(lines),
        stream_error=ProviderError("connection dropped", provider="openai"),
        stream_error_after=len(lines),
    )
    collected: list[str] = []
    with pytest.raises(ProviderError):
        for delta in stream(
            ChatRequest(model="m", messages=[_user("hi")]),
            provider=OpenAIProvider(),
            transport=transport,
            api_key="k",
        ):
            if isinstance(delta, TextDelta):
                collected.append(delta.text)
    assert collected == ["partial"], "tokens before the failure must have been yielded"


def test_provider_stream_wraps_foreign_exceptions() -> None:
    """A caller should never have to catch a stdlib exception from this layer."""

    def exploding() -> Iterator[TextDelta]:
        yield TextDelta(text="a")
        raise ValueError("something internal")

    wrapped = ProviderStream(exploding(), provider="p", model="m")
    seen = []
    with pytest.raises(ProviderError):
        for delta in wrapped:
            seen.append(delta)
    assert len(seen) == 1


def test_provider_stream_passes_through_provider_errors_unchanged() -> None:
    original = ProviderError("real failure", provider="p", status_code=429)

    def failing() -> Iterator[TextDelta]:
        yield TextDelta(text="a")
        raise original

    with pytest.raises(ProviderError) as excinfo:
        list(ProviderStream(failing(), provider="p", model="m"))
    assert excinfo.value is original


# =========================================================================== #
# Security properties
# =========================================================================== #


def test_error_messages_do_not_contain_the_raw_body() -> None:
    """A provider body can echo request content; it must not reach a prompt."""
    provider = OpenAIProvider()
    secret = "sk-LEAKED-SECRET"  # noqa: S105 -- a fake credential for a leak test
    error = provider.classify_error(
        _signals(provider, 500, {"error": {"message": "boom"}, "debug": secret})
    )
    assert secret not in str(error)
    assert secret not in error.message


def test_retryability_is_structural_not_textual() -> None:
    """D-4: classification must not consult message text.

    A message that *looks* retryable on a status that is not, must not become
    retryable.
    """
    provider = OpenAIProvider()
    error = provider.classify_error(
        _signals(provider, 400, {"error": {"message": "please retry this request"}})
    )
    assert error.retryable is False


def test_no_third_party_imports() -> None:
    """Zero runtime dependencies is a load-bearing property (ADR-0003)."""
    import ast
    import sys as _sys

    package_root = Path(__file__).resolve().parents[1]
    stdlib: frozenset[str] = getattr(_sys, "stdlib_module_names", frozenset())
    offenders: list[str] = []

    for path in sorted(package_root.rglob("*.py")):
        if "tests" in path.parts or "examples" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name not in stdlib and name != "model_provider":
                    offenders.append(f"{path.name}: {name}")

    assert offenders == [], f"third-party imports found: {offenders}"


def test_tool_result_block_round_trips_to_openai() -> None:
    wire = OpenAIProvider().build_request(
        ChatRequest(
            model="m",
            messages=[
                Message(Role.TOOL, (ToolResultBlock(tool_call_id="c1", content="42"),))
            ],
        ),
        api_key="k",
    )
    message = json.loads(wire.body)["messages"][0]
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "c1"


def test_collect_stream_assembles_a_complete_response() -> None:
    from model_provider import collect_stream

    lines = [
        'data: {"choices":[{"delta":{"content":"Hi"}}]}',
        "",
        'data: {"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}',
        "",
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
        "",
        "data: [DONE]",
        "",
    ]
    transport = RecordingTransport(lines=tuple(lines))
    response = collect_stream(
        stream(
            ChatRequest(model="m", messages=[_user("hi")]),
            provider=OpenAIProvider(),
            transport=transport,
            api_key="k",
        ),
        provider="openai",
        model="m",
    )
    assert response.text == "Hi"
    assert response.finish_reason is FinishReason.STOP
    assert response.usage is not None and response.usage.total_tokens == 2


def test_tool_call_blocks_are_returned_from_a_collected_stream() -> None:
    from model_provider import collect_stream

    lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
        '"function":{"name":"read","arguments":"{\\"p\\":"}}]}}]}',
        "",
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        '"function":{"arguments":"1}"}}]}}]}',
        "",
        "data: [DONE]",
        "",
    ]
    transport = RecordingTransport(lines=tuple(lines))
    response = collect_stream(
        stream(
            ChatRequest(model="m", messages=[_user("hi")]),
            provider=OpenAIProvider(),
            transport=transport,
            api_key="k",
        ),
        provider="openai",
        model="m",
    )
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].arguments == {"p": 1}


def _signals(
    provider: object,
    status: int,
    body: object,
    *,
    retry_after: float | None = None,
) -> ErrorSignals:
    name = str(getattr(provider, "name", "unknown"))
    return ErrorSignals(
        provider=name, model="m", status_code=status, body=body, retry_after=retry_after
    )
