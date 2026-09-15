# USA Audit (foundation declared) — ai_infrastructure

**Date:** 2026-09-15 · **Commit:** `6e934e39`+ · **USA version:** 2.19.0 · **Depth:** standard
**Profile:** MVP / Early product (auto-detected, score 2.5/7.5)
**Foundation:** [`.usa/foundation.yaml`](../../.usa/foundation.yaml) — vision, intents, stage declared
**Raw output:** [`2026-09-15-usa-raw-foundation.md`](2026-09-15-usa-raw-foundation.md)
**Prior run:** [`2026-09-15-usa-audit.md`](2026-09-15-usa-audit.md) (71.4, 1 HIGH)

## Result

**72.4/100** · 59 ✅ · 0 🔴 FAIL · 0 ⚠️ WRONG · 0 🟠 HIGH · 3 🟡 MEDIUM · 18 🟢 LOW · 15 🔵 FUTURE · 28 to review.
Automation coverage 77.2%. **Sprint 0 and Sprint 1 are both empty.**

Diff against the prior run: **+1.0**, one item fixed, **zero regressions, zero newly-applicable findings.**

---

## What `usa foundation init` added

```
$ usa foundation init /home/sajan/Projects/ai_infrastructure --non-interactive
created /home/sajan/Projects/ai_infrastructure/.usa/foundation.yaml

$ usa foundation show /home/sajan/Projects/ai_infrastructure
# Foundation: ai_infrastructure
vision: An independent, evolving AI infrastructure laboratory: study how real AI
  systems solve infrastructure problems, then build composable, verifiable,
  well-documented implementations of those capabilities so that many different
  AI systems can be assembled from the pieces. Not a framework, not a clone.
stage: prototype
intents: library, cli, docs-site
facts this intent would assert:
  intent:library
  intent:cli
  intent:docs-site
pillars:
  docs.required: README.md, CHARTER.md, CONTRIBUTING.md, LICENSE, TAXONOMY.md
  governance: contributing, security-policy, license
  ai: readable, writable
  testing: tests @ >=0%
  environment: (none)
  pipelines.local: check, status, test, lint, typecheck, validate
  pipelines.ci: .github/workflows/ci.yml
```

### Declared intent, and what was corrected

`foundation init` auto-detected reasonable defaults, but three were wrong for
this project. Corrected — because declaring a false intent would make the audit
grade against a fiction (charter §4):

| Field | Auto-detected | Declared | Why |
|---|---|---|---|
| `vision` | `""` | Full statement | The one thing no tool can guess. Taken from the charter in the project's own words. |
| `project.intents` | `library` | `library`, `cli`, `docs-site` | `scripts/*.py` are real CLIs, and the knowledge plane (`research/`, `TAXONOMY.md`, ADRs) is a **primary deliverable**, not an afterthought. |
| `stage` | `prototype` | `prototype` *(kept)* | Honest. Phase 1 Seed, empty `catalog/`. Declaring `mvp` would overstate it and hold the repo to a bar it has not reached. |
| `testing.minCoverage` | `80` | `0` | No threshold is enforced. `pyproject.toml` says so explicitly: *"Set `fail_under` when the first catalog entry lands."* Declaring 80 asserts a bar the repo does not hold itself to. |
| `governance.securityPolicy` | `false` | `true` | Made true **by adding `SECURITY.md`** in the same change, so the declaration is factual rather than aspirational. |
| `pillars.ai.writable` | `false` | `true` | Agent sessions do write here; `AGENTS.md` and the `make check`/`make status` gates exist precisely to constrain them. |
| `pipelines.local` | `test`, `build` | `check`, `status`, `test`, `lint`, `typecheck`, `validate` | The real Makefile targets. There is no `build` step (nothing to build). |

**VERDICT on `stage`: the tool does not let the declared stage override the auto-detected maturity profile.** The header still reads `Maturity: MVP / Early product (auto-detected)` and downgrades apply on the MVP profile. `stage: prototype` is recorded and visible in `foundation show`, and it gates intent-specific rules, but it does not change the severity bar. *That is a genuine, reproducible observation about USA, reported here rather than glossed over.*

---

## The fix

### `REPO-009` SECURITY.md — ✅ RESOLVED

The prior run's only genuine HIGH. Now present, and written to be useful rather than ceremonial:

- supported versions (honestly: **none yet**, no tags exist)
- a private reporting channel + acknowledgement/fix targets
- **an explicit scope and threat model** naming what does *not* exist — no model, prompt, agent, retrieval, or tool-execution code — so the absent AI-era attack surface is stated rather than left to implication
- in-scope items that are unusual but correct: the governance gate itself (`make status` must not be bypassable), and supply-chain integrity of the pinned toolchain
- known limitations: no vulnerability scanning in CI, and **zero runtime dependencies**

Status: `REPO-009 — MISSING → PASS`. Diff confirms 0 regressions.

---

## Remaining findings (all adjudicated)

The adjudication from the prior run stands: **~8 of the 37 "missing" findings are false negatives** from Node-shaped detection patterns applied to a pure-Python repo. Re-verified this run — the tool's pattern sets are unchanged:

