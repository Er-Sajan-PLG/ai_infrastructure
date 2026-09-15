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
last_reviewed: 2026-09-16
review_note: >
  Re-read in depth in session 16 against 2026-07-28 primary sources. Two findings
  this entry did not carry: (1) the two protocol ERAS are now named in the spec
  ("Modern" = per-request _meta, 2026-07-28+; "Legacy" = initialize handshake,
  2025-11-25 and earlier), and the compatibility matrix says a modern client against
  a legacy server FAILS rather than degrades -- so the era choice determines which
  servers a client can reach at all. (2) The spec now partitions the JSON-RPC reserved
  range (-32000..-32099): -32020..-32099 is reserved for MCP, -32000..-32019 is frozen
  legacy, and -32002 (resource not found, legacy) MUST NOT be emitted but SHOULD still
  be accepted. None of this changes the entry's conclusions; it sharpens the era risk
  from "six revisions in flight" to "two incompatible protocol designs".
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

### LiteLLM

```yaml
project: LiteLLM
repository: https://github.com/BerriAI/litellm
authors: BerriAI
license: MIT
version_studied: 1.102.0 (pyproject.toml on main, and docs.litellm.ai)
capabilities: >
  Unified completion()/acompletion() over 100+ providers, addressed by a
  "provider/model" string. Also ships a proxy server, cost maps, caching and
  budget tracking.
architecture: >
  Per-provider adapters under litellm/llms/<provider>/, each with a
  transformation module converting between the provider's wire format and
  OpenAI-shaped dicts. ModelResponse subclasses OpenAI's ChatCompletion.
  Provider detection lives in litellm_core_utils/get_llm_provider_logic.py
  (894 lines), split into per-provider _get_*_provider helpers plus
  provider_list data-table lookups.
strengths:
  - "The ergonomics are genuinely good: one model string selects the provider, and messages are plain dicts rather than framework classes."
  - "Error taxonomy maps provider HTTP failures onto a familiar OpenAI-shaped hierarchy, so callers learn one set of names."
  - "Breadth of provider coverage, including OpenAI-compatible endpoints as a fallback category."
weaknesses:
  - "FACT (verified): base `dependencies` in pyproject.toml is 14 packages including openai, httpx, tiktoken, tokenizers, pydantic, jsonschema, aiohttp and boto3. Depending on LiteLLM means depending on all of them."
  - "FACT (verified): exceptions subclass the OpenAI SDK's classes (class RateLimitError(openai.RateLimitError)). This is the root cause of the openai dependency: the abstraction cannot shed another vendor without a breaking change."
  - "OBSERVATION: the error mapper is ~2,753 lines and much of it matches on substrings of str(exception)."
  - "OBSERVATION: normalisation is per-provider and explicitly lossy; docs acknowledge system-list blocks are joined with newlines and non-text blocks dropped."
  - "OBSERVATION: retry/fallback logic (router.py, ~14,373 lines) is bundled into the same distribution as the core call path."
patterns_worth_adopting:
  - "provider/model string addressing — but backed by an explicit, typed registry rather than a string cascade."
  - "A flat normalised error set carrying status_code/provider/model, with dedicated RateLimit and ContextWindowExceeded types that a caller can branch on."
  - "usage as a record with Optional fields, because providers genuinely omit different parts."
  - "A repeated-chunk guard on streams (REPEATED_STREAMING_CHUNK_LIMIT) — cheap protection against a runaway provider stream."
patterns_worth_avoiding:
  - "Subclassing another vendor's exception hierarchy. It is a permanent, breaking coupling in exchange for familiarity."
  - "Owning HTTP transport in the abstraction. This is what drags in boto3 and httpx for every consumer."
  - "Fields carried via extra='allow' (e.g. Delta.reasoning_content) — invisible to mypy --strict and to any schema."
  - "Global mutable configuration (drop_params/modify_params/success_callback) on the call path."
  - "Silent schema downgrades: stripping JSON-Schema keywords a target provider rejects, rather than surfacing the incompatibility."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. LiteLLM's INTERFACE is studied as a concept source;
  its implementation strategy is deliberately not followed. No code reused, no
  shared types, no shared dependency.
standards: ["OpenAI Chat Completions wire format", "JSON Schema"]
last_reviewed: 2026-09-15
```

### OpenAI Python SDK (provider client design)

```yaml
project: OpenAI Python SDK
repository: https://github.com/openai/openai-python
authors: OpenAI
license: Apache-2.0
version_studied: main branch (httpx2-based 2.x line)
capabilities: >
  The reference client for OpenAI's APIs, and the de-facto vocabulary that most
  other abstractions copy.
architecture: >
  Generated from OpenAI's OpenAPI spec. Synchronous and asynchronous trees are
  entirely separate mirrored hierarchies (OpenAI/AsyncOpenAI, SyncAPIClient/
  AsyncAPIClient, Stream/AsyncStream).
strengths:
  - "Streaming is a proper iterator with context-manager semantics, and it raises APIError MID-ITERATION on an error frame rather than silently truncating."
  - "Exception tree separates APIError / APIStatusError / APIConnectionError / APITimeoutError, and per-status subclasses."
  - "The message vocabulary (role/content dicts, model-as-string, temperature, max_tokens, tools) is the lingua franca other libraries converge on."
weaknesses:
  - "Full sync/async duplication is only affordable because a code generator produces it. Line count is roughly doubled; a hand-written library cannot copy this."
  - "Client-side retry (max_retries) plus a bespoke 401 token-refresh replay path is non-trivial behaviour hidden inside the client."
patterns_worth_adopting:
  - "Streams that can fail mid-iteration, and say so — the single detail most wrappers get wrong."
  - "Separating connection/timeout failures from status-code failures."
  - "Plain dicts for messages rather than owned classes, so callers are not forced through converters."
patterns_worth_avoiding:
  - "Hand-mirroring the entire surface for async. If async is offered, it must be derived or genuinely different, not a duplicate that will drift."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  The wire format is a compatibility TARGET for the OpenAI adapter (that is what
  makes an OpenAI-compatible endpoint usable). No SDK code is reused, and the SDK
  is not a dependency.
standards: ["OpenAI Chat Completions", "Server-Sent Events"]
last_reviewed: 2026-09-15
```

