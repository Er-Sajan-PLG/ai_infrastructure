# ai_infrastructure Implementation Plan — Filling All Gaps

**Based on:** Gap Analysis Report (2026-10-22)  
**Approach:** Charter lifecycle per capability — RESEARCHED → UNDERSTOOD → DESIGNED → DECIDED → IMPLEMENTED → TESTED  
**Principle:** Zero runtime dependencies, structural independence, protocol-first, default-off capture

---

## Phase Overview

| Phase | Focus | Capabilities | Duration |
|-------|-------|--------------|----------|
| **Phase 5A** | Evaluation & Safety (P0) | Evaluation Framework, Guardrails (deterministic) | 2-3 sessions |
| **Phase 5B** | Production Infrastructure (P1) | Model Gateway, Memory Framework, Multi-Agent Orchestration, Rate Limiting, Prompt Management | 4-6 sessions |
| **Phase 5C** | Ecosystem Integration (P2) | MCP Server, OTel Export, Agent Skills, Harnesses | 2-3 sessions |
| **Phase 5D** | Platform Extensions (P3+) | Config/Settings, Response Cache, Data Pipeline, Fine-tuning, Distributed Execution | Deferred to triggers |

---

## Phase 5A: Evaluation & Safety (P0 — Immediate)

### 5A.1 Evaluation Framework

**ADR Required:** Yes — new capability, independent implementation

**Research Targets (Primary Sources):**
- RAGAS (faithfulness, answer relevance, context precision, context recall)
- TruLens (RAG triad, agent evaluators: LogicalConsistency, ExecutionEfficiency, PlanAdherence, ToolSelection, ToolCalling, ToolQuality)
- DeepEval (G-Eval, faithfulness, hallucination)
- LangSmith evaluators (correctness, coherence, relevance)
- OpenInference semantic conventions for evaluation spans

**Design Decisions (to be recorded in ADR):**
- D-1: **Protocol-first** — `Evaluator` protocol with `evaluate(input, output, context) -> EvaluationResult`
- D-2: **Injected model caller** — same pattern as ReactAgentLoop, enables testing with doubles
- D-3: **Deterministic evaluators first** — schema validation, length checks, citation coverage, exact match; LLM-as-judge as separate adapter
- D-4: **EvaluationResult** — score (0-1), reasoning (optional), metadata, pass/fail threshold
- D-5: **Suite composition** — `EvaluationSuite` runs multiple evaluators, aggregates with weights
- D-6: **TraceRecorder integration** — evaluators consume TraceRecords, not just final output
- D-7: **No network in core** — all model calls injected, stdlib-only

**Implementation Path:**
```
catalog/evaluation/
├── __init__.py
├── protocols.py          # Evaluator, EvaluationSuite, EvaluationResult
├── evaluators/
│   ├── __init__.py
│   ├── deterministic.py  # Schema, length, citation coverage, exact match
│   ├── rag_triad.py      # Faithfulness, answer relevance, context precision/recall
│   └── agent.py          # LogicalConsistency, ExecutionEfficiency, PlanAdherence, ToolSelection, ToolCalling
├── llm_judge.py          # Adapter for LLM-as-judge (injected ModelCaller)
├── aggregation.py        # Weighted average, pass/fail, confidence intervals
├── examples/quickstart.py
└── tests/
    ├── test_evaluation.py
    ├── test_deterministic.py
    ├── test_rag_triad.py
    ├── test_agent_evaluators.py
    └── test_llm_judge.py
```

**Dependencies:** TraceRecorder, ToolRegistry, ModelProvider (injected)
**Estimated Tests:** 80-100
**Effort:** Medium (1-2 sessions)

---

### 5A.2 Guardrails (Deterministic Half)

**ADR Required:** Yes — new capability, independent implementation  
**Note:** DW-016 defers model-backed classifiers; deterministic validators are in scope now

**Research Targets:**
- Guardrails AI validators (regex_match, valid_json, valid_length, one_line, restrict_to_topic, detect_jailbreak, guardrails_pii, toxic_language, competitor_check, provenance_llm)
- NeMo Guardrails input/output rails
- OpenAI moderation API categories
- PII detection patterns (email, phone, SSN, credit card, API keys)

