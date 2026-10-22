# ADR-0037: Evaluation Framework — Independent Implementation

**Status:** Accepted
**Date:** 2026-10-22
**Drivers:** Charter §18 (honest evaluation), Gap Analysis P0, Phase 5A implementation plan

## Context

The repository has 8 fully tested capabilities and 5 integration compositions, but **no evaluation primitives**. Charter §18 requires "honest evaluation" — without evaluation infrastructure, claims about agent quality, RAG correctness, or tool reliability cannot be substantiated. The Gap Analysis identifies Evaluation Framework as P0 (immediate priority).

## Decision

**IMPLEMENT** an independent, stdlib-only Evaluation Framework with:

1. **Protocol-first design** — `Evaluator` protocol, composable `EvaluationSuite`
2. **Deterministic evaluators first** — schema validation, length checks, citation coverage, exact match (zero model calls)
3. **RAG Triad evaluators** — faithfulness, answer relevance, context precision, context recall (require injected ModelCaller)
4. **Agent evaluators** — LogicalConsistency, ExecutionEfficiency, PlanAdherence, ToolSelection, ToolCalling (require injected ModelCaller)
5. **LLM-as-judge adapter** — injected ModelCaller, not a hard dependency
6. **TraceRecorder integration** — evaluators consume TraceRecords for full-trajectory evaluation
7. **Zero runtime dependencies** — stdlib only, all model calls injected

## Options Considered

| Option | Verdict | Reason |
|--------|---------|--------|
| **IMPLEMENT** (selected) | ✅ | Full control over protocol, zero deps, composes existing primitives |
| ADAPT RAGAS/TruLens/DeepEval | ❌ | Heavy dependencies (pydantic, numpy, torch), not stdlib, vendor lock-in |
| COMPATIBILITY (wrap existing) | ❌ | No standard evaluation protocol exists; each framework has own API |
| PROTOTYPE only | ❌ | Charter §18 requires production evaluation, not experiment |
| DEFER | ❌ | Blocking: Guardrails, Memory Framework, Multi-Agent Orchestration all need evaluation |

## Consequences

### Positive
- Enables honest evaluation of all existing capabilities (agent loops, RAG, tools)
- Deterministic evaluators work immediately with no API keys
- LLM-as-judge available when ModelGateway provides real provider access
- TraceRecorder integration allows full-trajectory evaluation (not just final output)
- Protocol design allows third-party evaluators without forking

### Negative
- LLM-backed evaluators require injected ModelCaller (not available until ModelGateway)
- Initial release covers ~60% of evaluation surface (deterministic + RAG triad + agent)
- Benchmark integration (MAFBench, GAIA, etc.) deferred to future work

## Implementation Scope

**catalog/evaluation/** with:
- `protocols.py` — Evaluator, EvaluationSuite, EvaluationResult, EvaluatorProtocol
- `evaluators/deterministic.py` — SchemaValidator, LengthValidator, CitationCoverage, ExactMatch
- `evaluators/rag_triad.py` — Faithfulness, AnswerRelevance, ContextPrecision, ContextRecall
- `evaluators/agent.py` — LogicalConsistency, ExecutionEfficiency, PlanAdherence, ToolSelection, ToolCalling
- `llm_judge.py` — LLMJudgeAdapter (injected ModelCaller)
- `aggregation.py` — WeightedAverage, PassFail, ConfidenceInterval
- `trace_integration.py` — evaluate_trace, evaluate_steps
- `examples/quickstart.py`
- `tests/` — 80+ tests

## Verification

- `make check` passes (lint, typecheck, catalog contract, tests)
- `make status` shows `evaluation` category with TESTED capability
- Coverage ≥ 85%
- Import-linter contracts maintained
- All tests pass with doubles (no network)