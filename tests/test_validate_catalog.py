"""Cross-cutting tests for repository machinery.

These test the repository's own tooling (charter §29: "the study pipeline
itself is infrastructure — it should be tested, documented, and versioned like
everything else"). Capability tests live with their catalog entry.

Run:  python -m pytest tests/ -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_catalog import CATEGORIES, main, validate  # noqa: E402

REPO = REPO_ROOT


def _category_readme(title: str) -> str:
    return f"# {title}\n\n## What it is\n\nx\n\n## Why it exists\n\ny\n"


def _entry_readme(title: str) -> str:
    return (
        f"# {title}\n\n## What it is\n\nx\n\n## How it works\n\ny\n"
        "## Our implementations\n\nz\n\n## References\n\nnone\n"
    )


def test_real_repository_passes() -> None:
    """The committed repository satisfies its own catalog contract."""
    report = validate(REPO, strict=False)
    assert report.errors == [], report.errors


def test_cli_returns_zero_on_real_repository() -> None:
    """CLI exit code is 0 for a valid catalog."""
    assert main(["--root", str(REPO)]) == 0


def _scaffold(tmp_path: Path) -> Path:
    """Create a minimal valid catalog tree under tmp_path."""
    for category in CATEGORIES:
        category_dir = tmp_path / "catalog" / category
        category_dir.mkdir(parents=True)
        (category_dir / "README.md").write_text(
            _category_readme(category), encoding="utf-8"
        )
    return tmp_path


def test_valid_scaffold_passes(tmp_path: Path) -> None:
    """A minimal well-formed tree validates cleanly."""
    report = validate(_scaffold(tmp_path), strict=False)
    assert report.errors == [], report.errors


def test_missing_category_directory_is_error(tmp_path: Path) -> None:
    """A declared category directory that does not exist is an error."""
    root = _scaffold(tmp_path)
    import shutil

    shutil.rmtree(root / "catalog" / "evaluation")
    report = validate(root, strict=False)
    assert any("evaluation" in e for e in report.errors), report.errors


def test_category_readme_missing_section_is_error(tmp_path: Path) -> None:
    """Category READMEs must carry the required headings (charter §13)."""
    root = _scaffold(tmp_path)
    (root / "catalog" / "tools" / "README.md").write_text(
        "# Tools\n\nNo required sections here.\n", encoding="utf-8"
    )
    report = validate(root, strict=False)
    assert any("required section" in e for e in report.errors), report.errors


def test_entry_missing_provenance_is_error(tmp_path: Path) -> None:
    """An entry without PROVENANCE.md violates the entry contract."""
    root = _scaffold(tmp_path)
    entry = root / "catalog" / "tools" / "demo_tool"
    entry.mkdir()
    (entry / "README.md").write_text(_entry_readme("Demo"), encoding="utf-8")
    report = validate(root, strict=False)
    assert any("PROVENANCE.md" in e for e in report.errors), report.errors


def test_entry_missing_readme_section_is_error(tmp_path: Path) -> None:
    """An entry README missing required sections is an error."""
    root = _scaffold(tmp_path)
    entry = root / "catalog" / "tools" / "demo_tool"
    entry.mkdir()
    (entry / "README.md").write_text("# Demo\n\nNothing useful.\n", encoding="utf-8")
    (entry / "PROVENANCE.md").write_text("# Provenance\n", encoding="utf-8")
    report = validate(root, strict=False)
    assert any("required section" in e for e in report.errors), report.errors


def test_missing_examples_is_warning_not_error(tmp_path: Path) -> None:
    """examples/ and tests/ warn by default so the skeleton validates."""
    root = _scaffold(tmp_path)
    entry = root / "catalog" / "tools" / "demo_tool"
    entry.mkdir()
    (entry / "README.md").write_text(_entry_readme("Demo"), encoding="utf-8")
    (entry / "PROVENANCE.md").write_text("# Provenance\n", encoding="utf-8")
    report = validate(root, strict=False)
    assert report.errors == [], report.errors
    assert any("examples" in w for w in report.warnings), report.warnings


def test_strict_promotes_missing_examples_to_error(tmp_path: Path) -> None:
    """--strict is what a releasing entry must satisfy."""
    root = _scaffold(tmp_path)
    entry = root / "catalog" / "tools" / "demo_tool"
    entry.mkdir()
    (entry / "README.md").write_text(_entry_readme("Demo"), encoding="utf-8")
    (entry / "PROVENANCE.md").write_text("# Provenance\n", encoding="utf-8")
    report = validate(root, strict=True)
    assert any("examples" in e for e in report.errors), report.errors


# ---------------------------------------------------------------------------
# Empty-directory holes (regression)
#
# These were REAL holes: an entry whose tests/ directory existed but was empty
# passed --strict, and pytest's testpaths never looked inside catalog/ at all.
# A capability could therefore ship tests that never ran (or none at all) while
# every gate stayed green — the exact failure charter §4 forbids.
# ---------------------------------------------------------------------------


def _entry_with(root: Path, name: str = "demo_tool") -> Path:
    """Create a structurally valid entry, without tests/ or examples/."""
    entry = root / "catalog" / "tools" / name
    entry.mkdir()
    (entry / "README.md").write_text(_entry_readme("Demo"), encoding="utf-8")
    (entry / "PROVENANCE.md").write_text("# Provenance\n", encoding="utf-8")
    return entry


def test_empty_tests_directory_is_an_error_in_normal_mode(tmp_path: Path) -> None:
    """An empty tests/ is never evidence, even outside strict mode."""
    root = _scaffold(tmp_path)
    entry = _entry_with(root)
    (entry / "tests").mkdir()
    report = validate(root, strict=False)
    assert any("no test_*.py files" in e for e in report.errors), report.errors


def test_empty_tests_directory_is_an_error_in_strict_mode(tmp_path: Path) -> None:
    """--strict must not accept a placeholder tests/ directory."""
    root = _scaffold(tmp_path)
    entry = _entry_with(root)
    (entry / "tests").mkdir()
    report = validate(root, strict=True)
    assert any("no test_*.py files" in e for e in report.errors), report.errors


def test_tests_directory_with_a_real_test_passes(tmp_path: Path) -> None:
    """A populated tests/ satisfies the contract."""
    root = _scaffold(tmp_path)
    entry = _entry_with(root)
    tests = entry / "tests"
    tests.mkdir()
    (tests / "test_demo.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    report = validate(root, strict=False)
    assert report.errors == [], report.errors


def test_empty_examples_directory_is_an_error(tmp_path: Path) -> None:
    """An empty examples/ is a placeholder, not an example."""
    root = _scaffold(tmp_path)
    entry = _entry_with(root)
    (entry / "examples").mkdir()
    report = validate(root, strict=False)
    assert any(
        "examples/ directory is empty" in e for e in report.errors
    ), report.errors


def test_nested_test_file_is_found(tmp_path: Path) -> None:
    """Tests nested below tests/ still count as present."""
    root = _scaffold(tmp_path)
    entry = _entry_with(root)
    nested = entry / "tests" / "unit"
    nested.mkdir(parents=True)
    (nested / "test_nested.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    report = validate(root, strict=False)
    assert report.errors == [], report.errors


def test_catalog_tests_are_collected_by_pytest() -> None:
    """pytest's testpaths must include catalog/ (regression).

    If this fails, capability tests are silently skipped by `make check` while
    the suite still reports green.
    """
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + result.stderr
    # The real repo has no catalog entries yet, so assert the CONFIG includes
    # catalog rather than that it collected something from it.
    assert "catalog" in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert result.returncode == 0, combined


def test_private_directories_are_ignored(tmp_path: Path) -> None:
    """Directories starting with _ or . are not treated as entries."""
    root = _scaffold(tmp_path)
    (root / "catalog" / "tools" / "_scratch").mkdir()
    report = validate(root, strict=False)
    assert report.errors == [], report.errors


def test_failing_validation_returns_nonzero(tmp_path: Path) -> None:
    """CLI exit code is 1 when the contract is violated."""
    root = _scaffold(tmp_path)
    import shutil

    shutil.rmtree(root / "catalog" / "memory")
    assert main(["--root", str(root)]) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
