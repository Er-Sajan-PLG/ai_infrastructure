"""Unit tests for study_pipeline.report — rendering the study report.

The report is the deliverable, so these tests assert on the properties that
make it *honest* rather than on its exact wording:

  * `code_reused` is always false and the reason given is the structural one;
  * the method's limits are always stated, including on a thin result;
  * a pattern-free study says so as a RESULT, not as an error;
  * no section overclaims what structure can establish.

Exact-string assertions are limited to things that must not change silently.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from study_pipeline.classify import Taxonomy, TaxonomyCategory, classify_all
from study_pipeline.inventory import Inventory, Manifest, build_inventory
from study_pipeline.licence import Licence, LicenceConfidence
from study_pipeline.patterns import Candidate, Confidence, extract_candidates
from study_pipeline.report import (
    CODE_REUSED,
    CONFIDENCE_MEANING,
    REPORTS_DIRNAME,
    StudyReport,
    _human_bytes,
    _today,
    build_report,
    render_report,
    report_path,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _write(root: Path, relative: str, content: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _inventory(**overrides: object) -> Inventory:
    defaults: dict[str, object] = {
        "total_files": 10,
        "total_bytes": 1000,
        "extension_counts": {".py": 10},
        "top_level_entries": ("src", "README.md"),
        "directories": ("src",),
        "packages": ("src",),
        "test_dirs": ("tests",),
        "test_file_count": 3,
        "markers": {"licence": ("LICENSE",)},
        "manifests": (),
        "truncated": False,
        "notes": (),
    }
    defaults.update(overrides)
    return Inventory(**defaults)  # type: ignore[arg-type]


def _candidate(
    pattern_id: str = "retrieval",
    category: str = "retrieval",
    confidence: Confidence = Confidence.STRONG,
    evidence: tuple[str, ...] = ("src/retrieval/",),
) -> Candidate:
    return Candidate(
        pattern_id=pattern_id,
        name="Retrieval / vector search",
        category=category,
        confidence=confidence,
        evidence_paths=evidence,
        evidence_kind="directory evidence",
        limitations="Presence says nothing about the algorithm.",
    )


TAXONOMY = Taxonomy(
    categories=(
        TaxonomyCategory("retrieval", "Retrieval"),
        TaxonomyCategory("tools", "Tools"),
    ),
    capability_ids=("basic-rag-pipeline",),
    capability_categories=("retrieval",),
)


def _report(
    inventory: Inventory | None = None,
    candidates: tuple[Candidate, ...] = (),
    taxonomy: Taxonomy = TAXONOMY,
    **overrides: object,
) -> StudyReport:
    inv = inventory or _inventory()
    kwargs: dict[str, object] = {
        "slug": "target__example",
        "url": "https://github.com/example/target",
        "commit": "a" * 40,
        "size_bytes": 2048,
        "inventory": inv,
        "candidates": candidates,
        "classifications": classify_all(candidates, taxonomy),
        "taxonomy": taxonomy,
        "licence": Licence(
            spdx_id="MIT",
            confidence=LicenceConfidence.DECLARED,
            evidence=("pyproject.toml: license = 'MIT'",),
        ),
        "studied_on": "2026-01-01",
    }
    kwargs.update(overrides)
    return build_report(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The honesty guarantees
# ---------------------------------------------------------------------------


def test_code_reused_is_always_false() -> None:
    # Emitted from a constant so no caller can produce a report claiming reuse.
    assert CODE_REUSED is False
    assert "| `code_reused` | `false` |" in render_report(_report())


def test_report_states_reuse_is_structural_not_a_promise() -> None:
    text = render_report(_report())
    assert "no code path that writes into" in text


def test_report_states_that_nothing_was_executed() -> None:
    text = render_report(_report())
    assert "never imported, never installed" in text


def test_report_always_states_the_methods_limits() -> None:
    # Even for a thin result: a reader must know what the method cannot see.
    text = render_report(_report())
    for expected in (
        "declared, not resolved",
        "Test count is files, not tests",
        "matches names and manifests",
        "is a judgement of quality",
    ):
        assert expected in text, expected


def test_report_does_not_claim_to_understand_the_code() -> None:
    text = render_report(_report(candidates=(_candidate(),)))
    assert "It does not execute the studied" in text
    assert "does not read every source file" in text


def test_findings_section_refuses_to_recommend() -> None:
    text = render_report(_report(candidates=(_candidate(),)))
    assert "None is a recommendation" in text


# ---------------------------------------------------------------------------
# The empty result — a legitimate outcome, not a failure
# ---------------------------------------------------------------------------


def test_empty_result_is_reported_as_a_result() -> None:
    text = render_report(_report(candidates=()))
    assert "No conventional infrastructure patterns were detected" in text
    assert "This is a real result, not a failure" in text


def test_empty_result_explains_why_it_can_happen() -> None:
    # Without this, a report on a non-AI project reads as a broken tool.
    text = render_report(_report(candidates=()))
    assert "AI-infrastructure conventions" in text


def test_empty_result_still_renders_every_other_section() -> None:
    text = render_report(_report(candidates=()))
    for section in (
        "## Provenance",
        "## What this report cannot tell you",
        "## Structure",
    ):
        assert section in text, section


# ---------------------------------------------------------------------------
# Candidates and confidence
# ---------------------------------------------------------------------------


def test_each_candidate_renders_its_evidence() -> None:
    candidate = _candidate(evidence=("src/a/retrieval/", "src/b/retrieval/"))
    text = render_report(_report(candidates=(candidate,)))
    assert "`src/a/retrieval/`" in text
    assert "`src/b/retrieval/`" in text


def test_each_candidate_renders_its_limitation() -> None:
    text = render_report(_report(candidates=(_candidate(),)))
    assert "Presence says nothing about the algorithm." in text


def test_confidence_groups_are_labelled_and_ordered() -> None:
    candidates = (
        _candidate("weak-one", "retrieval", Confidence.WEAK),
        _candidate("strong-one", "retrieval", Confidence.STRONG),
    )
    text = render_report(_report(candidates=candidates))
    assert text.index("### STRONG (1)") < text.index("### WEAK (1)")


def test_every_confidence_label_has_a_stated_meaning() -> None:
    # An unexplained "weak" label invites a reader to treat it as a minor
    # version of "strong" rather than as a different kind of claim.
    for confidence in Confidence:
        assert confidence in CONFIDENCE_MEANING
        assert len(CONFIDENCE_MEANING[confidence]) > 40


def test_confidence_meaning_is_rendered() -> None:
    text = render_report(_report(candidates=(_candidate(),)))
    assert CONFIDENCE_MEANING[Confidence.STRONG] in text


def test_candidate_with_no_evidence_is_flagged_inline() -> None:
    # Should be unreachable, but rendering must not silently produce an empty
    # bullet list that looks like a rendering bug.
    candidate = _candidate(evidence=())
    text = render_report(_report(candidates=(candidate,)))
    assert "should not be reported" in text


# ---------------------------------------------------------------------------
# Taxonomy mapping and proposals
# ---------------------------------------------------------------------------


def test_mapped_patterns_render_as_a_table() -> None:
    text = render_report(_report(candidates=(_candidate(),)))
    assert "### Already in the taxonomy" in text
    assert "| `retrieval` | `retrieval` |" in text


def test_new_categories_render_as_proposals() -> None:
    text = render_report(_report(candidates=(_candidate("guardrails", "guardrails"),)))
    assert "### Proposed new categories" in text
    assert "`guardrails`" in text


def test_proposals_state_that_the_pipeline_does_not_edit_the_taxonomy() -> None:
    # The whole point of ADR-0021 Decision 2: proposing is not changing.
    text = render_report(_report(candidates=(_candidate("guardrails", "guardrails"),)))
    assert "proposals for review" in text and "not taxonomy changes" in text
    assert "does not edit `TAXONOMY.md`" in text


def test_no_proposals_says_so_explicitly() -> None:
    text = render_report(_report(candidates=(_candidate(),)))
    assert "No new categories proposed." in text


# ---------------------------------------------------------------------------
# Open questions
# ---------------------------------------------------------------------------


def test_weak_candidates_generate_a_question() -> None:
    candidate = _candidate("memory", "memory", Confidence.WEAK, ("memory/",))
    text = render_report(_report(candidates=(candidate,)))
    assert "implemented machinery or a stub?" in text


def test_no_test_files_generates_a_question() -> None:
    text = render_report(_report(inventory=_inventory(test_file_count=0, test_dirs=())))
    assert "No test files were detected" in text


def test_unparseable_manifest_generates_a_question() -> None:
    inventory = _inventory(
        manifests=(Manifest("bad.toml", "pyproject", (), "parse error"),)
    )
    text = render_report(_report(inventory=inventory))
    assert "could not be parsed" in text


def test_a_clean_study_still_has_a_question() -> None:
    # A section that is empty on a good run is a section that gets skipped on
    # a bad one.
    text = render_report(_report(candidates=(_candidate(),)))
    assert "Which of the STRONG candidates is load-bearing" in text


# ---------------------------------------------------------------------------
# Incomplete studies
# ---------------------------------------------------------------------------


def test_incomplete_reason_is_prominent() -> None:
    text = render_report(_report(incomplete_reason="Clone exceeded the size cap."))
    assert "This study is incomplete" in text
    assert "Clone exceeded the size cap." in text


def test_incomplete_is_absent_when_the_study_completed() -> None:
    assert "This study is incomplete" not in render_report(_report())


def test_inventory_notes_are_surfaced() -> None:
    text = render_report(
        _report(inventory=_inventory(notes=("Walk truncated at 200000 files.",)))
    )
    assert "Walk truncated at 200000 files." in text


# ---------------------------------------------------------------------------
# Structure and dependencies
# ---------------------------------------------------------------------------


def test_structure_lists_top_level_entries() -> None:
    text = render_report(
        _report(inventory=_inventory(top_level_entries=("src", "docs")))
    )
    assert "- `src`" in text
    assert "- `docs`" in text


def test_long_top_level_list_is_truncated_with_a_count() -> None:
    entries = tuple(f"dir{i}" for i in range(60))
    text = render_report(_report(inventory=_inventory(top_level_entries=entries)))
    assert "and 20 more" in text


def test_empty_top_level_renders_without_crashing() -> None:
    text = render_report(_report(inventory=_inventory(top_level_entries=())))
    assert "### Top level" in text


def test_markers_are_grouped() -> None:
    inventory = _inventory(markers={"licence": ("LICENSE",), "ci": (".github",)})
    text = render_report(_report(inventory=inventory))
    assert "**licence**: `LICENSE`" in text
    assert "**ci**: `.github`" in text


def test_dependencies_render_per_manifest() -> None:
    inventory = _inventory(
        manifests=(Manifest("pyproject.toml", "pyproject", ("requests>=2",)),)
    )
    text = render_report(_report(inventory=inventory))
    assert "### `pyproject.toml`" in text
    assert "`requests>=2`" in text


def test_manifest_parse_error_renders_inline() -> None:
    inventory = _inventory(manifests=(Manifest("bad.toml", "pyproject", (), "boom"),))
    text = render_report(_report(inventory=inventory))
    assert "Could not parse: boom" in text


def test_manifest_with_no_requirements_says_so() -> None:
    inventory = _inventory(manifests=(Manifest("empty.toml", "pyproject", ()),))
    text = render_report(_report(inventory=inventory))
    assert "No requirements declared." in text


def test_no_manifests_explains_the_possibility() -> None:
    text = render_report(_report(inventory=_inventory(manifests=())))
    assert "No root manifest was recognised" in text


# ---------------------------------------------------------------------------
# Assembly, naming, formatting
# ---------------------------------------------------------------------------


def test_report_filename_is_the_project_name() -> None:
    assert _report().filename == "example.md"


def test_report_path_uses_the_studied_repos_directory() -> None:
    path = report_path(REPO_ROOT, _report())
    assert path.parent == REPO_ROOT / REPORTS_DIRNAME
    assert path.name == "example.md"


def test_studied_on_defaults_to_utc_today() -> None:
    # Explicitly UTC: two runs on machines in different zones must not date the
    # same commit differently.
    assert _today() == dt.datetime.now(dt.UTC).date().isoformat()


def test_explicit_studied_on_is_used() -> None:
    assert _report(studied_on="2020-05-05").studied_on == "2020-05-05"


def test_studied_on_is_rendered() -> None:
    assert "| Studied | 2026-01-01 |" in render_report(_report())


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KiB"),
        (2048, "2.0 KiB"),
        (1024 * 1024, "1.0 MiB"),
        (3 * 1024**3, "3.0 GiB"),
    ],
)
def test_human_bytes(count: int, expected: str) -> None:
    assert _human_bytes(count) == expected


def test_rendering_is_deterministic() -> None:
    report = _report(candidates=(_candidate(),))
    assert render_report(report) == render_report(report)


def test_rendering_ends_with_exactly_one_newline() -> None:
    text = render_report(_report())
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_rendering_has_no_triple_blank_lines() -> None:
    # Keeps the output stable and diffable across runs.
    assert "\n\n\n\n" not in render_report(_report())


def test_rendering_a_real_repository_succeeds() -> None:
    # End-to-end on a known tree: this repository. Catches a renderer that only
    # works against synthetic inventories.
    inventory = build_inventory(REPO_ROOT)
    candidates = extract_candidates(inventory)
    from study_pipeline.classify import load_taxonomy

    taxonomy = load_taxonomy(REPO_ROOT)
    report = _report(
        inventory=inventory,
        candidates=candidates,
        taxonomy=taxonomy,
        slug="local__ai_infrastructure",
    )
    text = render_report(report)
    assert "## Candidate patterns" in text
    assert "`tool-registry`" in text


def test_generated_report_has_no_unfilled_placeholders() -> None:
    text = render_report(_report(candidates=(_candidate(),)))
    for marker in ("TODO", "FIXME", "None", "{}"):
        assert marker not in text.split("## Structure")[0], marker


# ---------------------------------------------------------------------------
# Licence in the report header
# ---------------------------------------------------------------------------


def test_licence_is_rendered_in_the_header() -> None:
    """The plan requires the licence at the studied version in each record.

    It sits next to the commit, because a licence is only true of the commit it
    was read at -- the same reason the commit is recorded at all (charter §11).
    """
    text = render_report(_report())
    assert "| Licence | MIT (declared) |" in text


def test_licence_appears_next_to_the_commit() -> None:
    text = render_report(_report())
    commit_at = text.index("| Commit |")
    licence_at = text.index("| Licence |")
    studied_at = text.index("| Studied |")
    assert commit_at < licence_at < studied_at


def test_undetermined_licence_is_reported_not_omitted() -> None:
    """A report with no licence must SAY so, not silently drop the row.

    A missing row reads as "not checked"; an explicit one reads as "checked and
    not determinable", which is the truthful description and tells the reader a
    human must look at the LICENSE file before any reuse.
    """
    report = _report(
        licence=Licence(
            spdx_id="",
            confidence=LicenceConfidence.UNIDENTIFIED,
            evidence=("LICENSE exists",),
            licence_file="LICENSE",
        )
    )
    text = render_report(report)
    assert "| Licence |" in text
    assert "not determined" in text
    assert "LICENSE" in text


def test_conflicting_licence_is_surfaced_in_the_report() -> None:
    report = _report(
        licence=Licence(
            spdx_id="",
            confidence=LicenceConfidence.DECLARED,
            evidence=("both",),
            conflicts=("MIT", "Apache-2.0"),
        )
    )
    text = render_report(report)
    assert "CONFLICT" in text
    assert "needs review" in text


def test_reports_stay_deterministic_with_a_licence() -> None:
    assert render_report(_report()) == render_report(_report())
