"""Unit tests for scripts/check_risks.py.

This checker guards the accepted-risk register, which is where every
suppression in the repository is justified. Its most important behaviour is the
**anti-gaming control**: a `review_by` date may not advance while the entry's
rationale is unchanged.

That control is tested both ways, because it is the kind of check that is easy
to write in a way that never fires:

  * re-dating alone must FAIL;
  * re-dating alongside a genuine rationale change must PASS.

A register checker that only ever fails on expiry is theatre: the cheapest way
to clear an expired entry is to edit the date, and the check must make that
insufficient.
"""

from __future__ import annotations

import dataclasses
import shutil
import sys
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_risks import (  # noqa: E402
    ID_RE,
    MAX_REVIEW_WINDOW_DAYS,
    RATIONALE_ENUM,
    REF_RE,
    REQUIRED_FIELDS,
    Risk,
    _load_yaml_block,
    _parse,
    _parse_date,
    main,
)


def _entry(**overrides: Any) -> dict[str, Any]:
    """A minimal valid register entry, with overrides applied."""
    entry: dict[str, Any] = {
        "id": "AR-001",
        "title": "A risk",
        "kind": "detective",
        "scope": "somewhere",
        "rationale": "accepted_cost",
        "rationale_ref": "ADR-0001",
        "statement": "Why this is accepted.",
        "accepted_by": "maintainer",
        "accepted_on": "2026-01-01",
        "review_by": "2026-06-01",
        "tool": "bandit",
    }
    entry.update(overrides)
    return entry


def _register(*entries: dict[str, Any]) -> str:
    return yaml.safe_dump({"version": 1, "risks": list(entries)})


# ---------------------------------------------------------------------------
# Regexes and the enum, tested directly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["AR-001", "AR-999"])
def test_id_regex_accepts_well_formed_ids(value: str) -> None:
    assert ID_RE.match(value)


@pytest.mark.parametrize("value", ["AR-1", "ar-001", "001", "AR-0001", ""])
def test_id_regex_rejects_malformed_ids(value: str) -> None:
    assert not ID_RE.match(value)


@pytest.mark.parametrize("value", ["ADR-0001", "#123", "DO-NOT #7"])
def test_ref_regex_accepts_recorded_decisions(value: str) -> None:
    assert REF_RE.match(value)


@pytest.mark.parametrize("value", ["TODO", "ADR-1", "see the docs", ""])
def test_ref_regex_rejects_prose(value: str) -> None:
    # Prose like "TODO" is rejected because a date with no decision behind it
    # is not a review.
    assert not REF_RE.match(value)


def test_rationale_enum_is_the_vex_style_closed_set() -> None:
    assert "accepted_cost" in RATIONALE_ENUM
    assert "awaiting_upstream" in RATIONALE_ENUM
    assert "no_bandwidth" in RATIONALE_ENUM


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_accepts_a_well_formed_register() -> None:
    risks, problems = _parse(_register(_entry()))
    assert problems == []
    assert len(risks) == 1
    assert risks[0].id == "AR-001"


def test_parse_reports_a_non_mapping_entry() -> None:
    risks, problems = _parse(yaml.safe_dump({"risks": ["not a mapping"]}))
    assert risks == []
    assert any("not a mapping" in p for p in problems)


def test_parse_reports_a_missing_risks_list() -> None:
    risks, problems = _parse(yaml.safe_dump({"version": 1}))
    assert risks == []
    assert any("no 'risks' list" in p for p in problems)


def test_parse_reports_a_non_mapping_document() -> None:
    risks, problems = _parse("- just\n- a\n- list\n")
    assert risks == []
    assert any("did not parse to a mapping" in p for p in problems)


def test_parse_requires_every_field() -> None:
    incomplete = {"id": "AR-001", "title": "only two fields"}
    _risks, problems = _parse(_register(incomplete))
    missing = {
        f
        for f in REQUIRED_FIELDS
        if f"missing required field {f!r}" in " ".join(problems)
    }
    assert missing == set(REQUIRED_FIELDS) - {"id", "title"}


