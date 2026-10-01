#!/usr/bin/env python3
"""Keep git-derived MACP state blocks fresh (auto-sync).

What this enforces, and why it exists
-------------------------------------
Session records rotted three times in one day while a session was still
open: commit lists fell behind, branch fields pointed at deleted branches,
timestamps described dead realities. Every instance had the same shape — a
human wrote a git-derived fact down, then git moved on. The fix is to stop
writing git-derived facts by hand: this script regenerates them, and the
pre-commit hook runs it on every commit, so the record tracks reality at
commit granularity ("save points").

What the script owns vs what stays human-owned:

  SCRIPT-OWNED (git-derived, inside marked blocks only):
    branch name, HEAD hash, session commits not on master, sync timestamp.
  HUMAN-OWNED (everything else):
    prose, judgments, decisions, gate numbers from runs, plans, debt, ADRs.

The script never writes outside `<!-- AUTO-*:START -->...<!-- END -->`
markers. Anything outside markers is left byte-identical. If markers are
absent, the block is appended (the "forgot" case) — never inserted
mid-file where it could split prose.

Modes:
  default   rewrite stale blocks in place. Idempotent: a second run with
            no new commits changes nothing (this property is load-bearing —
            the hook runs it on every commit, and --check depends on it).
  --check   verify only: exit 1 listing stale/missing blocks, change
            nothing. For the terminal verification loop and for proving
            the hook ran.
  --stage    after syncing, `git add` exactly the files the script
            modified (never anything else). For the pre-commit hook, so
            synced blocks join the commit being made.

Exit codes: 0 clean (or nothing to do: no state/ dir, no git repo —
bootstrap and tarball flows are unaffected); 1 problems found (--check
only, or an unexpected failure).

Charter references: §4 (claims match artifacts), §20 (a rule with no
check is a preference), §28 (never weaken a check).
"""

from __future__ import annotations

import argparse
import re
import subprocess  # nosec B404 - fixed git argv below, no shell, no user input
import sys
from pathlib import Path

DASHBOARD_START = "<!-- AUTO-SYNC:START -->"
DASHBOARD_END = "<!-- AUTO-SYNC:END -->"
COMMITS_START = "<!-- AUTO-COMMITS:START -->"
COMMITS_END = "<!-- AUTO-COMMITS:END -->"

_SESSION_RE = re.compile(r"state/sessions/[\w\-.]+\.md")


