# ADR-0013 — Verification Breadth: Which Checks Are Added, Deferred, or Rejected

- **Status:** Accepted
- **Date:** 2026-09-16
- **Supersedes:** —

## Context

[ADR-0012](0012-gate-architecture.md) establishes *how* gates are defined and kept equivalent. This ADR decides *which* checks exist.

The input is the peer survey of 2026-09-16 ([`../audits/2026-09-16-peer-infrastructure-report.md`](../audits/2026-09-16-peer-infrastructure-report.md)), which read `JARVIS`, `Universal_Software_Auditor` and `PROFESSOR-J` in full and produced a gap matrix. The relevant rows, with what each sibling actually runs:

| Capability | JARVIS | USA | PROFESSOR-J | This repository |
|---|---|---|---|---|
| SAST | semgrep + bandit | CodeQL | bandit | ruff `S` subset only |
| Dependency vulnerabilities | pip-audit, trivy, osv | `npm audit` | pip-audit | none |
| Licence compliance | denies AGPL/GPL/SSPL | `--onlyAllow` 9 SPDX ids | — | manual only |
| Dependency updates | dependabot + automerge | dependabot + automerge | dependabot + automerge | **none** |
| Commit messages | commitlint (hook + CI) | commitlint (hook + CI) | commitlint (hook + CI) | convention only |
| Coverage threshold | floor 80 + opt-in gate | ratchet 84/75/90/85 | 80, plus per-layer 95 | **none** |
| Workflow linting / pinning | partial | partial | partial | none |
| SBOM | CycloneDX per commit | generated, not kept | — | none |
| Provenance | in-toto + cosign | Sigstore + VSA by PR | — | none |
| Scheduled reminders | n8n + systemd | 6 cron workflows | — | none |
| Container | Dockerfile + hadolint | — | docker/ | none |
| Mutation testing | mutmut (opt-in) | mutation probes on fixtures | hypothesis present | none |

Two findings from the survey constrain what should be adopted rather than copied:

- **A check that tests for a string rather than a behaviour is worse than no check**, because it reports success. PROFESSOR-J's observability emits **zero spans** while its OTel board check passes on string-presence greps; USA's own docs claim 281 rules against a real 315 while `docs:check` passes because the stale paths are exempt; JARVIS's `deploy.yml` is live, broken, and unnoticed.
- **Every sibling needed an escape hatch for accumulated debt** once it had some (JARVIS: a mypy ceiling of 485 errors; USA: a complexity budget configured `warn` while documented as a hard cap; PROFESSOR-J: a coverage gate in one layer only). This repository has no debt of that kind yet, which is the whole argument for installing ratchets now.

The zero-runtime-dependency rule (charter §22) is unaffected by anything here: every tool below is a development or CI dependency, and none ships inside `catalog/`.

## Decision

### Added in Phase 1.5

| Check | Tool | Why this tool |
|---|---|---|
| **SAST** | `bandit` via ruff's `S` rules *plus* bandit itself | The `S` (flake8-bandit) subset is already written but its rules are **not enabled** — two `noqa: S101`/`BLE001` comments in the tree are currently dead because ruff never evaluates them. Enabling `S` closes that for free; standalone bandit adds the checks ruff does not port and matches all three siblings. |
| **Dependency vulnerabilities** | `pip-audit` | Python-native, reads the pinned lockfile, no service account. `osv-scanner` and `trivy` overlap it and are deferred (see below). |
| **Licence compliance** | `pip-licenses` with a deny-list, in `requirements-dev.txt` | Our own licence is Apache-2.0 and the repository is closed to contributions (`CONTRIBUTING.md`), so the rule is simple: a copyleft dev dependency is not acceptable. A deny-list is honest about what we reject; an allow-list of everything installed is maintenance churn. |
| **Dependency updates** | GitHub `dependabot.yml` | The only mechanism available that sees pinned versions in `.github/workflows/`, `requirements-dev.txt` and `pyproject.toml` together. Pinned `gitleaks` is invisible to it — see the reminder decision in ADR-0014. |
| **Commit-message validation** | **A first-party `scripts/check_commit_msg.py`** with unit tests, wired as a `commit-msg` hook and a CI step | See "Alternatives considered" — this is a deliberate departure from the siblings. |
| **Workflow linting** | `actionlint` (syntax, expressions, runner labels) and `zizmor` (security: template injection, credential persistence, over-broad permissions) | Both are single static binaries, pinned by version in CI like `gitleaks` already is. `zizmor` is the only check available that reads *permissions* semantics rather than syntax. |
| **Action pinning** | Every `uses:` pinned to a full commit SHA with the version as a trailing comment | Prevents a moved tag from changing what the pipeline runs. Neither USA nor JARVIS does this despite both auditing supply chains — the survey recorded it as a gap in all three. |

