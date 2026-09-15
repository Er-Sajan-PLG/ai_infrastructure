# ADR-0006 — `tool-registry`: Implement a Standalone, JSON-Schema-Native Registry

- **Status:** Accepted
- **Date:** 2026-09-15
- **Capability:** [`tool-registry`](../TAXONOMY.md) (category: tools)
- **Research record:** [`research/tools/tool-registry.md`](../research/tools/tool-registry.md)
- **Supersedes:** —

## Context

`tool-registry` is the first Phase 1 capability and the foundation nearly
everything downstream consumes (charter §24.1 — dependency order first). It
needed a decision before any code (charter §8, §12).

Four reference projects were studied in depth — OpenAI function calling,
LangChain/LangGraph, the Model Context Protocol, and Microsoft Semantic Kernel —
with mechanisms verified against primary sources rather than documentation alone
(`langgraph/prebuilt/tool_node.py` read in full; `semantic_kernel` source read
directly; MCP normative `schema.ts` fetched per revision; OpenAI's schema subset
verified verbatim against the official Structured Outputs guide).

**The decisive finding is what those projects do not have.** All four solve
*tool invocation*. None ships a genuine tool registry:

| Project | Registry situation |
|---|---|
| OpenAI | No registry. Stateless API; caller dispatches. |
| LangChain | No registry. A name-keyed dict rebuilt per `ToolNode`. |
| MCP | Identity scoped to a live connection; dies on restart. |
| Semantic Kernel | A god object with a fail-open allowlist default. |

*Verified in source, not inferred.* The gap this capability fills is real and
externally corroborated.

**The second decisive finding is convergence.** OpenAI, LangChain, and MCP
independently split tool failures by whether *the model can act on them*, and MCP
states the rationale normatively: report tool errors in-band *"otherwise the LLM
would not be able to see that an error occurred and self-correct."* Three
independent arrivals at the same rule is strong evidence it is load-bearing.

## Decision

**IMPLEMENT** (charter §8) a standalone, JSON-Schema-native tool registry with
zero runtime dependencies.

### Scope — declaration and validation

The capability performs two of the five concerns identified in research:
**declaration** (what tools exist, with typed contracts) and **validation**
(are arguments acceptable *before* any side effect).

It explicitly does **not**: select tools for a model; speak any provider's wire
format; own telemetry; execute work beyond calling a registered callable;
schedule, queue, or retry.

### Ten non-negotiable requirements

Distilled from the surveys, each traceable to evidence:

