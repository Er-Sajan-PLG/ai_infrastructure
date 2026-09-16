# ai_infrastructure — Baseline Engineering Mechanism Inventory

**Repository:** `/home/sajan/Projects/ai_infrastructure`
**Generated:** from a full read of the repository working tree at `HEAD` (commit `f26136f`, 28 commits, branch `master`, **no git remote**)
**Purpose:** authoritative PRESENT / ABSENT / PARTIAL baseline for a gap analysis against three sibling repos.
**Method:** `git ls-files` (181 tracked files) enumerated in full; every config, workflow, script, hook, test and governance doc read directly; gates executed to verify behaviour rather than trusting their documentation. Documentation was cross-checked but is not treated as authoritative — where a doc claims a mechanism, the implementing file is cited.

---

## 0. Repository shape at a glance

| Fact | Value | Evidence |
|---|---|---|
| Tracked files | 181 | `git ls-files \| wc -l` |
| Commits | 28 | `git rev-list --count HEAD` |
| Tags / releases | **0** | `git tag` empty |
| Remotes | **none** | `git remote -v` empty |
| Branches | `master` only | `git branch -a` |
| Primary language | Python (63 `.py` files) | black/mypy output |
| Runtime dependencies | **zero** (deliberate) | `pyproject.toml:20` |
| Dev dependencies | 5 direct, 17 pinned | `pyproject.toml:25-31`, `requirements-dev.txt:16-33` |
| Tests | **411 passing**, 90% coverage | live `pytest --cov` run |
| Catalog entries | 5 (across 5 of 20 declared categories) | `find catalog -mindepth 2 -maxdepth 2 -type d` |
| ADRs | 11 (0000–0010) | `docs/decisions/` |
| Specifications | 5 | `specifications/*.md` |
| Research records | 5 | `research/**/*.md` excl. READMEs |
| Research registry entries | 21 | `grep -c '^### ' docs/registry/RESEARCH_REGISTRY.md` |
| GitHub workflows | **1** | `.github/workflows/ci.yml` |
| Git hooks | pre-commit only | `scripts/hooks/pre-commit` |

---

## 1. Environment reproducibility

### PRESENT
- **Python version pinned:** `.python-version:1` → `3.14.7`. Also `requires-python = ">=3.12"` (`pyproject.toml:6`), ruff/mypy/black all target `py312` (`pyproject.toml:84,156,163`).
- **Fully pinned dev toolchain:** `requirements-dev.txt:16-33` — 17 packages, all `==`-pinned, direct **and transitive** (`ast-serialize==0.11.2`, `black==26.5.1`, `click==8.5.0`, `coverage==7.16.1`, `iniconfig==2.3.0`, `librt==0.15.0`, `mypy==2.3.1`, `mypy-extensions==1.1.0`, `packaging==26.3`, `pathspec==1.1.1`, `platformdirs==4.11.8`, `pluggy==1.6.0`, `pygments==2.21.0`, `pytest==9.1.1`, `pytest-cov==7.1.0`, `pytokens==0.4.1`, `ruff==0.16.7`, `typing-extensions==4.16.0`).
- **Two-source dependency discipline:** `pyproject.toml:22-31` declares *intent* (`[project.optional-dependencies].dev`); `requirements-dev.txt:1-14` is documented as the *lock file* with explicit regeneration commands (`requirements-dev.txt:5-9`).
- **Deterministic env creation:** `Makefile:31-35` (`make setup` → `uv venv --python 3.14` + `uv pip install -r requirements-dev.txt`).
- **Cache locality pinned:** `Makefile:18-20` exports `UV_CACHE_DIR := $(CURDIR)/.uv-cache`; `.gitignore:22`.
- **CI reproduces the environment:** `.github/workflows/ci.yml:35-38` (`uv venv --python 3.12`, `uv pip install -r requirements-dev.txt`).
- **External binary pinned:** gitleaks `v8.30.1` curl-pinned by URL in CI (`.github/workflows/ci.yml:46-49`); "pinned" rationale inline at `ci.yml:41-43`.

### PARTIAL
- **No `uv.lock` / lockfile with hashes.** Reproducibility rests on `==` pins only — no transitive hash verification. Confirmed absent: `ls *.lock` → none; `git grep -il "uv.lock"` returns only audit docs.
- **CI Python minor drifts from local.** CI creates `--python 3.12` (`ci.yml:37`) while `.python-version` and `Makefile:33` use **3.14**. Local and CI exercise different interpreters.
- **`make setup` / CI do not pass `--frozen`**; the survey itself flags this as open item SUP-002 (`docs/audits/2026-09-16-usa-infrastructure-survey.md:31,117`).

### ABSENT
- No `setup.py`, `setup.cfg`, `tox.ini`, `.flake8`, `MANIFEST.in`, `poetry.lock`, `Pipfile`, `conda`/`environment.yml`, `nix` files. (Verified: root listing + `git ls-files`.)

---

## 2. Task runner and coverage

`Makefile` — 19 targets, `.DEFAULT_GOAL := help` (`Makefile:10`), self-documenting via `##` comments (`Makefile:24-25`).

| Target | Line | Depends on | Actually runs |
|---|---|---|---|
| `help` | 23 | — | greps `##` comments from the Makefile |
| `setup` | 32 | — | `uv venv --python 3.14` (if absent) + `uv pip install -r requirements-dev.txt` |
| `clean` | 38 | — | `rm -rf` caches + `find … __pycache__` removal (keeps `.venv`) |
| `install-hooks` | 43 | — | `cp scripts/hooks/pre-commit .git/hooks/pre-commit && chmod +x` |
| `uninstall-hooks` | 50 | — | `rm -f .git/hooks/pre-commit` |
| `lint` | 59 | — | `ruff check .` **and** `black --check .` |
| `format` | 64 | — | `ruff check --fix .` **and** `black .` |
| `typecheck` | 69 | — | `find catalog integrations scripts tests study_pipeline -name '*.py'` → `mypy $targets` |
| `test` | 81 | — | `pytest` |
| `coverage` | 85 | — | `pytest --cov --cov-report=term-missing` |
| `validate` | 89 | `links phase-plan` | `python scripts/validate_catalog.py` |
| `links` | 93 | — | `python scripts/check_links.py` |
| `phase-plan` | 97 | — | `python scripts/check_phase_plan.py` |
| `validate-strict` | 101 | — | `python scripts/validate_catalog.py --strict` |
| `check` | 109 | `lint typecheck validate links test` | aggregate |
| `check-strict` | 112 | `lint typecheck validate-strict links phase-plan test` | aggregate |
| `ci` | 115 | `check-strict coverage` | "What CI runs" |
| `status` | 122 | — | `python scripts/repo_status.py` |
| `bench` | 130 | — | guarded no-op: runs `pytest benchmarks -q` only if `benchmarks/bench_*.py` exists, else prints a message |

**Verdict: PRESENT and unusually complete.** Every claimed rule is reachable from the Makefile; `Makefile:3-4` states the philosophy ("If a rule is not enforced here, it is a preference, not a standard"). `bench` is a **PARTIAL/declared no-op** — `benchmarks/` contains only `README.md`.

---

## 3. Lint / format / typecheck strictness

### Lint — `ruff` 0.16.7, PRESENT and strict
- `pyproject.toml:82-88`: `line-length = 88`, `target-version = "py312"`, `src = [...]`, `extend-exclude = [".venv", ".uv-cache", "study_pipeline/studied_repos"]`.
- **19 rule families selected** (`pyproject.toml:90-110`): `E, W, F, I, N, UP, B, A, C4, DTZ, T20, SIM, PTH, RUF, S, TID, PIE, RET, ARG`. Notably includes **`S` = flake8-bandit security checks** and **`DTZ`** (naive datetimes) and **`T20`** (print ban) and **`PTH`** (pathlib-forcing).
- **Only 2 global ignores** (`pyproject.toml:111-117`): `E501` (long docstring/URL lines) and `S101` (assert in tests).
- **Per-file ignores, all justified inline** (`pyproject.toml:119-139`): `tests/**` → `S101, ARG, T20, S108`; `catalog/**/tests/**` → `+TID252, INP001`; `scripts/**` → `T20`; `catalog/**` → `T20, TID252`; `catalog/**/examples/**` → `T20, TID252, S108, INP001`; `integrations/**` → `TID252`.
- **Relative imports banned globally** (`pyproject.toml:144-145`, `ban-relative-imports = "all"`) then re-permitted per-path for catalog/integration relocatability.
- `known-first-party = ["catalog"]` (`pyproject.toml:142`).
- Verified: `.venv/bin/ruff check .` → **"All checks passed!"**, exit 0.

### Format — `black` 26.5.1, PRESENT
- `pyproject.toml:154-156`: `line-length = 88`, `target-version = ["py312"]`.
- **Deliberate single-formatter policy:** ruff's formatter config exists (`pyproject.toml:147-152`) but is documented as **not used**; ADR-0003 (`docs/decisions/0003-toolchain-and-enforcement.md`) records the reasoning, echoed at `docs/development.md:58-62`.
- Verified: `.venv/bin/black --check .` → 63 files unchanged, exit 0.

### Typecheck — `mypy` 2.3.1 strict, PRESENT and strict
- `pyproject.toml:162-178`: `strict = true`, plus explicit `warn_unreachable`, `warn_no_return`, `disallow_any_unimported`, `disallow_untyped_defs`, `no_implicit_optional`, `show_error_codes`, `pretty`.
- **No `files` list, deliberately** (`pyproject.toml:174-177`) — targets come from the Makefile because naming an empty category dir makes mypy exit 2.
- One override: `tests.*` → `disallow_untyped_decorators = false` (`pyproject.toml:180-183`).
- **Enforcement is itself tested**: `tests/test_gate_coverage.py:218-249` parses the Makefile's `find` line and asserts every gated directory is traversed.
- Verified: `.venv/bin/mypy <63 files>` → **"Success: no issues found in 63 source files"**.

