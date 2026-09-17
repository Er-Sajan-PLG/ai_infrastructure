# Architecture Decision Records

Records of significant decisions, per charter §12. Format defined by [ADR-0000](0000-adr-format.md).

| ADR | Title | Status |
|---|---|---|
| [0000](0000-adr-format.md) | ADR Format | Accepted |
| [0001](0001-bootstrap-structure.md) | Bootstrap the Repository as a Knowledge/Code Plane Split | Accepted |
| [0002](0002-license-selection.md) | License Selection (Apache-2.0) | Accepted |
| [0003](0003-toolchain-and-enforcement.md) | Toolchain, Enforcement, and the Drift Detector | Accepted |
| [0004](0004-testing-enforcement-holes.md) | Close the Testing-Enforcement Holes | Accepted |
| [0005](0005-phase-model-and-plans.md) | Name the Foundation Work "Phase 0"; add phase plans | Accepted |
| [0006](0006-tool-registry.md) | `tool-registry`: a standalone, JSON-Schema-native registry | Accepted |
| [0007](0007-model-provider-abstraction.md) | `model-provider-abstraction`: own the shape, not the socket | Accepted |
| [0008](0008-react-agent-loop.md) | `react-agent-loop`: a bounded dispatcher, not a reasoner | Accepted |
| [0009](0009-mcp-client.md) | `mcp-client`: implement the legacy era, and put the approval before the call | Accepted |
| [0010](0010-execution-trace-recorder.md) | `execution-trace-recorder`: record flat, bound everything, capture nothing by default | Accepted |
| [0011](0011-phase-1-5-hardening.md) | Name the pre-Phase-2 hardening work "Phase 1.5" | Accepted |
| [0012](0012-gate-architecture.md) | Gate architecture: CI runs the same gates as local | Accepted |
| [0013](0013-verification-breadth.md) | Verification breadth: which checks are added, deferred, or rejected | Accepted |
| [0014](0014-governance-drift.md) | Governance drift: an accepted-risk register and scheduled reminders | Accepted |
| [0015](0015-makefile-shell-hardening.md) | Makefile shell hardening and the parity contract with CI | Accepted |
| [0016](0016-coverage-policy.md) | Coverage measurement: a regression floor plus change-scoped gating | Accepted |
| [0017](0017-structural-checks.md) | Structural checks: import-linter and a first-party collectability gate | Accepted |
| [0018](0018-security-tooling.md) | Security tooling: SAST, SCA, licences, workflow linting, and version pinning | Accepted |
| [0019](0019-commit-message-validation.md) | Commit-message validation: header only, first-party, with a visible escape hatch | Accepted |
| [0020](0020-deferral-register.md) | What is deferred to scale, and the register that holds it | Accepted |
| [0021](0021-study-pipeline-architecture.md) | Study pipeline: static-only, never executes studied code, stdlib only, emits proposals not code | Accepted |
| [0022](0022-configuration-taxonomy-category.md) | New taxonomy category `config/` — configuration and settings infrastructure (15/25 studied repos) | Accepted |
| [0023](0023-caching-taxonomy-category.md) | New taxonomy category `caching/` — response caching, AI-specific form (14/25 studied repos) | Accepted |
| [0024](0024-agent-repository-configuration.md) | New taxonomy category `agent-config/` — agent instruction files in repositories (18/25 studied repos) | Accepted |

## When an ADR is required

Charter §12 and §22: why implement or not; why this architecture; why this dependency or abstraction; why adopt or reject a protocol; why replace or deprecate; why change a trust boundary; any human-review gate item.

## Open items requiring human decision

- **Contribution policy — DECIDED 2026-09-16: remains closed.** Apache-2.0 is in place and no CLA/DCO-with-relicense-grant has been adopted, so external contributions are not accepted ([ADR-0002](0002-license-selection.md), [`../CONTRIBUTING.md`](../../CONTRIBUTING.md)).

  This was reviewed and the maintainer chose to keep the repository closed rather than adopt a CLA or DCO now. The reasoning: the ability to relicense *future* versions survives only while the maintainer is sole copyright holder, and it is destroyed by the first accepted outside contribution. Nothing in Phase 1 needs outside contributions, so keeping it closed costs nothing today and preserves the whole option. Adopting a policy later remains possible at any time; the reverse is not.

  **Recorded without a new ADR deliberately.** No decision was *changed* — ADR-0002 and `CONTRIBUTING.md` already stated this policy, and the review confirmed them. Burning an ADR number on a non-change would create a record implying a change occurred. If a CLA or DCO is ever adopted, that *is* a change and takes an ADR superseding the note in ADR-0002.

  It stays listed here, rather than being deleted, because it is a **standing choice with a known cost**: it blocks an entire class of work, and the next session should see that cost rather than have it silently disappear.