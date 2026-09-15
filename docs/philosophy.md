# Design Philosophy

The operating attitude of this repository, distilled from the charter. When unsure how to act, read [`../CHARTER.md`](../CHARTER.md).

## Principles

1. **Capability-driven, not copy-driven** (§1). Existing projects are evidence, not blueprints.
2. **Evidence over hype** (§6). Every claim carries its class: FACT / OBSERVATION / INFERENCE / DESIGN OPINION / EXPERIMENTAL RESULT.
3. **Complexity earns its place** (§3). Every abstraction, dependency, and operational burden is justified against simpler alternatives.
4. **Independent but standards-compatible** (§9, §16). Own implementations behind interfaces that speak established protocols where useful.
5. **Honest status** (§4, §10). Research is not implementation; a wrapper is not a reimplementation; a prototype is not production.
6. **Composable by construction** (§17). Explicit interfaces, minimal coupling, dependency inversion; consumers pick components, not the monolith.
7. **Verifiable or unclaimed** (§18). No capability advances without tests; no performance claim without a recorded benchmark methodology (§19).
8. **Long-lived** (§23). The repository continuously re-researches, re-benchmarks, and deprecates. Nothing here is allowed to fossilize.

## Priority order for engineering trade-offs (§20)

correctness → security → simplicity → explicitness → modularity → composability → testability → observability → reproducibility → interoperability → maintainability → performance → extensibility.

Deviation is allowed — with a recorded rationale in an ADR.

## What "good" looks like

A new capability lands as: honest taxonomy entry → research record → decision ADR → specification → small standalone implementation with tests and examples → benchmark where meaningful → updated registry/roadmap. Each artifact exists before the next is claimed.
