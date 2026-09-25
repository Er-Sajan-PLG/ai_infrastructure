"""Offline tests for the stdlib HTTP transport and key resolution.

What "offline" means here
-------------------------
No test in this file opens a socket. ``urllib.request.urlopen`` is replaced
with fakes, so the suite exercises the transport's mapping logic -- request
encoding, status-as-data, failure classification, streaming -- deterministically
and stays inside the default gate (no ``network`` marker needed; charter §18).

Why fakes rather than ``http.server`` in-process
------------------------------------------------
A loopback server would test :mod:`urllib` itself, which is CPython's job, not
ours. What is ours is the boundary: exact bytes forwarded, non-2xx returned
rather than raised, stdlib failures classified, credentials never leaked into
messages. Fakes assert exactly that boundary.
"""

from __future__ import annotations

import io
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from email.message import Message as EmailMessage
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _sub in ("catalog/models", "integrations"):
    sys.path.insert(0, str(_ROOT / _sub))

from llm_http_transport.keys import (  # noqa: E402
    PROVIDER_ENV_VARS,
    MissingApiKeyError,
    resolve_api_key,
)
from llm_http_transport.transport import DEFAULT_TIMEOUT, UrllibTransport  # noqa: E402
from model_provider import (  # noqa: E402
    ProviderTimeoutError,
    Transport,
    TransportError,
    WireRequest,
    WireResponse,
)

# --------------------------------------------------------------------------- #
# Doubles
# --------------------------------------------------------------------------- #


class FakeHeaders:
    """Minimal headers stand-in: only ``items()`` is read."""

    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = headers

    def items(self) -> Any:
        return self._headers.items()


def http_headers(headers: dict[str, str] | None = None) -> EmailMessage:
    """Build a real :class:`email.message.Message` for ``HTTPError``.

    ``HTTPError`` requires a genuine message object, not a stand-in, so the
    non-2xx tests construct one here rather than reusing ``FakeHeaders``.
    """
    message = EmailMessage()
    for key, value in (headers or {}).items():
        message[key] = value
    return message


class FakeReply:
    """An open HTTP reply: context manager, ``status``/``headers``, readable,
    line-iterable, closeable. Records whether it was closed."""

    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
        lines: list[bytes] | None = None,
        read_error: Exception | None = None,
        iter_error_at: int = -1,
        iter_error: Exception | None = None,
    ) -> None:
        self.status = status
        self.headers = FakeHeaders(headers or {})
        self._body = body
        self._lines = lines or []
        self._read_error = read_error
        self._iter_error_at = iter_error_at
        self._iter_error = iter_error
        self.closed = False

    def __enter__(self) -> FakeReply:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def read(self) -> bytes:
        if self._read_error is not None:
            raise self._read_error
        return self._body

    def __iter__(self) -> Iterator[bytes]:
        for index, line in enumerate(self._lines):
            if self._iter_error is not None and index == self._iter_error_at:
                raise self._iter_error
            yield line

    def close(self) -> None:
        self.closed = True


def make_request() -> WireRequest:
    """A representative provider-built request: POST, headers (incl. auth),
    JSON body -- exactly what an adapter's ``build_request`` produces."""
    return WireRequest(
        method="POST",
        url="https://api.example.test/v1/chat",
        headers={
            "Authorization": "Bearer test-key-value",
            "Content-Type": "application/json",
        },
        body=b'{"model":"m","messages":[]}',
    )


def patch_urlopen(
    monkeypatch: pytest.MonkeyPatch, behaviour: Any
) -> list[urllib.request.Request]:
    """Replace ``urlopen`` with ``behaviour``; return the requests it received."""
    seen: list[urllib.request.Request] = []

    def fake(urlopen_request: urllib.request.Request, *, timeout: float) -> Any:
        seen.append(urlopen_request)
        return behaviour(urlopen_request, timeout)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return seen


# --------------------------------------------------------------------------- #
# The seam is real only if an outsider can implement it
# --------------------------------------------------------------------------- #


def test_structurally_satisfies_the_transport_protocol() -> None:
    assert isinstance(UrllibTransport(), Transport)


def test_default_timeout_is_positive() -> None:
    assert DEFAULT_TIMEOUT > 0
    assert UrllibTransport().timeout == DEFAULT_TIMEOUT


def test_non_positive_timeout_rejected() -> None:
    with pytest.raises(ValueError):
        UrllibTransport(timeout=0)


# --------------------------------------------------------------------------- #
# send(): the request goes out exactly as given
# --------------------------------------------------------------------------- #


