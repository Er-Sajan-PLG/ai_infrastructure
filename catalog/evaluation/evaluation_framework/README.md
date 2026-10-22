# Evaluation Framework

> **Status: `TESTED`.** Protocol-first, composable evaluation system. Zero runtime dependencies — standard library only; all model calls are injected.

| | |
|---|---|
| **Capability** | [`evaluation-framework`](../../../TAXONOMY.md) (category: evaluation) |
| **Specification** | [`specifications/evaluation-framework.md`](../../../specifications/evaluation-framework.md) |
| **Decision** | [ADR-0037](../../../docs/decisions/0037-evaluation-framework.md) — `IMPLEMENT` |
| **Research** | [`research/evaluation/evaluation-framework.md`](../../../research/evaluation/evaluation-framework.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — original, inspired-by |

## What it is

Composable evaluation primitives for AI systems: an `Evaluator` protocol, an
`EvaluationSuite` aggregator, deterministic evaluators (schema, length, citation
coverage, exact match, tool-call validation), RAG-triad evaluators
(faithfulness, answer relevance, context precision/recall), agent evaluators
(logical consistency, execution efficiency, plan adherence, tool selection,
tool calling), and an LLM-as-judge adapter over an injected `ModelCaller`. All
model-backed evaluators are optional and advisory; deterministic evaluators run
offline with no API key.

## How it works

```python
from evaluation_framework import (
    CitationCoverage,
    ExactMatch,
    LengthValidator,
    SchemaValidator,
    EvaluationSuite,
)
from evaluation_framework.suites import rag_evaluation_suite

suite = rag_evaluation_suite(min_citations=1)
result = suite.run(input="What is X?", output=rag_answer, context=chunks)
print(result.overall_score, result.overall_passed)
for r in result.results:
    print(r.name, r.score, r.passed)
```

**Design decisions:**

- **Protocol-first** — `Evaluator` is a `Protocol`; third parties implement
  without subclassing (D-1).
- **Injected model caller** — same pattern as `ReactAgentLoop`; enables
  testing with doubles (D-2).
- **Deterministic evaluators first** — schema, length, citation coverage,
  exact match run with zero model calls (D-3).
- **Normalised result** — `EvaluationResult(score in [0,1], passed,
  reasoning, threshold, metadata)` (D-4).
- **Suite composition** — `EvaluationSuite` runs multiple evaluators and
  aggregates with weights (D-5).
- **Trace integration** — `evaluate_trace`, `evaluate_steps`, `evaluate_rag`
  consume execution records, not just final output (D-6).
- **Zero runtime dependencies** — stdlib only (D-7).

## Our implementations

| Implementation | Language | Notes |
|---|---|---|
| [`protocols.py`](protocols.py) | Python | `Evaluator`, `EvaluationResult`, `EvaluationSuite`, `SuiteResult`, aggregation helpers |
| [`evaluators/deterministic.py`](evaluators/deterministic.py) | Python | Schema, length, citation coverage, exact match, tool-call validation |
| [`evaluators/rag_triad.py`](evaluators/rag_triad.py) | Python | Faithfulness, answer relevance, context precision/recall |
| [`evaluators/agent.py`](evaluators/agent.py) | Python | Logical consistency, execution efficiency, plan adherence, tool selection, tool calling |
| [`llm_judge.py`](llm_judge.py) | Python | `LLMJudgeAdapter` over injected `ModelCaller` |
| [`suites.py`](suites.py) | Python | Pre-built suites |
| [`trace_integration.py`](trace_integration.py) | Python | `evaluate_trace`, `evaluate_steps`, `evaluate_rag` |
| [`aggregation.py`](aggregation.py) | Python | Re-exported aggregation helpers |

## References

- [RAGAS](https://github.com/explodinggradients/ragas) — metric contracts, LLM-as-judge
- [TruLens](https://github.com/truera/trulens) — RAG triad, agent evaluators
- [DeepEval](https://github.com/confident-ai/deepeval) — G-Eval, faithfulness, hallucination
- [LangSmith](https://github.com/langchain-ai/langsmith-sdk) — correctness, coherence, relevance
- [OpenInference](https://github.com/Arize-ai/openinference) — evaluation span conventions