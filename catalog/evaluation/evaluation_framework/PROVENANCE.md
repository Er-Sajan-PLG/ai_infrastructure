# Provenance

- **Kind**: original
- **Based on**: None — independent implementation
- **License**: Apache-2.0
- **Notes**: Inspired-by (not derived-from) the convergent evaluation patterns
  observed structurally across RAGAS, TruLens, DeepEval, LangSmith and
  OpenInference (pinned commits in `study_pipeline/studied_repos/`). No code
  was executed or reused; the `Evaluator` protocol, `EvaluationResult` shape and
  suite aggregation are an independent design per ADR-0037. Composes
  `react-agent-loop` (ModelCaller), `tool-registry` (schema validation,
  ToolRegistry) and `basic-rag-pipeline` (RagAnswer, Citation) through their
  public interfaces.