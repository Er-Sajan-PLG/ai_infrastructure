"""Tests for study_pipeline/review.py — Phase 3 review workflow."""

from __future__ import annotations

from pathlib import Path

from study_pipeline.discover import Convergence, DiscoveryResult
from study_pipeline.review import (
    ReviewItem,
    generate_review_docs,
    render_review_summary,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_convergence(
    proposed_id: str = "caching",
    count: int = 5,
    total_repos: int = 25,
) -> Convergence:
    return Convergence(
        proposed_id=proposed_id,
        count=count,
        total_repos=total_repos,
        repos=tuple(f"repo-{i}" for i in range(count)),
        from_patterns=("caching",),
        in_taxonomy=False,
    )


def _make_result() -> DiscoveryResult:
    return DiscoveryResult(
        total_repos=25,
        proposals=(),
        convergences=(
            _make_convergence("caching", 5, 25),
            _make_convergence("config", 3, 25),
            _make_convergence("guardrails", 10, 25),
        ),
        mapped_patterns=(),
        confirmed_categories=(),
        repos_parsed=tuple(f"repo-{i}" for i in range(25)),
    )


class TestGenerateReviewDocs:
    def test_creates_review_documents(self, tmp_path: Path) -> None:
        result = _make_result()
        items = generate_review_docs(result, tmp_path)

        assert len(items) == 3
        # Check files were written
        assert (tmp_path / "docs/discovery/review/caching.md").is_file()
        assert (tmp_path / "docs/discovery/review/config.md").is_file()
        assert (tmp_path / "docs/discovery/review/guardrails.md").is_file()
        assert (tmp_path / "docs/discovery/review/README.md").is_file()

    def test_review_document_content(self, tmp_path: Path) -> None:
        result = _make_result()
        generate_review_docs(result, tmp_path)

        caching_doc = (tmp_path / "docs/discovery/review/caching.md").read_text()
        assert "Review: `caching`" in caching_doc
        assert "5 of 25" in caching_doc
        assert "ADOPT" in caching_doc
        assert "DEFER" in caching_doc
        assert "REJECT" in caching_doc

    def test_index_lists_all_items(self, tmp_path: Path) -> None:
        result = _make_result()
        generate_review_docs(result, tmp_path)

        index = (tmp_path / "docs/discovery/review/README.md").read_text()
        assert "caching" in index
        assert "config" in index
        assert "guardrails" in index

    def test_no_convergent_patterns(self, tmp_path: Path) -> None:
        result = DiscoveryResult(
            total_repos=25,
            proposals=(),
            convergences=(),
            mapped_patterns=(),
            confirmed_categories=(),
            repos_parsed=(),
        )
        items = generate_review_docs(result, tmp_path)

        assert len(items) == 0
        # Index should still be written
        assert (tmp_path / "docs/discovery/review/README.md").is_file()

    def test_real_repos(self) -> None:
        """Run against the real studied_repos/ directory."""
        from study_pipeline.discover import discover

        result = discover(_REPO_ROOT)
        items = generate_review_docs(result, _REPO_ROOT)

        # Should have at least the 4 known convergent patterns
        assert len(items) >= 4
        # All should have count >= 3
        for item in items:
            assert item.convergence.count >= 3


class TestRenderReviewSummary:
    def test_summary_lists_items(self) -> None:
        items = (
            ReviewItem(
                convergence=_make_convergence("caching", 5, 25),
                doc_path=Path("docs/discovery/review/caching.md"),
                adr_name="proposed-caching",
            ),
        )
        summary = render_review_summary(items)

        assert "caching" in summary
        assert "5/25" in summary

    def test_empty_summary(self) -> None:
        summary = render_review_summary(())

        assert "No convergent patterns" in summary
