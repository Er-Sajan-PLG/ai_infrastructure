# Research: `execution-trace-recorder`

**Capability:** [`execution-trace-recorder`](../../TAXONOMY.md) (category: observability)
**Status:** `RESEARCHED`
**Session:** 14
**Date:** 2026-09-15
**Depends on:** nothing
**Decision:** pending (see §9 open questions)

---

## 1. The problem, stated precisely

An agent run produces behaviour that is invisible after the fact. `react-agent-loop`
returns an `AgentResult` carrying a `Step` trace, so a *single* run is inspectable
in memory — but nothing persists it, nothing aggregates across runs, and nothing
records how long any step took or what it cost.

The capability's own taxonomy entry puts it plainly: *"Without traces, agent
behavior cannot be tested, evaluated, or debugged with evidence."* Charter §18
requires demonstrated runs; a trace is the artefact that makes a run reviewable by
someone who was not present.

This is also the first capability in the **observability** category, so this
research has to answer a prior question: what does this repository mean by a
"trace", given that three ecosystems already mean three different things?

## 2. What the standard says, and how stable it is

### 2.1 FACT: the OpenTelemetry GenAI conventions are `Development`, and they just moved repositories

Fetched 2026-09-15.

* `docs/gen-ai/gen-ai-spans.md` opens with `**Status**: [Development][DocumentStatus]`.
* Every `gen_ai.*` attribute row in that document carries the
  `![Development]` badge. The *only* attributes marked `![Stable]` are
  borrowed from the core conventions: `error.type`, `server.address`,
  `server.port`.
* The pages in `open-telemetry/semantic-conventions` at
  `docs/gen-ai/gen-ai-spans.md` and `docs/gen-ai/gen-ai-agent-spans.md`
  now contain only a stub: *"GenAI semantic conventions have moved to the
  [OpenTelemetry GenAI semantic conventions repository]. This page has moved
  and is no longer maintained in this repository."*
* The new repository's README declares its **Schema URL is `TODO`** — there is
  no published schema URL for the GenAI conventions yet.

**Consequence for this repository.** There is no stable standard to conform to.
Anything that claims "OTel-compatible agent tracing" today is claiming
compatibility with a moving development target. This is the same finding shape as
`tool-registry` (session 6): the ecosystem has a *vocabulary*, not a *contract*.

### 2.2 FACT: the span-name rule is a template, not a fixed string

> **Span name** SHOULD be `{gen_ai.operation.name} {gen_ai.request.model}`.

And, on the agent side, `invoke_agent` spells out a conditional:

> **Span name** SHOULD be `invoke_agent {gen_ai.agent.name}` if
> `gen_ai.agent.name` is readily available. When `gen_ai.agent.name` is not
> available, it SHOULD be `invoke_agent`.

So a name is *derived*, never stored. A recorder that stores a pre-rendered name
loses the ability to answer "show me every call to this model" by attribute
filter.

### 2.3 FACT: retries collapse into one span

> If a transient issue happened and the request was retried automatically, the
> corresponding span SHOULD cover the duration of the logical operation with all
> retries.

This is a direct interaction with ADR-0007 **D-4**, which decided that retry
policy belongs to the *caller*, and that the provider primitive only classifies
(`retryable`) and exposes `retry_after`. The conventions agree with the layering
and then add a recording rule: if a caller *does* retry, the trace should show one
logical operation, not N attempts. A recorder that only sees the primitive cannot
know this; the retrying caller must be the one to say so.

### 2.4 FACT: the operation vocabulary is a closed list of verbs

`gen_ai.operation.name` well-known values, verbatim from the registry table:
`chat`, `create_agent`, `create_memory`, `create_memory_store`, `delete_memory`,
`delete_memory_store`, `embeddings`, `execute_tool`, `fetch_response`,
`generate_content`, `invoke_agent`, `invoke_workflow`, `plan`, `retrieval`,
`search_memory`, `text_completion`, `update_memory`, `upsert_memory`.

Two of these matter for this capability: **`execute_tool`** and **`invoke_agent`**.
Note what they are: *verbs*. OTel has **no span-type enum** — it models "what kind
of thing is this" as "what operation was performed". That is a materially different
modelling choice from both OpenInference and Langfuse (§4).

### 2.5 FACT: the model-facing content attributes are all `Opt-In`

Verbatim from the attribute table, for `gen_ai.input.messages`,
`gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions`,
`gen_ai.memory.query.text`, and `gen_ai.memory.records`:

> `Opt-In`

And the footnotes are explicit, e.g. for `gen_ai.memory.query.text`:

> Instrumentations SHOULD NOT capture this attribute by default. Capture SHOULD be
> gated by an explicit user opt-in, for example
> `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`.
>
> > [!Warning]
> > This attribute may contain sensitive information.

The warning is stronger for `gen_ai.output.messages` and `gen_ai.memory.records`:
*"likely to contain sensitive information including user/PII data."*

### 2.5.1 FACT: this policy *reversed*, and the reversal is visible in the registry

The delegation report supplies the transition I had only suspected, read from the
**Deprecated GenAI Attributes** table in
`semantic-conventions/docs/registry/attributes/gen-ai.md`:

| Old attribute | Stability | Description |
|---|---|---|
| `gen_ai.prompt` | `![Deprecated]` | *"Removed, no replacement at this time."* — *"Deprecated, use Event API to report prompt contents."* |
| `gen_ai.completion` | `![Deprecated]` | *"Removed, no replacement at this time."* — *"Deprecated, use Event API to report completions contents."* |

The replacement mechanism is an **event**, `gen_ai.client.inference.operation.details`
(`Opt-In`), described as *"Describes the details of a GenAI completion request
including chat history and parameters. This event could be used to store input and
output details independently from traces."*

So the change is threefold, and all three point the same way: (a) the old flat
content attributes were deprecated **and removed with no replacement at that
location**; (b) content moved to structured `gen_ai.input.messages` /
`gen_ai.output.messages` / `gen_ai.system_instructions`, all `Opt-In`; (c) an
`Opt-In` event exists for detail capture decoupled from traces.

**UNKNOWN:** the *date* of this transition. Neither subagent fetched git history,
so the change is visible and complete in the current docs but **not dated**. Do not
cite a version or date for it.

**Consequence.** The standard's own position is that **prompt and completion text
is off by default and requires an explicit opt-in**. That is a security decision
this capability should adopt rather than re-derive — and it is the same shape as
ADR-0008 D-6 (observations bounded) and D-8 (actions from structured calls only):
the safe thing is the default. The deprecated-with-no-replacement detail matters
for a second reason: it is what a *reversal* looks like in a `Development` spec.
Anyone who had built against `gen_ai.prompt` on a span has no migration target.

### 2.6 FACT: usage is modelled, cost is not

Token attributes found, all `Recommended` and all `![Development]`:

`gen_ai.usage.input_tokens` (int), `gen_ai.usage.output_tokens` (int),
`gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_write.input_tokens`,
`gen_ai.usage.reasoning.output_tokens`, plus `text.`, `image.`, and `audio.`
variants of the same three shapes.

**No cost attribute exists in the GenAI spans document.** A grep of the full
document for `cost`, `Cost`, `USD`, and `pricing` returned **no matches**. Cost is
deliberately out of scope for the standard: it is a pricing-table computation, and
a pricing table is not a telemetry convention.

### 2.7 FACT: one timing field is specified, in seconds

> `gen_ai.response.time_to_first_chunk` ... double ... Time to first chunk in a
> streaming response, measured from request issuance, in seconds.

Start and end timestamps are not `gen_ai.*` attributes at all — they are the OTel
span's own `start_time` / `end_time`. The `gen_ai` conventions add *derived*
timing, not the container's.

### 2.8 FACT: content on spans may be a JSON string; on events it must be structured

> When the attribute is recorded on events, it MUST be recorded in structured
> form. When recorded on spans, it MAY be recorded as a JSON string if structured
> format is not supported and SHOULD be recorded in structured form otherwise.

This is an OTel wire constraint (span attributes are scalars or homogeneous
arrays) leaking into the convention. It is *not* a statement that JSON strings are
good; it is a statement that OTel cannot carry nested structure on a span.

### 2.9 FACT: the `execute_tool` span — a tool call is a span, and its result is an attribute

My first pass could not read this section (the fetch truncated before it). The
delegation report read it verbatim, so the gap is now closed:

> Describes tool execution span. `gen_ai.operation.name` SHOULD be `execute_tool`.