**Design Decisions (to be recorded in ADR):**
- D-1: **Validator protocol** — `Validator.validate(text) -> ValidationResult(pass, message, metadata)`
- D-2: **Policy object** — `GuardrailPolicy(validators: list[Validator], mode: "block" | "rewrite" | "flag")`
- D-3: **Deterministic validators only** — regex, length, JSON schema, PII patterns, allowlist/denylist, topic keywords
- D-4: **Input + Output rails** — separate policies for pre-model and post-model
- D-5: **Integration with ToolRegistry** — validators as tools? No, separate layer; but can wrap ToolRegistry.invoke
- D-6: **Integration with ReactAgentLoop** — optional wrapper around dispatcher
- D-7: **No model calls in core** — stdlib-only; LLM-backed validators are separate adapters (deferred)

**Implementation Path:**
```
catalog/safety/guardrails/
├── __init__.py
├── protocols.py          # Validator, ValidationResult, GuardrailPolicy, GuardrailMode
├── validators/
│   ├── __init__.py
│   ├── regex.py          # RegexMatchValidator
│   ├── length.py         # LengthValidator (min/max chars, tokens)
│   ├── json_schema.py    # JsonSchemaValidator
│   ├── pii.py            # PIIValidator (email, phone, SSN, credit card, API keys)
│   ├── allowlist.py      # AllowlistValidator (topic, word, pattern)
│   ├── denylist.py       # DenylistValidator
│   └── structure.py      # OneLineValidator, ValidJsonValidator
├── policy.py             # GuardrailPolicy, InputRails, OutputRails
├── integration.py        # wrap_dispatcher, wrap_model_caller
├── examples/quickstart.py
└── tests/
    ├── test_validators.py
    ├── test_policy.py
    ├── test_integration.py
    └── test_pii.py
```

**Dependencies:** ToolRegistry (for integration), basic types
**Estimated Tests:** 60-80
**Effort:** Small (1 session)

---

## Phase 5B: Production Infrastructure (P1)

### 5B.1 Model Gateway / Provider Proxy

**ADR Required:** Yes — major capability, enables real provider calls

**Research Targets:**
- LiteLLM (load balancing, fallbacks, cost tracking, 1600+ models)
- Portkey (unified API, caching, guardrails, prompt management, 200+ models)
- OpenRouter (simple routing, community models)
- Vercel AI Gateway (edge caching, frontend integration)
- Kong AI Gateway, Solo.io Gloo, F5, IBM, Azure AI Gateway (enterprise)

**Design Decisions (to be recorded in ADR):**
- D-1: **Gateway protocol** — `Gateway.chat(request) -> ChatResponse`, `Gateway.stream(request) -> Iterator[StreamDelta]`
- D-2: **Provider registry** — register providers with capabilities, models, cost, rate limits
- D-3: **Routing strategies** — priority, round-robin, least-latency, cost-optimized, fallback chain
- D-4: **Load balancing** — per-provider health checks, circuit breaker, retry with backoff
- D-5: **Cost tracking** — token counting, per-model pricing, budget alerts
- D-6: **Request/response logging** — optional, integrates with TraceRecorder
- D-7: **Batch API emulation** — batch completions across providers (Portkey feature)
- D-8: **Zero runtime deps** — stdlib only; HTTP via urllib; no pydantic, no httpx

**Implementation Path:**
```
catalog/models/gateway/
├── __init__.py
├── protocols.py          # Gateway, ProviderEntry, RoutingStrategy
├── registry.py           # ProviderRegistry
├── routing.py            # PriorityRouter, RoundRobinRouter, FallbackRouter, CostRouter
├── load_balancing.py     # CircuitBreaker, HealthCheck, RetryPolicy
├── cost_tracking.py      # CostTracker, PricingTable, BudgetAlert
├── batch.py              # BatchEmulator
├── providers/            # Adapter wrappers for ModelProvider adapters
│   ├── __init__.py
│   ├── openai.py
│   ├── anthropic.py
│   └── gemini.py
├── examples/quickstart.py
└── tests/
    ├── test_gateway.py
    ├── test_routing.py
    ├── test_load_balancing.py
    ├── test_cost_tracking.py
    └── test_batch.py
```

