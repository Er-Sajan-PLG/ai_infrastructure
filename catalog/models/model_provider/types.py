"""The neutral types every provider adapter translates to and from.

Design rules (ADR-0007):

* Plain frozen dataclasses, never framework classes (D-2) -- no Pydantic, no
  vendor types, so a consumer never converts.
* Every usage field is optional (D-5), because each provider omits a different
  one. A zero is a measurement; ``None`` is the absence of one, and conflating
  them corrupts cost accounting.
* Finish reasons normalise to a closed enum *and* keep the provider's raw string
  (D-6), because Gemini exposes 18+ values that cannot be merged losslessly and
  the raw value is what a human debugs against.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class Role(enum.Enum):
    """Who produced a message.

    ``SYSTEM`` exists so the neutral model is complete, but providers differ
    sharply: OpenAI expresses a system prompt as a message with this role, while
    Anthropic's Messages API has no system role at all and wants a top-level
    parameter. Adapters therefore handle it differently -- see
    :class:`~model_provider.request.ChatRequest`.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class TextBlock:
    """Plain text."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolCallBlock:
    """A model's request to call a tool.

    Attributes:
        id: The provider's call id, echoed back on the result. Providers that
            omit ids get a synthesised one so correlation never silently breaks.
        name: The tool name.
        arguments: **Parsed** arguments. Providers disagree on the wire: OpenAI
            sends a JSON *string* (fragmented across stream chunks) while
            Anthropic and Gemini send an already-parsed object. Normalising here
            means no consumer ever has to know that.
    """

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResultBlock:
    """The result of a tool call, to be sent back to the model."""

    tool_call_id: str
    content: str


Block = TextBlock | ToolCallBlock | ToolResultBlock


@dataclass(frozen=True, slots=True)
class Message:
    """One turn in a conversation."""

    role: Role
    content: tuple[Block, ...]

    def text(self) -> str:
        """Concatenate every text block.

        Tool calls and results are excluded: this is the conversational text, and
        folding a tool's payload into it would corrupt the transcript.
        """
        return "".join(b.text for b in self.content if isinstance(b, TextBlock))


class FinishReason(enum.Enum):
    """A small closed set, with the provider's original kept alongside (D-6)."""

    STOP = "stop"
    """Natural completion."""

    LENGTH = "length"
    """Hit the output token cap."""

    TOOL_USE = "tool_use"
    """The model wants a tool called."""

    CONTENT_FILTER = "content_filter"
    """Stopped for policy or safety reasons."""

    ERROR = "error"
    """Ended abnormally."""

    UNKNOWN = "unknown"
    """A provider value we do not map. ``raw_finish_reason`` carries the detail."""


@dataclass(frozen=True, slots=True)
class Usage:
    """Token accounting. Every field optional, because providers omit different ones.

    Anthropic has no ``total_tokens`` field at all, so it is derived only when
    both parts are present -- never defaulted to zero, which would be
    indistinguishable from a genuine zero and would corrupt sums downstream.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None

    def is_complete(self) -> bool:
        """Whether every headline figure was actually reported.

        A caller computing cost must consult this: an incomplete ``Usage`` means
        the number is unknown, not that it was zero.
        """
        return (
            self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens is not None
        )

    def derive_total(self) -> Usage:
        """Return a copy with ``total_tokens`` filled in when derivable.

        Anthropic reports input and output but no total. Summing is safe only
        when both are known; otherwise this returns an equal, still-incomplete
        value rather than inventing a number.
        """
        if self.total_tokens is not None:
            return self
        if self.input_tokens is None or self.output_tokens is None:
            return self
        return Usage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.input_tokens + self.output_tokens,
            reasoning_tokens=self.reasoning_tokens,
            cache_read_tokens=self.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens,
        )


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """A completed (non-streamed) model response."""

    text: str
    blocks: tuple[Block, ...]
    tool_calls: tuple[ToolCallBlock, ...]
    finish_reason: FinishReason
    raw_finish_reason: str
    usage: Usage | None
    model: str
    provider: str

    @classmethod
    def build(
        cls,
        *,
        blocks: tuple[Block, ...],
        finish_reason: FinishReason,
        raw_finish_reason: str,
        usage: Usage | None,
        model: str,
        provider: str,
    ) -> ChatResponse:
        """Assemble a response, deriving ``text`` and ``tool_calls`` from blocks.

        Deriving rather than accepting them as arguments makes it impossible to
        construct a response whose flattened fields disagree with its blocks.
        """
        text = "".join(b.text for b in blocks if isinstance(b, TextBlock))
        calls = tuple(b for b in blocks if isinstance(b, ToolCallBlock))
        return cls(
            text=text,
            blocks=blocks,
            tool_calls=calls,
            finish_reason=finish_reason,
            raw_finish_reason=raw_finish_reason,
            usage=usage,
            model=model,
            provider=provider,
        )


# --------------------------------------------------------------------------- #
# Streaming (D-9)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TextDelta:
    """A fragment of output text."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolCallDelta:
    """A fragment of a tool call.

    ``arguments_fragment`` is a **partial JSON string**, not parseable on its
    own. OpenAI fragments ``arguments`` across chunks and Anthropic fragments
    ``input_json_delta.partial_json``; reassembly is the consumer's job via
    :class:`~model_provider.stream.ToolCallAccumulator`.
    """

    index: int
    id: str | None = None
    name: str | None = None
    arguments_fragment: str = ""


@dataclass(frozen=True, slots=True)
class UsageDelta:
    """Usage reported mid-stream, when the provider does so at all."""

    usage: Usage


@dataclass(frozen=True, slots=True)
class FinishDelta:
    """The stream's terminal signal, carrying the normalised reason."""

    finish_reason: FinishReason
    raw_finish_reason: str


StreamDelta = TextDelta | ToolCallDelta | UsageDelta | FinishDelta


@dataclass(frozen=True, slots=True)
class WireRequest:
    """An encoded HTTP request, ready for a transport to send.

    The abstraction produces this and never sends it (D-1). Keeping it a value
    means a test asserts on the exact bytes a provider would receive.
    """

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


@dataclass(frozen=True, slots=True)
class WireResponse:
    """A transport's reply, before any provider-specific parsing."""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    request_id: str | None = None
