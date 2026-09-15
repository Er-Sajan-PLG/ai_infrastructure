# Specification: `react-agent-loop`

- **Capability:** [`react-agent-loop`](../TAXONOMY.md) (category: agents)
- **Status:** specified — implementation not started
- **Decision:** [ADR-0008](../docs/decisions/0008-react-agent-loop.md) — `IMPLEMENT`
- **Research:** [research/agents/react-agent-loop.md](../research/agents/react-agent-loop.md)
- **Depends on:** [`tool-registry`](tool-registry.md) (`TESTED`), [`model-provider-abstraction`](model-provider-abstraction.md) (`TESTED`)

> This document describes what will be built. Where the implementation and this
> document disagree, one of them is a bug.

---

## 1. Problem and who needs it

An agent is a model that can act. Acting needs a loop: call the model, run what it
asks for, feed the results back, and stop at some point. Without a bounded,
inspectable loop, every capability above this one reinvents that control flow —
and the research shows that the reinvented version is usually the one that runs
forever.

This is the first capability that **composes** two others. It is therefore also
the first test of whether the boundaries below it were drawn correctly: if the
loop needs to reach into the registry's internals, or to understand a provider's
wire format, the layering is wrong.

**Who needs it:** `basic-rag-pipeline` (multi-step retrieval), evaluation
harnesses, and any tool-using application.

## 2. Scope

**In scope.** A synchronous loop that: renders a conversation as neutral messages,
calls a model, reads structured tool calls from the response, dispatches them,
appends results as observations, detects non-progress, and terminates with a
stated reason. Plus the two adapters that bind it to `tool-registry` and
`model-provider-abstraction`.

**Out of scope (with reasons).**

| Excluded | Why | Type |
|---|---|---|
| HTTP / provider wire formats | `model-provider-abstraction` owns those | OUT OF SCOPE |
| Tool schema validation and dispatch | `tool-registry` owns those | OUT OF SCOPE |
| Tool *selection* (which tools to advertise) | A prompt/strategy concern, not a control-flow one | LATER |
| Retry of a failed tool | The loop reports; the caller decides (ADR-0007 D-4) | OUT OF SCOPE |
| Async / concurrent tool calls | ADR-0008 D-3 | DEFER |
| Multi-agent, handoffs, sub-agents | One loop, one agent. Handoffs are a different capability | OUT OF SCOPE |
| Persistent memory across runs | `vector-memory-store` | OUT OF SCOPE |
| Summarising old observations | Needs a model call and an injection posture | DEFER |
| Full cycle detection (A→B→A) | Consecutive detection covers the documented failure | DEFER |
| Planning / task decomposition as a separate step | The model's own reasoning covers it | OUT OF SCOPE |
| Streaming a running loop | The loop is synchronous and returns a result | LATER |

## 3. Design overview

The loop is a **bounded dispatcher**. It does not reason; it routes.

```
        ┌─────────────────────────────────────────────────┐
        │  run(task, agent, ...)                          │
        └─────────────────────────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  for step in 1..max_steps  │
              └─────────────┬──────────────┘
                            │
                   ┌────────▼────────┐
                   │  ModelCaller    │  ← protocol (adapter → model_provider)
                   │  .call(msgs)    │
                   └────────┬────────┘
                            │  response
                   ┌────────▼────────┐
              no   │ tool_calls?     │
             ┌─────┤                 │
             │     └────────┬────────┘
             │              │ yes
     ┌───────▼──────┐  ┌────▼─────────────┐
     │ FINAL_ANSWER │  │ repeat?          │──yes──► REPEATED_ACTION
     └──────────────┘  └────┬─────────────┘
                            │ no
                   ┌────────▼────────┐
                   │ ToolDispatcher  │  ← protocol (adapter → tool_registry)
                   │ .dispatch(call) │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │ bound + append  │  observation
                   └─────────────────┘

     loop exhausted ────────────────────────► STEP_LIMIT
```

Three seams, all injected: the **model caller**, the **tool dispatcher**, and the
**clock-free step counter** (implicit). Nothing else is configurable.

## 4. Dependencies at runtime — D-1

The loop imports **neither** capability at module scope. It defines two protocols
and ships optional adapters:

```python
class ModelCaller(Protocol):
    def call(self, messages: Sequence[Message], *, tools: Sequence[Mapping]) -> ChatResponse: ...

class ToolDispatcher(Protocol):
    def dispatch(self, call: ToolCallBlock) -> DispatchOutcome: ...
```

*Why:* charter §31. A loop that imports the registry cannot be tested against a
scripted double without a registry, and cannot be reused with a different one.

*Cost:* one indirection plus two small adapters that must themselves be tested.
Accepted: it is what makes every failure path in §9 reachable with no network and
no model.

## 5. The neutral message flow — D-2

The loop **owns no message type**. It consumes `model_provider`'s neutral types
directly (`Message`, `Role`, `TextBlock`, `ToolCallBlock`, `ToolResultBlock`).

