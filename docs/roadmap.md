# Roadmap

## Current phase

**Phase 1 — Seed** (charter §30). Establish taxonomy, registry, documentation standards, and the first handful of end-to-end capabilities.

| Phase | Status |
|---|---|
| 1 — Seed | **In progress** — skeleton done, no capabilities implemented |
| 2 — Study pipeline | Not started (machinery in `study_pipeline/` is a stub) |
| 3 — Discover | Not started |
| 4 — Compose | Not started |
| 5 — Sustain | Not started |

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
- **Session 2 (environment):** Working environment and enforcement established before any research — `pyproject.toml`, pinned dev toolchain (ruff/black/mypy-strict/pytest (ruff lints, black formats)), `requirements-dev.txt`, Makefile entry points, pre-commit hook, CI workflow, `docs/standards.md` (every rule mapped to its check), `docs/development.md`, and **`scripts/repo_status.py`** — a governance drift detector that fails when a claimed lifecycle status exceeds artifacts on disk. Verified: clean environment rebuild from documented commands; 34 tests passing; false-claim injection correctly produces 5 errors and exit 1. ADR-0003 records the toolchain decisions.
- **Open human decision:** ADR-0002 — choose the repository license. Until resolved, no external code may enter `catalog/` and `code_reused: true` must not be set in the registry.
- **Next session:** begin `tool-registry` research (RESEARCHED stage) — survey how LangChain, OpenAI function calling, MCP, and Semantic Kernel model tool schema/validation/invocation; register studies in `docs/registry/`; record the DECISION as ADR-0004 before any code. The environment is ready; no further setup work is needed first.
