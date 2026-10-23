# Specification: `model-gateway`

- **Capability id:** `model-gateway`
- **Name:** Model Gateway / Provider Proxy
- **Lifecycle status:** `DECIDED` — **IMPLEMENT** ([ADR-0039](../docs/decisions/0039-model-gateway.md))
- **Date:** 2026-10-23

## Problem statement and who needs it

When a system calls more than one model or provider, every caller re-implements
provider selection, fallback, retry, load balancing, cost accounting and health
tracking. The consumer is any component that needs to route a request across
deployments of one or more models. The gateway composes `ModelProvider` (ADR-0007)
and an injected transport; it never replaces them.

## Interfaces and data flow

```
request (model name + messages + params)
  -> Gateway.chat(request) -> ChatResponse
     1. resolve model alias -> model group
     2. consult rate-limit hints (injected RateLimiter.acquire)
     3. health check (injected HealthCheck)
     4. route: strategy picks a deployment
     5. call provider adapter -> ChatResponse
     6. on failure: retry within group (weighted failover) -> fallback chain
     7. cooldown update on failure
     8. post-response: cost tracking + trace emission
```

Key types:

- `GatewayRequest(model, messages, *, system, tools, params)` — neutral request.
- `Gateway` — `Protocol` with `chat(request) -> ChatResponse`,
  `stream(request) -> Iterator[StreamDelta]`.
- `ProviderEntry(name, capabilities, models, cost, rate_limits, health_check)` —
  registry entry.
- `ProviderRegistry` — `register(entry)`, `lookup(model) -> list[ProviderEntry]`,
  `alias(name, target)`.
- `RoutingStrategy` — enum: `PRIORITY`, `ROUND_ROBIN`, `LEAST_BUSY`,
  `LATENCY_BASED`, `COST_BASED`, `SIMPLE_SHUFFLE` (default).
- `Router` — `route(request, registry, health) -> ProviderEntry`.
- `FallbackChain` — ordered list of model groups to try.
- `CooldownTracker` — per-deployment cooldown with automatic recovery.
- `CostTracker` — token counting, per-model pricing, budget alerts.
- `HealthCheck` — `Protocol`: `is_healthy(entry) -> bool`.
- `CircuitBreaker` — injected hook (owned by reliability layer, 5B.4).

## Invariants

- Routing is a pure function over (request, registry, strategy, health). No network,
  no model call, no provider SDK required to compute a route.
- Fallbacks have two scopes: intra-group (retry on another deployment of the same
  model) and cross-group (move to a different model). Weighted failover retries
  peers before escalating.
- Cooldown is per-deployment, not per-model.
- Cost tracking runs after the call returns (post-response hook).
- Rate limiting is consultative: the gateway consults hints; hard enforcement is
  injected.
- Health checks default to "assume healthy".
- Zero runtime dependencies; stdlib only.

## Error and failure modes

- No healthy deployment available: raise `NoHealthyDeploymentError`.
- All fallbacks exhausted: raise `AllFallbacksExhaustedError`.
- Provider call failure: caught, recorded, cooldown updated, next deployment tried.
- Rate-limit hint denied: raise `RateLimitedError` (or skip, per policy).

## Concurrency / thread safety

- `ProviderRegistry` and `CooldownTracker` must be thread-safe (lock-based).
- `Router` is stateless aside from strategy state (round-robin counter).

## Test strategy

- Unit tests: routing strategies, fallback chains, cooldown, cost tracking, aliasing,
  all with canned data (no network).
- Integration: gateway wrapping a scripted `ModelProvider` adapter.
- Coverage floor: ≥90% on changed lines.

## Dependencies

- `model-provider-abstraction` (composes `ModelCaller`/adapters).
- `execution-trace-recorder` (optional trace emission).
- `reliability` (5B.4 — rate limiting, circuit breaker; injected as hooks).

## Out of scope

- Async API (later addition).
- Batch completions (deferred).
- Virtual keys / teams / DB-backed accounting.
- Hosted proxy server.
- Provider SDK integration (stays in `model_provider`).
