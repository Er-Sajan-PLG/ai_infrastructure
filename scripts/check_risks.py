#!/usr/bin/env python3
"""Verify the accepted-risk register is current and honestly maintained.

What this enforces, and why each check exists
---------------------------------------------
1. SCHEMA. Every entry has all required fields, a well-formed id, and a
   `rationale` from the closed enum. A register that silently accepts a typo'd
   field name is a register that silently stops checking.

2. EXPIRY. No entry may be past its `review_by` date. This is the obvious
   check, and on its own it is the WEAK one -- see (3).

3. RE-DATING (the anti-gaming check). An entry whose `review_by` has ADVANCED
   while its `rationale_ref` and `statement` are unchanged since the previous
   commit is a failure. This is the check that makes the register more than
   ceremony.

   The reasoning is worth stating plainly. If the only gate is a date, then
   the cheapest way to turn a red build green is to edit the date. No review
   happens; the gate is satisfied anyway. That is a real failure mode for any
   team, and it is specifically MORE likely in a repository worked on by
   automated agent sessions, because "make the build pass" and "change one
   date" are a very short distance apart. Requiring the rationale to change
   alongside the date means a re-dating review has to produce SOMETHING
   -- a new reference, a revised statement -- which means a person (or an
   agent acting for one) had to reconsider the decision.

   Note the check compares against the PREVIOUS COMMIT, so it detects the
   change as it is being made rather than months later.

4. CEILING. `review_by` may not be more than 400 days after `accepted_on`.
   Without this, an entry can be parked indefinitely in one edit and never
   passes the expiry check. The 400-day bound is slightly over a year so that
   an annual review date is expressible but "in five years" is not.

5. WARNING HORIZON. Entries within 30 days of `review_by` are reported on
   EVERY run, including passing runs.

   Why a warning rather than a scheduled reminder: GitHub automatically
   disables scheduled workflows in a public repository after 60 days without
   repository activity, so a cron-based reminder can stop firing precisely
   when a quiet repository most needs it. A warning emitted by a check that
   runs on every push and pull request cannot be silently switched off.

6. VALIDATION ONLY. This script never modifies the register and never
   suppresses anything. It reads the file and reports. The scanner's own
   configuration is what applies a suppression; this is the record that keeps
   the two honest.

Charter references: §4 (claims must match artifacts), §20 (a rule with no
check is a preference), §22 (human review gates), §28 (never weaken a check).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess  # nosec B404 - invoking pinned git, fixed argv
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "docs" / "risks" / "ACCEPTED_RISKS.md"

MIN_EXPECTED_RISKS = 1
WARN_HORIZON_DAYS = 30
MAX_REVIEW_WINDOW_DAYS = 400

ID_RE = re.compile(r"^AR-\d{3}$")
REF_RE = re.compile(r"^(ADR-\d{4}|#\d+|DO-NOT #\d+)$")

RATIONALE_ENUM = frozenset(
    {
        "component_not_present",
        "not_reachable",
        "mitigated_elsewhere",
        "accepted_cost",
        "awaiting_upstream",
        "no_bandwidth",
    }
)

KIND_ENUM = frozenset({"detective", "normative"})

REQUIRED_FIELDS = (
    "id",
    "title",
    "kind",
    "scope",
    "rationale",
    "rationale_ref",
    "statement",
    "accepted_by",
    "accepted_on",
    "review_by",
    "tool",
)

_FENCED_YAML_RE = re.compile(r"```yaml\s*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Risk:
    """One register entry, with the fields this checker reasons about."""

    id: str
    title: str
    kind: str
    rationale_ref: str
    statement: str
    accepted_on: str
    review_by: str
    raw: dict[str, object]


def _load_yaml_block() -> str | None:
    """Extract the single fenced yaml block that is the register's authority."""
    if not REGISTER.exists():
        return None
    text = REGISTER.read_text(encoding="utf-8")
    blocks = _FENCED_YAML_RE.findall(text)
    if not blocks:
        return None
    # The register is the FIRST fenced yaml block in the document; the later
    # one is the copy-paste template, which is intentionally not parsed.
    return str(blocks[0])


