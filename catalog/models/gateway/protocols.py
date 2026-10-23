"""Core protocols and types for the Model Gateway capability.

The gateway owns *routing* — provider selection, fallback, load balancing, cost
tracking, cooldown and health checks. It composes ``ModelProvider`` (ADR-0007)
and an injected transport; it never replaces either, and it never owns the
socket or the shape (ADR-0039).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from model_provider import ChatResponse, Message, StreamDelta, Usage

# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class GatewayError(Exception):
    """Base class for gateway failures."""


class NoHealthyDeploymentError(GatewayError):
    """No deployment of the requested model is currently healthy."""


class AllFallbacksExhaustedError(GatewayError):
    """Every deployment and fallback in the chain failed."""


class RateLimitedError(GatewayError):
    """A rate-limit hint denied the request before routing."""


class UnknownModelError(GatewayError):
    """The requested model is not registered."""


# --------------------------------------------------------------------------- #
# Request / response
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class GatewayRequest:
    """A neutral request to the gateway.

    ``model`` is the (possibly aliased) model name. ``messages`` and ``system``
    are the conversation. ``tools`` is the tool schema list. ``params`` carries
    provider-specific knobs (temperature, max_tokens, ...) that are forwarded
    verbatim to the chosen adapter.
    """

    model: str
    messages: tuple[Message, ...]
    system: str | None = None
    tools: tuple[Mapping[str, Any], ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    stream: bool = False


# --------------------------------------------------------------------------- #
# Provider registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ProviderEntry:
    """One deployment of one model on one provider.

    A *model group* is the set of entries sharing a ``model`` name; the router
    load-balances across them. ``order`` is the priority tier (lower = higher
    priority); entries with the same ``order`` are peers.
    """

    name: str
    provider: str
    model: str
    capabilities: frozenset[str] = frozenset()
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    rate_limit_rpm: int | None = None
    rate_limit_tpm: int | None = None
    order: int = 0
    weight: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class HealthCheck(Protocol):
    """Injected health probe. Default: assume healthy."""

    def is_healthy(self, entry: ProviderEntry) -> bool:
        """Return ``True`` if the deployment should receive traffic."""
        ...


class DefaultHealthCheck:
    """Assume every deployment is healthy (no network probe)."""

    def is_healthy(self, entry: ProviderEntry) -> bool:  # noqa: ARG002
        return True


@runtime_checkable
class CircuitBreaker(Protocol):
    """Injected circuit-breaker hook (owned by the reliability layer, 5B.4)."""

    def is_open(self, entry: ProviderEntry) -> bool:
        """Return ``True`` if the deployment must be skipped."""
        ...

    def record_success(self, entry: ProviderEntry) -> None:
        """Record a successful call."""
        ...

    def record_failure(self, entry: ProviderEntry) -> None:
        """Record a failed call."""
        ...


class NoopCircuitBreaker:
    """Circuit breaker that never trips (default)."""

    def is_open(self, entry: ProviderEntry) -> bool:  # noqa: ARG002
        return False

    def record_success(self, entry: ProviderEntry) -> None:  # noqa: ARG002
        return None

    def record_failure(self, entry: ProviderEntry) -> None:  # noqa: ARG002
        return None


@runtime_checkable
class ProviderRegistry(Protocol):
    """Registry of providers, models, aliases and capabilities."""

    def register(self, entry: ProviderEntry) -> None:
        """Register one deployment."""
        ...

    def unregister(self, name: str) -> None:
        """Remove a deployment by name."""
        ...

    def entries_for(self, model: str) -> tuple[ProviderEntry, ...]:
        """All deployments for ``model`` (or its alias target)."""
        ...

    def alias(self, name: str, target: str) -> None:
        """Map ``name`` to ``target`` (model-group aliasing)."""
        ...

    def resolve(self, model: str) -> str:
        """Resolve an alias to its target model name."""
        ...

    def all_entries(self) -> tuple[ProviderEntry, ...]:
        """Every registered deployment."""
        ...


# --------------------------------------------------------------------------- #
# Routing strategy
# --------------------------------------------------------------------------- #


class RoutingStrategy(StrEnum):
    """Strategy used to pick a deployment within a model group."""

    SIMPLE_SHUFFLE = "simple-shuffle"
    PRIORITY = "priority"
    ROUND_ROBIN = "round-robin"
    LEAST_BUSY = "least-busy"
    LATENCY_BASED = "latency-based"
    COST_BASED = "cost-based"


@dataclass(slots=True)
class Router:
    """Picks a deployment for a request.

    ``strategy`` selects the algorithm. ``round_robin_counters`` is mutable
    state keyed by model group; ``_lock`` is not used (callers serialise or
    accept best-effort, matching the sync-first design).
    """

    strategy: RoutingStrategy = RoutingStrategy.SIMPLE_SHUFFLE
    _rr_counters: dict[str, int] = field(default_factory=dict)

    def pick(
        self,
        candidates: Sequence[ProviderEntry],
        *,
        busy: Mapping[str, int] | None = None,
        latency: Mapping[str, float] | None = None,
    ) -> ProviderEntry | None:
        """Pick one deployment from ``candidates`` per ``strategy``.

        Returns ``None`` if ``candidates`` is empty.
        """
        if not candidates:
            return None
        if self.strategy is RoutingStrategy.PRIORITY:
            return _pick_priority(candidates)
        if self.strategy is RoutingStrategy.ROUND_ROBIN:
            return _pick_round_robin(self, candidates)
        if self.strategy is RoutingStrategy.LEAST_BUSY:
            return _pick_least_busy(candidates, busy or {})
        if self.strategy is RoutingStrategy.LATENCY_BASED:
            return _pick_latency(candidates, latency or {})
        if self.strategy is RoutingStrategy.COST_BASED:
            return _pick_cost(candidates)
        # SIMPLE_SHUFFLE (default): weighted pick.
        return _pick_shuffle(candidates)


def _pick_priority(candidates: Sequence[ProviderEntry]) -> ProviderEntry:
    # Lowest order first; among peers, weighted shuffle.
    min_order = min(c.order for c in candidates)
    peers = [c for c in candidates if c.order == min_order]
    return _pick_shuffle(peers)


def _pick_round_robin(
    router: Router, candidates: Sequence[ProviderEntry]
) -> ProviderEntry:
    key = candidates[0].model if candidates else ""
    idx = router._rr_counters.get(key, 0)
    chosen = candidates[idx % len(candidates)]
    router._rr_counters[key] = idx + 1
    return chosen


def _pick_least_busy(
    candidates: Sequence[ProviderEntry], busy: Mapping[str, int]
) -> ProviderEntry:
    return min(candidates, key=lambda c: busy.get(c.name, 0))


def _pick_latency(
    candidates: Sequence[ProviderEntry], latency: Mapping[str, float]
) -> ProviderEntry:
    return min(candidates, key=lambda c: latency.get(c.name, float("inf")))


def _pick_cost(candidates: Sequence[ProviderEntry]) -> ProviderEntry:
    return min(candidates, key=lambda c: c.cost_per_1k_input + c.cost_per_1k_output)


def _pick_shuffle(candidates: Sequence[ProviderEntry]) -> ProviderEntry:
    import random

    weights = [max(c.weight, 0.0) for c in candidates]
    if all(w == 0 for w in weights):
        weights = [1.0] * len(candidates)
    return random.choices(candidates, weights=weights, k=1)[0]  # noqa: S311


# --------------------------------------------------------------------------- #
# Cooldown
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class CooldownTracker:
    """Per-deployment cooldown with automatic recovery.

    ``cooldowns`` maps deployment name -> expiry (monotonic seconds). A
    deployment is cooled while ``now < expiry``.
    """

    cooldown_seconds: float = 5.0
    _cooldowns: dict[str, float] = field(default_factory=dict)

    def cool(self, entry: ProviderEntry, *, now: float | None = None) -> None:
        import time

        t = now if now is not None else time.monotonic()
        self._cooldowns[entry.name] = t + self.cooldown_seconds

    def is_cooled(self, entry: ProviderEntry, *, now: float | None = None) -> bool:
        import time

        t = now if now is not None else time.monotonic()
        expiry = self._cooldowns.get(entry.name)
        if expiry is None:
            return False
        if t >= expiry:
            del self._cooldowns[entry.name]
            return False
        return True

    def clear(self, entry: ProviderEntry) -> None:
        self._cooldowns.pop(entry.name, None)


# --------------------------------------------------------------------------- #
# Cost tracking
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class CostRecord:
    """One recorded call's cost."""

    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost: float


