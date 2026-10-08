"""Tests for scripts/check_session_closure.py (ADR-0030, V16).

Why these tests exist
---------------------
On 2026-10-08 an agent closed its own session on its own authority with every
gate green. The shutdown sequence was prose; prose is not enforcement. This
gate makes silent closure fail the build. Per the repository's own rule, a
gate that has never been seen to fail is a gate that cannot be trusted — so
most tests below assert the failure, not just the pass.

Charter references: §4, §20, §25. ADR-0030.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_session_closure as csc  # noqa: E402


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture()
def tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A minimal state/ tree: sessions dir, registry, index."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    registry = _write(tmp_path / "REGISTRY.md", "# REGISTRY\n")
    index = _write(tmp_path / "INDEX.md", "# INDEX\n")
    return sessions, registry, index


def _active_session(sessions: Path, name: str = "20261008-0000-R9-work.md") -> Path:
    return _write(
        sessions / name,
        "- **Status:** Active\n\nDid some work. Nothing completed yet.\n",
    )


def _completed_session(
    sessions: Path,
    name: str = "20261008-0000-R9-work.md",
    auth: str | None = None,
) -> Path:
    lines = ["- **Status:** Completed", "", "All done."]
    if auth is not None:
        lines += ["", f"Close-Authorized-By: {auth}"]
    return _write(sessions / name, "\n".join(lines) + "\n")


def test_active_session_passes(tree: tuple[Path, Path, Path]) -> None:
    sessions, registry, index = tree
    _active_session(sessions)
    assert csc.run_all(sessions, registry, index) == []


def test_completed_without_auth_fails(tree: tuple[Path, Path, Path]) -> None:
    """The incident, reproduced: a self-closed session must fail."""
    sessions, registry, index = tree
    _completed_session(sessions)
    violations = csc.run_all(sessions, registry, index)
    assert len(violations) == 1
    assert "Close-Authorized-By" in str(violations[0])


def test_completed_with_auth_passes(tree: tuple[Path, Path, Path]) -> None:
    sessions, registry, index = tree
    _completed_session(
        sessions,
        auth='maintainer — "close the session" (2026-10-08)',
    )
    assert csc.run_all(sessions, registry, index) == []


def test_empty_auth_value_fails(tree: tuple[Path, Path, Path]) -> None:
    sessions, _registry, _index = tree
    path = _write(
        sessions / "20261008-0000-R9-work.md",
        "- **Status:** Completed\n\nClose-Authorized-By:   \n",
    )
    assert csc.check_session_file(path) != []


def test_auth_without_date_fails(tree: tuple[Path, Path, Path]) -> None:
    """An undated line can be copied forward forever without saying anything."""
    sessions, registry, index = tree
    _completed_session(sessions, auth="maintainer said close whenever")
    violations = csc.run_all(sessions, registry, index)
    assert len(violations) == 1


def test_outcome_completed_marker_fails_without_auth(
    tree: tuple[Path, Path, Path],
) -> None:
    sessions, registry, index = tree
    _write(
        sessions / "20261008-0000-R9-work.md",
        "## Summary\n\n- **Outcome:** COMPLETED. Everything done.\n",
    )
    assert csc.run_all(sessions, registry, index) != []


def test_claims_released_marker_fails_without_auth(
    tree: tuple[Path, Path, Path],
) -> None:
    sessions, registry, index = tree
    _write(
        sessions / "20261008-0000-R9-work.md",
        "- **Status:** Active\n\nSession closed by user; claims released.\n",
    )
    assert csc.run_all(sessions, registry, index) != []


def test_ordinary_prose_does_not_trigger(tree: tuple[Path, Path, Path]) -> None:
    """'Reconnaissance complete' is prose, not a lifecycle claim."""
    sessions, registry, index = tree
    _write(
        sessions / "20261008-0000-R9-work.md",
        "- Git reconnaissance complete\n- Status: Created\n- Outcome: TBD\n",
    )
    assert csc.run_all(sessions, registry, index) == []


def _registry_row(agent: str, status: str) -> str:
    return (
        "| Agent ID | Model | Branch | Task | Started | Status | Files Owned |\n"
        "|---|---|---|---|---|---|---|\n"
        f"| {agent} | m | b | t | 2026-10-08 | {status} | _(released)_ |\n"
    )


def test_registry_completed_with_authorized_session_passes(
    tree: tuple[Path, Path, Path],
) -> None:
    sessions, registry, index = tree
    _completed_session(
        sessions,
        name="20261008-0000-R9-work.md",
        auth='maintainer — "close" (2026-10-08)',
    )
    registry.write_text(_registry_row("R9", "Completed"), encoding="utf-8")
    assert csc.run_all(sessions, registry, index) == []


def test_registry_completed_with_unauthorized_session_fails(
    tree: tuple[Path, Path, Path],
) -> None:
    sessions, registry, index = tree
    _completed_session(sessions, name="20261008-0000-R9-work.md")
    registry.write_text(_registry_row("R9", "Completed"), encoding="utf-8")
    violations = csc.run_all(sessions, registry, index)
    # One from the session file, one from the registry coherence rule.
    assert len(violations) == 2
    assert any(str(registry) in str(v) for v in violations)


def test_registry_completed_with_no_session_file_fails(
    tree: tuple[Path, Path, Path],
) -> None:
    """A completion claim with no session file at all is dangling."""
    sessions, registry, index = tree
    registry.write_text(_registry_row("GHOST", "Completed"), encoding="utf-8")
    violations = csc.run_all(sessions, registry, index)
    assert len(violations) == 1
    assert "dangling" in str(violations[0])


def test_registry_active_needs_nothing(tree: tuple[Path, Path, Path]) -> None:
    sessions, registry, index = tree
    registry.write_text(_registry_row("R9", "Active"), encoding="utf-8")
    assert csc.run_all(sessions, registry, index) == []


def test_index_completed_requires_auth(tree: tuple[Path, Path, Path]) -> None:
    sessions, registry, index = tree
    _completed_session(sessions, name="20261008-0000-R9-work.md")
    index.write_text(
        "- **Agent:** R9 (m)\n- **Outcome:** COMPLETED. Done.\n",
        encoding="utf-8",
    )
    violations = csc.run_all(sessions, registry, index)
    assert len(violations) == 2  # session file + index coherence
    assert any(str(index) in str(v) for v in violations)


def test_one_agents_closure_does_not_implicate_another(
    tree: tuple[Path, Path, Path],
) -> None:
    sessions, registry, index = tree
    _active_session(sessions, name="20261008-0000-R1-work.md")
    _completed_session(
        sessions,
        name="20261008-0000-R2-work.md",
        auth='maintainer — "close R2" (2026-10-08)',
    )
    registry.write_text(
        _registry_row("R1", "Active")
        + "| R2 | m | b | t | 2026-10-08 | Completed | x |\n",
        encoding="utf-8",
    )
    assert csc.run_all(sessions, registry, index) == []


def test_missing_sessions_dir_fails(tree: tuple[Path, Path, Path]) -> None:
    sessions, registry, index = tree
    sessions.rmdir()
    violations = csc.run_all(sessions, registry, index)
    assert any("sessions directory is missing" in str(v) for v in violations)


def test_main_quiet_returns_zero_on_clean_tree(
    tree: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions, registry, index = tree
    _active_session(sessions)
    monkeypatch.setattr(csc, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(csc, "REGISTRY", registry)
    monkeypatch.setattr(csc, "INDEX", index)
    assert csc.main(["--quiet"]) == 0


def test_main_returns_one_on_violation(
    tree: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sessions, registry, index = tree
    _completed_session(sessions)
    monkeypatch.setattr(csc, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(csc, "REGISTRY", registry)
    monkeypatch.setattr(csc, "INDEX", index)
    assert csc.main([]) == 1
    assert "session-closure: error" in capsys.readouterr().out


def test_real_tree_passes() -> None:
    """The live state/ tree must satisfy its own gate.

    This is the grandfather check in reverse: instead of exempting history,
    the one historical closure (A001) was backfilled with its authorization
    evidence, so the real tree passes with no exemption list.
    """
    assert csc.run_all() == []
