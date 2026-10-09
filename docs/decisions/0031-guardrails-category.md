# ADR-0031: Guardrails Category

**Status:** Accepted
**Date:** 2026-10-08
**Drivers:** Phase 3 Discover — convergence detection

## Context

Phase 3 convergence detection found that 10 of 25 studied repositories
independently proposed a `guardrails` category absent from the taxonomy tree.
The convergence across independent implementations is evidence that this
pattern exists in the ecosystem.

The taxonomy already has `safety/ (+governance/)` for safety and governance.
Guardrails are distinct: they are output-validation and moderation machinery
that sits between model output and the user, not governance policy.

## Decision

Add `guardrails/` as a new top-level taxonomy category:
- **Name:** Guardrails & Output Validation
- **Scope:** Output moderation, content filtering, response validation,
  safety classifiers, and policy enforcement on model outputs
- **Excludes:** Governance policy, human-in-the-loop approval (those are
  in `safety/`)

## Consequences

- The taxonomy tree grows by one category
- Pattern rules now correctly classify guardrails under `guardrails/`
  instead of incorrectly mapping to `safety/`
- No existing capabilities are affected (none have `category: guardrails`)

## Evidence

From `docs/discovery/2026-10-08-convergence.md`:
- `guardrails`: 10/25 repos (40%)
- Proposing repos: agno, ai, haystack, langfuse, litellm, mastra, openai-python,
  phidata, semantic-kernel, SWE-agent

## Rejected alternatives

- **Map to `safety/`:** Rejected — safety is about governance, policy, and
  guardrails for *agent actions*. Model output validation is a different
  concern with different machinery.
- **Defer:** Rejected — 40% convergence is strong evidence, and the category
  is well-bounded.
