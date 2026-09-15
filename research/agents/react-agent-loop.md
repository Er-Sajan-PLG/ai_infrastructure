# Research: ReAct Agent Loop

- **Capability:** `react-agent-loop` (category: agents)
- **Status:** `RESEARCHED` → `UNDERSTOOD`
- **Session:** 11
- **Date:** 2026-09-15
- **Decision:** [ADR-0008](../../docs/decisions/0008-react-agent-loop.md)

Claims are labelled per charter §6:
**FACT** (verified against a primary source, cited) · **OBSERVATION** (read from
docs/source) · **INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice).

---

## 1. The problem, stated without reference to any implementation

> The simplest agent control loop that grounds LLM output in tool interaction
> with a clear termination condition.

The loop has four jobs, and the research shows they are separable:

| Job | Question | Evidence |
|---|---|---|
| **Decide** | Does the model want a tool, or is it done? | The model's own output |
| **Dispatch** | Turn that intent into a real call | `tool-registry` |
| **Observe** | Feed the result back | This capability |
| **Terminate** | When to stop | This capability |

**INFERENCE:** the loop's real difficulty is not "reasoning" — it is
**termination and containment**. Every failure the ReAct paper documents is a
loop that would not stop or stopped wrongly.

---

## 2. The ReAct paper — what it actually says

**FACT** (verified against arXiv:2210.03629v3, the ICLR camera-ready version):

1. **The interleaving.** ReAct augments the agent's action space:
   `Â = A ∪ L`, where `L` is the space of language. An action in `L` — a *thought*
   — "does not affect the external environment, thus leading to no observation
   feedback." A thought updates the context instead: `c_{t+1} = (c_t, â_t)`.

2. **Dense vs sparse thought.** For reasoning-heavy tasks the paper
   *alternates* thought-action-observation. For decision-making tasks
   "thoughts only need to appear sparsely ... so we let the language model decide
   the asynchronous occurrence of thoughts and actions for itself."

3. **Concrete step limits.** The paper's ReAct↔CoT-SC back-off uses **7 steps for
   HotpotQA and 5 for FEVER**, justified empirically: "we find more steps will not
   improve ReAct performance." Of correct trajectories, only **0.84%** (HotpotQA)
   and **1.33%** (FEVER) used the full 7/5 steps.

   **INFERENCE — this is the most decision-relevant fact in the paper.** Correct
   trajectories essentially never need many steps, which means a modest cap costs
   almost nothing in capability while bounding runaway cost. The paper set the cap
   at the *observed* 99th percentile, not at a round number.

4. **The repetition failure mode.** The paper documents a "frequent error pattern
   specific to ReAct, in which the model repetitively generates the previous
   thoughts and actions," categorised under reasoning error because "the model
   fails to reason about what the proper next action to take and jump out of the
   loop." The authors suspect "sub-optimal greedy decoding" and suggest beam
   search *might* help.

   **FACT.** Loop-the-model-does-not-escape is a documented, expected failure of
   the pattern — not a bug in an implementation.

5. **Non-informative observation is the dominant tool-side failure.**
   "Non-informative search ... counts for 23% of the error cases" and "derails the
   model reasoning and gives it a hard time to recover."

6. **Failure rates.** Of human-studied trajectories: ReAct 47% reasoning error,
   23% search-result error, **0% hallucination**; CoT 16% reasoning error, 56%
   hallucination. **ReAct traded hallucination for loop-and-recover errors.** That
   is the honest tradeoff, stated by the authors.

7. **The name is a prompt pattern, not an architecture.** The paper is a
   *prompting* result: a frozen PaLM-540B with few-shot exemplars. It does not
   specify a loop implementation, a termination mechanism, or a state object.

   **INFERENCE:** therefore anything we build is an *engineering* design informed
   by the pattern, not an implementation of the paper. Saying "ADR-0008 implements
   ReAct" would overstate the lineage.

---

## 3. Text-parsing vs native tool calls

