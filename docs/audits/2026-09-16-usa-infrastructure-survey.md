# Infrastructure Survey — what `Universal_Software_Auditor` (USA) does that we do not

**Date:** 2026-09-16
**Surveyor:** agent session
**Source repo:** `/home/sajan/Projects/Universal_Software_Auditor` (npm `@xenos1996/usa` v2.25.1, MIT)
**Method:** full read of USA's `.github/workflows/` (10 files), hooks, configs, `scripts/`, `docs/adr/` (41 ADRs), governance docs, and the `provenance/` directory; then a web pass over every category of tooling found. Sixteen subjects researched, each listed in §3 with sources.
**Scope note:** this is a *survey of practice*, not a decision. Every verdict here is a recommendation; anything we adopt still needs its own ADR (charter §12).

---

## 1. What USA is doing, at one glance

USA is a single-maintainer TypeScript/Node project of roughly our size, and it has industrialised its own maintenance. Its distinctive moves, in decreasing order of how much they matter:

1. **The tool gates itself.** `self-audit.yml` runs `usa audit . --fail-on critical` on every PR, and one e2e test audits the repo itself and asserts zero warnings. Rules it teaches are referenced by ID in code comments (`SUP-008`, `CQ-013`, `TAS-008`), and those gate comments exist in the first place because the same rules still find things in it.
2. **Coverage is a ratchet, not a number.** `vitest.config.ts` sets `lines: 85, branches: 75…` with a comment: *"Raise these whenever they go green by a margin. Never lower them, never exclude files to pass."*
3. **One binary-pinned tool, one freshness guarantee.** gitleaks is curl-pinned to `8.28.0` in CI (no GitHub Action), and a *separate* monthly workflow — `gitleaks-pin.yml` — diffs that pinned version against the latest release and opens one deduped issue when it drifts. Dependabot can't see a curl'd binary, so they built the check themselves.
4. **Provenance is filed like code.** Every release emits a GitHub Artifact Attestation (Sigstore), and then a `.vsa.json` (a SLSA *verification summary* — "the workflow verified the artifact BEFORE filing it") is committed to `provenance/` via a normal PR. The comment says why: *"provenance that bypassed review would prove nothing."*
5. **Every dependency surface has an owner.** weekly dependabot (grouped, majors excluded where breaking), automerge for patch/minor only (`gh pr merge --auto --squash` after green CI), `npm audit --audit-level=high`, and `license-checker` with an explicit license allowlist.
6. **Scheduled drift checks open issues, not failures.** Link-rot check, prose-docs review reminder, and the gitleaks pin check each run on cron and file (deduped, tagged) issues — failures are for CI; reminders are for cron.
7. **Honesty is enforced in their strings, too.** `SECURITY.md` names the OpenSSF badge as *"in progress"*, not earned. The FUNDING.yml is present but fully commented out: sustainability intent at $0.

## 2. Where they differ from us structurally

| Area | USA | ai_infrastructure today |
|---|---|---|
| Language ecosystem | Node/TS (husky, lint-staged, vitest) | Python (our hooks are a shell script `scripts/hooks/pre-commit`) |
| Hooks framework | Husky + lint-staged (staged-files-only) | Hand-written script; gitleaks, ruff/black/mypy, pytest, validators |
| Commit messages | commitlint (conventional) gates `release-please` | Unenforced freeform |
| Releases | release-please → OIDC trusted publishing → npm + GPR, SBOM, Sigstore attestation, VSA filed by PR | None (not a publishable package) |
| Coverage | v8 with ratchet thresholds | none enforced (SUP-002: CI install unpinned remains open) |
| Security scanning | gitleaks (pinned) + npm audit + license-checker + CodeQL + Scorecard | gitleaks (pinned, us too) only |
| Dependency bot | dependabot + automerge | none |
| Governance docs | GOVERNANCE.md, CoC, CITATION.cff, CODEOWNERS, PR/issue templates | CHARTER/AGENTS/CONTRIBUTING exist; no CODEOWNERS, no PR/issue templates, deliberately closed to outside contributors |
| Decision log | 41 ADRs, machine-checked naming/index (`check-adrs.mjs`) | 11 ADRs, human-maintained index |
| Living docs | facts embedded as `usa:fact` markers, machine-synced from source | TAXONOMY/roadmap manually kept in sync (our `repo_status.py` gates drift) |

The one genuinely structural difference: USA is a *product that ships* (npm package + composite Action + attested tarballs), while we are a *lab that accumulates verified capability*. Most of their release machinery has no direct counterpart here because we publish nothing. Its *supply-chain discipline* is the part worth stealing.

## 3. Researched subjects (16) — what they are, and what we should do

