# ADR-0008 — `react-agent-loop`: A Bounded Dispatcher, Not a Reasoner

- **Status:** Accepted
- **Date:** 2026-09-15
- **Capability:** [`react-agent-loop`](../../TAXONOMY.md) (category: agents)
- **Research record:** [`research/agents/react-agent-loop.md`](../../research/agents/react-agent-loop.md)
- **Supersedes:** —

## Context

`react-agent-loop` is capability 3 of 7, and the first capability that **composes**
the two below it: it consumes `tool-registry` (TESTED) and
`model-provider-abstraction` (TESTED). Both dependencies are satisfied, so this
is the first end-to-end proof the composition boundary holds.

Five sources were surveyed against primary material — the ReAct paper
(arXiv:2210.03629v3), LangGraph, smolagents, the OpenAI Agents SDK, and
LangChain's tool-error surface. The findings that forced this decision:

1. **The canonical pattern is a prompt format, not an architecture.** ReAct's
   contribution is that a *thought* is an action in language space that emits no
   observation and only updates context: `Â = A ∪ L`. The paper specifies a
   format (`Thought:` / `Act:` / `Obs:`) and few-shot exemplars. It specifies no
   loop implementation, no termination mechanism, and no parser.

   **Consequence:** we cannot "implement ReAct". We can build an engineering
   design *informed by* it. The ADR must not overstate the lineage.

2. **Repetition is a documented, expected failure of the pattern.**
   FACT: the paper names "one frequent error pattern specific to ReAct, in which
   the model repetitively generates the previous thoughts and actions ... the
   model fails to reason about what the proper next action to take and jump out
   of the loop." It offers no mechanism against it, only a guess that "sub-optimal
   greedy decoding" is at fault.

   **Consequence:** a loop that does not detect repetition ships a known-broken
   behaviour the source paper documented four years ago. And no surveyed
   framework ships a first-class duplicate-action detector.

3. **The paper's step cap was set at the observed 99th percentile, not at a round
   number.** FACT: 7 steps (HotpotQA) and 5 (FEVER), justified as "more steps will
   not improve ReAct performance"; only 0.84% and 1.33% of *correct* trajectories
   used the full budget.

   **Consequence:** a modest default cap costs almost nothing in capability and
   bounds runaway cost. The number should be chosen from evidence, not taste.

4. **Every modern implementation ships a hard cap, and exhaustion is a
   distinguishable outcome.** FACT: LangGraph raises `GraphRecursionError` —
   *"Recursion limit of {N} reached without hitting a stop condition. You can
   increase the limit by setting the `recursion_limit` config key."*; smolagents
   defaults to `max_steps: int = 20` and returns `state="max_steps_error"` while
   also raising `AgentMaxStepsError`; the OpenAI Agents SDK raises
   `MaxTurnsExceeded`.

   **Consequence:** the cap is mandatory, must be configurable, and its
   exhaustion must be **inspectable** — the partial trace is the useful artefact.

5. **LangChain places the model-actionable error decision at the tool.**
   FACT (verified in source): `ToolException` — *"This exception allows tools to
   signal errors without stopping the agent. The error is handled according to the
   tool's `handle_tool_error` setting, and the result is returned as an
   observation to the agent."*

   **Consequence:** this is precisely the split `tool-registry` already computes
   in `FailureKind.model_visible` (ADR-0006 D-4). The two designs agree
   independently; the loop must respect the flag rather than flattening every
   failure into an observation.

6. **Native tool calls delete a failure class that the paper's format creates.**
   With text parsing, an observation containing `Action: delete_everything` is
   *executable*, because the same channel carries both. With typed tool calls,
   an observation is data and is never parsed for actions.

   **Consequence:** the loop must never parse text for actions. This is the one
   security property it can structurally guarantee.

## Decision

**IMPLEMENT** a synchronous, bounded agent loop that dispatches structured tool
calls against a tool registry and a model provider, terminates on an explicit
condition, and reports *why* it stopped. It is a dispatcher with a bound. It does
not reason, plan, remember, or retry.

### D-1. The loop depends on protocols it defines, not on the concrete capabilities

