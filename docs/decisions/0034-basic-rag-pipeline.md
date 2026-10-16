# ADR-0034: Basic RAG Pipeline

**Status:** Accepted
**Date:** 2026-10-16
**Drivers:** The last remaining Phase 1 queue capability (`basic-rag-pipeline`,
`DISCOVERED` since Phase 1); both dependencies (`vector-memory-store`,
`model-provider-abstraction`) are `TESTED`; the study pipeline's structural
evidence is in place.

## Context

`basic-rag-pipeline` is the final item of the Phase 1 queue that has never left
`DISCOVERED`. Its declared dependencies — `vector-memory-store` (ADR-0033,
TESTED 2026-10-09) and `model-provider-abstraction` (ADR-0007, TESTED) — are
both done, so the capability has been unblocked and pending since Phase 4 closed.

The study pipeline's structural reports (haystack, llama_index, LangChain,
ragas — pinned commits in `study_pipeline/studied_repos/`) show every major
framework ships the same stage sequence — chunk, embed, index, retrieve,
augment, generate — and that all of them separate retrieval from generation into
different components. In-memory retrieval is a first-class variant in every
framework (haystack `components/retrievers/in_memory/`).

The 2026-09-16 adjudicated audit recorded a design input for this capability in
advance: the taxonomy entry currently has `security: ""`, which is honest for
DISCOVERED but must be filled before DESIGNED, because retrieved document text
is attacker-influenced input entering a prompt.

## Decision

**IMPLEMENT** `catalog/retrieval/basic_rag_pipeline/` — a stdlib-only pipeline
composing the two TESTED dependencies through injected seams:

- **Chunking** — character windows with overlap, snapped to whitespace; chunks
  carry stable ids (`<doc_id>#<index>`) and source offsets (D-1, D-2).
- **Embedding** — injected `Embedder` protocol; no model in the repository
  (D-3).
- **Store** — injected `VectorStore` instance, public interface only; no second
  similarity implementation (D-4).
- **Generation** — one call behind a `Generator` protocol, with a
  `ProviderGenerator` adapter binding `model-provider-abstraction` (D-5).
- **Citations** — the retrieved chunks in rank order, reported not parsed
  (D-6). Prompt assembly is public and chunk-id-annotated (D-7).
- **Sync, exact, no reranking** — deferred explicitly, not silently absent
  (D-8).

Full interface and decisions: [specifications/basic-rag-pipeline.md](../../specifications/basic-rag-pipeline.md).

## Consequences

- The Phase 1 capability queue is empty; all seven seeded capabilities reach
  at least `TESTED` after implementation.
- A future evaluation capability has a producer of inspectable RAG samples
  (retrieved chunks + prompt + answer) to consume — the ragas observation.
- Retrieval quality (recall, ranking) is the store's and the embedder's to
  determine; the pipeline reports, it does not judge.
- Prompt injection through retrieved text is possible and documented; the
  pipeline reports the evidence that entered the prompt so a reviewer can see
  what happened.
- System A's hand-rolled RAG flow (integration) and this catalog entry remain
  independent — the integration is not refactored in this change (a
  composition experiment, not a consumer).

## Evidence

From the study pipeline structural reports (no code executed, no code reused):

- `haystack.md`: `haystack/components/retrievers/`, `.../retrievers/in_memory/`;
  chunking "usually small and embedded rather than in its own module".
- `llama_index.md`: `llama-index-core/llama_index/core/ingestion`,
  `core/embeddings`, `core/chat_engine`, `llama-index-integrations/node_parser/`.
- `langchain.md`: `langchain_core/{document_loaders,documents,embeddings,indexing}`.
- `ragas.md`: `src/ragas/metrics/collections/answer_correctness/` — evaluation
  is a separate plane consuming samples it did not produce.

From the audit trail:

- `docs/audits/2026-09-15-usa-audit.md`: "the taxonomy entry currently has
  `security: ""` … must be filled before DESIGNED."
- `docs/audits/2026-09-16-usa-audit-adjudicated.md` §24.1: dependency-first
  sequencing correctly blocked this capability on `vector-memory-store`.

## Rejected alternatives

- **Adopt a framework pipeline (haystack / llama_index / LangChain):** Rejected
  — runtime dependencies (charter §20); the evidence shows the missing piece is
  glue over components we already own.
- **Token-exact chunk sizes:** Rejected — requires a tokenizer runtime
  dependency.
- **Parse citations from model output:** Rejected for the basic pipeline —
  unverifiable, and claiming verification we do not perform is exactly the
  unevidenced status charter §4 forbids.
- **Defer again:** Rejected — no blocker remains; both dependencies are TESTED
  and the design has been surveyed.
