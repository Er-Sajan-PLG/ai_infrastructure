# Specification: Basic RAG Pipeline

## 1. Purpose

A minimal, framework-free retrieval-augmented generation pipeline over
caller-provided documents: chunk → embed → index → retrieve → augment →
generate. Zero runtime dependencies. Embedder, store and generator are all
injected seams; the pipeline itself owns only the stage wiring, the chunking,
the prompt assembly, and the citation chain.

Decision: [ADR-0034](../docs/decisions/0034-basic-rag-pipeline.md).
Research: [research/retrieval/basic-rag-pipeline.md](../research/retrieval/basic-rag-pipeline.md).

## 2. Interface

```python
class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...

class Generator(Protocol):
    def generate(self, prompt: str) -> str: ...

@dataclass(frozen=True)
class Chunk:
    id: str        # "<doc_id>#<index>"
    doc_id: str
    index: int
    text: str
    start: int     # offset into the original document
    end: int

def chunk_text(text: str, *, doc_id: str, size: int = 800,
               overlap: int = 200) -> list[Chunk]: ...

@dataclass(frozen=True)
class Citation:
    chunk_id: str
    doc_id: str
    score: float   # cosine similarity, -1.0 to 1.0 (from the store)

@dataclass(frozen=True)
class RagAnswer:
    text: str
    citations: tuple[Citation, ...]

def build_prompt(query: str, results: Sequence[SearchResult]) -> str: ...

class BasicRagPipeline:
    def __init__(self, *, embedder: Embedder, store: VectorStore,
                 generator: Generator, size: int = 800,
                 overlap: int = 200) -> None: ...
    def index(self, documents: Mapping[str, str]) -> int: ...   # → chunk count
    def retrieve(self, query: str, k: int = 3) -> list[SearchResult]: ...
    def answer(self, query: str, k: int = 3) -> RagAnswer: ...

class ProviderGenerator:   # adapters.py — the only module importing model_provider
    def __init__(self, *, provider: Provider, transport: Transport,
                 api_key: str, model: str,
                 system: str | None = None,
                 max_output_tokens: int | None = None,
                 temperature: float | None = None) -> None: ...
    def generate(self, prompt: str) -> str: ...
```

## 3. Design Decisions

### D-1: Character windows with overlap, snapped to whitespace
Chunking is fixed-size character windows with `overlap` characters of
shared context, adjusted to end at a whitespace boundary when one exists
within the window. Character-based because token-exact sizing requires a
tokenizer dependency (rejected); whitespace snapping because splitting
mid-word degrades embedding quality. Deterministic by construction.

### D-2: Chunk identity is `<doc_id>#<index>`, stable across re-ingestion
The chunk index is its position in the chunk sequence for that document, so
re-indexing the same document produces the same ids and the store's
overwrite semantics make re-ingest idempotent. Offsets (`start`, `end`) are
recorded so a citation can be resolved back to the source text.

### D-3: The embedder is an injected protocol, not a model
The repository owns no embedding model and must not acquire one. `Embedder`
is a structural protocol (one method: text in, vector out); tests use a
deterministic hashing double, production injects a real embedder. This is
exactly the composition boundary System A already exercises.

### D-4: The store is an injected `VectorStore` instance
`vector-memory-store` (ADR-0033) is TESTED and already implements cosine
similarity, caller-assigned IDs, overwrite-on-duplicate, and metadata
preservation. The pipeline uses it through its public interface only
(`add`, `search`, `__len__`) and does not re-implement any of it.
Metadata stored per chunk: `doc_id`, `chunk_index`, `text`.

### D-5: Generation is one call behind a `Generator` protocol
`generate(prompt) -> str`, with `ProviderGenerator` (adapters.py) binding
`model-provider-abstraction`. Same protocol-plus-adapter pattern as
`react-agent-loop` (ADR-0008): every code path testable with a scripted
double, no network in the core, no provider wire format anywhere but the
adapter. The pipeline does not retry, stream, or use tools — those are the
caller's decisions (retry) or later capabilities.

### D-6: Citations are reported, not parsed
`RagAnswer.citations` is the retrieved chunks in rank order with their
similarity scores — the evidence that entered the prompt. The pipeline does
not parse the model's prose to guess which chunks it used. Parsing and
verifying model-attributed citations is a separate capability; a basic
pipeline that pretended to verify would violate charter §4.

### D-7: The augmented prompt is built by a public function
`build_prompt(query, results)` is public so that "what the model saw" is
inspectable without reading pipeline internals. Each context block is
prefixed with its chunk id, so a future citation-parsing capability has
anchors, and the model can be instructed to cite them.

### D-8: Synchronous, one call, no reranking, no hybrid search
Matches model-provider-abstraction and the store. Reranking, hybrid lexical
search, metadata filtering and streaming are deferred, not silently absent.

### D-9: Empty retrieval is a valid state
If the store is empty or nothing is indexed, `answer()` still builds a
prompt stating that no documents were retrieved and still calls the
generator. Retrieval quality is not generation error handling.

## 4. Non-Goals

- Persistence (the store is in-memory)
- Metadata filtering, reranking, hybrid search
- Token-exact chunk sizes (no tokenizer dependency)
- Citation parsing/verification from model output
- Streaming and async
- Multi-hop / iterative retrieval (that is `react-agent-loop` territory)
- Prompt injection defense beyond documentation (documents are untrusted;
  the pipeline reports evidence, it does not sanitize semantics)

## 5. Error Handling

- Empty or whitespace-only query → `ValueError` (there is nothing to embed)
- `k <= 0` → `ValueError` (validated by the store; the pipeline passes
  through and documents it)
- `size < 1`, `overlap < 0`, `overlap >= size` → `ValueError` at pipeline
  construction and in `chunk_text` — a bad configuration should fail before
  any embedding is paid for
- Empty document text → zero chunks, contributed to the count (not an error)
- Empty `documents` mapping → index() is a no-op returning 0
- Embedding dimension mismatch surfaces from the store's search as
  `ValueError` (documented, not compensated)

## 6. Testing Strategy

- `chunk_text`: size/overlap validation; empty text; text shorter than a
  window; exact-boundary windows; whitespace snapping; offsets satisfy
  `text[start:end] == chunk.text`; ids stable and ordered; no infinite loop
  on pathological whitespace-only or unbroken text (progress guarantee)
- `index`: chunk count returned; store contents and metadata; deterministic
  re-ingestion overwrites rather than duplicates; empty docs
- `retrieve`: rank order by similarity (deterministic double embedder);
  `k` respected; validation errors
- `answer`: prompt contains query, chunk ids and context text (assert on the
  prompt captured by the scripted generator); citations equal retrieved
  results in order, with doc_ids and scores; empty-store answer still
  generates; generator called exactly once
- `ProviderGenerator`: fake transport captured request — model, messages,
  system, token cap; response text returned; provider errors propagate
- Entry tests import only stdlib + the entry + `model_provider`; no network