@dataclass(slots=True)
class CostTracker:
    """Token counting + per-model pricing + budget alerts."""

    budget_usd: float | None = None
    _records: list[CostRecord] = field(default_factory=list)

    def record(
        self,
        *,
        model: str,
        provider: str,
        usage: Usage | None,
        entry: ProviderEntry,
    ) -> CostRecord:
        input_tokens = 0
        output_tokens = 0
        if usage is not None:
            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
        cost = (
            input_tokens / 1000.0 * entry.cost_per_1k_input
            + output_tokens / 1000.0 * entry.cost_per_1k_output
        )
        rec = CostRecord(
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
        self._records.append(rec)
        return rec

    @property
    def total_cost(self) -> float:
        return sum(r.cost for r in self._records)

    @property
    def records(self) -> tuple[CostRecord, ...]:
        return tuple(self._records)

    @property
    def budget_exceeded(self) -> bool:
        if self.budget_usd is None:
            return False
        return self.total_cost > self.budget_usd

    def clear(self) -> None:
        self._records.clear()


# --------------------------------------------------------------------------- #
# Gateway protocol
# --------------------------------------------------------------------------- #


@runtime_checkable
class Gateway(Protocol):
    """The gateway surface."""

    def chat(self, request: GatewayRequest) -> ChatResponse:
        """Route and execute one (non-streaming) request."""
        ...

    def stream(self, request: GatewayRequest) -> Iterator[StreamDelta]:
        """Route and execute one streaming request."""
        ...


def make_request(
    model: str,
    messages: Sequence[Message],
    *,
    system: str | None = None,
    tools: Sequence[Mapping[str, Any]] = (),
    params: Mapping[str, Any] | None = None,
    stream: bool = False,
) -> GatewayRequest:
    """Convenience constructor for ``GatewayRequest``."""
    return GatewayRequest(
        model=model,
        messages=tuple(messages),
        system=system,
        tools=tuple(tools),
        params=dict(params) if params else {},
        stream=stream,
    )