| Attribute | Requirement | Type | Note |
|---|---|---|---|
| `gen_ai.tool.name` | **`Required`** | string | — |
| `gen_ai.tool.call.id` | `Recommended` if available | string | e.g. `call_mszuSIzqtI65i1wAUOE8w5H4` |
| `gen_ai.tool.call.arguments` | **`Opt-In`** | any | — |
| `gen_ai.tool.call.result` | **`Opt-In`** | any | *"The result returned by the tool call (if any and if execution was successful)."* |
| `gen_ai.tool.type` | `Recommended` if available | string | `function` / `extension` / `datastore` |
| `gen_ai.tool.description` | `Recommended` if available | string | flagged *"may contain sensitive information"* |

**Span name** SHOULD be `execute_tool {gen_ai.tool.name}`; **Span kind** SHOULD be
`INTERNAL`.

Three consequences worth stating:

1. **The result is an attribute on the same span, not a separate signal.** There is
   no "tool result span". A recorder that models a tool call and its result as two
   records is diverging from every surveyed system.
2. **Arguments and result are both `Opt-In`.** A tool call can be recorded —
   name, id, timing, success — with **neither its inputs nor its outputs**. That is
   the same default-off posture as model content (§2.5), and it means a trace is
   useful and safe without ever holding tool payloads.
3. **The spec addresses manually-instrumented tools explicitly:** *"Tools are often
   executed directly by application code. Application developers are encouraged to
   follow this semantic convention for tools invoked by their own code and to
   manually instrument any tool calls that automatic instrumentations do not
   cover."* That is precisely our situation — `tool-registry` dispatches in-process,
   so no automatic instrumentation exists.

### 2.9.1 FACT: the full span-name rule set

Correcting §2.2's partial statement, the complete rule is
`<operation-name> <discriminator>`:

| Operation | Span name | Span kind |
|---|---|---|
| inference | `{gen_ai.operation.name} {gen_ai.request.model}` | `CLIENT` (or `INTERNAL`) |
| `create_agent` | `create_agent {gen_ai.agent.name}` | `CLIENT` |
| `invoke_agent` | `invoke_agent {gen_ai.agent.name}`, or bare `invoke_agent` | `CLIENT` **or** `INTERNAL` |
| `invoke_workflow` | `invoke_workflow {gen_ai.workflow.name}` | `INTERNAL` |
| `plan` | `plan {gen_ai.agent.name}`, or bare `plan` | `INTERNAL` |
| `execute_tool` | `execute_tool {gen_ai.tool.name}` | `INTERNAL` |

**OBSERVATION.** `invoke_agent` exists as **two** spans — client and internal —
distinguished only by Span kind. Every agent span carries the caveat *"Semantic
conventions for individual GenAI systems and frameworks MAY specify different span
name format."* So even the name is explicitly framework-overridable.

## 3. What the tools do

### 3.1 Langfuse: a 10-value type enum, and a provided/computed split

Fetched from `packages/shared/src/domain/observations.ts` (verbatim):

```ts
export const ObservationType = {
  SPAN: "SPAN", EVENT: "EVENT", GENERATION: "GENERATION", AGENT: "AGENT",
  TOOL: "TOOL", CHAIN: "CHAIN", RETRIEVER: "RETRIEVER", EVALUATOR: "EVALUATOR",
  EMBEDDING: "EMBEDDING", GUARDRAIL: "GUARDRAIL",
} as const;
```

Levels: `DEBUG`, `DEFAULT`, `WARNING`, `ERROR`.

The observation schema carries — among ~40 fields — this pair:

```
providedUsageDetails:  z.record(z.string(), z.number()),
usageDetails:          z.record(z.string(), z.number()),
costDetails:           z.record(z.string(), z.number()),
providedCostDetails:   z.record(z.string(), z.number()),
inputCost, outputCost, totalCost:  z.number().nullable(),
```

**This is the single most useful idea found in this survey.** The schema
distinguishes what the *caller reported* from what the *system computed*. A
recorder that collapses those two loses the ability to answer "did the provider
tell us this, or did we guess it?" — which is exactly the distinction ADR-0007 D-5
already draws between "a measurement" and "the absence of one."

Timing fields: `startTime`, `endTime` (nullable), plus derived `latency` and
`timeToFirstToken`. Linking: `parentObservationId` (nullable). Errors:
`level` + `statusMessage`. Content: `input`, `output` — plain nullable JSON, with
**no capture policy expressed in the schema** (the SDK decides).

### 3.2 OpenInference: a 10-value span-kind enum, and a cost model (one of four)

Fetched from `spec/semantic_conventions.md` (verbatim):

> The `openinference.span.kind` attribute is **required** for all OpenInference
> spans and identifies the type of operation being traced.

