# Plan: agent-SU1 — Package Quickstart Examples and Sustainment Operations

## Objective

Deliver unified package quickstart examples and operational sustainment on dedicated branch `feat/package-examples-and-sustain`:
1. **Developer Experience & Demonstrations**: Provide a runnable, stdlib-only quickstart demonstration of the top-level unified `ai_infrastructure` package showing tools, memory, RAG, agent loop, and trace recording.
2. **Quality & Regression Guard**: Wire the quickstart example into the regression suite (`tests/test_ai_infrastructure_api.py`) so any breaking changes to the quickstart or package exports are prevented.
3. **Documentation & Catalog Cross-linking**: Update `examples/README.md` and document the quickstart.
4. **Toolchain Alignment**: Ensure root-level `examples/` are covered by Ruff and formatting rules in `pyproject.toml`.
5. **Full Gate Validation**: Execute `make check-strict`, `make security`, `make status`, and `make sessions`.

## Scope

- `examples/ai_infrastructure_quickstart/quickstart.py`
- `examples/ai_infrastructure_quickstart/README.md`
- `examples/README.md`
- `pyproject.toml`
- `tests/test_ai_infrastructure_api.py`
- `state/REGISTRY.md`, `state/DASHBOARD.md`, `state/sessions/`

## Approach

- Work strictly on dedicated branch `feat/package-examples-and-sustain` per git workflow.
- Ensure pure standard library usage (zero runtime dependencies, zero external network calls).
- Keep all gates strictly green.

## Success criteria

- Quickstart executes cleanly with exit code 0 and is tested in `pytest`.
- `make check-strict` passes with 0 violations.
- Git tree is clean, and branch PR workflow is followed.