1. **Stable, explicit tool identifiers** — outliving any connection; never structure recovered by parsing a name. *(gap in all four)*
2. **Two schema views** — model-facing vs validation-facing. Injected arguments are never model-visible. *(LangChain)*
3. **Unconditional validation before side effects** — model-supplied arguments are untrusted input. *(all four; OpenAI's docs require it explicitly)*
4. **Fail closed** — unknown tool name is an error; with no advertising policy, advertise nothing. *(against Semantic Kernel's documented fail-open default)*
5. **Failure taxonomy by model-actionability** — not-found (never reaches the model), invalid-arguments (reaches it), execution-failed (reaches it, in-band). Internal exceptions never leak. *(three-way convergence)*
6. **Explicit `$schema`; self-contained schemas** — never dereference network `$ref`. *(MCP's documented multi-year breakage)*
7. **Injected/trusted arguments stripped from caller input** — prevents a model forging privileged fields. *(LangChain's explicit forgery defence)*
8. **Zero runtime dependencies** — a hand-written validator over a documented subset. *(ADR-0003)*
9. **Introspectable without invocation.** *(charter §16)*
10. **Usable standalone** — no agent loop, no model, no network. *(charter §31)*

### Accepted limitation, recorded before implementation

Requirement 8 has a real cost and it is accepted deliberately:

- We support a **documented JSON Schema subset**, not the whole specification. `$ref`, `oneOf`, `patternProperties`, and conditional composition are out of scope for Phase 1.
- **Unknown keywords are rejected loudly, never ignored.** A validator that skips what it does not understand provides false confidence.
- Validation is a **security boundary**: bounded recursion depth, bounded composition size, no `eval`/`exec`, no unbounded expansion. An untrusted schema is an attack surface (external `$ref` → SSRF; pathological composition → CPU exhaustion).

**If evidence later shows the subset blocks real use, the correct response is an
ADR adding a dependency — not a quiet widening of the subset.**

### Chunking boundary (charter §17)

- **This capability:** declaration, stable identity, schema validation, result normalisation.
- **`model-provider-abstraction`:** translating to/from a provider's wire format.
- **The caller / agent loop:** choosing which tools to advertise.
- **`execution-trace-recorder`:** telemetry. This capability emits plain data and never imports an observability library.
- **`mcp-client`:** remote tool discovery and the stdio transport.

## Consequences

- **A real gap is filled, not a clone produced.** No surveyed project offers stable connection-independent tool identity with a validated, dependency-free schema boundary.
- **The subset is a visible limitation** on a foundational component. Every consumer inherits it until it is widened by ADR.
- **Hand-written validation is code we must test adversarially** — malformed, oversized, deeply nested, and hostile input. This raises the testing bar for this capability above the others, and the Phase 1 definition of done requires failure-path tests.
- **Provider adapters carry the wire-format burden.** This is the intended cost of model-agnosticism.
- **The registry is usable and testable with no model and no network**, so its tests need no doubles — a direct benefit of the boundary chosen.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **ADAPT Semantic Kernel's plugin model** | Registration by dunder smuggling, a god-object container, unconditional telemetry in the core type, and documented fail-open defaults. The middleware idea is worth taking as a *concept* (recorded in the research record), but the structure is the wrong shape to adopt. |
| **ADAPT LangChain's `BaseTool`** | Hard Pydantic coupling, schema inference on a deprecated Pydantic path the maintainers' own comment says "should be re-written," and severe import churn across four versions. Adopting it adopts its weaknesses. |
| **COMPATIBILITY — implement MCP's tool shape** | Wrong layer. MCP is a *transport protocol*; adopting its identity model would make tool identity connection-scoped and die on restart, which is precisely the defect we exist to fix. `mcp-client` will map onto it instead. |
| **Use Pydantic for validation** | The easy path, and permitted (it is an established library). Rejected because it makes the foundational primitive the most-coupled component in the repository, contradicts the zero-dependency decision (ADR-0003), and the two projects that chose it are the heaviest and most-criticised of the four. |
| **Use the `jsonschema` package** | Removes requirement 8 for the subset problem, but adds a runtime dependency to the component everything else consumes, and its full specification support is itself an attack surface. Revisit only with evidence the subset is too small. |
| **DEFER — build something else first** | Rejected: `react-agent-loop`, `basic-rag-pipeline`, and `mcp-client` all `depends_on` this capability. Deferring it stalls the dependency graph. |
| **PROTOTYPE — spike it, decide later** | Rejected: the design questions are answered by the research, and a prototype that "sort of works" is exactly the unverified artifact the charter forbids claiming status for. |

## Charter references

§1 (begin with capability, not code), §4 (honest status), §6 (evidence classes),
§8 (decision vocabulary), §11 (inspired-by vs derived-from), §12 (decision
records), §13 (implementation standards), §16 (inspectability), §17 (chunking),
§18 (testing), §20 (security), §21 (capability map), §24 (prioritization),
§31 (independence).

## Taxonomy impact

`tool-registry` advances `DISCOVERED` → `RESEARCHED` → `UNDERSTOOD` → `DECIDED`.

Artifacts: research record, four registry entries, this ADR.
`decision: IMPLEMENT`. `reference_projects` updated. `status` becomes `DECIDED`
only when the specification exists (charter §4) — so the next stage is
`DESIGNED`, and the taxonomy will be updated to match the artifacts that actually
exist at the end of this session.

## Licensing

**No code was reused.** All four studied projects are registered with
`code_reused: false`; ideas adopted are conceptual (injected-argument namespacing,
error taxonomy, middleware placement, explicit schema dialects). Nothing here
requires a `NOTICE` update or `attribution_requirements` (charter §11).