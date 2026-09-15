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


## License compatibility note

All identified Phase-2 study targets are permissive and compatible with this repository's Apache-2.0 license:

| Project | License |
|---|---|
| LangChain, LlamaIndex, AutoGen, CrewAI, DSPy, SWE-agent, Semantic Kernel, OpenAI Swarm | MIT |
| Haystack, MemGPT / Letta | Apache-2.0 |

This table is orientation only — it is **not** a study record. Confirm each license at the version actually studied before setting `code_reused: true` (licenses change).