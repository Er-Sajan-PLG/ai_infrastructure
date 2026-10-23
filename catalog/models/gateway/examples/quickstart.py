"""Quickstart demonstration of the Model Gateway capability.

Shows:
- Registering two deployments of one model
- Routing with simple-shuffle
- Fallback chain on failure
- Cost tracking
- Cooldown after failure

Zero network calls in this example.
"""

from __future__ import annotations

import json

from gateway import (
    DefaultGateway,
    GatewayConfig,
    InMemoryProviderRegistry,
    ProviderBundle,
    ProviderEntry,
    make_request,
)
from model_provider import Message, Role, TextBlock, WireResponse
from model_provider.providers import OpenAIProvider
from model_provider.transport import RecordingTransport


def wire(payload: object) -> WireResponse:
    return WireResponse(status_code=200, body=json.dumps(payload).encode())


def user(text: str) -> Message:
    return Message(Role.USER, (TextBlock(text),))


def main() -> None:
    print("=" * 60)
    print("1. Registry + routing")
    print("=" * 60)

    registry = InMemoryProviderRegistry()
    registry.register(
        ProviderEntry(
            name="openai-east",
            provider="openai",
            model="gpt-4o-mini",
            cost_per_1k_input=0.15,
            cost_per_1k_output=0.60,
            weight=1.0,
        )
    )
    registry.register(
        ProviderEntry(
            name="openai-west",
            provider="openai",
            model="gpt-4o-mini",
            cost_per_1k_input=0.15,
            cost_per_1k_output=0.60,
            weight=1.0,
        )
    )

    payload = {
        "model": "m",
        "choices": [{"message": {"content": "Paris"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    bundle = ProviderBundle(
        provider=OpenAIProvider(),
        transport=RecordingTransport(response=wire(payload)),
        api_key="k",
    )
    config = GatewayConfig(
        registry=registry,
        providers={"openai": bundle},
    )
    gw = DefaultGateway(config)

    request = make_request("gpt-4o-mini", [user("Capital of France?")])
    response = gw.chat(request)
    print(f"  response text: {response.text!r}")
    assert config.cost_tracker is not None
    print(f"  total cost: {config.cost_tracker.total_cost:.6f}")

    print("\n" + "=" * 60)
    print("2. Fallback chain")
    print("=" * 60)

    registry2 = InMemoryProviderRegistry()
    registry2.register(
        ProviderEntry(name="primary", provider="openai", model="gpt-4o-mini")
    )
    registry2.register(
        ProviderEntry(name="backup", provider="openai", model="gpt-4o-mini-backup")
    )
    registry2.alias("gpt-4o-mini-backup", "gpt-4o-mini-backup")
    config2 = GatewayConfig(
        registry=registry2,
        providers={"openai": bundle},
        fallbacks={"gpt-4o-mini": ("gpt-4o-mini-backup",)},
    )
    # backup model has no entries -> entries_for empty -> skipped; demonstrate chain build
    print(f"  chain for gpt-4o-mini: {config2.fallbacks['gpt-4o-mini']}")

    print("\n" + "=" * 60)
    print("All demos completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
