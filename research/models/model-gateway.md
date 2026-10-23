# Research: Model Gateway / Provider Proxy

- **Capability:** `model-gateway` (category: models)
- **Status:** `RESEARCHED` → `UNDERSTOOD`
- **Session:** Phase 5B.1
- **Date:** 2026-10-23
- **Decision:** [ADR-0039](../../docs/decisions/0039-model-gateway.md) (to be created)

Claims are labelled per charter §6:
**FACT** (verified against a primary source, cited) · **OBSERVATION** (read from
docs/source) · **INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice).

---

## 1. The problem, stated without reference to any implementation

> When a system calls more than one model or provider, every caller re-implements
> provider selection, fallback, retry, load balancing, cost accounting and
> health tracking. None of these concerns belong in the model provider
> abstraction (ADR-0007): that layer owns *shape*, not *routing*.

Stated that way the problem decomposes into a **routing** concern, a **reliability**
concern, and an **accounting** concern:

| Concern | Question | Belongs to |
|---|---|---|
| **Provider registration** | Which providers/models are available, with what capabilities, cost, limits? | the gateway |
| **Routing strategy** | Given a request, which deployment serves it? | the gateway |
| **Fallback** | If a deployment fails, what is tried next? | the gateway |
| **Retry** | How many times, with what backoff? | the gateway |
| **Load balancing** | How is traffic spread across deployments of one model? | the gateway |
| **Circuit breaking** | When is a failing deployment temporarily removed? | the gateway (or reliability layer) |
| **Cost tracking** | How many tokens, at what price, against which budget? | the gateway |
| **Health checks** | Is a deployment alive before routing to it? | the gateway |
| **Wire encoding** | What JSON goes on the socket? | a provider adapter (ADR-0007) |
| **Normalisation** | How is a response flattened? | the model provider (ADR-0007) |

**INFERENCE — the load-bearing insight:** the gateway owns *routing*, not the
*socket* and not the *shape*. It composes `ModelProvider` (ADR-0007) and an
injected transport; it never replaces either. This mirrors ADR-0007's
"owns shape, not socket" split, one layer up.

---

## 2. Constraints

| Constraint | Source | Consequence |
|---|---|---|
| **Zero runtime dependencies** | ADR-0003 | No redis, no httpx, no pydantic. State in-memory (or injected store). |
| **Component independence** | charter §31 | No agent loop, no registry, no network required to import/type-check. |
| **No model calls in core** | charter §18 | Routing logic testable against canned outcomes. |
| **Python + mypy strict** | charter §13 | Fully annotated. |
| **Verifiable without network** | charter §18 | Provider quirks testable against canned payloads. |
| **Composes ModelProvider** | ADR-0007 | Gateway calls `ModelCaller`/provider adapters; never re-implements normalisation. |

---

## 3. Surveyed systems

### 3.1 LiteLLM (router + proxy)

- **FACT (docs.litellm.ai/docs/proxy/architecture):** The proxy runs auth/budget
  checks (virtual key, cache-first then DB), rate limiting (rpm/tpm per key/user/team/server),
  then the Router (load balancing, fallbacks, retries), then provider translation via the
  litellm SDK. Spend logging and rate-limit accounting run as async background tasks after
  the response is returned.
- **FACT (docs.litellm.ai/docs/routing):** Routing strategies: `simple-shuffle` (default,
  weighted pick), least-busy, usage-based-routing (async), latency-based, cost-based,
  custom. Cooldowns: 429 → 5s, >50% failures in a minute → 5s, non-retryable (401/404/408) → 5s.
- **FACT (docs.litellm.ai/docs/proxy/load_balancing):** Deployment `order` (lower = higher
  priority) with automatic escalation; `enable_weighted_failover` retries inside a model group
  before cross-group fallbacks; session affinity pins a conversation to one deployment.
- **OBSERVATION:** LiteLLM owns the transport and the provider SDKs (14 base deps incl.
  `boto3`); it is the "owns socket" family. Its routing logic is the useful part; its
  dependency weight is not.
- **INFERENCE:** The useful, liftable ideas are: model groups (deployments sharing a
  `model_name`), strategy enum, cooldown with recovery, `order`-based priority escalation,
  fallback chains (intra-group retries vs cross-group fallbacks), and post-response accounting.

### 3.2 Portkey

- **OBSERVATION (from implementation plan research targets):** Unified API, caching,
  guardrails, prompt management, 200+ models. Adds a *config* layer (provider + model + params)
  on top of routing.
