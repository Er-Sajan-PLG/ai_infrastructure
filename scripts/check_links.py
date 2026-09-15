#!/usr/bin/env python3
"""Verify that relative links in Markdown resolve to real files.

Why this exists
--------------
41 broken links accumulated in this repository undetected: category READMEs
pointed at ``../docs/...`` when the correct path was ``../../docs/...``, and
stale references survived multiple sessions. Every quality gate looked green.

A broken link is a charter §4 problem in miniature: the documentation *claims* a
target exists and nothing checks the claim. Documentation is part of the
knowledge plane this repository treats as a primary deliverable, so a dangling
reference is a defect, not cosmetics.

Usage::

    python scripts/check_links.py [--root PATH] [--quiet]

Exits 1 when any relative link is broken.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Matches [text](target) and [text](target#anchor).
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")

# Directories that never contain documentation we own.
_SKIP_DIRS = frozenset(
    {".git", ".venv", ".uv-cache", ".ruff_cache", ".mypy_cache", ".pytest_cache"}
)

_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:")


def _iter_markdown(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if not any(part in _SKIP_DIRS for part in path.parts)
    )


def find_broken_links(root: Path) -> list[tuple[Path, str]]:
    """Return ``(file, link)`` for every relative link that does not resolve."""
    broken: list[tuple[Path, str]] = []
    for md in _iter_markdown(root):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in _LINK_RE.finditer(text):
            target = match.group(1).strip()
            if (
                not target
                or target.startswith(_EXTERNAL_PREFIXES)
                or target.startswith("#")
            ):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            if not (md.parent / path_part).exists():
                broken.append((md.relative_to(root), target))
    return broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check relative Markdown links resolve."
    )
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--quiet", action="store_true", help="print only the summary")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    broken = find_broken_links(root)

    if broken and not args.quiet:
        for md, link in broken:
            print(f"BROKEN  {md}: {link}")

    total = sum(
        len(_LINK_RE.findall(p.read_text(encoding="utf-8")))
        for p in _iter_markdown(root)
    )
    print(
        f"\ncheck_links: {len(broken)} broken of {total} link(s) checked "
        f"across {len(_iter_markdown(root))} file(s)"
    )
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