### LangChain BaseChatModel

```yaml
project: LangChain (langchain-core)
repository: https://github.com/langchain-ai/langchain
authors: LangChain, Inc.
license: MIT
version_studied: langchain-core 1.6.3
capabilities: >
  The BaseChatModel interface underlying LangChain's chat integrations: invoke,
  stream, batch, and their async variants.
architecture: >
  BaseChatModel inherits Runnable. An implementer provides _generate() (and
  optionally _stream/_agenerate/_astream); the base DERIVES everything else.
strengths:
  - >
    FACT (verified in source): async is derived, not duplicated — the base
    _agenerate runs the sync _generate via run_in_executor, and _astream pulls
    the sync generator through an executor. An implementer gets a working async
    surface for free, with no event-loop footgun.
  - "Streaming is a generator of chunks, and generate_from_stream collapses a stream back into a full result, so one code path serves both."
weaknesses:
  - "Messages are library-specific Pydantic classes (HumanMessage/AIMessage/...), so consumers must convert; the types are not separable from the framework."
  - "BaseChatModel does roughly eleven jobs (transport, caching, rate limiting, tracing, serialization, model profiles, tool binding, structured output, deprecation shims), and its dependencies include langsmith and tenacity."
  - "bind_tools() in the base is literally `raise NotImplementedError` — the advertised capability is opt-in per integration."
  - "A v1 and v2 content-block protocol and a callback protocol all coexist on the same surface."
patterns_worth_adopting:
  - >
    The one-required-method contract with everything else derived. It is the
    single biggest predictor of integration burden: LangChain needs one method
    where LlamaIndex demands eight.
  - "Async derived via a thread-pool default, so sync-only implementations are not second-class."
  - "Streaming as an iterator of deltas, with an explicit collapse-to-final operation."
patterns_worth_avoiding:
  - "Putting caching, rate limiting, tracing, serialization and model profiling on the model object."
  - "Owning the message types, forcing every consumer through converters."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. The derived-async and one-required-method patterns are
  adopted as CONCEPTS. No code reused, no shared types.
standards: []
last_reviewed: 2026-09-15
```

### LlamaIndex LLM

```yaml
project: LlamaIndex (llama-index-core)
repository: https://github.com/run-llama/llama_index
authors: LlamaIndex, Inc.
license: MIT
version_studied: llama-index-core 0.14.24
capabilities: >
  The LLM interface underlying LlamaIndex: chat/complete and their streaming and
  async variants.
architecture: >
  An abstract LLM base declaring eight abstract methods, with Pydantic message
  and response types (ChatMessage, ChatResponse, CompletionResponse).
strengths:
  - "distinguishes chat from text completion as an explicit capability axis, rather than one method with a flag."
  - "The response object accumulates streamed text and exposes both the full extent and the latest delta."
weaknesses:
  - >
    OBSERVATION from source: all eight methods are @abstractmethod, which is the
    opposite of LangChain's one-method contract and the largest divergence in the
    survey.
  - >
    OBSERVATION: the async methods are a facade — `async def achat(...): return
    self.chat(...)`. It looks asynchronous and blocks the event loop unless every
    integration overrides it.
  - "Its dependency weight (SQLAlchemy, nltk, numpy, tiktoken, networkx, pillow, aiohttp) makes the interface inseparable from the RAG framework."
  - "ChatMessage's module imports mimetype-sniffing libraries at scope, so even the message type is not lightweight."
patterns_worth_adopting:
  - "Usage metadata surfaced per response, and a model-metadata object declaring context window and capabilities."
  - "An explicit chat-vs-completion capability axis on the model, not a silent fallback."
patterns_worth_avoiding:
  - "Declaring eight abstract methods where one suffices — it taxes every integrator."
  - "An async surface that is not actually asynchronous. This is the clearest anti-pattern found in the survey: it misleads callers and blocks the loop."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Studied as the negative case on interface burden and
  async honesty. No code reused.
standards: []
last_reviewed: 2026-09-15
```

### ReAct (Yao et al.)

```yaml
project: "ReAct: Synergizing Reasoning and Acting in Language Models"
repository: https://github.com/ysymyth/ReAct
authors: Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, Yuan Cao
license: MIT (reference implementation); paper CC BY 4.0
version_studied: arXiv:2210.03629v3 (ICLR 2023 camera-ready, 10 Mar 2023)
capabilities: >
  A prompting paradigm that interleaves free-form reasoning ("thoughts") with
  task actions and environment observations, so a frozen LLM can ground its
  reasoning in external retrieval.
architecture: >
  Prompt-format only. Few-shot in-context trajectories use the line prefixes
  Thought: / Act: / Obs:. The action space is augmented as A-hat = A union L,
  where L is the space of language; a thought in L emits no observation and only
  updates the context.
strengths:
  - "FACT (verified in the paper): a thought emits no observation -- c_{t+1} = (c_t, a-hat_t) -- which cleanly separates reasoning from environmental effect."
  - "FACT: thought density is deliberately variable. Dense alternation for reasoning tasks (HotpotQA, FEVER); for decision tasks 'thoughts only need to appear sparsely ... so we let the language model decide'."
  - "FACT: the step cap was set empirically, not by taste. 7 steps for HotpotQA and 5 for FEVER, justified as 'more steps will not improve ReAct performance'; only 0.84% and 1.33% of CORRECT trajectories used the full budget."
  - "FACT: the paper reports its own failure modes honestly (Table 2), including a named repetition failure."
weaknesses:
  - >
    FACT: repetition is a documented, frequent, and unmitigated failure. The
    paper names "one frequent error pattern specific to ReAct, in which the model
    repetitively generates the previous thoughts and actions ... the model fails
    to reason about what the proper next action to take and jump out of the
    loop." The only proposed remedy is a guess that "sub-optimal greedy decoding"
    is at fault and beam search might help.
  - >
    FACT: the format is injection-vulnerable by construction. Observations are
    concatenated into the same text stream as the thoughts they inform, and the
    stream is parsed for actions -- so an observation containing action-like text
    is executable. The paper does not discuss prompt injection at all.
  - "FACT: 47% of ReAct failures on HotpotQA were reasoning errors, versus 16% for CoT; the interleaving constraint costs flexibility."
  - "FACT: 23% of error cases were non-informative search results, which 'derails the model reasoning and gives it a hard time to recover'."
  - "OBSERVATION: it specifies a format but no parser, no loop implementation, no termination mechanism, and no state object. Anything built from it is an engineering design informed by the pattern, not an implementation of the paper."
patterns_worth_adopting:
  - "A hard step cap derived from observed data rather than a round number."
  - "Reporting failure modes honestly in the primary artifact."
  - "The observation that most correct trajectories need very few steps -- which is what makes a modest default cap nearly free."
patterns_worth_avoiding:
  - "Free-text action parsing. It creates format-drift, partial-parse, and injection failure classes that typed tool calls eliminate."
  - "A structurally mandatory thought step. The paper itself makes thought occurrence model-chosen; forcing it adds cost and a parse-failure mode."
  - "Shipping a known-recurring failure (repetition) with no mechanism against it."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. The pattern is studied as a CONCEPT source for the
  agent-loop control design. No prompt text, trajectory, code, or example from
  the paper or its reference implementation is reused.
standards: []
last_reviewed: 2026-09-15
```

