# Verification Package

Installable verification pipeline for any repository. Provides pre-commit hooks, pre-push hooks, full suite runner, and GitHub Actions CI — all wired together with zero redundancy.

## What's Inside

```
verification-package/
├── hooks/
│   ├── pre-commit          # Fast staged-files checks + branch enforcement
│   ├── pre-push            # Typecheck + branch enforcement before push
│   ├── commit-msg          # Conventional Commits header check
│   ├── agent-claude-code.sh # Claude Code PreToolUse enforcement
│   └── agent-opencode.sh    # OpenCode preToolUse enforcement
├── scripts/
│   ├── verify-full.sh      # Full suite runner (canonical entry point)
│   ├── check-branch.sh     # Standalone branch check
│   ├── branch-watcher.sh   # Background branch monitor (start|stop|status)
│   └── install-verification.sh  # One-command installer
├── config/
│   └── branch-guard.conf   # Protected branches, naming pattern, agent policy
├── docs/
│   └── github-rulesets.md  # Server-side enforcement guide
├── .github/workflows/
│   └── ci.yml              # GitHub Actions CI workflow
└── README.md               # This file
```

## Install

```bash
./verification-package/scripts/install-verification.sh
```

This installs git hooks, copies the verify-full script, adds CI workflow, and appends Makefile targets.

## Usage

| Command | What it runs | When |
|---|---|---|
| `make verify-commit` | Format, lint, syntax, secrets (staged files only) | Before every commit |
| `make verify-push` | Typecheck + unit tests | Before every push |
| `make verify-full` | Full suite (all properties) | Before pushing to remote |
| `make verify-ci` | Same as verify-full | Local CI simulation |

## Pipeline Flow

```
working tree → commit-msg → pre-commit → pre-push → push → remote CI → merge gate
```

| Stage | What runs | Blocking | Time |
|---|---|---|---|
| commit-msg | Conventional Commits header | Yes (local) | <1s |
| pre-commit | Format, lint, syntax, secrets | Yes (local, advisory) | ~10s |
| pre-push | Typecheck, unit tests | Yes (local, advisory) | ~1-2min |
| remote CI | Full suite + security + coverage | Yes (authoritative) | ~2-5min |
| merge gate | Required checks pass | Yes (platform) | — |

## Branch Enforcement

5 layers, config-driven via `config/branch-guard.conf`:

1. **pre-commit** — blocks commits on protected branches + naming violations
2. **pre-push** — blocks pushes on protected branches + naming violations
3. **background watcher** — `bash scripts/branch-watcher.sh start` monitors every 30s, warns/logs on protected branch
4. **agent hooks** — `agent-claude-code.sh` + `agent-opencode.sh` fire before any tool use, require `agent/` prefix
5. **GitHub rulesets** — server-side hard boundary, see `docs/github-rulesets.md`

## Design Principles

1. **Single source of truth** — `verify-full.sh` is the canonical entry point. Hooks and CI both call it.
2. **No false-greens** — Every check uses proper exit codes. No `|| true`, no `continue-on-error`.
3. **Tiered, not monolith** — Each property is addressable individually (`verify-full.sh lint`, `verify-full.sh type`, etc.).
4. **Defense-in-depth** — Pre-commit runs a subset for fast feedback. CI runs the full suite for independent verification.
5. **Idempotent** — Installer can run multiple times without duplication.
6. **Branch enforcement** — Commits on `main`/`master` blocked. Naming convention required. Agents require `agent/` prefix.

## Customize

Edit the hooks and scripts to match your stack. The package supports Python and TypeScript/JavaScript out of the box. Add new properties by creating a `verify-<property>` function in `verify-full.sh` and adding it to the CI workflow.
