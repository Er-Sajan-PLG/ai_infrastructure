# CI/CD Audit Report — ai_infrastructure vs Universal_Software_Auditor

**Date:** 2026-10-09
**Auditor:** HERMES (longcat-2.5-preview-free)
**Method:** Read all USA workflows, compare against our `.github/workflows/ci.yml`

---

## USA's CI/CD Infrastructure (11 workflows, 426-line ci.yml)

| Workflow | Purpose | Jobs |
|---|---|---|
| `ci.yml` | Main CI | lint, test, build, rules, commits, hygiene, resync, security, changesets, self-audit |
| `release.yml` | Version + publish to npmjs | changesets/action, OIDC trusted publishing |
| `publish.yml` | GPR mirror + SBOM + SLSA provenance | mirror, SBOM, attestation, provenance PR |
| `automerge.yml` | Dependabot auto-merge (patch/minor) | automerge |
| `codeql.yml` | CodeQL static analysis | analyze |
| `scorecard.yml` | OpenSSF Scorecard | analysis |
| `gitleaks-pin.yml` | Monthly gitleaks pin freshness | check |
| `docs-link-check.yml` | Docs link validation | check |
| `docs-review.yml` | Docs review | review |
| `protocol-check.yml` | Protocol validation | check |
| `self-audit.yml` | USA self-audit | audit |

## Our CI/CD Infrastructure (1 workflow, 198-line ci.yml)

| Workflow | Purpose | Jobs |
|---|---|---|
| `ci.yml` | All gates in one job | quality (lint, typecheck, validate, links, phase-plan, structural, risks, deferred, sessions, test, coverage, secrets, sast, sca, licenses, workflows, status, diff-coverage) |

---

## Gap Analysis

### CRITICAL (must fix — enforcement gaps)

| # | Gap | USA has | We have | Impact |
|---|---|---|---|---|
| C1 | **Branch protection** | CODEOWNERS + required status checks | Nothing | CI is advisory, not enforcement. Anyone can merge with red checks. |
| C2 | **Release automation** | changesets + OIDC + GPR mirror + SBOM + SLSA | Nothing | No way to publish. No provenance. No SBOM. |
| C3 | **Dependabot auto-merge** | automerge.yml (patch/minor) | Dependabot PRs only | Manual toil for every dependency bump. |
| C4 | **CodeQL** | codeql.yml | Nothing | No SAST beyond bandit/ruff. No dataflow analysis. |
| C5 | **Scorecard** | scorecard.yml | Nothing | No supply chain hygiene visibility. No public security posture. |

### IMPORTANT (should fix — hygiene gaps)

| # | Gap | USA has | We have | Impact |
|---|---|---|---|---|
| I1 | **Gitleaks pin freshness** | gitleaks-pin.yml (monthly) | Nothing | Gitleaks version can go stale. Supply chain risk. |
| I2 | **Self-audit** | self-audit.yml | Nothing | No dogfooding. No automated security posture check. |
| I3 | **Conventional commits CI check** | commits job in ci.yml | Local hook only | Hook can be bypassed with --no-verify. No CI enforcement. |
| I4 | **Separate security job** | security job in ci.yml | Inline in quality | Less visibility. Harder to require separately. |
| I5 | **Build + smoke test** | build job in ci.yml | Nothing | No verification that the package builds. No CLI smoke test. |

### NICE TO HAVE (can defer — workflow gaps)

| # | Gap | USA has | We have | Impact |
|---|---|---|---|---|
| N1 | Docs-review workflow | docs-review.yml | Nothing | No automated docs review. |
| N2 | Protocol-check workflow | protocol-check.yml | Nothing | No automated protocol validation. |
| N3 | Resync workflow | resync job in ci.yml | Nothing | No auto-regeneration of docs. |
| N4 | Changeset enforcement | changesets job in ci.yml | Nothing | No requirement for changesets on shipped paths. |

---

## Detailed Comparison

### 1. Branch Protection

**USA:**
- `CODEOWNERS` file: `*` owned by maintainer
- Required status checks: lint, test, build, rules, commits, hygiene, security, changesets, self-audit
- Required approving reviews: 1 (but maintainer is sole contributor, so this is a self-merge check)
- `enforce_admins: true`

**Us:**
- No branch protection
- No CODEOWNERS
- No required status checks
- CI runs but doesn't block merge

**Fix:** Add branch protection via `gh api` (free tier supports this on private repos). Add CODEOWNERS. Add required status checks for our CI job names.

### 2. Release Automation

**USA:**
- `release.yml`: changesets/action with OIDC trusted publishing to npmjs
- `publish.yml`: GPR mirror, CycloneDX SBOM, SLSA provenance, GitHub Artifact Attestations
- Tags: `@xenos1996/usa@X.Y.Z` (changesets pnpm workspace shape)
- Two registries: npmjs (OIDC) + GPR (PAT)
- Provenance: Sigstore bundle + VSA filed via PR

**Us:**
- No release workflow
- No publishing
- No SBOM
- No provenance
- No attestation

**Fix:** This is a big gap. For a Python repo, we'd use:
- `pypa/gh-action-pypi-publish` for PyPI publishing (OIDC trusted publishing)
- `anchore/sbom-action` for SBOM
- `sigstore/cosign-installer` + `gh attestation` for provenance
- Changesets or manual versioning

### 3. Dependabot Auto-merge

**USA:**
- `automerge.yml`: auto-merges patch/minor Dependabot PRs
- Uses `dependabot/fetch-metadata` to determine update type
- `gh pr merge --auto --squash` for patch/minor only
- Majors stay manual

