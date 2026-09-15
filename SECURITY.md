# Security Policy

## Supported versions

This project is at **Phase 1 (Seed)** — pre-release, no tagged versions, no
published artifacts. There is no supported release yet.

| Version | Supported |
|---|---|
| `main` (unreleased) | ✅ best-effort |
| Tagged releases | none exist yet |

Once tagged releases exist, this table will list them and their support windows.
See [`docs/roadmap.md`](docs/roadmap.md) for phase status.

## Reporting a vulnerability

Report security issues **privately**. Do not open a public issue for a
suspected vulnerability.

- Preferred: GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
  on this repository's **Security** tab.
- Alternative: open a minimal public issue asking for a private channel, and
  disclose no details until one is established.

Please include: affected version/commit, reproduction steps, impact, and any
suggested fix. If you are unsure whether something is a vulnerability, report it
privately anyway.

## What to expect

| Stage | Target |
|---|---|
| Acknowledgement | 7 days |
| Initial assessment | 14 days |
| Fix or mitigation plan | 30 days for HIGH/CRITICAL |

This is a single-maintainer project without a paid on-call rotation. Timelines
are best-effort, not contractual. Reporters who want public credit will receive
it in the advisory unless they ask otherwise.

## Scope and threat model

It is worth stating plainly what this project is and is not, because it shapes
what counts as a vulnerability:

**In scope:**

- `scripts/validate_catalog.py` and `scripts/repo_status.py` — the only
  executable code in the repository. Both are read-only tools that parse files
  in a repository the user names.
- The CI workflow and pre-commit hook — a bypass or injection here would
  undermine every quality gate the project relies on.
- Supply-chain integrity of the pinned development toolchain
  (`requirements-dev.txt`).
- Anything that would cause the repository's own governance claims to be false
  — for example a way to make `make status` pass while artifacts disagree with
  the taxonomy. Lifecycle honesty is a security property here.

**Out of scope / not yet applicable:**

- Model, prompt, agent, retrieval, and tool-execution code. **None exists yet.**
  When capabilities land in `catalog/`, the AI-era threat classes (prompt
  injection, excessive agency, insecure tool execution, cross-tenant retrieval
  leakage) become in scope and this section will be expanded.
- Sandbox or trust-boundary escapes — no sandbox exists yet.
- Denial of service against a service — nothing is deployed.

**Known limitations, stated honestly:**

- The scripts assume the repository they inspect is not actively hostile. A
  crafted `TAXONOMY.md` could cause incorrect drift reporting. It cannot cause
  code execution.
- There is no dependency vulnerability scanning in CI yet, and there are
  currently **zero runtime dependencies**. See the action backlog in
  [`docs/audits/2026-09-15-usa-audit.md`](docs/audits/2026-09-15-usa-audit.md).

## Licensing

This project is [Apache-2.0](LICENSE). Security research conducted in good
faith against your own copy, respecting this policy, will not be pursued.