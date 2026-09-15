# Architecture Decision Records

Records of significant decisions, per charter §12. Format defined by [ADR-0000](0000-adr-format.md).

| ADR | Title | Status |
|---|---|---|
| [0000](0000-adr-format.md) | ADR Format | Accepted |
| [0001](0001-bootstrap-structure.md) | Bootstrap the Repository as a Knowledge/Code Plane Split | Accepted |
| [0002](0002-license-selection.md) | License Selection (Apache-2.0) | Accepted |
| [0003](0003-toolchain-and-enforcement.md) | Toolchain, Enforcement, and the Drift Detector | Accepted |

## When an ADR is required

Charter §12 and §22: why implement or not; why this architecture; why this dependency or abstraction; why adopt or reject a protocol; why replace or deprecate; why change a trust boundary; any human-review gate item.

## Open items requiring human decision

- **Contribution policy.** Apache-2.0 is in place, but no CLA/DCO-with-relicense-grant has been adopted, so external contributions are not accepted ([ADR-0002](0002-license-selection.md), [`../CONTRIBUTING.md`](../../CONTRIBUTING.md)). Adopting one is required before external contributions can be taken.