"""Tests for the Markdown link checker.

The checker was added after 41 broken links accumulated undetected: category
READMEs pointed at ``../docs/...`` when the correct path was ``../../docs/...``,
and stale references survived several sessions while every gate reported green.
These tests pin the checker's ability to actually detect that class of defect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_links import find_broken_links, main  # noqa: E402


def _write(root: Path, name: str, content: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_real_repository_has_no_broken_links() -> None:
    """The committed documentation must be internally consistent."""
    assert find_broken_links(REPO_ROOT) == []


def test_broken_relative_link_is_detected(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "[gone](./missing.md)\n")
    broken = find_broken_links(tmp_path)
    assert broken, "a dangling relative link must be reported"
    assert broken[0][1] == "./missing.md"


def test_valid_relative_link_passes(tmp_path: Path) -> None:
    _write(tmp_path, "target.md", "# Target\n")
    _write(tmp_path, "a.md", "[ok](./target.md)\n")
    assert find_broken_links(tmp_path) == []


def test_wrong_directory_depth_is_detected(tmp_path: Path) -> None:
    """The exact historical bug: ../ when ../../ was required."""
    _write(tmp_path, "docs/real.md", "# Real\n")
    _write(tmp_path, "research/tools/README.md", "[t](../docs/real.md)\n")
    broken = find_broken_links(tmp_path)
    assert broken, "the ../-instead-of-../../ bug must be caught"


def test_correct_depth_passes(tmp_path: Path) -> None:
    _write(tmp_path, "docs/real.md", "# Real\n")
    _write(tmp_path, "research/tools/README.md", "[t](../../docs/real.md)\n")
    assert find_broken_links(tmp_path) == []


def test_external_links_are_not_checked(tmp_path: Path) -> None:
    """We cannot and must not try to verify the network."""
    _write(
        tmp_path,
        "a.md",
        "[x](https://example.com/nothing)\n[y](mailto:a@b.c)\n",
    )
    assert find_broken_links(tmp_path) == []


def test_pure_anchor_link_is_not_checked(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "[s](#some-section)\n")
    assert find_broken_links(tmp_path) == []


def test_anchor_on_a_real_file_resolves(tmp_path: Path) -> None:
    _write(tmp_path, "t.md", "# T\n")
    _write(tmp_path, "a.md", "[x](./t.md#heading)\n")
    assert find_broken_links(tmp_path) == []


def test_anchor_on_a_missing_file_is_detected(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "[x](./missing.md#heading)\n")
    assert find_broken_links(tmp_path), "the file part must still be checked"


def test_skipped_directories_are_ignored(tmp_path: Path) -> None:
    """Vendored/cache trees must not be scanned for our documentation."""
    _write(tmp_path, ".venv/lib/a.md", "[gone](./nope.md)\n")
    assert find_broken_links(tmp_path) == []


def test_directory_link_resolves(tmp_path: Path) -> None:
    _write(tmp_path, "sub/keep.txt", "x")
    _write(tmp_path, "a.md", "[d](./sub/)\n")
    assert find_broken_links(tmp_path) == []


@pytest.mark.parametrize(
    ("content", "expected"), [("[ok](./t.md)\n", 0), ("[bad](./x.md)\n", 1)]
)
def test_main_exit_code(tmp_path: Path, content: str, expected: int) -> None:
    _write(tmp_path, "t.md", "# T\n")
    _write(tmp_path, "a.md", content)
    assert main(["--root", str(tmp_path), "--quiet"]) == expected
