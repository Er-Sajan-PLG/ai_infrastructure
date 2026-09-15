#!/usr/bin/env python3
"""Verify that documented phase plans agree with the charter's lifecycle order.

Why this exists
---------------
``docs/phases/phase-1-seed.md`` described the per-capability session pattern as
session B producing ``DECIDED`` and session C producing ``DESIGNED``. Charter §4
orders the lifecycle ``... UNDERSTOOD -> DESIGNED -> DECIDED -> ...``, so the two
were in direct contradiction.

The contradiction was not cosmetic. ``scripts/repo_status.py`` enforces that a
``DECIDED`` claim has a specification on disk, because ``DESIGNED`` precedes
``DECIDED``. A session following the (wrong) plan would write the ADR first, set
``DECIDED``, and be told its claim was invalid — with the plan as its authority
for doing so. The check below makes that impossible to reintroduce silently.

Usage::

    python scripts/check_phase_plan.py [--root PATH] [--quiet]

Exits 1 when a documented stage transition contradicts the charter order.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The charter §4 order. Kept as a literal list rather than imported from
# repo_status so that a change to the enforced order and a change to the
# documented order cannot happen in the same silent edit: if the lifecycle ever
# changes, both files must be edited, and this one cites the charter section it
# is checking against.
LIFECYCLE: tuple[str, ...] = (
    "DISCOVERED",
    "RESEARCHED",
    "UNDERSTOOD",
    "DESIGNED",
    "DECIDED",
    "PROTOTYPED",
    "IMPLEMENTED",
    "TESTED",
    "BENCHMARKED",
    "INTEGRATED",
    "MATURE",
    "DEPRECATED",
)
_INDEX = {stage: i for i, stage in enumerate(LIFECYCLE)}

# Matches an arrow-chain of stage names inside backticks, e.g.
# `RESEARCHED → UNDERSTOOD → DECIDED`. The arrow may be a real arrow or "->".
_CHAIN = re.compile(r"`\s*([A-Z_]+(?:\s*(?:→|->)\s*[A-Z_]+)+)\s*`")
_SPLIT = re.compile(r"\s*(?:→|->)\s*")

# Files whose stage chains are checked. Anything under docs/phases/ is included
# by glob; this list holds documents outside that directory that also describe
# the lifecycle.
_EXTRA_FILES: tuple[str, ...] = (
    "TAXONOMY.md",
    "AGENTS.md",
)


def iter_chains(text: str) -> list[tuple[str, ...]]:
    """Return every stage chain found in ``text`` as a tuple of stage names."""
    chains: list[tuple[str, ...]] = []
    for match in _CHAIN.finditer(text):
        parts = tuple(p.strip() for p in _SPLIT.split(match.group(1)) if p.strip())
        # Only chains made entirely of known stages are lifecycle claims; a
        # backticked arrow of non-stage words is some other notation.
        if len(parts) >= 2 and all(p in _INDEX for p in parts):
            chains.append(parts)
    return chains


def find_violations(root: Path) -> list[tuple[Path, tuple[str, ...]]]:
    """Return ``(file, chain)`` for every chain that contradicts the charter."""
    targets: list[Path] = []
    phases_dir = root / "docs" / "phases"
    if phases_dir.is_dir():
        targets.extend(sorted(phases_dir.rglob("*.md")))
    for rel in _EXTRA_FILES:
        candidate = root / rel
        if candidate.is_file():
            targets.append(candidate)

    violations: list[tuple[Path, tuple[str, ...]]] = []
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for chain in iter_chains(text):
            indices = [_INDEX[stage] for stage in chain]
            if indices != sorted(indices):
                violations.append((path.relative_to(root), chain))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check documented stage transitions against charter §4."
    )
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--quiet", action="store_true", help="print only the summary")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    violations = find_violations(root)

    for path, chain in violations:
        if not args.quiet:
            print(f"OUT OF ORDER  {path}: {' → '.join(chain)}")

    print(
        f"\ncheck_phase_plan: {len(violations)} out-of-order transition(s); "
        f"charter §4 order is {' → '.join(LIFECYCLE)}"
    )
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