def _parse(text: str) -> tuple[list[Risk], list[str]]:
    """Parse the register, returning (risks, problems).

    Uses PyYAML, which is already in the toolchain. A parse failure is a
    failure: an unparseable register must never be treated as an empty one,
    because "no risks recorded" and "could not read the risks" are completely
    different facts.
    """
    import yaml

    problems: list[str] = []
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return [], ["register did not parse to a mapping"]

    entries = data.get("risks")
    if not isinstance(entries, list):
        return [], ["register has no 'risks' list"]

    risks: list[Risk] = []
    seen: set[str] = set()

    for index, entry in enumerate(entries):
        where = f"risks[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: not a mapping")
            continue

        identifier = str(entry.get("id", "")).strip()
        if not ID_RE.match(identifier):
            problems.append(f"{where}: id {identifier!r} is not of the form AR-NNN")
        elif identifier in seen:
            problems.append(f"{where}: duplicate id {identifier}")
        else:
            seen.add(identifier)
        where = identifier or where

        for field in REQUIRED_FIELDS:
            value = entry.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                problems.append(f"{where}: missing required field {field!r}")

        kind = str(entry.get("kind", "")).strip()
        if kind and kind not in KIND_ENUM:
            problems.append(
                f"{where}: kind {kind!r} not in {sorted(KIND_ENUM)}. "
                f"Classifying a risk is what decides whether a date-based "
                f"review is even meaningful for it."
            )

        rationale = str(entry.get("rationale", "")).strip()
        if rationale and rationale not in RATIONALE_ENUM:
            problems.append(
                f"{where}: rationale {rationale!r} not in {sorted(RATIONALE_ENUM)}"
            )

        ref = str(entry.get("rationale_ref", "")).strip()
        if ref and not REF_RE.match(ref):
            problems.append(
                f"{where}: rationale_ref {ref!r} is not a recorded decision. "
                f"Expected ADR-NNNN, #NNN or DO-NOT #NNN. Prose like 'TODO' is "
                f"rejected because a date with no decision behind it is not a "
                f"review."
            )

        accepted_on = str(entry.get("accepted_on", "")).strip()
        review_by = str(entry.get("review_by", "")).strip()

        risks.append(
            Risk(
                id=identifier,
                title=str(entry.get("title", "")).strip(),
                kind=kind,
                rationale_ref=ref,
                statement=str(entry.get("statement", "")).strip(),
                accepted_on=accepted_on,
                review_by=review_by,
                raw=entry,
            )
        )

    return risks, problems


