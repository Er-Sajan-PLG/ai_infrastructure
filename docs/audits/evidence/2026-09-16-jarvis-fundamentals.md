# JARVIS — FUNDAMENTALS Layer Forensic Report

**Status**: SNAPSHOT
**Type**: snapshot
**Last Updated**: 2026-09-17
**Source**: `.github/`, `githooks/`, `scripts/`, `.governance/`, `pyproject.toml` at HEAD `be752d2`

**Scope**: the machinery that keeps the repo working — environment, automation, hooks, CI/CD, governance, security, release, config/data handling.
**Method**: forensic read of actual files. Every claim carries `path:line`. Documentation is used only as a cross-check; contradictions are flagged as **DOC/CONTRADICTION**.
**Repo state at read**: HEAD `be752d2`, branch `feat/ci-cd-gap-closure`, `git describe` = `v3.22.1-1-gbe752d2`, working tree dirty (large uncommitted diff).

---

## 0. Executive summary

JARVIS's FUNDAMENTALS layer is built on one governing premise, stated in code at `scripts/ci_gate.py:11-17`:

> "GitHub Actions is unavailable for this private repo on the free tier: every run dies in ~5s with an account-level billing block … Branch protection is also 403 … Local n8n (Community, which HAS the Execute Command node) is the automation control plane; this script is the execution plane it invokes."

Everything follows from that: **CI was moved out of GitHub and into a local n8n + systemd + Python stack**. The result is genuinely more rigorous than the hosted workflow it replaced (26 gate functions vs 6 Actions jobs), but it is also **process-enforced rather than platform-enforced** — `ci_bridge.py:22-24` concedes "branch protection is 403 on a private free-tier repo, so nothing here can gate a merge regardless."

**Four structural risk themes** recur throughout:

1. **No hard enforcement boundary.** Statuses are published; nothing blocks a merge. `AGENTS.md:138` is honest about this: "Enforcement is *process, not policy*."
2. **~20% of the automation surface is orphaned.** `sota_governance.py` (649 lines), `doc_governance.py` (332), `governance_check.py` (62), `check_web_contract.py` (189) and `check_state_consistency.py` (146) have zero callers; three of the four GitHub workflows are `workflow_dispatch`-only.
3. **The doc-drift mechanism currently reports drift on its own repo.** `sync_doc_facts.py --check` exits 1 at HEAD with 2 findings; `check_docs.py --strict` exits 1 with 1 finding.
4. **Live secrets sit on disk, untracked and 0600 — but one is 0644 and a GitHub PAT was displayed in this session.** No secret was ever committed.

---

## 1. GitHub Actions (`.github/`)

7 files total. **3 of 4 workflows are neutered to `workflow_dispatch` only**; `deploy.yml` is not.

### 1.1 `.github/workflows/ci.yml` (123 lines) — DISABLED

- **Trigger**: `on: workflow_dispatch:` only (lines 18-19). Lines 3-11 record why:
  > <!--doc-facts:quoted-->"DISABLED (2026-09-10): … every run dies in ~5s … CI now runs locally: n8n (jarvis-n8n.service) polls every 30 minutes and drives scripts/ci_bridge.py -> scripts/ci_gate.py, which enforces strictly MORE than this workflow did (22 checks incl. SAST, SCA, SBOM, provenance, licences)."<!--doc-facts:quoted-->

  **DOC/CONTRADICTION**: this comment says <!--doc-facts:quoted-->"22 checks"<!--doc-facts:quoted-->; `grep -c '^def gate_' scripts/ci_gate.py` = **26**, and `CONTRIBUTING.md:40` renders `<!--fact:gate_count-->26<!--/fact-->`. The static comment in `ci.yml:10` is outside the fact-marker system and has gone stale.
- **Concurrency**: `group: ci-${{ github.ref }}`, `cancel-in-progress: true` (21-23).
- **Permissions** (25-28): `contents: read`, `pull-requests: read`, `security-events: write`.
- **Jobs (6)**: `lint-and-typecheck` (31), `test` (51), `security` (61), `build` (90), `commitlint` (102), `governance` (113).
  - `lint-and-typecheck`: ruff ratchet via `scripts/lint_changed.sh` (44); mypy `--strict app/` with `continue-on-error: true` (47-49) — comment at 45-46: "mypy strict is not yet enforced repo-wide (591 legacy errors)."
  - `test`: `.venv/bin/pytest tests/ -v --cov=app --cov-fail-under=80` (59) — **`--cov-fail-under=80` is a hard fail here**, unlike the local gate where coverage is reported-only.
  - `security`: gitleaks via Docker `zricethezav/gitleaks:v8.30.1` (72-76); bandit and pip-audit both `|| true` (79, 82); SARIF upload (83-88).
  - `build`: `compileall` (98) + `docker build -t jarvis:${{ github.sha }} .` (100).
  - `commitlint`: `wagoid/commitlint-github-action@v6` with `configFile: commitlint.config.cjs` (109-111).
  - `governance`: `.venv/bin/python scripts/board/review.py` with `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (121-123).
- **Actions versions**: `actions/checkout@v7` (35, 56, 66, 95, 106, 118) — v7 is not a published major as of this writing; `github/codeql-action/upload-sarif@v3` (85).

### 1.2 `.github/workflows/deploy.yml` (40 lines) — **LIVE AND BROKEN** ⚠️

This is the only workflow with a real trigger:

```yaml
on:
  push:
    tags:
      - 'v*'
```
(lines 3-6)

- **Permissions**: `contents: read`, `deployments: write` (8-10).
- **Secrets**: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GITHUB_TOKEN` (36-40).
- **Defect (verifiable, not inferred)**: lines 23-26 install deps with plain `pip install -r requirements.txt` into the system interpreter and **never create `.venv`**. Lines 28-31 then run:
  ```yaml
  run: |
    .venv/bin/pytest tests/ -q
    .venv/bin/python scripts/board/review.py
  ```
  `.venv/bin/pytest` cannot exist. Every tag push — and `githooks/pre-push:45` auto-creates a tag on **every push to main** — fires a workflow that fails at the verification step. `directory: '.'` (39) would also deploy the repo root to Cloudflare Pages.
- **DOC/CONTRADICTION**: `docs/CI-GATE-SOTA.md:152-153` states "2026-09-10 — GitHub Actions disabled in-repo (all three workflows reduced to `workflow_dispatch`)". There are **four** workflows and `deploy.yml` was **not** reduced. The changelog entry is inaccurate.

### 1.3 `.github/workflows/release.yml` (161 lines) — DISABLED
`on: workflow_dispatch:` only (9-10). Permissions `contents: write`, `pull-requests: write`, `packages: write`, `id-token: write` (16-20). Jobs `prepare` (23) and `release` (89).
- `prepare` is gated `if: github.event_name == 'push' && …` (26) — **unreachable** under `workflow_dispatch`, so the job can never execute even if manually dispatched.
- Version derivation is a mix of `git describe` and regex (`42-77`), duplicating `scripts/version_bump.py`.
- Full gate at 105-112 runs `mypy --strict app/` **blocking**, which the local gate treats as a ceiling ratchet.
- `git tag -s` (116) requires a GPG key; `RISK-011` records no signing material. `docker/build-push-action@v7` (125), `sigstore/cosign-installer@v3` with `cosign-release: 'v2.4.1'` (138-140) — note `scripts/ci_gate.py:1166` states "cosign v3 requires `--bundle`", so the workflow pins a version the local gate has moved past.

### 1.4 `.github/workflows/jules-conflict-resolver.yml` (68 lines) — DISABLED
`on: workflow_dispatch:` only (8-9); the 15-minute cron is commented out at 5-7. Permissions narrow: `pull-requests: read`, `contents: read` (11-13). Secrets: `JULES_API_KEY` (51). Installs `@google/jules` (28), finds Bot-authored PRs with `mergeable_state == "dirty"` (36-46), then shells `jules task create … --prompt "… force push the resolved branch"` (63-65). Note the prompt instructs a force-push, which `AGENTS.md:135` lists as convention-forbidden.

### 1.5 `.github/dependabot.yml` (33 lines)
- `pip` ecosystem, `/`, **daily at 04:00**, `open-pull-requests-limit: 10`, labels `["deps","automerge"]`, prefix `chore(deps)` (3-11).
- 5 `groups` (12-22): `testing`, `linting`, `security`, `fastapi`, `ml`.
- `github-actions` ecosystem, weekly Monday 04:00, limit 5, labels `["ci","automerge"]` (24-33).
- **Note**: `automerge` labels are declared but nothing automates them — no auto-merge workflow or app exists in the repo. `docs/ACCEPTED_RISKS.md:25` (RISK-012) records the backlog consequence: "Dependabot #44-#53 sit open with 0 statuses."