def test_send_forwards_method_url_headers_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = FakeReply(
        status=200,
        headers={"content-type": "application/json"},
        body=b'{"ok":true}',
    )
    seen = patch_urlopen(monkeypatch, lambda _req, _timeout: reply)

    wire = make_request()
    response = UrllibTransport().send(wire)

    assert len(seen) == 1
    outgoing = seen[0]
    assert outgoing.get_method() == "POST"
    assert outgoing.full_url == wire.url
    assert outgoing.get_header("Authorization") == "Bearer test-key-value"
    assert outgoing.data == wire.body
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json"}
    assert response.body == b'{"ok":true}'


def test_send_timeout_reaches_urlopen(monkeypatch: pytest.MonkeyPatch) -> None:
    timeouts: list[float] = []

    def behaviour(_req: urllib.request.Request, timeout: float) -> FakeReply:
        timeouts.append(timeout)
        return FakeReply(body=b"{}")

    patch_urlopen(monkeypatch, behaviour)
    UrllibTransport(timeout=7.5).send(make_request())
    assert timeouts == [7.5]


def test_send_non_2xx_returned_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_body = b'{"error":{"code":"rate_limited"}}'

    def behaviour(req: urllib.request.Request, _timeout: float) -> Any:
        raise urllib.error.HTTPError(
            req.full_url,
            429,
            "Too Many Requests",
            http_headers(),
            io.BytesIO(error_body),
        )

    patch_urlopen(monkeypatch, behaviour)
    response = UrllibTransport().send(make_request())
    assert response.status_code == 429
    assert response.body == error_body


# --------------------------------------------------------------------------- #
# send(): stdlib failures are classified, never leaked raw
# --------------------------------------------------------------------------- #


def test_send_connection_failure_becomes_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def behaviour(_req: urllib.request.Request, _timeout: float) -> Any:
        raise urllib.error.URLError("connection refused")

    patch_urlopen(monkeypatch, behaviour)
    with pytest.raises(TransportError):
        UrllibTransport().send(make_request())


def test_send_timeout_becomes_provider_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def behaviour(_req: urllib.request.Request, _timeout: float) -> Any:
        raise TimeoutError("timed out")

    patch_urlopen(monkeypatch, behaviour)
    with pytest.raises(ProviderTimeoutError):
        UrllibTransport().send(make_request())


def test_send_wrapped_timeout_becomes_provider_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # urlopen wraps inconsistently: sometimes URLError(reason=TimeoutError).
    def behaviour(_req: urllib.request.Request, _timeout: float) -> Any:
        raise urllib.error.URLError(TimeoutError("timed out"))

    patch_urlopen(monkeypatch, behaviour)
    with pytest.raises(ProviderTimeoutError):
        UrllibTransport().send(make_request())


def test_send_rejects_non_http_scheme() -> None:
    """``file:`` URLs never reach :mod:`urllib`: a confused caller must fail
    here, not become a local-file reader."""
    request = WireRequest(method="GET", url="file:///etc/hostname")
    with pytest.raises(TransportError):
        UrllibTransport().send(request)


def test_stream_rejects_non_http_scheme() -> None:
    request = WireRequest(method="GET", url="gopher://example.test/x")
    with pytest.raises(TransportError):
        UrllibTransport().stream(request)


def test_send_failure_message_leaks_no_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def behaviour(_req: urllib.request.Request, _timeout: float) -> Any:
        raise urllib.error.URLError("connection refused")

    patch_urlopen(monkeypatch, behaviour)
    with pytest.raises(TransportError) as exc_info:
        UrllibTransport().send(make_request())
    assert "test-key-value" not in str(exc_info.value)
    assert "Bearer" not in str(exc_info.value)


# --------------------------------------------------------------------------- #
# stream(): raw lines out, failures classified, reply always closed
# --------------------------------------------------------------------------- #


def test_stream_yields_raw_lines_with_endings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines = [b'data: {"a":1}\n', b"\n", b"data: [DONE]\n"]
    reply = FakeReply(lines=lines)
    patch_urlopen(monkeypatch, lambda _req, _timeout: reply)

    assert list(UrllibTransport().stream(make_request())) == [
        'data: {"a":1}\n',
        "\n",
        "data: [DONE]\n",
    ]
    assert reply.closed


def test_stream_non_2xx_open_raises_transport_error_with_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def behaviour(req: urllib.request.Request, _timeout: float) -> Any:
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", http_headers(), io.BytesIO(b"{}")
        )

    patch_urlopen(monkeypatch, behaviour)
    with pytest.raises(TransportError) as exc_info:
        UrllibTransport().stream(make_request())
    assert exc_info.value.status_code == 401