**Us:**
- Dependabot creates PRs but no auto-merge
- Manual toil for every dependency bump

**Fix:** Add `automerge.yml` workflow. Same pattern as USA.

### 4. CodeQL

**USA:**
- `codeql.yml`: CodeQL analysis for JavaScript/TypeScript
- Runs on push to master, PRs, and weekly schedule
- Uses `.github/codeql-config.yml` for configuration
- `continue-on-error: true` (advisory, not blocking)

**Us:**
- No CodeQL
- Only bandit + ruff S rules for SAST

**Fix:** Add `codeql.yml` for Python. CodeQL is free for public repos. Should be blocking (not advisory) for a security-focused repo.

### 5. Scorecard

**USA:**
- `scorecard.yml`: OpenSSF Scorecard
- Runs on push to master and monthly schedule
- Publishes results to Security tab
- Uses Sigstore keyless signing

**Us:**
- No Scorecard
- No public security posture

**Fix:** Add `scorecard.yml`. Free for public repos. Publishes to Security tab.

### 6. Gitleaks Pin Freshness

**USA:**
- `gitleaks-pin.yml`: Monthly workflow that checks if gitleaks version is current
- Creates PR if update needed
- Prevents stale security tooling

**Us:**
- Gitleaks installed via curl in CI, but no freshness check
- Version can go stale

**Fix:** Add `gitleaks-pin.yml` or add a step to existing CI.

### 7. Self-Audit

**USA:**
- `self-audit.yml`: Runs USA on its own tree
- Fails on CRITICAL findings
- Dogfooding: the tool audits itself

**Us:**
- No self-audit
- No automated security posture check

**Fix:** Add a self-audit step. Could use `bandit` + `pip-audit` + `gitleaks` as a self-audit suite.

### 8. Conventional Commits CI Check

**USA:**
- `commits` job in ci.yml: lints PR commits with commitlint
- Runs on PRs only (master receives squash merges)
- Uses `gh` to resolve SHAs (not event payload interpolation)

**Us:**
- Local commit-msg hook only
- Can be bypassed with --no-verify
- No CI enforcement

**Fix:** Add a `commits` job to ci.yml. Use `commitlint` or a simple grep-based check.

### 9. Separate Security Job

**USA:**
- `security` job in ci.yml: dependency audit, secret scan, license scan
- Separate from lint/test for visibility
- Can be required separately in branch protection

**Us:**
- Security checks inline in quality job
- Less visibility
- Harder to require separately

**Fix:** Split security checks into a separate job in ci.yml.

### 10. Build + Smoke Test

**USA:**
- `build` job: compiles TypeScript, runs CLI smoke test
- Verifies the package builds and the CLI works

**Us:**
- No build step (Python doesn't need compilation)
- No smoke test of the package

**Fix:** Add a `build` job that installs the package and runs a smoke test (e.g., `python -m study_pipeline --version`).

---

## Recommended Hardening Plan

### Phase 1: Critical (do first)

1. **Add branch protection** — `gh api` to configure required status checks
2. **Add CODEOWNERS** — `*` owned by maintainer
3. **Add Dependabot auto-merge** — `automerge.yml`
4. **Add CodeQL** — `codeql.yml` for Python
5. **Add Scorecard** — `scorecard.yml`

### Phase 2: Important (do next)

6. **Add conventional commits CI check** — `commits` job in ci.yml
7. **Split security job** — separate `security` job in ci.yml
8. **Add build + smoke test** — `build` job in ci.yml
9. **Add gitleaks pin freshness** — `gitleaks-pin.yml` or step in CI
10. **Add self-audit** — `self-audit.yml` or step in CI

### Phase 3: Nice to have (do later)

11. **Add docs-review workflow** — `docs-review.yml`
12. **Add protocol-check workflow** — `protocol-check.yml`
13. **Add resync workflow** — auto-regeneration of docs
14. **Add changeset enforcement** — `changesets` job in ci.yml
15. **Add release automation** — `release.yml` + `publish.yml`

---

## Branching Strategy

**USA:**
- Branches from master: `fix/<topic>`, `feat/<topic>`, `chore/<topic>`, `docs/<topic>`
- Never commit to master directly
- Squash-merge when green, delete branch
- Branch protection enforces this

**Us (current):**
- All commits go directly to master
- No branch protection
- No enforcement

**Fix:**
1. Add branch protection (required status checks)
2. Add pre-push hook that rejects direct pushes to master
3. Document branching strategy in AGENTS.md
4. Reset master and re-land work via feature branches + PRs

---

## Summary

| Category | USA | Us | Gap |
|---|---|---|---|
| Workflows | 11 | 1 | 10 missing |
| Jobs in ci.yml | 10 | 1 | 9 missing |
| Branch protection | Yes | No | Critical |
| Release automation | Yes | No | Critical |
| Dependabot auto-merge | Yes | No | Critical |
| CodeQL | Yes | No | Critical |
| Scorecard | Yes | No | Critical |
| Gitleaks pin freshness | Yes | No | Important |
| Self-audit | Yes | No | Important |
| Conventional commits CI | Yes | No | Important |
| Separate security job | Yes | No | Important |
| Build + smoke test | Yes | No | Important |
| Docs-review | Yes | No | Nice to have |
| Protocol-check | Yes | No | Nice to have |
| Resync | Yes | No | Nice to have |
| Changeset enforcement | Yes | No | Nice to have |

**Overall:** We have 1 of 11 workflows. We have 1 of 10 CI jobs. We have branch protection on 0 of 1 branches. We are at ~10% of USA's CI/CD maturity.
