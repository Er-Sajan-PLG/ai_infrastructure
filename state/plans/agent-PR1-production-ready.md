# Plan: agent-PR1 — Complete ai_infrastructure and make it production-ready

## Objective

Deliver full production-readiness for `ai_infrastructure` per maintainer directive:
1. **Supply Chain & Security**: Resolve open vulnerabilities in development toolchain (PYSEC-2026-4320 via `certifi==2026.10.19`).
2. **Environment & Toolchain**: Modernize `.python-version` to `3.14` for minor-version portability.
3. **Packaging & Unified API Surface**: Provide a first-class, typed `ai_infrastructure` package alongside granular `catalog/` entry modules, enabling both unified `import ai_infrastructure` and granular imports.
4. **Governance & Decision Records**: Record ADR-0036 declaring production-readiness (charter §22 human approval gate) and establishing the unified packaging architecture.
5. **Phase 5 Activation**: Move Phase 5 (Sustain) from "Not started" to active standing operations.
6. **Documentation & State Truth**: Reconcile all stale documentation (`README.md`, `docs/architecture.md`, `docs/roadmap.md`, `state/BLOCKERS.md`, `state/DASHBOARD.md`) with committed reality.
7. **Verification**: Prove all quality, security, architectural, and benchmark gates pass with 100% green.

## Scope

- `requirements-dev.txt`, `.python-version`
- `ai_infrastructure/` (`__init__.py`, `py.typed`)
- `pyproject.toml`
- `tests/test_ai_infrastructure_api.py`
- `docs/decisions/0036-production-readiness-and-unified-package.md`, `docs/decisions/README.md`, `state/DECISIONS.md`
- `docs/phases/phase-5-sustain.md`, `docs/roadmap.md`, `docs/architecture.md`, `README.md`
- `state/` (DASHBOARD.md, STATE.md, BLOCKERS.md, REGISTRY.md, INDEX.md, sessions/)

## Approach

- Work in verifiable, atomic increments.
- Zero runtime dependencies preserved (stdlib only).
- All gates enforced via `make check`, `make ci`, `make status`, `make bench`.

## Success criteria

- `make ci`, `make check`, `make status`, `make bench`, `make sessions` all exit 0.
- `ai-infrastructure` builds distribution packages (`sdist` and `wheel`) cleanly.
- `ai_infrastructure` public API is tested, typed, and verified.
- Zero governance drift.
- All state and documentation files reflect true repository status.
