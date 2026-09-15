# Integrations

Compositions of catalog components into working systems (charter §17, §31). An integration demonstrates that independent capabilities compose — it is not a framework and must not become one.

## Rules

- Integrations **consume** catalog components through their public interfaces; they do not patch or fork them.
- Every integration states which catalog entries it uses and at which taxonomy status, so a reader can see what it actually proves.
- Demonstrating composition requires running it: each integration carries its own tests and a documented command to reproduce.
- Prefer integration examples mirroring charter §31's System A / B / C sketches: partial adoption, mixed external + internal components, and fully internal.

## Status

Empty. No catalog entries exist yet, so there is nothing to compose. Expected first candidate: `tool-registry` + `model-provider-abstraction` + `react-agent-loop` (see [`../docs/roadmap.md`](../docs/roadmap.md)).