# Agents (catalog)

> **Status: 1 entry.** This directory holds independent implementations at IMPLEMENTED or later (charter §4, §27).

## What it is

Agent runtimes and control loops: ReAct, plan-and-execute, multi-agent delegation, supervisor patterns, state-machine and graph execution.

## Why it exists

The control loop is the defining structure of an agent system, and the clearest place to compare architectural trade-offs.

## How it works

Each entry documents its own architecture in its `README.md`. For the loop itself,
see [`react_agent_loop/README.md`](react_agent_loop/README.md).

## Variants & types

None implemented.

## Landscape

External reference projects, once studied, are registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md).

## Our implementations

| Entry | Status | What it does |
|---|---|---|
| [`react_agent_loop`](react_agent_loop/) | `TESTED` | A bounded dispatcher: calls a model, dispatches structured tool calls against a registry, feeds results back as observations, and stops with a stated reason. Composes `tool-registry` and `model-provider-abstraction` through protocols it defines, so it runs against scripted doubles with no network. Sync-only. |

Full capability list: [`../../TAXONOMY.md`](../../TAXONOMY.md) §4.

## When to use / When not to use

To be documented per entry.

## Entry contract

Every entry under this directory is a subdirectory containing:

```text
<capability_id>/
├── README.md          # Category documentation standard (charter §13)
├── PROVENANCE.md      # Original source, license, what was changed and why (§11)
├── <implementation>   # Python, type-hinted, ruff-linted, black-formatted
├── examples/          # Runnable usage examples
└── tests/             # Unit/integration tests (§18)
```

Validate with `python ../../scripts/validate_catalog.py`.

## References & citations

None yet.
