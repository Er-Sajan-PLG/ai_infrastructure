# `ai_infrastructure` — Master Charter & Operating Manual

---

## How to Use This Document

This is both a **charter** (why the repository exists, what "good" looks like) and an **operating manual** (what to do right now, this session). It is meant to be read by human contributors and by AI agents working across many independent sessions.

> **Starting a work session?** Skip to **§25 Session Protocol** and **§27 Output Contract**. Read the rest when you need the reasoning behind a rule — not before you're allowed to write code.

---

## Role

You are the lead research engineer, architect, and maintainer of the `ai_infrastructure` repository. You operate across sessions, possibly as different agent instances. Every session must leave the repository in a state the next session can pick up without re-deriving context.

---

## Mission

Build a long-lived, open-ended **AI infrastructure laboratory, research repository, architectural knowledge base, implementation library, interoperability layer, evaluation environment, and reusable engineering foundation**.

Its purpose is to:

1. **Discover** important AI infrastructure capabilities across the open-source ecosystem.
2. **Study** how existing systems solve those problems — their architecture, trade-offs, failure modes, and design rationale.
3. **Understand** the underlying engineering principles and architectural patterns, not merely the source code.
4. **Decide** explicitly whether to implement, adapt, prototype, document, defer, or reject each capability.
5. **Design and implement** independent, composable, well-tested versions where justified.
6. **Verify** implementations through rigorous testing and benchmarking.
7. **Integrate** capabilities through explicit, modular interfaces so they compose into larger systems.
8. **Preserve** research, provenance, licensing, and architectural knowledge in machine-readable form.
9. **Continuously evolve** as the AI ecosystem changes — deprecating the obsolete, adopting the emergent.

The goal is **not** to clone an existing framework or build "another agent framework."

The goal is to understand the infrastructure ideas behind modern AI systems and build an independent, composable foundation from which many different AI systems can be constructed.

---

# Part I — Purpose & Scope

## §1. Core Principle

Never begin with:

> "What existing repository should we copy?"

Always begin with:

> **"What capability exists, what problem does it solve, how do existing systems solve it, what architectural patterns are involved, what trade-offs exist, and what should we independently build?"**

Existing projects are research subjects, reference implementations, sources of architectural knowledge, compatibility targets, benchmarks, and evidence about ecosystem conventions. They are **not** automatically designs to copy, dependencies to adopt, or authorities to follow.

Popularity is not proof of correctness. The repository should **learn from** the ecosystem, not merely **reproduce** it.

## §2. What Counts as AI Infrastructure?

Treat "AI infrastructure" broadly. The categories below are for **navigation, not strict partitioning**. When something doesn't fit an existing category, that's a signal to extend the taxonomy (§14), not to drop the item.

- **Agents & Orchestration** — agent runtimes/loops, planners, executors, supervisors, delegation, multi-agent systems, task scheduling, state machines, graph-based execution, long-running/background agents, autonomous workflows, worker systems.
- **Agent Skills** — skill systems, discovery, registration, composition, execution, permissions, lifecycle, evaluation, packaging, versioning.
- **Agent Harnesses** — execution environments, coding-agent harnesses, sandboxes, terminal execution, filesystem access, browser automation, context management, task lifecycle, checkpointing, recovery, reproducibility, environment management.
- **Tools** — registries, tool calling, function execution, schemas, discovery, routing, permissions, validation, failure handling, composition.
- **MCP & Protocols** — MCP clients, servers, registries, transports, auth, protocol adapters, bridges, interoperability layers.
- **Models** — abstractions, provider abstraction, routing, selection, fallback, catalogs, inference interfaces, local/remote serving, batching, streaming, structured generation, multimodal inference, embeddings, reranking.
- **Context & Memory** — context management, compression, selection, conversation state, working/long-term/episodic/semantic/procedural memory, retrieval, consolidation, forgetting, persistence.
- **Retrieval & Knowledge** — RAG, hybrid/vector/lexical/graph retrieval, knowledge graphs, document indexing, chunking, reranking, citation, provenance, knowledge sync.
- **Evaluation** — model/agent/benchmark/task/trajectory/tool-use evaluation, regression, behavioral, adversarial, hallucination, reliability, capability evaluation.
- **Safety & Governance** — policy engines, permissions, capability security, sandboxing, human-in-the-loop, approval workflows, trust boundaries, audit logging, policy enforcement, risk classification, action gating, identity, auth.
- **Observability** — tracing, logging, metrics, telemetry, token/latency/cost accounting, execution traces, trajectory recording, debugging, replay, incident analysis.
- **Workflow & Distributed Infrastructure** — DAG execution, workflow engines, event-driven execution, queues, schedulers, retries, timeouts, distributed/durable execution, job management, state persistence.
- **Data** — ingestion, transformation, datasets + versioning, validation, synthetic data, labeling/annotation, provenance, pipelines, storage.
- **Development Infrastructure** — AI coding environments, repository analysis, code intelligence, patch generation, verification, test execution, CI integration, branch/commit management, agent development environments.
- **Deployment** — containers, sandboxes, model serving, API gateways, orchestration, scaling, resource management, GPU infrastructure, distributed/edge inference.
- **AI Application Infrastructure** — conversational/multimodal interfaces, voice, browser agents, computer-use, document intelligence, OCR, speech-to-text, text-to-speech, vision pipelines.
- **Prompt Engineering Primitives** — templates, few-shot managers, dynamic prompt construction, optimization, versioning.
- **Fine-tuning Infrastructure** — LoRA, RLHF, DPO pipelines, data curation tooling, training orchestration.
- **Emerging / Other** — open-ended; when a new class appears, evaluate whether it deserves its own category. The taxonomy itself must evolve.

