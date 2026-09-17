#!/usr/bin/env python3
"""Verify that every catalog entry's tests are actually collectable.

Why this exists
---------------
Charter §31 requires catalog entries to be independent, and §18 requires each
to carry tests that run. But pytest reports success for a directory that
collects ZERO items: running `pytest tests catalog integrations` where a
subdirectory contributes nothing looks exactly like running it where it
contributes 100 tests. A capability could therefore ship a `tests/`
directory that pytest never collected while every gate stayed green.

That is not hypothetical. `docs/decisions/0004` records the first instance of
this class of hole in this repository (testpaths excluded a directory, so its
tests never ran), and this file's own design was informed by a documented
case where an anti-orphan guard "failed to see the orphans it was written to
find" because it globbed `test_*.py` (missing `*_test.py`) and returned early
on the mere presence of a `pytest` invocation elsewhere.

Design
------
The primitive is `pytest --collect-only -q`, run PER ENTRY DIRECTORY, because
that is the only way to attribute a zero count to a specific entry.

Three details are load-bearing:

* The counting is done by SUMMING PER-FILE COUNTS from pytest's own output
  (`path/to/test_x.py: 58`), not by counting `::`-decorated node ids. Under
  `-q`, pytest prints one summary line per file; node ids appear only in
  verbose/`--collect-only` long form. An earlier revision of this script
  matched the wrong format and reported six collectable entries as empty --
  a false positive that, left unfixed, would have caused the gate to be
  deleted rather than trusted.
* The list of files pytest considers is derived from
  `pytestconfig.getini("python_files")`, NOT hard-coded to `test_*.py`. A
  hard-coded glob is precisely the bug described above: it silently misses
  any other configured naming convention.
* pytest's EXIT CODE is captured separately from parsing its output, and a
  collection error is a failure rather than an empty result. "Collected
  nothing" and "failed to collect" are different facts and must not be
  conflated.

This is deliberately first-party: no off-the-shelf tool answers "is this
entry's tests/ collectable?". The import half of charter §31 IS handled by a
maintained tool (`import-linter` — see `make independence`), and this script
does not duplicate it.

Charter references: §4 (claims must match artifacts), §18 (testing),
§31 (component independence).
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess  # nosec B404 - invoking the pinned pytest, no user input
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRY_ROOTS = ("catalog", "integrations")

# Under `-q`, pytest prints one line per file that yielded items:
#
#     catalog/tools/tool_registry/tests/test_tool_registry.py: 58
#
# and a final summary line when the run completes:
#
#     58 tests collected in 0.01s
#
# We sum the per-file lines, which is what attributes a count to a directory
# even when it contains several test files. The summary line is used only as a
# cross-check.
_PER_FILE_RE = re.compile(r"^(?P<path>\S+\.py):\s+(?P<count>\d+)\s*$", re.MULTILINE)
_SUMMARY_RE = re.compile(r"^(?P<count>\d+)\s+tests?\s+collected", re.MULTILINE)
# Lower bound on how many entries discovery must find. See the comment at its
# use site: without a floor, a broken discovery loop expands to nothing and the
# check passes having verified nothing.
MIN_EXPECTED_ENTRIES = 5

_SELECTED_RE = re.compile(r"^(?P<count>\d+)/\d+\s+tests?\s+collected", re.MULTILINE)


def _entry_dirs() -> list[Path]:
    """Return every directory that declares itself a capability entry.

    An entry is a directory under catalog/<category>/<name>/ that contains a
    tests/ subdirectory, or an integration under integrations/<name>/.
    """
    found: list[Path] = []

    catalog = REPO_ROOT / "catalog"
    if catalog.is_dir():
        for category in sorted(p for p in catalog.iterdir() if p.is_dir()):
            if category.name.startswith((".", "_")):
                continue
            for entry in sorted(p for p in category.iterdir() if p.is_dir()):
                if entry.name.startswith((".", "_")):
                    continue
                if (entry / "tests").is_dir():
                    found.append(entry)

    integrations = REPO_ROOT / "integrations"
    if integrations.is_dir():
        for entry in sorted(p for p in integrations.iterdir() if p.is_dir()):
            if entry.name.startswith((".", "_")):
                continue
            if (entry / "tests").is_dir():
                found.append(entry)

    return found


def _configured_python_files() -> list[str]:
    """Read python_files from pytest's OWN config, rather than assuming.

    Hard-coding `test_*.py` is the documented cause of an anti-orphan guard
    that could not see the orphans it was written to find. Asking pytest what
    it would collect keeps this check true if the naming convention changes.
    """
    try:
        import pytest

        config = pytest.Config.fromdictargs({}, [])
        patterns = list(config.getini("python_files"))
        if patterns:
            return patterns
    except Exception:  # any failure means "use the default"
        # Logged rather than swallowed: a silent fallback here would mean the
        # check quietly stopped honouring a non-default `python_files`, which
        # is exactly the class of invisible drift this script exists to catch.
        logging.warning(
            "check_collectability: could not read pytest's python_files ini; "
            "falling back to ['test_*.py']. If your pytest config sets a "
            "different convention, this check is now looking for the wrong "
            "filenames.",
            exc_info=True,
        )
    return ["test_*.py"]


def _collect(entry: Path) -> tuple[int, int, str]:
    """Run `pytest --collect-only` for one entry's tests/ directory.

    Returns (exit_code, collected_count, combined_output). The exit code is
    returned rather than acted on, so the caller can distinguish a collection
    ERROR from a legitimately empty directory.
    """
    tests_dir = entry / "tests"
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
        # Nested invocation may inherit MAKELEVEL/MAKEFLAGS; --no-print-directory
        # is not relevant here (no make involved), but keeping pytest's own
        # output machine-readable is.
        str(tests_dir),
    ]
    proc = subprocess.run(  # noqa: S603 - fixed argv, absolute interpreter, no shell
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{proc.stdout}\n{proc.stderr}"

    # Primary: sum per-file counts ("path/to/test_x.py: 58"), which is what
    # attributes a count to a directory containing several test files.
    per_file = sum(int(m.group("count")) for m in _PER_FILE_RE.finditer(proc.stdout))
    if per_file:
        return proc.returncode, per_file, output

    # Secondary: a run with a single file may only emit the summary line.
    for pattern in (_SUMMARY_RE, _SELECTED_RE):
        match = pattern.search(proc.stdout)
        if match:
            return proc.returncode, int(match.group("count")), output

    # No count anywhere. Distinguish "nothing to collect" (exit 5) from a
    # collection ERROR by leaving the count at zero and letting the caller
    # branch on the exit code -- never silently treating one as the other.
    return proc.returncode, 0, output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify every catalog entry's tests are collectable."
    )
    parser.add_argument("--quiet", action="store_true", help="print only problems")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print each entry and its collected count",
    )
    args = parser.parse_args(argv)

    entries = _entry_dirs()
    patterns = _configured_python_files()

    # --- Anti-silent-skip floor -------------------------------------------
    # If the discovery logic above ever breaks (a renamed directory, a changed
    # layout), it would find nothing and this check would pass having verified
    # NOTHING. That is the exact failure mode documented in the wild: "if
    # .PHONY is renamed or the parse otherwise breaks, this loop would expand
    # nothing at all and would pass green having checked NOTHING."
    #
    # NOTE ON HISTORY: this floor was originally written BELOW an
    # `if not entries: return 0` short-circuit, so a TOTAL discovery collapse
    # exited 0 while a partial one exited 1 -- backwards, and it meant the
    # guard did not cover the case it was written for. A unit test that
    # simulated collapse caught it. The early return is gone; the floor is now
    # the only exit for too few entries, including zero.
    if len(entries) < MIN_EXPECTED_ENTRIES:
        print(
            f"check_collectability: FAILED - discovered only {len(entries)} "
            f"entry(ies) with tests/, expected at least {MIN_EXPECTED_ENTRIES}.",
            file=sys.stderr,
        )
        print(
            "  This usually means entry DISCOVERY broke, not that entries were "
            "removed. Refusing to pass a check that verified nothing.",
            file=sys.stderr,
        )
        return 1

    problems: list[str] = []
    checked = 0

    for entry in entries:
        rel = entry.relative_to(REPO_ROOT)
        code, count, output = _collect(entry)
        checked += 1

        if args.verbose and not args.quiet:
            print(f"  {rel}: {count} test(s) collectable")

        # Exit 5 is pytest's "no tests collected". For an entry that DECLARES
        # a tests/ directory this is a failure: the directory exists but
        # contributes nothing, which is the hole this check closes.
        if code == 5 or count == 0:
            problems.append(
                f"{rel}: declares tests/ but collects ZERO tests "
                f"(pytest exit {code}). An entry's tests directory that "
                f"collects nothing means its tests never ran."
            )
            if args.verbose:
                print(output, file=sys.stderr)
            continue

        # Any other non-zero exit is a collection ERROR (import error, syntax
        # error, bad fixture) and must not be mistaken for an empty result.
        if code != 0:
            problems.append(
                f"{rel}: pytest --collect-only exited {code} "
                f"(collection error, not an empty directory)."
            )
            if args.verbose:
                print(output, file=sys.stderr)

    if problems:
        print("", file=sys.stderr)
        for problem in problems:
            print(f"check_collectability: {problem}", file=sys.stderr)
        print(
            f"\ncheck_collectability: {len(problems)} problem(s) across "
            f"{checked} entry(ies) checked.",
            file=sys.stderr,
        )
        print(
            f"  python_files patterns in effect: {', '.join(patterns)}",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        total_note = f" (python_files: {', '.join(patterns)})"
        print(
            f"check_collectability: {checked} entry(ies) checked, "
            f"all collectable{total_note}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
