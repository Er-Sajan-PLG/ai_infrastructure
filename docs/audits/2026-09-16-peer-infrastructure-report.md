# Peer Infrastructure Report — JARVIS, Universal_Software_Auditor, PROFESSOR-J

**Date:** 2026-09-16
**Type:** report only — no code changed, no decision taken
**Question asked:** before moving to the next phase, is any *fundamental* engineering machinery missing from `ai_infrastructure` that the three sibling repositories have?
**Answer, up front:** **yes — six items, of which two are defects in what we already claim, not missing features.** Details in §4 and §6.

**Method.** Three sibling repos were read by dedicated readers instructed to read source, configuration, scripts and tests — not documentation — and to treat docs only as a cross-check. Each reader had to state what it did *not* read. I independently read the high-signal files myself (all hooks, CI workflows, gate scripts, governance dirs, contracts) and **re-verified the two claims this report makes about our own repository** by running the commands, because those are the ones that lead to action. Findings are labelled per charter §6: **FACT** (read/executed), **OBSERVATION** (pattern across files), **INFERENCE** (my reading), **DESIGN OPINION** (recommendation).

**Scale of the three repos.** JARVIS: 802 files, 355 Python, 1,504 tests collected, 90% measured coverage. USA: 592 files, 136 TypeScript, 1,278 tests, 315 YAML rules, 41 ADRs. PROFESSOR-J: 692 files, 186 Python, 739 tests across 297 tracked files. Ours: 181 tracked files, 411 tests, 5 catalog entries, 11 ADRs. **We are the smallest and the youngest — which is the reason this comparison is worth doing now and not later.**

---

## 1. The one-sentence version

Our **governance and honesty machinery is the strongest of the four** (nothing in the siblings enforces "a claimed status must match artifacts on disk" the way `repo_status.py` does). Our **supply-chain, security and drift-reminder machinery is the weakest of the four** — JARVIS alone runs 26 gate functions where we run 9 steps, including SAST, SCA, SBOM, provenance and licence policy, none of which we have. And **two things we already claim are false in CI** (§3).

---

## 2. What each sibling actually is (so the comparison is fair)

| Repo | Shape | Its distinctive infrastructure bet |
|---|---|---|
| **JARVIS** | FastAPI monolith, 21k LOC app, personal assistant | GitHub Actions is billing-blocked and branch protection is 403 on a private free-tier repo, so CI was **rebuilt locally**: n8n → `ci_bridge.py` → `ci_gate.py` (1,761 lines, **26 gate functions**) run as a systemd user service, publishing commit statuses via the REST API |
| **USA** | npm package + composite Action, audit framework | **Rules are data, not code** (315 rules, 236 detectors, zero engine change to add one) + per-rule fixtures with a coverage gate + mutation probes + provenance filed by PR |
| **PROFESSOR-J** | FastAPI + frontend, education platform | **A deterministic "virtual board"** of 8 architecture-governance checks (import layering, domain purity, schema drift, safety-gate coverage, OTel spans) run as a blocking gate, plus a cross-repo authority/permission layer |

FACT: JARVIS's gate list includes `ruff_ratchet, semgrep, mypy, pytest, contract, gitleaks, trufflehog, bandit, trivy, osv, licenses, sbom, provenance, board, docs, doc_types, doc_facts, compileall, hadolint, checkov, commitlint` (+ opt-in coverage/docker/mutation/evals) — `scripts/ci_gate.py`.

---

## 3. First: two defects in our own repository, verified today

These are not "missing fundamentals". They are places where **we already claim coverage that does not exist** — the exact bug class `tests/test_gate_coverage.py` was written to prevent, now recurring in a place that test cannot see.

### 3.1 CI type-checks less than the Makefile does — FACT

```
.github/workflows/ci.yml:66   targets=$(find catalog scripts tests study_pipeline -name '*.py' ...
Makefile:72                   targets=$$(find catalog integrations scripts tests study_pipeline -name '*.py' ...
```

