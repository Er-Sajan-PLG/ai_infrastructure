# Provenance — `react-agent-loop`

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

Five sources were surveyed (session 11), each against primary material — the
ReAct paper itself and raw GitHub source at `main`. All are registered in
[`docs/registry/RESEARCH_REGISTRY.md`](../../../docs/registry/RESEARCH_REGISTRY.md)
with `code_reused: false`.

| Source | Version studied | What was taken |
|---|---|---|
| ReAct (Yao et al.) | arXiv:2210.03629v3 (ICLR 2023) | **Concept + negative finding:** the pattern's shape, and the evidence that repetition is its most common failure and is left unmitigated |
| LangGraph react agent | `main`, `chat_agent_executor.py` + `errors.py` | **Concept:** a cap trip that yields a readable result; model-readable templated error text; a history invariant check |
| OpenAI Agents SDK | `main`, `run.py` + `exceptions.py` | **Concept:** typed next-step values instead of boolean flags; a documented turn unit |
| smolagents | `main`, `agents.py` | **Concept:** recording *why* the loop stopped as a state flag; error kinds named by model-actionability |
| LangChain tool error surface | `main`, `langchain_core/tools/base.py` | **Concept:** the model-actionability split, which corroborates ADR-0006 D-4 independently |

**In every case the adoption is conceptual.** Ideas are not copyrightable; their
expression is. No source file, function body, docstring, comment, prompt, or test
from any of these projects was copied, paraphrased, or transliterated. No prompt
text from the ReAct paper's appendix was reproduced.

## Why no `NOTICE` update is required

Charter §11 and [`NOTICE`](../../../NOTICE) require a notice update when
`code_reused: true`. That flag is `false` for all five entries, and no license
obligation attaches to studying a permissively-licensed project or to
independently implementing a published prompting pattern.

Two specific things keep this defensible:

1. **The ReAct paper is a prompting result, not a code artefact.** Its
   contribution is that a *thought* is an action in language space emitting no
   observation: `Â = A ∪ L`. That is an idea, and it is described in the research
   record in our own words. The paper's own exemplars are not reproduced.
2. **No structurally-mirrored code.** Where a concept was adopted, the
   implementation differs in shape and naming. The clearest case is the loop
   itself: LangGraph's is a `StateGraph` with `Send()` fan-out and a `RemainingSteps`
   managed value; this one is a plain `while` over a step counter returning a
   frozen result — because owning a superstep engine for one control loop would be
   the larger dependency (ADR-0008, rejected alternatives).

## Ideas adopted, and how they differ from their sources

| Idea | Source | This implementation |
|---|---|---|
| A hard step cap | ReAct paper, smolagents, LangGraph | `max_steps=12`; exhaustion is a *returned reason* carrying the trace, not an exception and not a synthetic message |
| Cap exhaustion is inspectable | smolagents' `state="max_steps_error"` | `StopReason.STEP_LIMIT` plus the full `Step` trace |
| Repetition is a real failure | ReAct paper (documents it, no mechanism) | `RepetitionTracker` with canonicalised arguments — **we supply the mechanism the paper omits** |
| Model-actionability split | LangChain `ToolException`, and ADR-0006 D-4 | The loop *obeys* the registry's `model_visible` flag rather than re-deciding it |
| Typed step decisions | OpenAI Agents SDK `NextStep*` | A closed three-value `StopReason` enum, returned rather than raised |
| Cap checked before doing work | — (our own) | Checked before the model call *and* before dispatch, so `max_steps=1` dispatches nothing |
| Bounded observations | — (our own) | Head-and-tail with a marker naming the removed count; the trace records both lengths |

## Negative provenance — deliberately avoided

Recorded so a future session does not "helpfully" reintroduce them:

- **Free-text action parsing.** ReAct's `Action:` format requires it; it creates
  format-drift, partial-parse, and injection classes that typed tool calls
  eliminate. Our loop never parses text for an action.
- **A mandatory `Thought:` step.** The paper makes thought occurrence
  model-chosen; making it structural adds a turn where the model has nothing to
  say. With native tool calls, reasoning already lives in the model's own text.
- **A hard exception on cap exhaustion** (the OpenAI Agents SDK default). The
  trace is the useful artefact, and a caller can raise if it wants to.
- **A designated `final_answer` tool** (smolagents). It reserves a name the caller
  may want, and turns completion into a tool-call convention rather than an
  absence of tool calls.
- **Silent soft-termination with no machine-readable signal** (LangGraph's
  synthetic "Sorry, need more steps" message alone). A caller must be able to tell
  "finished" from "ran out" by reading a value, not by matching prose.
- **A fake async façade** (LlamaIndex). Sync-only, with the absence documented.
- **Owning the system prompt.** Prompt content belongs to `prompt-engineering`.
- **Reusing a raw exception message or a stack trace in an observation.** The
  registry already sanitises; the loop adds nothing.

## Verification

- The package imports only `__future__`, `collections.abc`, `dataclasses`, `enum`,
  `json`, and `typing`, plus the two first-party packages it composes. Asserted by
  `test_the_package_imports_no_third_party_module`.
- No file in this directory contains code from any surveyed project.
- Licenses were confirmed at the version studied, per the registry rule that
  licenses change.

## Maintainer sign-off

Per charter §22, `code_reused: true` would require human review. It is `false`
here, so no gate is triggered — but the classification is recorded explicitly so
the claim is auditable rather than assumed.
