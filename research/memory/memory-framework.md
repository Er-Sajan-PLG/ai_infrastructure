# Research: Memory Framework

- **Capability:** `memory-framework` (category: memory)
- **Status:** `RESEARCHED` → `UNDERSTOOD`
- **Session:** Phase 5B.2
- **Date:** 2026-10-23
- **Decision:** [ADR-0040](../../docs/decisions/0040-memory-framework.md) (to be created)

Claims are labelled per charter §6:
**FACT** (verified against a primary source, cited) · **OBSERVATION** (read from
docs/source) · **INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice).

---

## 1. The problem, stated without reference to any implementation

> A vector store answers "what is semantically similar to this query?". It does
> not answer "what should be remembered, what can be forgotten, and what has
> changed?" Memory needs lifecycle operations the vector store does not own.

The repository already has `vector-memory-store` (ADR-0033) — a cosine-similarity
store over caller-assigned embeddings. It has no notion of:
extraction (which facts to keep), consolidation (merging duplicates, resolving
contradictions), eviction (what to drop under capacity), or scoping (whose memory
is this). Those are the lifecycle concerns a memory framework owns.

| Concern | Question | Belongs to |
|---|---|---|
| **Extraction** | Which facts does a text yield? | the memory framework |
| **Deduplication** | Is this fact already stored? | the memory framework |
| **Consolidation** | Merge related facts, resolve contradictions | the memory framework |
| **Eviction** | What is dropped when capacity is hit? | the memory framework |
| **Scoping** | user / session / agent / global | the memory framework |
| **Retrieval** | Given a query, what is relevant? | the vector store |
| **Embedding** | How is text turned into a vector? | an injected embedder |
| **Fact extraction model call** | Which LLM call extracts facts? | an injected ModelCaller |

**INFERENCE — the load-bearing insight:** the framework composes the vector
store; it does not replace it. Extraction and consolidation are injected (no
model in core), so the framework stays stdlib-only and testable (charter §18).

---

## 2. Constraints

| Constraint | Source | Consequence |
|---|---|---|
| **Zero runtime dependencies** | ADR-0003 | No Qdrant, no Neo4j, no pydantic. In-memory. |
| **Component independence** | charter §31 | No agent loop, no registry, no network required. |
| **No model calls in core** | charter §18 | Extraction/consolidation injected as callables. |
| **Python + mypy strict** | charter §13 | Fully annotated. |
| **Verifiable without network** | charter §18 | Extraction/consolidation testable with scripted callables. |
| **Composes VectorStore** | ADR-0033 | `Memory` delegates retrieval to the store. |

---

## 3. Surveyed systems

### 3.1 Mem0 / Mem0g

- **FACT (mem0ai / aiagentmemory comparison):** `add(messages, {userId})` runs
  LLM fact extraction internally and stores the distilled claims; `search(query,
  {userId})` returns facts. Since April 2026 it is ADD-only — "nothing is
  overwritten"; time-aware retrieval picks the current fact. There is an escape
  hatch `infer: false` to store raw text.
- **OBSERVATION:** Mem0 ships an opinion: the unit of memory is the distilled
  fact, not the raw turn. That is the design choice to be aware of.
- **INFERENCE:** The liftable ideas are (1) ADD-only extraction, (2) user scoping
  as a required parameter, (3) an `infer` flag to bypass extraction.

### 3.2 Zep / Graphiti

- **FACT (getzep/graphiti README):** `add_episode` triggers entity extraction,
  relation extraction, dedup, bi-temporal stamping and contradiction detection in
  one call; `search` is hybrid (graph traversal + vector + BM25 fused with RRF)
  with **no LLM in the read path**.
- **OBSERVATION:** Bi-temporal is the differentiator: facts carry `valid_at` /
  `invalid_at`, so "as of March 20" returns the then-true fact.
- **INFERENCE:** A graph substrate is out of scope (no Neo4j). The liftable idea is
  **contradiction detection at write time** and **no model in the read path**.

### 3.3 Letta / MemGPT