**Dependencies:** ModelProvider, Transport, TraceRecorder (optional), Config (DW-014 or inline)
**Estimated Tests:** 100-150
**Effort:** Large (2-3 sessions)
**Unlocks:** DW-015 (Response Cache), DW-017 (Rate Limiting), real eval/guardrails

---

### 5B.2 Memory Framework (API Class)

**ADR Required:** Yes — new capability, builds on VectorStore

**Research Targets:**
- Mem0 (single-pass ADD-only extraction, entity linking, graph mode removed 2026)
- Zep / Graphiti (temporal knowledge graph, facts with validity periods)
- Letta / MemGPT (virtual context paging, agent-managed memory)
- LangMem (LangGraph checkpointer + store, semantic memory, procedural memory)
- Cognee (evolving knowledge graph from documents + interactions)
- Engram / Weaviate (vector-native memory layer, async extract-transform-commit)
- Supermemory (managed memory API with MCP server)

**Design Decisions (to be recorded in ADR):**
- D-1: **Memory API protocol** — `Memory.add(text, metadata)`, `Memory.search(query)`, `Memory.consolidate()`, `Memory.evict(policy)`
- D-2: **Extraction** — LLM-based fact extraction (injected ModelCaller), deduplication, entity resolution
- D-3: **Consolidation** — merge related facts, resolve contradictions, temporal validity
- D-4: **Eviction policies** — LRU, TTL, importance-based, capacity-based
- D-5: **Scoping** — per-user, per-session, per-agent, global
- D-6: **VectorStore as backend** — Memory composes VectorStore, not replaces it
- D-7: **No model calls in core** — extraction/consolidation injected

**Implementation Path:**
```
catalog/memory/framework/
├── __init__.py
├── protocols.py          # Memory, Extractor, Consolidator, EvictionPolicy
├── memory.py             # MemoryAPI (composes VectorStore)
├── extraction.py         # FactExtractor, EntityResolver, Deduplicator
├── consolidation.py      # FactConsolidator, TemporalResolver
├── eviction.py           # LRUEviction, TTLEviction, ImportanceEviction
├── scoping.py            # UserScope, SessionScope, AgentScope, GlobalScope
├── examples/quickstart.py
└── tests/
    ├── test_memory.py
    ├── test_extraction.py
    ├── test_consolidation.py
    ├── test_eviction.py
    └── test_scoping.py
```

**Dependencies:** VectorStore, ModelProvider (injected for extraction), EvaluationFramework (for quality)
**Estimated Tests:** 80-100
**Effort:** Medium (1-2 sessions)

---

### 5B.3 Multi-Agent Orchestration (Graph-Based)

**ADR Required:** Yes — major capability, new orchestration model

**Research Targets:**
- LangGraph (stateful graph, TypedDict + Annotated, checkpointing, human-in-the-loop)
- CrewAI (role-based crews, flows, delegation, event-driven)
- AutoGen / Microsoft Agent Framework (message-passing, group chat, Magentic-One)
- AWS Strands (graph-based, native tool calling)
- Google ADK (hierarchical agents, planning)

**Design Decisions (to be recorded in ADR):**
- D-1: **Graph protocol** — `Graph.add_node(name, agent)`, `Graph.add_edge(from, to, condition)`, `Graph.compile() -> Runnable`
- D-2: **State management** — TypedDict state, reducers for merging, checkpointing protocol
- D-3: **Agent as node** — wraps ReactAgentLoop or any ModelCaller+ToolDispatcher
- D-4: **Coordination patterns** — supervisor, swarm, hierarchical, delegation, map-reduce
- D-5: **Human-in-the-loop** — interrupt, approve, modify state
- D-6: **Streaming** — stream node outputs, stream state changes
- D-7: **Composes existing primitives** — ReactAgentLoop, ToolRegistry, ModelProvider, TraceRecorder
- D-8: **Zero runtime deps** — stdlib only; checkpointing to file/JSONL

