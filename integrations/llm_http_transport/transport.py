"""A real ``Transport`` over :mod:`urllib.request` (ADR-0028).

Why this module exists rather than extending a shipped double
------------------------------------------------------------
``model-provider-abstraction`` ships ``RecordingTransport``, which holds exactly
**one** canned response and returns it on every ``send``. That is the right
double for testing an adapter and useless for reaching a real provider: the
abstraction owns *shape* and by design never opens a socket (ADR-0007 D-1), so
without this module there is no path from :func:`chat` to a live model.

Implementing the protocol here is also this integration's own evidence that the
seam is real. This file imports ``model_provider``'s **public types only** --
never an internal -- and satisfies ``Transport`` structurally, without
subclassing it or asking the package for permission.

What this module does and does not do
-------------------------------------
It forwards ``WireRequest.method/url/headers/body`` to the network exactly
as given and returns the reply as a ``WireResponse``. In particular it does
**not**: retry (the caller owns retry policy -- ADR-0007 D-4), parse JSON,
interpret ``data: [DONE]`` or any other provider sentinel, raise on a non-2xx
status in :meth:`send` (status is data; classification is the adapter's job),
or log headers or bodies (bodies can echo credentials).

A non-2xx status on :meth:`stream` open raises :class:`TransportError`
carrying the status code. The streaming return type is lines, so there is no
channel for status-as-data, and feeding an error JSON body into the SSE parser
would fail silently downstream. This is a stated limit, documented in the
integration README.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from model_provider import (
    ProviderTimeoutError,
    Transport,
    TransportError,
    WireRequest,
    WireResponse,
)

__all__ = ["DEFAULT_TIMEOUT", "UrllibTransport"]

#: Default socket timeout, in seconds. Explicit and overridable per instance;
#: there is no global to mutate and no environment variable to discover.
DEFAULT_TIMEOUT = 30.0


class UrllibTransport:
    """Sends ``WireRequest`` values over HTTPS with :mod:`urllib.request`.

    Attributes:
        timeout: Seconds to wait for connect and read before the request
            fails as :class:`ProviderTimeoutError`.
    """

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout!r}")
        self.timeout = timeout

    def send(self, request: WireRequest) -> WireResponse:
        """Send one request and return the full response.

        A non-2xx status is returned, not raised. Connection problems raise
        :class:`TransportError` and timeouts raise
        :class:`ProviderTimeoutError`; no raw stdlib exception escapes.
        """
        self._require_http_url(request.url)
        outgoing = self._build(request)
        try:
            # _require_http_url() above restricts the URL to http/https before
            # this call, so Bandit's B310 scheme warning is intentionally
            # suppressed only at this guarded call site.
            with urllib.request.urlopen(  # nosec B310 -- _require_http_url restricts schemes to http/https  # noqa: S310
                outgoing, timeout=self.timeout
            ) as reply:
                return WireResponse(
                    status_code=reply.status,
                    headers=dict(reply.headers.items()),
                    body=reply.read(),
                )
        except urllib.error.HTTPError as exc:
            # Status is data, not failure: hand the adapter the error reply
            # exactly as received so it can classify it (ADR-0007 D-4).
            # The error object wraps a file; it is closed here so no
            # unclosed-file warning escapes to whoever collects this call.
            body = exc.read()
            headers = dict(exc.headers.items()) if exc.headers else {}
            exc.close()
            return WireResponse(
                status_code=exc.code,
                headers=headers,
                body=body,
            )
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            raise self._as_provider_error(request, exc) from exc

    def stream(self, request: WireRequest) -> Iterator[str]:
        """Send one request and yield raw response lines until EOF.

        Lines are yielded **with** their line endings intact; the SSE reader
        strips them itself, so stripping here would destroy information about
        blank-line event boundaries. May raise mid-iteration with
        :class:`TransportError` / :class:`ProviderTimeoutError` (ADR-0007 D-9).
        """
        self._require_http_url(request.url)
        outgoing = self._build(request)
        try:
            # _require_http_url() above restricts the URL to http/https before
            # this call, so Bandit's B310 scheme warning is intentionally
            # suppressed only at this guarded call site.
            reply = urllib.request.urlopen(  # nosec B310 -- _require_http_url restricts schemes to http/https  # noqa: S310
                outgoing, timeout=self.timeout
            )
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise TransportError(
                f"stream request failed with HTTP {code}",
                status_code=code,
            ) from exc
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            raise self._as_provider_error(request, exc) from exc
        return self._read_lines(reply, request)

    @staticmethod
    def _build(request: WireRequest) -> urllib.request.Request:
        """Encode a ``WireRequest`` as a :mod:`urllib` request, header for header.

        Headers pass through untouched: credentials already live in them (the
        adapter put them there via ``build_request``), and this layer must
        neither add auth scheme knowledge nor drop anything the adapter set.
        """
        return urllib.request.Request(  # noqa: S310 -- scheme already restricted by _require_http_url
            request.url,
            data=request.body,
            headers=dict(request.headers),
            method=request.method,
        )

    @staticmethod
    def _require_http_url(url: str) -> None:
        """Reject non-HTTP(S) URLs before they reach :mod:`urllib`.

        ``urlopen`` also speaks ``file:`` and custom schemes; handing it an
        unchecked URL would turn a confused caller into a local-file reader.
        Providers build ``https:`` URLs, so anything else is a caller bug,
        reported as :class:`TransportError` (retrying an identical URL cannot
        succeed, which is exactly what that classification means).
        """
        scheme = urllib.parse.urlsplit(url).scheme.lower()
        if scheme not in ("http", "https"):
            raise TransportError(
                f"refusing non-HTTP(S) request URL with scheme {scheme!r}"
            )

    @staticmethod
    def _read_lines(reply: Any, request: WireRequest) -> Iterator[str]:
        """Yield decoded lines, closing the reply whatever happens."""
        try:
            for raw in reply:
                try:
                    yield raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise TransportError(
                        f"undecodable bytes in {request.method} response",
                    ) from exc
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            raise UrllibTransport._as_provider_error(request, exc) from exc
        finally:
            reply.close()

    @staticmethod
    def _as_provider_error(
        request: WireRequest, exc: BaseException
    ) -> TransportError | ProviderTimeoutError:
        """Classify a stdlib failure without leaking request internals.

        The message names the method and host only. Headers carry credentials
        and bodies can echo request content, so neither ever appears here.
        A timeout wrapped as ``URLError(reason=TimeoutError(...))`` is still a
        timeout: ``urlopen`` wraps inconsistently across failure modes, so both
        the direct and the wrapped shape are recognised.
        """
        host = urllib.parse.urlsplit(request.url).hostname or request.url
        if isinstance(exc, TimeoutError) or (
            isinstance(exc, urllib.error.URLError)
            and isinstance(exc.reason, TimeoutError)
        ):
            return ProviderTimeoutError(
                f"{request.method} {host} timed out after the configured timeout",
            )
        return TransportError(f"{request.method} {host} connection failed")


if TYPE_CHECKING:
    # mypy checks structural conformance to the Transport protocol right here.
    # It must sit BELOW the class: the annotation evaluates the class object, so
    # placing it above the definition is a used-before-definition error, not a
    # stylistic preference (found by mypy, not by review).
    _CONFORMS_TO_TRANSPORT: type[Transport] = UrllibTransport
