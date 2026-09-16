# JARVIS — Application & Testing Layer Audit

**Scope**: `/home/sajan/Projects/JARVIS` — the running application (`app/`), its test suite (`tests/`), evals, frontend, automation, persistence, and the engineering fundamentals those imply.
**Method**: files read directly (source, tests, configs). `AGENTS.md`, `README.md`, `docs/` used only as cross-check.
**Measured at HEAD** `be752d2` + 102 modified/untracked working-tree files.
**Evidence rule**: every claim carries `file:line`. All file contents were treated as data.

---

## 0. Executive summary

JARVIS is a **single-tenant personal AI assistant platform**: a FastAPI monolith (21,028 lines of Python across 165 files in `app/`) with a genuinely layered architecture, a *real* governance gate, and an unexpectedly strong test suite (1,504 tests, **90% measured coverage**, 1,495 passing in 87s).

The critical finding is a **systematic wiring gap, not a coding gap**. Multiple correct, tested subsystems — circuit breaker, rate limiter, token budget, cost audit, tracer, Postgres checkpointer, SQLite checkpointer — are constructed at the composition root and then **never invoked by any live request path**. The tests pass because they test those units in isolation; nothing tests that the live `/chat` path traverses them. The dominant pattern is *capability present, capability inert*.

A second, independent finding: **CI is disabled**. `.github/workflows/ci.yml:22-23` reduces GitHub Actions to `workflow_dispatch` only, because the private repo is billing-blocked. The replacement is a local n8n → HTTP bridge → `scripts/ci_gate.py` (1,761 lines, 22 gates), which enforces *more* than Actions did — but it only runs if a systemd user service on one machine is up.

---

## 1. Application tree (`app/`) — structure, modules, entry points

### 1.1 Top-level layout (3 levels)

```
app/
├── main.py                  163 L   FastAPI app, middleware, /health /ready /metrics
├── bootstrap.py             166 L   Composition root (DI container)
├── provider_registry.py     838 L   Provider catalogue/registry
├── __init__.py                7 L
├── adapters/               1898 L   I/O protocol layer
│   ├── security.py           91 L   Single auth decision point
│   ├── http/router.py       226 L   REST /api/v1
│   ├── web/router.py        926 L   27 web endpoints (largest file)
│   ├── websocket/stream.py   ~85 L  WS + SSE
│   └── integrations/agy.py  229 L   AGY CLI adapter
├── agents/doc_agent.py      246 L   DocumentationAgent
├── api/ocr/routes.py        167 L   OCR HTTP surface (well-validated)
├── artifacts/manager.py     114 L   Blob store (sha256 names)
├── brain/                   933 L   Cognitive engine
│   ├── graph.py             233 L   LangGraph StateGraph
│   ├── nodes.py             267 L   5 contract nodes
│   ├── runner.py            149 L   ExecutionRunner
│   ├── planner.py           153 L / analyzer.py / synthesizer.py
├── config/                  492 L   settings.py, version.py, prompt.py
├── context/                 392 L   builder.py, manager.py
├── conversation/manager.py  257 L   Conversation persistence
├── domain/                  675 L   Pure dataclasses (11 files)
├── events/                  169 L   InMemoryAsyncBus
├── guardrails/              556 L   policy.py, approvals.py, decorator.py
├── integrations/           2056 L   mcp/ (8), ocr/ (8), vector/chroma.py
├── mcp/                     105 L   registry.py
├── memory/                 2929 L   Hybrid memory (16 files)
├── models/                 3240 L   20 provider clients + router
├── prompt/loader.py          92 L
├── resources/               214 L   budget, rate_limits, provider_health
├── session/                 885 L   manager, persistence, checkpointer
├── telemetry/               383 L   logger, metrics, tracer, otel_exporter
├── tools/                   973 L   base, executor, file/git/workspace
├── utils/                  2825 L   24 files (catalogs, tokenizer)
└── workspace/               242 L   manager, project, watcher
```

**Dead directories** (`.pyc` only, **zero tracked files** — `git ls-files` returns nothing for each):
- `app/backend/` — `__pycache__/providers/{registry,types,http,adapters,diagnostics}.cpython-314.pyc`
- `app/db/` — `__pycache__/engine.cpython-314.pyc`
- `app/evals/` — `__pycache__/{evaluator,metrics,dataset}.cpython-314.pyc`

