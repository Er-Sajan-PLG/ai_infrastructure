# Evaluation

> **Status: one entry — `evaluation-framework` (TESTED).** See `evaluation-framework.md`.

## What it is

Model, agent, benchmark, task, trajectory, tool-use, regression, behavioral, adversarial, hallucination, reliability, and capability evaluation.

## Why it exists

Without evaluation, every claim about an AI system is an anecdote. This category builds the evidence layer.

## How it works

Research artifacts live at `research/evaluation/<capability-id>.md` and must label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6).

## Variants & types

Not yet surveyed.

## Landscape

External projects studied: RAGAS, TruLens, DeepEval, LangSmith, OpenInference (structural observation only, recorded in `evaluation-framework.md`).

## Our implementations

- `evaluation-framework` — protocol-first, deterministic evaluators first, LLM-as-judge via injected `ModelCaller` (ADR-0037). See `catalog/evaluation/evaluation_framework/`.

## When to use / When not to use

To be filled from evidence, not intuition.

## References & citations

- ADR-0026: Evaluator/Verifier Separation
- ADR-0037: Evaluation Framework — Independent Implementation
- Ragas `src/ragas/metrics/` — metric contracts, LLM-as-judge
- Phoenix-evals `packages/phoenix-evals/` — evaluation from traces