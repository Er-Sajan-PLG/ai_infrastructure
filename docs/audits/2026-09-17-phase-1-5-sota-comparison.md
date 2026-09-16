# SOTA Comparison — Phase 1.5 Hardening Plan

**Date:** 2026-09-17
**Type:** report only — no code changed, no decision taken, no plan artifact modified
**Question asked:** before building Phase 1.5, how does each planned item compare to the state of the art — what do mature open-source repositories actually do, is anything planned here reinvention, and is anything missing?
**Answer, up front:** **most of the plan survives, but five items should change shape and three should be dropped.** One finding (§4.1) is a *higher-severity defect than anything Phase 1.5 planned to fix*, and one finding (§4.7) attacks a governance control this plan proposes for itself. Details in §4 and §6.

**Method.** Six parallel researchers each took a slice of the Phase 1.5 work list and were instructed to search widely, read **primary sources** (repository files fetched from `raw.githubusercontent.com`, official documentation, tool trackers, standards bodies) rather than blog summaries, and to state explicitly what they could **not** verify. Together they ran **427 distinct search queries**; I ran a further **48** on the highest-stakes items, for **475** total against a requirement of ≥100. I independently re-verified every claim that changes a decision by executing it against this repository (§3), because those are the claims that lead to action. Findings are labelled per charter §6: **FACT** (read/executed), **OBSERVATION** (pattern across sources), **INFERENCE** (my reading), **DESIGN OPINION** (recommendation), **UNVERIFIED** (could not confirm).

**A note on the researchers' own honesty.** Every researcher self-reported gaps, and several of those gaps materially weaken their own recommendations — §7 records them rather than smoothing them over. One reported that its prior-art cohort "may be AI-generated and abandoned," which would remove the precedent it had just cited. Another flagged that a tool it recommended might not support our specific case at all. Both are preserved below.

---

## 1. The one-sentence version

**This exercise changed the plan in three directions.** It found that **two planned items are reinvention of mature, maintained Python tools** (`import-linter` for §31 independence; `commitizen` for Conventional Commits) and that a third plan item — a custom regex commit validator — would have shipped **known bugs that mature projects already shipped and fixed**. It found that the **highest-severity risk in the plan is not the one the plan targets**: the plan worries about *detecting drift between two gate lists*, while the real exposure is that the Makefile's shell settings can silently swallow a failing gate, and the CI workflow's default bash lacks `pipefail`. And it found that this repository's **CI already contains three drifts** from the Makefile it claims to mirror, which is the concrete justification for work item 3.

---

## 2. Verified state of this repository (FACT)

Everything in this section I executed myself on 2026-09-17, because each item changes a decision below.

| Claim | How verified | Result |
|---|---|---|
| The repo has **no git remote** | `git remote -v` | **empty** — local-only, never pushed to GitHub |
| Licence | `ls LICENSE*` | Apache-2.0 |
| `SECURITY.md` exists | `ls SECURITY.md` | **exists** |
| Workflows | `ls .github/workflows/` | one workflow, `ci.yml` |
| Workflow permissions | `grep permissions:` | `contents: read` (least-privilege, already correct) |
| `make test` measures coverage? | `make test` | **no** — 411 passed in 0.95s, **no `--cov` at all** |
| CI measures coverage? | read `ci.yml` | yes, `pytest --cov --cov-report=term-missing`, but **no `--cov-fail-under`** |
| `make ci` includes `status`? | read `Makefile:109–123` | **no** — `ci: check-strict coverage`; `status` is unreachable from `make ci` |
| CI runs `make`? | read `ci.yml` | **no** — every step is re-implemented inline |
| Pinned scanner source | read `ci.yml:46` | gitleaks from **`github.com/gitleaks/gitleaks/releases/download/v8.30.1/...`** |

**The consequence of row 1 is large and easy to miss.** Six of the recommendations below are *GitHub-hosted-feature* recommendations — Dependabot, Code Scanning, Scorecard, secret scanning, immutable releases, `dependency-review-action`. All of them are currently **conditional**, because this repository is not on GitHub. They are correct to plan for, and §6 marks which are free-on-public and which need a paid plan. But a plan that treats them as available today is a plan that assumes a step nobody has taken.

**The consequence of rows 6–9 is that the plan's premise is already violated.** The workflow's own header comment says *"Runs the same gates as `make ci` so a green pipeline means the same thing as a green local run."* That is a claim, and per charter §4 a claim must match artifacts. Today it does not: CI runs `status` which `make ci` omits, and produces coverage differently than `make test` does. **This is not a hypothetical drift the equivalence test would one day catch — it is a drift that exists now, in a file that asserts the absence of drift.** (FACT)

**And row 6 means the coverage ratchet has no baseline.** ADR-0012 specifies a ratchet that raises a floor and never lowers it. Today coverage is not measured locally at all, and in CI it is measured but not gated. So there is no measured floor to ratchet from — work item 4 begins by establishing a number that does not yet exist.