def _git(root: Path, *args: str) -> str | None:
    """Run a fixed git argv. None on any failure (no git, no repo, bad ref)."""
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            # "git" is deliberately resolved through PATH: this must use the
            # same git the developer is using, not a bundled one.
            [  # noqa: S607
                "git",
                "-C",
                str(root),
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _git_facts(root: Path) -> tuple[str, str, list[tuple[str, str]]] | None:
    """Return (branch, head, [(hash, subject), ...]) or None if git unusable."""
    branch = _git(root, "branch", "--show-current")
    head = _git(root, "rev-parse", "--short", "HEAD")
    if branch is None or head is None:
        return None
    if not branch:
        branch = f"(detached HEAD {head})"
    entries: list[tuple[str, str]] = []
    if _git(root, "rev-parse", "--verify", "--quiet", "master") is not None:
        log = _git(root, "log", "master..HEAD", "--format=%h %s")
        if log:
            for line in log.splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    entries.append((parts[0], parts[1]))
    return branch, head, entries


def _dashboard_body(branch: str, head: str, count: int, dirty: bool) -> str:
    # Deliberately timestamp-free: a timestamp would make every run differ
    # from the last, so every commit would dirty these files and --check
    # could never pass except in the minute after a sync. Freshness is
    # proven by re-running, not by a string; history via `git log`.
    lines = [
        DASHBOARD_START,
        "> Branched reality check (auto-synced, git-derived — do not hand-edit):",
        f"> branch `{branch}` at `{head}`; session commits not on master: "
        f"{count} (see `git log master..HEAD --oneline`).",
    ]
    if dirty:
        lines.append("> working tree dirty at sync time — see `git status`.")
    lines.append(DASHBOARD_END)
    return "\n".join(lines) + "\n"


def _commits_body(entries: list[tuple[str, str]], dirty: bool) -> str:
    # Same timestamp-free reasoning as above.
    lines = [
        COMMITS_START,
        "### Synced commits (auto-generated, git-derived — do not hand-edit; `git log` is truth)",
        "",
    ]
    if entries:
        lines.extend(f"- `{h}` {s}" for h, s in entries)
    else:
        lines.append("- _none — branch matches master_")
    if dirty:
        lines.append("- _uncommitted changes present — see `git status`_")
    lines.append(COMMITS_END)
    return "\n".join(lines) + "\n"


def _apply_block(text: str, start: str, end: str, body: str) -> tuple[str, bool]:
    """Return (new_text, changed). Appends the block at EOF if markers absent.

    Replacement is anchored on the exact marker lines, so prose outside the
    block can never be altered. Idempotent: applying an already-fresh body
    returns changed=False.
    """
    pattern = re.compile(
        rf"^{re.escape(start)}\n.*?^{re.escape(end)}\n?",
        re.MULTILINE | re.DOTALL,
    )
    if pattern.search(text):
        new_text = pattern.sub(lambda _: body, text)
        return new_text, new_text != text
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + body, True


def _active_session_files(root: Path) -> list[Path]:
    """Session files owned by agents whose REGISTRY status is Active.

    Scoping to active agents keeps history untouched: old session files are
    records, not living documents, and regenerating their blocks would churn
    them on every commit. Returns repo-relative paths that exist on disk.
    """
    registry = root / "state" / "REGISTRY.md"
    try:
        content = registry.read_text(encoding="utf-8")
    except OSError:
        return []
    found: list[Path] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 7:
            continue
        status = cells[5].lower()
        if "active" not in status or "completed" in status:
            continue
        for match in _SESSION_RE.finditer(cells[6]):
            candidate = root / match.group(0)
            if candidate.is_file() and candidate not in found:
                found.append(candidate)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate git-derived MACP state blocks (idempotent)"
    )
    parser.add_argument(
        "--root", type=Path, default=Path(), help="repository root (default: cwd)"
    )
    parser.add_argument("--quiet", action="store_true", help="print only problems")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify only: exit 1 if any block is missing or stale",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="git-add exactly the files this run modified",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not (root / "state").is_dir() or not (root / ".git").exists():
        return 0

    facts = _git_facts(root)
    if facts is None:
        if not args.quiet:
            print("sync_state: git unavailable — skipping (environment, not an error)")
        return 0
    branch, head, entries = facts
    dirty = bool(_git(root, "status", "--porcelain"))

    targets: list[tuple[Path, str]] = [
        (
            root / "state" / "DASHBOARD.md",
            _dashboard_body(branch, head, len(entries), dirty),
        )
    ]
    for session_path in _active_session_files(root):
        targets.append((session_path, _commits_body(entries, dirty)))

    # Dirty-tree disclosure lines are transient snapshots ("at sync time"),
    # not stable claims: the tree is dirty during every pre-commit sync by
    # definition, and clean right after. Comparing them in --check mode would
    # make verification fail on every just-committed tree until the next
    # sync — flapping, not signal. Normalize them away on BOTH sides here;
    # write mode still records them (disclosure matters in the record).
    _dirty_re = re.compile(r"^.*(?:working tree dirty|uncommitted changes present).*$")

    def _normalized(block: str) -> str:
        return "\n".join(
            line for line in block.splitlines() if not _dirty_re.match(line)
        )

    problems: list[str] = []
    changed_files: list[Path] = []
    for path, body in targets:
        start = DASHBOARD_START if path.name == "DASHBOARD.md" else COMMITS_START
        end = DASHBOARD_END if path.name == "DASHBOARD.md" else COMMITS_END
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            problems.append(f"{path}: unreadable")
            continue
        new_text, changed = _apply_block(text, start, end, body)
        if args.check:
            _, check_changed = _apply_block(
                _normalized(text), start, end, _normalized(body)
            )
            if check_changed:
                problems.append(f"{path}: block missing or stale")
        elif changed:
            path.write_text(new_text, encoding="utf-8")
            changed_files.append(path)

    if args.check and problems:
        for problem in problems:
            print(problem)
        return 1
    if not args.quiet and changed_files and not args.check:
        for path in changed_files:
            print(f"sync_state: refreshed {path.relative_to(root)}")

    if args.stage and changed_files and not args.check:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, paths from own scan
            # Same PATH reasoning as above.
            [  # noqa: S607
                "git",
                "-C",
                str(root),
                "add",
                "--",
                *(str(p.relative_to(root)) for p in changed_files),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"sync_state: git add failed: {proc.stderr.strip()}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
