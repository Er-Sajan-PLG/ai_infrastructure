# Provenance

- **Kind**: original
- **Based on**: None — independent implementation
- **License**: Apache-2.0
- **Notes**: Inspired-by (not derived-from) the router design in LiteLLM (routing
  strategies, cooldown, weighted failover, model-group aliasing) and the provider
  registry shape in Portkey. No code was executed or reused. The `Gateway`
  protocol, `ProviderEntry`, `ProviderRegistry`, `Router`, `CooldownTracker`,
  `CostTracker`, and `DefaultGateway` are an independent design per ADR-0039.
  Composes `model-provider-abstraction` (ADR-0007) through its public interface.
