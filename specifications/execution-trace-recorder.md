# Specification: `execution-trace-recorder`

| Field | Value |
|---|---|
| **Capability id** | `execution-trace-recorder` |
| **Name** | Agent Trajectory / Execution Trace Recorder |
| **Category** | observability |
| **Lifecycle status** | `DESIGNED` |
| **Deciding ADR** | [ADR-0010](../docs/decisions/0010-execution-trace-recorder.md) — decision: **IMPLEMENT** |
| **Research record** | [`research/observability/execution-trace-recorder.md`](../research/observability/execution-trace-recorder.md) |
| **Dependencies** | none (charter §24.1) |
| **Standards** | none claimed — see §2 |
| **Runtime dependencies** | **none** (ADR-0003) |

Claims are labelled per charter §6: **FACT · OBSERVATION · INFERENCE · DESIGN OPINION**.

---

## 1. Problem and who needs it

> Persist what an agent run did, in a form another person can read and a machine
> can aggregate, without holding anything sensitive by default.

`react-agent-loop` returns an `AgentResult` carrying a `Step` trace, so a *single*
run is inspectable in memory. Nothing persists it, nothing aggregates across runs,
and nothing records how long a step took or what it cost. The taxonomy entry states
the consequence: *"Without traces, agent behavior cannot be tested, evaluated, or
debugged with evidence."*

**Who needs it** (charter §7):

| Consumer | Needs from this capability |
|---|---|
| `react-agent-loop` | A place to send a `Step` without importing it |
| `integrations/agent_loop_end_to_end` | A persisted artefact proving a run happened |
| A future evaluation capability | Aggregates over many runs |
| Charter §18 | A run reviewable by someone who was not present |

---

## 2. There is no standard to conform to — and that is the first finding

