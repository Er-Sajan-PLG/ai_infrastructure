# Observability

> **Status: 1 capability studied.** This directory is a declared research category (charter §2, ADR-0001).

## What it is

Tracing, logging, metrics, telemetry, token/latency/cost accounting, execution traces, trajectory recording, debugging, replay, incident analysis.

## Why it exists

You cannot test, evaluate, or debug agent behavior you cannot see. Traces are the substrate for evidence.

## How it works

To be documented once the first capability in this category is studied. Research artifacts are expected at `research/observability/<capability-id>.md` and must label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6).

## Variants & types

Not yet surveyed.

## Landscape

Six sources were studied for [`execution-trace-recorder`](execution-trace-recorder.md), all
registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md)
with the charter §11 schema and `code_reused: false`:

| Source | What it contributed |
|---|---|
| OpenTelemetry GenAI semantic conventions | The `execute_tool` span shape; the default-off content-capture rule; the finding that the conventions are `Development` and just moved repositories |
| Langfuse | The provided-vs-derived split for usage and cost; a nullable end time |
| LangSmith | A sortable execution-order key (`dotted_order`) |
| MLflow (tracing) | The only documented serializable span JSON; stated truncation limits |
| AgentOps | A session-root integrity model; explicit streaming-timing names |
| OpenInference | A span-kind taxonomy; the Anthropic/OpenAI cache-token asymmetry |

**The finding that shaped the design:** the six disagree on the taxonomy axis (OTel uses
an operation *verb*, the others a kind *noun*), on whether the taxonomy is closed, and on
what unit a duration is in. "Compatible with all six" is not a coherent goal.

## Our implementations

None yet — `execution-trace-recorder` is `RESEARCHED`. See
[`../../TAXONOMY.md`](../../TAXONOMY.md) §4.

## When to use / When not to use

To be documented when the capability reaches `IMPLEMENTED`.

## References & citations

See [`execution-trace-recorder.md`](execution-trace-recorder.md) §11 for sources, verification method, and the list of what could not be verified.
