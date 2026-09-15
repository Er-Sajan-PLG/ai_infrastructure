# Roadmap

## Current phase

**Phase 1 — Seed** (charter §30). Establish taxonomy, registry, documentation standards, and the first handful of end-to-end capabilities.

| Phase | Status | Plan |
|---|---|---|
| 0 — Foundation *(ADR-0005)* | ✅ Complete | [`phases/phase-0-foundation.md`](phases/phase-0-foundation.md) |
| 1 — Seed | 🔄 **In progress** — capability work starts now | [`phases/phase-1-seed.md`](phases/phase-1-seed.md) |
| 2 — Study pipeline | Not started | [`phases/phase-2-study.md`](phases/phase-2-study.md) |
| 3 — Discover | Not started | [`phases/phase-3-discover.md`](phases/phase-3-discover.md) |
| 4 — Compose | Not started | [`phases/phase-4-compose.md`](phases/phase-4-compose.md) |
| 5 — Sustain | Not started | [`phases/phase-5-sustain.md`](phases/phase-5-sustain.md) |

Executable plans — including exit criteria — live in [`docs/phases/`](phases/). Read the current phase's plan before starting work.

## Phase 1 queue

Priority order per charter §24 (dependency + verifiability first). Sources: [`../TAXONOMY.md`](../TAXONOMY.md) §4.

1. `tool-registry` (tools) — no dependencies, consumed by almost everything.
2. `model-provider-abstraction` (models) — no dependencies, consumed by everything above.
3. `react-agent-loop` (agents) — depends on 1+2; first end-to-end composition.
4. `execution-trace-recorder` (observability) — enables honest evaluation of 3.
5. `vector-memory-store` (memory), then `basic-rag-pipeline` (retrieval) — depends on 2/5.
6. `mcp-client` (mcp) — COMPATIBILITY candidate; narrow stdio client.

For each: RESEARCHED → UNDERSTOOD → DECIDED (ADR) → DESIGNED → IMPLEMENTED → TESTED — one stage at a time, no skipping (charter §4).

## What's deliberately NOT in Phase 1

- The study pipeline itself (Phase 2 machinery).
- Distributed/durable execution, GPU/deployment infrastructure, fine-tuning.
- Any external-service dependency (vector DBs, hosted eval platforms) — out of scope.

## Latest session notes

- **Session 1 (skeleton):** Repository bootstrapped — charter, taxonomy with 7 seeded DISCOVERED capabilities, registry, ADR-0000..0002, 39 category stubs, catalog validator with 11 tests. Commit `9cd728b`.
- **Session 2 (environment):** Working environment and enforcement established before any research — `pyproject.toml`, pinned dev toolchain (ruff lints, black formats; mypy strict; pytest), `requirements-dev.txt`, Makefile entry points, pre-commit hook, CI workflow, `docs/standards.md` (every rule mapped to its check), `docs/development.md`, and **`scripts/repo_status.py`** — a governance drift detector that fails when a claimed lifecycle status exceeds artifacts on disk. Verified: clean environment rebuild from documented commands; 34 tests passing; false-claim injection correctly produces 5 errors and exit 1. ADR-0003 records the toolchain decisions.
- **Session 3 (license + formatter):** Licensed **Apache-2.0** (`LICENSE`, `NOTICE`) after escalating to the maintainer — ADR-0002 is now Accepted, and `code_reused: true` is unblocked (subject to `attribution_requirements` + a `NOTICE` update). Chose permissive over AGPL/BSL because an undecided future favours optionality and permission is the reversible direction. **External contributions are deliberately not accepted** until a CLA or DCO-with-relicense-grant is adopted — this preserves the option to relicense future versions. Also reduced to one formatter (ruff lints, black formats; ADR-0003 amended).
- **Session 4 (testing enforcement):** Found and closed two real holes, prompted by the question *"doesn't testing belong to setting up the environment?"* — it does, and the setup was incomplete. (1) `validate_catalog.py` accepted an **empty** `tests/` directory in `--strict` mode (checked existence, not content). (2) `pyproject.toml` had `testpaths = ["tests"]`, so **pytest never collected `catalog/`** — a capability could ship tests that no gate ever ran while `make check` stayed green. Fixed: empty `tests/`/`examples/` are errors in all modes; `testpaths` includes `catalog/`; CI runs the contract in `--strict`; 6 regression tests added (34 → 40). ADR-0004.
- **Session 6 (Phase 1 begins — `tool-registry` research + decision):** Phase 1 capability work finally started; sessions 1-5 are now recorded as **Phase 0 — Foundation** (ADR-0005), because charter §30 defines Phase 1 as *seeded capabilities* and `catalog/` is empty. Added `docs/phases/` with an executable plan per phase (Phase 1 detailed enough to work from). Four reference projects surveyed with mechanisms verified against **primary source** (not docs): OpenAI function calling, LangChain/LangGraph, MCP, Semantic Kernel. **Key finding: none of the four ships a real tool registry** — OpenAI has none, LangChain's is a per-node dict, MCP's identity dies with the connection, SK's is a fail-open god object. Three of them independently converge on splitting tool failures by *model-actionability*. Decision **ADR-0006: IMPLEMENT** a standalone JSON-Schema-native registry, zero runtime dependencies, with 10 evidence-traceable requirements and an explicitly accepted subset limitation. Found and fixed a **third enforcement hole** while doing it: `repo_status.py` checked that `research_records` was non-empty but never that the file existed — the same class of bug as ADR-0004's empty-`tests/` hole. 5 regression tests added (40 → 45).
- **Session 7 (`tool-registry` → DESIGNED):** Wrote `specifications/tool-registry.md` — the design is now frozen enough to implement against. Key decisions: **D-1** `ToolId(namespace, name)` frozen dataclass (identity must outlive a connection; MCP's dies on restart, SK's parses a flattened name). **D-2** a documented JSON Schema subset with **unknown keywords rejected loudly, never ignored** — silent permissiveness in a validator converts an unchecked boundary into an apparently-checked one. **D-3** explicit `injected: frozenset[str]` + two schema views, closing LangChain's verified forging vector without annotation magic. **D-4** failure taxonomy by model-actionability (`NOT_FOUND` never reaches a model; `INVALID_ARGUMENTS` and `EXECUTION_FAILED` do). **D-5/D-6** dynamic registration and async deliberately **deferred, not half-designed**. The spec states what we do *not* protect against as prominently as what we do — a registry is **not** a sandbox. Taxonomy → `DESIGNED`. Gates verified to actually enforce the claim (removing the spec produces exit 1).
- **Next session:** `tool-registry` → **IMPLEMENTED → TESTED** — `catalog/tools/tool_registry/` with the schema-subset validator, tests covering every case in spec §11 (failure paths are the majority; adversarial input is a first-class case class), an example, README, and `PROVENANCE.md`. — survey how LangChain, OpenAI function calling, MCP, and Semantic Kernel model tool schema/validation/invocation; register studies in `docs/registry/`; record the DECISION as **ADR-0005** before any code. The environment is ready; no further setup work is needed first.
