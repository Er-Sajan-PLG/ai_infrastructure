# Basic RAG Pipeline

> **Status: `TESTED`.** Retrieval-augmented generation over caller-provided documents. Zero runtime dependencies — standard library only; embedder, store and generator are injected seams.

| | |
|---|---|
| **Capability** | [`basic-rag-pipeline`](../../../TAXONOMY.md) (category: retrieval) |
| **Specification** | [`specifications/basic-rag-pipeline.md`](../../../specifications/basic-rag-pipeline.md) |
| **Decision** | [ADR-0034](../../../docs/decisions/0034-basic-rag-pipeline.md) — `IMPLEMENT` |
| **Research** | [`research/retrieval/basic-rag-pipeline.md`](../../../research/retrieval/basic-rag-pipeline.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — original, inspired-by |

## What it is

A minimal pipeline that grounds a model answer in documents: chunk → embed →
index → retrieve → augment → generate, with citations back to the retrieved
chunks. It composes [`vector-memory-store`](../../memory/vector_store/) and
(via one small adapter) [`model-provider-abstraction`](../../models/model_provider/)
through injected seams, so it is usable standalone and testable without a
network, a model or an API key.

## How it works

```python
from basic_rag_pipeline import BasicRagPipeline
from vector_store import VectorStore

pipeline = BasicRagPipeline(
    embedder=my_embedder,          # anything with embed(text) -> list[float]
    store=VectorStore(max_size=1000),
    generator=my_generator,        # anything with generate(prompt) -> str
)
pipeline.index({"doc-1": "long document text ..."})
answer = pipeline.answer("what does the document say?")
print(answer.text)
for citation in answer.citations:
    print(citation.chunk_id, citation.doc_id, citation.score)
```

**Design decisions:**

- **Character windows with overlap, snapped to whitespace** — no tokenizer
  dependency; deterministic, auditable cuts (D-1).
- **Stable chunk ids and offsets** — `<doc_id>#<index>`; re-ingesting
  overwrites, and every chunk resolves back to `text[start:end]` (D-2).
- **Three injected seams** — `Embedder`, a `VectorStore` instance, and
  `Generator`; the core owns no model and no second similarity implementation
  (D-3, D-4).
- **Provider binding behind one adapter** — `ProviderGenerator` is the only
  module importing `model_provider`; tests run against scripted doubles (D-5).
- **Citations reported, not parsed** — `answer.citations` is the retrieval
  evidence in rank order; the pipeline makes no claim about which chunks the
  model used (D-6).
- **`build_prompt` is public** — what the model saw is inspectable without
  reading internals; chunk ids are prompt-visible anchors (D-7).

## Our implementations

| Implementation | Language | Notes |
|---|---|---|
| [`rag_pipeline.py`](rag_pipeline.py) | Python | Chunking, pipeline core, prompt assembly, citations |
| [`adapters.py`](adapters.py) | Python | `ProviderGenerator` → model-provider-abstraction |

## References

- [haystack](https://github.com/deepset-ai/haystack) — retriever components
  incl. `retrievers/in_memory/`
- [llama_index](https://github.com/run-llama/llama_index) — ingestion +
  node-parser integrations + query/chat engines
- [LangChain](https://github.com/langchain-ai/langchain) — `langchain_core`
  indexing/embeddings/document loaders
- [ragas](https://github.com/explodinggradients/ragas) — evaluation metrics
  over RAG samples (the future consumer of `RagAnswer`)
