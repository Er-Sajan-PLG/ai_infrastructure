# Specification: `tool-registry`

| Field | Value |
|---|---|
| **Capability id** | `tool-registry` |
| **Name** | Tool Registry & Function Calling Primitive |
| **Category** | tools |
| **Lifecycle status** | `DESIGNED` |
| **Deciding ADR** | [ADR-0006](../docs/decisions/0006-tool-registry.md) — decision: **IMPLEMENT** |
| **Research record** | [`research/tools/tool-registry.md`](../research/tools/tool-registry.md) |
| **Dependencies** | none (charter §24.1 — dependency-first) |
| **Standards** | JSON Schema 2020-12, **documented subset** (§5) |
| **Runtime dependencies** | **none** (ADR-0003, ADR-0006) |

Claims are labelled per charter §6: **FACT · OBSERVATION · INFERENCE · DESIGN OPINION**.

---

## 1. Problem and who needs it

> Provide a uniform, inspectable, validated boundary between **model intent** and **executable behaviour**.

**Who needs it** (charter §7 — real demand, not hypothetical):

| Consumer | Needs from this capability |
|---|---|
| `react-agent-loop` | A validated way to resolve a model-emitted call and get a structured result |
| `mcp-client` | A local registry to project remote tools into |
| Provider adapters | Our own logical tool record to render into a vendor wire format |
| A harness author | Registration, validation and dispatch with no agent and no model |

**INFERENCE — the case for this existing at all:** research found that none of
OpenAI, LangChain, MCP, or Semantic Kernel ships a genuine registry (ADR-0006).
This fills a gap rather than re-implementing something.

---

## 2. Scope

### In scope — declaration and validation

1. **Registration** of tools with stable, explicit identifiers.
2. **Descriptors** — name, description, input schema, and an explicit trust boundary for arguments the model may never supply.
3. **Introspection** — enumerate and describe tools without invoking them.
4. **Validation** of arguments against a declared schema, before any side effect.
5. **Invocation** of a registered callable, with the outcome normalised into a typed result.

### Explicitly out of scope

| Out of scope | Belongs to |
|---|---|
| Choosing which tools to advertise to a model | The caller / agent loop |
| Speaking any provider's wire format | A provider adapter |
| Telemetry, tracing, spans | `execution-trace-recorder` |
| Remote tool discovery, transports | `mcp-client` |
| Scheduling, queues, retries, concurrency | Nowhere in Phase 1 |
| Sandboxing or process isolation of tool bodies | Deferred — a trust boundary we do **not** claim to provide (§8) |
| Sandboxing, permissions enforcement | Deferred |
| Async execution | **Deferred to a later phase** (see §9, D-6) |
| Dynamic/late registration | **Deferred** — static registration in Phase 1 (see §9, D-5) |

---

## 3. Design overview

```text
                    ┌──────────────────────────────────────────┐
                    │              ToolRegistry                │
                    │  register(tool) -> None                  │
                    │  get(tool_id) -> Tool | None             │
                    │  ids() -> tuple[ToolId, ...]             │
                    │  describe(tool_id) -> ToolDescriptor     │
                    └───────────────┬──────────────────────────┘
                                    │ holds
                                    ▼
                    ┌──────────────────────────────────────────┐
                    │                  Tool                    │
                    │  id: ToolId                              │
                    │  description: str                        │
                    │  input_schema: JsonSchema (model-facing) │
                    │  validation_schema: JsonSchema           │
                    │    (= input_schema - injected + injected)│
                    │  callable: Callable[[Mapping], object]   │
                    └───────────────┬──────────────────────────┘
                                    │ validated call
                                    ▼
     arguments ──► validate() ──► ToolResult
     (untrusted)   (§5, §6)        ├─ Ok(value)
                                   └─ Err(ToolFailure)
                                        ├─ NotFound        (never reaches a model)
                                        ├─ InvalidArguments(reaches a model)
                                        └─ ExecutionFailed (reaches a model, in-band)
```

### The five separable concerns