**Implementation Path:**
```
catalog/orchestration/graph/
├── __init__.py
├── protocols.py          # Graph, Node, Edge, State, Checkpointer, Runnable
├── graph.py              # GraphBuilder, CompiledGraph
├── state.py              # StateSchema, Reducer, Checkpoint
├── patterns.py           # Supervisor, Swarm, Hierarchical, Delegation, MapReduce
├── nodes.py              # AgentNode, ToolNode, HumanNode, ConditionalNode
├── checkpointing.py      # FileCheckpointer, JSONLCheckpointer
├── streaming.py          # StreamMode, NodeStream, StateStream
├── examples/quickstart.py
└── tests/
    ├── test_graph.py
    ├── test_patterns.py
    ├── test_checkpointing.py
    ├── test_streaming.py
    └── test_human_in_loop.py
```

**Dependencies:** ReactAgentLoop, ToolRegistry, ModelProvider, TraceRecorder, EvaluationFramework
**Estimated Tests:** 120-180
**Effort:** Large (2-3 sessions)

---

### 5B.4 Rate Limiting & Circuit Breaker

**ADR Required:** Yes — DW-017 deferred, now implementable with ModelGateway

**Research Targets:**
- AWS exponential backoff + jitter patterns [10]
- Circuit breaker pattern (CLOSED/OPEN/HALF_OPEN)
- Token bucket algorithm
- Leaky bucket algorithm
- Google GenAI SDK retry strategy
- Resilience4j, Polly patterns

**Design Decisions (to be recorded in ADR):**
- D-1: **RateLimiter protocol** — `acquire(tokens=1) -> bool`, `release(tokens=1)`
- D-2: **TokenBucket** — capacity, refill_rate, thread-safe
- D-3: **CircuitBreaker** — failure_threshold, timeout, half_open_requests
- D-4: **RetryPolicy** — max_attempts, base_delay, max_delay, jitter, retryable_errors
- D-5: **Integration** — wraps ModelGateway.chat/stream, ModelProvider.chat/stream
- D-6: **Per-model / per-provider policies** — different limits for different providers
- D-7: **Observability** — emits TraceRecorder events for limit hits, breaker trips

**Implementation Path:**
```
catalog/reliability/
├── __init__.py
├── protocols.py          # RateLimiter, CircuitBreaker, RetryPolicy
├── token_bucket.py       # TokenBucketRateLimiter
├── circuit_breaker.py    # CircuitBreaker (CLOSED/OPEN/HALF_OPEN)
├── retry.py              # ExponentialBackoffRetry, Jitter
├── integration.py        # wrap_gateway, wrap_provider
├── examples/quickstart.py
└── tests/
    ├── test_token_bucket.py
    ├── test_circuit_breaker.py
    ├── test_retry.py
    └── test_integration.py
```

**Dependencies:** ModelProvider (errors), ModelGateway, TraceRecorder (optional)
**Estimated Tests:** 50-70
**Effort:** Small (1 session)

---

### 5B.5 Prompt Management

**ADR Required:** Yes — new capability, stdlib implementable

**Research Targets:**
- Langfuse prompt management (versioning, A/B testing, templates, rollback)
- Portkey prompt management
- LangSmith prompts
- Jinja2 templating (but stdlib-only → use string.Template or custom)

**Design Decisions (to be recorded in ADR):**
- D-1: **Prompt template** — `PromptTemplate(name, version, template_str, variables)`
- D-2: **Registry** — `PromptRegistry.get(name, version=None)`, `register(template)`
- D-3: **Versioning** — semantic versioning, immutable once registered
- D-4: **A/B testing** — `PromptExperiment(variants, traffic_split)`, `track_result(variant, score)`
- D-5: **Templating** — stdlib `string.Template` or custom `{{var}}` syntax
- D-6: **Storage** — file-based (JSONL), injectable backend
- D-7: **Integration** — `PromptRegistry.render(name, variables)` used in AgentLoop, RAG, etc.

**Implementation Path:**
```
catalog/prompt_engineering/
├── __init__.py
├── protocols.py          # PromptTemplate, PromptRegistry, PromptExperiment
├── template.py           # PromptTemplate, render, validate_variables
├── registry.py           # FilePromptRegistry, InMemoryPromptRegistry
├── experimentation.py    # PromptExperiment, Variant, ResultTracker
├── integration.py        # render_for_agent, render_for_rag
├── examples/quickstart.py
└── tests/
    ├── test_template.py
    ├── test_registry.py
    ├── test_experimentation.py
    └── test_integration.py
```