**Consequence, stated plainly:** the loop depends on `model-provider-abstraction`'s
*types* even though it does not import its *behaviour*. This is a deliberate,
narrow coupling — a loop with its own parallel message type would force every
adapter to convert, which is the exact cost LangChain and LlamaIndex pay. The
`ModelCaller` protocol is defined in terms of those types, so the dependency is in
the signature rather than the import graph.

### 5.1 The conversation

```
[system?]            supplied by the caller, never constructed here (D-7)
user:   <task>
loop {
  assistant: <text?> + <tool_calls>       appended from the response
  tool:      <result for each call>       appended per dispatch
}
```

Each tool result is a separate `Message(role=TOOL, (ToolResultBlock(...),))`, one
per call, because that is what every provider expects and what the registry's
`ToolCallBlock.id` correlates against.

## 6. Termination — D-2, D-4, D-5

```python
class StopReason(enum.Enum):
    FINAL_ANSWER = "final_answer"     # the model produced no tool call
    STEP_LIMIT = "step_limit"         # the cap was reached
    REPEATED_ACTION = "repeated_action"  # consecutive identical calls
```

`AgentResult` carries: `reason`, `final_text` (empty unless `FINAL_ANSWER`), the
`steps` trace, accumulated `Usage`, and the full `messages` list.

**Rules.**

1. **`FINAL_ANSWER` is the absence of tool calls.** No synthetic `finish` tool. A
   designated `final_answer` tool reserves a name the caller might want and turns
   completion into a tool-call convention (smolagents does this; we do not).
2. **The cap is checked before the model call**, so `max_steps=1` means exactly
   one model call and no tool dispatch. This is tested.
3. **Exhaustion is a result, not an exception.** The trace is the useful artefact;
   a caller that wants an exception raises on `reason is not FINAL_ANSWER`.
4. **`ProviderError` and `ToolRegistryError` propagate.** A loop that swallowed a
   provider outage and reported "finished" would be lying. There is deliberately
   no `StopReason` for them.

## 7. Repetition detection — D-5

A call is *identical* when its `name` and its **canonicalised** arguments match a
previous call's in the same run. Canonicalisation is `json.dumps(arguments,
sort_keys=True, separators=(",", ":"))` — key order must not defeat the check.

`repeat_limit: int = 3` counts **consecutive** identical calls. On the third, the
loop stops with `REPEATED_ACTION` *before* dispatching a fourth time, and the
result names the repeated call.

`repeat_limit=None` disables detection. `repeat_limit=1` is rejected at
construction: it would fire on the first call, which is not a repetition.

**Honest limitation, stated here and in the README:** this detects *consecutive*
duplicates only. A two-cycle (A→B→A→B) evades it. Full cycle detection needs a
window and a policy for what to do on a hit, and is deferred.

**Why it exists at all:** the ReAct paper documents repetition as its most common
ReAct-specific failure and ships no defence (research §2.4). Shipping the failure
knowingly, with the evidence in hand, would be indefensible.

## 8. Observations and bounding — D-6

Each dispatched result becomes text:

| Outcome | Observation text |
|---|---|
| Success | `str(value)` (a tool returns a string; anything else is `repr`'d) |
| `ToolFailure` with `model_visible=True` | a structured line naming the kind and the (already sanitised) message |
| `ToolFailure` with `model_visible=False` | **the loop stops**; nothing is appended (D-9) |

**Bounding.** `max_observation_chars: int = 8000`. Over-length text keeps the
**head and the tail** and replaces the middle with a marker stating how many
characters were removed:

```
<first 4000 chars>
… [truncated 12345 of 24345 characters] …
<last 4000 chars>
```

Head-and-tail is chosen because tool output is informative at both ends — a
header and a summary — and the marker makes the loss *visible* rather than
silent. The loop does not summarise: that needs a model call and an anti-injection
posture, and belongs to a context-management capability.

**Total bound.** `max_total_observation_chars: int | None = 400_000` bounds the
sum across a run, so a long run of large-but-legal results cannot grow without
limit. `None` disables it. When the budget is exhausted, further observations are
replaced by a fixed marker naming the exhausted budget — the loop does **not**
stop, because that would let one verbose tool end a run the model could finish.

## 9. Security and trust boundaries

| Boundary | Rule |
|---|---|
| **Actions** | Read from `ChatResponse.tool_calls` only. The loop **never** parses text for an action. This is the one structural guarantee it can make (D-8). |
| **Injection, what we prevent** | A tool result cannot *forge* a tool call: nothing in an observation is ever parsed as an action. Tested by dispatching a tool that returns `{"name":"delete_everything",...}`-shaped text and asserting no such call is dispatched. |
| **Injection, what we do NOT prevent** | A tool result can still *persuade* the model to call a tool. That is a model-alignment property, not a control-flow one. The README states this limit; the tests do not pretend otherwise. |
| **System prompt** | Never constructed, templated, or prepended here (D-7). Prompt content is `prompt-engineering`'s concern. |
| **Error text** | `ToolFailure.message` is already sanitised by the registry (ADR-0006 D-4). The loop does not add exception text, paths, or traces to an observation. |
| **Unknown tool** | `NOT_FOUND` has `model_visible=False`, so the loop **stops** rather than inviting the model to hallucinate the name again. |
| **Non-goal** | Not a sandbox, not a rate limiter, not an approval gate. A dispatched tool runs with full process privilege. |

## 10. Design decisions index

| ID | Decision | ADR |
|---|---|---|
| D-1 | Depends on protocols it defines; adapters are optional | ADR-0008 |
| D-2 | Termination is a closed reason enum, returned not raised | ADR-0008 |
| D-3 | Sync-only | ADR-0008 |
| D-4 | `max_steps: int = 12`, caller-overridable | ADR-0008 |
| D-5 | Consecutive-repeat detection, `repeat_limit=3`, `None` disables | ADR-0008 |
| D-6 | Observations bounded head-and-tail with an explicit marker | ADR-0008 |
| D-7 | The loop does not own the system prompt | ADR-0008 |
| D-8 | Actions from structured tool calls only | ADR-0008 |
| D-9 | Tool failures reach the model only when `model_visible` | ADR-0008 |
| D-10 | Not a router, planner, or memory | ADR-0008 |

## 11. Public interface (provisional)

```python
@dataclass(frozen=True, slots=True)
class Agent:
    model: str
    system: str | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None

