# ADR-0010 — `execution-trace-recorder`: Record Flat, Bound Everything, Capture Nothing by Default

- **Status:** Accepted
- **Date:** 2026-09-16
- **Capability:** [`execution-trace-recorder`](../../TAXONOMY.md) (category: observability)
- **Research record:** [`research/observability/execution-trace-recorder.md`](../../research/observability/execution-trace-recorder.md)
- **Specification:** [`specifications/execution-trace-recorder.md`](../../specifications/execution-trace-recorder.md)
- **Supersedes:** —

## Context

`execution-trace-recorder` is capability 6 of 7, the first in the **observability**
category, and the last capability Phase 1 needs: it takes the taxonomy to **5 of 5
categories with a `TESTED` capability**, which is the phase's exit criterion. It
has no dependencies, so it has been unblocked since session 14 and was deferred
only because other work came first.

Six systems were surveyed against primary material — OTel's GenAI conventions,
OpenInference, Langfuse, LangSmith, MLflow, and AgentOps. The findings that forced
this decision:

1. **THERE IS NO STANDARD TO CONFORM TO.** The OTel GenAI conventions are marked
   `Development`, have just **moved repositories** (the old pages now return HTTP
   200 with a *"this page has moved"* stub), have **no published schema URL** — the
   new repository's README declares it `TODO` — and have already **reversed** one
   content-capture decision, deprecating `gen_ai.prompt` and `gen_ai.completion`
   with *"Removed, no replacement at this time."* Anything claiming
   "OTel-compatible agent tracing" today claims compatibility with a moving
   development target.

2. **The six do not agree on a taxonomy axis.** OTel uses an operation **verb** —
   18 values, and **no node type at all**. The other five use a kind **noun**, with
   cardinality 7–15. MLflow makes its taxonomy a **non-enum on purpose**, with the
   reason in source: *"Not using enum as we want to allow custom span type string."*
   That is the opposite of OTel's closed list. "Compatible with all six" is not a
   coherent Phase 1 goal.

3. **Default-off content capture is the MINORITY position, and that is the
   argument for it.** Only **one of six** states a default-off policy — OTel — and
   it is the only one that has been through a privacy review. OpenInference,
   MLflow, Langfuse, LangSmith and AgentOps either capture by default and redact
   afterwards, or take no position at all. OTel's own text is unambiguous:
   *"Instrumentations SHOULD NOT capture this attribute by default"*, with
   `gen_ai.output.messages` flagged *"likely to contain sensitive information
   including user/PII data."*

4. **None of the six has a field for WHY THE RUN ENDED.** `react-agent-loop`
   already computes `StopReason` (`FINAL_ANSWER` / `STEP_LIMIT` /
   `REPEATED_ACTION`). It is arguably the single most valuable field in a trace,
   and it is ours to add.

5. **A tool call and its result are ONE node in every surveyed system.** OTel puts
   the result as an attribute on the same span; OpenInference and MLflow carry
   `tool_call.id` alongside. There is no "tool result" record anywhere.

6. **Flat records with parent pointers, unanimously.** No surveyed system stores a
   nested tree. Structure is an id pointing at a parent. LangSmith adds
   `dotted_order`, a sortable execution-order key, which no other system has.

7. **The units are a hazard.** Six systems, at least four unit conventions, and
   **MLflow disagrees with itself within one object** — span times in nanoseconds,
   trace duration in milliseconds. Langfuse and AgentOps state no unit at all. An
   unlabelled `latency: 1.5` is a bug waiting for a reader who assumed seconds.

8. **Langfuse's provided-vs-computed split is the best idea found.** Its
   `providedUsageDetails` vs `usageDetails` distinguishes *what the caller
   reported* from *what the system computed*, and that composes directly with
   ADR-0007 D-5, which already draws the line between a measurement and the
   absence of one.

9. **Cost is a pricing table, not a telemetry primitive.** Four of six model it,
   but each either embeds a price table or asks the caller, and MLflow's own
   docstring concedes *"Cost tracking is not supported for all LLM providers."*
   OTel declines to model it at all.

## Decision

**IMPLEMENT** a zero-runtime-dependency recorder that writes flat JSONL records,
bounds everything it writes, captures no content unless explicitly told to, and
never kills the run it is observing.

### D-1. Four record kinds on the noun axis; the mapping is a published correspondence

`trace_start`, `model_call`, `tool_call`, `trace_end` — a closed enum.

*Why:* finding 2. One axis must be picked. A noun reads correctly in a JSONL field
(`"kind": "tool_call"`) where a bare verb describes an action but not a record.
The correspondence table (spec §4) is published in the spec so the mapping is
auditable and the claim stays bounded.

*We claim no conformance to any standard* (finding 1), and the spec says so in §2
and again in §12. Following `tool-registry`'s precedent, the honest move is to
study the conventions and record the correspondence.