The loop defines two small protocols — a **model caller** and a **tool dispatcher** —
and ships thin adapters for `model-provider-abstraction` and `tool-registry`.

*Why:* charter §31 independence. A loop that imports `tool_registry` and
`model_provider` directly cannot be tested against a scripted double without
those packages, and cannot be reused with a different registry. The adapters are
where the coupling lives, and they are ~30 lines each.

*Acknowledged cost:* one more indirection, and the adapters are real code that
must be tested. Accepted: it is what makes the loop testable with no network, no
model, and no registry.

### D-2. Termination is a closed set of reasons, not a boolean

```python
class StopReason(enum.Enum):
    FINAL_ANSWER = "final_answer"   # the model produced no tool call
    STEP_LIMIT = "step_limit"       # the cap was reached
    REPEATED_ACTION = "repeated_action"  # the loop detected a cycle
```

The loop returns a `AgentResult` carrying the reason, the final text (when there
is one), the full step trace, and accumulated usage.

*Why:* research §4. LangGraph raises; smolagents returns a state. Returning a
state is the better fit because cap exhaustion is **expected**, not exceptional,
and the caller wants the trace. A caller that wants an exception can raise on
`reason is not FINAL_ANSWER`; a caller that wants to inspect can just inspect.

*Design note:* no `ToolError` or `ProviderError` reason exists. Those propagate
as exceptions, because a loop that swallows a provider outage and reports
"finished" is lying.

### D-3. Sync-only

No `async def`. Consistent with ADR-0007 D-3.

*Why:* the same reasoning as the model layer — an honest sync-only surface beats a
façade. A loop is where async would be most tempting (concurrent tool calls), and
that is exactly why it must be a deliberate future decision with a real need,
not a Phase 1 guess.

### D-4. The step cap is a caller parameter with an evidence-based default

`max_steps: int = 12`, configurable per run.

*Why:* the paper's 7/5 are task-specific and tiny; the three modern defaults are
20 (smolagents), configurable (LangGraph), and configurable (OpenAI). 12 is a
middle value chosen to sit above the paper's observed 99th percentile with
headroom for tool-heavy tasks while staying well under smolagents' 20 — and it is
documented as a *default*, not a law. `max_steps=1` must be legal (one model call,
no tools) and is tested.

*Rejected:* a fixed constant. Every surveyed implementation makes it configurable.

### D-5. Repetition detection is on by default, with an explicit threshold

A **consecutive identical call** — same tool id and same canonicalised arguments —
`repeat_limit` times in a row stops the loop with `REPEATED_ACTION`.

`repeat_limit: int = 3`, configurable, and `None` disables it.

*Why:* research §2.4 and §6.4. The paper documents repetition as its most common
ReAct-specific failure and ships no defence. Three consecutive identical calls is
high-confidence: one repeat is a legitimate retry after a transient error, two is
arguable, three is a loop.

*Honest limitation:* this does **not** detect a cycle of length > 1 (A→B→A→B).
Detecting that requires a windowed history and a policy for what to do, which is
a larger design. Stated as a limitation rather than half-implemented.

### D-6. Observations are bounded, middle-out, with an explicit marker

Each tool result is truncated to `max_observation_chars` (default 8000) by keeping
the head and tail and replacing the middle with a marker naming how much was
removed.

*Why:* research §5. Nothing in the surveyed implementations bounds observations in
the loop, and unbounded growth ends in an opaque `ContextLengthError` that
`model-provider-abstraction` correctly classifies as non-retryable. Bounding on
arrival converts that into a bounded, visible outcome. Head-and-tail is chosen
because tool output is usually informative at both ends (a header and a summary).

*Rejected:* summarising stale observations. That needs a model call, a cost
decision, and an anti-injection posture — a capability of its own, not a Phase 1
feature of the loop.

### D-7. The loop does not own the system prompt

`Agent` takes `system: str | None` and passes it through. It does not construct,
prepend, or template one.

*Why:* prompt content is `prompt-engineering`'s concern, and a loop that owns
prompt text is a loop whose behaviour changes when someone edits a string. It also
keeps the loop's tests independent of prompt wording.

### D-8. Actions come from structured tool calls only

The loop reads `ToolCallBlock` from the model response. It never parses text.

