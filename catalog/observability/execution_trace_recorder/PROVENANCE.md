# Provenance — `execution-trace-recorder`

Charter §11 draws a hard line between **inspired-by / studied-from** and
**derived-from / contains-reused-code**. This document states which this is.

## Summary

| Question | Answer |
|---|---|
| Does this contain code copied from another project? | **No** |
| Is it a derivative work of another project? | **No** |
| Was it informed by studying other projects? | **Yes** — documented below |
| Does it require a `NOTICE` update? | **No** |
| Does it require `attribution_requirements`? | **No** |
| Provenance class | **original** |

## What was studied

Six systems were surveyed (session 14), all against primary material — raw source
files and specification documents at the versions recorded in the registry. All
are registered in
[`docs/registry/RESEARCH_REGISTRY.md`](../../../docs/registry/RESEARCH_REGISTRY.md)
with `code_reused: false`.

| Source | License | What was taken |
|---|---|---|
| OpenTelemetry GenAI semantic conventions | Apache-2.0 | **Concept:** the `Opt-In` default for content attributes; the `execute_tool` span shape; the `gen_ai.operation.name` vocabulary, studied as the axis we did *not* choose |
| OpenInference | Apache-2.0 | **Concept:** a `TOOL` / `LLM` kind enum; the documented `prompt_details` token-accounting trap (Anthropic excludes cache tokens, OpenAI includes them) |
| Langfuse | MIT | **Concept:** `providedUsageDetails` vs `usageDetails` — the provided/computed split that became our `usage_provided` boolean |
| LangSmith | MIT | **Concept:** `dotted_order`, a sortable execution-order key — the reason our `sequence` field exists; and the observation that it has **no `agent` run type** |
| MLflow | Apache-2.0 | **Concept:** documented truncation limits; a JSON-serialised span; an error *status object* rather than a string |
| AgentOps | Apache-2.0 | **Concept:** the span-kind vocabulary, studied for the taxonomy comparison |

**In every case the adoption is conceptual.** Ideas are not copyrightable; their
expression is. No source file, function body, docstring, comment, or test from any
of these projects was copied, paraphrased, or transliterated. No OTel attribute
name appears in our record shape; the correspondence is *documented* in
`specifications/execution-trace-recorder.md` §4 and nowhere implemented.

## Why no `NOTICE` update is required

Charter §11 and [`NOTICE`](../../../NOTICE) require a notice update when
`code_reused: true`. That flag is `false` for all six entries. Five of the six are
permissively licensed, and no license obligation attaches to studying a project or
to independently implementing a published convention — **and we do not even claim
conformance to the convention we studied most closely.**

## Ideas adopted, and how they differ from their sources

| Idea | Source | This implementation |
|---|---|---|
| Content off by default | OTel | Adopted as a **policy object**, not a boolean flag — so enabling it is a named decision visible in a diff |
| Provided vs computed usage | Langfuse | Reduced from four fields to **one boolean** (`usage_provided`), because half of Langfuse's split exists to serve cost, which we decline |
| Sortable execution order | LangSmith `dotted_order` | A plain integer `sequence`, strictly increasing within a trace. Simpler than a dotted path because we do not need to sort across traces in one file |
| Documented truncation limits | MLflow | Limits stated as ours (`500` / `8000` / `10000`); truncation names the removed count rather than appending a bare `"..."` |
| Tool call and result as one node | all six | Adopted as the shape; implemented as a **context manager** so the record is written even when the block raises |
| Error status as a value, not a string | MLflow `SpanStatus` | A four-value `Outcome` enum, with `UNKNOWN` as a real value for a call that was never settled |

## Negative provenance — deliberately avoided

Recorded so a future session does not "helpfully" reintroduce them:

- **Claiming OTel conformance.** The target is `Development`, has moved
  repositories, has no schema URL, and has reversed a decision. A conformance
  claim would be a claim about a moving target.
- **OTel's operation-verb axis.** Five of the six use nouns, and a verb describes
  an action rather than a record.
- **An open (non-enum) record kind** (MLflow's deliberate choice). It costs the
  ability to validate, and four values are checkable.
- **An `AGENT` record kind.** LangSmith — a product whose whole subject is agent
  tracing — has no `agent` run type either.
- **Splitting a tool call and its result into two records.** No surveyed system
  does it, and it forces a join to answer "did this succeed?".
- **Capturing content by default.** Five of six do it; one of six has a privacy
  review. The reviewed rule wins.
- **A `"__REDACTED__"` sentinel** (OpenInference's placeholder). It puts a value
  where the honest answer is "we did not look".
- **A bare `latency: float`.** The units hazard research §8 documents.
- **Raising on a mid-run write failure**, and **silently swallowing one**. Each is
  half wrong; the failure is counted and inspectable instead.
- **A price table.** Cost is DEFERred.
- **Nesting the tree.** Unanimous across six: records are flat with a parent id.
- **Importing `react_agent_loop.Step`.** The recorder stays usable without the loop.

## Verification

- The package imports **only the standard library** — asserted by
  `test_the_recorder_imports_only_the_standard_library`, which parses the import
  statements and checks them against `sys.stdlib_module_names`.
- The recorder imports **none** of `react_agent_loop`, `tool_registry`,
  `model_provider`, `mcp_client` — asserted by
  `test_the_recorder_does_not_import_the_agent_loop`. That test parses the module
  rather than grepping it, because the module's own docstring names those projects
  to explain why they are not imported.
- No file in this directory contains code from any surveyed project.
- Licenses were confirmed at the version studied, per the registry rule that
  licenses change.

## Maintainer sign-off

Per charter §22, `code_reused: true` would require human review. It is `false`
here, so no gate is triggered — but the classification is recorded explicitly so
the claim is auditable rather than assumed.