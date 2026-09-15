# Research: Tool Registry & Function Calling Primitive

- **Capability:** `tool-registry` (category: tools)
- **Status:** `RESEARCHED` → `UNDERSTOOD`
- **Session:** 6
- **Date:** 2026-09-15
- **Decision:** see [ADR-0006](../../docs/decisions/0006-tool-registry.md) *(pending)*

Claims are labelled per charter §6:
**FACT** (verified, cited) · **OBSERVATION** (inferred from docs/source) ·
**INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice, not a fact).

---

## 1. The problem, stated without reference to any implementation

> Give agents and runtimes a uniform, inspectable, validated boundary between **model intent** and **executable behavior**.

Stated that way, the problem decomposes into five separable concerns — and keeping
them separable is the design. **DESIGN OPINION.**

| # | Concern | Question it answers |
|---|---|---|
| 1 | **Declaration** | What tools exist, and what is each one's typed input contract? |
| 2 | **Selection** | Which subset is advertised to a model on this call, and why? |
| 3 | **Binding** | A model emits "call `weather` with these arguments" — how does that map to a callable? |
| 4 | **Validation** | Are the arguments well-formed and semantically acceptable *before* any side effect? |
| 5 | **Invocation & result** | Run it, normalise success and failure, hand a structured result back. |

**INFERENCE — the load-bearing insight:** almost every difficulty in this space
comes from *conflating* these concerns. A registry that also dispatches, or a
validator that also calls the model, cannot be tested in isolation or reused by a
different runtime. The four surveyed projects each collapse some of these five
boundaries, and the places they collapse them are the places their users report
pain (§3).

**DESIGN OPINION — where our boundary sits:** concern 1 (declaration) and its
adjacent validation (4) are *this capability's* job. Selection (2) belongs to the
caller/agent loop. Binding (3) is a thin adapter over the registry. Invocation (5)
is ours, but strictly as "call a registered callable and normalise the outcome" —
not as a scheduler, queue, or retry engine.

---

## 2. Constraints we are designing under

These come from the charter and from Phase 0's enforcement layer, not from any
surveyed project. They are the filter every "pattern worth adopting" must pass.

| Constraint | Source | Consequence for the design |
|---|---|---|
| **Zero runtime dependencies** | ADR-0003 | No Pydantic, no `jsonschema`. Schema validation must be stdlib-only, or we accept a dependency via ADR — a high bar. |
| **Model-agnostic** | charter §31 | The registry must not know what a "tool call" looks like on any provider's wire. Provider wire formats are an *adapter* concern. |
| **Explicitly inspectable** | charter §16 | A registered tool must be introspectable without invoking it. No magic registration side effects. |
| **Component independence** | charter §31 | Usable standalone, with no agent loop and no model. If it only works inside a bundle, the boundary is wrong. |
| **Python, type-hinted, mypy strict** | charter §13 | Public API must be fully annotated; no `Any` in signatures without justification. |
| **Failure is a first-class outcome** | charter §18 | Validation failure and execution failure are *distinct, typed* results — not one generic error. |
| **Security at the boundary** | charter §20 | Arguments are untrusted input from a model. Validate before side effects. Never `eval`/`exec`. |

Two constraints deserve emphasis because they eliminate the obvious answer:

- **Zero dependencies kills the "just use Pydantic" shortcut.** Pydantic gives
  schema validation for free and is what LangChain (and much of the ecosystem)
  builds on. Taking it would be *easy* and is *permitted* — but it is a runtime
  dependency for the foundational primitive everything else consumes, and it
  would make the registry the most-coupled component in the repository. **DESIGN
  OPINION:** Phase 1 should implement a deliberately small validator over the
  JSON Schema subset we actually support, and record the supported subset
  explicitly as a documented limitation. Revisit if evidence shows the subset is
  too small to be useful.

- **Model-agnostic kills "the registry emits provider tool-call JSON."** That is
  genuinely useful — and belongs one layer up, in the adapter that translates
  between our registry and a provider's wire format.

---

## 3. Survey findings