*Why:* research §3 and §6.5. Text parsing reintroduces the injection channel that
native tool calls close. This is the loop's one structural security guarantee, and
it is testable: a tool result containing a forged action must not produce a call.

### D-9. Tool failures reach the model only when the model can act on them

The dispatcher adapter consults `ToolResult.failure.model_visible`. A failure with
`model_visible=True` becomes an observation. A failure with `model_visible=False`
— in the registry today, only `NOT_FOUND` — stops the loop rather than being fed
back.

*Why:* ADR-0006 D-4 already decided that "a hallucinated name cannot be fixed by
the model that hallucinated it". Feeding it back invites the model to hallucinate
again. The loop does not re-litigate the registry's taxonomy; it obeys it.

*Cross-check:* LangChain independently reached the same design — `ToolException`
is opt-in, and the default is to re-raise.

### D-10. The loop is not a router, a planner, or a memory

No tool selection, no sub-goal decomposition, no history beyond the run, no
retry. Each is a separate capability.

*Why:* charter §31 and §24.3. `vector-memory-store`, `basic-rag-pipeline`, and
future orchestration capabilities are named in the taxonomy; the loop must not
grow into them.

## Alternatives considered and rejected

| Alternative | Verdict | Reason |
|---|---|---|
| **A synthetic `think` tool** | REJECT | The paper's `Thought:` exists to separate reasoning from action *in one text channel*. With native tool calls they are already separate. A `think` tool costs a step and tokens to do what the model's own text does. |
| **Free-text `Action:` parsing** | REJECT | Reintroduces the injection channel, format drift, and partial parses. Research §3. |
| **Raise on step-limit exhaustion** | REJECT | Cap exhaustion is expected, and the trace is the useful artefact. A caller can raise; a loop cannot un-raise. |
| **No repetition detection** | REJECT | The source paper documents the failure and ships no defence; shipping it knowingly would be indefensible. |
| **Full cycle detection (A→B→A)** | DEFER | Needs a window and a policy; consecutive detection covers the documented failure at a fraction of the complexity. Recorded as a limitation. |
| **Summarise stale observations** | DEFER | Requires a model call and an injection posture. Belongs to a context-management capability. |
| **Async / concurrent tool calls** | DEFER | ADR-0007 D-3. Revisit with a concrete need. |
| **Retry a failed tool inside the loop** | REJECT | Retry policy belongs to the caller (ADR-0007 D-4). The loop reports; it does not decide. |
| **Adopt LangGraph** | REJECT | Pulls in `langchain-core`, and its loop is a graph runtime — a far larger dependency than the ~300 lines this needs. |
| **Adopt smolagents** | REJECT | Ties the loop to its agent/step types and its model layer, replacing ours. |

## Consequences

**Positive.** The first composed capability, proving the two layers below it
compose. Deterministic and testable: the loop is driven entirely through injected
protocols, so every failure path — cap, repetition, oversized observation,
non-model-visible failure — is exercised with no network and no model.

**Negative / accepted.**

- **Repetition detection covers only consecutive duplicates.** A two-cycle evades
  it. Documented, not hidden.
- **Observations are truncated, which is lossy.** A caller that needs the whole
  result must fetch it another way. The marker names how much was dropped.
- **No async means tool calls are sequential.** A task needing three independent
  lookups pays three round trips.
- **`max_steps=12` is a judgement, not a measurement.** The research supplies
  7/5 (2022, PaLM) and 20 (smolagents); ours is not benchmarked, and the ADR says
  so rather than implying precision.

**Reversal conditions.** D-3 (async) when a capability needs concurrent dispatch.
D-5 (repetition) if a real workload shows a legitimate workflow that repeats a call
three times — the threshold is a parameter, so this is a config change, not a
redesign.

## Charter compliance

- §8 — decision vocabulary used: **IMPLEMENT**, with explicit **DEFER** and
  **REJECT** entries above.
- §12 — recorded in the same session as the research.
- §22 — no runtime dependency added; no trust-boundary change beyond D-1's
  protocol seam. No human-review gate triggered.
- §31 — component independence: the loop defines its own protocols, imports
  neither capability at module scope, and runs against scripted doubles.