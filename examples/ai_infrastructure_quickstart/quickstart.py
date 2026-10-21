"""Quickstart demonstration of the unified ai_infrastructure package.

Demonstrates:
- Tool declaration and execution via ToolRegistry
- In-memory cosine vector search via VectorStore
- RAG pipeline execution via BasicRagPipeline
- Agent execution loop via Agent and run()
- Trajectory tracing via TraceRecorder

Zero runtime dependencies. Pure Python standard library only.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_infrastructure import (  # noqa: E402
    Agent,
    BasicRagPipeline,
    CaptureNothing,
    ChatResponse,
    FinishReason,
    RegistryDispatcher,
    TextBlock,
    ToolId,
    ToolRegistry,
    TraceRecorder,
    VectorStore,
    __version__,
    run,
)


def main() -> None:
    print(f"=== ai_infrastructure v{__version__} Unified Quickstart ===")

    # 1. Tool Registry
    print("\n1. Initializing ToolRegistry...")
    registry = ToolRegistry()
    add_tool_id = ToolId("math", "add")
    registry.register(
        tool_id=add_tool_id,
        description="Add two numbers",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        callable_=lambda *, a, b: a + b,
    )
    result = registry.invoke(add_tool_id, {"a": 20, "b": 22})
    assert result.ok
    print(f"   Invoked tool 'math:add': result = {result.value}")

    # 2. Vector Memory Store
    print("\n2. Initializing VectorStore...")
    store = VectorStore(max_size=50)
    store.add(
        "doc-1", [0.9, 0.1], metadata={"text": "AI infrastructure is foundational."}
    )
    store.add(
        "doc-2", [0.1, 0.9], metadata={"text": "Cooking pasta requires boiling water."}
    )
    search_res = store.search([0.9, 0.1], k=1)
    assert len(search_res) == 1
    print(
        f"   Vector search match: id={search_res[0].id}, score={search_res[0].score:.3f}"
    )

    # 3. Basic RAG Pipeline
    print("\n3. Running BasicRagPipeline...")

    class SimpleEmbedder:
        def embed(self, text: str) -> list[float]:
            return [0.9 if "infra" in text.lower() else 0.1, 0.1]

    class SimpleGenerator:
        def generate(self, prompt: str) -> str:
            return "Generated answer grounded in retrieved infrastructure context."

    rag_store = VectorStore(max_size=50)
    pipeline = BasicRagPipeline(
        embedder=SimpleEmbedder(),
        store=rag_store,
        generator=SimpleGenerator(),
    )
    pipeline.index(
        {"doc-ai": "AI infrastructure provides verification and modularity."}
    )
    answer = pipeline.answer("Tell me about infrastructure.")
    print(f"   RAG Answer: {answer.text}")
    print(f"   Citations: {[c.chunk_id for c in answer.citations]}")

    # 4. Agent Loop Execution
    print("\n4. Running ReAct Agent Loop...")
    dispatcher = RegistryDispatcher(registry)

    class ScriptedCaller:
        def call(
            self, messages: Any, *, system: Any = None, tools: Any = ()
        ) -> ChatResponse:
            return ChatResponse.build(
                blocks=(TextBlock(text="The calculation is complete."),),
                finish_reason=FinishReason.STOP,
                raw_finish_reason="stop",
                usage=None,
                model="mock-model",
                provider="scripted",
            )

    agent = Agent(model="mock-model")
    agent_res = run(
        "Calculate 20 + 22",
        agent=agent,
        model_caller=ScriptedCaller(),
        dispatcher=dispatcher,
        max_steps=3,
    )
    print(f"   Agent finished: ok={agent_res.ok}, text='{agent_res.final_text}'")

    # 5. Execution Trace Recorder
    print("\n5. Recording Telemetry with TraceRecorder...")
    with tempfile.TemporaryDirectory() as tmpdir:
        trace_path = Path(tmpdir) / "quickstart_trace.jsonl"
        with TraceRecorder(trace_path, capture=CaptureNothing()) as recorder:
            recorder.start_trace()
            with recorder.model_call(model="mock-model") as call:
                call.succeed(input_tokens=15, output_tokens=8, usage_provided=True)
            recorder.end_trace(stop_reason="finished")
        records = trace_path.read_text(encoding="utf-8").strip().splitlines()
        print(f"   Trace file written successfully ({len(records)} records).")

    print("\n=== Quickstart Finished Successfully (0 network calls, 100% stdlib) ===")


if __name__ == "__main__":
    main()
