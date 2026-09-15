# Phase 1 — Seed

**Status:** 🔄 In progress (started session 6)
**Charter basis:** §30 — *"5–10 categories with foundational patterns; establish taxonomy, registry, documentation standards."*
**Depends on:** [Phase 0](phase-0-foundation.md) ✅ complete

## Goal

Seed **5–10 categories** with *foundational patterns* — the smallest genuinely-working version of each, taken end-to-end through `RESEARCHED → DESIGNED → IMPLEMENTED → TESTED`.

The emphasis is **narrow and complete**, not broad and half-designed (charter §24.3–4). A thin `tool-registry` that actually works outranks a comprehensive one that is half-DESIGNED.

## Exit criteria

Phase 1 is complete when:

- [ ] **≥5 distinct categories** contain at least one `TESTED` capability
- [ ] Each has: research record, ADR, specification, implementation, tests, `PROVENANCE.md`
- [ ] Each image-level claim passes `make status` (no status exceeds artifacts)
- [ ] At least **one end-to-end composition** works: model + tools + agent loop, demonstrated in `integrations/`
- [ ] The registry contains real study records, not placeholders
- [ ] Known limitations are documented per capability

**"TESTED" means tests exist and pass — not "it ran once on my machine."**

## Category coverage target

7 capabilities span 7 categories:

| # | Capability | Category | Status | Session |
|---|---|---|---|---|
| 1 | `tool-registry` | tools | 🔄 in progress | 6 |
| 2 | `model-provider-abstraction` | models | ⬜ not started | 7 |
| 3 | `execution-trace-recorder` | observability | ⬜ not started | 8 |
| 4 | `react-agent-loop` | agents | ⬜ not started | 9 |
| 5 | `vector-memory-store` | memory | ⬜ not started | 10 |
| 6 | `basic-rag-pipeline` | retrieval | ⬜ not started | 11 |
| 7 | `mcp-client` | protocols | ⬜ not started | 12 |

That is **7 categories**, satisfying the 5–10 target with margin for one to slip.

## Dependency order (charter §24.1)

```text
tool-registry ────────────┬──> react-agent-loop ──> (composition)
                          │
model-provider-abstraction┘
        │
        └──> basic-rag-pipeline
                    ▲
vector-memory-store ─┘

execution-trace-recorder  (independent; enables evaluating the agent loop)

mcp-client ──> depends on tool-registry only
```

**Do not start a capability whose dependencies are not at least `TESTED`.** `react-agent-loop` therefore cannot begin before #1 and #2 are done. This is enforced as a warning by `make status`.

## Session pattern (repeat 7×)

Each capability takes **2–4 sessions**, one lifecycle stage each:

| Session | Stage | Deliverable |
|---|---|---|
| A | `DISCOVERED → RESEARCHED` | Survey 3–5 reference projects; findings in `research/<category>/<id>.md`; register each project in `docs/registry/RESEARCH_REGISTRY.md` |
| B | `RESEARCHED → UNDERSTOOD → DECIDED` | `docs/decisions/NNNN-<id>.md` — decision (IMPLEMENT/ADAPT/…) with rejected alternatives |
| C | `DECIDED → DESIGNED` | `specifications/<id>.md` — interfaces, data flow, invariants, failure modes, security, test strategy |
| D | `DESIGNED → IMPLEMENTED → TESTED` | `catalog/<category>/<id>/` with implementation, tests, examples, PROVENANCE |

You may merge B into A or C if the work is genuinely small — but **never** skip the ADR before code (charter §8).

## Per-capability definition of done

Every Phase 1 capability must exit with:

- [ ] Research record with evidence-classified claims (`FACT`/`OBSERVATION`/`INFERENCE`)
- [ ] ADR recording the decision + rejected alternatives
- [ ] Specification
- [ ] Implementation — Python, type-hinted, mypy strict, ruff/black clean
- [ ] Tests including **failure paths** (not just the happy path)
- [ ] ≥1 runnable example
- [ ] `PROVENANCE.md` — inspired-by vs derived-from, stated explicitly
- [ ] README with the charter §13 required sections
- [ ] Taxonomy entry updated with real artifact paths
- [ ] Known limitations documented

## Quality bar for this phase (charter §20 priority order)

1. **Correctness** — it does what the spec says, including on malformed input
2. **Security** — validate at boundaries; no `shell=True`; no unsafe deserialization
3. **Simplicity** — the smallest thing that works
4. **Explicitness** — no magic, no hidden state
5. Testability, observability, reproducibility

Performance is **not** a Phase 1 concern. Note it, defer it.

## Things deliberately NOT in Phase 1

Per charter §24 and the scope discipline rules:

- The study pipeline (§29) — that's Phase 2 machinery
- Distributed/durable execution, queues, schedulers
- GPU/deployment/container infrastructure
- Fine-tuning
- Any external service dependency (hosted vector DBs, eval platforms, model APIs used as *requirements* rather than test doubles)
- Performance optimization and benchmarking against alternatives — that's Phase 4 (though each capability should *record* what a future benchmark would measure)
- Multi-agent orchestration beyond the single ReAct loop

## Risks

| Risk | Mitigation |
|---|---|
| Scope creep — each capability grows unbounded | Hard rule: implement the smallest version that satisfies the spec. Extra ideas go in the taxonomy as new `DISCOVERED` entries. |
| Building on unproven abstractions | Dependency order is enforced; `make status` warns on lagging deps. |
| Research theatre — reading docs and calling it understood | Requires a spec with invariants and failure modes. If you can't write it, you don't understand it yet. |
| Tests that assert nothing | Regression tests pin real behavior; failure paths required. |
| Drifting from the vision toward "another agent framework" | Charter §31: every capability must be usable *independently*. If it only works as part of a bundle, the boundary is wrong. |
| Model dependence in tests | Tests must not require network or a real provider. Use fakes/doubles; mark real-provider tests `external` (never run in CI). |

## Next action

**`tool-registry` at the RESEARCHED stage.**

Survey how these model the same problem — tool schema, validation, invocation, error handling:

- **OpenAI function calling** — the de-facto wire format (`tools`/`tool_calls`)
- **LangChain** — tool abstraction, `@tool` decorator, args schema
- **MCP** — `tools/list`, `tools/call`, JSON Schema over JSON-RPC
- **Semantic Kernel** — plugin/function model

Output: `research/tools/tool-registry.md` + 4 registry entries, then `UNDERSTOOD`, then ADR-0005 decides IMPLEMENT vs ADAPT.

## Phase 1 session log

| Session | Capability | Stage reached | Notes |
|---|---|---|---|
| 6 | `tool-registry` | RESEARCHED → DECIDED | *(in progress)* |