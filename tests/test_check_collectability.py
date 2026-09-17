"""Unit tests for scripts/check_collectability.py.

This checker closes a specific, verified hole: a `tests/` directory whose tests
collect **zero items** reports success, so an entry could ship tests that never
ran while every gate stayed green.

Two properties are tested carefully because getting them wrong would make the
checker useless or actively harmful:

  * **Zero collected is a failure, a collection ERROR is a failure, and they
    are distinguishable.** The checker returns the exit code alongside the
    count precisely so the caller can tell "nothing to collect" (pytest exit 5)
    from "collection blew up" (another non-zero exit). Conflating them would
    mean a broken test file looked like a clean empty directory.

  * **Discovery must not silently collapse.** If entry discovery breaks, the
    loop expands to nothing and the check passes having verified nothing. The
    `MIN_EXPECTED_ENTRIES` floor exists for that, and it is tested.

A first version of this script reported six false "collects ZERO tests"
failures, because it looked for the summary line ("58 tests collected") when
`pytest -q --collect-only` prints per-file counts ("path: 58"). That regex is
tested directly here so the mistake cannot silently return.
"""

from __future__ import annotations

import re
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_collectability import (  # noqa: E402
    _PER_FILE_RE,
    _SELECTED_RE,
    _SUMMARY_RE,
    MIN_EXPECTED_ENTRIES,
    _configured_python_files,
    _entry_dirs,
    main,
)

# ---------------------------------------------------------------------------
# The counting regexes — the actual bug that was made and fixed
# ---------------------------------------------------------------------------


def test_per_file_regex_matches_what_pytest_really_prints() -> None:
    # `pytest -q --collect-only` emits per-file counts in this exact form.
    output = "catalog/tools/tool_registry/tests/test_x.py: 58\n"
    matches = list(_PER_FILE_RE.finditer(output))
    assert len(matches) == 1
    assert matches[0].group("path") == "catalog/tools/tool_registry/tests/test_x.py"
    assert matches[0].group("count") == "58"


def test_per_file_regex_sums_across_files() -> None:
    output = (
        "catalog/a/tests/test_one.py: 10\n"
        "catalog/a/tests/test_two.py: 5\n"
        "catalog/a/tests/test_three.py: 3\n"
    )
    total = sum(int(m.group("count")) for m in _PER_FILE_RE.finditer(output))
    assert total == 18


def test_per_file_regex_does_not_match_the_summary_style_line() -> None:
    # The original bug: this form is NOT what `-q --collect-only` prints, so a
    # checker keyed on it reports zero for a directory full of tests.
    assert list(_PER_FILE_RE.finditer("58 tests collected in 0.10s")) == []


def test_summary_and_selected_regexes_are_available_as_fallbacks() -> None:
    assert _SUMMARY_RE.search("58 tests collected in 0.12s") is not None
    assert _SELECTED_RE.search("58/58 tests collected") is not None


def test_per_file_regex_ignores_unrelated_output() -> None:
    output = "no tests ran in 0.01s\nsome warning: 3\n"
    assert list(_PER_FILE_RE.finditer(output)) == []


# ---------------------------------------------------------------------------
# Configuration and discovery
# ---------------------------------------------------------------------------


def test_configured_python_files_reads_pytest_own_config() -> None:
    patterns = _configured_python_files()
    assert patterns, "must never return an empty list"
    # This repository's pyproject.toml sets no custom python_files, so pytest's
    # own default should be reported.
    assert "test_*.py" in patterns


def test_configured_python_files_falls_back_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import check_collectability

    class Boom:
        @staticmethod
        def fromdictargs(*_args: object) -> object:
            raise RuntimeError("simulated")

    monkeypatch.setitem(sys.modules, "pytest", Boom)
    # A failure to read the config must degrade to the default, not crash.
    assert check_collectability._configured_python_files() == ["test_*.py"]


def test_entry_dirs_finds_the_real_entries() -> None:
    entries = _entry_dirs()
    assert len(entries) >= MIN_EXPECTED_ENTRIES, entries
    for entry in entries:
        assert (entry / "tests").is_dir(), entry
        # Entries live under catalog/<category>/<entry>/, and the end-to-end
        # INTEGRATION under integrations/<name>/ is checked the same way: it
        # has its own tests/ and a suite that collected nothing there would be
        # just as invisible.
        assert entry.parent.name in {
            "tools",
            "models",
            "agents",
            "protocols",
            "observability",
            "integrations",
        } or entry.parent.parent.name in {
            "catalog",
            "integrations",
        }, entry


def test_entry_dirs_are_absolute_and_unique() -> None:
    entries = _entry_dirs()
    assert len(entries) == len(set(entries))
    for entry in entries:
        assert entry.is_absolute()


# ---------------------------------------------------------------------------
# The real repository
# ---------------------------------------------------------------------------


def test_the_repository_entries_are_all_collectable() -> None:
    assert main(["--quiet"]) == 0


def test_main_reports_the_entries_checked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "entry(ies) checked" in out
    assert "python_files" in out


def test_main_verbose_lists_each_entry(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--verbose"]) == 0
    out = capsys.readouterr().out
    for entry in _entry_dirs():
        assert entry.name in out


# ---------------------------------------------------------------------------
# Teeth: a deliberately broken entry must be caught
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_entry(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """An entry whose tests/ directory exists but contains nothing.

    Created under the real `catalog/` tree so discovery finds it, then removed.
    A `tests/` with no test files is exactly the hole this checker exists for.
    """
    import check_collectability

    entry = REPO_ROOT / "catalog" / "tools" / f"tmp_probe_{uuid.uuid4().hex[:8]}"
    (entry / "tests").mkdir(parents=True)
    (entry / "__init__.py").write_text("", encoding="utf-8")
    (entry / "tests" / "not_a_test.txt").write_text("decoy\n", encoding="utf-8")

    original = check_collectability._entry_dirs

    def with_probe() -> list[Path]:
        return [*original(), entry]

    monkeypatch.setattr(check_collectability, "_entry_dirs", with_probe)
    try:
        yield entry
    finally:
        import shutil

        shutil.rmtree(entry, ignore_errors=True)


def test_an_entry_with_uncollectable_tests_is_reported(
    empty_entry: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import check_collectability

    # This is the whole point of the gate: without it, an entry can ship tests
    # that never run while every other check stays green.
    assert check_collectability.main(["--quiet"]) == 1
    combined = capsys.readouterr()
    assert "ZERO" in combined.out + combined.err


def test_discovery_collapse_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import check_collectability

    # Simulate discovery breaking: the floor must turn "found nothing" into a
    # failure rather than a green run that verified nothing.
    monkeypatch.setattr(check_collectability, "_entry_dirs", list)
    assert check_collectability.main(["--quiet"]) == 1
    assert "DISCOVERY broke" in capsys.readouterr().err


def test_min_expected_entries_is_a_real_floor() -> None:
    assert MIN_EXPECTED_ENTRIES >= 5
    assert len(_entry_dirs()) >= MIN_EXPECTED_ENTRIES


def test_per_file_regex_is_anchored_to_line_starts() -> None:
    # A path:count pair embedded mid-line (e.g. inside an error message) must
    # not be counted, or a collection error could inflate the total and hide
    # itself.
    assert isinstance(_PER_FILE_RE, re.Pattern)
    assert list(_PER_FILE_RE.finditer("error: test_x.py: 58 not a count")) == []