Kinds: `LLM`, `EMBEDDING`, `CHAIN`, `RETRIEVER`, `RERANKER`, `TOOL`, `AGENT`,
`GUARDRAIL`, `EVALUATOR`, `PROMPT`. Definitions worth quoting:

* `TOOL` — *"A span that represents a call to an external tool such as a
  calculator, weather API, or any function execution that is invoked by an LLM or
  agent."*
* `AGENT` — *"A span that encompasses calls to LLMs and Tools. An agent describes
  a reasoning block that acts on tools using the guidance of an LLM."*

Tool attributes: `tool.name`, `tool.description`, `tool.json_schema`, `tool.id`,
`tool.parameters`, plus `tool_call.id`, `tool_call.function.name`,
`tool_call.function.arguments`.

**Cost is modelled here.** Of the six surveyed, four model cost (see §6);
OpenInference is the one whose *spec* defines the field names:

> Cost attributes store floating point values in USD currency.

with `llm.cost.prompt`, `llm.cost.completion`, `llm.cost.total`, and nested
`completion_details.{output,reasoning,audio}` / `prompt_details.{input,cache_write,cache_read,cache_input,audio}`.

Errors are modelled as *exception attributes*: `exception.type`,
`exception.message`, `exception.stacktrace`, `exception.escaped`.

### 3.3 FACT: OpenInference documents a real token-accounting trap

Verbatim, and this is a correctness issue, not a style preference:

