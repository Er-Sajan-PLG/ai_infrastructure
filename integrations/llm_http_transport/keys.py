"""Resolve provider API keys from the environment (ADR-0028).

Why this module exists rather than living in the catalog
--------------------------------------------------------
ADR-0007 D-1 forbids the abstraction from reading an environment variable for
an API key: the catalog owns *shape* and must stay importable with no ambient
authority. Key resolution is therefore caller business, and this integration
is the caller. The mapping is exactly one variable per provider, looked up by
the provider's neutral name, so a caller writes ``resolve_api_key("openai")``
rather than scattering ``os.environ`` reads across call sites.
"""

from __future__ import annotations

import os

__all__ = ["PROVIDER_ENV_VARS", "MissingApiKeyError", "resolve_api_key"]

#: Provider neutral name -> environment variable holding its API key.
PROVIDER_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class MissingApiKeyError(RuntimeError):
    """An API key is absent from the environment.

    Raised instead of ``KeyError`` so the failure names the variable *and* the
    remedy in one message. The message never contains a key: this error is
    raised precisely when there is nothing safe to print, and keeping that
    invariant unconditional means no future edit can leak one.
    """


def resolve_api_key(provider: str) -> str:
    """Return the API key for ``provider`` from its environment variable.

    Args:
        provider: A neutral provider name (``"openai"``, ``"anthropic"``,
            ``"gemini"``; matched case-insensitively).

    Returns:
        The key with surrounding whitespace removed.

    Raises:
        ValueError: ``provider`` names no known provider.
        MissingApiKeyError: The variable is unset or blank.
    """
    name = provider.lower()
    if name not in PROVIDER_ENV_VARS:
        raise ValueError(
            f"unknown provider {provider!r}; expected one of "
            f"{', '.join(sorted(PROVIDER_ENV_VARS))}"
        )
    variable = PROVIDER_ENV_VARS[name]
    value = os.environ.get(variable, "").strip()
    if not value:
        raise MissingApiKeyError(
            f"missing environment variable {variable} for provider {name!r}; "
            f"export {variable}='<key>' and retry"
        )
    return value
