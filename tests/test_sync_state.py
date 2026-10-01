"""Unit tests for scripts/sync_state.py.

This checker closes a specific, verified hole: session records rotted three
times in one day while the session was still open — commit lists fell
behind, branch fields pointed at deleted branches, timestamps described dead
realities. Every instance had the same shape: a human wrote a git-derived
fact down, then git moved on.

The properties tested here are the ones the whole mechanism rests on:

  * IDEMPOTENCY. The pre-commit hook runs sync on every commit. If a run
    with no new git state changed any file, every commit would dirty the
    tree it just tried to clean — an infinite regress. Two consecutive runs
    must be byte-identical.
  * MARKER SAFETY. The script must never alter a byte outside its marked
    blocks. A regeneration that eats prose would destroy the record it
    exists to protect. Tested with hostile prose (marker-like strings
    nearby, no trailing newline).
  * SCOPING. Only active agents' session files are touched. Regenerating
    blocks in old (completed) session files would churn history on every
    commit. A completed agent's file must be byte-identical after a run.
  * --check HONESTY. Verification mode must fail on stale/missing blocks
    and pass immediately after a sync — otherwise the terminal loop that
    depends on it cannot terminate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sync_state import (  # noqa: E402
    _active_session_files,
    _apply_block,
    _commits_body,
    _dashboard_body,
    main,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 - fixed argv, test-only git repo, no shell
        [  # noqa: S607
            "git",
            "-C",
            str(cwd),
            *args,
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A tiny git repo with state/ layout: master + one session commit."""
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "sessions").mkdir()
    (tmp_path / "state" / "DASHBOARD.md").write_text("# DASHBOARD\n", encoding="utf-8")
    (tmp_path / "state" / "REGISTRY.md").write_text("# REGISTRY\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")
    return tmp_path


def _write_registry(repo: Path, active: str, completed: str = "") -> None:
    rows = [
        "# REGISTRY",
        "",
        "| Agent ID | Model | Branch | Task | Started | Status | Files Owned |",
        "|---|---|---|---|---|---|---|",
    ]
    if active:
        rows.append(f"| A001 | m | b | t | s | Active | `{active}` |")
    if completed:
        rows.append(f"| B002 | m | b | t | s | Completed | `{completed}` |")
    (repo / "state" / "REGISTRY.md").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Idempotency — the load-bearing property
# ---------------------------------------------------------------------------


def test_second_run_changes_nothing(repo: Path) -> None:
    session = repo / "state" / "sessions" / "s.md"
    session.write_text("# session\n", encoding="utf-8")
    _write_registry(repo, "state/sessions/s.md")
    assert main(["--root", str(repo), "--quiet"]) == 0
    first_dashboard = (repo / "state" / "DASHBOARD.md").read_bytes()
    first_session = session.read_bytes()
    # A second run with no new git state must be byte-identical. If this
    # ever fails, the pre-commit hook would dirty the tree on every commit.
    assert main(["--root", str(repo), "--quiet"]) == 0
    assert (repo / "state" / "DASHBOARD.md").read_bytes() == first_dashboard
    assert session.read_bytes() == first_session


def test_new_commit_changes_only_blocks(repo: Path) -> None:
    session = repo / "state" / "sessions" / "s.md"
    session.write_text("# session\n\nProse stays.\n", encoding="utf-8")
    _write_registry(repo, "state/sessions/s.md")
    _git(repo, "checkout", "-b", "work")
    assert main(["--root", str(repo), "--quiet"]) == 0
    (repo / "README.md").write_text("# test\nmore\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "second")
    assert main(["--root", str(repo), "--quiet"]) == 0
    text = session.read_text(encoding="utf-8")
    assert "Prose stays." in text
    assert "second" in text


# ---------------------------------------------------------------------------
# Marker safety — prose outside markers is never touched
# ---------------------------------------------------------------------------


def test_prose_outside_markers_untouched() -> None:
    text = "# Title\n\nSome <!-- almost-a-marker prose.\nNo trailing newline here"
    new_text, changed = _apply_block(
        text, "<!-- AUTO-SYNC:START -->", "<!-- AUTO-SYNC:END -->", "BODY\n"
    )
    assert changed
    assert new_text.startswith(text + "\n\n")
    assert new_text.endswith("BODY\n")


def test_missing_markers_appended_not_inserted(repo: Path) -> None:
    dashboard = repo / "state" / "DASHBOARD.md"
    original = "# DASHBOARD\n\nExisting content.\n"
    dashboard.write_text(original, encoding="utf-8")
    assert main(["--root", str(repo), "--quiet"]) == 0
    updated = dashboard.read_text(encoding="utf-8")
    assert updated.startswith(original)
    assert "<!-- AUTO-SYNC:START -->" in updated


# ---------------------------------------------------------------------------
# Scoping — history is not churned
# ---------------------------------------------------------------------------


def test_completed_agent_file_untouched(repo: Path) -> None:
    active = repo / "state" / "sessions" / "active.md"
    active.write_text("# active\n", encoding="utf-8")
    old = repo / "state" / "sessions" / "old.md"
    old.write_text("# old session, completed long ago\n", encoding="utf-8")
    _write_registry(repo, "state/sessions/active.md", "state/sessions/old.md")
    assert main(["--root", str(repo), "--quiet"]) == 0
    # The completed session's file must be byte-identical: history is a
    # record, not a living document. Churning it per commit would bury
    # real changes in noise.
    assert old.read_text(encoding="utf-8") == "# old session, completed long ago\n"
    assert "<!-- AUTO-COMMITS:START -->" in active.read_text(encoding="utf-8")


def test_active_session_files_resolves_only_active() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "state").mkdir()
        (root / "state" / "sessions").mkdir()
        (root / "state" / "sessions" / "a.md").write_text("x", encoding="utf-8")
        (root / "state" / "REGISTRY.md").write_text(
            "| A1 | m | b | t | s | Active | `state/sessions/a.md` |\n"
            "| B2 | m | b | t | s | Completed 12:00 | `state/sessions/gone.md` |\n",
            encoding="utf-8",
        )
        found = _active_session_files(root)
        assert found == [root / "state" / "sessions" / "a.md"]