> The `prompt_details.*` values are sub-counts of `llm.token_count.prompt`: they
> are already included in it, so `llm.token_count.prompt` is expected to be
> greater than or equal to their sum. For providers whose reported input token
> count excludes cache tokens (e.g. Anthropic's `input_tokens`), instrumentations
> should fold the cache read/write tokens back into `llm.token_count.prompt` (and
> `llm.token_count.total`) rather than reporting the exclusive value.

Anthropic reports `input_tokens` **excluding** cache reads; OpenAI reports
`prompt_tokens` **including** cached tokens. A recorder that sums naively produces
a number that is not comparable across providers. ADR-0007 D-7 already established
that lossy translation must be *declared*, never silent; this is the same rule
applied to a derived metric.

### 3.4 FACT: OpenInference flattens lists into indexed attribute prefixes

> All list-based attributes use zero-based indexing in their flattened form.

Pattern: `<prefix>.<index>.<suffix>`, e.g.
`llm.input_messages.0.message.role`. Again an OTel wire constraint, not a design
preference — but it means a consumer of an OpenInference trace must *unflatten* to
recover structure.

### 3.5 MLflow: the only surveyed system with a documented serialized span

My first fetch of `docs/docs/genai/tracing/index.mdx` returned **HTTP 404**, and I
wrote that off as "path moved". The delegation report found the actual cause, and
it is worth recording because it is a trap: **MLflow's default branch is `master`,
not `main`.** Every `main`-rooted raw URL for that repository 404s — including
`mlflow/entities/span.py`. The doc path genuinely does not exist, but the *code*
was reachable all along on the right branch.

Once fetched, the model is:

* **Unit of record: the span, deliberately OpenTelemetry-shaped.** `Span` wraps an
  `otel_span` and exposes `start_time_ns` / `end_time_ns` in **nanoseconds**.
* **Type taxonomy is a non-enum, with the rationale stated in source:**
  ```python
  # Not using enum as we want to allow custom span type string.
  class SpanType:
      LLM = "LLM"; CHAIN = "CHAIN"; AGENT = "AGENT"; TOOL = "TOOL"
      CHAT_MODEL = "CHAT_MODEL"; RETRIEVER = "RETRIEVER"; PARSER = "PARSER"
      EMBEDDING = "EMBEDDING"; RERANKER = "RERANKER"; MEMORY = "MEMORY"
      UNKNOWN = "UNKNOWN"; WORKFLOW = "WORKFLOW"; TASK = "TASK"
      GUARDRAIL = "GUARDRAIL"; EVALUATOR = "EVALUATOR"
  ```
  Stored as the attribute `mlflow.spanType`.
* **Errors are a status *object*, not a string.** `SpanStatusCode` is
  `UNSET` / `OK` / `ERROR` — *"Uses the same set of status codes as
  OpenTelemetry"* — carried in a `SpanStatus` dataclass with `description` that
  *"should be only set when the status is ERROR"*. `record_exception()` both adds
  a span event and flips the status.
* **Cost is computed by MLflow itself**, not supplied: the `TraceInfo.cost`
  docstring says *"The cost tracking is calculated based on token usage and model
  pricing from LiteLLM. Cost tracking is not supported for all LLM providers."*
  This is the clearest cost-provenance statement in the whole survey.
* **It has a versioned on-disk form.** `Span.to_dict()` emits
  `trace_id`, `span_id`, `parent_span_id`, `name`, `start_time_unix_nano`,
  `end_time_unix_nano`, `events[]`, `status{code,message}`, `attributes`, `links`
  — with `TRACE_SCHEMA_VERSION = 3` and a `_is_span_v2_schema` discriminator.
  Attribute values are JSON-stringified for OTel compatibility, with the reason
  stated in source: *"we serialize all into JSON string here for the simplicity in
  deserialization process"*.
* **It documents truncation limits**, which the other four do not:
  `MAX_CHARS_IN_TRACE_INFO_METADATA = 250`,
  `TRACE_REQUEST_RESPONSE_PREVIEW_MAX_LENGTH_OSS = 1000`,
  `TRACE_REQUEST_RESPONSE_PREVIEW_MAX_LENGTH_DBX = 10000`, suffix `"..."`.

**OBSERVATION.** MLflow is the **only** one of the six surveyed systems that
documents a serialized span JSON a zero-dependency emitter could target without an
HTTP ingest service — and it is also the only one that states an explicit
truncation policy. Both are direct evidence for §9's storage and bounding
decisions.

### 3.5.1 LangSmith: a run, and `dotted_order`

Unit of record is the **run** (`run_type`). The deprecated enum is
`tool` / `chain` / `llm` / `retriever` / `embedding` / `prompt` / `parser` — note
**no `agent`**. Timing is datetimes with `latency` derived in **seconds**, and
`first_token_time` as an absolute datetime, not a duration. Parent linkage is
`parent_run_id` plus a `dotted_order` string documented as *"{time}{run-uuid}.* so
that a trace can be sorted in the order it was executed"* — an ordering key, which
none of the others have.

### 3.5.2 AgentOps: a session root, and one span kind enum

**OBSERVATION, and a correction to the premises of this survey.** AgentOps's
README still implies an event model, but its SDK README states the transition
outright: *"In AgentOps v0.4, we've transitioned from the 'Event' concept to using
'Spans' for all event tracking."* And: *"Session: The master trace that serves as
the root for all spans. No spans can exist without a session at the top."*

Span kinds: `workflow`, `session`, `task`, `operation`, `agent`, `tool`, `llm`,
`chain`, `text`, `guardrail`, `http`, `unknown`. Transport is OTLP/HTTP with a
bearer JWT. Its cost key is a single `gen_ai.usage.total_cost` — no input/output
split — and provenance is not stated in the files read.

## 4. Six taxonomies, and where they agree

| | Kind label | Axis | Cardinality |
|---|---|---|---|
| OTel GenAI | **none** | `gen_ai.operation.name` — a **verb** | 18 operations |
| OpenInference | `openinference.span.kind` | a **noun** | 10 kinds |
| Langfuse | `ObservationType` | a **noun** | 10 types |
| LangSmith | `run_type` | a **noun** | 7 types |
| MLflow | `mlflow.spanType` | a **noun**, non-enum | 15 types |
| AgentOps | `agentops.span.kind` | a **noun** | 12 kinds |

**The headline convergence, and it is stronger than I first thought:**
**no surveyed system makes a tool call a distinct class.** All six use one record
type plus a type/kind label. OpenInference/Langfuse/MLflow/AgentOps each put
`TOOL` and an LLM kind in the *same enum*; LangSmith uses `run_type == "tool"`
vs `"llm"`; OTel uses an operation verb on a generic span.

| System | Tool label | Model label |
|---|---|---|
| OpenInference | `TOOL` | `LLM` |
| Langfuse | `TOOL` | `GENERATION` |
| LangSmith | `tool` | `llm` |
| MLflow | `TOOL` | `LLM` / `CHAT_MODEL` |
| AgentOps | `tool` | `llm` |
| OTel | `execute_tool` | `chat` / `generate_content` |

**Divergence that matters for us:**
* OTel refuses a node *type* entirely — the only one.
* **LangSmith has no `agent` type at all.** A system whose whole product is agent
  tracing does not have "agent" as a run type. That is worth noticing before
  treating `AGENT` as obviously necessary.
* MLflow makes its taxonomy a **non-enum on purpose**, with the reason in source:
  *"Not using enum as we want to allow custom span type string."* That is the
  opposite of OTel's closed operation list, and it is a real design fork.
* OpenInference has `RERANKER` and `PROMPT`; Langfuse has `EVENT` (a
  zero-duration point-in-time record), which no other system has first-class.
* AgentOps has `session` and `workflow` as *span kinds*, making the trace root a
  span rather than a separate record.

**INFERENCE.** "Compatible with all six" is not a coherent Phase 1 goal — they
disagree on the axis (verb vs noun), on closedness (enum vs open string), and on
whether the trace root is itself a span. The honest move is to pick one axis,
record the mapping, and state which was chosen and why.

## 5. Content capture: default-off is the majority position, not the rule

* **OTel**: explicit and strongest — `Opt-In`, *"SHOULD NOT capture by default"*,
  gated by `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`, PII warnings, and
  a **deprecated-and-removed** prior mechanism (§2.5.1).
* **OpenInference**: no opt-in marker on `input.value` / `llm.input_messages.*`.
  But `configuration.md` defaults **every** `OPENINFERENCE_HIDE_*` flag to `False`,
  and defines a redaction placeholder, the literal `"__REDACTED__"`, plus
  `OPENINFERENCE_BASE64_IMAGE_MAX_LENGTH = 32,000`. So the mechanism is redaction
  *after* capture, not prevention *before* it — and truncation is image-only.
* **MLflow**: captures by default, but **truncates previews** at 1000 chars (OSS) /
  10000 (DBX) and metadata at 250, with suffix `"..."`.
* **Langfuse**: `input` / `output` are plain nullable fields; the shared schema
  takes no position and I did not read the SDK.
* **LangSmith**: `inputs` / `outputs` are ordinary run fields; no policy found.
* **AgentOps**: no capture policy found in the files read.

**OBSERVATION.** Only **one of six** states a default-off policy, and it is the
only one that has been through a privacy review. The other five either capture by
default and redact, or say nothing.

**INFERENCE for this repository.** The majority practice is *not* the safe default,
which is precisely why "follow the crowd" would be the wrong move here. Charter §6
plus this repo's own posture (ADR-0008 D-6 bounded observations, D-8 actions from
structured calls only) both point at default-off with explicit enablement. We adopt
OTel's *rule* while not implementing OTel — and we should say so plainly rather
than implying conformance.

