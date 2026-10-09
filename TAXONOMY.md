# TAXONOMY.md — Infrastructure Taxonomy & Capability Registry

The machine-readable maps of this repository (charter §14):

1. **The taxonomy tree** — what categories of AI infrastructure exist (charter §2).
2. **The capability registry** — every tracked capability, its lifecycle stage, priority, and where its artifacts live.

**Honesty rule (charter §4):** `status` must reflect artifacts that actually exist. A `status: TESTED` entry with no `tests:` path is a bug in this file.

---

## 1. Taxonomy Tree

```text
agents/                Agents & Orchestration
skills/                Agent Skills
harnesses|harness/     Agent Harnesses (research/ uses harnesses, catalog/ uses harness)
tools/                 Tools
mcp|protocols/         MCP & Protocols (research/ uses mcp, catalog/ uses protocols)
models/                Models
memory/                Context & Memory
retrieval/             Retrieval & Knowledge
evaluation/            Evaluation
safety/ (+governance/) Safety & Governance
guardrails/            Guardrails & Output Validation (added Phase 3, ADR-0031)
reliability/           Rate Limiting & Retry Infrastructure (added Phase 3, ADR-0032)
orchestration/         Workflow & Distributed Infrastructure
observability/         Observability
data/                  Data
development/           Development Infrastructure (research/ only, for now)
deployment/            Deployment
application/           AI Application Infrastructure (research/ only, for now)
prompt-engineering/    Prompt Engineering Primitives (catalog: prompt_engineering naming TBD on first entry)
finetuning/            Fine-tuning Infrastructure
| config/                | Configuration & Settings Infrastructure (added Phase 2, ADR-0022) |
| caching/               | Caching Infrastructure (added Phase 2, ADR-0023) |
| agent-config/          | Agent Repository Configuration (added Phase 2, ADR-0024) |
| evidence-plane/        | Execution Evidence Plane (added Phase 2, ADR-0025) |
| evaluation/            | Evaluation & Verification Architecture (added Phase 2, ADR-0026) |
| worker-contract/       | Worker/Agent Execution Contracts (added Phase 2, ADR-0027) |
emerging/              Emerging / Other (research/ only)
frameworks/            Distilled essence of full frameworks (catalog/ only)
primitives/            Shared low-level building blocks (catalog/ only)
runtime/               Shared runtime substrate (catalog/ only)
```

New categories are added by editing this file and creating the directory — an explicit taxonomy change, not a side effect (charter §2, §25).

## 2. Capability Entry Schema

Each entry in the registry below follows this schema (charter §14):

```yaml
id:                    # kebab-case, stable — never renamed once referenced
name:
category:              # taxonomy tree leaf above
status:                # DISCOVERED | RESEARCHED | UNDERSTOOD | DESIGNED | DECIDED
                       # | PROTOTYPED | IMPLEMENTED | TESTED | BENCHMARKED
                       # | INTEGRATED | MATURE | DEPRECATED
maturity:              # experimental | stable | deprecated  (independent of status)
priority:              # high | medium | low + WHY (see charter §24)
depends_on:            # [ids] that must exist first
decision:              # IMPLEMENT | ADAPT | COMPATIBILITY | PROTOTYPE | DOCUMENT | DEFER | REJECT | pending
description:
problem:
inputs:
outputs:
interfaces:
dependencies:
standards:
reference_projects:    # ids of entries in docs/registry/RESEARCH_REGISTRY.md
research_records:
implementation:        # path in catalog/ — "" if none
tests:
benchmarks:
security:
license:
provenance:            # inspired-by | derived-from | original
compatibility:
last_reviewed:         # YYYY-MM-DD
```

Fill every field. Use `""` or `[]` for not-applicable or absent; empty means "not yet", never pretend otherwise.

## 3. Decision Legend

| Decision | Meaning |
|---|---|
| IMPLEMENT | Independent implementation justified |
| ADAPT | Wrap/use an existing implementation |
| COMPATIBILITY | Interface/protocol implementation for interop |
| PROTOTYPE | Build only to validate an architectural hypothesis |
| DOCUMENT | Research, don't implement |
| DEFER | Valuable, but prerequisites/evidence insufficient |
| REJECT | Unjustified complexity or poor fit |

---

## 4. Capability Registry