**FACT** (research §2.1): the OpenTelemetry GenAI conventions are marked
`Development`, have just **moved repositories**, have **no published schema URL**
(`TODO` in the new repository's README), and have already **reversed** one
content-capture decision. `gen_ai.prompt` and `gen_ai.completion` are
`Deprecated` with the description *"Removed, no replacement at this time."*

**Decision: we claim no conformance.** Following `tool-registry`'s precedent
(ADR-0006), the honest position is to study the conventions, record the
correspondence, and say plainly that it is a correspondence. A claim of
"OTel-compatible agent tracing" would be a claim about a moving development target.

**FACT** (research §4): the six surveyed systems do not agree on a taxonomy axis.
OTel uses an operation **verb** (`execute_tool`, `chat` — 18 values, no node type
at all). The other five use a kind **noun** with cardinality 7–15. MLflow makes
its taxonomy a **non-enum on purpose** — *"Not using enum as we want to allow
custom span type string"* — which is the opposite of OTel's closed list.

**INFERENCE:** "compatible with all six" is not a coherent Phase 1 goal. We pick
one axis, document the mapping (§4), and state which was chosen.

---

## 3. Scope

### In scope

1. **Record** — trace start/end, model calls, tool calls, into flat records.
2. **Persist** — append-only JSONL, one record per line.
3. **Correlate** — every record carries `trace_id`, every child carries `parent_id`.
4. **Bound** — every string and collection is bounded before it is written.
5. **Gate content** — prompt/completion/tool payloads are **off by default**.
6. **Survive** — a write failure never kills the run it is observing.

### Explicitly out of scope

| Out of scope | Why | Type |
|---|---|---|
| Cost computation | A pricing table ages; OTel declines it and MLflow concedes it is *"not supported for all LLM providers"* | **DEFER** |
| Aggregation / statistics | A second responsibility; compose it from the records | **DEFER** |
| An OTLP exporter or HTTP ingest | Wire-protocol work with no local consumer | **DEFER** |
| Sampling | Meaningful at scale we do not have | **DEFER** |
| Prompt/completion capture **by default** | The one security decision here; see §6 | **REJECT (as a default)** |
| Nested-tree storage | Unanimous across six systems (research §7); cannot be appended to | **REJECT** |
| An `agent` record kind | LangSmith — a product whose whole subject is agent tracing — has **no** `agent` run type (research §4) | **REJECT** |
| A cost field the recorder fills in | It would have to hold a price table | **REJECT** |

---

## 4. The taxonomy — D-1, and the mapping is published as a correspondence

Four record kinds, a closed enum, on the **noun** axis:

| Kind | What it is | Discriminator |
|---|---|---|
| `trace_start` | The root record | — |
| `model_call` | One call to a model provider | `model` |
| `tool_call` | One tool invocation **and its result** | `tool_name` |
| `trace_end` | The terminal record | `stop_reason` |

**Why a noun and not a verb:** four of the five non-OTel systems use nouns, and a
noun reads correctly in a JSONL field (`"kind": "tool_call"`) where a bare verb
(`"kind": "execute_tool"`) describes an action but not a record.

**Correspondence table, published so the mapping is auditable and the claim stays
bounded:**

| Ours | OTel GenAI | OpenInference | Langfuse |
|---|---|---|---|
| `model_call` | `chat` / `generate_content` | `LLM` | `GENERATION` |
| `tool_call` | `execute_tool` | `TOOL` | `TOOL` |
| `trace_start` / `trace_end` | the trace's own root | — | `TRACE` |
| — | — | `CHAIN`, `RETRIEVER`, `RERANKER`, … | `CHAIN`, `RETRIEVER`, … |

**This table is a correspondence, not a compatibility claim.** The right-hand
columns are the surveyed systems' vocabulary; the left column is ours.

### 4.1 A tool call and its result are ONE record — D-2

**FACT** (research §2.9, §3.2): OTel puts the result as an attribute on the *same*
span; OpenInference and MLflow carry `tool_call.id` alongside; **none of the six
models them as two nodes.** Splitting them would be a divergence with no
justification, and it would make "did this tool call succeed?" require a join.

The implementation offers a context manager so one call produces exactly one line:

```python
with recorder.tool_call(name="search", arguments={...}) as call:
    call.succeed(result=value)      # or call.fail(message="…")
```

The record is written on `__exit__`, so an exception inside the block still
produces a record — with `outcome="error"`. A missing record would be
indistinguishable from a tool that was never called.

### 4.2 `stop_reason` is our field, and it is the point — D-3

**OBSERVATION** (research §9.8): **none of the six** surveyed systems has a field
for *why the run ended*. `react-agent-loop` already computes `StopReason`
(`FINAL_ANSWER` / `STEP_LIMIT` / `REPEATED_ACTION`). It is arguably the single
most valuable field in a trace, and it is ours to add.

So `trace_end` carries `stop_reason`. A `trace_id` with no `trace_end` means the
run never finished — a crash, a kill, a process death. That is the most
interesting failure and it is representable.

---

## 5. Interfaces and data flow

### 5.1 Shape

```
  TraceRecorder(sink, clock=…, capture=…, bounds=…)
        │
        ├── sink       a write target (Path, or any TextIO)
        ├── clock      injectable; monotonic for durations, wall for timestamps
        ├── capture    CapturePolicy — content OFF by default
        └── bounds     max lengths, so a record is always bounded
```

### 5.2 The clock is injected — D-4

```python
class Clock(Protocol):
    def now_ns(self) -> int: ...        # monotonic, for durations
    def now_utc(self) -> str: ...       # ISO 8601, for the human timestamp
```

**Two methods, not one, because they answer different questions.** A duration must
come from a monotonic source or a wall-clock adjustment makes it negative. A
timestamp must be wall-clock or it is meaningless to a reader. Research §8 records
that the surveyed systems disagree on units and that **MLflow disagrees with
itself within one object** (span times in nanoseconds, trace duration in
milliseconds). Injecting the clock is also what makes timing tests deterministic
rather than flaky.

### 5.3 Units live in the field name — D-5

Every duration field is an **int named with its unit**:

```python
started_at_ns: int          # monotonic
ended_at_ns: int | None     # monotonic; None means "never finished"
duration_ns: int | None
```

**Never a bare float.** Research §8 calls this the single most likely source of
silent bugs in this capability: six systems, at least four unit conventions, and
an unlabelled `latency: 1.5` is a bug waiting for a reader who assumed seconds.
`duration_ns` cannot be misread. The derived value is `ended - started`, and it is
`None` when `ended_at_ns` is `None` rather than `0` — an unknown duration and an
instantaneous one are different facts.

### 5.4 The record

```python
@dataclass(frozen=True, slots=True)
class TraceRecord:
    trace_id: str
    record_id: str
    parent_id: str | None
    kind: RecordKind
    started_at_ns: int
    ended_at_ns: int | None
    duration_ns: int | None
    timestamp_utc: str
    sequence: int                 # execution order within the trace
    outcome: Outcome              # ok | error | denied | unknown
    # kind-specific, all optional
    model: str | None
    tool_name: str | None
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    usage_provided: bool          # see §5.5
    error_type: str | None
    error_message: str | None
    content: Mapping[str, Any] | None   # None unless capture is enabled
    truncated: tuple[str, ...]    # which fields were cut, by name
```

### 5.5 `usage_provided` — the Langfuse split, adopted — D-6

**OBSERVATION** (research §3.1): Langfuse distinguishes `providedUsageDetails`
(what the caller reported) from `usageDetails` (what the system computed). The
survey calls this *"the single most useful idea found in this survey"*, and it
composes with ADR-0007 D-5, which already draws the line between a measurement and
the absence of one.

**Decision: one boolean, `usage_provided`.** `True` means the provider reported
these token counts. `False` means the field is present but we did not get it from
the provider. A trace that cannot say "the provider told us this" versus "we
computed this" cannot be audited. `None` in `input_tokens` with
`usage_provided=False` is an honest "not reported"; `0` would be a lie.

**We do not adopt the full four-field split** (`providedUsageDetails` +
`usageDetails` + `providedCostDetails` + `costDetails`). Half of it exists to
serve cost, which we decline (§6). One boolean carries the distinction we need.

### 5.6 Flat records with parent pointers — D-7

**OBSERVATION, and it is unanimous** (research §7): no surveyed system stores a
nested tree. Records are flat; structure is an id pointing at a parent.

**INFERENCE:** flat records are what make JSONL natural rather than a compromise.
A nested tree cannot be appended to without rewriting the file; this can.

---

## 6. Security: content is off by default — D-8

**FACT** (research §2.5): OTel marks every model-facing content attribute `Opt-In`,
with *"Instrumentations SHOULD NOT capture this attribute by default"* and a
warning that `gen_ai.output.messages` is *"likely to contain sensitive information
including user/PII data."*

**OBSERVATION, and it is the uncomfortable one** (research §5): **only one of the
six** surveyed systems states a default-off policy — and it is the only one that
has been through a privacy review. The other five either capture by default and
redact afterwards, or take no position at all.

**INFERENCE: the majority practice is not the safe default, which is exactly why
"follow the crowd" is the wrong move here.** Charter §6 plus this repository's own
posture (ADR-0008 D-6 bounded observations, D-8 actions from structured calls only)
both point at default-off with explicit enablement. We adopt OTel's **rule** while
not implementing OTel, and §2 says so plainly.

```python
class CapturePolicy(Protocol):
    def capture_model_content(self) -> bool: ...
    def capture_tool_payloads(self) -> bool: ...

CaptureNothing()      # the default
CaptureEverything()   # named so a reader sees the decision
```

**Why a policy object and not a boolean** (research §10 Q4): "off by default" needs
a way to be turned on that is not a boolean buried in a call site. A policy is
inspectable, has a `__repr__` that appears in a denial message, and can be
narrowed per-tool later without changing the signature.

**A redacted field is not the same as an absent one.** With capture off, `content`
is `None`. It is never `"__REDACTED__"` — a sentinel string would put a value where
the honest answer is "we did not look".

---

## 7. Invariants

1. **One record is one line.** Encoded with `separators=(",", ":")` and asserted
   free of `\n`/`\r`, the same rule `mcp-client`'s framing applies.
2. **`duration_ns == ended_at_ns - started_at_ns`** whenever both are present.
3. **`duration_ns is None` iff `ended_at_ns is None`.** An unknown duration is
   never `0`.
4. **`record_id` is unique within a trace; `parent_id` names an earlier
   `record_id`** or is `None` for the root.
5. **`sequence` is strictly increasing** within a trace, so execution order is
   recoverable without parsing timestamps.
6. **A write failure never propagates to the caller** (§8).
7. **Every string is bounded before it is written**; every truncation is recorded
   in `truncated`.
8. **`usage_provided=False` with `input_tokens=None`** is the honest default.

---

## 8. Failure modes — and the write-failure decision is D-9

| Failure | Surface |
|---|---|
| Sink path's parent directory does not exist | `TraceRecorderError` at construction — a config error, fail loudly |
| Sink cannot be opened (permission) | `TraceRecorderError` at construction |
| A write fails mid-run (disk full, closed stream) | **Recorded, not raised** — see below |
| A record's content exceeds a bound | Truncated; the field name is listed in `truncated` |
| An unserialisable value in `content` | Converted by a deep JSON-safe pass; never raises |
| `succeed()` and `fail()` both called | `TraceRecorderError` — a programming error |
| Neither called before the context exits | Recorded as `outcome="unknown"`, not omitted |

### 8.1 The write-failure decision, and why neither extreme is right

**OBSERVATION** (research §10 Q7): a recorder that raises can **kill the run it was
observing**; one that swallows can **lose the evidence**. Both are bad, and the two
obvious answers are each half wrong.

**Decision: a mid-run write failure is caught, counted, and inspectable.**
`recorder.write_failures` returns the count and the first exception's message;
`close()` reports it. Nothing is silent — the loss of evidence is itself recorded —
and nothing kills the run.

**Why the constructor still fails loudly:** an unusable sink is a *programming*
error known before the run starts. Failing then is cheap and honest. Failing on
line 400 of an agent run, after the model calls have been paid for, is not.

---

## 9. Bounds — D-10

| Bound | Value | Why |
|---|---|---|
| `max_error_message_chars` | 500 | A sanitised message, not a stack trace |
| `max_content_chars` | 8000 | Matches `react-agent-loop`'s `max_observation_chars` |
| `max_records` | 10000 | A recorder that grows without bound is a leak |

**FACT** (research §3.5): MLflow is the only surveyed system that documents
truncation limits (`250`, `1000`, `10000`, suffix `"..."`). The numbers are ours;
the practice of stating them is theirs.

Truncation is head-only with a suffix naming the removed count, matching
ADR-0008 D-6's observation bounding rather than inventing a second convention.

---

## 10. Decisions carried into ADR-0010

| # | Decision |
|---|---|
| D-1 | Four record kinds on the **noun** axis; correspondence published, conformance **not** claimed. |
| D-2 | A tool call and its result are **one** record. |
| D-3 | `stop_reason` on `trace_end`; a missing `trace_end` means the run did not finish. |
| D-4 | The clock is injected, with **two** methods (`now_ns`, `now_utc`). |
| D-5 | Units live in the field name (`duration_ns`, never a bare float). |
| D-6 | `usage_provided: bool` — the Langfuse split, reduced to one field. |
| D-7 | Flat records with `parent_id`; JSONL append-only. |
| D-8 | **Content capture off by default**, as a policy object. |
| D-9 | Constructor fails loudly; a mid-run write failure is caught, counted, inspectable. |
| D-10 | Bounds stated as ours. |
| D-11 | The recorder defines its own record type; it does **not** import `react_agent_loop`. |
| D-12 | No aggregation in Phase 1. |
| D-13 | Sync-only. |

### 10.1 D-11, stated fully — the dependency question

**OBSERVATION** (research §10 Q2): charter §31 says compose through protocols, but
`Step` is `react-agent-loop`'s type, and importing it would make the recorder
depend on the loop.

**Decision: the recorder owns its record type and imports nothing from
`react_agent_loop`.** An adapter that maps `Step` → records lives in the loop's
own `adapters.py`, beside the two adapters already there, because that is the
module that already imports its dependencies. The recorder stays usable by
anything that can call `record_model_call` — which is what makes it independent
rather than a private detail of one loop.

---

## 11. Testing strategy (charter §18)

No network, no real clock, no real model.

- **Scripted clock.** A `Clock` double returning a fixed sequence, so every
  duration assertion is exact rather than tolerant.
- **A real file** in `tmp_path`, read back and parsed — the only test that proves
  the on-disk format.
- **An in-memory `io.StringIO` sink** for every behavioural test.

**Required failure-path tests** (charter §21): a bad sink path raises at
construction; a mid-run write failure is counted and does not propagate; a
5000-char error message is truncated and the field is named in `truncated`; an
unserialisable content value does not raise; `duration_ns` is `None` when the
record never ended; a tool-call block that raises still writes a record with
`outcome="error"`; capture-off writes `content is None` and never a sentinel;
capture-on writes the payload; `usage_provided` is `False` when tokens are absent;
`sequence` is strictly increasing; `parent_id` points at a real earlier record.

**Benchmark plan (charter §19, deferred):** a future benchmark would measure
records-per-second on a JSONL sink and the cost of the JSON-safe pass. Not a
Phase 1 concern.

---

## 12. Known limitations, stated before implementation

1. **No conformance claim to any standard** (§2), because there is no stable
   standard to conform to.
2. **No cost.** Recorded as DEFER, with the reason: a price table ages.
3. **No aggregation.** A second responsibility; compose it from the records.
4. **No sampling**, so a long run writes every record.
5. **`max_records` drops records past the cap** and records the drop count — a
   bounded trace of an unbounded run is necessarily incomplete.
6. **Content is off by default**, so a trace alone does not explain *what* the
   model said. That is the intended trade.
7. **A write failure loses that record.** The count and the first message survive;
   the record does not.
8. **No concurrency.** One recorder, one trace, one thread.

---

## 13. Out-of-scope summary

See §3. The short version: **record flat, bounded, content-free by default, and
never kill the run.**