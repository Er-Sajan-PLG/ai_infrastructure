# Worker Execution Contracts

## what it is

Explicit interface defining what a worker accepts and produces. Specifies inputs,
outputs, lifecycle, and error semantics. Enables testing, swapping, and composing
worker implementations without coupling.

## why it exists

Without explicit worker contracts, orchestration is implicit and untestable,
workers cannot be swapped or isolated, and multi-agent workflows are fragile.
Needed for JARVIS multi-worker orchestration and PROFESSOR-J specialist delegation.

## status

Empty. First expected implementations: JARVIS `app.evidence/`, PROFESSOR-J worker interface.

## references

- ADR-0027: Worker Contract
- SWE-agent `sweagent/types.py` — StepOutput, Trajectory, AgentInfo
- Semantic Kernel `dotnet/src/Agents/Abstractions/` — cross-language contracts
