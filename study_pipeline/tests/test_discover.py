"""Tests for study_pipeline/discover.py — Phase 3 convergence detection."""

from __future__ import annotations

from pathlib import Path

from study_pipeline.discover import (
    Convergence,
    DiscoveryResult,
    _parse_report,
    discover,
    render_discovery,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _write_report(root: Path, slug: str, body: str) -> Path:
    """Write a study report under studied_repos/ and return its path."""
    reports_dir = root / "study_pipeline" / "studied_repos"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{slug}.md"
    path.write_text(body, encoding="utf-8")
    return path


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

_REPORT_WITH_PROPOSALS = """\
# test-repo

## Taxonomy mapping

### Already in the taxonomy

| Pattern | Taxonomy category |
|---|---|
| `agent-loop` | `agents` |
| `model-provider` | `models` |

### Proposed new categories

> These are **proposals for review**, not taxonomy changes.

| Proposed id | From pattern | Why it is new |
|---|---|---|
| `caching` | `caching` | category `performance` is not in the taxonomy tree |
| `config` | `config` | category `tooling` is not in the taxonomy tree |
| `guardrails` | `guardrails` | category `guardrails` is not in the taxonomy tree |
"""

_REPORT_NO_PROPOSALS = """\
# another-repo

## Taxonomy mapping

### Already in the taxonomy

| Pattern | Taxonomy category |
|---|---|
| `agent-loop` | `agents` |

### Proposed new categories

No new categories proposed.
"""

_REPORT_SINGLE_PROPOSAL = """\
# third-repo

## Taxonomy mapping

### Proposed new categories

| Proposed id | From pattern | Why it is new |
|---|---|---|
| `caching` | `caching` | category `performance` is not in the taxonomy tree |
"""


# ---------------------------------------------------------------------------
# _parse_report
# ---------------------------------------------------------------------------


class TestParseReport:
    def test_extracts_proposals(self, tmp_path: Path) -> None:
        path = _write_report(tmp_path, "test-repo", _REPORT_WITH_PROPOSALS)
        proposals, _mapped = _parse_report(path)

        assert len(proposals) == 3
        assert proposals[0].proposed_id == "caching"
        assert proposals[0].from_pattern == "caching"
        assert proposals[0].category == "performance"
        assert proposals[0].repo == "test-repo"

    def test_extracts_mapped_patterns(self, tmp_path: Path) -> None:
        path = _write_report(tmp_path, "test-repo", _REPORT_WITH_PROPOSALS)
        _, mapped = _parse_report(path)

        assert len(mapped) == 2
        assert mapped[0].pattern_id == "agent-loop"
        assert mapped[0].category == "agents"

    def test_no_proposals(self, tmp_path: Path) -> None:
        path = _write_report(tmp_path, "another-repo", _REPORT_NO_PROPOSALS)
        proposals, _ = _parse_report(path)

        assert proposals == ()

    def test_single_proposal(self, tmp_path: Path) -> None:
        path = _write_report(tmp_path, "third-repo", _REPORT_SINGLE_PROPOSAL)
        proposals, _ = _parse_report(path)

        assert len(proposals) == 1
        assert proposals[0].proposed_id == "caching"


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestDiscover:
    def test_empty_reports_dir(self, tmp_path: Path) -> None:
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        result = discover(tmp_path)

        assert result.total_repos == 0
        assert result.convergences == ()

    def test_convergence_detection(self, tmp_path: Path) -> None:
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        # 3 repos propose "caching" → convergent
        for slug in ("repo-a", "repo-b", "repo-c"):
            _write_report(tmp_path, slug, _REPORT_SINGLE_PROPOSAL)

        result = discover(tmp_path)

        assert result.total_repos == 3
        assert len(result.convergences) == 1
        conv = result.convergences[0]
        assert conv.proposed_id == "caching"
        assert conv.count == 3
        assert conv.is_convergent

    def test_non_convergent_proposals(self, tmp_path: Path) -> None:
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        # Only 1 repo proposes "caching" → not convergent
        _write_report(tmp_path, "solo-repo", _REPORT_SINGLE_PROPOSAL)

        result = discover(tmp_path)

        assert result.total_repos == 1
        assert len(result.convergences) == 1
        conv = result.convergences[0]
        assert conv.count == 1
        assert not conv.is_convergent

    def test_mixed_convergence(self, tmp_path: Path) -> None:
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        # 3 repos propose "caching"
        for slug in ("repo-a", "repo-b", "repo-c"):
            _write_report(tmp_path, slug, _REPORT_SINGLE_PROPOSAL)

        # 2 repos propose "config"
        _write_report(tmp_path, "repo-d", _REPORT_WITH_PROPOSALS)
        _write_report(
            tmp_path,
            "repo-e",
            _REPORT_WITH_PROPOSALS.replace("test-repo", "repo-e"),
        )

        result = discover(tmp_path)

        assert result.total_repos == 5
        # caching: 5 (3 single + 2 from multi-proposal reports)
        # config: 2, guardrails: 2
        assert len(result.convergences) == 3
        caching = next(c for c in result.convergences if c.proposed_id == "caching")
        config = next(c for c in result.convergences if c.proposed_id == "config")
        guardrails = next(
            c for c in result.convergences if c.proposed_id == "guardrails"
        )
        assert caching.count == 5
        assert caching.is_convergent
        assert config.count == 2
        assert not config.is_convergent
        assert guardrails.count == 2
        assert not guardrails.is_convergent

    def test_confirmed_categories(self, tmp_path: Path) -> None:
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        _write_report(tmp_path, "repo-a", _REPORT_WITH_PROPOSALS)

        result = discover(tmp_path)

        assert "agents" in result.confirmed_categories
        assert "models" in result.confirmed_categories

    def test_real_reports_dir(self) -> None:
        """Run discover against the real studied_repos/ directory."""
        result = discover(_REPO_ROOT)

        assert result.total_repos > 0
        assert len(result.repos_parsed) == result.total_repos
        # The real reports should have some proposals
        assert len(result.proposals) > 0

    def test_filters_existing_categories(self, tmp_path: Path) -> None:
        """Categories already in the taxonomy should not appear as proposals."""
        (tmp_path / "study_pipeline" / "studied_repos").mkdir(parents=True)
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        # 3 repos propose "caching" — but caching is NOT in the minimal taxonomy
        for slug in ("repo-a", "repo-b", "repo-c"):
            _write_report(tmp_path, slug, _REPORT_SINGLE_PROPOSAL)

        result = discover(tmp_path)

        # caching should appear as a proposal since it's not in the taxonomy
        assert len(result.convergences) == 1
        assert result.convergences[0].proposed_id == "caching"
        assert not result.convergences[0].in_taxonomy

    def test_missing_reports_dir(self, tmp_path: Path) -> None:
        """discover() returns empty result when reports dir doesn't exist."""
        (tmp_path / "TAXONOMY.md").write_text(_MINIMAL_TAXONOMY, encoding="utf-8")

        result = discover(tmp_path)

        assert result.total_repos == 0
        assert result.convergences == ()
        assert result.proposals == ()

    def test_proposal_evidence_property(self, tmp_path: Path) -> None:
        """Proposal.evidence returns a one-line summary string."""
        path = _write_report(tmp_path, "test-repo", _REPORT_SINGLE_PROPOSAL)
        proposals, _ = _parse_report(path)

        assert len(proposals) == 1
        evidence = proposals[0].evidence
        assert "test-repo" in evidence
        assert "caching" in evidence


# ---------------------------------------------------------------------------
# render_discovery
# ---------------------------------------------------------------------------


class TestRenderDiscovery:
    def test_renders_convergent_section(self) -> None:
        result = DiscoveryResult(
            total_repos=5,
            proposals=(),
            convergences=(
                Convergence(
                    proposed_id="caching",
                    count=3,
                    total_repos=5,
                    repos=("repo-a", "repo-b", "repo-c"),
                    from_patterns=("caching",),
                    in_taxonomy=False,
                ),
            ),
            mapped_patterns=(),
            confirmed_categories=("agents",),
            repos_parsed=("repo-a", "repo-b", "repo-c", "repo-d", "repo-e"),
        )

        text = render_discovery(result)

        assert "Convergent patterns" in text
        assert "`caching`" in text
        assert "3" in text
        assert "60%" in text

    def test_renders_non_convergent_section(self) -> None:
        result = DiscoveryResult(
            total_repos=5,
            proposals=(),
            convergences=(
                Convergence(
                    proposed_id="config",
                    count=1,
                    total_repos=5,
                    repos=("repo-a",),
                    from_patterns=("config",),
                    in_taxonomy=False,
                ),
            ),
            mapped_patterns=(),
            confirmed_categories=(),
            repos_parsed=("repo-a", "repo-b", "repo-c", "repo-d", "repo-e"),
        )

        text = render_discovery(result)

        assert "Non-convergent proposals" in text
        assert "`config`" in text

    def test_renders_confirmed_categories(self) -> None:
        result = DiscoveryResult(
            total_repos=3,
            proposals=(),
            convergences=(),
            mapped_patterns=(),
            confirmed_categories=("agents", "models"),
            repos_parsed=("repo-a", "repo-b", "repo-c"),
        )

        text = render_discovery(result)

        assert "Confirmed categories" in text
        assert "`agents`" in text
        assert "`models`" in text

    def test_renders_empty_result(self) -> None:
        result = DiscoveryResult(
            total_repos=0,
            proposals=(),
            convergences=(),
            mapped_patterns=(),
            confirmed_categories=(),
            repos_parsed=(),
        )

        text = render_discovery(result)

        assert "0 studied repositories" in text