### ABSENT
- No `py.typed` marker anywhere in `catalog/` — the packaged library does not declare itself typed for downstream consumers.
- No separate security-linter config (`bandit` as a standalone tool is absent; its rules are only the ruff `S` subset).

---

## 4. Test framework, markers, coverage config, threshold enforcement

### Framework — PRESENT
- `pytest 9.1.1` + `pytest-cov 7.1.0` (`pyproject.toml:26-27`).
- `[tool.pytest.ini_options]` (`pyproject.toml:44-65`):
  - `minversion = "9.0"` (line 45)
  - **`testpaths = ["tests", "catalog", "integrations"]`** (line 54) — extended twice because capability tests live beside their entry; the rationale and the historical hole are documented at lines 46-53.
  - `norecursedirs = [".venv", ".uv-cache", "study_pipeline"]` (line 56)
  - `python_files = ["test_*.py"]` (line 57)
  - **`addopts = "-q --strict-markers --strict-config"`** (line 59) — unknown markers and unknown config keys are hard errors.
  - **3 registered markers** (lines 60-64): `slow`, `network` ("never run in CI by default"), `external`.
  - **`filterwarnings = ["error"]`** (line 65) — every warning is a test failure.

### Coverage config — PRESENT, **threshold ABSENT**
- `[tool.coverage.run]` (`pyproject.toml:67-70`): `source = ["catalog", "integrations", "scripts"]`, **`branch = true`**.
- `[tool.coverage.report]` (`pyproject.toml:72-76`): `show_missing = true`, `skip_covered = false`.
- **NO `fail_under`.** The string appears only inside an explanatory comment: `pyproject.toml:74-75` — *"No threshold is enforced yet: there is no implementation to measure. Set fail_under when the first catalog entry lands (charter §18)."* That condition is now false — **5 catalog entries exist** — yet the threshold was never added. Corroborated by `.usa/foundation.yaml:54` (`minCoverage: 0`) and by the survey's gap list item #1 (`docs/audits/2026-09-16-usa-infrastructure-survey.md:113`).
- **Live measurement:** 411 tests pass in 2.91s; **TOTAL 90% statements (5119 stmts, 362 missed), 1112 branches, 192 partial.** Lowest measured modules: `catalog/protocols/mcp_client/transport.py` 68%, `catalog/tools/tool_registry/schema.py` 77%, `catalog/protocols/mcp_client/jsonrpc.py` 81%, `scripts/check_links.py` 81%.

### Test inventory — PRESENT
- 5 cross-cutting files in `tests/` (1 actually named in the README, 4 undocumented):
  - `tests/test_validate_catalog.py` (242 lines) — catalog contract validator incl. failure paths.
  - `tests/test_repo_status.py` (335 lines) — drift detector: parser, per-stage artifact rules, dependency rules, ADR-index rule, CLI exit codes, `--json`.
  - `tests/test_check_links.py` (105 lines) — link checker incl. depth errors, anchors, skip dirs.
  - `tests/test_check_phase_plan.py` (148 lines) — stage-chain order, charter-order equality, historical-reversal regression.
  - **`tests/test_gate_coverage.py` (284 lines) — the meta-test.** Asserts that every Python-holding top-level directory is classified (`SOURCE_DIRS` / `EXEMPT_DIRS`), that `testpaths` covers every test-holding directory, that `coverage.source` covers every gated directory, that the Makefile's mypy `find` traverses every gated directory, and does a live `pytest --collect-only integrations` run.
- In-tree capability tests: 7 files / 277 tests across the 5 catalog entries + 1 integration (25 tests).
- Assertion totals by file: `test_react_agent_loop.py` 45, `test_model_provider.py` 70, `test_execution_trace_recorder.py` 50, `test_mcp_client.py` 44, `test_tool_registry.py` 43, `test_adapter_json_safety.py` 10, `test_dispatcher_allowlist.py` 15, `test_end_to_end.py` 25.

### ABSENT
- **No `conftest.py` anywhere** (verified `find . -name conftest.py`; none outside `.venv`/`.uv-cache`).
- No test-time coverage gate in CI or Makefile (`ci.yml:86` runs `--cov-report=term-missing` only).
- No mutation testing, no property-based testing (no Hypothesis), no test-impact analysis, no flaky-test retry.
- No E2E/browser tests, no load/performance tests.
- `norecursedirs` excludes `study_pipeline`, but that tree has no code yet.

---

## 5. CI pipeline — what CI runs vs what the Makefile runs

**Single workflow:** `.github/workflows/ci.yml` (86 lines). Triggers: `push` on all branches, `pull_request`, `workflow_dispatch` (`ci.yml:12-16`). `permissions: contents: read` (`ci.yml:18-19`). One job `quality` on `ubuntu-latest` (`ci.yml:22-24`).

**Every step, in order, exact commands:**

| # | Line | Step | Command |
|---|---|---|---|
| 1 | 27-28 | Checkout | `actions/checkout@v4` (tag-pinned) |
| 2 | 30-33 | Install uv | `astral-sh/setup-uv@v5` with `enable-cache: true` |
| 3 | 35-38 | venv + toolchain | `uv venv --python 3.12` ; `uv pip install -r requirements-dev.txt` |
| 4 | 40-49 | Install gitleaks | curl `v8.30.1` linux_x64 tarball → `$HOME/.local/bin` ; append to `$GITHUB_PATH` |
| 5 | 51-56 | **Secret scan** | `gitleaks git . --no-banner --redact --exit-code 1` (full history) |
| 6 | 58-59 | Lint | `.venv/bin/ruff check .` |
| 7 | 61-62 | Format check | `.venv/bin/black --check .` |
| 8 | 64-68 | Type check | `find catalog scripts tests study_pipeline -name '*.py'` → `.venv/bin/mypy $targets` |
| 9 | 70-74 | Catalog contract (strict) | `.venv/bin/python scripts/validate_catalog.py --strict` |
| 10 | 76-77 | Markdown links | `.venv/bin/python scripts/check_links.py` |
| 11 | 79-80 | Phase plan vs charter | `.venv/bin/python scripts/check_phase_plan.py` |
| 12 | 82-83 | Governance drift | `.venv/bin/python scripts/repo_status.py` |
| 13 | 85-86 | Tests | `.venv/bin/pytest --cov --cov-report=term-missing` |

### CI vs Makefile — divergence analysis (the answer to "are they the same?")

**Substantially aligned, with four concrete divergences:**

1. **CI's mypy target list omits `integrations/`.** `ci.yml:66` — `find catalog scripts tests study_pipeline` — while `Makefile:72` uses `find catalog integrations scripts tests study_pipeline`. Note `tests/test_gate_coverage.py:244` asserts `(SOURCE_DIRS | {"tests"}) - searched == set()`, and `SOURCE_DIRS` includes `integrations` — **so this meta-test would fail if it parsed `ci.yml`; it only parses the Makefile (line 224).** The integration's code is therefore untyped in CI but typed locally.
2. **CI never runs `make` at all.** Every step hand-repeats a Makefile command. `make ci` is documented as "what CI runs" (`Makefile:115`) but CI does not invoke it, so the two can drift — and #1 proves they already have.
3. **Ordering differs**: Makefile `check-strict` = `lint typecheck validate-strict links phase-plan test`; CI runs validate-strict, then links, then phase-plan, then **drift**, then tests. CI adds the `repo_status.py` drift gate that `make check`/`make check-strict` do **not** include (`make status` is a standalone target).
4. **CI adds gitleaks** (step 5), which no Makefile target runs.

**Coverage:** CI runs `pytest --cov --cov-report=term-missing` — identical to `make coverage` (`Makefile:86`). No `fail_under`, so the coverage number is printed and ignored.

