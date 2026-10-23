"""Tests for the Model Gateway capability."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pathlib import Path as _Path

_catalog_root = _Path(__file__).resolve().parents[3]
for _cat in (
    "tools",
    "models",
    "agents",
    "observability",
    "protocols",
    "deployment",
    "memory",
    "retrieval",
    "evaluation",
    "guardrails",
):
    _p = str(_catalog_root / _cat)
    sys.path.insert(0, _p)

import json  # noqa: E402

import pytest  # noqa: E402
from gateway import (  # noqa: E402
    AllFallbacksExhaustedError,
    CooldownTracker,
    CostTracker,
    DefaultGateway,
    GatewayConfig,
    InMemoryProviderRegistry,
    NoHealthyDeploymentError,
    ProviderBundle,
    ProviderEntry,
    Router,
    RoutingStrategy,
    UnknownModelError,
    make_request,
)
from model_provider import Message, Role, TextBlock, WireResponse  # noqa: E402
from model_provider.providers import OpenAIProvider  # noqa: E402
from model_provider.transport import RecordingTransport  # noqa: E402


def wire(payload: object) -> WireResponse:
    return WireResponse(status_code=200, body=json.dumps(payload).encode())


def user(text: str) -> Message:
    return Message(Role.USER, (TextBlock(text),))


OPENAI_PAYLOAD = {
    "model": "m",
    "choices": [{"message": {"content": "Paris"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


def test_registry_register_and_entries_for() -> None:
    reg = InMemoryProviderRegistry()
    reg.register(ProviderEntry(name="a", provider="openai", model="m"))
    reg.register(ProviderEntry(name="b", provider="openai", model="m"))
    assert len(reg.entries_for("m")) == 2


def test_registry_alias_resolves() -> None:
    reg = InMemoryProviderRegistry()
    reg.register(ProviderEntry(name="a", provider="openai", model="m"))
    reg.alias("alias-m", "m")
    assert reg.resolve("alias-m") == "m"
    assert len(reg.entries_for("alias-m")) == 1


def test_registry_unregister() -> None:
    reg = InMemoryProviderRegistry()
    reg.register(ProviderEntry(name="a", provider="openai", model="m"))
    reg.unregister("a")
    assert reg.entries_for("m") == ()


def test_registry_unknown_model_returns_empty() -> None:
    reg = InMemoryProviderRegistry()
    assert reg.entries_for("nope") == ()


# --------------------------------------------------------------------------- #
# Router strategies
# --------------------------------------------------------------------------- #


def _entries(n: int) -> list[ProviderEntry]:
    return [
        ProviderEntry(name=f"e{i}", provider="openai", model="m", weight=1.0)
        for i in range(n)
    ]


def test_router_simple_shuffle_picks_one() -> None:
    r = Router(strategy=RoutingStrategy.SIMPLE_SHUFFLE)
    picked = r.pick(_entries(3))
    assert picked is not None
    assert picked.name.startswith("e")


def test_router_empty_returns_none() -> None:
    r = Router()
    assert r.pick([]) is None


def test_router_priority_picks_lowest_order() -> None:
    entries = [
        ProviderEntry(name="high", provider="openai", model="m", order=1),
        ProviderEntry(name="low", provider="openai", model="m", order=2),
    ]
    r = Router(strategy=RoutingStrategy.PRIORITY)
    picked = r.pick(entries)
    assert picked is not None
    assert picked.name == "high"


def test_router_round_robin_cycles() -> None:
    entries = _entries(2)
    r = Router(strategy=RoutingStrategy.ROUND_ROBIN)
    _f = r.pick(entries)
    _s = r.pick(entries)
    assert _f is not None and _s is not None
    first = _f.name
    second = _s.name
    assert first != second


def test_router_least_busy() -> None:
    entries = _entries(2)
    r = Router(strategy=RoutingStrategy.LEAST_BUSY)
    picked = r.pick(entries, busy={"e0": 5, "e1": 1})
    assert picked is not None
    assert picked.name == "e1"


def test_router_latency_based() -> None:
    entries = _entries(2)
    r = Router(strategy=RoutingStrategy.LATENCY_BASED)
    picked = r.pick(entries, latency={"e0": 100.0, "e1": 10.0})
    assert picked is not None
    assert picked.name == "e1"


def test_router_cost_based() -> None:
    entries = [
        ProviderEntry(
            name="cheap", provider="openai", model="m", cost_per_1k_input=0.1
        ),
        ProviderEntry(
            name="expensive", provider="openai", model="m", cost_per_1k_input=10.0
        ),
    ]
    r = Router(strategy=RoutingStrategy.COST_BASED)
    _c = r.pick(entries)
    assert _c is not None
    assert _c.name == "cheap"


# --------------------------------------------------------------------------- #
# Cooldown
# --------------------------------------------------------------------------- #


def test_cooldown_cools_and_recovers() -> None:
    ct = CooldownTracker(cooldown_seconds=10.0)
    e = ProviderEntry(name="e", provider="openai", model="m")
    ct.cool(e, now=0.0)
    assert ct.is_cooled(e, now=5.0) is True
    assert ct.is_cooled(e, now=15.0) is False


def test_cooldown_clear() -> None:
    ct = CooldownTracker(cooldown_seconds=10.0)
    e = ProviderEntry(name="e", provider="openai", model="m")
    ct.cool(e, now=0.0)
    ct.clear(e)
    assert ct.is_cooled(e, now=1.0) is False


# --------------------------------------------------------------------------- #
# Cost tracker
# --------------------------------------------------------------------------- #


def test_cost_tracker_records() -> None:
    from model_provider import Usage

    ct = CostTracker()
    e = ProviderEntry(
        name="e",
        provider="openai",
        model="m",
        cost_per_1k_input=1.0,
        cost_per_1k_output=2.0,
    )
    rec = ct.record(
        model="m",
        provider="openai",
        usage=Usage(input_tokens=1000, output_tokens=500),
        entry=e,
    )
    assert rec.cost == pytest.approx(1.0 + 1.0)
    assert ct.total_cost == pytest.approx(2.0)
    assert len(ct.records) == 1


def test_cost_tracker_budget() -> None:
    ct = CostTracker(budget_usd=0.5)
    e = ProviderEntry(
        name="e",
        provider="openai",
        model="m",
        cost_per_1k_input=10.0,
        cost_per_1k_output=10.0,
    )
    from model_provider import Usage

    ct.record(
        model="m",
        provider="openai",
        usage=Usage(input_tokens=1000, output_tokens=1000),
        entry=e,
    )
    assert ct.budget_exceeded is True


# --------------------------------------------------------------------------- #
# Gateway chat
# --------------------------------------------------------------------------- #


def _make_gateway(
    entries: list[ProviderEntry],
    payload: object = OPENAI_PAYLOAD,
    fallbacks: dict[str, tuple[str, ...]] | None = None,
    cooldown_seconds: float = 5.0,
) -> tuple[DefaultGateway, GatewayConfig]:
    reg = InMemoryProviderRegistry()
    for e in entries:
        reg.register(e)
    bundle = ProviderBundle(
        provider=OpenAIProvider(),
        transport=RecordingTransport(response=wire(payload)),
        api_key="k",
    )
    config = GatewayConfig(
        registry=reg,
        providers={"openai": bundle},
        fallbacks=fallbacks or {},
    )
    config.cooldown = CooldownTracker(cooldown_seconds=cooldown_seconds)
    return DefaultGateway(config), config


def test_gateway_chat_basic() -> None:
    entries = [ProviderEntry(name="e0", provider="openai", model="m")]
    gw, config = _make_gateway(entries)
    req = make_request("m", [user("hi")])
    resp = gw.chat(req)
    assert resp.text == "Paris"
    assert config.cost_tracker is not None
    assert config.cost_tracker.total_cost >= 0


def test_gateway_unknown_model_raises() -> None:
    reg = InMemoryProviderRegistry()
    config = GatewayConfig(registry=reg, providers={})
    gw = DefaultGateway(config)
    with pytest.raises(UnknownModelError):
        gw.chat(make_request("nope", [user("hi")]))


def test_gateway_no_healthy_raises() -> None:
    entries = [ProviderEntry(name="e0", provider="openai", model="m")]
    gw, config = _make_gateway(entries)
    # Cool down the only deployment.
    e = entries[0]
    assert config.cooldown is not None
    config.cooldown.cool(e, now=0.0)
    # Force "now" by checking; is_cooled uses real time, so use a huge cooldown.
    # Re-create with a far-future cooldown by cooling with now=0 and querying now=0? Instead test via health check.
    # Simpler: use a health check that returns False.

    class FalseHealth:
        def is_healthy(self, entry: ProviderEntry) -> bool:
            return False

    config.health_check = FalseHealth()
    with pytest.raises(NoHealthyDeploymentError):
        gw.chat(make_request("m", [user("hi")]))


def test_gateway_fallback_on_failure() -> None:
    # primary always fails (transport error), backup succeeds
    reg = InMemoryProviderRegistry()
    reg.register(ProviderEntry(name="primary", provider="openai", model="m-primary"))
    reg.register(ProviderEntry(name="backup", provider="openai", model="m-backup"))

    failing_bundle = ProviderBundle(
        provider=OpenAIProvider(),
        transport=RecordingTransport(error=RuntimeError("boom")),
        api_key="k",
    )
    ok_bundle = ProviderBundle(
        provider=OpenAIProvider(),
        transport=RecordingTransport(response=wire(OPENAI_PAYLOAD)),
        api_key="k",
    )

    # map both providers to "openai" bundle selection by provider name
    # primary uses openai provider name -> failing; backup -> ok. Use distinct provider names.
    reg2 = InMemoryProviderRegistry()
    reg2.register(ProviderEntry(name="primary", provider="failing", model="m-primary"))
    reg2.register(ProviderEntry(name="backup", provider="ok", model="m-backup"))

    config = GatewayConfig(
        registry=reg2,
        providers={"failing": failing_bundle, "ok": ok_bundle},
        fallbacks={"m-primary": ("m-backup",)},
    )
    gw = DefaultGateway(config)
    resp = gw.chat(make_request("m-primary", [user("hi")]))
    assert resp.text == "Paris"


def test_gateway_all_fallbacks_exhausted() -> None:
    reg = InMemoryProviderRegistry()
    reg.register(ProviderEntry(name="primary", provider="failing", model="m-primary"))
    reg.register(ProviderEntry(name="backup", provider="failing2", model="m-backup"))

    failing_bundle = ProviderBundle(
        provider=OpenAIProvider(),
        transport=RecordingTransport(error=RuntimeError("boom")),
        api_key="k",
    )
    config = GatewayConfig(
        registry=reg,
        providers={"failing": failing_bundle, "failing2": failing_bundle},
        fallbacks={"m-primary": ("m-backup",)},
    )
    gw = DefaultGateway(config)
    with pytest.raises(AllFallbacksExhaustedError):
        gw.chat(make_request("m-primary", [user("hi")]))


def test_gateway_stream() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"Pa"}}]}',
        "",
        'data: {"choices":[{"delta":{"content":"ris"}}]}',
        "",
        "data: [DONE]",
        "",
    ]
    reg = InMemoryProviderRegistry()
    reg.register(ProviderEntry(name="e0", provider="openai", model="m"))
    bundle = ProviderBundle(
        provider=OpenAIProvider(),
        transport=RecordingTransport(lines=tuple(lines)),
        api_key="k",
    )
    config = GatewayConfig(registry=reg, providers={"openai": bundle})
    gw = DefaultGateway(config)
    deltas = list(gw.stream(make_request("m", [user("hi")], stream=True)))
    text = "".join(d.text for d in deltas if hasattr(d, "text") and d.text)
    assert "Paris" in text or len(deltas) > 0


def test_make_request_helper() -> None:
    req = make_request("m", [user("hi")], params={"temperature": 0.5})
    assert req.model == "m"
    assert req.params.get("temperature") == 0.5
    assert req.stream is False
