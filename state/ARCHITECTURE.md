# ARCHITECTURE — System Design

> Living document. Update when system structure changes.

---

## Overview

`ai_infrastructure` is an AI infrastructure laboratory. It is NOT an agent framework. It is a collection of independent, composable, well-tested infrastructure capabilities for AI systems.

## Repository Layout

```text
ai_infrastructure/
├── CHARTER.md             # Constitution — mission, rules, quality bar
├── AGENTS.md              # Entry point for agent sessions (MACP protocol)
├── TAXONOMY.md            # Machine-readable capability registry
├── STATE.md               # Session state (legacy — see state/ directory)
├── state/                 # MACP coordination directory
│   ├── DASHBOARD.md       # Executive summary
│   ├── REGISTRY.md        # Active agents & file ownership
│   ├── INDEX.md           # Session log
│   ├── ARCHITECTURE.md    # This file
│   ├── DECISIONS.md       # Architecture decisions
│   ├── DEBT.md            # Technical debt
│   ├── BLOCKERS.md        # Active blockers
│   ├── sessions/          # Per-agent session files
│   ├── plans/             # Active plans
│   ├── conflicts/         # Documented conflicts
│   └── archive/           # Compressed old sessions
├── catalog/               # Implementation library
│   ├── tools/tool_registry/
│   ├── models/model_provider/
│   ├── agents/react_agent_loop/
│   ├── protocols/mcp_client/
│   ├── observability/execution_trace_recorder/
│   └── infrastructure/scanner/  (uncommitted)
├── research/              # Study findings by category
├── specifications/        # Designs before code
├── integrations/          # Compositions into working systems
├── docs/
│   ├── standards.md       # Enforceable rules mapped to checks
│   ├── development.md     # Environment setup
│   ├── roadmap.md         # Phase status
│   ├── phases/            # Executable phase plans
│   ├── decisions/         # ADRs
│   └── registry/          # Research registry
├── study_pipeline/        # Automated repo-study subsystem
├── scripts/               # Maintenance/validation scripts
├── tests/                 # Cross-cutting test suites
└── benchmarks/            # Benchmark methodology
```

## Capability Lifecycle

```text
DISCOVERED → RESEARCHED → UNDERSTOOD → DESIGNED → DECIDED → PROTOTYPED
    → IMPLEMENTED → TESTED → BENCHMARKED → INTEGRATED → MATURE → DEPRECATED
```

## Quality Gates

| Gate | Command | What it checks |
|---|---|---|
| Lint | `make lint` | ruff |
| Format | `make format` | black |
| Typecheck | `make typecheck` | mypy strict |
| Tests | `make test` | pytest |
| Coverage | `make coverage` | pytest-cov, floor 85% |
| Catalog contract | `make validate` | validate_catalog.py |
| Links | `make links` | check_links.py |
| Phase plan | `make phase-plan` | check_phase_plan.py |
| Status | `make status` | repo_status.py (drift detector) |
| SAST | `make sast` | bandit + ruff S |
| SCA | `make sca` | pip-audit (2 sources) |
| Licence | `make licence` | allow-list with fail-on-unknown |
| Import independence | `make structural` | import-linter |
| Workflows | `make workflows` | actionlint + zizmor |
| Risks | `make risks` | check_risks.py |
| Deferred | `make deferred` | check_deferred.py |
| Commit message | commit-msg hook | check_commit_msg.py |

## Coordination

Multi-agent work follows the MACP protocol, canonical text at
[`docs/macp-protocol.md`](../docs/macp-protocol.md) (amendment rationale:
[`docs/macp-protocol-review.md`](../docs/macp-protocol-review.md)).
`AGENTS.md` is the entry digest; on conflict the canonical text wins.

## Design Principles

1. **Zero runtime dependencies** — stdlib only
2. **Composability** — capabilities compose through explicit interfaces
3. **Honesty** — status claims must match artifacts (enforced by `make status`)
4. **Research before implementation** — understand before building
5. **Decide before building** — ADR for every meaningful decision
6. **Test everything** — unit, integration, contract, property-based, failure-injection
7. **No cargo-cult** — complexity must earn its place
