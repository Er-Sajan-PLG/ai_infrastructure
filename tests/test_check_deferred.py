"""Unit tests for scripts/check_deferred.py.

The deferred-work register records work that is deliberately NOT done yet,
because a specific present-day fact makes it premature. The checker's job is to
stop that register decaying into a wish list, so the tests are organised around
exactly that risk:

  * an entry with a STUB trigger must be refused — "trigger: soon" is not a
    trigger, and a register full of them is a list of good intentions;
  * `review_by` may not advance while `current_fact` and `trigger` are
    unchanged — the same anti-gaming rule as the accepted-risk register;
  * an empty parse must FAIL rather than pass, so a broken parser cannot
    masquerade as "everything was implemented".

The module deliberately does NOT try to decide whether a trigger has fired;
those are prose conditions and several are not repository-observable. Tests
assert the advisory behaviour is advisory, so a future change does not
accidentally turn an observation into a failure.
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

from check_deferred import (  # noqa: E402
    CATEGORY_ENUM,
    EFFORT_ENUM,
    ID_RE,
    MAX_REVIEW_WINDOW_DAYS,
    MIN_FIELD_LENGTH,
    REQUIRED_FIELDS,
    DeferredItem,
    _has_runtime_dependency,
    _load_yaml_block,
    _parse,
    _parse_date,
    main,
)


def _entry(**overrides: Any) -> dict[str, Any]:
    """A minimal valid entry, with overrides applied."""
    entry: dict[str, Any] = {
        "id": "DW-001",
        "title": "Some future work",
        "category": "security",
        "current_fact": "Zero released artifacts on the repository today.",
        "why_now_wrong": "There is nothing to protect yet, so this is theatre.",
        "trigger": "The first git tag, or the first published artifact.",
        "reversal": "Add a release workflow with provenance attestation.",
        "effort": "medium",
        "source": "docs/audits/some-report.md",
        "review_by": "2027-01-01",
        "adr": "ADR-0020",
    }
    entry.update(overrides)
    return entry


def _register(*entries: dict[str, Any]) -> str:
    return yaml.safe_dump({"version": 1, "deferred": list(entries)})


# ---------------------------------------------------------------------------
# Schema vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["DW-001", "DW-999"])
def test_id_regex_accepts_well_formed_ids(value: str) -> None:
    assert ID_RE.match(value)


@pytest.mark.parametrize("value", ["DW-1", "dw-001", "001", ""])
def test_id_regex_rejects_malformed_ids(value: str) -> None:
    assert not ID_RE.match(value)


def test_category_and_effort_are_closed_enums() -> None:
    assert {"scale", "security", "governance"} <= CATEGORY_ENUM
    assert {"small", "medium", "large"} == EFFORT_ENUM


def test_min_field_length_is_meaningful() -> None:
    # Long enough to exclude a stub like "soon" or "later".
    assert MIN_FIELD_LENGTH >= 20


def test_max_review_window_is_just_over_a_year() -> None:
    assert 366 <= MAX_REVIEW_WINDOW_DAYS <= 400


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_accepts_a_well_formed_entry() -> None:
    items, problems = _parse(_register(_entry()))
    assert problems == []
    assert len(items) == 1
    assert items[0].id == "DW-001"


def test_parse_reports_a_missing_deferred_list() -> None:
    items, problems = _parse(yaml.safe_dump({"version": 1}))
    assert items == []
    assert any("no 'deferred' list" in p for p in problems)


def test_parse_reports_a_non_mapping_document() -> None:
    items, problems = _parse("- a\n- list\n")
    assert items == []
    assert any("did not parse to a mapping" in p for p in problems)


def test_parse_reports_a_non_mapping_entry() -> None:
    items, problems = _parse(yaml.safe_dump({"deferred": ["nope"]}))
    assert items == []
    assert any("not a mapping" in p for p in problems)


def test_parse_requires_every_field() -> None:
    _items, problems = _parse(_register({"id": "DW-001", "title": "two fields"}))
    joined = " ".join(problems)
    for field in REQUIRED_FIELDS:
        if field in {"id", "title"}:
            continue
        assert f"missing required field {field!r}" in joined


def test_parse_rejects_a_duplicate_id() -> None:
    _items, problems = _parse(_register(_entry(), _entry(title="A different one")))
    assert any("duplicate id" in p for p in problems)


def test_parse_rejects_an_unknown_category() -> None:
    _items, problems = _parse(_register(_entry(category="vibes")))
    assert any("category 'vibes'" in p for p in problems)


def test_parse_rejects_an_unknown_effort() -> None:
    _items, problems = _parse(_register(_entry(effort="enormous")))
    assert any("effort 'enormous'" in p for p in problems)


def test_parse_rejects_an_adr_that_is_not_a_record() -> None:
    _items, problems = _parse(_register(_entry(adr="some decision")))
    assert any("is not of the form ADR-NNNN" in p for p in problems)


# ---------------------------------------------------------------------------
# Specificity — the reason the register is not a wish list
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["current_fact", "trigger", "reversal"])
def test_parse_refuses_a_stub_in_a_load_bearing_field(field: str) -> None:
    # "trigger: soon" is not a trigger. Without this floor the register decays
    # into a list of things someone once thought would be nice.
    _items, problems = _parse(_register(_entry(**{field: "soon"})))
    assert any(f"{field} is only" in p for p in problems)


def test_parse_accepts_a_field_exactly_at_the_floor() -> None:
    _items, problems = _parse(_register(_entry(trigger="x" * MIN_FIELD_LENGTH)))
    assert problems == []


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------


def test_parse_date_accepts_iso_dates() -> None:
    assert _parse_date("2027-01-01") == date(2027, 1, 1)


@pytest.mark.parametrize("value", ["01-01-2027", "soon", "", "2027-13-01"])
def test_parse_date_rejects_other_formats(value: str) -> None:
    assert _parse_date(value) is None


# ---------------------------------------------------------------------------
# The real register in this repository
# ---------------------------------------------------------------------------


def test_the_repository_register_passes() -> None:
    assert main(["--quiet"]) == 0


def test_load_yaml_block_reads_the_register_not_the_template() -> None:
    block = _load_yaml_block()
    assert block is not None
    assert "deferred:" in block


def test_repository_entries_are_all_wellformed() -> None:
    block = _load_yaml_block()
    assert block is not None
    items, problems = _parse(block)
    assert problems == [], problems
    assert items, "the register must not be empty"
    for item in items:
        assert ID_RE.match(item.id), item.id
        assert item.category in CATEGORY_ENUM, item.id
        assert len(item.trigger) >= MIN_FIELD_LENGTH, item.id
        assert len(item.reversal) >= MIN_FIELD_LENGTH, item.id


# ---------------------------------------------------------------------------
# Observable trigger probes
#
# These read the real repository. They assert only that the probes are
# well-behaved booleans, because the repository is expected to have no tag and
# no runtime dependency (that is WHY those entries exist). Asserting the
# current value would make this test an obstacle to the very change the
# register anticipates.
# ---------------------------------------------------------------------------


def test_git_tag_probe_returns_a_bool() -> None:
    from check_deferred import _has_git_tag

    assert isinstance(_has_git_tag(), bool)


def test_runtime_dependency_probe_returns_a_bool() -> None:
    assert isinstance(_has_runtime_dependency(), bool)


# ---------------------------------------------------------------------------
# main() over a synthetic register
# ---------------------------------------------------------------------------


@pytest.fixture
def register() -> Iterator[Path]:
    """A redirectable register path inside REPO_ROOT, cleaned up after."""
    directory = REPO_ROOT / "tests" / f".tmp-deferred-{uuid.uuid4().hex}"
    directory.mkdir()
    yield directory / "DEFERRED.md"
    shutil.rmtree(directory, ignore_errors=True)


def _install(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    body: str,
    previous: str | None = None,
    fill_to_floor: bool = True,
) -> None:
    """Point the checker at a synthetic register and predecessor.

    The register has a minimum-entries floor (an anti-silent-skip guard), so
    synthetic registers are padded with valid entries to reach it; otherwise
    every test would fail on the floor rather than on its subject.
    """
    import check_deferred

    if fill_to_floor:
        parsed = yaml.safe_load(body) or {}
        entries = list(parsed.get("deferred", []))
        existing = {e.get("id") for e in entries if isinstance(e, dict)}
        index = len(entries)
        while len(entries) < check_deferred.MIN_EXPECTED_ENTRIES:
            index += 1
            filler = _entry(id=f"DW-{index:03d}", title="Filler entry")
            if filler["id"] not in existing:
                entries.append(filler)
        body = yaml.safe_dump({"version": 1, "deferred": entries})

    path.write_text(f"# Deferred\n\n```yaml\n{body}```\n", encoding="utf-8")
    monkeypatch.setattr(check_deferred, "REGISTER", path)
    if previous is None:
        monkeypatch.setattr(check_deferred, "_previous_version", lambda: None)
    else:
        monkeypatch.setattr(
            check_deferred,
            "_previous_version",
            lambda: f"# Deferred\n\n```yaml\n{previous}```\n",
        )


def test_main_fails_when_the_fenced_block_is_absent(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import check_deferred

    register.write_text("# No fenced block\n", encoding="utf-8")
    monkeypatch.setattr(check_deferred, "REGISTER", register)
    monkeypatch.setattr(check_deferred, "_previous_version", lambda: None)
    assert check_deferred.main(["--quiet"]) == 1


def test_main_fails_below_the_entry_floor(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An empty parse is a failure, not a pass.
    _install(
        monkeypatch,
        register,
        yaml.safe_dump({"version": 1, "deferred": []}),
        fill_to_floor=False,
    )
    import check_deferred

    assert check_deferred.main(["--quiet"]) == 1


def test_main_passes_a_current_register(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, register, _register(_entry(review_by="2027-01-01")))
    import check_deferred

    assert check_deferred.main(["--quiet", "--today", "2026-09-17"]) == 0


def test_main_fails_on_an_overdue_entry(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, register, _register(_entry(review_by="2020-01-01")))
    import check_deferred

    assert check_deferred.main(["--quiet", "--today", "2026-09-17"]) == 1


def test_main_warns_within_the_horizon(
    register: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, register, _register(_entry(review_by="2026-10-01")))
    import check_deferred

    assert check_deferred.main(["--today", "2026-09-17"]) == 0
    assert "review due in" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The anti-gaming control
# ---------------------------------------------------------------------------


def test_redating_alone_is_refused(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(review_by="2027-06-01")),
        previous=_register(_entry(review_by="2027-01-01")),
    )
    import check_deferred

    assert check_deferred.main(["--quiet", "--today", "2026-09-17"]) == 1


def test_redating_with_a_new_current_fact_is_allowed(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        register,
        _register(
            _entry(
                review_by="2027-06-01",
                current_fact="Still zero tags, but now also zero consumers of any kind.",
            )
        ),
        previous=_register(_entry(review_by="2027-01-01")),
    )
    import check_deferred

    assert check_deferred.main(["--quiet", "--today", "2026-09-17"]) == 0


def test_redating_with_a_new_trigger_is_allowed(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        register,
        _register(
            _entry(
                review_by="2027-06-01",
                trigger="The first git tag, OR the repository gaining a remote.",
            )
        ),
        previous=_register(_entry(review_by="2027-01-01")),
    )
    import check_deferred

    assert check_deferred.main(["--quiet", "--today", "2026-09-17"]) == 0


def test_shortening_a_review_date_is_allowed(
    register: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(review_by="2027-01-01")),
        previous=_register(_entry(review_by="2027-06-01")),
    )
    import check_deferred

    assert check_deferred.main(["--quiet", "--today", "2026-09-17"]) == 0


def test_skip_note_is_printed_when_no_previous_version_exists(
    register: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(
        monkeypatch,
        register,
        _register(_entry(review_by="2027-01-01")),
        previous=None,
    )
    import check_deferred

    assert check_deferred.main(["--today", "2026-09-17"]) == 0
    assert "not available" in capsys.readouterr().out


def test_deferred_item_is_frozen() -> None:
    item = DeferredItem(
        id="DW-001",
        title="t",
        category="security",
        trigger="a sufficiently long trigger string",
        reversal="a sufficiently long reversal string",
        current_fact="a sufficiently long fact string",
        review_by="2027-01-01",
        raw={},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.id = "DW-002"  # type: ignore[misc]
