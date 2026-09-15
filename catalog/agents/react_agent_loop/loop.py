"""The bounded agent loop (ADR-0008).

A dispatcher with a bound, not a reasoner. Four properties are the decisions, not
implementation detail:

* Actions come from structured tool calls only (D-8). The loop never parses text
  for an action, so a tool result cannot forge one. It can still persuade the
  model; that is a model-alignment property this loop does not claim to solve.
* Termination is a returned reason, not an exception (D-2). The trace is the
  useful artefact when a loop runs out of budget.
* A dispatched result is always followed by a model call that can use it. The cap
  is checked before the model call and before dispatch, so max_steps=1 is exactly
  one model call and no dispatch.
* Provider and registry failures propagate. There is deliberately no StopReason
  for them (D-2 rule 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from model_provider import (
    ChatResponse,
    Message,
    Role,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    Usage,
)

from .errors import UnactionableToolError
from .observations import TOTAL_BUDGET_MARKER, bound_observation
from .protocols import DispatchOutcome, ModelCaller, ToolDispatcher
from .repetition import RepetitionTracker

__all__ = [
    "DEFAULT_MAX_OBSERVATION_CHARS",
    "DEFAULT_MAX_STEPS",
    "DEFAULT_MAX_TOTAL_OBSERVATION_CHARS",
    "DEFAULT_REPEAT_LIMIT",
    "Agent",
    "AgentResult",
    "DispatchRecord",
    "Step",
    "StopReason",
    "run",
]

DEFAULT_MAX_STEPS = 12
DEFAULT_REPEAT_LIMIT = 3
DEFAULT_MAX_OBSERVATION_CHARS = 8000
DEFAULT_MAX_TOTAL_OBSERVATION_CHARS = 400_000


class StopReason(Enum):
    """Why the loop stopped. A closed set of exactly three values (D-2)."""

    FINAL_ANSWER = "final_answer"
    STEP_LIMIT = "step_limit"
    REPEATED_ACTION = "repeated_action"


@dataclass(frozen=True, slots=True)
class Agent:
    """What to call, and with which settings.

    The loop does not own the system prompt (D-7): system is stored and
    forwarded, never constructed or templated.
    """

    model: str
    system: str | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class DispatchRecord:
    """What happened to one tool call.

    Records both the original and the kept length when an observation was
    bounded, so a caller can see the loss rather than infer it.
    """

    tool_call_id: str
    tool_name: str
    ok: bool
    kind: str
    observation_chars: int
    original_chars: int
    omitted: bool = False

    @property
    def truncated(self) -> bool:
        """Whether the observation was cut, by bounding or by the total budget."""
        return self.omitted or self.original_chars > self.observation_chars


@dataclass(frozen=True, slots=True)
class Step:
    """One model call and the dispatches it caused."""

    index: int
    text: str
    tool_calls: tuple[ToolCallBlock, ...]
    dispatches: tuple[DispatchRecord, ...]


@dataclass(frozen=True, slots=True)
class AgentResult:
    """The outcome of a run, including why it stopped."""

    reason: StopReason
    final_text: str
    steps: tuple[Step, ...]
    usage: Usage | None
    messages: tuple[Message, ...]
    repeated_call: str | None = None
    """The name(args) form of a repeated call, when reason is REPEATED_ACTION."""

    @property
    def ok(self) -> bool:
        """Whether the run produced an answer."""
        return self.reason is StopReason.FINAL_ANSWER


def _merge_usage(current: Usage | None, new: Usage | None) -> Usage | None:
    """Add two usage records, treating a missing field as unknown.

    A field absent on every call stays None rather than becoming 0: zero is a
    measurement and None is the absence of one, and conflating them corrupts cost
    accounting silently (ADR-0007 D-5).
    """
    if new is None:
        return current

    # Derive each call's total *before* summing. A provider that reports input
    # and output but no total (Anthropic does exactly this) has a derivable
    # total, and summing a derived total against a raw ``None`` would silently
    # lose that call's contribution: 12 + None must be 12 + 8, not 12 + 0.
    new = new.derive_total()
    if current is None:
        return new
    current = current.derive_total()

    def add(a: int | None, b: int | None) -> int | None:
        # A field absent on *both* sides stays None rather than becoming 0:
        # zero is a measurement and None is the absence of one (ADR-0007 D-5).
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    return Usage(
        input_tokens=add(current.input_tokens, new.input_tokens),
        output_tokens=add(current.output_tokens, new.output_tokens),
        total_tokens=add(current.total_tokens, new.total_tokens),
        reasoning_tokens=add(current.reasoning_tokens, new.reasoning_tokens),
        cache_read_tokens=add(current.cache_read_tokens, new.cache_read_tokens),
        cache_write_tokens=add(current.cache_write_tokens, new.cache_write_tokens),
    ).derive_total()


def run(
    task: str,
    *,
    agent: Agent,
    model_caller: ModelCaller,
    dispatcher: ToolDispatcher,
    max_steps: int = DEFAULT_MAX_STEPS,
    repeat_limit: int | None = DEFAULT_REPEAT_LIMIT,
    max_observation_chars: int = DEFAULT_MAX_OBSERVATION_CHARS,
    max_total_observation_chars: int | None = DEFAULT_MAX_TOTAL_OBSERVATION_CHARS,
) -> AgentResult:
    """Run a bounded agent loop until it stops, and report why.

    Args:
        task: The user's request, as the first user message.
        agent: Model and settings.
        model_caller: Makes model calls. Injected (D-1).
        dispatcher: Advertises and invokes tools. Injected (D-1).
        max_steps: Maximum model calls. max_steps=1 means exactly one call and
            no tool dispatch.
        repeat_limit: Consecutive identical calls that stop the run. None
            disables detection.
        max_observation_chars: Per-observation bound, head-and-tail.
        max_total_observation_chars: Run-wide bound on kept observation
            characters. None disables it. When exhausted the loop continues,
            substituting a marker: one verbose tool must not be able to end a run
            the model could finish.

    Returns:
        An AgentResult. Exhaustion is a result, not an exception.

    Raises:
        ValueError: For an out-of-range bound, rejected loudly at the boundary.
        UnactionableToolError: A tool failed in a way the model cannot act on.
        ProviderError: From the model caller. Propagates (D-2 rule 4).
        ToolRegistryError: From the dispatcher, for a broken registry.
    """
    if max_steps < 1:
        raise ValueError(f"max_steps must be at least 1, got {max_steps}")
    if max_observation_chars < 1:
        raise ValueError(
            f"max_observation_chars must be positive, got {max_observation_chars}"
        )
    if max_total_observation_chars is not None and max_total_observation_chars < 1:
        raise ValueError(
            "max_total_observation_chars must be positive or None, got "
            f"{max_total_observation_chars}"
        )

    # Built here so an invalid repeat_limit fails before any model call is made.
    tracker = RepetitionTracker(repeat_limit)

    tools = tuple(dispatcher.schemas())
    messages: list[Message] = [Message(Role.USER, (TextBlock(text=task),))]
    steps: list[Step] = []
    usage: Usage | None = None
    spent = 0
    calls_made = 0

    while True:
        if calls_made >= max_steps:
            return _finish(StopReason.STEP_LIMIT, "", steps, usage, messages)

        calls_made += 1
        response: ChatResponse = model_caller.call(
            messages, system=agent.system, tools=tools
        )
        usage = _merge_usage(usage, response.usage)

        # Append the assistant turn before dispatching, so the tool results that
        # follow correlate against the calls that produced them. Providers reject
        # an unmatched tool call, and a trace missing the request is unreadable.
        messages.append(Message(Role.ASSISTANT, response.blocks))
        step_index = len(steps) + 1

        if not response.tool_calls:
            steps.append(
                Step(index=step_index, text=response.text, tool_calls=(), dispatches=())
            )
            return _finish(
                StopReason.FINAL_ANSWER, response.text, steps, usage, messages
            )

        # Repetition is checked before dispatch (D-5): the brake exists to avoid
        # the work, not to perform it once more and notice.
        for call in response.tool_calls:
            if tracker.record(call):
                steps.append(
                    Step(
                        index=step_index,
                        text=response.text,
                        tool_calls=response.tool_calls,
                        dispatches=(),
                    )
                )
                tripped = tracker.tripped
                return _finish(
                    StopReason.REPEATED_ACTION,
                    "",
                    steps,
                    usage,
                    messages,
                    repeated_call=tripped.render() if tripped else call.name,
                )

        # No budget left to use results the model would never see.
        if calls_made >= max_steps:
            steps.append(
                Step(
                    index=step_index,
                    text=response.text,
                    tool_calls=response.tool_calls,
                    dispatches=(),
                )
            )
            return _finish(StopReason.STEP_LIMIT, "", steps, usage, messages)

        records: list[DispatchRecord] = []

        for call in response.tool_calls:
            outcome: DispatchOutcome = dispatcher.dispatch(call)

            if not outcome.ok and not outcome.model_visible:
                # D-9. The model cannot act on this, so feeding it back invites
                # another hallucination of the same name. Raised, not returned:
                # the stop-reason set is closed at three (D-2), and this is a
                # caller/harness bug rather than a loop outcome. The trace travels
                # with the exception so the evidence is not discarded.
                records.append(
                    DispatchRecord(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        ok=False,
                        kind=outcome.kind,
                        observation_chars=0,
                        original_chars=0,
                    )
                )
                steps.append(
                    Step(
                        index=step_index,
                        text=response.text,
                        tool_calls=response.tool_calls,
                        dispatches=tuple(records),
                    )
                )
                raise UnactionableToolError(
                    tool_id=outcome.tool_id,
                    kind=outcome.kind,
                    message=(
                        f"tool {outcome.tool_id!r} failed with kind "
                        f"{outcome.kind!r}, which the model cannot act on"
                    ),
                    steps=tuple(steps),
                    messages=tuple(messages),
                )

            raw = outcome.text or ""
            bounded, original = bound_observation(raw, max_observation_chars)

            omitted = False
            if (
                max_total_observation_chars is not None
                and spent + len(bounded) > max_total_observation_chars
            ):
                bounded = TOTAL_BUDGET_MARKER
                omitted = True
            spent += len(bounded)

            records.append(
                DispatchRecord(
                    tool_call_id=call.id,
                    tool_name=call.name,
                    ok=outcome.ok,
                    kind=outcome.kind,
                    observation_chars=len(bounded),
                    original_chars=original,
                    omitted=omitted,
                )
            )
            messages.append(
                Message(
                    Role.TOOL,
                    (ToolResultBlock(tool_call_id=call.id, content=bounded),),
                )
            )

        steps.append(
            Step(
                index=step_index,
                text=response.text,
                tool_calls=response.tool_calls,
                dispatches=tuple(records),
            )
        )


def _finish(
    reason: StopReason,
    final_text: str,
    steps: list[Step],
    usage: Usage | None,
    messages: list[Message],
    *,
    repeated_call: str | None = None,
) -> AgentResult:
    """Assemble the result, freezing the mutable accumulators."""
    return AgentResult(
        reason=reason,
        final_text=final_text,
        steps=tuple(steps),
        usage=usage,
        messages=tuple(messages),
        repeated_call=repeated_call,
    )
