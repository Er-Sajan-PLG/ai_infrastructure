"""A queued-response Transport, and OpenAI-shaped response builders.

Why this module exists rather than reusing a shipped double
-----------------------------------------------------------
``model-provider-abstraction`` ships ``RecordingTransport``, which holds exactly
**one** canned response and returns it on every ``send``. That is the right
double for testing an adapter and the wrong one for driving an agent loop: the
loop makes one model call per step and each step needs a different reply, so a
single-response double makes step two impossible to script.

Implementing the protocol here is also this integration's own evidence that the
seam is real. This file imports ``model_provider``'s **public types only** --
never an internal -- and satisfies ``Transport`` structurally, without
subclassing it or asking the package for permission. If the composition only
worked because the loop reached inside the provider package, that would be the
bug this integration exists to catch.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

from model_provider import Transport, WireRequest, WireResponse

__all__ = ["MODEL", "ScriptedTransport", "openai_response"]

#: The model name used throughout the integration. One constant so a mismatch
#: between what the caller sends and what the scripted response claims cannot
#: hide.
MODEL = "scripted-model"


class ScriptedTransport:
    """Returns a queued sequence of canned HTTP responses, recording requests.

    Attributes:
        requests: Every :class:`WireRequest` sent, in order. The integration's
            assertions read these -- the request body is the only place the
            composition's actual behaviour is observable.
    """

    def __init__(self, responses: Sequence[WireResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[WireRequest] = []

    @property
    def calls(self) -> int:
        """How many requests have been sent."""
        return len(self.requests)

    @property
    def last_request(self) -> WireRequest | None:
        """The most recent request, or ``None`` when nothing was sent."""
        return self.requests[-1] if self.requests else None

    def sent_body(self, index: int) -> dict[str, Any]:
        """Decode the JSON body of the request at ``index``, for assertions."""
        body: dict[str, Any] = json.loads(self.requests[index].body.decode("utf-8"))
        return body

    def send(self, request: WireRequest) -> WireResponse:
        """Return the next scripted response.

        Raises:
            AssertionError: The loop sent more requests than were scripted. That
                is a bug in the test, and it is better surfaced here than as a
                confusing ``IndexError`` from inside a list pop.
        """
        self.requests.append(request)
        if not self._responses:
            raise AssertionError(
                "the loop sent more requests than the transport was scripted for"
            )
        return self._responses.pop(0)

    def stream(self, request: WireRequest) -> Iterator[str]:
        """Unsupported: this integration exercises the non-streaming path only.

        Raising rather than silently yielding nothing is deliberate. A method
        that returns an empty iterator would look like a successful empty stream
        and would hide the fact that the loop never streams.
        """
        raise NotImplementedError(
            "this integration exercises the non-streaming path only"
        )


if TYPE_CHECKING:
    # mypy checks structural conformance to the Transport protocol right here.
    # It must sit BELOW the class: the annotation evaluates the class object, so
    # placing it above the definition is a used-before-definition error, not a
    # stylistic preference (found by mypy, not by review).
    _CONFORMS_TO_TRANSPORT: type[Transport] = ScriptedTransport


def openai_response(
    *,
    text: str | None = None,
    tool_calls: Sequence[tuple[str, str, dict[str, Any]]] = (),
    finish_reason: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> WireResponse:
    """Build an OpenAI Chat Completions response body.

    The shape is the one the adapter documents and parses: assistant text at
    ``choices[0].message.content``, tool calls at
    ``choices[0].message.tool_calls``, and -- the detail most likely to be got
    wrong -- ``function.arguments`` as a JSON **string**, not an object.

    Args:
        text: The assistant's text, if any.
        tool_calls: ``(id, name, arguments)`` triples to emit as tool calls.
        finish_reason: Overrides the derived reason. Defaults to ``tool_calls``
            when tool calls are present and ``stop`` otherwise, which is what
            the real API does.
        prompt_tokens: Input tokens, for the usage block.
        completion_tokens: Output tokens, for the usage block.

    Returns:
        A 200 :class:`WireResponse` whose body is the encoded JSON payload.
    """
    message: dict[str, Any] = {"role": "assistant", "content": text}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
            for call_id, name, arguments in tool_calls
        ]

    resolved_finish = (
        finish_reason
        if finish_reason is not None
        else ("tool_calls" if tool_calls else "stop")
    )

    payload: dict[str, Any] = {
        "id": "chatcmpl-scripted",
        "object": "chat.completion",
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": resolved_finish,
            }
        ],
    }

    if prompt_tokens is not None or completion_tokens is not None:
        prompt = prompt_tokens or 0
        completion = completion_tokens or 0
        payload["usage"] = {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }

    return WireResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
    )
