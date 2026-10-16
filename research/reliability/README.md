# Rate Limiting & Retry Infrastructure

> **Status: first entry researched, decision recorded.** `rate-limiting` is `DECIDED` — `DEFER` ([ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md), DW-017). See its research record below.

## What it is

Rate limiting, retry with backoff, circuit breakers, throttling, and resilience patterns for AI API calls.

## Why it exists

Production AI systems must handle rate limits, transient failures, and provider outages gracefully. This machinery is cross-cutting: it protects a remote dependency's quota and shields callers from its failure behaviour. With no remote dependency, there is nothing to protect.

## How it works

Research artifacts live at `research/reliability/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6). The first record aggregated convergent evidence only; no per-implementation deep study was done, because the capability is deferred and the decision does not require one.

## Variants & types

- **Retry with backoff** — exponential backoff with jitter, honoring the provider error taxonomy's existing `retryable` flags (ADR-0007 D-4).
- **Token-bucket limiter** — client-side pacing against a provider quota.
- **Circuit breaker** — stop hammering a failing dependency; last resort, added only after the first two prove insufficient.

## Landscape

External projects surveyed via the study pipeline (structural analysis only, no code executed or reused); 6 of 25 studied repositories proposed this category ([ADR-0032](../../docs/decisions/0032-reliability-category.md): `SWE-agent`, `dspy`, `haystack`, `langchain`, `langfuse`, `litellm`). Registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) per the charter §11 schema.

## Our implementations

None — deferred. No remote calls exist to protect; see [`../../docs/DEFERRED.md`](../../docs/DEFERRED.md) DW-017 for the trigger.

## When to use / When not to use

- **Use** once real (network or metered) provider calls exist, as a caller-invoked policy — per `specifications/basic-rag-pipeline.md` D-4, retry ownership belongs to the caller, not the provider.
- **Do not use** against stubbed transports in tests, and do not weave it into providers: a provider that retries internally cannot be bounded by its caller.

## References & citations

- [Research record: rate-limiting](rate-limiting.md)
- [Specification: rate-limiting](../../specifications/rate-limiting.md)
- [ADR-0032](../../docs/decisions/0032-reliability-category.md) — taxonomy category
