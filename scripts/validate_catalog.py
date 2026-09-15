#!/usr/bin/env python3
"""Validate that every catalog entry meets the repository's entry contract.

Charter §13 (Implementation Standards) requires each recreated infrastructure
piece to ship a README, a PROVENANCE.md, an implementation, examples, and
tests. Charter §4 requires that lifecycle status never claim more than the
artifacts that actually exist. This script enforces the structural half of
that contract; it cannot judge whether content is any good.

A "catalog entry" is any immediate subdirectory of a category directory under
catalog/ that is not itself a category. Category READMEs (the category-level
documentation required by charter §13) are checked separately and only for the
required headings.

Usage:
    python scripts/validate_catalog.py [--root PATH] [--strict]

Exit codes:
    0  all present entries satisfy the contract
    1  one or more violations found
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Category directories declared in TAXONOMY.md §1. A category directory holds
# entries; its own README.md is category documentation, not an entry.
CATEGORIES: tuple[str, ...] = (
    "primitives",
    "runtime",
    "agents",
    "skills",
    "harness",
    "tools",
    "protocols",
    "memory",
    "retrieval",
    "evaluation",
    "safety",
    "governance",
    "orchestration",
    "observability",
    "models",
    "data",
    "deployment",
    "prompt-engineering",
    "finetuning",
    "frameworks",
)

# Headings required in every category README.md (charter §13, Category
# Documentation Standard). Matched case-insensitively as a prefix of an H2.
REQUIRED_CATEGORY_SECTIONS: tuple[str, ...] = (
    "what it is",
    "why it exists",
)

# Files/dirs required in every catalog entry.
REQUIRED_ENTRY_PATHS: tuple[str, ...] = (
    "README.md",
    "PROVENANCE.md",
)

# Sections required in every catalog entry README.md.
REQUIRED_ENTRY_SECTIONS: tuple[str, ...] = (
    "what it is",
    "how it works",
    "our implementations",
    "references",
)

# Files/dirs that count as "an implementation exists". Tests and examples are
# warned about rather than failed until the first entry lands, so the skeleton
# can be validated before any implementation exists (--strict upgrades these).
SOFT_ENTRY_PATHS: tuple[str, ...] = ("examples", "tests")

# An entry's tests/ directory must contain real test files. An empty directory
# satisfies "exists" while proving nothing, which is the exact failure charter
# §4 forbids: a status claim the artifacts do not support. Enforced in BOTH
# normal and strict mode, because "the directory is there" is never evidence.
#
# This was a real hole: an entry with an empty tests/ passed --strict, and
# pyproject.toml's testpaths never looked in catalog/ at all, so a capability
# could ship tests that never ran while every gate stayed green.
TEST_FILE_GLOB: str = "test_*.py"


@dataclass
class Report:
    """Collected validation findings."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, path: Path, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def warn(self, path: Path, message: str) -> None:
        self.warnings.append(f"{path}: {message}")


def _headings(text: str) -> list[str]:
    """Return lowercased H2 heading texts from markdown `text`."""
    found: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            found.append(stripped[3:].strip().lower())
    return found


def _has_section(text: str, section: str) -> bool:
    """True when some H2 heading starts with `section`."""
    return any(h.startswith(section) for h in _headings(text))


def _read_markdown(path: Path) -> str | None:
    """Read a markdown file, returning None when unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def validate(root: Path, strict: bool) -> Report:
    """Validate the catalog tree rooted at `root`."""
    report = Report()
    catalog = root / "catalog"

    if not catalog.is_dir():
        report.error(catalog, "catalog directory not found")
        return report

    # 1. Declared category directories must exist and carry category docs.
    for category in CATEGORIES:
        category_dir = catalog / category
        if not category_dir.is_dir():
            report.error(category_dir, "declared category directory is missing")
            continue

        readme = category_dir / "README.md"
        if not readme.is_file():
            report.error(readme, "category README.md is missing")
            continue

        text = _read_markdown(readme)
        if text is None:
            report.error(readme, "unreadable (not valid UTF-8?)")
            continue

        for section in REQUIRED_CATEGORY_SECTIONS:
            if not _has_section(text, section):
                report.error(readme, f"missing required section '## {section}'")

    # 2. Any subdirectory of a category is an entry and must meet the contract.
    for category in CATEGORIES:
        category_dir = catalog / category
        if not category_dir.is_dir():
            continue

        for entry in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            if entry.name.startswith((".", "_")):
                continue

            for required in REQUIRED_ENTRY_PATHS:
                if not (entry / required).is_file():
                    report.error(entry / required, "required entry file is missing")

            readme = entry / "README.md"
            if readme.is_file():
                text = _read_markdown(readme)
                if text is None:
                    report.error(readme, "unreadable (not valid UTF-8?)")
                else:
                    for section in REQUIRED_ENTRY_SECTIONS:
                        if not _has_section(text, section):
                            report.error(
                                readme, f"missing required section '## {section}'"
                            )

            for soft in SOFT_ENTRY_PATHS:
                if not (entry / soft).is_dir():
                    message = f"entry has no {soft}/ directory"
                    if strict:
                        report.error(entry / soft, message)
                    else:
                        report.warn(entry, message)

            # A tests/ directory that exists but is empty (or holds no test
            # files) is never evidence. This is an error in every mode: the
            # directory's presence is what the contract asks for, but its
            # contents are what the claim depends on.
            tests_dir = entry / "tests"
            if tests_dir.is_dir():
                test_files = sorted(tests_dir.rglob(TEST_FILE_GLOB))
                if not test_files:
                    report.error(
                        tests_dir,
                        f"tests/ directory contains no {TEST_FILE_GLOB} files — "
                        "an empty or placeholder tests/ directory is not evidence "
                        "of testing (charter §4, §18)",
                    )
            elif strict:
                report.error(
                    tests_dir,
                    "entry has no tests/ directory (required in strict mode)",
                )

            examples_dir = entry / "examples"
            if examples_dir.is_dir():
                contents = [p for p in examples_dir.rglob("*") if p.is_file()]
                if not contents:
                    report.error(
                        examples_dir,
                        "examples/ directory is empty — remove it or add a real "
                        "example (charter §13)",
                    )

            provenance = entry / "PROVENANCE.md"
            if provenance.is_file():
                text = _read_markdown(provenance)
                if text is None:
                    report.error(provenance, "unreadable (not valid UTF-8?)")

    return report


def count_entries(root: Path) -> int:
    """Count catalog entries present on disk."""
    catalog = root / "catalog"
    if not catalog.is_dir():
        return 0
    total = 0
    for category in CATEGORIES:
        category_dir = catalog / category
        if not category_dir.is_dir():
            continue
        total += sum(
            1
            for p in category_dir.iterdir()
            if p.is_dir() and not p.name.startswith((".", "_"))
        )
    return total


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate the ai_infrastructure catalog entry contract."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root (default: parent of this script's directory)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat missing examples/ and tests/ as errors instead of warnings",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    report = validate(root, args.strict)

    for warning in report.warnings:
        print(f"WARN  {warning}")
    for error in report.errors:
        print(f"ERROR {error}")

    print(
        f"\nvalidate_catalog: {len(report.errors)} error(s), "
        f"{len(report.warnings)} warning(s); "
        f"{count_entries(root)} catalog entry(ies) present"
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
