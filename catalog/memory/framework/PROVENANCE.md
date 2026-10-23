# Provenance

- **Kind**: original
- **Based on**: None — independent implementation
- **License**: Apache-2.0
- **Notes**: Inspired-by (not derived-from) the memory APIs in Mem0 (add/search,
  user scoping, ADD-only), Zep/Graphiti (no LLM in the read path, contradiction
  detection deferred), Letta (agent-driven tiers out of scope), LangMem
  (background consolidation), and Cognee (remember/recall/improve/forget). No
  code was executed or reused. The ``Memory`` protocol, ``MemoryItem``,
  ``Extractor`` / ``Embedder`` / ``EvictionPolicy`` seams, ``InMemoryMemory``,
  and the eviction policies are an independent design per ADR-0040. Composes
  ``vector-memory-store`` (ADR-0033) through its public interface.
