"""Tests for infrastructure scanner models."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import pytest

# The entry lives at catalog/deployment/scanner/tests/, so the importable
# parent is catalog/deployment/ -- tests/ -> scanner/ -> deployment/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scanner.models import (
    INFRASTRUCTURE_LAYERS,
    LAYER_DESCRIPTIONS,
    InfraComponent,
    InfrastructureMap,
)


def test_valid_component_creation() -> None:
    comp = InfraComponent(
        layer="data",
        component_type="postgresql",
        name="PostgreSQL Database",
        description="Primary relational database",
        technologies=("PostgreSQL", "pgvector"),
        code_locations=("src/db.py",),
        config_locations=(".env", "docker-compose.yml"),
        confidence=0.9,
        detection_method="manifest",
    )
    assert comp.layer == "data"
    assert comp.component_type == "postgresql"
    assert comp.confidence == 0.9


def test_invalid_layer_raises() -> None:
    with pytest.raises(ValueError):
        InfraComponent(
            layer="invalid_layer",
            component_type="test",
            name="Test",
            description="Test",
            technologies=(),
            code_locations=(),
            config_locations=(),
            confidence=0.5,
            detection_method="keyword",
        )


def test_confidence_bounds() -> None:
    with pytest.raises(ValueError):
        InfraComponent(
            layer="data",
            component_type="test",
            name="Test",
            description="Test",
            technologies=(),
            code_locations=(),
            config_locations=(),
            confidence=1.5,
            detection_method="keyword",
        )
    with pytest.raises(ValueError):
        InfraComponent(
            layer="data",
            component_type="test",
            name="Test",
            description="Test",
            technologies=(),
            code_locations=(),
            config_locations=(),
            confidence=-0.1,
            detection_method="keyword",
        )


def test_invalid_detection_method() -> None:
    with pytest.raises(ValueError):
        InfraComponent(
            layer="data",
            component_type="test",
            name="Test",
            description="Test",
            technologies=(),
            code_locations=(),
            config_locations=(),
            confidence=0.5,
            detection_method="invalid_method",
        )


def test_infrastructure_map_creation() -> None:
    from scanner.models import InfraComponent

    [
        InfraComponent(
            layer="data",
            component_type="postgresql",
            name="PostgreSQL",
            description="Primary DB",
            technologies=("PostgreSQL",),
            code_locations=(),
            config_locations=(".env",),
            confidence=0.9,
            detection_method="manifest",
        ),
        InfraComponent(
            layer="data",
            component_type="redis",
            name="Redis Cache",
            description="Cache layer",
            technologies=("Redis",),
            code_locations=(),
            config_locations=(".env",),
            confidence=0.9,
            detection_method="manifest",
        ),
        InfraComponent(
            layer="identity",
            component_type="jwt",
            name="JWT Auth",
            description="JWT authentication",
            technologies=("JWT",),
            code_locations=("auth.py",),
            config_locations=(),
            confidence=0.8,
            detection_method="keyword",
        ),
    ]

    infra_map = InfrastructureMap(
        repo_name="test-repo",
        components=(
            InfraComponent(
                layer="data",
                component_type="postgresql",
                name="PostgreSQL",
                description="Primary DB",
                technologies=("PostgreSQL",),
                code_locations=(),
                config_locations=(".env",),
                confidence=0.9,
                detection_method="manifest",
            ),
            InfraComponent(
                layer="data",
                component_type="redis",
                name="Redis Cache",
                description="Cache layer",
                technologies=("Redis",),
                code_locations=(),
                config_locations=(".env",),
                confidence=0.9,
                detection_method="manifest",
            ),
            InfraComponent(
                layer="identity",
                component_type="jwt",
                name="JWT Auth",
                description="JWT authentication",
                technologies=("JWT",),
                code_locations=("auth.py",),
                config_locations=(),
                confidence=0.8,
                detection_method="keyword",
            ),
        ),
        layers_covered=2,
        total_components=3,
        layer_summary={"data": 2, "identity": 1},
    )

    assert infra_map.layers_covered == 2
    assert infra_map.total_components == 3
    assert infra_map.layer_summary == {"data": 2, "identity": 1}


def test_components_by_layer() -> None:
    from scanner.models import InfraComponent

    [
        InfraComponent(
            layer="data",
            component_type="postgresql",
            name="PostgreSQL",
            description="Primary DB",
            technologies=("PostgreSQL",),
            code_locations=(),
            config_locations=(),
            confidence=0.9,
            detection_method="manifest",
        ),
        InfraComponent(
            layer="identity",
            component_type="jwt",
            name="JWT Auth",
            description="JWT Auth",
            technologies=("JWT",),
            code_locations=(),
            config_locations=(),
            confidence=0.8,
            detection_method="keyword",
        ),
    ]
    infra_map = InfrastructureMap(
        repo_name="test",
        components=(
            InfraComponent(
                layer="data",
                component_type="postgresql",
                name="PostgreSQL",
                description="Primary DB",
                technologies=("PostgreSQL",),
                code_locations=(),
                config_locations=(),
                confidence=0.9,
                detection_method="manifest",
            ),
            InfraComponent(
                layer="identity",
                component_type="jwt",
                name="JWT Auth",
                description="JWT Auth",
                technologies=("JWT",),
                code_locations=(),
                config_locations=(),
                confidence=0.8,
                detection_method="keyword",
            ),
        ),
        layers_covered=2,
        total_components=2,
        layer_summary={"data": 1, "identity": 1},
    )

    data_comps = infra_map.components_by_layer("data")
    assert len(data_comps) == 1
    assert data_comps[0].component_type == "postgresql"

    identity_comps = infra_map.components_by_layer("identity")
    assert len(identity_comps) == 1


def test_components_by_type() -> None:
    from scanner.models import InfraComponent

    [
        InfraComponent(
            layer="data",
            component_type="postgresql",
            name="PostgreSQL",
            description="Primary DB",
            technologies=("PostgreSQL",),
            code_locations=(),
            config_locations=(),
            confidence=0.9,
            detection_method="manifest",
        ),
        InfraComponent(
            layer="state",
            component_type="redis",
            name="Redis Cache",
            description="Cache",
            technologies=("Redis",),
            code_locations=(),
            config_locations=(),
            confidence=0.9,
            detection_method="manifest",
        ),
    ]
    infra_map = InfrastructureMap(
        repo_name="test",
        components=(
            InfraComponent(
                layer="data",
                component_type="postgresql",
                name="PostgreSQL",
                description="Primary DB",
                technologies=("PostgreSQL",),
                code_locations=(),
                config_locations=(),
                confidence=0.9,
                detection_method="manifest",
            ),
            InfraComponent(
                layer="state",
                component_type="redis",
                name="Redis Cache",
                description="Cache",
                technologies=("Redis",),
                code_locations=(),
                config_locations=(),
                confidence=0.9,
                detection_method="manifest",
            ),
        ),
        layers_covered=2,
        total_components=2,
        layer_summary={"data": 1, "state": 1},
    )

    pg_comps = infra_map.components_by_type("postgresql")
    assert len(pg_comps) == 1


def test_get_coverage() -> None:
    from scanner.models import InfraComponent

    [
        InfraComponent(
            layer="data",
            component_type="postgresql",
            name="PostgreSQL",
            description="Primary DB",
            technologies=("PostgreSQL",),
            code_locations=(),
            config_locations=(),
            confidence=0.9,
            detection_method="manifest",
        ),
        InfraComponent(
            layer="data",
            component_type="redis",
            name="Redis Cache",
            description="Cache",
            technologies=("Redis",),
            code_locations=(),
            config_locations=(),
            confidence=0.9,
            detection_method="manifest",
        ),
    ]
    infra_map = InfrastructureMap(
        repo_name="test",
        components=(
            InfraComponent(
                layer="data",
                component_type="postgresql",
                name="PostgreSQL",
                description="Primary DB",
                technologies=("PostgreSQL",),
                code_locations=(),
                config_locations=(),
                confidence=0.9,
                detection_method="manifest",
            ),
            InfraComponent(
                layer="data",
                component_type="redis",
                name="Redis Cache",
                description="Cache",
                technologies=("Redis",),
                code_locations=(),
                config_locations=(),
                confidence=0.9,
                detection_method="manifest",
            ),
        ),
        layers_covered=1,
        total_components=2,
        layer_summary={"data": 2},
    )

    coverage = infra_map.get_coverage()
    # data layer has 2 components, expected 5 for full coverage = 0.4
    assert coverage["data"] == 0.4
    # other layers have 0
    assert coverage["identity"] == 0.0
    assert coverage["transaction"] == 0.0


def test_to_dict() -> None:
    from scanner.models import InfraComponent

    [
        InfraComponent(
            layer="data",
            component_type="postgresql",
            name="PostgreSQL",
            description="Primary DB",
            technologies=("PostgreSQL",),
            code_locations=(),
            config_locations=(),
            confidence=0.9,
            detection_method="manifest",
        ),
    ]
    infra_map = InfrastructureMap(
        repo_name="test-repo",
        components=(
            InfraComponent(
                layer="data",
                component_type="postgresql",
                name="PostgreSQL",
                description="Primary DB",
                technologies=("PostgreSQL",),
                code_locations=(),
                config_locations=(),
                confidence=0.9,
                detection_method="manifest",
            ),
        ),
        layers_covered=1,
        total_components=1,
        layer_summary={"data": 1},
    )

    d = infra_map.to_dict()
    assert d["repo_name"] == "test-repo"
    assert d["layers_covered"] == 1
    assert d["total_components"] == 1
    assert d["layer_summary"] == {"data": 1}
    components = cast(list[dict[str, object]], d["components"])
    assert len(components) == 1
    assert components[0]["component_type"] == "postgresql"


def test_infrastructure_layers_constant() -> None:
    assert len(INFRASTRUCTURE_LAYERS) == 12
    expected = {
        "identity",
        "transaction",
        "state",
        "data",
        "communication",
        "delivery",
        "observability",
        "security",
        "deployment",
        "integration",
        "user_experience",
        "governance",
    }
    assert set(INFRASTRUCTURE_LAYERS) == expected


def test_layer_descriptions() -> None:
    assert len(LAYER_DESCRIPTIONS) == 12
    for layer in INFRASTRUCTURE_LAYERS:
        assert layer in LAYER_DESCRIPTIONS
        assert len(LAYER_DESCRIPTIONS[layer]) > 10