**Dependencies:** Config (DW-014 or inline file storage), TraceRecorder (optional)
**Estimated Tests:** 40-60
**Effort:** Small (1 session)

---

## Phase 5C: Ecosystem Integration (P2)

### 5C.1 MCP Server

**ADR Required:** Yes — COMPATIBILITY (implementing MCP server protocol)

**Research Targets:**
- MCP specification (server side)
- MCP Python SDK server
- MCP TypeScript SDK server
- 31,595+ existing servers [9] — analyze patterns

**Design Decisions (to be recorded in ADR):**
- D-1: **Server protocol** — `MCPServer.handle_request(request) -> Response`
- D-2: **Tool registration** — `MCPServer.register_tool(name, description, schema, handler)`
- D-3: **Resource support** — `MCPServer.register_resource(uri, mime_type, handler)`
- D-4: **Prompt support** — `MCPServer.register_prompt(name, description, handler)`
- D-5: **Stdio transport** — reuse framing from MCPClient
- D-6: **ToolRegistry projection** — export local ToolRegistry as MCP tools
- D-7: **Approval seam** — server-side approval for dangerous operations

**Implementation Path:**
```
catalog/protocols/mcp_server/
├── __init__.py
├── protocols.py          # MCPServer, ToolHandler, ResourceHandler, PromptHandler
├── server.py             # MCPServer implementation
├── registry.py           # ToolRegistryAdapter, ResourceRegistry, PromptRegistry
├── transport.py          # StdioServerTransport (reuse framing)
├── examples/quickstart.py
└── tests/
    ├── test_server.py
    ├── test_registry.py
    ├── test_transport.py
    └── test_integration.py
```

**Dependencies:** MCPClient (framing, jsonrpc), ToolRegistry, TraceRecorder
**Estimated Tests:** 60-80
**Effort:** Medium (1-2 sessions)

---

### 5C.2 OTel / OpenInference Export

**ADR Required:** Yes — COMPATIBILITY (export to standard)

**Research Targets:**
- OpenTelemetry GenAI semantic conventions
- OpenInference specification
- OTel Python SDK (but zero runtime deps → emit JSONL in OTel format)

**Design Decisions (to be recorded in ADR):**
- D-1: **Export protocol** — `Exporter.export(records) -> None`
- D-2: **OTel format** — map TraceRecord to OTel spans with GenAI attributes
- D-3: **OpenInference format** — map to OpenInference span attributes
- D-4: **Batch export** — buffer and flush periodically
- D-5: **Transport** — stdout, file, HTTP (stdlib urllib)
- D-6: **No OTel SDK dependency** — emit compliant JSON, not use SDK

**Implementation Path:**
```
catalog/observability/otel_export/
├── __init__.py
├── protocols.py          # Exporter, OTelExporter, OpenInferenceExporter
├── mapping.py            # TraceRecord -> OTel Span, OpenInference Span
├── transport.py          # StdoutTransport, FileTransport, HTTPTransport
├── batching.py           # BatchExporter
├── examples/quickstart.py
└── tests/
    ├── test_mapping.py
    ├── test_transport.py
    └── test_batching.py
```

**Dependencies:** TraceRecorder
**Estimated Tests:** 30-50
**Effort:** Small (1 session)

---

### 5C.3 Agent Skills & Harnesses

**ADR Required:** Yes — two related capabilities

**Research Targets:**
- LangChain tools/skills
- LangGraph prebuilt agents
- CrewAI tools
- AutoGen skills
- Semantic Kernel skills

**Design Decisions (to be recorded in ADR):**
- D-1: **Skill protocol** — `Skill(name, description, tools: list[ToolId], prompt_template?)`
- D-2: **Skill registry** — composable, versioned, dependency-aware
- D-3: **Harness protocol** — `Harness.run(agent, scenario) -> EvaluationResult`
- D-4: **Scenario** — input, expected_output, expected_tool_calls, max_steps
- D-5: **Harness types** — unit (single agent), integration (multi-agent), regression (golden traces)
- D-6: **CI integration** — JUnit XML output, pass/fail thresholds

