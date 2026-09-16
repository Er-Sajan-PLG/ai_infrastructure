# PROFESSOR-J — FUNDAMENTALS Layer Report

Repository: `/home/sajan/Projects/PROFESSOR-J`
Scope: machinery that keeps the repo working + source/test implementation. **Actual files only**; docs used as cross-check.
Method: every tracked file enumerated via `git ls-files` (297 tracked / 183 `.py`), plus untracked working-tree files (`authority/`, `scripts/verify*.py`, `docs/CAPABILITY-CONTRACT.md`). All findings verified by running the commands.
Baseline: HEAD `4bdf1d7`, working tree **dirty** (16 modified, 1 deleted, 5 untracked paths).

---

## 0. Executed-command ground truth (the headline)

These were run, not inferred. They are the backbone of the PRESENT/ABSENT calls below.

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/ -q` | **739 tests, 3 FAILED, 0 errors, 0 skipped**, 64.2s |
| `.venv/bin/mypy app/` | **FAIL — 12 errors in 3 files** (119 files checked) |
| `.venv/bin/ruff check app/ tests/ scripts/` | **FAIL — 26 errors** (E402 ×10, E501 ×7, W292 ×4, F541 ×3) |
| `pytest tests/unit/domain/ --cov=app.domain --cov-fail-under=95` | **PASS — 100.00%** (800 stmts, 0 miss) |
| `python3 scripts/verify_export_contract.py` | **FAIL, exit 1 — `DRIFT — digest mismatch`** |
| `python3 scripts/verify_git_safety.py` | **exit 0**, reports "dirty (preserved, not cleaned)" |
| `.venv/bin/python --version` | **Python 3.14.7** (CI pins 3.11) |

**Consequence:** `scripts/verify.py` runs pytest → mypy → pre-commit and **breaks on the first failure**. As of this snapshot it fails at step 1 (3 failing tests) and would also fail at step 2 (12 mypy errors). CI `lint-and-typecheck` and CI `test` are both **red**.

---

## 1. CI/CD — `.github/`

### 1.1 `.github/workflows/ci.yml` (218 lines)

**Triggers** (`ci.yml:3-7`): `push` to `main`, `pull_request` to `main`.
**Concurrency** (`ci.yml:12-14`): group `ci-${{ github.ref }}`, `cancel-in-progress: true`.
**Permissions** (`ci.yml:17-18`): `contents: read` — explicit least privilege, commented "Least privilege for non-deploy CI."
**Env** (`ci.yml:9-10`): `PYTHON_VERSION: "3.11"`.

Eight jobs:

| Job | Line | Enforces | Tool versions |
|---|---|---|---|
| `lint-and-typecheck` | 21-35 | `.venv/bin/pre-commit run --all-files`; `.venv/bin/mypy app/` | pre-commit 4.0.1, ruff 0.6.9, mypy 1.14.1 (from `action.yml:29`) |
| `test` | 37-61 | `pytest tests/ -v --tb=short --cov=app --cov-report=xml`; then domain gate | pytest/cov from `requirements.txt` |
| `security` | 63-90 | gitleaks action; bandit `-r app/ -c pyproject.toml`; pip-audit | gitleaks-action@v3, bandit+pip-audit installed ad hoc |
| `virtual-board` | 92-106 | `.venv/bin/python scripts/board/review.py`, `needs: [lint-and-typecheck, test]` | — |
| `verify-docs` | 108-144 | asserts 11 required docs exist + `docs/adr/` dir | — |
| `build-frontend` | 146-179 | `pnpm install/typecheck/lint/build` | pnpm **11.18.0**, Node **"22"** |
| `check-branching` | 181-201 | PR-only; branch must match `^(phase\|task\|fix\|docs\|chore\|ci\|exp\|dependabot)/` | — |
| `check-conventional-commits` | 203-218 | PR-only; `wagoid/commitlint-github-action@v6`, `configFile: commitlint.config.cjs` | — |

Zero-cost observations:
- `ci.yml:90` pip-audit is `continue-on-error: true` ("advisory; fail only on the gitleaks/bandit gates").
- `ci.yml:61` codecov `fail_ci_if_error: false` — coverage upload cannot block merges; enforcement is local.
- **CI runs Python 3.11, local venv is 3.14.7.** The `pyproject.toml:8` `disable_error_code = "syntax"` and `[tool.mypy] python_version = "3.11"` show the mismatch is known.
- `virtual-board` runs `review.py` in the `if`-less shell; `review.py` returns 1 on failure so the job fails, but the job only *needs* lint+test, so a red typecheck blocks it anyway.

### 1.2 `.github/workflows/release.yml` (32 lines)
Trigger `push` tags `v*` (`release.yml:5-8`). `permissions: contents: write` (`:10-11`). Derives version from tag (`:23`), creates a **draft** GitHub release via `softprops/action-gh-release@v2` with `generate_release_notes: true` and `fail_on_unmatched_files: true` (`:25-32`). Comment: `draft: true  # review before publish; chained deploy lands in a later phase`.

### 1.3 `.github/workflows/dependabot-auto-merge.yml` (34 lines)
Trigger `pull_request: [opened, synchronize, reopened]` (`:8-10`). `permissions: contents: write, pull-requests: write` (`:12-14`). Gated `if: github.actor == 'dependabot[bot]'` (`:19`). Runs `gh pr review --approve` (best-effort `|| true`, `:29`) then `gh pr merge --auto --squash --delete-branch` (`:32-34`). Merge completes only when required checks pass — so this cannot bypass the red checks above.

### 1.4 `.github/dependabot.yml` (27 lines)
Two ecosystems: **pip** (`directory: /`, daily 04:00, limit 10, labels `dependencies`/`python`, prefix `chore(deps)`, allows **direct and indirect**) and **github-actions** (weekly, limit 5, prefix `chore(ci)`).

### 1.5 `.github/actions/setup-env/action.yml` (29 lines)
Composite action; input `python-version` default `"3.11"`. `actions/setup-python@v5` with `cache: pip` (`:13-17`); creates `.venv`, upgrades pip, `pip install -r requirements.txt` (`:19-24`); then **explicitly** installs `pre-commit==4.0.1 ruff==0.6.9 mypy==1.14.1` and runs `pre-commit install --install-hooks` (`:26-29`) so the local `mypy` hook resolves.

---

## 2. Build / quality configuration

### 2.1 `pyproject.toml` (64 lines) — single source of tool config
- **mypy** (`:1-17`): `python_version = "3.11"`, **`strict = true`**, `files = ["app", "tests"]`, `warn_unused_configs/redundant_casts/unused_ignores = true`, `disable_error_code = "syntax"`. Overrides: `tests.*` → `disallow_untyped_defs = false`, `check_untyped_defs = true` (`:10-13`); `numpy.*` ignore_errors (`:15-17`).
- **pytest** (`:19-22`): `testpaths = ["tests"]`, `addopts = "-q --tb=short"`, `asyncio_mode = "auto"`.
- **ruff** (`:24-41`): `line-length = 100`, `target-version = "py311"`, `src = ["app","tests","scripts"]`, `force-exclude = true`; `select = ["E","F","W","I","UP","B","C4","SIM","PIE"]`; `ignore = ["B008"]`. Verbatim comment `:32-33`: *"Security (S) deliberately NOT blanket-enabled; secrets are handled by gitleaks + bandit separately."* isort: `combine-as-imports`, `known-first-party = ["app"]`.
- **bandit** (`:43-46`): `exclude_dirs = ["tests","scripts",".venv",".github"]`, `targets = ["app"]`, `skips = ["B311"]` ("random is not used for security-critical randomness").
- **coverage** (`:48-64`): `source = ["app"]`, **`branch = true`**, `show_missing = true`, `skip_covered = false`; `exclude_lines` pragma/TYPE_CHECKING/NotImplementedError/main; **`fail_under = 80`** with comment `:62-63`: *"Aggregate floor for the whole app… Per-layer targets (95% domain/brain, 85% adapters) are enforced per-module in CI."*
- **ABSENT: no `[project]`, no `[build-system]`** (grep confirms). The repo is not pip-installable; `import app` works only from the repo root.

### 2.2 `requirements.txt` (67 lines)
**Mixed pinning strategy** — some `==`, some `>=`:
- Exact: `pydantic==2.13.5`, `python-dotenv==1.2.3`, `python-json-logger==4.2.0`, all three OTel packages (`1.29.0`/`1.29.0`/`1.44.0`), `mcp-agent==0.2.6`, `faster-whisper==1.2.1`, `piper-tts==1.7.0`, `pytest==9.1.1`, `pytest-asyncio==1.4.0`, `pytest-cov==7.1.0`, `hypothesis==6.167.0`, `mypy==2.3.1`, `pre-commit==4.6.2`, `ruff==0.16.5`.
- Ranges: `mcp>=2.1.1,<3.0.0`, `langgraph>=1.2.11`, `chromadb>=1.5.9`, `sqlalchemy>=2.0.52`, `alembic>=1.19.1`, `fastapi>=0.141.1`, `uvicorn[standard]>=0.52.4`, etc.
- **Duplicates**: `faster-whisper` at `:36` (`>=1.0.0`) and `:54` (`==1.2.1`); `piper-tts` at `:37` (`>=1.2.0`) and `:55` (`==1.7.0`).
- **Version conflict with CI tooling**: `requirements.txt:65-67` pins `mypy==2.3.1`, `pre-commit==4.6.2`, `ruff==0.16.5`, but `setup-env/action.yml:29` installs `mypy==1.14.1`, `pre-commit==4.0.1`, `ruff==0.6.9`. Local venv has ruff 0.6.9 (the action pin), not 0.16.5.
- Header comment `:2`: *"regenerate pins via `pip freeze` after deliberate upgrades"* — so `>=` entries are intentional drift.

### 2.3 `Makefile` (96 lines)
`.PHONY` (`:3`): `help install test typecheck lint format clean langfuse-up langfuse-down langfuse-logs eval`.

| Target | Line | Runs |
|---|---|---|
| `help` | 6-30 | prints command list (default target) |
| `install` | 34-35 | `.venv/bin/pip install -r requirements.txt` |
| `install-dev` | 37-38 | **identical to `install`** — no dev/test extra |
| `test` | 42-43 | `.venv/bin/python -m pytest tests/ -v --tb=short` |
| `test-cov` | 45-51 | pytest + `--cov=app --cov-report=term-missing/html`; **then** domain gate `--cov-fail-under=95`; echoes "adapters (>=85%) and brain (>=95%) gates activate when those layers are implemented" |
| `typecheck` | 53-54 | `.venv/bin/mypy app/` |
| `lint` | 56-57 | `.venv/bin/pre-commit run --all-files` |
| `format` | 59-61 | `.venv/bin/ruff format app/ tests/` + `ruff check --fix app/ tests/` |
| `langfuse-up/down/logs` | 65-75 | `docker-compose -f docker/observability.yml up -d` / `down` / `logs -f` |
| `eval` | 79-81 | **stub** — echoes "Evaluation harness not yet implemented (Phase 9)" |
| `clean` | 85-90 | removes caches, `.coverage`, `htmlcov`, `dist`, `build`, `*.egg-info` |
| `reset-venv` | 92-95 | rm `.venv`, recreate, pip upgrade, install requirements |

**No `make verify` target.** `scripts/verify.py` is not referenced by the Makefile.

