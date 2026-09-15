"""The recorder: flat JSONL records, bounded, and never fatal.

Three decisions shape this file, and each is an ADR decision rather than a
preference.

**A write failure does not propagate (ADR-0010 D-9).** A recorder that raises can
kill the run it was observing; one that swallows loses the evidence. Neither is
acceptable, so :meth:`TraceRecorder._write` is the single place that catches, and
the loss is counted and inspectable via
:attr:`TraceRecorder.write_failures`. Nothing is silent, nothing is fatal.

**The constructor fails loudly.** An unusable sink is a programming error known
before the run starts, so failing then is cheap. Failing on record 400, after the
model calls have been paid for, is not.

**A tool call and its result are one record (ADR-0010 D-2).** Every surveyed
system models them as one node, and splitting them would make "did this call
succeed?" require a join. :meth:`TraceRecorder.tool_call` is a context manager,
so one call produces exactly one line — including when the block raises.

Nothing here imports ``react_agent_loop``, ``tool_registry``, ``model_provider``
or ``mcp_client`` (ADR-0010 D-12). An adapter that maps the loop's ``Step`` onto
these records belongs in the loop's own module.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, runtime_checkable

from .bounds import Bounds, bound_content, truncate
from .capture import CaptureNothing, CapturePolicy
from .clock import Clock, SystemClock
from .errors import TraceRecorderError, WriteFailures
from .records import Outcome, RecordKind, TraceRecord

__all__ = ["ModelCallHandle", "Sink", "ToolCallHandle", "TraceRecorder"]


@runtime_checkable
class Sink(Protocol):
    """A write target: exactly what the recorder needs from one.

    Deliberately narrower than ``IO[str]``. The recorder calls three methods and
    nothing else, so demanding the full ``IO`` surface would reject a double that
    has all three — which is what made the first version of the write-failure
    test fail mypy rather than the test suite. ``io.StringIO`` and a file opened
    by ``Path.open`` both satisfy this, and so does any object with these three
    methods.
    """

    def write(self, text: str) -> object:
        """Write ``text``; the return value is unused."""
        ...

    def flush(self) -> object:
        """Flush buffered output; the return value is unused."""
        ...

    def close(self) -> object:
        """Release the target; the return value is unused."""
        ...


@dataclass(slots=True)
class _WriteState:
    """Mutable write accounting, kept out of the recorder's own attributes."""

    written: int = 0
    dropped: int = 0
    failures: int = 0
    first_failure: str | None = None


@dataclass(slots=True)
class ToolCallHandle:
    """The object yielded by :meth:`TraceRecorder.tool_call`.

    Exactly one of :meth:`succeed` or :meth:`fail` is expected. If neither is
    called, the record is written with ``outcome=UNKNOWN`` — a missing record
    would be indistinguishable from a call that never happened, so an unresolved
    call is recorded as unresolved rather than omitted.

    Settling twice is a programming error and raises: the second call would have
    to either overwrite the first (silently discarding a fact) or be ignored
    (silently discarding a fact).
    """

    name: str
    arguments: Mapping[str, Any] | None = None
    _settled: bool = field(default=False, init=False)
    _outcome: Outcome = field(default=Outcome.UNKNOWN, init=False)
    _result: object = field(default=None, init=False)
    _error_type: str | None = field(default=None, init=False)
    _error_message: str | None = field(default=None, init=False)

    def succeed(self, result: object = None) -> None:
        """Mark the call as having produced a value."""
        self._settle(Outcome.OK)
        self._result = result

    def fail(self, *, error_type: str | None = None, message: str = "") -> None:
        """Mark the call as having failed."""
        self._settle(Outcome.ERROR)
        self._error_type = error_type
        self._error_message = message

    def deny(self, *, message: str = "denied by policy") -> None:
        """Mark the call as refused before it ran.

        Distinct from ``fail`` because a refusal is not a tool error: nothing
        executed. ``denied`` is its own outcome so a reader can count refusals
        separately from failures.
        """
        self._settle(Outcome.DENIED)
        self._error_message = message

    def _settle(self, outcome: Outcome) -> None:
        if self._settled:
            raise TraceRecorderError(
                f"{self.name}: already settled as {self._outcome}; "
                f"settling twice would silently discard a fact"
            )
        self._settled = True
        self._outcome = outcome

    @property
    def settled(self) -> bool:
        """True once one of ``succeed`` / ``fail`` / ``deny`` has been called."""
        return self._settled


