"""Deprecation detection — flag obsolete patterns for review (charter §23).

WHAT THIS MODULE DOES
----------------------
Reads all study reports in `studied_repos/`, extracts candidate patterns from
each report, and identifies taxonomy categories that are candidates for
deprecation review.

A pattern is flagged when:
- It is tracked in the taxonomy (i.e., it is a known category)
- It appeared in fewer than MIN_ROUNDS_ESTABLISHED studies
  (the ecosystem has largely moved on from it)
- It has been absent from at least MIN_ROUNDS_DISAPPEARED studies

This is a conservative signal: a taxonomy category that most studied repos
do NOT have is a candidate for deprecation review.

The output is a structured proposal document for human review. This module
NEVER writes to `TAXONOMY.md` — that is a session decision requiring an ADR.

WHAT "OBSOLETE" MEANS HERE
--------------------------
A pattern is a deprecation candidate when the evidence suggests the
ecosystem has moved on. This is NOT a judgement that the pattern was wrong
— it may have been correct for its time and since replaced by something
better. The deprecation review determines whether to mark it DEPRECATED
in the taxonomy or leave it as-is.

WHAT THIS MODULE DOES NOT DO
-----------------------------
- It does not auto-deprecate. Proposals are printed in a document; a human
  decides whether to deprecate, with an ADR.
- It does not judge quality. A pattern disappearing from studies may mean
  it is obsolete, or it may mean the studied repos changed. The review
  document states both possibilities.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from study_pipeline.classify import load_taxonomy

#: Directory containing study reports, relative to repo root.
REPORTS_DIR: Final = Path("study_pipeline/studied_repos")

#: Pattern candidate extraction — same format as discover.py
_CANDIDATE_SECTION: Final = "## Candidate patterns"
_CONFIDENCE_RE: Final = re.compile(
    r"^####\s+(?P<name>.+?)\s+—\s+`(?P<pattern_id>[a-z0-9-]+)`$"
)
_CATEGORY_RE: Final = re.compile(r"^\*\*Category:\*\*\s*`(?P<category>[a-z0-9-]+)`$")

#: Date extraction from report header
_DATE_RE: Final = re.compile(r"\|\s*Studied\s*\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*\|")

#: Slug extraction
_SLUG_RE: Final = re.compile(r"^#\s+(?P<slug>.+)$", re.MULTILINE)

#: How many study rounds a pattern must appear in to be "established"
MIN_ROUNDS_ESTABLISHED: Final = 3

#: How many study rounds without the pattern to be "disappeared"
MIN_ROUNDS_DISAPPEARED: Final = 2


@dataclass(frozen=True, slots=True)
class PatternOccurrence:
    """One occurrence of a pattern in a study report."""

    pattern_id: str
    repo: str
    #: Date the study was conducted
    studied_on: str
    #: Confidence level
    confidence: str
    #: Taxonomy category this pattern maps to
    category: str


@dataclass(frozen=True, slots=True)
class DeprecationCandidate:
    """A pattern flagged as a potential deprecation candidate."""

    pattern_id: str
    name: str
    #: Total number of study reports where this pattern appeared
    total_appearances: int
    #: Most recent study date where this pattern appeared
    last_seen: str
    #: Number of study reports where this pattern did NOT appear
    rounds_absent: int
    #: All repos where this pattern appeared
    repos: tuple[str, ...]
    #: Whether this pattern is in the current taxonomy
    in_taxonomy: bool

    @property
    def is_candidate(self) -> bool:
        """Whether this pattern qualifies as a deprecation candidate.

        A pattern is a candidate when:
        - It is in the taxonomy (still tracked)
        - It appeared in fewer than MIN_ROUNDS_ESTABLISHED studies
          (the ecosystem has largely moved on from it)
        - It has been absent from at least MIN_ROUNDS_DISAPPEARED studies

        This is a conservative signal: a taxonomy category that most studied
        repos do NOT have is a candidate for deprecation review.
        """
        return (
            self.in_taxonomy
            and self.total_appearances < MIN_ROUNDS_ESTABLISHED
            and self.rounds_absent >= MIN_ROUNDS_DISAPPEARED
        )


@dataclass(frozen=True, slots=True)
class DeprecationResult:
    """The full result of deprecation detection."""

    total_reports: int
    #: All pattern occurrences found across all reports
    occurrences: tuple[PatternOccurrence, ...]
    #: Patterns that are deprecation candidates
    candidates: tuple[DeprecationCandidate, ...]
    #: All unique pattern ids found
    all_patterns: tuple[str, ...]
    #: Repo slugs that were parsed
    repos_parsed: tuple[str, ...]


def _parse_report_patterns(path: Path) -> tuple[str, list[tuple[str, str, str]]]:
    """Parse a study report for pattern candidates and its study date.

    Returns (date, [(pattern_id, confidence, category), ...]).
    """
    text = path.read_text(encoding="utf-8")

    # Extract study date
    date_match = _DATE_RE.search(text)
    studied_on = date_match.group("date") if date_match else "unknown"

    # Extract pattern candidates
    patterns: list[tuple[str, str, str]] = []
    in_candidates = False
    current_confidence = ""
    current_category = ""
    pending_pattern: str | None = None

    for line in text.splitlines():
        stripped = line.strip()

        if stripped == "## Candidate patterns":
            in_candidates = True
            continue
        if stripped.startswith("## ") and stripped != "## Candidate patterns":
            in_candidates = False
            continue

        if in_candidates:
            if stripped.startswith("### "):
                # Confidence header: "### STRONG (5)"
                current_confidence = stripped.split("(")[0].strip("# ").strip()
                continue
            match = _CONFIDENCE_RE.match(stripped)
            if match:
                pending_pattern = match.group("pattern_id")
                continue
            cat_match = _CATEGORY_RE.match(stripped)
            if cat_match and pending_pattern is not None:
                current_category = cat_match.group("category")
                patterns.append((pending_pattern, current_confidence, current_category))
                pending_pattern = None

    return studied_on, patterns


def detect_deprecations(root: Path) -> DeprecationResult:
    """Run deprecation detection over all study reports.

    Reads every `.md` file in `studied_repos/`, extracts pattern candidates,
    and identifies patterns that may be obsolete.
    """
    reports_dir = root / REPORTS_DIR
    if not reports_dir.is_dir():
        return DeprecationResult(
            total_reports=0,
            occurrences=(),
            candidates=(),
            all_patterns=(),
            repos_parsed=(),
        )

    taxonomy = load_taxonomy(root)

    all_occurrences: list[PatternOccurrence] = []
    repos_parsed: list[str] = []

    for report_path in sorted(reports_dir.glob("*.md")):
        if report_path.name == "README.md":
            continue
        studied_on, patterns = _parse_report_patterns(report_path)
        repos_parsed.append(report_path.stem)

        for pattern_id, confidence, category in patterns:
            all_occurrences.append(
                PatternOccurrence(
                    pattern_id=pattern_id,
                    repo=report_path.stem,
                    studied_on=studied_on,
                    confidence=confidence,
                    category=category,
                )
            )

    # Group by pattern_id
    by_pattern: dict[str, list[PatternOccurrence]] = defaultdict(list)
    for occ in all_occurrences:
        by_pattern[occ.pattern_id].append(occ)

    # Identify deprecation candidates
    candidates: list[DeprecationCandidate] = []
    for pattern_id, occs in sorted(by_pattern.items()):
        # Sort occurrences by date
        sorted_occs = sorted(occs, key=lambda o: o.studied_on)
        last_seen = sorted_occs[-1].studied_on

        # Count how many repos studied AFTER last_seen did NOT have this pattern
        repos_after = [
            repo for repo in repos_parsed if repo not in {o.repo for o in sorted_occs}
        ]
        rounds_absent = len(repos_after)

        # Check if the pattern's category is in the taxonomy
        categories = {o.category for o in occs if o.category}
        in_taxonomy = any(taxonomy.has_category(cat) for cat in categories)

        candidate = DeprecationCandidate(
            pattern_id=pattern_id,
            name=pattern_id.replace("-", " ").title(),
            total_appearances=len(occs),
            last_seen=last_seen,
            rounds_absent=rounds_absent,
            repos=tuple(sorted({o.repo for o in occs})),
            in_taxonomy=in_taxonomy,
        )
        candidates.append(candidate)

    # Sort: candidates first, then by total_appearances descending
    candidates.sort(key=lambda c: (-c.total_appearances, c.pattern_id))

    all_patterns = tuple(sorted(by_pattern.keys()))

    return DeprecationResult(
        total_reports=len(repos_parsed),
        occurrences=tuple(all_occurrences),
        candidates=tuple(candidates),
        all_patterns=all_patterns,
        repos_parsed=tuple(sorted(repos_parsed)),
    )


def render_deprecation_report(result: DeprecationResult) -> str:
    """Render the deprecation report as a Markdown document for human review."""
    lines = [
        "# Deprecation Review — Obsolete Pattern Candidates",
        "",
        f"Generated from {result.total_reports} studied repositories.",
        "",
        "> **This document is a proposal, not a taxonomy change.**",
        "> Deprecating a pattern requires an ADR and a session decision",
        "> (charter §23, ADR-0021 Decision 2).",
        "",
    ]

    # Deprecation candidates
    candidates = [c for c in result.candidates if c.is_candidate]
    if candidates:
        lines.extend(
            [
                "## Deprecation candidates",
                "",
                "These patterns appeared in multiple studies but have not been",
                "seen recently. They may be obsolete — the ecosystem may have",
                "moved on to better approaches.",
                "",
                "| Pattern | Name | Appearances | Last seen | Absent since | Repos |",
                "|---|---|---|---|---|---|",
            ]
        )
        for c in candidates:
            lines.append(
                f"| `{c.pattern_id}` | {c.name} | {c.total_appearances} "
                f"| {c.last_seen} | {c.rounds_absent} repos "
                f"| {', '.join(f'`{r}`' for r in c.repos[:3])}"
                f"{', …' if len(c.repos) > 3 else ''} |"
            )
        lines.append("")
    else:
        lines.extend(
            [
                "## Deprecation candidates",
                "",
                "No patterns qualified as deprecation candidates.",
                "A pattern must appear in ≥3 studies and be absent for ≥2 rounds",
                "to be flagged.",
                "",
            ]
        )

    # All patterns summary
    if result.all_patterns:
        lines.extend(
            [
                "## All patterns observed",
                "",
                f"{len(result.all_patterns)} unique patterns were found across "
                f"all studies:",
                "",
            ]
        )
        for pattern_id in result.all_patterns:
            # Find the candidate info if it exists
            cand = next(
                (c for c in result.candidates if c.pattern_id == pattern_id),
                None,
            )
            if cand and cand.is_candidate:
                lines.append(
                    f"- `{pattern_id}` — **DEPRECATION CANDIDATE** "
                    f"({cand.total_appearances} appearances, last seen {cand.last_seen})"
                )
            elif cand:
                lines.append(
                    f"- `{pattern_id}` — {cand.total_appearances} appearance(s), "
                    f"still active"
                )
            else:
                lines.append(f"- `{pattern_id}`")
        lines.append("")

    # Methodology
    lines.extend(
        [
            "## How this works",
            "",
            "1. Each study report is parsed for candidate patterns",
            "2. Patterns are grouped by pattern_id across all reports",
            "3. A pattern is a deprecation candidate when:",
            "   - It appeared in ≥3 studies (established)",
            "   - It has been absent for ≥2 rounds (disappeared)",
            "   - It is NOT in the current taxonomy (not still tracked)",
            "4. The output is a proposal for human review — deprecation",
            "   requires an ADR (charter §23)",
            "",
            "## Caveats",
            "",
            "- A pattern disappearing from studies may mean it is obsolete,",
            "  OR it may mean the studied repos changed focus",
            "- The study pipeline detects structural patterns by name —",
            "  a pattern that changed its name will appear to have disappeared",
            "- This report is a starting point for review, not a verdict",
            "",
        ]
    )

    return "\n".join(lines)
