# Guardrails & Output Validation

> **Status: first entry researched, decision recorded.** `guardrails` is `DECIDED` — `DEFER` ([ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md), DW-016). See its research record below.

## What it is

Output moderation, content filtering, response validation, safety classifiers, and policy enforcement on model outputs — the machinery between a model response and whatever consumes it.

## Why it exists

Model output must be validated before reaching users, but no taxonomy category covered the machinery between model response and user-facing output. `safety/` covers governance, policy, and guardrails for *agent actions*; this category covers validation of *model outputs* — different concern, different machinery ([ADR-0031](../../docs/decisions/0031-guardrails-category.md)).

## How it works

Research artifacts live at `research/guardrails/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6). The first record aggregated convergent evidence only; no per-implementation deep study was done, because the capability is deferred and the decision does not require one.

## Variants & types

- **Deterministic validators** — length and schema validation, regex/allowlist checks, policy objects with pass/reject/regenerate decisions.
- **Model-backed classifiers** — moderation and safety classification via a separate model call (out of scope until a metered call path exists).

## Landscape

External projects surveyed via the study pipeline (structural analysis only, no code executed or reused); 10 of 25 studied repositories proposed this category ([ADR-0031](../../docs/decisions/0031-guardrails-category.md): `agno`, `ai`, `haystack`, `langfuse`, `litellm`, `mastra`, `openai-python`, `phidata`, `semantic-kernel`, `SWE-agent`). Registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) per the charter §11 schema.

## Our implementations

None — deferred. No user-facing model-output boundary exists yet; see [`../../docs/DEFERRED.md`](../../docs/DEFERRED.md) DW-016 for the trigger.

## When to use / When not to use

- **Use** wherever untrusted model output crosses a trust boundary — toward a user, a tool call, or another system.
- **Do not use** inside a test harness: validating against assertions is what tests are for, and a guardrail with no boundary to guard cannot be exercised honestly.

## References & citations

- [Research record: guardrails](guardrails.md)
- [Specification: guardrails](../../specifications/guardrails.md)
- [ADR-0031](../../docs/decisions/0031-guardrails-category.md) — taxonomy category