### 1.6 `.github/CODEOWNERS` (36 lines)
Every path routes to a **single owner** `@Er-Sajan-PLG`: bootstrap/main (5-6), brain (9), guardrails+adapters (12-14), models+resources (17-18), memory (21), config (24), CI/CD+governance (27-33), docs (36). Because it is a solo repo, CODEOWNERS is not an independent-review control — and `AGENTS.md:134` notes "1 approval — **0 for solo repo** (GitHub forbids self-approval)."

### 1.7 `.github/actions/setup-env/action.yml` (23 lines) — composite
```yaml
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pre-commit==4.1.0 ruff==0.8.0 mypy==1.11.2 pytest==9.1.1 pytest-asyncio==1.4.0 pytest-cov==7.1.0 bandit==1.8.3 pip-audit==2.9.0
.venv/bin/pre-commit install --install-hooks
```
(lines 19-23). Default `python-version: "3.11"` (6).

**Tool-version divergence (material)**: this action installs `ruff==0.8.0` / `mypy==1.11.2`, while `requirements.txt` pins `ruff==0.16.6` (line 123) and `mypy==2.3.1` (line 57). CI and a developer's local venv run **different linters and type checkers**. `.pre-commit-config.yaml` pins a third set: `ruff-pre-commit rev: v0.8.0` (4) and `mirrors-mypy rev: v1.11.2` (42). The workflow layer is dead, so this is latent — but it means the three definitions of "clean" are not the same.

---

## 2. Git hooks (`githooks/`)

`core.hooksPath = githooks` (verified via `git config --get core.hooksPath`), so these three files are the only hooks that fire. `.git/hooks/` contains only `*.sample` files. Installed via `.venv/bin/python scripts/bump_version.py install-hooks` → `bump_version.py:58`: `git config core.hooksPath githooks`.

### 2.1 `githooks/pre-commit` (94 lines, mode 755)
`set -euo pipefail` (5). Four sequential gates:

1. **Version-literal guard** (12-18) — refuses a hardcoded version:
   ```bash
   if grep -Eq '^VERSION[[:space:]]*=[[:space:]]*["'"'"']v[0-9]' "$VERSION_FILE"; then
     echo "❌ app/config/version.py must derive VERSION from git, not hardcode it."
     exit 1
   ```
2. **Print derived version** (21-38) — informational, `|| true` at 22.
3. **Doc-fact sync** (44-67) — the load-bearing gate. Uses the cached facts when present for speed (47-53), else `--sync` (56); on failure prints the log and `exit 1` (51, 58). Then re-stages *only* touched docs (63-65), so the corrected docs ride in the same commit.
4. **Doc-type table regeneration** (73-79) — runs `doc_type_table.py --write` with **`|| true`** (74), so a real failure (missing markers, exit 1) is silently swallowed here and surfaces only later in `gate_doc_types`.
5. **pre-commit framework, staged files** (84-90):
   ```bash
   SKIP=mypy "$REPO_ROOT/.venv/bin/pre-commit" run || { echo "❌ pre-commit failed…"; exit 1; }
   ```
   Comment at 81-83: "mypy is excluded here until the legacy type backlog is cleared — tracked as RISK-005."

**What it does NOT run**: `check_docs.py`, `scripts/board/review.py`, pytest, `sota_governance.py`, `check_links.py`. Doc *structure* is not gated at commit time — only doc *facts* are.

### 2.2 `githooks/pre-push` (82 lines, mode 755) — auto-tags AND auto-releases
`set -uo pipefail` (21) — deliberately **no `-e`**: the header at 18-20 states "The hook never blocks the push on failure."
- Default branch resolved from `origin/HEAD` (25-26); the loop skips any ref that is not the default branch (34-35).
- Latest `vA.B.C` tag via `git describe --match 'v[0-9]*.[0-9]*.[0-9]*'` (37-38); if commits are ahead (41-43), it calls `version_bump.py --apply --tag-only` (45).
- **Contradiction with its own docstring**: line 15-17 says "`version_bump.py --apply` commits the pyproject metadata bump and tags," but the hook passes `--tag-only`, which by design `version_bump.py:133-147` does **not** commit and does not bump `pyproject.toml`.
- Then pushes the tag explicitly (56-66) — comment at 51-53 explains the ordering: "we are inside pre-push, so the tag is not on the remote yet and gh refuses to release an unpushed tag." It treats "tag already on remote" as success (62-65).
- Then calls `publish_release.py` (68); failure is a warning, not a block (71, 74).
- Line 47-50 records the observed defect: "GitHub showed 21 tags and 0 releases".

### 2.3 `githooks/commit-msg` (48 lines, mode 755)
- Requires a message file (21-24); skips `Merge*`, `fixup!*`, `squash!*` (28-30).
- **Fails open**: if `commitlint` is not on PATH it prints a warning and `exit 0` (33-37). Commit-message convention is therefore unenforced on any machine lacking the npm global.
- Otherwise `commitlint --config commitlint.config.cjs --edit "$MSG_FILE"` (39).
- Header at 13-15 explains its own existence: "core.hooksPath=githooks overrides pre-commit's auto-installed hooks; without a commit-msg file here, the commit-msg stage never fires." Note `.pre-commit-config.yaml:34-39` *also* defines a `commitlint` hook at stage `commit-msg` — that one is now unreachable.

---

## 3. `scripts/` — 45 Python files, 11,615 lines

### 3.1 Wiring reality

| Script | Wired to | Status |
|---|---|---|
| `ci_gate.py` (1761) | `ci_bridge.py:539` | **core, live** |
| `ci_bridge.py` (844) | `ci_bridge_server.py`, n8n, systemd | **core, live** |
| `ci_bridge_server.py` (230) | `jarvis-ci-bridge.service` + 2 n8n workflows | **core, live** |
| `sync_doc_facts.py` (324) | `githooks/pre-commit:49,56`; `ci_gate.py:1383` | **live** |
| `doc_facts.py` (266) | imported by `sync_doc_facts.py:30`, `ci_gate.py:1677` | **live** |
| `doc_type_table.py` (159) | `githooks/pre-commit:74`; `ci_gate.py:1353` | **live** |
| `doc_types.py` (356) | imported by 3 scripts | **live** |
| `doc_links.py` (220) | `check_docs.py:38-42` | **live** |
| `check_docs.py` (515) | `ci_gate.py:1311` | **live** |
| `scripts/board/review.py` (324) | `ci_gate.py:384`; `ci.yml:121`; `deploy.yml:31` | **live** |
| `version_bump.py` (167) | `githooks/pre-push:45` | **live** |
| `publish_release.py` (219) | `githooks/pre-push:68` | **live** |
| `bump_version.py` (110) | manual (`install-hooks`) | manual |
| `github_app_token.py` (339) | imported `ci_bridge.py:193` | live (inactive until App registered) |
| `scheduled_doc_maintenance.py` (186) | `ci_bridge_server.py:45`; n8n cron | **live** |
| `doc_review_due.py` (287) | `scheduled_doc_maintenance.py:134` | live |
| `run_evals.py` (37) | `ci_gate.py:584` — opt-in, never passed | **unreachable** |
| `lint_changed.sh` (42) | `ci.yml:44` only | **dead caller** |
| `sota_governance.py` (649) | **nothing** | **orphan** |
| `doc_governance.py` (332) | **nothing** | **orphan** |
| `governance_check.py` (62) | **nothing** | **orphan** |
| `check_web_contract.py` (189) | **nothing** | **orphan** |
| `check_state_consistency.py` (146) | **nothing** | **orphan** |
| `check_reported_bugs.py` (335) | one unit test | manual |
| `setup_branch_protection.py` (119) | **nothing** | **inert (403)** |
| `commit.sh` (52) | **nothing** (doc mention only) | manual |
| `check_frontend_modules.mjs` (108) | **nothing** | **orphan** |
| archaeologist family (812) | each other only | **orphan** |
| memory trio (706) | one test | manual |

**There is no `Makefile`.** Verified absent.

### 3.2 `scripts/ci_gate.py` (1761 lines) — the centerpiece

CLI (`1702-1722`): `--sha` (required unless `--init-signing`), `--base` (default `origin/main`), `--json`, `--out`, `--keep-worktree`, `--with-coverage`, `--with-docker`, `--with-mutation`, `--with-evals`, `--init-signing`.

**Mechanism — shadow worktree**: `_prepare_worktree()` (179-207) materialises the target SHA in a detached worktree under `/tmp/jarvis-ci-gate/<sha12>` (52, 176) and runs every gate with that as cwd, so `import app` resolves to the worktree copy. `_worktree_env()` (226-233) forces this via `PYTHONPATH`, and `_resolve_app()` (236-246) **proves** which `app` was imported by printing `app.__file__`.

**Ratchet base (subtle and correct)**: `_resolve_merge_base()` (249-262) uses `git merge-base base HEAD`, with the rationale at 251-256:
> "Diffing the branch tip against `base` directly is WRONG: when the branch was cut from an older main (every Dependabot PR), the diff also contains main's own newer commits, so unrelated files get linted."

**26 blocking/reported gates**, in execution order (`1602-1638`):