def test_parse_rejects_a_duplicate_id() -> None:
    _risks, problems = _parse(_register(_entry(), _entry(title="A second risk")))
    assert any("duplicate id" in p for p in problems)


def test_parse_rejects_an_unknown_kind() -> None:
    _risks, problems = _parse(_register(_entry(kind="guess")))
    assert any("kind 'guess'" in p for p in problems)


def test_parse_rejects_an_unknown_rationale() -> None:
    _risks, problems = _parse(_register(_entry(rationale="because")))
    assert any("rationale 'because'" in p for p in problems)


def test_parse_rejects_a_prose_rationale_ref() -> None:
    _risks, problems = _parse(_register(_entry(rationale_ref="TODO")))
    assert any("is not a recorded decision" in p for p in problems)


def test_parse_treats_a_whitespace_field_as_missing() -> None:
    _risks, problems = _parse(_register(_entry(title="   ")))
    assert any("missing required field 'title'" in p for p in problems)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def test_parse_date_accepts_iso_dates() -> None:
    assert _parse_date("2026-09-17") == date(2026, 9, 17)


@pytest.mark.parametrize("value", ["17-09-2026", "not a date", "", "2026-13-01"])
def test_parse_date_rejects_other_formats(value: str) -> None:
    assert _parse_date(value) is None


def test_max_review_window_is_just_over_a_year() -> None:
    # Slightly over a year so an annual review date is expressible but
    # "in five years" is not.
    assert 366 <= MAX_REVIEW_WINDOW_DAYS <= 400


# ---------------------------------------------------------------------------
# The real register in this repository
# ---------------------------------------------------------------------------


def test_the_repository_register_parses_and_is_current() -> None:
    # The end-to-end assertion: whatever is committed must pass the checker.
    assert main(["--quiet"]) == 0


def test_load_yaml_block_reads_the_authoritative_block() -> None:
    block = _load_yaml_block()
    assert block is not None
    # The register block, not the copy-paste template that follows it.
    assert "version:" in block
    assert "risks:" in block


def test_repository_register_entries_have_wellformed_refs() -> None:
    block = _load_yaml_block()
    assert block is not None
    risks, problems = _parse(block)
    assert problems == [], problems
    assert risks, "the register must not be empty"
    for risk in risks:
        assert REF_RE.match(risk.rationale_ref), risk.id
        assert risk.kind in {"detective", "normative"}, risk.id


# ---------------------------------------------------------------------------
# main() behaviour over a synthetic register
# ---------------------------------------------------------------------------


