"""Map candidate patterns onto the taxonomy, and propose new categories.

WHAT CLASSIFICATION DECIDES, AND WHAT IT REFUSES TO
---------------------------------------------------
A candidate pattern is either *already covered* by a taxonomy category, or it
is *not*, in which case it becomes a proposal for a new `DISCOVERED` entry.

This module reads [`TAXONOMY.md`](../../TAXONOMY.md) rather than hardcoding a
category list. That matters: the first version of this code carried a guessed
`KNOWN_CATEGORIES` constant, and it was wrong in both directions — it omitted
`mcp`, which the taxonomy has, and it invented `performance` and `reliability`,
which the taxonomy does not. A classifier whose notion of the taxonomy can
drift from the taxonomy is worse than no classifier, because its output looks
authoritative.

WHAT IT DOES NOT DO
-------------------
It does not add anything to `TAXONOMY.md`. Proposals are *printed in a report*
and a human or agent session decides whether to adopt them, with an ADR
(ADR-0021 Decision 2). An automated classifier writing taxonomy entries would
be exactly the "recreation into catalog/" failure this decision exists to
prevent, one step earlier in the pipeline.

It also does not judge *value*. "This category is not in the taxonomy" is a
fact about the taxonomy; "this pattern is worth adopting" is a design opinion
that belongs to a session, and the report labels it as such (charter §6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from study_pipeline.patterns import Candidate, slugify

#: The taxonomy's fenced YAML block opens with this.
_YAML_FENCE: Final = "```yaml"

#: A taxonomy-tree line looks like `category-name/    Description`, optionally
#: with a parenthetical and an alias group like `mcp|protocols/`. The tree is
#: the authoritative list of valid categories; the capability entries below it
#: are instances.
_TREE_LINE_RE: Final = re.compile(
    r"^\|?\s*(?P<names>[a-z][a-z0-9|_-]*)/\s+(?P<description>.+?)\s*\|?\s*$"
)

#: Capability ids are `- id: some-id` inside the YAML block.
_CAPABILITY_ID_RE: Final = re.compile(r"^-\s+id:\s*(?P<id>[a-z0-9-]+)\s*$")

#: Capability category values are `category: some-category`.
_CAPABILITY_CATEGORY_RE: Final = re.compile(
    r"^category:\s*(?P<category>[a-z0-9-]+)\s*$"
)

#: Capability implementation paths are `implementation: "catalog/x/y"` (or `""`).
#: This is the taxonomy's own link to the code, so it is the correct thing to
#: cross-check against the directories on disk -- parsing it beats guessing a
#: transformation from directory name to capability id, which is what a first
#: attempt did (`catalog/models/model_provider` is the capability
#: `model-provider-abstraction`, not `model-provider`).
_CAPABILITY_IMPLEMENTATION_RE: Final = re.compile(
    r'^implementation:\s*"(?P<path>[^"]*)"\s*$'
)


@dataclass(frozen=True, slots=True)
class TaxonomyCategory:
    """One leaf of the taxonomy tree."""

    name: str
    description: str
    #: Alternate names for the same category, from a `a|b/` tree entry.
    #: `research/` uses `mcp`, `catalog/` uses `protocols`; both are the same
    #: category and a classifier that treated them as different would propose
    #: a duplicate.
    aliases: tuple[str, ...] = ()

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


@dataclass(frozen=True, slots=True)
class Taxonomy:
    """The parsed taxonomy: categories, and the capabilities already tracked."""

    categories: tuple[TaxonomyCategory, ...]
    capability_ids: tuple[str, ...]
    capability_categories: tuple[str, ...]
    #: Implementation paths declared by capabilities, relative to the repo root.
    #: Only non-empty values are kept.
    capability_implementations: tuple[str, ...] = ()

    def category(self, name: str) -> TaxonomyCategory | None:
        """Look a category up by name or alias, case-insensitively."""
        wanted = name.strip().lower()
        for category in self.categories:
            if wanted in category.all_names:
                return category
        return None

    def has_category(self, name: str) -> bool:
        return self.category(name) is not None

    def has_capability(self, capability_id: str) -> bool:
        return capability_id in self.capability_ids


@dataclass(frozen=True, slots=True)
class Classification:
    """The result of classifying one candidate against the taxonomy."""

    candidate: Candidate
    #: The taxonomy category this maps onto, or `None` if it is new.
    mapped_category: TaxonomyCategory | None
    #: True when the candidate's category does not appear in the taxonomy at
    #: all, so the report proposes it as a `DISCOVERED` entry.
    proposes_new_category: bool

    @property
    def proposed_id(self) -> str:
        """Taxonomy-safe id for a proposal.

        Derived from the candidate's own id rather than its display name so
        that two repositories reporting the same pattern propose the SAME id,
        which is what makes convergence visible across study reports.
        """
        return slugify(self.candidate.pattern_id)

    @property
    def summary(self) -> str:
        """One-line description for a report table."""
        if self.proposes_new_category:
            return f"NEW CATEGORY PROPOSAL: {self.proposed_id}"
        assert (
            self.mapped_category is not None
        )  # logical invariant: set when not proposing
        return f"maps to existing category: {self.candidate.category}"


def parse_taxonomy(text: str) -> Taxonomy:
    """Parse the taxonomy tree and capability list out of `TAXONOMY.md`.

    A small targeted parser rather than a YAML dependency, matching the approach
    already used by `scripts/repo_status.py`. The format is under this
    repository's control, and `TAXONOMY.md` is markdown with one fenced YAML
    block among prose — a general YAML load would fail on the surrounding text.
    """
    categories: list[TaxonomyCategory] = []
    capability_ids: list[str] = []
    capability_categories: list[str] = []
    capability_implementations: list[str] = []

    in_tree = False
    in_yaml = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()

        if stripped.startswith("```text"):
            in_tree = True
            continue
        if stripped.startswith(_YAML_FENCE):
            in_yaml = True
            continue
        if stripped.startswith("```"):
            in_tree = False
            in_yaml = False
            continue

        if in_tree:
            match = _TREE_LINE_RE.match(stripped)
            if match:
                names = match.group("names").split("|")
                # Strip a trailing `(+alias)` note from the description.
                description = match.group("description").split("(")[0].strip()
                categories.append(
                    TaxonomyCategory(
                        name=names[0],
                        description=description,
                        aliases=tuple(names[1:]),
                    )
                )
            continue

        if in_yaml:
            id_match = _CAPABILITY_ID_RE.match(stripped)
            if id_match:
                capability_ids.append(id_match.group("id"))
                continue
            category_match = _CAPABILITY_CATEGORY_RE.match(stripped)
            if category_match:
                capability_categories.append(category_match.group("category"))
                continue
            implementation_match = _CAPABILITY_IMPLEMENTATION_RE.match(stripped)
            if implementation_match and implementation_match.group("path"):
                capability_implementations.append(implementation_match.group("path"))

    return Taxonomy(
        categories=tuple(categories),
        capability_ids=tuple(capability_ids),
        capability_categories=tuple(capability_categories),
        capability_implementations=tuple(capability_implementations),
    )


def load_taxonomy(root: Path) -> Taxonomy:
    """Read and parse `TAXONOMY.md` from a repository root."""
    taxonomy_path = root / "TAXONOMY.md"
    if not taxonomy_path.is_file():
        raise FileNotFoundError(f"no TAXONOMY.md at {taxonomy_path}")
    return parse_taxonomy(taxonomy_path.read_text(encoding="utf-8"))


def classify(candidate: Candidate, taxonomy: Taxonomy) -> Classification:
    """Classify one candidate against the taxonomy.

    Mapping is by the candidate's declared category. A candidate whose category
    is absent from the taxonomy is a proposal — the report says so explicitly
    rather than quietly filing it under the nearest existing name, because
    filing it under the wrong category is how a taxonomy quietly stops
    describing reality.
    """
    mapped = taxonomy.category(candidate.category)
    return Classification(
        candidate=candidate,
        mapped_category=mapped,
        proposes_new_category=mapped is None,
    )


def classify_all(
    candidates: tuple[Candidate, ...], taxonomy: Taxonomy
) -> tuple[Classification, ...]:
    """Classify every candidate, preserving the extractor's ordering."""
    return tuple(classify(candidate, taxonomy) for candidate in candidates)


def proposal_summary(
    classifications: tuple[Classification, ...],
) -> dict[str, list[str]]:
    """Group results for a report header.

    Returns `{"mapped": [...], "proposed": [...]}`, each holding pattern ids.
    The split is what a reader scans first: proposals are the actionable output
    of a study, mappings are confirmation that the taxonomy already covers
    ground a large project also found worth building.
    """
    mapped: list[str] = []
    proposed: list[str] = []
    for classification in classifications:
        if classification.proposes_new_category:
            proposed.append(classification.proposed_id)
        else:
            mapped.append(classification.candidate.pattern_id)
    return {"mapped": sorted(mapped), "proposed": sorted(proposed)}
