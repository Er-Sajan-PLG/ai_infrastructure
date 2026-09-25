#!/usr/bin/env python3
"""A runnable tour of the LLM HTTP transport.

Demonstrates the full path from a neutral request to a live model and back:
resolve a key from the environment, build a neutral ``ChatRequest``, encode it
with the real OpenAI adapter, send it over the real stdlib transport, and read
back neutral text.

Run offline by default::

    python integrations/llm_http_transport/examples/quickstart.py

The live call requires an explicit opt-in as well as ``OPENAI_API_KEY``::

    AI_INFRASTRUCTURE_LIVE_TEST=1 python integrations/llm_http_transport/examples/quickstart.py

Without the opt-in, this prints instructions and exits 0 without network I/O,
even if a key is present. No dependencies beyond the standard library.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for _sub in ("catalog/models", "integrations"):
    sys.path.insert(0, str(_ROOT / _sub))

from llm_http_transport.keys import MissingApiKeyError, resolve_api_key  # noqa: E402
from llm_http_transport.transport import UrllibTransport  # noqa: E402
from model_provider import ChatRequest, Message, Role, TextBlock, chat  # noqa: E402
from model_provider.providers import OpenAIProvider  # noqa: E402


def build_demo_request() -> ChatRequest:
    """The request the live call would send: one user turn, no tools."""
    return ChatRequest(
        model="gpt-4o-mini",
        messages=[
            Message(
                role=Role.USER,
                content=(TextBlock(text="Say hello in one short sentence."),),
            )
        ],
    )


def main() -> None:
    if os.environ.get("AI_INFRASTRUCTURE_LIVE_TEST") != "1":
        print(  # noqa: T201 -- quickstart instructions are terminal output
            "Live provider calls are disabled by default. To enable the live "
            "quickstart, set AI_INFRASTRUCTURE_LIVE_TEST=1 and provide "
            "OPENAI_API_KEY."
        )
        return

    provider = OpenAIProvider()
    transport = UrllibTransport(timeout=30.0)
    request = build_demo_request()

    try:
        api_key = resolve_api_key("openai")
    except MissingApiKeyError as exc:
        # Offline demo: show the exact bytes that WOULD go out, then stop.
        # Nothing here touches the network; exiting 0 keeps the example
        # runnable in every environment, key or no key.
        wire = provider.build_request(request, api_key="<redacted>")
        lines = [
            f"{exc}",
            "",
            "Would send (key redacted):",
            f"  {wire.method} {wire.url}",
            f"  headers: {sorted(wire.headers)}",
            f"  body: {len(wire.body)} bytes",
            "",
            "Set the key to make the live call:",
            "  export OPENAI_API_KEY='<key>'",
        ]
        print("\n".join(lines))  # noqa: T201 -- demo output
        return

    # The key travels env -> memory -> request headers only: it is never
    # printed, logged, or written anywhere in this example.
    response = chat(request, provider=provider, transport=transport, api_key=api_key)
    lines = [
        f"model: {response.model}",
        f"finish: {response.finish_reason.value}",
    ]
    if response.usage is not None:
        lines.append(f"usage: {response.usage}")
    lines += ["", response.text]
    print("\n".join(lines))  # noqa: T201 -- demo output


if __name__ == "__main__":
    main()
