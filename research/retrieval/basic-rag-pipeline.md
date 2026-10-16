# Research Record: Basic RAG Pipeline

- **Capability:** `basic-rag-pipeline` (category: retrieval)
- **Status:** `RESEARCHED` → `UNDERSTOOD`
- **Date:** 2026-10-16
- **Decision:** see [ADR-0034](../../docs/decisions/0034-basic-rag-pipeline.md) *(IMPLEMENT)*
- **Sources:** Study pipeline structural reports (25 repos), taxonomy analysis,
  our own [`vector-memory-store`](../memory/vector-memory-store.md) record

Claims are labelled per charter §6:
**FACT** (verified, cited) · **OBSERVATION** (inferred from docs/structure) ·
**INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice, not a fact).

---

## 1. The problem, stated without reference to any implementation

> Ground a language model's answer in a set of caller-provided documents, and
> make the retrieval that produced the answer inspectable.

Stated that way, the capability decomposes into five separable stages.
**DESIGN OPINION.**

| # | Stage | Question it answers |
|---|---|---|
| 1 | **Chunk** | A document is too long for one retrieval unit — how is it divided? |
| 2 | **Embed & index** | How does each chunk become searchable? |
| 3 | **Retrieve** | Given a query, which chunks are relevant, and how is that ranked? |
| 4 | **Augment** | How do the retrieved chunks enter the prompt, traceably? |
| 5 | **Generate** | One model call that answers *from* the context, with sources reported. |

**INFERENCE — the load-bearing boundary is 3 vs 5.** Retrieval determines
what evidence exists; generation determines what is claimed from it. A pipeline
that fuses the two cannot be tested without a model and cannot be reused with a
different generator. Every studied framework eventually separates them (§3).

## 2. Constraints we are designing under

| Constraint | Source | Consequence |
|---|---|---|
| **Zero runtime dependencies** | ADR-0003 | No framework, no tokenizer library, no numpy. Chunking must be stdlib-only. |
| **Embedder is external** | this record | The repo has no embedding model (and must not acquire one). Embedding must be an injected seam. |
| **Store exists and is TESTED** | ADR-0033 | `vector-memory-store` provides add/search; reuse it through its public interface rather than re-implementing similarity. |
| **Provider-agnostic** | charter §31 | The pipeline must not know any provider's wire format; generation goes through `model-provider-abstraction` behind a one-call protocol. |
| **Component independence** | charter §31 | Usable standalone: no agent loop, no network. Doubles for embedder, store and generator must make every path testable. |
| **Documents and queries are untrusted input** | charter §20 | No `eval`/`exec`; retrieval text is attacker-influenced and enters a prompt — this must be a documented security property, not an assumption. |
| **Python, type-hinted, mypy strict** | charter §13 | Public API fully annotated. |

## 3. Evidence from the study pipeline

Per-project structural reports live in
[`study_pipeline/studied_repos/`](../../study_pipeline/studied_repos/). Statements
below are structural observations at pinned commits, not quality judgements.

**OBSERVATION — every major framework ships the same stage sequence.** Structural
evidence at pinned commits:

| Repository | Ingest / chunk | Embed | Retrieve | Generate |
|---|---|---|---|---|
| haystack | downloaders + converters (docs) | component-level | `haystack/components/retrievers/`, incl. `in_memory/` | pipeline components |
| llama_index | `llama-index-core/llama_index/core/ingestion` + `llama-index-integrations/node_parser/` | `core/embeddings` + `llama-index-integrations/embeddings/` | vector stores + retrievers | `core/chat_engine` |
| LangChain | `langchain_core/document_loaders` | `langchain_core/embeddings` | `langchain_core/indexing` + retriever interfaces | chains (out of core) |
| ragas | consumes ingested samples | `src/ragas/embeddings/` | — (evaluation plane) | — |

*Sources: [`haystack.md`](../../study_pipeline/studied_repos/haystack.md),
[`llama_index.md`](../../study_pipeline/studied_repos/llama_index.md),
[`langchain.md`](../../study_pipeline/studied_repos/langchain.md),
[`ragas.md`](../../study_pipeline/studied_repos/ragas.md) — all structural
observations at the commits recorded in each report.*

**OBSERVATION — retrieval and generation are separate directories in every
framework that has both.** haystack keeps retrievers under `components/`;
llama_index separates `core/ingestion` from `core/chat_engine`; LangChain keeps
indexing in `langchain-core` while chains live elsewhere. **INFERENCE:** the
3-vs-5 boundary in §1 is not our invention; the ecosystem converged on it.

