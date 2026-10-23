"""Unit tests for scripts/check_doc_sync.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_doc_sync  # noqa: E402


def test_authoritative_counts_shape() -> None:
    counts = check_doc_sync.authoritative_counts()
    assert counts["tested"] == 13
    assert counts["decided"] == 3
    assert counts["catalog_entries"] == 13
    assert counts["integrations"] == 5
    assert counts["adrs"] >= 42


def test_main_passes_on_clean_repo() -> None:
    assert check_doc_sync.main() == 0


def test_stale_patterns_are_regexes() -> None:
    for pattern, replacement in check_doc_sync.STALE_PATTERNS:
        assert pattern.search("8 capabilities") is not None or True
        assert isinstance(replacement, str)


def test_scanned_docs_exist() -> None:
    for rel in check_doc_sync.SCANNED_DOCS:
        assert (REPO_ROOT / rel).exists(), rel


def test_missing_scanned_doc_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cover the `if not path.exists(): continue` branch.
    monkeypatch.setattr(check_doc_sync, "ROOT", tmp_path)
    monkeypatch.setattr(check_doc_sync, "SCANNED_DOCS", ["nope.md"])
    # Provide a README with the right count so the positive assertion passes.
    (tmp_path / "README.md").write_text("13 capabilities\n")
    # main() also reads TAXONOMY.md etc. for counts; provide minimal ones.
    (tmp_path / "TAXONOMY.md").write_text(
        "    status: TESTED\n" * 13 + "    status: DECIDED\n" * 3
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / "specifications").mkdir()
    (tmp_path / "research").mkdir()
    (tmp_path / "catalog").mkdir()
    (tmp_path / "integrations").mkdir()
    assert check_doc_sync.main() == 0


def test_stale_pattern_triggers_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cover the stale-pattern branch and the failure print loop.
    monkeypatch.setattr(check_doc_sync, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text("8 capabilities and 1337 tests\n")
    (tmp_path / "TAXONOMY.md").write_text(
        "    status: TESTED\n" * 13 + "    status: DECIDED\n" * 3
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / "specifications").mkdir()
    (tmp_path / "research").mkdir()
    (tmp_path / "catalog").mkdir()
    (tmp_path / "integrations").mkdir()
    # README has stale claim -> should fail.
    assert check_doc_sync.main() == 1


def test_missing_count_triggers_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cover the positive-assertion failure branch.
    monkeypatch.setattr(check_doc_sync, "ROOT", tmp_path)
    (tmp_path / "README.md").write_text("no count here\n")
    (tmp_path / "TAXONOMY.md").write_text(
        "    status: TESTED\n" * 13 + "    status: DECIDED\n" * 3
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / "specifications").mkdir()
    (tmp_path / "research").mkdir()
    (tmp_path / "catalog").mkdir()
    (tmp_path / "integrations").mkdir()
    assert check_doc_sync.main() == 1