## 6. Cost — four positions, and the provenance question is the useful one

| | Cost modelled? | Who computes it? |
|---|---|---|
| OTel GenAI | **No.** No cost attribute or metric exists. | — |
| OpenInference | Yes, `llm.cost.*` in USD, with detail breakdowns | the instrumentor supplies it |
| Langfuse | Yes, `inputCost`/`outputCost`/`totalCost` | **both** — `providedCostDetails` vs `costDetails` |
| LangSmith | Yes, `total_cost`/`prompt_cost`/`completion_cost` (Decimal) | not stated in the schema |
| MLflow | Yes, `mlflow.llm.cost` | **MLflow itself**, from a LiteLLM price table |
| AgentOps | Yes, but only a single `gen_ai.usage.total_cost` | not stated |

**MLflow is the only one that states its cost provenance outright**, and the
statement carries a limitation worth quoting: *"The cost tracking is calculated
based on token usage and model pricing from LiteLLM. Cost tracking is not supported
for all LLM providers."*

**Langfuse's split is the better design** — it can express "the caller said this"
and "we derived this" as different fields, which composes directly with ADR-0007
D-5.

**INFERENCE.** Cost is a pricing table applied to a usage record, not a telemetry
primitive, and OTel's refusal to model it is defensible. Four of six do model it,
so it is not eccentric — but every one that does either embeds a price table or
asks the caller. **Phase 1 records usage and declines cost**, because a price table
ages and this capability has no other reason to hold one.

## 7. Shape: flat records with parent pointers, in all six

| | Record unit | Link mechanism |
|---|---|---|
| OTel | span | ambient span context |
| OpenInference | span | `parent_id` field + `trace_id` in span context |
| Langfuse | observation | `parentObservationId` (nullable) + `traceId` |
| LangSmith | run | `parent_run_id` + `parent_run_ids` + `dotted_order` |
| MLflow | span | OTel context object, encoded from `parent_id` |
| AgentOps | span | `parent.id` attribute + `trace.id`, over an OTel context |

**OBSERVATION, and it is unanimous: no surveyed system stores a nested tree.**
Records are flat; structure is an id pointing at a parent. LangSmith adds
`dotted_order` — a sortable execution-order key — which no other system has and
which matters for replay.

