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
orchestration/         Workflow & Distributed Infrastructure
observability/         Observability
data/                  Data
development/           Development Infrastructure (research/ only, for now)
deployment/            Deployment
application/           AI Application Infrastructure (research/ only, for now)
prompt-engineering/    Prompt Engineering Primitives (catalog: prompt_engineering naming TBD on first entry)
finetuning/            Fine-tuning Infrastructure
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
    status: DISCOVERED
    maturity: experimental
    priority: high — everything above depends on a minimal LLM call interface; the narrow slice is text-in/text-out with errors and token metadata.
    depends_on: []
    decision: pending
    description: A minimal, vendor-neutral interface for chat/completion calls with streaming, error normalization, and usage metadata.
    problem: Components must not hard-code one provider's SDK, error shapes, or streaming model.
    inputs: ["messages/prompts", "generation parameters"]
    outputs: ["completions", "token usage", "provider errors normalized"]
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
    compatibility: ""
    last_reviewed: ""

  - id: react-agent-loop
    name: ReAct Agent Loop
    category: agents
    status: DISCOVERED
    maturity: experimental
    priority: high — canonical first agent pattern; exercises model abstraction + tool registry together; classic first end-to-end proof of composition.
    depends_on: [tool-registry, model-provider-abstraction]
    decision: pending
    description: Reason-act-observe loop: interleaved reasoning traces and tool calls until termination.
    problem: Simplest agent control loop that grounds LLM output in tool interaction with a clear termination condition.
    inputs: ["task", "tool registry", "model"]
    outputs: ["final answer", "step trace"]
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
    status: DISCOVERED
    maturity: experimental
    priority: medium — COMPATIBILITY candidate (charter §16): MCP is an established protocol; a thin working client beats a comprehensive never-finished one (§24.4).
    depends_on: [tool-registry]
    decision: pending
    description: Connect to an MCP server over stdio, list tools, call tools, surface results into the local tool registry.
    problem: Interoperate with the MCP ecosystem instead of inventing a private tool protocol.
    inputs: ["server command/config", "tool calls"]
    outputs: ["tool listings", "tool results"]
    interfaces: []
    dependencies: []
    standards: ["Model Context Protocol"]
    reference_projects: []
    research_records: []
    implementation: ""
    tests: ""
    benchmarks: ""
    security: ""
    license: Apache-2.0
    provenance: original
    compatibility: ""
    last_reviewed: ""

  - id: execution-trace-recorder
    name: Agent Trajectory / Execution Trace Recorder
    category: observability
    status: DISCOVERED
    maturity: experimental
    priority: medium — needed to evaluate and debug agents honestly (charter §18); simple JSONL recorder first.
    depends_on: []
    decision: pending
    description: Record structured traces of agent/model/tool steps with timing and token usage for replay and evaluation.
    problem: Without traces, agent behavior cannot be tested, evaluated, or debugged with evidence.
    inputs: ["step events"]
    outputs: ["JSONL traces", "aggregate stats"]
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
```

---

*Next expected edits: when the first capability session runs, update that entry through RESEARCHED → UNDERSTOOD → DECIDED with a linked ADR, and add the studied projects to `docs/registry/RESEARCH_REGISTRY.md`.*