- **FACT (jatinbansal.com):** three-tier hierarchical memory (core/recall/
  archival) with the agent self-managing tier promotion via tool calls; there is
  no explicit `memory.add()` — the agent decides what to remember.
- **OBSERVATION:** "Agent-driven memory management" is either right (long-running
  stateful agents) or wrong (harness-owned write policy).
- **INFERENCE:** For this repository, the harness owns the write policy, so the
  API is explicit (`add`), not agent-driven.

### 3.4 LangMem / Cognee / Supermemory / Hindsight

- **OBSERVATION:** LangMem composes a LangGraph store with a background manager
  that "extracts, consolidates, and updates". Cognee exposes `remember`,
  `recall`, `improve`, `forget`. Supermemory resolves contradictions and expires
  temporary facts. Hindsight consolidates into observations that are refined,
  not overwritten.
- **INFERENCE:** The convergence across all of them is a `remember`/`recall`
  surface plus explicit `forget`/`improve` lifecycle verbs, and a consolidation
  pass that refines rather than overwrites.

### 3.5 Existing in-repo primitives

- **FACT (catalog/memory/vector_store):** `VectorStore.add(id, embedding,
  metadata)`, `VectorStore.search(query, k)`, `VectorStore.delete(id)`. Metadata
  is an arbitrary dict.
- **FACT (catalog/models/model_provider):** `ModelCaller.call(messages, *,
  system, tools) -> ChatResponse` is the injection seam for extraction.
- **FACT (catalog/agents/react_agent_loop):** `Embedder` protocol in
  `basic-rag-pipeline`? The basic-rag-pipeline uses an injected embedder.

---

## 4. Findings (the things that force design)

1. **Extraction is a pure function of (text, model_caller).** Injected, so the
   framework has no model dependency.
2. **Retrieval is the vector store's job.** The framework translates a query into
   an embedding (injected embedder) and delegates to `VectorStore.search`.
3. **Consolidation is a pure function of (facts, embeddings).** Deduplication by
   cosine similarity above a threshold; contradiction detection is a later stage.
4. **Eviction is a policy, not a fixed rule.** LRU / TTL / importance / capacity
   are all valid; the framework exposes them and the caller chooses.
5. **Scoping is a namespace.** A `scope` key (user/session/agent/global) prefixes
   every memory id and filters every search.
6. **Contradiction detection is deferred.** It needs a model call and is
   out of scope (no model in core).

---

## 5. What we will NOT build

- A graph substrate (Neo4j, bi-temporal edges) — out of scope.
- Bi-temporal validity windows — out of scope.
- A hosted memory service / persistence — out of scope.
- Model-backed extraction in core — injected, not owned.
- Async API — sync-first, matching the rest of the repository.

---

## 6. Proposed capability shape (for the spec)

- `Memory` protocol: `add(text, scope=None, metadata=None) -> MemoryId`,
  `search(query, scope=None, k=5) -> list[MemoryItem]`, `consolidate() -> int`,
  `evict(policy) -> int`.
- `MemoryItem(id, text, embedding, metadata, scope, created_at)`.
- `Extractor` protocol: `extract(text) -> list[str]` (facts).
- `Embedder` protocol: `embed(text) -> list[float]`.
- `EvictionPolicy` protocol: `select(items, capacity) -> list[MemoryId]`.
- `InMemoryMemory` — composes `VectorStore`.
- Implementations: `LRUEviction`, `TTLEviction`, `ImportanceEviction`.

---

## 7. Open questions (to resolve in the spec)

- Q1: Does extraction replace raw storage or augment it? Proposed: extract facts
  and store each as a memory item; the raw text is stored as metadata.
- Q2: Is consolidation automatic or explicit? Proposed: explicit `consolidate()`,
  matching Cognee's `improve`.
- Q3: Does the framework own an embedder? Proposed: injected, defaulting to a
  simple hash-based embedder for tests (documented as non-semantic).

---

## 8. Decision

**DESIGN OPINION:** IMPLEMENT a `memory-framework` capability that composes the
vector store and owns extraction (injected), consolidation, eviction policies,
and scoping. Zero runtime dependencies; no model calls in core.

See ADR-0040.