Adoption order is the Phase 1.5 work queue, not this list's order (see the phase plan).

### Deferred, with the condition that would reverse it

| Item | Reversal condition |
|---|---|
| **SBOM** (`cyclonedx-python`) | Reversed when this repository publishes an artifact. Generating an SBOM for a library consumed from source produces a file nobody consumes; USA generates one and does not attach or commit it, which is the failure mode being avoided. |
| **Provenance / attestation** (in-toto, Sigstore, cosign) | Reversed on the first published release. Attestation proves *how* an artifact was built; with no artifact distribution there is nothing to attest. |
| **Containerization** (Dockerfile, hadolint) | Reversed when a deployable service exists. The repository is a library and a study pipeline; a container would be a container for a `make` target. |
| **Mutation testing** (mutmut) | Reversed when the catalog's test suite has a stable coverage floor and a test-quality question the coverage number cannot answer. JARVIS runs it opt-in only and USA's mutation probes are fixture-specific, which is the honest version of this tool — a full mutation budget on 411 tests would dominate session cost. |
| **Doc-fact inlining** (USA's `usa:fact` markers, JARVIS's commit-stamped cache) | Reversed when a first drift incident shows `repo_status.py` cannot see it. Drift detection already works here; inlining prose facts duplicates their home and both siblings have live stale markers despite the machinery. |
| **Contract tests for catalog entry interfaces** | Reversed when a second entry consumes a first, or when an interface changes twice. Deferred rather than rejected: with five entries and one composition, a contract test suite would mostly restate the entry's own tests. |
| **`osv-scanner` / `trivy`** | Reversed when `pip-audit` misses an advisory that matters, or when non-Python artifacts exist. Three overlapping scanners on one dependency set is noise, and JARVIS runs all three. |
| **`tsconfig`-style complexity budget** | Reversed when a function is demonstrated too complex. USA documents a complexity budget its linter only warns about, so the breach exits 0 — a warn-only budget is a preference wearing a standard's clothes (§20). If added, it is added as an error with a stated ceiling. |
| **Self-auditing the release pipeline** | Reversed on the first release; nothing is released yet. |

### Rejected

| Item | Why rejected |
|---|---|
| **Coverage service** (Codecov, Coveralls) | Adds a network dependency and a third-party status check to enforce a number the local suite computes. `fail_under` in ADR-0012 achieves the enforcement without the dependency. |
| **Node toolchain for commit messages** (commitlint + husky + lint-staged) | All three siblings use it, and it is the standard. Rejected here because it introduces a second language ecosystem — `package.json`, a lockfile, a Node version pin, `node_modules` — into a repository whose entire premise is zero runtime dependencies and a single 59-file mypy-strict Python tree. The validation required is a header format, not a parser ecosystem; see Alternatives. |
| **Branch protection and required checks as code** | Not enforceable from the repository on this plan; JARVIS wrote `setup_branch_protection.py` and it returns 403 in practice. The rule stands as a documented process, and a script that cannot run would imply enforcement that does not exist. |
| **Workspace-level governance across the three sibling repos** | The workspace was deliberately decoupled (its own final report), and each repo is an independent peer. The survey's evidence supports this: the siblings' shared failure mode was proving things about themselves. Integration, where it happens, goes through contracts and adapters — never by nesting repositories. |
| **Copying JARVIS's local-CI bridge (n8n + systemd + status API)** | It exists because GitHub Actions is billing-blocked on that private repo, and it concedes it "cannot gate a merge regardless". We have working hosted CI; adopting a process-enforced substitute for a platform-enforced gate would be strictly weaker. |
| **Copying PROFESSOR-J's 8-check governance board wholesale** | Two of its eight checks are always-true placeholders that print ✅ unconditionally, and the OTel check passes on string presence while emitting zero spans. The *idea* of structural checks is adopted in ADR-0012 (import independence); the implementation is not. |
| **Suppression-by-risk-register** (JARVIS parses accepted risks at gate runtime to suppress findings) | Coupling findings suppression to a prose document whose backtick regex over-harvests (`app`, `dict`, `user` parse as package names) makes a gate's verdict depend on prose formatting. The register in ADR-0014 is for *governance*; suppressions stay explicit and inline per §28. |
| **Enabling all remaining ruff rule families** | The 19 configured families were chosen deliberately (ADR-0003). Breadth for its own sake produces dead `noqa`s — which is exactly the defect found here with `S101`/`BLE001` — unless the rule is enabled and its violations fixed. Enable `S`, fix its findings, and reject adding families without a demonstrated defect. |