**OBSERVATION:** the original ReAct parses `Action: search[...]` from free text. Modern
provider APIs return structured tool calls, which the `model-provider-abstraction`
capability already normalises into `ToolCallBlock`.

**INFERENCE — this changes what the loop must do, and removes a class of bug:**

| Concern | Text parsing | Native tool calls |
|---|---|---|
| Malformed action | Possible every step; needs a repair prompt | Structurally impossible |
| Argument encoding | Whatever the parser tolerates | Already a parsed object |
| Prompt injection via observation | An observation containing "Action: delete" is *executable* | Observations are data, never parsed for actions |
| Partial parses | Requires heuristics | None |

**DESIGN OPINION:** because this repository's model layer returns structured
tool calls, the loop **must not** parse text for actions. Doing so would
reintroduce an injection channel that the structured path closes — the exact
failure the ReAct paper's format suffers and native tool calling eliminates.

**INFERENCE — does the loop still need a separate "thought" step?** No, and adding
one would be a regression. The paper's `Thought:` exists because the model had only
one output channel and reasoning had to be *told apart from* action text. With
native tool calls, reasoning lives in the model's own response text (or its
reasoning channel) and the tool call is separately typed. Forcing a synthetic
`think` tool would consume a step, cost tokens, and add nothing the model cannot
already express.

---

## 4. How four implementations actually terminate

All verified against source this session.

| | Loop shape | Termination | Step cap | On exceeding |
|---|---|---|---|---|
| **ReAct paper** | prompt cycle | model emits `finish[answer]` | 7 / 5 steps | back off to CoT-SC |
| **LangGraph** | graph, `Pregel` superstep loop | conditional edge; no tool calls → END | `recursion_limit` config | `GraphRecursionError(RecursionError)` — "Recursion limit of {N} reached without hitting a stop condition." |
| **smolagents** | `while` over steps | step produces final answer | `max_steps: int = 20` | `state="max_steps_error"`, raises `AgentMaxStepsError` |
| **OpenAI Agents SDK** | `_run_single_turn` loop | no tool calls / handoff | `max_turns` | raises `MaxTurnsExceeded(AgentsException)` |

**FACT (verified):** LangGraph's error message is *"Recursion limit of {N} reached
without hitting a stop condition. You can increase the limit by setting the
`recursion_limit` config key."* — the cap is **configurable and the error names
the remedy**.

**FACT (verified):** smolagents defaults to **20** steps and surfaces the outcome
as a **result state** (`"max_steps_error"`) rather than only an exception.

**FACT (verified):** OpenAI Agents SDK raises `MaxTurnsExceeded`, a typed
exception in its own hierarchy.

**INFERENCE — the convergence:** all three modern implementations (a) have a hard
cap, (b) make it configurable, (c) surface exhaustion as a **distinguishable
outcome**, not a generic failure. None lets the loop run unbounded.

**INFERENCE — the divergence worth choosing between:** LangGraph *raises*;
smolagents *returns a state*. These encode different beliefs about whether hitting
the cap is exceptional. It is not: it is an expected, recoverable outcome that the
caller may want to inspect (the partial trace) rather than catch.

---

## 5. Observations, context growth, and injection

**OBSERVATION:** none of the surveyed implementations bounds observation size in the
loop itself; LangGraph's tool node truncates some content, but the general
approach is that the message list grows until the model's context limit is hit.

**INFERENCE:** the loop must not grow context without bound and then fail opaquely
with a provider `ContextLengthError`. A configurable cap on observation bytes,
declared and applied before appending, converts an opaque failure into a bounded,
visible one. The `model-provider-abstraction` already surfaces
`ContextLengthError` as non-retryable, so *something* must prevent reaching it.

**OBSERVATION — injection.** The ReAct paper does not discuss prompt injection. The
paper's own format is injection-vulnerable by construction: an observation is
concatenated into the prompt, and the prompt is parsed for actions.

