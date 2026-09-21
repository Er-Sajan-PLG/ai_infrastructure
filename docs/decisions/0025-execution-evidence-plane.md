# ADR-0025 — Execution Evidence Plane: Structured Proof of What Happened

- **Status:** Accepted
- **Date:** 2026-09-21
- **Supersedes:** —
- **Superseded by:** —

## Context

The 18-repository study revealed a **convergent architectural pattern** that is
absent from our projects: an execution evidence plane — a structured, queryable
record of what an AI system actually did.

Currently:
- **JARVIS** records correlation IDs + JSON logs (telemetry, not evidence).
- **PROFESSOR-J** instruments via Langfuse (observability, not evidence).
- **STEMMA** stores a `provenance.source` field (a claim, not a chain).
- **LearningHub** has a tracer decorator (content-focused, not execution-focused).

None of these constitute a semantic execution record that can be queried,
replayed, or used to verify what happened.

### Source evidence

Three independent repositories implement this pattern differently:

1. **Phoenix** (`src/phoenix/trace/`): `Span(trace_id, span_id, kind, attributes,
   events, exceptions)` — a typed event model with `SpanKind(TOOL, LLM, AGENT,
   RETRIEIVER, EVALUATOR, GUARDRAIL)`. Spans are persisted in PostgreSQL with full
   attributes. OTEL is the internal representation, not an export format.

2. **SWE-agent** (`sweagent/types.py`): `StepOutput(thought, action, output,
   observation, tool_calls, state)` + `Trajectory = list[TrajectoryStep]` — every
   step of the agent loop is recorded as an immutable step in a trajectory list.

3. **Ragas** (`src/ragas/metrics/base.py`): `SingleTurnMetric` consumes
   `SingleTurnSample(input, output, reference, retrieved_contexts)` — metrics
   operate against execution records, not raw code.

### The problem this solves

Without structured execution evidence, we cannot:

- Prove what a worker did (reproducibility, audit)
- Replay a failed execution from a known-good checkpoint
- Evaluate worker output quality against what actually happened
- Detect drift between intended and actual behavior
- Support proof-of-delta (STEMMA requirement)

### What it is NOT

This is NOT:
- **Telemetry** (metrics, latency, cost) — that is Phoenix's secondary output
- **Logging** (unstructured text) — JARVIS already has this
- **Evaluation** (judging quality) — that is Ragas/Phoenix-evals
- **Durable execution** (checkpoint/resume) — that is LangGraph/Pydantic AI

Evidence is the *record*. Evaluation is the *judgment*. Durability is the *resume*.
These are separate architectural concerns.

## Decision

Implement an execution evidence plane across all projects. Each project records
what happened in a structured, queryable model specific to its domain.

### JARVIS: `app.evidence/`

Records worker execution: model invocations, tool calls, observations, state
changes, and results per task. Schema mirrors SWE-agent's `StepOutput`:
`WorkerStep(worker_id, thought, action, output, observation, tool_calls,
state, timestamp)`.

### PROFESSOR-J: `app.evidence/`

Records research workflow execution: planner steps, tool invocations, evaluator
outputs, and synthesis results. Langfuse instrumentation is preserved as a
transport layer; the evidence model is the authoritative record.

### STEMMA: Evidence chain extends provenance

Current `provenance.source` becomes a link in a chain:
`source → extraction → validation → verification → canonicalization`.
Each step records who/what/when/evidence. Validator output is attached.

### LearningHub: `packages/tracer/` becomes evidence model

Current tracer decorator records execution steps. Extend to structured
`ContentStep(pipeline_id, stage, input_ref, output_ref, actor, timestamp)`.

## Consequences

### Positive
- Reproducibility: executions can be replayed from evidence
- Auditability: human reviewers can inspect what actually happened
- Evaluation: evaluators consume structured evidence (not raw code)
- Debugging: failed executions can be diagnosed from the evidence trail

### Negative
- Storage: evidence accumulates; requires retention policies
- Complexity: every execution step must record to the evidence plane
- Performance: serialization cost at each step
- Schema evolution: evidence model must support backward compatibility

### Neutral
- Can be implemented incrementally (start with JARVIS, extend to others)
- Does not require framework adoption (Phoenix/Ragas/SWE-agent are references,
  not dependencies)

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| Adopt Phoenix directly | Too heavy (PostgreSQL, OTEL, TypeScript); we need a Python model |
| Use only correlation IDs (current JARVIS) | Not queryable, not replayable, not evidence |
| Use only Langfuse (current PROFESSOR-J) | Observability is not evidence; vendor coupling |
| Store only final outputs (current STEMMA) | Loses the chain of reasoning; cannot verify intermediate steps |
| Wait for OTel GenAI standard | Standard is still "Development" and moving; we need this now |

## References

- Phoenix: `src/phoenix/trace/schemas.py` (Span, SpanKind, SpanEvent)
- SWE-agent: `sweagent/types.py` (StepOutput, Trajectory)
- Ragas: `src/ragas/metrics/base.py` (SingleTurnMetric, SingleTurnSample)
- TruLens: `src/feedback/` (feedback functions consume execution records)
