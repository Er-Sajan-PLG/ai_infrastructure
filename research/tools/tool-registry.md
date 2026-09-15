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

**FACT — the error distinction is the single most valuable thing in any survey.**
MCP splits failures into two channels, and the spec says why *(verified verbatim
in `schema/2025-06-18/schema.ts`)*:

> Any errors that originate from the tool SHOULD be reported inside the result
> object, with `isError` set to true, **_not_ as an MCP protocol-level error
> response. Otherwise, the LLM would not be able to see that an error occurred and
> self-correct.**
> However, any errors in _finding_ the tool, an error indicating that the server
> does not support tool calls, or any other exceptional conditions, should be
> reported as an MCP error response.

**DESIGN OPINION — this is exactly the taxonomy our registry needs**, and it is
the same split LangChain arrived at independently (validation vs execution). Two
surveys converging on the same distinction from different starting points is
strong evidence it is load-bearing, not incidental:

| Failure | Channel | Reaches the model? |
|---|---|---|
| Tool not found / unknown name | Protocol error | No — a caller bug; fail closed |
| Arguments malformed | Validation error | **Yes** — the model can fix it |
| Tool executed but failed | In-band result, `isError: true` | **Yes** — the model can react |
| Internal exception in our code | Raised, out of band | No — never leak internals |

**FACT — `tools/call` returns both unstructured and structured content.**
`CallToolResult` carries `content: ContentBlock[]` (unstructured) and an optional
`structuredContent` object, plus `isError`.

**FACT — tool annotations are explicitly untrusted.** The schema states all
properties of `ToolAnnotations` are *"hints"*, not guaranteed faithful, and
clients *"should never make tool use decisions based on ToolAnnotations received
from untrusted servers."*

**INFERENCE — this matters for our registry:** annotations (like `readOnlyHint`)
are advisory metadata for *display and policy*, never a security control. Our
own registry should mark fields as trusted-by-construction vs advisory with the
same clarity.

**FACT — discovery is dynamic.** `tools/list` and the
`notifications/tools/list_changed` notification mean the tool set can change at
runtime with no prior subscription. A registry designed only for static
registration would be wrong for MCP.

**FACT — MCP has six revision dirs and the handshake is already gone.**
`2024-11-05`, `2025-03-26`, `2025-06-18`, `2025-11-25`, `2026-07-28`, `draft`.
*Verified via the GitHub contents API.* `2026-07-28` removes the
`initialize`/`notifications/initialized` handshake entirely (protocol version and
capabilities move per-request into `_meta`), adds a required `server/discover`,
and drops protocol sessions. *Verified: `InitializeRequest` occurs twice in the
`2025-06-18` schema and **zero times** in `2026-07-28`, which introduces
`server/discover` and a required `resultType`.*

> **Correction to our own process.** This survey was briefed with the assumption
> that `2025-06-18` was the current revision. **That brief was wrong**, and the
> survey caught it by checking the repository rather than trusting the premise.
> Recorded here because it is evidence for a design principle, not just a fix:
> *revision state is a fact to verify, never an assumption to inherit* — the same
> rule the charter applies to lifecycle status (§4).

**INFERENCE — a direct consequence for our design:** do not build the registry
around handshake-scoped capability negotiation. It is already removed upstream.
Capability discovery must be modelled as a *per-request* concern.

**FACT — `inputSchema` strictness is under-specified, and that caused real
breakage.** In `2025-06-18` the normative type permits only
`{type: "object"; properties?; required?}`; `$ref`, `$defs`, `oneOf`,
`additionalProperties`, even `$schema` are not named, while the prose says "JSON
Schema." Documented cross-SDK consequences followed: `$ref` made tools invisible
or unusable to models, the TypeScript SDK added `dereferenceLocalRefs`, and
multiple SDK issues were filed. Later revisions default to dialect 2020-12 and
require network-URI `$ref` to **not** be auto-dereferenced.

**DESIGN OPINION — the sharpest lesson in this whole survey, and it generalises:**
*say which dialect you mean, and make schemas self-contained.* "JSON Schema" as a
bare string is not a specification; it is an ambiguity that will be resolved
differently by each implementer. Our registry must **always emit an explicit
`$schema`** and must never depend on a default.