**Two further structural notes.** AgentOps makes the *session* the root and every
span a descendant, so the trace root is itself a span. MLflow serializes attributes
as JSON strings specifically because OTel span attributes cannot carry nested
structure — the same constraint OTel's own conventions acknowledge (§2.8).

**INFERENCE.** Flat records plus a parent id is what makes JSONL a natural on-disk
format rather than a compromise: a nested tree cannot be appended to without
rewriting, and this can.

## 8. Timing — and the units hazard, which is the real interop risk

| | Start / end | Unit | Derived |
|---|---|---|---|
| OTel | span's own | — | `gen_ai.response.time_to_first_chunk` (**seconds**, double) |
| Langfuse | `startTime` / `endTime` (nullable) | not stated | `latency`, `timeToFirstToken` (units **not stated**) |
| OpenInference | OTel span | ISO 8601 with offset | time-to-first-token as a **span event**, not an attribute |
| LangSmith | `start_time` / `end_time` | datetime | `latency` derived in **seconds**; `first_token_time` an absolute datetime |
| MLflow | `start_time_ns` / `end_time_ns` | **nanoseconds** | trace `execution_duration` in **milliseconds** |
| AgentOps | OTel-native (not stated) | not stated | `gen_ai.streaming.time_to_first_token`, `time_to_generate`, `streaming_duration`, `chunk_count` — units not stated |

**Two observations, both load-bearing.**

