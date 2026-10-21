# ai_infrastructure Unified Package Quickstart

This example demonstrates how an application developer can consume `ai_infrastructure` as a single, coherent, zero-dependency Python package.

## What It Shows

1. **Tool Declaration & Dispatch:** Creating a `ToolRegistry`, registering tools with strict schemas, and invoking them safely.
2. **Vector Memory & Search:** Storing vector embeddings in `VectorStore` with cosine similarity retrieval.
3. **Retrieval-Augmented Generation (RAG):** Indexing documents, chunking text, and executing `BasicRagPipeline`.
4. **Agent Control Loop:** Running a bounded ReAct `Agent` with `RegistryDispatcher` and `run()`.
5. **Observability Tracing:** Recording structured JSONL telemetry with `TraceRecorder`.

## How to Run

```bash
python examples/ai_infrastructure_quickstart/quickstart.py
```

## Prerequisites

- Standard Python 3.14+ (no third-party dependencies required).
