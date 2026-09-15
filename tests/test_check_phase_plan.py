"""Tests for the phase-plan/charter order checker.

The checker exists because ``docs/phases/phase-1-seed.md`` documented the
lifecycle with ``DESIGNED`` and ``DECIDED`` swapped relative to charter §4. The
drift detector then rejected a *correct* ``DECIDED`` claim, using the plan as the
reader's authority. These tests pin both halves: that the checker passes on the
real repository, and that it actually fails on the historical bug.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_phase_plan import (  # noqa: E402
    _INDEX,
    LIFECYCLE,
    find_violations,
    iter_chains,
    main,
)


def _write(root: Path, name: str, content: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# The real repository
# --------------------------------------------------------------------------- #


def test_real_repository_has_no_out_of_order_transitions() -> None:
    """Every documented stage chain in this repo must agree with charter §4."""
    assert find_violations(REPO_ROOT) == []


def test_charter_order_is_the_enforced_order() -> None:
    """Pin the order itself: DESIGNED precedes DECIDED (charter §4)."""
    assert _INDEX["DESIGNED"] < _INDEX["DECIDED"]
    assert _INDEX["UNDERSTOOD"] < _INDEX["DESIGNED"]
    assert _INDEX["DECIDED"] < _INDEX["IMPLEMENTED"]
    assert _INDEX["TESTED"] < _INDEX["MATURE"]


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


def test_iter_chains_reads_a_backticked_arrow_chain() -> None:
    chains = iter_chains("| B | `RESEARCHED → UNDERSTOOD → DESIGNED` |")
    assert chains == [("RESEARCHED", "UNDERSTOOD", "DESIGNED")]


def test_iter_chains_accepts_ascii_arrow() -> None:
    assert iter_chains("`A -> B`") == [] or True  # placeholder, see next test
    chains = iter_chains("`DISCOVERED -> RESEARCHED`")
    assert chains == [("DISCOVERED", "RESEARCHED")]


def test_iter_chains_ignores_non_stage_words() -> None:
    """A backticked arrow of ordinary words is not a lifecycle claim."""
    assert iter_chains("`foo -> bar -> baz`") == []


def test_iter_chains_ignores_a_lone_stage() -> None:
    """One stage is not a transition, so there is nothing to order."""
    assert iter_chains("`TESTED`") == []


def test_iter_chains_finds_multiple_chains_in_one_document() -> None:
    text = "`DISCOVERED → RESEARCHED` and `DESIGNED → DECIDED`"
    assert len(iter_chains(text)) == 2


# --------------------------------------------------------------------------- #
# The historical bug
# --------------------------------------------------------------------------- #


def test_the_historical_reversal_is_detected(tmp_path: Path) -> None:
    """The exact bug: DECIDED listed as the predecessor of DESIGNED."""
    _write(
        tmp_path,
        "docs/phases/phase-1-seed.md",
        "| C | `DECIDED → DESIGNED` | spec |\n",
    )
    violations = find_violations(tmp_path)
    assert len(violations) == 1
    assert violations[0][1] == ("DECIDED", "DESIGNED")


def test_the_corrected_order_is_accepted(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "docs/phases/phase-1-seed.md",
        "| B | `RESEARCHED → UNDERSTOOD → DESIGNED` | spec |\n"
        "| C | `DESIGNED → DECIDED` | adr |\n",
    )
    assert find_violations(tmp_path) == []


def test_a_skipped_stage_is_fine(tmp_path: Path) -> None:
    """Chains may skip stages; only the *order* is checked."""
    _write(tmp_path, "docs/phases/phase-1-seed.md", "`DISCOVERED → DECIDED`\n")
    assert find_violations(tmp_path) == []


def test_extra_tracked_files_are_checked(tmp_path: Path) -> None:
    """TAXONOMY.md and AGENTS.md describe the lifecycle too."""
    _write(tmp_path, "TAXONOMY.md", "`TESTED → IMPLEMENTED`\n")
    violations = find_violations(tmp_path)
    assert len(violations) == 1
    assert violations[0][0] == Path("TAXONOMY.md")


def test_missing_targets_are_not_an_error(tmp_path: Path) -> None:
    """A repo with neither docs/phases/ nor the tracked files must not crash."""
    assert find_violations(tmp_path) == []


@pytest.mark.parametrize(
    ("content", "expected"),
    [("`DESIGNED → DECIDED`\n", 0), ("`DECIDED → DESIGNED`\n", 1)],
)
def test_main_exit_code(tmp_path: Path, content: str, expected: int) -> None:
    _write(tmp_path, "docs/phases/phase-1-seed.md", content)
    assert main(["--root", str(tmp_path), "--quiet"]) == expected


def test_lifecycle_matches_repo_status() -> None:
    """The checker's order and the drift detector's order must not diverge.

    They are separate literals on purpose — a lifecycle change should require
    editing both — but they must agree at all times.
    """
    from repo_status import LIFECYCLE as ENFORCED

    assert tuple(LIFECYCLE) == tuple(ENFORCED)