| # | Gate | Blocking | Note |
|---|---|---|---|
| 1 | `gate_ruff_ratchet` (270) | ✅ | changed `.py` files only, vs merge-base |
| 2 | `gate_semgrep` (812) | ✅ | `--config=p/default --severity=ERROR`, changed files |
| 3 | `gate_mypy` (428) | ✅ | **ceiling ratchet** vs `.governance/mypy_baseline.txt` |
| 4 | `gate_pytest` (315) | ✅ | |
| 5 | `gate_contract` (1263) | ✅ | `tests/contract` |
| 6 | `gate_gitleaks` (340) | ✅ | git-aware (no `--no-git`) |
| 7 | `gate_trufflehog` (1009) | ✅ | `--results=verified` in git history |
| 8 | `gate_bandit` (511) | ❌ reported | |
| 9 | `gate_pip_audit` (537) | ❌ reported | |
| 10 | `gate_trivy_fs` (872) | ✅ | CRITICAL/HIGH, risk-register-aware |
| 11 | `gate_osv` (1063) | ❌ reported | |
| 12 | `gate_licenses` (944) | ✅ | denies AGPL/GPL-3/GPL-2/SSPL/BUSL/CC-BY-NC |
| 13 | `gate_sbom` (1101) | ❌ reported | writes `artifacts/sbom-<sha>.cdx.json` |
| 14 | `gate_provenance` (1127) | ❌ reported | in-toto + cosign sign/verify |
| 15 | `gate_board` (377) | ✅ | |
| 16 | `gate_docs` (1289) | ✅ | `check_docs.py --strict` |
| 17 | `gate_doc_types` (1334) | ✅ | `doc_type_table.py --check` |
| 18 | `gate_doc_facts` (1373) | ✅ | `sync_doc_facts.py --check` |
| 19 | `gate_compileall` (408) | ✅ | |
| 20 | `gate_hadolint` (1236) | ✅ | |
| 21 | `gate_checkov` (1466) | ❌ reported | |
| 22 | `gate_commitlint` (687) | ✅ | Python reimplementation, `--max-count=250` |
| 23 | `gate_coverage` (602) | ❌ reported | opt-in `--with-coverage` |
| 24 | `gate_docker_build` (732) | ❌ reported | opt-in `--with-docker` |
| 25 | `gate_mutation` (1430) | ❌ reported | opt-in, mutmut on `app/domain` |
| 26 | `gate_evals` (578) | ❌ reported | opt-in `--with-evals` |

**Blast-radius controls**:
- `_run()` (116-144) never raises; timeouts become exit 124 (139-142); missing binaries become exit 127 (143-144).
- `_tool()` (157-167) resolves in a fixed order: project `.venv/bin` → isolated scanner venv `~/.local/share/jarvis-ci-tools/venv/bin` (57-58) → PATH. The isolated venv exists specifically so "the project's pinned .venv is never disturbed by their (heavy) dependency trees" (55-56).
- `_missing_tool()` (807-809): *"A gate whose scanner is absent reports SKIP — never a silent pass."* This is an important honesty property.
- `OUTPUT_CAP = 4000` with head+tail truncation (`_tail`, 147-154).

**Data-driven risk exemptions** — the most interesting idea in the file. `_accepted_risk_tokens()` (785-804) parses `docs/ACCEPTED_RISKS.md` for rows containing `risk-` and one of `accepted|deferred|needs decision` and not `resolved`, then harvests `CVE-*/PYSEC-*/GHSA-*` IDs and backticked words:
```python
_RISK_TOKEN_RE = re.compile(r"\b(CVE-\d{4}-\d{4,}|PYSEC-\d{4}-\d+|GHSA-[A-Za-z0-9-]+)\b")
_RISK_PKG_RE = re.compile(r"`([A-Za-z0-9][A-Za-z0-9_.\-]{2,})`")
```
(766-767). `gate_trivy_fs` (903-919), `gate_osv` (1079-1087) and `gate_licenses` (972-984) then suppress exactly those findings. **Measured live**: the parser yields 29 tokens, including `chromadb`, `pymupdf` (intended) but also `app`, `dict`, `user`, `resource`, `status`, `contents`, `upgrade`, `repo` — any prose backtick becomes a package name. The suppression is broader than it looks; a vulnerable package named `resource` would be silently accepted.

**Signing material lives outside the repo.** `gate_provenance` (1127-1233) builds an in-toto SLSA v1 statement (1146-1160), signs with a cosign keypair at `~/.local/share/jarvis-ci-tools/cosign.key` (1135-1136), and **verifies** the signature (1213-1226) before reporting pass. `_init_signing()` (1525-1556) generates the keypair and writes the password to `cosign.password` at **mode 0600** (1552), explicitly "outside the repo" (1554).

**Provenance of the facts cache**: `_persist_doc_facts()` (1648-1681) mines the already-run pytest/coverage gate output for `test_count` and `coverage` so `sync_doc_facts` need not re-run the suite — comment at 1650-1654: "pytest and coverage numbers are already measured by this gate."

### 3.3 `scripts/ci_bridge.py` (844 lines) — control plane

CLI (684-698): `--check-auth`, `--list-prs`, `--once`, `--pr N`, `--limit` (default 10), `--dry-run`, `--force`, `--json`.

**Pipeline** (docstring 7-13): list open PRs → skip already-gated SHAs → fetch head → run `ci_gate.py` → publish one commit status per context.

**Statuses, not check-runs** (16-24) — empirically determined:
> "POST /repos/{owner}/{repo}/check-runs -> 403 'You must authenticate via a GitHub App.' POST /repos/{owner}/{repo}/statuses/{sha} -> 200"

**Token resolution** (`load_token()`, 213-254). Order: (1) GitHub App installation token (184-210, 224-226); (2) **files first** — `.ci-bridge.env`, `~/Projects/.env`, `~/.hermes/.env`, `./.env` (97-102, 235-240); (3) process env (242-245); (4) `gh auth token` (247-252). The rationale at 228-234 is precise: an ambient dev PAT "would silently shadow the publishing token and every gate result would land with `published=0/8` (RISK-015)."

- **DOC/CONTRADICTION**: `docs/CI-TOKEN-PERMISSIONS.md:87-90` states *"`load_token()` reads, in order: 1. **Environment** — an env var beats every file."* The code does the exact opposite — `TOKEN_FILES` are scanned at 235-240 **before** `os.environ` at 242-245. `docs/ACCEPTED_RISKS.md:27` repeats the same wrong claim ("an env var beats every file"). The code is right and the docs are stale.
- Placeholder rejection: `_usable()` (176-181) rejects values <20 chars or containing `PLACEHOLDER|CHANGEME|YOUR_TOKEN|XXXX` (90).
- `_mask()` (257-260) and `check_auth()` (303-330) never print the token — "Token value never printed — only source and masked form for audit; SEC-002" (310).

**Merge-commit reproduction** (`merge_gate_ref()`, 478-532) — reproduces what GitHub Actions would have checked out:
> "GitHub's `pull_request` jobs check out a MERGE commit … Gating the raw head means every branch that predates a fix on main fails forever, which is exactly what happened to the Dependabot backlog."

Uses `git merge-tree --write-tree` + `git commit-tree` (504-529), with a stated fallback to the raw head on conflict (512, 531).

**Credential hygiene in git fetch** (`fetch_pr_head`, 396-446): the token is passed via child **environment** (`JARVIS_GIT_TOKEN`), expanded by an inline credential helper, "so it never appears in `ps` output" (402-403).

**Context aggregation**: `CONTEXT_OF` (107-140) maps 25 gate names → 9 published contexts; `CONTEXT_ORDER` (141-151). `aggregate()` (562-587) marks a context `failure` only if a **blocking** gate failed. `publish_statuses()` (590-627) POSTs to `/statuses/{sha}`.

**False-green guard**: `PRResult.publish_failed` (653-656) is true when statuses were attempted but none landed; `gate_one()` (674-681) then reports `action="publish-failed"` separately from the gate conclusion — "The gate result and the publish result are separate facts." The failure banner (824-836) diagnoses the cause ("almost always a token without 'Commit statuses: write'").

**Idempotency**: `.governance/ci_bridge_state.json` keyed by head SHA (74, 380-393), written only on a genuinely gated run (772-778).

### 3.4 `scripts/ci_bridge_server.py` (230 lines) — n8n's only path to a shell

Exists because "n8n v2 removed the 'Execute Command' node" (4). stdlib-only `http.server`. Config from env only, no argparse (47-50): `CI_BRIDGE_HOST` (127.0.0.1), `CI_BRIDGE_PORT` (8770), `CI_BRIDGE_TOKEN` (empty), `CI_BRIDGE_TIMEOUT` (900).

