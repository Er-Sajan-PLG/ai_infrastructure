# Execution Trace Recorder

> **Status: `TESTED`.** Writes what an agent run did as flat, bounded JSONL
> records — with prompt text, completions and tool payloads **off by default**.
> Zero runtime dependencies; standard library only.

| | |
|---|---|
| **Capability** | [`execution-trace-recorder`](../../../TAXONOMY.md) (category: observability) |
| **Specification** | [`specifications/execution-trace-recorder.md`](../../../specifications/execution-trace-recorder.md) |
| **Decision** | [ADR-0010](../../../docs/decisions/0010-execution-trace-recorder.md) — `IMPLEMENT` |
| **Research** | [`research/observability/execution-trace-recorder.md`](../../../research/observability/execution-trace-recorder.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — inspired-by, **not** derived-from |
| **Depends on** | nothing |
| **Standards** | **none claimed** — see below |

## What it is

A recorder that persists one agent run as append-only JSONL. Four record kinds —
`trace_start`, `model_call`, `tool_call`, `trace_end` — flat, with `parent_id`
pointers. Every duration is an integer named with its unit. Every string is
bounded. Nothing sensitive is written unless a caller asks for it.

It is the first capability in the **observability** category, and the one that
makes charter §18's *"demonstrated run"* reviewable by someone who was not
present: `react-agent-loop` returns a `Step` trace in memory, and this persists it.

## Why it exists

`AgentResult` carries the trace of a *single* run. Nothing persisted it, nothing
aggregated across runs, and nothing recorded how long a step took. The taxonomy
entry states the consequence: *"Without traces, agent behavior cannot be tested,
evaluated, or debugged with evidence."*

Three findings shaped the design, all from
[`research/observability/execution-trace-recorder.md`](../../../research/observability/execution-trace-recorder.md):

1. **There is no standard to conform to.** The OTel GenAI conventions are marked
   `Development`, have just moved repositories, have **no published schema URL**,
   and have already **reversed** one content-capture decision — `gen_ai.prompt`
   and `gen_ai.completion` are `Deprecated` with *"Removed, no replacement at this
   time."* So this capability claims **no conformance** and publishes a
   correspondence table (spec §4) instead.
2. **Default-off content capture is the minority position, and that is the
   argument for it.** Only **one of six** surveyed systems states a default-off
   policy — OTel — and it is the only one with a privacy review. The other five
   capture by default and redact afterwards, or say nothing. The majority practice
   is not the safe default.
3. **None of the six has a field for why the run ended.** `react-agent-loop`
   already computes `StopReason`. It is arguably the most valuable field in a
   trace, and it is ours to add.

## How it works

```python
from execution_trace_recorder import TraceRecorder

with TraceRecorder("run.jsonl") as recorder:
    recorder.start_trace()
    with recorder.model_call(model="gpt-4o-mini") as call:
        call.succeed(input_tokens=12, output_tokens=8, usage_provided=True)
    with recorder.tool_call(name="add", arguments={"a": 1, "b": 2}) as call:
        call.succeed(result=3)
    recorder.end_trace(stop_reason="final_answer")
```

Run the tour — no network, no model, no API key:

```bash
.venv/bin/python catalog/observability/execution_trace_recorder/examples/quickstart.py
```

### The pieces

| Module | Owns |
|---|---|
| `records.py` | `RecordKind`, `Outcome`, `TraceRecord` — the flat shape. |
| `clock.py` | The injected `Clock` protocol and `SystemClock`. |
| `capture.py` | `CapturePolicy`, `CaptureNothing` (default), `CaptureEverything`. |
| `bounds.py` | `Bounds`, `truncate`, `json_safe` — nothing unbounded is written. |
| `recorder.py` | `TraceRecorder` and the two context managers. |
| `errors.py` | `TraceRecorderError`, `WriteFailures`. |

### The decisions a reader should check

- **A tool call and its result are ONE record.** OTel puts the result as an
  attribute on the same span; OpenInference and MLflow carry `tool_call.id`
  alongside. None of the six models them as two nodes, and splitting them would
  make "did this call succeed?" require a join.
- **`duration_ns`, never a bare `latency`.** Six systems use at least four unit
  conventions, and **MLflow disagrees with itself within one object** — span times
  in nanoseconds, trace duration in milliseconds. An unlabelled float is a bug
  waiting for a reader who assumed seconds.
- **`usage_provided` distinguishes what the provider said from what we computed.**
  Adopted from Langfuse's `providedUsageDetails` vs `usageDetails` split. `None`
  tokens with `usage_provided=False` is an honest "not reported"; `0` would be a
  lie.
- **A write failure does not propagate, and does not vanish.** A recorder that
  raises can kill the run it was observing; one that swallows loses the evidence.
  It is caught, counted, and exposed as `recorder.write_failures`.

### Security posture

- **Content is off by default.** `content` is `None`, never a `"__REDACTED__"`
  sentinel — a sentinel would put a value where the honest answer is "we did not
  look". A trace produced under the default policy is safe to commit as a test
  fixture.
- **Everything is bounded before it is written.** An error message is capped at
  500 chars, content strings at 8000, and records at 10000; a truncated field is
  named in `truncated`.
- **An unserialisable payload cannot kill the run.** Anything JSON cannot
  represent becomes a bounded string, and a cyclic structure terminates instead of
  raising `RecursionError`.
- **A caller who passes `CaptureEverything()` is capturing PII** when the model or
  the tools handle any. That is the caller's decision, made explicitly and visible
  in the diff.

## Our implementations

| Implementation | Notes |
|---|---|
| `execution_trace_recorder` | This entry. `TESTED`, 50 tests. |

### Composing with `react-agent-loop`

The recorder **does not import the loop** (ADR-0010 D-12). An adapter that maps
`Step` → records belongs in the loop's own `adapters.py`, beside the two adapters
already there, because that is the module that already imports its dependencies.

Until that adapter exists, a caller records explicitly:

```python
recorder.start_trace()
with recorder.model_call(model=agent.model) as call:
    response = caller.call(messages, tools=schemas)
    call.succeed(
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        usage_provided=True,
    )
recorder.end_trace(stop_reason=str(result.reason))
```

## When to use / When not to use

**Use it** when you need a persisted, reviewable record of what a run did, and you
want the safe default to be the one you get without thinking about it.

**Do not use it** when:

- you need OTLP or an HTTP ingest — there is no exporter, and no conformance claim;
- you need cost — it is **DEFER**red, because a pricing table ages;
- you need aggregation or statistics — that is a second responsibility, and a
  reader over these records is a better place for it;
- you expect it to explain *what the model said* without opting in. It will not,
  by design.

## Known limitations

Stated here so they are not assumed away (spec §12):

1. **No conformance claim to any standard**, because there is no stable one.
2. **No cost.** Recorded usage only.
3. **No aggregation.** Compose it from the records.
4. **No sampling**, so a long run writes every record.
5. **`max_records` drops records past the cap** and counts the drops — a bounded
   trace of an unbounded run is necessarily incomplete.
6. **Content is off by default**, so a trace alone does not explain what the model
   said. That is the intended trade.
7. **A write failure loses that record.** The count and the first message survive;
   the record does not.
8. **No concurrency.** One recorder, one trace, one thread.

## Testing

50 tests, no network, no real clock, no model.

- **A scripted clock** — every duration assertion is exact rather than tolerant.
- **A real file** in `tmp_path`, read back and parsed — the only test that proves
  the on-disk format.
- **An in-memory sink**, and an `ExplodingSink` that fails from a chosen call
  onward, for the write-failure paths.

The failure paths are the majority: a mid-run write failure counted and not
raised, a truncated message with the field named, a cycle that terminates, a
broken `__repr__` that does not kill the run, a doubled settlement that raises, an
exception inside a tool block that still writes a record.

## Relationship to Evidence Plane

The execution trace recorder is the first concrete implementation within the
**evidence-plane** category (ADR-0025). It records structured execution traces.
The broader evidence plane may later include additional adapters for semantic
evidence, replayable actions, and state-change records. The trace recorder's
data model is designed to be composable with those future adapters, not replaced
by them.

## References

- [`specifications/execution-trace-recorder.md`](../../../specifications/execution-trace-recorder.md)
- [`docs/decisions/0010-execution-trace-recorder.md`](../../../docs/decisions/0010-execution-trace-recorder.md)
- [`research/observability/execution-trace-recorder.md`](../../../research/observability/execution-trace-recorder.md)
  — six systems surveyed, all `code_reused: false`
- [`PROVENANCE.md`](PROVENANCE.md)