### D-2. A tool call and its result are ONE record

*Why:* finding 5. Splitting them would make "did this call succeed?" require a
join, and it would diverge from every surveyed system with no justification.

A context manager makes one call produce exactly one line, and an exception inside
the block still produces a record with `outcome="error"` — a missing record would
be indistinguishable from a tool that was never called.

### D-3. `stop_reason` on `trace_end`, and a missing `trace_end` means the run did not finish

*Why:* finding 4. This is our field. A `trace_id` with no terminal record is a
crash, a kill, or a process death — the most interesting failure, and representable
only if the reader can distinguish "no end record" from "end record with no reason".

### D-4. The clock is injected, with two methods

`now_ns()` for monotonic durations, `now_utc()` for the wall-clock timestamp.

*Why:* finding 7. A duration must come from a monotonic source or a wall-clock
adjustment makes it negative; a timestamp must be wall-clock or it is meaningless
to a reader. Two methods because they answer different questions. Injecting the
clock is also what makes timing tests exact rather than tolerant.

### D-5. Units live in the field name

`started_at_ns`, `ended_at_ns`, `duration_ns` — integers, never a bare float.

*Why:* finding 7. This is the single most likely source of silent bugs in this
capability. `duration_ns` cannot be misread as seconds.

*And `duration_ns is None` iff `ended_at_ns is None`.* An unknown duration and an
instantaneous one are different facts; `0` would conflate them.

### D-6. `usage_provided: bool` — the Langfuse split, reduced

*Why:* finding 8. A trace that cannot say "the provider told us this" versus "we
computed this" cannot be audited. `None` with `usage_provided=False` is an honest
"not reported"; `0` would be a lie.

*Rejected:* the full four-field split. Half of it exists to serve cost, which D-11
declines. One boolean carries the distinction we need.

### D-7. Flat records with `parent_id`, in append-only JSONL

*Why:* finding 6, which is unanimous. A nested tree cannot be appended to without
rewriting the file. This can.

### D-8. Content capture is OFF by default, as a policy object

`CaptureNothing()` is the default; `CaptureEverything()` is a named alternative.
A `CapturePolicy` protocol, not a boolean parameter.

*Why:* finding 3. **The majority practice is not the safe default, which is exactly
why following the crowd is the wrong move here.** Charter §6 plus this repository's
own posture (ADR-0008 D-6 bounded observations, D-8 actions from structured calls
only) both point at default-off with explicit enablement. We adopt OTel's *rule*
without implementing OTel.

*Why a policy object:* "off by default" needs a way to be turned on that is not a
boolean buried in a call site. A policy is inspectable and has a `__repr__` that can
appear in a message.

*A redacted field is not the same as an absent one.* With capture off, `content` is
`None`. It is never a `"__REDACTED__"` sentinel — that would put a value where the
honest answer is "we did not look".

### D-9. The constructor fails loudly; a mid-run write failure is caught and counted

*Why:* the two obvious answers are each half wrong. A recorder that raises can
**kill the run it was observing**; one that swallows can **lose the evidence**.

An unusable sink is a *programming* error known before the run starts, so failing
then is cheap and honest. A write failure on record 400 of an agent run — after the
model calls have been paid for — is not the moment to raise. It is caught, counted,
and exposed as `recorder.write_failures`, so the loss of evidence is itself
recorded rather than silent.

### D-10. Bounds are stated, and they are ours

`max_error_message_chars=500`, `max_content_chars=8000`, `max_records=10000`.

*Why:* MLflow is the only surveyed system that documents truncation limits. The
numbers are ours; the practice of stating them is theirs. Truncation is head-only
with a suffix naming the removed count, matching ADR-0008 D-6 rather than
inventing a second convention.

### D-11. Cost is DEFERRED, not implemented

*Why:* finding 9. A price table ages, and this capability has no other reason to
hold one. Record usage; expose cost later. OTel's refusal to model it is
defensible, and MLflow's own docstring concedes the limitation.

### D-12. The recorder defines its own record type and imports nothing from `react_agent_loop`

*Why:* charter §31. `Step` is the loop's type, and importing it would make the
recorder depend on the loop. An adapter mapping `Step` → records belongs in the
loop's own `adapters.py`, beside the two adapters already there — that is the
module that already imports its dependencies.

The recorder stays usable by anything that can call `record_model_call`, which is
what makes it independent rather than a private detail of one loop.

### D-13. No aggregation, and sync-only

*Why:* the taxonomy entry mentions "aggregate stats". That is a **second
responsibility** — a reader over the records — and folding it in would make the
writer carry query logic it does not need. Sync-only is consistent with ADR-0007
D-3, ADR-0008 D-3, and ADR-0009 D-8.

