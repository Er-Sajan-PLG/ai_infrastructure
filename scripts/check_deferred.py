#!/usr/bin/env python3
"""Verify the deferred-work register is well-formed, current, and honest.

The register (docs/DEFERRED.md) records work that is deliberately NOT done yet
because a specific present-day fact makes it premature. Its value depends
entirely on two fields being real:

  * `current_fact` -- the reason it is premature, stated so it can be checked
  * `trigger`      -- the condition that would make it worth doing

This script enforces the mechanical properties of those fields, and adds the
same anti-gaming control as the accepted-risk register: `review_by` may not
ADVANCE while nothing else about the entry changes. A deferral review whose
only output is a later date is not a review.

WHAT THIS SCRIPT DOES NOT DO
----------------------------
It does not decide whether a trigger has fired. Triggers are prose describing
observable conditions ("a git tag exists", "a second contributor appears"),
and several are not mechanically detectable -- "a defect was found that the
tests missed" cannot be read from the repository at all. Claiming a check that
verified prose would be exactly the dishonesty charter §4 forbids.

Instead it does the two things it CAN do honestly:
  1. enforce that every entry HAS a specific, non-empty trigger and reversal,
     so the register cannot decay into a list of good intentions;
  2. where a trigger names a condition this script CAN observe, print it as a
     POSSIBLE TRIGGER FIRE for a human to adjudicate.

Charter references: §4 (claims must match artifacts), §8 (DEFER is a decision
and must be recorded), §20 (a rule with no check is a preference), §26 step 4.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "docs" / "DEFERRED.md"

MIN_EXPECTED_ENTRIES = 8
WARN_HORIZON_DAYS = 30
MAX_REVIEW_WINDOW_DAYS = 400

ID_RE = re.compile(r"^DW-\d{3}$")

CATEGORY_ENUM = frozenset(
    {
        "scale",
        "performance",
        "operability",
        "security",
        "governance",
        "tooling",
        "quality",
    }
)

EFFORT_ENUM = frozenset({"small", "medium", "large"})

REQUIRED_FIELDS = (
    "id",
    "title",
    "category",
    "current_fact",
    "why_now_wrong",
    "trigger",
    "reversal",
    "effort",
    "source",
    "review_by",
    "adr",
)

_FENCED_YAML_RE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)

# Minimum useful length for the two fields the register lives or dies on. A
# trigger of "when it matters" is not a trigger, and this floor is what stops
# the register from being filled with them.
MIN_FIELD_LENGTH = 25

# Observable conditions, mapped to a probe. These are printed as POSSIBLE
# FIRES, never as failures: the probe tells a human "this may have happened",
# and the human decides. Only conditions that are genuinely readable from the
# repository are listed.
_OBSERVABLE_TRIGGERS: tuple[tuple[str, str], ...] = (
    (
        "git tag exists",
        "a git tag or a published artifact exists",
    ),
    (
        "runtime dependency added",
        "a runtime dependency was added",
    ),
)


@dataclass(frozen=True)
class DeferredItem:
    """One register entry, with the fields this checker reasons about."""

    id: str
    title: str
    category: str
    trigger: str
    reversal: str
    current_fact: str
    review_by: str
    raw: dict[str, object]


def _load_yaml_block() -> str | None:
    """Extract the register's machine-readable fenced block.

    The FIRST fenced yaml block is the register; the later one is the
    copy-paste template and is deliberately not parsed.
    """
    if not REGISTER.exists():
        return None
    text = REGISTER.read_text(encoding="utf-8")
    blocks = _FENCED_YAML_RE.findall(text)
    if not blocks:
        return None
    return str(blocks[0])


def _parse(text: str) -> tuple[list[DeferredItem], list[str]]:
    """Parse the register, returning (items, problems)."""
    import yaml

    problems: list[str] = []
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return [], ["register did not parse to a mapping"]

    entries = data.get("deferred")
    if not isinstance(entries, list):
        return [], ["register has no 'deferred' list"]

    items: list[DeferredItem] = []
    seen: set[str] = set()

    for index, entry in enumerate(entries):
        where = f"deferred[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: not a mapping")
            continue

        identifier = str(entry.get("id", "")).strip()
        if not ID_RE.match(identifier):
            problems.append(f"{where}: id {identifier!r} is not of the form DW-NNN")
        elif identifier in seen:
            problems.append(f"{where}: duplicate id {identifier}")
        else:
            seen.add(identifier)
        where = identifier or where

        for field in REQUIRED_FIELDS:
            value = entry.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                problems.append(f"{where}: missing required field {field!r}")

        category = str(entry.get("category", "")).strip()
        if category and category not in CATEGORY_ENUM:
            problems.append(
                f"{where}: category {category!r} not in {sorted(CATEGORY_ENUM)}"
            )

        effort = str(entry.get("effort", "")).strip()
        if effort and effort not in EFFORT_ENUM:
            problems.append(f"{where}: effort {effort!r} not in {sorted(EFFORT_ENUM)}")

        # The two fields the register exists for must be SPECIFIC, not merely
        # present. A length floor is crude, but it is the difference between a
        # register and a list of good intentions, and it is measurable.
        for field in ("current_fact", "trigger", "reversal"):
            value = str(entry.get(field, "")).strip()
            if value and len(value) < MIN_FIELD_LENGTH:
                problems.append(
                    f"{where}: {field} is only {len(value)} characters. This "
                    f"field is the register's entire value; a stub here makes "
                    f"the entry unactionable."
                )

        adr = str(entry.get("adr", "")).strip()
        if adr and not re.match(r"^ADR-\d{4}$", adr):
            problems.append(
                f"{where}: adr {adr!r} is not of the form ADR-NNNN. Every "
                f"deferral is a DECIDE-stage decision (charter §8) and must "
                f"cite the record that made it."
            )

        items.append(
            DeferredItem(
                id=identifier,
                title=str(entry.get("title", "")).strip(),
                category=category,
                trigger=str(entry.get("trigger", "")).strip(),
                reversal=str(entry.get("reversal", "")).strip(),
                current_fact=str(entry.get("current_fact", "")).strip(),
                review_by=str(entry.get("review_by", "")).strip(),
                raw=entry,
            )
        )

    return items, problems


def _has_git_tag() -> bool:
    """True if the repository has at least one tag."""
    proc = subprocess.run(
        ["git", "tag", "-l"],  # noqa: S607 - "git" via PATH, as the developer uses
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(proc.stdout.strip())


def _has_runtime_dependency() -> bool:
    """True if pyproject.toml declares any runtime dependency.

    Parsed with tomllib rather than a regex, so a commented-out dependency or
    a mention in prose cannot be mistaken for a real one.
    """
    import tomllib

    path = REPO_ROOT / "pyproject.toml"
    if not path.exists():
        return False
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    dependencies = data.get("project", {}).get("dependencies", [])
    return bool(dependencies)


def _previous_version() -> str | None:
    """The register's content at HEAD, or None when unavailable."""
    try:
        # S603/S607: fixed argv, no shell, no user input; "git" is resolved
        # through PATH deliberately so this uses the developer's own git.
        proc = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "git",
                "show",
                f"HEAD:{REGISTER.relative_to(REPO_ROOT).as_posix()}",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _parse_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the deferred-work register.")
    parser.add_argument("--quiet", action="store_true", help="print only problems")
    parser.add_argument(
        "--today", help="override today's date (YYYY-MM-DD); for testing"
    )
    args = parser.parse_args(argv)

    today = (
        dt.date.fromisoformat(args.today)
        if args.today
        else dt.date.today()  # noqa: DTZ011
    )

    text = _load_yaml_block()
    if text is None:
        print(
            f"check_deferred: FAILED - no fenced yaml block found in "
            f"{REGISTER.relative_to(REPO_ROOT)}.",
            file=sys.stderr,
        )
        print(
            "  The register's machine-readable source is a fenced yaml block; "
            "refusing to pass a check that read nothing.",
            file=sys.stderr,
        )
        return 1

    items, problems = _parse(text)

    # Anti-silent-skip floor: an empty parse is a failure, not a pass.
    if len(items) < MIN_EXPECTED_ENTRIES:
        problems.append(
            f"parsed only {len(items)} deferred item(s); expected at least "
            f"{MIN_EXPECTED_ENTRIES}. This usually means the block failed to "
            f"parse, not that every deferral was implemented."
        )

    warnings: list[str] = []
    for item in items:
        review = _parse_date(item.review_by)
        if review is None:
            problems.append(f"{item.id}: review_by is not a YYYY-MM-DD date")
            continue
        days_left = (review - today).days
        if days_left < 0:
            problems.append(
                f"{item.id} ({item.title}): review OVERDUE by {abs(days_left)} "
                f"day(s) (was due {item.review_by}). Re-read the trigger and "
                f"either implement it, or update current_fact with the new "
                f"reason for deferring."
            )
        elif days_left <= WARN_HORIZON_DAYS:
            warnings.append(
                f"{item.id} ({item.title}): review due in {days_left} day(s) "
                f"on {item.review_by}."
            )

    # --- Re-dating check (the anti-gaming control) ------------------------
    previous = _previous_version()
    if previous is None:
        if not args.quiet:
            print(
                "check_deferred: note - previous version of the register is "
                "not available; re-dating check skipped for this run."
            )
    else:
        old_blocks = _FENCED_YAML_RE.findall(previous)
        if old_blocks:
            old_items, _ = _parse(str(old_blocks[0]))
            old_by_id = {i.id: i for i in old_items}
            for item in items:
                old = old_by_id.get(item.id)
                if old is None:
                    continue
                if (
                    item.review_by > old.review_by
                    and item.current_fact == old.current_fact
                    and item.trigger == old.trigger
                ):
                    problems.append(
                        f"{item.id}: review_by moved {old.review_by} -> "
                        f"{item.review_by} but neither current_fact nor "
                        f"trigger changed. Re-dating without reconsidering is "
                        f"refused; if the deferral was genuinely re-examined, "
                        f"update current_fact or trigger."
                    )

    # --- Possible trigger fires (advisory only) ---------------------------
    # Reported, never failed on: see the module docstring for why prose
    # triggers cannot be adjudicated mechanically.
    fires: list[str] = []
    if _has_git_tag():
        fires.append(
            "DW-001 (signed releases), DW-002 (SBOM) and DW-006 (branch "
            "protection) are conditioned on a published artifact: this "
            "repository NOW HAS at least one git tag. Their `current_fact` "
            "fields may no longer be true."
        )
    if _has_runtime_dependency():
        fires.append(
            "DW-002 (SBOM) and DW-011 (scancode) are conditioned on a runtime "
            "dependency existing: pyproject.toml NOW DECLARES one. Re-read "
            "their `current_fact` fields."
        )

    # --- Report -----------------------------------------------------------
    if problems:
        print("", file=sys.stderr)
        for problem in problems:
            print(f"check_deferred: {problem}", file=sys.stderr)
        print(
            f"\ncheck_deferred: {len(problems)} problem(s) across "
            f"{len(items)} deferred item(s).",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        for warning in warnings:
            print(f"check_deferred: WARNING - {warning}")
        for fire in fires:
            print(f"check_deferred: POSSIBLE TRIGGER FIRE - {fire}")
        by_category: dict[str, int] = {}
        for item in items:
            by_category[item.category] = by_category.get(item.category, 0) + 1
        summary = ", ".join(
            f"{count} {category}" for category, count in sorted(by_category.items())
        )
        print(
            f"check_deferred: {len(items)} deferred item(s) current ({summary}); "
            f"none overdue."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
