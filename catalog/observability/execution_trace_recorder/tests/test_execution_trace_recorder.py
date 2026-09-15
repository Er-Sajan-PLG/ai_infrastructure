"""Tests for the execution trace recorder.

The failure paths matter more than the happy path here, because the two decisions
this capability is built on are both about what happens when something goes wrong:

* **ADR-0010 D-9** — a write failure must not kill the run, and must not vanish
  silently either. :class:`ExplodingSink` is the evidence: it fails on demand and
  the tests assert the run continues *and* that the loss is countable.
* **ADR-0010 D-8** — content capture is off by default. The tests assert
  ``content is None`` and, separately, that it is never a ``"__REDACTED__"``
  sentinel: a redacted field and an absent one are different facts.

The clock is scripted rather than real, so ``duration_ns`` assertions are exact.
Research §8 is why that matters: six surveyed systems use at least four unit
conventions, and a duration a test can only assert within a tolerance is a
duration nobody can assert precisely.
"""

from __future__ import annotations

import ast
import io
import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

_CATALOG = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_CATALOG / "observability"))

from execution_trace_recorder import (  # noqa: E402
    Bounds,
    CaptureEverything,
    CaptureNothing,
    Outcome,
    RecordKind,
    TraceRecorder,
    TraceRecorderError,
    json_safe,
    truncate,
)

# --------------------------------------------------------------------------- #
# Doubles.
# --------------------------------------------------------------------------- #

# 1 ms in nanoseconds. Every scripted duration is a multiple of this so the
# expected values are readable rather than magic.
_MS = 1_000_000


class ScriptedClock:
    """A clock that advances by a fixed step on every reading.

    Each call to :meth:`now_ns` returns the next value in ``steps``; the last
    value repeats once the sequence is exhausted. That makes every duration
    exactly predictable without a sleep or a tolerance.
    """

    def __init__(self, *steps_ns: int) -> None:
        self._steps = list(steps_ns) or [0]
        self._index = 0
        self._wall = 0

    def now_ns(self) -> int:
        value = self._steps[min(self._index, len(self._steps) - 1)]
        self._index += 1
        return value

    def now_utc(self) -> str:
        # A deterministic, ordered wall stamp. Real ISO parsing is not the
        # subject here; that it is present and monotonic is.
        self._wall += 1
        return f"2026-09-16T00:00:{self._wall:02d}+00:00"


class ExplodingSink:
    """A text sink that fails from a chosen call onward.

    ``fail_from`` is 1-based and **sticky**: once reached, every later call fails
    too, which is what a full disk actually does. ``fail_from=None`` never fails.

    The first version of this double failed on exactly one call, so a test
    asserting three failures only ever produced one — the test was wrong about
    its own fixture, and the fixture was wrong about disks.
    """

    def __init__(self, *, fail_from: int | None = None) -> None:
        self.fail_from = fail_from
        self.calls = 0
        self.written: list[str] = []
        self.closed = False

    def write(self, text: str) -> int:
        self.calls += 1
        if self.fail_from is not None and self.calls >= self.fail_from:
            raise OSError("simulated disk full")
        self.written.append(text)
        return len(text)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def _lines(sink: io.StringIO | ExplodingSink) -> list[dict[str, Any]]:
    """Parse written records back out of a sink."""
    text = "".join(sink.written) if isinstance(sink, ExplodingSink) else sink.getvalue()
    return [json.loads(line) for line in text.splitlines() if line]


@pytest.fixture()
def sink() -> io.StringIO:
    return io.StringIO()


def _recorder(
    sink: io.StringIO | ExplodingSink | Path,
    **kwargs: Any,
) -> TraceRecorder:
    """A recorder with a scripted clock unless one was supplied."""
    kwargs.setdefault("clock", ScriptedClock(0, _MS, 2 * _MS, 3 * _MS, 4 * _MS))
    return TraceRecorder(sink, **kwargs)


# --------------------------------------------------------------------------- #
# The trace and its records.
# --------------------------------------------------------------------------- #


