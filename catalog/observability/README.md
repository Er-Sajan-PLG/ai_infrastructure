# Observability (catalog)

> **Status: 1 entry, `TESTED`.** This directory holds independent implementations at IMPLEMENTED or later (charter §4, §27).

## What it is

Trace recorders, span/step models, token and cost accounting, replay, and export to standard formats.

## Why it exists

Turning agent behavior into inspectable, testable data.

## How it works

Each entry documents its own architecture. The shared pattern in this category is a
**writer with an injected clock and a bounded record shape**: the clock is a
protocol so timing is deterministic in tests, and every string is bounded before it
reaches the sink so a record is always writable.

## Variants & types

| Entry | What it is |
|---|---|
| [`execution_trace_recorder`](execution_trace_recorder/) | Flat JSONL records with `parent_id` pointers, content **off by default**, and a write failure that is counted rather than raised. `TESTED`, 50 tests. |

## Landscape

Six systems studied for `execution-trace-recorder`, registered in
[`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md)
with `code_reused: false`: OpenTelemetry's GenAI conventions, OpenInference,
Langfuse, LangSmith, MLflow, and AgentOps.

**The findings that shaped the category:**

- **There is no stable standard to conform to.** The OTel GenAI conventions are
  `Development`, have just moved repositories, have **no published schema URL**, and
  have already reversed one content-capture decision. An entry here therefore
  publishes a *correspondence* rather than claiming compatibility.
- **The six do not agree on a taxonomy axis.** OTel uses an operation *verb*; the
  other five use a kind *noun*; MLflow keeps its taxonomy open on purpose. Any
  entry must pick one and say which.
- **Default-off content capture is the minority position**, and that is the argument
  for it: only one of six states that rule, and it is the only one with a privacy
  review.
- **Flat records with parent pointers are unanimous.** No surveyed system stores a
  nested tree, and a nested tree cannot be appended to without rewriting the file.

## Our implementations

[`execution_trace_recorder`](execution_trace_recorder/) — `TESTED`. The first
capability in this category, and the one that makes charter §18's *"demonstrated
run"* reviewable by someone who was not present.

## When to use / When not to use

Use an entry in this category when you need a persisted, reviewable record of what
a run did — and when you want the safe default to be what you get without thinking
about it.

Do **not** expect an entry here to export to a vendor's ingest endpoint or to
compute cost. `execution_trace_recorder` claims conformance to no standard, and
cost is DEFERred because a pricing table ages.

## Entry contract

Every entry under this directory is a subdirectory containing:

```text
<capability_id>/
├── README.md          # Category documentation standard (charter §13)
├── PROVENANCE.md      # Original source, license, what was changed and why (§11)
├── <implementation>   # Python, type-hinted, ruff-linted, black-formatted
├── examples/          # Runnable usage examples
└── tests/             # Unit/integration tests (§18)
```

Validate with `python ../../scripts/validate_catalog.py`.

## References & citations

See [`execution_trace_recorder/README.md`](execution_trace_recorder/README.md) and
its [`PROVENANCE.md`](execution_trace_recorder/PROVENANCE.md).