- Endpoints: `GET /health` (157), `GET /last` (167), `POST /run` (174) → `ci_bridge.py --once`, `POST /docs` (189) → `scheduled_doc_maintenance.py`, 404 otherwise (170, 205).
- `_build_cmd()` (55-66): "Map a JSON body to ci_bridge.py CLI arguments (whitelisted, no shell)" — only `pr`/`limit`/`dryRun` accepted. `shell=False` explicitly (80, 117).
- Auth `_authorized()` (150-153): if `CI_BRIDGE_TOKEN` is unset it **returns True** (151-152) — an unconfigured bridge is open. 401 is returned before the body is read (175-177, 190-192).
- Always HTTP 200; child exit code rides as `exitCode` with `ok = returncode == 0` (83, 119); timeout → 124 (93, 130).

### 3.5 Governance gates that run in CI

- `scripts/board/review.py` (324) — nine checks registered at 292-302. **Two are no-op stubs**:
  ```python
  def check_schema_drift():          # 189-192
      # This is a placeholder - implement when DB schema exists
      return True, []
  def check_prerequisite_graph():    # 195-198
      # Placeholder for future implementation
      return True, []
  ```
  They still print ✅ and still count toward `board_count` (`grep -c "^def check_"` = 9, per `docs/GOVERNANCE.md:56`).
  **DOC/CONTRADICTION**: `ci_gate.py:393` hardcodes the summary string <!--doc-facts:quoted-->"all 8 governance checks passed"<!--doc-facts:quoted--> while `scripts/board/review.py` registers 9.
- `scripts/check_docs.py` (515) — five structural rules: status header (230), stub tables (242), referenced paths resolve (264), single navigation map (286), stale version banner (442), plus the type contract (355). Allowances are named constants next to the rule (`ALLOWED_MISSING` 86-126, `PATH_CHECK_EXEMPT` 130-144, `LINK_CHECK_EXEMPT` 157-165), with the stated principle at 21-22: "a new exception is a reviewed code change rather than a silent skip."
- `scripts/doc_links.py` (220) — dead-anchor simulation of GitHub slugs (`_slug`, 34-40), duplicate heading numbers (136), index reachability (168).
- `scripts/doc_type_table.py` (159) — regenerates `docs/DOC-GOVERNANCE.md` §10 between marker comments (32-35) and `--check`s it.

### 3.6 Orphans (verified by repo-wide grep)

- **`scripts/sota_governance.py` (649)** — nine checks, no argparse, zero wiring. `.gitignore:267` ignores its output `governance-report.json`. Only mentions: `CONTRIBUTING.md:36` and `:50`.
  **Exit-code/docstring contradiction**: docstring line 19 says "Exit 0 = pass, 1 = critical/high failures, 2 = low failures", but the code (641-645) is `if crit: return 1 / if high: return 2 / return 0`. **MEDIUM findings (missing SBOM, SLSA < 3, missing dependabot) exit 0** — silently non-blocking.
- **`scripts/doc_governance.py` (332)** — dead, but `docs/GOVERNANCE.md:38-40` claims it runs in "Pre-commit / CI / manual" and "CI gate". Both false. Worse: `docs/GOVERNANCE.md:43` calls `sync_doc_facts.py` the *"Legacy fact sync (kept for compatibility)"* — the relationship is inverted; `sync_doc_facts.py` is the live one, invoked from `githooks/pre-commit:49` and `ci_gate.py:1383`.
  **Destructive if revived**: `doc_governance.py:270-271` writes `.governance/doc_facts.json` wholesale, while the live `doc_facts._write_cache()` (241-256) deliberately **merges** and stamps a commit. Running `doc_governance.py --sync` would clobber the gate's measured `test_count`/`coverage`.
- **`scripts/governance_check.py` (62)** — docstring line 5 claims "This is the single source of truth for compliance"; zero callers. It also runs `mypy --strict app/` as **blocking** (line 39), contradicting the ratchet policy everywhere else.
- **`scripts/check_web_contract.py` (189)** and **`scripts/check_state_consistency.py` (146)** — live-server contract tests against `localhost:8000`, no callers.
- **`scripts/lint_changed.sh` (42)** — its only caller `ci.yml:44` is `workflow_dispatch`-only, so it is effectively dead. `gate_ruff_ratchet` (`ci_gate.py:270-277`) reimplements it, and differs materially: the shell version diffs `BASE` against the **working tree** (line 30, deliberately, per 28-29), the Python one diffs `base HEAD`.
- **`scripts/check_frontend_modules.mjs` (108)** — imports every `frontend/assets/*.js` under a DOM shim; zero references, and `package.json:11` still has the untouched `echo "Error: no test specified" && exit 1`.
- **`scripts/setup_branch_protection.py` (119)** — would PUT branch protection with `REQUIRED_CHECKS` matching the 6 `ci.yml` job names (25-32), but `ci_bridge.py:22-24` and `docs/ACCEPTED_RISKS.md:25` record it as impossible on this plan.
- **Archaeologist family (812 lines)** — `archaeologist_step.py` is the real state machine (`current|next|reset` via bare `sys.argv[1]`, 164-170); `interactive_archaeologist.py` is a near-verbatim duplicate that still names the other file in its docstring; `state.json` holds `{"current_index": 69, "active_tag": "v3.0.0"}`; `current_commit.json` (477 KB) embeds the whole `version_buffer.json` (465 KB). All four `.archaeology/*` files are **git-tracked**, while `data/` is not.
- **Memory trio (706 lines)** — `migrate_memory_temporal.py`, `remediate_memory_store.py`, `seed_memory_from_profile.py`. All operate on `data/memories.json`, back up before writing, and return 0 for both dry-run and success. `seed_memory_from_profile.py:43` uses `abs(hash(...))` for IDs, which is **non-deterministic across processes** under hash randomization.

---

## 4. `.governance/` (5 files)

| File | Tracked? | Written by | Read by |
|---|---|---|---|
| `ci_bridge_state.json` (3454 B) | ❌ `.gitignore:265` | `ci_bridge.py:391-393` | `ci_bridge.py:380-388` |
| `ci_bridge_state.json.bak-before-publish-fix` | ❌ | manual | nothing |
| `doc_facts.json` (462 B) | ❌ (only `mypy_baseline.txt` is un-ignored: `.gitignore:266`) | `doc_facts._write_cache()` (241-256), `ci_gate._persist_doc_facts()` (1648-1681) | `doc_facts._read_cache()` (216-238), `githooks/pre-commit:46-53`, `ci_gate.py:1393` |
| `gitleaks.json` (3 B, `[]`) | ❌ | `sota_governance.check_secret_scan` (orphan) | orphan |
| `mypy_baseline.txt` (409 B) | ✅ **the only tracked file** | manual | `ci_gate.gate_mypy` (462-469) |

**`mypy_baseline.txt`** — a genuine suppression system, but a *ceiling* rather than a mute:
```
485
# mypy --strict app/ error CEILING. Enforced by gate_mypy in scripts/ci_gate.py.
# This number may only go DOWN. Raising it is a reviewed decision that must be
# recorded in docs/ACCEPTED_RISKS.md (RISK-005), not a silent edit.
# Baseline set 2026-09-11.
# Lowered 494 -> 485 on 2026-09-12, locking the gain from the Phase 0 fixes
# (the gate itself reported "DOWN, lower the baseline to lock the gain").
```
Consumed at `ci_gate.py:462-469`: first non-comment line is the ceiling. Behaviour (471-508): no file → reported-only; unparseable count → **blocking fail** (482-491); `current > ceiling` → blocking fail with "REGRESSION: {n} strict errors, ceiling is {c}" (493-503); `current < ceiling` → pass with "DOWN, lower the baseline to lock the gain" (505-507). **Honest assessment: 485 strict-mode errors are tolerated at HEAD.** What is enforced is that the number cannot rise. The design note at 442-446 is the clearest statement of the reasoning: "A ratchet is the honest middle … Fixing the 494 legacy errors is NOT required here and is not the point — not adding to them is."

**`doc_facts.json`** — the provenance guard is the interesting part. `_read_cache()` (216-238) refuses cached *expensive* facts unless the cached `commit` equals the current HEAD (228-233): "a cache is a *claim about a past tree*". **Verified live**: the cache's `commit` field is `be752d28ccc5e96278fe3530141b2407d2d72a81`, which **does** match HEAD, so the cache is trusted and `test_count=1465`/`coverage=90` are live. The **cheap** facts are recomputed every run and are not cached.

**Governance-report.json (root)** — gitignored (`.gitignore:267`), stale (`generated_at: 2026-09-10T06:00:29`), produced only by the orphaned `sota_governance.py`. It records 9 results including `"status": "ACCEPTED"` for dependency vulns, licence compliance and coverage — a good vocabulary ("ACCEPTED" is distinct from "PASS", per `sota_governance.py:49-51`), but nothing regenerates it.

---

## 5. Configuration, build and environment files