def _write_register(tmp_path: Path, body: str) -> Path:
    """Write a register into a temp dir that is a child of REPO_ROOT.

    The checker resolves the register path relative to REPO_ROOT, so a
    tmp_path outside the repository would raise ValueError rather than test
    anything. `tests/` is inside REPO_ROOT and is gitignored for stray files,
    so a uniquely-named temp directory there exercises the real code path.
    """
    directory = REPO_ROOT / "tests" / f".tmp-register-{uuid.uuid4().hex}"
    directory.mkdir()
    path = directory / "ACCEPTED_RISKS.md"
    path.write_text(
        f"# Accepted Risks\n\nProse above is not parsed.\n\n```yaml\n{body}```\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def register(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A redirectable register path inside REPO_ROOT, cleaned up afterwards."""
    directory = REPO_ROOT / "tests" / f".tmp-register-{uuid.uuid4().hex}"
    directory.mkdir()
    yield directory / "ACCEPTED_RISKS.md"
    shutil.rmtree(directory, ignore_errors=True)


def _install(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    body: str,
    previous: str | None = None,
) -> None:
    """Point the checker at a synthetic register and a synthetic predecessor."""
    import check_risks

    path.write_text(f"# Accepted Risks\n\n```yaml\n{body}```\n", encoding="utf-8")
    monkeypatch.setattr(check_risks, "REGISTER", path)
    monkeypatch.setattr(
        check_risks,
        "_previous_version",
        (
            (lambda: f"# Accepted Risks\n\n```yaml\n{previous}```\n")
            if previous is not None
            else (lambda: None)
        ),
    )


def test_main_fails_when_the_fenced_block_is_absent(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import check_risks

    register.write_text("# No fenced block here\n", encoding="utf-8")
    monkeypatch.setattr(check_risks, "REGISTER", register)
    monkeypatch.setattr(check_risks, "_previous_version", lambda: None)
    # Refusing to pass a check that read nothing.
    assert check_risks.main(["--quiet"]) == 1


def test_main_fails_when_fewer_than_the_floor_parses(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An empty parse is a failure, not a pass: "no risks recorded" and "the
    # parser broke" must not look alike.
    _install(monkeypatch, register, yaml.safe_dump({"version": 1, "risks": []}))
    import check_risks

    assert check_risks.main(["--quiet"]) == 1


def test_main_fails_on_an_overdue_entry(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, register, _register(_entry(review_by="2020-01-01")))
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 1


def test_main_fails_when_review_by_precedes_accepted_on(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(accepted_on="2026-06-01", review_by="2026-01-01")),
    )
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 1


def test_main_fails_when_the_review_window_exceeds_the_ceiling(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Over a year out: "parking a risk beyond a year is not a review schedule".
    _install(
        monkeypatch,
        register,
        _register(_entry(accepted_on="2026-01-01", review_by="2030-01-01")),
    )
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 1


def test_main_warns_within_the_horizon(
    register: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(accepted_on="2026-01-01", review_by="2026-10-01")),
    )
    import check_risks

    assert check_risks.main(["--today", "2026-09-17"]) == 0
    assert "review due in" in capsys.readouterr().out


def test_main_passes_a_current_register(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(accepted_on="2026-01-01", review_by="2026-11-01")),
    )
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 0


# ---------------------------------------------------------------------------
# The anti-gaming control — the reason this checker exists
# ---------------------------------------------------------------------------


def test_redating_alone_is_refused(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # THE key assertion: bumping the date is the one-keystroke fix, and it is
    # exactly what this check must make insufficient.
    _install(
        monkeypatch,
        register,
        _register(_entry(review_by="2027-01-01")),
        previous=_register(_entry(review_by="2026-10-01")),
    )
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 1


def test_redating_with_a_new_rationale_ref_is_allowed(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(review_by="2027-01-01", rationale_ref="ADR-0002")),
        previous=_register(_entry(review_by="2026-10-01", rationale_ref="ADR-0001")),
    )
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 0


def test_redating_with_a_revised_statement_is_allowed(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(review_by="2027-01-01", statement="Re-reviewed: still true.")),
        previous=_register(_entry(review_by="2026-10-01")),
    )
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 0


def test_shortening_a_review_date_is_allowed(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Moving a date EARLIER is not gaming: it commits to reviewing sooner.
    _install(
        monkeypatch,
        register,
        _register(_entry(review_by="2026-10-01")),
        previous=_register(_entry(review_by="2027-01-01")),
    )
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 0


def test_new_entries_are_not_subject_to_the_redating_check(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An id absent from the previous version is new work, not a re-dating.
    _install(
        monkeypatch,
        register,
        _register(_entry(id="AR-002", review_by="2027-01-01")),
        previous=_register(_entry(id="AR-001")),
    )
    import check_risks

    assert check_risks.main(["--quiet", "--today", "2026-09-17"]) == 0


def test_skip_note_is_printed_when_no_previous_version_exists(
    register: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(accepted_on="2026-01-01", review_by="2026-11-01")),
        previous=None,
    )
    import check_risks

    assert check_risks.main(["--today", "2026-09-17"]) == 0
    # Reported, never silently treated as "no change".
    assert "not available" in capsys.readouterr().out


def test_risk_dataclass_is_frozen() -> None:
    risk = Risk(
        id="AR-001",
        title="t",
        kind="normative",
        rationale_ref="ADR-0001",
        statement="s",
        accepted_on="2026-01-01",
        review_by="2026-06-01",
        raw={},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        risk.id = "AR-002"  # type: ignore[misc]
