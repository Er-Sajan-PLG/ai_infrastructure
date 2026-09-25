"""Offline regression tests for network read and request-body boundaries."""

from __future__ import annotations

import sys
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _sub in ("catalog/models", "integrations"):
    sys.path.insert(0, str(_ROOT / _sub))

from llm_http_transport.transport import UrllibTransport  # noqa: E402
from model_provider import TransportError, WireRequest  # noqa: E402


class _Headers:
    def items(self) -> list[tuple[str, str]]:
        return []


class _Reply:
    status = 200
    headers = _Headers()

    def __init__(
        self,
        *,
        body: bytes = b"",
        lines: list[bytes] | None = None,
        read_error: OSError | None = None,
    ) -> None:
        self.body = body
        self.lines = lines or []
        self.read_error = read_error
        self.closed = False

    def __enter__(self) -> _Reply:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def read(self) -> bytes:
        if self.read_error is not None:
            raise self.read_error
        return self.body

    def __iter__(self) -> Iterator[bytes]:
        return iter(self.lines)

    def close(self) -> None:
        self.closed = True


def _request(body: bytes = b"data") -> WireRequest:
    return WireRequest(
        method="POST",
        url="https://api.example.test/v1/chat",
        body=body,
    )


def _patch_urlopen(
    monkeypatch: pytest.MonkeyPatch, reply: _Reply
) -> list[urllib.request.Request]:
    seen: list[urllib.request.Request] = []

    def fake(request: urllib.request.Request, *, timeout: float) -> _Reply:
        del timeout
        seen.append(request)
        return reply

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return seen


@pytest.mark.parametrize(
    "read_error",
    [
        ConnectionResetError("connection reset during read"),
        BrokenPipeError("broken pipe during read"),
        OSError("generic read failure"),
    ],
    ids=["connection-reset", "broken-pipe", "generic-oserror"],
)
def test_send_read_oserror_is_translated_and_reply_closed(
    monkeypatch: pytest.MonkeyPatch, read_error: OSError
) -> None:
    reply = _Reply(read_error=read_error)
    _patch_urlopen(monkeypatch, reply)

    with pytest.raises(TransportError):
        UrllibTransport().send(_request())

    assert reply.closed


def test_stream_invalid_utf8_raises_transport_error_and_closes_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = _Reply(lines=[b"data: \xff\n"])
    _patch_urlopen(monkeypatch, reply)

    with pytest.raises(TransportError, match="undecodable bytes"):
        list(UrllibTransport().stream(_request()))

    assert reply.closed


def test_empty_wire_body_is_distinct_from_urllib_no_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = _Reply(body=b"ok")
    seen = _patch_urlopen(monkeypatch, reply)

    UrllibTransport().send(_request(b""))

    assert len(seen) == 1
    assert seen[0].data == b""
    no_body_request = urllib.request.Request("https://api.example.test/no-body")
    assert no_body_request.data is None
    assert reply.closed