# ---------------------------------------------------------------------------
# --check honesty — the terminal loop depends on this terminating
# ---------------------------------------------------------------------------


def test_check_fails_stale_then_passes_after_sync(repo: Path) -> None:
    session = repo / "state" / "sessions" / "s.md"
    session.write_text("# session\n", encoding="utf-8")
    _write_registry(repo, "state/sessions/s.md")
    assert main(["--root", str(repo), "--quiet", "--check"]) == 1
    assert main(["--root", str(repo), "--quiet"]) == 0
    assert main(["--root", str(repo), "--quiet", "--check"]) == 0


def test_dirty_tree_is_disclosed_not_hidden(repo: Path) -> None:
    session = repo / "state" / "sessions" / "s.md"
    session.write_text("# session\n", encoding="utf-8")
    _write_registry(repo, "state/sessions/s.md")
    _git(repo, "checkout", "-b", "work")
    # Uncommitted changes must be disclosed, never silently absorbed: a block
    # claiming "branch matches master" while files are modified would be a
    # lie the automation tells on the agent's behalf.
    (repo / "README.md").write_text("# test\nuncommitted\n", encoding="utf-8")
    assert main(["--root", str(repo), "--quiet"]) == 0
    text = session.read_text(encoding="utf-8")
    assert "uncommitted changes present" in text
    dashboard = (repo / "state" / "DASHBOARD.md").read_text(encoding="utf-8")
    assert "working tree dirty" in dashboard
    # After committing, the disclosure disappears on the next sync — and the
    # run is still idempotent.
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "save")
    assert main(["--root", str(repo), "--quiet"]) == 0
    text = session.read_text(encoding="utf-8")
    assert "uncommitted changes present" not in text
    assert "save" in text


def test_generated_blocks_carry_no_timestamps() -> None:
    # A timestamp inside a generated block makes every run differ from the
    # last: every commit would dirty state files and --check could never
    # pass except in the minute after a sync. This test pins the design
    # decision that cost one real debugging round — freshness is proven by
    # re-running, never by a string.
    dashboard = _dashboard_body("b", "abc1234", 2, False)
    commits = _commits_body([("abc1234", "subj")], True)
    combined = dashboard + commits
    assert not re.search(r"20\d\d-\d\d-\d\d", combined)
    assert not re.search(r"\d{2}:\d{2} UTC", combined)


def test_check_ignores_transient_dirty_lines(repo: Path) -> None:
    # --check on a just-committed (clean) tree must pass even though the
    # stored block was rendered while dirty: dirty-state is transient, and
    # verification that flaps on every commit is noise, not signal. Only
    # stable claims (branch, HEAD, commit list) participate in --check.
    session = repo / "state" / "sessions" / "s.md"
    session.write_text("# session\n", encoding="utf-8")
    _write_registry(repo, "state/sessions/s.md")
    _git(repo, "checkout", "-b", "work")
    (repo / "README.md").write_text("# test\ndirty\n", encoding="utf-8")
    assert main(["--root", str(repo), "--quiet"]) == 0
    assert "uncommitted changes present" in session.read_text(encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "save")
    # Re-sync to pick up the new commit, then dirty the tree again without
    # committing: the stored block keeps its old dirty line while a fresh
    # render would too — --check must pass regardless, because only stable
    # claims (branch, HEAD, commit list) participate in verification.
    assert main(["--root", str(repo), "--quiet"]) == 0
    (repo / "README.md").write_text("# test\ndirty again\n", encoding="utf-8")
    assert main(["--root", str(repo), "--quiet", "--check"]) == 0


def test_no_state_dir_exits_zero(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path), "--quiet"]) == 0
    assert main(["--root", str(tmp_path), "--quiet", "--check"]) == 0
