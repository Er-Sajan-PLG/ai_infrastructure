# Research Registry

The evolving map of the external AI-infrastructure ecosystem (charter §11, §15). One schema serves two views:

- **Research view** — every project worth knowing about, what it does, how it is built, what to adopt and avoid.
- **Attribution view** — the subset with legal weight: anything actually reused, adapted, or closely inspired by licensed code.

> **Inspired by / studied from `X`** ≠ **Derived from / contains reused code from `X`.**
> Conflating these is a licensing risk, not a documentation gap.

## Entry schema

```yaml
project:                    # name
relevant_categories:        # which §2 categories this informs
repository:                 # URL
authors:                    # organization / individuals
license:
version_studied:            # version or commit studied
capabilities:               # what it does
architecture:               # how it's built
strengths:
weaknesses:
patterns_worth_adopting:
patterns_worth_avoiding:
code_reused:                # true/false — see rules below
attribution_requirements:   # required if code_reused is true
our_implementation:         # path in catalog/, or ""
compatibility_status:
standards:
last_reviewed:              # YYYY-MM-DD
```

## Rules

1. **Every project that materially influences an implementation must be registered here** before the implementation is claimed at DESIGNED or later.
2. **`code_reused: true` requires human review** (charter §22). As of [ADR-0002](../decisions/0002-license-selection.md) (Apache-2.0) this is no longer prohibited, but an entry setting it **must** record `attribution_requirements`, and the required notice text must be added to [`../../NOTICE`](../../NOTICE) in the same change.
3. **Never remove copyright or license notices** from studied material.
4. Every entry states what was learned as **FACT / OBSERVATION / INFERENCE / DESIGN OPINION** where a claim is non-obvious (charter §6).
5. `last_reviewed` is updated whenever the project is re-studied, even if conclusions are unchanged (charter §23).
6. Study is not derivation. Registering a project records that it was *studied*; it does not imply code was reused. Set `code_reused` deliberately and honestly.

## Entries

Studied during session 6 for the `tool-registry` capability (charter §11).

---

### OpenAI function calling / tools

```yaml
project: OpenAI function calling / tools
relevant_categories: [tools]
repository: https://github.com/openai/openai-openapi
authors: OpenAI
license: proprietary API (spec repository: MIT)
version_studied: developers.openai.com docs as of 2026-09; openai-openapi openapi.yaml
capabilities: >
  Vendor-hosted tool-calling: declares tools with a JSON Schema, returns model-emitted
  calls, accepts results back as messages. Both a wire format and a de-facto industry
  convention for tool schema shape.
architecture: >
  Stateless HTTP API. Tools are declared per request in `tools`; the model emits
  `tool_calls` (Chat Completions) or function-call items (Responses). Two surfaces
  disagree on encoding: flat in Responses, nested under `function` in Chat Completions.
  Call identity is `call_id` vs `id`. No server-side execution, no registry, no error channel.
strengths:
  - Universal adoption; the de-facto interchange shape for tool schemas
  - strict:true gives schema-enforced argument generation
  - Correlation ids support parallel calls
  - Opaque result envelope keeps the protocol simple
weaknesses:
  - Restricted JSON Schema subset; unsupported keywords cause outright rejection
  - Requested strictness can silently downgrade (response must be read back)
  - No protocol-level error channel — errors ride inside result strings
  - No registry, no discovery, no capability negotiation
  - Wire format differs between the vendor's own two surfaces
patterns_worth_adopting:
  - Logical tool record kept separate from any wire encoding
  - Unconditional caller-side argument validation (the vendor explicitly requires it)
  - Correlation id pairing request to result, safe under parallelism
  - Opaque, in-band result envelope that can carry errors
  - Separating tool visibility (offered this turn) from tool existence
patterns_worth_avoiding:
  - Treating "JSON Schema" support as unbounded when it is a strict subset
  - Trusting model-emitted tool names — resolve against the registry, fail closed
  - Assuming the requested strictness was honoured
  - Depending on deprecated compatibility fields (`functions`/`function_call`)
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  Not a compatibility target — a wire format. Future per-provider adapters will translate
  between our registry and this shape. No code reused.
standards: ["JSON Schema", "OpenAI tool calling"]
last_reviewed: 2026-09-15
```

---

### LangChain / LangGraph