### LangGraph react agent executor

```yaml
project: LangGraph (langgraph.prebuilt react agent)
repository: https://github.com/langchain-ai/langgraph
authors: LangChain, Inc.
license: MIT
version_studied: main branch, libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py and langgraph/errors.py
capabilities: >
  A graph-based agent loop: an "agent" node calls the model, a "tools" node
  dispatches tool calls, and a conditional edge routes between them until the
  model stops requesting tools.
architecture: >
  A StateGraph rather than a while-loop. AgentState carries exactly two keys:
  `messages` (an append-only message list) and `remaining_steps`. Tool calls fan
  out via Send(). A separate `langgraph/errors.py` defines GraphRecursionError.
strengths:
  - >
    FACT: cap exhaustion produces a readable result, not an opaque crash. The
    docstring states that when remaining_steps < 2 with tool calls present the
    agent returns an AI message reading "Sorry, need more steps to process this
    request." and that "No GraphRecusionError will be raised in this case" -- the
    cap is soft.
  - "FACT: an unknown tool becomes a ToolMessage, not an exception: INVALID_TOOL_NAME_ERROR_TEMPLATE = \"Error: {requested_tool} is not a valid tool, try one of [{available_tools}]\"."
  - "FACT: tool errors are templated for the model: TOOL_CALL_ERROR_TEMPLATE = \"Error: {error}\\n Please fix your mistakes.\""
  - "FACT: handled errors carry a status: ToolMessage(content=..., name=call[\"name\"], tool_call_id=call[\"id\"], status=\"error\")."
  - "FACT: a chat-history invariant is validated -- _validate_chat_history raises ValueError with ErrorCode.INVALID_CHAT_HISTORY if any AIMessage.tool_calls entry lacks a matching ToolMessage."
  - "FACT: retry and caching are explicitly delegated to wrap_tool_call / awrap_tool_call rather than owned by the loop."
weaknesses:
  - >
    FACT: the graph is a runtime, and adopting it means adopting langchain-core.
    A dispatcher with a bound does not need a superstep engine.
  - >
    OBSERVATION: AgentState has NO thought field. This is evidence that a
    harness-imposed reasoning step is unnecessary once native tool calls exist.
  - >
    FACT: the module studied is deprecated -- its decorator points to
    langchain.agents.create_agent -- so the surface studied is a compatibility
    path, not the forward direction.
patterns_worth_adopting:
  - "A cap trip that yields a readable result rather than an opaque crash."
  - "Model-readable, templated error text on the unknown-tool and tool-error paths."
  - "A history invariant check before each model call, since most providers reject an unmatched tool call."
  - "Delegating retry to a wrapper, keeping the loop free of retry policy."
patterns_worth_avoiding:
  - "Owning a graph runtime for a single control loop."
  - "Silent soft-termination with no machine-readable signal: a caller cannot distinguish 'finished' from 'out of steps' unless a state flag is also recorded."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Mechanism-level study only. No source, template
  string, or state type is copied; the loop is not graph-based.
standards: []
last_reviewed: 2026-09-15
```

### OpenAI Agents SDK

```yaml
project: OpenAI Agents SDK (openai-agents-python)
repository: https://github.com/openai/openai-agents-python
authors: OpenAI
license: MIT
version_studied: main branch, src/agents/run.py and src/agents/exceptions.py
capabilities: >
  An imperative agent runtime: Agent + Runner + RunResult, with a turn loop,
  handoffs between agents, guardrails, sessions, and streaming.
architecture: >
  A turn loop, not a graph. run.py documents the cycle: the agent is invoked; if
  there is a final output the loop terminates; if there is a handoff the loop
  re-runs with the new agent; otherwise tool calls run and the loop repeats.
  Decisions are typed next-step values, not booleans.
strengths:
  - >
    FACT: termination is a closed set of typed step results --
    NextStepFinalOutput | NextStepHandoff | NextStepRunAgain | NextStepInterruption
    (from run_internal/run_steps.py). This makes the decision surface readable
    where a boolean flag would not.
  - "FACT: the cap is a documented parameter with a stated unit -- max_turns, where 'A turn is defined as one AI invocation (including any tool calls that might occur)', and None disables it."
  - "FACT: exceeding the cap raises MaxTurnsExceeded(AgentsException), a typed exception in the library's own hierarchy."
  - "FACT: a max-turns handler can produce output instead of raising (finalize_max_turns_handler_output exists), so the hard default is overridable."
  - "FACT: ModelBehaviorError is documented as 'raised when the model does something unexpected, e.g. calling a tool that doesn't exist, or providing malformed JSON' -- and the unknown-tool response is configurable via ToolNotFoundBehavior and ToolErrorFormatter."
weaknesses:
  - >
    OBSERVATION: the default for an unknown tool is to raise, which kills a run
    the model could have recovered from. It is configurable, but the safe default
    is the wrong way round for a bounded loop.
  - >
    FACT: the logical cycle is spread across run.py and a run_internal package
    (run_loop.py and peers, together thousands of lines), and the streaming path
    is reimplemented separately (start_streaming / run_single_turn_streamed)
    rather than shared with the sync path.
  - "OBSERVATION: it is bound to OpenAI's platform features (previous_response_id, conversation_id, sessions), so it is not a neutral loop."
patterns_worth_adopting:
  - "Typed next-step values instead of boolean flags."
  - "A documented turn unit, so 'max turns' has a definition rather than an intuition."
  - "An overridable cap-exhaustion handler."
patterns_worth_avoiding:
  - "Raising on an unknown tool by default, killing a recoverable run."
  - "Splitting one logical cycle across several large modules."
  - "Reimplementing the loop separately for streaming."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Studied for control-flow and cap design only. No code,
  type, or name is reused; this repository has no OpenAI platform dependency.
standards: []
last_reviewed: 2026-09-15
```