`integrations/` is in the Makefile's mypy list and **absent from CI's**. Integration code (25 tests, the end-to-end composition) is type-checked locally and **never in CI**. The meta-test that exists to catch precisely this (`tests/test_gate_coverage.py:224`, "the Makefile's `find` must traverse every gated directory") parses **only the Makefile** — so it verifies the *intended* list and cannot observe that CI diverged from it.

### 3.2 `make check` can pass with governance drift — FACT

```
Makefile:109   check: lint typecheck validate links test
Makefile:112   check-strict: lint typecheck validate-strict links phase-plan test
```

`status` (the drift detector, our flagship check) is in **neither** aggregate. Only CI (`.github/workflows/ci.yml:82`) and the path-conditional pre-commit hook run it. A contributor running the documented `make check`, or a session following `AGENTS.md` ("make check … must pass"), can be green while `TAXONOMY.md` overclaims.

### 3.3 And the framing claim is wrong — FACT

`Makefile:115` says `ci: check-strict coverage  ## What CI runs`. **CI invokes no `make` target at all** — it hand-repeats 13 commands. So "what CI runs" is a comment, not a mechanism, and the two lists have already drifted in two places. This is our own version of the pattern the USA survey called the *cron-reminds / CI-gates* split: a documented equivalence that nothing enforces.

**DESIGN OPINION:** fix all three the same way — make CI call `make ci` (plus its extras), or add a test that parses `ci.yml` and asserts its step list covers the Makefile's aggregate targets. The second is more robust and matches `test_gate_coverage.py`'s existing approach.

---

## 4. The gap matrix

Dimensions where at least one sibling has machinery we do not. **Status** is ours today.

