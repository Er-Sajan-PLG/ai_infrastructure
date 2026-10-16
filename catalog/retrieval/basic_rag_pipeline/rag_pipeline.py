"""Basic RAG pipeline -- chunk, index, retrieve, augment, generate.

A minimal, stdlib-only retrieval-augmented generation pipeline over
caller-provided documents. Three seams are injected, so the core never
touches a model, a network, or a second similarity implementation:

* ``embedder`` -- anything with ``embed(text) -> list[float]``
* ``store`` -- a ``vector_store.VectorStore`` instance (ADR-0033)
* ``generator`` -- anything with ``generate(prompt) -> str``

    from basic_rag_pipeline import BasicRagPipeline

    pipeline = BasicRagPipeline(embedder=..., store=..., generator=...)
    pipeline.index({"doc-1": "document text ..."})
    answer = pipeline.answer("question")
    print(answer.text)
    for citation in answer.citations:
        print(citation.chunk_id, citation.score)

See specifications/basic-rag-pipeline.md for the design and
docs/decisions/0034-basic-rag-pipeline.md for the decision.

What it does not do: it does not parse citations out of the model's prose
(D-6 -- citations are the retrieved chunks, reported not verified), does not
rerank, filter metadata, search lexically, stream, or run concurrently
(D-8), and does not sanitize document text (documents are untrusted input;
the prompt is built so a reviewer can inspect exactly what entered it).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from vector_store import SearchResult, VectorStore

__all__ = [
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHUNK_SIZE",
    "BasicRagPipeline",
    "Chunk",
    "Citation",
    "Embedder",
    "Generator",
    "RagAnswer",
    "build_prompt",
    "chunk_text",
]

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 200


class Embedder(Protocol):
    """Turns text into a vector.

    Structural protocol: any object with a matching ``embed`` method works.
    The repository owns no embedding model; tests inject deterministic
    doubles and production injects a real embedder (D-3).
    """

    def embed(self, text: str) -> list[float]:
        """Embed one piece of text into a vector."""
        ...


class Generator(Protocol):
    """Produces a model answer for a prompt.

    Structural protocol: the pipeline makes exactly one call per ``answer``
    and does not retry, stream, or parse the result (D-5, D-6).
    """

    def generate(self, prompt: str) -> str:
        """Generate an answer for one fully assembled prompt."""
        ...


@dataclass(frozen=True)
class Chunk:
    """One retrieval unit of a document.

    Attributes:
        id: Stable identity, ``"<doc_id>#<index>"`` (D-2). Re-ingesting the
            same document reproduces the same ids, so the store's
            overwrite-on-duplicate behaviour makes re-indexing idempotent.
        doc_id: The source document's caller-assigned id.
        index: Position of this chunk in the document's chunk sequence.
        text: The exact slice ``text_start:text_end`` of the source text.
        start: Offset of the slice in the source text.
        end: End offset (exclusive) of the slice in the source text.
    """

    id: str
    doc_id: str
    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Citation:
    """The retrieval evidence behind an answer.

    Reported from retrieval, not parsed from model output (D-6): the
    pipeline makes no claim about which chunks the model actually used.
    """

    chunk_id: str
    doc_id: str
    score: float


@dataclass(frozen=True)
class RagAnswer:
    """A generated answer and the chunks that were retrieved for it."""

    text: str
    citations: tuple[Citation, ...]


def _validate_chunk_params(size: int, overlap: int) -> None:
    """Reject a chunking configuration before any embedding is paid for."""
    if size < 1:
        raise ValueError(f"size must be >= 1, got {size}")
    if overlap < 0:
        raise ValueError(f"overlap must be >= 0, got {overlap}")
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")


def chunk_text(
    text: str,
    *,
    doc_id: str,
    size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Split ``text`` into overlapping fixed-size character windows (D-1).

    Windows are ``size`` characters with ``overlap`` shared characters
    between neighbours. When a window would end mid-word and whitespace
    exists inside it, the cut is moved back to the last whitespace so words
    stay whole. Chunk ids are ``"<doc_id>#<index>"`` and ``start``/``end``
    record the offsets such that ``text[start:end] == chunk.text``.

    Args:
        text: The document text. Empty text produces no chunks.
        doc_id: Non-empty source document id.
        size: Window size in characters.
        overlap: Shared characters between neighbouring windows.

    Returns:
        The document's chunks in order.

    Raises:
        ValueError: ``doc_id`` is empty, ``size < 1``, ``overlap < 0``, or
            ``overlap >= size``.
    """
    _validate_chunk_params(size, overlap)
    if not doc_id:
        raise ValueError("doc_id must be a non-empty string")
    if not text:
        return []

    chunks: list[Chunk] = []
    n = len(text)
    start = 0
    index = 0
    while start < n:
        end = min(start + size, n)
        if end < n:
            window = text[start:end]
            snap = max(window.rfind(" "), window.rfind("\n"), window.rfind("\t"))
            if snap > 0:
                end = start + snap
        chunks.append(
            Chunk(
                id=f"{doc_id}#{index}",
                doc_id=doc_id,
                index=index,
                text=text[start:end],
                start=start,
                end=end,
            )
        )
        index += 1
        if end >= n:
            break
        # max() is the progress guarantee: even with pathological input the
        # next window starts at least one character later than this one.
        start = max(end - overlap, start + 1)
    return chunks


