# Development Environment

How to get a working environment and what the repository expects of it. Everything here is enforced by `make check` and by CI; nothing is advisory.

## Prerequisites

| Tool | Version used | Notes |
|---|---|---|
| Python | 3.12+ (verified on 3.14.7) | `pyproject.toml` sets `requires-python = ">=3.12"` |
| [uv](https://docs.astral.sh/uv/) | 0.12.1 | Environment and installation |
| git | 2.55.0 | Pre-commit hook |
| [gitleaks](https://github.com/gitleaks/gitleaks) | 8.30.1 | Secret scanning. **Optional locally, required in CI** |

Runtime dependencies: **none**. The toolchain is development-only.

`gitleaks` is the one prerequisite that is a standalone binary rather than a Python package, so
unlike everything else here it can be absent. The pre-commit hook detects that and prints a
warning instead of silently passing — an unrun check must never look like a passed one (charter
§28). CI installs a pinned 8.30.1 and has no such excuse. To install locally:

```bash
# macOS
brew install gitleaks
# Linux — see https://github.com/gitleaks/gitleaks/releases for the current version
curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
  | tar -xz -C "$HOME/.local/bin" gitleaks
```

## Setup

```bash
make setup        # creates .venv and installs the pinned toolchain
make install-hooks
make check        # lint + types + catalog contract + tests
```

`make setup` uses `uv` with a workspace-local cache (`.uv-cache/`, gitignored). If `uv` tries to write to `~/.cache/uv` in a restricted environment, the cache is already redirected by the `UV_CACHE_DIR` variable the Makefile exports.

If you prefer plain `venv`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Toolchain

Versions are pinned in `requirements-dev.txt` (a lock file) and declared in `pyproject.toml` (`[project.optional-dependencies].dev`). The lock file is the source of truth for reproducibility; `pyproject.toml` is the source of truth for intent.

| Tool | Version | Role | Config |
|---|---|---|---|
| pytest | 9.1.1 | Tests | `[tool.pytest.ini_options]` |
| pytest-cov | 7.1.0 | Branch coverage | `[tool.coverage.*]` |
| ruff | 0.16.7 | **Lint only** | `[tool.ruff.lint]` |
| black | 26.5.1 | **Format only** | `[tool.black]` |
| mypy | 2.3.1 | Types, **strict** | `[tool.mypy]` |

**Division of labour: ruff lints, black formats.** Ruff's formatter is
deliberately not used. Two opinionated formatters that always agree provide no
additional coverage — disagreement would be a config bug, not a signal — so the
repository keeps one formatter and inherits one convention. Reason recorded in
[ADR-0003](decisions/0003-toolchain-and-enforcement.md).

## The gates

| Command | Checks | Charter |
|---|---|---|
| `make lint` | ruff lint + black format check | §13, §20 |
| `make typecheck` | mypy strict | §13 |
| `make validate` | catalog entry contract | §13, §21 |
| `make test` | test suite | §18 |
| `make status` | **taxonomy drift vs. disk** | §4 |
| `make check` | all of the above | §21 |
| `make ci` | `check-strict` + coverage | §18, §19 |

## Enforcement

- **`make install-hooks`** installs `.git/hooks/pre-commit`, which runs the relevant gates on staged changes. It is per-clone, not versioned by git, so run it once per clone.
- **CI** (`.github/workflows/ci.yml`) runs the same gates plus coverage on every push and pull request.
- A gate failure is never resolved by weakening the check (charter §28) or by `--no-verify`.

## Governance drift detection

`make status` is the mechanism that keeps this repository honest. It parses
`TAXONOMY.md` and compares every capability's claimed lifecycle status against
what actually exists on disk:

- `RESEARCHED`+ requires non-empty `research_records`
- `DESIGNED`+ requires `specifications/<id>.md`
- `DECIDED`+ requires a non-`pending` decision
- `IMPLEMENTED`+ requires the `implementation` path to exist
- `TESTED`+ requires the `tests` path to exist
- `BENCHMARKED`+ requires `benchmarks`
- `depends_on` must reference real capability ids

It exits `1` on any violation. This is the mechanical form of the rule the
charter states most forcefully: *status must reflect artifacts that actually
exist*.

## Adding a dependency

Adding a runtime dependency is a human review gate (charter §22). The process:

1. Write an ADR explaining why the dependency earns its place (§3).
2. Add it to `[project].dependencies` in `pyproject.toml`.
3. Regenerate the lock: `UV_CACHE_DIR=.uv-cache uv pip install -r requirements-dev.txt`.
4. Record it in `docs/registry/RESEARCH_REGISTRY.md` if it is an infrastructure subject, not merely a library.

There are deliberately no runtime dependencies today — see the note in
`pyproject.toml`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Could not acquire lock` from uv | Cache outside the writable workspace | The Makefile exports `UV_CACHE_DIR`; do not call `uv` bare |
| mypy: "no .py files in directory" | Naming an empty category directory | Use `make typecheck`, which passes only existing files |
| `pytest: command not found` | Venv not activated or not created | `make setup`, then use `.venv/bin/pytest` |