### smolagents

```yaml
project: smolagents
repository: https://github.com/huggingface/smolagents
authors: Hugging Face
license: Apache-2.0
version_studied: main branch, src/smolagents/agents.py
capabilities: >
  A minimal agent library offering a ToolCallingAgent (native JSON-like tool
  calls) and a CodeAgent (tool calls generated as executable Python), over a
  MultiStepAgent base.
architecture: >
  A generator-based loop. _run_stream sets step_number, builds an ActionStep per
  step, delegates to _step_stream, and in a finally block finalises the step,
  appends it to AgentMemory, yields it, and increments. RunResult carries a state
  literal distinguishing success from exhaustion.
strengths:
  - >
    FACT: cap exhaustion is recorded as a distinguishable STATE, not only an
    exception -- RunResult.state is Literal["success", "max_steps_error"], and
    _handle_max_steps_reached appends an ActionStep carrying
    AgentMaxStepsError("Reached max steps."). A caller can therefore tell
    "finished" from "ran out".
  - "FACT: the step cap has a concrete default and is overridable per call: max_steps: int = 20 on __init__, and run(max_steps=...)."
  - "FACT: tool failures are differentiated by kind -- AgentToolCallError for bad arguments, AgentToolExecutionError for an unknown tool ('Unknown tool {tool_name}, should be one of: ...') and for execution failure ('Please try again or use another tool')."
  - "FACT: most AgentError subclasses set action_step.error and let the loop continue, so the model sees the failure on the next step."
  - "FACT: ToolCallingAgent exists specifically to use the model's own tool-calling capability, replacing the older text-parsing path -- a direct precedent for our structured-only decision."
weaknesses:
  - >
    FACT: the final answer is a designated tool. self.tools.setdefault("final_answer",
    FinalAnswerTool()) and is_final_answer = tool_name == "final_answer". That
    reserves a tool name and makes completion a tool-call convention rather than
    an absence of tool calls.
  - "FACT: CodeAgent executes model-generated Python, which is a materially larger trust boundary than dispatching typed tool calls."
  - "OBSERVATION: AgentMemory holds typed step objects (SystemPromptStep, TaskStep, PlanningStep, ActionStep, FinalAnswerStep), which is more machinery than an append-only message list."
patterns_worth_adopting:
  - "Recording WHY the loop stopped as a state flag a caller can branch on."
  - "Error kinds named by what the caller/model can do about them."
  - "Providing a native-tool-calling agent as the successor to a text-parsing one."
patterns_worth_avoiding:
  - "Reserving a tool name for the final answer; the absence of a tool call is simpler and does not collide with a user's tools."
  - "Executing model-generated code inside the loop."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Studied for cap and error reporting design. No code
  reused; the final-answer-as-tool convention is deliberately NOT adopted.
standards: []
last_reviewed: 2026-09-15
```

### LangChain tool error surface

```yaml
project: LangChain (langchain-core tool error handling)
repository: https://github.com/langchain-ai/langchain
authors: LangChain, Inc.
license: MIT
version_studied: langchain-core, libs/core/langchain_core/tools/base.py
capabilities: >
  The per-tool error policy that decides whether a tool failure ends a run or is
  returned to the model as an observation.
architecture: >
  A ToolException a tool may raise, plus a handle_tool_error setting on the tool
  that controls how it is treated.
strengths:
  - >
    FACT (read in source, line 371): `class ToolException(Exception)` with the
    docstring "This exception allows tools to signal errors without stopping the
    agent. The error is handled according to the tool's `handle_tool_error`
    setting, and the result is returned as an observation to the agent."
  - >
    OBSERVATION: this is the same split our tool-registry already computes as
    FailureKind.model_visible (ADR-0006 D-4) -- the decision about whether a
    failure is model-actionable lives at the TOOL, and defaults to fatal.
  - "OBSERVATION: defaulting to fatal is the safe direction: nothing enters the model's context unless someone opted in."
weaknesses:
  - >
    OBSERVATION: the mechanism is opt-in per tool, so whether the model ever sees
    a failure depends on individual tool authors remembering to classify it --
    a silent, per-tool inconsistency rather than a registry-level guarantee.
patterns_worth_adopting:
  - "Classifying a tool failure by whether the model can act on it, and defaulting to not feeding it back."
  - "Delivering a handled failure as a structured, status-marked message rather than raw exception prose."
patterns_worth_avoiding:
  - "Leaving classification to per-tool discretion when a registry can compute it once and enforce it for every tool."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Studied as independent corroboration of the
  model-actionability split already adopted in ADR-0006. No code reused; our
  registry computes the classification rather than asking each tool to declare it.
standards: []
last_reviewed: 2026-09-15
```

### OpenTelemetry GenAI semantic conventions