def test_stream_mid_iteration_failure_surfaces_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = FakeReply(
        lines=[b"data: 1\n", b"data: 2\n"],
        iter_error_at=1,
        iter_error=urllib.error.URLError("connection reset"),
    )
    patch_urlopen(monkeypatch, lambda _req, _timeout: reply)

    with pytest.raises(TransportError):
        list(UrllibTransport().stream(make_request()))
    assert reply.closed


def test_stream_mid_iteration_timeout_surfaces_as_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = FakeReply(
        lines=[b"data: 1\n", b"data: 2\n"],
        iter_error_at=1,
        iter_error=TimeoutError("timed out"),
    )
    patch_urlopen(monkeypatch, lambda _req, _timeout: reply)

    with pytest.raises(ProviderTimeoutError):
        list(UrllibTransport().stream(make_request()))


# --------------------------------------------------------------------------- #
# keys: env resolution
# --------------------------------------------------------------------------- #


def test_resolve_api_key_reads_the_mapped_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "key-from-env")
    assert resolve_api_key("openai") == "key-from-env"


def test_resolve_api_key_matches_provider_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    assert resolve_api_key("Anthropic") == "anthropic-key"


def test_resolve_api_key_covers_all_mapped_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for provider, variable in PROVIDER_ENV_VARS.items():
        monkeypatch.setenv(variable, f"key-for-{provider}")
        assert resolve_api_key(provider) == f"key-for-{provider}"


def test_resolve_api_key_missing_variable_names_variable_and_remedy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError) as exc_info:
        resolve_api_key("openai")
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_resolve_api_key_blank_variable_counts_as_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    with pytest.raises(MissingApiKeyError):
        resolve_api_key("gemini")


def test_resolve_api_key_unknown_provider_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_api_key("unknown-vendor")


# --------------------------------------------------------------------------- #
# Composition: the real adapter over this transport, socket stubbed at urlopen
# --------------------------------------------------------------------------- #


def test_openai_adapter_round_trip_over_urllib_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transport is endpoint-agnostic: whatever the adapter encodes, the
    transport carries. Proven with the real OpenAI adapter and a canned reply."""
    sys.path.insert(0, str(_ROOT / "catalog/models"))
    from model_provider import ChatRequest, Message, Role, TextBlock, chat
    from model_provider.providers import OpenAIProvider

    payload = (
        b'{"id":"chatcmpl-x","object":"chat.completion","model":"m",'
        b'"choices":[{"index":0,"message":{"role":"assistant",'
        b'"content":"hello"},"finish_reason":"stop"}]}'
    )
    patch_urlopen(monkeypatch, lambda _req, _timeout: FakeReply(body=payload))

    response = chat(
        ChatRequest(
            model="m",
            messages=[Message(role=Role.USER, content=(TextBlock(text="hi"),))],
        ),
        provider=OpenAIProvider(),
        transport=UrllibTransport(),
        api_key="test-key-value",
    )
    assert response.text == "hello"


def test_openai_adapter_error_classification_survives_the_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 401 reply carried by this transport classifies as authentication --
    the status-as-data contract holding across the real seam."""
    sys.path.insert(0, str(_ROOT / "catalog/models"))
    from model_provider import (
        AuthenticationError,
        ChatRequest,
        Message,
        Role,
        TextBlock,
        chat,
    )
    from model_provider.providers import OpenAIProvider

    def behaviour(req: urllib.request.Request, _timeout: float) -> Any:
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", http_headers(), io.BytesIO(b"{}")
        )

    patch_urlopen(monkeypatch, behaviour)
    with pytest.raises(AuthenticationError):
        chat(
            ChatRequest(
                model="m",
                messages=[Message(role=Role.USER, content=(TextBlock(text="hi"),))],
            ),
            provider=OpenAIProvider(),
            transport=UrllibTransport(),
            api_key="wrong-key",
        )


def test_send_returns_a_wire_response_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transport returns values, not provider knowledge: status, headers
    and body cross the seam uninterpreted for the adapter to classify."""
    patch_urlopen(
        monkeypatch,
        lambda _req, _timeout: FakeReply(
            status=201, headers={"x-id": "abc"}, body=b"{}"
        ),
    )
    response = UrllibTransport().send(make_request())
    assert isinstance(response, WireResponse)
    assert response.status_code == 201
    assert response.headers == {"x-id": "abc"}
    assert response.body == b"{}"
