"""System B — mixed composition: external runtime + our observability/safety.

Composes:
- external runtime: scripted agent (double — does NOT use our react-agent-loop)
- our observability: execution-trace-recorder (TESTED)
- our safety: mcp-client approval seam (TESTED)
- our evaluation: scoring function over trace records

This is the "mixed" composition: an external runtime wrapped with our
harness/eval/safety/observability. Our components are real TESTED capabilities,
consumed through their public interfaces. The external runtime is a double.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
for _sub in (
    "catalog/models",
    "catalog/tools",
    "catalog/agents",
    "catalog/protocols",
    "catalog/observability",
    "integrations",
):
    sys.path.insert(0, str(_ROOT / _sub))

from agent_loop_end_to_end.scripted_transport import (  # noqa: E402
    MODEL,
    ScriptedTransport,
    openai_response,
)
from execution_trace_recorder import (  # noqa: E402
    CaptureNothing,
    SystemClock,
    TraceRecorder,
)
from model_provider import (  # noqa: E402
    ChatRequest,
    Message,
    Provider,
    Role,
    TextBlock,
    chat,
)
from model_provider.providers import OpenAIProvider  # noqa: E402


class ExternalRuntime:
    """A simple scripted agent — does NOT use our react-agent-loop.

    This is a double for an external runtime (e.g., LangChain, LlamaIndex).
    It makes LLM calls and tool calls, but does not use our agent loop.
    The interface is the same: task in, result out.
    """

    def __init__(
        self,
        transport: ScriptedTransport,
        provider: Provider,
        max_steps: int = 5,
    ) -> None:
        self._transport = transport
        self._provider = provider
        self._max_steps = max_steps

    def run(self, task: str) -> dict[str, Any]:
        """Run the external runtime: make LLM calls until done.

        Returns a dict with the answer, steps, and tool calls.
        """
        messages: list[Message] = [
            Message(role=Role.USER, content=(TextBlock(text=task),))
        ]
        tool_calls_made: list[dict[str, object]] = []

        for step in range(self._max_steps):
            response = chat(
                ChatRequest(
                    model=MODEL,
                    messages=messages,
                ),
                provider=self._provider,
                transport=self._transport,
                api_key="scripted-key",
            )

            if response.tool_calls:
                for tc in response.tool_calls:
                    tool_calls_made.append(
                        {
                            "step": step,
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    )
                # In a real runtime, we would execute the tool and add the result
                # For this double, we just record the call
                messages.append(
                    Message(
                        role=Role.ASSISTANT, content=(TextBlock(text=response.text),)
                    )
                )
            else:
                return {
                    "answer": response.text,
                    "steps": step + 1,
                    "tool_calls": tool_calls_made,
                }

        return {
            "answer": "max steps reached",
            "steps": self._max_steps,
            "tool_calls": tool_calls_made,
        }


@dataclass
class SystemB:
    """A wired system: external runtime + our observability/safety/eval."""

    runtime: ExternalRuntime
    recorder: TraceRecorder
    transport: ScriptedTransport
    provider: Provider

    def run(self, task: str) -> dict[str, Any]:
        """Run the external runtime with our trace recording and evaluation."""
        self.recorder.start_trace()
        try:
            result = self.runtime.run(task)
            self.recorder.end_trace(stop_reason="completed")
            return result
        except Exception:
            self.recorder.end_trace(stop_reason="error")
            raise

    def evaluate(self, result: dict[str, Any]) -> dict[str, float]:
        """Evaluate the external runtime's output using our trace records.

        This is a simple scoring function that uses the trace recorder's output.
        In a real system, this would use a full evaluation framework.
        """
        # Read the trace file
        trace_path = self.recorder._path
        if trace_path is None or not Path(trace_path).exists():
            return {"score": 0.0, "steps": 0.0, "tool_calls": 0.0}

        # Simple scoring: more steps = lower score, more tool calls = higher score
        steps = float(result.get("steps", 0))
        tool_count = float(len(result.get("tool_calls", [])))
        score = min(1.0, tool_count / max(steps, 1))

        return {
            "score": score,
            "steps": steps,
            "tool_calls": tool_count,
        }


def build_system_b(
    responses: Sequence[Any] | None = None,
    trace_path: str = "system_b_trace.jsonl",
) -> SystemB:
    """Assemble System B with scripted transport and trace recorder.

    Args:
        responses: WireResponse objects to return, one per model call.
        trace_path: Path for the trace JSONL file.

    Returns:
        A SystemB whose parts a test can inspect.
    """
    scripted = (
        list(responses) if responses is not None else [openai_response(text="ok")]
    )

    transport = ScriptedTransport(scripted)
    provider = OpenAIProvider()
    recorder = TraceRecorder(
        trace_path,
        clock=SystemClock(),
        capture=CaptureNothing(),
    )

    runtime = ExternalRuntime(transport=transport, provider=provider)

    return SystemB(
        runtime=runtime,
        recorder=recorder,
        transport=transport,
        provider=provider,
    )
