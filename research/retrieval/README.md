# Retrieval & Knowledge

> **Status: first entry researched.** `basic-rag-pipeline` is `DECIDED` (ADR-0034); see its research record below.

## What it is

RAG, hybrid, vector, lexical and graph retrieval, knowledge graphs, document indexing, chunking, reranking, citation systems, provenance, knowledge synchronization.

## Why it exists

Grounding generation in external knowledge is how systems answer about things the model was never trained on — and how answers become auditable.

## How it works

Research artifacts live at `research/retrieval/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6). The first record found the ecosystem's convergent stage sequence — chunk → embed → index → retrieve → augment → generate — with retrieval and generation separated in every major framework.

## Variants & types

- **Basic RAG pipeline** (`basic-rag-pipeline`) — fixed-size chunking with overlap, embedding-based retrieval, single-call generation, citations reported from retrieval.

## Landscape

External projects surveyed via the study pipeline (structural analysis only, no code executed or reused): haystack (`components/retrievers/`, `components/retrievers/in_memory/`), llama_index (`core/ingestion`, `core/chat_engine`, node-parser integrations), LangChain (`langchain_core/indexing`, `document_loaders`), ragas (evaluation metrics over RAG samples). Registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) per the charter §11 schema.

## Our implementations

- [`basic-rag-pipeline`](../../catalog/retrieval/basic_rag_pipeline/) — `TESTED` (ADR-0034). See [`../../TAXONOMY.md`](../../TAXONOMY.md) §4 for lifecycle status.

## When to use / When not to use

- **Use** when answers must be grounded in caller-provided documents and the retrieval behind each answer must be inspectable.
- **Do not use** when documents need token-exact chunking, reranking, hybrid search, metadata filtering, or citation verification against model output — all deferred (specification §4).

## References & citations

- [Research record: basic-rag-pipeline](basic-rag-pipeline.md)
- [Specification: basic-rag-pipeline](../../specifications/basic-rag-pipeline.md)
- [ADR-0034](../../docs/decisions/0034-basic-rag-pipeline.md)
