#!/usr/bin/env python3
"""Check that narrative state documents agree with authoritative repository state.

This is the gate that prevents the "8 capabilities / 1337 tests / 36 ADRs"
stale-state class of drift: a document that names a number that no longer
matches the repository is a CI failure, not a nit.

Authority (in order):
  1. TAXONOMY.md status fields (TESTED / DECIDED counts)
  2. docs/decisions/NNNN-*.md file count (ADR count)
  3. specifications/ file count
  4. research/ file count
  5. catalog/ directories containing __init__.py (real capability entries)
  6. integrations/ directories

Scope: only "current-state" narrative documents. Historical records (ADRs,
session logs, roadmap, deferred register, research registry, ADRs) are
intentionally excluded because their numbers are snapshots of a past moment.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Current-state narrative documents only. Historical records are excluded
# deliberately (see module docstring).
SCANNED_DOCS = [
    "README.md",
    "docs/architecture.md",
    "docs/gap-analysis-report.md",
    "state/BLOCKERS.md",
    "state/INDEX.md",
    "state/DASHBOARD.md",
    "examples/README.md",
]

# Patterns that are known-stale claims from the 2026-10 audit. Any hit in a
# scanned doc is a failure. Each maps to the authoritative replacement.
STALE_PATTERNS = [
    (re.compile(r"\b8 capabilities\b"), "13 capabilities (13 TESTED)"),
    (re.compile(r"\b8 catalog entries\b"), "13 catalog entries"),
    (re.compile(r"\b8 TESTED\b"), "13 TESTED"),
    (re.compile(r"\b8 of 30"), "13 of 29 declared categories"),
    (re.compile(r"\b1337\b"), "1570 tests"),
    (re.compile(r"\b1338\b"), "1570 tests"),
    (re.compile(r"\b36 ADR"), "42 ADRs"),
    (re.compile(r"\b102 symbols\b"), "175 symbols"),
]


def authoritative_counts() -> dict[str, int]:
    taxonomy = (ROOT / "TAXONOMY.md").read_text()
    return {
        "tested": len(re.findall(r"^\s*status:\s*TESTED\s*$", taxonomy, re.M)),
        "decided": len(re.findall(r"^\s*status:\s*DECIDED\s*$", taxonomy, re.M)),
        "adrs": len(
            list((ROOT / "docs" / "decisions").glob("[0-9][0-9][0-9][0-9]-*.md"))
        ),
        "specs": len(list((ROOT / "specifications").glob("*.md"))),
        "research": len(list((ROOT / "research").rglob("*.md"))),
        "catalog_entries": sum(
            1
            for p in (ROOT / "catalog").iterdir()
            if p.is_dir()
            for q in p.iterdir()
            if q.is_dir() and (q / "__init__.py").exists()
        ),
        "integrations": sum(1 for p in (ROOT / "integrations").iterdir() if p.is_dir()),
    }


def main() -> int:
    counts = authoritative_counts()
    failures: list[str] = []

    # 1. Stale-pattern scan.
    for rel in SCANNED_DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            for pattern, replacement in STALE_PATTERNS:
                if pattern.search(line):
                    failures.append(
                        f"{rel}:{lineno}: stale claim {pattern.pattern!r} "
                        f"(authoritative: {replacement})"
                    )

    # 2. Positive assertion: README must name the current capability count.
    readme = (ROOT / "README.md").read_text()
    if (
        f"{counts['tested']} capabilities" not in readme
        and f"{counts['tested']} TESTED" not in readme
    ):
        failures.append(
            f"README.md: does not state current TESTED count "
            f"({counts['tested']}); add '{counts['tested']} capabilities' or "
            f"'{counts['tested']} TESTED'"
        )

    # 3. Report authoritative counts for visibility.
    print("Authoritative counts:")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    if failures:
        print("\nDoc-sync failures:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nDoc-sync: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