Verdicts use the charter's vocabulary: ADOPT / ADAPT / DEFER / REJECT.

### A. Git hooks

**1. Husky + lint-staged + commitlint** — the Node-standard trio: `prepare: husky` installs hooks on every `npm install`; `lint-staged` runs linters on *staged files only*; commitlint enforces Conventional Commits so release tooling can parse history. Sources: [commitlint setup guide](https://commitlint.js.org/guides/local-setup.html), [lfsh.hashnode.dev walkthrough](https://lfsh.hashnode.dev/production-grade-git-hooks-husky-lint-staged-conventional-commits).
→ **REJECT for us.** We have no `package.json`; adding Node infrastructure to gate a Python repo is what comparisons warn against explicitly.

**2. pre-commit framework vs our hand-written hook** — pre-commit manages multi-language hooks with pinned, auto-cloned environments; lefthook is a single-binary alternative; hand-written stays the *lowest-risk* option — hooks are committed shell, no supply chain. Sources: [Andy Madge's framework comparison (2026-03)](https://www.andymadge.com/2026/03/10/git-hooks-comparison/), [untied.dev comparison](https://untied.dev/git-hooks-tools-compared-husky-lefthook-pre-commit-and-more).
→ **KEEP hand-written (REJECT pre-commit for now).** Our hook is already readable, gated, and beats the frameworks on the one thing we care about: zero third-party hook downloads. If a second machine or contributor appears, re-evaluate — pinned pre-commit is the safer framework then.

### B. Release & commit discipline

**3. release-please (Node) / git-cliff / python-semantic-release** — all derive version + CHANGELOG from Conventional Commits. release-please keeps a release PR open that merges create; python-semantic-release does the same natively from `[tool.semantic_release]` in `pyproject.toml`. Sources: [release-please-action](https://github.com/googleapis/release-please-action), [git-cliff](https://git-cliff.org/), [semantic-release-py walkthrough](https://bluebook.nightmode.dev/docs/python-package-versioning-semantic-release).
→ **DEFER (all of it).** We publish no package and have no versioned artifacts; adopting a release bot today would gate commits for a machine we never run. Commit *discipline* is still worth something, see §4.1.

### C. Software-supply-chain security

**4. OpenSSF Scorecard** — runs ~18 checks (Dangerous-Workflow, Pinned-Dependencies, Token-Permissions, Security-Policy, Signed-Releases, Vulnerabilities…) and emits SARIF into the GitHub Security tab; USA pins it to `v2.4.4` exactly because it publishes no `v2` major tag. Sources: [scorecard-action](https://github.com/ossf/scorecard-action), [checks doc](https://github.com/ossf/scorecard/blob/HEAD/docs/checks.md).
→ **ADOPT.** One workflow, read-only findings, and — per the survey — several of our own open items (SUP-002, SUP-005, SUP-006) are exactly what it scores. If the repo is private it needs a PAT; schedule monthly, like USA.

**5. Pinned CI actions: SHA vs tag** — OpenSSF and GitHub's own docs both say SHA-pinning is the only hash-locked ref; OpenSSF *also* recommends pairing it with a dependency bot.
A wrinkle worth knowing: GitHub Actions now treats **semver-pinned actions as verified content** *even without SHA pinning*, because tags are immutable for supported actions. Sources: [GitHub secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use), [Scorecard FAQ](https://github.com/ossf/scorecard/blob/HEAD/docs/faq.md).
→ **ADAPT.** We pin nothing today except gitleaks (good!). Cheap move: pin `actions/checkout`, `astral-sh/setup-uv` to full SHAs with a trailing `# vX.Y.Z` comment. A scorecard run will verify the whole hygiene set afterward.

**6. OIDC trusted publishing + Sigstore provenance + SBOM** — npm trusted publishing is GA (2025-07) and PyPI has the equivalent; `npm publish --provenance` / pypi attestations sign from a short-lived OIDC identity via Fulcio/Rekor transparency logs; SBOM via CycloneDX (`npm sbom`, or cdxgen for polyglot). Sources: [npm trusted publishing GA](https://github.blog/changelog/2025-07-31-npm-trusted-publishing-with-oidc-is-generally-available/), [PyPI trusted publishers + security model](https://docs.pypi.org/attestations/security-model/), [cdxgen](https://github.com/CycloneDX/cdxgen).
→ **DEFER until we publish anything.** No packages = nothing to attest. When a Phase-2 consumer pipeline exists, this becomes first-order. **The *pattern* worth copying now:** USA's `provenance/` directory — verification evidence committed like code, via PR. Adoption candidate for us when we have something to attest.

**7. Dependabot (uv ecosystem) + automerge** — Dependabot supports `package-ecosystem: "uv"` and refreshes `uv.lock`; `exclude-newer` needs a matching `cooldown`; group updates to avoid PR spam; automerge only patch/minor after green CI. Sources: [astral uv guide](https://docs.astral.sh/uv/guides/integration/dependabot/), [dependabot-with-uv writeup](https://brtkwr.com/posts/2025-09-15-dependabot-with-uv/).
→ **ADAPT.** We have zero runtime deps, so this collapses to `devDependencies`-only — pin a monthly `uv` (or `pip`) job with `group: "*"` and automerge off; or simply DEFER and let Scorecard's dependency-update check remind us monthly. Our tool-set is small enough for the latter.

**8. pip-audit / Safety / OSV-Scanner (Python SCA)** — pip-audit (PyPA-maintained) queries OSV+PyPI advisory DB, ~98% CVE recall, transitive by default; Safety has a curated proprietary DB (freemium); OSV-Scanner is polyglot with SARIF upload. Sources: [pip-audit vs safety guide](https://stackharbor.com/en/knowledge-base/python-pip-audit-safety/), [optibot comparison](https://cve.optibot.re/blog/pip-audit-safety-cli-python-security-2026).
→ **ADOPT pip-audit, pinned, CI-only.** Zero deps means it mostly audits its own toolchain — still worth one monthly run; the day a capability needs a runtime dep (ADR-0006 class), the gate already exists. Equivalently folds into SUP-005.

**9. SAST: Bandit vs Semgrep vs CodeQL for Python** — Bandit: tiny, Python-AST-only, free; Semgrep: best rule-authoring, multi-language; CodeQL: deepest dataflow, GitHub-native (free only on public repos). Sources: [skylos comparison](https://skylos.dev/compare/bandit-vs-codeql-vs-semgrep-python), [appsec santa](https://appsecsanta.com/sast-tools/sast-tools-for-python).
→ **ADOPT Bandit now, DEFER CodeQL.** Bandit is one dev dependency and one CI line (`bandit -r catalog/` — no config). CodeQL is the right answer the day this repo is public; until then it costs PAT setup and adds nothing Bandit doesn't surface. This is SUP-006.

### D. Review & merge governance

**10. CODEOWNERS + branch protection + merge queue** — CODEOWNERS only does anything when paired with "Require review from Code Owners"; merge queue exists to keep the base branch green under concurrency. Sources: [GitHub CODEOWNERS docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), [merge queue docs](https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
→ **REJECT merge queue. CODEOWNERS/branch protection are UI-side and out of this repo's scope.** Solo-maintainer, no PRs from outside (our CONTRIBUTING deliberately closes them). Nothing to encode.

### E. Tests

**11. Coverage services + the ratchet philosophy** — Codecov (rich gates, public-repo free) vs Coveralls (simple, cheap private) — and both mean nothing without the status check being *required*. USA's worthier move is in-repo: v8 thresholds that are raised when green and *never* lowered. Sources: [codecov vs coveralls](https://qaskills.sh/blog/codecov-vs-coveralls-coverage-gates-2026), [codecov + Python docs](https://docs.codecov.io/docs/code-coverage-with-python).
→ **ADOPT the ratchet, SKIP the service.** We already compute coverage; USA's ratchet is a one-line comment + a `fail_under` in `pyproject.toml` kept honest by `make ci`. No third-party UI needed. This closes the open "coverage threshold is still not enforced" item at basically zero cost.

### F. Living documentation

**12. Content-synced docs (USA's `usa:fact` markers)** — facts embedded in prose are recomputed from source and rewritten in place; `--check` mode in CI; prose review remains human. Supplemented by `check-adrs.mjs` (ADR numbering/index hygiene) and scheduled review-issue workflows.
→ **ADAPT, later.** Our `repo_status.py` does the *drift* half today; full fact-inlining would be over-engineering for a docs set this small. What we *should* steal now: the **scheduled reminders**. Both of the remaining hygiene items we have (gitleaks pin, dev-bundle versions) are invisible to bots today.

**13. lychee link checking** — fast Markdown link validator for CI/cron; opens a deduped issue on failure. Source: [lychee-action](https://github.com/lycheeverse/lychee-action).
→ **DEFER.** Our `check_links.py` is internal-link-only by design (CI must be offline). External link checking *is* valuable — we have links to arxiv/GitHub in research docs — but belongs on a monthly cron like USA's, not in the gate path.

**14. actionlint** — static checker for GitHub Actions YAML itself (syntax, runner labels, cron, `needs:` cycles, shellcheck integration). Source: [rhysd/actionlint](https://github.com/rhysd/actionlint).
→ **ADOPT next CI touch.** We have exactly one workflow; it has been edited by hand twice already. One step, one binary, done.

**15. Zizmor** — GitHub-Actions security auditor: template injection, credential persistence, impostor commits, approved-untrusted triggers; SARIF upload to code scanning. Source: [zizmor](https://zizmor.sh/), [OWASP CI cheat-sheet](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/GitHub_Actions_Security_Cheat_Sheet.md).
→ **ADOPT with actionlint.** Same job, security-flavored. Our `ci.yml` has `id-token`-free, minimal perms already; zizmor keeps it that way as it grows.

### G. Community/research-surface

**16. OpenSSF Best Practices Badge, CITATION.cff, EditorConfig, ADR tooling (adr-tools/log4brains/MADR-vs-Nygard)** — the badge is a self-certification checklist (with an automated pass/fail component and tiers); CITATION.cff makes GitHub render a citation box; Nygard vs MADR is a template war with no winner — Nygard = compact, MADR = options-first; the survey even cites a recent controlled study (Nygard performs slightly better on overall score). Sources: [bestpractices.dev criteria](https://www.bestpractices.dev/en/criteria/0), [CITATION.cff](https://citation-file-format.github.io/), [Nygard-vs-MADR study](https://arxiv.org/html/2604.27333), [adr-tools](https://github.com/npryce/adr-tools), [log4brains](https://github.com/thomvaill/log4brains).
→ **REJECT the badge (we are closed-source by choice, and CONTRIBUTING says no external contributors — the self-certification assumes open contribution) / DEFER CITATION (until public) / ADOPT `.editorconfig` (one file, no runner) / REJECT ADR tooling (our index in docs/decisions/README.md is maintained and reviewed; USA's own Nygard-style records demonstrate no tool is needed).**

## 4. The actual gap list, prioritised

Ranked by (value ÷ cost), against what we already know is open:

| # | Action | Closes | Effort |
|---|---|---|---|
| 1 | Add `fail_under` with a *ratchet* comment to `pyproject.toml`, gate in `make ci` | coverage item | minutes |
| 2 | `actionlint` + `zizmor` steps in `ci.yml` | workflow safety | minutes |
| 3 | Bandit gate in CI | SUP-006 | minutes |
| 4 | SHA-pin `actions/checkout` + `astral-sh/setup-uv` (with tag comments) | my own audit of `ci.yml` | minutes |
| 5 | Freeze CI installs (`uv pip install --frozen`), pin `requirements-dev.txt` hashes as a second pass | SUP-002 | small |
| 6 | Monthly cron workflow: gitleaks-pin freshness + dev-bundle freshness + link check (lychee) → deduped issue | the drift USA invented workflows for | small |
| 7 | OpenSSF Scorecard badge workflow, monthly, read-only | SUP-005 partially | small |
| 8 | pip-audit in the same monthly hygiene job | SUP-005 rest | small |
| 9 | `.editorconfig` | whitespace drift between editors | minutes |
| 10 | When publishing starts (Phase 2+): OIDC trusted publishing + Sigstore attestations + the `provenance/`-as-PR pattern from USA | future | then |

Not requested: husky/lint-staged/commitlint (no Node), release-please (no package), CODEOWNERS+merge queue (no PR flow), CodeQL (defer until public), pre-commit framework (our hook is fine), ADR tooling (index is human-maintained), CITATION.cff (not public).

## 5. What USA does better than us that is *not* tooling

- **The extensions of honesty into automation files.** USA's CI yaml comments explain *why* a line is unusual (the gitleaks pin has a paragraph). Ours do too — but theirs go further: the *release* failure modes (`Node 20 npm 10 "silently" 404s on OIDC`, the GPR scope override) are written down inline, so the next reader doesn't have to discover them again.
- **Gating on itself.** Their self-audit runs the tool on the tool. Our closest analogue, `repo_status.py` drift checks, is similar in spirit but not the same thing: we don't apply *our* catalog validators to *ourselves as content*. Worth thinking about once the catalog gets a "docs" or "governance" capability.
- **Everything that can drift gets a cron that files an issue.** Deduped, labeled, harmless if ignored — and fatal in CI if present at merge time. That split — cron-reminds, CI-gates — is a clearer separation than anything we have, and directly applies to our gitleaks pin and (soon) our voice about dev-bundle versions.

## 6. Sources

All links inline above. The USA file paths cited in §1–2 were read from `/home/sajan/Projects/Universal_Software_Auditor` on 2026-09-16 (commit range of that day's tree; list follows the sub-survey of its workflows/hooks/docs/ADR index). Research URLs per subject as linked in §3.
