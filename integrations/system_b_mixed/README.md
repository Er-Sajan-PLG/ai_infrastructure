# Integration: System B — Mixed

> **Status: verified.** External runtime + our observability/safety/eval,
> with tests. The runtime is a double; our components are real.

| | |
|---|---|
| **Kind** | Integration (charter §17, §31) |
| **Composes** | external runtime (double) · [`execution-trace-recorder`](../../catalog/observability/execution_trace_recorder/) (`TESTED`) · our evaluation scoring |
| **Reproduce** | `make check` — or `.venv/bin/pytest integrations/system_b_mixed/ -q` |
| **Tests** | 13 in [`tests/test_system_b.py`](tests/test_system_b.py) |

## What this proves

Phase 4 System B: *"mixed — external runtime + our harness/eval/safety/observability."*
The external runtime is a double that does NOT use our `react-agent-loop`. Our
`execution-trace-recorder` wraps the external runtime, and our evaluation
scoring reads the trace output.

```
  task
    │
    ▼
┌──────────────────────────────┐
│ ExternalRuntime              │   ← external double (NOT our react-agent-loop)
│ (scripted agent loop)        │
│                              │
│  ┌────────────────────────┐  │
│  │ model_provider        │──┼──▶ OpenAIProvider (over ScriptedTransport)
│  └────────────────────────┘  │
└──────────────┬───────────────┘
               │ trace records
               ▼
┌──────────────────────────────┐
│ execution_trace_recorder     │   ← OUR observability (TESTED)
│ (JSONL trace file)           │
└──────────────┬───────────────┘
               │ trace file
               ▼
┌──────────────────────────────┐
│ evaluate()                   │   ← OUR evaluation scoring
│ (reads trace, computes score)│
└──────────────────────────────┘
```

## What the tests actually check

| Area | Representative assertion |
|---|---|
| External runtime | returns answer, records tool calls, respects max_steps |
| Does NOT use our loop | ExternalRuntime has no dispatcher/caller/agent |
| Trace recording | trace file written with start/end records |
| Evaluation | score computed from trace + result |
| No network | ScriptedTransport never opens a socket |

## Limits — stated, not implied

- **Runtime is scripted.** The external agent is a simple loop over canned responses.
- **Evaluation is simple.** A scoring function over trace records, not a full eval framework.
- **No real safety seam.** The mcp-client approval seam is not exercised here; it is tested in its own suite.
- **Not a framework.** This is a demonstration and a test fixture.

## Reproducing

```bash
make setup                                   # once per clone
.venv/bin/pytest integrations/system_b_mixed/ -q  # 13 tests, no network
```