| # | Fundamental | JARVIS | USA | PROF-J | Ours | Verdict |
|---|---|---|---|---|---|---|
| 1 | Coverage threshold enforced | ✅ floor 80 + opt-in gate | ✅ ratchet 84/75/90/85 | ✅ 80 + per-layer 95/85/95 | ❌ **none** | **ADOPT** |
| 2 | SAST | ✅ semgrep + bandit | ✅ CodeQL | ✅ bandit config | ⚠️ ruff `S` subset only | **ADOPT (bandit)** |
| 3 | Dependency vulnerability scan | ✅ pip-audit, trivy, osv | ✅ npm audit | ✅ pip-audit (advisory) | ❌ none | **ADOPT (pip-audit)** |
| 4 | SBOM | ✅ CycloneDX per commit | ⚠️ generated, not kept | ❌ | ❌ | **DEFER** |
| 5 | Provenance/attestation | ✅ in-toto + cosign (L1) | ✅ Sigstore + VSA by PR | ❌ | ❌ | **DEFER (until we publish)** |
| 6 | Licence compliance gate | ✅ denies AGPL/GPL/SSPL | ✅ `--onlyAllow` SPDX | ❌ | ❌ manual only | **ADOPT (cheap, we're Apache-2.0)** |
| 7 | Dependency-update bot | ✅ dependabot + automerge | ✅ dependabot + automerge | ✅ dependabot + automerge | ❌ **none** | **ADOPT** |
| 8 | Commit-message enforcement | ✅ commitlint + hook + CI | ✅ commitlint + CI | ✅ commitlint + CI | ❌ convention only | **ADOPT (cheap)** |
| 9 | Risk register with expiry | ✅ `ACCEPTED_RISKS.md`, 17 items, owners, review dates | ⚠️ suppressions w/ dates | ⚠️ | ❌ **none** | **ADOPT — highest value** |
| 10 | Architecture-boundary checks in code | ✅ import layering (in gate) | ✅ ADR-0003 data-not-code | ✅ 8 board checks | ❌ **none** | **ADOPT (scoped)** |
| 11 | Scheduled drift reminders (cron) | ✅ n8n + systemd | ✅ 6 cron workflows | ⚠️ | ❌ none | **ADOPT (cheap)** |
| 12 | Doc facts derived from code | ✅ markers + commit-stamped cache | ✅ markers + resync bot | ⚠️ | ⚠️ drift check only | **CONSIDER** |
| 13 | Machine-checked ADR hygiene | ✅ | ✅ `check-adrs.mjs` | ⚠️ | ⚠️ index check inside `repo_status.py` | **CONSIDER** |
| 14 | Runner/workflow linting (actionlint, zizmor) | ⚠️ | ⚠️ | ⚠️ | ❌ | **ADOPT (cheap)** |
| 15 | SHA-pinned actions | ❌ majors | ❌ majors | ❌ majors | ❌ majors | **ADOPT (cheap)** |
| 16 | Containerization | ✅ Dockerfile + compose + hadolint | ❌ | ✅ docker/ | ❌ | **DEFER** |
| 17 | Branch protection as code | ✅ script (403 in practice) | ⚠️ settings-side | ⚠️ | ❌ | **REJECT (settings-side)** |
| 18 | Contract/interface tests | ✅ `tests/contract/` | ✅ 3 format contracts | ✅ `verify_export_contract.py` | ❌ | **CONSIDER** |
| 19 | Cross-repo contract verification | ✅ CAPABILITY-CONTRACT v1.0.0 | ❌ | ✅ digest-pinned export | ❌ | **CONSIDER (Phase 2)** |
| 20 | Mutation / property-based testing | ✅ mutmut (opt-in) | ✅ mutation probes | ⚠️ hypothesis present | ❌ | **DEFER** |
| 21 | Self-dogfooding gate | ✅ gate runs on JARVIS | ✅ `usa audit .` on every PR | ✅ board | ⚠️ drift check only | **CONSIDER** |
| 22 | Per-unit test coverage gate (fixtures) | ⚠️ | ✅ **every rule needs a fixture** | ⚠️ | ⚠️ per-entry contract only | **CONSIDER — maps well to us** |

---

## 5. The six things worth doing, ranked

**Tier A — defects and near-zero-cost, do before Phase 2:**

1. **Fix §3.1–3.3** (CI/Makefile divergence). Adding a check that parses `ci.yml` closes a real hole and prevents recurrence.
2. **Adopt a risk register** — JARVIS's `docs/ACCEPTED_RISKS.md` is the single most valuable artifact I found in any of the three: a table of known findings with severity, *named owner*, *accepted date*, *review date*, rationale, and the rule that **a lapsed review date blocks release**. It is what turns an audit backlog (our SUP-002/005/006 scattered across roadmap prose and audit docs) into a governed, expiring register. We have findings; we have no register.
3. **Enforce a coverage threshold with ratchet semantics** — USA's doctrine is written in its config: *"Raise these whenever they go green by a margin — never lower them, never exclude files to pass."* JARVIS adds the honest variant: a gate that reports **DOWN, lower the baseline to lock the gain.** Our `pyproject.toml:75` still carries the comment "Set `fail_under` when the first catalog entry lands" — five entries have landed since.

**Tier B — cheap, real coverage gains:**

4. **Commit-message enforcement** (`commitlint`/`commit-msg` hook). Ours is documented convention only; all three siblings enforce it. Relevant soon: a changelog or release process needs parseable messages.
5. **Dependency-update bot + SCA + SAST + licence check** — this is four config/CI lines' worth of work to close the whole supply-chain row of the matrix. JARVIS is the reference for *how to be honest* about it: `_missing_tool()` reports **SKIP, never a silent pass**, and a gate whose scanner is absent says so.
6. **actionlint + zizmor + SHA-pinned actions.** One workflow, hand-edited twice already; the cheapest hardening available.

**Tier C — consider at Phase 2 (study pipeline) rather than now:**

- **Doc facts derived from code** (USA's `usa:fact` markers, JARVIS's commit-stamped cache). Our `repo_status.py` covers *drift*; fact-inlining would cover *stale numbers in prose*. Note both siblings have live holes here (USA has 281-vs-315 stale markers in its own exempt docs; JARVIS's doc gates are currently red), so adopt the idea, not the implementation.
- **Architecture-boundary checks** (PROFESSOR-J's board): a `catalog/` entry importing another `catalog/` entry's internals is exactly the kind of violation our §31 independence rule forbids and nothing currently detects. Scoped to a handful of AST rules over `catalog/`, this is high value. **Do not copy their full board**: 2 of its 8 checks are always-true placeholders that print ✅ unconditionally.
- **Per-entry fixture/coverage gates** — USA's rule "every automatable rule has a fixture, or CI fails" and "a fixture suite that stays green under mutation is decoration" map directly onto our catalog entry contract.
- **Contract tests for the capability interfaces** — we have none; USA pins three report formats and asserts they agree.

---

## 6. What the siblings have that they cannot actually rely on — do not copy these

This matters as much as the gaps. **Each of the three has a red or inert verification surface**, which is a caution against adopting their shapes wholesale:

- **JARVIS: enforcement is process, not platform.** `ci_bridge.py:22-24` concedes *"nothing here can gate a merge regardless"*, and `AGENTS.md:138` says *"Enforcement is process, not policy."* Its doc gates are currently **red on HEAD**, its last 6 gated PRs all failed, `deploy.yml` is live and calls a `.venv` it never creates, and **~20% of its automation is orphaned** (a 649-line `sota_governance.py` with zero wiring; a `doc_governance.py` documented as running in CI that would clobber the facts cache if it did).
- **PROFESSOR-J: the gates that would have caught it passed anyway.** Its observability stack is **aspirational** — `init_tracer_provider()` and `setup_logging()` are never called, zero spans are emitted, no metrics exist — yet the board's `check_otel_spans` **passes**, because 5 of its 8 checks are string-presence greps rather than behavioural assertions. Its `scripts/verify.py` (the advertised canonical command) is **untracked and wired into nothing**, and its verification is currently red (3 test failures from a live cross-repo contract break, 12 mypy errors, 26 ruff errors, digest drift).
- **USA: a documentation-truth hole in its own fact system.** `docs/writing-docs.md` and `docs/adr/0020-*.md` still claim **281 rules** while the real count is **315**, and `docs:check` passes because those paths are exempted. Its complexity budget is documented as a hard cap but configured `warn`, so `pnpm lint` exits 0 on a breach. Its `.usa.yaml` still describes `release-please` as live machinery after the changesets migration — prose no gate can see.

**OBSERVATION:** the failure mode across all three is the same one our charter warns about in other words — *a check that reports on the presence of a string is not a check that the behaviour works*. Our `repo_status.py` is genuinely unusual in testing **artifacts on disk** rather than claims; that is our strongest asset and it should be the model for anything we add.

---

## 7. Things I found that you should know about regardless of this report

**A. Live credentials are sitting in plaintext on this machine** (found incidentally while reading config as part of the survey; both files are correctly **gitignored and absent from git history** — verified — so this is a local-disk exposure, not a repo leak):

- `JARVIS/.ci-bridge.env` (mode 600) — contains a real GitHub PAT.
- `JARVIS/.claude/settings.local.json.bak` (mode **644**, world-readable) — contains a real OpenRouter API key.
- `PROFESSOR-J/.env` (mode 644) — eight live-looking provider keys (Singularity, OpenRouter, NVIDIA, Google, Groq, Cerebras…).

**DESIGN OPINION:** rotate the two JARVIS values and tighten the modes; consider whether the PROFESSOR-J `.env` needs `chmod 600`. I have not reproduced any value here.

**B. PROFESSOR-J's live cross-repo contract is broken** — `LHSAdapterError: LHS export missing required fields: {'generated_at'}`; the adapter expects `export_version 0.1/schema 0.2` while STEMMA now exports `2.1.0/1.1.0`; the pinned digest also drifted. That is 3 of its test failures and a direct instance of the contract drift the workspace's decoupling rules exist to prevent.

**C. Two audit report files were written into sibling repos** by my readers, which is a side effect of this survey and not something I would normally do (`cross-repo-contracts`: per-repo governance wins; I should not be adding files to JARVIS or PROFESSOR-J):
`JARVIS/docs/FUNDAMENTALS-FORENSIC-REPORT.md`, `JARVIS/AUDIT-APPLICATION-TESTING-LAYER.md`, `JARVIS/docs/README.md` (one index row added), and `PROFESSOR-J-FUNDAMENTALS-REPORT.md`. Also `BASELINE_ENGINEERING_INVENTORY.md` in our root. **Say the word and I will remove all of them** (they are untracked additions; nothing was committed in any repo).

---

## 8. Answering the actual question: what is missing *before the next phase*

**Genuinely missing machinery, in priority order:** (1) a risk register, (2) an enforced coverage threshold, (3) the supply-chain row — SCA, SAST, licence check, dependency bot, (4) commit-message enforcement, (5) CI-runner linting and action pinning, (6) cron-based drift reminders. Plus the two **defects** of §3, which are not missing features but false coverage.

**Not missing, and worth saying:** our lifecycle enforcement, provenance/attribution discipline (`PROVENANCE.md` per entry, registry, `code_reused` rules), research-registry discipline, ADR practice, link/phase-plan checks, `filterwarnings = ["error"]`, and the meta-test that no source directory can go silently ungated are all **at or above** the standard of the three siblings. USA has 315 rules and 1,278 tests but its own fact docs are stale; JARVIS has 26 gates but cannot block a merge; PROFESSOR-J has an 8-check governance board with 2 checks that always pass. **We are not behind on governance — we are behind on verification breadth.**

**One structural note.** All three siblings needed an escape hatch for accumulated debt (JARVIS: mypy ceiling 485 errors; USA: complexity warn-only; PROFESSOR-J: domain-only coverage gate). We currently have **no legacy debt** — mypy strict is clean across 59 files, ruff has 2 global ignores, coverage claims are honest. **The cheap moment to install ratchets is before there is anything to ratchet**, which is now. That is the strongest argument for Tier A and B above.

---

## 9. Evidence and coverage

**Read first-hand by me:** all hooks (`githooks/pre-commit`, `pre-push`, `commit-msg`, our `scripts/hooks/pre-commit`), all CI workflows in JARVIS/USA/PROFESSOR-J, `ci_gate.py` (structure + gate bodies for ruff/mypy/board/run_gates), `ACCEPTED_RISKS.md`, `PROFESSOR-J/scripts/{verify,verify_export_contract,board/review}.py`, `authority/*`, `docker/otel-collector-config.yaml`, capability contracts, both repos' `pyproject.toml`/`Makefile`, `.pre-commit-config.yaml` files, USA `package.json`/`vitest.config.ts`/`release.yml`/`publish.yml`, plus our own `Makefile`, `ci.yml`, four validator scripts, `docs/standards.md`, `tests/test_gate_coverage.py`.

**Read by dedicated readers** (each returned an explicit coverage statement; full reports hold file:line evidence): JARVIS fundamentals (611-line report), JARVIS application/testing (820-line report incl. a merged second pass), USA fundamentals (executed `vitest run`, `vitest run --coverage`, `sync-docs --check`), PROFESSOR-J (executed pytest, mypy, ruff, coverage gate, export-contract check), our own baseline (733-line inventory; gates executed).

**Not read:** sibling `app/` bodies beyond the files listed; vendor trees (`node_modules`, `external/Unlimited-OCR`, `legacy/`); the ~1,380 of `ci_gate.py`'s 1,761 lines not in the gate bodies examined; all 315 USA rule YAML bodies (counted and schema-verified instead); provenance payload files; and my own repo's 382 capability test bodies (counted and coverage-measured). **INFERENCE, not verified:** that fixing §3 makes CI equivalent to a full local `make check` — I did not diff every remaining step.

**Claims about our repo in §3 were verified by running the commands on 2026-09-16**, then re-verified after the last change. Sibling-repo states are as of their HEADs at survey time and will drift.

---

*Report only. No file in `ai_infrastructure` was modified to produce this; the three sibling-repo files noted in §7C are the survey's only side effects and are removable on request.*