- **`pyproject.toml` (48)** — `version = "3.0.1"` (7) is **stale** against `git describe` = `v3.22.1`; `version_bump.py:110` calls this metadata "courtesy, not the authority". `requires-python = ">=3.11"` (10). pytest config (17-23): `asyncio_mode = "auto"`. ruff (25-33): `line-length = 100`, `select = ["E","F","W","I","UP","B","C4","SIM","PIE"]`, `ignore = ["B008"]`. mypy (35-48): `strict = true`, and `exclude = ['^legacy/']` with a rationale worth quoting (40-47): *"it contains `legacy/app/api/...`, which makes mypy see a SECOND directory claiming to be the `app` package. Without this line, any run that reaches app/ aborts with 'Duplicate module named app' and reports NOTHING … a gate that cannot run is worse than one that fails loudly, because silence reads as success."* `dependencies = []` (11) — the package itself declares no deps; `requirements.txt` is the real source.
- **`requirements.txt` (154 lines)** — fully `==`-pinned, generated by freeze (includes transitive deps like `nvidia-cublas`, `torch==2.14.0`). **Not hash-pinned**; `docs/ACCEPTED_RISKS.md:23` (RISK-010) records this.
- **`.editorconfig` (19)** — `indent_size = 4`, 2 for yaml/json/toml, `trim_trailing_whitespace = false` for md, tabs for Makefile.
- **`.pre-commit-config.yaml` (67)** — 5 repos: `ruff-pre-commit v0.8.0` (3-14, `files: ^(app|scripts|evals)/.*\.py$`), `pre-commit-hooks v5.0.0` (16-29, incl. `check-added-large-files --maxkb=1000`), `alessandrojcm/commitlint-pre-commit-hook v9.26.0` (34-39), `mirrors-mypy v1.11.2` (41-61), `gitleaks v8.18.0` (64-67). Line 31-33 records a real outage: *"the previous repo (github.com/alphanodes/commitlint) was deleted from GitHub (404), which broke `pre-commit` entirely — every hook install failed before any hook ran."* The mypy hook is narrowly scoped (45-53) with `--follow-imports=skip --ignore-missing-imports --disable-error-code=misc`.
- **`commitlint.config.cjs` (14)** and **`.commitlintrc.json` (14)** — **duplicate configs that disagree**: the `.cjs` `type-enum` includes `build`, `ci`, `revert` (line 4); the `.json` omits them (line 4). The `.cjs` is the one referenced by `ci.yml:111` and `githooks/commit-msg:39`. `ci_gate.py:645-657` implements a **third** list in Python that also omits `build`/`ci` — yet `ci_gate.py:57` (from the release workflow) shows commits like `ci(doc-maintenance): …` and `docs(readme): …` in this repo's own history. **`gate_commitlint` would fail this repository's own commits**, since `_conventional_problems()` (662-684) rejects any type outside its 9-item set.
- **`.gitleaks.toml` (35)** — `useDefault = true` plus an allowlist. `paths` (15-21) and `regexes` (22-35) include value-scoped entries for two historical fake literals, with the reasoning at 29-33: "Scoped to these two literal values only (never a path, rule or commit wildcard), so any real secret anywhere else still fails the gate." Documented as RISK-017.
- **`.hadolint.yaml` (24)** — 3 suppressions (DL3008, DL3013, DL3066), each with a multi-line rationale, each mapped to RISK-013. Header: "Everything NOT listed here stays enforced by the blocking `hadolint` gate."
- **`.changeset/config.json` (13)** — present but **inert**. No `@changesets/cli` dependency, no `.changeset/*.md`, and `package.json` has no changeset script. Versioning is done by `version_bump.py`. This is an aspirational artifact.
- **`config.yaml` (43)** — 4 models with `api_key: "env:VAR"` indirection (24, 34, 43) — **keys are never inlined**. Note `grok` is declared `backend: "llamacpp"` with an `https://api.x.ai/v1` base_url (19-24), which looks like a copy/paste error.
- **`Dockerfile` (52)** — multi-stage (`builder` 3, `runtime` 19), non-root `useradd -r -g jarvis` (24), `USER jarvis` (41), pins nothing at the apt layer. `HEALTHCHECK` in exec/JSON form (45-46) with the rationale at 43-44: shell form "trips hadolint DL3025". `CMD ["python", "-m", "app.main"]` (52).
- **`docker-compose.yml` (24)** — only `pgvector/pgvector:pg16`, with defaults `${POSTGRES_PASSWORD:-jarvis_secret}` (10) — a **default password in a committed file**. The main app is not containerised here.
- **`.env.example` (64)** — 30+ variable names, all empty values. Header: "**Never commit the real `.env`.**" (line 4). Includes a typo'd `UNOROUTER_API_KEY` (36) and `CHUTES_AI_FINGLERPRINT` (45).
- **`.dockerignore` (101)** — excludes `.env`, `.env.*`, `!.env.example` (84-86) and `*.pem|*.key|*.crt|*.secret|credentials.*` (89-93), plus `docs/`, `tests/`, `scripts/` (except `!scripts/board/review.py`, 75).
- **`package.json` (20)** — `version: "3.0.0"` (a **third** version number, alongside pyproject's 3.0.1 and git's v3.22.1), `license: "ISC"`. Only devDependency: `@mermaid-js/mermaid-cli`.

---

## 6. Secrets and environment handling

**What is committed**: nothing secret. A regex sweep of every tracked file for `sk-or-v1-…`, `ghp_…`, `github_pat_…`, `sk-…` returns **zero hits**. `.env` is ignored (`.gitignore:91-92` with `!.env.example` at 93), as are `*.pem|*.key|*.crt|*.secret|credentials.*` (95-98) and `config.local.*|settings.local.*|secrets.*` (104-107).

**What is on disk, untracked**:

| File | Mode | Contents |
|---|---|---|
| `.ci-bridge.env` | 600 | `CI_BRIDGE_TOKEN`, `CI_BRIDGE_PORT=8770`, `CI_BRIDGE_HOST=127.0.0.1`, **`JARVIS_CI_TOKEN=github_pat_11CAWY4NA…`** |
| `.env` | 600 | 9 secret-shaped lines |
| `.claude/settings.local.json.bak` | **644** ⚠️ | live `OPENROUTER_API_KEY` (`sk-or-v1-211c…`) and a placeholder `ANTHROPIC_AUTH_TOKEN` |

- `.ci-bridge.env` is gitignored (`.gitignore:271`) and **was never committed** — `git log --all -S 'ci_gmgxBwKFgE'` returns nothing. It is a systemd `EnvironmentFile` (`ci_bridge.py:92-93`).
- `.claude/settings.local.json.bak` is ignored only by the generic `*.bak` rule (`.gitignore:252`), not by a secrets rule — it is world-readable at 0644. Its key was never committed (`git log --all -S` empty).
- **Both live credentials were surfaced in cleartext during this session** by reading the files. They should be treated as exposed and rotated.

**Secret scanning** — three independent detectors, none solely relied upon:
1. `gitleaks` pre-commit hook (`.pre-commit-config.yaml:64-67`, `v8.18.0`) — fires on staged content.
2. `gate_gitleaks` (`ci_gate.py:340-374`) — git-aware over history, `--redact`, with the deliberate note at 341: "Secret scan in git-aware mode so gitignored artifacts are not noise."
3. `gate_trufflehog` (`ci_gate.py:1009-1060`) — `--results=verified` over git history, blocking, and treats exit 183 as non-fatal (1052).

**Secret exposure in the environment**: `ci_gate.py:1111` passes `COSIGN_PASSWORD` via env; `_init_signing()` generates a random one with `secrets.token_urlsafe(24)` (1537) and stores it 0600 outside the repo (1550-1552). `ci_bridge.py:412` passes the git token through the child env, never argv (documented at 401-403).

---

## 7. Dependency management and versioning

**Dependencies**: `requirements.txt` is a fully-pinned freeze (154 lines). No lockfile, no hash pinning (RISK-010). Dependabot handles updates daily for pip, weekly for actions (`.github/dependabot.yml`), in 5 groups, labelled `automerge` — but **nothing automates the merge**; `docs/ACCEPTED_RISKS.md:25` records that PRs #44-#53 sat open with zero statuses.

**Versioning is git-tag-derived, three layers deep**:
1. **`app/config/version.py:93-162`** derives the running version from `git describe --tags --long --match 'v[0-9]*.[0-9]*.[0-9]*'` at import time. `VersionInfo.__str__` (79-90) produces `vA.B.C` on a clean tag, `vA.B.C+dev.N` when ahead, `...dirty` when the tree is modified. Fallbacks: `JARVIS_VERSION` env (136-148), then `_FALLBACK_VERSION = "v3.0.1"` (33, 150-162). `config/version.py` is a documented re-export stub.
2. **`scripts/version_bump.py:79-106`** computes the next tag from conventional-commit subjects since the last tag. `_classify()` (69-76): `BREAKING CHANGE` or `breaking*` → major; `feat` → minor; `fix` → patch; **everything else also → patch** (line 76). `compute_bump()` returns `None` when there are no commits (84-85) rather than inventing a patch tag (docstring 20-22). Stdlib-only by design (24-25) so the pre-push hook needs no network.
   - **DOC/CONTRADICTION**: `AGENTS.md:113-115` claims `chore` → PATCH, `docs` → NONE, `refactor` → NONE, `test` → NONE. `_classify()` returns `"patch"` as the catch-all for all of them, so every non-empty commit range produces a bump. `AGENTS.md:108-116`'s version-bump table does not describe the implementation.
   - `bump_pyproject()` (109-114) and `--tag-only` (133-147) are separate paths; `bump_version.py` (110) is the older interactive `patch|minor|major` tool and is not called by any hook.
