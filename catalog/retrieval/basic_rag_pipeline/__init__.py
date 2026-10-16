"""Basic RAG Pipeline -- chunk, index, retrieve, augment, generate.

A minimal, stdlib-only retrieval-augmented generation pipeline. Composes
``vector-memory-store`` (ADR-0033) and, via its adapter,
``model-provider-abstraction`` (ADR-0007) through injected seams, so it runs
against scripted doubles with no network, no model and no API key.

    from basic_rag_pipeline import BasicRagPipeline

    pipeline = BasicRagPipeline(
        embedder=my_embedder,
        store=VectorStore(max_size=1000),
        generator=my_generator,
    )
    pipeline.index({"doc-1": "document text ..."})
    answer = pipeline.answer("what does the document say?")
    print(answer.text)
    for citation in answer.citations:
        print(citation.chunk_id, citation.score)

See specifications/basic-rag-pipeline.md for the design and
docs/decisions/0034-basic-rag-pipeline.md for the decision.

What it does not do: it does not parse citations out of model output (D-6),
rerank, filter by metadata, search lexically, stream, or run concurrently
(D-8). It does not sanitize document text -- retrieved text enters the
prompt, so documents are untrusted input (see TAXONOMY security notes).
"""

from __future__ import annotations

from .adapters import ProviderGenerator
from .rag_pipeline import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    BasicRagPipeline,
    Chunk,
    Citation,
    Embedder,
    Generator,
    RagAnswer,
    build_prompt,
    chunk_text,
)

__all__ = [
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHUNK_SIZE",
    "BasicRagPipeline",
    "Chunk",
    "Citation",
    "Embedder",
    "Generator",
    "ProviderGenerator",
    "RagAnswer",
    "build_prompt",
    "chunk_text",
]
