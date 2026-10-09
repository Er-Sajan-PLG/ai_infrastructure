"""Tests for study_pipeline/deprecation.py — Phase 3 deprecation detection."""

from __future__ import annotations

from pathlib import Path

from study_pipeline.deprecation import (
    DeprecationCandidate,
    DeprecationResult,
    _parse_report_patterns,
    detect_deprecations,
    render_deprecation_report,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_MINIMAL_TAXONOMY = """\
# TAXONOMY.md

## 1. Taxonomy Tree

```text
agents/                Agents & Orchestration
tools/                 Tools
models/                Models
memory/                Context & Memory
retrieval/             Retrieval & Knowledge
observability/         Observability
```

## 4. Capability Registry

```yaml
capabilities:
  - id: tool-registry
    name: Tool Registry
    category: tools
    status: TESTED
```
"""

_REPORT_WITH_PATTERNS = """\
# test-repo

| | |
|---|---|
| Repository | https://github.com/test/repo |
| Studied | 2026-09-17 |

## Candidate patterns

### STRONG (2)

#### Agent Loop / Orchestration — `agent-loop`

**Category:** `agents`

#### Model Provider Abstraction — `model-provider`

**Category:** `models`

### MODERATE (1)

#### Caching Layer — `caching`

**Category:** `caching`
"""

_REPORT_NO_PATTERNS = """\
# empty-repo

| | |
|---|---|
| Repository | https://github.com/test/empty |
| Studied | 2026-09-17 |

## Candidate patterns

No conventional infrastructure patterns were detected.
"""

_REPORT_OLD_PATTERNS = """\
# old-repo

| | |
|---|---|
| Repository | https://github.com/test/old |
| Studied | 2025-01-15 |

## Candidate patterns

### STRONG (3)

#### Agent Loop / Orchestration — `agent-loop`

**Category:** `agents`

#### Model Provider Abstraction — `model-provider`

**Category:** `models`

#### Caching Layer — `caching`

**Category:** `caching`

#### Rate Limiting / Retry Policy — `rate-limiting`

**Category:** `reliability`
"""


# ---------------------------------------------------------------------------
# _parse_report_patterns
# ---------------------------------------------------------------------------


class TestParseReportPatterns:
    def test_extracts_patterns(self, tmp_path: Path) -> None:
        path = tmp_path / "test-repo.md"
        path.write_text(_REPORT_WITH_PATTERNS, encoding="utf-8")
        date, patterns = _parse_report_patterns(path)

        assert date == "2026-09-17"
        assert len(patterns) == 3
        assert patterns[0] == ("agent-loop", "STRONG", "agents")
        assert patterns[1] == ("model-provider", "STRONG", "models")
        assert patterns[2] == ("caching", "MODERATE", "caching")

    def test_no_patterns(self, tmp_path: Path) -> None:
        path = tmp_path / "empty-repo.md"
        path.write_text(_REPORT_NO_PATTERNS, encoding="utf-8")
        date, patterns = _parse_report_patterns(path)

        assert date == "2026-09-17"
        assert patterns == []

    def test_old_patterns(self, tmp_path: Path) -> None:
        path = tmp_path / "old-repo.md"
        path.write_text(_REPORT_OLD_PATTERNS, encoding="utf-8")
        date, patterns = _parse_report_patterns(path)

        assert date == "2025-01-15"
        assert len(patterns) == 4
        assert ("rate-limiting", "STRONG", "reliability") in patterns


# ---------------------------------------------------------------------------
# detect_deprecations
# ---------------------------------------------------------------------------


class TestDetectDeprecations:
    def test_empty_reports_dir(self, tmp_path: Path) -> None:
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        result = detect_deprecations(tmp_path)

        assert result.total_reports == 0
        assert result.candidates == ()

    def test_no_deprecation_candidates(self, tmp_path: Path) -> None:
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        # All reports have the same patterns — nothing disappears
        for slug in ("repo-a", "repo-b", "repo-c"):
            path = tmp_path / "study_pipeline" / "studied_repos" / f"{slug}.md"
            path.write_text(_REPORT_WITH_PATTERNS, encoding="utf-8")

        result = detect_deprecations(tmp_path)

        assert result.total_reports == 3
        # No candidates because all taxonomy patterns appear in all reports
        candidates = [c for c in result.candidates if c.is_candidate]
        assert len(candidates) == 0

    def test_deprecation_candidate_detected(self, tmp_path: Path) -> None:
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        # Only 1 report has "agent-loop" (which IS in the taxonomy)
        path = tmp_path / "study_pipeline" / "studied_repos" / "old-a.md"
        path.write_text(_REPORT_OLD_PATTERNS, encoding="utf-8")

        # 4 reports do NOT have "agent-loop"
        for slug in ("new-a", "new-b", "new-c", "new-d"):
            path = tmp_path / "study_pipeline" / "studied_repos" / f"{slug}.md"
            path.write_text(_REPORT_NO_PATTERNS, encoding="utf-8")

        result = detect_deprecations(tmp_path)

        assert result.total_reports == 5
        # agent-loop should be a deprecation candidate (in taxonomy, <3 appearances, >=2 absences)
        candidates = [c for c in result.candidates if c.is_candidate]
        assert len(candidates) >= 1
        agent_loop = next((c for c in candidates if c.pattern_id == "agent-loop"), None)
        assert agent_loop is not None
        assert agent_loop.total_appearances == 1
        assert agent_loop.rounds_absent == 4
        assert agent_loop.in_taxonomy is True

    def test_real_reports_dir(self) -> None:
        """Run against the real studied_repos/ directory."""
        result = detect_deprecations(_REPO_ROOT)

        assert result.total_reports > 0
        assert len(result.repos_parsed) == result.total_reports
        # The real reports should have some patterns
        assert len(result.occurrences) > 0

    def test_missing_reports_dir(self, tmp_path: Path) -> None:
        """detect_deprecations() returns empty result when reports dir doesn't exist."""
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        result = detect_deprecations(tmp_path)

        assert result.total_reports == 0
        assert result.candidates == ()
        assert result.occurrences == ()


# ---------------------------------------------------------------------------
# render_deprecation_report
# ---------------------------------------------------------------------------


class TestRenderDeprecationReport:
    def test_renders_candidates(self) -> None:
        result = DeprecationResult(
            total_reports=5,
            occurrences=(),
            candidates=(
                DeprecationCandidate(
                    pattern_id="rate-limiting",
                    name="Rate Limiting",
                    total_appearances=2,
                    last_seen="2025-01-15",
                    rounds_absent=3,
                    repos=("old-a", "old-b"),
                    in_taxonomy=True,
                ),
            ),
            all_patterns=("rate-limiting",),
            repos_parsed=("old-a", "old-b", "old-c", "new-a", "new-b"),
        )

        text = render_deprecation_report(result)

        assert "Deprecation candidates" in text
        assert "`rate-limiting`" in text
        assert "2" in text
        assert "2025-01-15" in text

    def test_renders_empty_result(self) -> None:
        result = DeprecationResult(
            total_reports=0,
            occurrences=(),
            candidates=(),
            all_patterns=(),
            repos_parsed=(),
        )

        text = render_deprecation_report(result)

        assert "0 studied repositories" in text
        assert "No patterns qualified" in text

    def test_renders_all_patterns(self) -> None:
        result = DeprecationResult(
            total_reports=3,
            occurrences=(),
            candidates=(
                DeprecationCandidate(
                    pattern_id="agent-loop",
                    name="Agent Loop",
                    total_appearances=3,
                    last_seen="2026-09-17",
                    rounds_absent=0,
                    repos=("repo-a", "repo-b", "repo-c"),
                    in_taxonomy=True,
                ),
            ),
            all_patterns=("agent-loop", "model-provider"),
            repos_parsed=("repo-a", "repo-b", "repo-c"),
        )

        text = render_deprecation_report(result)

        assert "All patterns observed" in text
        assert "`agent-loop`" in text
        assert "`model-provider`" in text