@dataclass(slots=True)
class ModelCallHandle:
    """The object yielded by :meth:`TraceRecorder.model_call`.

    Mirrors :class:`ToolCallHandle`, with the model-specific fields — token
    counts and ``usage_provided`` — carried on the settle calls rather than the
    constructor, because a provider reports usage on the *response*.
    """

    model: str
    _settled: bool = field(default=False, init=False)
    _outcome: Outcome = field(default=Outcome.UNKNOWN, init=False)
    _input_tokens: int | None = field(default=None, init=False)
    _output_tokens: int | None = field(default=None, init=False)
    _usage_provided: bool = field(default=False, init=False)
    _error_type: str | None = field(default=None, init=False)
    _error_message: str | None = field(default=None, init=False)

    def succeed(
        self,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        usage_provided: bool = False,
    ) -> None:
        """Mark the call as having produced a response.

        ``usage_provided`` defaults to ``False`` deliberately. ADR-0010 D-6: a
        trace that cannot say "the provider told us this" versus "we computed
        this" cannot be audited, so the honest default is "we did not get it
        from the provider". A caller passing token counts it derived itself must
        say so explicitly.
        """
        self._settle(Outcome.OK)
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._usage_provided = usage_provided

    def fail(self, *, error_type: str | None = None, message: str = "") -> None:
        """Mark the call as having failed."""
        self._settle(Outcome.ERROR)
        self._error_type = error_type
        self._error_message = message

    def _settle(self, outcome: Outcome) -> None:
        if self._settled:
            raise TraceRecorderError(
                f"{self.model}: already settled as {self._outcome}"
            )
        self._settled = True
        self._outcome = outcome

    @property
    def settled(self) -> bool:
        """True once ``succeed`` or ``fail`` has been called."""
        return self._settled


