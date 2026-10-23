"""Model Gateway — routing, fallback, load balancing, cost tracking.

Composes ``ModelProvider`` (ADR-0007) and an injected transport; owns *routing*,
not the socket or the shape (ADR-0039). Zero runtime dependencies.

    from gateway import DefaultGateway, GatewayConfig, InMemoryProviderRegistry, make_request
"""

from __future__ import annotations

from .gateway import DefaultGateway, GatewayConfig, ProviderBundle
from .protocols import (
    AllFallbacksExhaustedError,
    CircuitBreaker,
    CooldownTracker,
    CostRecord,
    CostTracker,
    DefaultHealthCheck,
    Gateway,
    GatewayError,
    GatewayRequest,
    HealthCheck,
    NoHealthyDeploymentError,
    NoopCircuitBreaker,
    ProviderEntry,
    RateLimitedError,
    Router,
    RoutingStrategy,
    UnknownModelError,
    make_request,
)
from .registry import InMemoryProviderRegistry, create_registry

__all__ = [
    "AllFallbacksExhaustedError",
    "CircuitBreaker",
    "CooldownTracker",
    "CostRecord",
    "CostTracker",
    "DefaultGateway",
    "DefaultHealthCheck",
    "Gateway",
    "GatewayConfig",
    "GatewayError",
    "GatewayRequest",
    "HealthCheck",
    "InMemoryProviderRegistry",
    "NoHealthyDeploymentError",
    "NoopCircuitBreaker",
    "ProviderBundle",
    "ProviderEntry",
    "RateLimitedError",
    "Router",
    "RoutingStrategy",
    "UnknownModelError",
    "create_registry",
    "make_request",
]
