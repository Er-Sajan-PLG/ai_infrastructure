# Verification Package

Installable verification pipeline for any repository. Provides pre-commit hooks, pre-push hooks, full suite runner, and GitHub Actions CI — all wired together with zero redundancy.

## What's Inside

```
verification-package/
├── hooks/
│   ├── pre-commit          # Fast staged-files checks (~10s)
│   ├── pre-push            # Typecheck + fast tests (~1-2min)
│   └── commit-msg          # Conventional Commits header check
├── scripts/
│   ├── verify-full.sh      # Full suite runner (canonical entry point)
│   └── install-verification.sh  # One-command installer
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

## Design Principles

1. **Single source of truth** — `verify-full.sh` is the canonical entry point. Hooks and CI both call it.
2. **No false-greens** — Every check uses proper exit codes. No `|| true`, no `continue-on-error`.
3. **Tiered, not monolith** — Each property is addressable individually (`verify-full.sh lint`, `verify-full.sh type`, etc.).
4. **Defense-in-depth** — Pre-commit runs a subset for fast feedback. CI runs the full suite for independent verification.
5. **Idempotent** — Installer can run multiple times without duplication.

## Customize

Edit the hooks and scripts to match your stack. The package supports Python and TypeScript/JavaScript out of the box. Add new properties by creating a `verify-<property>` function in `verify-full.sh` and adding it to the CI workflow.
