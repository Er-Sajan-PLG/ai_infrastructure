"""Tests for the unified ai_infrastructure top-level package API.

Verifies that the unified package interface exposes all 8 tested capabilities:
1. tools: ToolRegistry, ToolId
2. models: Provider, OpenAIProvider, AnthropicProvider, GeminiProvider, ChatRequest
3. agents: Agent, run, StopReason
4. observability: TraceRecorder, CapturePolicy
5. protocols: MCPClient, ApprovalPolicy
6. deployment: InfrastructureScanner, InfrastructureMap
7. memory: VectorStore, SearchResult
8. retrieval: BasicRagPipeline, chunk_text, build_prompt
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_infrastructure
from ai_infrastructure import (
    Agent,
    AllowAllApprovals,
    AnthropicProvider,
    ApprovalPolicy,
    BasicRagPipeline,
    CaptureNothing,
    ChatRequest,
    ChatResponse,
    DenyAllApprovals,
    FinishReason,
    GeminiProvider,
    InfrastructureMap,
    InfrastructureScanner,
    MCPClient,
    Message,
    OpenAIProvider,
    Provider,
    Role,
    SearchResult,
    StopReason,
    TextBlock,
    ToolId,
    ToolRegistry,
    TraceRecorder,
    VectorStore,
    __version__,
    build_prompt,
    chunk_text,
    run,
)


def test_package_metadata() -> None:
    assert __version__ == "0.0.1"
    assert "ToolRegistry" in ai_infrastructure.__all__
    assert "Provider" in ai_infrastructure.__all__
    assert "Agent" in ai_infrastructure.__all__
    assert "TraceRecorder" in ai_infrastructure.__all__
    assert "MCPClient" in ai_infrastructure.__all__
    assert "InfrastructureScanner" in ai_infrastructure.__all__
    assert "VectorStore" in ai_infrastructure.__all__
    assert "BasicRagPipeline" in ai_infrastructure.__all__


def test_tool_registry_via_unified_api() -> None:
    registry = ToolRegistry()
    tool_id = ToolId("math", "multiply")
    registry.register(
        tool_id=tool_id,
        description="Multiply two integers",
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
            "additionalProperties": False,
        },
        callable_=lambda *, x, y: x * y,
    )
    tool = registry.get(tool_id)
    assert tool is not None
    assert tool.description == "Multiply two integers"
    result = registry.invoke(tool_id, {"x": 6, "y": 7})
    assert result.ok
    assert result.value == 42


def test_model_provider_types_via_unified_api() -> None:
    req = ChatRequest(
        messages=[
            Message(role=Role.USER, content=(TextBlock(text="Hello!"),)),
        ],
        model="gpt-4o",
    )
    assert len(req.messages) == 1
    assert req.messages[0].role == Role.USER

    # Providers can be constructed without network calls
    openai = OpenAIProvider()
    anthropic = AnthropicProvider()
    gemini = GeminiProvider()
    assert isinstance(openai, Provider)
    assert isinstance(anthropic, Provider)
    assert isinstance(gemini, Provider)


def test_agent_loop_via_unified_api() -> None:
    agent = Agent(model="test-model")
    registry = ToolRegistry()
    dispatcher = ai_infrastructure.RegistryDispatcher(registry)

    class MockCaller:
        def call(
            self, messages: Any, *, system: Any = None, tools: Any = ()
        ) -> ChatResponse:
            return ChatResponse.build(
                blocks=(TextBlock(text="Final answer"),),
                finish_reason=FinishReason.STOP,
                raw_finish_reason="stop",
                usage=None,
                model="test-model",
                provider="mock",
            )

    result = run(
        "Hello",
        agent=agent,
        model_caller=MockCaller(),
        dispatcher=dispatcher,
        max_steps=2,
    )
    assert result.ok
    assert result.final_text == "Final answer"
    assert result.reason == StopReason.FINAL_ANSWER


def test_mcp_client_types_via_unified_api() -> None:
    assert issubclass(AllowAllApprovals, ApprovalPolicy)
    assert issubclass(DenyAllApprovals, ApprovalPolicy)
    assert hasattr(MCPClient, "from_command")


def test_vector_store_via_unified_api() -> None:
    store = VectorStore(max_size=10)
    store.add("doc-1", [1.0, 0.0], metadata={"topic": "ai"})
    store.add("doc-2", [0.0, 1.0], metadata={"topic": "cooking"})

    results = store.search([1.0, 0.0], k=1)
    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].id == "doc-1"
    assert results[0].score == pytest.approx(1.0)


def test_trace_recorder_via_unified_api() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        trace_file = Path(tmpdir) / "trace.jsonl"
        with TraceRecorder(trace_file, capture=CaptureNothing()) as recorder:
            recorder.start_trace()
            with recorder.model_call(model="test-model") as call:
                call.succeed(input_tokens=10, output_tokens=5, usage_provided=True)
            recorder.end_trace(stop_reason="finished")

        assert trace_file.exists()
        lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3  # trace_start, model_call, trace_end


class _MockEmbedder:
    def embed(self, text: str) -> list[float]:
        return [1.0 if "one" in text else 0.0, 1.0]


class _MockGenerator:
    def generate(self, prompt: str) -> str:
        return "Answer based on context."


def test_basic_rag_pipeline_via_unified_api() -> None:
    chunks = chunk_text(
        "Paragraph one. Paragraph two.", doc_id="doc-1", size=20, overlap=5
    )
    assert len(chunks) >= 2

    prompt = build_prompt(
        query="test",
        results=[SearchResult(id="c1", score=0.9, metadata={"text": "Chunk 1 text"})],
    )
    assert "Chunk 1 text" in prompt

    store = VectorStore(max_size=100)
    pipeline = BasicRagPipeline(
        embedder=_MockEmbedder(),
        store=store,
        generator=_MockGenerator(),
    )
    pipeline.index({"doc-1": "Paragraph one content."})
    ans = pipeline.answer("query about one")
    assert ans.text == "Answer based on context."
    assert len(ans.citations) >= 1


def test_scanner_via_unified_api() -> None:
    scanner = InfrastructureScanner()
    result = scanner.scan(Path(__file__).resolve().parents[1])
    assert isinstance(result, InfrastructureMap)
    assert result.total_components >= 1
    assert result.layers_covered >= 1


def test_quickstart_example_runs() -> None:
    from examples.ai_infrastructure_quickstart.quickstart import main as quickstart_main

    quickstart_main()
