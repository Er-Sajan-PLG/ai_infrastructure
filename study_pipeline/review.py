"""Review workflow for accepting/rejecting proposed taxonomy categories.

WHAT THIS MODULE DOES
----------------------
Given a discovery result (from `discover.py`), this module generates a
structured review document for each convergent pattern. The document includes:
- The evidence (which repos proposed it, convergence count)
- A draft ADR template for adopting the category
- A checklist for the reviewer to complete

The output is a directory of Markdown files, one per convergent pattern,
plus an index. A human reviews each file and decides: ADOPT, DEFER, or REJECT.

WHAT THIS MODULE DOES NOT DO
-----------------------------
- It does not write to TAXONOMY.md (ADR-0006 Decision 2)
- It does not create ADRs in docs/decisions/ (that requires a session)
- It does not judge value — it presents evidence and asks for a decision

The workflow is deliberately manual: a taxonomy change is a design decision,
not a mechanical one (charter §6, §24).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from study_pipeline.discover import Convergence, DiscoveryResult

#: Directory for review documents, relative to repo root.
REVIEW_DIR: Final = Path("docs/discovery/review")

#: Minimum convergence count to qualify for review.
MIN_CONVERGENCE: Final = 3


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """One category proposed for review."""

    convergence: Convergence
    #: Path to the review document (relative to repo root)
    doc_path: Path
    #: Draft ADR name
    adr_name: str


def _adr_name(proposed_id: str) -> str:
    """Generate a draft ADR name for a proposed category."""
    return f"proposed-{proposed_id}"


def _render_review_item(item: ReviewItem) -> str:
    """Render one review document for a convergent pattern."""
    c = item.convergence
    lines = [
        f"# Review: `{c.proposed_id}`",
        "",
        "**Proposed new taxonomy category**",
        "",
        "## Evidence",
        "",
        f"- **Convergence:** {c.count} of {c.total_repos} studied repositories "
        f"({c.percentage:.0f}%) proposed this category",
        f"- **From patterns:** {', '.join(f'`{p}`' for p in c.from_patterns)}",
        f"- **In taxonomy:** {'yes' if c.in_taxonomy else 'no'}",
        "",
        "## Repositories",
        "",
        "The following independent repositories proposed this category:",
        "",
    ]
    for repo in c.repos:
        lines.append(f"- `{repo}`")
    lines.extend(
        [
            "",
            "## Draft ADR",
            "",
            f"**ADR-{item.adr_name}**",
            "",
            "### Context",
            "",
            f"{c.count} of {c.total_repos} studied repositories independently "
            f"proposed `{c.proposed_id}` as a new taxonomy category. The "
            f"convergence across independent implementations is evidence "
            f"that this pattern exists in the ecosystem.",
            "",
            "### Decision",
            "",
            f"[ ] ADOPT — add `{c.proposed_id}` to the taxonomy tree",
            "[ ] DEFER — valuable but prerequisites/evidence insufficient",
            "[ ] REJECT — unjustified complexity or poor fit",
            "",
            "### Consequences",
            "",
            "_To be filled by the reviewer._",
            "",
            "## Review checklist",
            "",
            "- [ ] Read at least 2 of the proposing repositories' reports",
            "- [ ] Verify the pattern is AI-infrastructure-specific (not general software)",
            "- [ ] Check the category name is clear and unambiguous",
            "- [ ] Confirm no existing category covers this (check aliases)",
            "- [ ] Assess priority: is this needed now, or can it wait?",
            "",
            "## Decision",
            "",
            "_Reviewer: [ ] ADOPT  [ ] DEFER  [ ] REJECT_",
            "",
            "_Date: _______",
            "",
            "_Rationale: _",
            "",
        ]
    )
    return "\n".join(lines)


def generate_review_docs(result: DiscoveryResult, root: Path) -> tuple[ReviewItem, ...]:
    """Generate review documents for all convergent patterns.

    Creates one Markdown file per convergent pattern in the review directory,
    plus an index file. Returns the review items for further processing.
    """
    review_dir = root / REVIEW_DIR
    review_dir.mkdir(parents=True, exist_ok=True)

    convergent = [c for c in result.convergences if c.is_convergent]
    items: list[ReviewItem] = []

    for conv in convergent:
        adr_name = _adr_name(conv.proposed_id)
        doc_path = REVIEW_DIR / f"{conv.proposed_id}.md"
        item = ReviewItem(
            convergence=conv,
            doc_path=doc_path,
            adr_name=adr_name,
        )
        items.append(item)

        # Write the review document
        full_path = root / doc_path
        full_path.write_text(_render_review_item(item), encoding="utf-8")

    # Write the index
    index_lines = [
        "# Taxonomy Category Review",
        "",
        f"Generated from {result.total_repos} studied repositories.",
        "",
        f"{len(items)} convergent patterns (≥{MIN_CONVERGENCE} repos) are "
        "proposed for review.",
        "",
        "> **This is a review workflow, not a taxonomy change.**",
        "> Adopting a category requires an ADR and a session decision.",
        "",
        "## Convergent patterns",
        "",
        "| Proposed id | Count | % of repos | Document |",
        "|---|---|---|---|",
    ]
    for item in items:
        c = item.convergence
        index_lines.append(
            f"| `{c.proposed_id}` | {c.count} | {c.percentage:.0f}% "
            f"| [{c.proposed_id}]({item.doc_path.name}) |"
        )
    index_lines.extend(
        [
            "",
            "## How to review",
            "",
            "1. Open each document above",
            "2. Read the evidence and the proposing repositories' reports",
            "3. Complete the review checklist",
            "4. Record your decision (ADOPT, DEFER, or REJECT)",
            "5. If ADOPT: write an ADR in `docs/decisions/` and update "
            "`TAXONOMY.md` in the same session",
            "",
        ]
    )
    (review_dir / "README.md").write_text("\n".join(index_lines), encoding="utf-8")

    return tuple(items)


def render_review_summary(items: tuple[ReviewItem, ...]) -> str:
    """Render a summary of the review workflow for terminal output."""
    if not items:
        return "No convergent patterns to review."

    lines = [
        f"Generated {len(items)} review document(s) in {REVIEW_DIR}/",
        "",
        "Convergent patterns (≥3 repos):",
    ]
    for item in items:
        c = item.convergence
        lines.append(
            f"  - `{c.proposed_id}`: {c.count}/{c.total_repos} repos "
            f"({c.percentage:.0f}%)"
        )
    lines.extend(
        [
            "",
            f"Review index: {REVIEW_DIR}/README.md",
            "",
            "Next: review each document, then ADOPT/DEFER/REJECT with an ADR.",
        ]
    )
    return "\n".join(lines)
