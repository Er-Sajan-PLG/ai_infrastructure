# Caching

> **Status: first entry researched, decision recorded.** `response-cache` is `DECIDED` — `DEFER` ([ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md), DW-015). See its research record below.

## What it is

Caching of model responses, embeddings and tool results: cache-key derivation, eviction policy, TTL and invalidation, in-process versus persistent storage — specifically the AI form keyed on prompt + model + parameters that avoids a metered API call.

## Why it exists

An identical request billed twice is pure waste — but a cache keyed on the wrong inputs silently returns a wrong answer for a different prompt. The correctness property and the security property are the same: the key must include every input that changes the answer.

## How it works

Research artifacts live at `research/caching/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6). The first record aggregated convergent evidence only; no per-implementation deep study was done, because the capability is deferred and the decision does not require one.

## Variants & types

- **Response cache** (`response-cache`) — canonical-hash key (model, messages, parameters, tool set), in-process LRU with TTL first, persistent storage only after cross-process repetition is measured.

## Landscape

External projects surveyed via the study pipeline (structural analysis only, no code executed or reused); 14 of 25 studied repositories proposed this category after a false-positive fix ([convergence report](../../docs/discovery/2026-10-08-convergence.md): `agno`, `autogen`, `crewAI`, `dspy`, `haystack`, and 9 more). Registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) per the charter §11 schema.

## Our implementations

None — deferred. No code path in this repository makes a metered model call; see [`../../docs/DEFERRED.md`](../../docs/DEFERRED.md) DW-015 for the trigger.

## When to use / When not to use

- **Use** when identical requests are repeated against a billed endpoint and every input that changes the answer is known.
- **Do not use** when the caller mix is unknown or the retention boundary is unclear — a prompt cached across tenants leaks one tenant's content to another.

## References & citations

- [Research record: response-cache](response-cache.md)
- [Specification: response-cache](../../specifications/response-cache.md)
- [ADR-0023](../../docs/decisions/0023-caching-taxonomy-category.md) — taxonomy category