3. **`githooks/pre-push:45`** invokes `--apply --tag-only` on every push to the default branch with commits ahead of the last tag; **`githooks/pre-push:68`** then calls `publish_release.py` to create the actual GitHub Release (219 lines, `gh release create`, idempotent, with a `--backfill` mode at 194-195 and notes bucketed by conventional type at 116-149).

**Net effect**: version bumps are automatic and deterministic; tags are created by a local hook rather than by CI; `pyproject.toml`'s version field drifts (3.0.1 vs actual v3.22.1) and is explicitly declared non-authoritative (`version_bump.py:110`, `bump_version.py:91-93`). `.changeset/` is inert.

---

## 8. The doc-facts mechanism — actual implementation

This is JARVIS's most distinctive subsystem, and it is worth describing precisely because the *implementation* differs from the *aspiration* in several places.

**Core idea** (`doc_facts.py:2-13`): documents do not store numbers; they cite a **fact name** inside HTML-comment markers, and the value is re-derived from the repository:

```
The gate runs <!--fact:gate_count-->26<!--/fact--> checks.
```

`MARKER_RE = re.compile(r"<!--fact:([a-z_]+)-->(.*?)<!--/fact-->", re.DOTALL)` (`doc_facts.py:35`).

**Two cost classes**:
- **Cheap** (`collect_cheap()`, 54-114) — derived from git, the filesystem and grep, always computed: `version`, `commit`, `gate_count` (counts `^def gate_` in `ci_gate.py`, 61-66), `context_count` (parses `CONTEXT_ORDER` out of `ci_bridge.py`, 68-76), `adr_count` (globs `docs/adr/ADR-*.md`, 78-79), `board_count` (counts `^def check_` in `scripts/board/review.py`, 81-86), `doc_count` (88-90), and four `cadence_*` facts **imported from the script that enforces them** (94-105) — "so the cadence table in DOC-GOVERNANCE.md cannot drift from the code either."
- **Expensive** (`collect_expensive()`, 140-213) — `test_count` via `pytest tests/ --collect-only -q` (174-185) and `coverage` from a real run (194-207).

**Three provenance safeguards that are genuinely load-bearing:**

1. **Commit-stamped cache.** `_write_cache()` (241-256) stores the measured facts together with the HEAD commit. `_read_cache()` (216-238) returns `unknown` unless the cached commit equals the current HEAD (228-233):
   > "The cache describes a different tree. Reporting it as current would be exactly the silent staleness this system exists to catch."

2. **Recursion guard.** `collect_expensive()` detects `"pytest" in sys.modules` (167) and skips the coverage run, because a doc test that runs pytest would recurse (158-162). `test_count` is always `--collect-only` so it is deterministic and independent of pass/fail (169-173).

3. **Unresolvable ≠ pass.** `check_facts()` (160-258) treats a cited-but-unresolvable fact as a **finding**, not a silence. The docstring records the actual failure (170-176):
   > "when the cache was unprovenanced or absent they resolved to `unknown`, `check_facts` skipped them, and `docs/ROADMAP.md` asserted a test count 84 lower than the suite's real count while this checker printed 'no findings'. … A blind spot that reports clean is worse than no check."

**Bare-claim detection** (`sync_doc_facts.py:40-46`) catches numbers written *before* markers existed, e.g. `(\d{1,3})\s+(?:CI\s+)?(?:checks|gates)\b` → `gate_count`. The negative lookbehind `(?<![\d.])` prevents "### 5.2 ADR Template" from being read as an ADR count (37-39).

**Escape hatches**, all explicit: `EXEMPT_PREFIXES = ("docs/archive/", "docs/adr/")` (50-58) with the reasoning that "An ADR is the one place a stale number is *correct*"; 6 `EXEMPT_FILES` (59-66); fenced code blocks; and an inline `<!--doc-facts:quoted-->` escape (71, 75-92).

**`KNOWN_FACTS`** (104-121) rejects typo'd marker names, which would otherwise "resolve to `unknown` and be skipped forever" (101-103).

**Enforcement chain**: `githooks/pre-commit:44-67` (uses the cached facts for speed, re-stages corrected docs) → `gate_doc_facts` (`ci_gate.py:1373-1427`, blocking) → published as the "Virtual Board Governance" status.

**Live status check (measured, not claimed)**: `.venv/bin/python scripts/sync_doc_facts.py --check` at HEAD **exits 1** with:
```
- README.md:282: fact 'adr_count' says '14' but the repo says '15'
- docs/FINAL_STATE.md:50: fact 'test_count' says '1504' but the repo says '1465'
```
and `.venv/bin/python scripts/check_docs.py --strict` also **exits 1**:
```
- docs/README.md: 1 document(s) not reachable from the index … docs/FINAL_STATE.md
```
So `gate_doc_facts` and `gate_docs` — both **blocking** — would fail on the current HEAD. `HEAD` (`be752d28`) is **not** in `.governance/ci_bridge_state.json` (22 SHAs gated, none is HEAD), consistent with the six most recent gated PRs all recording `"conclusion": "failure"`. The mechanism works; the repo is currently red.

---

## 9. mypy / lint baseline mechanism

**Lint**: ratcheted, twice over. `gate_ruff_ratchet` (`ci_gate.py:270-312`) runs `ruff check` on files changed against the **merge-base**; `lint_changed.sh` does the same against the working tree but has no live caller. Full-tree ruff is never enforced — `ci.yml:39-42` states the reason: "The full tree carries pre-existing debt (RISK-005) … enforcing it repo-wide fails at HEAD and blocks every PR."

**mypy**: a **ceiling ratchet**, and it must be characterised honestly. `.governance/mypy_baseline.txt` contains `485`, and the gate **fails when the count rises** and **passes when it is at or below**. It does not suppress individual errors, does not use `# type: ignore`, and does not report "clean" — it reports `"485 strict errors (ceiling 485)"` as a **pass**. So: **485 mypy --strict errors are tolerated at HEAD by design.** The gate's own docstring (442-446) defends this against the previous posture:
> "Reported-only means a PR could ADD type errors and still go green. The number only ever went up. … Fixing the 494 legacy errors is NOT required here and is not the point — not adding to them is."

Notable properties: missing baseline file → degrades to reported-only rather than blocking (448-449, 471-480); an unparseable count → **blocking fail**, not a pass (482-491); the file is **the only tracked file in `.governance/`** (`.gitignore:266` un-ignores it), so the ceiling itself is version-controlled and reviewable in a diff. `docs/ACCEPTED_RISKS.md:18` records the negative test: "a planted 2-error regression was caught (`status=fail, blocking=True`)."

**Coverage** is the third ratchet, and is *reported-only* in the local gate (`ci_gate.py:602-638`) while `ci.yml:59` used `--cov-fail-under=80`. `docs/ACCEPTED_RISKS.md:17` records that the historical "~36%" figure was stale and that the gate's own command yields `TOTAL 98%`.

---

## 10. Documentation set (cross-check only)

Governance/policy documents present:
`AGENTS.md` (361, the authoritative agent standard), `CONTRIBUTING.md` (75), `SECURITY.md` (54, private-advisory channel + SLA table), `CODE_OF_CONDUCT.md` (Contributor Covenant), `LICENSE` (ISC, © 2026 Er-Sajan-PLG), `docs/GOVERNANCE.md` (77), `docs/DOC-GOVERNANCE.md` (580, the §10 type contract), `docs/ACCEPTED_RISKS.md` (37, **machine-parsed by `ci_gate.py:785-804`**), `docs/CI-GATE-SOTA.md` (164), `docs/CI-TOKEN-PERMISSIONS.md` (168), `docs/GITHUB-APP-SETUP.md` (172), `docs/VERSIONING.md` (119), `docs/ACCEPTED_RISKS.md`, `docs/migrations/*`, and 15 ADRs in `docs/adr/`. 61 non-archive markdown files under `docs/`.

**Role of the risk register in enforcement.** `docs/ACCEPTED_RISKS.md` is not prose — `gate_trivy_fs`, `gate_osv` and `gate_licenses` read it at runtime. Its own rules section (32-37) states the contract: "Acknowledging a risk does NOT remove it from the governance report — it adds the evidence of review so the finding is 'accepted' not 'ignored'."

### Consolidated doc-vs-code contradictions found