These are untracked build residue from deleted source (Python 3.14 bytecode vs the project's 3.11 — `pyproject.toml:10` `requires-python = ">=3.11"`). They are **dead weight** and would import as empty namespace packages.

### 1.2 Entry points

| Entry | File:line | Notes |
|---|---|---|
| ASGI app | `app/main.py:42` | `app = FastAPI(...)`, lifespan at `:34-39` calls `bootstrap_system()` |
| `python -m app.main` | `app/main.py:160-163` | `uvicorn.run("app.main:app", port=8000, reload=True)` |
| Docker CMD | `Dockerfile:56` | `["python", "-m", "app.main"]` |
| MCP server | `scripts/run_mcp_server.py` | Separate process |
| CI bridge server | `scripts/ci_bridge_server.py:211` | localhost:8770, `ThreadingHTTPServer` |
| Eval runner | `scripts/run_evals.py:37` | `sys.exit(main())` |

**No Makefile** (`ls Makefile makefile` → not found). Task running is via `pyproject.toml`, `scripts/`, and `.pre-commit-config.yaml`.

### 1.3 Architectural layering and enforced boundaries

The layering is **declared and machine-enforced** by `scripts/board/review.py:27-48`:

```python
ALLOWED_DEPS = {
    "app.adapters": {"app.bootstrap", "app.brain"},
    "app.bootstrap": {brain, models, resources, memory, session,
                      workspace, telemetry, prompt, guardrails, artifacts, tools},
    "app.brain":    {"app.domain", "app.events", "app.guardrails"},
    "app.models":   {"app.resources"},
    "app.memory":   {"app.integrations"},
    "app.telemetry":{"app.events"},
    "app.guardrails": set(), "app.events": set(),
}
ALLOWED_UNIVERSAL = {"app.domain", "app.config", "app.utils", "app.integrations"}
```

Enforced by AST walk (`review.py:77-128`), run as the `import_layering` governance check.

**This check FAILS at HEAD.** Measured:

```
$ .venv/bin/python scripts/board/review.py ; echo $?
❌ import_layering
   - app/adapters/web/router.py: app.adapters imports app.models.factory (not allowed)
   - app/adapters/web/router.py: app.adapters imports app.provider_registry (not allowed)
✅ domain_purity ✅ schema_drift ✅ prerequisite_graph ✅ safety_gate_coverage
✅ mcp_tool_search ✅ otel_spans ✅ langgraph_checkpoint ✅ eval_suite
💥 Some governance checks failed!
1
```

Two of the nine checks are **placeholders that always return `True`**:
- `check_schema_drift()` — `review.py:189-192`, body is `return True, []` with comment *"This is a placeholder - implement when DB schema exists"*. The DB schema **does** exist (`app/session/checkpointer.py:114-123`, `app/session/postgres_checkpointer.py:82-93`).
- `check_prerequisite_graph()` — `review.py:195-198`, `return True, []`.

So the gate prints `✅ schema_drift` unconditionally; the check cannot fail.

**Domain purity is real and independently verified.** Direct AST scan of `app/domain/` yields external imports of exactly `['__future__', 'dataclasses', 'datetime', 'enum', 'typing']` — all stdlib, matching the allowlist at `review.py:152-163`.

### 1.4 Adapters / interfaces / protocols

Real interface seams exist:

| Seam | File:line | Kind |
|---|---|---|
| `BaseLLMProvider(ABC)` | `app/models/interface.py:22-58` | 4 abstract methods (`provider_name`, `is_available`, `generate_text`, `stream_text`) |
| `Checkpointer(Protocol)` | `app/session/checkpointer.py:17-24` | `@runtime_checkable` |
| `OCRBackend(ABC)` | `app/integrations/ocr/backends/base.py:15-42` | 5 abstract methods |
| `ToolResult` / `ToolDefinition` | `app/tools/base.py:19-31`, `:34-56` | Tools never raise to the agent loop |
| `ApplicationContainer` | `app/bootstrap.py:30-52` | DI dataclass, 19 services |

**A protocol is violated**: `Checkpointer` (`checkpointer.py:17-24`) declares `save/load/list_checkpoints/delete`, but `LangGraphCheckpointer` implements `save_checkpoint/get_checkpoint/get_latest_checkpoint/delete_checkpoint` (`:144, :174, :191, :228`). It does not satisfy the protocol it is annotated against — and `@runtime_checkable` only checks method *presence*, so an `isinstance` check would silently fail.

---

## 2. Test suite

### 2.1 Inventory (measured)

| Directory | `.py` files | Lines | `def test_` | Status |
|---|---|---|---|---|
| `tests/unit/` | 126 | 22,472 | 1,374 | Active |
| `tests/performance/` | 1 | 773 | 48 | Active — **but see note** |
| `tests/integration/` | 1 | 271 | 12 | Active — **but see note** |
| `tests/contract/` | 1 | 103 | 7 | Active |
| `tests/sprint3/` | 3 | 147 | 7 | Active |
| `tests/e2e/` | **0** | 0 | 0 | **Empty — `.pyc` only (source deleted)** |
| `tests/sprint4/` | **0** | 0 | 0 | **Empty — `.pyc` only (source deleted)** |
| `tests/utils/` | **0** | 0 | 0 | **Empty — `.pyc` only (source deleted)** |
| **Total** | **132** | **23,766** | **1,448 static** (1,372 sync + 76 async) | |

**Two directory names do not match their contents**:
- `tests/performance/` holds `test_security.py` (773 L, 48 tests) — a **security/stress suite** for the Documentation Agent, not benchmarks. No `pytest-benchmark`, no locust, no timing thresholds. Its docstring `:1-14` calls it a "Stress test suite".
- `tests/integration/` holds `test_ci_bridge_gate_loop.py` (271 L, 12 tests), which loads `scripts/ci_bridge.py` via `importlib.util.spec_from_file_location` (`:28-38`) with a fake GitHub transport — a *script* integration test, not an app integration test.

**Measured by pytest**: `1504 tests collected in 5.94s`. The 56-test gap between 1,448 static definitions and 1,504 collected nodes is `@pytest.mark.parametrize` expansion (6 parametrize sites).

Per-directory collected counts: `tests/unit` 1,430 · `tests/performance` 48 · `tests/integration` 12 · `tests/contract` 7 · `tests/sprint3` 7 · **`tests/e2e` 0** (`pytest tests/e2e --collect-only` → "no tests collected").

**Test quality rules from `AGENTS.md` §3.3 are only partly met.** The suite explicitly forbids "hand-built literals", "wall-clock time, network, global state", and "mocking internals" — but §2.4 shows internal-seam mocking outweighs boundary mocking 288:126, §2.8 shows 30 real `time.time()` sites and genuine `localhost:8000` network calls, and §2.7 shows there is no quarantine mechanism for flaky tests.

### 2.2 Framework and configuration

- **pytest 9.1.1**, `pytest-asyncio==1.4.0` (`requirements.txt`), `pytest-cov==7.1.0`.
- Config — `pyproject.toml:17-23`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  python_files = ["test_*.py"]
  asyncio_mode = "auto"          # 76 async tests need no decorator
  addopts = "-v --tb=short"
  ```
- **`conftest.py`: ZERO exist.** `find . -name conftest.py` excluding `.venv/node_modules/external` returns **0**. Also **zero `tests/__init__.py`** — test directories are not packages, so there is no shared fixture layer, no global setup/teardown, and no collection-time `sys.path` bootstrap. State is set up per-file via `tmp_path` (measured 354 uses), `tempfile`/`TemporaryDirectory`/`mkdtemp` (46), and `monkeypatch` (389 references across 34 files).
- **53 `@pytest.fixture` definitions exist, all file-local** — e.g. `tests/unit/test_ws_sse_auth.py:32` (`app_client`), `tests/contract/test_api_contract.py:17` (`client`, `scope="module"`), and `@pytest.fixture(autouse=True)` in the 13 `test_cat_*_catalog.py` files.
- **`asyncio_mode = "auto"` is load-bearing**: only **48** `@pytest.mark.asyncio` decorators exist for **76** `async def test_` functions — the other **28 async tests are collected only because of auto mode**. Changing that setting silently drops 28 tests.
- Installed plugins at runtime: `anyio-4.15.1, cov-7.1.0, asyncio-1.4.0, langsmith-0.12.4`.
- **No `hypothesis`, no `pytest-mock`, no `freezegun`, `responses`, `respx`, `faker`, `pytest-benchmark`, `locust`, or `syrupy`.** `requirements.txt` pins exactly four: `:17` coverage==7.16.0, `:111` pytest==9.1.1, `:112` pytest-asyncio==1.4.0, `:113` pytest-cov==7.1.0.

### 2.3 Markers

| Marker | Count |
|---|---|
| `asyncio` | 48 |
| `parametrize` | 6 |
| `skipif` | 1 |

No custom markers registered in `pyproject.toml`; no marker-based selection in CI (no `-m` flag in any workflow or gate).

### 2.4 Mocking — what is mocked

**68 of 132 test files** use `unittest.mock`/`MagicMock`/`patch`; **34** use `monkeypatch`.

Top mock targets (measured by frequency):

| Target | Count | Boundary? |
|---|---|---|
| `requests.get` | 36 | ✅ External HTTP — correct boundary |
| `app.models.switcher.ModelRouter` | 21 | ⚠️ Internal class |
| `app.utils.model_selector.llamacpp_live_models` | 18 | ⚠️ Internal function |
| `app.utils.model_selector._categorize_cloud_models` | 18 | ⚠️ Private function |
| `app.utils.model_selector.ollama_model_names` | 17 | ⚠️ Internal |
| `requests.get` (side_effect=Timeout) | 8 | ✅ Failure path |
| `app.models.switcher.create_client` | 6 | ⚠️ Internal factory |
| `builtins.input` | 9 | ✅ I/O boundary |
| `app.utils.tokenizer._try_tiktoken` | 5 | ⚠️ **Private** |
| `builtins.__import__` | 4 | ⚠️ Very deep |

**Verdict**: mocking is *mixed*. Provider HTTP is mocked correctly at the `requests.get` boundary — and importantly, failure paths are injected (`side_effect=Exception("HuggingFace down")` at `tests/unit/test_cat_hf_catalog.py:110,121,178`). But a significant cluster patches **private/internal** symbols (`_categorize_cloud_models`, `_try_tiktoken`, `_try_transformers`), which couples tests to implementation rather than behaviour — the anti-pattern `AGENTS.md:§3.3` ("Mock at boundaries, not internals") explicitly forbids.

The adversarial security suite is the exception and mocks well — `tests/performance/test_security.py:54` defines a `MockModel` and drives the *real* tool/allowlist code.

### 2.5 Contract tests — real, not mocked

`tests/contract/test_api_contract.py:16-22` builds a `TestClient` against the **real** `app.main:app` module (re-imported to escape singleton state), with `importlib.reload`. Docstring (`:1-8`): *"These tests exercise the real FastAPI app via TestClient, not mocks, so they fail loudly if an endpoint's shape drifts."* 7 tests pin `/health`, `/ready`, `/api/v1/chat/completions` shape, and auth enforcement.

This is run as a **first-class blocking gate** — `scripts/ci_gate.py:gate_contract`, registered at `ci_gate.py:1606`, `blocking=True`.

### 2.6 Failure-path coverage

- `pytest.raises`: **150 occurrences**.
- Tests matching `test_.*(fail|error|invalid|reject|denied|raise)`: **177**.
- Representative: `tests/unit/test_guardrails.py:202` `test_approval_registry_errors`; `tests/unit/test_models_exceptions.py`; `tests/unit/test_cat_together_catalog.py:111,122` (`Connection refused`, `Network error`); `tests/unit/test_cat_hf_catalog.py:110`.

**Verdict: PRESENT and substantive.** Failure paths are a real part of the suite, not an afterthought.

### 2.7 What is NOT present

| Property | Status | Evidence |
|---|---|---|
| Golden/snapshot tests | **ABSENT** | No `syrupy`, no `snapshot`, no `.ambr`/golden files in `tests/` |
| Property-based (hypothesis) | **ABSENT** | `grep -rn hypothesis tests/ app/` → 0 hits preferred; not in `requirements.txt` |
| E2E (Playwright/browser) | **ABSENT** | `tests/e2e/` contains only `__pycache__`; no `playwright` in `requirements.txt`; no `.spec.ts` |
| Mutation testing | **PARTIAL** | `scripts/ci_gate.py:gate_mutation` exists but is **opt-in** (`--with-mutation`, `:1632`) and non-blocking; `mutmut` not in `requirements.txt` |
| Coverage threshold enforced | **PARTIAL** | `ci.yml:59` `--cov-fail-under=80` (Actions disabled); `ci_gate.py:gate_coverage` is **non-blocking** (`blocking=False`) |
| `conftest.py` / shared fixtures | **ABSENT** | 0 files |
| Markers registered | **ABSENT** | none in `pyproject.toml` |

### 2.8 Determinism of the suite

**Honest assessment: mostly deterministic, with named exceptions.**

- `tmp_path` / `TemporaryDirectory`: **362 uses** — good isolation.
- `monkeypatch.setenv` / `os.environ[...]`: **55 uses** — env state restored by pytest.
- `datetime.now` / `time.time()` in tests: **36 uses** — no clock injection seam; real wall-clock in tests.
- `time.sleep` in tests: **2** — `tests/unit/test_prompt.py:46` (`0.01`), `tests/unit/test_domain.py:160` (`0.001`). Small but real.
- **Network-dependent tests that self-skip** (not hermetic, but fail-safe):
  - `tests/unit/test_chat_model_shapes.py:37` → `pytest.skip("server not running on :8000")`, hitting `http://localhost:8000/api/chat` with `timeout=180` (`:33`).
  - `tests/unit/test_memory_api_temporal.py:36,46` → same guard, `localhost:8000/api/memory`.
  - `tests/unit/test_education_facts.py:75` → `pytest.skip(f"live server not reachable: {exc}")`.
  - These 8 skipped tests explain the `8 skipped` in the measured run.

### 2.9 Measured execution

Two independent runs (mine, and a second measurement by a delegated test-suite auditor) agree on collection and coverage, and both produced a failing docs-drift assertion. Failure count varied (1 vs 3) because `tests/unit/test_check_docs.py` asserts on **live repository doc content** — an uncommitted working tree changes the count.

```
$ .venv/bin/pytest tests/ -q --cov=app --cov-report=term
1 failed, 1495 passed, 8 skipped, 1 warning in 87.33s (0:01:27)
TOTAL   8685 stmts   898 miss   90%
```

All failures are **documentation-governance guards**, not application logic: `tests/unit/test_doc_facts.py::test_real_repository_has_no_doc_drift` and the `tests/unit/test_check_docs.py` live-repo assertions. They fail because the working tree carries uncommitted modifications. **This is itself a finding**: those tests assert on mutable repository state rather than on fixtures, so the suite's green/red status depends on what is checked out.

**Lowest-coverage modules** — a clear map of what the suite does not reach:

| Module | Cover | Why it matters |
|---|---|---|
| `app/adapters/web/router.py` | **33%** | The **primary user-facing surface** (926 L, 27 endpoints) |
| `app/integrations/mcp/transports.py` | 34% | Transport layer |
| `app/adapters/integrations/agy.py` | 43% | External CLI |
| `app/utils/google_catalog.py` | 63% | |
| `app/memory/llm_extractor.py` | 65% | LLM fact extraction |
| `app/memory/dedup.py` | 66% | |
| `app/telemetry/tracer.py` | 67% | |
| `app/session/postgres_checkpointer.py` | 74% | |
| `app/brain/graph.py` | 75% | The cognitive loop |
| `app/main.py` | 78% | Entry point |

Meanwhile `app/utils/*_catalog.py`, `app/tools/*`, `app/models/*_client.py` are mostly 97-100%. **The suite is deep on leaf utilities and thin on the integrated request path** — exactly the shape that lets the wiring gaps in §7 survive.

### 2.9b Modules with ZERO test reference — and one that is unreachable dead code

Cross-referencing every `app.*` import across all 132 test files against the 138 app modules yields **nine modules that no test file references at all**:

| Module | Lines | Note |
|---|---|---|
| `app/adapters/integrations/agy.py` | **229** | Largest untested module |
| `app/integrations/mcp/transports.py` | **196** | |
| `app/api/ocr/routes.py` | **167** | See below — **unreachable** |
| `app/adapters/security.py` | **91** | Uses `hmac.compare_digest`; covered only indirectly via endpoint tests |
| `app/utils/google_catalog.py` | 82 | |
| `app/domain/cognitive_state.py` | 47 | |
| `app/domain/tool_result.py` | 36 | |
| `app/domain/safety_flag.py` | 36 | |
| `app/domain/intent.py` | 26 | |

Plus two large modules covered only indirectly: **`app/adapters/http/router.py` (226 L)** — no test file imports `app.adapters.http` — and `app/integrations/vector/chroma.py` (82 L), touched only as a patch target.

**Coverage-vs-reference reconciliation.** These two measures disagree on purpose, and the disagreement is informative. `app/adapters/security.py` shows **100% coverage** yet **zero test references**; `app/adapters/http/router.py` shows **94%** yet zero references. Coverage is achieved *transitively* — the contract tests drive the real FastAPI app, which executes both modules, but no test targets their behaviour. 100% line coverage of an auth module with no test that names it means **the auth decision path is executed but never asserted directly**. Conversely `app/api/ocr/routes.py` appears in **no coverage report row at all** (0 statements measured) — it is never imported.

**`app/api/ocr/routes.py` is dead code.** Verified three ways:
1. It defines `router = APIRouter(prefix="/ocr", tags=["OCR"])` at `:32`.
2. **No module anywhere imports it** — `grep -rn "from app.api\|import app.api\|ocr.routes\|get_ocr" app/ scripts/` returns only `app.integrations.ocr.*` (a different package) and the docstring in `app/api/__init__.py:10`.
3. `app/main.py:91-93` mounts exactly three routers — `http_router`, `ws_router`, `web_router`. **The OCR router is not among them.**

So 167 lines of the repo's most carefully validated HTTP surface (§8.4: pydantic models, extension allowlist `:84-89`, size limit `:91-99`, typed `Form` params) are **unreachable at runtime and untested**. The validation quality is real but shipped to nobody. `app/api/__init__.py:8-11` even documents *"app.api.ocr remains a live subpackage"* — the package is importable, but its router is never served. This is the same "built correctly, never wired" pattern as §7, in a different layer.

### 2.10 How tests are actually run

| Mechanism | Evidence |
|---|---|
| Repo verification command | `scripts/verify.py:19` → `.venv/bin/python -m pytest tests/ -q` |
| CI (Actions, **disabled**) | `.github/workflows/ci.yml:59` `pytest tests/ -v --cov=app --cov-fail-under=80 --cov-report=term-missing` |
| Local CI gate | `scripts/ci_gate.py:315 gate_pytest`, `:1606` |
| Pre-commit | `.pre-commit-config.yaml:1-82` — ruff, ruff-format, trailing-whitespace, check-yaml/json, gitleaks, mypy, commitlint. **Does not run pytest.** |
| Git hook | `githooks/pre-commit` — version guard, doc-fact sync, `pre-commit run` (pytest only if the facts cache is missing) |

---

## 3. `evals/` — what is evaluated

A **custom, dependency-free eval harness** (334 lines total) — not promptfoo/DeepEval/LangSmith.

| File | Lines | Role |
|---|---|---|
| `evals/eval.py` | 58 | `EvalStatus{PASS,FAIL,SKIP}`, `EvalResult(name,status,score,message,details,duration_ms)`, `EvalSuite` with `.passed`/`.score` |
| `evals/runner.py` | 87 | `discover_evals()` (:17) via `pkgutil.iter_modules`; collects classes whose name ends in `Eval` (`:42`); `run_eval` (:57); `run_suite` (:80) via `asyncio.gather` |
| `evals/reporters.py` | 52 | `terminal_report` (:8, emoji + aggregate), `json_report` (:34) |
| `evals/evals/cognitive.py` | 90 | 2 evals |
| `evals/evals/memory.py` | 137 | 3 evals |
| `evals/evals/system.py` | 211 | 5 evals |

**10 evals total**, all `async def run() -> EvalResult`:

| Eval | File:line | What it asserts |
|---|---|---|
| `cognitive_graph` | `cognitive.py:8` | Drives `stream_cognitive_loop(...)`, requires non-empty events and `next_node == "end"` (`:31`) |
| `cognitive_graph_nodes` | `cognitive.py:51` | All 5 nodes importable and callable |
| `memory_item_schema` | `memory.py:8` | 7 field defaults on `MemoryItem` |
| `memory_dedup` | `memory.py:48` | Near-dup detected, unrelated not flagged, `deduplicate` collapses |
| `hybrid_weights` | `memory.py:102` | `DEFAULT_DENSE_WEIGHT == 0.6`, `DEFAULT_SPARSE_WEIGHT == 0.4` |
| `mcp_client` | `system.py:8` | `MCPServerConfig` constructs |
| `session_lifecycle` | `system.py:41` | fork/archive/delete in a `TemporaryDirectory` |
| `context_trimming` | `system.py:101` | Pinned message survives a `max_tokens=1` trim |
| `board_governance` | `system.py:142` | `subprocess.run([sys.executable, "scripts/board/review.py"])`, timeout 60 |
| `doc_facts_drift` | `system.py:178` | `subprocess.run([... "scripts/sync_doc_facts.py", "--check"])` |

**Metrics**: pass/fail per eval, `score` 0.0-1.0, `duration_ms`, aggregate mean (`eval.py:54-58`). **No accuracy/F1/latency/cost metric** — these are structural/contract assertions, not quality measurements.

**Runnable offline?** **Partially.**
- 8 of 10 are pure Python, no network, no server → **offline-runnable**.
- `board_governance` and `doc_facts_drift` shell out to scripts. `doc_facts_drift` **currently fails** (the same doc-drift failure as the pytest suite), and the eval harness is not part of the default test run.
- `discover_evals` degrades gracefully: import failure → `EvalResult(status=SKIP)` (`runner.py:29-38`).

**Gate status**: `scripts/ci_gate.py:gate_evals` (registered `:1638`) is **opt-in** via `--with-evals`. The board check `check_eval_suite` (`review.py:270-288`) only verifies the *files exist* — it never runs them.

---

## 4. `frontend/` and JS/TS

**Framework: none — hand-written vanilla ES modules.** This is the single most misleading area of the repo.

| Artifact | Reality |
|---|---|
| `frontend/index.html` | 12,636 B, the real UI |
| `frontend/assets/*.js` | 6 files: `core.js`, `chat.js`, `picker.js`, `settings.js`, `main.js`, `app.css`, `theme.css` — **the live code** |
| `frontend/js/**` | Legacy ES-module tree (`modules/`, `utils/`), tracked but superseded by `assets/` |
| `frontend/css/**` | 6 CSS files, legacy |
| `frontend/.next/`, `frontend/_next/`, `frontend/out/` | **~419-node `node_modules` + Next.js build output** |
| `frontend/next.config.*`, `frontend/app/`, `frontend/pages/` | **DO NOT EXIST** |

**Determination**: Next.js build artifacts are present but there is **no Next.js source and no Next.js config**. `frontend/tsconfig.json` (`strict: true`, `noUncheckedIndexedAccess: true`) is **untracked by git** (`git ls-files frontend` lists 26 files, none of them `tsconfig.json`), and `include: ["**/*.ts","**/*.tsx"]` matches **zero files**. The `.next`/`_next`/`out`/`node_modules` directories are gitignored (`.gitignore:238-240`) — **pure build residue and dead weight**.

**Build tooling**: `frontend/package.json` has **no build step**:
```json
"scripts": {
  "serve": "python3 -m http.server 8081 --directory .",
  "dev":   "python3 -m http.server 8081 --directory .",
  "test":  "echo \"No tests specified for frontend\""
}
```
Served in production by FastAPI `StaticFiles` at `/static` (`app/main.py:97-101`).

**Test setup**: **no JS test framework at all** — `package.json` `"test"` is an `echo` that exits 0. The root `package.json` `"test"` is `echo "Error: no test specified" && exit 1`.

The frontend **is** tested, but **from Python**: `tests/unit/test_frontend_module_integrity.py` (299 lines) is a self-written static analyser that strips comments/strings/regex (`:26-107`), extracts imported vs declared vs called identifiers (`:110-198`), and asserts every callee is bound (`:201-218`). It includes targeted regression tests:
- `:221` `test_settings_imports_apply_default_to_chat` — the `applyDefaultToChat is not defined` class of bug
- `:234` `test_chat_does_not_statically_import_settings` — load-order cycle
- `:273` `test_chat_request_has_a_timeout_and_aborts_cleanly` — requires `CHAT_TIMEOUT_MS >= 120000` and `AbortController`
- `:292` `test_slow_replies_show_elapsed_progress`

This is genuinely clever and **PRESENT**. It is also a bespoke regex-based JS parser — it is not a substitute for a JS runtime test.

---

## 5. `n8n/` and `n8n-workflows/`

**Yes — workflows are version-controlled as JSON**, in two locations:

| Path | Lines | n8n name | Nodes |
|---|---|---|---|
| `n8n/workflows/JARVIS-Local-CI.json` | 231 | JARVIS-CI-Local | 7 |
| `n8n/workflows/JARVIS-Cleanup.json` | 600 | JARVIS-Cleanup | 15 |
| `n8n/workflows/JARVIS-HITL.json` | 522 | JARVIS-HITL | 14 |
| `n8n-workflows/doc-maintenance.json` | 91 | JARVIS-doc-maintenance | 3 |

**Duplicate directory** — `n8n/workflows/` and `n8n-workflows/` both hold workflow JSON. The split is real duplication, not a symlink.

**What the automation does**:
- **JARVIS-CI-Local** (`:231`): Schedule (30 min) / Manual → Config → HTTP POST to bridge → Summarize → Slack → Fail-if-not-OK. This *is* the CI system.
- **JARVIS-Cleanup** (`:600`): Schedule (Mon 04:00) → delete merged branches, close stale Dependabot PRs, prune old workflow runs → Slack summary.
- **JARVIS-HITL** (`:522`): poll pending → Slack/Telegram notify → webhook callback → `POST /api/v1/hitl/approve` → timeout sweep.
- **JARVIS-doc-maintenance** (`:91`): scheduled documentation maintenance.

**Deployment mechanism** (documented in `n8n/README.md`, cross-checked against code):
```
n8n (orchestration, 127.0.0.1:5678) → ci_bridge_server.py (execution, :8770) → ci_bridge.py → ci_gate.py
```
- n8n v2 removed the `executeCommand` node, so `scripts/ci_bridge_server.py` (stdlib `ThreadingHTTPServer`, `:39`) is a localhost-only, token-protected HTTP wrapper (`CI_BRIDGE_TOKEN`, header auth).
- Endpoints: `GET /health`, `POST /run`, `POST /docs`, `GET /last` (`ci_bridge_server.py:19-24`).
- Import: `n8n import:workflow --input=n8n/workflows/<file>.json`; each workflow needs a unique top-level `id` (`n8n/README.md` lists three UUIDs).
- Runs as systemd **user** services `jarvis-n8n.service` and `jarvis-ci-bridge.service`.

**Operational status (from `n8n/README.md`, "Honest gaps")**: only `JARVIS-CI-Local` is verified end-to-end. `JARVIS-HITL` is self-described as *"a labelled scaffold, not a working automation."* The README claims `/api/v1/hitl/approve` does not exist — **that documented claim is stale**: the endpoint is implemented at `app/adapters/http/router.py:126-196`. (This is exactly the kind of doc/code drift the `doc_facts` gate exists to catch, and it is currently failing.)

**No n8n version pinning, no workflow validation schema, no CI check that the JSON parses** was found.

---

## 6. `external/`, `legacy/`, `data/`, `config/`, `artifacts/`, `.claude/`, `prompts/`

| Path | Verdict | Evidence |
|---|---|---|
| `external/Unlimited-OCR/` | **Vendored third-party** — has its **own `.git`** | `external/Unlimited-OCR/.git/`, `LICENSE`, `infer.py` (11,241 B), `Unlimited-OCR.pdf` (460 KB) |
| `external/remote_ocr_example/service.py` | **Example/stub** | FastAPI `POST /ocr/process`; returns 501 if pytesseract absent |
| `legacy/server.py` | **Dead weight** | 1,114 L, not imported anywhere. Explicitly excluded from mypy: `pyproject.toml:48` `exclude = ['^legacy/']` with a comment about a *"Duplicate module named app"* hazard |
| `legacy/web_api_server.py` | **Dead weight** | 855 L, superseded by `app/adapters/web/router.py` |
| `data/` | **Runtime data — correctly gitignored** | `.gitignore:52` `data/`; `git ls-files data` → **0 files**. Contains `memories.json`, `web_settings.json`, `jarvis.db`, `checkpoints.db`, `chroma/`, `backups/`, `uploads/` |
| `config/` (dir) | **DEAD** | Only `config/version.py` + stale `__pycache__`. The live module is `app/config/version.py` |
| `config.yaml` | **Live config** | Read by `Settings.load` default (`app/config/settings.py:176`) |
| `artifacts/` | **Generated — gitignored** | `.gitignore:215`; `git ls-files artifacts` → **0 files**. 160 files: `provenance-*.intoto.json`, `*.sigstore.json`, SBOMs |
| `.claude/` | **Dead** | Single file `settings.local.json.bak` (252 B) |
| `prompts/` | **Live source data** | 4 Jinja2 MD files: `identity.md` (4,553 B), `planner.md`, `synthesizer.md`, `system_base.md`. Consumed by `app/prompt/loader.py` |

**Orphaned database**: `data/jarvis.db` contains 5-6 tables (`sessions`, `conversations`, `episode_reflections`, `learned_skills`, `library_documents`, `library_folders`) but **`grep "jarvis.db"` across the entire tree returns zero references** — leftover from removed code. `data/checkpoints.db` DDL matches `app/session/checkpointer.py:115-123`.

---

## 7. Database / persistence / memory

### 7.1 Store inventory

| Store | Tech | File:line | Wired? |
|---|---|---|---|
| `MemoryStore` | JSON, atomic (tmp+`fsync`+`os.replace`) | `app/memory/store.py:68`, save `:200-215` | ✅ Yes |
| `ConversationManager` | JSON, atomic | `app/conversation/manager.py:189,199-207` | ✅ Yes |
| `SessionPersistence` | JSON files | `app/session/persistence.py:16` | ✅ Yes |
| `WebSettingsStore` | JSON, `chmod 0o600` | `app/adapters/web/settings.py:27,89` | ✅ Yes |
| `ApprovalRegistry` | JSON, atomic | `app/guardrails/approvals.py:195`; wired `bootstrap.py:142` | ✅ Yes |
| `ArtifactManager` | Blobs, sha256 names | `app/artifacts/manager.py:43-49` | ✅ Yes |
| `ChromaVectorStore` | ChromaDB + Ollama embeddings | `app/integrations/vector/chroma.py:15-40` | ✅ Yes |
| `ConversationVectorStore` | ChromaDB | `app/memory/conversation_store.py:21-39` | ✅ Yes |
| `LangGraphCheckpointer` | **SQLite** | `app/session/checkpointer.py:96,103` | ❌ **Never constructed in `app/`** |
| `MemorySaverAdapter` | In-memory dict | `app/session/checkpointer.py:46-93` | ⚠️ Constructed, **result discarded** |
| `PostgresCheckpointer` | Postgres JSONB | `app/session/postgres_checkpointer.py:53` | ❌ **Driver not installed** |

**`bootstrap.py:93-105` constructs `MemorySaverAdapter()` at `:99` and `:104` and discards the return value.** `ApplicationContainer` (`bootstrap.py:30-52`) has **no checkpointer field**. `get_checkpointer()` (`checkpointer.py:249-254`) is referenced only by tests.

### 7.2 SQL and schema

Only **two** `CREATE TABLE` statements exist app-wide:
- `app/session/checkpointer.py:114-123` (SQLite `checkpoints`)
- `app/session/postgres_checkpointer.py:82-93` (Postgres `checkpoints`, JSONB)

Both use `CREATE TABLE IF NOT EXISTS`. **No ORM, no SQLAlchemy, no Alembic** (`grep -rni "sqlalchemy\|alembic" app/` → 0 hits; `find -name alembic.ini` → nothing).

### 7.3 Migrations and versioning

**ABSENT as a system.** `grep -rni "schema_version|migration_version" app/` → **0 hits**.

Version handling is ad-hoc and non-functional:
- `app/memory/store.py:194` writes `{"version": "2.0", ...}` — a **hardcoded string literal**, never read or validated on load.
- `app/conversation/manager.py:189` — same hardcoded `"2.0"`.
- `app/memory/schema.py:88-116` `Memory.from_dict` does implicit field back-compat (`data.get("created_at", data.get("timestamp", ...))`).
- `scripts/remediate_memory_store.py:179` *does* write `doc["version"]="2.1"` — the only version bump in the repo, in a **manual one-off script not invoked by any runtime or CI path**.

Schema evolution is therefore "whatever `CREATE TABLE IF NOT EXISTS` does" — which for an **existing** `checkpoints.db` means **nothing**; adding a column is silently ignored.

**Two documented migrations exist as prose only**: `docs/migrations/v2_to_v3_migration.md` (16 lines, an API-usage guide) and `docs/migrations/tombstones.md`. Neither is executable.

**One-off remediation scripts (manual, not wired)**: `scripts/migrate_memory_temporal.py` (ADR-015 backfill, dry-run by default `:148`), `scripts/remediate_memory_store.py`.

### 7.4 The single highest-severity defect: silent write loss

`app/session/persistence.py`:
- `:23` selects Postgres mode by URL prefix.
- `:115-116` `_save_session_pg` is an **EMPTY PLACEHOLDER**.
- `:27-29` when `_use_postgres` is true, `save_session` returns having **written nothing**.
- `:49-53` `load_session` still reads the **JSON file**.

So with `JARVIS_DATABASE_URL=postgresql://...` set (`bootstrap.py:79`), the system **accepts every conversation write and silently discards it**, then reads back a stale file. No error is raised or logged.

### 7.5 Memory subsystem

16 files, 2,929 lines: `manager.py` (291), `store.py` (301), `service.py` (207), `temporal.py` (430, bi-temporal ADR-015), `ranking.py` (178), `retrieval.py`, `hybrid_retriever.py`, `vector_retriever.py`, `dedup.py` (155), `fact_extractor.py` (162), `llm_extractor.py` (159), `pipeline.py`, `conversation_store.py`, `rules.py` (316), `schema.py` (156).

Bi-temporal model (`app/memory/schema.py:42-48`): `valid_at`/`invalid_at` (event time), `expired_at` (system time), `occurs_at`, plus a `superseded_by`/`supersedes` correction chain — *"so nothing is deleted."* This is a real, non-trivial design.

Retrieval is hybrid: `app/memory/hybrid_retriever.py` with `DEFAULT_DENSE_WEIGHT = 0.6`, `DEFAULT_SPARSE_WEIGHT = 0.4` (pinned by the `hybrid_weights` eval, `evals/evals/memory.py:114-125`).

Corruption handling is genuinely good: `app/memory/store.py:244-250` quarantines unparseable JSON via `app/utils/corruption.py:27-49` (`backup_corrupt_file`, replace-or-copy2) and `:52-77` (`report_corruption`, logs ERROR with an explicit **data-loss** warning), then starts empty rather than crashing.

---

## 8. Error handling and configuration

### 8.1 Error taxonomy

**Typed errors — PRESENT and coherent** (`app/models/exceptions.py`):

| Class | Line | Purpose |
|---|---|---|
| `ModelError` | `:21` | Base; carries `.cause` (`:28-30`), repr includes cause (`:32-36`) |
| `ModelConnectionError` | `:39` | Never reached a backend |
| `ModelTimeoutError` | `:43` | |
| `ModelRateLimitError` | `:47` | |
| `ModelResponseError` | `:51` | Responded but malformed |
| `PolicyViolationError` | `app/guardrails/policy.py:17` | **Never raised anywhere** |
| `HITLRequiredError` | `app/guardrails/policy.py:21` | Raised `:72`, `:82` |
| `ApprovalNotFoundError(KeyError)` | `app/guardrails/approvals.py:39` | Subclasses `KeyError` deliberately |
| `ApprovalAlreadyDecidedError(ValueError)` | `app/guardrails/approvals.py:43` | Subclasses `ValueError` deliberately |
| `OCRServiceError` | `app/integrations/ocr/service.py:18` | → 502 at `app/api/ocr/routes.py:150` |

Translation is centralised: `map_openai_error` (`exceptions.py:94-136`) and `map_ollama_error` (`:139-161`), ordered most-specific-first, preserving `.cause`. The docstring (`:11-15`) explains this replaced a broad swallow in `main.py`.

**Exception-to-protocol mapping is confined to adapters** (correct — keeps the decision testable):
- `app/adapters/http/router.py:177-182` — `KeyError`→404, `ValueError`→409, with comments naming the domain classes.
- `app/api/ocr/routes.py:150-156` — `OCRServiceError`→502, catch-all→500.

**Broad-catch counts in `app/` (measured)**:
- Bare `except:` → **0**
- `except Exception` → **93** (35 annotated `# noqa: BLE001`)
- `except BaseException` → **0**

Heavy concentrations: `app/adapters/web/router.py` (14), `app/utils/*_catalog.py` (14). Zero bare excepts is a genuine, enforced-standard positive.

### 8.2 Configuration

**Mechanism**: hand-rolled dataclasses, **not** pydantic — `app/config/settings.py:16-103`, loaded by `Settings.load` (`:172-243`).

Validation is defensive rather than schema-based:
- `_safe_dataclass` (`:106-119`) — filters unknown keys against `dataclasses.fields`, falls back to defaults on `TypeError`/`ValueError`.
- `_safe_model_config` (`:122-138`) — defaults `name`/`role` to the dict key, **skips** invalid entries.
- `yaml.YAMLError` (`:185-187`) and `OSError` (`:188-190`) both degrade to defaults with a warning.
- Thread-safe double-checked singleton (`:246-258`), with `reset_settings()` for tests (`:261-265`).

**No JSON-Schema / pydantic config model, no fail-fast on invalid config** — every malformed section silently falls back to defaults. That is a deliberate resilience choice, but it means a typo'd config key produces default behaviour with only a log warning.

### 8.3 Env vars

- `python-dotenv`: `load_dotenv` at `app/main.py:17` (deliberately before other imports, `:16`), `app/adapters/web/router.py:35`, and `override=False` at `app/utils/provider_catalog.py:40-42`.
- **40 raw `os.environ`/`os.getenv` call sites** across `app/`. **No centralised env schema or registry.**
- `.env.example` (1,420 B) enumerates ~35 variables with a "never commit the real `.env`" warning.
- `.env` is correctly gitignored (`.gitignore:91`), as is `.ci-bridge.env` (`.gitignore:271`). **Verified not tracked**: `git ls-files .env .ci-bridge.env` → empty.

### 8.4 Secret handling

**The strongest part of the codebase** (`app/adapters/security.py`, 91 lines):

- Single decision point, deliberately framework-free (`:8-11`).
- `is_authorized` (`:53-74`) uses **`hmac.compare_digest`** (`:74`) with the comment *"a plain `!=` would leak the key prefix to a timing probe."*
- Credential precedence: `Authorization: Bearer` → `X-API-Key` → query param (`:38-50`).
- Query-param credentials (which land in logs/history) are **opt-in** via `allow_query` (`:56-58`); only streaming opts in (`:77-91`). The REST surface does not.
- Empty key ⇒ allow-all (`:62-63`) — documented single-tenant local-dev behaviour.
- **Phase 0 fix F4** (`:1-6`): this module exists because WS/SSE previously enforced nothing while REST did.

**The weakness**: API keys are stored **plaintext** in `data/web_settings.json` (`app/adapters/web/settings.py:289-296`). Verified present on disk: the `google` key is set, 52 chars. File mode is `0600` (`:89`) — but the tmp file is written *before* the `chmod`, and there is no encryption at rest. Redaction is by convention at the API boundary (`get_api_key_status` `:284-286`, `MASK` sentinel `:39`).

`config.yaml` uses `api_key: "env:XAI_API_KEY"` references (lines 24, 34, 43) — **no literal secrets tracked**.

**Bug**: `app/models/factory.py:212-214` passes the **raw** `config.api_key` (not the resolved value) to `LlamaCppClient`, so an `env:` reference reaches the backend unresolved.

---

## 9. Observability

| Capability | Status | Evidence |
|---|---|---|
| Structured logging | **PARTIAL** | `app/main.py:24-30` `basicConfig` with a hand-built JSON format; `:64-87` middleware emits `request_start`/`request_end` JSON. But `app/utils/logging_setup.py:28-44` `setup_logging()` — the proper helper — is **never called**. The OCR subsystem uses `structlog` independently (`app/api/ocr/routes.py:8,30`) — two logging stacks. |
| Correlation IDs | **PARTIAL** | `X-Correlation-ID` generated/propagated in `main.py:68,72,80,84` and echoed in the response header (`:84`). **Confined to `main.py`** — never propagated into any app-layer logger. |
| Metrics | **PARTIAL — near-inert** | `MetricsCollector` (`app/telemetry/metrics.py:24`) exposes 4 counters via `export_prometheus` (`:40-58`) at `GET /metrics` (`main.py:146-157`). `record_request()` is called **exactly once** (`app/adapters/http/router.py:97`). `record_step_failure()` is **never called**. The **web `/chat` endpoint never records anything**. |
| Tracing | **INERT** | `Tracer.trace` (`app/telemetry/tracer.py:60-105`) is constructed (`bootstrap.py:112-117`) but its **only consumer** is `app/brain/graph.py:69` inside the LangGraph wrapper — and `bootstrap_system()` never calls `build_cognitive_graph`. **No span is produced on the live path.** |
| OTel | **PARTIAL** | `app/telemetry/otel_exporter.py:42`, opt-in via `JARVIS_OTEL_ENABLED` (`bootstrap.py:102`). Docstring default `:4318` (`:14`) vs code default `:4317` (`:28`) — a doc/code mismatch. |
| Cost tracking | **ABSENT** | `TokenUsageEvent` is defined (`app/events/models.py:58-67`) and consumed by the logger (`app/telemetry/logger.py:49-53`, prints `[COST AUDIT]`). **Nothing in `app/` ever publishes it.** `MetricsCollector.total_cost_usd` is therefore always 0. |
| Health/readiness | **PRESENT** | `/health` (`main.py:114-116`, static dict), `/ready` (`main.py:119-143`, real container checks + 503), `/metrics` (`:146`) |
| Event bus | **PRESENT** | `InMemoryAsyncBus` (`app/events/bus.py:22`); `publish_async` uses `gather(return_exceptions=True)` (`:41-48`); `_safe_execute` swallows handler errors with `logger.exception` (`:59-69`) |

`/health` returns a **static dict** without consulting any subsystem — it cannot detect a degraded system.

---

## 10. How the app is run

### 10.1 Docker

`Dockerfile` (57 lines), multi-stage, and genuinely hardened:
- `:2` builder stage `python:3.11-slim`; `:19` runtime stage
- `:23-24` **non-root user** `jarvis`; `:40` `USER jarvis`
- `:44-45` `HEALTHCHECK` in **JSON (exec) form** — `:41-43` explains the shell form was replaced to satisfy hadolint DL3025
- `:56` `CMD ["python", "-m", "app.main"]`

### 10.2 docker-compose

`docker-compose.yml` (19 lines) — **one service only**:
```yaml
postgres:
  image: pgvector/pgvector:pg16
  ports: ["${POSTGRES_PORT:-5432}:5432"]
  healthcheck: pg_isready...
```
The app itself is **not** in compose. Postgres + pgvector is provisioned, but see §7.4: the Postgres code path silently discards writes, and `psycopg`/`asyncpg` are **not in `requirements.txt`** — so `PostgresCheckpointer` raises `RuntimeError` on construction (`postgres_checkpointer.py:71-75`).

### 10.3 Dev/prod split

| Aspect | Dev | Prod |
|---|---|---|
| Checkpointer | `MemorySaverAdapter` (in-memory) | `PostgresCheckpointer` — **unreachable (no driver)** |
| Session store | JSON files | Postgres — **`_save_session_pg` is empty** |
| Auth | allow-all when `JARVIS_API_KEY` unset (`security.py:62-63`) | Bearer/key required |
| Reload | `uvicorn.run(..., reload=True)` (`main.py:163`) | `CMD python -m app.main` (no reload) |
| CORS | `localhost:3000/8000` defaults (`main.py:50-53`) | `CORS_ALLOWED_ORIGINS` env |

**The prod split is nominal**: the Postgres backend cannot actually serve (no driver installed, empty save method). In practice, setting `JARVIS_DATABASE_URL` *causes silent data loss* rather than enabling production persistence.

### 10.4 CI

**GitHub Actions is DISABLED.** `ci.yml:4-22` — the account is billing-blocked; runs die in ~5s. Reduced to `on: workflow_dispatch` (`:22-23`).

Four workflows exist: `ci.yml`, `deploy.yml`, `release.yml`, `jules-conflict-resolver.yml`.

**The real CI** is `scripts/ci_gate.py` (1,761 lines), invoked by `ci_bridge.py` (844 lines) from n8n. **22 gates** (`ci_gate.py:1601-1638`):

*Blocking*: `ruff_ratchet`, `semgrep`, `mypy`, `pytest`, `contract`, `gitleaks`, `trufflehog`, `bandit`(reported), `trivy`, `osv`, `licenses`, `sbom`, `provenance`, `board`, `docs`, `doc_types`, `doc_facts`, `compileall`, `hadolint`, `checkov`, `commitlint`.
*Opt-in*: `coverage`, `docker_build`, `mutation`, `evals`.

Notable properties:
- **Isolated worktree**: materialises the target commit in a detached worktree so the gate never touches the primary tree (`ci_gate.py:1-10`).
- **Isolated tool venv**: SOTA scanners live in `~/.local/share/jarvis-ci-tools` so the pinned `.venv` is never disturbed (`ci_gate.py:50-53`).
- **Ratchet semantics**: `lint_changed.sh` ruff-checks only *changed* files, because the tree carries pre-existing debt.
- **mypy baseline**: `.governance/mypy_baseline.txt` = **485 errors**, enforced by `gate_mypy` as a ceiling that "may only go DOWN."
- **Provenance**: emits in-toto + sigstore attestations to `artifacts/`.

`deploy.yml:1-40` deploys to Cloudflare Pages on `v*` tags — but its `directory: '.'` and `cloudflare/pages-action@v1` target a static site, while the app is a FastAPI backend. It also runs `.venv/bin/pytest` on a runner that installed deps to the *system* Python (`deploy.yml:24-31`) — that step would fail.

---

## 11. FUNDAMENTALS — PRESENT / ABSENT / PARTIAL

### 11.1 Present in code

| # | Fundamental | Status | Proof file:line |
|---|---|---|---|
| 1 | **Type checking (mypy strict configured)** | **PRESENT** | `pyproject.toml:35-48` `strict=true`, `disallow_untyped_defs=true`; `legacy/` excluded `:48` |
| 2 | **Lint config** | **PRESENT** | `pyproject.toml:25-33` ruff, select `E,F,W,I,UP,B,C4,SIM,PIE`, line-length 100 |
| 3 | **Coverage config + threshold** | **PRESENT (threshold not blocking)** | `ci.yml:59` `--cov-fail-under=80`; measured **90%**; `ci_gate.py:gate_coverage` `blocking=False` |
| 4 | **Dependency injection seams** | **PRESENT** | `app/bootstrap.py:30-52` `ApplicationContainer`, wired `:143-163`; `ModelRouter(resource_manager=…)` `:123`; `BaseLLMProvider` ABC `app/models/interface.py:22` |
| 5 | **Secret handling** | **PRESENT** | `app/adapters/security.py:74` `hmac.compare_digest`; query-param opt-in `:56-58`; `.env` gitignored (`.gitignore:91`, verified untracked) |
| 6 | **Input validation** | **PRESENT (partial coverage)** | `app/integrations/ocr/schemas.py:25,53` pydantic models; `app/api/ocr/routes.py:84-99` extension+size; `app/memory/store.py:29-65` field validator; manual 422s `app/adapters/http/router.py:141-168` |
| 7 | **Error taxonomy** | **PRESENT** | `app/models/exceptions.py:21-52`; `app/guardrails/policy.py:17,21`; `app/guardrails/approvals.py:39,43`; zero bare excepts in `app/` |
| 8 | **Circuit breaker** | **PRESENT (state machine) / INERT (wiring)** | `app/resources/provider_health.py:13,26-27,35-72` |
| 9 | **Retry / failover** | **PRESENT (single-shot)** | `app/models/router.py:146-169`; `app/models/omni_client.py:50-57` backoff window |
| 10 | **Timeout policy** | **PARTIAL** | Hardcoded `timeout=120` in `anthropic/cohere/google/hf` clients; OCR `config.py:51` 600s. **No timeout on any OpenAI-SDK client** |
| 11 | **Rate limiting** | **PARTIAL — tracks, does not enforce** | `app/resources/rate_limits.py:10-51` counter; `get_rpm`/`get_tpm` never called |
| 12 | **Contract / schema verification** | **PRESENT** | `tests/contract/test_api_contract.py` runs against real app (`:16-22`); blocking gate `ci_gate.py:gate_contract` |
| 13 | **Experiment / eval harness** | **PRESENT** | `evals/eval.py:39-58`, `evals/runner.py:80`, 10 evals; `scripts/run_evals.py:37` |
| 14 | **Cost accounting (plumbing)** | **PARTIAL — plumbing only** | `TokenUsageEvent` `app/events/models.py:58-67`; consumer `app/telemetry/logger.py:49-53`; **no publisher** |
| 15 | **Determinism controls** | **PARTIAL** | `tmp_path` ×362; `monkeypatch` ×55; **no clock injection** (`datetime.now` ×36 in tests), no seeding |
| 16 | **Observability (structured logs + metrics + health)** | **PRESENT (partial wiring)** | `main.py:24-30,64-87,114-157`; `app/telemetry/metrics.py:24-58` |
| 17 | **Feature flags** | **ABSENT** | `grep -rni "feature_flag\|is_enabled\|enable_feature" app/` → only `git_diff_stat` false positives |
| 18 | **Migration strategy** | **ABSENT as a system** | No Alembic/SQLAlchemy; no `schema_version`; `CREATE TABLE IF NOT EXISTS` only |
| 19 | **Governance gate (architecture boundary enforcement)** | **PRESENT** | `scripts/board/review.py:27-48,77-128` — **currently failing** at `app/adapters/web/router.py` |
| 20 | **Supply-chain / SAST / SCA** | **PRESENT** | `ci_gate.py`: semgrep, trivy, osv, bandit, pip-audit, gitleaks, trufflehog, sbom, licenses, provenance, checkov |
| 21 | **Reproducible build provenance** | **PRESENT** | `ci_gate.py:gate_provenance`; 160 artifacts in `artifacts/` (in-toto + sigstore) |
| 22 | **Pre-commit hooks** | **PRESENT** | `.pre-commit-config.yaml:1-82`; `githooks/pre-commit` |
| 23 | **Convention enforcement (commits)** | **PRESENT** | `commitlint.config.cjs`; `ci_gate.py:gate_commitlint`; `githooks/commit-msg` |
| 24 | **Non-root container** | **PRESENT** | `Dockerfile:23-24,40` |

### 11.2 Notably absent (with evidence of absence)

| # | Fundamental | Evidence of absence |
|---|---|---|
| 1 | **Property-based testing** | `grep -rn hypothesis app/ tests/` → 0 hits; not in `requirements.txt`. No generated-input tests anywhere |
| 2 | **Golden / snapshot testing** | No `syrupy`/`snapshottest`; no `*.ambr`, no `__snapshots__/`, no `golden/` under `tests/` |
| 3 | **E2E tests (browser/Playwright)** | `tests/e2e/` contains **only `__pycache__/`** — zero `.py`. No playwright in `requirements.txt`; no `.spec.ts` |
| 4 | **Frontend test framework** | `frontend/package.json` `"test": "echo \"No tests specified for frontend\""` (exits 0); root `package.json` `"test"` = `exit 1` |
| 5 | **Shared test fixtures (`conftest.py`)** | `find . -name conftest.py` (excl. vendored) → **0 files** |
| 6 | **Registered pytest markers** | None in `pyproject.toml:17-23`; no `-m` marker selection in any gate |
| 7 | **Feature flags** | Searched `feature_flag`, `featureflag`, `enable_feature`, `is_enabled` across `app/` → 0 real hits |
| 8 | **Migration framework** | No `alembic.ini`, no `alembic/`, no `sqlalchemy` import; `grep schema_version app/` → 0 |
| 9 | **Schema versioning of stored data** | `app/memory/store.py:194` and `app/conversation/manager.py:189` write a hardcoded `"version": "2.0"` that is never validated on read |
| 10 | **Clock/randomness injection** | No `Clock`/`TimeProvider` abstraction; `time.time()` and `datetime.now()` called directly (34 sites in `app/`); `import random` appears **nowhere** in `app/` and no `seed()` |
| 11 | **Cost accounting (actual)** | `TokenUsageEvent` is never published — searched all `publish(` call sites in `app/`: tracer `:105`, `brain/runner.py:127,149`, `brain/nodes.py:126`. None is `TokenUsageEvent` |
| 12 | **Rate-limit enforcement** | `RateLimitTracker.get_rpm`/`get_tpm` have **zero callers**; no limit constant defined anywhere |
| 13 | **Token-budget enforcement** | `TokenBudgetManager.is_within_budget` (`budget.py:53`) and `record_usage` (`:29`) have **zero callers** in `app/` |
| 14 | **Real distributed tracing** | `Tracer.trace` is called only from `app/brain/graph.py:69`, reached only when LangGraph builds a graph — which `bootstrap_system()` never does |
| 15 | **Retry with backoff/jitter** | `tenacity==9.1.4` is in `requirements.txt` but **imported nowhere** (`grep -rn tenacity app/ scripts/ evals/ tests/` → 0). The only retry (`models/router.py:159`) has no loop, no delay, no jitter |
| 16 | **Config schema validation** | No pydantic/JSON-Schema model for `config.yaml`; `app/config/settings.py:106-119` silently falls back to defaults on any error |
| 17 | **Centralised env-var schema** | 40 raw `os.environ`/`os.getenv` sites; no registry, no startup validation |
| 18 | **Encrypted secret storage** | `app/adapters/web/settings.py:289-296` plaintext JSON; verified on disk (google key, 52 chars) |
| 19 | **`PolicyViolationError` ever raised** | Defined `app/guardrails/policy.py:17`; `grep` shows only the definition — the tier policy can only raise `HITLRequiredError` |
| 20 | **Mutation testing in CI** | `ci_gate.py:gate_mutation` is opt-in (`--with-mutation`, `:1632`); `mutmut` not in `requirements.txt` |
| 21 | **Localization / i18n** | No `gettext`, no locale files |
| 22 | **Load/soak testing harness** | `tests/performance/` holds security/adversarial tests, not load tests; no locust/k6 |
| 23 | **Database connection pooling** | `app/session/checkpointer.py:137` opens a connection per call (`check_same_thread=False`); `postgres_checkpointer.py` likewise (`:108-116`). No pool anywhere |
| 24 | **Idempotency keys / dedup on write APIs** | Searched `idempotenc` across `app/` → 0 hits; `POST /api/upload`, `/api/memory` unguarded |
| 25 | **Shared test fixtures (`conftest.py`)** | 0 files repo-wide; 53 fixtures all file-local; 0 `tests/__init__.py` |
| 26 | **Registered pytest markers** | No `markers = [...]` block anywhere; `--strict-markers` not set; custom markers (`e2e`, `slow`, `integration`) never used |
| 27 | **`xfail` / quarantine mechanism** | `grep xfail` across `tests/` → **0 hits**; no `pytest.importorskip`, no `unittest.skip`. Flaky tests have no quarantine path despite AGENTS.md §3.3 requiring one |
| 28 | **Real network isolation library** | No `responses`, `respx`, `vcrpy`, or `httpretty`; network is either hand-patched or genuinely attempted against `localhost:8000` |
| 29 | **Performance/load benchmarks** | `tests/performance/` holds `test_security.py` — a security/stress suite with no benchmarks, no timing thresholds, no `pytest-benchmark`/locust. The directory name is misleading |
| 30 | **E2E tests** | `tests/e2e/` collects **0 items**; only `test_api_server_e2e.cpython-314-pytest-9.1.1.pyc` (17,794 B) survives — the source was deleted |
| 31 | **Any test of `app/api/ocr/routes.py`** | 0 references — and the module is unreachable anyway (§2.9b) |

---

## 12. Cross-cutting risks (ranked)

| # | Risk | Evidence | Impact |
|---|---|---|---|
| 1 | **Silent conversation-write loss in Postgres mode** | `app/session/persistence.py:115-116` empty; `:27-29` returns without writing; `:49-53` reads a different backend | Data loss with no error |
| 2 | **Governance gate fails at HEAD** | `app/adapters/web/router.py` imports `app.models.factory` + `app.provider_registry` — measured exit 1 | Architecture boundary already breached; gate is red in CI |
| 3 | **Primary UI surface is 33% covered** | `app/adapters/web/router.py` 456 stmts, 306 missed | 27 endpoints, most paths unexercised |
| 4 | **Resilience stack is inert in production** | `container.model_router` used only at `main.py:126` as a boolean | Circuit breaker, rate limiting, budget never engage on live traffic |
| 5 | **Postgres deployment path is unreachable** | `psycopg`/`psycopg2`/`asyncpg` absent from `requirements.txt` | Prod-mode boot would raise `RuntimeError` (`postgres_checkpointer.py:71-75`) |
| 6 | **Plaintext API keys at rest** | `app/adapters/web/settings.py:289-296`; key present in `data/web_settings.json` | Credential exposure on host compromise |
| 7 | **Duplicate-UUID bug in SQLite checkpointer** | `checkpointer.py:152` generates id, `:162` inserts a **second** `uuid4()` | `save_checkpoint` returns an id that matches no row |
| 8 | **`Checkpointer` protocol not satisfied** | Protocol `checkpointer.py:17-24` vs impl `:144,174,191,228` | `runtime_checkable` isinstance silently fails |
| 9 | **CI depends on one machine** | `ci.yml:22-23` `workflow_dispatch`; n8n systemd user service | No CI if that host is down; merges unverified |
| 10 | **Two always-pass governance checks** | `review.py:189-192`, `:195-198` | `schema_drift` falsely reports ✅ |
| 11 | **`/health` cannot detect degradation** | `main.py:114-116` static dict | Orchestrators get a green light from a broken process |
| 12 | **Frontend test coverage is regex-based** | `tests/unit/test_frontend_module_integrity.py:26-107` | No JS runtime executes the UI in tests |
| 13 | **Untracked dead packages** | `app/backend/`, `app/db/`, `app/evals/` — `.pyc` only | Confusing; importable as empty namespaces |
| 14 | **Orphaned `data/jarvis.db`** | 5-6 tables, 0 references tree-wide | Stale state, misleading |
| 15 | **`deploy.yml` is misconfigured** | `deploy.yml:33-39` Cloudflare Pages on a FastAPI backend; `.venv/bin/pytest` on a system-Python runner | Deploy job cannot succeed |
| 16 | **`app/api/ocr/routes.py` is unreachable dead code** | Defines `router` at `:32`; no importer anywhere; `app/main.py:91-93` mounts only 3 routers | 167 L of the best-validated HTTP surface is never served |
| 17 | **`adapters/security.py` at 100% coverage with zero test references** | 0 test files import it; transitively executed via contract tests only | Auth path executes but is never asserted directly |
| 18 | **Suite asserts on live repo state** | `test_doc_facts.py`, `test_check_docs.py` read the checked-out tree | Green/red depends on uncommitted files, not on code correctness |

---

## 13. Coverage statement

### Files read per area

| Area | Read breadth | Notable exclusions |
|---|---|---|
| **`app/` top level** | `main.py` (163 L, full), `bootstrap.py` (166 L, full), `provider_registry.py` (structure, 838 L) | `provider_registry.py` body read selectively |
| **`app/adapters/`** | `http/router.py` (226 L, full), `security.py` (91 L, full), `__init__.py` (full), `websocket/stream.py` (full), `web/router.py` (~350 of 926 L), `integrations/agy.py` (structure) | `web/router.py` middle sections (~570 L) read via targeted grep, not linearly |
| **`app/guardrails/`** | `policy.py` (88 L, full), `decorator.py` (full), `approvals.py` (first 120 L + grep) | `approvals.py:121-365` via grep only |
| **`app/brain/`** | `graph.py` (233 L, full) | `nodes.py`, `runner.py`, `planner.py`, `analyzer.py`, `synthesizer.py` via grep/structure |
| **`app/models/`** | `interface.py` (58 L, full), `exceptions.py` (161 L, full), `router.py` (184 L, full) | The 20 provider clients via grep only (catalog/factory behavior verified through subagent report) |
| **`app/telemetry/`** | `metrics.py` (58 L, full), `tracer.py` (105 L, full) | `logger.py`, `otel_exporter.py` via grep + subagent |
| **`app/config/`** | `settings.py` (269 L, full), `version.py` (194 L, full) | `prompt.py` via structure |
| **`app/memory/`** | `schema.py` (156 L, full) | Remaining 15 files via grep + subagent report |
| **`app/resources/`** | `rate_limits.py` (51 L, full), `budget.py` (56 L, full), `manager.py` (full) | `provider_health.py` via subagent (read in full by them) |
| **`app/session/`** | `checkpointer.py` (first 150 L + grep), `postgres_checkpointer.py` (220 L, full) | `persistence.py`, `manager.py`, `context.py` via subagent |
| **`app/tools/`** | `base.py` (full), `__init__.py` (full), `workspace_tools.py` (first 60 L) | `executor.py`, `file_tools.py`, `git_tools.py` via grep |
| **`app/domain/`** | Full AST scan of all 11 files for external imports | Individual dataclass bodies not read line-by-line |
| **`app/integrations/`** | `vector/chroma.py` (first 50 L), `ocr/service.py` (structure), `ocr/backends/base.py` (full) | MCP package (8 files, 1,215 L) via structure only |
| **`tests/`** | Full file listing (132 files); `test_frontend_module_integrity.py` (299 L, full), `test_api_contract.py` (first 80 L), `test_ci_bridge_gate_loop.py` (first 50 L), `test_security.py` (structure), `test_chat_model_shapes.py` (first 45 L), `test_education_facts.py` (partial), `test_memory_api_temporal.py` (first 45 L), `test_langgraph_engine_contract.py`, `test_s3_execution_verification.py` | 120 of 126 unit test files read via aggregate grep only, not individually |
| **Test metrics** | Measured by executing pytest twice (collection + coverage) | — |
| **`evals/`** | All 6 source files read in full (334 L) | — |
| **`frontend/`** | `package.json`, `tsconfig.json` (full); file inventory of `assets/`, `js/`, `css/`, `.next/`, `_next/`, `out/` | Individual `.js` bodies not read (validated by the Python integrity test) |
| **`n8n/`, `n8n-workflows/`** | All 4 workflow JSONs parsed and node-listed; `n8n/README.md` (full) | Individual node parameter bodies not read |
| **Configs** | `pyproject.toml` (full), `ci.yml` (full), `deploy.yml` (first 60 L), `docker-compose.yml` (full), `Dockerfile` (full), `.pre-commit-config.yaml` (full), `config.yaml` (full), `.env.example` (full), `.gitignore` (targeted) | `release.yml`, `jules-conflict-resolver.yml` not read |
| **Scripts** | `board/review.py` (324 L, full), `run_evals.py` (37 L, full), `lint_changed.sh` (full), `verify.py` (full), `githooks/pre-commit` (full), `ci_gate.py` (registry + ~10 gates + orchestration), `ci_bridge_server.py` (head) | ~1,400 of `ci_gate.py`'s 1,761 lines not read linearly |
| **Data/persistence** | `data/web_settings.json` (keys inspected, values not printed) | Binary DBs inspected for table names only |

### Executed (measured, not inferred)

- `.venv/bin/pytest tests/ --co -q` → **1504 tests collected in 5.94s**
- `.venv/bin/pytest tests/ --cov=app --cov-report=term` → **1 failed, 1495 passed, 8 skipped in 87.33s**, **TOTAL 8685 stmts, 898 miss, 90%**. An independent second run measured `3 failed, 1493 passed, 8 skipped in 84.47s`, same 90% — the failure-count delta is live-repo doc assertions (see §2.9).
- `.venv/bin/pytest tests/e2e --collect-only` → **collected 0 items** ("no tests collected")
- Per-directory collection: unit 1430 · performance 48 · integration 12 · contract 7 · sprint3 7 · **e2e 0** = 1504
- `.venv/bin/python scripts/board/review.py` → **exit 1** (import_layering fails)
- `.venv/bin/python -m coverage report --sort=cover` → per-module table
- Zero-test-reference cross-check: every `app.*` import across all 132 test files diffed against all 138 app modules → **9 modules unreferenced** (§2.9b)
- Import/reachability trace for `app/api/ocr/routes.py` → `router` defined at `:32`, **0 importers**, not mounted at `app/main.py:91-93`, absent from coverage report → dead code
- AST purity scan over `app/domain/` → `['__future__','dataclasses','datetime','enum','typing']`

### Skipped and why

- **`docs/` content** — explicitly designated cross-check only; not audited as a deliverable. (Its drift is *measured* indirectly via the failing `test_doc_facts` and `doc_facts_drift` eval.)
- **Vendored `external/Unlimited-OCR/`** — third-party with its own `.git`; not this repo's code. `external/remote_ocr_example/service.py` read (head).
- **`node_modules/`, `.venv/`, `.mypy_cache/`, `__pycache__/`** — vendored/generated. Exception: orphaned test `.pyc` files were inventoried as evidence (§2.1, below).
- **`legacy/*.py` (1,969 L)** — confirmed dead (nothing imports it; mypy-excluded at `pyproject.toml:48`); not read beyond the head of `web_api_server.py`.
- **Binary artifacts** — `data/chroma/*`, `data/*.db`, `artifacts/*.intoto.json` inspected for structure/table names only.
- **`release.yml`, `jules-conflict-resolver.yml`, `sbom.json` (75 KB), `governance-report.json`** — not read.
- **`app/provider_registry.py` (838 L)** — read at structure level; its behaviour is exercised by `tests/unit/test_provider_registry.py`.
- **~1,400 lines of `scripts/ci_gate.py`** — the gate *registry* and representative gates were read; individual scanner wrappers were not. (A delegated auditor read `gate_pytest:315-318`, `gate_contract:1265-1270` and the coverage check at `:~613-620` in full and confirmed their blocking/non-blocking status.)
- **Individual bodies of the 20 `test_models_*_client.py` files** — pattern confirmed identical (real constructor exercised, SDK method overwritten with `MagicMock`), then sampled rather than read end-to-end.

### Orphaned test bytecode (evidence of deleted suites)

Six `.pyc` files survive with no corresponding `.py`, recoverable only by filename:

| Orphaned `.pyc` | Deleted source |
|---|---|
| `tests/e2e/__pycache__/test_api_server_e2e.cpython-314-pytest-9.1.1.pyc` (17,794 B) | `tests/e2e/test_api_server_e2e.py` |
| `tests/sprint4/__pycache__/test_ecosystem_contract.cpython-311-pytest-9.1.1.pyc` (10,456 B) | `tests/sprint4/test_ecosystem_contract.py` |
| `tests/utils/__pycache__/test_tokenizer.cpython-314-pytest-9.1.1.pyc` (5,190 B) | `tests/utils/test_tokenizer.py` |
| `tests/integration/__pycache__/test_brain_guardrails_integration.cpython-314-…pyc` (8,634 B) | `test_brain_guardrails_integration.py` |
| `tests/integration/__pycache__/test_memory_models_integration.cpython-314-…pyc` (7,076 B) | `test_memory_models_integration.py` |
| `tests/performance/__pycache__/stress_test.cpython-311-…pyc` | `tests/stress_test.py` |

Note the **Python version mix** (3.14 and 3.11 bytecode) — `tests/e2e/`, `tests/utils/`, and the two `tests/integration` orphans were built by a *different interpreter* than the pinned 3.11 venv, corroborating that these suites were deleted rather than merely moved. No test references a nonexistent module: full collection produced **0 import errors**, so all 132 surviving files are valid and importable.
