# 18-Repository Evolution Analysis — Deep-First Protocol

## Purpose

The previous repository-study sessions used a structural/surface reconnaissance pipeline across approximately 18 repositories.

That approach was useful for cheap inventory, but it has reached its limit.

The next analysis session must **not simply repeat the existing surface-analysis methodology**.

The objective now is to determine:

> **What architectural ideas, mechanisms, boundaries, invariants, workflows, and design patterns from these repositories are genuinely worth considering when evolving JARVIS, PROFESSOR-J, and STEMMA?**

The answer cannot be derived reliably from directory names, package names, dependency counts, or file counts.

Therefore this session must use a **two-stage methodology**:

```text
STAGE 1
Deep architectural analysis
        ↓
STAGE 2
Surface/structural analysis
        ↓
Cross-repository synthesis
        ↓
Evolution assessment
```

The existing surface-analysis pipeline should remain available, but it must become a **secondary corroboration/indexing mechanism**, not the primary source of architectural understanding.

---

# 1. Critical methodological rule

## Deep analysis comes first

For every repository:

1. Read the repository's actual architecture.
2. Identify the important runtime/control/data relationships.
3. Trace representative execution paths.
4. Identify abstractions, contracts, boundaries, state transitions, and invariants.
5. Determine what the architecture actually does.
6. Only then run the existing surface-analysis pipeline against that repository.
7. Compare the deep findings against what the surface pipeline detected.

Do NOT allow the surface detector's taxonomy to determine what the deep study looks for.

The repository must be allowed to reveal architectural concepts that are not currently present in the taxonomy.

---

# 2. What "deep analysis" means

Deep analysis does NOT mean reading every line of every repository.

It means reconstructing architecture from source evidence.

For each repository, determine:

### A. System purpose

What problem is the repository actually solving?

Do not rely only on README marketing language.

### B. Architectural units

Identify meaningful architectural units such as:

* runtime
* orchestrator
* agent
* worker
* environment
* tool
* capability
* protocol
* model/provider
* state
* memory
* knowledge
* persistence
* execution record
* trace
* evidence
* evaluator
* verifier
* policy
* guardrail
* authorization
* human approval
* scheduler
* workflow
* graph
* plugin
* extension
* transport

These are examples, not a fixed taxonomy.

### C. Relationships

For every important component, determine:

```text
WHO CALLS WHOM?
WHO OWNS WHAT?
WHO CONTROLS WHAT?
WHO PRODUCES WHAT?
WHO CONSUMES WHAT?
WHERE DOES STATE LIVE?
WHERE DOES AUTHORITY LIVE?
WHERE DOES VALIDATION HAPPEN?
WHERE DOES FAILURE PROPAGATE?
WHERE DOES EXECUTION STOP?
```

Relationships are more important than component names.

### D. Lifecycle

Trace representative flows from beginning to end.

For example:

```text
request
→ planning
→ model call
→ tool selection
→ execution
→ observation
→ state update
→ evaluation
→ result
```

Do not assume this exact lifecycle exists.

Reconstruct the actual lifecycle.

### E. Contracts

Identify actual interfaces/contracts between architectural boundaries.

Examples:

```text
Agent ↔ Model
Agent ↔ Tool
Agent ↔ Environment
Runtime ↔ Persistence
Execution ↔ Evidence
Trace ↔ Evaluation
Evaluator ↔ Metric
Worker ↔ Orchestrator
Client ↔ Protocol
Policy ↔ Execution
```

For each contract determine:

* inputs
* outputs
* state
* errors
* authority
* extensibility
* lifecycle

### F. Invariants

Look for rules that the implementation appears to preserve.

Examples:

* who may mutate state
* what must happen before execution
* what must be persisted
* what constitutes successful completion
* how retries work
* what can be resumed
* how identity is maintained
* how tool execution is isolated
* how evaluation results are attached to executions

These are often more transferable than classes or directory structures.

---

# 3. Deep analysis must use source evidence

For every major architectural conclusion, provide:

```text
Claim
Evidence files
Relevant symbols/classes/functions
Observed relationship
Confidence
```