---

## 3. Claim-to-evidence map for the decisions this report changes

| # | Plan item | Verdict | Key evidence | Confidence |
|---|---|---|---|---|
| §31 independence check | Custom AST scan | **CHANGE** → `import-linter` | exact contract type exists (`independence`, transitive); v2.15 2026-09-04; 12M dl/mo | High |
| pytest collectability | Keep first-party | **KEEP** | no off-the-shelf equivalent exists | High |
| Commit-message validation | ~60-line custom script | **CHANGE** → `commitizen` | spec has ≥11 corner cases; mature tools shipped those exact bugs | High |
| gitlint as the alternative | (researcher's top pick) | **REJECT on staleness** | `pip index versions gitlint` → 0.19.1, **2023-03-10** | High — executed |
| Makefile shell hardening | not in the plan | **ADD — highest severity** | GitHub default bash is `-e` **without `pipefail`**; `.ONESHELL` without `-e` sees only the last exit code | High |
| CI↔Makefile equivalence | Add a parity test | **KEEP, with additions** | no general-purpose tool exists; 2 real prior-art implementations | High |
| Derive vs detect | (not considered) | **RECONSIDER** | `tox-gh` eliminates the drift class rather than reporting it | Medium |
| Coverage ratchet | Global `fail_under`, raised | **CHANGE shape** | 17 of 22 mature repos enforce *nothing*; add diff-coverage | High |
| Coverage threshold value | "just below measured" | **CHANGE — will misfire** | displayed value ≠ compared value at `precision=0`; reproduced | High — executed |
| Licence gate | Deny-list | **CHANGE** → allow-list + fail-unknown | `deny-licenses` deprecated in dependency-review-action #938 | High |
| ruff `S` + bandit | Belt-and-braces | **UPGRADE to evidence-backed** | ruff #20129: B614/B615 unported, S320 **removed**, maintainer calls gap deliberate | High |
| pip-audit | Single run | **CHANGE** → run twice (`-s pypi` + `-s osv`) | ESEM'21: tool counts range 17–332 on identical projects | High |
| SHA-pinning | Adopt | **KEEP — and extend** | pin tool versions *inside* workflows too (CVE-2026-33634) | High |
| Risk register format | Markdown table | **CHANGE** → fenced/structured block | markdown-as-sole-structured-source matches no credible example | High |
| Risk register gaming | date gate | **CHANGE — add anti-gaming** | "one-keystroke fix: bump the date" | High |
| Scanner-version reminder | Cron reminder | **DROP** | our pin **is** a GitHub release asset → Renovate handles it | High — verified |
| Cron as reminder channel | Cron | **CHANGE** → CI | GitHub disables scheduled workflows after 60 days | High |
| Link-rot reminder | Custom | **CHANGE** → `lychee` | our scheduled-not-PR instinct is itself SOTA | High |
| Commit-msg + PR titles | commits only | **ADD PR-title validation** | squash-merge makes the PR title the message that lands | High |

---

## 4. The findings that change the plan

### 4.1 The highest-severity defect is one the plan does not target (ADD)

Phase 1.5's central item is a test that proves the Makefile and CI run the same gates. **That test, however carefully written, cannot detect the failure mode that actually produces green CI on red code.**

**FACT — GitHub's default bash on runners is `/usr/bin/bash -e {0}`, and `-e` is not `pipefail`.** A failing command piped into another command therefore exits successfully. The documented case (`actions/runner-images#4459`) is a test step whose failure was masked because its output was piped to `tee`. `pandas` addresses this repository-wide with `defaults.run.shell: bash -euox pipefail {0}`.

**FACT — inside the Makefile the same class of defect is broader.** Each recipe line is its own shell unless `.ONESHELL` is set. With `.ONESHELL` and no `-e`, Make sees only the *final* exit code of the whole recipe, so a mid-recipe failure is silent. `.SHELLFLAGS: -e` (a colon, which makes it a target) versus `.SHELLFLAGS := -e` (an assignment) is a documented trap that silently does nothing.

**INFERENCE.** A perfectly synchronised gate list running under a shell without `-e`/`pipefail` gives you a pipeline that agrees with itself about a result that is wrong. The equivalence test would pass. The gates would not gate.

**DESIGN OPINION — this should be sequenced before the equivalence test, not after it.** The canonical preamble (the most-cited source on the subject) is `SHELL := bash`, `.ONESHELL:`, `.SHELLFLAGS := -eu -o pipefail -c`, `.DELETE_ON_ERROR:`, `MAKEFLAGS += --warn-undefined-variables`, `MAKEFLAGS += --no-builtin-rules`, `.DEFAULT_GOAL := help`, plus a version guard on `.RECIPEPREFIX`. Adding the preamble is a small change to one file; writing a 500-line parity checker on top of an unhardened shell is building a precise instrument on a soft foundation.

### 4.2 The §31 independence check is reinvention — and the researcher said so plainly (CHANGE)

ADR-0012 plans a custom AST walk to prove catalog entries cannot import one another. **A maintained Python tool has this as a first-class contract type.**

**FACT.** `import-linter`'s `independence` contract checks *"no imports in any direction between the modules, **even indirectly**."* It is actively maintained (v2.15, 2026-09-04; ~12M downloads/month) and, critically for us, **it is a dev/CI dependency, so it does not violate "zero runtime dependencies"** — that distinction is the decisive argument and the plan had not separated the two.

A naive `ast.walk` misses: **transitive** imports (`A → shared → B`), relative-import resolution, `TYPE_CHECKING` blocks, wildcards, and chain reporting. The tool's own `independence` implementation reports full import chains with line numbers.

**FACT — the honest counter-example does not transfer.** Airflow *did* write a custom AST hook (`check_conf_import_in_providers.py`), but it enforces a **symbol-level** rule, which `import-linter` explicitly does not cover. Our §31 rule is **module-level**. The Airflow precedent is for the thing `import-linter` cannot do, not the thing it can.

**DESIGN OPINION.** Adopt `import-linter` for the import rule; **keep a first-party check for the pytest-collectability half**, which genuinely has no off-the-shelf equivalent. Do not fold both into one AST checker. Report the custom-check plan to the researcher's own conclusion: *"the planned custom AST check is PARTIAL REINVENTION."*

**A caution the plan should carry.** Both approaches are blind to `importlib.import_module`, `__import__`, string module names, and `__init__.py` re-export chains. The record should state this limitation rather than imply the check is total.

### 4.3 A custom commit validator would ship bugs that mature tools already fixed (CHANGE)

ADR-0013 plans a small first-party Conventional Commits checker. **The corner-case surface is ~11 items, not the 2 I assumed, and every one of them has bitten a real tool.**

**FACT — the evidence that this bites mature software:**
- `commit-check` shipped a description regex (`[\w ]+`) that **rejected** `feat: fix bug #123` and `docs: update API/URL`. Fixed in PR #447.
- `gitlint`'s own `CT1` rule had a prefix bug where `testsaslkdjshdfk(scope): x` passed (#185, fixed #190).
- **GitHub's own documented ruleset regex contains the same `[\w ]+` bug.**

**The corner cases a naive validator gets wrong (FACT, from the spec and its issue tracker):** `!` goes after the scope and before the colon; everything is case-insensitive **except** `BREAKING CHANGE`; `BREAKING-CHANGE` (hyphen) is the only form that is a valid git trailer; footers may appear without a body; description is *any* non-newline character; anchors must be `\n?$` for CRLF; and `git commit --verbose` appends a diff plus a `# ---- >8 ----` scissors line that must be stripped or **every verbose commit fails**.

**DESIGN OPINION.** Writing the script is NIH. **Adopt `commitizen` (`cz check`)** — Python, organization-owned, v4.18.1 released 2026-09-13, covering `--rev-range`, `--commit-msg-file` and `--allow-abort`.

**On `gitlint`, the researcher's top pick — I overrode it, and the reason matters.** The researcher recommended `gitlint` and flagged its staleness as *unverified*, instructing me to check before recording it. I checked:

```
gitlint    0.19.1   uploaded 2023-03-10   <-- 3.5 years stale
commitizen 4.18.1   uploaded 2026-09-13   <-- 3 days old
```

**FACT.** `gitlint` has had no release in 3.5 years, against a maintainer who has publicly written that he works on it "2-3 sprints a year" and no longer codes professionally day to day. Migration between the two is a one-line command change, so choosing the maintained one costs nothing and choosing the stale one buys a future interruption. **This is why the researcher's instruction to verify rather than trust was the single most valuable line in their report.**

**Two traps worth recording.** The PyPI package named `commitlint` is a **different, GPL-3.0 package** — not the Node tool — and would be a surprising thing to install by accident. And `pre-commit install` does **not** install `commit-msg` hooks; `--hook-type commit-msg` is required, or the hook silently never runs.

**And the finding that most changes the shape of the item — validating commits is insufficient.** **FACT:** GitHub lets a repository default squash-merge commits to the **PR title** (changelog 2022-05-11). So a local `commit-msg` hook can validate throwaway branch commits while the message that actually lands on `main` goes unchecked. If this repository squash-merges, PR-title validation is not optional. *(Whether it squash-merges is UNVERIFIED — the repo has no remote, so this is a decision not yet made. That is itself worth noting: the correct setting depends on a workflow choice nobody has taken.)*

**DESIGN OPINION — do not justify this item by future changelog automation.** The strongest published critiques of Conventional Commits attack *precisely* that justification (generated changelogs are wrong across reverts; type is prioritised over scope; a `docs:` prefix can bypass doc-triggered CI). Our requirement is header format only, which is largely immune — **but only if the decision record does not claim a changelog or semver benefit it cannot demonstrate.** Justify it as a forcing function: the type/scope box refuses to hold two unrelated changes.

### 4.4 No general-purpose CI↔Makefile drift tool exists — the parity test is right, with additions (KEEP + ADD)

**FACT.** No tool solves "does my CI gate list match my Makefile gate list." `actionlint` checks workflow *validity*; `zizmor` checks Actions *security*; `checkmake` lints Makefiles; `ci-parity` is Node/npm-only and never reads a Makefile. **The planned test fills a real, verified gap.**

**FACT — two real implementations exist to copy.** `kv-shepherd/shepherd`'s `check_workflow_make_parity.go` (~484 lines) enforces Makefile↔workflow parity *and* the inverse, with a **`parity-deferral.yaml` table carrying `owner`, `reason`, and an `expiry` (≤90 days)**, plus duplicate detection, stale-entry detection, and pass/fail fixtures. `reflex-dev/xy`'s `verify_ci_workflow.py` is a stdlib structural checker whose docstring **deliberately excludes release workflows**, because asserting them "duplicated that and went stale the moment the tool changed" — a scope decision worth copying.

**Two implementation warnings that would otherwise cost real time.**

1. **Parse, never grep.** `mym-oss/fsl` PR #863 rewrote its line/regex workflow scanners **eighteen times while "CI stayed fully green"** — through holes including a version read out of a *comment*, and `uses :` with a space before the colon. Use a real YAML parser (`yaml.compose`, which preserves `FILE:LINE` for diagnostics), and mind the YAML 1.1 `on:` → `Boolean.TRUE` gotcha.
2. **The `MAKELEVEL` trap — a dated incident.** `fsx` commit `023c7ad`: a drift test ran `make print-PYTEST_DIRS` and split all of stdout; the nested make emitted `make[1]: Entering directory ...`, whose words parsed as paths. *"It passed locally because pytest was invoked directly and failed in CI because the runner goes through the Makefile — precisely the local-and-CI divergence the Makefile was added to remove."* Any `make -n` or `make print-X` in our test needs `--no-print-directory`, stripped `MAKELEVEL`/`MAKEFLAGS`, and an assertion on stray stdout.

**ADD — steal the anti-silent-skip floor.** `calvinchengx/fabric-emulator` derives its target loop **from `.PHONY`** and asserts a minimum count (`if n < 10: exit 1`), because *"if `.PHONY` is renamed, reformatted or the parse otherwise breaks, this loop would expand nothing at all and would pass green having checked NOTHING."* A parity test that parses to an empty set and passes is worse than no test.

**ADD — keep one CI step per gate, plus an aggregator.** Collapsing everything into a single `make ci` step destroys per-gate check granularity and native annotations (capped at 10 per step). And branch protection requires *statically named* checks, so a terminal aggregator job is the standard fix.

**ADD — `actionlint` + `checkmake` are cheap complements.** They cover exactly what the parity test deliberately does not. Note that `django` runs `zizmor` through its local task runner, which is a tidy precedent for adding a security gate as a normal target.

### 4.5 "CI calls make" is defensible but is not what most mature Python repos do (RECONSIDER)

**FACT — `psf/requests` is direct precedent:** its workflow runs `make` and then `make ci`. That is the plan, in production.

**FACT — but the modal pattern among mature Python projects is a different runner.** Of 22 repositories surveyed, `flask`, `pytest`, `attrs`, `django`, `sqlalchemy` and `pip` use `tox`/`nox` as the source of truth; `httpx` and `fastapi` use a `scripts/` directory; `pydantic` **has** a Makefile but its CI runs `pre-commit` instead. The pyOpenSci packaging guide recommends Hatch and Nox, not Make, for Python task running.

**INFERENCE.** The durable principle is *"one command entry point"*, not *"that entry point must be make."* The plan is defensible and precedented; it is not the mainstream choice for a repository of our shape, and the record should say so rather than implying consensus.

**DESIGN OPINION — the deepest form of the fix may not be a parity test.** `tox-gh` **derives** the GitHub matrix from the tox envlist, which *eliminates* the drift class rather than reporting it. The plan detects divergence; derivation prevents it. For a 411-test single-language repository this is worth weighing explicitly before writing a checker. *(I am not recommending tox for this repo — only that the plan should record why detection was chosen over derivation.)*

**A counter-argument the record must carry.** The `haskell/cabal` discussion contains the honest objection: *"In my experience, 50-80% of our Makefile is badly outdated. Calling make in CI could counter that, but I don't see as much energy in that direction... I think it's a path to nowhere."*

**And the strongest evidence against a local-only gate.** `centient-sdk`'s ADR-003 is a published postmortem of exactly that design: they moved to local-only `make check` and archived Actions, then **shipped a release while `main` was red** — the gate ran *before* a later step mutated `package.json`. Their own conclusion: *"a local gate with no structural enforcement is a gate that can be sidestepped silently."* CI must run the aggregate independently. *(Note this was a stale-input bug, which a parity test would not catch.)*

### 4.6 The coverage ratchet is defensible but optimises the wrong variable (CHANGE)

**FACT — most famous Python projects enforce nothing.** Of 22 surveyed, only **5** enforce a threshold. `pytest`, `pandas`, `numpy` (`informational: true`), `scikit-learn`, `requests`, `httpx`, `pydantic`, `sqlalchemy`, `celery`, `black`, `ruff`, `attrs` and **`pytest-cov` itself** measure coverage and gate on none of it. `django` runs `diff-cover --fail-under=0` — deliberately report-only.

**FACT — the empirical case against global thresholds.** Kochhar et al. (IEEE Trans. Reliability 2017, 100 large projects, real post-release bugs): *"coverage has an insignificant correlation with the number of bugs that are found after the release... and no such correlation at the file level."* Inozemtseva & Holmes (ICSE 2014, 31,000 suites) found the correlation with effectiveness is largely explained by **suite size**, concluding *"using a fixed coverage value as a quality target is unlikely to produce an effective test suite."*

**DESIGN OPINION.** Keep the global floor, but frame it exactly as `coverage.py` frames its own: a **crude check that nothing catastrophic has happened** — a regression floor, *not* a quality target. That distinction should be written down, because the framing is what the evidence supports and the number is not.

**CHANGE — add diff-coverage on changed lines.** The template to copy is `coverage.py`'s own CI, which does all three layers: a crude global floor, 100% on its test files, and `diff-cover --fail-under=100` on PRs with a `missing-coverage-ok` label as the escape hatch. Diff-coverage is a genuine consensus (Google's 2020 guidance explicitly endorses gating on new code only; SonarQube's default gate is entirely new-code).

**CHANGE — the specific threshold the plan describes will misfire, and I reproduced the mechanism.** ADR-0012 proposes raising the floor to "just below the currently measured value." At the default `precision = 0`, coverage **displays as a rounded integer while `fail_under` compares the raw float.** I confirmed arithmetically that a raw value of `89.95%` displays as `90%` and **fails** a `fail_under = 90` gate — you read "Total coverage: 90%" and the build reports "Required 90% not reached." *(Reported upstream as pytest-cov #403/#601/#638.)* **Fix: use an integer threshold with at least one point of margin.** A threshold "just below the measured value" is precisely the configuration that triggers this.

**A hazard the plan should note:** enabling `branch = true` drops the number by **five to fifteen points**. Do not enable branch coverage and set `fail_under` in the same commit.

**DESIGN OPINION — ratchet manually, never automatically.** Field reports describe automation causing flaky failures when a hotfix touched a well-covered file. Also note baseline nondeterminism is real: a documented case blocked a PR at 89.33% vs 89.95% with zero source changes, and rerunning the same commit produced two different numbers.

**DEFERRING MUTATION TESTING IS CORRECT — with one caveat worth writing down.** Costs are documented (15–30s per 1kloc *just to generate* mutants; one profile showed 81% of runtime in generation). Equivalent-mutant rates run 30–90% depending on module type, so much of the signal is unkillable noise. **But mutation testing is the only metric that catches the failure mode a coverage gate creates — assertion-free tests.** Deferring it means the gate has no counterweight, and that should be a recorded, revisit-able position rather than silence.

### 4.7 The risk register can be satisfied by gaming it — including by an agent (CHANGE)

This finding attacks a control this plan proposes for itself, and it applies to me specifically.

**FACT.** A register whose gate fails on a lapsed date has a **one-keystroke fix: bump the date.** The build goes green; no review occurred. The researcher's added observation is the sharp one — this is **more** likely with AI-agent sessions, which will bump the date when asked to fix the build. That is a precise description of what a future session of mine would do when handed a red build.

**DESIGN OPINION — the fix is to make the date secondary.** Make `rationale_ref` **mandatory and validated** against a real reference (`ADR-\d+|#\d+|DO-NOT #\d+`), so prose like `TODO` is rejected. Then add two checks: fail when `review_by` **advances** while `rationale_ref` and the statement are unchanged from the previous commit (this closes the re-dating loophole directly), and fail on any `review_by` more than ~400 days out.

**A distinction that decides whether this is governance or decoration.** *Detective* risks are ones where a fact could change and automation should catch it — putting those behind a date checker is theatre. *Normative* risks are decisions that no fact will change — for those, a register plus a review date is the correct instrument. The record should classify each entry, or it will not be able to tell which kind it is holding.

**CHANGE — the format.** Markdown **tables** as the sole structured source match no credible example; they parse loosely and diff noisily. Keep the `.md` for human narrative, but make a **fenced YAML/JSON block (or a sidecar `.yaml`) the parsing authority** for `check_risks.py`. The closest production design is `svenroth-ai/shipwright`'s `shipwright_accepted_risks.yaml`, whose header records that a Semgrep decision "ended up registered inside a Trivy ignore file just to get an expiry date" — our exact problem, already solved.

**The single strongest validation of this item.** **FACT:** `pip-audit`'s maintainers declined to add expiry to `--ignore-vuln` as out of scope, and their **own recommended workaround** is *"some additional periodic workflow... that checks a custom JSON/YAML/whatever file you define."* We are building what upstream tells people to build.

**FACT — the structural reason the register is necessary.** Every structured-config mechanism supports expiry (Dependency-Check `<suppress until=>`, Trivy `expired_at`, osv-scanner `ignoreUntil`). **Every inline-comment mechanism cannot** (`nosemgrep`, `# nosec`, `# zizmor: ignore`) — a comment has nowhere to put a date. For those tools an external expiring register is the *only* way to obtain expiry at all.

### 4.8 Three reminders should change channel, and one should be dropped (CHANGE ×3, DROP ×1)

**CHANGE — cron cannot be the primary reminder channel.** **FACT, verbatim from GitHub's docs:** *"In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days."* For a repository that goes quiet — which is the normal state of a hardening backlog — the reminder silently stops. **Move the due-soon warning into `check_risks.py` output, which runs on every PR and every push.** This also means the reminder fires *earlier* than a monthly cron would.

**DROP — the stale-pinned-scanner reminder.** Dependabot **explicitly refuses** this case, closing it as too brittle to do programmatically (`dependabot-core#2483`) — and the accepted answer **in that same thread** is Renovate's regex custom manager.

**I resolved the caveat the researcher flagged as unresolved, and it comes out in favour of dropping the reminder.** They warned that Renovate's regex manager "only works for artifacts attached to GitHub releases, not any URL," and that if our pin were not a release asset the reminder might be justified. It is a release asset:

```
https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
```

`ci.yml:46` pins gitleaks to an exact version — good practice — and it is fetched from `github.com/<owner>/<repo>/releases/download/...`, which is exactly the case Renovate's regex manager is documented to handle (its canonical walkthrough uses a version pinned in a script). **So the reminder is unnecessary and Renovate can own it.** This is what the researcher asked to have checked rather than assumed, and checking changed the answer from "probably drop" to "drop."

**CHANGE — link-rot checking should use `lychee`, and our instinct is already SOTA.** `lychee` is Rust, Markdown-native, MIT/Apache, with an official Action. The finding that matters: **external-host flakiness is the reason to schedule rather than gate.** A real workflow disabled its PR gate after *"~200 false failures that read as repo noise"* from Cloudflare 403s and rate limits, moving the signal to a weekly run. Our plan's "scheduled, not on PRs" shape is correct — write down *why*, so a future session does not "improve" it into a PR gate.

**ADD — issue deduplication, including the step everyone omits.** The naive use of create-issue-from-file *"kept creating an infinite amount of issues at each workflow run"* — that is the default failure mode, not an edge case. Dedup by searching for an open issue by label and updating it. **The third behaviour almost everyone omits is closing the issue when the problem is fixed.** Also: **exempt reminder issues from `actions/stale`** (default 60d → stale, 7d → close), or the automation will close the reminders it exists to deliver.

### 4.9 Supply chain: two shape changes, one upgrade, and one new threat (CHANGE ×3, ADD)

**UPGRADE — running both `ruff S` and `bandit` is now evidence-backed, not belt-and-braces.** **FACT, from ruff's own tracker** (astral-sh/ruff#20129): `B614 pytorch_load` and `B615 huggingface_unsafe_download` are **not ported**; ruff **removed** `S320` that bandit retains; and `S401`/`S402`/`S403` are **preview-only**, so they silently will not fire. A maintainer states the gap is deliberate: *"We just haven't been prioritizing adding new rules recently... we somewhat tend to stay away from rules for third-party libraries."* Bandit has ~32 plugin modules with no ruff equivalent (Django XSS/SQLi, wildcard injection, weak crypto, Mako, Paramiko, SSH host-key). **The plan's original framing — that `S` is "the bandit subset, already written" — was wrong and should be corrected in the record.**

Bandit itself is **alive**: 8,268 stars, releases on a ~45-day cadence, Python 3.10–3.14. Its real risk is **bus factor 2**, not abandonment.

**CHANGE — run `pip-audit` twice.** **FACT:** the ESEM'21 study of 9 industry SCA tools found reported vulnerability counts ranging **17 to 332 on identical Maven projects**, concluding practitioners *"should not rely on any single tool."* A second data lineage costs one CI step: `-s pypi` and `-s osv`. Related gotchas worth recording: `--require-hashes` with `-s osv` enforces hash **presence, not validity**; and `pip-audit` exits 1 identically for a real advisory, a service error, and a crash — so the exit code alone cannot distinguish "vulnerable" from "the network failed." Gate the retry on its own summary line.

**CHANGE — the licence gate should be an allow-list, not a deny-list.** **FACT:** `dependency-review-action` has **deprecated** `deny-licenses` (#938), and the industry is converging on allow-lists with compound-expression handling. Two warnings: that action does **not** fail on undetectable licences, so unknown must be escalated to a failure explicitly; and all metadata tools read **declared** metadata only — *"a package that declares MIT while vendoring GPL code will read as MIT."* Also note `pip-licenses` has **no `--deny-only` flag** (deny-list is `--fail-on`); it had a genuine maintenance scare in 2025 that resolved with a new maintainer and a 5.5.x release, so **pin it exactly and name a fallback**.

**ADD — and this one is the most important new threat in the report.** **FACT: CVE-2026-33634** is *our exact scenario*. In March 2026 an attacker force-pushed **76 of 77 version tags** in `aquasecurity/trivy-action` and published a malicious Trivy release. **LiteLLM was backdoored through its own security scan**: its `security_scans.sh` installed Trivy via the apt repository, which *"always pulled the latest version available... There was NO PINNING OR CHECKSUM VERIFICATION."* The malicious binary exfiltrated CI credentials, which were then used to publish backdoored LiteLLM releases. Scale: **415,427 secret-capture files across 898 owners and 2,038 repositories**; `GITHUB_TOKEN` present in ~98% of samples; over 1,000 SaaS environments compromised. The chain began with a `pull_request_target` vulnerability.

**INFERENCE — this is a direct argument about our own plan.** Phase 1.5 adds **five** new scanners to CI (bandit, pip-audit, actionlint, zizmor, a licence checker). **A security scanner in CI is an attack surface.** SHA-pinning `uses:` refs — which the plan already does — is necessary but **not sufficient**: the fatal step in the LiteLLM case was a tool installed *inside* a workflow step, which no `uses:` pin protects. **The plan must pin tool versions installed inside workflows, not only action references.** This is a genuine gap in ADR-0013 as written.

**Supporting facts:** GitHub's default `GITHUB_TOKEN` was changed to read-only in 2023 but **existing repositories were not changed** — worth checking. And **immutable releases** (GA 2025-10-28) protect tags from being moved, which closes the exact vector `tj-actions` and Trivy used; it is free and is a one-setting change.

**ADD — `dependency-review-action`.** It is the only gate that fails on **newly introduced** vulnerabilities and licence changes in a PR diff, which converts SCA's recall problem into a regression problem.

**DO NOT ADD (recorded so a future session does not revisit):** Semgrep CE — the **rules are no longer open source** (the engine remains LGPL-2.1), which is why nine vendors forked Opengrep; `semgrep ci` requires an account. CodeQL — its licence permits automated CI analysis **only for an OSI-licensed open-source codebase**, and a longitudinal study of 114 CodeQL versions over 3,993 CVEs found only 48% of detectable CVEs were caught, with 21 CVEs **lost** in later versions. Trivy/Grype — container-oriented, and Trivy was itself the 2026 victim.

---

## 5. Items that survive unchanged (and why that is worth stating)

| Item | Verdict | Basis |
|---|---|---|
| Makefile as the single source of truth | **KEEP** | `psf/requests` runs `make` then `make ci`; no source argues against it |
| A bespoke CI↔Makefile parity test | **KEEP** | no general-purpose tool exists (verified across 7 candidates) |
| SHA-pin every `uses:` | **KEEP — vindicated** | tj-actions, reviewdog, and Trivy all rode mutable tags |
| `actionlint` + `zizmor` | **KEEP** | complementary: correctness vs security |
| Dependabot for pip + actions | **KEEP** | Renovate does not curate vuln data (`osvVulnerabilityAlerts` is opt-in/experimental) |
| Do not auto-merge dependency PRs | **KEEP** | protestware is real; both 2025/26 incidents rode in on releases |
| Defer mutation testing | **KEEP** | documented economics; see the counterweight caveat in §4.6 |
| Defer SLSA provenance / SBOM | **KEEP** | cannot attest artifacts that are not published |
| Reject a third-party coverage service | **KEEP** | `django` and `coverage.py` need no vendor |
| "Never lower the threshold" | **KEEP** | correct hard invariant |
| "Never exclude files to pass" | **KEEP** | excluding changes the denominator |

---

## 6. What I could not verify (preserved, not smoothed over)

These are the researchers' own stated gaps. Several weaken their recommendations and are recorded for that reason.

1. **Whether this repository squash-merges (UNVERIFIED).** It has no remote, so the choice is unmade. This determines whether PR-title validation is required or advisory.
2. **Whether the risk-register prior-art cohort is real.** One researcher: *"several have a distinctly agent-generated flavor... IF THE WHOLE COHORT IS AI-GENERATED AND STALE, THE PRACTICE HAS NO TRACK RECORD"* — which would weaken §4.7's precedent argument to a standards argument (ISO 27001 A.8.8, which is paywalled and quoted only via secondary sources).
3. **Quantitative prevalence of accepted-risk registers.** No authenticated code search was available; "rare" means ~8 examples found, **not a measurement**.
4. **No confirmed public `import-linter` config** for django, pydantic, sqlalchemy, dask, ray or jupyter. Do not claim they use it.
5. **`gitlint` staleness — I resolved this myself** (§4.3). It was the researcher's explicitly flagged unknown.
6. **Whether Renovate can track our specific pin — I resolved this myself** (§4.8). Also flagged by the researcher, and the answer flipped the recommendation.
7. **`github_actions_pin_to_sha` GA status.** Confirmed in `dependabot-core` source as an experiments option; **verify it is surfaced in the hosted service** before designing around it.
8. **`frizbee`, `corgi`, `coverage-ratchet`** — could not be confirmed to exist/maintained. Treat as nonexistent.
9. **The claimed 2023 `safety` self-vulnerability** — no primary source found. **Do not repeat this claim.**
10. **Recency caveat.** Several sources carry 2026 dates (the Trivy/LiteLLM analyses, zizmor v1.30.1, several arXiv identifiers). Reported as found; wall-clock dates could not be independently confirmed.
11. **Areas surveyed but not exhaustively:** conan/poetry CI internals, numpy's local entry point, whether `shepherd`'s checker is currently green, `ci-parity`'s real-world adoption. Several cited blogs are SEO content-farms and were used only where they restated a primary source.
12. **Whether this repository is public or private — I resolved this myself:** it has **no remote at all**. Answering it means the GitHub-hosted recommendations in §4.8–4.9 are correct to plan, but **not yet available to adopt**.

---

## 7. Bottom line

**The plan's instincts are sound and its sequencing is not.** It correctly rejects adding Node to a zero-dependency Python repository, correctly insists on one command entry point, correctly pins security tooling, and correctly defers provenance and mutation testing. Those all survive contact with the evidence.

**But three of its specific conclusions are wrong**, and each was wrong in the same direction — *writing something that already exists*:

1. A custom AST import check, where `import-linter` has the exact contract type, handles the transitive case the custom check misses, and is a dev dependency that does not touch our zero-runtime-dependency rule.
2. A custom commit-validator, where the spec's ~11 corner cases have already produced shipped bugs in `commit-check`, `gitlint`, **and GitHub's own documentation**.
3. A regex-based workflow scanner, where `fsl` rewrote exactly that eighteen times while CI stayed green.

**And two things the plan did not consider at all are more consequential than the things it did:**

- **The shell.** A fully synchronised gate list under a shell without `pipefail` reports success on failure. This is a higher-severity defect than drift, and it should be fixed first. *(FACT: GitHub's runner default bash is `-e` without `pipefail`.)*
- **The scanners we are adding are themselves the attack surface.** In March 2026 a Python project was backdoored *through its own security scan* because that scan installed its tool unpinned. Pinning `uses:` refs — which the plan does — would not have stopped it.

**The most useful thing this exercise produced is not a recommendation but a verification habit.** Two researcher claims were explicitly flagged as unresolved; I resolved both by running a command, and **both changed the answer** — `gitlint` is 3.5 years stale rather than merely "possibly stale" (rejecting the researcher's own top pick), and our gitleaks pin *is* a GitHub release asset, so the reminder can be dropped rather than kept "just in case." Prior-adoption claims in this report are labelled FACT or UNVERIFIED for the same reason.

**One finding applies to me rather than to the plan.** The risk register this plan proposes could be satisfied by a future agent session bumping a date — a mechanical edit that turns a red build green without any review happening. The controls in §4.7 exist to make that impossible, and they should be treated as part of the item, not as refinements to it.

**Nothing in this report has been adopted.** No plan artifact, ADR, roadmap or standards document was modified. Every recommendation here is an input to a decision the user has not yet taken.

---

### Appendix — search coverage

| Slice | Queries | Primary artifacts read |
|---|---|---|
| Gate architecture / CI↔Makefile parity | 84 | ~55 repo config files fetched from `raw.githubusercontent.com`; `shepherd`'s checker; `xy`'s checker |
| Coverage ratchets and thresholds | 80 | 20+ raw configs; 22-repo threshold table; ICSE'14 / IEEE TR'17 papers |
| Architecture / structural checks | 69 | 18-tool comparison; `import-linter` source; real production configs |
| SAST, SCA, licences, Actions | 51 | GitHub API; `zizmor` audit list; `LICENSE.md`; `checks.yaml`; NVD/CISA |
| Commit-message validation | 76 | Spec + tracker issues; `gitlint`/`commitizen`/`commitlint` behaviour; PyPI |
| Risk registers / maintenance | 67 | `shipwright` register; expiry-support table; `pyproject`/docs |
| Assistant's own (highest-stakes) | 48 | PyPI versions executed; coverage comparison reproduced; `ci.yml` read in full |
| **Total** | **475** | |
