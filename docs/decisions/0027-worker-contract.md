# ADR-0027 — Worker Contract: Explicit Interface for Agent Execution

- **Status:** Accepted
- **Date:** 2026-09-21
- **Supersedes:** —
- **Superseded by:** —

## Context

The 18-repository study revealed that repositories with explicit worker/agent
contracts are more testable, composable, and debuggable. Our projects have
implicit contracts (brain → adapters, brain → tools) that are not documented
as interfaces.

Currently:
- **JARVIS**: `app.brain` → `app.adapters` → external execution. Contract is implicit.
- **PROFESSOR-J**: `app.brain` → `app.tools` → sandbox. Contract is implicit.
- **STEMMA**: No workers (content is static). N/A.
- **LearningHub**: Planned (Phase 9) but no contract defined yet.

### Source evidence

Two independent repositories demonstrate explicit worker contracts:

1. **SWE-agent** (`sweagent/types.py` + `sweagent/agent/agents.py`):
   `AbstractAgent` interface with `DefaultAgent` implementation.
   `StepOutput` defines what each step produces. `Trajectory = list[TrajectoryStep]`
   defines what the agent produces. `AgentInfo` defines run-level metadata.
   Hooks (`AbstractAgentHook`) provide lifecycle interception without coupling.

2. **Semantic Kernel** (`dotnet/src/Agents/Abstractions/`): Agent abstractions
   with `Plugins/`, `Connectors/`, and `AI services` as explicit contracts.
   Cross-language (Python + .NET + Java) with shared conceptual model.

### The problem this solves

Without explicit worker contracts:

- Cannot test orchestration without running actual workers
- Cannot swap worker implementations (e.g., local → remote)
- Cannot enforce isolation (workers can import anything)
- Cannot compose workers into multi-agent workflows

### What it is NOT

This is NOT:
- **ACP (Agent Client Protocol)** — that is the transport layer
- **MCP (Model Context Protocol)** — that is the capability protocol
- **LangGraph graphs** — that is the orchestration engine
- **Module boundaries** (already enforced) — those are static; contracts are runtime

Contract = what a worker promises to accept and produce.
Transport = how messages reach the worker.
Orchestration = how workers are composed.

## Decision

Define explicit worker contracts for JARVIS and PROFESSOR-J. The contract
specifies inputs, outputs, lifecycle, and error semantics.

### Worker contract

```python
@dataclass
class WorkerTask:
    """What the worker is asked to do."""
    task_id: str
    action: str
    parameters: dict
    context: dict          # Previous evidence, session state
    evidence_chain: list   # For traceability

@dataclass
class WorkerResult:
    """What the worker produces."""
    task_id: str
    status: str            # "completed", "failed", "needs_review"
    output: Any            # The actual result
    evidence: ExecutionStep  # Evidence of what happened (ADR-0025)
    confidence: float      # Worker confidence in result
    error: Optional[WorkerError]

@dataclass
class ExecutionStep:
    """One step in the worker's execution."""
    thought: str
    action: str
    output: str
    observation: str
    tool_calls: list
    state: dict
    timestamp: datetime

class Worker(Protocol):
    async def execute(self, task: WorkerTask) -> WorkerResult: ...
    async def health_check(self) -> WorkerHealth: ...
```

### Project mapping

| Project | Worker | Contract applies |
|---------|--------|------------------|
| JARVIS | `app.brain` → `app.adapters` | Yes — brain is a worker |
| PROFESSOR-J | `app.brain` → `app/tools/` | Yes — brain is a worker |
| STEMMA | N/A | No workers (content is static) |
| LearningHub | Planned Phase 9 | Yes — future workers need contracts |

### Integration with evidence and evaluator ADRs

- Worker result includes `evidence: ExecutionStep` (ADR-0025)
- Worker result includes `confidence: float` for evaluator input (ADR-0026)
- Worker contract is consumed by orchestration (LangGraph for PROFESSOR-J, n8n for JARVIS)

## Consequences

### Positive
- Workers can be tested in isolation (mock the contract)
- Workers can be swapped (local → remote, different implementations)
- Multi-agent workflows are explicit (contract → composition)
- Evidence and evaluation attach to contract boundaries

### Negative
- Contract maintenance (schema evolution, versioning)
- Overhead for small tasks (not every task needs full contract)
- Initial refactoring cost (extract implicit contract → explicit)

### Neutral
- Contract can be versioned independently of implementation
- Transport (ACP, HTTP, direct call) is separate concern
- Orchestration engine (LangGraph, n8n) consumes contract

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| Use only ACP | ACP is transport; we need execution semantics too |
| Use only LangGraph nodes | LangGraph is orchestration; we need worker-level contract |
| Implicit contracts (current) | Untestable, uncomposeable, undocumented |
| Semantic Kernel model | Too heavyweight; we need a lightweight Python contract |

## References

- SWE-agent: `sweagent/types.py` (StepOutput, Trajectory, AgentInfo)
- SWE-agent: `sweagent/agent/hooks/abstract.py` (AbstractAgentHook lifecycle)
- Semantic Kernel: `dotnet/src/Agents/Abstractions/` (cross-language contracts)
- MCP SDK: `src/mcp/` (capability protocol, separate from execution contract)
