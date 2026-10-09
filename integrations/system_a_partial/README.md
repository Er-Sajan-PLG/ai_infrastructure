# Integration: System A — Partial Adoption

> **Status: verified.** Our runtime + our memory + external provider + external
> embedding model, with tests. The provider and embedder are doubles; our
> components are real.

| | |
|---|---|
| **Kind** | Integration (charter §17, §31) |
| **Composes** | [`react-agent-loop`](../../catalog/agents/react_agent_loop/) (`TESTED`) · [`vector-memory-store`](../../catalog/memory/vector_store/) (`TESTED`) · external LLM provider (double) · external embedding model (double) |
| **Reproduce** | `make check` — or `.venv/bin/pytest integrations/system_a_partial/ -q` |
| **Tests** | 15 in [`tests/test_system_a.py`](tests/test_system_a.py) |

## What this proves

Phase 4 System A: *"partial adoption — our runtime + our memory + external
provider + external vector DB."* Our components (react-agent-loop,
vector-memory-store) are consumed through their public interfaces. The external
components (LLM provider, embedding model) are doubles with realistic
interfaces.

```
  query
    │
    ▼
┌──────────────────────────────┐
│ HashingEmbedder              │   ← external double
│ (text → vector)              │
└──────────────┬───────────────┘
               │ embedding
               ▼
┌──────────────────────────────┐
│ vector_store.VectorStore     │   ← OUR memory (TESTED)
│ (cosine similarity search)   │
└──────────────┬───────────────┘
               │ documents
               ▼
┌──────────────────────────────┐
│ react_agent_loop.run         │   ← OUR runtime (TESTED)
│                              │
│  ┌────────────────────────┐  │
│  │ RegistryDispatcher     │──┼──▶ tool_registry.ToolRegistry
│  └────────────────────────┘  │
│  ┌────────────────────────┐  │
│  │ ProviderCaller         │──┼──▶ model_provider.OpenAIProvider
│  └────────────────────────┘  │    (over ScriptedTransport — double)
└──────────────────────────────┘
```

## What the tests actually check

| Area | Representative assertion |
|---|---|
| Embedder | deterministic, different text → different vectors, normalized |
| Indexing | documents added to our vector store |
| Retrieval | cosine similarity returns most-relevant document first |
| RAG answer | query → retrieve → augment → agent → final answer |
| Tool dispatch | agent can call retrieve tool during answer generation |
| No network | `ScriptedTransport` never opens a socket |

## Limits — stated, not implied

- **Provider is scripted.** The LLM is a queue of canned responses.
- **Embedder is a hash.** `HashingEmbedder` is a deterministic double, not a
  real embedding model. Cosine similarity over hashed vectors is meaningful
  for exact token overlap but not semantic similarity.
- **In-memory only.** No persistence for documents or embeddings.
- **Not a framework.** This is a demonstration and a test fixture.

## Reproducing

```bash
make setup                                   # once per clone
.venv/bin/pytest integrations/system_a_partial/ -q  # 15 tests, no network
```
