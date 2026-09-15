"""Provider-agnostic errors.

The taxonomy exists so a caller can branch on a *structured* signal rather than
inspecting a message string. ADR-0007 D-4 requires that ``retryable`` be derived
from status code and provider-specific rules only -- never from message text.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any


class ErrorKind(enum.Enum):
    """Why a call failed, by what the *caller* can do about it."""

    RATE_LIMIT = "rate_limit"
    """The provider is throttling. Often retryable after a delay."""

    CONTEXT_LENGTH = "context_length"
    """The request exceeded the model's context window. Never retryable as-is:
    the caller must shorten the input."""

    AUTHENTICATION = "authentication"
    """Credentials missing, invalid, or lacking permission. Never retryable:
    retrying with the same credentials cannot succeed."""

    CONTENT_POLICY = "content_policy"
    """The provider refused on policy grounds. Never retryable: an identical
    request is refused identically."""

    TRANSPORT = "transport"
    """The connection failed before a response. Retryable."""

    TIMEOUT = "timeout"
    """The request timed out. Retryable."""

    BAD_REQUEST = "bad_request"
    """The request was malformed or unsupported. Never retryable."""

    SERVER = "server"
    """The provider failed. Usually retryable."""

    UNKNOWN = "unknown"
    """Unclassified. Treated as NOT retryable by default, because retrying an
    unrecognised failure can turn one error into a retry storm."""


# Retryability is a property of the *kind* in every case except RATE_LIMIT,
# which depends on whether the provider offered a usable delay.
_RETRYABLE_KINDS = frozenset({ErrorKind.TRANSPORT, ErrorKind.TIMEOUT, ErrorKind.SERVER})


class ProviderError(Exception):
    """The root failure type for every provider interaction.

    Attributes:
        kind: What went wrong, by caller-actionable category.
        message: A sanitised description safe for logs and prompts. It must not
            contain a raw response body or a header dump -- provider bodies can
            echo request content and occasionally credentials.
        provider: The provider name, e.g. ``"openai"``.
        model: The model that was requested.
        status_code: The HTTP status, when there was one.
        request_id: The provider's request id. This is the only handle for
            resolving a vendor-side incident, so it is always propagated.
        retry_after: Seconds to wait, when the provider said so.
        retryable: Whether a later identical attempt could plausibly succeed.
    """

    kind: ErrorKind = ErrorKind.UNKNOWN

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        model: str = "",
        status_code: int | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.request_id = request_id
        self.retry_after = retry_after
        # Default from the kind. RATE_LIMIT passes an explicit value because a
        # spend-cap 429 is retryable in shape but never in practice.
        self.retryable = (
            self.kind in _RETRYABLE_KINDS if retryable is None else retryable
        )

    @property
    def retry_hint(self) -> str:
        """A short human/model-readable summary of what to do next."""
        if self.kind is ErrorKind.RATE_LIMIT:
            if self.retryable:
                delay = (
                    f" after {self.retry_after:g}s"
                    if self.retry_after is not None
                    else ""
                )
                return f"rate limited; retry{delay}"
            return "rate limited and not retryable (quota or spend cap)"
        if self.kind is ErrorKind.CONTEXT_LENGTH:
            return "input too long; shorten it before retrying"
        if self.kind is ErrorKind.AUTHENTICATION:
            return "credentials rejected; fix them, do not retry"
        if self.kind is ErrorKind.CONTENT_POLICY:
            return "refused on policy grounds; do not retry"
        return "retryable" if self.retryable else "not retryable"

    def __str__(self) -> str:
        parts = [f"{self.provider}:{self.model}" if self.provider else "provider"]
        if self.status_code is not None:
            parts.append(f"HTTP {self.status_code}")
        parts.append(self.kind.value)
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return " ".join(parts) + f": {self.message}"


class RateLimitError(ProviderError):
    """Throttled, or out of quota."""

    kind = ErrorKind.RATE_LIMIT


class ContextLengthError(ProviderError):
    """The context window was exceeded."""

    kind = ErrorKind.CONTEXT_LENGTH


class AuthenticationError(ProviderError):
    """Credentials were rejected."""

    kind = ErrorKind.AUTHENTICATION


class ContentPolicyError(ProviderError):
    """The provider refused on policy grounds."""

    kind = ErrorKind.CONTENT_POLICY


class TransportError(ProviderError):
    """The connection failed before a response was received."""

    kind = ErrorKind.TRANSPORT


class ProviderTimeoutError(ProviderError):
    """The request timed out."""

    kind = ErrorKind.TIMEOUT


class BadRequestError(ProviderError):
    """The request was rejected as malformed or unsupported."""

    kind = ErrorKind.BAD_REQUEST


class ServerError(ProviderError):
    """The provider reported an internal failure."""

    kind = ErrorKind.SERVER


class TranslationError(ValueError):
    """A neutral request cannot be expressed on the target provider.

    This is the mechanism for ADR-0007 D-7: lossy translation is *declared*,
    never silent. It is raised before any bytes are sent, so a caller learns at
    the boundary rather than receiving a subtly wrong answer.

    It is a ``ValueError`` because it signals a problem in the caller's request,
    not a provider outage.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        feature: str = "",
        remedy: str = "",
    ) -> None:
        self.provider = provider
        self.feature = feature
        self.remedy = remedy
        detail = message
        if remedy:
            detail = f"{detail} Remediation: {remedy}"
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class ErrorSignals:
    """Structured inputs to error classification.

    Passing explicit values rather than a parsed message enforces D-4:
    classification can only use status, body, and provider. There is
    deliberately no way to hand it a message string to pattern-match.
    """

    provider: str
    model: str
    status_code: int | None = None
    body: Any = None
    retry_after: float | None = None
    transport_failed: bool = False
    timed_out: bool = False
