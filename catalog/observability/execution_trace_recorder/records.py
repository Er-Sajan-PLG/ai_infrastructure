"""The record types: four kinds, flat, and bounded.

ADR-0010 D-1 picks the **noun** axis. Research §4 is the evidence: OTel uses an
operation *verb* (`execute_tool`, `chat` — 18 values, no node type at all) while
the other five surveyed systems use a kind *noun*. A noun reads correctly in a
JSONL field, where a bare verb describes an action but not a record.

ADR-0010 D-5 is the field naming rule, and research §8 is why: six systems, at
least four unit conventions, and MLflow disagrees with *itself* within one object.
Every duration here is an integer named with its unit. There is no bare
``latency: float`` anywhere, because ``duration_ns`` cannot be misread as seconds.

**No conformance to any standard is claimed.** Research §2.1 is the reason: the
OTel GenAI conventions are `Development`, have moved repositories, have no
published schema URL, and have already reversed one content-capture decision.
``specifications/execution-trace-recorder.md`` §4 publishes the correspondence
table instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

__all__ = ["Outcome", "RecordKind", "TraceRecord"]


class RecordKind(StrEnum):
    """What a record is. A closed enum of four.

    Closed rather than open deliberately: MLflow keeps its taxonomy open —
    *"Not using enum as we want to allow custom span type string"* — and that
    costs the ability to validate. Four values are checkable.

    There is no ``AGENT`` kind. Research §4: LangSmith, a product whose whole
    subject is agent tracing, has no ``agent`` run type either.
    """

    TRACE_START = "trace_start"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    TRACE_END = "trace_end"


class Outcome(StrEnum):
    """How a record ended.

    ``UNKNOWN`` is a real value, not a placeholder: a tool call whose context
    manager exited without ``succeed()`` or ``fail()`` is recorded as unknown
    rather than omitted, because a missing record is indistinguishable from a
    call that never happened.
    """

    OK = "ok"
    ERROR = "error"
    DENIED = "denied"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TraceRecord:
    """One line of a trace.

    Flat, with a ``parent_id`` pointer — ADR-0010 D-7. Research §7 found this
    unanimous across all six surveyed systems: none stores a nested tree, and a
    nested tree cannot be appended to without rewriting the file.

    Attributes:
        trace_id: Identifies the whole run.
        record_id: Unique within the trace.
        parent_id: The enclosing record's id, or ``None`` for the root.
        kind: What this record is.
        sequence: Execution order within the trace, strictly increasing. Lets a
            reader recover order without parsing timestamps.
        started_at_ns: Monotonic start, in nanoseconds.
        ended_at_ns: Monotonic end, or ``None`` when the record never finished.
            A crashed or killed step is exactly this, and it is the most
            interesting failure to be able to represent.
        duration_ns: ``ended - started``, or ``None``. **Never ``0`` for an
            unknown duration** — an instantaneous call and an unknown one are
            different facts.
        timestamp_utc: Wall-clock ISO 8601, for a human reader.
        outcome: How it ended.
        model: The model name, for ``MODEL_CALL``.
        tool_name: The tool name, for ``TOOL_CALL``.
        stop_reason: Why the run ended, for ``TRACE_END``. **None of the six
            surveyed systems has this field** (research §9.8) and it is arguably
            the most valuable one in a trace.
        input_tokens: Prompt tokens, when known.
        output_tokens: Completion tokens, when known.
        usage_provided: ``True`` when the provider reported the token counts.
            ADR-0010 D-6, adopted from Langfuse's ``providedUsageDetails`` vs
            ``usageDetails`` split. ``None`` tokens with ``usage_provided=False``
            is an honest "not reported"; ``0`` would be a lie.
        error_type: The exception class name, when one was raised.
        error_message: A bounded, sanitised message.
        content: Model text or tool payloads — ``None`` unless capture is on.
        truncated: Names of the fields that were cut by a bound.
    """

    trace_id: str
    record_id: str
    parent_id: str | None
    kind: RecordKind
    sequence: int
    started_at_ns: int
    ended_at_ns: int | None
    duration_ns: int | None
    timestamp_utc: str
    outcome: Outcome
    model: str | None = None
    tool_name: str | None = None
    stop_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    usage_provided: bool = False
    error_type: str | None = None
    error_message: str | None = None
    content: Mapping[str, Any] | None = None
    truncated: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        """Render for a JSONL line.

        Every field is emitted, including the ``None`` ones. An explicit JSON
        ``null`` says "this was not reported"; an omitted key says "this build
        does not have that field", and a reader cannot tell those apart. The
        cost is a longer line, and the line is bounded anyway.
        """
        return {
            "trace_id": self.trace_id,
            "record_id": self.record_id,
            "parent_id": self.parent_id,
            "kind": str(self.kind),
            "sequence": self.sequence,
            "started_at_ns": self.started_at_ns,
            "ended_at_ns": self.ended_at_ns,
            "duration_ns": self.duration_ns,
            "timestamp_utc": self.timestamp_utc,
            "outcome": str(self.outcome),
            "model": self.model,
            "tool_name": self.tool_name,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usage_provided": self.usage_provided,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "content": dict(self.content) if self.content is not None else None,
            "truncated": list(self.truncated),
        }