```yaml
project: LangChain / LangGraph
relevant_categories: [tools]
repository: https://github.com/langchain-ai/langchain
authors: LangChain, Inc.
license: MIT
version_studied: langchain-core 0.3/v1 line; langgraph prebuilt/tool_node.py (main, 2026-09)
capabilities: >
  Tool abstraction (`BaseTool`, `@tool`, `StructuredTool`), schema inference from Python
  types and docstrings, tool binding to models, and graph-based dispatch via `ToolNode`.
architecture: >
  `BaseTool` requires a Pydantic `args_schema`. Schema is derived from type hints and
  optionally the docstring. Dispatch is a plain name-keyed dict rebuilt per `ToolNode`;
  there is no registry service. Injected arguments are excluded from the model-facing
  schema and re-added after validation, with caller-supplied values stripped first.
strengths:
  - Injected-argument design, including an explicit defence against LLM forging
  - Two distinct error channels (validation vs execution) with sensible defaults
  - Rich ecosystem and model bindings
  - Docstring-driven schema inference is ergonomic for simple cases
weaknesses:
  - No actual registry — no namespacing, collision policy, or versioning
  - Hard Pydantic coupling; validation cannot be swapped
  - Schema inference depends on a deprecated Pydantic code path
  - Severe import-surface churn across 0.1 -> 0.2 -> 0.3 -> v1
  - Inconsistent defaults between `@tool` and `StructuredTool.from_function`
patterns_worth_adopting:
  - The injected-argument concept (declared args the model can never populate)
  - Stripping caller-supplied values for injected keys before adding trusted ones
  - Splitting validation errors (model-fixable, return to model) from execution errors
    (re-raise / handle out of band)
patterns_worth_avoiding:
  - Pydantic as a hard dependency of the tool primitive
  - Docstring parsing as a hidden schema source, with inconsistent defaults
  - A tool abstraction inseparable from a graph runtime
  - Re-exporting a dependency's types as one's own public API
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. The injected-argument idea is adopted as a CONCEPT, re-designed
  with an explicit declaration rather than an `Annotated[..., Marker]` convention. No code reused.
standards: ["JSON Schema", "Pydantic (studied, not adopted)"]
last_reviewed: 2026-09-15
```

> **Depth note.** LangGraph's `tool_node.py` was read directly (2030 lines) to verify the
> injection-defence and error-handling claims rather than relying on documentation alone.

---

### Model Context Protocol (MCP)

```yaml
project: Model Context Protocol
relevant_categories: [tools, protocols]
repository: https://github.com/modelcontextprotocol/modelcontextprotocol
authors: Anthropic (and contributors)
license: MIT
version_studied: schema revisions 2024-11-05 .. 2026-07-28 (2025-06-18 and 2026-07-28 in depth)
capabilities: >
  An open protocol for exposing tools, resources, and prompts to LLM applications over
  JSON-RPC. Defines tool discovery (tools/list) and invocation (tools/call), plus
  capability negotiation and transports (stdio, Streamable HTTP).
architecture: >
  JSON-RPC 2.0 with a lifecycle: initialize -> notifications/initialized -> tools/list
  -> tools/call. Tools carry a name, description, and inputSchema (JSON Schema).
  Results carry content[] and optional structuredContent, with isError as an in-band flag.
  Later revisions (2026-07-28) remove the handshake entirely, add server/discover, make
  the protocol stateless, and require resultType on all results.
strengths:
  - Clean separation of discovery from invocation
  - Two-tier error taxonomy grounded in model-actionability, with the rationale documented
  - Annotations explicitly marked as untrusted hints rather than guarantees
  - Real transport specification (stdio and Streamable HTTP)
  - list_changed invalidation notification for dynamic tool sets
weaknesses:
  - Tool identity is scoped to a live connection/process and dies on restart
  - The 2025-06-18 inputSchema type permits only type/properties/required while prose
    says "JSON Schema"; the ambiguity caused documented multi-year cross-SDK breakage
  - structuredContent was object-only until SEP-2106 (2025-06-18 shape carries a
    now-removed constraint)
  - 2025-06-18 lists "Invalid arguments" as protocol-level AND "Invalid input data" as
    execution-level - overlapping guidance
  - Six schema revisions in flight; anything built against the handshake is already legacy
patterns_worth_adopting:
  - Discovery/invocation separation
  - inputSchema rooted at type:object; ALWAYS emit an explicit $schema (>=2020-12)
  - Normalise schemas to be self-contained; never auto-dereference network $ref
  - Error taxonomy keyed on model-visibility, with isError as an in-band flag
  - Annotations explicitly untrusted
  - The observation that an untrusted schema is an attack surface (external $ref -> SSRF,
    pathological composition -> CPU exhaustion)
patterns_worth_avoiding:
  - Inheriting the dialect ambiguity
  - Object-only structuredContent
  - Duplicated structured+text payload shims
  - Accepting unvalidated opaque inputSchema
  - Coupling to handshake lifecycle
  - Server-centric tool identity
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target for Phase 1. The capability map is the launch point (charter 21).
  The mcp-client capability (separate taxonomy entry) will implement the stdio transport.
  This study informs our registry's identity and schema model, not a shared wire format.
standards: ["JSON-RPC 2.0", "JSON Schema"]
last_reviewed: 2026-09-15
```

