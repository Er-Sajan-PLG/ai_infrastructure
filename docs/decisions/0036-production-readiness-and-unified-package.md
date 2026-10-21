# ADR-0036: Production Readiness Declaration and Unified Top-Level Package Distribution

**Status:** Accepted
**Date:** 2026-10-21
**Drivers:** Maintainer directive ("Complete ai_infrastructure , make it production ready.", 2026-10-21); Phase 5 Sustain; Session PR1; Charter §13 (Packaging), §30 (Phases), §31 (Independence)

## Context

Following the completion of Phase 4 (Compose) and the implementation of all seeded capabilities, the repository reached structural completeness: 8 fully tested capabilities across 8 categories, 5 end-to-end integration compositions, 1337+ passing tests, and standardized benchmarks vs monolithic baselines.

The maintainer directed the laboratory to achieve full **production readiness**. To satisfy production standards for an AI infrastructure foundation, four concrete gaps required resolution:

1. **Packaging & Consumption Ergonomics:** The repository permitted imports of individual catalog modules via sys.path manipulation, but lacked a unified, PEP 561 typed top-level Python package (`ai_infrastructure`). Enterprise and library consumers require standard `import ai_infrastructure` ergonomics and `py.typed` markers while preserving catalog modularity.
2. **Dev Toolchain Security (SCA):** The pinned development toolchain carried a moderate advisory on `certifi==2026.7.22` (PYSEC-2026-4320). A production-ready foundation must be clean against dual-source SCA audits (PyPI and OSV.dev).
3. **Runtime Python Compatibility:** `.python-version` pinned micro-version `3.14.7`, causing execution friction in modern environments where system Python is `3.14.8+`.
4. **MACP Session Compliance:** Prior work in session OC1 required formal maintainer closure authorization under ADR-0030, and the production readiness scope required registration of session PR1.
5. **Phase Progression:** Phase 5 (Sustain) remained marked "Not started" despite all prerequisites being satisfied.

## Decision

1. **Establish Unified `ai_infrastructure` Package Distribution:**
   - Create a top-level `ai_infrastructure` package containing `__init__.py` and `py.typed`.
   - Export all public types, classes, functions, and errors from the 8 verified capabilities with clean `__all__` definitions.
   - Configure `pyproject.toml` with `packages = ["catalog", "ai_infrastructure"]` and `[tool.coverage.run] source = ["catalog", "integrations", "ai_infrastructure"]`.
   - Maintain dual-consumption: individual catalog entries remain importable independently per Charter §31, while `ai_infrastructure` provides a cohesive facade.
   - Retain **zero runtime dependencies** across all package exports.

2. **Remediate Toolchain Vulnerabilities:**
   - Upgrade `certifi` from `2026.7.22` to `2026.10.19` in `requirements-dev.txt`.
   - Verify `make sca` exits 0 with 0 vulnerabilities across PyPI and OSV.dev advisories.

3. **Broaden Python Environment Versioning:**
   - Update `.python-version` to `3.14` (major.minor) to ensure seamless portability across Python 3.14 patch releases.

4. **Activate Phase 5 (Sustain):**
   - Transition `docs/phases/phase-5-sustain.md`, `README.md`, and `docs/roadmap.md` to `🟩 Active`.
   - Update status counters and documentation to reflect 8 capabilities, 5 integrations, 36 ADRs, and production readiness.

5. **Formalize Session Authorizations (ADR-0030):**
   - Record explicit maintainer closure authorization for session OC1.
   - Register and execute session PR1 under full gate enforcement (`make check-strict`, `make ci`, `make status`).

## Consequences

### Positive
- Consumers can install and import `ai_infrastructure` directly via standard Python package tooling.
- Static type checkers (mypy, pyright) automatically recognize package types via `py.typed`.
- Both dual-source SCA scanners report clean 0 vulnerabilities.
- Gate coverage enforces coverage across catalog, integrations, and the top-level package.
- Charter §31 component independence remains uncompromised.

### Neutral / Trade-offs
- Adding `ai_infrastructure` as a source directory requires keeping its `__all__` exports aligned with catalog changes.
- `ai_infrastructure/__init__.py` adds a lightweight path-mapping preamble to resolve catalog directories during standalone imports.
