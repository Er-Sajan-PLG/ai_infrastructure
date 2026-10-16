# Retrieval (catalog)

> **Status: one entry.** `basic_rag_pipeline` is `TESTED` (ADR-0034). This directory holds independent implementations at IMPLEMENTED or later (charter §4, §27).

## What it is

Chunking, embedding, indexing, hybrid and vector search, reranking, and citation-bearing RAG pipelines.

## Why it exists

Retrieval determines whether generated answers are grounded and auditable.

## How it works

The first entry, [`basic_rag_pipeline/`](basic_rag_pipeline/), wires five stages — chunk, index, retrieve, augment, generate — with the embedder, an in-memory `VectorStore`, and the generator all injected. It documents its architecture in its own `README.md`.

## Variants & types

- **Basic RAG pipeline** — fixed-size overlapping chunking, embedding-based retrieval, single-call generation, citations reported from retrieval.

## Landscape

External reference projects, once studied, are registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md).

## Our implementations

| Entry | Status | Notes |
|---|---|---|
| [`basic_rag_pipeline/`](basic_rag_pipeline/) | `TESTED` | Stdlib-only pipeline over injected seams; `ProviderGenerator` binds `model_provider` |

Capabilities planned for this category are listed in [`../../TAXONOMY.md`](../../TAXONOMY.md) §4.

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
