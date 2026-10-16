# Configuration & Settings

> **Status: first entry researched, decision recorded.** `config-and-settings` is `DECIDED` — `DEFER` ([ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md), DW-014). See its research record below.

## What it is

Settings objects and their validation, environment-variable loading and precedence, layered/overridden configuration, per-environment profiles, and secret referencing (not secret storage).

## Why it exists

Every service needs configuration resolved from several sources with a defined precedence. Hand-rolled environment lookups scattered through a codebase make failure modes untraceable — the classic ones being wrong precedence and resolved secrets in logs.

## How it works

Research artifacts live at `research/config/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6). The first record aggregated convergent evidence only; no per-implementation deep study was done, because the capability is deferred and the decision does not require one.

## Variants & types

- **Settings resolution layer** (`config-and-settings`) — explicit precedence chain (constructor > environment > file > defaults), per-source validation, secret references resolved at use.

## Landscape

External projects surveyed via the study pipeline (structural analysis only, no code executed or reused); 15 of 25 studied repositories proposed this category ([convergence report](../../docs/discovery/2026-10-08-convergence.md): `OpenHands`, `SWE-agent`, `agno`, `ai`, `autogen`, and 10 more). Registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) per the charter §11 schema.

## Our implementations

None — deferred. Every catalog entry takes explicit constructor arguments by design; see [`../../docs/DEFERRED.md`](../../docs/DEFERRED.md) DW-014 for the trigger.

## When to use / When not to use

- **Use** when configuration is resolved from more than one source and precedence must be explicit.
- **Do not use** when constructor injection suffices — a settings layer with no reader is untestable theatre.

## References & citations

- [Research record: config-and-settings](config-and-settings.md)
- [Specification: config-and-settings](../../specifications/config-and-settings.md)
- [ADR-0022](../../docs/decisions/0022-configuration-taxonomy-category.md) — taxonomy category
