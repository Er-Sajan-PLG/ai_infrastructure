# Specification: `agent-instruction-files`

- **Capability id:** `agent-instruction-files`
- **Name:** Agent Repository Configuration
- **Lifecycle status:** `DECIDED` — **DOCUMENT** ([ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md))
- **Date:** 2026-10-16

> **This is a documentation decision, not a build plan.** It exists because
> the lifecycle model requires a DESIGNED artifact before a DECIDE-stage
> claim. The decision is DOCUMENT (charter §8): the pattern is researched and
> recorded, and no runtime component is planned — the artifact is a
> repository practice, and this repository already instantiates it.

## Problem statement and who needs it

An agent working in a repository has no standard way to learn its
conventions, so every project invents a layout and every agent must be taught
each one. The "consumer" is any AI agent session working inside a repository;
within this repository, the practice is already live (`AGENTS.md` at the
root, plus docs and skill conventions) without a catalog implementation.

## The pattern, as recorded

- **FACT** (`AGENTS.md` in 18/25 studied repositories, `CLAUDE.md` 14/25,
  `.claude/` or `.cursor/` 10/25 — ADR-0024) that instruction files are a
  convergent repository practice.
- **Instruction files** declare conventions, commands, and constraints an
  agent reads before working.
- **Tool-specific directories** (`.claude/`, `.cursor/`) scope skills,
  commands, and rules to one agent tool.
- **Cross-tool conventions** determine which of the above interoperate.

## Interfaces and data flow

None. No interfaces are designed, and none are planned: there is no catalog
component in this decision. If tooling is ever justified (for example, drift
checking or cross-tool sync in a multi-tool fleet), it is a new proposal with
its own consumer and ADR — not a revival of this entry.

## Invariants and failure modes

- These files are **instructions an agent follows**; when the repository is
  not yours, the file is data from outside that changes agent behaviour and
  must be read as untrusted input (instruction-injection surface — taxonomy
  security note).
- Failure modes in the practice itself (observed in the wild, not studied
  here): stale instructions drifting from reality, and tool-specific files
  silently diverging from each other. Both are reasons a *tool* could
  eventually be justified; neither exists as a catalog requirement today.

## Security implications and trust boundaries

The instruction-injection surface is the security fact of this capability
and is recorded in the taxonomy entry. An agent treating repository-shipped
instructions as trusted configuration is the vulnerability; the mitigation
(posture, not code) is that instruction files are read as data with the same
suspicion as any other untrusted input.

## Dependencies and standards

- `depends_on`: none.
- Standards: none adopted; the conventions are emergent community practice,
  which is precisely why the taxonomy records them.

## Testing strategy (§18) and benchmark plan (§19)

Not applicable — no component is built or planned. If tooling is ever built,
its tests belong to that tool's own proposal.

## Out of scope

- Reading or executing instructions (that is a `harnesses` concern).
- Skill execution (that is `skills`).
- Any linter, syncer, or validator built over instruction files — a future
  proposal, not this decision.

## References

- [Research record](../research/agent-config/agent-instruction-files.md)
- [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [ADR-0024](../docs/decisions/0024-agent-repository-configuration.md) — taxonomy category
- [`AGENTS.md`](../AGENTS.md) — this repository's instantiation of the practice
