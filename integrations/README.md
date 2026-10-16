# Integrations

Compositions of catalog components into working systems (charter §17, §31). An integration demonstrates that independent capabilities compose — it is not a framework and must not become one.

## Rules

- Integrations **consume** catalog components through their public interfaces; they do not patch or fork them.
- Every integration states which catalog entries it uses and at which taxonomy status, so a reader can see what it actually proves.
- Demonstrating composition requires running it: each integration carries its own tests and a documented command to reproduce.
- Prefer integration examples mirroring the [Phase 4 plan](../docs/phases/phase-4-compose.md)'s System A / B / C sketches: partial adoption, mixed external + internal components, and fully internal.

## Status

**5 integrations.** Phase 1's exit criterion — *"at least one end-to-end
composition: model + tools + agent loop, demonstrated in `integrations/`"* — is
met. Phase 4's Systems A, B and C are all present.

| Integration | Composes | Proves |
|---|---|---|
| [`agent_loop_end_to_end`](agent_loop_end_to_end/) | `tool-registry` + `model-provider-abstraction` + `react-agent-loop`, all `TESTED` | The three capabilities compose into a working system, and the composition is verified by 25 tests with no network. It found a real defect on the seam that neither capability's own suite could see. |
| [`llm_http_transport`](llm_http_transport/) | `model-provider-abstraction` (`TESTED`) | The missing stdlib transport implementation and basic live-call path are provided without new dependencies. Offline tests verify local mapping and composition only; live vendor verification is deferred. See [ADR-0028](../docs/decisions/0028-llm-http-transport.md). |
| [`system_a_partial`](system_a_partial/) | `react-agent-loop` + `vector-memory-store`, both `TESTED` | Phase 4 System A — partial adoption. Our runtime + our memory compose with external provider and external embedder (doubles), verified by 15 tests with no network. |
| [`system_b_mixed`](system_b_mixed/) | external runtime (double) + `execution-trace-recorder` (`TESTED`) + `mcp-client` approval seam + our evaluation scoring | Phase 4 System B — mixed. An external runtime is wrapped by our observability, safety and evaluation, verified by 13 tests with no network. |
| [`system_c_internal`](system_c_internal/) | `tool-registry` + `model-provider-abstraction` + `react-agent-loop`, all `TESTED` | Phase 4 System C — entirely composed from `ai_infrastructure`. Three capabilities compose into a working system, verified by 12 tests with no network. |

Every integration carries its own tests and a reproduce command; see each
integration's `README.md` for the pipeline diagram and honest limits.