See `TAXONOMY.md` for the full descriptive taxonomy and the machine-readable capability registry.

## §3. No Cargo-Cult Engineering

Before adding a component, work through: Is the problem real? Who needs it? Is the abstraction useful? What alternatives exist? What complexity, dependencies, and operational burden does it introduce? Can it be simplified? Is it needed *now*? Can it be built and verified with current resources? Does it compose? Can it be tested and maintained?

**Complexity must earn its place.**

---

# Part II — How Work Happens

## §4. Capability Lifecycle

```text
DISCOVERED → RESEARCHED → UNDERSTOOD → DESIGNED → DECIDED → PROTOTYPED
    → IMPLEMENTED → TESTED → BENCHMARKED → INTEGRATED → MATURE → DEPRECATED
```

Not every capability must reach every state. **Critical rule:** never claim a later stage while still actually in an earlier one. A `status: TESTED` claim with no test file present is a bug in the taxonomy.

## §5. Research Before Implementation

Before implementing a substantial capability: identify relevant projects and architectural approaches; study documentation, source, tests, failure modes, trade-offs, abstractions, coupling, standards, and licensing. Research answers **why**, not merely what.

## §6. Research Evidence Standards

Prefer, in order: official specifications, documentation, source code, official tests, benchmarks, issue discussions, papers, credible engineering analysis, community reports. Clearly distinguish **FACT / OBSERVATION / INFERENCE / DESIGN OPINION / EXPERIMENTAL RESULT**.

## §7. Understand Before Reimplementing

For every adopted capability, document: problem, consumers, inputs/outputs, abstraction, architecture/execution model, invariants, failure modes, security implications, scalability, testing strategy, standards, alternatives, and why this repository chose its implementation.

## §8. Decide Before Building

For each meaningful capability, choose one of: **IMPLEMENT / ADAPT / COMPATIBILITY / PROTOTYPE / DOCUMENT / DEFER / REJECT**. Record the decision in an ADR (§12) and in the taxonomy entry (§14).

## §9. Independent Implementation

Follow `UNDERSTAND → ABSTRACT → DESIGN → IMPLEMENT → TEST`, not `COPY → RENAME → MODIFY`. Use mature external libraries for low-level primitives where appropriate — independence, not unnecessary duplication.

## §10. Wrappers Are Not Reimplementations

Maintain a strict distinction: RESEARCH / ADAPTER / WRAPPER / COMPATIBILITY IMPLEMENTATION / PROTOTYPE / INDEPENDENT IMPLEMENTATION / PRODUCTION IMPLEMENTATION. Status must always be explicit.

## §11. Research Registry, Attribution & Intellectual Property

Every external project that materially influences an implementation must be recorded in `docs/registry/RESEARCH_REGISTRY.md`. One schema serves both the research view and the attribution view:

```yaml
project:                    # name
relevant_categories:         # which §2 categories this informs
repository:                  # URL
authors:                     # organization / individuals
license:
version_studied:             # version or commit studied
capabilities:                # what it does
architecture:                # how it's built
strengths:
weaknesses:
patterns_worth_adopting:
patterns_worth_avoiding:
code_reused:                 # true/false — triggers legal fields below
attribution_requirements:    # if code_reused is true
our_implementation:          # link to what we built, if anything
compatibility_status:
standards:
last_reviewed:
```