Seeded with candidate Phase-1 capabilities. All are `DISCOVERED`, `decision: pending`, with **no artifacts yet** — nothing here has been studied or built. Priorities below are proposals to be re-derived by evidence (charter §24), not commitments.

```yaml
capabilities:

  - id: tool-registry
    name: Tool Registry & Function Calling Primitive
    category: tools
    status: TESTED
    maturity: experimental
    priority: high — a named call graph: model-agnostic tool schema/invocation/result handling; nearly every downstream capability (agents, harnesses, MCP) consumes it.
    depends_on: []
    decision: IMPLEMENT — standalone, JSON-Schema-native registry with zero runtime dependencies (ADR-0006)
    description: Register, describe, validate, and invoke tools/functions with typed schemas; surface call failures deterministically.
    problem: Give agents and runtimes a uniform, inspectable, validated boundary between model intent and executable behavior.
    inputs: ["tool definitions", "call arguments"]
    outputs: ["tool results", "validation/execution failures"]
    interfaces: ["ToolRegistry.register", "ToolRegistry.invoke", "ToolRegistry.describe", "ToolRegistry.ids"]
    dependencies: []
    standards: ["JSON Schema 2020-12 (documented subset — see ADR-0006)"]
    reference_projects: ["OpenAI function calling / tools", "LangChain / LangGraph", "Model Context Protocol", "Microsoft Semantic Kernel"]
    research_records: ["research/tools/tool-registry.md"]
    implementation: "catalog/tools/tool_registry"
    tests: "catalog/tools/tool_registry/tests"
    benchmarks: ""
    security: "catalog/tools/tool_registry/README.md#the-injection-boundary"
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-09-15"

  - id: model-provider-abstraction
    name: Model Provider Abstraction
    category: models
    status: TESTED
    maturity: experimental
    priority: high — everything above depends on a minimal LLM call interface; the narrow slice is text-in/text-out with errors and token metadata.
    depends_on: []
    decision: IMPLEMENT — shape-owning, transport-injected; zero runtime dependencies; sync-only core (ADR-0007)
    description: A minimal, vendor-neutral interface for chat/completion calls with streaming, error normalization, and usage metadata.
    problem: Components must not hard-code one provider's SDK, error shapes, or streaming model.
    inputs: ["messages/prompts", "generation parameters"]
    outputs: ["completions", "token usage", "provider errors normalized"]
    interfaces: []
    dependencies: []
    standards: ["OpenAI Chat Completions wire format", "Anthropic Messages API", "Google Gemini GenerateContent v1beta", "Server-Sent Events"]
    reference_projects: ["LiteLLM", "OpenAI Python SDK (provider client design)", "LangChain BaseChatModel", "LlamaIndex LLM"]
    research_records: ["research/models/model-provider-abstraction.md"]
    implementation: "catalog/models/model_provider"
    tests: "catalog/models/model_provider/tests"
    benchmarks: ""
    security: "catalog/models/model_provider/README.md#failure-taxonomy--by-caller-actionable-category"
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-09-15"

  - id: react-agent-loop
    name: ReAct Agent Loop
    category: agents
    status: TESTED
    maturity: experimental
    priority: high — canonical first agent pattern; exercises model abstraction + tool registry together; classic first end-to-end proof of composition.
    depends_on: [tool-registry, model-provider-abstraction]
    decision: IMPLEMENT — a bounded dispatcher with injected protocols; sync-only; consecutive-repeat detection and bounded observations (ADR-0008)
    description: Reason-act-observe loop: interleaved reasoning traces and tool calls until termination.
    problem: Simplest agent control loop that grounds LLM output in tool interaction with a clear termination condition.
    inputs: ["task", "tool registry", "model"]
    outputs: ["final answer", "step trace", "stop reason"]
    interfaces: ["run", "Agent", "AgentResult", "StopReason", "ModelCaller", "ToolDispatcher", "ProviderCaller", "RegistryDispatcher"]
    dependencies: []
    standards: []
    reference_projects: ["ReAct (Yao et al.)", "LangGraph react agent executor", "OpenAI Agents SDK", "smolagents", "LangChain tool error surface"]
    research_records: ["research/agents/react-agent-loop.md"]
    implementation: "catalog/agents/react_agent_loop"
    tests: "catalog/agents/react_agent_loop/tests"
    benchmarks: ""
    security: "catalog/agents/react_agent_loop/README.md#security"
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-09-15"

  - id: vector-memory-store
    name: In-Memory Vector Memory Store
    category: memory
    status: DISCOVERED
    maturity: experimental
    priority: medium — needed by retrieval and memory work, but a dict+numpy slice serves until real demand appears (charter §24.2).
    depends_on: []
    decision: pending
    description: Minimal embedding store: add, similarity-search, evict; the seam for later pluggable vector backends.
    problem: Agents and RAG need a memory interface without committing to an external vector DB (out of scope).
    inputs: ["text + embeddings"]
    outputs: ["ranked nearest items"]
    interfaces: []
    dependencies: []
    standards: []
    reference_projects: []
    research_records: []
    implementation: ""
    tests: ""
    benchmarks: ""
    security: ""
    license: Apache-2.0
    provenance: original
    last_reviewed: ""

  - id: basic-rag-pipeline
    name: Basic RAG Pipeline
    category: retrieval
    status: DISCOVERED
    maturity: experimental
    priority: medium — depends on vector store and model abstraction; documents ingest→chunk→retrieve→answer end-to-end.
    depends_on: [vector-memory-store, model-provider-abstraction]
    decision: pending
    description: Chunk → embed → store → retrieve → augment prompt → generate, with citations to source chunks.
    problem: Ground model answers in provided documents with inspectable retrieval.
    inputs: ["documents", "query"]
    outputs: ["answer", "retrieved chunks with sources"]
    interfaces: []
    dependencies: []
    standards: []
    reference_projects: []
    research_records: []
    implementation: ""
    tests: ""
    benchmarks: ""
    security: ""
    license: Apache-2.0
    provenance: original
    last_reviewed: ""

  - id: mcp-client
    name: MCP Client (stdio transport)
    category: mcp
    status: TESTED
    maturity: experimental
    priority: medium — COMPATIBILITY candidate (charter §16): MCP is an established protocol; a thin working client beats a comprehensive never-finished one (§24.4).
    depends_on: [tool-registry]
    decision: COMPATIBILITY (ADR-0009) — legacy era only; approval decision before every dispatch
    description: Connect to an MCP server over stdio, list tools, call tools, surface results into the local tool registry.
    problem: Interoperate with the MCP ecosystem instead of inventing a private tool protocol.
    inputs: ["server command/config", "tool calls"]
    outputs: ["tool listings", "tool results"]
    interfaces: ["MCPClient", "Transport", "ApprovalPolicy", "ApprovalRequest", "ToolCallOutcome", "project_tools", "ProjectionReport", "StdioTransport"]
    dependencies: ["Python standard library only (no runtime dependency)"]
    standards: ["Model Context Protocol", "JSON-RPC 2.0", "JSON Schema 2020-12 (documented subset)"]
    reference_projects: ["Model Context Protocol", "MCP Python SDK (official client)", "MCP TypeScript SDK (official client)", "mcp-go (independent client)"]
    research_records: ["research/mcp/mcp-client.md"]
    implementation: "catalog/protocols/mcp_client"
    tests: "catalog/protocols/mcp_client/tests"
    benchmarks: ""
    security: "Mandatory approval seam (default denies); no shell; client-minted namespace; stderr drained but never an error signal; tool annotations untrusted. Not a sandbox for the server."
    license: Apache-2.0
    provenance: original
    compatibility: "Legacy MCP era only (2025-11-25 and earlier). A modern-only (2026-07-28+) server is reported as a named protocol error, not retried."
    last_reviewed: "2026-09-16"
  - id: execution-trace-recorder
    name: Agent Trajectory / Execution Trace Recorder
    category: observability
    status: TESTED
    maturity: experimental
    priority: medium — needed to evaluate and debug agents honestly (charter §18); simple JSONL recorder first.
    depends_on: []
    decision: IMPLEMENT (ADR-0010) — flat JSONL records; content capture off by default; a write failure is counted, never raised
    description: Record structured traces of agent/model/tool steps with timing and token usage for replay and evaluation.
    problem: Without traces, agent behavior cannot be tested, evaluated, or debugged with evidence.
    inputs: ["step events", "model calls", "tool calls"]
    outputs: ["JSONL traces"]
    interfaces: ["TraceRecorder", "TraceRecord", "RecordKind", "Outcome", "Clock", "CapturePolicy", "Bounds"]
    dependencies: ["Python standard library only (no runtime dependency)"]
    standards: ["OpenTelemetry GenAI semantic conventions (Development — studied, correspondence documented, NOT conformed to)"]
    reference_projects: ["OpenTelemetry GenAI semantic conventions", "Langfuse", "LangSmith", "MLflow (tracing)", "AgentOps", "OpenInference"]
    research_records: ["research/observability/execution-trace-recorder.md"]
    implementation: "catalog/observability/execution_trace_recorder"
    tests: "catalog/observability/execution_trace_recorder/tests"
    benchmarks: ""
    security: "Content capture OFF by default as a policy object; never a '__REDACTED__' sentinel. Every string bounded before writing. An unserialisable or cyclic payload cannot kill the run. A write failure is counted and inspectable, never raised — it cannot kill the run it observes."
    license: Apache-2.0
    provenance: original
    compatibility: "No conformance to any standard claimed: the OTel GenAI conventions are Development, moved repositories, have no published schema URL, and reversed one content-capture decision. specifications/execution-trace-recorder.md s4 publishes a correspondence table instead."
    last_reviewed: "2026-09-16"

  - id: infrastructure-scanner
    name: Infrastructure Scanner
    category: deployment
    status: TESTED
    maturity: experimental
    priority: medium — needed by AI agents that require infrastructure context before generating code; also consumed by the study pipeline's stack detection.
    depends_on: []
    decision: IMPLEMENT (ADR-0029) — deterministic 12-layer detection, zero runtime deps, optional LLM enhancement
    description: Automatically detect and classify infrastructure components across 12 layers (identity, transaction, state, data, communication, delivery, observability, security, deployment, integration, UX, governance) using keyword scanning, config parsing, and optional LLM enhancement.
    problem: Infrastructure is implicit in most codebases — answering "what infrastructure does this project use?" requires manual code archaeology.
    inputs: ["repository filesystem path"]
    outputs: ["InfraMap with layers_covered, total_components, layer_summary, components"]
    interfaces: ["InfrastructureScanner", "InfraMap", "InfraComponent", "ScanConfig"]
    dependencies: ["Python standard library only (no runtime dependency)"]
    standards: []
    reference_projects: ["AWS Well-Architected Framework", "CNCF Cloud Native Landscape", "Twelve-Factor App Methodology"]
    research_records: ["research/deployment/infrastructure-scanner.md"]
    implementation: "catalog/deployment/scanner"
    tests: "catalog/deployment/scanner/tests"
    benchmarks: ""
    security: "Read-only — never modifies scanned repository. No execution of scanned code. Path traversal bounded. Secret values never logged. LLM layer is opt-in."
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-10-01"

  # ---------------------------------------------------------------------
  # Discovered in Phase 2 Track 2B (25 repositories studied at pinned
  # commits). Each of these categories was ABSENT from the taxonomy tree
  # before this phase. Each is recorded with decision: pending, because
  # being found in many repositories is evidence that the pattern EXISTS,
  # not that it is worth building here (charter §24).
  # ---------------------------------------------------------------------

  - id: config-and-settings
    name: Configuration & Settings Infrastructure
    category: config
    status: DISCOVERED
    maturity: experimental
    priority: low — proposed by 15 of 25 studied repositories, but ubiquity is partly a Python packaging convention rather than an AI-infrastructure signal. Re-derive from evidence before acting (charter §24).
    depends_on: []
    decision: pending
    description: Settings objects and their validation, environment-variable loading and precedence, layered/overridden configuration, per-environment profiles, and secret referencing (not secret storage).
    problem: Every service needs configuration resolved from several sources with a defined precedence, and hand-rolled os.environ lookups scattered through a codebase make failure modes untraceable.
    inputs: ["environment variables", "config files", "defaults"]
    outputs: ["validated settings object"]
    interfaces: []
    dependencies: []
    standards: []
    reference_projects: []
    research_records: ["study_pipeline/studied_repos/ (15 of 25 reports propose this category)"]
    implementation: ""
    tests: ""
    benchmarks: ""
    security: "Referencing a secret is in scope; storing or rotating one is not. A configuration layer that logs resolved values leaks credentials — that risk is stated rather than assumed away."
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-09-17"

  - id: response-cache
    name: Response Caching
    category: caching
    status: DISCOVERED
    maturity: experimental
    priority: low — proposed by 14 of 25; the weakest of the three Phase 2 categories, since caching is general software infrastructure and only its AI-specific form (keyed on prompt + model + parameters, avoiding a metered API call) is in scope here.
    depends_on: []
    decision: pending
    description: Caching of model responses, embeddings and tool results; cache-key derivation, eviction policy, TTL and invalidation, in-process vs persistent storage.
    problem: An identical request billed twice is pure waste, but a cache keyed on the wrong inputs silently returns a wrong answer for a different prompt.
    inputs: ["request (prompt, model, parameters)"]
    outputs: ["cached response, or a miss"]
    interfaces: []
    dependencies: []
    standards: []
    reference_projects: []
    research_records: ["study_pipeline/studied_repos/ (14 of 25 reports propose this category, after the vector_stores false positive was fixed)"]
    implementation: ""
    tests: ""
    benchmarks: ""
    security: "A cache is a data-retention boundary: a prompt cached across tenants leaks one tenant's content to another. Key derivation must include every input that changes the answer — that is the correctness and the security property alike."
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-09-17"

  - id: agent-instruction-files
    name: Agent Repository Configuration
    category: agent-config
    status: DISCOVERED
    maturity: experimental
    priority: medium — the clearest new finding of Phase 2: AGENTS.md appears in 18 of 25 studied repositories (72%), and unlike configuration this practice is both common and recent, which is what a taxonomy extension should look like.
    depends_on: []
    decision: pending
    description: In-repository declarations of how AI agents should work: instruction files (AGENTS.md, CLAUDE.md and equivalents), in-repo skill and prompt definitions for external agents, agent-facing ignore and scope rules, and the conventions between them.
    problem: An agent working in a repository has no standard way to learn its conventions, so every project invents a layout and every agent must be taught each one.
    inputs: ["repository conventions"]
    outputs: ["agent behaviour inside the repository", "cross-tool interoperability"]
    interfaces: []
    dependencies: []
    standards: []
    reference_projects: []
    research_records: ["study_pipeline/studied_repos/ (AGENTS.md in 18/25; CLAUDE.md 14/25; .claude/ or .cursor/ 10/25)"]
    implementation: ""
    tests: ""
    benchmarks: ""
    security: "These files are instructions an agent follows. An untrusted repository shipping them is an instruction-injection surface — the file is data from outside that changes agent behaviour, and it must be read as such."
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-09-17"

  # ---------------------------------------------------------------------
  # Added Phase 3 (ADR-0031, ADR-0032) — convergent patterns from
  # cross-repo convergence detection (25 studied repos).
  # ---------------------------------------------------------------------

  - id: guardrails
    name: Guardrails & Output Validation
    category: guardrails
    status: DISCOVERED
    maturity: experimental
    priority: medium — 10/25 studied repos (40%) proposed this category; output validation is distinct from safety/governance and needs its own taxonomy leaf.
    depends_on: []
    decision: pending
    description: Output moderation, content filtering, response validation, safety classifiers, and policy enforcement on model outputs.
    problem: Model output must be validated before reaching users, but no taxonomy category covered the machinery between model response and user-facing output.
    inputs: ["model output", "validation policy"]
    outputs: ["validated output", "rejection reason"]
    interfaces: []
    dependencies: []
    standards: []
    reference_projects: []
    research_records: ["study_pipeline/studied_repos/ (10/25 repos proposed guardrails)"]
    implementation: ""
    tests: ""
    benchmarks: ""
    security: "A guardrail that validates model output is a trust boundary — it must not become a bypass for prompt injection."
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-10-08"

  - id: rate-limiting
    name: Rate Limiting & Retry Infrastructure
    category: reliability
    status: DISCOVERED
    maturity: experimental
    priority: medium — 6/25 studied repos (24%) proposed this category; rate limiting and retry are cross-cutting infrastructure every production AI system needs.
    depends_on: []
    decision: pending
    description: Rate limiting, retry with backoff, circuit breakers, throttling, and resilience patterns for AI API calls.
    problem: Production AI systems must handle rate limits, transient failures, and provider outages gracefully, but no taxonomy category covered this machinery.
    inputs: ["API call", "retry policy"]
    outputs: ["successful response", "backoff/retry decision"]
    interfaces: []
    dependencies: []
    standards: []
    reference_projects: []
    research_records: ["study_pipeline/studied_repos/ (6/25 repos proposed rate-limiting)"]
    implementation: ""
    tests: ""
    benchmarks: ""
    security: ""
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: "2026-10-08"

