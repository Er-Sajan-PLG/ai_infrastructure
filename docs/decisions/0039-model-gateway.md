# ADR-0039: Model Gateway / Provider Proxy (IMPLEMENT)

**Status:** Accepted
**Date:** 2026-10-23
**Drivers:** Charter §18 (honest evaluation), Phase 5B.1 of the implementation plan, ADR-0007 (model-provider-abstraction), ADR-0003 (zero runtime deps), ADR-0036 (production readiness)

## Context

The repository has a `model-provider-abstraction` capability (ADR-0007) that owns
*shape*, not the socket, and is TESTED. Components that call more than one model or
provider currently re-implement provider selection, fallback, retry, load
balancing, cost accounting and health tracking ad hoc. Phase 5B.1 of the
implementation plan brings a `model-gateway` capability into scope to centralise
these concerns. The reliability layer (5B.4 — rate limiting, circuit breaker) is
DECIDED and depends on the gateway exposing hooks rather than owning the policies.

## Decision

**IMPLEMENT** a `model-gateway` capability as a stdlib-only library component:

1. **Protocol-first design** — `Gateway` protocol: `chat(request) -> ChatResponse`,
   `stream(request) -> Iterator[StreamDelta]`.
2. **Composes, does not replace** — the gateway calls `ModelProvider` adapters
   (ADR-0007) and an injected transport; it never re-implements normalisation or
   wire encoding.
3. **Provider registry** — `ProviderRegistry` holds providers with capabilities,
   models, cost, rate-limit hints.
4. **Routing strategies** — `Priority`, `RoundRobin`, `LeastBusy`, `LatencyBased`,
   `CostBased`, `SimpleShuffle` (default). A strategy is a pure function over
   (request, registry, health).
5. **Two scopes of fallback** — intra-group (retry on another deployment of the
   same model) vs cross-group (move to a different model). Weighted failover
   retries peers before escalating.
6. **Per-deployment cooldown** — a single bad deployment must not poison all
   deployments of a model. Cooldown with automatic recovery.
7. **Post-response accounting** — cost tracking runs after the call returns, since
   token counts arrive in the response. Synchronous hook, not a background task.
8. **Rate limiting is consultative** — the gateway consults rpm/tpm hints for
   routing; hard enforcement lives in the reliability layer (5B.4) and is injected.
9. **Circuit breaker is injected** — owned by the reliability layer; the gateway
   calls an injected `CircuitBreaker` hook.
10. **Health checks are injected** — default "assume healthy"; a library cannot
    probe a provider without network and a configured URL.
11. **Zero runtime dependencies** — stdlib only; no redis, no httpx, no pydantic.
    State is in-memory (or an injected store).
12. **No hosted proxy** — this is a library component, not an HTTP listener.
13. **Sync-first** — matches `react-agent-loop`; async is a later addition.

## Options Considered

| Option | Verdict | Reason |
|--------|---------|--------|
| **IMPLEMENT gateway (selected)** | ✅ | Centralises routing/fallback/cost; unblocks 5B.4 and real eval/guardrails |
| Defer (keep ad hoc routing) | ❌ | Every caller re-implements; inconsistent fallback behaviour |
| Adopt LiteLLM as dependency | ❌ | Violates ADR-0003 (14 base deps incl. boto3); owns the socket |
| Hosted proxy only | ❌ | Out of scope; this is a library |

## Consequences

- New catalog entry `catalog/models/gateway/` (to be implemented in the next session).
- New taxonomy entry `model-gateway` in `models` category at `DECIDED`.
- Research record at `research/models/model-gateway.md`.
- Specification at `specifications/model-gateway.md`.
- Unblocks: 5B.4 (Rate Limiting & Circuit Breaker), real eval/guardrails (DW-015).
- Does not change existing capabilities; composes them.

## Deferred

- Async API (later addition).
- Batch completions (Portkey feature, low priority).
- Virtual keys / teams / DB-backed accounting (out of scope).
- Hosted proxy server (out of scope).
