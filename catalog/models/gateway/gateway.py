"""Gateway implementation: routing, fallback, cooldown, cost tracking."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from model_provider import (
    ChatRequest,
    ChatResponse,
    Provider,
    StreamDelta,
    Transport,
)
from model_provider import (
    chat as provider_chat,
)
from model_provider import (
    stream as provider_stream,
)

from .protocols import (
    AllFallbacksExhaustedError,
    CircuitBreaker,
    CooldownTracker,
    CostTracker,
    DefaultHealthCheck,
    GatewayError,
    GatewayRequest,
    HealthCheck,
    NoHealthyDeploymentError,
    NoopCircuitBreaker,
    ProviderEntry,
    ProviderRegistry,
    RateLimitedError,
    Router,
    RoutingStrategy,
    UnknownModelError,
)


@dataclass(slots=True)
class ProviderBundle:
    """Wiring for one provider: adapter + transport + api key."""

    provider: Provider
    transport: Transport
    api_key: str


@dataclass(slots=True)
class GatewayConfig:
    """Configuration for a ``DefaultGateway``."""

    registry: ProviderRegistry
    providers: Mapping[str, ProviderBundle]
    router: Router | None = None
    cooldown: CooldownTracker | None = None
    circuit_breaker: CircuitBreaker | None = None
    health_check: HealthCheck | None = None
    cost_tracker: CostTracker | None = None
    fallbacks: Mapping[str, Sequence[str]] = field(default_factory=dict)
    rate_limiter: Callable[[ProviderEntry], bool] | None = None
    max_retries_per_group: int = 2

    def __post_init__(self) -> None:
        if self.router is None:
            self.router = Router(strategy=RoutingStrategy.SIMPLE_SHUFFLE)
        if self.cooldown is None:
            self.cooldown = CooldownTracker()
        if self.circuit_breaker is None:
            self.circuit_breaker = NoopCircuitBreaker()
        if self.health_check is None:
            self.health_check = DefaultHealthCheck()
        if self.cost_tracker is None:
            self.cost_tracker = CostTracker()


class DefaultGateway:
    """Default ``Gateway`` implementation."""

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    @property
    def config(self) -> GatewayConfig:
        return self._config

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #

    def chat(self, request: GatewayRequest) -> ChatResponse:
        model = request.model
        if not self._config.registry.entries_for(
            model
        ) and not self._config.fallbacks.get(model):
            # Could still be an alias; resolve.
            resolved = self._config.registry.resolve(model)
            if not self._config.registry.entries_for(resolved):
                raise UnknownModelError(f"model {model!r} is not registered")
            model = resolved

        chain = self._build_chain(model)
        last_error: Exception | None = None

        for group_model in chain:
            entries = self._healthy_entries(group_model)
            if not entries:
                last_error = NoHealthyDeploymentError(
                    f"no healthy deployment for {group_model!r}"
                )
                continue

            # Retry within group up to max_retries_per_group.
            tried: set[str] = set()
            attempts = 0
            max_attempts = max(1, self._config.max_retries_per_group + 1)
            while attempts < max_attempts:
                attempts += 1
                # Pick a deployment not yet tried in this round.
                available = [e for e in entries if e.name not in tried]
                if not available:
                    available = list(entries)
                    tried.clear()
                picked = (
                    self._config.router.pick(available)
                    if self._config.router
                    else (available[0] if available else None)
                )
                if picked is None:
                    break

                # Rate limit hint.
                if self._config.rate_limiter is not None:
                    try:
                        if not self._config.rate_limiter(picked):
                            raise RateLimitedError(f"rate limited: {picked.name}")
                    except RateLimitedError:
                        raise

                # Circuit breaker check.
                cb = self._config.circuit_breaker
                if cb is not None and cb.is_open(picked):
                    tried.add(picked.name)
                    continue

                bundle = self._config.providers.get(picked.provider)
                if bundle is None:
                    tried.add(picked.name)
                    last_error = GatewayError(
                        f"no provider bundle for {picked.provider!r}"
                    )
                    continue

                try:
                    response = provider_chat(
                        self._to_chat_request(request, picked.model),
                        provider=bundle.provider,
                        transport=bundle.transport,
                        api_key=bundle.api_key,
                    )
                except Exception as exc:
                    last_error = exc
                    tried.add(picked.name)
                    if cb is not None:
                        cb.record_failure(picked)
                    cooldown = self._config.cooldown
                    if cooldown is not None:
                        cooldown.cool(picked)
                    # Weighted failover: try another peer in the same group.
                    continue

                # Success.
                if cb is not None:
                    cb.record_success(picked)
                cooldown = self._config.cooldown
                if cooldown is not None:
                    cooldown.clear(picked)

                # Cost tracking.
                ct = self._config.cost_tracker
                if ct is not None:
                    ct.record(
                        model=picked.model,
                        provider=picked.provider,
                        usage=response.usage if hasattr(response, "usage") else None,
                        entry=picked,
                    )

                return response

            # Exhausted retries in this group; move to next fallback.
            continue

        if last_error is None:
            last_error = AllFallbacksExhaustedError("all fallbacks exhausted")
        if isinstance(last_error, GatewayError):
            raise last_error
        raise AllFallbacksExhaustedError(str(last_error)) from last_error

    def stream(self, request: GatewayRequest) -> Iterator[StreamDelta]:
        # Route once, then stream from the chosen deployment.
        model = request.model
        resolved = self._config.registry.resolve(model)
        entries = self._healthy_entries(resolved)
        if not entries:
            raise NoHealthyDeploymentError(f"no healthy deployment for {resolved!r}")

        picked = (
            self._config.router.pick(entries) if self._config.router else entries[0]
        )
        if picked is None:
            raise NoHealthyDeploymentError(f"no deployment for {resolved!r}")

        cb = self._config.circuit_breaker
        if cb is not None and cb.is_open(picked):
            raise NoHealthyDeploymentError(f"circuit open: {picked.name}")

        bundle = self._config.providers.get(picked.provider)
        if bundle is None:
            raise GatewayError(f"no provider bundle for {picked.provider!r}")

        try:
            it = provider_stream(
                self._to_chat_request(request, picked.model, stream=True),
                provider=bundle.provider,
                transport=bundle.transport,
                api_key=bundle.api_key,
            )
        except Exception as exc:
            if cb is not None:
                cb.record_failure(picked)
            cooldown = self._config.cooldown
            if cooldown is not None:
                cooldown.cool(picked)
            raise GatewayError(str(exc)) from exc

        if cb is not None:
            cb.record_success(picked)

        def _wrapped() -> Iterator[StreamDelta]:
            try:
                yield from it
            except Exception as exc:
                if cb is not None:
                    cb.record_failure(picked)
                cooldown = self._config.cooldown
                if cooldown is not None:
                    cooldown.cool(picked)
                raise GatewayError(str(exc)) from exc

        return _wrapped()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _healthy_entries(self, model: str) -> list[ProviderEntry]:
        entries = list(self._config.registry.entries_for(model))
        health = self._config.health_check
        cooldown = self._config.cooldown
        cb = self._config.circuit_breaker
        out: list[ProviderEntry] = []
        for e in entries:
            if health is not None and not health.is_healthy(e):
                continue
            if cooldown is not None and cooldown.is_cooled(e):
                continue
            if cb is not None and cb.is_open(e):
                continue
            out.append(e)
        return out

    def _build_chain(self, model: str) -> list[str]:
        chain = [model]
        for fb in self._config.fallbacks.get(model, ()):
            if fb not in chain:
                chain.append(fb)
        return chain

    def _to_chat_request(
        self, request: GatewayRequest, model: str, *, stream: bool = False
    ) -> ChatRequest:
        return ChatRequest(
            model=model,
            messages=request.messages,
            system=request.system,
            tools=list(request.tools),
            stream=stream or request.stream,
            extra=dict(request.params),
        )