Do not write:

> "This appears to be an agent framework."

Instead write something equivalent to:

> `Agent.run()` constructs execution state, invokes the model adapter, dispatches tool calls through X, receives observations through Y, and updates Z. Therefore the agent is the runtime owner of the control loop.

The exact source locations must be recorded.

---

# 4. Identify the actual architecture before categorizing it

Do NOT begin by asking:

> "Does this repository have agent-loop?"

Instead ask:

> "What is the execution architecture?"

Only after reconstructing it should the system map it to existing taxonomy concepts.

This is essential because previous studies have demonstrated that the current detector repeatedly misses architectures whose important relationships are not represented by obvious directory names.

---

# 5. Run the existing surface analysis AFTER deep analysis

Once the deep study is complete, run the existing structural pipeline.

Record:

* what the surface analysis detected
* what it missed
* what it falsely suggested
* what it correctly corroborated
* what architectural concepts were invisible to it

Create a comparison:

| Deep finding   | Surface detector | Result               |
| -------------- | ---------------- | -------------------- |
| Architecture X | detected         | corroborated         |
| Architecture Y | missed           | detector blind spot  |
| Architecture Z | weak signal      | under-represented    |
| Directory A    | strong signal    | misleading/ambiguous |

This is a required output.

---

# 6. Do not force discoveries into the existing taxonomy

If deep analysis discovers an important concept that the current taxonomy cannot express, record it explicitly.

Examples of possible concepts:

* execution environment
* control plane
* execution plane
* evidence plane
* evaluation plane
* capability protocol
* worker contract
* execution trajectory
* execution record
* policy enforcement boundary
* authority boundary
* verification boundary
* canonicalization gate
* durable execution
* state machine
* lifecycle hook
* extension contract

These are examples only.

Discover the actual concepts from the repositories.

---

# 7. For every repository produce two reports

## Report A — Deep Architectural Analysis

This is the authoritative analysis.

Required sections:

1. Repository purpose
2. Architecture overview
3. Major components
4. Component relationships
5. Runtime/control flow
6. Data/state flow
7. Important contracts
8. Authority/control boundaries
9. Extension mechanisms
10. Failure/retry semantics
11. Persistence/durability
12. Observability/evidence
13. Evaluation/verification
14. Security/safety boundaries
15. Architectural invariants
16. Architectural strengths
17. Architectural limitations
18. Transferable primitives
19. Non-transferable mechanisms
20. Source evidence

---

## Report B — Surface/Structural Analysis

Run the existing reconnaissance pipeline unchanged.

Do not modify its semantics merely to make it agree with the deep analysis.

Preserve its original methodology and limitations.

Then explicitly document:

### Surface → Deep agreement

What the cheap structural analysis correctly identified.

### Surface → Deep disagreement

What it classified incorrectly or overestimated.

### Deep → Surface blind spots

What the deep study discovered that the structural detector could not see.

### Taxonomy gaps

Concepts discovered by deep analysis that are absent from the current taxonomy.

---

# 8. Evolution assessment

Only after both analyses are complete should the agent answer:

> **What is actually worth evolving into JARVIS, PROFESSOR-J, or STEMMA?**

Do NOT rank repositories as "best."

Do NOT produce simplistic framework recommendations.

Instead identify **architectural primitives**.

For each candidate primitive:

```text
Primitive:
Source repository:
Source evidence:
Problem it solves:
Current implementation:
Architectural boundary:
Required dependencies:
Transferability:
Potential benefit:
Potential cost:
Risks:
Where it belongs:
JARVIS relevance:
PROFESSOR-J relevance:
STEMMA relevance:
```

---

# 9. Distinguish copying from learning

The objective is NOT:

> "Which framework should we adopt?"

The objective is:

> "Which architectural ideas should influence our own architecture?"

Therefore classify findings as:

### Directly reusable concept

The underlying abstraction is sufficiently general.

### Adaptable concept

The idea is useful but implementation must be redesigned.

### Context-specific concept

Useful only under the original repository's assumptions.

