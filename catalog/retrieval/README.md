# Retrieval (catalog)

> **Status: no entries yet.** This directory holds independent implementations at IMPLEMENTED or later (charter §4, §27). Empty is correct for Phase 1.

## What it is

Chunking, embedding, indexing, hybrid and vector search, reranking, and citation-bearing RAG pipelines.

## Why it exists

Retrieval determines whether generated answers are grounded and auditable.

## How it works

Not yet implemented. Any future entry documents its architecture in its own `README.md`.

## Variants & types

None implemented.

## Landscape

External reference projects, once studied, are registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md).

## Our implementations

None. Capabilities planned for this category are listed in [`../../TAXONOMY.md`](../../TAXONOMY.md) §4.

## When to use / When not to use

To be documented per entry.

## Entry contract

Every entry under this directory is a subdirectory containing:

```text
<capability_id>/
├── README.md          # Category documentation standard (charter §13)
├── PROVENANCE.md      # Original source, license, what was changed and why (§11)
├── <implementation>   # Python, type-hinted, ruff/black formatted
├── examples/          # Runnable usage examples
└── tests/             # Unit/integration tests (§18)
```

Validate with `python ../../scripts/validate_catalog.py`.

## References & citations

None yet.
