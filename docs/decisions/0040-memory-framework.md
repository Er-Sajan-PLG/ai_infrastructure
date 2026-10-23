# ADR-0040: Memory Framework (IMPLEMENT)

**Status:** Accepted
**Date:** 2026-10-23
**Drivers:** Charter §18 (honest evaluation), Phase 5B.2 of the implementation plan, ADR-0033 (vector-memory-store), ADR-0003 (zero runtime deps)

## Context

The repository has `vector-memory-store` (ADR-0033): a cosine-similarity store over
caller-assigned embeddings. It answers "what is similar to this query?" but owns
none of the memory lifecycle: extraction (which facts to keep), deduplication,
consolidation, eviction, or scoping. Components that need memory re-implement
these concerns ad hoc. Phase 5B.2 of the implementation plan brings a
`memory-framework` capability into scope to centralise them.

## Decision

**IMPLEMENT** a `memory-framework` capability as a stdlib-only library component:

1. **Protocol-first design** — `Memory` protocol: `add`, `search`, `consolidate`,
   `evict`.
2. **Composes VectorStore** — the framework delegates retrieval to
   `vector-memory-store` (ADR-0033); it never re-implements similarity search.
3. **Extraction is injected** — `Extractor` protocol (`extract(text) -> list[str]`),
   so the framework has no model dependency. The caller supplies the extraction
   callable (a `ModelCaller` adapter in production, a script in tests).
4. **Embedding is injected** — `Embedder` protocol; the framework does not own
   tokenisation.
5. **Consolidation is explicit** — `consolidate()` deduplicates by cosine
   similarity above a threshold; contradiction detection is deferred.
6. **Eviction is a policy** — `EvictionPolicy` protocol with `LRU`, `TTL`,
   `Importance` implementations; the caller chooses.
7. **Scoping is a namespace** — `scope` keys every memory id and filters every
   search (user / session / agent / global).
8. **Zero runtime dependencies** — stdlib only; in-memory.
9. **Sync-first** — matches the rest of the repository.

## Options Considered

| Option | Verdict | Reason |
|--------|---------|--------|
| **IMPLEMENT framework (selected)** | ✅ | Centralises lifecycle; composes VectorStore; unblocks agent memory |
| Extend VectorStore directly | ❌ | Couples retrieval to lifecycle; violates single responsibility |
| Adopt Mem0/Graphiti as dependency | ❌ | Violates ADR-0003; graph substrate out of scope |
| Graph-first (bi-temporal) | ❌ | Out of scope; no Neo4j |

## Consequences

- New catalog entry `catalog/memory/framework/`.
- New taxonomy entry `memory-framework` in `memory` category at `DECIDED`.
- Research record at `research/memory/memory-framework.md`.
- Specification at `specifications/memory-framework.md`.
- Composes `vector-memory-store` (ADR-0033).
- Does not change existing capabilities.

## Deferred

- Contradiction detection (needs a model call).
- Graph substrate / bi-temporal windows.
- Persistence.
- Async API.
