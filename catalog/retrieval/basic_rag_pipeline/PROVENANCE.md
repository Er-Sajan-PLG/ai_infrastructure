# Provenance

- **Kind**: original
- **Based on**: None — independent implementation
- **License**: Apache-2.0
- **Notes**: Inspired-by (not derived-from) the convergent RAG stage
  sequence observed structurally across 25 studied repositories (haystack,
  llama_index, LangChain, ragas — pinned commits in
  `study_pipeline/studied_repos/`). No code was executed or reused; the
  stage boundaries and the citation chain are an independent design per
  ADR-0034. Composes `vector-memory-store` (ADR-0033) and, via
  `adapters.py`, `model-provider-abstraction` (ADR-0007) through their
  public interfaces.
