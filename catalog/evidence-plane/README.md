# Evidence Plane

## what it is

The evidence plane is a structured, queryable record of what an AI system actually
did — not logs, but semantic evidence. It records actions, observations, state
changes, and results in a model that can be replayed, audited, and evaluated.

## why it exists

Without structured execution evidence, we cannot prove what a worker did, replay
a failed execution, evaluate worker output quality, or detect drift between
intended and actual behavior. This is the foundation for reproducibility,
proof-of-delta, and evaluation across all projects.

## status

The first concrete implementation is
[`catalog/observability/execution_trace_recorder/`](../observability/execution_trace_recorder/)
(`TESTED`, 50 tests). It provides flat, bounded JSONL traces with
prompt text, completions, and tool payloads **off by default**. Additional
adapters for semantic evidence, replayable actions, and state-change records
may be added later. The trace recorder's data model is designed to be
composable with those future adapters, not replaced by them.

## references

- ADR-0025: Execution Evidence Plane
- Phoenix `src/phoenix/trace/schemas.py` — Span, SpanKind, SpanEvent
- SWE-agent `sweagent/types.py` — StepOutput, Trajectory
- Ragas `src/ragas/metrics/base.py` — SingleTurnMetric, SingleTurnSample
