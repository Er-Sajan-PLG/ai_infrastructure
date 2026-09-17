"""Unit tests for study_pipeline.classify — taxonomy mapping and proposals.

The classifier reads the REAL `TAXONOMY.md`, so these tests assert against the
actual file for the integration case and against synthetic taxonomy text for the
parser's edge cases. That split is deliberate: hardcoding the expected category
list into the test would reproduce the bug this module was written to fix, where
a constant drifted from the file it was supposed to describe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from study_pipeline.classify import (
    Classification,
    Taxonomy,
    TaxonomyCategory,
    classify,
    load_taxonomy,
    parse_taxonomy,
)
from study_pipeline.patterns import Candidate, Confidence

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _candidate(pattern_id: str = "retrieval", category: str = "retrieval") -> Candidate:
    return Candidate(
        pattern_id=pattern_id,
        name="A pattern",
        category=category,
        confidence=Confidence.STRONG,
        evidence_paths=("src/x/",),
        evidence_kind="directory evidence",
        limitations="Cannot tell how it is implemented.",
    )


SYNTHETIC = """
# Fake taxonomy

## 1. Taxonomy Tree

```text
agents/                Agents & Orchestration
tools/                 Tools
mcp|protocols/         MCP & Protocols (research/ uses mcp, catalog/ uses protocols)
harnesses|harness/     Agent Harnesses
```

## 2. Capability Entry Schema

```yaml
id:                    # kebab-case
name:
category:
```

## 3. The registry

```yaml
capabilities:
  - id: tool-registry
    name: Tool Registry
    category: tools
  - id: mcp-client
    name: MCP Client
    category: mcp
```
"""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_reads_tree_categories() -> None:
    taxonomy = parse_taxonomy(SYNTHETIC)
    names = [c.name for c in taxonomy.categories]
    assert names == ["agents", "tools", "mcp", "harnesses"]


def test_parse_records_aliases() -> None:
    # `research/` uses `mcp`, `catalog/` uses `protocols`. Treating them as
    # different categories would propose a duplicate of an existing one.
    taxonomy = parse_taxonomy(SYNTHETIC)
    mcp = taxonomy.category("mcp")
    assert mcp is not None
    assert mcp.aliases == ("protocols",)
    assert taxonomy.category("protocols") is mcp


def test_parse_strips_parenthetical_from_description() -> None:
    taxonomy = parse_taxonomy(SYNTHETIC)
    assert taxonomy.category("mcp").description == "MCP & Protocols"  # type: ignore[union-attr]


def test_parse_reads_capability_ids() -> None:
    taxonomy = parse_taxonomy(SYNTHETIC)
    assert taxonomy.capability_ids == ("tool-registry", "mcp-client")


def test_parse_reads_capability_categories() -> None:
    taxonomy = parse_taxonomy(SYNTHETIC)
    assert "tools" in taxonomy.capability_categories
    assert "mcp" in taxonomy.capability_categories


def test_parse_ignores_prose_and_schema_blocks() -> None:
    # The schema block contains `id:` and `category:` lines with no values; a
    # naive parser would read them as an entry.
    taxonomy = parse_taxonomy(SYNTHETIC)
    assert "kebab-case" not in taxonomy.capability_ids


def test_parse_of_empty_text_is_empty() -> None:
    taxonomy = parse_taxonomy("")
    assert taxonomy.categories == ()
    assert taxonomy.capability_ids == ()


def test_parse_does_not_confuse_the_schema_example() -> None:
    taxonomy = parse_taxonomy(SYNTHETIC)
    # The schema block lists bare field names, not entries.
    assert "name" not in taxonomy.capability_ids


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def test_has_category_accepts_aliases() -> None:
    taxonomy = parse_taxonomy(SYNTHETIC)
    assert taxonomy.has_category("mcp")
    assert taxonomy.has_category("protocols")


def test_has_category_is_case_insensitive() -> None:
    assert parse_taxonomy(SYNTHETIC).has_category("MCP")


def test_has_category_rejects_unknown() -> None:
    assert not parse_taxonomy(SYNTHETIC).has_category("quantum")


def test_has_capability() -> None:
    taxonomy = parse_taxonomy(SYNTHETIC)
    assert taxonomy.has_capability("tool-registry")
    assert not taxonomy.has_capability("nonexistent")


# ---------------------------------------------------------------------------
# The real taxonomy
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_taxonomy() -> Taxonomy:
    return load_taxonomy(REPO_ROOT)


def test_real_taxonomy_parses(real_taxonomy: Taxonomy) -> None:
    assert len(real_taxonomy.categories) >= 20
    assert len(real_taxonomy.capability_ids) >= 7


def test_every_implementation_path_exists_on_disk() -> None:
    """Cross-check the parsed implementation paths against the catalog.

    This is what makes the parser's output meaningful rather than merely
    well-formed: it asserts the paths it read correspond to entries that exist.
    A parser that silently stopped finding capabilities -- because the file's
    format changed, say -- would leave the list empty and every downstream
    classification would look fine while describing nothing.

    Uses the taxonomy's OWN `implementation:` field rather than guessing a
    name transformation. A first attempt derived a capability id from the
    directory name and produced a false failure: `catalog/models/model_provider`
    implements `model-provider-abstraction`, not `model-provider`.
    """
    taxonomy = load_taxonomy(REPO_ROOT)
    assert taxonomy.capability_implementations, "taxonomy parsed zero implementations"

    for declared in taxonomy.capability_implementations:
        path = REPO_ROOT / declared
        assert path.is_dir(), f"TAXONOMY.md declares {declared!r}, which does not exist"
        assert (path / "__init__.py").is_file(), f"{declared} is not a Python package"


def test_every_implemented_catalog_entry_is_declared() -> None:
    """And the converse: no catalog entry is missing from the taxonomy.

    Drift in this direction is the one charter §14 cares about -- an entry on
    disk that TAXONOMY.md does not know about.
    """
    taxonomy = load_taxonomy(REPO_ROOT)
    declared = {Path(p).resolve() for p in taxonomy.capability_implementations}
    on_disk = {
        path.resolve()
        for path in (REPO_ROOT / "catalog").glob("*/*")
        if path.is_dir() and (path / "__init__.py").is_file()
    }
    assert on_disk, "no catalog entries found on disk; the fixture path is wrong"
    untracked = on_disk - declared
    assert not untracked, (
        "catalog entries exist with no TAXONOMY.md implementation path: "
        f"{sorted(p.name for p in untracked)}"
    )


def test_classification_dataclass_is_frozen() -> None:
    import dataclasses

    result = classify(_candidate(), parse_taxonomy(SYNTHETIC))
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.proposes_new_category = True  # type: ignore[misc]


def test_taxonomy_category_all_names() -> None:
    category = TaxonomyCategory("mcp", "MCP", ("protocols", "proto"))
    assert category.all_names == ("mcp", "protocols", "proto")


def test_classification_summary_for_a_mapping() -> None:
    result: Classification = classify(
        _candidate(category="tools"), parse_taxonomy(SYNTHETIC)
    )
    assert result.summary == "maps to existing category: tools"