**FACT — a fresh failure mode worth taking seriously: an untrusted schema is an
attack surface.** An `inputSchema` containing an external `$ref` invites SSRF, and
pathological composition invites CPU exhaustion at validation time. A registry
that accepts remote schemas is accepting executable-shaped input.

**INFERENCE — this becomes a security requirement on our validator**, not a
footnote: reject external and network `$ref` outright; bound validation depth and
composition size.

**FACT — `list_changed` carries no payload and needs no subscription.** It is an
*invalidation hint*, not a diff. In-flight calls must not be cancelled on receipt.

**FACT — MCP's tool identity is connection-scoped and dies with the process.**
There is no stable, dereferenceable tool identifier that outlives a connection.

**INFERENCE — this is precisely the gap our capability exists to fill.** MCP
solves *remote tool invocation* well and *stable tool identity* not at all. A
vendor-neutral registry must provide identifiers that survive restart and a
manifest that outlives a session. That is a real, externally-validated
justification for this capability existing.

**Worth adopting:** the discovery/invocation split; `inputSchema` rooted at
`type: "object"`; **always emit an explicit `$schema`**; normalise schemas to be
self-contained (inline local `$ref`, never dereference network `$ref`); the
two-tier error taxonomy keyed on model-visibility; `isError` as an in-band flag;
annotations as explicitly-untrusted hints.
**Worth avoiding:** repeating the dialect ambiguity; object-only
`structuredContent` (a constraint already removed upstream); duplicated
structured+text payload shims; accepting unvalidated opaque schemas; coupling to
the handshake lifecycle; server-centric identity.

### 3.4 Microsoft Semantic Kernel

Surveyed at **1.44.1**; source read directly. *Claims verified against
`python/semantic_kernel/functions/kernel_function.py` and related modules.*

**FACT — registration is decorator-gated, not protocol-based.**
`KernelFunctionFromMethod.__init__` raises `FunctionInitializationError` unless
the function carries `__kernel_function__`. Metadata is smuggled through
`__kernel_function_*__` dunder attributes set as a decorator side effect.

**INFERENCE:** this makes "is this a tool?" an implicit question answered by
attribute sniffing. An explicit protocol — a declared descriptor — is testable
and introspectable; dunder smuggling is neither.

**FACT — schema inference is an eager side effect.** `KernelParameterMetadata`
computes `schema_data` inside a Pydantic `model_validator(mode="before")`, i.e.
as a construction side effect, whereas the C# original caches it lazily.

**FACT — the namespace is flattened into the model-visible name.** The tool name
is `Plugin-function` (`fully_qualified_name`), re-parsed on the way back.

**DESIGN OPINION:** encoding a namespace into a string that is then parsed back is
a silent mismatch source. Our registry should key tools by an explicit
identifier and never recover structure by parsing a name.

**FACT — the tool type imports OpenTelemetry unconditionally and instruments
every invocation.** *Verified directly: `kernel_function.py` line 12–13 imports
`opentelemetry` `metrics`/`trace` and `semconv`; the type declares
`invocation_duration_histogram` and `streaming_duration_histogram` fields created
per function.*

**DESIGN OPINION — this is decisive for us.** Observability is a legitimate
concern, but wiring it into the *core tool type* means no one can consume a tool
without the telemetry stack. Our chunked architecture (charter §17) should emit
plain data and let `execution-trace-recorder` decide what to do with it.

**FACT — dependency weight.** The core package's declared dependencies include
`azure-ai-projects`, `azure-ai-agents`, `azure-identity`, `openai`, `numpy`,
`openapi_core`, `aiortc`, `websockets`, `pydantic`, and `opentelemetry-api`.

**FACT — fail-open defaults.** With no `function_choice_behavior`, the code logs
at debug that *"No allowlist validation will be performed"*. An empty include
list is a documented no-op.

**DESIGN OPINION — adopt the opposite.** Absent an explicit policy, a registry
should advertise *nothing* rather than everything. Fail-closed is the only
defensible default when the thing being advertised can cause side effects.

