# ReAct Agent Loop

> **Status: `TESTED`.** A bounded agent loop that composes a tool registry and a
> vendor-neutral model provider. Zero runtime dependencies; both dependencies are
> injected through protocols it defines.

| | |
|---|---|
| **Capability** | [`react-agent-loop`](../../../TAXONOMY.md) (category: agents) |
| **Specification** | [`specifications/react-agent-loop.md`](../../../specifications/react-agent-loop.md) |
| **Decision** | [ADR-0008](../../../docs/decisions/0008-react-agent-loop.md) — `IMPLEMENT` |
| **Research** | [`research/agents/react-agent-loop.md`](../../../research/agents/react-agent-loop.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — inspired-by, **not** derived-from |
| **Depends on** | [`tool-registry`](../../tools/tool_registry/) (`TESTED`), [`model-provider-abstraction`](../../models/model_provider/) (`TESTED`) |

## What it is

The simplest agent control loop that grounds model output in tool interaction with
a clear termination condition: call the model, run what it asks for, feed the
results back, and stop at a defined point.

It is a **dispatcher with a bound**, not a reasoner. Reasoning is the model's job;
the loop's job is dispatch and containment. It does not plan, remember across
runs, retry, or run anything concurrently.

## Why it exists

Three reasons, each from evidence rather than intuition:

1. **Every capability above this one needs the same control flow.** Without a
   bounded, inspectable loop, each one reinvents it — and the reinvented version
   is usually the one that runs forever.
2. **Repetition is a documented failure with no shipped defence.** The ReAct paper
   names "one frequent error pattern specific to ReAct, in which the model
   repetitively generates the previous thoughts and actions" as its most common
   ReAct-specific failure, and offers only a guess about decoding. No surveyed
   framework ships a first-class duplicate-action detector.
3. **This is the first capability that composes.** It proves the two layers below
   it actually fit together; if the loop needed the registry's internals or a
   provider's wire format, the boundaries would be wrong.

## How it works

```python
from react_agent_loop import Agent, StopReason, run

result = run(
    "What is 2 + 3?",
    agent=Agent(model="gpt-4o-mini"),
    model_caller=my_caller,      # injected
    dispatcher=my_dispatcher,    # injected
)

if result.ok:
    print(result.final_text)
else:
    print(f"stopped: {result.reason.value}")
```

Run the full tour — eleven design properties, no network:
`python catalog/agents/react_agent_loop/examples/quickstart.py`

### The two seams

```
 caller              this capability             injected
┌──────┐ ChatRequest? no -- the loop owns  ┌───────────┐
│ agent│ ──messages──▶│   for step in 1..N  │ ModelCaller│
│ loop │ ◀──response──│        │            └───────────┘
└──────┘              │        ▼            ┌─────────────┐
                      │  ToolDispatcher ──▶│  registry   │
                      └────────────────────└─────────────┘
```

The loop imports **neither** capability's behaviour. It defines `ModelCaller` and
`ToolDispatcher` and ships small adapters (`ProviderCaller`,
`RegistryDispatcher`) that bind them. Everything else runs against the protocols.

**Why this matters concretely.** The entire test suite — 47 tests, including every
failure path — runs against scripted doubles with no network, no model, no API key
and no registry. That is only possible because the seams are injected.

### Termination: three reasons, and only three

```python
class StopReason(Enum):
    FINAL_ANSWER = "final_answer"        # the model produced no tool call
    STEP_LIMIT = "step_limit"            # the cap was reached
    REPEATED_ACTION = "repeated_action"  # consecutive identical calls
```

Exhaustion is a **result**, not an exception — the trace is the useful artefact
when a loop runs out of budget. A caller that wants an exception raises on
`reason is not FINAL_ANSWER`.

There is deliberately **no** stop reason for a provider outage or a registry
failure. Those propagate. A loop that swallowed a provider outage and reported
"finished" would be lying.

## Variants & types

### The step cap

`max_steps: int = 12`, caller-overridable.

| Source | Cap |
|---|---|
| ReAct paper (HotpotQA / FEVER) | 7 / 5 — the observed 99th percentile |
| smolagents | 20 |
| **this implementation** | **12** |

The paper's cap was set from data, not taste: only **0.84%** and **1.33%** of
*correct* trajectories used the full 7/5 budget, so a modest cap costs almost
nothing. Ours is a documented default, not a benchmark.

**The cap is checked before the model call *and* before dispatch**, so
`max_steps=1` means exactly one model call and no tool dispatch. Running a tool
whose result the model will never see would spend money and add a misleading trace
entry.

### Repetition detection

Three **consecutive** calls with the same name and the same canonicalised
arguments stop the run with `REPEATED_ACTION`, *before* the third is dispatched —
the brake exists to avoid the work, not to perform it once more and notice.

Arguments are canonicalised with `json.dumps(..., sort_keys=True)`, because
reordering keys is free for a model and would otherwise evade the check.

| `repeat_limit` | Behaviour |
|---|---|
| `3` (default) | stop after three consecutive identical calls |
| `None` | detection disabled — for a workload that legitimately polls |
| `1` | **rejected**: a single call is not a repetition |

**Honest limitation.** This detects *consecutive* duplicates only. A two-cycle
(A → B → A → B) evades it. Full cycle detection needs a window and a policy for
what to do on a hit, and is deferred.

### Tool failures: the model-actionability split

The dispatcher reports whether the model can act on a failure, and the loop obeys
it — the registry already computes this (ADR-0006 D-4), and re-deciding it here
would let the two drift.

| Failure | `model_visible` | Loop behaviour |
|---|---|---|
| `INVALID_ARGUMENTS` | `True` | becomes an observation; the loop continues |
| `EXECUTION_FAILED` | `True` | becomes an observation; the loop continues |
| `NOT_FOUND` | `False` | **raises** `UnactionableToolError` |

A hallucinated name cannot be corrected by the model that hallucinated it — the
model has no view of the registry it failed to match against — so feeding it back
would invite a second hallucination of the same name.

**Why raise rather than add a fourth stop reason?** ADR-0008 D-2 fixes the
stop-reason set at three, and the spec's definition of done says "all three stop
reasons reachable and tested". A fourth value would contradict both. Raising
satisfies D-9 (*stop the loop*) and D-2 (*keep the set closed*) at once, and the
trace travels with the exception so the evidence is not discarded.

### Observations: bounded, and the loss is visible

| Bound | Default | Behaviour |
|---|---|---|
| `max_observation_chars` | 8000 | keep head + tail, replace the middle with a marker |
| `max_total_observation_chars` | 400 000 | substitute a marker; **the loop continues** |

The per-observation bound keeps both ends — tool output is usually informative at
both — and the marker names exactly how many characters were removed, so the loss
is visible rather than silent. The trace records the original length alongside the
kept length.

The total budget **does not stop the loop**: one verbose tool must not be able to
end a run the model could finish.

### Usage

Summed across calls, with a field absent on *both* calls staying `None` rather
than becoming `0`. Zero is a measurement; `None` is the absence of one, and
conflating them corrupts cost accounting silently.

## Security

**What the loop structurally prevents.** Actions are read from
`ChatResponse.tool_calls` only. The loop never parses text for an action, so a
tool result cannot **forge** a tool call. Tested by dispatching a tool that
returns `{"name": "delete_everything", "arguments": {"path": "/"}}`-shaped text
and asserting no such call is dispatched.

**What it does not prevent.** A tool result can still **persuade** the model to
call a tool. That is a model-alignment property, not a control-flow one. The
README states the limit; the tests do not pretend otherwise.

**System prompt.** Never constructed, templated, or prepended here. The loop
stores and forwards a prompt; it does not own prompt text.

**Error text.** A provider error body never reaches a model-facing message.

**Non-goal.** This is not a sandbox, a rate limiter, or an approval gate. A
dispatched tool runs with full process privilege.

## Landscape

Registered reference projects (all `code_reused: false`, concepts only):
ReAct (Yao et al.) · LangGraph react agent executor · OpenAI Agents SDK ·
smolagents · LangChain tool-error surface. See
[`docs/registry/`](../../../docs/registry/RESEARCH_REGISTRY.md).

**The findings that shaped the design.** LangChain requires one method and derives
async via `run_in_executor`; LlamaIndex declares eight abstract methods and its
async is a façade that blocks the event loop. Cap exhaustion is a soft,
*signal-carrying* result in LangGraph and smolagents, but a hard exception in the
OpenAI Agents SDK. This capability is therefore **sync-only**, with async a
documented absence rather than a façade.

## Our implementations

This is the only implementation in this category. See
[`TAXONOMY.md`](../../../TAXONOMY.md) §4.

## When to use / When not to use

**Use it when** you need a model to call tools in a loop and you want the bound,
the trace, and the stop reason to be explicit and testable.

**Do not use it when** you need planning, multi-agent handoffs, durable execution,
or concurrent tool dispatch. Those are different capabilities, named in the
taxonomy.

**Limitations, stated plainly:**

- **No async.** Use `asyncio.to_thread`. This is the decision most likely to be revisited — [ADR-0008](../../../docs/decisions/0008-react-agent-loop.md) D-3 names the condition.
- **No retries.** A failed tool is observed, not retried. Retry policy belongs to the caller.
- **Repetition detection is consecutive-only.** A two-cycle evades it.
- **Observations are truncated, which is lossy.** The marker names how much was dropped.
- **No summarisation of stale observations.** That needs a model call and an anti-injection posture; it belongs to a context-management capability.
- **`max_steps=12` is a judgement, not a measurement.**
- **Tool calls are sequential.** A task needing three independent lookups pays three round trips.

## References

- [`specifications/react-agent-loop.md`](../../../specifications/react-agent-loop.md) — the design
- [`docs/decisions/0008-react-agent-loop.md`](../../../docs/decisions/0008-react-agent-loop.md) — the decision and rejected alternatives
- [`research/agents/react-agent-loop.md`](../../../research/agents/react-agent-loop.md) — the survey
