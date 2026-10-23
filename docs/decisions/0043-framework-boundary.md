# ADR-0043: Framework Boundary (What ai_infrastructure Is Not)

**Status:** Accepted
**Date:** 2026-10-23
**Drivers:** Phase 7 of the stabilization sequence; audit finding F-scope-drift;
charter §1, §3, §4

## Context

The repository already ships `react-agent-loop`, a memory framework, an
evaluation framework, integrations, and (planned) orchestration, prompt
management, MCP server, skills, and harnesses. Without an explicit boundary,
the project risks drifting into "another agent framework" — duplicating work
that belongs to consumers (JARVIS, PROFESSOR-J, LearningHub) and blurring
the line between infrastructure primitives and application policy.

## Decision

**ai_infrastructure is an infrastructure layer. It provides reusable
primitives and infrastructure contracts. It does NOT own:**

1. Application policy (what an agent should do, when, for whom).
2. User-facing agent behavior (prompts, personas, UX, conversation state).
3. Orchestration authority (which capability runs when, retry policy at the
   product level, multi-agent coordination decisions).
4. Deployment lifecycle (shipping, hosting, scaling, secrets management).
5. A complete agent product (no end-user-facing agent ships from this repo).

**Concretely, a capability is in-scope iff it is a reusable primitive or
contract that a consumer could plug in without adopting ai_infrastructure's
opinions about the consumer's domain.** Each new capability must pass this
test at proposal time (recorded in its ADR's "Context" section).

**Out-of-scope examples (belong to consumers, not here):**
- A specific agent's system prompt or skill set.
- A particular orchestration topology for a product.
- Deployment manifests, CI for a product, secret stores.
- End-to-end user flows.

**In-scope examples (primitives):**
- Tool registry, model provider abstraction, agent loop *mechanism*,
  trace recorder, vector store, memory framework, RAG pipeline mechanism,
  guardrails primitives, rate limiting, evaluation primitives.

## Options Considered

| Option | Verdict | Reason |
|---|---|---|
| No explicit boundary | Rejected | Scope drift is already observable (evaluation composes 4 caps) |
| Boundary enforced by code (import rules) | Deferred | Charter §31 covers independence; a product-scope rule needs a consumer first |
| Boundary recorded as ADR + checklist | Accepted | Cheapest enforceable artifact today |

## Consequences

- New capability proposals must state how they are a primitive, not a product.
- Consumers (JARVIS, PROFESSOR-J) remain the owners of application policy.
- The `react-agent-loop` is in-scope as a *mechanism*; any specific agent
  built on it is out-of-scope and lives in a consumer repo.
- Revisiting this boundary requires a superseding ADR.

## Charter references

§1 (purpose), §3 (charter), §4 (decide before building), §31 (independence).

## Taxonomy impact

None — policy only. Future categories (orchestration, skills, harnesses) must
be re-evaluated against this boundary before implementation.
PY
echo written