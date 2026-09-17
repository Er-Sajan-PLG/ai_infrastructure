# ADR-0021 — Study Pipeline Architecture

- **Status:** Accepted
- **Date:** 2026-09-17
- **Supersedes:** —
- **Superseded by:** —

## Context

Charter §29 says *"build the study pipeline; point it at 20–30 major repos"*, and
§30 places that in Phase 2. `study_pipeline/` has existed since Phase 1 as a
**declared seam** — two READMEs describing eight intended steps and five planned
components, and zero lines of Python.

This ADR is written **before** the pipeline is built, per §8 (*decide before
building*) and §12 (*record the decision in the same session*). The decision is
not "should Phase 2 exist" — that is settled by §29/§30 and
[ADR-0005](0005-phase-model-and-plans.md). The decisions are the ones the seam's
README describes but does not resolve:

1. **How the pipeline executes untrusted third-party code**, or whether it does.
2. **What "recreate" is allowed to produce**, given §9 forbids `COPY → RENAME →
   MODIFY` and ADR-0002 blocks importing third-party source into `catalog/`.
3. **What the pipeline is written in**, given the repository has *zero runtime
   dependencies*.
4. **How the pipeline avoids becoming the project**, which its own README names
   as a risk.

### Verified constraints (not assumptions)

- **No runtime dependencies.** `pyproject.toml` declares `dependencies = []`.
  Adding one is a human review gate (§22) and a separate ADR.
- **The pipeline clones attacker-controlled content.** A target repository's
  `setup.py`, `conftest.py`, `.pth` files, or Makefile all execute on import or
  invocation. This is a **trust-boundary change**, which §22 lists as a stop
  condition.
- **Git and curl are present** on this machine; network access to GitHub works
  (`git ls-remote https://github.com/psf/requests` succeeded, verified
  2026-09-17).
- **Python 3.14.7 locally**; CI pins 3.12.
- Five catalog entries and the `integrations/` composition already exist, so the
  pipeline has a real taxonomy to classify into rather than an empty one.

## Decision

### Decision 1: the pipeline NEVER executes studied code

This is the load-bearing decision, and it is a **capability restriction, not a
safety guideline**. The pipeline performs only static operations:

- `git clone --depth 1` into a **non-importable** workspace directory
  (`.study-workspace/`, gitignored, never on `sys.path`).
- `git rev-parse HEAD` to record the exact commit studied.
- Read files as **data** (bytes → text), never `import`, never `exec`, never
  `subprocess` into the clone, never `pip install` from it.
- Inventory: file counts by extension, top-level layout, presence of marker
  files, declared dependencies **parsed from manifests** rather than resolved.

**The pipeline may not `import`, `exec`, `eval`, or run any file from a studied
repository, and may not install its dependencies.** There is no configuration
flag to enable this. It is not a mode.

The asymmetry that decides it: the pipeline needs a *structural map* to produce
a study report, and a structural map is obtainable statically. Executing a
target would buy richer data (resolved dependency graphs, discovered test
counts) at the cost of running arbitrary code from repositories chosen
specifically because they are large and unfamiliar. For a subsystem whose
deliverable is *knowledge*, that trade is not close. A tool that executes what
it studies is a supply-chain surface with a research report attached.

### Decision 2: "recreate" produces a PROPOSAL, never code in `catalog/`

The pipeline writes **one Markdown report per studied repository** into
`study_pipeline/studied_repos/<project>.md`. It writes nothing into `catalog/`,
`integrations/`, or any importable path. There is no code-generation step.

The README's step 5 ("RECREATE a clean standalone version") is therefore
**downgraded from artifact to proposal**: the report contains a *design sketch*
— the pattern's boundary, its interface, its trade-offs, and what to avoid —
and a human or agent session decides whether to build it, in a separate act with
its own ADR. This resolves the tension the README left open:

- §9's prohibition is absolute, and an automated recreator is a laundering
  machine by construction — it cannot distinguish *understanding* from
  *paraphrasing* without semantic judgement it does not have.
- §11 requires *inspired-by* to be distinguished from *derived-from*, which
  requires knowing whether any expression was carried across. A generator that
  has read the source cannot honestly make that claim about its own output.
- ADR-0002 blocks importing third-party source into `catalog/` regardless.

A proposal is reviewable, citeable, and reversible. Generated code in `catalog/`
would be none of those.

### Decision 3: stdlib only — no runtime dependency is added

The pipeline is Python, type-hinted, mypy-strict, per §13, using **only the
standard library**. Verified sufficient for every static operation above: `pathlib`/
`os` for traversal, `subprocess` for the fixed-argv `git clone`/`rev-parse`,
`json`/`tomllib`/`re` for manifest parsing, `dataclasses`/`typing` for the model,
`argparse` for the CLI, `hashlib` for content hashing.

This is not minimalism for its own sake. A dependency that parses other
projects' manifests is a parser fed arbitrary input from the least trusted
source available; the standard library's `tomllib` and `json` are already
well-tested against malformed input and already present. Adding a YAML or
tree-sitter dependency would add a supply-chain surface to a subsystem whose
whole justification is *not* trusting the studied code.

If a future step genuinely needs a parser the stdlib lacks, that is a new ADR
and a §22 review — not a quiet addition.