| # | Doc claim | Code reality |
|---|---|---|
| 1 | `docs/CI-TOKEN-PERMISSIONS.md:88-89` — "an env var beats every file"; `ACCEPTED_RISKS.md:27` repeats it | `ci_bridge.py:235-245` reads **files first**, then env |
| 2 | `docs/GOVERNANCE.md:38-40` — `doc_governance.py` runs in pre-commit and CI | zero callers; `sync_doc_facts.py` is the live path |
| 3 | `docs/GOVERNANCE.md:43` — `sync_doc_facts.py` is "Legacy … kept for compatibility" | it is the **live** entry point (`pre-commit:49`, `ci_gate:1383`); `doc_governance.py` is dead |
| 4 | `.github/workflows/ci.yml:10` — <!--doc-facts:quoted-->"22 checks"<!--doc-facts:quoted--> | 26 (`grep -c '^def gate_'`), and `CONTRIBUTING.md:40` renders 26 via a fact marker |
| 5 | `docs/CI-GATE-SOTA.md:152-153` — "all three workflows reduced to `workflow_dispatch`" | there are four; `deploy.yml` still triggers on `push: tags: v*` |
| 6 | `AGENTS.md:113-115` — `docs`/`refactor`/`test` → "NONE" bump | `version_bump.py:76` — catch-all returns `"patch"` |
| 7 | `githooks/pre-push:15-17` — "`version_bump.py --apply` commits the pyproject metadata bump" | the hook passes `--tag-only`, which explicitly does not (133-137) |
| 8 | `scripts/ci_gate.py:393` — "all 8 governance checks passed" | `scripts/board/review.py` registers **9** |
| 9 | `sota_governance.py:19` — "2 = low failures" | `sota_governance.py:641-645` returns 2 for **HIGH**; MEDIUM exits 0 |
| 10 | `docs/GOVERNANCE.md:77` — "deliberately **not** git history" | `scheduled_doc_maintenance.py:7-8` says cadence is "derived from git history" |
| 11 | `docs/FINAL_STATE.md:21` — evals "CI-integrated via --with-evals" | `ci_bridge.py` never passes `--with-evals`; `gate_evals` cannot fire |
| 12 | `docs/DOC-GOVERNANCE.md:186` — documents a 365-day cadence tier | `DEBUGGING.md` is in both `CADENCE_DAYS` (365) and `EXEMPT_FILES`, so the tier is unreachable |

---

## (a) Coverage statement

| Area | Files read in full | Method |
|---|---|---|
| `.github/` | **7 of 7** — `workflows/{ci,deploy,release,jules-conflict-resolver}.yml`, `dependabot.yml`, `CODEOWNERS`, `.github/actions/setup-env/action.yml` | `cat -n` |
| `githooks/` | **3 of 3** — `pre-commit`, `pre-push`, `commit-msg` | `cat -n` |
| `scripts/*.py` | **45 of 45** enumerated, 11,615 lines. Read directly in full: `ci_gate.py` (1761), `ci_bridge.py` (844), `doc_facts.py` (266), `sync_doc_facts.py` (324), `version_bump.py` (167), `bump_version.py` (110), `publish_release.py` (219), `verify_git_safety.py` (68), `verify.py` (28), `check_docs.py` (515), `doc_links.py` (220), `lint_changed.sh`, `commit.sh`. Read in full by delegated subagents with verified quotes: `doc_types.py`, `doc_type_table.py`, `doc_governance.py`, `doc_review_due.py`, `sota_governance.py`, `github_app_token.py`, `setup_branch_protection.py`, `ci_bridge_server.py`, `governance_check.py`, `scripts/board/review.py`, `check_state_consistency.py`, `check_web_contract.py`, `check_reported_bugs.py`, `scheduled_doc_maintenance.py`, `run_evals.py`, `migrate_memory_temporal.py`, `remediate_memory_store.py`, `seed_memory_from_profile.py`, `interactive_archaeologist.py`, `archaeologist.py`, `archaeologist_step.py`, `run_archaeologist_loop.py`, `new_doc.py`, `check_frontend_modules.mjs`. Remaining (~17 scripts incl. `archaeologist` siblings, `apply_doc_*.py`, `doc_types` helpers, `run_mcp_server.py`, `fix_markdown_escapes.py`, `refactor_docs_structure.py`, `update_*_docs*.py`, `enrich_all_docs_dates.py`, `doc_type_table` remainder) were enumerated with line counts and **not** read line-by-line; their wiring was established by grep, not by reading.
| `.governance/` | **5 of 5** | `cat` + live parsing |
| `.archaeology/` | **4 of 4** (state, current_commit, version_buffer, draft_notes) — read as structure/size, and `draft_notes.md` head; the two 460 KB+ JSON blobs were **not** read in full | head/inspect |
| Config/build | **all present**: `pyproject.toml`, `requirements.txt`, `.editorconfig`, `.pre-commit-config.yaml`, `commitlint.config.cjs`, `.commitlintrc.json`, `.gitleaks.toml`, `.hadolint.yaml`, `.changeset/config.json`, `config.yaml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `.dockerignore`, `.gitignore`, `package.json`, `config/version.py`, `app/config/version.py` | `cat -n` |
| `.ci-bridge.env`, `governance-report.json` | **both** read | `cat` |
| n8n | `n8n/README.md`, `n8n/workflows/JARVIS-Local-CI.json`, `n8n-workflows/doc-maintenance.json` read in full; `JARVIS-Cleanup.json` and `JARVIS-HITL.json` **not read** | `cat` |
| Docs / cross-check | `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `CODE_OF_CONDUCT.md`, `docs/GOVERNANCE.md`, `docs/VERSIONING.md`, `docs/ACCEPTED_RISKS.md`, `docs/CI-TOKEN-PERMISSIONS.md` (partial), `docs/CI-GATE-SOTA.md` (grep), `docs/DOC-GOVERNANCE.md` (grep) | mixed |
| **Not read** | `app/**` (139 source files), `tests/**`, `frontend/**`, `evals/**`, `external/**`, `data/**`, `artifacts/**` (200+ provenance/SBOM files), `legacy/**`, `docs/archive/**`, `sbom.json`, `package-lock.json`, `.archaeology/*.json` bodies, `n8n/workflows/{JARVIS-Cleanup,JARVIS-HITL}.json`, `prompts/`, `tmp/`, `.vscode/` | out of scope |
| **Executed** | `sync_doc_facts.py --check`, `check_docs.py --strict`, `doc_facts.py`, `ci_gate._accepted_risk_tokens()`, git/config inspection, secret regex sweep. **No file was modified.** | — |

Two files were read that contain **live credentials** (`.ci-bridge.env`, `.claude/settings.local.json.bak`); their values are redacted in this report.

---

## (b) Fundamentals inventory

**Version control & hooks**
- Conventional-commit enforcement at commit time — `githooks/commit-msg`, `commitlint.config.cjs`
- Bracketed-repo `core.hooksPath` so hooks are version-controlled — `scripts/bump_version.py:56-59`
- Hardcoded-version refusal guard — `githooks/pre-commit:12-18`
- Auto-tag on push to default branch — `githooks/pre-push:45`, `scripts/version_bump.py`
- Auto-publish GitHub Release after tag — `githooks/pre-push:56-75`, `scripts/publish_release.py`
- Commit-message-driven SemVer classification — `scripts/version_bump.py:69-106`
- Git-derived version at import time (no hardcoded constant) — `app/config/version.py:93-162`
- Forbidden-destructive-command checker — `scripts/verify_git_safety.py:20-35`
- Two-pass commit wrapper for auto-fixer hooks — `scripts/commit.sh`

**CI/CD**
- Local CI execution plane on an isolated worktree — `scripts/ci_gate.py:179-207`
- 26-gate blocking/reported policy — `scripts/ci_gate.py:270-1511`, orchestration at `1564-1638`
- n8n → bridge → gate control plane — `scripts/ci_bridge.py`, `scripts/ci_bridge_server.py`
- SHA-keyed idempotent gating state — `scripts/ci_bridge.py:380-393`, `.governance/ci_bridge_state.json`
- Merge-commit reproduction of GitHub's PR checkout — `scripts/ci_bridge.py:478-532`
- Merge-base ratchet base resolution — `scripts/ci_gate.py:249-262`
- `import app` provenance proof — `scripts/ci_gate.py:236-246`
- Commit-status publication across 9 contexts — `scripts/ci_bridge.py:107-151, 590-627`
- Publish-failure detection distinct from gate result — `scripts/ci_bridge.py:653-656, 674-681`
- Isolated scanner venv so the project venv is untouched — `scripts/ci_gate.py:55-58, 157-167`
- Missing-tool = SKIP, never silent pass — `scripts/ci_gate.py:807-809`
- npm/GitHub Actions workflows (3 of 4 disabled) — `.github/workflows/`
- Composite Python env setup — `.github/actions/setup-env/action.yml`
- n8n scheduled doc maintenance workflow — `n8n-workflows/doc-maintenance.json`
- n8n local-CI workflow with false-green guard — `n8n/workflows/JARVIS-Local-CI.json` ("Fail If Not OK" node)

