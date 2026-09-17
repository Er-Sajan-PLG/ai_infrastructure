"""Study pipeline — static analysis of third-party repositories (charter §29).

This package studies open-source AI infrastructure repositories to discover
patterns worth adopting. It is **machinery for finding capabilities**, not a
capability itself; it contributes nothing to `TAXONOMY.md`.

THE ONE RULE
------------
**Nothing in this package ever executes, imports, or installs code from a
studied repository.**

That is not a safety guideline, a default, or a mode — it is the architecture
([ADR-0021](../../docs/decisions/0021-study-pipeline-architecture.md), Decision
1). A study target is arbitrary third-party code chosen because it is large and
unfamiliar; its `conftest.py`, `setup.py`, `.pth` files and Makefiles all run on
import or invocation. The pipeline obtains a *structural map* instead, which is
sufficient for the deliverable (a study report) and involves no execution.

There is no configuration flag to relax this, and
`study_pipeline/tests/test_no_execution.py` enforces it as a check rather than a
comment (charter §20 — a rule with no check is a preference).

Package layout
--------------
======================== =====================================================
:mod:`workspace`         Clone lifecycle, commit pinning, cleanup
:mod:`inventory`         Structural map: layout, counts, manifests, markers
:mod:`patterns`          Candidate pattern extraction (static)
:mod:`classify`          Map patterns onto taxonomy categories
:mod:`report`            Render the Markdown study report
:mod:`cli`               Thin command-line wrapper
======================== =====================================================

Provenance and licensing
------------------------
Every study records the exact commit studied and reports `code_reused: false`.
That field is not a promise the pipeline makes about its own restraint — it is
structurally guaranteed, because the pipeline has no code path that writes
anywhere except `study_pipeline/studied_repos/*.md` (ADR-0021 Decision 2).
"""

from __future__ import annotations

__all__ = [
    "__version__",
]

#: Bumped when the report format changes in a way that invalidates old reports.
#: Recorded in every generated report so a reader can tell how it was produced.
__version__ = "0.1.0"