### Decision 4: the pipeline is a library with a thin CLI, and it is tested

`study_pipeline/` contains importable, independently testable functions; the
component scripts named in the README become modules, and `scripts/study_repo.sh`
(or a `make study` target) is a thin wrapper. §29 is explicit that the pipeline
*"is infrastructure too"*, so it lands with:

- unit tests for every pure function (classification, manifest parsing,
  inventory, report rendering) using **fixtures on disk**, not network calls;
- at least one test asserting the no-execution guarantee in Decision 1, so the
  restriction is enforced by a check rather than by reviewer memory (§20);
- a `study_pipeline/tests/` directory that **collects** — the Phase 1.5
  `collectability` gate will refuse an empty one.

Network-dependent end-to-end tests are excluded from the default run and must be
opt-in, so `make check` never depends on GitHub being reachable.

### Decision 5: effort is capped, and the cap is checkable

The README's own risk table says *"pipeline becomes the project — cap effort"*.
The cap is expressed as exit criteria, not intent: the pipeline is done when it
can produce a correct report for a target repository, and **breadth (20–30
repos) is separate work that the pipeline enables**. Pipeline work that does not
increase the number or quality of committed reports is out of scope.

## Options considered

| Option | Verdict | Why |
|---|---|---|
| **Static analysis only; never execute studied code** | **Chosen** | Produces the structural map the deliverable needs, at zero execution risk. |
| Execute studied code in a container/sandbox to enrich the map | **Rejected** | No container infrastructure exists (ADR-0013 deferred containerization), and building one to study repos inverts the cost — the sandbox becomes a larger project than the study. Revisit if resolved dependency graphs become a hard requirement. |
| Execute studied code in a subprocess with `--no-site-packages` | **Rejected** | Defence in depth, not a boundary. `conftest.py` runs on collection; `setup.py` runs on install; both are ordinary Python with full process privileges. A subprocess is not a sandbox. |
| Vendor the studied repos' own analysers (e.g. tree-sitter) | **Rejected** | Adds a runtime dependency to a zero-dependency repo (§22) and a parser surface fed untrusted input, for a benefit the stdlib already covers at the fidelity needed. |
| Generate "recreated" code into `catalog/` automatically | **Rejected** | §9; §11 cannot be honestly satisfied; ADR-0002 blocks it. This is the laundering risk the README names. |
| Use an LLM to summarise studied repos | **Rejected** | Importable into the pipeline only as a network dependency to `model_provider`; the *understanding* step is exactly where human review is required (§6 evidence classification, §22). An agent session reads the report, not the pipeline. |
| Study repositories by fetching the GitHub API instead of cloning | **Rejected (deferred)** | Lower risk (no clone) but the API returns a partial tree, rate-limits unauthenticated requests, and cannot hash file contents for provenance. Revisit as an *additional* mode; cloning with `--depth 1` is not the bottleneck. |
| Do nothing / keep the seam empty | **Rejected** | §29/§30 require it; the taxonomy's ≥3 new patterns cannot be discovered without it. |
| Add `pyyaml` for manifest parsing | **Rejected** | `tomllib` is stdlib and `requirements*.txt` is line-oriented; YAML appears in studied repos' CI, not in the dependency data the inventory needs. |

## Consequences

**Positive.** The pipeline can study any repository, including hostile ones,
with no execution surface. Reports are plain Markdown, diffable and reviewable
like every other artifact here. The stdlib-only choice means the pipeline cannot
itself become a dependency-review problem, and the no-execution rule is testable
— a check exists rather than a convention.

**Negative / accepted costs.**

- The structural map is **shallower** than a resolved dependency graph or a real
  test count. Reports will say "declares 14 dependencies" not "resolves to 63
  packages", and "212 test files" not "1,504 tests pass". This is a genuine
  loss and is recorded so a future session does not mistake the limit for an
  oversight. Reversal condition: a concrete question the structural map cannot
  answer, recurring across several reports.
- `git clone --depth 1` still writes **up to hundreds of MB** into
  `.study-workspace/`. Clone size is bounded by the target, not by us; disk
  hygiene (prune after study) is a real concern and is handled in the
  implementation, not hand-waved.
- No automatic code generation means the *recreate* step is human-paced. That is
  intentional and is the point, but it means the ≥3-new-patterns criterion
  depends on session effort, not on the pipeline running.
- A stdlib-only inventory will **miss** patterns expressed only in framework
  DSLs it cannot parse. Recorded as a deferral if it proves limiting.

## Compliance

- §8 — decided before building; rejected options recorded above.
- §9 — the recreate step cannot launder code because it does not emit code.
- §11 — provenance records the studied commit; `code_reused: false` is
  structurally guaranteed, since the pipeline cannot write to `catalog/`.
- §13 — Python, type-hinted, mypy strict, ruff, black.
- §20 — the no-execution guarantee is enforced by a test, not by a comment.
- §22 — the trust boundary is analysed above; no runtime dependency is added; no
  code from a studied repository enters the repository.
- §29 — the pipeline is treated as infrastructure: tested, documented, versioned.
- §30 — Phase 2 scope; adds no capability to `TAXONOMY.md`.