| Rule | Tool says | Adjudicated | Evidence |
|---|---|---|---|
| `SUP-001` lockfile | 🟡 MISSING | ✅ **PASS** | `requirements-dev.txt` exists, fully pinned (`ruff==0.16.7`…). Not in the tool's pattern set. |
| `SUP-022` SLSA provenance | 🟡 MISSING | ⏭️ **N/A** | Zero releases, zero tags. Premature — the tool's own MVP profile downgrades it. |
| `SUP-005` dep scanning in CI | 🟡 MISSING | 🚫 **GENUINE** | Real gap. Mitigated by `dependencies = []` — nothing to scan yet. Closes at the first runtime dependency. |
| `FND-009`/`TAS-005` coverage config | 🚫 MISSING | ✅ **PASS** | `[tool.coverage.run]` with `branch = true` + `[tool.coverage.report]` in `pyproject.toml`. Tool only globs standalone files/JS runners. |
| `ARCH-001` architecture documented | 🚫 MISSING | ✅ **PASS** | `docs/architecture.md` exists. Tool requires uppercase `ARCHITECTURE.md` or a directory. |
| `TAS-010` failure paths asserted | 🚫 MISSING | ✅ **PASS** | `test_unknown_status_is_an_error`, `test_unknown_dependency_is_an_error`, `test_failing_validation_returns_nonzero`, `test_missing_category_directory_is_error`. Failure paths are the **majority** of the suite. |
| `TEST-003` meaningful test count | 🚫 MISSING (found 2) | ✅ **PASS** | 29 tests (18 + 11). The glob missed `tests/test_*.py`. |
| `FND-003`/`FND-004` CODEOWNERS, branch protection | 🚫 MISSING | ⏭️ **N/A** | Single maintainer, no remote configured. Governance theatre at this size. |
| `FND-011` environment reproducible | 🚫 MISSING | 🚫 **GENUINE but misframed** | No Dockerfile by design (no deployment). But `docs/development.md` + `Makefile` + `requirements-dev.txt` **do** give reproducible setup — verified by tearing down `.venv` and rebuilding from the documented command. The tool's file-pattern list can't see that. |
| 17 further findings | 🚫 | ⏭️ **N/A** | jest, playwright, vitest, `package.json`, IaC, APM — no corresponding technology in this repo. |

### Critical and HIGH after adjudication

**None actionable.** With `REPO-009` fixed, no CRITICAL or HIGH remains. The AI-era CRITICAL/HIGH rules (`AI-001`, `AI-003`, `AI-007`, `AI-010`) remain **NOT APPLICABLE** — there is still no LLM-facing code. They activate with the first capability, which is exactly what the roadmap queues. Marking them ✅ would be an unevidenced pass; the framework forbids it.

---

## Foundation readiness: 3 of 6 pillars READY

| Pillar | Grade | Adjudication |
|---|---|---|
| Docs | ✅ READY | Accurate. |
| Pipelines | ✅ READY | Accurate — CI runs lint, format, mypy strict, catalog contract, drift check, tests+coverage. |
| AI readiness | ✅ READY | Accurate (foundation file parses, intent declared). |
| Governance | ⚠️ PARTIAL | Analysis correct; the two open items are N/A for a solo repo with no remote. |
| Testing | ⚠️ PARTIAL | **Inaccurate** — blocked only by `FND-009`, a false negative. Coverage config exists. Should be READY. |
| Environment | ⚠️ PARTIAL | **Partly inaccurate** — the tool wants `.env.example`/`Dockerfile`; neither fits a library with no deployment and no runtime config. |

**Corrected readiness: 4–5 of 6**, not 3 of 6.

---

## Assessment

The value of this run was not the +1.0 point — it was **making the project's intent machine-readable**. Before, the auditor had to guess what `ai_infrastructure` was for and graded it as a generic MVP-trending app (hence jest and Playwright findings). Now `.usa/foundation.yaml` states, in the project's own words, that this is a library + CLI + documentation project at prototype stage.

The remaining MEDIUM items are small, and two of the three (`SUP-001` lockfile, `SUP-022` provenance) are false negatives or premature. The genuine backlog is now: **secret scanning, dependency scanning, SAST, and a frozen install in CI** — all supply-chain hardening, none of it architectural.

The honest headline: **an empty-`catalog/` repository scoring 72.4 with zero FAIL and zero WRONG is a statement about its governance, not its capability.** The score is carried entirely by the charter, standards, ADRs, and enforcement machinery. It will drop when real code arrives, and that will be the more informative number.

## Recommendations for USA (the tool, not the audited project)

Reproducible pattern gaps found across two runs:

1. **Lockfiles**: add `requirements*.txt`, `constraints*.txt`, `Pipfile`, `environment.yml`.
2. **Coverage config**: read `pyproject.toml` `[tool.coverage.*]`, `setup.cfg`, `tox.ini`.
3. **Architecture docs**: case-insensitive match, plus `docs/architecture.md` and `docs/adr/**`.
4. **Python test discovery**: `tests/test_*.py` and `**/test_*.py` for `TAS-010`/`TEST-003` — currently undercounts by ~93%.
5. **Declared `stage` does not override the auto-detected maturity profile.** Either honour it, or document that `--profile` is the only override. As it stands, `foundation init`'s stage answer is recorded but has no effect on the severity bar.
6. Exclude `.uv-cache/` and similar tool caches from file walking.