**FACT — failures are rewritten into prompt text.** On an invalid tool name or
missing argument, SK synthesizes a tool result into chat history so the model can
self-correct rather than raising.

**INFERENCE:** good for runtime reliability, bad for deterministic testing — a
function that never raises is hard to assert on. We should make this an explicit
*option* on the caller's side, not default registry behaviour.

**FACT — filters are onion middleware.** `(context, next)` chains over
invocation, assembled per filter type, enabling logging, approval, retry,
caching, and PII redaction *without touching tool code*. Two sharp edges: not
calling `next` silently cancels the operation, and filters attach to the
`Kernel` instance, so they vanish when a chat service is used without passing one.

**DESIGN OPINION — adopt the pattern, not the placement.** Middleware over
invocation is genuinely good design. But attaching policy to a god-object
container means the policy silently disappears in a valid usage path. If we adopt
middleware, it must live on a standalone object whose absence is a *type error*,
not a silent bypass.

**Worth adopting:** middleware over invocation; metadata separated from the
callable; a pure `metadata → vendor tool JSON` rendering adapter; advertising as
an explicit policy; the ≤10–20 advertised-tools constraint.
**Worth avoiding:** a god-object container; dunder-gated registration instead of
an explicit protocol; namespace flattened into a model-facing name; schema
inference inside a validator side effect; unconditional telemetry imports in the
core tool type; exception masking (`KernelInvokeException` hides the original
cause); fail-open allowlist defaults.

---

## 4. Synthesis

### 4.1 Independent convergence — the strongest signal we have

Four projects, built by different organisations for different purposes, arrived
at the same conclusions in several places. Where they agree, we should not
deliberate; where they disagree, that is where design judgement is needed.

| Finding | OpenAI | LangChain | MCP | Semantic Kernel |
|---|---|---|---|---|
| **Errors split by whether the model can fix them** | in-band only | validation vs execution | `isError` vs protocol error | synthesized into prompt |
| **Caller validates; the model is untrusted** | explicit requirement | Pydantic at the boundary | schema is advisory | Pydantic + allowlist |
| **Correlation id pairs request to result** | `call_id`/`id` | `tool_call_id` | JSON-RPC `id` | `function_count` |
| **Tool set is dynamic, and visibility ≠ existence** | `tool_search`/`defer_loading` | graph-scoped | `tools/list` + `list_changed` | filters/allowlist |
| **A namespace/identity concept is needed** | namespace field | absent | connection-scoped | `Plugin-function` |
| **The registry primitive as such** | absent | **absent** | server-scoped | god object |

**INFERENCE — what the table says.** All four solve *invocation*. **None of them
ships a genuine tool registry**: OpenAI has no registry, LangChain's is an
implicit per-node dict, MCP's identity dies with the connection, and Semantic
Kernel's is a god object with a fail-open default. The capability we are scoping
is not a re-implementation of something that exists — it addresses a gap all four
leave open. That is a materially stronger position than "we wrote our own
version of X."

**The convergence on error handling is decisive.** OpenAI, LangChain, and MCP
independently concluded that failures must be divided by *whether the model can
act on them*, and MCP states the rationale outright: report tool errors in-band
*"otherwise the LLM would not be able to see that an error occurred and
self-correct."* Three independent arrivals at the same rule is the strongest
evidence in this survey. **We treat this as a requirement, not a preference.**

### 4.2 Where the four disagree — and what we take

| Question | Positions | Our choice | Why |
|---|---|---|---|
| **Argument validation** | Pydantic (LC, SK) vs JSON Schema (OpenAI, MCP) | **JSON Schema, stdlib-only** | Both Pydantic users are the heaviest and most-criticised. Zero-dependency constraint (ADR-0003) rules it out anyway. |
| **Schema dialect** | restricted subset (OpenAI) vs underspecified (MCP 2025-06-18) vs unspecified | **Explicit `$schema`, documented subset** | Ambiguity already broke real SDKs. Say what we support. |
| **Default advertising** | all (SK) vs caller-supplied (LC) vs server list (MCP) | **Fail closed — nothing** | SK's fail-open default is documented and wrong for side-effecting tools. |
| **Injected/trusted args** | forged-defence (LC) vs absent (others) | **Adopt the concept, explicit syntax** | Genuine security boundary. Reject `Annotated[..., Marker]` magic. |
| **Middleware** | filters (SK) only | **Adopt, on a standalone object** | Valuable; must not vanish silently as SK's do. |
| **Telemetry** | coupled (SK) vs absent | **Emit plain data** | Charter §17 chunking: observability is a separate capability. |
| **Namespace** | `Plugin-function` string (SK) vs absent | **Explicit identifier** | Never recover structure by parsing a name. |