Research identified declaration, selection, binding, validation, and invocation as
distinct. **This capability owns declaration and validation**; binding is a thin
adapter over it; selection belongs to the caller.

**DESIGN OPINION:** keeping these separate is the whole point. A registry that
also selects cannot be tested without a model.

---

## 4. Identifiers — D-1: stable and explicit

**Requirement:** a tool's identity must outlive any process, connection, or session,
and must never be derived by parsing a string.

```python
@dataclass(frozen=True, slots=True)
class ToolId:
    namespace: str   # e.g. "core", "mcp.github"
    name: str        # e.g. "get_weather"
```

**Why not a bare string** *(evidence: ADR-0006)*:

| Project | Identity model | Consequence |
|---|---|---|
| Semantic Kernel | `"Plugin-function"` — namespace flattened into a name | Structure recovered by parsing; silent mismatch source |
| MCP | Scoped to a live connection/process | **Identity dies on restart** |
| LangChain | Name-keyed dict rebuilt per node | No namespace, no collision policy |

**Invariants:**
- `namespace` and `name` are non-empty, and match `^[a-z0-9][a-z0-9._-]*$`.
- `ToolId` is frozen and hashable — usable as a dict key.
- Equality is structural. `ToolId("core","x") != ToolId("mcp","x")`.
- `str(tool_id)` renders `namespace:name` **for display only**. Reconstructing a `ToolId` by splitting that string is not part of the API and must not be relied upon.

**DESIGN OPINION:** the display form exists for humans and error messages. The
*structured* object is the interface. This is the deliberate opposite of
Semantic Kernel's name-encoded namespace.

---

## 5. The supported JSON Schema subset — D-2

This is the most consequential design decision, and its cost is stated in ADR-0006.

**We support a documented subset and reject everything else loudly.**

### Supported keywords

| Keyword | Applies to | Notes |
|---|---|---|
| `type` | any | `object`, `string`, `integer`, `number`, `boolean`, `array`, `null` |
| `properties` | object | Required when `type` is `object` |
| `required` | object | List of property names; mutually consistent with `properties` |
| `additionalProperties` | object | Boolean only. Default **`false`** — see below |
| `items` | array | A single schema (not a tuple form) |
| `enum` | any | Non-empty list of literals |
| `description` | any | Documentation; never affects validation |

### `$schema` — always emitted, never assumed

Every emitted schema carries `"$schema": "https://json-schema.org/draft/2020-12/schema"`.

**FACT (ADR-0006):** MCP's `2025-06-18` `inputSchema` permitted only
`type`/`properties`/`required` while its prose said "JSON Schema", and the
ambiguity caused documented multi-year cross-SDK breakage. **The lesson: a bare
"JSON Schema" string is not a specification — it is an ambiguity that each
implementer resolves differently.**

### Explicitly unsupported in Phase 1

`$ref`, `$defs`, `oneOf`, `anyOf`, `allOf`, `not`, `patternProperties`,
`if`/`then`/`else`, `dependentRequired`, `dependentSchemas`, `prefixItems`,
`pattern`, `format`, `minLength`/`maxLength`, `minimum`/`maximum`, `multipleOf`,
`minItems`/`maxItems`, `minProperties`/`maxProperties`, `const`, `default`.

### The rejection rule

**Unknown or unsupported keywords are rejected at registration with an error
naming the keyword. They are never silently ignored.**

**DESIGN OPINION — this is a security property, not a style preference.** A
validator that ignores what it does not understand returns "valid" for input it
never checked, converting an unverified boundary into an apparently-verified one.
Silent permissiveness is worse than a loud failure.

### Why `additionalProperties` defaults to `false`

