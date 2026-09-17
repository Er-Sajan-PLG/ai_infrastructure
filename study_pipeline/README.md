# Study Pipeline

Automated repository-study subsystem (charter §29). It clones an open-source
repository, maps its structure, extracts candidate infrastructure patterns,
classifies them against [`TAXONOMY.md`](../TAXONOMY.md), and writes a Markdown
report. Architecture and the reasoning behind it:
[ADR-0021](../docs/decisions/0021-study-pipeline-architecture.md).

**Status: Track 2A complete.** The machinery is built and tested. Reports are in
[`studied_repos/`](studied_repos/).

## The one rule

> **The pipeline never executes, imports, or installs the code it studies.**

It is not a mode, not a flag, and not a promise. The studied repository is
cloned and read as data — no import, no install, no subprocess inside it. This is
enforced by
[`tests/test_no_execution.py`](tests/test_no_execution.py), which is a static AST
scan of the pipeline's own source *plus* a behavioural test against a fixture
repository whose module writes a sentinel file on import. Each check has been
proven to fail on an injected violation.

Consequently the report distinguishes sharply between what a *reader* can see
and what the pipeline can: declared dependencies are counted, never resolved;
test *files* are counted, never run; pattern detection matches names and
manifests, never source semantics.

## Usage

```bash
make study URL=https://github.com/owner/repo          # write a report
make study URL=... STUDY_FLAGS=--dry-run              # print, write nothing
make study-clean                                      # remove clones
make test-network                                     # the network-marked tests
```

The CLI is thin over the library and can also be run directly:

```bash
python -m study_pipeline https://github.com/owner/repo
```

Allowed hosts are `github.com`, `gitlab.com` and `codeberg.org`. Anything else
is refused before a directory is created.

## Pipeline

```text
1. CLONE     a target repository, pinned to an exact commit
2. ANALYZE   its structure — layout, manifests, markers, file counts
3. EXTRACT   candidate infrastructure patterns, with evidence and confidence
4. UNDERSTAND why it was built this way  ← NOT AUTOMATED (see below)
5. RECREATE  a proposal, as Markdown only ← NOT AUTOMATED INTO CODE
6. CLASSIFY  against TAXONOMY.md; propose new categories rather than assume them
7. CITE      the exact commit; `code_reused: false` is emitted structurally
8. LOG       a study report in studied_repos/
```

Steps 4 and 5 are the ones a script cannot do honestly. Understanding requires
judgement, and recreating means `UNDERSTAND → ABSTRACT → DESIGN → IMPLEMENT →
TEST`, never `COPY → RENAME → MODIFY` (charter §9). The pipeline therefore
produces a **proposal** and stops. Each report ends with the questions a session
must answer before anything is adopted.

## Components

| File | Role |
|---|---|
| `workspace.py` | The trust boundary: URL validation, clone, commit pinning, cleanup |
| `inventory.py` | Structural map — layout, packages, manifests, markers, file counts |
| `patterns.py` | Candidate pattern extraction with evidence-based confidence |
| `classify.py` | Maps candidates onto the real taxonomy; proposes new categories |
| `report.py` | Renders the Markdown report |
| `__main__.py` | Thin CLI over the above |

## Honesty constraints

These are properties of the code, not aspirations. Each is checked.

- **Nothing is executed.** No import, install, or subprocess inside a studied
  tree. Test-enforced (ADR-0021 Decision 1).
- **Nothing is written to `catalog/` or `integrations/`.** The pipeline has no
  code path that mutates them, which is what makes `code_reused: false`
  structural rather than a claim (ADR-0021 Decision 2).
- **`TAXONOMY.md` is read, never written.** A candidate whose category is absent
  becomes a printed proposal. Adopting one is a session decision requiring an
  ADR (charter §12).
- **Confidence labels the evidence, not the importance.** Two module-bearing
  directories rate `STRONG`; a bare directory name rates `WEAK` and says why.
- **The detector recognises AI-infrastructure conventions and can be blind.**
  Measured limits and the reversal path are recorded as
  [DW-013](../docs/DEFERRED.md).
- **Reports are proposals, not canonical knowledge.** A session reads the source
  and decides (charter §6, §28).
- The pipeline is itself infrastructure: tested, documented, versioned (charter
  §29). It adds no runtime dependency — standard library only.