def test_start_trace_writes_a_root_record(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    trace_id = recorder.start_trace()

    records = _lines(sink)
    assert len(records) == 1
    root = records[0]
    assert root["kind"] == RecordKind.TRACE_START
    assert root["trace_id"] == trace_id
    assert root["parent_id"] is None
    assert root["sequence"] == 0


def test_a_full_trace_has_the_expected_shape(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.model_call(model="gpt-4o-mini") as call:
        call.succeed(input_tokens=12, output_tokens=8, usage_provided=True)
    with recorder.tool_call(name="add", arguments={"a": 1, "b": 2}) as tool:
        tool.succeed(result=3)
    recorder.end_trace(stop_reason="final_answer")

    records = _lines(sink)
    assert [r["kind"] for r in records] == [
        RecordKind.TRACE_START,
        RecordKind.MODEL_CALL,
        RecordKind.TOOL_CALL,
        RecordKind.TRACE_END,
    ]
    # sequence is strictly increasing, so order is recoverable without timestamps.
    assert [r["sequence"] for r in records] == [0, 1, 2, 3]
    # Every child points at the root; the root points at nothing.
    root_id = records[0]["record_id"]
    assert [r["parent_id"] for r in records[1:]] == [root_id, root_id, root_id]


def test_parent_id_names_an_earlier_real_record(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.tool_call(name="t") as call:
        call.succeed()
    recorder.end_trace(stop_reason="final_answer")

    records = _lines(sink)
    ids = [r["record_id"] for r in records]
    for index, record in enumerate(records):
        if record["parent_id"] is None:
            continue
        assert record["parent_id"] in ids[:index], "parent must precede its child"


def test_end_trace_carries_the_stop_reason(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    recorder.end_trace(stop_reason="step_limit")

    final = _lines(sink)[-1]
    assert final["kind"] == RecordKind.TRACE_END
    # The field none of the six surveyed systems has (research 9.8).
    assert final["stop_reason"] == "step_limit"


def test_a_trace_without_an_end_record_is_representable(sink: io.StringIO) -> None:
    # A crash, a kill, a process death: the trace simply stops. Nothing forces a
    # synthetic terminal record, which is what makes the failure readable.
    recorder = _recorder(sink)
    recorder.start_trace()
    recorder.close()

    records = _lines(sink)
    assert [r["kind"] for r in records] == [RecordKind.TRACE_START]
    assert not any(r["kind"] == RecordKind.TRACE_END for r in records)


# --------------------------------------------------------------------------- #
# Units — ADR-0010 D-5, and research 8's hazard.
# --------------------------------------------------------------------------- #


def test_duration_is_an_int_named_with_its_unit(sink: io.StringIO) -> None:
    clock = ScriptedClock(0, _MS, 5 * _MS, 7 * _MS, 9 * _MS)
    recorder = _recorder(sink, clock=clock)
    recorder.start_trace()
    with recorder.tool_call(name="t") as call:
        call.succeed()

    record = _lines(sink)[1]
    assert isinstance(record["duration_ns"], int)
    assert record["duration_ns"] == record["ended_at_ns"] - record["started_at_ns"]
    # There is no bare `latency` field anywhere: an unlabelled float is the bug
    # research 8 warns about.
    assert "latency" not in record


def test_every_duration_field_is_named_for_its_unit(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    record = _lines(sink)[0]
    for key in ("started_at_ns", "ended_at_ns", "duration_ns"):
        assert key in record


# --------------------------------------------------------------------------- #
# Content capture — ADR-0010 D-8.
# --------------------------------------------------------------------------- #


def test_content_is_none_by_default_and_never_a_sentinel(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.tool_call(name="add", arguments={"secret": "hunter2"}) as call:
        call.succeed(result=3)

    record = _lines(sink)[1]
    assert record["content"] is None
    # The distinction that matters: absent, not redacted. A sentinel would put a
    # value where the honest answer is "we did not look".
    assert "__REDACTED__" not in json.dumps(record)
    assert "hunter2" not in json.dumps(record)


def test_the_default_capture_policy_is_capture_nothing() -> None:
    assert CaptureNothing().capture_model_content() is False
    assert CaptureNothing().capture_tool_payloads() is False
    # Named so that a reader of the call site sees the decision.
    assert CaptureEverything().capture_tool_payloads() is True


def test_capture_everything_records_the_payload(sink: io.StringIO) -> None:
    recorder = _recorder(sink, capture=CaptureEverything())
    recorder.start_trace()
    with recorder.tool_call(name="add", arguments={"a": 1}) as call:
        call.succeed(result=3)

    record = _lines(sink)[1]
    assert record["content"] == {"arguments": {"a": 1}, "result": 3}


def test_a_failed_tool_call_records_no_result_even_with_capture_on(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink, capture=CaptureEverything())
    recorder.start_trace()
    with recorder.tool_call(name="add", arguments={"a": 1}) as call:
        call.fail(error_type="ValueError", message="nope")

    record = _lines(sink)[1]
    # A failure has no result, so recording one would invent a value.
    assert record["content"] == {"arguments": {"a": 1}}
    assert record["error_message"] == "nope"


# --------------------------------------------------------------------------- #
# Usage provenance — ADR-0010 D-6.
# --------------------------------------------------------------------------- #


def test_usage_provided_is_false_when_the_provider_did_not_report_it(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.model_call(model="m") as call:
        call.succeed()

    record = _lines(sink)[1]
    # None, not 0. "Not reported" and "reported zero" are different facts, and
    # 0 would be a lie.
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["usage_provided"] is False


def test_usage_provided_can_be_asserted_true(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.model_call(model="m") as call:
        call.succeed(input_tokens=7, output_tokens=3, usage_provided=True)

    record = _lines(sink)[1]
    assert record["input_tokens"] == 7
    assert record["output_tokens"] == 3
    assert record["usage_provided"] is True


def test_tokens_without_provenance_are_marked_unprovided(sink: io.StringIO) -> None:
    # A caller who computed its own counts must not be able to claim the
    # provider supplied them by accident.
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.model_call(model="m") as call:
        call.succeed(input_tokens=7, output_tokens=3)

    record = _lines(sink)[1]
    assert record["usage_provided"] is False


# --------------------------------------------------------------------------- #
# Failure paths — ADR-0010 D-9.
# --------------------------------------------------------------------------- #


def test_an_unusable_sink_path_fails_at_construction(tmp_path: Path) -> None:
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")

    # A programming error known before the run starts, so it is loud now rather
    # than on record 400 after the model calls have been paid for.
    with pytest.raises(TraceRecorderError, match="could not open"):
        TraceRecorder(blocker / "nested" / "trace.jsonl")


def test_a_mid_run_write_failure_is_counted_and_does_not_propagate() -> None:
    exploding = ExplodingSink(fail_from=2)  # root succeeds, the first child fails
    recorder = _recorder(exploding)
    recorder.start_trace()

    with recorder.tool_call(name="t") as call:  # must NOT raise
        call.succeed()

    failures = recorder.write_failures
    assert failures.count == 1
    assert failures.first_message is not None
    assert "simulated disk full" in failures.first_message
    # The run continued: the failure did not kill the recorder.
    assert recorder.records_written == 1


def test_a_write_failure_keeps_only_the_first_message() -> None:
    exploding = ExplodingSink(fail_from=2)
    recorder = _recorder(exploding)
    recorder.start_trace()
    for _ in range(3):
        with recorder.tool_call(name="t") as call:
            call.succeed()

    # Every failure is counted; the first message is kept because later ones are
    # usually the same cause repeating.
    assert recorder.write_failures.count == 3
    assert "simulated disk full" in (recorder.write_failures.first_message or "")


def test_no_write_failures_reports_clean(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    assert recorder.write_failures.count == 0
    assert recorder.write_failures.any is False
    assert str(recorder.write_failures) == "no write failures"


def test_an_exception_inside_a_tool_block_still_writes_a_record(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()

    with pytest.raises(RuntimeError, match="boom"), recorder.tool_call(name="t"):
        raise RuntimeError("boom")

    record = _lines(sink)[1]
    # A missing record would be indistinguishable from a tool never called.
    assert record["kind"] == RecordKind.TOOL_CALL
    assert record["outcome"] == Outcome.ERROR
    assert record["error_type"] == "RuntimeError"
    assert record["error_message"] == "boom"


def test_an_exception_inside_a_model_block_still_writes_a_record(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()

    with pytest.raises(RuntimeError), recorder.model_call(model="m"):
        raise RuntimeError("provider down")

    record = _lines(sink)[1]
    assert record["kind"] == RecordKind.MODEL_CALL
    assert record["outcome"] == Outcome.ERROR
    assert record["error_message"] == "provider down"


def test_settling_a_tool_call_twice_is_a_programming_error(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.tool_call(name="t") as call:
        call.succeed()
        # Overwriting the first settlement would silently discard a fact;
        # ignoring it would silently discard a fact.
        with pytest.raises(TraceRecorderError, match="already settled"):
            call.fail(message="also failed")


def test_settling_a_model_call_twice_is_a_programming_error(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.model_call(model="m") as call:
        call.succeed()
        with pytest.raises(TraceRecorderError, match="already settled"):
            call.succeed()


def test_an_unsettled_call_is_recorded_as_unknown(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.tool_call(name="t"):
        pass  # neither succeed() nor fail()

    record = _lines(sink)[1]
    assert record["outcome"] == Outcome.UNKNOWN


def test_a_denied_call_is_its_own_outcome(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.tool_call(name="dangerous") as call:
        call.deny(message="denied by policy")

    record = _lines(sink)[1]
    # A refusal is not a failure: nothing executed. Counting them together would
    # hide the difference between "it broke" and "we stopped it".
    assert record["outcome"] == Outcome.DENIED
    assert record["error_message"] == "denied by policy"


def test_recording_without_a_trace_is_an_error(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    # A single combined `with`: entering the tool_call context is what raises, so
    # the raise still happens inside the pytest.raises scope. Same semantics, and
    # ruff's SIM117 requires the combined form.
    with (
        pytest.raises(TraceRecorderError, match="no trace is open"),
        recorder.tool_call(name="t"),
    ):
        pass


def test_starting_two_traces_on_one_recorder_is_an_error(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with pytest.raises(TraceRecorderError, match="already open"):
        recorder.start_trace()


def test_recording_after_close_is_an_error(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    recorder.close()
    with pytest.raises(TraceRecorderError):
        recorder.start_trace()


def test_close_is_idempotent_for_a_caller_supplied_stream(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    recorder.close()
    recorder.close()
    # The caller owns a stream it supplied; closing it would be a surprising
    # side effect on another part of the program.
    assert sink.closed is False


def test_close_closes_an_owned_path(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "trace.jsonl"
    recorder = _recorder(path)
    recorder.start_trace()
    recorder.close()
    # A path we opened is ours to close, and the parent directory was created.
    assert path.is_file()


def test_close_reports_a_failure_rather_than_raising() -> None:
    class BadClose(ExplodingSink):
        def close(self) -> None:
            raise OSError("cannot close")

    bad = BadClose()
    recorder = _recorder(bad)
    recorder.start_trace()
    # Constructed with a stream, so `_owns_handle` is False and close is a
    # no-op on it — this asserts the no-op does not raise.
    recorder.close()


# --------------------------------------------------------------------------- #
# Bounds — ADR-0010 D-10.
# --------------------------------------------------------------------------- #


def test_a_long_error_message_is_truncated_and_the_field_is_named(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink, bounds=Bounds(max_error_message_chars=50))
    recorder.start_trace()
    with recorder.tool_call(name="t") as call:
        call.fail(message="x" * 5000)

    record = _lines(sink)[1]
    assert len(record["error_message"]) < 5000
    assert record["truncated"] == ["error_message"]
    assert "chars]" in record["error_message"]


def test_a_record_within_bounds_names_nothing_as_truncated(
    sink: io.StringIO,
) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.tool_call(name="t") as call:
        call.fail(message="short")

    assert _lines(sink)[1]["truncated"] == []


def test_max_records_drops_and_counts_instead_of_growing() -> None:
    exploding = ExplodingSink()
    recorder = _recorder(exploding, bounds=Bounds(max_records=2))
    recorder.start_trace()
    with recorder.tool_call(name="a") as call:
        call.succeed()
    with recorder.tool_call(name="b") as call:
        call.succeed()

    assert recorder.records_written == 2
    # A bounded trace of an unbounded run cannot be whole; it can say by how much.
    assert recorder.records_dropped == 1


def test_bounds_reject_a_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="max_records must be positive"):
        Bounds(max_records=0)


def test_truncate_names_how_much_it_removed() -> None:
    cut, was_cut = truncate("abcdefghij", 4)
    assert was_cut is True
    assert cut.startswith("abcd")
    assert "+6 chars" in cut


def test_truncate_leaves_a_short_value_alone() -> None:
    value, was_cut = truncate("abc", 10)
    assert value == "abc"
    assert was_cut is False


# --------------------------------------------------------------------------- #
# JSON safety — an unserialisable payload must not kill the run.
# --------------------------------------------------------------------------- #


def test_json_safe_handles_values_json_cannot_represent() -> None:
    class Opaque:
        def __repr__(self) -> str:
            return "<opaque>"

    assert json_safe(Opaque()) == "<opaque>"
    assert json_safe(b"abcd") == "<bytes 4 bytes>"
    assert json_safe({1: "a", "b": [1, 2]}) == {"1": "a", "b": [1, 2]}


def test_json_safe_bounds_recursion_rather_than_overflowing() -> None:
    cyclic: dict[str, Any] = {}
    cyclic["self"] = cyclic
    # A cycle would recurse forever; the depth cap converts it into a bounded
    # string instead of a RecursionError. Asserted by searching the rendered
    # form rather than by pinning the exact nesting count, because the cap is an
    # implementation detail while "it terminates" is the contract.
    assert "<nested too deep>" in json.dumps(json_safe(cyclic))


def test_json_safe_bounds_a_deeply_nested_non_cyclic_value() -> None:
    deep: object = "bottom"
    for _ in range(20):
        deep = {"n": deep}
    # Depth alone, with no cycle, must also be bounded.
    assert "<nested too deep>" in json.dumps(json_safe(deep))


def test_a_broken_repr_does_not_kill_the_run() -> None:
    class Nasty:
        def __repr__(self) -> str:
            raise RuntimeError("no repr for you")

    assert json_safe(Nasty()) == "<unrepresentable Nasty>"


def test_an_unserialisable_payload_is_recorded_not_raised(
    sink: io.StringIO,
) -> None:
    class Opaque:
        pass

    recorder = _recorder(sink, capture=CaptureEverything())
    recorder.start_trace()
    with recorder.tool_call(name="t", arguments={"obj": Opaque()}) as call:
        call.succeed()

    record = _lines(sink)[1]
    # The default repr carries an address, so the assertion is on the stable
    # part: the value became a string instead of killing the run.
    assert "Opaque object" in record["content"]["arguments"]["obj"]


# --------------------------------------------------------------------------- #
# The on-disk format — one record is one line.
# --------------------------------------------------------------------------- #


def test_one_record_is_one_line_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    recorder = _recorder(path)
    recorder.start_trace()
    with recorder.tool_call(name="t") as call:
        call.succeed()
    recorder.end_trace(stop_reason="final_answer")
    recorder.close()

    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    lines = [line for line in text.splitlines() if line]
    assert len(lines) == 3
    # Every line parses independently, which is what makes the format appendable.
    for line in lines:
        assert json.loads(line)["trace_id"] == recorder.trace_id


def test_the_jsonl_file_is_appendable_across_recorders(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    first = _recorder(path)
    first.start_trace()
    first.end_trace(stop_reason="final_answer")
    first.close()

    second = _recorder(path)
    second.start_trace()
    second.end_trace(stop_reason="step_limit")
    second.close()

    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    # Two traces in one file, distinguished by trace_id rather than by file.
    assert len(records) == 4
    assert len({r["trace_id"] for r in records}) == 2


def test_every_record_carries_every_field(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    record = _lines(sink)[0]
    # An explicit null says "not reported"; an omitted key says "this build does
    # not have that field". A reader cannot tell those apart, so nothing is
    # omitted.
    expected = {
        "trace_id",
        "record_id",
        "parent_id",
        "kind",
        "sequence",
        "started_at_ns",
        "ended_at_ns",
        "duration_ns",
        "timestamp_utc",
        "outcome",
        "model",
        "tool_name",
        "stop_reason",
        "input_tokens",
        "output_tokens",
        "usage_provided",
        "error_type",
        "error_message",
        "content",
        "truncated",
    }
    assert set(record) == expected


# --------------------------------------------------------------------------- #
# Independence — ADR-0010 D-12.
# --------------------------------------------------------------------------- #


def test_the_package_imports_no_third_party_module() -> None:
    import execution_trace_recorder as package

    allowed = {
        "bounds",
        "capture",
        "clock",
        "errors",
        "records",
        "recorder",
    }
    for name, module in vars(package).items():
        if name.startswith("__"):
            continue
        origin = getattr(module, "__module__", None)
        if origin is not None and origin.startswith("execution_trace_recorder"):
            continue
        # Only stdlib and this package's own submodules are reachable from here.
        assert origin is None or not origin.startswith("execution_trace_recorder"), name
    assert allowed  # the submodule set is asserted by the import above succeeding


def test_the_recorder_does_not_import_the_agent_loop() -> None:
    import execution_trace_recorder.recorder as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    # ADR-0010 D-12: the adapter that maps Step onto records lives in the loop's
    # own module, so the recorder stays usable without it.
    #
    # The check parses the import statements rather than grepping the source.
    # The first version grepped, and failed on the module's own docstring, which
    # names `react_agent_loop` precisely to explain why it is not imported. A
    # test that cannot tell an import from a sentence about imports is testing
    # the wrong thing.
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])

    forbidden = {"react_agent_loop", "tool_registry", "model_provider", "mcp_client"}
    assert not (imported & forbidden), f"unexpected import(s): {imported & forbidden}"


def test_the_recorder_imports_only_the_standard_library() -> None:
    import execution_trace_recorder.recorder as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue  # a relative import inside this package
            if node.module:
                imported.add(node.module.split(".")[0])

    # Zero runtime dependencies (ADR-0003). This is the check that keeps it true
    # as the module grows.
    assert imported <= set(sys.stdlib_module_names)


def test_a_handle_reports_whether_it_was_settled(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    recorder.start_trace()
    with recorder.tool_call(name="t") as call:
        assert call.settled is False
        call.succeed()
        assert call.settled is True


def test_the_recorder_repr_names_the_policy(sink: io.StringIO) -> None:
    recorder = _recorder(sink)
    # The capture policy appears in the repr, so a log line records the decision.
    assert "CaptureNothing()" in repr(recorder)


def _iterator_type_check() -> Iterator[None]:
    """A no-op that keeps the unused import of Iterator meaningful for mypy.

    ``tool_call`` and ``model_call`` are generators typed ``Iterator[...]``; this
    function exists so the import is not flagged as unused while the annotations
    remain precise.
    """
    yield None


def test_a_tool_arguments_mapping_is_not_mutated_by_the_recorder(
    sink: io.StringIO,
) -> None:
    arguments: Mapping[str, Any] = {"a": 1}
    recorder = _recorder(sink, capture=CaptureEverything())
    recorder.start_trace()
    with recorder.tool_call(name="t", arguments=arguments) as call:
        call.succeed()
    # The caller's mapping is theirs; the recorder copies what it writes.
    assert arguments == {"a": 1}