```yaml
project: OpenTelemetry GenAI semantic conventions
repository: https://github.com/open-telemetry/semantic-conventions-genai
authors: OpenTelemetry authors
license: Apache-2.0
version_studied: main branch, docs/gen-ai/{gen-ai-spans,gen-ai-agent-spans,gen-ai-events,gen-ai-metrics}.md and docs/registry/attributes/gen-ai.md (fetched 2026-09-15)
capabilities: >
  Vendor-neutral semantic conventions for generative-AI telemetry: span names,
  attribute names, events, and metrics for model calls, agent invocations, tool
  execution, retrieval, and memory.
architecture: >
  Not an implementation. A naming and requirement-level specification, generated
  from YAML definitions via Weaver, layered on OpenTelemetry's core span model.
  Node "type" is expressed as gen_ai.operation.name -- an operation verb -- rather
  than a span-kind enum. Content attributes are Opt-In.
strengths:
  - "FACT: span naming is derived, not stored: `{gen_ai.operation.name} {gen_ai.request.model}` for inference, `execute_tool {gen_ai.tool.name}`, `invoke_agent {gen_ai.agent.name}`."
  - "FACT: the model-facing content attributes (gen_ai.input.messages, gen_ai.output.messages, gen_ai.system_instructions, gen_ai.tool.definitions) are all Opt-In, with the explicit rule 'Instrumentations SHOULD NOT capture them by default, but SHOULD provide an option for users to opt in'."
  - "FACT: a tool call is a span with the result as an ATTRIBUTE on the same span (gen_ai.tool.call.result, Opt-In) -- not a separate signal. `gen_ai.tool.name` is Required; `gen_ai.tool.call.id` is Recommended."
  - "FACT: usage is modelled (gen_ai.usage.input_tokens / output_tokens, plus cache_read, cache_write, reasoning, and per-modality splits), with subset arithmetic specified."
  - "FACT: retry semantics are stated -- a span SHOULD cover the logical operation including all retries, which agrees with ADR-0007's placement of retry policy at the caller."
  - "FACT: the conventions address manually-instrumented tools explicitly, which is our exact situation (in-process dispatch)."
weaknesses:
  - >
    FACT: everything is `Development`. Every span, event, metric, and attribute
    carries the Development badge; the only Stable markers are borrowed core
    attributes (error.type, server.address, server.port). There is no version or
    date in the doc bodies, and the new repository's README declares its Schema URL
    as `TODO`.
  - >
    FACT: the conventions MOVED repositories mid-survey. The pages in
    open-telemetry/semantic-conventions now return HTTP 200 with a "this page has
    moved" stub rather than a 404 -- a trap for any automated check that trusts a
    status code.
  - >
    FACT: the content-capture policy REVERSED. `gen_ai.prompt` and
    `gen_ai.completion` are marked Deprecated with "Removed, no replacement at
    this time", replaced by Opt-In structured attributes and the Opt-In event
    `gen_ai.client.inference.operation.details`. The date of the reversal could
    not be determined (no git history fetched).
  - "FACT: cost is not modelled at all -- no cost attribute and no cost metric exist."
  - "OBSERVATION: invoke_agent exists as two spans (client and internal) distinguished only by Span kind, and every agent span carries a caveat that frameworks MAY override the span name format."
patterns_worth_adopting:
  - "Default-off content capture with explicit opt-in -- the only surveyed system to state this, and the only one with a privacy review."
  - "Result-as-attribute on the tool span, not a second node."
  - "Distinguishing a required identifier from an optional payload (tool.name Required, tool.call.arguments Opt-In)."
  - "Stating the retry/span relationship explicitly."
patterns_worth_avoiding:
  - "Claiming compatibility with a Development-track specification that has no schema URL and has already reversed a decision. Study the vocabulary; do not assert conformance."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target, and deliberately no compatibility CLAIM. The
  conventions are Development, have just moved repositories, and have no published
  schema URL. We adopt two RULES from them -- default-off content capture and
  result-as-attribute -- and record the correspondence, without asserting that any
  artifact we produce conforms.
standards: ["OpenTelemetry GenAI semantic conventions (Development)"]
last_reviewed: 2026-09-15
```

### Langfuse

```yaml
project: Langfuse
repository: https://github.com/langfuse/langfuse
authors: Langfuse GmbH
license: MIT (core; some enterprise features separately licensed)
version_studied: main branch, packages/shared/src/domain/observations.ts, domain/traces.ts, server/ingestion/types.ts (fetched 2026-09-15)
capabilities: >
  An LLM observability platform: trace/observation ingestion, storage, and analysis,
  with a first-class cost and usage model.
architecture: >
  Unit of record is the OBSERVATION, a single flat record with a `type`
  discriminator and a nullable `parentObservationId`. A separate thinner
  TraceDomain exists and does NOT embed its observations. Ingestion is a versioned
  HTTP event union (trace-create, span-create, generation-create, ...) backed by
  ClickHouse.
strengths:
  - "FACT: the taxonomy is a 10-value enum -- SPAN, EVENT, GENERATION, AGENT, TOOL, CHAIN, RETRIEVER, EVALUATOR, EMBEDDING, GUARDRAIL -- with levels DEBUG/DEFAULT/WARNING/ERROR."
  - >
    FACT, and the single most useful idea found in the whole survey: the schema
    distinguishes caller-supplied numbers from derived ones --
    `providedUsageDetails` vs `usageDetails`, and `providedCostDetails` vs
    `costDetails`, with source comments "aggregated data from cost_details" and
    "aggregated data from usage_details". A trace can therefore say whether a
    number was reported or computed.
  - "FACT: `endTime` is nullable, which is the honest model of a span that started and never finished."
  - "FACT: EVENT is a first-class zero-duration type, which no other surveyed system has."
weaknesses:
  - >
    FACT: no documented on-disk format. Ingestion is HTTP into ClickHouse, so a
    zero-dependency emitter cannot produce a Langfuse-compatible artefact without
    running a Langfuse server.
  - "FACT: `latency` and `timeToFirstToken` carry no stated unit in the schema."
  - "OBSERVATION: tool data is a flat set of nullable fields (toolDefinitions, toolCalls, toolCallNames) rather than a structured type."
  - "OBSERVATION: the shared schema states no content-capture policy; the decision lives in the SDK, which was not read."
patterns_worth_adopting:
  - "The provided-vs-derived split for usage and cost. It composes directly with ADR-0007 D-5 (None is the absence of a measurement, 0 is a measurement)."
  - "A nullable end time."
  - "A point-in-time EVENT type alongside duration-bearing spans."
patterns_worth_avoiding:
  - "Leaving the time unit unstated in a numeric field name."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Studied for its provided/derived split and its nullable
  end time. No code reused.
standards: []
last_reviewed: 2026-09-15
```

