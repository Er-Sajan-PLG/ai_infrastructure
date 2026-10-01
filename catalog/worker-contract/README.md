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

## Open Invariants — UNDECIDED

The following invariants MUST be decided before any implementation is built.
Each is marked **UNDECIDED** to prevent premature defaults from locking in
behavior.

| Invariant | Decision | Rationale / Evidence Needed |
|-----------|----------|----------------------------|
| **Synchronous vs asynchronous execution model** | UNDECIDED | Do workers execute synchronously or via async protocols? Evidence: SWE-agent uses async; Semantic Kernel uses both. |
| **Cancellation semantics and timeout ownership** | UNDECIDED | Who owns cancellation — worker or orchestrator? How are timeouts propagated? |
| **Idempotency expectations** | UNDECIDED | At-least-once vs exactly-once semantics. Can a worker be safely retried? |
| **Retry ownership** | UNDECIDED | Worker retries internally vs orchestrator retries the whole worker. |
| **Identity and authorization context passing** | UNDECIDED | How are credentials, tenant IDs, and auth passed through the contract? |
| **Evidence emitted per worker invocation** | UNDECIDED | What evidence structure (ADR-0025) does a worker produce? Mandatory vs optional fields. |
| **Progress/status reporting protocol** | UNDECIDED | Streaming updates vs polling vs callbacks. Granularity of status events. |
| **Input/output serialization format** | UNDECIDED | JSON, msgpack, protobuf? Schema evolution strategy. |
| **Version compatibility and schema evolution** | UNDECIDED | How are contract versions negotiated? Breaking vs non-breaking changes. |
| **Partial failure and rollback behavior** | UNDECIDED | What happens when a multi-step worker fails halfway? Compensation actions? |

## references

- ADR-0027: Worker Contract
- SWE-agent `sweagent/types.py` — StepOutput, Trajectory, AgentInfo
- Semantic Kernel `dotnet/src/Agents/Abstractions/` — cross-language contracts