**Implementation Path:**
```
catalog/skills/
├── __init__.py
├── protocols.py          # Skill, SkillRegistry, SkillDependency
├── registry.py           # SkillRegistry
├── composition.py        # compose_skills, resolve_dependencies
├── examples/quickstart.py
└── tests/
    ├── test_skill.py
    └── test_registry.py

catalog/harnesses/
├── __init__.py
├── protocols.py          # Harness, Scenario, HarnessResult
├── harness.py            # BaseHarness, UnitHarness, IntegrationHarness
├── scenario.py           # Scenario, ExpectedOutput, ExpectedToolCalls
├── reporting.py          # JUnitXMLReporter, SummaryReporter
├── examples/quickstart.py
└── tests/
    ├── test_harness.py
    ├── test_scenario.py
    └── test_reporting.py
```

**Dependencies:** ToolRegistry, ReactAgentLoop, EvaluationFramework, Orchestration
**Estimated Tests:** 80-120
**Effort:** Medium (1-2 sessions)

---

## Phase 5D: Platform Extensions (P3+ — Deferred to Triggers)

| Capability | Trigger | ADR | Effort |
|------------|---------|-----|--------|
| Config & Settings (DW-014) | First consumer needs layered resolution | Yes | Medium |
| Response Cache (DW-015) | First metered call / repeated workload | Yes | Medium |
| Data Pipeline / ETL | RAG needs data prep, versioning | Yes | Large |
| Fine-tuning Infrastructure | Checkpoint management, training loops | Yes | Large |
| Distributed Execution | Durable execution, scheduling, checkpointing | Yes | Large |

---

## Detailed Session Plan

