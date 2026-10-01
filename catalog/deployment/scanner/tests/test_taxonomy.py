"""Tests for infrastructure scanner taxonomy."""

from __future__ import annotations

import sys
from pathlib import Path

# The entry lives at catalog/deployment/scanner/tests/, so the importable
# parent is catalog/deployment/ -- tests/ -> scanner/ -> deployment/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scanner.models import INFRASTRUCTURE_LAYERS
from scanner.taxonomy import (
    INFRASTRUCTURE_TAXONOMY,
    validate_taxonomy,
)


def test_taxonomy_size() -> None:
    """Taxonomy should have 80+ component types."""
    assert len(INFRASTRUCTURE_TAXONOMY) >= 80


def test_all_layers_covered() -> None:
    """All 12 layers should have at least 5 component types."""
    for _comp_type, info in INFRASTRUCTURE_TAXONOMY.items():
        assert "layer" in info
        assert info["layer"] in INFRASTRUCTURE_LAYERS

    for layer in INFRASTRUCTURE_LAYERS:
        count = sum(
            1 for info in INFRASTRUCTURE_TAXONOMY.values() if info["layer"] == layer
        )
        assert count >= 5, f"Layer {layer} has only {count} component types"


def test_component_structure() -> None:
    """Each component type should have required fields."""
    for _comp_type, info in INFRASTRUCTURE_TAXONOMY.items():
        assert "layer" in info
        assert "keywords" in info
        assert "file_patterns" in info
        assert "config_patterns" in info
        assert isinstance(info["keywords"], tuple)
        assert isinstance(info["file_patterns"], tuple)
        assert isinstance(info["config_patterns"], tuple)
        assert len(info["keywords"]) >= 5
        assert len(info["file_patterns"]) >= 1
        assert len(info["config_patterns"]) >= 1


def test_no_duplicate_component_types() -> None:
    """Component types should be unique."""
    types = list(INFRASTRUCTURE_TAXONOMY.keys())
    assert len(types) == len(set(types))


def test_layer_distribution() -> None:
    """Each layer should have reasonable number of types."""
    layer_counts: dict[str, int] = {}
    for info in INFRASTRUCTURE_TAXONOMY.values():
        layer = info["layer"]
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    for layer, count in layer_counts.items():
        assert count >= 5, f"Layer {layer} has only {count} types"


def test_validate_taxonomy() -> None:
    """validate_taxonomy should not raise."""
    validate_taxonomy()


def test_keyword_uniqueness_within_layer() -> None:
    """Keywords should not have too much overlap within a layer."""
    for layer in ("identity", "data", "deployment"):
        layer_types = [
            t for t, i in INFRASTRUCTURE_TAXONOMY.items() if i["layer"] == layer
        ]
        all_keywords: list[str] = []
        for t in layer_types:
            all_keywords.extend(INFRASTRUCTURE_TAXONOMY[t]["keywords"])
        # Some overlap is expected, but not total duplication
        unique = set(all_keywords)
        assert len(unique) > len(all_keywords) * 0.3  # At least 30% unique


def test_all_layers_have_config_patterns() -> None:
    for comp_type, info in INFRASTRUCTURE_TAXONOMY.items():
        assert info["config_patterns"], f"{comp_type}: missing config_patterns"


def test_layer_names_valid() -> None:
    for info in INFRASTRUCTURE_TAXONOMY.values():
        assert info["layer"] in INFRASTRUCTURE_LAYERS