### LangSmith

```yaml
project: LangSmith (Python SDK)
repository: https://github.com/langchain-ai/langsmith-sdk
authors: LangChain, Inc.
license: MIT
version_studied: main branch, python/langsmith/schemas.py (fetched 2026-09-15)
capabilities: >
  Tracing and evaluation for LLM applications: runs, traces, sessions, datasets.
architecture: >
  Unit of record is the RUN. A trace is not a record; it is the set of runs sharing
  a trace_id. Hierarchy is carried redundantly by parent_run_id, parent_run_ids, and
  a sortable `dotted_order` string encoding execution order.
strengths:
  - "FACT: `dotted_order` is documented as '{time}{run-uuid}.* so that a trace can be sorted in the order it was executed' -- an explicit replay-ordering key, which no other surveyed system has."
  - "FACT: `latency` is a derived property in SECONDS, computed from start_time/end_time, so the unit is unambiguous in code even though it is not in the field name."
  - "FACT: token and cost details are modelled separately from totals (prompt_token_details, completion_token_details, prompt_cost_details, completion_cost_details) with the note that details 'Does *not* need to sum to full ... token count'."
weaknesses:
  - >
    FACT: there is NO `agent` run type. The deprecated RunTypeEnum is tool, chain,
    llm, retriever, embedding, prompt, parser -- a product dedicated to agent
    tracing does not model "agent" as a run type.
  - "FACT: cost-computation provenance is not stated in the schema -- whether the client or server computes it is unknown."
  - "OBSERVATION: errors are a plain `error: Optional[str]` plus an optional `status: Optional[str]`, with no structured exception type."
  - "OBSERVATION: no on-disk format; transport is an HTTP API."
patterns_worth_adopting:
  - "A sortable execution-order key (`dotted_order`) alongside parent ids -- it makes replay deterministic without re-sorting by timestamp."
patterns_worth_avoiding:
  - "A plain error string where a structured error type belongs."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Studied for its ordering key and its cost-detail model.
  No code reused.
standards: []
last_reviewed: 2026-09-15
```

### MLflow (tracing)

```yaml
project: MLflow (GenAI tracing)
repository: https://github.com/mlflow/mlflow
authors: Databricks / MLflow contributors
license: Apache-2.0
version_studied: master branch, mlflow/entities/span.py, span_status.py, trace_info.py, tracing/constant.py (fetched 2026-09-15)
capabilities: >
  Experiment and model tracking, extended with an OpenTelemetry-shaped tracing
  layer for GenAI applications, including client- or server-side cost computation.
architecture: >
  Unit of record is the SPAN, deliberately OTel-shaped: the Span class wraps an
  OTelReadableSpan. Span, LiveSpan, NoOpSpan, and LazySpan variants exist. Trace-level
  metadata lives in a separate TraceInfo. Parent linkage is an OTel context object
  built from `parent_id`.
strengths:
  - >
    FACT: the ONLY surveyed system with a documented serialized span JSON a
    zero-dependency emitter could target without an HTTP ingest service --
    `to_dict()` / `from_dict()`, schema-versioned at TRACE_SCHEMA_VERSION = 3, with
    a `_is_span_v2_schema` discriminator, persisted as TRACKING_STORE spans.content.
  - "FACT: truncation limits are stated explicitly -- MAX_CHARS_IN_TRACE_INFO_METADATA = 250, TRACE_REQUEST_RESPONSE_PREVIEW_MAX_LENGTH_OSS = 1000 / _DBX = 10000, suffix '...'. No other surveyed system documents its limits."
  - >
    FACT: cost provenance is stated outright, with its limitation: "The cost
    tracking is calculated based on token usage and model pricing from LiteLLM.
    Cost tracking is not supported for all LLM providers."
  - "FACT: errors are a structured SpanStatus dataclass with SpanStatusCode UNSET/OK/ERROR -- documented as the same set as OpenTelemetry -- plus a description 'only set when the status is ERROR'. record_exception() adds a span event AND flips the status."
  - "FACT: the taxonomy is a non-enum on purpose, with the reason in source: 'Not using enum as we want to allow custom span type string.'"
weaknesses:
  - >
    OBSERVATION: the units disagree within one object -- span times are
    NANOSECONDS (start_time_ns/end_time_ns) while trace execution_duration is
    MILLISECONDS. A single implementation disagrees with itself.
  - "FACT: cost computation depends on a LiteLLM price table, and the docstring concedes it is not supported for all providers. A price table is a maintenance burden and an accuracy risk."
  - "UNVERIFIED: mlflow/tracing/sampling.py exists in the directory listing (1579 bytes) but was not read, so its sampling policy is unknown."
patterns_worth_adopting:
  - "A versioned, self-describing serialized span JSON."
  - "Stated truncation limits with an explicit suffix."
  - "A structured error status object rather than a string."
  - "An open span-type taxonomy when custom types are genuinely expected."
patterns_worth_avoiding:
  - "Mixed time units within one object."
  - "Computing cost from an embedded third-party price table."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Studied for its serialized span form, its stated
  truncation limits, and its error-status object. No code reused. Note: MLflow's
  default branch is `master`, not `main` -- any main-rooted raw URL 404s, which is a
  retrieval trap, not a missing file.
standards: []
last_reviewed: 2026-09-15
```

### AgentOps