## Alternatives considered and rejected

| Alternative | Verdict | Reason |
|---|---|---|
| **Claim OTel conformance** | REJECT | Finding 1 — the target is `Development`, has moved repositories, has no schema URL, and has reversed a decision. |
| **Adopt OTel's verb axis** | REJECT | Finding 2 — five of six use nouns, and a verb describes an action rather than a record. |
| **An open (non-enum) kind** | REJECT | MLflow does this deliberately, and it costs the ability to validate. A closed enum of four is checkable. |
| **Two records per tool call** | REJECT | Finding 5 — diverges from all six, and forces a join. |
| **Capture content by default** | REJECT | Finding 3 — five of six do it and only one has a privacy review. Charter §6 says follow the reviewed rule. |
| **A `"__REDACTED__"` sentinel** | REJECT | D-8 — puts a value where the honest answer is "we did not look". |
| **A boolean `capture_content=`** | REJECT | D-8 — invisible at the call site and cannot be narrowed per-tool later. |
| **Raise on a mid-run write failure** | REJECT | D-9 — kills the run it was observing. |
| **Silently swallow a write failure** | REJECT | D-9 — loses evidence with no trace that it was lost. |
| **Model cost** | **DEFER** | D-11 — a price table ages; every system that models it embeds one or asks the caller. |
| **Aggregate statistics** | **DEFER** | D-13 — a second responsibility; compose it from the records. |
| **Nested-tree storage** | REJECT | Finding 6 — cannot be appended to. |
| **An `agent` record kind** | REJECT | LangSmith — a product whose whole subject is agent tracing — has no `agent` run type. |
| **Import `react_agent_loop.Step`** | REJECT | D-12 — makes the recorder depend on the loop and unusable without it. |
| **A bare float `latency`** | REJECT | Finding 7 — the units hazard. |
| **An OTLP exporter** | **DEFER** | Wire-protocol work with no local consumer. |
| **Sampling** | **DEFER** | Meaningful at a scale we do not have. |
| **Async writes** | REJECT | D-13 — one writer, one trace, one thread; a background thread would need its own failure accounting. |

## Consequences

**Positive.** The repository can persist what a run did, which is what makes
charter §18's *"demonstrated run"* reviewable by someone who was not present. The
dependency posture is preserved — standard library only. Content is off by default,
so a trace is safe to commit as a test fixture. `stop_reason` is a field none of
the six surveyed systems has. The clock is injectable, so timing tests are exact.
A write failure cannot kill the run it observes, and it cannot vanish silently
either.

**Negative / accepted.**

- **No conformance claim** to any standard, because there is no stable one. A
  consumer wanting OTel output must write a translation, and the spec says the
  mapping is a correspondence rather than a compatibility promise.
- **No cost.** Recorded usage only.
- **No aggregation.** A reader must be written separately.
- **Content is off by default**, so a trace alone does not explain *what* the model
  said. That is the intended trade, not an oversight.
- **A write failure loses that record.** The count and the first message survive;
  the record does not.
- **`max_records` drops records past the cap.** A bounded trace of an unbounded run
  is necessarily incomplete, and the drop count is recorded.

**Reversal conditions.** D-11 when a caller needs cost and is willing to supply a
price table. D-8's default should be revisited only if a capture mechanism arrives
that is safer than opt-in — not because other systems default to on.

## Charter compliance

- §6 — every claim in the research record, the specification, and this ADR carries
  an explicit FACT / OBSERVATION / INFERENCE label.
- §8 — decision vocabulary used: **IMPLEMENT**, with explicit **DEFER** and
  **REJECT** entries above.
- §12 — recorded in the same session as the specification.
- §18 — the testing strategy is stated before implementation, and failure paths are
  required rather than optional.
- §20 — the security posture is stated, including what is **not** protected: a
  caller who enables `CaptureEverything()` is capturing PII.
- §22 — no runtime dependency added; no trust boundary changed. The default-off
  content policy **reduces** what is written rather than expanding it.
- §31 — component independence: the recorder imports nothing from
  `react_agent_loop`, `tool_registry`, `model_provider`, or `mcp_client`.

## Licensing

**No code was reused.** All six surveyed systems are registered in
[`docs/registry/RESEARCH_REGISTRY.md`](../registry/RESEARCH_REGISTRY.md) with
`code_reused: false` (charter §11). Nothing here requires a `NOTICE` update.

## Taxonomy impact

`execution-trace-recorder` advances `RESEARCHED → UNDERSTOOD → DESIGNED → DECIDED`.

Artifacts: research record (session 14), specification
(`specifications/execution-trace-recorder.md`), this ADR. `decision: IMPLEMENT`.
`status` becomes `DECIDED`; the implementation follows in
`catalog/observability/execution_trace_recorder/`.