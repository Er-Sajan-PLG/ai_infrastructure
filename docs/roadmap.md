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
- **Session 2 (environment):** Working environment and enforcement established before any research — `pyproject.toml`, pinned dev toolchain (ruff lints, black formats; mypy strict; pytest), `requirements-dev.txt`, Makefile entry points, pre-commit hook, CI workflow, `docs/standards.md` (every rule mapped to its check), `docs/development.md`, and **`scripts/repo_status.py`** — a governance drift detector that fails when a claimed lifecycle status exceeds artifacts on disk. Verified: clean environment rebuild from documented commands; 34 tests passing; false-claim injection correctly produces 5 errors and exit 1. ADR-0003 records the toolchain decisions.
- **Session 3 (license + formatter):** Licensed **Apache-2.0** (`LICENSE`, `NOTICE`) after escalating to the maintainer — ADR-0002 is now Accepted, and `code_reused: true` is unblocked (subject to `attribution_requirements` + a `NOTICE` update). Chose permissive over AGPL/BSL because an undecided future favours optionality and permission is the reversible direction. **External contributions are deliberately not accepted** until a CLA or DCO-with-relicense-grant is adopted — this preserves the option to relicense future versions. Also reduced to one formatter (ruff lints, black formats; ADR-0003 amended).
- **Session 4 (testing enforcement):** Found and closed two real holes, prompted by the question *"doesn't testing belong to setting up the environment?"* — it does, and the setup was incomplete. (1) `validate_catalog.py` accepted an **empty** `tests/` directory in `--strict` mode (checked existence, not content). (2) `pyproject.toml` had `testpaths = ["tests"]`, so **pytest never collected `catalog/`** — a capability could ship tests that no gate ever ran while `make check` stayed green. Fixed: empty `tests/`/`examples/` are errors in all modes; `testpaths` includes `catalog/`; CI runs the contract in `--strict`; 6 regression tests added (34 → 40). ADR-0004.
- **Next session:** begin `tool-registry` research (RESEARCHED stage) — survey how LangChain, OpenAI function calling, MCP, and Semantic Kernel model tool schema/validation/invocation; register studies in `docs/registry/`; record the DECISION as ADR-0004 before any code. The environment is ready; no further setup work is needed first.
