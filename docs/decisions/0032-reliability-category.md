# ADR-0032: Reliability Category

**Status:** Accepted
**Date:** 2026-10-08
**Drivers:** Phase 3 Discover — convergence detection

## Context

Phase 3 convergence detection found that 6 of 25 studied repositories
independently proposed a `rate-limiting` category absent from the taxonomy tree.
The convergence across independent implementations is evidence that this
pattern exists in the ecosystem.

The taxonomy had no category for reliability infrastructure. Rate limiting,
retry policies, backoff strategies, and circuit breakers are distinct
machinery that every production AI system needs but no existing category
covered.

## Decision

Add `reliability/` as a new top-level taxonomy category:
- **Name:** Rate Limiting & Retry Infrastructure
- **Scope:** Rate limiting, retry with backoff, circuit breakers,
  throttling, and resilience patterns for AI API calls
- **Excludes:** Error handling within a model response (that is the
  provider's concern, surfaced through `model-provider-abstraction`)

## Consequences

- The taxonomy tree grows by one category
- Pattern rules now correctly classify rate-limiting under `reliability/`
  instead of having no match
- No existing capabilities are affected

## Evidence

From `docs/discovery/2026-10-08-convergence.md`:
- `rate-limiting`: 6/25 repos (24%)
- Proposing repos: SWE-agent, dspy, haystack, langchain, langfuse, litellm

## Rejected alternatives

- **Map to `models/`:** Rejected — rate limiting is not model-specific; it
  is a cross-cutting infrastructure concern.
- **Defer:** Rejected — 24% convergence is adequate evidence, and the
  category is well-bounded.