**CI hygiene — PARTIAL:** `actions/checkout@v4` and `astral-sh/setup-uv@v5` are **tag-pinned, not SHA-pinned** (`ci.yml:28,31`); the survey's own gap list item #4 flags this (`docs/audits/2026-09-16-usa-infrastructure-survey.md:116`). No `concurrency` group, no `timeout-minutes`, no matrix, no job-level caching beyond `setup-uv`'s own. No `actionlint`/`zizmor` YAML validation (survey items #2, `:97-100`).

### ABSENT from CI
- Dependency vulnerability scanning, SAST, SBOM, licence audit, Scorecard, coverage upload/badge, scheduled/cron workflows, release workflows, container builds, docs builds, matrix testing, artifact upload. Verified by `find .github` → exactly one file.

---

## 6. Secret scanning, SCA, SAST, licence audit, SBOM

| Control | Status | Evidence |
|---|---|---|
| **Secret scanning** | **PRESENT** | `.gitleaks.toml` (35 lines); CI step `ci.yml:51-56` scans **full history**; pre-commit `scripts/hooks/pre-commit:41-58` scans **staged changes** |
| — config policy | `[extend] useDefault = true` (`.gitleaks.toml:34-35`) — upstream ruleset extended, not replaced |
| — allowlist | **Deliberately none**, with a 25-line documented argument (`.gitleaks.toml:8-32`) including the reproduction commands proving the flagged sentinel is a false positive |
| — tool pinning | gitleaks `v8.30.1` pinned in CI (`ci.yml:46-49`) and documented in `docs/development.md:12,19`; locally verified installed at 8.30.1 |
| **Dependency vulnerability scanning (SCA)** | **ABSENT** | No `pip-audit`, `safety`, `osv-scanner`, `trivy`, `grype`, `dependabot` config. `SECURITY.md:74-76` states it honestly: *"There is no dependency vulnerability scanning in CI yet, and there are currently zero runtime dependencies."* Survey verdict: **ADOPT pip-audit** (`…survey.md:73`), still not implemented |
| **SAST** | **PARTIAL** | No standalone SAST. Ruff's `S` (flake8-bandit) ruleset is enabled (`pyproject.toml:105`) — that is a real static security lint over 63 files, but it is ~a subset of Bandit and is not run as a dedicated gate. Standalone Bandit: **ABSENT** (survey: **ADOPT now**, `…survey.md:76`, tracked as SUP-006). CodeQL/Semgrep: **ABSENT** (survey: DEFER) |
| **Licence auditing** | **PARTIAL — manual, not automated** | No `licensecheck`, `liccheck`, `reuse`, or allowlist tool. Compensating manual controls: a per-entry `PROVENANCE.md` in all 5 catalog entries; a research registry with a `code_reused` field and rules (`docs/registry/RESEARCH_REGISTRY.md:34-40`); `NOTICE:19-34` third-party notice section; charter §11/§22 human review gates (`docs/standards.md:82-98`). No tool enforces any of it |
| **SBOM** | **ABSENT** | No CycloneDX/SPDX generation anywhere. Survey: **DEFER until publishing** (`…survey.md:66-67`) |
| **Supply-chain posture** | **PARTIAL** | Only the gitleaks binary is version-pinned. No OpenSSF Scorecard, no SHA-pinned actions, no Sigstore/attestation, no provenance artifacts (survey items #4, #6, #7) |

---

## 7. Dependency update automation

### ABSENT — confirmed
- **No `.github/dependabot.yml`.** `.github/` contains exactly one file (`.github/workflows/ci.yml`).
- No Renovate config (`renovate.json`, `.renovaterc`), no `pin-freshness`/hygiene cron workflow (there is only one workflow, and it has no `schedule:` trigger).
- No `uv.lock`, so a bot would have nothing to refresh even if configured.

### Compensating manual mechanism — PARTIAL
- Regeneration is a documented manual procedure: `requirements-dev.txt:5-9` gives the exact `uv pip freeze > requirements-dev.txt` recipe; `docs/development.md:100-110` gives a 4-step "Adding a dependency" process.
- The gap is **known and tracked**: survey verdict **ADAPT** (`…survey.md:70`) — *"We have zero runtime deps, so this collapses to devDependencies-only… or simply DEFER and let Scorecard's dependency-update check remind us monthly."* Recorded in the Phase-1.5 backlog (`docs/roadmap.md:100`).

---

## 8. Commit message conventions and enforcement

### PARTIAL — convention is documented, enforcement is ABSENT
- **Documented convention (no format spec):** `CONTRIBUTING.md:50` — *"Commits: small, scoped to one capability or record."* That is scope guidance, not a grammar.
- **Observed practice** (28 commits, `git log --format='%s'`): an informal but consistent `<subject>: <LIFECYCLE TRANSITION>` / `<verb> <thing>` style, frequently citing ADRs. Examples: `tool-registry: IMPLEMENTED -> TESTED (first capability)`, `react-agent-loop: RESEARCHED -> UNDERSTOOD -> DECIDED (ADR-0008)`, `Build mcp-client: legacy MCP era, approval before the call (ADR-0009)`, `Close the sixth enforcement gap: integrations/ was ungated`. Conventional Commits is **not** used (`feat:`/`fix:` prefixes absent).
- **Enforcement: ABSENT.** No `commitlint`, no `commit-msg` git hook (only `pre-commit` exists), no CI step inspecting messages, no commit template (`.gitmessage`).
- Survey verdict: commitlint **REJECT for us** (no Node) but *"Commit discipline is still worth something"* (`…survey.md:47,55`).

---

## 9. Git hooks

### PRESENT — one hook, hand-written
- **`scripts/hooks/pre-commit`** (118 lines), version-controlled, bash, `set -euo pipefail`.
- **Installation:** `make install-hooks` (`Makefile:43-47`) copies it to `.git/hooks/pre-commit` and `chmod +x`. Removal via `make uninstall-hooks` (`Makefile:50-52`). Per-clone, not auto-installed — `docs/development.md:78` says so explicitly.
- **Environment guard** (`pre-commit:18-23`): if `.venv/bin/python` is missing it warns and **exits 0** (skips gates rather than blocking).
- **Staged-file detection** (`pre-commit:26-30`): `git diff --cached --name-only --diff-filter=ACM`; no staged files → exit 0.
- **Failure helper** (`pre-commit:32-39`) prints the charter §28 rule against `--no-verify`.

**Gates, in exact order:**

| # | Line | Gate | Condition to run | Command |
|---|---|---|---|---|
| 0 | 41-58 | **gitleaks** | **every commit** | `gitleaks git --staged --no-banner --redact --exit-code 1 -c .gitleaks.toml`; if binary missing → **WARN and skip** (never silent pass) |
| 1a | 60-63 | ruff | any staged `.py` | `.venv/bin/ruff check .` |
| 1b | 65-66 | black | any staged `.py` | `.venv/bin/black --check .` |
| 1c | 68-73 | mypy | any staged `.py` | same `find` as `Makefile:72` minus `integrations`? — matches Makefile (`catalog scripts tests study_pipeline`) |
| 2 | 76-80 | pytest | staged `^(catalog\|scripts\|tests)/.*\.py$` | `.venv/bin/pytest` |
| 3 | 82-87 | catalog contract | any staged `catalog/` | `python scripts/validate_catalog.py` (non-strict) |
| 3b | 89-96 | markdown links | any staged `.md` | `python scripts/check_links.py --quiet` |
| 3c | 98-106 | phase plan | staged `docs/phases/`, `TAXONOMY.md`, `AGENTS.md` | `python scripts/check_phase_plan.py --quiet` |
| 4 | 108-115 | **governance drift** | staged `TAXONOMY.md`, `specifications/`, `catalog/`, `docs/decisions/` | `python scripts/repo_status.py --quiet` |
| — | 117-118 | success | — | prints "all gates passed", exit 0 |

Each gate carries an inline comment recording the *historical defect* it exists to prevent (e.g. `pre-commit:89-91` — "41 broken links once accumulated here undetected").

### ABSENT
- No `pre-commit` (the Python framework), no `.pre-commit-config.yaml`, no lefthook/husky.
- No `commit-msg` hook, no `pre-push` hook, no `post-checkout`/`post-merge` hook.
- No bypass auditing (a `--no-verify` commit leaves no trace).

---

## 10. Branch / merge governance

### ABSENT across the board
- **No `.github/CODEOWNERS`** (or `CODEOWNERS`, `docs/CODEOWNERS`). Verified via `git ls-files | grep -i codeowners` → nothing.
- **No PR template** (`.github/PULL_REQUEST_TEMPLATE.md`, `.github/PULL_REQUEST_TEMPLATE/`).
- **No issue templates** (`.github/ISSUE_TEMPLATE/`, `config.yml`).
- **No `FUNDING.yml`, no `SECURITY.md`-adjacent GitHub config, no `dependabot.yml`.**
- **No branch-protection-as-code**, no merge queue config, no rulesets. (Note: branch protection is a server-side setting, not a repo file — but nothing in the repo *references* it either.)
- **`.github/` contains exactly one file:** `.github/workflows/ci.yml`.

### Compensating governance — PRESENT but social, not mechanical
- **`CONTRIBUTING.md:5-18` closes the repository to external contributions** outright, with the relicense-preservation rationale; `docs/decisions/README.md:25-31` records this as a reviewed, standing decision. With no outside PRs, CODEOWNERS/templates have little to gate.
- **Charter §22 human review gates** (`CHARTER.md:237-241`, enumerated in `docs/standards.md:78-98`): 9 categories requiring a human stop, including licensing changes, dependency additions, trust-boundary changes, mature-infrastructure deletion, production-readiness claims.
- **`docs/standards.md:100-112`** explicitly lists what is deliberately *not* automated (research sufficiency, design quality, failure-mode coverage, abstraction justification).
- The survey's verdict on CODEOWNERS/branch protection/merge queue is **REJECT** — *"Solo-maintainer, no PRs from outside… Nothing to encode."* (`…survey.md:81`).

### Note on process risk
Single branch (`master`), no remote, no tags. CI triggers on `pull_request` (`ci.yml:15`) but no PR flow exists in practice. There is no mechanism preventing a direct push to `master`.

---

## 11. Release / versioning / changelog

### ABSENT
- **No release process.** No `CHANGELOG.md` (or `CHANGES.md`, `HISTORY.md`, `RELEASES.md`), no `.releaserc`, no `release-please` config, no `python-semantic-release`/`[tool.semantic_release]`, no `towncrier`, no `bump2version`/`bumpver`.
- **No release workflow** — the single CI workflow has no `release`/`publish` trigger and no `tags:` trigger.
- **No git tags** (`git tag` empty) and **no version-bump automation**.
- Version exists in exactly one hand-maintained place: `pyproject.toml:3` → `version = "0.0.1"`.
- `SECURITY.md:3-14` states the situation honestly: *"pre-release, no tagged versions, no published artifacts. There is no supported release yet"* with a support table listing only `main (unreleased)` and `Tagged releases — none exist yet`.
- The package is not published (`[build-system]` hatchling config exists at `pyproject.toml:33-38`, `packages = ["catalog"]` at line 38, but nothing invokes a build).

### Rationale on record
Survey verdict for release tooling: **DEFER (all of it)** — *"We publish no package and have no versioned artifacts; adopting a release bot today would gate commits for a machine we never run."* (`…survey.md:55`). Structural note: *"USA is a product that ships… while we are a lab that accumulates verified capability."* (`…survey.md:38`).

---

## 12. Documentation automation (link checking, drift detection, fact syncing)

### PRESENT — three custom checkers, all wired into Makefile + pre-commit + CI

**`scripts/check_links.py`** (99 lines)
- Purpose: verify **relative** Markdown links resolve to real files.
- CLI: `[--root PATH] [--quiet]`; exit 1 on any broken link.
- Mechanics: regex `\[[^\]]+\]\(([^)\s]+)\)` (line 30); skips `http(s)://`, `mailto:`, `tel:`, pure `#anchor` (lines 37,58-63); strips `#fragment` before resolving (line 64); skips `.git/.venv/.uv-cache/.ruff_cache/.mypy_cache/.pytest_cache` (lines 33-35,44).
- Wired: `Makefile:93`, `pre-commit:94`, `ci.yml:77`. Called by `make validate` via dependency (`Makefile:89`).
- **Measured:** 354 links across 107 files, 0 broken.
- Tested by `tests/test_check_links.py` (13 tests). Historical defect documented at `check_links.py:5-13` (41 links once broken).

**`scripts/repo_status.py`** (519 lines) — the **governance drift detector**, the repository's flagship mechanism
- Purpose: make it impossible for `TAXONOMY.md` to claim a lifecycle status the artifacts do not support (charter §4).
- CLI: `[--root PATH] [--quiet] [--json]`; exit 1 when any **error**-severity drift exists.
- Mechanics: a deliberate stdlib-only mini-YAML parser for the `TAXONOMY.md` fenced block (`_parse_capabilities`, lines 94-173) handling inline lists, block lists, comments and quoted values; a 12-stage `LIFECYCLE` tuple (lines 31-44).
- **`check_capability` (lines 201-354) enforces per-stage artifact existence:** DECIDED+ requires a non-`pending` `decision`; DESIGNED+ requires `specifications/<id>.md` **to exist**; RESEARCHED+ requires `research_records` **non-empty AND every cited path to exist** (lines 254-281); IMPLEMENTED+ requires the `implementation` path to exist; TESTED+ requires the `tests` path to exist; BENCHMARKED+ requires `benchmarks`; pre-artifact stages that over-claim get a warning; unknown status is an error.
- **`check_dependencies` (357-391):** every `depends_on` id exists; a dependency may not lag its dependent (warning).
- **`check_adr_index` (394-418):** every `docs/decisions/NNNN-*.md` must be named in `docs/decisions/README.md` — an unlisted ADR is an error.
- `count_catalog_entries` (421-433) and `summarize` (436-442) feed the human report; `--json` (480-493) emits machine-readable output.
- Wired: `Makefile:122` (`make status`), `pre-commit:113`, `ci.yml:83`. **Not** part of `make check`/`check-strict`.
- Tested by `tests/test_repo_status.py` (~30 tests) incl. CLI non-zero on injected drift and `--json` validity.
- **Measured:** tracks 7 capabilities, 5 catalog entries, distribution `DISCOVERED 2 · TESTED 5`, **0 drift**.

**`scripts/check_phase_plan.py`** (125 lines)
- Purpose: verify documented stage transitions in prose agree with the charter §4 order.
- CLI: `[--root PATH] [--quiet]`; exit 1 on an out-of-order chain.
- Mechanics: regex matching backticked arrow-chains of known stages (line 54), accepting both `→` and `->`; scans every `docs/phases/**/*.md` plus `TAXONOMY.md` and `AGENTS.md` (lines 60-63, 81-87); the `LIFECYCLE` tuple is **deliberately duplicated** rather than imported from `repo_status.py` so a lifecycle change cannot happen in one silent edit (lines 31-35).
- Wired: `Makefile:97`, `pre-commit:104`, `ci.yml:80`.
- Tested by `tests/test_check_phase_plan.py` (15 tests) incl. a regression pinning the historical reversal, and `test_lifecycle_matches_repo_status` asserting the two duplicated tuples stay equal.
- **Measured:** 0 out-of-order transitions.

**`scripts/validate_catalog.py`** (285 lines) — the catalog entry contract
- CLI: `[--root PATH] [--strict]`; exit 1 on errors.
- Mechanics: 20 declared `CATEGORIES` (lines 32-53) must each exist **and** carry a `README.md` whose H2s include `what it is` and `why it exists` (lines 57-60,139-157); each entry subdirectory must carry `README.md` + `PROVENANCE.md` (lines 63-66,169-171) with required H2 sections `what it is`, `how it works`, `our implementations`, `references` (lines 69-74,179-183); `examples/` and `tests/` are **warnings** normally, **errors** under `--strict` (lines 185-191); **an empty `tests/` dir (no `test_*.py`) is an error in every mode** (lines 197-206) — the fix for a real hole; an empty `examples/` is an error (lines 213-221); `PROVENANCE.md` must be readable UTF-8.
- Wired: `Makefile:90,102`, `pre-commit:85`, `ci.yml:74` (**strict in CI, lenient in pre-commit** — deliberate, `ci.yml:71-73`).
- Tested by `tests/test_validate_catalog.py` (~15 tests).
- **Measured:** 0 errors, 0 warnings, 5 entries.

### PARTIAL / ABSENT
- **No fact-syncing / content-inlining** (no `usa:fact`-style markers). Survey verdict: **ADAPT, later** (`…survey.md:91`).
- **No external link checking** — `check_links.py` is internal-only by design (offline CI). Survey: **DEFER** lychee, noting external links belong on a monthly cron (`…survey.md:94`).
- **No ADR numbering/index automation** — `repo_status.py:408-417` validates only *presence in the index*, not numbering sequence or gaps.
- **No docs-site build** — no mkdocs, Sphinx, Docusaurus, or Read the Docs config; no markdownlint, no Vale, no prose linter.
- **No scheduled/drift cron** — no workflow has a `schedule:` trigger. Survey item #6 proposes a monthly hygiene cron (`…survey.md:118`).
- **No stale-content detection.** This is a demonstrated gap, not a hypothetical: `docs/roadmap.md` records three instances where READMEs kept claiming "no entries yet" after an entry landed, and `docs/architecture.md:40` **still says "Skeleton only (Phase 1). No catalog entries exist"** while 5 entries exist. `check_links.py` cannot catch this class.

### Human-maintained docs that serve as the sync mechanism
- `docs/roadmap.md` "Latest session notes" — charter §25.10 requires a note per session; it is the de-facto changelog (101 lines, ~16 sessions narrated).
- `TAXONOMY.md` — the machine-readable registry that `repo_status.py` gates (275 lines, 7 capabilities).
- `docs/registry/RESEARCH_REGISTRY.md` — 1142 lines, 21 project entries, the licensing/attribution ledger.
- `AGENTS.md:20-29` mandates the end-of-session updates (taxonomy, registry, roadmap) — enforced by convention and partly by the drift gate, not by a dedicated checker.

---

## 13. Data / config handling, secrets, `.env`

### PRESENT (minimal, appropriate to a zero-dependency library)
- **No runtime configuration system at all** — deliberate: zero runtime deps (`pyproject.toml:11-20`), and every capability is specified stdlib-only.
- **`.gitignore` (30 lines)** covers `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `build/`, `dist/`, `.venv/`, `venv/`, **`.env`** (line 12), all four tool caches, `.coverage`, `htmlcov/`, `.uv-cache/`, study-pipeline checkouts (line 25), and OS/editor files.
- **Secret handling:** no secrets in the repo; `.env` is gitignored; gitleaks scans staged + full history. The one flagged literal is a documented sentinel (`integrations/agent_loop_end_to_end/system.py`, adjudicated at `.gitleaks.toml:11-25`).
- **Config-as-data:** `.usa/foundation.yaml` (71 lines) — a declarative project-intent file (vision, intents `library/cli/docs-site`, stage `prototype`, pillar requirements, `minCoverage: 0`, pipelines). It is a *deterministic input to the USA audit*, not runtime config.
- **Catalog entries treat config explicitly:** `catalog/protocols/mcp_client/approvals.py` implements an approval policy that **defaults to deny**; `catalog/observability/execution_trace_recorder/capture.py` implements content capture **off by default** as a policy object. These are library-level config/safety seams.

### ABSENT
- **No `.env.example` / `environment:` exemplar.** Verified: no tracked file matches `\.env`; `.usa/foundation.yaml:56-57` explicitly records `environment: files: []`.
- No `config.yaml`/`settings.toml`/pydantic-settings, no secrets manager integration, no env-var validation.
- (Correctly absent: nothing is deployed and nothing reads env vars.)

---

## 14. Observability of the repository itself

### PRESENT — this is the repository's strongest differentiator
- **`make status`** — human + `--json` machine-readable repository state report (`repo_status.py:480-513`): capabilities tracked, catalog entries present, lifecycle distribution, and every drift finding with severity and the offending `TAXONOMY.md` line.
- **Drift detection across 6 rule classes** (lifecycle artifact existence, dependency validity, ADR index completeness, unrecognized statuses, over-claiming pre-artifact stages, missing research records) — see §12.
- **`make bench`** — a guarded no-op that reports "No benchmarks defined yet (charter §19)" rather than silently passing (`Makefile:129-133`).
- **Four USA audit passes recorded** in `docs/audits/` (7 files, 2640 lines): two raw machine outputs (`2026-09-15-usa-raw*.md`, `2026-09-16-usa-raw.md`) and three adjudicated human-readable audits + one peer-infrastructure survey. Scores are tracked over time: 71.4 → 72.4 → 73.3. This is a real, repeated external self-measurement loop.
- **The audit trail is honest about its own errors** — `2026-09-16-usa-audit-adjudicated.md:9-…` opens with "Correction to the first draft of this file".
- **Testing of the gates themselves** — `tests/test_gate_coverage.py` is essentially an observability mechanism for the enforcement layer: it asserts no source directory can go ungated.

### PARTIAL / ABSENT
- **No scheduled/automated status reporting** — `make status` is pull-based and manual; the drift gate only runs on the paths listed in `pre-commit:111` and in CI.
- **No coverage trend/ratchet**, no badge, no metrics history. `.coverage` exists locally (gitignored).
- **No dashboards, no health checks, no telemetry** (nothing is deployed).
- Survey's "cron-reminds / CI-gates" split — rated *"a clearer separation than anything we have"* (`…survey.md:130`) — is **ABSENT**.

---

## 15. Containerization

### ABSENT — complete
- No `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `Containerfile`, `devcontainer.json`, `.devcontainer/`, Kubernetes/Helm manifests, `Procfile`.
- No container build step in CI; `ci.yml` runs directly on `ubuntu-latest`.
- Survey notes devcontainer appears only in USA audit *findings* (`docs/audits/*-usa-raw*.md`), never as an implementation.
- **Rationale:** the repository ships a pure-Python, zero-runtime-dependency library — nothing is deployed, so there is nothing to containerize at Phase 1.

---

## 16. Error / licence / provenance metadata

### PRESENT — deliberately strong
- **Licence:** `LICENSE` (Apache-2.0, full text, 11358 bytes); `pyproject.toml:7-8` declares `license = "Apache-2.0"` + `license-files = ["LICENSE"]`; **ADR-0002** (`docs/decisions/0002-license-selection.md`) records the choice against MIT/AGPL/BSL alternatives; `README.md:53-57` and `SECURITY.md:78-81` restate it.
- **`NOTICE` (33 lines):** Apache-2.0 boilerplate + a "THIRD-PARTY NOTICES" section (lines 18-24) stating *no* third-party code has been copied, plus the rule that `code_reused: true` requires adding notice text *in the same change* (lines 26-34).
- **Per-entry `PROVENANCE.md`** — all 5 catalog entries carry one. Format (from `catalog/tools/tool_registry/PROVENANCE.md:7-16`): a 6-question table answering copied / derivative / informed-by / NOTICE-required / attribution-required / provenance-class, then a per-project table of exactly what concept was taken and each project's licence (`:24-29`), then an explicit statement that no file, function, docstring or test was transliterated (`:31-34`).
- **Research registry** (`docs/registry/RESEARCH_REGISTRY.md`, 1142 lines, 21 entries) with a 19-field schema (lines 11-31) including `license`, `version_studied`, `code_reused`, `attribution_requirements`, `our_implementation`, `compatibility_status`, `last_reviewed`, plus 6 governance rules (lines 34-40) and a license-compatibility note at line 1134.
- **Evidence-class labeling** mandated for non-obvious claims: FACT / OBSERVATION / INFERENCE / DESIGN OPINION / EXPERIMENTAL RESULT (charter §6; `docs/README.md:34-35`, `CONTRIBUTING.md:49`).
- **Error taxonomy as a design principle**, consistently applied across capabilities: `catalog/tools/tool_registry/errors.py` (failure taxonomy by *model-actionability*, ADR-0006 D-4), `catalog/models/model_provider/errors.py` (normalized provider errors), `catalog/agents/react_agent_loop/errors.py` (`UnactionableToolError`), `catalog/protocols/mcp_client/errors.py` (named protocol errors incl. the modern-era refusal), `catalog/observability/execution_trace_recorder/errors.py`. Each is a dedicated module, not bare `Exception`.
- **`security:` metadata field** in every taxonomy entry pointing at the capability's security section (e.g. `TAXONOMY.md:118,144,170,246,271`).
- **`compatibility:` metadata field** naming the bounded compatibility claim (`TAXONOMY.md:249,274`) — e.g. mcp-client restricted to "Legacy MCP era only (2025-11-25 and earlier)".

### PARTIAL
- Provenance/licence review is **human-only**; no tool validates `PROVENANCE.md` content (the catalog validator only checks the file is present and UTF-8-readable, `validate_catalog.py:223-227`).
- No SPDX headers in source files; no `REUSE` compliance; no machine-readable licence audit output.

---

## 17. Root governance / documentation file roles (one line each)

| File | Role |
|---|---|
| `CHARTER.md` (322 lines) | The constitution: 32 sections in 7 parts — mission, lifecycle §4, human review gates §22, session protocol §25, output contract §27; source of truth on any conflict. |
| `TAXONOMY.md` (275 lines) | Machine-readable capability registry (7 entries, 28-field schema) + category tree; parsed and gated by `repo_status.py`. |
| `AGENTS.md` (45 lines) | Level-2 operating instructions for AI agent sessions: start-of-session checklist, environment gates, hard rules, end-of-session resumability protocol. |
| `CONTRIBUTING.md` (50 lines) | Contribution policy — states external contributions are **not accepted** (relicense preservation), plus the 5 golden rules and the adding-a-capability procedure. |
| `SECURITY.md` (81 lines) | Security policy: supported versions (none), private vulnerability reporting route, response SLAs, scope/threat model, and an explicit known-limitations section. |
| `README.md` (57 lines) | Orientation table, current status (Phase 1 — Seed), getting-started commands, working method, licence. |
| `NOTICE` (33 lines) | Apache-2.0 attribution + third-party notices section with the `code_reused` update rule. |
| `LICENSE` | Apache License 2.0 full text. |
| `docs/README.md` (37 lines) | Documentation index: prescribed reading order + documentation rules (state status, charter wins, label evidence class, don't duplicate the charter). |
| `docs/standards.md` (133 lines) | **The enforceable standards table** — 30 numbered rules (H1-H5, L1-L8, C1-C7, T1-T10, D1-D6) each mapped to the check that enforces it, plus a rule-to-check map and the "deliberately not automated" list. |
| `docs/development.md` (117 lines) | Environment setup, prerequisites table (uv 0.12.1, git 2.55.0, gitleaks 8.30.1), toolchain roles, gates table, drift-detection behaviour, adding-a-dependency procedure, troubleshooting. |
| `docs/architecture.md` (40 lines) | How the repository itself is organized: knowledge plane / code plane / machinery split, 5 design rules. **Stale at line 40** ("No catalog entries exist" — 5 exist). |
| `docs/philosophy.md` (24 lines) | Distilled engineering attitude: 8 principles + the 13-item priority order for trade-offs. |
| `docs/roadmap.md` (101 lines) | Current phase, phase status table, Phase-1 capability queue, explicit non-goals, and ~16 narrative session notes functioning as a changelog. |
| `docs/registry/RESEARCH_REGISTRY.md` (1142 lines) | The external-project/attribution ledger: 19-field schema, 6 rules, 21 studied projects, licence-compatibility note. |
| `docs/decisions/README.md` (31 lines) | ADR index (0000-0010 with status), when-an-ADR-is-required rules, and one standing open human decision. |
| `scripts/README.md` (23 lines) | Script inventory table + usage + rules ("scripts are infrastructure: they carry tests"). |
| `tests/README.md` (24 lines) | Cross-cutting test index + running instructions + rules. **Stale:** lists only 1 of 5 test files and claims "11 passed". |
| `specifications/README.md` (29 lines) | Spec rules, naming convention, required spec contents, and a status table for the 5 specs. |
| `integrations/README.md` (23 lines) | Integration rules + status table (1 integration). |
| `benchmarks/README.md` (25 lines) | Benchmark methodology rules and the 6 honesty questions; status: empty. |
| `examples/README.md` (25 lines) | Example rules; status: "Empty. No catalog entries exist yet." — **stale** (5 entries exist). |
| `study_pipeline/README.md` (40 lines) | Phase-2 declared seam: intended 8-step pipeline, planned components, honesty constraints; not implemented. |
| `study_pipeline/studied_repos/README.md` (18 lines) | Report format contract for studied repositories; status: empty. |
| `research/*/README.md` (19 files) | Per-category research stubs (what/why headings required by the catalog validator). |
| `catalog/*/README.md` (20 files) | Per-category catalog documentation with the required `## What it is` / `## Why it exists` H2s. |
| `.usa/foundation.yaml` (71 lines) | Declarative project-intent input to the USA auditor (vision, intents, stage, pillars, testing bar, pipelines). |

### Explicit presence checks requested

| Artifact | Status | Evidence |
|---|---|---|
| `CODE_OF_CONDUCT.md` | **ABSENT** | not in `git ls-files`; `.usa/foundation.yaml:39` declares `codeOfConduct: false` |
| `GOVERNANCE.md` | **ABSENT** | not in `git ls-files`; survey §2 lists it as a USA-only file (`…survey.md:34`) |
| `CITATION.cff` | **ABSENT** | not present; survey verdict **DEFER until public** (`…survey.md:105`) |
| `.editorconfig` | **ABSENT** | not present; survey verdict **ADOPT** (`…survey.md:105,121`) — a recommended-but-unimplemented item |
| `dependabot.yml` | **ABSENT** | `.github/` has exactly 1 file |
| `CODEOWNERS` | **ABSENT** | not present; survey verdict **REJECT** as out of scope (`…survey.md:81`) |
| Issue templates | **ABSENT** | no `.github/ISSUE_TEMPLATE/` |
| PR template | **ABSENT** | no `.github/PULL_REQUEST_TEMPLATE.md` |
| `CHANGELOG.md` | **ABSENT** | not present; `docs/roadmap.md` session notes serve informally |
| Release process | **ABSENT** | no release workflow/tooling/tags; `SECURITY.md:5-6` states no releases exist |
| `.env.example` | **ABSENT** | no tracked `.env*`; `.usa/foundation.yaml:56-57` records `environment.files: []` |

---

## 18. Structural tree with counts

### `catalog/` — 20 declared categories, **5 entries**, 50 `.py` files
```
catalog/
├── agents/react_agent_loop/          1 entry  (adapters, errors, loop, observations,
│                                                protocols, repetition + examples/ tests/
│                                                README.md PROVENANCE.md)
├── models/model_provider/            1 entry  (errors, provider, request, stream,
│                                                transport, types + providers/{anthropic,
│                                                gemini,openai} + examples/ tests/)
├── observability/execution_trace_recorder/ 1 entry (bounds, capture, clock, errors,
│                                                recorder, records + examples/ tests/)
├── protocols/mcp_client/             1 entry  (approvals, client, errors, framing,
│                                                jsonrpc, projection, transport +
│                                                examples/ tests/)
├── tools/tool_registry/              1 entry  (errors, ids, registry, schema +
│                                                examples/ tests/)
└── [data, deployment, evaluation, finetuning, frameworks, governance, harness,
   memory, orchestration, primitives, prompt-engineering, retrieval, runtime,
   safety, skills]/                  **15 empty categories** — each holds only its
                                     required category README.md
```
Entry counts by category: agents 1, models 1, observability 1, protocols 1, tools 1, all others 0. Total **5**. Every entry has `README.md`, `PROVENANCE.md`, `examples/`, `tests/` — the full contract.

### `integrations/` — 1 entry, 5 tracked files
`integrations/agent_loop_end_to_end/` — `__init__.py`, `scripted_transport.py`, `system.py`, `tests/test_end_to_end.py` (25 tests), `README.md`. Composes tool-registry + model-provider-abstraction + react-agent-loop.

### `specifications/` — **5 specs** + README
`execution-trace-recorder.md`, `mcp-client.md`, `model-provider-abstraction.md`, `react-agent-loop.md`, `tool-registry.md`.

### `research/` — 19 category dirs, **5 records**, 24 `.md` total
Records: `agents/react-agent-loop.md`, `mcp/mcp-client.md`, `models/model-provider-abstraction.md`, `observability/execution-trace-recorder.md`, `tools/tool-registry.md`. 14 category dirs hold only a README stub.

### `docs/` — 33 `.md` files
- `docs/decisions/` — **11 ADRs** (0000-0010) + `README.md`
- `docs/phases/` — **6 phase plans** (phase-0-foundation … phase-5-sustain) + `README.md`
- `docs/audits/` — **7 files** (3 USA machine outputs, 3 adjudicated audits, 1 peer-infrastructure survey)
- root docs — `architecture.md`, `development.md`, `philosophy.md`, `README.md`, `roadmap.md`, `standards.md`
- `docs/registry/RESEARCH_REGISTRY.md`

### `benchmarks/` — README only (empty)
### `examples/` — README only (empty)
### `study_pipeline/` — README + `studied_repos/README.md` only (empty, Phase 2 seam)
### `scripts/` — 4 `.py` + 1 hook + README
### `tests/` — 5 `.py` + README
### `.github/` — 1 file (`workflows/ci.yml`)
### `.usa/` — 1 file (`foundation.yaml`)

---

## 19. Cross-cutting mechanisms worth naming explicitly

These are structural mechanisms the sibling repos will likely lack, and they are the repository's actual differentiators:

1. **Mechanical honesty enforcement (charter §4).** `repo_status.py` makes a false lifecycle claim a build failure. This is the single most distinctive mechanism.
2. **Meta-tests over the enforcement layer.** `tests/test_gate_coverage.py` asserts that new source/test directories *cannot* be silently ungated — and it was written after six real instances of the "presence was checked, validity was not" bug class (documented at `test_gate_coverage.py:5-23`).
3. **Every gate carries its own origin story.** Inline comments in `pre-commit`, `.gitleaks.toml`, `check_links.py`, `check_phase_plan.py` and `ci.yml` record the specific historical defect the gate prevents. This is unusual and directly enables drift analysis.
4. **Rule-to-check mapping.** `docs/standards.md` maps 30 rules to enforcing commands; anything unautomatable is explicitly listed as such (`standards.md:100-112`) rather than left ambiguous.
5. **Evidence-class vocabulary** (FACT/OBSERVATION/INFERENCE/DESIGN OPINION/EXPERIMENTAL RESULT) applied across research docs and registry entries.
6. **Negative-result preservation.** Specs and taxonomy record *deferred* and *not-protected-against* explicitly (e.g. `TAXONOMY.md:249,274`), and `.gitleaks.toml:8-32` documents a deliberately-absent allowlist.
7. **Deliberate duplication as a safety property.** `check_phase_plan.py:31-35` duplicates the lifecycle tuple on purpose so a change requires two edits; pinned by `test_lifecycle_matches_repo_status`.
8. **Repeated external audit loop** with adjudication and self-correction (7 audit files, scores trended 71.4 → 72.4 → 73.3).

---

# (a) Coverage statement

**Files read in full (or read for every relevant line):**

*Configuration & tooling (9):* `.github/workflows/ci.yml` (all 86 lines), `Makefile` (all 133), `pyproject.toml` (all 183), `requirements-dev.txt` (all 33), `.gitleaks.toml` (all 35), `.gitignore` (all 30), `.python-version` (1), `.usa/foundation.yaml` (all 71), `scripts/hooks/pre-commit` (all 118).

*Scripts (5):* `scripts/repo_status.py` (all 519), `scripts/validate_catalog.py` (all 285), `scripts/check_phase_plan.py` (all 125), `scripts/check_links.py` (all 99), `scripts/README.md` (all 23).

*Tests (6):* `tests/README.md` (all 24), `tests/test_gate_coverage.py` (all 284), plus `tests/test_check_links.py`, `tests/test_check_phase_plan.py`, `tests/test_repo_status.py`, `tests/test_validate_catalog.py` — **read at function-signature/name granularity plus full read of `test_gate_coverage.py`; individual test bodies of the latter four were inspected via their names/docstrings and the modules they exercise, not read line-by-line end to end.**

*Governance & docs (read in full):* `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `NOTICE`, `AGENTS.md` (via system injection + direct read), `docs/README.md`, `docs/standards.md` (all 133), `docs/development.md` (all 118), `docs/architecture.md` (all 40), `docs/philosophy.md` (all 24), `docs/decisions/README.md` (all 31), `docs/audits/2026-09-16-usa-infrastructure-survey.md` (all 134), `specifications/README.md`, `integrations/README.md`, `benchmarks/README.md`, `examples/README.md`, `study_pipeline/README.md`, `study_pipeline/studied_repos/README.md`, `catalog/tools/tool_registry/PROVENANCE.md` (partial — summary + study tables).

*Read at structure/extract granularity:* `TAXONOMY.md` (full YAML registry block read in full via `repo_status.py` execution + direct grep of all 7 entries' fields; prose §1-§3 read), `CHARTER.md` (all 32 section headings enumerated; first 60 lines read in full; individual sections consulted by reference from `docs/standards.md`), `docs/roadmap.md` (head + tail read in full; middle session notes read), `docs/registry/RESEARCH_REGISTRY.md` (header, schema, rules, and the full 25-heading structure read; individual project entries not read line-by-line), `docs/phases/README.md` (all), `docs/audits/*.md` (headers of all 7; survey read fully; adjudicated audit partially).

*Empirically executed:* `ruff check .`, `black --check .`, `mypy` over 63 files, `pytest --cov` (411 tests, 90%), `scripts/repo_status.py`, `scripts/check_links.py`, `scripts/validate_catalog.py --strict`, `scripts/check_phase_plan.py`, `gitleaks version`, plus `git log`/`git tag`/`git remote`/`git ls-files` enumerations.

**Not read (and why):**
- **Bodies of the 382 capability/unit test functions** across the 5 catalog entries and the integration — their *existence, count, naming and coverage contribution* were verified; reading 382 test bodies is not required to inventory the mechanisms, and their coverage was measured empirically instead.
- **`CHARTER.md` §5-§32 narrative prose in full** — section headings, purposes and every normative rule were captured through `docs/standards.md`'s rule-to-charter-section map and direct citation; the charter is documentation, and the code is authoritative per the task brief.
- **The 21 individual registry entry bodies** in `RESEARCH_REGISTRY.md` (1142 lines).
- **The 5 specifications' full bodies** (structure and status confirmed via `specifications/README.md` + file listing).
- **`catalog/**` implementation module bodies** — 50 files across 5 entries; their public surfaces were confirmed via `__init__.py` listings, error modules, README/PROVENANCE presence, mypy's 63-file clean pass, and coverage per-module numbers.
- **`LICENSE`** full text (identified as Apache-2.0 boilerplate; 11358 bytes).
- **`docs/audits/*-usa-raw*.md`** (3 machine-generated reports, ~2165 lines) — headers read; they are tool output, not repo mechanism.
- **Ignored/untracked trees:** `.venv/`, `.uv-cache/` (thousands of vendored files), `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.coverage`, and `__pycache__` dirs inside `integrations/`.

**Nothing material was inaccessible.** No sandbox denials occurred; all gates ran successfully.

---

# (b) Baseline fundamentals inventory

Flat list of every engineering mechanism confirmed present, one line each, with its implementing file.

- Python version pinned to 3.14.7 — `.python-version:1`
- `requires-python >= 3.12` declared — `pyproject.toml:6`
- Dev toolchain fully pinned, direct + transitive (17 pkgs) — `requirements-dev.txt:16-33`
- Direct dev deps declared as intent in pyproject — `pyproject.toml:22-31`
- Lockfile regeneration procedure documented — `requirements-dev.txt:5-9`
- Deterministic env creation target — `Makefile:31-35`
- Workspace-local uv cache exported — `Makefile:18-20`
- CI recreates the pinned environment — `.github/workflows/ci.yml:35-38`
- External binary (gitleaks 8.30.1) curl-pinned by version — `.github/workflows/ci.yml:46-49`
- Task runner with 19 documented targets — `Makefile` (`help` self-documenting at `:24-25`)
- Aggregate gate `make check` — `Makefile:109`
- Strict aggregate gate `make check-strict` — `Makefile:112`
- CI-equivalent aggregate `make ci` — `Makefile:115`
- Hook install/uninstall targets — `Makefile:42-52`
- Benchmark target, guarded no-op — `Makefile:129-133`
- Ruff lint, 19 rule families incl. flake8-bandit `S` — `pyproject.toml:89-117`
- Ruff per-file ignores, each justified inline — `pyproject.toml:119-139`
- Ruff relative-import ban with per-path exemptions — `pyproject.toml:144-145,123,130,134,139`
- Black formatting (sole formatter; ruff formatter deliberately unused) — `pyproject.toml:154-156`, `docs/decisions/0003-*.md`
- Mypy `strict = true` + 7 extra strictness flags — `pyproject.toml:162-178`
- Mypy override for tests — `pyproject.toml:180-183`
- Mypy target list built by `find` to tolerate empty categories — `Makefile:69-78`
- pytest 9.1.1 with `--strict-markers --strict-config` — `pyproject.toml:59`
- pytest `filterwarnings = ["error"]` — `pyproject.toml:65`
- 3 registered markers (`slow`, `network`, `external`) — `pyproject.toml:60-64`
- `testpaths` covering `tests`, `catalog`, `integrations` — `pyproject.toml:54`
- Branch coverage enabled — `pyproject.toml:67-70`
- Coverage source = catalog + integrations + scripts — `pyproject.toml:69`
- Coverage reporting recipe — `Makefile:85-86`, `.github/workflows/ci.yml:86`
- Cross-cutting test suite (5 files) — `tests/*.py`
- **Meta-test asserting no source dir can go ungated** — `tests/test_gate_coverage.py:81-101`
- Meta-test asserting `testpaths` covers every test-holding dir — `tests/test_gate_coverage.py:127-142`
- Meta-test asserting `coverage.source` covers every gated dir — `tests/test_gate_coverage.py:192-210`
- Meta-test asserting the Makefile mypy `find` traverses every gated dir — `tests/test_gate_coverage.py:218-249`
- Meta-test doing a live `pytest --collect-only` proof — `tests/test_gate_coverage.py:257-284`
- 277 in-tree capability tests across 5 entries — `catalog/*/*/tests/`
- 25 integration tests — `integrations/agent_loop_end_to_end/tests/test_end_to_end.py`
- Single CI workflow on push/PR/dispatch — `.github/workflows/ci.yml:12-16`
- CI least-privilege `contents: read` — `.github/workflows/ci.yml:18-19`
- CI secret scan over **full history** — `.github/workflows/ci.yml:51-56`
- CI ruff step — `.github/workflows/ci.yml:58-59`
- CI black step — `.github/workflows/ci.yml:61-62`
- CI mypy step — `.github/workflows/ci.yml:64-68`
- CI strict catalog contract — `.github/workflows/ci.yml:70-74`
- CI markdown link integrity — `.github/workflows/ci.yml:76-77`
- CI phase-plan check — `.github/workflows/ci.yml:79-80`
- CI governance drift check — `.github/workflows/ci.yml:82-83`
- CI test + coverage step — `.github/workflows/ci.yml:85-86`
- gitleaks config extending upstream ruleset — `.gitleaks.toml:34-35`
- gitleaks **documented-absent allowlist** with reproduction proof — `.gitleaks.toml:8-32`
- Pre-commit hook, version-controlled, hand-written bash — `scripts/hooks/pre-commit`
- Hook skips gracefully without a venv — `scripts/hooks/pre-commit:18-23`
- Hook staged-file detection limiting slow gates — `scripts/hooks/pre-commit:26-30`
- Hook gitleaks gate on every commit — `scripts/hooks/pre-commit:41-58`
- Hook ruff/black/mypy gates for `.py` changes — `scripts/hooks/pre-commit:60-74`
- Hook pytest gate for catalog/scripts/tests changes — `scripts/hooks/pre-commit:76-80`
- Hook catalog contract gate — `scripts/hooks/pre-commit:82-87`
- Hook markdown-link gate — `scripts/hooks/pre-commit:89-96`
- Hook phase-plan gate — `scripts/hooks/pre-commit:98-106`
- Hook governance-drift gate — `scripts/hooks/pre-commit:108-115`
- Hook anti-`--no-verify` messaging — `scripts/hooks/pre-commit:32-39`
- Governance drift detector with 6 rule classes — `scripts/repo_status.py:201-418`
- Drift detector machine-readable `--json` mode — `scripts/repo_status.py:480-493`
- Drift detector lifecycle-distribution report — `scripts/repo_status.py:436-442,495-505`
- ADR-index completeness check — `scripts/repo_status.py:394-418`
- Dependency-validity check — `scripts/repo_status.py:357-391`
- stdlib-only TAXONOMY YAML parser (zero deps) — `scripts/repo_status.py:94-173`
- Catalog entry-contract validator — `scripts/validate_catalog.py`
- Validator requiring 20 category dirs + category README sections — `scripts/validate_catalog.py:32-60,139-157`
- Validator requiring entry README + PROVENANCE + 4 H2 sections — `scripts/validate_catalog.py:63-74,169-183`
- Validator rejecting **empty** `tests/` in every mode — `scripts/validate_catalog.py:197-206`
- Validator rejecting empty `examples/` — `scripts/validate_catalog.py:213-221`
- Validator `--strict` mode (used by CI only) — `scripts/validate_catalog.py:261-265`, `.github/workflows/ci.yml:74`
- Relative Markdown link checker — `scripts/check_links.py`
- Link checker handling anchors/external/skip-dirs — `scripts/check_links.py:33-67`
- Phase-plan vs charter-lifecycle checker — `scripts/check_phase_plan.py`
- Deliberate lifecycle-tuple duplication as a safety property — `scripts/check_phase_plan.py:31-35`, `tests/test_check_phase_plan.py:140`
- Per-entry provenance document (all 5 entries) — `catalog/*/*/PROVENANCE.md`
- Research registry with licensing/attribution schema (21 entries) — `docs/registry/RESEARCH_REGISTRY.md`
- Apache-2.0 licence declared + file — `pyproject.toml:7-8`, `LICENSE`
- Third-party NOTICE section + `code_reused` update rule — `NOTICE:18-34`
- Licence-choice ADR — `docs/decisions/0002-license-selection.md`
- External-contribution prohibition with rationale — `CONTRIBUTING.md:5-18`
- Security policy with private reporting route + SLAs — `SECURITY.md:16-40`
- Security threat model with explicit out-of-scope list — `SECURITY.md:42-76`
- Explicit known-limitations disclosure (no SCA in CI) — `SECURITY.md:69-76`
- 9 human review gates — `CHARTER.md:237-241`, `docs/standards.md:78-98`
- 30 rules mapped to enforcing checks — `docs/standards.md:16-76`
- Explicit list of intentionally-unautomated properties — `docs/standards.md:100-112`
- Rule-to-check command map — `docs/standards.md:116-127`
- Charter §4 lifecycle (12 stages) with artifact requirements — `scripts/repo_status.py:31-44`
- Decision legend (7 decision types) — `TAXONOMY.md:77-88`
- Capability registry schema (28 fields) — `TAXONOMY.md:41-75`
- 11 ADRs with human-maintained index — `docs/decisions/`
- ADR format standard — `docs/decisions/0000-adr-format.md`
- 6 executable phase plans with exit criteria — `docs/phases/`
- Phase model ADR (Phase 0 added) — `docs/decisions/0005-phase-model-and-plans.md`
- 5 specifications (design-before-code artifacts) — `specifications/`
- 5 research records — `research/`
- Roadmap with per-session narrative notes — `docs/roadmap.md:37-101`
- Documentation index with reading order — `docs/README.md`
- Evidence-class vocabulary (5 classes) — `docs/README.md:34-35`, `CONTRIBUTING.md:49`
- Repository architecture doc (knowledge/code/machinery planes) — `docs/architecture.md`
- Design-philosophy doc with 13-item trade-off priority order — `docs/philosophy.md`
- Agent session protocol (start/end-of-session) — `AGENTS.md:8-45`
- Declarative project-intent file for external auditing — `.usa/foundation.yaml`
- 7 recorded USA audit artifacts with trended scores — `docs/audits/`
- Peer-infrastructure survey with adopt/adapt/defer/reject verdicts — `docs/audits/2026-09-16-usa-infrastructure-survey.md`
- `.env` gitignored — `.gitignore:12`
- Comprehensive cache/artifact gitignore — `.gitignore:1-30`
- Zero runtime dependencies (deliberate, ADR-gated) — `pyproject.toml:11-20`
- Build system declared (hatchling) — `pyproject.toml:33-38`
- Per-capability error taxonomy modules — `catalog/*/*/errors.py`
- Default-deny approval seam in MCP client — `catalog/protocols/mcp_client/approvals.py`
- Default-off content capture policy object — `catalog/observability/execution_trace_recorder/capture.py`
- Least-privilege tool allowlist enforced in both directions — `catalog/agents/react_agent_loop/adapters.py` + `tests/test_dispatcher_allowlist.py`
- Security metadata field per capability — `TAXONOMY.md:118,144,170,246,271`
- Bounded compatibility claims per capability — `TAXONOMY.md:249,274`

---

# (c) Confirmed absent

Flat list of fundamentals with **no implementation**, and the search performed to confirm.

| # | Absent fundamental | How confirmed |
|---|---|---|
| 1 | **Coverage threshold (`fail_under`) — config exists, threshold does not** | `grep -n "fail_under" pyproject.toml` → single hit at line 75, **inside a comment**; the sibling keys at `pyproject.toml:72-76` are `show_missing`/`skip_covered` only. Corroborated: `.usa/foundation.yaml:54` `minCoverage: 0`; survey gap-list item #1 (`…survey.md:113`). CI prints coverage and ignores it (`ci.yml:86`). |
| 2 | **Lockfile with hashes (`uv.lock`/`poetry.lock`/`Pipfile.lock`)** | `ls *.lock` → none; `git ls-files \| grep -i "lock"` → none; `git grep -il "uv.lock"` → only `docs/audits/*` (5 files), all recommending it. |
| 3 | **Dependabot / Renovate config** | `find .github -type f` → exactly `workflows/ci.yml`. `git ls-files \| grep -iE "dependabot\|renovate"` → none. `git grep -il dependabot` → 7 files, **all** under `docs/audits/` + `docs/roadmap.md` (recommendations). |
| 4 | **CODEOWNERS** | `git ls-files \| grep -i codeowners` → none. `ls CODEOWNERS .github/CODEOWNERS docs/CODEOWNERS` → absent. Survey verdict REJECT (`…survey.md:81`). |
| 5 | **PR template** | `.github/` contains one file; no `PULL_REQUEST_TEMPLATE*` anywhere. |
| 6 | **Issue templates** | no `.github/ISSUE_TEMPLATE/`; `find .github -type d` → only `workflows`. |
| 7 | **Branch protection / merge queue as code** | no ruleset/CODEOWNERS/branch config file; `git grep -il "branch protection\|merge queue"` → `docs/audits/2026-09-16-usa-infrastructure-survey.md` only. Also structurally moot: **no git remote** (`git remote -v` empty). |
| 8 | **Commit-message enforcement (commitlint / commit-msg hook / CI check)** | `git grep -il commitlint` → 1 file, the survey (verdict REJECT). Hook directory has only `pre-commit` (`scripts/hooks/`). No `.gitmessage`. Only `CONTRIBUTING.md:50` (scope guidance, no grammar). |
| 9 | **`commit-msg` / `pre-push` / `post-*` git hooks** | `ls scripts/hooks/` → `pre-commit` only; `find . -name "commit-msg" -o -name "pre-push" -not -path './.venv/*'` → none. |
| 10 | **pre-commit framework (`.pre-commit-config.yaml`)** | `ls .pre-commit-config.yaml` → absent. Survey verdict: KEEP hand-written (REJECT framework) (`…survey.md:50`). |
| 11 | **CHANGELOG / release notes** | `ls CHANGELOG.md CHANGES.md HISTORY.md RELEASES.md` → all absent. `git grep -il "towncrier\|release-please\|semantic-release"` → only the survey. |
| 12 | **Release automation / publishing / versioning** | `find .github` → 1 workflow with no `release`/`tags`/`publish` trigger; `git tag` → empty; no `.releaserc`, no `[tool.semantic_release]`. Survey verdict DEFER (`…survey.md:55`). |
| 13 | **Git tags / versioned releases** | `git tag \| wc -l` → `0`. `SECURITY.md:11` states "Tagged releases — none exist yet". |
| 14 | **Dependency vulnerability scanning (SCA)** | `git grep -il "pip-audit\|osv-scanner\|safety"` → `docs/audits/*` (4) + `docs/roadmap.md`. No such step in `ci.yml` (13 steps, none SCA). `SECURITY.md:74-76` discloses the gap. |
| 15 | **Standalone SAST (Bandit / Semgrep / CodeQL)** | `git grep -il bandit` → `pyproject.toml` (only as the ruff `S` comment at line 105), `docs/audits/*`, `docs/roadmap.md`. `git grep -il "codeql\|semgrep"` → survey/audit docs only. No SAST job in `ci.yml`. |
| 16 | **SBOM generation (CycloneDX / SPDX)** | `git grep -il sbom` → `docs/audits/*` only (4 files). `git grep -il "syft\|cyclonedx"` → survey only. No generation step anywhere. |
| 17 | **Automated licence audit / allowlist tooling** | `git grep -il "license-checker\|liccheck\|reuse lint"` → none/none/none. Licence control is 100% manual (`PROVENANCE.md`, registry, `NOTICE`, human gates). |
| 18 | **OpenSSF Scorecard** | `git grep -il scorecard` → `docs/audits/*` (4) + `docs/roadmap.md`, all recommending adoption. No workflow. |
| 19 | **SHA-pinned GitHub Actions** | `ci.yml:28,31` use `@v4`/`@v5` tags, not SHAs. Survey gap-list item #4 (`…survey.md:116`). |
| 20 | **Containerization (Dockerfile / compose / devcontainer)** | `ls Dockerfile docker-compose.yml .dockerignore` → absent; `git ls-files \| grep -iE "docker\|container"` → none. `git grep -il devcontainer` → 3 raw audit files only. |
| 21 | **`.env.example` / env-var exemplar** | `git ls-files \| grep "\.env"` → none; `.usa/foundation.yaml:56-57` → `environment: files: []`. |
| 22 | **`.editorconfig`** | `ls .editorconfig` → absent. Survey verdict ADOPT (`…survey.md:105,121`), unimplemented. |
| 23 | **`CODE_OF_CONDUCT.md`** | not in `git ls-files`; `.usa/foundation.yaml:39` → `codeOfConduct: false`. |
| 24 | **`GOVERNANCE.md`** | not in `git ls-files`; survey §2 lists it as a USA-only artifact (`…survey.md:34`). |
| 25 | **`CITATION.cff`** | absent; survey verdict DEFER until public (`…survey.md:105`). |
| 26 | **Scheduled / cron workflows (drift reminders, link-rot, pin freshness)** | `grep -n "schedule:" .github/workflows/ci.yml` → no hit; the only trigger set is `push`/`pull_request`/`workflow_dispatch` (`ci.yml:12-16`). Only one workflow exists. Survey calls this its #6 priority (`…survey.md:118,130`). |
| 27 | **Workflow YAML linting/security (actionlint, zizmor)** | `git grep -il "actionlint\|zizmor"` → the survey only (verdicts ADOPT, `…survey.md:97-100`). No such CI step. |
| 28 | **External link checking (lychee or equivalent)** | `check_links.py:58-63` explicitly skips `http(s)://`; `git grep -il lychee` → survey only (verdict DEFER). |
| 29 | **Docs site / prose linting (mkdocs, Sphinx, Docusaurus, markdownlint, Vale, Read the Docs)** | `git grep -il "mkdocs\|sphinx\|markdownlint\|vale"` → `vale` appears only as a substring inside unrelated words (verified); no config file for any. No `docs/conf.py`, no `mkdocs.yml`. |
| 30 | **Stale-content / fact-sync detection** | No `usa:fact`-style markers; survey verdict ADAPT-later (`…survey.md:91`). **Demonstrated live:** `docs/architecture.md:40` still says "No catalog entries exist" while 5 exist; `examples/README.md:15` says the same; `tests/README.md:7,19` lists 1 of 5 test files and claims "11 passed". |
| 31 | **`py.typed` marker / downstream typing declaration** | `find catalog -name py.typed` → no results. |
| 32 | **`conftest.py` (shared fixtures)** | `find . -name conftest.py` (excl. `.venv`/`.uv-cache`) → no results. |
| 33 | **Code-coverage service integration (Codecov/Coveralls) or badge** | `git grep -il "codecov\|coveralls"` → audit/survey docs only; no upload step or token in `ci.yml`. |
| 34 | **Mutation testing / property-based testing / load testing / E2E browser tests** | No Hypothesis, mutmut, locust, or Playwright in `requirements-dev.txt` (18 pins, none matching); no such test directories. |
| 35 | **Container/deploy/observability runtime config (K8s, Helm, Procfile, health checks, telemetry)** | Nothing is deployed (`README.md:32`, `.usa/foundation.yaml:24` stage `prototype`); no matching files tracked. |
| 36 | **CI matrix / multi-version testing** | `ci.yml:22-24` — one job, one `runs-on`, no `strategy:` key. CI tests only Python 3.12 while local is 3.14. |
| 37 | **CI concurrency control / job timeouts / artifact upload** | `grep -n "concurrency\|timeout-minutes\|upload-artifact" ci.yml` → no hits. |
| 38 | **Make targets for `status` in the aggregate gate** | `Makefile:109,112` — `check` and `check-strict` **omit** `status`; `make status` is standalone (`Makefile:122`). A session can pass `make check` with governance drift present. Only CI (`ci.yml:83`) and the pre-commit path-aware gate (`pre-commit:111`) catch it. |
| 39 | **`integrations/` in the CI mypy target list** | `ci.yml:66` `find catalog scripts tests study_pipeline` vs `Makefile:72` `find catalog integrations scripts tests study_pipeline`. Integration code is type-checked locally but **not** in CI; `tests/test_gate_coverage.py:224` parses only the Makefile, so nothing catches the divergence. |
| 40 | **Evidence of CI ↔ Makefile equivalence** | `make ci` is documented as "What CI runs" (`Makefile:115`) but CI invokes **no** `make` target — it hand-repeats 13 commands. Divergences #38/#39 prove the two have already drifted. |
| 41 | **`linux`/`macOS`/`windows` cross-platform verification** | CI is `ubuntu-latest` only (`ci.yml:23`); no matrix. |
