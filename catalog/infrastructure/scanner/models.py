"""Data models for the infrastructure scanner.

Frozen dataclasses with slots for performance and immutability.
No Pydantic — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# The 12 Infrastructure Layers (constant for validation)
# ---------------------------------------------------------------------------

INFRASTRUCTURE_LAYERS: Final[tuple[str, ...]] = (
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
)

LAYER_DESCRIPTIONS: Final[dict[str, str]] = {
    "identity": "Authentication, authorization, OAuth, SSO, MFA, RBAC, sessions, API keys",
    "transaction": "Payments, billing, subscriptions, invoicing, checkout, refunds",
    "state": "Caching, sessions, distributed locks, feature flags, rate limit state",
    "data": "Databases, search engines, object storage, ETL pipelines, backups, data warehouses",
    "communication": "REST, GraphQL, gRPC, WebSocket, message queues, event streaming, pub/sub",
    "delivery": "CDN, load balancer, reverse proxy, API gateway, edge computing, DNS",
    "observability": "Logging, metrics, distributed tracing, error tracking, APM, alerting",
    "security": "Encryption, WAF, secrets management, audit logs, vulnerability scanning, compliance",
    "deployment": "CI/CD pipelines, containers, Kubernetes, IaC, artifact registries, GitOps",
    "integration": "Webhooks, third-party APIs, SDKs, plugins, marketplace, partner integrations",
    "user_experience": "i18n, accessibility, feature flags, A/B testing, personalization, analytics",
    "governance": "Rate limiting, quotas, multi-tenancy, data residency, compliance, policies",
}


@dataclass(frozen=True, slots=True)
class InfraComponent:
    """A single infrastructure component detected in a codebase.

    Attributes:
        layer: One of the 12 infrastructure layers.
        component_type: Specific type within the layer (e.g., "payment_gateway", "redis_cache").
        name: Human-readable name (e.g., "Stripe Payment Processing").
        description: What this component does in the system.
        technologies: Concrete technologies/products detected (e.g., ("Stripe", "PostgreSQL")).
        code_locations: Source files where this component is implemented.
        config_locations: Config files where this component is configured.
        confidence: Detection confidence 0.0-1.0.
        detection_method: How this was detected ("keyword", "config_parse", "manifest", "llm").
    """

    layer: str
    component_type: str
    name: str
    description: str
    technologies: tuple[str, ...]
    code_locations: tuple[str, ...]
    config_locations: tuple[str, ...]
    confidence: float
    detection_method: str

    def __post_init__(self) -> None:
        if self.layer not in INFRASTRUCTURE_LAYERS:
            raise ValueError(
                f"Invalid layer: {self.layer}. Must be one of {INFRASTRUCTURE_LAYERS}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")
        if self.detection_method not in ("keyword", "config_parse", "manifest", "llm"):
            raise ValueError(
                f"Invalid detection_method: {self.detection_method}. "
                "Must be 'keyword', 'config_parse', 'manifest', or 'llm'"
            )


@dataclass(frozen=True, slots=True)
class InfrastructureMap:
    """Complete infrastructure map of a repository.

    Attributes:
        repo_name: Name of the scanned repository.
        components: All detected infrastructure components.
        layers_covered: Number of the 12 layers that have at least one component.
        total_components: Total number of components detected.
        layer_summary: Mapping of layer name to component count.
    """

    repo_name: str
    components: tuple[InfraComponent, ...]
    layers_covered: int
    total_components: int
    layer_summary: dict[str, int]

    def components_by_layer(self, layer: str) -> tuple[InfraComponent, ...]:
        """Filter components by layer."""
        return tuple(c for c in self.components if c.layer == layer)

    def components_by_type(self, component_type: str) -> tuple[InfraComponent, ...]:
        """Filter components by component_type."""
        return tuple(c for c in self.components if c.component_type == component_type)

    def get_coverage(self) -> dict[str, float]:
        """Return per-layer coverage scores (0.0-1.0).

        Coverage = min(1.0, component_count / expected_components_per_layer).
        Expected is 5 components per layer for full coverage.
        """
        expected_per_layer = 5
        return {
            layer: min(1.0, self.layer_summary.get(layer, 0) / expected_per_layer)
            for layer in INFRASTRUCTURE_LAYERS
        }

    def to_dict(self) -> dict[str, object]:
        """Serialize to dictionary for report output."""
        return {
            "repo_name": self.repo_name,
            "layers_covered": self.layers_covered,
            "total_components": self.total_components,
            "layer_summary": self.layer_summary,
            "components": [
                {
                    "layer": c.layer,
                    "component_type": c.component_type,
                    "name": c.name,
                    "description": c.description,
                    "technologies": list(c.technologies),
                    "code_locations": list(c.code_locations),
                    "config_locations": list(c.config_locations),
                    "confidence": c.confidence,
                    "detection_method": c.detection_method,
                }
                for c in self.components
            ],
        }