@dataclass(frozen=True, slots=True)
class AgentResult:
    reason: StopReason
    final_text: str
    steps: tuple[Step, ...]
    usage: Usage | None
    messages: tuple[Message, ...]

def run(
    task: str,
    *,
    agent: Agent,
    model_caller: ModelCaller,
    dispatcher: ToolDispatcher,
    max_steps: int = 12,
    repeat_limit: int | None = 3,
    max_observation_chars: int = 8000,
    max_total_observation_chars: int | None = 400_000,
) -> AgentResult: ...
```

The five keyword-only bounds are all optional with documented defaults, so the
common call is `run(task, agent=..., model_caller=..., dispatcher=...)`.

## 12. Testing strategy (charter §18)

Every test runs against a **scripted** model caller and a **fake** dispatcher. No
network, no model, no API key, no registry required.

| Class | What it proves |
|---|---|
| Happy path | Two tool calls then a final answer produce the right step trace and `FINAL_ANSWER` |
| **Step limit** | `max_steps=1` performs exactly one model call; the reason is `STEP_LIMIT` and the trace is intact |
| **Repetition** | Three identical consecutive calls stop with `REPEATED_ACTION` before a fourth dispatch; the fourth is proven *not* to have run |
| Repetition, negatives | Two identical calls do **not** stop; a repeat after a different call does **not** stop; `repeat_limit=None` never stops |
| Argument canonicalisation | The same arguments with different key order still count as identical |
| **Injection** | A tool returning action-shaped text produces no forged dispatch |
| `model_visible=False` | A `NOT_FOUND` failure stops the loop and appends nothing |
| `model_visible=True` | An `INVALID_ARGUMENTS` failure becomes an observation and the loop continues |
| Bounding | An oversized observation is truncated head-and-tail with a marker naming the removed count |
| Total budget | The summed budget is enforced; the loop continues rather than stopping |
| Propagation | A `ProviderError` from the caller and a `ToolRegistryError` from the dispatcher both propagate unchanged |
| Purity | The package imports no third-party module (import-scanning test) |
| Construction | `repeat_limit=1` and `max_steps=0` are rejected loudly |

The failure classes are the majority of the suite, because they are the reason the
capability exists.

## 13. Benchmark plan

Deferred. The loop adds no work of its own beyond dispatch and string bounding, so
a benchmark would measure the model and the tools. The one honest measurement —
**overhead per step** against a no-op caller — is noted here and deferred to the
benchmark harness capability.

## 14. Definition of done

- [ ] `run`, `Agent`, `AgentResult`, `StopReason`, the two protocols, and two adapters
- [ ] All three stop reasons reachable and tested
- [ ] Repetition detection with canonicalised arguments, and its negatives
- [ ] Observation bounding, including the total budget
- [ ] `model_visible` respected in both directions
- [ ] Injection test: no forged dispatch from tool output
- [ ] No third-party import (asserted by test)
- [ ] `examples/` program demonstrating a full run against a scripted caller
- [ ] README and `PROVENANCE.md`
- [ ] Taxonomy → `TESTED`; `basic-rag-pipeline` unblocked

## 15. Open questions for implementation

1. **`str(value)` vs `repr(value)`.** A tool contract says it returns a string.
   What does the loop do with a non-string? *Leaning:* `repr` for anything that is
   not already `str`, so an integer result is not silently indistinguishable from
   a string one.
2. **Where the step trace records the observation length.** Truncation is a
   meaningful event; the step should probably carry both the original and the
   kept length so a caller can see the loss. Cosmetic, but it affects the
   `AgentResult` shape, so decide before writing tests.
3. **Whether `Step` is a dataclass or a small union.** A step always has a model
   response; it sometimes has dispatches. A union may be clearer than a struct
   with an optional field.
4. **Cap on `max_steps`.** Should there be an upper sanity bound, or is it the
   caller's business? *Leaning:* the caller's, since they pay for the calls.

These are implementation-level and do not change D-1..D-10.