```yaml
project: AgentOps
repository: https://github.com/AgentOps-AI/agentops
authors: AgentOps AI
license: MIT
version_studied: main branch, agentops/sdk/README.md, sdk/types.py, sdk/attributes.py, sdk/exporters.py, semconv/span_kinds.py, semconv/span_attributes.py, semconv/core.py, semconv/status.py (fetched 2026-09-15)
capabilities: >
  Agent observability: session-scoped tracing of agents, tools, and LLM calls, with
  cost and streaming metrics.
architecture: >
  Built directly on the OpenTelemetry trace SDK. Unit of record is the SPAN with an
  `agentops.span.kind` attribute; a SESSION is the root and every span needs one, so
  the trace root is itself a span. Transport is OTLP/HTTP with bearer JWT auth.
strengths:
  - "FACT: a documented migration away from an event model -- 'In AgentOps v0.4, we've transitioned from the Event concept to using Spans for all event tracking.'"
  - "FACT: 12 span kinds including session, workflow, task, operation, agent, tool, llm, chain, text, guardrail, http, unknown."
  - "FACT: the session-as-root model means no span can exist orphaned, which is a stronger integrity property than a nullable parent on every record."
  - "FACT: streaming timing is named explicitly (gen_ai.streaming.time_to_first_token, time_to_generate, streaming_duration, chunk_count)."
weaknesses:
  - "FACT: cost is a single `gen_ai.usage.total_cost` with no input/output split, and its provenance is not stated in the files read."
  - "OBSERVATION: core span start/end/latency field names are not present in the semconv files read; they rely on OTel natives, so the unit is implicit."
  - "UNVERIFIED: numeric defaults for max_queue_size, max_wait_time, and export_flush_interval -- the comments say defaults exist but the values are not in the read files."
  - "OBSERVATION: no documented on-disk format; transport is OTLP."
patterns_worth_adopting:
  - "A session root that every span must belong to, which prevents orphan records."
  - "Naming streaming timing explicitly rather than leaving it to be derived."
patterns_worth_avoiding:
  - "A cost field with no stated provenance."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. Studied for its session-root integrity model and its
  streaming timing names. No code reused.
standards: []
last_reviewed: 2026-09-15
```

### MCP Python SDK (official client)

```yaml
project: MCP Python SDK
repository: https://github.com/modelcontextprotocol/python-sdk
authors: Anthropic and contributors
license: MIT
version_studied: main branch, src/mcp/client/stdio.py, src/mcp/client/session.py, src/mcp/shared/jsonrpc_dispatcher.py, src/mcp/shared/exceptions.py, src/mcp/os/posix/utilities.py, pyproject.toml (fetched 2026-09-16)
capabilities: >
  The reference Python client and server implementation of MCP, including the stdio
  transport, request/response correlation, and the session lifecycle.
architecture: >
  Async-only, built on anyio. stdio_client is an async context manager that spawns the
  server with anyio.open_process and wires TextReceiveStream to a newline-delimited
  reader. Correlation is a dict of pending entries keyed by request id, with the request
  id doubling as the progress token.
strengths:
  - "FACT: no shell anywhere -- the command and args are passed as a list to anyio.open_process; there is no shell=True equivalent."
  - "FACT: the environment is an ALLOWLIST, not the full os.environ. POSIX inherits only HOME, LOGNAME, PATH, SHELL, TERM, USER, and values starting with '()' are skipped with the comment 'Skip functions, which are a security risk.'"
  - "FACT: shutdown kills the whole POSIX process GROUP via os.killpg(pgid, SIGTERM) then os.killpg(pgid, SIGKILL), enabled by start_new_session=True. The docstring names the leak this avoids: killpg 'reaches every descendant atomically, even ones whose parent already exited.'"
  - "FACT: shutdown runs inside anyio.CancelScope(shield=True), so a cancellation cannot leak the child process."
  - "FACT: stderr is INHERITED to the parent's stderr by default (errlog: TextIO = sys.stderr), not captured. Separately, the remaining stdout is drained and discarded in a cancel shield so a server flushing buffered output cannot block on a full pipe."
  - "FACT: three distinct error paths -- MCPError(code=CONNECTION_CLOSED) for transport failure, MCPError(code=<peer code>) for a JSON-RPC error response, and a plain returned CallToolResult with is_error=True for a tool failure. An isError result is NOT an exception."
  - "FACT: coerce_request_id turns a stringified int back to int so a peer-echoed id still correlates (the docstring says it matches the TS SDK)."
  - "FACT: read_timeout_seconds defaults to None (no timeout); DISCOVER_TIMEOUT_SECONDS = 10.0 is a module constant."
  - "FACT: timeouts on shutdown are named constants -- PROCESS_TERMINATION_TIMEOUT = 2.0, FORCE_KILL_TIMEOUT = 2.0."
weaknesses:
  - "FACT: it cannot meet a zero-runtime-dependency rule. Declared runtime deps include anyio, httpx2, pydantic, starlette, python-multipart, sse-starlette, uvicorn, jsonschema, pyjwt[crypto], typing-extensions, typing-inspection, and opentelemetry-api. The stdio transport alone needs anyio."
  - "FACT: async-only. Every entry point is async def; there is no sync client in the package. A sync client would have to be a wrapper."
  - "OBSERVATION: a JSON parse failure on stdout is returned as a VALUE on the read stream and the connection stays open -- the client tolerates a chatty server rather than failing. The spec does not require either behaviour."
  - "FACT: no startup timeout on the transport."
patterns_worth_adopting:
  - "Process-group kill on POSIX. The Go and TypeScript clients kill only the direct child and leak grandchildren."
  - "The stderr allowlist rather than full environment inheritance."
  - "The cancel-shield around shutdown, so a cancelled run cannot leak a process."
  - "Three genuinely distinct error paths for transport / protocol / tool failure."
patterns_worth_avoiding:
  - "The dependency footprint, which is disqualifying for a zero-dependency repository."
  - "The async-only posture, which would force a repository-wide reversal of ADR-0007 D-3."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target and no code reuse. Studied as the reference implementation of
  the transport we intend to build, and as the source of the process-group-kill behaviour
  we do intend to adopt.
standards: ["Model Context Protocol"]
last_reviewed: 2026-09-16
```

### MCP TypeScript SDK (official client)