Research found that model-supplied arguments routinely include fields the schema
never declared (OpenAI's own documentation warns the model "may hallucinate
parameters not defined by your function schema"). Defaulting to `true` would pass
those through to a callable. **DESIGN OPINION:** strict by default; a caller must
opt in explicitly to accept undeclared arguments.

### Consequence of the subset — stated plainly

A caller with a schema using `$ref`, `oneOf`, or `pattern` **cannot register it**.
That is a real limitation on a foundational component. ADR-0006 fixes the remedy:
an ADR adding a dependency, **never** a quiet widening of the subset.

---

## 6. Two schema views and the injection boundary — D-3

**The rule:** the arguments a model may supply and the arguments a tool receives
are **different sets**, and the difference is a security boundary.

```python
@dataclass(frozen=True, slots=True)
class Tool:
    id: ToolId
    description: str
    input_schema: Mapping[str, object]        # model-facing: injected params removed
    validation_schema: Mapping[str, object]   # full: injected params included
    injected: frozenset[str]                  # names the model may NEVER supply
    callable: Callable[..., object]
```

**FACT — the risk this closes** *(verified verbatim in `tool_node.py`)*:

> `Strip any caller-supplied values for injected args, then add back only trusted
> values. This prevents an LLM from forging hidden InjectedToolArg fields via
> ToolCall.args.`

**Why an explicit `injected` set, not annotation magic.** LangChain marks these
with `Annotated[..., InjectedToolArg]`, and its own source carries evidence of the
cost — reserved names fail asymmetrically, with some raising and others silently
dropped from the schema (research record §3.2). **DESIGN OPINION:** an explicit
`frozenset[str]` is introspectable, testable, and cannot fail silently.

**Invariants:**
- Every name in `injected` **must** appear in `validation_schema.properties`, or registration fails.
- No name in `injected` may appear in `input_schema.properties` — the model-facing view can never reveal them.
- `input_schema` is always `validation_schema` minus the injected properties, and removing a name from `required` too.
- Removing a property is an error if the result would make `required` reference a missing property.

**Registration-time forging check (test requirement):** a call supplying a value
for an injected name must have that value **discarded and replaced** with the
trusted one. Supplying it is not an error — it simply has no effect. The
implementation must never pass a caller-supplied value into an injected slot.

---

## 7. Failure taxonomy — D-4

**The requirement, distilled from three-way convergence** (ADR-0006): failures are
divided by **whether the model can act on them**, not by severity.

**FACT — MCP states the rationale normatively:**

> Any errors that originate from the tool SHOULD be reported inside the result
> object, with `isError` set to true, **_not_ as an MCP protocol-level error
> response. Otherwise, the LLM would not be able to see that an error occurred
> and self-correct._**

```python
class FailureKind(StrEnum):
    NOT_FOUND = "not_found"                 # unknown tool id — a caller bug
    INVALID_ARGUMENTS = "invalid_arguments" # model-fixable
    EXECUTION_FAILED = "execution_failed"   # tool ran and failed — model-visible
```

| Failure | Cause | `model_visible` | Rationale |
|---|---|---|---|
| `NOT_FOUND` | Unknown tool id | **`False`** | A caller bug or a hallucinated name. The model cannot fix a registry it cannot see. |
| `INVALID_ARGUMENTS` | Schema violation | **`True`** | The model produced the arguments and *can* correct them. |
| `EXECUTION_FAILED` | Tool body raised | **`True`** | The model should know the action failed, so it does not assume success. |

**The internal-exception rule.** An unexpected exception inside *our own* code
(a bug in validation, registry corruption) is **not** an `EXECUTION_FAILED`. It
raises out of the API. It must never be stringified into a model-visible message.

**FACT — the counter-example we are avoiding.** Semantic Kernel wraps every
invocation failure in `KernelInvokeException`, masking the original cause. **DESIGN
OPINION:** we preserve the original exception as `__cause__` and never mask it.

### Error messages must be safe to show a model

A `ValidationError` names the field and the expectation. It **must not** echo
internal paths, stack traces, or environment detail.

**DESIGN OPINION on the model-visibility flag:** the registry *records* whether a
failure is model-visible; it does not *send* anything. Deciding what goes into a
prompt remains the caller's job (§2). The flag encodes the policy; the caller
applies it.

---

## 8. Security and trust boundaries

**We state what we do NOT protect against, because implied protection is worse
than none** (the same discipline as `SECURITY.md`).

### We DO protect against

| Threat | Defence |
|---|---|
| Model forging privileged arguments | Injected args stripped from caller input (§6) |
| Unvalidated input reaching a side effect | Validation is mandatory and unconditional |
| Malformed/hostile schema causing resource exhaustion | Bounded recursion depth and schema size (§8.1) |
| External `$ref` SSRF | `$ref` unsupported, so unreachable — rejected loudly |
| Silent permissiveness | Unknown keywords rejected, never ignored (§5) |
| Error messages leaking internals | Sanitised, and internal exceptions never converted to model-visible failures (§7) |
| Confused-deputy dispatch | Unknown tool id fails closed; never fuzzy-matched or defaulted |

### We do NOT protect against

- **A malicious tool body.** A registered callable runs with full process privilege. This capability is a registry, **not a sandbox**, and does not claim to be one.
- **Argument values being semantically appropriate.** A schema can require `path: string`; it cannot require that the path is not `/etc/shadow`. Semantic validation is the tool body's responsibility.
- **Prompt injection.** Out of scope entirely.
- **Resource limits on tool execution** — no timeouts, no memory caps in Phase 1.

**DESIGN OPINION:** this list is in the specification rather than only the docs
because the most dangerous failure mode is a consumer assuming a registry implies
isolation.

### 8.1 Bounds (adversarial input)

| Bound | Value | Rationale |
|---|---|---|
| Max schema nesting depth | 32 | Deep nesting is a stack-exhaustion vector |
| Max properties per object | 256 | Bounded work |
| Max enum values | 1024 | Bounded comparison |
| Max validation errors returned | 50 | Bounded output |

Exceeding a bound is a registration failure (for schemas) or a validation failure
(for arguments) — never a crash. **`RecursionError` must be impossible**: the
validator is depth-limited *before* recursing, not after.

---

## 9. Design decisions

| ID | Decision | Rationale |
|---|---|---|
| **D-1** | `ToolId` as a frozen `(namespace, name)` dataclass | Identity stable across connections; no parsing (§4) |
| **D-2** | Documented JSON Schema subset; reject the rest loudly | Zero dependencies; silent permissiveness is a security bug (§5) |
| **D-3** | Explicit `injected: frozenset[str]`, two schema views | Closes the forging vector; introspectable, no annotation magic (§6) |
| **D-4** | Failure taxonomy by model-actionability | Three-way convergence in research (§7) |
| **D-5** | **Static registration only** in Phase 1 | No consumer needs dynamic registration yet. Deferred rather than half-designed. |
| **D-6** | **Synchronous only** in Phase 1 | Async doubles the API surface. A model call is async, but tool bodies are usually not. Revisit with evidence. |
| **D-7** | `Tool` is immutable (frozen dataclass) | Registration is idempotent; no post-registration mutation races |
| **D-8** | Registry rejects duplicate ids | Silent last-write-wins hides a real bug |
| **D-9** | No I/O, no network, no imports outside stdlib | Charter §31 independence; testable with no doubles |

**D-5, D-6 recorded as deferred, not forgotten.** Per the scope-discipline rules
they are **LATER**, documented with a trigger for revisiting rather than built now.

---

## 10. Public interface (provisional)

Shapes, not implementation (charter §10 — no code in `specifications/`).

```text
ToolId(namespace, name)                      -> frozen, hashable
Tool(id, description, input_schema,
     validation_schema, injected, callable)  -> frozen
ToolRegistry()
    .register(tool)                          -> None      [raises DuplicateTool|InvalidSchema]
    .get(tool_id)                            -> Tool|None
    .ids()                                   -> sorted tuple[ToolId, ...]
    .describe(tool_id)                       -> ToolDescriptor  [stable ordering]
    .invoke(tool_id, arguments, *, trusted)  -> ToolResult
ToolResult
    .ok(value) / .fail(kind, message)
ValidationError / DuplicateToolError / InvalidSchemaError
```

**`ids()` returns a deterministic, sorted order.** *Evidence: MCP later revisions
added deterministic ordering for exactly this reason — an unstable enumeration
makes tests flaky and diffs noisy.*

**`invoke` takes `trusted` separately from `arguments`.** This makes the trust
boundary visible in the signature: `arguments` is untrusted caller input,
`trusted` is supplied by the host. A reader cannot confuse them.

---

## 11. Testing strategy (charter §18)

**No model, no network, no filesystem, no doubles** — a direct benefit of the
boundary chosen (D-9).

Tests live in `catalog/tools/tool_registry/tests/` and are collected by pytest
(`testpaths` includes `catalog/` — ADR-0004).

### Failure paths are the majority

| Area | Must-test cases |
|---|---|
| **Identity** | Equality/`__hash__`; namespace collision distinctness; invalid chars; empty parts |
| **Registration** | Duplicate id; unsupported keyword rejected **by name**; unknown keyword; depth/size bounds exceeded; `injected` not in validation schema; injected leaking into `input_schema` |
| **Validation** | Missing required; wrong type; `enum` miss; `additionalProperties: false` rejects unknown; nested object/array; `null` handling; multiple errors capped at 50 |
| **Injection** | Caller-supplied injected value **discarded and replaced** (the forging test); absent trusted value; injected key absent from `input_schema` |
| **Invocation** | Success; unknown id → `NOT_FOUND` + `model_visible False`; tool raising → `EXECUTION_FAILED` + original preserved as `__cause__`; internal error propagates |
| **Bounds** | Deeply nested schema rejected without `RecursionError`; huge property count rejected; deep *argument* nesting |
| **Introspection** | `ids()` sorted and stable; `describe()` deterministic |
| **Purity** | Registry works with no model/network/filesystem; no stdlib-external imports |

**Adversarial input is a first-class case class**, because validation is a
security boundary (§8.1). Deep-nesting and oversized-schema tests are not edge
cases; they are the threat model.

### What "TESTED" requires

Charter §4: the `tests` path must exist and the suite must pass. A coverage
threshold is **not** set at this stage (ADR-0004) — a line-coverage bar rewards
hitting lines, not testing behaviour.

---

## 12. Benchmark plan

**Not applicable in Phase 1** (charter §19 requires measurement *where
meaningful*). No performance claim is made, and none is needed. The charter §24.4
rule applies: narrow the slice.

*Recorded for a future phase:* if a benchmark is added, the meaningful measures
are validation latency at schema depth, registration throughput, and memory per
registered tool — **not** invocation throughput, which is dominated by the tool
body.

---

## 13. Definition of done

Per the Phase 1 per-capability checklist (`docs/phases/phase-1-seed.md`):

- [ ] `catalog/tools/tool_registry/` implementation, type-hinted, mypy strict
- [ ] Tests covering every case in §11, failure paths included
- [ ] ≥1 runnable example in `examples/`
- [ ] `README.md` with the charter §13 sections
- [ ] `PROVENANCE.md` — **inspired-by, not derived-from**; all four studied projects are `code_reused: false`
- [ ] Taxonomy entry updated with real artifact paths
- [ ] `make check` and `make status` pass
- [ ] Known limitations documented (the subset, most importantly)

---

## 14. Open questions for implementation

Carried forward rather than guessed at now:

1. **Exact exception hierarchy** — one base `ToolRegistryError`, or independent types?
2. **`ToolDescriptor` shape** — a frozen dataclass mirroring `Tool` minus the callable, or a mapping?
3. **`trusted` typing** — `Mapping[str, object]` or per-tool typed? Untyped is simpler and honest.
4. **Does `describe()` omit the callable?** It must — descriptors cross a boundary that callables should not.
5. **Where does the schema-subset validator live** — `catalog/tools/tool_registry/schema.py` (internal) or a separate capability? **Recommendation: internal.** Extract later only if a second consumer appears (charter §3).