**FACT — chunking is usually embedded, not a module.** The haystack report
records it directly: *"Chunking strategies are usually small and embedded rather
than in their own module, so absence here is not evidence of absence"*
(haystack report, `chunking` section limitation). **INFERENCE:** chunking is
small enough that frameworks treat it as configuration. Ours can be a function.

**FACT — in-memory retrieval is a first-class variant.** haystack ships
`components/retrievers/in_memory/`; llama_index's integrations list in-memory
document/retriever stores. Our `vector-memory-store` (ADR-0033) is the same
choice — and our own record already established caller-assigned IDs, cosine
similarity, and metadata preservation as the convergent interface.

**FACT — evaluation is a separate plane.** ragas is entirely metrics
(`src/ragas/metrics/collections/answer_correctness/`, …) consuming samples it did
not produce. **INFERENCE:** answer-quality measurement is *not* this
capability's job; this pipeline's job is to produce the inspectable sample
(retrieved chunks + prompt + answer) that a future evaluation capability can
consume.

## 4. What the capability must therefore do (requirements)

Distilled from §1–§3; each requirement traces to evidence above.

1. **Five explicit stages**, each observable from outside: chunk, index,
   retrieve, augment, generate. *(§1, §3)*
2. **Chunking is deterministic and dependency-free** — fixed-size windows with
   overlap, snapping to whitespace when possible. Token-exact sizes need a
   tokenizer; deferred with the limitation documented. *(constraints table)*
3. **Chunks carry stable identity and provenance** — chunk id, source doc id,
   offsets into the original text. Citations without provenance are not
   auditable. *(§1 stage 4)*
4. **Embedding is injected** (`Embedder` protocol). Tests use a deterministic
   double; production injects a real embedder — exactly the composition
   boundary System A already exercises. *(constraints table)*
5. **The store is injected** (a `VectorStore` instance, public interface only).
   No second similarity implementation. *(ADR-0033 reuse)*
6. **Generation is one call behind a `Generator` protocol**, with a
   `ProviderGenerator` adapter binding `model-provider-abstraction` — the same
   protocol-plus-adapter pattern `react-agent-loop` uses, for the same reason:
   every path testable without a network. *(§3 boundary; ADR-0008 precedent)*
7. **The augmented prompt is built by a public function**, so what the model
   saw is inspectable without reading the pipeline's internals. *(§1 stage 4)*
8. **Citations are the retrieved chunks in rank order — reported, not parsed.**
   Parsing citations out of model prose is a separate, later capability; the
   basic pipeline must not pretend to verify what it does not check. *(honesty;
   charter §4)*

## 5. Design implications

- **Chunk ids as `<doc_id>#<index>`** — stable across re-ingestion, so
  re-indexing a changed document overwrites deterministically. **[DESIGN OPINION]**
- **Retrieval returns store results; the answer object carries the citation
  chain.** `RagAnswer(text, citations)` where each citation is
  `(chunk_id, doc_id, score)`. **[DESIGN OPINION]**
- **Prompt format names each chunk id** so a future citation-parsing capability
  has anchors to parse against, and the model can be asked to cite. **[DESIGN
  OPINION]**
- **Empty retrieval is a valid answer, not an error**: the prompt says no
  documents were retrieved; the generator still runs. **[DESIGN OPINION]**
- **Pure Python, exact search** — inherited from the store's documented
  O(n·d) limit; fine for the <10k-item use case. **[FACT, from ADR-0033]**

## 6. Rejected approaches (feeding the ADR)

- **Adopting a framework's pipeline (haystack/llama_index/LangChain):**
  Rejected — runtime dependencies violate charter §20; and the evidence shows
  what we need is a few hundred lines of glue over components we already own.
- **Token-exact chunk sizes:** Rejected — requires a tokenizer runtime
  dependency; character windows with overlap are the honest stdlib baseline.
- **Parsing citations from model output:** Rejected for the basic pipeline —
  unreliable to verify, and pretending to verify is worse than not claiming to.
- **Reranking / hybrid search / metadata filtering:** Deferred — real features,
  not MVP; record in DEFERRED if a future session needs them.
- **Async interface:** Rejected — matches the sync-only decision already made
  for model-provider-abstraction and the store.

## 7. Open questions carried to the decision

1. **Naming of the entry**: `basic_rag_pipeline` (capability id is
   `basic-rag-pipeline`; mirrors `vector_store` ↔ `vector-memory-store`).
2. **Where the entry lives**: `catalog/retrieval/basic_rag_pipeline/` — a new
   category directory becomes a real catalog category with this entry.
3. **Should `ProviderGenerator` default a system prompt?** Proposal: optional
   `system`; `None` sends none. A pipeline should not silently inject persona.
4. **What happens when the store is over capacity mid-ingest?** Inherited LRU
   eviction from the store; documented, not compensated.