```yaml
project: MCP TypeScript SDK
repository: https://github.com/modelcontextprotocol/typescript-sdk
authors: Anthropic and contributors
license: MIT
version_studied: main branch (v2 pnpm monorepo), packages/client/src/client/stdio.ts, packages/client/package.json, packages/core-internal/package.json, root package.json (fetched 2026-09-16)
capabilities: >
  The official TypeScript client and server implementation of MCP, including a stdio
  transport exported as a separate entry point so browser bundles do not pull in Node
  process APIs.
architecture: >
  Promise-based, layered over a shared protocol module that owns request correlation.
  The stdio transport spawns via cross-spawn with an explicit shell:false, feeds stdout
  chunks into a ReadBuffer, and writes with backpressure via the drain event.
strengths:
  - "FACT: shell is explicitly false -- 'shell: false' appears verbatim in the spawn options. No code path in the stdio file uses a shell."
  - "FACT: the environment is an allowlist mirroring the Python SDK, and also skips values starting with '()'."
  - "FACT: the stdio entry is deliberately kept separate from the root entry so bundling for browser or Cloudflare Workers 'does not pull in node:child_process, node:stream, or cross-spawn' -- an explicit acknowledgement that the transport is Node-only."
  - "FACT: ReadBuffer carries a maxBufferSize with a documented default of 10 MB; a single message exceeding it emits an error and closes the transport."
  - "FACT: writes respect backpressure -- if write() returns false the transport waits for the 'drain' event."
weaknesses:
  - "FACT: the stdio entry requires cross-spawn, a third-party package. Package deps also include eventsource, eventsource-parser, jose, pkce-challenge, and zod. This alone is disqualifying under a zero-runtime-dependency rule."
  - "OBSERVATION: on an unparseable stdout line it throws out of readMessage(), routes to onerror, and CLOSES the transport -- the opposite of the Python SDK's tolerate-and-continue."
  - "FACT: no startup timeout; start() resolves on the 'spawn' event and rejects on 'error'."
  - "UNVERIFIED: the newline-vs-Content-Length boundary logic inside ReadBuffer (packages/core-internal/src/shared/stdio.ts was not read), and the request-correlation table in protocol.ts. Do not cite the TS framing mechanism as FACT."
  - "UNVERIFIED: the SdkErrorCode taxonomy and whether any TypeScript code path elsewhere uses shell: true."
patterns_worth_adopting:
  - "An explicit documented buffer cap with a stated number (10 MB) -- a bound rather than an unbounded read."
  - "Explicit shell:false as a stated property rather than an incidental one."
  - "Backpressure handled via the drain event rather than ignoring the write result."
patterns_worth_avoiding:
  - "Failing the whole transport on one unparseable line, when the spec does not require it."
  - "The dependency footprint."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target and no code reuse. Studied as a contrast case: it is the only
  one of the three clients that tears the transport down on bad stdout, and it is the one
  whose stdio entry point cannot exist without a third-party dependency.
standards: ["Model Context Protocol"]
last_reviewed: 2026-09-16
```

### mcp-go (independent client)

```yaml
project: mcp-go
repository: https://github.com/mark3labs/mcp-go
authors: mark3labs
license: MIT
version_studied: main branch, client/transport/stdio.go, client/stdio.go (fetched 2026-09-16)
capabilities: >
  An independent Go implementation of MCP, including a stdio client transport written
  entirely against the standard library.
architecture: >
  Blocking API taking a context.Context. The stdio transport wraps the child in a
  bufio.Reader for newline framing, a map of response channels for correlation, a
  drop-oldest ring buffer for stderr, and a bounded shutdown escalation.
strengths:
  - "FACT: imports are the Go standard library only -- bufio, bytes, context, encoding/json, errors, fmt, io, io/fs, log/slog, os, os/exec, runtime, strings, sync, syscall, time -- plus an in-repo package. Its stdio transport is genuinely zero-third-party-dependency."
  - "FACT: stderr defaults to io.Discard and is DRAINED CONTINUOUSLY into a 64 KiB drop-oldest ring buffer, so Write never blocks. The doc comment states the reason exactly: 'the transport drains stderr continuously so that the OS pipe (about 64KB) can never fill up and block the child process, which would deadlock the whole stdio channel.'"
  - "FACT: writes are serialised under a mutex so concurrent SendRequest/SendNotification/sendResponse calls cannot interleave JSON-RPC lines."
  - "FACT: framing tolerates CRLF -- ReadString('\\n') followed by TrimRight(line, '\\r\\n')."
  - "FACT: shutdown is a bounded escalation -- gracefulShutdownTimeout = 2 * time.Second, forceKillTimeout = 3 * time.Second -- and is idempotent via closeOnce."
  - "FACT: an optional CommandFunc seam exists specifically for sandboxing and custom environment control."
weaknesses:
  - "FACT: it inherits the FULL os.Environ() (cmd.Env = append(os.Environ(), c.env...)), the opposite of the Python and TypeScript allowlists. This is the one place where the zero-dependency reference is less safe than the dependency-heavy ones."
  - "FACT: it kills only the direct child (c.cmd.Process), not the process group, so grandchildren leak -- the exact leak the Python SDK's killpg avoids."
  - "OBSERVATION: unparseable stdout lines are silently continue'd. A dropped message produces no diagnostic at all."
  - "FACT: no startup timeout."
patterns_worth_adopting:
  - "The drained drop-oldest stderr ring. This is the single most valuable finding in the client survey: an undrained stderr pipe deadlocks the child, and the failure is invisible on a cooperative server."
  - "Serialised writes, so concurrent sends cannot interleave."
  - "CRLF tolerance in the framing reader."
  - "A bounded, idempotent shutdown escalation with named constants."
patterns_worth_avoiding:
  - "Full environment inheritance -- we should adopt the allowlist the other two use."
  - "Silently discarding an unparseable line with no diagnostic."
  - "Killing only the direct child rather than the process group."
code_reused: false
attribution_requirements: ""
our_implementation: ""
compatibility_status: >
  No compatibility target. This is the closest existing design to what a zero-dependency
  stdio client can be, and it is the primary structural reference for mcp-client. No code
  reused -- the reference is architectural, not textual.
standards: ["Model Context Protocol"]
last_reviewed: 2026-09-16
```


## License compatibility note

All identified Phase-2 study targets are permissive and compatible with this repository's Apache-2.0 license:

| Project | License |
|---|---|
| LangChain, LlamaIndex, AutoGen, CrewAI, DSPy, SWE-agent, Semantic Kernel, OpenAI Swarm | MIT |
| Haystack, MemGPT / Letta | Apache-2.0 |

This table is orientation only — it is **not** a study record. Confirm each license at the version actually studied before setting `code_reused: true` (licenses change).