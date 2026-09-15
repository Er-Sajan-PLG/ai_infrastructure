"""Execution Trace Recorder.

Persist what an agent run did, as flat JSONL records another person can read and
a machine can aggregate — without holding anything sensitive by default.

Zero runtime dependencies; standard library only::

    from execution_trace_recorder import CaptureEverything, TraceRecorder

    with TraceRecorder("run.jsonl") as recorder:
        recorder.start_trace()
        with recorder.model_call(model="gpt-4o-mini") as call:
            call.succeed(input_tokens=12, output_tokens=8, usage_provided=True)
        with recorder.tool_call(name="add", arguments={"a": 1, "b": 2}) as call:
            call.succeed(result=3)
        recorder.end_trace(stop_reason="final_answer")

**Content capture is off by default.** Passing ``capture=CaptureEverything()``
records prompt text, completions and tool payloads; a caller who does that is
capturing PII when any is present, and the name is in the diff on purpose.

**No conformance to any standard is claimed.** The OTel GenAI conventions are
`Development`, have moved repositories, have no published schema URL, and have
already reversed one content-capture decision. ``specifications/`` §4 publishes a
correspondence table instead.

See ``specifications/execution-trace-recorder.md`` for the design and
``docs/decisions/0010-execution-trace-recorder.md`` for the decision.
"""

from __future__ import annotations

from .bounds import Bounds, json_safe, truncate
from .capture import CaptureEverything, CaptureNothing, CapturePolicy
from .clock import Clock, SystemClock
from .errors import TraceRecorderError, WriteFailures
from .recorder import ModelCallHandle, ToolCallHandle, TraceRecorder
from .records import Outcome, RecordKind, TraceRecord

__all__ = [
    "Bounds",
    "CaptureEverything",
    "CaptureNothing",
    "CapturePolicy",
    "Clock",
    "ModelCallHandle",
    "Outcome",
    "RecordKind",
    "SystemClock",
    "ToolCallHandle",
    "TraceRecord",
    "TraceRecorder",
    "TraceRecorderError",
    "WriteFailures",
    "json_safe",
    "truncate",
]