### 2.4 `.pre-commit-config.yaml` (30 lines)
Three repos: `pre-commit-hooks@v5.0.0` (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-merge-conflict`, `check-ast`, `check-toml`, `debug-statements`); `astral-sh/ruff-pre-commit@v0.7.3` (`ruff --fix`, `ruff-format`); local `mypy` hook (`:22-30`) with `entry: .venv/bin/mypy`, `language: system`, `types: [python]`, `pass_filenames: false`, `args: [app, tests]`.
Note the rev skew: pre-commit pins ruff **v0.7.3**, `requirements.txt` pins ruff **0.16.5**, CI action installs **0.6.9**.

### 2.5 `.gitleaks.toml` (11 lines)
Allowlist: `paths = ["tests/**/*"]` and `regexes = ['''REDACTED''']`. **This exempts the entire `tests/` tree from secret scanning** — a real blind spot if a live key is ever pasted into a test.

### 2.6 `commitlint.config.cjs` (21 lines)
Declared "Pure rule config (no external parser preset)". Rules: `header-max-length` 100; `type-enum` = `[feat, fix, docs, refactor, test, chore, build, ci, perf, style, revert, merge]`; `type-case` lower-case; no empty type/subject; no trailing full-stop; body/footer leading blank (warn level 1).

### 2.7 `.editorconfig`
**ABSENT** (`ls: cannot access '.editorconfig'`). Formatting is governed by ruff (`line-length = 100`) and the pre-commit whitespace hooks only.

### 2.8 `VERSION`
Contains `1.0.0`. **Contradicted by code** — see §12.

---

## 3. `scripts/` — every file (5 total)

All three verify scripts are **untracked working-tree files** (`git status` shows `?? scripts/verify.py`, `?? scripts/verify_export_contract.py`, `?? scripts/verify_git_safety.py`). None is referenced by `.github/workflows/*`, `Makefile`, `.pre-commit-config.yaml`, or `commitlint.config.cjs` — grep across those files returns **zero matches**.

### 3.1 `scripts/verify.py` (37 lines) — the "canonical verification command"
**Purpose:** repo-wide verification runner.
**CLI:** `python3 scripts/verify.py` — no arguments, no flags.
**Mechanism:** `REPO_ROOT = Path(__file__).resolve().parent.parent` (`:14`). Iterates a fixed 3-command list (`:20-24`):
```python
[".venv/bin/python", "-m", "pytest", "tests/", "-q"],
[".venv/bin/mypy", "app/"],
[".venv/bin/pre-commit", "run", "--all-files"]
```
Runs each via `subprocess.run(cmd, cwd=REPO_ROOT)` (`:26`) — **repo root is forced**, so it works from any cwd.
**Failure semantics (`:27-32`):** on the first non-zero return code it prints `✗ PROFESSOR-J verification FAIL (exit {code})` to **stderr**, sets `code = result.returncode`, and **`break`s** — fail-fast, remaining steps are skipped. If the loop completes without break, the `else` clause prints `✓ PROFESSOR-J verification PASS`.
**Exit codes:** `0` on all-pass; otherwise the **first failing command's** exit code (not 1). `main()` is wrapped `sys.exit(main())` (`:36-37`).
**Output:** one `→ Verifying PROFESSOR-J: <cmd>` line per step (`:25`), the subprocess's own inherited stdout/stderr, then a single PASS/FAIL line.
**Current behavior:** fails. Step 1 (`pytest tests/ -q`) returns non-zero because 3 tests fail.

### 3.2 `scripts/verify_git_safety.py` (66 lines)
**Purpose:** forbid destructive git operations; preserve dirty work.
**CLI:** `python3 scripts/verify_git_safety.py [--check "<cmd>"]` (`argparse`, `:50-52`).
**`FORBIDDEN` list (`:20-27`):** `git reset --hard`, `git clean -fd`, `git clean -fdx`, `git push --force`, `git push -f`, `git reset --hard HEAD`. Matching is a plain **substring** `in` test (`:31-34`).
**Modes:** with `--check`, `check_command()` returns 0/1 (`:54-56`). Without, `check_status()` (`:38-46`) runs `git status --porcelain`, prints `Git status: dirty (preserved, not cleaned)` + first 500 chars, and **always returns 0** — a dirty tree is a warning, never a failure. It then prints a blanket "no destructive operations detected" (`:61`) which, per the `:58-60` comments ("For now just check status", "Not needed"), is **not actually derived from any scan of history or the command stream**.
**Wired into:** nothing.

### 3.3 `scripts/verify_export_contract.py` (107 lines)
**Purpose:** consumer-side verification of the STEMMA knowledge-export digest — the "mechanical half of the consumers must verify contract".
**CLI:** `verify_export_contract.py` (verify, CI-safe read-only) | `--record` (recompute + write digest) (`:37-39`).
**Paths (`:23-25`):** `STEMMA_EXPORT = REPO_ROOT.parent / "STEMMA" / "exports" / "knowledge.json"`; `MANIFEST = REPO_ROOT / "authority" / "exports-manifest.yaml"`.
**Mechanism:** streaming SHA-256 in 64 KiB chunks (`sha256_of`, `:28-33`). Verify mode (`:80-100`) loads the manifest, reads `exports.knowledge-json.expected.sha256`, compares; mismatch prints `DRIFT — digest mismatch (content regenerated without record)`.
**Exit codes:** `2` export file missing (`:43`); `1` manifest missing (`:83`), key unpinned (`:90`), digest absent (`:96`), or **DRIFT** (`:100`); `0` OK.
**`--record` mode (`:47-77`)** rewrites the manifest in place and *creates* a minimal one if absent.
**Actual result:** **exit 1, DRIFT.** Pinned `authority/exports-manifest.yaml:5` = `1ffe9aec…cbba3`; actual `sha256sum ../STEMMA/exports/knowledge.json` = `7c872be1…570a77`. The manifest also declares `contract: {export_version: '0.1', schema_version: '0.2'}` (`authority/exports-manifest.yaml:7-8`).
**Wired into:** nothing (not in CI, not in Makefile, not pre-commit).

### 3.4 `scripts/board/review.py` (510 lines) — "Virtual Board Review"
**Purpose:** deterministic governance checks gating every PR. **This one IS wired into CI** (`.github/workflows/ci.yml:105`).
**CLI:** `python scripts/board/review.py` — no args.
**Structure:** `@dataclass CheckResult(name, passed, message, details)` (`:21-26`); `class VirtualBoard` (`:29`) with `run_all()` driving 8 checks (`:38-47`), printing `✓ PASS`/`✗ FAIL` per check.
**The 8 checks:**
1. `check_import_layering` (`:62-104`) — `app/domain/` may import only from `app.domain.*`; `app/brain/` may not import `app.adapters` nor the literal strings `fastapi`/`starlette`/`uvicorn` (`:83`).
2. `check_domain_purity` (`:106-205`) — AST-based: every public class in `app/domain/` must be `@dataclass(frozen=True)` (Enums and `_`-prefixed exempt, `:147-149`); non-dataclass classes may define no public methods (`:151-162`); imports restricted to a stdlib allow-list plus `app.domain` (`:169-197`).
3. `check_schema_drift` (`:207-241`) — reads `app/knowledge/lhs_adapter.py` as **text** and asserts the strings `EXPECTED_EXPORT_VERSION`+"0.1", `EXPECTED_SCHEMA_VERSION`+"0.1", and "zero-drift"/"zerodrift" appear.
4. `check_prerequisite_graph` (`:243-273`) — text grep of `app/domain/concept.py` for 5 method names.
5. `check_safety_gate_coverage` (`:275-333`) — scans `app/tools/*.py` + `app/skills/*.py` (excluding `__init__/base/registry/builtin/executor`) for `@safety_gate` **or** the substring `safety_tier`; plus positively requires `app/tools/executor.py` to contain both `SafetyPolicy` and `policy.check` (`:317-323`).
6. `check_mcp_tool_search` (`:335-371`) — concatenates all `app/mcp/*.py` and greps for `MCPServerManager`, `MCPToolSearch`/`tool_search`, `cache_tools_list`, `CodeExecutionTools`/`code_as_tools`.
7. `check_otel_spans` (`:373-413`) — reads `app/telemetry/exporter.py` as text and requires `OTLPSpanExporter`, a Langfuse auth header, `gen_ai.operation.name`, `tool.name`, `retrieval.query`/`retrieval.vector_store`, `guardrail.tool`/`guardrail.tier`, `evaluator.name`/`evaluator.score`.
8. `check_langgraph_checkpoint` (`:415-466`) — concatenates `app/brain/*.py`; `StateGraph`+`TypedDict` are **blocking**, `checkpointer`/`interrupt` are recorded as `pending` and pass with a note (`:442-461`).

**Important weakness:** checks 3, 4, 6, 7, 8 are **substring/textual greps over source text**, not behavioural verification. They will pass as long as the literal strings exist, even if the code path is dead or unwired. Check 7 (`otel_spans`) is exactly this: it passes on `exporter.py` containing `OTLPSpanExporter`, while **no span is ever created anywhere in the app** (§10).

**Output / side effect (`:482-504`):** writes a Markdown ledger to `REPO_ROOT / "board" / "ledger.md"` (creating parents), containing a UTC timestamp, pass/fail counts, per-check status and `json.dumps(details, indent=2)`.
**Exit code:** `0` if all checks pass, else `1` (`:506`). Prints `Summary: N/M checks passed`.

### 3.5 `scripts/board/ledger.md` (28 lines) — **stale artifact**
Committed snapshot generated `2026-08-22T17:12:31.684679Z`, "Total Checks: 8, Passed: 5, Failed: 3, Status: ❌ FAIL". Two tells that this predates the current tree:
- `:22` records the schema-drift path as `/home/sajan/Projects/PROFESSOR-J/scripts/app/knowledge/lhs_adapter.py` — i.e. an older `review.py` computed `REPO_ROOT` as `parents[1]` instead of `parents[2]` (`review.py:18` is now `parents[2]`). The stale ledger embeds the **bug**, not the code.
- Entries "LHS adapter not found", "Concept entity not found", "No tools/skills yet", "MCP client not yet implemented", "Telemetry exporter not found", "Cognitive brain not yet implemented" are all pre-Phase-1 states; those files now exist.

The **live** ledger path is `board/ledger.md` (not `scripts/board/ledger.md`), and `board/ledger.md` is **gitignored** (`.gitignore:48`, comment "Virtual Board generated ledger (derived, regenerable)"). `ls board/` confirms a newer `board/ledger.md` (Aug 31) exists on disk next to `board/personas/README.md`.

---

## 4. `docker/` — observability stack vs. actual instrumentation

### 4.1 `docker/observability.yml` (98 lines), `version: "3.8"`
Four services on a bridge network `professor-observability` (`:92-94`), two named volumes (`:96-98`):
- **postgres** (`:5-21`): `postgres:16-alpine`; DB/user `langfuse`; password `${LANGFUSE_POSTGRES_PASSWORD:-langfuse}`; `pg_isready` healthcheck (10s/5s/5), `restart: unless-stopped`.
- **clickhouse** (`:24-44`): `clickhouse/clickhouse-server:24.8-alpine`; `SELECT 1` healthcheck; `ulimits.nofile` 262144.
- **langfuse** (`:47-73`): `langfuse/langfuse:3`; `DATABASE_URL` → postgres; `CLICKHOUSE_URL: http://clickhouse:8123`; `NEXTAUTH_SECRET`/`LANGFUSE_SALT` default to **`$(openssl rand -base64 32)`** (`:58-59`); `TELEMETRY_ENABLED: "false"`; port `3000:3000`; `depends_on` both healthy.
- **otel-collector** (`:76-90`): `otel/opentelemetry-collector-contrib:0.112`; mounts the config read-only; ports **4317** (OTLP gRPC), **4318** (OTLP HTTP), **8888** (Prometheus); **`profiles: [production]`** — so it does **not** start under a bare `docker-compose up`.

### 4.2 `docker/otel-collector-config.yaml` (31 lines)
- **receivers:** `otlp` grpc `0.0.0.0:4317`, http `0.0.0.0:4318` (`:1-7`).
- **processors:** `batch` (timeout 10s, send_batch_size 1000), `memory_limiter` (check_interval 1s, limit_mib 400, spike_limit_mib 100) (`:9-16`).
- **exporters:** `langfuse` → `http://langfuse:3000/api/public/otel/v1/traces` with `Authorization: "Basic ${LANGFUSE_AUTH_HEADER}"`; `logging` loglevel debug (`:18-24`).
- **service:** single traces pipeline `receivers [otlp] → processors [memory_limiter, batch] → exporters [langfuse, logging]` (`:26-31`). No metrics or logs pipeline despite port 8888 being exposed.

### 4.3 Does the app instrument against it? — **NO (config is aspirational)**
- The only OTel code is `app/telemetry/exporter.py` (231 lines): `init_tracer_provider()` (`:22`), `get_tracer()` (`:86`), `shutdown_tracer_provider()` (`:93`), plus attribute helpers `set_gen_ai_attributes` (`:112`), `set_tool_attributes` (`:136`), `set_retrieval_attributes` (`:157`), `set_guardrail_attributes` (`:174`), `set_evaluator_attributes` (`:194`), and `_sanitize_args` (`:209`).
- `init_tracer_provider()` is **never called** anywhere in the repo (grep across all `*.py`/`*.md` excluding `.venv`/`.git` returns only its own definition).
- `get_tracer()` is **never called** by any module. No `start_as_current_span`/`start_span` exists outside the exporter — the only `span` hits in `app/` are arithmetic in `app/gamedev/primitives.py:89-90`.
- Therefore **no span is ever emitted**, the collector receives nothing, and there is **no metrics implementation at all** (no meter/counter/histogram outside incidental identifiers).
- `app/config/settings.py:112` `otel_endpoint = "http://localhost:4318/v1/traces"` exists but is only read by the never-called `init_tracer_provider` (`exporter.py:32`).
- The `otel_spans` board check (`.github` → `review.py:373-413`) nevertheless **passes**, because it greps the exporter's source text.

---

## 5. Source tree — structure, layering, abstractions

### 5.1 Top-level layout (tracked, 297 files; 183 `.py`)
`app/` (23,703 LOC across 119 modules), `app/gamedev/` (5,957 LOC, 22 modules), `tests/` (59 test files), `frontend/` (Next.js), `docs/` (55 md), `docker/` (2), `scripts/` (5), `agents_dev/` (5 md), `board/personas/README.md`, `.templates/manifest.json`, `authority/` (4, untracked), `data/` (runtime), `prompts/` (**empty**).

### 5.2 `app/` — per-package purpose (approx LOC, entry points)

| Package | LOC | Purpose / entry point |
|---|---|---|
| `app/skills/` | 2,823 | Skill abstraction; `builtin.py` **2,405 LOC / 16 skill classes** (`FilesystemSkill:145`, `GitSkill:244`, `WebSearchSkill:347`, `CodeExecutionSkill:405`, `LHSTEMSkill:463`, `MemorySkill:584`, `ProjectBuildSkill:674`, `GitExtendedSkill:790`, `FileTemplateSkill:883`, `MCPSkill:1167`, `GroundedCitationsSkill:1365`, `ArxivSkill:1494`, `WorkspaceSynthesisSkill:1660`, `GitHubAuthSkill:1864`, `GitHubCodeReviewSkill:1983`, `GitHubPRWorkflowSkill:2170`). |
| `app/gamedev/` | 5,957 | Largest subsystem. `agent.py:321` (`GameDevAgent`), `reasoner.py:571`, `adapters/pure_core.py:482`, `adapters/unity.py:399`, `certification.py:402`, `repair.py:371`, `components.py:361`, `primitives.py:441`, `synthesizer.py:270`, `schema.py:259`, `core.py:241`, `workflows.py:223`, `replay.py:172`, `validator.py:172`, `fuzzer.py:136`, `presentation.py:289`, `knowledge.py:374`, `patterns.py:117`, `analyzer.py:127`, `base.py:127`. Public surface re-exported in `__init__.py:96`. |
| `app/adapters/` | 953 | `api.py` — the FastAPI surface. `__init__.py` re-exports `create_app`. |
| `app/models/` | ~1,300 | `providers.py` (`LLMProvider` ABC, `MockProvider`), `real_providers.py:484`, `cloud_providers.py:237`, `catalog.py`, **`router.py:199` (`ModelRouter`)**, `retry.py` (`bounded_retry`). |
| `app/authority/` | ~900 | Trust root: `principal.py:106`, `gateway.py:445`, `ledger.py:140`, `policy.py:45`. |
| `app/tools/` | ~1,000 | `executor.py:353` (`ToolExecutor`), `sandbox.py:316` (`CodeSandbox`, `MathSolver`), `charts.py:171`. |
| `app/memory/` | ~1,400 | `store.py:240`, `manager.py:206`, `hybrid.py:189`, `ranking.py`, `reflexion.py`, `fact_extractor.py`, `schema.py`, `service.py:164`, `backends.py:305` (`InMemoryBackend:104`, `JsonMemoryBackend:142`, `ChromaMemoryBackend:206`). |
| `app/db/` | ~500 | `engine.py:140` (`DatabaseEngine` ABC + `SqliteDatabaseEngine`), `repositories.py:442` (`MasteryRepository:38`, `TranscriptRepository:77`, `SessionRepository:116`). |
| `app/brain/` | ~1,300 | LangGraph cognitive core: `graph.py:216`, `state.py:20` (`BrainState` TypedDict), `professor.py:294`, `tutorial.py:314`, `evaluator.py:195`, `intents.py`. |
| `app/knowledge/` | ~800 | `lhs_adapter.py:336` (STEMMA consumer), `ingest.py`, `pdf.py`, `research.py`. |
| `app/mcp/` | ~1,300 | `client.py:594`, `manager.py:178`, `registry.py:226`, `transports.py:228`, `search.py`. |
| `app/guardrails/` | ~400 | `policy.py:181` (`SafetyPolicy`, `safety_gate`), `injection.py:114`, `pii.py:68`. |
| `app/events/` | ~150 | `bus.py` `InMemoryAsyncBus` — explicitly passive telemetry only. |
| `app/context/` | ~250 | `manager.py:175` (pair-preserving trim), `tokenizer.py`. |
| `app/voice/` | ~700 | `routes.py:177` (`/api/voice`), `stt/` (`whisper_local.py:197`), `tts/` (`piper_local.py:255`), factories. |
| `app/domain/` | ~800 | Pure frozen-dataclass core: `concept.py:143`, `learner.py:314`, `gamedev.py:526`, `plan.py:173`, `session.py:245`, `tool.py` (`SafetyTier`), `time.py`. |
| `app/config/` | 229 | `settings.py` — pydantic-settings. |
| `app/session/` | 312 | `session_manager.py`. |
| `app/workspace/` | 120 | `workspace.py` — rooted, bounded file IO. |
| `app/telemetry/` | 231 | `exporter.py` — **unwired** (see §4.3). |
| `app/resources/` | ~130 | `budget.py` (`TokenBudget`), `circuit_breaker.py` (`CircuitBreaker`). |
| **Root modules** | — | `bootstrap.py:226` (**composition root**), `exceptions.py:426` (**error taxonomy**), `logging_config.py:122` (**unwired**), `__init__.py:7` (`__version__ = "0.0.1"`). |

### 5.3 Architectural layering
Documented direction (`board/personas/README.md`): `Presentation → Adapters → Bootstrap → Brain → Domain`, and `review.py:63` states `domain ← brain ← bootstrap ← adapters ← presentation`.

Enforcement is **two-tier**:
- **Code-level:** `app/bootstrap.py` is the composition root; `build_root()` (`:84-223`) constructs every singleton and returns the `AppRoot` dataclass (`:39-81`) with a `health()` method (`:62-81`) reporting per-subsystem liveness and a composite `ready` flag.
- **Gate-level:** `scripts/board/review.py` `check_import_layering` (`:62-104`) + `check_domain_purity` (`:106-205`) run in CI (`ci.yml:105`). Domain purity is AST-verified (frozen dataclasses only, stdlib-only imports), which is stronger than a grep.

**Layer leak found:** `app/domain/gamedev.py` imports nothing external (passes purity), but `app/tools/executor.py:21` imports `EngineTarget` from `app.domain.gamedev` — fine direction — while `app/adapters/api.py` reaches through `app.bootstrap` and `app.brain` and dynamically re-imports `app.models.router` inline (`api.py:~408`) rather than via the composition root.

### 5.4 Agent / tool abstractions
- **Tool:** `RegisteredTool` frozen dataclass (`executor.py:44-51`: `name`, `tier`, `description`, `fn`). Registration is gate-checked: `register()` → `_check_register()` (`:89-104`) consults an optional `register_policy`, raising `CapabilityRegistrationError` on denial and writing a ledger event either way.
- **Safety tiering:** `SafetyTier` enum in `app/domain/tool.py` with `SAFE < SENSITIVE < DESTRUCTIVE`.
- **Skill:** `Skill(ABC, Generic[T])` (`skills/base.py:99`) with `SkillMetadata` (`:36-65`, incl. `parameters_schema`/`returns_schema`/`timeout_seconds`/`mcp_servers`), `SkillStatus` enum (`:26`), `SkillResult` (`:68-96`). `SkillRegistry` (`skills/registry.py:18`) accepts a `register_policy` seam (`:25`), denies policy failures (`:43-47`), and **refuses silent overwrite** (`:48-52`).
- **Agent:** `GameDevAgent` (`gamedev/agent.py`), `ProfessorAgent` (`brain/professor.py`), `EvaluatorAgent` (`brain/evaluator.py`), `ResearchAgent` (`knowledge/research.py`). All are constructed in `build_root()`.
- **Brain graph:** LangGraph `StateGraph(BrainState)` (`graph.py:163`) with nodes `classify → plan → synthesize` (`:165-172`). Deterministic classifier/planner; only synthesis hits the router. Falls back to `MockProvider` when no router is supplied (`:160-162`).

### 5.5 How authority/permissions are enforced **in code**

Four independent mechanisms:

1. **Principal — forgery-proof identity.** `Principal` is `@dataclass(frozen=True, slots=True)` (`principal.py:31-45`) with a private `_trusted: bool = False` marker; `__post_init__` (`:64-69`) raises `RuntimeError("Principal.forge_attempt: …")` if `_trusted` is false. The only constructor is `Principal.create()` (`:47-62`). Propagation is via `contextvars.ContextVar` (`:26-28`) with `set/reset/get/require_current_principal`. **The composition root is the only creator** — `bootstrap.py:142-189` creates 8 Principals (researcher/architect/implementer/security-reviewer at `SENSITIVE`; tester/code-reviewer/docs-reviewer/ci-reviewer at `SAFE`), commented `:139-141`: *"These are the ONLY places Principals are created (trust root)."*
2. **AuthorityGateway — single execution boundary.** `execute()` (`gateway.py:300-415`) is the mandated path for all privileged calls. Order: `require_principal()` (`:318`) → resolve capability tier (`:321-328`) → `_check_allocation()` (`:337`) → `_check_tier()` (`:338`) → `SafetyPolicy.check()` (`:342-347`) → record positive `AuthorizationDecision` (`:368-381`) → `_enforce_provenance_rules()` (`:384`) → execute under principal context (`:391-408`). `_check_allocation` (`:178-208`) enforces three things separately: project exists in `allocation.yaml`, **principal id ∈ allocation.agents** (`:185-190`), and **tier ≤ allocation.max_tier** (`:193-200`). `_check_tier` (`:210-221`) **denies by default** on an unknown capability (`:213-215`) and compares principal tier to capability tier. `_enforce_provenance_rules` (`:223-268`) blocks AI-sourced or untrusted-sourced (`mcp`/`retrieved`/`tool`/`external`) requests for mutation capabilities unless `human` precedes them in the chain.
3. **Registration policy — no privilege self-grant.** `default_register_policy` (`authority/policy.py:31-42`): a non-blessed registrar may only introduce `SAFE`/`SENSITIVE`; `DESTRUCTIVE` requires `blessed=True`, which only the composition root passes (`bootstrap.py:118-122`, `blessed_registrar=True`).
4. **Safety gate — call-time tiering.** `SafetyPolicy.check()` (`guardrails/policy.py:56-80`) runs injection detection on **every tier including SAFE** (`:64`), PII-redacts args (`:66`), auto-approves SAFE, auto-approves SENSITIVE if `auto_approve_sensitive` else requires callback, and for DESTRUCTIVE **always** requires a callback — absent callback raises `HITLRequiredError` (`:50-51`), i.e. **fails closed**. `safety_gate()` (`:92-136`) wraps sync and async callables and binds positional args to names for the check (`_bind_args`, `:162-170`).

Two secondary enforcement surfaces:
- **MCP fail-closed:** `MCPServerManager.call_tool()` (`mcp/manager.py:116-134`) raises `SafetyGateError` if **no policy is wired** (`:125-133`); MCP tools default to tier `SENSITIVE` (`:40`).
- **Workspace path escape:** `WorkspaceManager._resolve()` (`workspace/workspace.py:46-51`) resolves then asserts `target.is_relative_to(self.root)`, raising `WorkspaceSecurityError`; reads/writes bounded by `max_bytes` (`:65`, `:96`); delete refuses the root (`:108`).
- **Sandbox:** `CodeSandbox.run_python()` (`tools/sandbox.py:90-135`) uses `python3 -I` (isolated), `stdin=DEVNULL`, a scrubbed `env` (`{"PATH": …, "LANG": …}`, `:104`), `tmpdir` cwd, `timeout`, and `preexec_fn` applying `RLIMIT_AS` = `memory_limit_mb` (`:66-81`). `run_command` additionally allow-lists executables `{python, python3, pytest, dotnet}` (`:233`), requires `python -m {pytest|compileall|unittest}` (`:244-249`), permits only `dotnet {test|build}` (`:252-255`), and rejects flags `-c/--override-ini/-o/--import-mode` (`:258-260`).

### 5.6 `agents_dev/`, `board/`, `prompts/`, `.templates/`, `frontend/`, `data/`
- **`agents_dev/`** (5 md, **no code**): `skills/{README.md, stem-tuition-content-developer.md, stem-tuition-content-engine.md}`, `stem-tuition/{current-state.md, workflow.md}`. Documentation only — not loaded by any Python.
- **`board/personas/README.md`** (5,034 B): six persona definitions (Platform Architect, Cognitive Engineer, …) with Role/Responsibilities/Review Criteria. Prose; `review.py` implements the checks it describes but does not parse this file.
- **`prompts/`** — **EMPTY directory** (only `.`/`..`). `app/prompt/loader.py` (`PromptLoader`) and `settings.prompts_dir = Path("prompts")` (`settings.py:38`) point at it, so the loader has nothing to load.
- **`.templates/manifest.json`**: `format: 1`, `libraryVersion 0.1.0`, generated 2026-08-20, types `[education, software]`, 20 modules and their file versions (`100-identity.md` … `software-testing.md`).
- **`frontend/`**: Next.js 15.3.1 + React 19 + TypeScript 5 + Tailwind 4. `package.json:5` `packageManager: pnpm@11.18.0`; scripts `dev/build/start/lint/typecheck` (`:6-12`); deps incl. `katex`, `plotly.js:^4`, `react-plotly.js`. `tsconfig.json` has **`"strict": true`** and `noEmit`. `eslint.config.mjs`, `postcss.config.mjs`, `next.config.ts`, `pnpm-lock.yaml`, `pnpm-workspace.yaml` present. Components: `ChatCanvas`, `FileUpload`, `MessageContent`, `ModelSelectorDropdown`, `PersonaSelectorDropdown`, `PlotlyChart`, `ProviderSelector`, `SessionSidebar`, `SettingsModal`, `TopBar`, `VoiceComponents`; hooks `useGlobalSettings`, `usePersonas`. **No frontend test file exists** (no jest/vitest/playwright config anywhere).
- **`data/`**: `data/uploads/` (**≥30 runtime PDFs on disk**), `data/skills/`, `data/workspace/`. Gitignored selectively — `.gitignore:35-39` covers `data/runtime/`, `data/uploads/`, `data/test_*.txt`, `*.sqlite3`, `*.db`. `data/ledger/` **does not exist yet and is NOT gitignored** (see §9).

---

## 6. Tests — `tests/`

- **Framework:** pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`, `pyproject.toml:22`) + pytest-cov 7.1.0 + hypothesis 6.167.0. Config lives only in `pyproject.toml:19-22`; **no `pytest.ini`, `tox.ini`, `setup.cfg`, or `setup.py`**.
- **Count:** **739 test functions collected** (grep of `def test_`/`async def test_` yields 752 including nested helpers; the authoritative collected count is 739). Result: **736 pass / 3 fail / 0 skipped / 0 errors, 64.2s.**
- **Structure:** `tests/__init__.py`, `tests/test_smoke.py`, `tests/fixtures/lhs_knowledge_fixture.json`, and `tests/unit/<layer>/test_*.py` under 17 layer dirs: `adapters, authority, brain, config, db, domain, gamedev, guardrails, knowledge, mcp, memory, models, resources, session, skills, tools, voice, workspace`. **No `tests/integration/` and no `tests/evals/`** despite both being referenced in docs (see §12).
- **`conftest.py`: ABSENT — there is none anywhere in `tests/`.** Shared setup is instead done with 40 module/class-level `@pytest.fixture` definitions and 205 `tmp_path` usages (good isolation), plus per-module `teardown_module` (e.g. `test_safety_gate.py:154-155` calls `reset_default_policy()`).
- **Fixtures / real vs mocked:** 170 `mock`/`patch`/`monkeypatch`/`MagicMock`/`AsyncMock` references across 10 files — mocking is **localised**, not global. Most tests exercise **real** implementations: real `SqliteDatabaseEngine` against `tmp_path`, real `SafetyPolicy`, real `Principal`/`AuthorityGateway`, real `CodeSandbox` (subprocess), real `sympy`, real `json`/`yaml` parsing. Only network/provider/transport edges are mocked (`test_real_providers.py`, `test_mcp/{client,search,transports}.py`, `test_voice.py`, `test_resources.py`, `test_session_manager_extended.py`, `test_skills/*`, `test_settings.py`).
- **Failure paths:** well covered. `test_safety_gate.py` has an explicit **18-row decision matrix** (`:29-48`) of `(tier, auto_approve_sensitive, approved) → allow|hitl_blocked` with a hypothesis property test over the same space (`:51-67`, `max_examples=40`); plus `pytest.raises` for `PromptInjectionError` (`:78`), `HITLRequiredError` (`:88`, `:116`, `:138`). `test_phase6_security.py` is explicitly adversarially framed (`:1-5`: *"These tests ATTACK the security properties rather than testing happy paths"*) and pins the forge-prevention `RuntimeError` (`:59-66`).
- **Contract tests:** `tests/unit/knowledge/test_lhs_adapter.py::TestLHSSchemaContract` contains 3 real-export contract tests — `test_real_export_structure`, `test_real_export_ids_unique`, `test_real_export_prerequisites_resolve` — reading the live `../STEMMA/exports/knowledge.json`. **All 3 currently FAIL**, all from the same root cause: `LHSAdapterError: LHS export missing required fields: {'generated_at'}` raised at `app/knowledge/lhs_adapter.py:90`. The live export is now `export_version 2.1.0` / `schema_version 1.1.0` with top-level keys `{connection_count, connections, content_hash, entities, entity_count, export_version, kernel_version, relation_registry, relation_registry_version, schema_version, source, source_count, sources, vocabularies}` — **no `generated_at`** — while the adapter demands `EXPECTED_EXPORT_VERSION = "0.1"` / `EXPECTED_SCHEMA_VERSION = "0.2"` (`lhs_adapter.py:43-44`). This is a **live cross-repo contract break**, not a flaky test.
- **Property-based testing:** hypothesis is a hard dependency and used in exactly **one** place — `tests/unit/guardrails/test_safety_gate.py` (`@settings(deadline=None, max_examples=40)` + `@given`). `.hypothesis/` **is present** (cache dir with `.gitignore` + `constants/` entries, latest run) but contains **only generated cache/DB artifacts — no committed `settings` profile and no `conftest`-registered hypothesis profile**. There is no configured `max_examples`/`deadline` default beyond the single inline decorator.

---

## 7. MCP configuration

Three competing declarations plus a secrets template:

| File | Tracked? | Format/consumer | Servers declared |
|---|---|---|---|
| `mcp_servers.json` (36 lines) | **NO — gitignored** (`.gitignore:57` `/mcp_servers.json`) | JSON `servers[]`; fields `server_id, name, transport, command, args, env, timeout_seconds, auto_reconnect` | `github`, `brave-search`, `arxiv` |
| `mcp_servers.yaml` (20 lines) | **yes** (currently modified) | YAML `servers[]`; header `:2` *"This format is used by app.mcp.manager (management/config layer)"*; fields `name, transport_type, command, env, enabled` | `github`, `brave-search`, `arxiv` |
| `mcp_agent.config.yaml` (82 lines) | yes | `mcp-agent` upstream format (`mcp.servers.<name>`) | `filesystem, git, fetch, python, github, sqlite, postgres, brave-search, slack`, plus `agent: {default_model: "openai:gpt-4o", max_iterations: 10, auto_approve: false}` |
| `mcp_agent.secrets.yaml.example` (21 lines) | yes | example only; header `:1-2` *"Copy to mcp_agent.secrets.yaml and fill in values / NEVER commit this file! It's in .gitignore"* | github/postgres/brave-search/slack env placeholders |

- **How secrets stay out of git:** the specs use `${ENV_VAR}` indirection (`mcp_servers.json:20` `${BRAVE_API_KEY}`; `mcp_agent.config.yaml:42,55,65,74-75`). No literal secret is committed in any MCP file. `.env` is gitignored (`.gitignore:2-3`) and confirmed **absent from git history** (`git log --all -- .env` → no output).
- **But two gaps:** (1) `mcp_agent.secrets.yaml.example:2` claims it is gitignored, yet **`.gitignore` has no rule for `mcp_agent.secrets.yaml`** — `git check-ignore` reports it untracked-but-not-ignored, so a filled-in copy would be committable. (2) `mcp_servers.json` is gitignored per `.gitignore:57` under the "Local scratch / devel artifacts" block, yet a real one exists on disk with a live `${BRAVE_API_KEY}` reference — config drift between the three formats is unchecked (no test asserts they agree).
- **Wiring:** `settings.mcp_config_path: Path = Path("mcp_agent.config.yaml")` (`settings.py:115`); `MCPServerManager` is constructed in `build_root()` (`bootstrap.py:202`) with **no servers registered** — `bootstrap.py:199-201` comments *"Dormant by default (no servers registered)"*.

---

## 8. Configuration and secrets

- **Loader:** `app/config/settings.py` — `Settings(BaseSettings)` with `SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore", env_prefix="PROFESSOR_")` (`:14-20`). Exposed through the `@lru_cache(maxsize=1) def get_settings()` singleton (`:174-191`).
- **Validation:** pydantic v2 with typed fields and constraints — `environment: Literal["development","staging","production"]` (`:25`), `api_host/api_port/api_workers` (`:31-33`). Paths normalised by `_resolve_paths` (`:127-130`). Provider keys use `AliasChoices` so both `OPENAI_API_KEY` and `PROFESSOR_OPENAI_API_KEY` work (`:54-101`).
- **Unusual, deliberate precedence inversion:** `_repo_env()` (`:160-171`) reads the repo `.env` directly via `dotenv_values`, and `get_settings()` (`:184-191`) **forces those values on top** of normal resolution so an ambient shell export cannot shadow the repo's own key. Rationale in docstring `:162-166`: the global `SINGULARITY_API_KEY` in `~/.bashrc` "must not shadow the repo's own." `_PROVIDER_ENV_KEYS` (`:146-157`) is the 10-entry mapping.
- **`_validate_api_key`** (`:132-140`): rejects empty/`"changeme"` **only outside development** — `raise ValueError("PROFESSOR_API_KEY must be set to a secure random value")`.
- **`validate_required_secrets(settings)`** (`:197-229`): in production requires `OPENAI_API_KEY` **and** `ANTHROPIC_API_KEY`; always requires ≥1 of six provider keys; raises `RuntimeError("Missing required configuration: …")`. **This function is never called** anywhere (grep confirms) — startup secret validation is dead code.
- **`.env`** exists on disk (557 B, mode `-rw-r--r--`, dated Aug 30) containing **8 live-looking credentials**: `SINGULARITY_API_KEY=sk-sapi-live-…`, `OPENROUTER_API_KEY=sk-or-v1-…`, `NVIDIA_NIM_API_KEY=nvapi-…`, `GOOGLE_API_KEY=Q.…`, `GROQ_API_KEY=gsk_…`, `CEREBRAS_API_KEY=csk-…`, plus `BLUESMIND_API_KEY=REPLACE_WITH_YOUR_KEY` and `BLUESMIND_BASE_URL`.
  - **Containment is correct:** `.env` is **not tracked** (`git ls-files --error-unmatch .env` → *"did not match any file(s) known to git"*), appears **nowhere in git history** (`git log --all -- .env` → empty), and is matched by `.gitignore:2` (`.env`) and `:3` (`.env.*`).
  - **Residual risk (not a git leak):** the file is world-readable (`0644`), holds what appear to be production-shaped keys, and two of them (`BLUESMIND_*`) are read through `settings.py` fields that **do not exist** (see §12). Whether these are live credentials is not verifiable from the repo; they should be treated as live until proven otherwise.
- **`.env.example`: ABSENT.** No template enumerates the expected environment, so the only interface contract for configuration is `settings.py` itself plus `.gitignore`.
- **`.gitignore` (61 lines) covers:** secrets (`.env`, `.env.*`), Python artifacts (`__pycache__/`, `*.py[cod]`, `.venv/`, `venv/`), Node (`node_modules/`, `.next/`, `dist/`), test artifacts (`.pytest_cache/`, `test-results/`, `coverage/`), editors, logs (`*.log`, `server.log`, `server.pid`), OS files, runtime data (`data/runtime/`, `data/uploads/`, `data/test_*.txt`, `*.sqlite3`, `*.db`), coverage (`.coverage`, `.coverage.*`, `htmlcov/`, `coverage.xml`), `board/ledger.md`, and a "Local scratch" block (`/default_system_prompt.json`, `/jarvis_persona.json`, `/jarvis_system_prompt.txt`, `/session_update.json`, `/mcp_servers.json`, `/system_prompt.py`, `/test_*.py`, `/test_*.wav`, `/piper_voices/`).
- **Not ignored but should be considered:** `data/ledger/` (audit JSONL, §9), `mcp_agent.secrets.yaml`, `.hypothesis/`, `.mypy_cache/`/`.ruff_cache/`.

---

## 9. Database / persistence

- **Engine abstraction:** `DatabaseEngine(ABC)` (`db/engine.py:90-109`) declares `uri`, `create_schema()`, `execute()`, `fetch_all()`, `dispose()`. `SqliteDatabaseEngine` (`:112-137`) uses `sqlite3.connect(..., check_same_thread=False)` with `row_factory = Row`; parent dir auto-created (`:117`).
- **Schema:** a **module-level `SCHEMA` tuple of 6 `CREATE TABLE IF NOT EXISTS` statements** (`engine.py:19-87`) — `mastery_records` (PK `learner_id, concept_id`), `transcripts` (autoincrement id), `sessions` (PK `session_id`, with `api_keys TEXT -- JSON`), `conversations` (FK → `sessions`), `user_settings`, `personas`. Applied idempotently by `create_schema()` (`:124-127`) and called from `build_root()` (`bootstrap.py:97`).
- **Repositories:** `MasteryRepository` (`repositories.py:38`) with an `ON CONFLICT … DO UPDATE` upsert (`_MASTERY_UPSERT`, `:20-30`) and `load_for`; `TranscriptRepository` (`:77`) with bounded `history(session_id, limit=200)` ordered `id DESC`; `SessionRepository` (`:116`) covering sessions, conversations, settings (upsert, `:350-359`), and personas (full CRUD). All SQL uses `?` bound parameters.
- **Migration strategy: ABSENT.** `alembic>=1.19.1` is in `requirements.txt:45` but there is **no `alembic.ini`, no `migrations/`, no `versions/` directory, and no `alembic` import anywhere in `app/`**. Schema evolution is `CREATE TABLE IF NOT EXISTS` + `ALTER`-by-hand; adding a column to an existing DB is unhandled. `MigrationError` exists in `exceptions.py:195` but is never raised.
- **Doc/code contradiction:** `db/engine.py:1-7` describes Postgres as "the Phase 9 SEAM: the same repositories run against a different engine URI (URL scheme `postgresql+psycopg`)". No SQLAlchemy engine is actually constructed — the only implementation is raw `sqlite3`; `settings.database_url` (`settings.py:42-45`, "PostgreSQL URL … None = SQLite") is never read by the engine.
- **Versioning — two distinct systems:**
  1. **Memory format version:** `app/memory/store.py:28` `_FORMAT_VERSION = "2.0"`, with atomic persistence (temp file + `os.replace`, per module docstring `:5-6`) and field-level validation `_validate_field_value` (`:31-66`): rejects unknown fields, rejects immutable `{id, created_at}` (`:26`, `:39-40`), type-coerces float/int/str, and range-checks `confidence`/`importance` to `[0,1]` and `access_count >= 0`.
  2. **Authority ledger:** `app/authority/ledger.py` — `AuthorityLedger` writing append-only JSONL to `data/ledger/authority.jsonl` (`:23`), default constructor creates the parent dir (`:35`). Each entry is hash-chained: the body excludes its own `hash`, is `json.dumps(..., sort_keys=True, separators=(",",":"))`, SHA-256'd, and stores `prev_hash` (`:86-108`). Genesis = `sha256(b"genesis")` (`:40`). `verify_chain()` (`:110-132`) returns `False` if any entry's hash mismatches or `prev_hash` differs from the running chain. Docstring `:6-7` is careful: *"tamper-EVIDENT, not tamper-proof: it detects alteration, which is the recorded promise."* `_last_hash()` (`:37-60`) does an 8 KiB tail read with a full-scan fallback.
  - **Gap:** the gateway writes a *separate*, **non-hash-chained** audit file — `build_root()` passes `audit_log_path="data/ledger/gateway_audit.jsonl"` (`bootstrap.py:135`) and `gateway._record_decision()` (`gateway.py:270-276`) appends `json.dumps(decision.__dict__)` with **no chaining, no integrity check**. Two audit trails with different guarantees. `data/ledger/` **does not exist** and is **not in `.gitignore`**.
  - **Coverage gap:** `ToolExecutor` accepts a `ledger` parameter (`executor.py:63`, `:71`) and has `_ledger_event()` (`:73-87`), but **`build_root()` never passes a ledger** — so tool-executor audit events are silently skipped (`_ledger_event` returns immediately when `self._ledger is None`, `:76-77`).

---

## 10. Observability in code — actual implementation

| Concern | Status | Evidence |
|---|---|---|
| **Structured logging** | **PARTIAL — implemented, never initialised** | `app/logging_config.py:23-66` `JSONFormatter` emits `timestamp/level/logger/message/correlation_id` plus any `extra` fields and `exception`; `CorrelationIdFilter` (`:15-20`) injects a ContextVar-backed id; `setup_logging(level, json_format, include_correlation)` (`:69-104`) installs a stdout handler and quiets httpx/httpcore/openai/anthropic/chromadb (`:100-104`); `set_correlation_id`/`clear_correlation_id` (`:112-122`). **`setup_logging` is never called** — grep repo-wide finds only its definition. Modules use bare `logging.getLogger(__name__)`, so output is the default unformatted root handler. `python-json-logger==4.2.0` is pinned (`requirements.txt:10`) but never imported (the formatter is hand-rolled). |
| **Tracing** | **ABSENT in practice (code defined, wiring unreachable)** | `app/telemetry/exporter.py` fully implements OTLP setup (`:22-72`), Langfuse Basic auth (`:75-83`), and five semantic-convention helper families. But `init_tracer_provider()` is called **nowhere**, `get_tracer()` is called **nowhere**, and there is **no `start_span`/`start_as_current_span` anywhere in `app/`**. Net span count emitted at runtime: **0**. |
| **Metrics** | **ABSENT** | No `set_meter_provider`, no `Meter`, no counter/histogram. `otel-collector-config.yaml:26-31` has no metrics pipeline. Port 8888 is exposed (`observability.yml:85`) but unused. |
| **Cost accounting** | **ABSENT** | The closest thing is *token usage*, not cost. `app/models/providers.py:33-43` `LLMResult` carries `prompt_tokens/completion_tokens/total_tokens` and a `usage()` dict; populated from provider responses in `providers.py:147-154` and `real_providers.py:91-98, 190-197, 270-277, 367-374`. `set_gen_ai_attributes` (`exporter.py:112-133`) can emit `gen_ai.usage.*`. But **no price table, no per-request cost computation, no budget in currency, and no aggregation**. `app/resources/budget.py` `TokenBudget` (`:10-54`) limits request/token *counts* in a rolling 60s window (`try_acquire`: `:25-36`, `_prune`: `:51-54`) — a rate limiter, not a cost account. `app/skills/builtin.py:1056` has a `price: float` field that is a **skill-template placeholder**, unrelated to LLM cost. |
| **Audit / provenance** | **PARTIAL** | Hash-chained `AuthorityLedger` (§9) is real and verifiable; `AuthorizationDecision` (`gateway.py:65-79`) is recorded per call with principal/project/capability/tiers/max_tier/allowed/reason/provenance_source/chain; `_build_provenance` (`:278-287`) stores **argument *types*, not values** (`{k: type(v).__name__}`, `:286`) — a deliberate data-minimisation choice. But the ledger is never wired into `ToolExecutor`, and the gateway's own file audit is unchained. |
| **Event bus** | **PRESENT but unused for observability** | `InMemoryAsyncBus` (`events/bus.py:26`) with `subscribe/unsubscribe/publish_async`; handlers awaited concurrently and exceptions swallowed (`:44-50`). Constructed in `build_root()` (`bootstrap.py:193`) and exposed on `AppRoot`, but no production code subscribes. Module docstring `:5-8` is explicit that core loops must **not** use it. |
| **Health** | **PRESENT** | `AppRoot.health()` (`bootstrap.py:62-81`) and `GET /api/health` (`api.py:423-431`) return `status: ok|degraded`, per-subsystem booleans, and a composite `ready`. |

---

## 11. How the app is run

- **HTTP entry point:** `app/adapters/api.py` builds the app via `create_app()`; the file's last line (`:936`) is the comment `# Uvicorn entrypoint: uvicorn app.adapters.api:app`. `app/adapters/__init__.py` re-exports `create_app`. `FastAPI(title="PROFESSOR-J", version="0.1.0")` (`api.py:~413`).
- **Route surface (`api.py`):** `GET /api/health:423`, `POST /api/chat:432`, `POST /api/chat/stream:457` (SSE), full session CRUD `510-564`, conversation CRUD `569-610`, settings `615-626`, `POST /api/upload:631`, `POST /api/ingest:674`, `POST /api/chat/upload:723`, persona CRUD `803-848`, defaults `853-870`, `POST /api/skills/execute:878`, `GET /api/skills:908`. Plus `/api/voice/*` via `app/voice/routes.py:23` (`APIRouter(prefix="/api/voice")`).
- **Configuration for run:** `api_host 0.0.0.0`, `api_port 8000`, `api_workers 1` (`settings.py:31-33`, with a `# nosec B104` justification comment).
- **CLI:** **there is no `if __name__ == "__main__"` in any `app/` module.** The only occurrence (`app/skills/builtin.py:953`) is inside a heredoc string that emits a project template. There is no `console_scripts` entry point (no `[project]` section at all).
- **Make targets:** `make test`/`test-cov`/`typecheck`/`lint`/`format`/`clean`/`reset-venv`/`langfuse-*` (§2.3). `make eval` is a stub.
- **Docker:** only `docker/observability.yml` — the Langfuse stack. **There is no `Dockerfile` and no compose service for the application itself** (`find` for `Dockerfile*` returns nothing).
- **Dev/prod split:** expressed **only** through config, never through separate entry points. `environment: Literal[...] = "development"` (`settings.py:25`) and `debug: bool = True` (`:26`) gate: the `api_key` validation (`:137-139`), the mandatory-secret list (`:201-207`), the OTel console exporter (`exporter.py:58`), and a comment-only CORS posture (`api.py:415` *"dev only; tighten for production"*). The OTel collector is behind `profiles: [production]` (`observability.yml:89-90`), so the production profile starts a collector the app never talks to.
- **Frontend dev:** `pnpm dev` (Next.js) from `frontend/`; built in CI by `ci.yml:146-179`.

---

## 12. Doc claims contradicted by code (cross-check)

1. **Version contract is internally inconsistent.** `VERSION` = `1.0.0`; `app/__init__.py:7` = `"0.0.1"`; `tests/test_smoke.py:8-9` asserts `app.__version__ == "0.0.1"`; `api.py` declares `version="0.1.0"`; `settings.py:24` `app_version = "0.1.0"`. The smoke test passes only because it pins the stale value.
2. **"Strict typecheck" does not pass.** `docs/500-software-testing.md:35` lists `.venv/bin/mypy app/  # strict typecheck` and `ARCHITECTURE-ESSENTIALS.md:188` says `make typecheck  # mypy --strict app/`. Actual: **12 errors in 3 files**. Failing modules are `app/tools/charts.py` (unused-ignore + untyped plotly imports), `app/authority/gateway.py` (7 errors: non-exported re-exports at `:35`, `no-any-return` at `:141,157,164`, missing annotation at `:290`), and `app/adapters/api.py` (`Settings` has no attribute `bluesmind_base_url`/`bluesmind_api_key` at `:336,341`).
3. **The type error at `api.py:336,341` reveals a dead code path.** `api.py` reads `settings.bluesmind_api_key`/`bluesmind_base_url`, but `Settings` defines **no such fields** — yet `.env` contains `BLUESMIND_API_KEY`/`BLUESMIND_BASE_URL`. Because `extra="ignore"` (`settings.py:18`) those values are silently dropped; the BlueSmind provider branch can never receive a key.
4. **Per-layer coverage gates are claimed but not enforced.** `pyproject.toml:63` says "Per-layer targets (95% domain/brain, 85% adapters) are enforced per-module in CI." Only the **domain** gate exists (`ci.yml:50-51`). `Makefile:51` concedes the brain/adapters gates "activate when those layers are implemented" — while `app/brain/` and `app/adapters/` are both implemented today. `app/adapters/api.py` (953 LOC, the largest single entry surface) has **no coverage gate and 5 tests**.
5. **"Contract tests against LHS export" are documented as a fixed regression signal.** `docs/500-software-testing.md:45-46`: *"A failing contract test against LHS export = schema drift → adapter fix, do not touch the canonical source."* The 3 contract tests **are failing right now** from exactly that drift (export moved to v2.1.0/1.1.0; adapter expects 0.1/0.2 and a `generated_at` field) — the documented process has not been applied.
6. **`verify.py` is presented as the workspace's canonical command but is untracked and unwired.** `docs/archive/650-workspace-operations.md:144` — *"Verify with the repo's own command: `python3 scripts/verify.py <repo>`"* — documents a **positional `<repo>` argument that does not exist** (`verify.py` takes none and hardcodes `REPO_ROOT`). The file is untracked, so a fresh clone does not have it, and CI/Makefile/pre-commit never invoke it.
7. **`docs/architecture/PROFESSOR-J-AUTHORITY-FORENSIC-AUDIT.md` documents the advisory-script problem as an open finding; it remains true.** `:171` — *"None of these is referenced by any `.github/workflows/*.yml`, `.pre-commit-config.yaml`, `Makefile`, or `commitlint.config.cjs` — verified by grep"*. Re-verified here: still zero matches for the verify scripts.
8. **A governance doc referenced by `AGENTS.md` is deleted.** `AGENTS.md:29` lists `docs/650-workspace-operations.md` as required reading; `git status` shows ` D docs/650-workspace-operations.md` and the only surviving copy is `docs/archive/650-workspace-operations.md`. `README.md`/`docs/600-changelog.md:36` still reference the live path. Note `ci.yml`'s required-docs list (`:117-129`) does **not** include it, so CI does not catch the breakage.
9. **`docs/601-agents.md` / `board/personas/README.md` describe a richer persona system than exists.** Personas are prose plus 4 DB columns; `PersonaSelectorDropdown.tsx` exists, but no code loads persona definitions from `board/personas/`.
10. **`.gitignore`-claimed secret safety is incomplete.** `mcp_agent.secrets.yaml.example:2` says *"It's in .gitignore"*; `git check-ignore` shows `mcp_agent.secrets.yaml` is **not** ignored.
11. **`prompts/` is an empty directory** though `settings.prompts_dir` (`settings.py:38`) and `PromptLoader` (`bootstrap.py:197`) are wired to it, and `ARCHITECTURE-ESSENTIALS.md:174` advertises a "Prompt Hub: versioned prompts, A/B testing".

---

## 13. Fundamentals inventory — PRESENT / PARTIAL / ABSENT

### Type checking strictness — **PARTIAL (configured strict; currently failing)**
- `pyproject.toml:3` `strict = true`; `:4` `files = ["app","tests"]`; `:10-13` tests override (`check_untyped_defs = true`).
- Enforced in CI at `ci.yml:34-35` and pre-commit `.pre-commit-config.yaml:22-30`.
- **But:** `mypy app/` exits non-zero with 12 errors → the gate is real but **red**. Tool-version skew (`1.14.1` in CI vs `2.3.1` in requirements) means local and CI strictness can diverge. Frontend: `frontend/tsconfig.json` `"strict": true`, `pnpm typecheck` in CI (`ci.yml:169-171`).

### Lint / format config — **PRESENT**
- `pyproject.toml:24-41` ruff (`line-length 100`, 9 rule families, isort first-party `app`); `:43-46` bandit; `.pre-commit-config.yaml` ruff + ruff-format + 8 hygiene hooks; `ci.yml:31-32` runs pre-commit; `frontend/eslint.config.mjs` + `pnpm lint` (`ci.yml:173-175`).
- **But:** `ruff check app/ tests/ scripts/` currently reports **26 errors** (E402 ×10 mostly in `tests/unit/authority/*`, E501 ×7, W292 ×4, F541 ×3); three ruff revisions are in play (`0.6.9` CI, `0.7.3` pre-commit, `0.16.5` requirements). `.editorconfig` absent.

### Coverage config + threshold — **PARTIAL**
- `pyproject.toml:48-64`: `source=["app"]`, **`branch = true`**, `fail_under = 80`, 4 `exclude_lines`.
- CI enforces a **domain-only ≥95%** gate (`ci.yml:50-51`), which **passes at 100.00%** (800 stmts, 0 missed).
- Codecov upload is non-blocking (`ci.yml:61` `fail_ci_if_error: false`). The documented brain ≥95% and adapters ≥85% gates **do not exist** in any config. `Makefile:45-51` `test-cov` mirrors the domain gate only.

### Determinism controls — **PRESENT (targeted)**
- Deterministic by construction in the brain: classifier/planner are LLM-free (`graph.py:32-34`, `:112-121`); `MockProvider` is the default router (`graph.py:160-162`).
- Injectable sleep for deterministic retry tests: `retry.py:34` `sleep: Callable | None = None` ("injectable for deterministic tests").
- Jittered backoff is bounded and explicit: `retry.py:81` `# noqa: S311 - bounded jitter, not security`; `pyproject.toml:46` skips bandit B311 with the same justification.
- `app/gamedev/replay.py` records and verifies deterministic execution: module docstring `:3-4` ("Records initial state, seed, intent sequence, dt steps, hashes, and emitted events"), `record_session(seed: int, …)` (`:28-35`), `verify_replay()` (`:97`).
- `app/gamedev/validator.py:132` checks for unseeded random usage in deterministic games.
- Tests isolate time/FS via 205 `tmp_path` uses and `teardown_module` resets.
- **Gap:** no `PYTHONHASHSEED`/session-wide seed pinning, and no committed hypothesis profile (`.hypothesis/` holds only cache).

### DI seams — **PRESENT (constructor injection)**
- Composition root: `app/bootstrap.py:84-223` `build_root(db_path=…, lhs_export=…, workspace_root=…)` constructs and returns every dependency in `AppRoot` (`:39-81`).
- Constructor seams: `DatabaseEngine` ABC injected into all three repositories (`repositories.py:41,80,119`); `ProviderCatalog` into `ModelRouter` (`router.py:36`); `SafetyPolicy` into `ToolExecutor` (`executor.py:59-65`) and `MCPServerManager` (`manager.py:46`); `SandboxConfig` into `CodeSandbox` (`sandbox.py:87`); `register_policy` + `blessed_registrar` into `ToolExecutor` (`executor.py:61-62`) and `SkillRegistry` (`registry.py:25`); `ledger` into `ToolExecutor` (`executor.py:63`); `approval_callback` into `SafetyPolicy` (`guardrails/policy.py:36,47`).
- Protocols/ABCs as seams: `LLMProvider`, `MemoryBackend`, `DatabaseEngine`, `MCPTransport`, `CandidateRetriever` Protocol (`memory/hybrid.py:20`), `PresentationAdapterProtocol`, `EngineRegistry`/`GameEngineAdapter`.
- **Weakness:** three module-level singletons leak global state — `_gateway` (`gateway.py:427` + `set_gateway`/`require_gateway`), `_principal_context` ContextVar (`principal.py:26`), and `_default` SafetyPolicy (`guardrails/policy.py:139` + `set_default_policy`). `build_root()` is **not idempotent** and is called per-`create_app()`.

### Retry / timeout policy — **PRESENT**
- `app/models/retry.py:27-59` `bounded_retry(operation, *, max_attempts=3, base_delay=0.05, max_delay=2.0, jitter=True, sleep=None)`; honors `retry_after` from `ProviderRateLimitError` (`_retry_after`, `:62-69`); `_delay` (`:72-82`) = `min(max_delay, base·2^(attempt-1))` with `[0.5,1.5]×` jitter and a hard `max_delay` cap. `max_attempts<1` clamps to 1 (`:42-43`).
- Error-level policy: `app/exceptions.py:384-405` `RETRYABLE_CODES` (6) and `NON_RETRYABLE_CODES` (11), plus `is_retryable()` (`:408-417`) and `get_retry_delay()` (`:420-426`, exponential + 10% jitter). Every `ProfessorError` carries `code`, `retryable`, `context` (`:11-22`).
- Timeouts: OTLP export `timeout=10` (`exporter.py:53`); sandbox wall-clock `timeout_seconds=10` (`sandbox.py:44`, enforced `:115`, `:196`); MCP `timeout_seconds: 30` per server (`mcp_servers.json:10,22,32`); `SkillMetadata.timeout_seconds = 30` (`skills/base.py:46`).
- **Gap:** `bounded_retry` is **never called** by `ModelRouter` — the router relies purely on failover (`router.py:92-111`). Router failover itself does **not** retry within a provider.

### Rate limiting — **PARTIAL**
- **Provider-level:** `app/resources/budget.py:10-54` `TokenBudget` rolling-60s window with `requests_per_min=60` / `tokens_per_min=0` (unlimited); consumed in `ModelRouter.generate` (`router.py:87-91`) and `.stream` (`:162-166`), where exhaustion is converted to `ProviderRateLimitError(retry_after=1)` and triggers failover.
- **Provider-side 429 handling:** `ProviderRateLimitError` with `retry_after` (`exceptions.py:55-64`).
- **HTTP API-level: ABSENT.** No limiter, no `slowapi`, no middleware — `api.py` registers only `CORSMiddleware`. Every endpoint is unbounded.

### Input validation — **PARTIAL**
- **Request models:** pydantic `BaseModel`s with constraints — `ChatRequest.prompt: str = Field(..., min_length=1, max_length=8000)` (`api.py:58`) is the strongest; other models are largely unconstrained (`SessionCreateRequest`, `SessionUpdateRequest`, `api.py:82-99`).
- **Guardrails:** `PromptInjectionDetector` — 7 compiled regex families (`injection.py:21-62`: `ignore_prior`, `override`, `system_prompt`, `role_change`, `jailbreak`, `instruction_leak`, `role_confusion`) applied to every string arg on **every tier** (`policy.py:64`); `PIIRedactor` — 5 patterns (email, intl phone, long digit runs, US SSN, card numbers, `pii.py:18-24`).
- **Filesystem:** `WorkspaceManager._resolve` prefix check (`workspace.py:46-51`) + size caps (`:65`, `:96`) + UTF-8 guard (`:72-73`).
- **Sandbox:** executable allow-list, module allow-list, dotnet subcommand allow-list, flag denylist, null-byte rejection (`sandbox.py:224-262`).
- **DB:** parameterised queries throughout; the two f-string `UPDATE`s are explicitly flagged `# nosec B608: fixed allowlist, bound params` (`repositories.py:247`, `:337`, `:428`) and only interpolate a hardcoded column allow-list.
- **Gaps:** no `EmailStr`/URL/ID format validation; `api_key`, `base_url`, `provider`, `model` accepted from the client verbatim and passed to provider construction (`api.py:278-351`); no output-schema validation on LLM responses; `pii.redact_deep` only walks top-level string values (`pii.py:53-67`), so nested dicts/lists are unredacted.

### Contract / schema verification — **PARTIAL (and currently broken)**
- **STEMMA export contract:** `LHSKnowledgeAdapter` validates 6 required top-level fields (`lhs_adapter.py:80-93`), then **exact** `export_version` and `schema_version` equality, raising `LHSSchemaDriftError` (`:99-109`); exposes `EXPECTED_EXPORT_VERSION = "0.1"` / `EXPECTED_SCHEMA_VERSION = "0.2"` (`:43-44`).
- **Digest contract:** `scripts/verify_export_contract.py` pins SHA-256 in `authority/exports-manifest.yaml`.
- **Tests:** 3 real-export contract tests in `test_lhs_adapter.py::TestLHSSchemaContract`.
- **Status: RED on both fronts.** Tests fail with `LHS export missing required fields: {'generated_at'}`; the digest check fails with `DRIFT — digest mismatch` (pinned `1ffe9aec…`, actual `7c872be1…`). The live export is `2.1.0/1.1.0`. The board's `check_schema_drift` (`review.py:207-241`) **still passes** because it only greps for the strings `"0.1"` and `"zero-drift"` in the adapter source — a textbook example of a string-presence check masking a real contract failure.
- **Frontend↔backend contract:** `SessionResponse`/`ConversationResponse`/`PersonaResponse` etc. are typed on the backend; `frontend/src/types/` is minimal, and nothing generates or cross-checks the client types against the FastAPI models.

### Migration strategy — **ABSENT**
- `alembic>=1.19.1` pinned (`requirements.txt:45`) but no `alembic.ini`, no `migrations/`, no `versions/`, no `alembic` import in `app/`.
- Only `CREATE TABLE IF NOT EXISTS` (`engine.py:19-87`, applied `:124-127`). No version table, no forward/backward path, no data migration. `MigrationError` (`exceptions.py:195`) is defined and never raised.
- Memory store has a `_FORMAT_VERSION = "2.0"` (`memory/store.py:28`) but no upgrader from earlier formats.

### Error taxonomy — **PRESENT (strongest fundamental in the repo)**
- `app/exceptions.py` (426 lines): `ProfessorError` base with `code`/`retryable`/`context` (`:8-22`), then 40+ typed subclasses grouped by domain — config (`:28-33`), providers (`:39-100`), circuit breaker (`:106-124`), routing (`:129-135`), knowledge (`:140-177`), memory (`:183-196`), safety/guardrails (`:202-259`), sandbox/tools (`:265-318`), MCP (`:324-345`), session/workspace (`:351-364`), evaluation (`:370-379`).
- Machine-readable retry classification: `RETRYABLE_CODES`/`NON_RETRYABLE_CODES` (`:384-405`) + `is_retryable()` (`:408-417`).
- Domain-local subclasses exist where the taxonomy doesn't fit: `AuthorizationError`/`AllocationError`/`TierExceededError`/`CapabilityNotGrantedError` (`gateway.py:41-62`), `ToolNotFoundError` (`executor.py:34-41`), `WorkspaceError`/`WorkspaceSecurityError` (`workspace.py:24-33`), `SkillError` (`skills/base.py:17-23`), `MemoryBackendError` (`memory/backends.py:24`).
- **Gaps:** `gateway.py:41-62` duplicates rather than subclasses the central taxonomy, and the four classes there use a plain `code` **class attribute** while the base uses an instance attribute — two idioms for the same concept. Several `except Exception` blocks intentionally continue (`bootstrap.py:110`, `executor.py:160`, `manager.py:83`, `ledger.py:59,72,120`), each annotated `# noqa: BLE001` with a reason.

### Eval harness — **ABSENT**
- `Makefile:79-81` is a stub: *"Evaluation harness not yet implemented (Phase 9)"* / *"Will run: .venv/bin/python -m pytest tests/evals/ -v"*.
- `tests/evals/` **does not exist**.
- Evaluation *exception types* exist (`EvaluationError`, `DatasetError`, `EvaluatorError`, `exceptions.py:370-379`) and an `EvaluatorAgent` exists (`app/brain/evaluator.py:195`) for mastery scoring — neither constitutes an eval harness over model outputs.
- `view` of `.mypy_cache` shows `langsmith` is present transitively but is not a declared dependency and is unused in `app/`.
- `docs/500-software-testing.md:17-18` promises Playwright E2E and fault-injection levels; neither exists (no Playwright config, no `tests/e2e`).

### Cost accounting — **ABSENT** (see §10) — token counts only, no pricing/aggregation.

### Secret scanning — **PRESENT**
- `.gitleaks.toml` (allowlist `tests/**/*` + `REDACTED` regex); CI job `security` runs `gitleaks/gitleaks-action@v3` with `fetch-depth: 0` (full history, `ci.yml:67-79`); plus `bandit -r app/` (`:81-84`) and advisory `pip-audit -r requirements.txt` (`:86-90`, `continue-on-error: true`).
- `.gitignore` blocks `.env`, `.env.*`; `.env` confirmed untracked and absent from history.
- **Gaps:** the `tests/**/*` allowlist makes the whole test tree unscannable; `mcp_agent.secrets.yaml` is not gitignored despite its own claims; `data/ledger/` (which will hold audit records) is not gitignored.

### Dependency management — **PARTIAL**
- `requirements.txt` pinned mixed `==`/`>=`, with declared duplicates; no lockfile, no hashes, no `pip-compile`/`uv.lock`.
- Dependabot: pip **daily** (direct + indirect, limit 10) and github-actions weekly (`.github/dependabot.yml`), with hands-off auto-merge after checks (`dependabot-auto-merge.yml`).
- Advisory `pip-audit` in CI (non-blocking).
- **Gap:** no automated check that `requirements.txt` agrees with `setup-env/action.yml`'s hardcoded `mypy==1.14.1 pre-commit==4.0.1 ruff==0.6.9`, or with `.pre-commit-config.yaml`'s ruff `v0.7.3` — three ruff versions and two mypy/pre-commit versions coexist.

---

## (a) Coverage statement

**Enumerated exhaustively (not sampled):** all **297 tracked files** via `git ls-files`, plus untracked working-tree paths (`authority/*` ×4, `scripts/verify.py`, `scripts/verify_export_contract.py`, `scripts/verify_git_safety.py`, `docs/CAPABILITY-CONTRACT.md`, `docs/archive/650-workspace-operations.md`).

**Read in full:**
- CI/CD: `ci.yml`, `release.yml`, `dependabot-auto-merge.yml`, `dependabot.yml`, `setup-env/action.yml` — **5/5**.
- Build/config: `pyproject.toml`, `requirements.txt`, `Makefile`, `.pre-commit-config.yaml`, `.gitleaks.toml`, `commitlint.config.cjs`, `.gitignore`, `VERSION` — **8/8**; `.editorconfig` confirmed absent.
- Scripts: `verify.py`, `verify_git_safety.py`, `verify_export_contract.py`, `board/review.py`, `board/ledger.md` — **5/5**.
- Docker: `observability.yml`, `otel-collector-config.yaml` — **2/2**; OTel usage grep swept all of `app/`.
- Source (full reads): `bootstrap.py`, `config/settings.py`, `exceptions.py`, `authority/{principal,policy,gateway,ledger}.py`, `tools/{executor,sandbox}.py`, `guardrails/{policy,injection,pii}.py`, `db/{engine,repositories}.py`, `logging_config.py`, `telemetry/exporter.py`, `resources/{budget,circuit_breaker}.py`, `models/retry.py`, `brain/{graph,state}.py`, `mcp/manager.py`, `workspace/workspace.py`, `skills/base.py`, `skills/registry.py`, `events/bus.py` (head), `context/manager.py` (head), `voice/routes.py` (head), `adapters/api.py` (targeted ranges + full route/signature sweep), `knowledge/lhs_adapter.py` (contract half), `models/catalog.py`, `gamedev/__init__.py`, `models/router.py`.
- Source (structural sweep: LOC, class/function inventory, grep): all 119 `app/**/*.py`, including the 16 skill classes in `skills/builtin.py` (2,405 LOC — enumerated by class/line, not read line-by-line) and the 22 `app/gamedev/*` modules.
- Tests: full tree listed; **739 collected / 3 failed** measured; per-file test counts computed for all 59 test files; `test_safety_gate.py` read in full; `test_phase6_security.py` (head) read; mocking/fixture/tmp_path/hypothesis greps across the whole tree; `.hypothesis/` inspected.
- MCP: `mcp_servers.json`, `mcp_servers.yaml`, `mcp_agent.config.yaml`, `mcp_agent.secrets.yaml.example` — **4/4**.
- Config/secrets: `.env`, `.gitignore`; `.env.example` confirmed absent; git-history checks run for `.env`.
- Persistence: `db/engine.py`, `db/repositories.py`, `memory/{store,schema}.py` (heads) + class inventory for all of `memory/`.
- Run: `frontend/{package.json,tsconfig.json}` full; `Dockerfile` confirmed absent; `__main__`/entry-point greps.
- Docs (cross-check only): `docs/500-software-testing.md`, `docs/architecture/PROFESSOR-J-AUTHORITY-FORENSIC-AUDIT.md`, `docs/archive/650-workspace-operations.md`, `AGENTS.md`, `ARCHITECTURE-ESSENTIALS.md` (targeted greps).

**Verification commands actually run:** `pytest tests/ -q` (×3, incl. `--junitxml`), `pytest tests/unit/domain/ --cov=app.domain --cov-fail-under=95`, `pytest tests/test_smoke.py`, `mypy app/`, `ruff check app/ tests/ scripts/`, `ruff --version`, `python3 scripts/verify_git_safety.py`, `python3 scripts/verify_export_contract.py`, `sha256sum ../STEMMA/exports/knowledge.json`, `.venv/bin/python --version`, plus ~20 targeted `git`/`grep`/`find`/`wc` evidence commands.

**Deliberately not read line-by-line (named, with reason):**
- `app/skills/builtin.py` — 2,405 LOC of mostly skill templates; enumerated by class/line and grepped for `@safety_gate`/`parameters_schema`/`price`.
- The body of the 22 `app/gamedev/*` modules — sized, class-inventoried, and the consensus-bearing ones (`replay.py`, `validator.py`, `core.py`) read in part; a full cognitive-repair/certification trace was out of scope for a fundamentals pass.
- `app/mcp/{client,transports,registry,search}.py` and `app/memory/{hybrid,ranking,reflexion,manager,backends,service,fact_extractor}.py` — module/class inventory + targeted reads; internals not line-audited.
- The 55 `docs/*.md` beyond the cross-checked subset.
- `frontend/src/**` (11 components, 2 hooks) — config and structure only; no line-level React audit.
- `data/uploads/*.pdf` (≥30 binary runtime artifacts) — not opened.
- `.venv/` (66k files) — excluded by design; `python -c`/grep excluded it.
- **Nothing was skipped for lack of time; the omissions above are stated as scope boundaries of a fundamentals review.**

---

## (b) Fundamentals inventory — flat list

- **Strict type checking** — `pyproject.toml:3` (`strict = true`), CI `ci.yml:34-35`; **currently red** (12 mypy errors).
- **Frontend strict TS** — `frontend/tsconfig.json` (`"strict": true`), CI `ci.yml:169-171`.
- **Lint/format** — `pyproject.toml:24-41` ruff; `.pre-commit-config.yaml:15-20` ruff+ruff-format; `frontend/eslint.config.mjs`; **26 ruff errors outstanding**.
- **Static security (SAST)** — `pyproject.toml:43-46` bandit config; `ci.yml:81-84` runs it.
- **Secret scanning** — `.gitleaks.toml`; `ci.yml:67-79` gitleaks full-history; `.gitignore:2-3`.
- **Dependency vulnerability scan** — `ci.yml:86-90` pip-audit (advisory, non-blocking).
- **Dependency updates** — `.github/dependabot.yml` (pip daily, actions weekly) + `dependabot-auto-merge.yml`.
- **Dependency pinning** — `requirements.txt` (mixed `==`/`>=`, duplicates at `:36/:54` and `:37/:55`); **no lockfile/hashes**.
- **Tool-version pinning** — `.github/actions/setup-env/action.yml:29`; **skewed** vs `requirements.txt:65-67` and `.pre-commit-config.yaml:16`.
- **Conventional commits** — `commitlint.config.cjs`; `ci.yml:203-218`.
- **Branch-name policy** — `ci.yml:181-201`.
- **Required-docs gate** — `ci.yml:108-144` (11 files + `docs/adr/`).
- **Make targets** — `Makefile` (`test`, `test-cov`, `typecheck`, `lint`, `format`, `install`, `install-dev`, `clean`, `reset-venv`, `langfuse-*`, `eval`).
- **Canonical verification runner** — `scripts/verify.py` (pytest → mypy → pre-commit, fail-fast, no args); **untracked, unwired, currently failing**.
- **Git-safety guard** — `scripts/verify_git_safety.py` (6 forbidden substrings, `--check` mode); **unwired**.
- **Export-digest contract check** — `scripts/verify_export_contract.py` + `authority/exports-manifest.yaml:5`; **currently DRIFT (exit 1)**.
- **Governance/board review gate** — `scripts/board/review.py` (8 deterministic checks); **wired at `ci.yml:105`**; 5 of 8 checks are text greps.
- **Board ledger** — `review.py:482-504` writes `board/ledger.md` (gitignored `.gitignore:48`); committed `scripts/board/ledger.md` is stale/misleading.
- **Coverage engine** — `pyproject.toml:48-64` (`branch = true`, `fail_under = 80`).
- **Coverage gate (enforced)** — domain ≥95%, `ci.yml:50-51`; measured **100.00%**.
- **Coverage gates (absent)** — brain ≥95%, adapters ≥85% (claimed `pyproject.toml:63`, not implemented).
- **Test framework** — pytest 9.1.1 + pytest-asyncio (`asyncio_mode = "auto"`) + pytest-cov; `pyproject.toml:19-22`.
- **Test suite** — 739 tests / 59 files / 17 layer dirs; **736 pass, 3 fail**.
- **Property-based testing** — hypothesis 6.167.0; one use site `tests/unit/guardrails/test_safety_gate.py:51-67`; no committed profile.
- **Test isolation** — 205 `tmp_path` usages; 40 fixtures; **no `conftest.py`**.
- **Mock boundary** — 170 mock refs in 10 files; real implementations elsewhere.
- **Failure-path testing** — 18-row safety decision matrix + adversarial security suite (`tests/unit/authority/test_phase6_security.py`).
- **Contract testing** — `test_lhs_adapter.py::TestLHSSchemaContract` (3 tests, **failing**).
- **Error taxonomy** — `app/exceptions.py` (426 lines, 40+ typed classes) + retry classification `:384-417`.
- **Retry with jittered backoff** — `app/models/retry.py:27-82`; **not wired into `ModelRouter`**.
- **Circuit breaker (3-state)** — `app/resources/circuit_breaker.py` (threshold 5, cooldown 30s); used `router.py:81,94,101`.
- **Provider failover** — `app/models/router.py:58-113` (`generate`) and `:130-193` (`stream`).
- **Rate limiting (provider)** — `app/resources/budget.py` `TokenBudget`; consumed `router.py:87-91,162-166`.
- **Rate limiting (HTTP API)** — **absent** (no middleware in `api.py`).
- **Timeout policy** — `sandbox.py:44,115,196` (10s); `exporter.py:53` (10s); MCP 30s (`mcp_servers.json:10`); skill 30s (`skills/base.py:46`).
- **Input validation (HTTP)** — pydantic models, `api.py:58` `min_length=1, max_length=8000`.
- **Prompt-injection detection** — `app/guardrails/injection.py:21-62` (7 pattern families); applied every tier `guardrails/policy.py:64`.
- **PII redaction** — `app/guardrails/pii.py:18-24` (5 patterns); `redact_deep` `:53-67`.
- **Safety tiering + HITL** — `app/domain/tool.py` `SafetyTier`; `guardrails/policy.py:56-80`; `safety_gate` decorator `:92-136`.
- **Centralized tool dispatch through the gate** — `app/tools/executor.py:321-346` (`policy.check` at `:332`).
- **Capability-registration authorization** — `app/authority/policy.py:31-42`; enforced `executor.py:89-104`, `skills/registry.py:43-52`.
- **Forgery-proof identity** — `app/authority/principal.py:31-69` (`_trusted` + `forge_attempt`).
- **Principal propagation via ContextVar** — `principal.py:26-28, 83-105`.
- **Single authoritative execution boundary** — `app/authority/gateway.py:300-415`.
- **Allocation enforcement** — `gateway.py:178-208` (project, agent membership, `max_tier`) over `authority/allocation.yaml`.
- **Permission-manifest capability grants** — `gateway.py:143-166` over `authority/permission-manifest.yaml`.
- **Tier-ceiling check** — `gateway.py:210-221` (deny-by-default on unknown capability, `:213-215`).
- **Provenance-based authorization** — `gateway.py:223-268` (AI/untrusted sources blocked from mutation caps without `human`).
- **Hash-chained audit ledger** — `app/authority/ledger.py:76-132` (SHA-256 chain + `verify_chain`).
- **Gateway decision audit log** — `gateway.py:270-276` → `data/ledger/gateway_audit.jsonl` (**unchained**).
- **MCP fail-closed gate** — `app/mcp/manager.py:116-134` (raises if no policy).
- **Workspace path-escape prevention** — `app/workspace/workspace.py:46-51`.
- **Resource-capped code sandbox** — `app/tools/sandbox.py:90-135` (`-I`, RLIMIT_AS, timeout, scrubbed env, DEVNULL stdin).
- **Sandbox command allow-listing** — `app/tools/sandbox.py:224-262`.
- **Composition root / DI** — `app/bootstrap.py:84-223`; `AppRoot` `:39-81`.
- **Typed settings with validation** — `app/config/settings.py:11-140`; repo-`.env` precedence `:160-191`.
- **Startup secret validation** — `settings.py:197-229`; **never called (dead code)**.
- **Structured JSON logging + correlation IDs** — `app/logging_config.py:15-122`; **never initialised**.
- **OTel tracing + Langfuse** — `app/telemetry/exporter.py:22-231`; **never initialised, zero spans emitted**.
- **Metrics** — **absent**.
- **Cost accounting** — **absent** (token counts only: `providers.py:33-43`, `exporter.py:112-133`).
- **Passive event bus** — `app/events/bus.py:26-50` (constructed, unsubscribed).
- **Health/readiness** — `bootstrap.py:62-81`; `api.py:423-431`.
- **Persistence abstraction** — `app/db/engine.py:90-137` (`DatabaseEngine` ABC).
- **Schema creation** — `app/db/engine.py:19-87` (6 idempotent DDL statements).
- **Repositories** — `app/db/repositories.py` (mastery upsert, transcripts, sessions/conversations/settings/personas).
- **Migration strategy** — **absent** (alembic pinned, never configured; only `CREATE TABLE IF NOT EXISTS`).
- **Memory format versioning + atomic writes + field validation** — `app/memory/store.py:26-66` (`_FORMAT_VERSION = "2.0"`, immutable `{id, created_at}`, range checks).
- **Memory backends (swappable)** — `app/memory/backends.py:104,142,206` (in-memory / JSON / Chroma).
- **Hybrid retrieval** — `app/memory/hybrid.py:34,76,124` (keyword + vector + adapter).
- **Deterministic replay** — `app/gamedev/replay.py:28-97` (seeded record/verify); `validator.py:132` unseeded-random check.
- **Layering enforcement (AST/text)** — `scripts/board/review.py:62-205`, wired `ci.yml:105`.
- **MCP declaration (3 formats)** — `mcp_servers.json` (**gitignored**), `mcp_servers.yaml`, `mcp_agent.config.yaml`; `settings.py:115`.
- **MCP secrets indirection** — `${VAR}` in all three; `mcp_agent.secrets.yaml.example`.
- **Secrets exclusion** — `.gitignore:2-3`; `.env` untracked and absent from history (verified).
- **Observability stack (compose)** — `docker/observability.yml` (postgres 16, clickhouse 24.8, langfuse 3, otel-collector 0.112 behind `production` profile).
- **Collector pipeline** — `docker/otel-collector-config.yaml:26-31` (traces only; langfuse + logging exporters).
- **App entry point** — `uvicorn app.adapters.api:app` (`api.py:936`); `create_app()`.
- **Container image for the app** — **absent** (no `Dockerfile`).
- **Packaging metadata** — **absent** (`pyproject.toml` has no `[project]`/`[build-system]`).
- **Eval harness** — **absent** (`Makefile:79-81` stub; no `tests/evals/`).
- **E2E/Playwright** — **absent** (promised at `docs/500-software-testing.md:17-18`).

---

## (c) Notable practices — most reusable

1. **Forgery-proof identity via a private constructor marker + frozen dataclass.** `Principal` sets `_trusted: bool = False` and raises `RuntimeError("Principal.forge_attempt: …")` in `__post_init__` unless `Principal.create()` set it (`app/authority/principal.py:44-69`). *Why:* it makes "who may mint an identity" a structural property of the type, not a convention — attacker code that imports the class still cannot construct a usable Principal, and the failure is loud and testable (`test_phase6_security.py:56-66`).

2. **A single choke-point execution boundary with ordered, separately-testable checks.** `AuthorityGateway.execute()` runs identity → allocation → tier → safety policy → provenance, recording an immutable `AuthorizationDecision` for **both** allow and deny (`app/authority/gateway.py:300-415`). *Why:* each authorization dimension can be reasoned about and unit-tested in isolation, and "was this allowed?" always has a persisted answer.

3. **Deny-by-default on unknown capability.** `_check_tier` raises `CapabilityNotGrantedError` when a capability has no registered tier (`gateway.py:213-215`) rather than assuming a safe default. *Why:* new/renamed tools fail closed instead of silently bypassing tiering.

4. **Bidirectional registration policy (no privilege self-grant) + explicit "no silent overwrite".** `default_register_policy` allows only SAFE/SENSITIVE for non-blessed registrars (`authority/policy.py:31-42`), and `SkillRegistry.register` refuses to replace an existing name unless `overwrite=True` (`skills/registry.py:48-54`). *Why:* an agent cannot escalate by registering a DESTRUCTIVE tool, and a typo'd name collision surfaces instead of shadowing.

5. **Fail-closed external-capability gating.** `MCPServerManager.call_tool` raises `SafetyGateError` when no safety policy is wired (`mcp/manager.py:125-133`); MCP tools default to `SENSITIVE` (`:40`); the MCP executor wrapper returns failures as data rather than propagating (`executor.py:157-165`). *Why:* a missing dependency degrades to "refuse", never to "run unguarded" — the correct direction for a security control.

6. **Tamper-evident, hash-chained audit ledger with an honest threat statement.** Each entry hashes its own body plus `prev_hash` with sorted, compact JSON separators, and `verify_chain()` re-derives the whole chain (`authority/ledger.py:76-132`); the docstring explicitly says *"tamper-EVIDENT, not tamper-proof"* (`:6-7`). *Why:* it is cheap, dependency-free, and the stated guarantee matches what the code actually delivers — no overclaiming.

7. **A property-based decision matrix for the security-critical authorization tree.** The safety gate's 18 `(tier, auto_approve_sensitive, approved)` outcomes are pinned as an explicit dict **and** re-explored by hypothesis (`tests/unit/guardrails/test_safety_gate.py:29-67`), with a `teardown_module` resetting the process-wide default policy (`:154-155`). *Why:* it converts "we think this matrix is right" into an executable oracle that also catches unconsidered combinations, and the teardown prevents cross-test policy leakage.

8. **Input-minimising provenance and telemetry.** `_build_provenance` records **argument types, not values** (`gateway.py:286`), and `_sanitize_args` redacts secret-shaped keys and truncates >1000-char strings before tracing (`exporter.py:209-231`). *Why:* audit and trace data are exactly where secrets and PII leak; minimising at the boundary is cheaper and safer than redacting later.

9. **Error taxonomy with machine-readable retry classification.** Every error carries `code`/`retryable`/`context`, and `is_retryable()` consults `RETRYABLE_CODES`/`NON_RETRYABLE_CODES` before consulting the instance flag (`exceptions.py:11-22, 384-417`). *Why:* retry policy becomes data rather than a chain of `isinstance` checks scattered through call sites, and the same error object carries enough context for structured logging.

10. **Determinism by construction in the cognitive core.** The intent classifier and planner are deliberately LLM-free (`brain/graph.py:32-34, 112-121`), the default router is a deterministic `MockProvider` (`:160-162`), and `bounded_retry`/`CodeSandbox` accept injected `sleep`/`config` seams (`retry.py:34`, `sandbox.py:87`) — additionally `gamedev/replay.py` records seeds and state hashes for replay verification. *Why:* it makes the whole graph runnable end-to-end in CI with zero network, with no flaky timing, and lets a failure be reproduced exactly.

---

### Closing summary

PROFESSOR-J's **security/authority fundamentals are the strongest layer in the repo** — forgery-proof principals, a single authorization gateway with deny-by-default tiering, gate-checked capability registration, fail-closed MCP gating, a hash-chained audit ledger, a path-escaped workspace, and a resource-capped sandbox, all with typed errors and targeted tests.

Its **verification fundamentals are configured but currently red**: 3 failing cross-repo contract tests, 12 mypy errors under `strict = true`, 26 ruff errors, and a drifting export digest — while the governance check that is wired into CI passes because 5 of its 8 checks grep for string presence rather than exercising behaviour. The canonical runner `scripts/verify.py` exists but is untracked and referenced by nothing, and the thin CI-looking corners (coverage gates for brain/adapters, eval harness, migrations, API rate limiting, API authentication, cost accounting) are documented as present-or-coming in places where the code shows otherwise.

The immediate, highest-leverage actions a parent agent should consider: (1) reconcile the STEMMA export contract (adapter expects `0.1/0.2` + `generated_at`; live export is `2.1.0/1.1.0`), (2) clear the 12 mypy errors, (3) re-record or fix the export digest, and (4) decide whether `scripts/verify.py` should be committed and wired into `make`/CI — because right now the repo's advertised canonical verification command is neither tracked nor green.