1. **`endTime` is nullable in Langfuse** (and `end_time` is `Optional` in
   LangSmith, and MLflow's `end()` is not always reached). That is the honest model
   of a span that started and never finished — a crash, a kill, a process death. A
   recorder that *requires* an end time cannot record the most interesting failure.

2. **The units disagree, and one system disagrees with itself.** MLflow stores span
   times in **nanoseconds** and trace duration in **milliseconds in the same
   object**; LangSmith derives latency in seconds from datetimes; OTel specifies
   seconds for its one derived field; Langfuse and AgentOps state no unit at all.

**INFERENCE — this is the single most likely source of silent bugs in this
capability.** Every surveyed system agrees on *what* to time and disagrees on
*what to call the unit*. A recorder must therefore either (a) state its unit in the
field name (`duration_ns`, `duration_s`) or (b) store an unambiguous type
(`timedelta`, nanosecond int) and never a bare float. An unlabelled `latency: 1.5`
is a bug waiting for a reader who assumed seconds.

## 9. Synthesis: what this implies for our design

Nine points, each traceable to evidence above.

1. **There is no standard to conform to, so we must not claim one.** OTel's GenAI
   conventions are `Development`, just moved repositories, have no published schema
   URL, and have *already reversed* one content-capture decision. Following
   `tool-registry`'s precedent, the honest position is to study them and record the
   correspondence — not to assert compatibility. §2.1, §2.5.1.

2. **Pick one axis and document the mapping.** OTel uses an operation *verb*; the
   other five use a kind *noun*; MLflow deliberately keeps its taxonomy open.
   "Compatible with all six" is not coherent. §4.

3. **Prompt and completion text is off by default, and enablement is explicit.**
   One of six states that rule and it is the only one with a privacy review. We
   adopt the rule without claiming conformance. This is also what makes a trace
   safe to commit as a test fixture. §5.

4. **Distinguish provided from derived numbers.** Langfuse's
   `providedUsageDetails` vs `usageDetails`, and `providedCostDetails` vs
   `costDetails`, is the right instinct and composes with ADR-0007 D-5. A trace
   that cannot say "the provider told us this" versus "we computed this" cannot be
   audited. §3.1, §6.

5. **Do not model cost in Phase 1.** Four of six do, but each either embeds a
   price table or asks the caller, and MLflow's own docstring concedes *"not
   supported for all LLM providers."* A price table ages. Record usage; expose cost
   later. §6.

6. **Flat records with parent ids; `endTime` nullable.** Unanimous across six, and
   the nullable end is what makes a crashed run recordable. §7, §8.

7. **Label the time unit in the field name or the type.** Six systems, at least
   four different unit conventions, and MLflow disagrees with *itself* within one
   object. Never a bare `latency: float`. §8.

8. **Record the stop reason.** None of the six has a place for "why did this run
   end". `react-agent-loop` already computes `StopReason` — it is arguably the
   single most valuable field in the whole trace and it is our field to add. §10.

9. **A tool call and its result are ONE record.** OTel puts the result as an
   attribute on the same span; OpenInference and MLflow carry `tool_call.id`
   alongside; none models them as two nodes. Splitting them would be a divergence
   with no justification. §2.9, §3.2.

## 10. Open questions carried to the decision

1. **Storage format**: JSONL append-only (the taxonomy entry's stated intent), or
   something else? JSONL composes with §7's flat records; nothing else does as
   cheaply.
2. **Does the recorder define its own event type, or consume `Step` objects?**
   Charter §31 says compose through protocols — but `Step` is `react-agent-loop`'s
   type, and depending on it makes the recorder depend on the loop.
3. **Where does the clock come from?** `time.monotonic` vs `time.time`; injectable
   or not. A non-injectable clock makes every timing test flaky.
4. **Is redaction a policy object or a callback?** "Off by default" needs a way to
   be turned on that is not a boolean buried in a call site.
5. **Does it own aggregation**, or only recording? "aggregate stats" is in the
   taxonomy entry; that is a second responsibility.
6. **How does a trace correlate with the loop's `StopReason`?** The reason a run
   ended is arguably the most important single field, and **none of the six**
   surveyed systems has a place for it. This is our field to add.
7. **Does writing fail loudly or degrade?** A recorder that raises can kill the run
   it was observing; one that swallows can lose the evidence.

## 11. Method and limitations

**Verified directly, by me, from primary source (fetched 2026-09-15):**
OpenTelemetry GenAI spans and agent spans (both the current
`semantic-conventions-genai` repository and the moved-stub pages in
`semantic-conventions`), Langfuse `packages/shared/src/domain/observations.ts`,
OpenInference `spec/semantic_conventions.md`.

**Verified via delegation, with the subagent's URL and quoted line for each claim:**
OTel events, metrics, and the attribute registry (including the Deprecated GenAI
Attributes table and the `execute_tool` span); OpenInference `traces.md` and
`configuration.md`; Langfuse `domain/traces.ts` and `server/ingestion/types.ts`;
LangSmith `python/langsmith/schemas.py`; MLflow `entities/span.py`,
`entities/span_status.py`, `entities/trace_info.py`, `tracing/constant.py` (on
**master**); AgentOps `sdk/README.md`, `semconv/span_kinds.py`,
`semconv/span_attributes.py`, `semconv/core.py`, `semconv/status.py`,
`sdk/exporters.py`, `sdk/types.py`.

**Could not verify — stated, not filled in from memory:**
* **The date of the content-capture reversal.** No git history was fetched. The
  change is visible and complete in current docs; it is **not dated**. Do not cite
  a version or date for it.
* **Allowed OTel span-status values.** The conventions delegate to
  `docs/general/recording-errors.md`, which was not fetched. Do not assume
  `{Unset, Error, Ok}` from memory.
* **Langfuse `latency` / `timeToFirstToken` units** — not stated in the files read.
* **Langfuse payload truncation limits** — not found in the shared schema or
  ingestion types.
* **AgentOps core start/end/latency field names** and numeric queue/flush defaults
  — not present in the files read.
* **LangSmith and AgentOps cost-computation provenance** — not stated.
* **MLflow `tracing/sampling.py`** — the file exists in the directory listing
  (1579 bytes) but was not read, so its policy is unknown.
* **The MCP doc** (`docs/gen-ai/mcp.md`) and the GenAI JSON schema files were not
  fetched.
* **OpenInference's `tool_calling.md`, `llm_spans.md`, `embedding_spans.md`,
  `multimodal_attributes.md`, `annotations.md`** — directory listing confirmed,
  contents not read.

**Method notes worth carrying forward.**

1. **A 200 is not evidence.** Both OTel pages I fetched from the *old* repository
   location returned HTTP 200 with a "this page has moved" stub. A survey that only
   checked status codes would have concluded the conventions were where they used
   to be. Every claim above was read from content.

2. **A 404 can be a branch problem, not a missing file.** MLflow's default branch
   is `master`, not `main`, so every `main`-rooted raw URL for that repository
   fails — including source files that plainly exist. "The path moved" was my first
   inference and it was wrong.

3. **The two surveys disagreeing on cardinality is itself data.** My own count of
   OTel's operation values was 18; the delegation report's attribute list is longer
   because it read the registry page, not just the spans page. Neither is wrong;
   they are different views. Where they differ, the narrower claim (spans page) is
   the one quoted as FACT above.

