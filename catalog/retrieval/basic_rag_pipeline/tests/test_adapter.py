"""Tests for ``ProviderGenerator`` -- the model_provider binding.

The fake transport ships with model-provider-abstraction
(``RecordingTransport``), so the exact bytes a provider would receive are
assertable with no network and no credentials.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The entry lives at catalog/retrieval/basic_rag_pipeline/, so the importable
# parents are catalog/retrieval/ (this entry), catalog/models/ (model_provider)
# and catalog/memory/ (vector_store, imported by the package __init__).
_CATALOG = Path(__file__).resolve().parents[3]
for _sub in ("retrieval", "models", "memory"):
    sys.path.insert(0, str(_CATALOG / _sub))

from basic_rag_pipeline import ProviderGenerator  # noqa: E402
from model_provider import (  # noqa: E402
    ProviderError,
    RecordingTransport,
    WireResponse,
)
from model_provider.providers import OpenAIProvider  # noqa: E402


def _wire(status: int, payload: object) -> WireResponse:
    return WireResponse(
        status_code=status,
        headers={},
        body=json.dumps(payload).encode("utf-8"),
    )


def _openai_ok(text: str) -> WireResponse:
    return _wire(
        200,
        {
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def _make(
    responses: list[WireResponse] | None = None,
    *,
    system: str | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    error: Exception | None = None,
) -> tuple[ProviderGenerator, RecordingTransport]:
    wire = responses[0] if responses else _openai_ok("ok")
    transport = RecordingTransport(response=wire, error=error)
    generator = ProviderGenerator(
        provider=OpenAIProvider(),
        transport=transport,
        api_key="test-key",
        model="gpt-4o-mini",
        system=system,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    return generator, transport


class TestProviderGenerator:
    def test_returns_the_response_text(self) -> None:
        generator, transport = _make([_openai_ok("the answer")])
        assert generator.generate("prompt") == "the answer"
        assert len(transport.requests) == 1

    def test_sends_one_user_message_with_the_prompt(self) -> None:
        generator, transport = _make()
        generator.generate("what is retrieval?")
        request = transport.last_request
        assert request is not None
        payload = json.loads(request.body)
        assert payload["model"] == "gpt-4o-mini"
        assert payload["messages"] == [
            {"role": "user", "content": "what is retrieval?"}
        ]

    def test_system_prompt_sent_when_given(self) -> None:
        generator, transport = _make(system="Answer from context only.")
        generator.generate("prompt")
        assert transport.last_request is not None
        payload = json.loads(transport.last_request.body)
        assert payload["messages"][0] == {
            "role": "system",
            "content": "Answer from context only.",
        }

    def test_no_system_prompt_by_default(self) -> None:
        generator, transport = _make()
        generator.generate("prompt")
        assert transport.last_request is not None
        payload = json.loads(transport.last_request.body)
        assert [m["role"] for m in payload["messages"]] == ["user"]

    def test_token_cap_and_temperature_are_forwarded(self) -> None:
        generator, transport = _make(max_output_tokens=64, temperature=0.25)
        generator.generate("prompt")
        assert transport.last_request is not None
        payload = json.loads(transport.last_request.body)
        assert payload["max_completion_tokens"] == 64
        assert payload["temperature"] == pytest.approx(0.25)

    def test_provider_errors_propagate(self) -> None:
        wire = _wire(400, {"error": {"message": "bad model"}})
        generator, _ = _make([wire])
        with pytest.raises(ProviderError):
            generator.generate("prompt")

    def test_transport_errors_propagate(self) -> None:
        generator, _ = _make(error=RuntimeError("connection refused"))
        with pytest.raises(RuntimeError, match="connection refused"):
            generator.generate("prompt")
