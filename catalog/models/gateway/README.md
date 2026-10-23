# Model Gateway

> **Status: `TESTED`.** Routing, fallback, load balancing, cost tracking, cooldown and health checks across providers. Zero runtime dependencies — standard library only; composes `ModelProvider` (ADR-0007).

| | |
|---|---|
| **Capability** | [`model-gateway`](../../../TAXONOMY.md) (category: models) |
| **Specification** | [`specifications/model-gateway.md`](../../../specifications/model-gateway.md) |
| **Decision** | [ADR-0039](../../../docs/decisions/0039-model-gateway.md) — `IMPLEMENT` |
| **Research** | [`research/models/model-gateway.md`](../../../research/models/model-gateway.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — original |

## What it is

A stdlib-only model gateway: `ProviderRegistry` holds deployments (model groups),
a `Router` picks a deployment per strategy (simple-shuffle, priority, round-robin,
least-busy, latency-based, cost-based), `DefaultGateway` executes with intra-group
retry (weighted failover) and cross-group fallback chains, per-deployment cooldown,
injected health checks and circuit breakers, and post-response cost tracking.
Model-backed classification, async, and a hosted proxy are out of scope.

## How it works

```python
from gateway import (
    DefaultGateway,
    GatewayConfig,
    InMemoryProviderRegistry,
    ProviderBundle,
    ProviderEntry,
    make_request,
)
from model_provider import Message, Role, TextBlock
from model_provider.providers import OpenAIProvider
from model_provider.transport import RecordingTransport

registry = InMemoryProviderRegistry()
registry.register(ProviderEntry(name="e0", provider="openai", model="m"))
bundle = ProviderBundle(
    provider=OpenAIProvider(),
    transport=RecordingTransport(response=...),
    api_key="k",
)
gw = DefaultGateway(GatewayConfig(registry=registry, providers={"openai": bundle}))
response = gw.chat(make_request("m", [Message(Role.USER, (TextBlock("hi"),))]))
```

**Design decisions:**

- **Protocol-first** — `Gateway`, `HealthCheck`, `CircuitBreaker`, `ProviderRegistry` are Protocols.
- **Composes, doesn't replace** — calls `ModelProvider` adapters; never re-implements shape or socket.
- **Routing is pure** — selection is a function of (request, registry, health); testable without network.
- **Two scopes of fallback** — intra-group retry (weighted failover) then cross-group fallback chain.
- **Per-deployment cooldown** — one bad deployment does not poison the model group.
- **Post-response accounting** — cost tracking runs after the call returns.
- **Rate limiting consultative** — hints for routing; hard enforcement injected (reliability layer).
- **Zero runtime dependencies** — stdlib only.

## Our implementations

| Implementation | Language | Notes |
|---|---|---|
| [`protocols.py`](protocols.py) | Python | `Gateway`, `GatewayRequest`, `ProviderEntry`, `ProviderRegistry`, `RoutingStrategy`, `Router`, `CooldownTracker`, `CostTracker`, `HealthCheck`, `CircuitBreaker`, errors |
| [`registry.py`](registry.py) | Python | `InMemoryProviderRegistry` |
| [`gateway.py`](gateway.py) | Python | `DefaultGateway`, `GatewayConfig`, `ProviderBundle` |

## References

- [LiteLLM](https://github.com/BerriAI/litellm) — routing strategies, cooldown, weighted failover
- [Portkey](https://portkey.ai) — provider registry shape, fallback chains
- [OpenRouter](https://openrouter.ai) — model aliasing
- [Vercel AI Gateway](https://vercel.com/docs/ai-gateway) — edge caching (out of scope)
