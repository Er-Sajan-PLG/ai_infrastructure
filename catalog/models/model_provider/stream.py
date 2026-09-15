"""Streaming: the SSE reader, the delta accumulator, and the fallible iterator.

Three things live here because they are the parts of streaming that are easy to
get subtly wrong:

1. **SSE framing** (:func:`iter_sse_events`) -- transport-shaped, but pure string
   manipulation, so it belongs here rather than in a transport, and is testable
   without a socket.
2. **Tool-argument reassembly** (:class:`ToolCallAccumulator`) -- OpenAI
   fragments a JSON string across chunks. A partial JSON string is not
   parseable, so treating each fragment as complete would yield corrupt
   arguments rather than an error.
3. **Mid-stream failure** (:class:`ProviderStream`) -- a stream can raise after
   already yielding tokens (ADR-0007 D-9).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .errors import ProviderError
from .types import ToolCallBlock, ToolCallDelta


@dataclass(frozen=True, slots=True)
class SSEEvent:
    """One decoded Server-Sent Event.

    Attributes:
        data: The concatenated ``data:`` payload, with no trailing newline.
        event: The ``event:`` name when the provider names events (Anthropic
            does, OpenAI does not).
        is_done: True for OpenAI's ``data: [DONE]`` sentinel.
    """

    data: str = ""
    event: str | None = None
    is_done: bool = False


def iter_sse_events(lines: Iterator[str]) -> Iterator[SSEEvent]:
    """Decode an SSE line stream into events.

    Handles the framing rules that matter in practice:

    * ``data:`` lines accumulate, joined by newline, until a blank line ends the
      event (the spec allows a multi-line payload).
    * A leading space after the colon is stripped, per the SSE spec.
    * Comment lines (``:``) are ignored.
    * ``data: [DONE]`` is recognised as OpenAI's sentinel and reported via
      ``is_done`` rather than being handed on as JSON, since it is not JSON.

    Termination is deliberately **not** decided here. OpenAI ends with a sentinel,
    Anthropic with an event, and Gemini with a bare EOF; the transport reports
    EOF and the adapter interprets the end. Deciding here would push provider
    knowledge into the transport, which ADR-0007 D-1 forbids.
    """
    data_lines: list[str] = []
    event_name: str | None = None

    for raw in lines:
        line = raw.rstrip("\r\n")

        if line == "":
            if data_lines or event_name is not None:
                payload = "\n".join(data_lines)
                yield SSEEvent(
                    data=payload,
                    event=event_name,
                    is_done=payload.strip() == "[DONE]",
                )
            data_lines = []
            event_name = None
            continue

        if line.startswith(":"):
            continue

        field_name, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]

        if field_name == "data":
            data_lines.append(value)
        elif field_name == "event":
            event_name = value

    # A final event may arrive without its terminating blank line.
    if data_lines or event_name is not None:
        payload = "\n".join(data_lines)
        yield SSEEvent(
            data=payload, event=event_name, is_done=payload.strip() == "[DONE]"
        )


@dataclass
class _PendingCall:
    """A tool call being accumulated across chunks."""

    index: int
    id: str | None = None
    name: str | None = None
    fragments: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AccumulatedToolCall:
    """A fully reassembled tool call.

    Attributes:
        index: The stream position this call came from.
        id: The provider's call id.
        name: The tool name.
        arguments: Parsed arguments.
        raw_arguments: The re-joined JSON string before parsing, kept so a parse
            failure can be diagnosed against what the provider actually sent.
    """

    index: int
    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str


class ToolCallAccumulator:
    """Reassembles fragmented tool-call arguments across stream chunks.

    Providers fragment tool calls differently, and both ways require reassembly
    before the arguments mean anything:

    * OpenAI sends ``arguments`` as a JSON *string*, split at arbitrary byte
      offsets -- a fragment can end mid-token, mid-key, or mid-number.
    * Anthropic sends ``input_json_delta.partial_json`` fragments.

    Both arrive here as strings, so one accumulator serves both. A call is
    identified by ``index`` because the ``id`` and ``name`` are typically sent
    only on the first fragment.
    """

    def __init__(self) -> None:
        self._calls: dict[int, _PendingCall] = {}

    def add(self, delta: ToolCallDelta) -> None:
        """Fold one fragment into the accumulated state."""
        pending = self._calls.get(delta.index)
        if pending is None:
            pending = _PendingCall(index=delta.index)
            self._calls[delta.index] = pending
        if delta.id is not None:
            pending.id = delta.id
        if delta.name is not None:
            pending.name = delta.name
        if delta.arguments_fragment:
            pending.fragments.append(delta.arguments_fragment)

    def finish(
        self,
        *,
        on_parse_error: Callable[[str, str], ProviderError] | None = None,
    ) -> tuple[AccumulatedToolCall, ...]:
        """Return the completed calls, in stream order.

        Args:
            on_parse_error: Builds the error to raise when a call's reassembled
                arguments are not valid JSON. Defaults to a
                :class:`~model_provider.errors.ProviderError`.

        Raises:
            ProviderError: If the reassembled string is not valid JSON, or a call
                never received a name. Both are provider-side protocol
                violations; silently substituting ``{}`` would hand the caller a
                tool invocation with invented arguments.
        """
        finished: list[AccumulatedToolCall] = []
        for index in sorted(self._calls):
            pending = self._calls[index]
            raw = "".join(pending.fragments)
            if not pending.name:
                raise _parse_error(
                    on_parse_error,
                    f"tool call at index {index} never received a name",
                    raw,
                )
            if not raw:
                # A call with no arguments at all is legitimate (a zero-argument
                # tool); an empty object is the correct reading, unlike a
                # truncated string.
                arguments: dict[str, Any] = {}
            else:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise _parse_error(
                        on_parse_error,
                        f"tool call arguments at index {index} are not valid JSON: {exc.msg}",
                        raw,
                    ) from exc
                if not isinstance(parsed, dict):
                    raise _parse_error(
                        on_parse_error,
                        f"tool call arguments at index {index} are "
                        f"{type(parsed).__name__}, expected object",
                        raw,
                    )
                arguments = parsed

            finished.append(
                AccumulatedToolCall(
                    index=index,
                    id=pending.id or f"call_{index}",
                    name=pending.name,
                    arguments=arguments,
                    raw_arguments=raw,
                )
            )
        return tuple(finished)

    def as_blocks(self) -> tuple[ToolCallBlock, ...]:
        """Convenience: the accumulated calls as neutral blocks."""
        return tuple(
            ToolCallBlock(id=c.id, name=c.name, arguments=c.arguments)
            for c in self.finish()
        )


def _parse_error(
    factory: Callable[[str, str], ProviderError] | None, message: str, raw: str
) -> ProviderError:
    if factory is not None:
        return factory(message, raw)
    return ProviderError(message)


class ProviderStream:
    """Wraps a delta iterator so mid-stream failures surface as ProviderError.

    A stream that could only fail before its first chunk would silently truncate:
    OpenAI raises on an ``error`` frame after a 200, and Anthropic sends a
    mid-stream ``error`` event after a 200 as well. Both must reach the caller as
    a normal exception from the iteration, so one handler covers pre- and
    post-first-chunk failures (ADR-0007 D-9).

    The wrapped iterator's own :class:`ProviderError` passes through unchanged;
    any other exception is wrapped so callers never have to catch vendor or
    stdlib exceptions from this layer.
    """

    def __init__(
        self,
        deltas: Iterator[Any],
        *,
        provider: str,
        model: str,
    ) -> None:
        self._deltas = deltas
        self._provider = provider
        self._model = model

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        try:
            delta = next(self._deltas)
        except StopIteration:
            raise
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"stream failed mid-iteration: {type(exc).__name__}",
                provider=self._provider,
                model=self._model,
            ) from exc
        return delta
