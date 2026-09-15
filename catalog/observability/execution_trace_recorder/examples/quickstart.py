#!/usr/bin/env python3
"""Runnable tour of ``execution_trace_recorder`` — no network, no model, no clock.

Why a scripted clock rather than the real one
---------------------------------------------
This example is meant to be run by a reader, and a reader should see *exact*
durations. With ``SystemClock`` every ``duration_ns`` would be a few thousand and
different on each run, which makes the output unreadable and the point invisible.

So the clock is a double, and that is also the honest demonstration of ADR-0010
D-4: the clock is injected, which is what makes timing testable at all.

Run it::

    .venv/bin/python catalog/observability/execution_trace_recorder/examples/quickstart.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# The catalog convention: a consumer adds catalog/<category>/ to sys.path and
# imports the package by name (see pyproject.toml's ruff notes).
_CATALOG = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_CATALOG / "observability"))

from execution_trace_recorder import (  # noqa: E402
    Bounds,
    CaptureEverything,
    CaptureNothing,
    TraceRecorder,
)


class ScriptedClock:
    """A clock that advances 10 ms on every reading.

    Two methods, because they answer different questions: ``now_ns`` is monotonic
    and measures durations, ``now_utc`` is wall-clock and is what a human reads.
    One method returning "the time" cannot do both correctly — a wall-clock
    adjustment can make a duration negative.
    """

    def __init__(self) -> None:
        self._ns = 0
        self._wall = 0

    def now_ns(self) -> int:
        value = self._ns
        self._ns += 10_000_000  # +10 ms
        return value

    def now_utc(self) -> str:
        self._wall += 1
        return f"2026-09-16T12:00:{self._wall:02d}+00:00"


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def read(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="trace-quickstart-"))
    path = tmp / "run.jsonl"

    # ------------------------------------------------------------------ #
    rule("1. A full trace, one JSONL line per record")

    with TraceRecorder(path, clock=ScriptedClock()) as recorder:
        trace_id = recorder.start_trace()
        with recorder.model_call(model="gpt-4o-mini") as call:
            call.succeed(input_tokens=12, output_tokens=8, usage_provided=True)
        with recorder.tool_call(name="add", arguments={"a": 2, "b": 3}) as tool:
            tool.succeed(result=5)
        recorder.end_trace(stop_reason="final_answer")

    records = read(path)
    print(f"file       : {path}")
    print(f"trace_id   : {trace_id}")
    print(f"records    : {len(records)}")
    for record in records:
        print(
            f"  {record['sequence']}  {record['kind']:<12} "
            f"outcome={record['outcome']:<8} "
            f"duration_ns={record['duration_ns']}"
        )

    print("\n  ^ every duration is an integer NAMED with its unit.")
    print("    Research 8 found six systems using at least four unit")
    print("    conventions, and MLflow disagreeing with itself within one")
    print("    object. There is no bare `latency` field anywhere here.")

    # ------------------------------------------------------------------ #
    rule("2. Flat records with parent pointers")

    root = records[0]
    print(f"root record_id : {root['record_id']}")
    print(f"root parent_id : {root['parent_id']}")
    for record in records[1:]:
        print(
            f"{record['kind']:<12} parent={str(record['parent_id'])[:12]}… "
            f"({'root' if record['parent_id'] == root['record_id'] else '?'})"
        )
    print("\n  ^ a nested tree cannot be appended to without rewriting the")
    print("    file. Flat records with a parent id can — and all six")
    print("    surveyed systems do it this way.")

    # ------------------------------------------------------------------ #
    rule("3. Content is OFF by default")

    off_path = tmp / "off.jsonl"
    with TraceRecorder(off_path, clock=ScriptedClock()) as recorder:
        recorder.start_trace()
        with recorder.tool_call(
            name="send_email", arguments={"to": "someone@example.com"}
        ) as tool:
            tool.succeed(result="sent")

    off_record = read(off_path)[1]
    print(f"content            : {off_record['content']}")
    print(f"contains the secret: {'someone@example.com' in json.dumps(off_record)}")
    print("\n  ^ None, not '__REDACTED__'. A redacted field and an absent")
    print("    one are different facts, and a sentinel would put a value")
    print("    where the honest answer is 'we did not look'.")

    # ------------------------------------------------------------------ #
    rule("4. Content capture is a named decision")

    on_path = tmp / "on.jsonl"
    with TraceRecorder(
        on_path, clock=ScriptedClock(), capture=CaptureEverything()
    ) as recorder:
        recorder.start_trace()
        with recorder.tool_call(name="add", arguments={"a": 2, "b": 3}) as tool:
            tool.succeed(result=5)

    on_record = read(on_path)[1]
    print(f"content: {on_record['content']}")
    print("\n  ^ a caller who passes CaptureEverything() is capturing PII")
    print("    when any is present. That is why the name is in the diff")
    print("    and not a boolean buried in a call site.")
    print(f"  default policy repr: {CaptureNothing()!r}")
    print(f"  opt-in policy repr : {CaptureEverything()!r}")

    # ------------------------------------------------------------------ #
    rule("5. A write failure does not kill the run, and does not vanish")

    class ExplodingSink:
        """Fails from the second write onward, like a full disk."""

        def __init__(self) -> None:
            self.calls = 0
            self.written: list[str] = []

        def write(self, text: str) -> int:
            self.calls += 1
            if self.calls >= 2:
                raise OSError("No space left on device")
            self.written.append(text)
            return len(text)

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    exploding = ExplodingSink()
    with TraceRecorder(exploding, clock=ScriptedClock()) as recorder:
        recorder.start_trace()
        with recorder.tool_call(name="add") as tool:  # must NOT raise
            tool.succeed()
        with recorder.tool_call(name="add") as tool:
            tool.succeed()

    print(f"records written : {recorder.records_written}")
    print(f"write failures  : {recorder.write_failures}")
    print("\n  ^ the run continued. A recorder that raised here would have")
    print("    killed the run it was observing; one that swallowed the")
    print("    error would have lost the evidence silently. The loss is")
    print("    counted and inspectable instead.")

    # ------------------------------------------------------------------ #
    rule("6. Bounded: nothing unbounded is ever written")

    bounded_path = tmp / "bounded.jsonl"
    with TraceRecorder(
        bounded_path,
        clock=ScriptedClock(),
        bounds=Bounds(max_error_message_chars=40, max_records=2),
    ) as recorder:
        recorder.start_trace()
        with recorder.tool_call(name="t") as tool:
            tool.fail(message="x" * 2000)
        with recorder.tool_call(name="dropped") as tool:
            tool.succeed()

    bounded = read(bounded_path)
    print(f"error_message   : {bounded[1]['error_message']}")
    print(f"truncated       : {bounded[1]['truncated']}")
    print(f"records dropped : {recorder.records_dropped}")
    print("\n  ^ a truncated field is NAMED, so a reader never has to guess")
    print("    whether a value is whole. And a bounded trace of an")
    print("    unbounded run says by how much it is incomplete.")

    # ------------------------------------------------------------------ #
    rule("7. A tool call and its result are ONE record")

    print("kinds present in the first trace:")
    for record in records:
        print(f"  {record['kind']}")
    print("\n  ^ there is no 'tool_result' kind. OTel puts the result as an")
    print("    attribute on the same span; OpenInference and MLflow carry")
    print("    tool_call.id alongside. None of the six surveyed systems")
    print("    splits them, and splitting would force a join to answer")
    print("    'did this call succeed?'")

    rule(f"Done — no network, no model, no real clock. Trace in {tmp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