**Critical distinctions:** *"Inspired by / studied from X"* and *"Derived from / contains reused code from X"* are not the same claim. Conflating them is a licensing risk, not just a documentation gap.

Do not copy source code unless legally permitted. Do not remove copyright or license notices. When uncertain about licensing, **stop and flag for human review** (§22).

## §12. Decision Records

Record significant architectural decisions as ADRs in `docs/decisions/`. Link each ADR to the taxonomy entries it affects.

---

# Part III — System Structure

## §13. Repository Architecture

See `docs/architecture.md` for the current layout and its rationale. The structure is **provisional** — change it when evidence demonstrates a better organization. Each implementation directory needs a matching taxonomy entry. Top-level layout:

```text
ai_infrastructure/
├── README.md              # Project overview, vision, how to use
├── CHARTER.md             # This document
├── TAXONOMY.md            # Machine-readable taxonomy + capability registry
├── CONTRIBUTING.md        # How to add new patterns
├── AGENTS.md              # Entry point for AI agent sessions
├── LICENSE                # Apache-2.0 — see ADR-0002
├── NOTICE                 # Apache-2.0 copyright + third-party notices
├── research/              # Findings, mirrors §2 categories
├── specifications/        # DESIGNED-stage docs, pre-code
├── catalog/               # The main implementation library
├── integrations/          # Compositions into working systems
├── benchmarks/
├── examples/
├── study_pipeline/        # Automated repo-studying subsystem (§29)
├── scripts/               # Utility scripts
├── docs/
│   ├── architecture.md    # How this repo itself is designed
│   ├── philosophy.md      # Design principles
│   ├── roadmap.md         # What's been studied, what's next
│   ├── decisions/         # ADRs — §12
│   └── registry/          # Research registry — §11
└── tests/                 # Cross-cutting test suites
```

### Category Documentation Standard

Each category `README.md` must contain: What it is · Why it exists · How it works · Variants & types · Landscape · Our implementations · When to use / when not · References.

### Implementation Standards

Each recreated piece must be standalone, well-documented, include examples and tests, include `PROVENANCE.md`, be Pythonic (primary language: Python), and follow consistent style (ruff-linted, black-formatted, type-hinted).

## §14. Infrastructure Taxonomy

`TAXONOMY.md` holds the machine-readable taxonomy with the schema defined there. **Fill every field honestly rather than optimistically.**

## §15. External Project Registry

`docs/registry/RESEARCH_REGISTRY.md` is the evolving map of the ecosystem — not merely a dependency list.

## §16. Compatibility & Standards

Support useful established standards (e.g. MCP, OpenAI-compatible APIs, OpenTelemetry) with **standard-compatible interfaces over independent internal implementations**. Do not adopt standards blindly.

## §17. Integration Philosophy

Components compose into larger systems through modularity, explicit interfaces, replaceable implementations, minimal coupling, clear boundaries, dependency inversion, and composability. A consumer selects individual capabilities without adopting the entire repository.

---

# Part IV — Quality Bar

## §18. Testing & Verification

Every implemented capability must be verifiable: unit, integration, contract, property-based, failure-injection, security, regression, interoperability, and benchmark tests as appropriate. Test normal operation, malformed input, dependency failure, timeout, partial failure, concurrency, recovery, unexpected state, and security boundaries. A successful demo is not evidence of correctness.

## §19. Benchmarking

Where meaningful, benchmark: where are we better / worse / simpler / more general / more constrained / more maintainable. Record methodology and environment.

## §20. Engineering Standards & Priorities

Priorities, in order: correctness · security · simplicity · explicitness · modularity · composability · testability · observability · reproducibility · interoperability · maintainability · performance · extensibility. Avoid cargo-cult abstractions, unnecessary dependencies, opaque magic, untested agent behavior, undocumented architecture, fake implementations, unsupported claims, research presented as implementation, premature optimization, unnecessary framework coupling.

## §21. Definition of Done

Problem defined · research documented · alternatives understood · design rationale recorded · licensing understood · interfaces documented · implementation exists · tests exist · failure modes tested · security considered · compatibility tested · benchmarks where meaningful · documentation exists · taxonomy/registry updated · limitations documented · production claims justified. Mark non-applicable items explicitly.

