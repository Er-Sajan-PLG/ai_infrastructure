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

Empty. First expected implementation: JARVIS `app.evidence/`.

## references

- ADR-0025: Execution Evidence Plane
- Phoenix `src/phoenix/trace/schemas.py` — Span, SpanKind, SpanEvent
- SWE-agent `sweagent/types.py` — StepOutput, Trajectory
- Ragas `src/ragas/metrics/base.py` — SingleTurnMetric, SingleTurnSample