### Session 1: Evaluation Framework (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: RAGAS, TruLens, DeepEval, LangSmith evaluators
2. Write specification: `specifications/evaluation-framework.md`
3. Write ADR: `docs/decisions/0037-evaluation-framework.md`
4. Implement: `catalog/evaluation/`
5. Tests: 80-100 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 2: Guardrails Deterministic (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: Guardrails AI, NeMo Guardrails validators
2. Write specification: `specifications/guardrails.md`
3. Write ADR: `docs/decisions/0038-guardrails-deterministic.md`
4. Implement: `catalog/safety/guardrails/`
5. Tests: 60-80 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 3-4: Model Gateway (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: LiteLLM, Portkey, OpenRouter, gateway patterns
2. Write specification: `specifications/model-gateway.md`
3. Write ADR: `docs/decisions/0039-model-gateway.md`
4. Implement: `catalog/models/gateway/`
5. Tests: 100-150 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 5-6: Memory Framework (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: Mem0, Zep, Letta, LangMem, Cognee, Engram
2. Write specification: `specifications/memory-framework.md`
3. Write ADR: `docs/decisions/0040-memory-framework.md`
4. Implement: `catalog/memory/framework/`
5. Tests: 80-100 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 7-9: Multi-Agent Orchestration (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: LangGraph, CrewAI, AutoGen/MAF, Strands, ADK
2. Write specification: `specifications/multi-agent-orchestration.md`
3. Write ADR: `docs/decisions/0041-multi-agent-orchestration.md`
4. Implement: `catalog/orchestration/graph/`
5. Tests: 120-180 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 10: Rate Limiting & Circuit Breaker (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: AWS patterns, circuit breaker, token bucket
2. Write specification: `specifications/rate-limiting.md` (update existing)
3. Write ADR: `docs/decisions/0042-rate-limiting-circuit-breaker.md`
4. Implement: `catalog/reliability/`
5. Tests: 50-70 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 11: Prompt Management (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: Langfuse, Portkey, LangSmith prompt management
2. Write specification: `specifications/prompt-management.md`
3. Write ADR: `docs/decisions/0043-prompt-management.md`
4. Implement: `catalog/prompt_engineering/`
5. Tests: 40-60 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 12: MCP Server (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: MCP server spec, existing servers
2. Write specification: `specifications/mcp-server.md`
3. Write ADR: `docs/decisions/0044-mcp-server.md`
4. Implement: `catalog/protocols/mcp_server/`
5. Tests: 60-80 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 13: OTel/OpenInference Export (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: OTel GenAI, OpenInference spec
2. Write specification: `specifications/otel-export.md`
3. Write ADR: `docs/decisions/0045-otel-export.md`
4. Implement: `catalog/observability/otel_export/`
5. Tests: 30-50 tests
6. Update TAXONOMY.md, add to unified package exports

### Session 14-15: Agent Skills & Harnesses (RESEARCHED → DESIGNED → DECIDED → IMPLEMENTED → TESTED)
1. Research: LangChain, LangGraph, CrewAI, AutoGen skills
2. Write specification: `specifications/agent-skills.md`, `specifications/agent-harnesses.md`
3. Write ADRs: `docs/decisions/0046-agent-skills.md`, `0047-agent-harnesses.md`
4. Implement: `catalog/skills/`, `catalog/harnesses/`
5. Tests: 80-120 tests
6. Update TAXONOMY.md, add to unified package exports

---

## Integration Compositions (Post-Capability)

After each major capability, create integration compositions:

| Integration | Composes | Purpose |
|-------------|----------|---------|
| `eval_agent_loop` | EvaluationFramework + ReactAgentLoop + TraceRecorder | Evaluate agent runs |
| `guarded_agent` | Guardrails + ReactAgentLoop + ModelGateway | Safe agent with validation |
| `memory_rag` | MemoryFramework + BasicRagPipeline + ModelGateway | RAG with persistent memory |
| `multi_agent_system` | Orchestration + ModelGateway + EvaluationFramework | Production multi-agent |
| `mcp_e2e` | MCPClient + MCPServer + ToolRegistry | Full MCP loop |
| `observability_stack` | TraceRecorder + OTelExport + EvaluationFramework | Full observability |

---

## Gate Enforcement for New Capabilities

Each new capability must pass:
- `make check` — lint, typecheck, catalog contract, tests
- `make status` — taxonomy drift detection
- `make ci` — full CI gate (including structural, SCA, licence, risks, deferred)
- Coverage ≥ 85% (enforced by `--cov-fail-under=85`)
- Import-linter contracts — independence maintained
- `validate_catalog.py` — entry has tests, examples, README, PROVENANCE

---

## Unified Package Maintenance

For each new capability added to `catalog/<category>/<name>/`:
1. Add exports to `ai_infrastructure/__init__.py`
2. Update `pyproject.toml` coverage source if new directory
3. Add to `catalog/` in wheel packages
4. Run `make check` and `make status` to verify

---

## Risk Register Updates

| Risk | Mitigation |
|------|------------|
| Scope creep in ModelGateway | Strict ADR scope: routing + load balancing + cost tracking only; no prompt management, no fine-tuning |
| Multi-agent orchestration complexity | Start with Supervisor pattern only; add Swarm/Hierarchical in follow-up |
| Memory framework LLM extraction quality | Deterministic extractors first; LLM extraction as injected adapter |
| Evaluation framework LLM-as-judge reliability | Deterministic evaluators primary; LLM judge advisory, not blocking |
| Zero-deps constraint on HTTP | Use urllib; document limitations; defer advanced HTTP to DW-015/DW-017 triggers |

---

## Success Criteria

**Phase 5A Complete:**
- [ ] Evaluation Framework: TESTED, 80+ tests, integrated with TraceRecorder
- [ ] Guardrails (deterministic): TESTED, 60+ tests, integrated with ToolRegistry/ReactAgentLoop

**Phase 5B Complete:**
- [ ] Model Gateway: TESTED, 100+ tests, routes to 3+ providers with fallbacks
- [ ] Memory Framework: TESTED, 80+ tests, composes VectorStore
- [ ] Multi-Agent Orchestration: TESTED, 120+ tests, Supervisor + Swarm patterns
- [ ] Rate Limiting: TESTED, 50+ tests, integrates with ModelGateway
- [ ] Prompt Management: TESTED, 40+ tests, versioning + A/B testing

**Phase 5C Complete:**
- [ ] MCP Server: TESTED, 60+ tests, interoperates with MCPClient
- [ ] OTel Export: TESTED, 30+ tests, emits valid OTel/OpenInference
- [ ] Agent Skills + Harnesses: TESTED, 80+ tests, JUnit XML output

**Overall:**
- [ ] All 20+ capabilities TESTED across 15+ categories
- [ ] 2,500+ tests passing
- [ ] Coverage ≥ 85%
- [ ] 5+ integration compositions
- [ ] Unified package exports 200+ symbols
- [ ] `make ci` green on every commit