#!/usr/bin/env python3
"""Verify no session claims completion without maintainer authorization.

A session file in state/sessions/ may only carry a completion marker
(Status/Outcome Completed|Closed, "claims released") if it also records an
explicit maintainer close directive on a `Close-Authorized-By:` line naming
the directive and its date. The same rule extends by coherence: a completion
marker for an agent in state/REGISTRY.md or state/INDEX.md requires that
agent's session file to carry a valid authorization, and a completion claim
with no matching session file fails as dangling.

Why this check exists: on 2026-10-08 an agent marked its own session
Completed, released its registry claims, and logged the closure — on its own
authority, with every gate green before, during, and after. The shutdown
sequence was prose, and prose is not enforcement. See ADR-0030.

WHAT THIS SCRIPT DOES NOT DO
----------------------------
It does not verify the maintainer actually uttered the directive. No
tree-local check can — a fabricated authorization line passes this gate, just
as a well-formed lie passes the commit-msg format check. What the gate
removes is *silent* closure: without authorization on record the build fails,
and with a fabricated one the diff carries a signed, dated, falsifiable
claim. That is the same bar as every other gate in this repository, and it
is stated here rather than implied (charter §4).

Charter references: §4 (claims must match artifacts), §20 (a rule with no
check is a preference), §25 (session protocol).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = REPO_ROOT / "state" / "sessions"
REGISTRY = REPO_ROOT / "state" / "REGISTRY.md"
INDEX = REPO_ROOT / "state" / "INDEX.md"

# Completion markers. Deliberately narrow: bare words like "complete" appear
# in ordinary prose ("reconnaissance complete", "Recently Completed"), so
# only the lifecycle fields and the claims-release phrase count.
CLOSURE_RES = (
    re.compile(
        r"^\s*[-*]?\s*\*{0,2}Status:\*{0,2}\s*(Completed|Closed)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^\s*[-*]?\s*\*{0,2}Outcome:\*{0,2}\s*COMPLETED\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(r"claims released", re.IGNORECASE),
)

AUTH_RE = re.compile(r"^\s*Close-Authorized-By:\s*(.+?)\s*$", re.MULTILINE)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class Violation:
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}"


def _closure_markers(text: str) -> list[str]:
    """Return the matched marker strings (for diagnostics), else []."""
    found: list[str] = []
    for rx in CLOSURE_RES:
        found.extend(m.group(0).strip() for m in rx.finditer(text))
    return found


def _authorization(text: str) -> str | None:
    """Return the authorization value if valid, else None.

    Valid means: a Close-Authorized-By line exists, its value is non-empty,
    and it carries a date (YYYY-MM-DD). The date requirement exists so the
    record pins *which* directive authorized *this* closure — an undated
    line can be copied forward forever without saying anything.
    """
    m = AUTH_RE.search(text)
    if m is None:
        return None
    value = m.group(1).strip()
    if not value or DATE_RE.search(value) is None:
        return None
    return value


def check_session_file(path: Path) -> list[Violation]:
    """A session file with a closure marker must carry authorization."""
    text = path.read_text(encoding="utf-8")
    markers = _closure_markers(text)
    if not markers:
        return []
    if _authorization(text) is not None:
        return []
    return [
        Violation(
            str(path),
            f"claims completion ({markers[0]!r}) without a valid "
            "`Close-Authorized-By:` line naming the maintainer directive "
            "and its date (ADR-0030)",
        )
    ]


def _table_rows(text: str) -> list[tuple[str, str, str]]:
    """Parse markdown table rows as (agent-id, status-cell, full-line) triples.

    Registry tables are positional — the status cell carries no "Status:"
    label — so the status column (6th) is inspected directly in addition to
    a whole-row scan for the claims-release phrase. Header and separator
    rows are skipped. Inspection is row-local on purpose: one agent's
    completion marker must never implicate another agent's row via a
    character window.
    """
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if not first or set(first) <= set("-: "):
            continue  # separator row
        if first.lower() in {"agent id", "agent"}:
            continue  # header row
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", first):
            continue  # not an agent-ID row
        status = cells[5] if len(cells) > 5 else ""
        rows.append((first, status, line))
    return rows


def _index_entries(text: str) -> list[tuple[str, str]]:
    """Split INDEX.md into (agent-id, entry-block) pairs.

    Blocks run from one `- **Agent:**` line to the next, so entry-scoped
    inspection cannot leak markers across entries.
    """
    id_pattern = re.compile(
        r"^-\s*\*\*Agent:\*\*\s*([A-Za-z][A-Za-z0-9_-]*)", re.MULTILINE
    )
    matches = list(id_pattern.finditer(text))
    entries: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entries.append((m.group(1), text[m.start() : end]))
    return entries


def _session_file_for(agent_id: str, sessions_dir: Path) -> Path | None:
    """Session files follow YYYYMMDD-HHMM-<AGENT-ID>-<slug>.md."""
    matches = sorted(sessions_dir.glob(f"*-{agent_id}-*.md"))
    return matches[0] if matches else None


def check_registry(registry: Path, sessions_dir: Path) -> list[Violation]:
    """REGISTRY completion markers require an authorized session file."""
    if not registry.exists():
        return [Violation(str(registry), "registry file is missing")]
    text = registry.read_text(encoding="utf-8")
    violations: list[Violation] = []
    for agent_id, status, row in _table_rows(text):
        status_closed = (
            re.match(r"(Completed|Closed)\b", status, re.IGNORECASE) is not None
        )
        if not status_closed and not _closure_markers(row):
            continue
        session = _session_file_for(agent_id, sessions_dir)
        if session is None:
            violations.append(
                Violation(
                    str(registry),
                    f"agent {agent_id!r} is marked complete with no matching "
                    f"session file (*-{agent_id}-*.md): dangling completion claim",
                )
            )
            continue
        if _authorization(session.read_text(encoding="utf-8")) is None:
            violations.append(
                Violation(
                    str(registry),
                    f"agent {agent_id!r} is marked complete but "
                    f"{session.name} carries no valid `Close-Authorized-By:` "
                    "line (ADR-0030)",
                )
            )
    return violations


def check_index(index: Path, sessions_dir: Path) -> list[Violation]:
    """INDEX completion entries require an authorized session file."""
    if not index.exists():
        return [Violation(str(index), "index file is missing")]
    text = index.read_text(encoding="utf-8")
    violations: list[Violation] = []
    for agent_id, block in _index_entries(text):
        if not _closure_markers(block):
            continue
        session = _session_file_for(agent_id, sessions_dir)
        if session is None:
            violations.append(
                Violation(
                    str(index),
                    f"agent {agent_id!r} is logged complete with no matching "
                    f"session file (*-{agent_id}-*.md): dangling completion claim",
                )
            )
            continue
        if _authorization(session.read_text(encoding="utf-8")) is None:
            violations.append(
                Violation(
                    str(index),
                    f"agent {agent_id!r} is logged complete but "
                    f"{session.name} carries no valid `Close-Authorized-By:` "
                    "line (ADR-0030)",
                )
            )
    return violations


def run_all(
    sessions_dir: Path | None = None,
    registry: Path | None = None,
    index: Path | None = None,
) -> list[Violation]:
    # Defaults resolve at call time (not def time) so tests can redirect
    # the module globals and exercise main() against fixture trees.
    if sessions_dir is None:
        sessions_dir = SESSIONS_DIR
    if registry is None:
        registry = REGISTRY
    if index is None:
        index = INDEX
    violations: list[Violation] = []
    if sessions_dir.is_dir():
        for path in sorted(sessions_dir.glob("*.md")):
            violations.extend(check_session_file(path))
    else:
        violations.append(Violation(str(sessions_dir), "sessions directory is missing"))
    violations.extend(check_registry(registry, sessions_dir))
    violations.extend(check_index(index, sessions_dir))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail if any session claims completion without "
        "maintainer authorization (ADR-0030)."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print only violations, no summary"
    )
    args = parser.parse_args(argv)

    violations = run_all()
    for v in violations:
        print(f"session-closure: error: {v}")
    if violations:
        print(f"session-closure: {len(violations)} violation(s)")
        return 1
    if not args.quiet:
        print("session-closure: 0 violation(s); all completions authorized")
    return 0


if __name__ == "__main__":
    sys.exit(main())