### Anti-pattern / caution

The implementation demonstrates something we should explicitly avoid.

### Research lead

Interesting enough to investigate further, but insufficient evidence for an architectural decision.

---

# 10. Analyze the repositories as a combined architectural dataset

After all repositories have been deeply studied, build a cross-repository synthesis.

Do not simply create a feature comparison table.

Construct an architectural map.

For example:

```text
                    AUTHORITY
                       │
                       ▼
                 ORCHESTRATION
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       AGENTS       WORKERS      WORKFLOWS
          │            │
          ▼            ▼
       TOOLS       CAPABILITIES
          │            │
          └──────┬─────┘
                 ▼
             EXECUTION
                 │
                 ▼
             ENVIRONMENT
                 │
                 ▼
             OBSERVATION
                 │
                 ▼
                TRACE
                 │
                 ▼
              EVIDENCE
                 │
          ┌──────┴──────┐
          ▼             ▼
      EVALUATION     VERIFICATION
          │             │
          └──────┬──────┘
                 ▼
              DECISION
                 │
                 ▼
          CANONICALIZATION
```

This is only an example.

The final graph must emerge from the repositories.

---

# 11. Identify convergent architectural patterns

If multiple independent repositories implement similar concepts, investigate why.

For example:

```text
Repository A → execution records
Repository B → trajectories
Repository C → traces
Repository D → durable execution
```

Do not immediately conclude these are the same thing.

Determine:

* what problem each solves
* what information each preserves
* who owns it
* when it is created
* whether it is mutable
* whether it is replayable
* whether it is evidence
* whether it is merely telemetry

Then determine whether they represent a deeper common primitive.

---

# 12. Identify divergent solutions to the same problem

This is equally important.

For example:

```text
Problem: durable agent execution

Repo A → checkpoints
Repo B → database-backed sessions
Repo C → workflow engine
Repo D → event sourcing
Repo E → execution graph
```

Analyze the trade-offs rather than selecting a winner.

The objective is to understand the design space.

---

# 13. Specifically investigate these cross-cutting dimensions

Across all repositories, look for:

### Authority

Who is allowed to decide?

### Orchestration

Who controls execution?

### Capability

What can the system actually do?

### Environment

Where does execution occur?

### State

What persists between operations?

### Memory

What information is intentionally retained for future reasoning?

### Knowledge

What information is treated as domain knowledge?

### Observation

How does the system know what happened?

### Evidence

How can what happened be independently established?

### Evaluation

How is performance/correctness assessed?

### Verification

How is a claim checked against independent evidence?

### Canonicalization

How does information become authoritative?

### Durability

Can execution resume after interruption?

### Reproducibility

Can the execution be reconstructed?

### Extensibility

How are capabilities added without modifying the core?

### Isolation

How are workers/tools/environments separated?

### Failure semantics

What happens when something fails?

### Human control

Where can humans inspect, approve, reject, override, or intervene?

---

# 14. JARVIS-specific analysis

Evaluate what the combined research implies for:

```text
JARVIS
```

Focus particularly on:

* orchestrator architecture
* worker contracts
* worker isolation
* model/provider abstraction
* execution environments
* tool/capability boundaries
* proof-of-delta
* execution trajectories
* evidence
* reproducibility
* HITL
* policy enforcement
* authority hierarchy
* durable state
* observability
* evaluation
* worker trust

Do not redesign JARVIS prematurely.

Identify architectural decisions that the repository evidence can actually inform.

---

# 15. PROFESSOR-J-specific analysis

Evaluate implications for:

```text
PROFESSOR-J
```

Focus on:

* cognitive/runtime architecture
* Professor/Evaluator/Researcher/ToolExecutor boundaries
* orchestration
* state
* memory
* knowledge
* evaluation
* verification
* HITL
* model routing
* tool execution
* observability
* durable workflows

Determine whether any existing separation should be strengthened, merged, or reconsidered based on repository evidence.

---

# 16. STEMMA-specific analysis

Treat STEMMA differently.

The central question is not agent execution.

It is:

```text
source
→ extraction
→ candidate knowledge
→ validation
→ evidence
→ evaluation
→ verification
→ conflict analysis
→ human review
→ canonicalization
```

Investigate repositories for mechanisms relevant to:

* provenance
* source traceability
* evidence
* evaluation
* disagreement
* confidence
* verification
* reproducibility
* canonical data governance
* immutable/append-only records
* schema evolution

Do not allow agent-framework concepts to contaminate STEMMA's authority model.

---

# 17. Produce an Evolution Gap Map

After studying all repositories, compare the current architecture of JARVIS / PROFESSOR-J / STEMMA against the discovered architectural primitives.

Use:

```text
Existing
Missing
Weak
Duplicated
Coupled
Unclear
Well-defined
Requires research
```

Do NOT score them numerically.

For each gap provide source-backed reasoning.

---

# 18. Produce an Evolution Candidate Map

Create groups:

## Candidate architectural primitives

Ideas worth considering.

## Candidate subsystem boundaries

Boundaries that may deserve explicit architectural separation.

## Candidate contracts

Interfaces that should become explicit.

## Candidate invariants

Rules that should be enforced architecturally.

## Candidate evidence mechanisms

Mechanisms that improve reproducibility/trust.

## Candidate evaluation mechanisms

Mechanisms useful for assessing execution.

## Candidate governance mechanisms

Mechanisms useful for authority/HITL/policy.

---

# 19. Identify what NOT to evolve

This is mandatory.

For each major repository, identify mechanisms that should NOT be copied because they are:

* framework-specific
* unnecessarily complex
* coupled to a particular ecosystem
* incompatible with our authority model
* incompatible with STEMMA canonicalization
* redundant with stronger existing architecture
* premature for current project maturity

Do not call something an anti-pattern without implementation evidence.

---

# 20. Final deliverable

The final session report must contain:

## Part I — Method

Explain:

```text
Deep source analysis
        ↓
Surface structural analysis
        ↓
Cross-check
        ↓
Cross-repository synthesis
        ↓
Evolution assessment
```

## Part II — Per-repository findings

For all studied repositories:

* deep architecture
* source evidence
* surface findings
* surface/deep discrepancies
* architectural primitives
* transferability

## Part III — Cross-repository architecture

Identify convergent and divergent architectural solutions.

## Part IV — Taxonomy evolution

List:

* existing categories validated
* categories requiring refinement
* genuinely new concepts
* concepts that should be removed/merged

Do not automatically modify the taxonomy.

## Part V — Evolution implications

Separate:

### JARVIS

### PROFESSOR-J

### STEMMA

## Part VI — Architectural gaps

Identify what the current projects do not yet model explicitly.

## Part VII — Candidate evolution directions

Provide architectural directions, not implementation plans.

## Part VIII — Research agenda

Identify questions that remain unresolved and require another source-reading session.

---

# 21. Critical anti-patterns for this analysis

Do NOT:

* infer architecture from directory names alone
* treat dependency counts as architectural importance
* treat test-file count as quality
* equate "agent" with orchestration
* equate "memory" with persistent state
* equate "knowledge" with canonical knowledge
* equate "trace" with evidence
* equate "evaluation" with verification
* equate "guardrail" with authorization
* equate "tool registry" with capability protocol
* equate "MCP" with orchestration
* equate "database" with durable execution
* equate "LLM judge" with truth
* recommend copying a framework merely because it is popular
* create rankings of repositories
* force every discovery into the existing taxonomy

---

# 22. The fundamental question

Throughout the entire analysis, keep asking:

> **What architectural problem is this repository solving, how does it solve it, what boundary makes that solution possible, and which part of that solution could remain valuable if the original framework disappeared?**

That final question is the purpose of this study.

We are not selecting frameworks.

We are extracting architectural knowledge.

The desired end state is not:

```text
"Use Framework X."
```

It is:

```text
Problem
→ architectural principle
→ boundary
→ contract
→ invariant
→ evidence
→ applicability
```

That is what should inform the next evolution of JARVIS, PROFESSOR-J, and STEMMA.