## §22. Human Review Gates

Require human approval before: significant licensing risk, copying/adapting substantial external code, changing foundational architecture, adding a major dependency, security-sensitive infrastructure, trust-boundary changes, auth changes, deleting mature infrastructure, declaring production-readiness, major compatibility commitments. **Surface uncertainty rather than silently resolving high-impact ambiguity.**

---

# Part V — Operating This Repository

## §23. Continuous Ecosystem Research

Continuously discover projects, monitor standards, identify shifts, reassess assumptions, update research, deprecate the obsolete, and improve implementations. **Do not allow the repository to become a static snapshot.**

## §24. Prioritization & Sequencing

1. **Dependency first** — check `depends_on` in the taxonomy.
2. **Real demand first** — a capability a real consuming system needs beats abstract importance.
3. **Verifiable first** — buildable/testable now beats correct-on-paper.
4. **Narrow the slice** — smallest version that's genuinely IMPLEMENTED → TESTED end-to-end.

Record current priority and its reasoning in the taxonomy entry.

## §25. Session Protocol

### Start of Session
1. Check §24's priority order; find the highest-priority capability that isn't MATURE.
2. Read that capability's taxonomy entry: `status`, `depends_on`, linked registry/ADR entries. Don't redo recorded research.
3. Confirm the *actual* pipeline stage by checking what artifacts really exist.
4. Do the **next** stage.

### During the Session
5. Advance `status` only when the corresponding artifact exists and passes §18–§19.
6. Add uncovered capabilities/categories to the taxonomy instead of doing untracked work.
7. Record architectural decisions as ADRs in the same session.

### End of Session
8. Update `status`, `priority`, `depends_on` in the taxonomy.
9. Update the research registry with anything newly studied.
10. Leave one or two lines on what's next and why.

## §26. Agent Operating Procedure

1. **Understand** the repository's current state. 2. **Identify** the capability. 3. **Research** approaches. 4. **Compare** alternatives/trade-offs/licensing. 5. **Decide** per §8. 6. **Design**. 7. **Implement** the smallest coherent capability. 8. **Verify** with tests. 9. **Benchmark** where appropriate. 10. **Document** everything. 11. **Report** per §27.

## §27. Output Contract

Produce or update: capability ID/name · lifecycle status · research summary · spec/design · implementation plan or code · tests and results · benchmarks · licensing notes · ADR updates · registry/taxonomy updates · explicit next steps · what was NOT implemented and why · known limitations and open questions. If implementation isn't appropriate yet, say so and produce research/design artifacts instead.

## §28. Failure & Uncertainty Policy

Insufficient evidence → research first. Unclear architecture → research first. Risky implementation → prototype first. Unclear licensing → **stop, request human review**. Failing tests → investigate, never weaken the test. Superior existing implementation → adapt when appropriate. Unnecessary capability → don't build it.

---

# Part VI — Study Pipeline

## §29. Automated Repository Study System

`study_pipeline/` automates discovery and extraction: clone → analyze → extract → understand → recreate → classify → cite → log. Entry point (planned): `./scripts/study_repo.sh <github_url>`. The pipeline itself is infrastructure — tested, documented, versioned.

## §30. Growth Model & Phases

| Phase | Focus |
|---|---|
| **1 — Seed** | 5–10 categories with foundational patterns; establish taxonomy, registry, documentation standards. |
| **2 — Study** | Build the study pipeline; point it at 20–30 major repos. |
| **3 — Discover** | Automate discovery of new patterns and categories. |
| **4 — Compose** | Integration examples; benchmark composed systems against monolithic frameworks. |
| **5 — Sustain** | Community, periodic re-study, deprecation, continuous monitoring. |

Current phase: **Phase 1 — Seed** (repository skeleton established; no capabilities seeded yet).

---

# Part VII — Vision

## §31. Long-Term Goal

Build an independent, comprehensive, evolving foundation of AI infrastructure from which many different AI systems can be constructed — consumable piece by piece, not as a monolith.

## §32. Definition of Success

We understand the major classes of AI infrastructure, the architectural alternatives, and the trade-offs; we have independently implemented useful versions where justified; we can verify their behavior and interoperate with established systems; we can compose the results into reliable AI systems.

---

*This repository should become the place someone goes to understand "what are all the building blocks of modern AI systems, and how do they actually work?"*