## Consequences

- Every added tool becomes a pinned line in `requirements-dev.txt` (or a pinned binary version in CI) and must be installed by contributors. `make check` remains the local contract; the new scanners that need a binary are named as CI-only exemptions in ADR-0012's comparator.
- `bandit` and the newly-enabled ruff `S` rules will produce findings on existing code. The Phase 1.5 queue fixes them rather than suppressing them; §28 forbids weakening a check to pass, and a `noqa` added solely to silence a newly enabled rule would recreate the dead-`noqa` defect.
- A first-party commit-message checker means we own its correctness, including conventional-commit edge cases (scopes, breaking-change markers, merge commits, `fixup!`/`squash!`). It carries unit tests for that reason, and the rule list is deliberately the subset we actually use.
- Deferrals are conditions, not permissions to forget. Each appears in the phase plan's backlog with its reversal condition, so a future session can reverse one without re-deriving the argument.
- Rejecting the Node toolchain means our commit hook is not the industry-standard binary and will differ in corner cases from the siblings'. Accepted, and the difference is written down here.

## Alternatives considered

- **Adopt commitlint like all three siblings** — rejected on the second-toolchain cost above, but noted as the closest call in this ADR. The honest counter-argument: commitlint's conventional-commit grammar is battle-tested, ours will not be. The deciding factor is that our requirement is narrow (a typed header with an optional scope and a subject, plus the two merge/fixup exceptions), and a 60-line checker with tests is cheaper to own than a Node toolchain in a Python repository. If the checker ever needs to be more than that, this decision should be revisited.
- **Enable ruff's `S` rules and skip standalone bandit** — rejected: ruff ports a subset, and the survey's matrix shows all three siblings treat bandit as the floor. Using both is cheap; the overlap is reported once.
- **Generate and commit an SBOM now** — rejected: nothing consumes it, and USA's own SBOM is generated then discarded, which is how an unread artifact becomes a false claim of supply-chain rigour.
- **Adopt the workspace's archived governance layer for all repos** — rejected: deliberately decoupled, and the failure evidence (three repos each failing to verify their own claims) argues for per-repo verification, which is what this ADR strengthens.
- **Add a coverage *target* (e.g. 95%) rather than a ratchet** — rejected in ADR-0012; repeated here because it was a live proposal. Targets invite either an immediate red build or a lowered number.
- **Do nothing and rely on review** — rejected: the survey's evidence is that review did not catch these in three repositories, and §20 is explicit that an unenforced rule is a preference.

## Charter references

§3 (no cargo-cult engineering — every addition answers a demonstrated gap); §6 (claim labels — the sibling evidence is labelled as surveyed fact, and what was not independently re-verified is stated in the parent report); §11 (inspired-by is not derived-from — this ADR adopts *ideas* and rejects *implementations*, each recorded); §18 (testing and verification); §20 (enforced standards); §22 (dependency addition and the human-review gate); §26 step 4 (rejected options); §28 (never weaken a check); §31 (independence — the reason the cross-repo items are rejected).

## Taxonomy impact

None. Every item is verification machinery; no capability is added, advanced or deprecated.

## What was verified, and what was assumed

**Verified by the survey with executed commands:** the ruff `noqa` dead-rule finding; the sibling tool inventories in the table above; USA's stale rule count and JARVIS's red doc gates; PROFESSOR-J's zero emitted spans against a passing OTel check; the two CI/Makefile divergences in ADR-0012.

**Assumed, not verified:** that `bandit` and the ruff `S` rules will produce a manageable number of findings on this tree — the count is unknown until the work runs, and if it is large the phase plan's queue absorbs it before the gate is made blocking. That is stated here rather than discovered later.