def build_prompt(query: str, results: Sequence[SearchResult]) -> str:
    """Assemble the augmented prompt from retrieved chunks (D-7).

    Public so that "what the model saw" is inspectable without reading the
    pipeline's internals. Each context block is prefixed with its chunk id,
    giving a future citation-parsing capability stable anchors.
    """
    if results:
        context = "\n\n".join(f"[{r.id}] {r.metadata.get('text', '')}" for r in results)
    else:
        context = "(no documents retrieved)"
    return (
        "Answer the question using the context below. "
        "Cite the chunk ids you use, like [doc#0].\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )


class BasicRagPipeline:
    """Chunk -> embed -> index -> retrieve -> augment -> generate (D-1..D-9).

    Composes an injected ``Embedder``, an injected ``VectorStore`` and an
    injected ``Generator``; owns only the wiring, the chunking, the prompt
    assembly and the citation chain.
    """

    def __init__(
        self,
        *,
        embedder: Embedder,
        store: VectorStore,
        generator: Generator,
        size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        """Wire the three seams and the chunking configuration.

        Raises:
            ValueError: ``size``/``overlap`` are not a valid chunking
                configuration (see :func:`chunk_text`).
        """
        _validate_chunk_params(size, overlap)
        self._embedder = embedder
        self._store = store
        self._generator = generator
        self._size = size
        self._overlap = overlap

    def index(self, documents: Mapping[str, str]) -> int:
        """Chunk, embed and store every document.

        Args:
            documents: Document id -> text. Ids must be non-empty; re-indexing
                a document overwrites its previous chunks in the store.

        Returns:
            The total number of chunks stored.

        Raises:
            ValueError: A document id is empty.
        """
        count = 0
        for doc_id, text in documents.items():
            for chunk in chunk_text(
                text, doc_id=doc_id, size=self._size, overlap=self._overlap
            ):
                self._store.add(
                    chunk.id,
                    self._embedder.embed(chunk.text),
                    {
                        "doc_id": chunk.doc_id,
                        "chunk_index": chunk.index,
                        "text": chunk.text,
                    },
                )
                count += 1
        return count

    def retrieve(self, query: str, k: int = 3) -> list[SearchResult]:
        """Embed the query and return the ``k`` nearest chunks.

        Args:
            query: Non-empty, non-whitespace query text.
            k: Number of results; validated by the store (``k <= 0`` raises
                ``ValueError``).

        Raises:
            ValueError: The query is empty or whitespace-only.
        """
        if not query.strip():
            raise ValueError("query must be non-empty")
        return self._store.search(self._embedder.embed(query), k=k)

    def answer(self, query: str, k: int = 3) -> RagAnswer:
        """Retrieve, augment, generate exactly once, and report citations.

        An empty retrieval is a valid state (D-9): the prompt states that no
        documents were retrieved and the generator still runs.

        Raises:
            ValueError: The query is empty or whitespace-only.
        """
        results = self.retrieve(query, k=k)
        prompt = build_prompt(query, results)
        text = self._generator.generate(prompt)
        citations = tuple(
            Citation(
                chunk_id=result.id,
                doc_id=str(result.metadata.get("doc_id", "")),
                score=result.score,
            )
            for result in results
        )
        return RagAnswer(text=text, citations=citations)