class TraceRecorder:
    """Writes one trace as append-only JSONL.

    Usage::

        recorder = TraceRecorder(Path("run.jsonl"))
        recorder.start_trace()
        try:
            with recorder.model_call(model="gpt-4o-mini") as call:
                call.succeed(input_tokens=12, output_tokens=8, usage_provided=True)
            with recorder.tool_call(name="add", arguments={"a": 1, "b": 2}) as call:
                call.succeed(result=3)
            recorder.end_trace(stop_reason="final_answer")
        finally:
            recorder.close()
    """

    __slots__ = (
        "_bounds",
        "_capture",
        "_clock",
        "_closed",
        "_drop_reported",
        "_handle",
        "_owns_handle",
        "_parent_id",
        "_path",
        "_sequence",
        "_sink",
        "_state",
        "_trace_id",
    )

    def __init__(
        self,
        sink: Path | str | Sink,
        *,
        clock: Clock | None = None,
        capture: CapturePolicy | None = None,
        bounds: Bounds | None = None,
    ) -> None:
        """Open a sink and bind the policies.

        Args:
            sink: A path (opened in append mode) or an open text stream the
                caller owns. A path is opened here so an unusable destination
                fails now rather than mid-run.
            clock: The time source. Defaults to :class:`~.clock.SystemClock`.
            capture: Whether content is written. Defaults to
                :class:`~.capture.CaptureNothing` — **off**, per ADR-0010 D-8.
            bounds: The limits applied before writing. Defaults to
                :class:`~.bounds.Bounds`.

        Raises:
            TraceRecorderError: The sink path could not be opened. A programming
                error, so it is raised at construction rather than at the first
                write — see the module docstring.
        """
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._capture: CapturePolicy = (
            capture if capture is not None else CaptureNothing()
        )
        self._bounds = bounds if bounds is not None else Bounds()

        self._sink: Sink
        if isinstance(sink, (str, Path)):
            path = Path(sink)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._sink = path.open("a", encoding="utf-8")
            except OSError as exc:
                raise TraceRecorderError(
                    f"could not open trace sink {path}: {exc}"
                ) from exc
            self._owns_handle = True
            self._path: Path | None = path
        else:
            self._sink = sink
            self._owns_handle = False
            self._path = None

        self._state = _WriteState()
        self._trace_id: str | None = None
        self._parent_id: str | None = None
        self._sequence = 0
        self._closed = False
        self._drop_reported = False
        self._handle: Sink | None = self._sink

    # -- introspection ------------------------------------------------------- #

    @property
    def trace_id(self) -> str | None:
        """The current trace's id, or ``None`` before :meth:`start_trace`."""
        return self._trace_id

    @property
    def records_written(self) -> int:
        """How many records reached the sink."""
        return self._state.written

    @property
    def records_dropped(self) -> int:
        """How many records the ``max_records`` cap discarded.

        Non-zero means the trace is incomplete, and the number says by how much.
        A bounded trace of an unbounded run cannot be whole; it can be honest.
        """
        return self._state.dropped

    @property
    def write_failures(self) -> WriteFailures:
        """What could not be written. ADR-0010 D-9: never raised, never hidden."""
        return WriteFailures(
            count=self._state.failures, first_message=self._state.first_failure
        )

    @property
    def path(self) -> Path | None:
        """The sink path, or ``None`` when the caller supplied a stream."""
        return self._path

    # -- the trace ----------------------------------------------------------- #

    def start_trace(self) -> str:
        """Open a trace and write its root record.

        Returns:
            The new ``trace_id``.

        Raises:
            TraceRecorderError: A trace is already open on this recorder. One
                recorder writes one trace; starting a second would silently
                merge two runs under one id.
        """
        self._require_open()
        if self._trace_id is not None:
            raise TraceRecorderError(
                f"trace {self._trace_id} is already open; one recorder writes "
                f"one trace — create a second recorder for a second run"
            )
        self._trace_id = uuid.uuid4().hex
        self._sequence = 0
        self._parent_id = None
        root_id = self._emit(
            RecordKind.TRACE_START,
            outcome=Outcome.OK,
        )
        self._parent_id = root_id
        return self._trace_id

    def end_trace(self, *, stop_reason: str) -> str:
        """Write the terminal record and return its id.

        Args:
            stop_reason: Why the run ended. ``react-agent-loop`` computes
                ``StopReason``; pass ``str(result.reason)``.

        Returns:
            The terminal record's id.

        Raises:
            TraceRecorderError: No trace is open.
        """
        self._require_trace()
        record_id = self._emit(
            RecordKind.TRACE_END,
            outcome=Outcome.OK,
            stop_reason=stop_reason,
        )
        self._parent_id = None
        return record_id

    @contextmanager
    def model_call(self, *, model: str) -> Iterator[ModelCallHandle]:
        """Record one model call as a single record.

        Args:
            model: The model identifier.

        Yields:
            A :class:`ModelCallHandle` to settle. An exception inside the block
            settles the record as ``outcome=ERROR`` and re-raises.
        """
        self._require_trace()
        handle = ModelCallHandle(model=model)
        started = self._clock.now_ns()
        try:
            yield handle
        except BaseException as exc:
            if not handle.settled:
                handle._settle(Outcome.ERROR)
                handle._error_type = type(exc).__name__
                handle._error_message = str(exc)
            self._emit(
                RecordKind.MODEL_CALL,
                started_at_ns=started,
                outcome=handle._outcome,
                model=model,
                input_tokens=handle._input_tokens,
                output_tokens=handle._output_tokens,
                usage_provided=handle._usage_provided,
                error_type=handle._error_type,
                error_message=handle._error_message,
            )
            raise
        self._emit(
            RecordKind.MODEL_CALL,
            started_at_ns=started,
            outcome=handle._outcome,
            model=model,
            input_tokens=handle._input_tokens,
            output_tokens=handle._output_tokens,
            usage_provided=handle._usage_provided,
            error_type=handle._error_type,
            error_message=handle._error_message,
        )

    @contextmanager
    def tool_call(
        self, *, name: str, arguments: Mapping[str, Any] | None = None
    ) -> Iterator[ToolCallHandle]:
        """Record one tool call **and its result** as a single record.

        ADR-0010 D-2: one record, not two. Every surveyed system does this, and
        splitting would make success require a join.

        The record is written on exit, so an exception inside the block still
        produces one — with ``outcome=ERROR``. A missing record would be
        indistinguishable from a tool that was never called.

        Args:
            name: The tool name.
            arguments: The call's arguments. Recorded only when the capture
                policy permits tool payloads.

        Yields:
            A :class:`ToolCallHandle` to settle.
        """
        self._require_trace()
        handle = ToolCallHandle(name=name, arguments=arguments)
        started = self._clock.now_ns()
        try:
            yield handle
        except BaseException as exc:
            if not handle.settled:
                handle._settle(Outcome.ERROR)
                handle._error_type = type(exc).__name__
                handle._error_message = str(exc)
            self._emit_tool(handle, started)
            raise
        self._emit_tool(handle, started)

    # -- internals ----------------------------------------------------------- #

    def _emit_tool(self, handle: ToolCallHandle, started_at_ns: int) -> None:
        """Write a tool record, applying the payload-capture policy."""
        content: dict[str, Any] | None = None
        if self._capture.capture_tool_payloads():
            payload: dict[str, Any] = {}
            if handle.arguments is not None:
                payload["arguments"] = dict(handle.arguments)
            if handle._outcome is Outcome.OK and handle._result is not None:
                payload["result"] = handle._result
            content = payload or None

        self._emit(
            RecordKind.TOOL_CALL,
            started_at_ns=started_at_ns,
            outcome=handle._outcome,
            tool_name=handle.name,
            error_type=handle._error_type,
            error_message=handle._error_message,
            content=content,
        )

    def _emit(
        self,
        kind: RecordKind,
        *,
        started_at_ns: int | None = None,
        outcome: Outcome,
        model: str | None = None,
        tool_name: str | None = None,
        stop_reason: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        usage_provided: bool = False,
        error_type: str | None = None,
        error_message: str | None = None,
        content: Mapping[str, Any] | None = None,
    ) -> str:
        """Build and write one record, returning its id."""
        assert self._trace_id is not None

        started = started_at_ns if started_at_ns is not None else self._clock.now_ns()
        ended = self._clock.now_ns()
        truncated_fields: list[str] = []

        bounded_error: str | None = None
        if error_message is not None:
            bounded_error, cut = truncate(
                error_message, self._bounds.max_error_message_chars
            )
            if cut:
                truncated_fields.append("error_message")

        bounded_content: Mapping[str, Any] | None = None
        if content is not None:
            bounded_content, cut_content = bound_content(
                content, self._bounds.max_content_chars
            )
            if cut_content:
                truncated_fields.append("content")

        record = TraceRecord(
            trace_id=self._trace_id,
            record_id=uuid.uuid4().hex,
            parent_id=self._parent_id,
            kind=kind,
            sequence=self._sequence,
            started_at_ns=started,
            # A terminal record has an end; a nested one does too, because it is
            # written after the work. Only a record that never finished has none,
            # and that path is the exception handler's, not this one.
            ended_at_ns=ended,
            duration_ns=ended - started,
            timestamp_utc=self._clock.now_utc(),
            outcome=outcome,
            model=model,
            tool_name=tool_name,
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            usage_provided=usage_provided,
            error_type=error_type,
            error_message=bounded_error,
            content=bounded_content,
            truncated=tuple(truncated_fields),
        )
        self._sequence += 1
        self._write(record)
        return record.record_id

    def _write(self, record: TraceRecord) -> None:
        """Serialise and write one record. **Never raises.**

        ADR-0010 D-9. Everything that can go wrong here — a full disk, a closed
        stream, an encoding problem — is caught, counted, and left for the caller
        to inspect. The alternative is a recorder that kills the run it was
        observing, which is worse than losing a record.

        The one thing this method does check is the record cap: past
        ``max_records`` the record is dropped *and counted*, so a truncated trace
        says so instead of looking complete.
        """
        if self._state.written >= self._bounds.max_records:
            self._state.dropped += 1
            return

        handle = self._handle
        if handle is None:
            # close() already ran; treat as a dropped record rather than raising.
            self._record_failure("recorder is closed")
            return

        try:
            line = json.dumps(
                record.to_json(), separators=(",", ":"), ensure_ascii=False
            )
            if "\n" in line or "\r" in line:
                # The same invariant mcp-client's framing enforces: one record is
                # one line. ensure_ascii=False plus compact separators makes this
                # unreachable today, and it is asserted because a future encoder
                # change could silently split a record across two lines.
                raise ValueError("encoded record contains an embedded newline")
            handle.write(line + "\n")
            handle.flush()
        except Exception as exc:
            self._record_failure(f"{type(exc).__name__}: {exc}")
            return

        self._state.written += 1

    def _record_failure(self, message: str) -> None:
        """Count a write failure and keep the first message."""
        self._state.failures += 1
        if self._state.first_failure is None:
            self._state.first_failure = message

    def _require_open(self) -> None:
        if self._closed:
            raise TraceRecorderError("recorder is closed")

    def _require_trace(self) -> None:
        self._require_open()
        if self._trace_id is None:
            raise TraceRecorderError(
                "no trace is open; call start_trace() before recording"
            )

    # -- lifecycle ----------------------------------------------------------- #

    def close(self) -> None:
        """Flush and close an owned sink. Idempotent.

        A caller-supplied stream is **not** closed: the caller owns it, and
        closing a file another part of the program is still writing to would be
        a surprising side effect. Owned paths are closed here.
        """
        if self._closed:
            return
        self._closed = True

        if self._owns_handle and self._handle is not None:
            try:
                self._handle.flush()
                self._handle.close()
            except Exception as exc:
                self._record_failure(f"close: {type(exc).__name__}: {exc}")
        self._handle = None

    def __enter__(self) -> TraceRecorder:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        where = str(self._path) if self._path is not None else "stream"
        return (
            f"TraceRecorder({where}, trace={self._trace_id}, "
            f"written={self._state.written}, capture={self._capture!r})"
        )