---

### Microsoft Semantic Kernel

```yaml
project: Microsoft Semantic Kernel
relevant_categories: [tools]
repository: https://github.com/microsoft/semantic-kernel
authors: Microsoft
license: MIT
version_studied: python 1.44.1 (source read directly)
capabilities: >
  Plugin/function model for exposing native and prompt functions to models, with an
  auto function-calling loop, allowlisting, and an onion middleware filter system.
architecture: >
  KernelFunction (Pydantic model) with KernelFunctionFromMethod / FromPrompt subclasses.
  @kernel_function plants __kernel_function_*__ dunders; KernelFunctionFromMethod raises
  unless they are present. KernelPlugin is dict-like; the Kernel is a god object holding
  services, plugins, filters, and prompt rendering. FunctionChoiceBehavior drives the
  auto-calling loop. Filters are (context, next) middleware assembled per filter type.
strengths:
  - Onion middleware over invocation - logging, approval, retry, caching, PII redaction
    without touching tool code
  - Metadata separated from the callable
  - A pure metadata -> vendor tool JSON rendering function
  - Explicit advertise filters (include/exclude plugins and functions)
weaknesses:
  - Registration is decorator-gated dunder smuggling, not an explicit protocol
  - Schema inference runs as an eager Pydantic model_validator side effect (C# caches lazily)
  - Tool name is "Plugin-function" - a namespace flattened into a model-visible string
    then re-parsed
  - The core tool type imports opentelemetry unconditionally and instruments every
    invocation with spans and histograms
  - Very heavy transitive dependencies (azure-*, openai, numpy, openapi_core, aiortc,
    websockets, pydantic, opentelemetry-api)
  - Fail-open defaults: with no function_choice_behavior it logs (at debug) that no
    allowlist validation will be performed; an empty include list is a no-op
  - Filters live on the Kernel instance, so they silently vanish when a chat service is
    used without passing the kernel
  - KernelInvokeException masks the original error cause
patterns_worth_adopting:
  - Middleware over invocation - but on a standalone object whose absence is a type
    error, not a silent bypass
  - Metadata/callable separation
  - A pure per-vendor rendering adapter
  - Advertising as explicit policy
  - The <=10-20 advertised-tools constraint
patterns_worth_avoiding:
  - God-object container
  - Dunder-gated registration instead of an explicit protocol
  - Namespace flattened into a model-facing name
  - Schema inference inside a validator side effect
  - Unconditional telemetry imports in the core tool type
  - Fail-open allowlist defaults
  - Exception masking
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. The middleware pattern is adopted as a CONCEPT, deliberately
  re-placed onto a standalone object. No code reused.
standards: ["JSON Schema", "OpenAPI"]
last_reviewed: 2026-09-15
```


## License compatibility note

All identified Phase-2 study targets are permissive and compatible with this repository's Apache-2.0 license:

| Project | License |
|---|---|
| LangChain, LlamaIndex, AutoGen, CrewAI, DSPy, SWE-agent, Semantic Kernel, OpenAI Swarm | MIT |
| Haystack, MemGPT / Letta | Apache-2.0 |

This table is orientation only — it is **not** a study record. Confirm each license at the version actually studied before setting `code_reused: true` (licenses change).