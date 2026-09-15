# Tools (catalog)

> **Status: 1 entry.** Independent implementations at IMPLEMENTED or later (charter §4, §27).

## What it is

Tool registries, schemas, validation, invocation, routing, and failure semantics.

## Why it exists

The narrow model-to-side-effect boundary. Everything acting on the world passes through it.

## How it works

Not yet implemented. Any future entry documents its architecture in its own `README.md`.

## Variants & types

None implemented.

## Landscape

External reference projects, once studied, are registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md).

## Our implementations

| Entry | Status | What it does |
|---|---|---|
| [`tool_registry`](tool_registry/) | `TESTED` | Register, describe, validate and invoke tools with typed JSON-Schema contracts. Zero runtime dependencies. |

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
