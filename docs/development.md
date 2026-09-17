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
| pytest-cov | 7.1.0 | Coverage measurement | `[tool.coverage.*]` |
| ruff | 0.16.7 | **Lint only** | `[tool.ruff.lint]` |
| black | 26.5.1 | **Format only** | `[tool.black]` |
| mypy | 2.3.1 | Types, **strict** | `[tool.mypy]` |
| bandit | 1.9.4 | SAST, alongside ruff `S` | `[tool.bandit]` |
| import-linter | 2.15 | Entry independence (charter §31) | `[tool.importlinter]` |
| pip-audit | 2.10.1 | Dependency audit (PyPI + OSV) | CLI flags |
| diff-cover | 10.5.1 | Change-scoped coverage on PRs | CLI flags |
| types-PyYAML | 6.0.12.20260906 | Stubs; mypy strict rejects untyped imports | — |

**Division of labour: ruff lints, black formats.** Ruff's formatter is
deliberately not used. Two opinionated formatters that always agree provide no
additional coverage — disagreement would be a config bug, not a signal — so the
repository keeps one formatter and inherits one convention. Reason recorded in
[ADR-0003](decisions/0003-toolchain-and-enforcement.md).

**ruff `S` and bandit are both run, deliberately.** They are not equivalent:
`B614`/`B615` are unported in ruff, `S320` was removed, and `S401`–`S403` are
preview-only. See [ADR-0018](decisions/0018-security-tooling.md).

## The gates

| Command | Checks | Charter |
|---|---|---|
| `make lint` | ruff lint + black format check | §13, §20 |
| `make typecheck` | mypy strict | §13 |
| `make validate` | catalog entry contract | §13, §21 |
| `make test` | test suite | §18 |
| `make coverage` | tests + floor `85` | §18 |
| `make diff-coverage` | coverage of changed lines (PRs) | §18 |
| `make structural` | entry independence + test collectability | §31 |
| `make security` | secrets, SAST, SCA, licences | §18, §22 |
| `make workflows` | actionlint + zizmor | §18, §22 |
| `make risks` | accepted-risk register current | §4, §22 |
| `make deferred` | deferral register well-formed | §8 |
| `make commit-msg` | Conventional Commits header | §25 |
| `make status` | **taxonomy drift vs. disk** | §4 |
| `make check` | lint + typecheck + validate + links + test | §21 |
| `make check-strict` | `check` + strict catalog + structural + registers | §21 |
| `make ci` | what CI runs — see `make print-gates` | §18, §19 |

`make print-gates` prints the exact CI gate list, and
[`tests/test_ci_parity.py`](../tests/test_ci_parity.py) fails the build if the
workflow and that list diverge in either direction.

## Enforcement

- **`make install-hooks`** installs `.git/hooks/pre-commit` (quality gates on
  staged changes) and `.git/hooks/commit-msg` (commit header format). Hooks are
  per-clone, not versioned by git, so run it once per clone.
- **CI** (`.github/workflows/ci.yml`) invokes every gate through `make`, so a
  green pipeline means the same thing as a green local run.
- A gate failure is never resolved by weakening the check (charter §28) or by
  `--no-verify`. If a check is wrong, fix the check and record why.

## The three registers

Three separate artefacts answer three different questions. Conflating them —
treating a deferral as a bug, or a rejected option as planned work — is the
mistake they exist to prevent:

| Artefact | Question it answers | Checked by |
|---|---|---|
| [`decisions/`](decisions/README.md) "Options considered" | *Why was this **rejected**?* | review |
| [`risks/ACCEPTED_RISKS.md`](risks/ACCEPTED_RISKS.md) | *What are we **living with**?* | `make risks` |
| [`DEFERRED.md`](DEFERRED.md) | *What will become valuable **later**, and when?* | `make deferred` |

Both checkers enforce an anti-gaming rule: a `review_by` date may not advance
while the entry's rationale is unchanged. A date-only gate has a one-keystroke
fix, and *"make the build pass"* and *"edit one date"* are a very short
distance apart. The rationale must genuinely change, which means someone had to
think about it again.

`make deferred` additionally prints `POSSIBLE TRIGGER FIRE` advisories for the
triggers it can observe (a git tag appearing, a runtime dependency being
added). It never fails on those — adjudicating prose is not something a script
can honestly claim to do.

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