Per-project detail lives in [`docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md),
which carries the charter §11 schema for each studied project.

### 3.1 OpenAI function calling

**FACT — the wire format is not one format, even within one vendor.** In the
Responses API a function definition is flat (`type`, `name`, `description`,
`parameters`, `strict`); in Chat Completions the same fields are nested under a
`function` key. Call identity differs too: `call_id` (Responses) vs `id` (Chat
Completions). *Source: OpenAI function-calling guide; `tool_call_id` confirmed
independently in `openai/openai-openapi` `openapi.yaml`.*

**INFERENCE — the single most important finding for our design:** if a vendor's
own two surfaces disagree on the encoding, then *no wire shape can be the
abstraction*. The logical tool record must be our own type; every wire shape is
an adapter.

**FACT — the schema dialect is a restricted subset, and only under `strict: true`.**
Verified directly against the official Structured Outputs guide, which states:
*"Composition: `allOf`, `not`, `dependentRequired`, `dependentSchemas`, `if`,
`then`, `else`"* are unsupported; `anyOf` is supported; and *"If you turn on
Structured Outputs by supplying `strict: true` and call the API with an
unsupported JSON Schema, you will receive an error."* Additionally: the root must
be an object, every property must be listed in `required`, and every object needs
`additionalProperties: false` (optionality is emulated with
`"type": ["string", "null"]`).

**FACT — requested strictness ≠ effective strictness.** Omitting `strict` lets the
API normalize the schema "when possible" and otherwise fall back to best-effort,
reporting `strict: false` back in the response. Strictness must be read back
per-response, not assumed from the request.

**FACT — the caller validates, and there is no protocol-level error channel.**
OpenAI's own API reference attaches to the `arguments` field: *"the model does not
always generate valid JSON, and may hallucinate parameters not defined by your
function schema. Validate the arguments in your code."* `arguments` arrives as a
JSON-**encoded string**, so a parse failure is entirely a caller-side concern with
no model-facing signal.

**FACT — unknown tool names are a real, documented failure mode.** Models have
been observed emitting calls to tools that were never registered (e.g.
`multi_tool_use.parallel`). Names arriving from a model must be treated as
untrusted input and resolved against the registry, failing closed.

**OBSERVATION — errors ride inside the result.** Tool results return as
`{role:"tool", tool_call_id, content}` (Chat) or
`{type:"function_call_output", call_id, output}` (Responses), where the content is
opaque and its format is explicitly up to the caller. There is no error envelope
in the protocol.

**Worth adopting:** a stable logical core
(`name` + `description` + input schema + call + correlation id + opaque string
result); caller-side validation, unconditionally; correlation id to pair results
with requests under parallel calls; separating *visibility* (offered this turn)
from *existence*; an opaque result envelope that can carry errors in-band.
OpenAI's own `tool_search`/`defer_loading` exist because upfront injection of many
tools costs context and accuracy — the docs advise offering fewer than ~20 tools.

**Worth avoiding:** canonicalizing on "JSON Schema" without acknowledging the
strict subset; trusting model-emitted names; assuming `strict` was honoured;
depending on deprecated compatibility fields.

### 3.2 LangChain tools

**FACT — there is no registry.** LangChain has no first-class registry service.
Registration is implicit: `ToolNode(tools=[...])` builds a plain
`self.tools_by_name` dict, recreated per node. No namespacing, no collision
policy, no versioning. *Verified against `langgraph/prebuilt/tool_node.py`.*

**FACT — validation is Pydantic-only.** `args_schema` must be a
`pydantic.BaseModel` subclass or a raw JSON-schema dict; anything else raises
`TypeError` at construction. Schema inference runs through the *deprecated*
`pydantic.validate_arguments` decorator, with a source comment saying the code
"should be re-written."

**INFERENCE:** Pydantic is the reason the ecosystem's tool abstraction is heavy.
It is the easy path and it is the path that makes a "tool" inseparable from a
validation framework. Our zero-dependency constraint rules it out — and that is
a feature, not a sacrifice.

**FACT — injection, and why it is a security boundary.** LangChain's
`InjectedToolArg` / `InjectedToolCallId` / `ToolRuntime` arguments are excluded
from the schema shown to the model but present during validation, then added
afterwards. Critically, `ToolNode` **strips any caller-supplied values for
injected keys before adding trusted ones**, with this comment in the source:

> `This prevents an LLM from forging hidden InjectedToolArg fields via ToolCall.args.`

**Verified verbatim in `tool_node.py`.** This is the sharpest idea in the survey
and we should adopt the *concept*: a declared argument namespace that the model
can never populate. The mechanism (an `Annotated[..., Marker]` convention) is
magic we can avoid — an explicit flag on the argument declaration is clearer.

**FACT — two error channels, deliberately split.** `handle_validation_error`
(model supplied bad arguments) is separate from `handle_tool_error` (the tool
raised). The default LangGraph handler returns the message for
`ToolInvocationError` — because the model *can* fix bad arguments — and
**re-raises everything else** (`_default_handle_tool_errors`; verified in source).

**DESIGN OPINION — adopt this directly.** Only surface to the model the errors it
can actually act on. Feeding an internal exception back into a prompt leaks
implementation detail and invites the model to fabricate a "fix" for a problem it
cannot see.

**FACT — historical churn is severe.** The import surface moved
`langchain.tools` → `langchain-core` → `langchain-classic` across 0.1→0.2→0.3→v1,
and docstring-parsing defaults are inconsistent between
`StructuredTool.from_function` and the `@tool` decorator. A design that is stable
across such churn must expose its own types, not re-export a dependency's.

**Worth adopting:** the injected-argument *concept* and its forging defence;
the two-channel error split with "only model-fixable errors go back"; explicit
argument declarations.
**Worth avoiding:** Pydantic coupling; docstring-parsing magic with inconsistent
defaults; a tool abstraction welded to a graph runtime; re-exporting a
dependency's types as your public API.

### 3.3 Model Context Protocol (MCP)

*(populated from survey — §4)*

### 3.4 Microsoft Semantic Kernel

*(populated from survey — §4)*

---

## 4. Synthesis

*(populated after surveys complete)*

---

## 5. Open questions carried to the decision

*(populated after surveys complete)*