"""Verify that every directory holding project source is actually gated.

Why this file exists
--------------------
This repository has now closed six instances of one bug class:

1. ``validate_catalog.py`` accepted an **empty** ``tests/`` directory.
2. ``testpaths`` excluded ``catalog/``, so capability tests never ran.
3. ``repo_status.py`` checked ``research_records`` was non-empty but never
   that the file existed.
4. 41 relative Markdown links were broken with every gate green.
5. ``docs/decisions/README.md`` was missing ADRs 0006 and 0007.
6. ``docs/phases/phase-1-seed.md`` contradicted the charter lifecycle.

The pattern was the same every time: **something was assumed to be covered,
and nothing asserted the coverage.** ``integrations/`` was the sixth: the
Phase 1 exit criterion requires an end-to-end composition there *with its own
tests*, but ``testpaths``, ``coverage.source``, and the Makefile's mypy target
list all omitted it. Building the integration before fixing that would have
produced tests that never ran while ``make check`` stayed green.

These tests assert the coverage itself, over the *set of directories* rather
than one hard-coded path, so a seventh directory cannot be added silently.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Directories that hold this project's own Python source and must therefore be
#: measured by coverage and traversed by mypy. ``tests/`` is absent: measuring a
#: test suite's own coverage is circular, and it is still type-checked.
SOURCE_DIRS: frozenset[str] = frozenset({"catalog", "integrations", "scripts"})

#: Directories whose tests live *inside* them rather than in ``tests/``. These
#: must appear in pytest's ``testpaths`` or their tests never run.
#: ``scripts/`` is deliberately NOT here: it holds tooling whose tests live in
#: ``tests/``, so it needs coverage and mypy but not a testpath. Conflating the
#: two properties was the first draft of this file's mistake, caught by running
#: it — which is the point of writing the check before trusting it.
IN_TREE_TEST_DIRS: frozenset[str] = frozenset({"catalog", "integrations"})

#: Directories that may contain Python but are deliberately out of scope.
#: ``study_pipeline/`` is Phase 2 machinery (charter §29) and ``.venv`` is the
#: toolchain. Listing them explicitly means the check below reports an
#: unexplained new directory rather than silently passing it.
EXEMPT_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        ".uv-cache",
        "study_pipeline",
        "benchmarks",
        "__pycache__",
        ".mypy_cache",
    }
)


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _dirs_with_python() -> set[str]:
    """Top-level directories containing at least one .py file, excluding exemptions."""
    found: set[str] = set()
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT)
        if not rel.parts:
            continue
        top = rel.parts[0]
        if top in EXEMPT_DIRS or top.endswith(".egg-info"):
            continue
        found.add(top)
    return found


# --------------------------------------------------------------------------- #
# The pinned set is the truth
# --------------------------------------------------------------------------- #


def test_every_directory_with_python_is_declared_source_or_exempt() -> None:
    """A new top-level source directory must be classified, not overlooked.

    This is the test that would have caught ``integrations/`` the moment a
    Python file landed in it.
    """
    undeclared = _dirs_with_python() - SOURCE_DIRS - EXEMPT_DIRS - {"tests"}
    assert undeclared == set(), (
        f"top-level director{'y' if len(undeclared) == 1 else 'ies'} "
        f"{sorted(undeclared)} contain Python but are neither in SOURCE_DIRS "
        "(and therefore measured and type-checked) nor in EXEMPT_DIRS. "
        "Classify it: add it to the gates, or record why it is exempt."
    )


def test_the_source_set_is_not_vacuous() -> None:
    """A gate over an empty set proves nothing."""
    assert SOURCE_DIRS & _dirs_with_python(), (
        "no declared source directory contains any Python; these tests would "
        "pass vacuously"
    )


# --------------------------------------------------------------------------- #
# pytest collects them
# --------------------------------------------------------------------------- #


def _dirs_containing_tests() -> set[str]:
    """Top-level directories that actually contain test files, right now.

    Derived from the filesystem rather than declared, so it cannot go stale: a
    directory starts mattering the moment a test lands in it.
    """
    found: set[str] = set()
    for path in REPO_ROOT.rglob("test_*.py"):
        rel = path.relative_to(REPO_ROOT)
        if not rel.parts:
            continue
        top = rel.parts[0]
        if top in EXEMPT_DIRS:
            continue
        found.add(top)
    return found


def test_every_directory_containing_tests_is_collected() -> None:
    """``testpaths`` must cover every directory that holds test files.

    Regression: ``testpaths`` was ``["tests"]`` while capability tests lived in
    ``catalog/``. They were never collected and every gate stayed green.

    This is derived from the filesystem, not from a hard-coded list, so it
    catches a *new* test-holding directory automatically.
    """
    configured = set(_pyproject()["tool"]["pytest"]["ini_options"]["testpaths"])
    holders = _dirs_containing_tests()
    uncovered = holders - configured
    assert uncovered == set(), (
        f"these directories contain test files but are not in pytest "
        f"testpaths: {sorted(uncovered)} — their tests would never run"
    )


def test_reality_is_a_subset_of_the_declaration() -> None:
    """Every directory that holds tests must be a declared in-tree test dir.

    Reality may be SMALLER than the declaration — ``integrations/`` is declared
    because the Phase 1 exit criterion requires it to hold its own tests, and
    that is true before the first integration exists. Reality must never be
    larger: a test file in an unclassified directory is a new thing that needs
    a decision.
    """
    actual = _dirs_containing_tests() - {"tests"}
    unexpected = actual - IN_TREE_TEST_DIRS
    assert unexpected == set(), (
        f"tests were found inside {sorted(unexpected)}, which is not in "
        f"IN_TREE_TEST_DIRS ({sorted(IN_TREE_TEST_DIRS)}). Classify the "
        "directory: declare it, or move the tests under tests/."
    )


def test_declared_in_tree_test_dirs_are_in_testpaths() -> None:
    """Every DECLARED in-tree test directory must be in ``testpaths``.

    This is the assertion that pins ``integrations/`` *before* it contains any
    test. Without it, the config check would pass vacuously today and silently
    swallow the integration's tests the moment they were written — which is
    exactly how the ``catalog/`` hole happened.
    """
    configured = set(_pyproject()["tool"]["pytest"]["ini_options"]["testpaths"])
    unconfigured = IN_TREE_TEST_DIRS - configured
    assert unconfigured == set(), (
        f"these declared in-tree test directories are not in pytest "
        f"testpaths: {sorted(unconfigured)} — tests written there later would "
        "never run"
    )


def test_testpaths_entries_exist() -> None:
    """A testpath naming a non-existent directory makes pytest exit non-zero."""
    configured = _pyproject()["tool"]["pytest"]["ini_options"]["testpaths"]
    absent = [d for d in configured if not (REPO_ROOT / d).is_dir()]
    assert absent == [], f"testpaths names missing directories: {absent}"


# --------------------------------------------------------------------------- #
# coverage measures them
# --------------------------------------------------------------------------- #


def test_coverage_source_covers_every_gated_directory() -> None:
    """``coverage.source`` must name every gated directory.

    ``tests/`` is deliberately excluded here: measuring a test suite's own
    coverage is circular. Every other gated directory is implementation and
    must be measured.
    """
    measured = set(_pyproject()["tool"]["coverage"]["run"]["source"])
    missing = SOURCE_DIRS - measured
    assert missing == set(), (
        f"these implementation directories are absent from coverage.source: "
        f"{sorted(missing)} — their tests would run but contribute no measurement"
    )


def test_coverage_source_entries_exist() -> None:
    measured = _pyproject()["tool"]["coverage"]["run"]["source"]
    absent = [d for d in measured if not (REPO_ROOT / d).is_dir()]
    assert absent == [], f"coverage.source names missing directories: {absent}"


# --------------------------------------------------------------------------- #
# mypy sees them
# --------------------------------------------------------------------------- #


def test_mypy_target_list_covers_every_gated_directory() -> None:
    """The Makefile's ``find`` must traverse every gated directory.

    The type-check target builds an explicit file list. A directory omitted
    from that list is silently un-typechecked while ``make typecheck`` passes.
    """
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    find_lines = [
        line
        for line in makefile.splitlines()
        if "find " in line and "-name '*.py'" in line
    ]
    assert find_lines, "no mypy find line found in the Makefile"

    # Extract the exact set of top-level directories the find traverses, rather
    # than substring-matching the raw line: "tests" is a substring of
    # "tests_helper", and a substring check would pass for a directory the find
    # never touches.
    searched: set[str] = set()
    for line in find_lines:
        after_find = line.split("find ", 1)[1]
        for word in after_find.split():
            if word == "-name":
                break
            searched.add(word)

    missing = sorted((SOURCE_DIRS | {"tests"}) - searched)
    assert missing == [], (
        f"these gated directories are absent from the Makefile's mypy find line: "
        f"{missing} — their code would never be type-checked. "
        f"(find traverses: {sorted(searched)})"
    )


# --------------------------------------------------------------------------- #
# and the whole thing actually runs
# --------------------------------------------------------------------------- #


def test_integrations_tests_would_be_collected() -> None:
    """End-to-end proof that a test placed in integrations/ is collected.

    The config assertions above could all pass while something else (a
    ``norecursedirs`` entry, a ``conftest`` exclusion) still prevented
    collection. This drops a real test file in and asks pytest to find it.

    Skipped when integrations/ has no Python yet, so it stays useful in the
    window before the first integration lands.
    """
    integrations = REPO_ROOT / "integrations"
    if not any(integrations.rglob("test_*.py")):
        pytest.skip("no integration tests exist yet")

    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "integrations"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "no tests ran" not in result.stdout
    ), "pytest found no tests under integrations/ — they exist but are not collected"