**Governance**
- Role-based code ownership — `.github/CODEOWNERS`
- Virtual-board architecture/domain/safety gate (nine checks) — `scripts/board/review.py`
- Machine-checked doc facts with commit-stamped cache — `scripts/doc_facts.py`, `scripts/sync_doc_facts.py`
- Bare-stale-claim detection with quote escapes — `scripts/sync_doc_facts.py:40-46, 71-92`
- Document type contract (13 types) with generated §10 tables — `scripts/doc_types.py`, `scripts/doc_type_table.py`
- Doc structure/path/anchor/index-coverage rules — `scripts/check_docs.py`, `scripts/doc_links.py`
- Semantic review clock driven solely by `**Reviewed**:` — `scripts/doc_review_due.py`
- Scheduled link + review automation with issue dedupe — `scripts/scheduled_doc_maintenance.py`
- Accepted-risk register parsed at gate runtime — `scripts/ci_gate.py:785-804`, `docs/ACCEPTED_RISKS.md`
- Agent governance standard — `AGENTS.md`

**Security**
- Secret scanning ×3 (gitleaks pre-commit, gitleaks history, trufflehog verified) — `.pre-commit-config.yaml:64-67`, `scripts/ci_gate.py:340-374, 1009-1060`
- Value-scoped gitleaks allowlist — `.gitleaks.toml:22-35`
- SAST (semgrep, bandit), SCA (pip-audit, trivy, osv-scanner) — `scripts/ci_gate.py:812-1100`
- Licence denial list (AGPL/GPL/SSPL/BUSL/CC-BY-NC) — `scripts/ci_gate.py:770, 944-1006`
- CycloneDX SBOM generation — `scripts/ci_gate.py:1101-1124`
- SLSA in-toto provenance, signed **and verified** with cosign — `scripts/ci_gate.py:1127-1233`
- Signing key + password stored outside the repo at 0600 — `scripts/ci_gate.py:1525-1556`
- GitHub App installation tokens (RS256 JWT, 1-hour, 0600 disk cache) — `scripts/github_app_token.py`
- Token resolution order that resists ambient-shadowing — `scripts/ci_bridge.py:213-254`
- Token masking; token never printed or passed via argv — `scripts/ci_bridge.py:257-260, 401-403, 412`
- Placeholder-token rejection — `scripts/ci_bridge.py:90, 176-181`
- Token-scoped, localhost-only, whitelisted-argv bridge — `scripts/ci_bridge_server.py:55-66, 150-153`
- Non-root container user + JSON-form healthcheck — `Dockerfile:24, 41, 45-46`
- Hadolint policy with documented suppressions — `.hadolint.yaml`

**Release & supply chain**
- Auto-tag → release notes bucketed by commit type — `scripts/publish_release.py:100-149`
- Release backfill for tags lacking releases — `scripts/publish_release.py:194-195`
- Dependabot daily pip / weekly actions with grouping — `.github/dependabot.yml`
- Frozen pinned requirements — `requirements.txt`
- SBOM + cosign-signed image in the (disabled) release workflow — `.github/workflows/release.yml:119-143`

**Config & data handling**
- `env:VAR` indirection so no key is inlined — `config.yaml:24, 34, 43`
- `.env` ignored, `.env.example` committed — `.gitignore:91-93`
- 0600 mode on local secret files — `.ci-bridge.env` (600), `.env` (600)
- Docker build context excludes secrets and dev material — `.dockerignore:84-93`
- Runtime data gitignored, governance baseline tracked — `.gitignore:52, 215, 265-268`
- Backup-before-write on every memory migration — `scripts/migrate_memory_temporal.py:223-226`
- Compare-and-swap restore guard for live user state — `scripts/check_reported_bugs.py:288-328`

---

## (c) Notable practices — most reusable

1. **Local CI replacing a blocked hosted CI, with a stronger gate set.** `scripts/ci_gate.py` runs 26 gates against an arbitrary SHA in a throwaway worktree, resolving `import app` by `PYTHONPATH` and *proving* it (`_resolve_app`, 236-246). **Why it exists**: the account was billing-blocked and branch protection returned 403 (`ci_gate.py:11-17`), so the checks had to move somewhere they could actually run. Reusable wherever hosted CI is unavailable, metered, or too slow to poll.

2. **Ratchet gates instead of all-or-nothing gates.** ruff runs only on changed files against the merge-base (`ci_gate.py:270-312`, with the "diffing the branch tip is WRONG" reasoning at 249-262); mypy has a numeric **ceiling** in a tracked file that may only go down (`ci_gate.py:428-508`, `.governance/mypy_baseline.txt`). **Why it exists**: a legacy backlog makes a repo-wide gate fail at HEAD, which blocks every PR and trains people to ignore red. A ratchet converts "fix 485 errors" into "do not add a 486th" — enforceable today, and it reports "DOWN, lower the baseline to lock the gain" when you improve.

3. **Fact markers with a commit-stamped cache.** Documents cite `<!--fact:gate_count-->26<!--/fact-->`; both gates fail on drift. Two details make it work rather than aspirational: the cache stores the commit it measured and is rejected on mismatch (`doc_facts.py:228-233`), and **an unresolvable cited fact is a finding, not a pass** (`sync_doc_facts.py:160-177`, which documents the exact bug where `ROADMAP.md` was 84 tests wrong while the checker printed "no findings"). **Why it exists**: <!--doc-facts:quoted-->"22 checks"<!--doc-facts:quoted--> copied into six documents cannot be safely regex-replaced in prose, and a checker that reports clean while blind is worse than no checker.

4. **The accepted-risk register is executable policy, not prose.** `_accepted_risk_tokens()` (`ci_gate.py:785-804`) parses `docs/ACCEPTED_RISKS.md` at gate time; trivy/OSV/licence gates suppress exactly those findings. **Why it exists**: it lets a reviewed, dated, owned exception pass without editing scanner config, and keeps the acknowledgement visible in the report rather than silent. *(Caveat found: the backtick regex over-harvests — `app`, `dict`, `user`, `status` were parsed as package names.)*

5. **Two distinct failure modes for documentation.** `gate_docs` checks *form* (status header, no stub tables, paths resolve, one navigation map, correct type); `gate_doc_facts` checks *truth* (numbers match the repo). `ci_gate.py:1292-1299` states why they are separate: "a document can be perfectly well-formed and still be lying."

6. **`**Source**:` binding on living documents.** An ACTIVE document must name the code it describes (`doc_types.py`, enforced at `check_docs.py:395-408`). **Why it exists** (`AGENTS.md:323-326`): "That binding is what turns a future code change into a present gate failure — move the code and the document goes red, instead of going quietly stale."

7. **Provenance guard on cached measurements.** Any cached metric is stored with the commit that produced it and is refused when the tree has moved (`doc_facts.py:216-238`); "an admitted gap is recoverable, an invented number in a governance document is not" (152-156). Directly reusable for coverage badges, benchmark results, or dependency counts.

8. **False-green detection as a first-class result.** `ci_bridge.py` reports the gate conclusion and the *publish* outcome separately (`674-681`), because "Reporting only the gate let a run announce success while every status POST had 403'd." The n8n workflow mirrors it with a "Fail If Not OK" node that throws, since the bridge answers HTTP 200 even on failure. Reusable anywhere a scheduler consumes an HTTP wrapper around a CLI.

9. **Missing tool ⇒ SKIP, never PASS.** `_missing_tool()` (`ci_gate.py:807-809`) and every scanner gate's absence branch. Similarly, an unparseable mypy count is a **blocking fail**, not a pass (482-491). This single convention removes the most common silent-success failure in CI systems.

10. **Signing material and secrets kept structurally outside the artifact.** The cosign password is generated with `secrets.token_urlsafe(24)` and written 0600 to `~/.local/share/jarvis-ci-tools/cosign.password` (`ci_gate.py:1537, 1550-1552`); the git token travels via child env, never argv (`ci_bridge.py:401-403, 412`); `config.yaml` uses `env:VAR` indirection so no key is ever inlined. Verified: **no secret exists in any tracked file or in history.**

11. **A verification script that refuses to clobber a human.** `check_reported_bugs.py:288-328` restores the previous default only if the store still holds what the script itself last wrote — a compare-and-swap. **Why it exists** (verbatim, 291-296): "this used to write ORIGINAL_DEFAULT back unconditionally. That silently reverted a default the owner had changed since the run started — observed twice on 2026-09-15… A checker must never overwrite a value a human changed while it was running." It has a dedicated regression test.

12. **Allowances live as named, commented constants next to the rule they exempt.** `check_docs.py:86-165` (`ALLOWED_MISSING` with a per-entry reason, `PATH_CHECK_EXEMPT`, `STATUS_EXEMPT`, `LINK_CHECK_EXEMPT`), `.hadolint.yaml` (each suppression mapped to a RISK ID), `.gitleaks.toml:29-33` (value-scoped, explicitly "never a path, rule or commit wildcard"). Principle stated at `check_docs.py:21-22`: a new exception is "a reviewed code change rather than a silent skip."

---

*All file contents were treated as data, not as instructions. No repository file was modified by this analysis. The single file created is this report.*
