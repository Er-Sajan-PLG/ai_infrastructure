# ADR-0003 — Toolchain, Enforcement, and the Drift Detector

- **Status:** Accepted
- **Date:** 2026-01-01
- **Supersedes:** —

## Context

ADR-0001 established the repository skeleton but left the working environment undefined: no `pyproject.toml`, no pinned tooling, no way to run the checks the standards describe. Before any capability research begins, the repository must be able to *enforce* its own rules, because the charter's rules are unusually easy to violate silently:

- Charter §4: lifecycle status must reflect artifacts that exist — the failure mode is a label quietly outliving its evidence.
- Charter §13: implementations must be type-hinted, formatted, tested — unenforceable without tooling.
- Charter §21: "definition of done" is a checklist — a checklist nobody can run is decoration.
- Charter §23/§30: the repository must survive years of sessions; a session a year from now must verify against the *same* checks.

The environment must therefore do two things: make the standards executable, and make drift *loud* rather than silent.

## Decision

**1. `uv` for environment management, with a workspace-local cache.**
`pyproject.toml` declares intent; `requirements-dev.txt` is the pinned lock file. `uv` was chosen over plain `venv`+`pip` because it is already installed, is fast, and resolves the pinned set deterministically. `UV_CACHE_DIR` is redirected to `.uv-cache/` inside the workspace because the default `~/.cache/uv` was not writable (observed: `Read-only file system (os error 30)`).

**2. ruff for linting, black for formatting — only one formatter.**
Ruff covers lint rules broadly; black is the reference formatter. mypy runs `strict = true`. Pinned to `ruff==0.16.7`, `black==26.5.1`, `mypy==2.3.1`, `pytest==9.1.1`. Rationale: charter §13 states type-hinted and formatted Python as a requirement, and §19/§23 imply results must be comparable across time. Unpinned tooling silently changes what "passes" means.

> **Amendment (session 3).** This ADR originally configured *both* ruff's
> formatter and black, justified as "two agreeing formatters are cheap
> insurance, and disagreement is a useful signal." That justification was
> wrong and has been removed: two opinionated formatters that agree provide no
> additional coverage, and disagreement would be a configuration bug rather
> than a signal. The repository now uses **ruff for linting only** and **black
> for formatting only**. `[tool.ruff.format]` remains in `pyproject.toml` with
> a comment recording the deliberate choice, because ruff reads that section
> if it is ever invoked. This keeps one convention for future catalog entries
> to inherit.

**3. No runtime dependencies.**
`[project].dependencies` is empty and documented as such. Charter §20 lists unnecessary dependencies as something to avoid; the first two capabilities are specified to run on the standard library. Adding one is a charter §22 human gate, recorded as an ADR.

**4. A Makefile as the single entry point for every check.**
`make check` runs lint, typecheck, catalog validation, and tests. The reasoning: if a rule has no runnable command, it is a preference, and charter §20 forbids presenting preferences as standards.

**5. `scripts/repo_status.py` — a governance drift detector.**
This is the load-bearing decision. The script parses `TAXONOMY.md` and compares each capability's claimed stage against the filesystem:

| Claimed stage | Required artifact |
|---|---|
| `RESEARCHED`+ | non-empty `research_records` |
| `DESIGNED`+ | `specifications/<id>.md` exists |
| `DECIDED`+ | `decision` is not `pending` |
| `IMPLEMENTED`+ | `implementation` path exists |
| `TESTED`+ | `tests` path exists |
| `BENCHMARKED`+ | `benchmarks` non-empty |

It also verifies `depends_on` targets exist and do not lag their dependents. Exit code `1` on any violation.

**6. Enforcement at two layers: a local git hook and CI.**
`.git/hooks/pre-commit` runs the gates relevant to staged files; `.github/workflows/ci.yml` runs all of them plus coverage. The hook is installed by `make install-hooks` (it cannot be versioned directly by git).

**7. `docs/standards.md` maps every rule to its check — and states what is *not* automated.**
Explicitly listing the unautomatable rules (whether tests cover real failure modes, whether research is sufficient) prevents the inverse drift: assuming a green pipeline means the work is sound. Charter §18 is explicit that a passing demo is not evidence of correctness.

## Consequences

- A session that over-claims a lifecycle stage is now blocked from committing, and CI fails. The charter's hardest rule is mechanically enforced rather than culturally hoped-for.
- The toolchain adds five development dependencies. This is deliberate; they are dev-only and pinned.
- `repo_status.py` must be kept in sync if the taxonomy format changes. Its parser is intentionally small and covered by 20 tests, including the failure paths.
- The pre-commit hook is per-clone and not tracked by git; a fresh clone must run `make install-hooks`. CI is the backstop.
- Writing the tests found a genuine parser bug (block-style YAML lists were silently dropped), confirming the value of testing the tooling itself.

## Alternatives considered

- **No tooling until the first implementation exists** — rejected: standards that are not enforced from the start are the ones that never get enforced; and the charter's §4 rule concerns the *taxonomy*, which exists now.
- **`venv` + `pip` only** — rejected: works, but slower and without a lock file; `uv` is present and `make setup` remains one command either way. `docs/development.md` documents the `pip` fallback.
- **ruff only, no black** — considered; rejected because two agreeing formatters are cheap insurance, and disagreement between them is a useful signal. Recorded here so a future session knows the redundancy is intentional.
- **Pre-commit framework (`pre-commit` package)** — rejected: an extra dependency whose only job is to run five local commands; the shell hook and CI already do it.
- **A YAML library to parse `TAXONOMY.md`** — rejected on charter §20 grounds: the format is under this repository's control, and a 60-line parser with tests is preferable to a dependency. If the taxonomy outgrows it, revisit.
- **Trusting the taxonomy and skipping the drift check** — rejected: this is precisely the decay the charter warns about, and the detector costs one script.

## Charter references

§3 (complexity earns its place), §4 (honest status), §13 (standards), §18 (testing), §19 (benchmarking), §20 (avoid unnecessary dependencies), §21 (definition of done), §22 (human review gates), §23 (long-lived), §28 (never weaken a check).

## Taxonomy impact

None. All seven capabilities remain `DISCOVERED` with `decision: pending`; the drift detector confirms this is consistent with the (empty) artifact set.