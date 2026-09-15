"""The transport seam (ADR-0007 D-1).

The abstraction owns *shape*; the caller owns the *socket*. This module defines
the narrow contract between them and provides an in-memory implementation for
tests.

Why the seam exists: it is the single decision that preserves zero runtime
dependencies. Owning transport is what forces LiteLLM to depend on 14 packages
including ``boto3`` -- verified by fetching its ``pyproject.toml``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from .errors import TransportError
from .types import WireRequest, WireResponse


@runtime_checkable
class Transport(Protocol):
    """Performs HTTP. Knows nothing about providers.

    An implementation must:

    * attach authentication (the abstraction never handles credentials),
    * apply timeouts and proxies,
    * raise :class:`~model_provider.errors.TransportError` or
      :class:`~model_provider.errors.ProviderTimeoutError` on connection
      problems, rather than a stdlib exception,
    * yield **raw response lines** from :meth:`stream`, without interpreting SSE
      framing or provider sentinels.

    It must **not**:

    * retry (the caller owns retry policy -- D-4),
    * interpret ``data: [DONE]`` (that is provider knowledge; the adapter decides
      termination),
    * parse JSON.
    """

    def send(self, request: WireRequest) -> WireResponse:
        """Send a request and return the full response. Must not raise on a
        non-2xx status -- status is data, and classification is the adapter's
        job, not the transport's."""
        ...

    def stream(self, request: WireRequest) -> Iterator[str]:
        """Send a request and yield raw response lines until EOF.

        Must raise ``TransportError``/``ProviderTimeoutError`` for connection
        failures, and is permitted to raise mid-iteration."""
        ...


class RecordingTransport:
    """A transport that returns canned responses and records what it was sent.

    This is what makes three providers' edge cases testable deterministically,
    with no network, no credentials and no model. It is a test double that ships
    with the package because the package's own tests need it and because a
    consumer testing their adapter wiring needs exactly this.

    Not thread-safe: it records into a list without locking, which is correct for
    its intended use and cheaper than the alternative.
    """

    def __init__(
        self,
        *,
        response: WireResponse | None = None,
        lines: tuple[str, ...] = (),
        error: Exception | None = None,
        stream_error: Exception | None = None,
        stream_error_after: int = 0,
    ) -> None:
        """
        Args:
            response: Returned by :meth:`send`.
            lines: Yielded by :meth:`stream`.
            error: Raised by :meth:`send` instead of returning.
            stream_error: Raised from :meth:`stream` after
                ``stream_error_after`` lines, to exercise mid-stream failure.
            stream_error_after: How many lines to yield before ``stream_error``.
        """
        self.response = response or WireResponse(status_code=200)
        self.lines = lines
        self.error = error
        self.stream_error = stream_error
        self.stream_error_after = stream_error_after
        self.requests: list[WireRequest] = []

    @property
    def last_request(self) -> WireRequest | None:
        """The most recent request, for assertions."""
        return self.requests[-1] if self.requests else None

    def send(self, request: WireRequest) -> WireResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response

    def stream(self, request: WireRequest) -> Iterator[str]:
        self.requests.append(request)
        for i, line in enumerate(self.lines):
            if self.stream_error is not None and i == self.stream_error_after:
                raise self.stream_error
            yield line
        if self.stream_error is not None and self.stream_error_after >= len(self.lines):
            raise self.stream_error


def require_http_ok(provider: str, model: str, response: WireResponse) -> None:
    """Convenience guard for adapters that want a single early status check.

    Provided as a helper rather than enforced by the transport, because status
    classification needs the provider's error-body shape, which the transport
    must not know.
    """
    if response.status_code >= 400 and not response.body:
        raise TransportError(
            f"HTTP {response.status_code} with an empty body",
            provider=provider,
            model=model,
            status_code=response.status_code,
        )
