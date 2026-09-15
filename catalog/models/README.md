# Models (catalog)

> **Status: 1 entry.** Independent implementations at IMPLEMENTED or later (charter §4, §27).

## What it is

Provider abstractions, routing and fallback, streaming, structured output, embeddings, and local serving interfaces.

## Why it exists

One normalized interface where provider SDKs, error shapes, and retry semantics differ.

## How it works

Not yet implemented. Any future entry documents its architecture in its own `README.md`.

## Variants & types

None implemented.

## Landscape

External reference projects, once studied, are registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md).

## Our implementations

| Entry | Status | What it does |
|---|---|---|
| [`model_provider`](model_provider/) | `TESTED` | A vendor-neutral chat interface for OpenAI, Anthropic and Gemini with streaming, usage normalisation and a structural error taxonomy. Zero runtime dependencies; transport injected. |

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