### 4.3 The design, in one paragraph

A `tool-registry` is an **explicit registration operation over a JSON-Schema-native
descriptor**, with stable identifiers that outlive any connection, two distinct
schema views (model-facing vs validation-facing), and a failure taxonomy divided
by model-actionability. It performs **declaration and validation**; it does not
select tools for a model, does not speak any provider's wire format, and does not
own telemetry.

### 4.4 Non-negotiable requirements distilled from the surveys

1. **Stable, explicit tool identifiers.** Not names parsed structurally, not connection-scoped. *(gap in all four)*
2. **Two schema views.** Model-facing vs validation-facing; injected arguments never model-visible. *(LangChain)*
3. **Unconditional validation before side effects.** Arguments from a model are untrusted input. *(all four)*
4. **Fail closed.** Unknown tool name → error. No policy → advertise nothing. *(against SK)*
5. **Failure taxonomy by model-actionability**, with three outcomes: not-found (never reaches model), invalid-arguments (reaches model), execution-failed (reaches model, in-band). Plus internal exceptions that never leak. *(convergence)*
6. **Explicit `$schema`; self-contained schemas.** Never dereference network `$ref`. *(MCP's hard-won lesson)*
7. **Injected/trusted arguments stripped from caller input.** *(LangChain's forgery defence)*
8. **No runtime dependencies.** Hand-written validator over a documented subset. *(ADR-0003)*
9. **Introspectable without invocation.** *(charter §16)*
10. **Usable standalone** — no agent loop, no model, no network. *(charter §31)*

### 4.5 Consequential limitation, stated upfront

**Requirement 8 has a real cost, and it should be recorded before the decision,
not discovered during implementation.** Hand-writing a JSON Schema validator
means:

- We support a **documented subset**, not all of JSON Schema. `$ref`, `oneOf`,
  `patternProperties`, and conditional composition will not be supported initially.
- We must **reject what we do not understand loudly** rather than silently
  passing it. A validator that ignores unknown keywords is worse than one that
  refuses them — it gives false confidence.
- Validation is a **security boundary**, so the implementation must be
  adversarial-input-safe: bounded recursion depth, bounded composition size, no
  `eval`, no unbounded expansion.

**DESIGN OPINION:** this is the correct trade. A validated subset, explicitly
documented and loudly enforced, is safer than a full implementation of a
specification whose complexity is itself an attack surface. But if evidence later
shows the subset blocks real use, the right response is an ADR adding a
dependency — not a quiet widening of the subset.

## 5. Open questions carried to the decision

1. **IMPLEMENT, ADAPT, or COMPATIBILITY?** Nothing to adopt wholesale; the
   sub-patterns are conceptual. Leaning **IMPLEMENT** (charter §8).
2. **How large a schema subset does Phase 1 need?** Proposal: `type`, `properties`,
   `required`, `enum`, `items`, `description` — plus explicit rejection of
   everything else. `additionalProperties` is a judgement call.
3. **Do we expose injection as a declared flag on parameters, or a separate
   registry-time argument list?** (Decision detail — belongs in the specification.)
4. **Is a `Tool` immutable?** Immutability makes registration idempotent and
   thread-safe; it also means no post-hoc mutation.
5. **Does the registry support late-registration at all in Phase 1?** Static
   registration is far simpler; MCP-style dynamic sets are Phase 2+.
6. **What does "stable identifier" mean concretely** — a string, or a namespaced
   compound type? MCP's failure argues for something with structure, not `a-b`.