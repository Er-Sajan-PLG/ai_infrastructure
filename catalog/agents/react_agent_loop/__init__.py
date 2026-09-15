"""ReAct Agent Loop -- a bounded dispatcher, not a reasoner.

The simplest agent control loop that grounds model output in tool interaction
with a clear termination condition. It composes tool-registry and
model-provider-abstraction through protocols it defines, so it runs against
scripted doubles with no network, no model and no registry.

    from react_agent_loop import Agent, run

    result = run(
        "What is 2 + 3?",
        agent=Agent(model="gpt-4o-mini"),
        model_caller=my_caller,
        dispatcher=my_dispatcher,
    )
    if result.ok:
        print(result.final_text)
    else:
        print(f"stopped: {result.reason.value}")

See specifications/react-agent-loop.md for the design and
docs/decisions/0008-react-agent-loop.md for the decision.

What it does not do: it does not parse text for actions (D-8), retry a failed
tool (retry belongs to the caller, ADR-0007 D-4), plan, remember across runs, or
run anything concurrently. It also does not prevent a tool result from
persuading the model, only from forging an action.
"""

from __future__ import annotations

from .adapters import ProviderCaller, RegistryDispatcher
from .errors import UnactionableToolError
from .loop import (
    DEFAULT_MAX_OBSERVATION_CHARS,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_TOTAL_OBSERVATION_CHARS,
    DEFAULT_REPEAT_LIMIT,
    Agent,
    AgentResult,
    DispatchRecord,
    Step,
    StopReason,
    run,
)
from .observations import TOTAL_BUDGET_MARKER, bound_observation
from .protocols import DispatchOutcome, ModelCaller, ToolDispatcher
from .repetition import CallSignature, RepetitionTracker, canonical_arguments

__all__ = [
    "DEFAULT_MAX_OBSERVATION_CHARS",
    "DEFAULT_MAX_STEPS",
    "DEFAULT_MAX_TOTAL_OBSERVATION_CHARS",
    "DEFAULT_REPEAT_LIMIT",
    "TOTAL_BUDGET_MARKER",
    "Agent",
    "AgentResult",
    "CallSignature",
    "DispatchOutcome",
    "DispatchRecord",
    "ModelCaller",
    "ProviderCaller",
    "RegistryDispatcher",
    "RepetitionTracker",
    "Step",
    "StopReason",
    "ToolDispatcher",
    "UnactionableToolError",
    "bound_observation",
    "canonical_arguments",
    "run",
]