- **INFERENCE:** We do not need Portkey's hosted gateway; the liftable idea is the
  *provider registry entry* shape (capabilities, models, cost, rate limits) and the
  fallback-chain config.

### 3.3 OpenRouter / Vercel AI Gateway / Kong

- **OBSERVATION:** OpenRouter is simple routing over community models; Vercel AI Gateway
  adds edge caching and frontend integration; Kong/Azure/IBM are enterprise gateways.
- **INFERENCE:** For a stdlib-only, zero-dep library these are out of scope as *products*;
  their *ideas* (model aliasing, fallback chains, cost-based routing) are in scope.

### 3.4 Existing in-repo primitives

- **FACT (catalog/models/model_provider):** `ModelProvider` owns shape; `ModelCaller`
  protocol (`call(messages, *, system, tools) -> ChatResponse`) is the seam. `Transport`
  is injected.
- **FACT (catalog/reliability):** `RateLimiter`, `CircuitBreaker`, `RetryPolicy` are
  DECIDED (DW-017) and depend on the gateway. So the gateway must expose hooks, not
  own the policies.
- **FACT (catalog/observability):** `TraceRecorder` records steps; gateway can emit
  trace records optionally.

---

## 4. Findings (the things that force design)

1. **Routing is a pure function over (request, registry, strategy, health).** No network,
   no model, no provider SDK required to compute a route. This is what makes it testable
   without network (charter §18).
2. **Fallbacks have two scopes.** Intra-group (retry on another deployment of the same
   model) vs cross-group (move to a different model). Conflating them loses the "try
   all peers first" behaviour that weighted failover needs.
3. **Cooldown is per-deployment, not per-model.** A single bad Azure region must not
   poison all Azure deployments of that model.
4. **Cost tracking is post-response.** Token counts arrive in the response, so accounting
   must run after the call returns (LiteLLM's async background tasks). In a sync,
   zero-dep library this means a synchronous post-call hook, not a background task.
5. **Rate limiting splits into two.** Routing uses rpm/tpm as *hints* (pick a deployment
   with capacity); enforcement uses them as *hard limits*. The reliability layer (5B.4)
   owns enforcement; the gateway only consults hints.
6. **Health checks are optional and injected.** A library cannot probe a provider's
   `/health` endpoint without network and a configured URL; health is therefore an
   injected `HealthCheck` callable, defaulting to "assume healthy".

---

## 5. What we will NOT build

- A hosted proxy server / HTTP listener (out of scope; this is a library).
- Virtual keys, teams, budgets, DB-backed accounting (out of scope; no DB).
- Provider SDK integration (stays in `model_provider` adapters).
- Async (sync-first, matching `react-agent-loop`; async is a later addition).
- Streaming routing decisions (route once per request; streaming is the provider's job).

---

## 6. Proposed capability shape (for the spec)

- `Gateway` protocol: `chat(request) -> ChatResponse`, `stream(request) -> Iterator[StreamDelta]`
- `ProviderRegistry`: register providers with capabilities, models, cost, rate limits
- `RoutingStrategy` enum + implementations: `Priority`, `RoundRobin`, `LeastBusy`, `LatencyBased`, `CostBased`, `SimpleShuffle` (default)
- `Router`: picks a deployment given a request + registry + health
- `FallbackChain`: ordered list of model groups to try
- `CircuitBreaker` hook: injected (owned by reliability layer, 5B.4)
- `CostTracker`: token counting, per-model pricing, budget alerts
- `HealthCheck`: injected callable
- Integration: wraps `ModelProvider` adapters; emits `TraceRecorder` events optionally

---

## 7. Open questions (to resolve in the spec)

- Q1: Does the gateway own model *aliasing* (map `gpt-6.1-sol` → `gpt-6-luna`)? Proposed: yes, in the registry.
- Q2: Does the gateway expose a `batch()` for batched completions? Proposed: defer (Portkey feature, low priority).
- Q3: How does the gateway interact with `RateLimiter` (5B.4)? Proposed: gateway consults `acquire()` before routing; reliability layer owns the limiter.
- Q4: Streaming: route once, then stream from the chosen deployment. Proposed: yes.

---

## 8. Decision

**DESIGN OPINION:** IMPLEMENT a `model-gateway` capability that owns routing, fallback,
load balancing, cost tracking and health-check hooks, composing `ModelProvider` and
an injected transport, with zero runtime dependencies. Rate limiting and circuit
breaking remain in the reliability layer (5B.4) and are injected as hooks.

See ADR-0039.
