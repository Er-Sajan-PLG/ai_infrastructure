# Integrations

Compositions of catalog components into working systems (charter §17, §31). An integration demonstrates that independent capabilities compose — it is not a framework and must not become one.

## Rules

- Integrations **consume** catalog components through their public interfaces; they do not patch or fork them.
- Every integration states which catalog entries it uses and at which taxonomy status, so a reader can see what it actually proves.
- Demonstrating composition requires running it: each integration carries its own tests and a documented command to reproduce.
- Prefer integration examples mirroring charter §31's System A / B / C sketches: partial adoption, mixed external + internal components, and fully internal.

## Status

**1 integration.** Phase 1's exit criterion — *"at least one end-to-end
composition: model + tools + agent loop, demonstrated in `integrations/`"* — is
met.

| Integration | Composes | Proves |
|---|---|---|
| [`agent_loop_end_to_end`](agent_loop_end_to_end/) | `tool-registry` + `model-provider-abstraction` + `react-agent-loop`, all `TESTED` | The three capabilities compose into a working system, and the composition is verified by 25 tests with no network. It found a real defect on the seam that neither capability's own suite could see. |

See [`agent_loop_end_to_end/README.md`](agent_loop_end_to_end/README.md).