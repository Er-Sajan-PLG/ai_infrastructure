# ADR-0015: Makefile shell hardening and the parity contract with CI

- **Status:** Accepted
- **Date:** 2026-09-17
- **Phase:** 1.5 (Hardening)
- **Supersedes:** none
- **Related:** [ADR-0012](0012-gate-architecture.md), [ADR-0017](0017-structural-checks.md), [`../standards.md`](../standards.md)

## Context

Phase 1.5 was planned after a survey of sixteen mature infrastructure projects
and a follow-on SOTA comparison (475 searches). The single highest-severity
finding was not a missing capability: it was that **a gate in this repository
could fail and still report success.**

`Makefile` began with `SHELL := /bin/bash`. With that alone, GNU Make runs each
recipe *line* in a separate shell and inspects only the final line's exit code.
Consequences, all reachable in the existing file:

- `failing-command | tee log` exits 0, because the shell reports `tee`'s status.
- A multi-line recipe whose second line fails passes.
- A `cd` or variable assignment on one line does not survive to the next.

The second point is not specific to this repository. GitHub's default runner
shell for `run:` steps is `/usr/bin/bash -e {0}` — `-e` **without** `pipefail`
(`actions/runner-images#4459`). A failing test piped to `tee` in a workflow step
reports success there too. The defect is systemic, not local sloppiness.

### What was verified, not assumed

The claim was reproduced rather than reasoned about. Two side-by-side
Makefiles (`/tmp/shellproof/Makefile.old` and `Makefile.new`) were built around
a recipe of the form `false | tee /tmp/gate-report`. Results:

| Preamble | Exit code | Printed |
|---|---|---|
| `SHELL := /bin/bash` | 0 | `GATE REPORTED SUCCESS` |
| Hardened (see Decision) | 2 | failure reported |

This matters for how the ADR is written: the finding is an **EXPERIMENTAL
RESULT**, not an inference from documentation.

## Decision

Adopt a hardened shell preamble in `Makefile`:

```make
SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules
.DEFAULT_GOAL := help

ifeq ($(origin .RECIPEPREFIX), undefined)
  $(error GNU Make 4.0 or later is required (for .RECIPEPREFIX and .ONESHELL))
endif
```

Each line, and why:

- `.ONESHELL` — one shell per recipe, so multi-line recipes behave as written.
  Without it, `-e` does not help across lines, because each line gets its own
  shell.
- `-eu -o pipefail` — `-e` stops on error, `-u` makes an unset variable an
  error rather than an empty string, `pipefail` is the fix for the reproduced
  defect.
- `.DELETE_ON_ERROR` — a recipe that fails partway does not leave a
  half-written artifact that a later target mistakes for a complete one.
- `--warn-undefined-variables` — reports a typo'd variable at parse time.
- The `.RECIPEPREFIX` guard — fails loudly on a Make older than 4.0 rather than
  silently ignoring the settings above.

**Also decided:** CI and the Makefile are held together by a test.

`.github/workflows/ci.yml` now invokes gates only through `make`, and
`tests/test_ci_parity.py` fails the build if the two disagree about which gates
exist. The gate list is obtained from `make print-gates` — the test asks make
what the Makefile says rather than re-parsing it, so the test cannot become a
second source of truth about the first.

## Why a parity test and not a convention

The workflow already *claimed* it "runs the same gates as `make ci`". That
claim was **false**: CI ran `scripts/repo_status.py` while `make ci` did not
include `status` at all, coverage was produced by a different route than
`make test`, and the workflow never invoked `make`. Three drifts, in a file
whose opening comment asserted there were none.

A documented guarantee with no check is a preference (charter §20). The test is
what makes the guarantee real.

Three implementation details in that test are load-bearing and were each
arrived at by hitting the problem:

1. **The MAKELEVEL trap.** `make print-gates` runs inside pytest. If pytest is
   itself running under make — as `make ci` does — the nested make inherits
   `MAKELEVEL` and writes `make[1]: Entering directory ...` to **stdout**, whose
   words then parse as gate names. A drift test in the wild "passed locally
   because pytest was invoked directly and failed in CI because the runner goes
   through the Makefile". The test therefore passes `--no-print-directory`,
   scrubs `MAKELEVEL`/`MAKEFLAGS`/`MFLAGS`, and asserts the output contains
   nothing that is not a bare target name.
2. **A real YAML parser.** `yaml.safe_load`, never a regex. A project that
   scanned workflow YAML with regexes rewrote its scanners eighteen times
   "while CI stayed fully green".
3. **An anti-silent-skip floor.** If discovery breaks the test would compare
   two empty sets and pass having verified nothing, so an empty result is a
   failure.

## Options considered

| Option | Verdict | Why |
|---|---|---|
| Keep `SHELL := /bin/bash` | **Rejected** | Reproduced as a false-success path. Every other gate in the file is unenforceable while it stands. |
| `set -euo pipefail` per recipe | **Rejected** | Repeats in ~30 recipes; the first one that omits it silently reintroduces the defect. Must be global. |
| `SHELL := bash -euo pipefail -c` inline | **Rejected** | Works, but hides the settings in one long line and cannot express `.ONESHELL`, which is required for `-e` to apply across a multi-line recipe. |
| Rewrite gates as `scripts/run_gates.py` | **Rejected** | Would replace a well-understood tool with a bespoke one, and Make's dependency graph is genuinely useful. Also: the SOTA survey found no mature project that abandoned Make for this. |
| Hand-maintained parity documentation | **Rejected** | This is exactly the artifact that was already false. Documentation cannot enforce. |
| `actionlint` / `zizmor` for parity | **Rejected (for this purpose)** | They validate workflow *validity* and *security*. Neither reads a Makefile or compares gate sets. They are adopted separately in ADR-0018 for what they do cover. |
| Do the parity check in CI as a shell step | **Rejected** | Then the checker itself is not tested, and a broken checker reports success. A pytest test runs under the same suite as everything else and is covered by the coverage gate. |

## Consequences

**Positive.** A failing gate can no longer report success, locally or in CI. CI
and local runs are provably equivalent. The `entering directory` class of
output-parsing bug is handled explicitly rather than discovered later.

**Negative / accepted costs.**

- Every recipe now runs under `-u`, so an unset variable that used to expand to
  an empty string becomes a hard error. Two existing recipes were adjusted;
  more may surface on future edits. This is the intended direction — a silent
  empty string in a gate command is how a gate becomes a no-op.
- `.ONESHELL` changes the semantics of every existing multi-line recipe. They
  were reviewed, but a recipe that accidentally *relied* on per-line isolation
  would now behave differently. None did.
- More Makefile, which is not a popular surface. Mitigated by the comment block
  at the top explaining each setting, so the next editor does not remove them
  as redundant.
- The parity test is a new failure mode: a legitimate CI change now requires a
  matching Makefile change. That is the point, and `_PR_ONLY_GATES` documents
  the one deliberate asymmetry (`diff-coverage`).

## Compliance

- [`CHARTER.md`](../../CHARTER.md) §20 — a rule with no check is a preference.
  This ADR is the check.
- §28 — never weaken a check. The hardened preamble makes weakening harder,
  not easier.
- §29 — pipeline is infrastructure too.
- Enforced by: `make check` (via `tests/test_ci_parity.py`) and every recipe in
  `Makefile`.
