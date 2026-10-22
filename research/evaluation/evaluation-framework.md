# Research Record: Evaluation Framework

- **Capability:** `evaluation-framework` (category: evaluation)
- **Status:** `RESEARCHED` → `UNDERSTOOD`
- **Date:** 2026-10-22
- **Decision:** see [ADR-0037](../../docs/decisions/0037-evaluation-framework.md) *(IMPLEMENT)*
- **Sources:** Charter §18 (honest evaluation), Gap Analysis P0, Phase 5A implementation plan,
  RAGAS/TruLens/DeepEval/LangSmith/OpenInference (structural observation only)

Claims are labelled per charter §6:
**FACT** (verified, cited) · **OBSERVATION** (inferred from docs/structure) ·
**INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice, not a fact).

## 1. The problem, stated without reference to any implementation

> Given a system's input, output, and context, produce a normalised score in
> [0, 1] with a pass/fail verdict and human-readable reasoning, for one or more
> criteria, and aggregate the per-criterion results into a suite verdict.

Stated that way, the capability decomposes into four separable concerns.
**DESIGN OPINION.**

| # | Concern | Question it answers |
|---|---|---|
| 1 | **Evaluator** | Does this single criterion hold for this input/output/context? |
| 2 | **Suite** | How are many criteria combined and thresholded? |
| 3 | **Judge** | When a criterion needs a model, how is the model injected? |
| 4 | **Trace** | How is an execution record turned into something evaluable? |

**INFERENCE — the load-bearing boundary is 1 vs 3.** Deterministic evaluators
(schema, length, citation coverage, exact match, tool calls) need no model and
run offline; LLM-backed evaluators need an injected `ModelCaller`. Fusing the
two makes deterministic evaluation depend on network/credentials and hides the
cost of a judge call. Every studied framework separates deterministic checks
from LLM-as-judge (§3).

## 2. Constraints we are designing under

| Constraint | Source | Consequence |
|---|---|---|
| **Zero runtime dependencies** | ADR-0003 | stdlib only; no pydantic, numpy, torch, ragas, deepeval. |
| **Model calls are injected** | ADR-0007, charter §31 | No evaluator imports a provider; judge models arrive via `ModelCaller`. |
| **Protocol-first** | charter §31 | `Evaluator` is a `Protocol`; third parties implement without subclassing. |
| **Honest evaluation** | charter §18 | Scores must be reproducible and thresholded; no claim without artifacts. |
| **Deterministic first** | ADR-0037 | Deterministic evaluators ship and pass without API keys; LLM judges are advisory. |
| **Component independence** | charter §31 | Usable standalone; doubles for model caller make every path testable. |

## 3. Evidence from the study pipeline

**OBSERVATION — RAGAS, TruLens and DeepEval all separate metric from judge.**
RAGAS `src/ragas/metrics/base.py` defines `SingleTurnMetric` with `MetricWithLLM`
and `MetricWithEmbeddings` mixins; Phoenix-evals splits `evaluators/`, `metrics/`,
and `llm/`. **INFERENCE:** the metric (criterion) and the judge (model) are
distinct components in every studied framework, and conflation is the common
anti-pattern.

**OBSERVATION — deterministic checks are first-class in every framework.**
Guardrails AI, NeMo Guardrails and DeepEval all ship regex/length/JSON validators
that require no model. **INFERENCE:** deterministic evaluation is the baseline
that makes LLM-as-judge affordable and debuggable.

**FACT — no standard evaluation protocol exists across frameworks.** Each
framework defines its own metric base class and result shape. **INFERENCE:**
a small, stdlib `Evaluator` protocol with a normalised `EvaluationResult` is
the interoperable seam this repository can own (ADR-0037).

## 4. What we are building

- `protocols.py` — `Evaluator` (Protocol), `EvaluationResult`, `EvaluationSuite`, `SuiteResult`, aggregation helpers.
- `evaluators/deterministic.py` — `SchemaValidator`, `LengthValidator`, `CitationCoverage`, `ExactMatch`, `ToolCallValidator`.
- `evaluators/rag_triad.py` — `Faithfulness`, `AnswerRelevance`, `ContextPrecision`, `ContextRecall` (injected `ModelCaller`).
- `evaluators/agent.py` — `LogicalConsistency`, `ExecutionEfficiency`, `PlanAdherence`, `ToolSelection`, `ToolCalling`.
- `llm_judge.py` — `LLMJudgeAdapter` wrapping any injected `ModelCaller`.
- `aggregation.py` — re-exported aggregation helpers.
- `suites.py` — pre-built suites (`rag_evaluation_suite`, `agent_evaluation_suite`, ...).
- `trace_integration.py` — `evaluate_trace`, `evaluate_steps`, `evaluate_rag`.

## 5. Research conclusion

**DESIGN OPINION — implement independently.** The ecosystem's evaluation
libraries carry heavy dependencies (pydantic, numpy, torch) and vendor-specific
APIs; none offers a stdlib, protocol-first, injection-friendly seam. Owning the
protocol keeps deterministic evaluation offline, makes LLM judges swappable, and
composes with the existing `TraceRecorder`, `ToolRegistry` and `ModelProvider`
seams without coupling. See ADR-0037.
path">
/home/sajan/Projects/ai_infrastructure/research/evaluation/evaluation-framework.md