**INFERENCE — the mitigation available to us, and its limit.** Using native tool
calls means a tool result can never be *parsed as an action*. It can still
*influence* the model through its content. So the loop can eliminate the
**parsing** channel but not the **persuasion** channel.

**DESIGN OPINION:** the honest claim is therefore narrow and must be stated
narrowly: *a tool result cannot forge an action; it can still persuade the model
to take one.* The former is a structural guarantee we can test; the latter is a
model-alignment property we cannot. Claiming more would be the same
documentation-asserts-what-code-does-not-do failure this repository has already
caught three times.

---

## 6. Synthesis

1. **The loop is a dispatcher with a bound, not a reasoner.** Reasoning is the
   model's job; the loop's job is dispatch and containment.
2. **Terminate on the absence of tool calls**, which is what all three modern
   implementations do, and which requires no synthetic finish tool.
3. **A hard, configurable step cap is mandatory**, and exhaustion must be a
   distinguishable *outcome* carrying the partial trace — closer to smolagents'
   result state than to a bare exception, because the trace is the useful part.
4. **Detect repetition explicitly.** The ReAct paper documents repetition as a
   frequent failure and offers no mechanism. A consecutive-identical-call detector
   is cheap, testable, and addresses a known-real failure. It must be
   *configurable*, because a legitimate retry after a transient failure looks
   identical to a loop.
5. **Never parse text for actions.** Structured tool calls only. This is the one
   security property the loop can structurally guarantee.
6. **Bound the observation.** Context growth is the failure the loop can prevent
   but the providers only report.
7. **Tool failures go back to the model only when the model can act on them.**
   `tool-registry` already computes this: `FailureKind.model_visible` is `False`
   only for `NOT_FOUND`, because "a hallucinated name cannot be fixed by the model
   that hallucinated it" (ADR-0006 D-4). The loop must respect that flag rather
   than flattening every failure into an observation.

---

## 7. Open questions carried to the decision

1. Does the loop depend on both `tool-registry` and `model-provider-abstraction`,
   or define its own protocols?
2. Sync-only (consistent with ADR-0007 D-3), or does the loop justify async?
3. Who owns the step cap — the caller, a default, or both?
4. Is cap exhaustion an exception, a result state, or both?
5. How is repetition detected without false-positiving on legitimate retries?
6. Are observations truncated, and by what measure — bytes, characters, tokens?
7. Does the loop own the system prompt, or does the caller supply it?

All seven are resolved in [ADR-0008](../../docs/decisions/0008-react-agent-loop.md).

---

## 8. Method and limitations

Primary sources: the ReAct paper (arXiv:2210.03629v3, ICLR camera-ready);
LangGraph source (`langgraph/pregel/main.py`, `langgraph/errors.py`) fetched from
`main`; smolagents source (`src/smolagents/agents.py`) fetched from `main`;
openai-agents-python source (`src/agents/run.py`, `src/agents/exceptions.py`)
fetched from `main`.

**Limitations recorded rather than smoothed over:**

- **Versions are `main`, not pinned releases.** The constants (`max_steps=20`,
  `DEFAULT_MAX_TURNS`, `recursion_limit`) are read from moving branches. They are
  evidence of *what implementations do*, not a compatibility target, and this
  capability targets none of them.
- **LangGraph's default `recursion_limit` value was not located** — the constant
  is not in the files searched. The *mechanism* (configurable, raises
  `GraphRecursionError` with a named remedy) is verified; the default number is
  UNKNOWN and is not relied upon.
- **AutoGPT/BabyAGI were not surveyed.** Their value would have been historical
  evidence about unbounded loops; the ReAct paper's repetition finding and the
  three modern caps already establish the point, so the gap does not affect the
  decision.
- **The ReAct paper's own numbers are PaLM-540B, few-shot, 2022.** They are not
  transferable to current models. They are cited for *mechanism and failure modes*,
  not for expected performance.
- **Prompt injection is under-specified in every primary source consulted.** The
  mitigation in §5 is our own reasoning and is labelled as such.