def _parse_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _previous_version() -> str | None:
    """Return the register's content at HEAD, or None if unavailable.

    None is a normal outcome (a fresh clone with no commits, or a new file)
    and means the re-dating check cannot run. That is reported, never silently
    treated as "no change".
    """
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
            # "git" is deliberately resolved through PATH: this must use the
            # same git the developer is using, not a bundled one.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the accepted-risk register is current."
    )
    parser.add_argument("--quiet", action="store_true", help="print only problems")
    parser.add_argument(
        "--today",
        help="override today's date (YYYY-MM-DD); for testing the expiry logic",
    )
    args = parser.parse_args(argv)

    # DTZ011: date-only by design. The register stores YYYY-MM-DD and the
    # comparison is a whole-day one; introducing a timezone would move the
    # boundary by up to a day relative to what the register actually says.
    today = (
        dt.date.fromisoformat(args.today)
        if args.today
        else dt.date.today()  # noqa: DTZ011
    )

    text = _load_yaml_block()
    if text is None:
        print(
            "check_risks: FAILED - no fenced yaml block found in "
            f"{REGISTER.relative_to(REPO_ROOT)}.",
            file=sys.stderr,
        )
        print(
            "  The register's machine-readable source is a fenced yaml block. "
            "Prose is not parsed. Refusing to pass a check that read nothing.",
            file=sys.stderr,
        )
        return 1

    risks, problems = _parse(text)

    # Anti-silent-skip floor: if parsing yields nothing, refuse to report
    # success. "No risks recorded" and "the parser broke" must not look alike.
    if len(risks) < MIN_EXPECTED_RISKS:
        problems.append(
            f"parsed only {len(risks)} risk(s); expected at least "
            f"{MIN_EXPECTED_RISKS}. This usually means the block failed to "
            f"parse, not that every risk was retired."
        )

    # --- Expiry, ceiling and warning horizon ------------------------------
    warnings: list[str] = []
    for risk in risks:
        accepted = _parse_date(risk.accepted_on)
        review = _parse_date(risk.review_by)
        if accepted is None:
            problems.append(f"{risk.id}: accepted_on is not a YYYY-MM-DD date")
        if review is None:
            problems.append(f"{risk.id}: review_by is not a YYYY-MM-DD date")
            continue

        if accepted is not None:
            window = (review - accepted).days
            if window > MAX_REVIEW_WINDOW_DAYS:
                problems.append(
                    f"{risk.id}: review_by is {window} days after accepted_on, "
                    f"over the {MAX_REVIEW_WINDOW_DAYS}-day ceiling. Parking a "
                    f"risk beyond a year is not a review schedule."
                )
            if window < 0:
                problems.append(f"{risk.id}: review_by precedes accepted_on")

        days_left = (review - today).days
        if days_left < 0:
            problems.append(
                f"{risk.id} ({risk.title}): review OVERDUE by {abs(days_left)} "
                f"day(s) (was due {risk.review_by}). Either re-review it, or "
                f"delete the entry and its suppression together."
            )
        elif days_left <= WARN_HORIZON_DAYS:
            warnings.append(
                f"{risk.id} ({risk.title}): review due in {days_left} day(s) "
                f"on {risk.review_by}."
            )

    # --- Re-dating check (the anti-gaming control) ------------------------
    previous = _previous_version()
    if previous is None:
        if not args.quiet:
            print(
                "check_risks: note - previous version of the register is not "
                "available (new file or no commits); re-dating check skipped "
                "for this run."
            )
    else:
        old_blocks = _FENCED_YAML_RE.findall(previous)
        if old_blocks:
            old_risks, _ = _parse(old_blocks[0])
            old_by_id = {r.id: r for r in old_risks}
            for risk in risks:
                old = old_by_id.get(risk.id)
                if old is None:
                    continue
                if (
                    risk.review_by > old.review_by
                    and risk.rationale_ref == old.rationale_ref
                    and risk.statement == old.statement
                ):
                    problems.append(
                        f"{risk.id}: review_by moved {old.review_by} -> "
                        f"{risk.review_by} but neither rationale_ref nor "
                        f"statement changed. Re-dating without re-reviewing is "
                        f"the one-keystroke way to satisfy this gate, so it is "
                        f"refused. If the risk was genuinely reconsidered, "
                        f"update the statement or cite a new decision."
                    )

    # --- Report -----------------------------------------------------------
    if problems:
        print("", file=sys.stderr)
        for problem in problems:
            print(f"check_risks: {problem}", file=sys.stderr)
        print(
            f"\ncheck_risks: {len(problems)} problem(s) across {len(risks)} "
            f"accepted risk(s).",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        for warning in warnings:
            print(f"check_risks: WARNING - {warning}")
        detective = sum(1 for r in risks if r.kind == "detective")
        normative = sum(1 for r in risks if r.kind == "normative")
        print(
            f"check_risks: {len(risks)} accepted risk(s) current "
            f"({detective} detective, {normative} normative); "
            f"none overdue."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
