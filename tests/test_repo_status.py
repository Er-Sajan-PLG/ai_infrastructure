"""Tests for the governance drift detector (scripts/repo_status.py).

The detector exists to enforce charter §4 — status must reflect artifacts that
actually exist. A detector that cannot fail is worse than none, because it
manufactures false confidence, so the failure paths are the primary subject
here.

Run:  .venv/bin/python -m pytest tests/ -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from repo_status import (  # noqa: E402
    LIFECYCLE,
    Capability,
    _parse_capabilities,
    check_adr_index,
    check_capability,
    check_dependencies,
    main,
    summarize,
)

REPO = REPO_ROOT


def _cap(**overrides: object) -> Capability:
    """Build a Capability with sensible defaults, overridable per test."""
    defaults: dict[str, object] = {
        "id": "demo",
        "name": "Demo",
        "category": "tools",
        "status": "DISCOVERED",
        "implementation": "",
        "tests": "",
        "benchmarks": "",
        "research_records": "",
        "decision": "pending",
        "depends_on": [],
    }
    defaults.update(overrides)
    return Capability(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_real_taxonomy_parses_all_capabilities() -> None:
    """The committed TAXONOMY.md parses into the expected capability set."""
    caps = _parse_capabilities((REPO / "TAXONOMY.md").read_text(encoding="utf-8"))
    ids = {c.id for c in caps}
    assert ids == {
        "tool-registry",
        "model-provider-abstraction",
        "react-agent-loop",
        "vector-memory-store",
        "basic-rag-pipeline",
        "mcp-client",
        "execution-trace-recorder",
    }


def test_parsed_capabilities_have_valid_statuses() -> None:
    """Every parsed status is a real lifecycle stage (charter §4)."""
    caps = _parse_capabilities((REPO / "TAXONOMY.md").read_text(encoding="utf-8"))
    for cap in caps:
        assert cap.status in LIFECYCLE, f"{cap.id} has status {cap.status!r}"


def test_parser_reads_inline_list() -> None:
    """Inline YAML lists (depends_on: [a, b]) are parsed into entries."""
    text = "```yaml\ncapabilities:\n  - id: x\n    depends_on: [a, b]\n```\n"
    caps = _parse_capabilities(text)
    assert caps[0].depends_on == ["a", "b"]


def test_parser_reads_block_list() -> None:
    """Block-style YAML lists are parsed into entries."""
    text = "```yaml\ncapabilities:\n  - id: x\n    depends_on:\n      - a\n      - b\n```\n"
    caps = _parse_capabilities(text)
    assert caps[0].depends_on == ["a", "b"]


# ---------------------------------------------------------------------------
# Drift detection: the core rule
# ---------------------------------------------------------------------------


def test_discovered_claim_is_clean() -> None:
    """A DISCOVERED capability with no artifacts is honest, not drift."""
    assert check_capability(_cap(status="DISCOVERED"), REPO) == []


# ---------------------------------------------------------------------------
# Research-record existence (regression)
#
# REAL HOLE: the RESEARCHED check only verified that `research_records` was
# non-empty. A taxonomy entry could cite a research record that did not exist
# on disk and still pass — the same class of bug as the empty-tests/ hole in
# validate_catalog.py (ADR-0004). Existence is not evidence.
# ---------------------------------------------------------------------------


def test_researched_with_missing_record_path_is_an_error() -> None:
    """Citing a research record that does not exist is drift."""
    drifts = check_capability(
        _cap(status="RESEARCHED", research_records="research/tools/nope.md"), REPO
    )
    assert drifts, "a cited but missing research record must be an error"
    assert any("do not exist" in d.message for d in drifts), drifts


def test_researched_with_real_record_path_is_clean() -> None:
    """A research record that exists satisfies the claim."""
    assert (
        check_capability(
            _cap(
                status="RESEARCHED",
                research_records="research/tools/tool-registry.md",
            ),
            REPO,
        )
        == []
    )


def test_researched_with_empty_records_is_still_an_error() -> None:
    """The original empty-field check must not regress."""
    drifts = check_capability(_cap(status="RESEARCHED"), REPO)
    assert any("is empty" in d.message for d in drifts), drifts


def test_quoted_inline_list_records_are_stripped() -> None:
    """YAML renders inline lists with quotes; paths must be stripped of them."""
    assert (
        check_capability(
            _cap(
                status="RESEARCHED",
                research_records='"research/tools/tool-registry.md"',
            ),
            REPO,
        )
        == []
    )


def test_multiple_records_report_only_the_missing_ones() -> None:
    """A real path alongside a fake one reports just the fake one."""
    drifts = check_capability(
        _cap(
            status="RESEARCHED",
            research_records="research/tools/tool-registry.md, research/tools/ghost.md",
        ),
        REPO,
    )
    assert drifts, "the missing record must be reported"
    assert "ghost.md" in drifts[0].message
    assert "tool-registry.md" not in drifts[0].message


@pytest.mark.parametrize(
    "status",
    ["DESIGNED", "DECIDED", "IMPLEMENTED", "TESTED", "BENCHMARKED", "MATURE"],
)
def test_claim_without_artifacts_is_always_an_error(status: str) -> None:
    """No stage past RESEARCHED can be claimed without its artifacts."""
    drifts = check_capability(_cap(status=status), REPO)
    errors = [d for d in drifts if d.severity == "error"]
    assert errors, f"claiming {status} with no artifacts produced no error"


def test_tested_without_tests_is_the_canonical_bug() -> None:
    """The charter §4 example: TESTED with no test artifact."""
    drifts = check_capability(_cap(status="TESTED", tests=""), REPO)
    messages = " ".join(d.message for d in drifts)
    assert "'tests' is empty" in messages


def test_tested_with_missing_test_path_is_an_error() -> None:
    """A test path pointing at nothing is drift, not evidence."""
    drifts = check_capability(
        _cap(status="TESTED", tests="catalog/tools/nope/tests"), REPO
    )
    messages = " ".join(d.message for d in drifts)
    assert "test path does not exist" in messages


def test_implemented_with_nonexistent_path_is_an_error() -> None:
    """An implementation path must exist on disk."""
    drifts = check_capability(
        _cap(status="IMPLEMENTED", implementation="catalog/tools/ghost"), REPO
    )
    messages = " ".join(d.message for d in drifts)
    assert "implementation path does not exist" in messages


def test_decided_requires_a_real_decision() -> None:
    """DECIDED while decision is still 'pending' violates charter §8."""
    drifts = check_capability(_cap(status="DECIDED", decision="pending"), REPO)
    messages = " ".join(d.message for d in drifts)
    assert "decision' is still unset/pending" in messages


def test_unknown_status_is_an_error() -> None:
    """A status outside the lifecycle enum is drift, not a typo to ignore."""
    drifts = check_capability(_cap(status="MOSTLY_DONE"), REPO)
    assert any("unrecognized lifecycle status" in d.message for d in drifts)


def test_pre_implementation_status_with_implementation_is_warning() -> None:
    """Recording an implementation path while still DISCOVERED is suspicious."""
    drifts = check_capability(
        _cap(status="DISCOVERED", implementation="catalog/x"), REPO
    )
    assert any(d.severity == "warning" for d in drifts)
    assert not any(d.severity == "error" for d in drifts)


# ---------------------------------------------------------------------------
# Dependency integrity
# ---------------------------------------------------------------------------


def test_unknown_dependency_is_an_error() -> None:
    """depends_on must reference real capability ids."""
    drifts = check_dependencies([_cap(id="a", depends_on=["ghost"])])
    assert any("unknown capability id" in d.message for d in drifts)


def test_known_dependency_is_clean() -> None:
    """A resolvable dependency produces no drift."""
    caps = [_cap(id="a"), _cap(id="b", depends_on=["a"])]
    assert check_dependencies(caps) == []


# ---------------------------------------------------------------------------
# CLI and aggregation
# ---------------------------------------------------------------------------


def test_cli_clean_on_real_repository() -> None:
    """The committed repository reports no drift."""
    assert main(["--root", str(REPO), "--quiet"]) == 0


def test_cli_nonzero_when_drift_injected(tmp_path: Path) -> None:
    """The CLI exits 1 when a capability over-claims."""
    (tmp_path / "TAXONOMY.md").write_text(
        "```yaml\ncapabilities:\n  - id: x\n    category: tools\n"
        "    status: TESTED\n    tests: ''\n```\n",
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "--quiet"]) == 1


def test_cli_json_output_is_valid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--json emits parseable machine-readable output."""
    import json

    (tmp_path / "TAXONOMY.md").write_text(
        "```yaml\ncapabilities:\n  - id: x\n    category: tools\n    status: DISCOVERED\n```\n",
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["capabilities"] == 1
    assert payload["by_status"]["DISCOVERED"] == 1


def test_summarize_counts_each_stage() -> None:
    """Stage counts reflect the parsed capabilities."""
    counts = summarize([_cap(id="a"), _cap(id="b", status="TESTED")])
    assert counts["DISCOVERED"] == 1
    assert counts["TESTED"] == 1
    assert counts["MATURE"] == 0


# --------------------------------------------------------------------------- #
# ADR index (charter §4 applied to the decision log)
# --------------------------------------------------------------------------- #


def _adr_repo(tmp_path: Path, *, listed: bool) -> Path:
    """Build a minimal repo containing one ADR, optionally listed in the index."""
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "0001-example.md").write_text("# ADR-0001\n", encoding="utf-8")
    body = "# Architecture Decision Records\n\n"
    if listed:
        body += "| [0001](0001-example.md) | Example | Accepted |\n"
    (decisions / "README.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_unlisted_adr_is_reported(tmp_path: Path) -> None:
    """An ADR absent from the index is invisible to a reader, so it is an error.

    Two ADRs were shipped in earlier sessions without being added to the index;
    nothing detected it until it was done by hand. This pins the check that now
    does.
    """
    drifts = check_adr_index(_adr_repo(tmp_path, listed=False))
    assert len(drifts) == 1
    assert drifts[0].severity == "error"
    assert "0001-example.md" in drifts[0].message


def test_listed_adr_is_clean(tmp_path: Path) -> None:
    assert check_adr_index(_adr_repo(tmp_path, listed=True)) == []


def test_missing_decisions_dir_is_not_an_error(tmp_path: Path) -> None:
    """A repo with no ADR directory must not crash the detector."""
    assert check_adr_index(tmp_path) == []


def test_real_adr_index_lists_every_adr() -> None:
    """The committed decisions directory must be fully indexed."""
    assert check_adr_index(REPO_ROOT) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
