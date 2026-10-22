"""Quickstart demonstration of the Evaluation Framework.

Shows:
- Deterministic evaluators (no model calls needed)
- RAG triad evaluators (with mock ModelCaller)
- Agent evaluators (with mock ModelCaller)
- EvaluationSuite composition
- TraceRecorder integration

Zero network calls in this example.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from basic_rag_pipeline import Citation, RagAnswer

# Use local implementations for demo (no network)
# In production, inject real ModelProvider + Transport
from evaluation_framework import (
    Evaluator,
    ExactMatch,
    LengthValidator,
    SchemaValidator,
    ToolCallValidator,
    agent_evaluation_suite,
    evaluate_rag,
    evaluate_steps,
    rag_evaluation_suite,
)
from react_agent_loop import AgentResult, StopReason

# Use local implementations for demo (no network)
# In production, inject real ModelProvider + Transport
from vector_store import SearchResult

# =======================================================================
# Mock ModelCaller for demonstration (no network)
# =======================================================================


class MockModelCaller:
    """Scripted model caller that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0

    def call(
        self,
        messages: Any,
        *,
        system: Any = None,
        tools: Any = (),
    ) -> Any:
        """Return a scripted response."""
        _ = messages, system, tools
        if self.index >= len(self.responses):
            response_text = "Default response"
        else:
            response_text = self.responses[self.index]
            self.index += 1

        # Return a minimal chat response-like object
        @dataclass
        class MockChatResponse:
            text: str
            blocks: tuple[Any, ...] = ()
            tool_calls: tuple[Any, ...] = ()
            usage: None = None
            model: str = "mock"
            provider: str = "mock"
            finish_reason: str = "stop"
            raw_finish_reason: str = "stop"

        return MockChatResponse(text=response_text)


# =======================================================================
# 1. Deterministic Evaluators (no model calls)
# =======================================================================


def demo_deterministic() -> None:
    print("=" * 60)
    print("1. Deterministic Evaluators")
    print("=" * 60)

    # Schema Validator
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
        "additionalProperties": False,
    }
    validator = SchemaValidator(schema)
    result = validator.evaluate(input={}, output={"name": "Alice", "age": 30})
    print(f"  SchemaValidator (valid): score={result.score}, passed={result.passed}")

    result = validator.evaluate(input={}, output={"name": "Bob"})
    print(
        f"  SchemaValidator (invalid): score={result.score}, passed={result.passed}, reason={result.reasoning}"
    )

    # Length Validator
    length_val = LengthValidator(min_chars=10, max_chars=100)
    result = length_val.evaluate(input="", output="This is a valid length string")
    print(f"  LengthValidator (valid): score={result.score}")

    result = length_val.evaluate(input="", output="Short")
    print(
        f"  LengthValidator (too short): score={result.score}, reason={result.reasoning}"
    )

    # Exact Match
    exact = ExactMatch("expected output", normalize=str.strip)
    result = exact.evaluate(input="", output="expected output")
    print(f"  ExactMatch (match): score={result.score}")

    result = exact.evaluate(input="", output="different output")
    print(f"  ExactMatch (mismatch): score={result.score}")

    # Tool Call Validator
    tool_val = ToolCallValidator(
        expected_calls=[("add", {"a": 1, "b": 2}), ("multiply", {"x": 3, "y": 4})],
        order_matters=True,
    )

    @dataclass
    class MockStep:
        tool_calls: tuple[Any, ...]
        index: int = 0
        text: str = ""

    @dataclass
    class MockCall:
        name: str
        arguments: dict[str, Any]

    @dataclass
    class MockAgentResult:
        steps: tuple[Any, ...]

    output = MockAgentResult(
        steps=(
            MockStep(
                tool_calls=(
                    MockCall("add", {"a": 1, "b": 2}),
                    MockCall("multiply", {"x": 3, "y": 4}),
                )
            ),
        )
    )
    result = tool_val.evaluate(input="", output=output)
    print(f"  ToolCallValidator (match): score={result.score}")

    output = MockAgentResult(
        steps=(MockStep(tool_calls=(MockCall("add", {"a": 1, "b": 2}),)),)
    )
    result = tool_val.evaluate(input="", output=output)
    print(f"  ToolCallValidator (partial): score={result.score}")


# =======================================================================
# 2. RAG Evaluation (with mock ModelCaller)
# =======================================================================


def demo_rag_evaluation() -> None:
    print("\n" + "=" * 60)
    print("2. RAG Evaluation Suite")
    print("=" * 60)

    # Mock ModelCaller that returns specific judge scores
    model_caller = MockModelCaller(
        [
            "SCORE: 0.9\nREASONING: Answer is faithful to context",
            "SCORE: 0.8\nREASONING: Answer addresses the query well",
            "SCORE: 0.7\nREASONING: Most chunks are relevant",
            "SCORE: 0.6\nREASONING: Some info missing from context",
        ]
    )

    # Create RAG evaluation suite
    suite = rag_evaluation_suite(model_caller)
    print(f"  Suite: {suite.name}, evaluators: {len(suite.evaluators)}")

    # Mock RAG output
    chunks = [
        SearchResult(
            id="doc#0",
            score=0.9,
            metadata={"text": "AI infrastructure provides verification"},
        ),
        SearchResult(id="doc#1", score=0.7, metadata={"text": "Cooking requires heat"}),
    ]
    citations = (Citation(chunk_id="doc#0", doc_id="doc", score=0.9),)
    rag_answer = RagAnswer(
        text="AI infrastructure provides verification and modularity.",
        citations=citations,
    )

    # Evaluate
    result = suite.run(
        input="What is AI infrastructure?", output=rag_answer, context=chunks
    )
    print(
        f"  Overall score: {result.overall_score:.2f}, passed: {result.overall_passed}"
    )
    for r in result.results:
        print(f"    {r.name}: {r.score:.2f} ({'PASS' if r.passed else 'FAIL'})")


# =======================================================================
# 3. Agent Evaluation (with mock ModelCaller)
# =======================================================================


def demo_agent_evaluation() -> None:
    print("\n" + "=" * 60)
    print("3. Agent Evaluation Suite")
    print("=" * 60)

    model_caller = MockModelCaller(
        [
            "SCORE: 0.9\nREASONING: Coherent reasoning",
            "SCORE: 0.8\nREASONING: Efficient execution",
            "SCORE: 0.7\nREASONING: Followed plan",
            "SCORE: 0.8\nREASONING: Good tool selection",
            "SCORE: 0.9\nREASONING: Valid calls, results used well",
        ]
    )

    # Create mock agent result
    @dataclass
    class MockToolCall:
        id: str
        name: str
        arguments: dict[str, Any]

    @dataclass
    class MockStep:
        index: int
        text: str
        tool_calls: tuple[Any, ...]
        dispatches: tuple[Any, ...] = ()

    @dataclass
    class MockUsage:
        input_tokens: int = 100
        output_tokens: int = 50

    agent_result: Any = AgentResult(
        reason=StopReason.FINAL_ANSWER,
        final_text="The calculation is complete: 42",
        steps=cast(
            Any,
            (
                MockStep(
                    index=1,
                    text="I need to add 20 and 22",
                    tool_calls=(MockToolCall("call1", "add", {"a": 20, "b": 22}),),
                ),
                MockStep(index=2, text="The result is 42", tool_calls=()),
            ),
        ),
        usage=cast(Any, MockUsage()),
        messages=(),
    )

    # Note: agent_evaluation_suite expects ToolRegistry for ToolCalling
    # We'll skip ToolRegistry for this demo
    suite = agent_evaluation_suite(model_caller, optimal_steps=2)
    result = suite.run(input="Calculate 20 + 22", output=agent_result)
    print(
        f"  Overall score: {result.overall_score:.2f}, passed: {result.overall_passed}"
    )
    for r in result.results:
        print(f"    {r.name}: {r.score:.2f} ({'PASS' if r.passed else 'FAIL'})")


# =======================================================================
# 4. Direct RAG Evaluation
# =======================================================================


def demo_direct_rag() -> None:
    print("\n" + "=" * 60)
    print("4. Direct RAG Evaluation")
    print("=" * 60)

    model_caller = MockModelCaller(
        [
            "SCORE: 0.9\nREASONING: Faithful",
            "SCORE: 0.8\nREASONING: Relevant",
            "SCORE: 0.7\nREASONING: Precise",
            "SCORE: 0.6\nREASONING: Some recall gaps",
        ]
    )

    chunks = [
        SearchResult(
            id="doc#0",
            score=0.9,
            metadata={"text": "AI infrastructure provides verification"},
        ),
        SearchResult(id="doc#1", score=0.7, metadata={"text": "Cooking requires heat"}),
    ]
    citations = (Citation(chunk_id="doc#0", doc_id="doc", score=0.9),)
    rag_answer = RagAnswer(
        text="AI infrastructure provides verification.", citations=citations
    )

    suite = rag_evaluation_suite(model_caller)
    results = evaluate_rag(
        query="What is AI infrastructure?",
        answer=rag_answer.text,
        citations=list(citations),
        retrieved_chunks=chunks,
        evaluators=[e for e, _ in suite.evaluators],
    )

    for r in results:
        print(
            f"  {r.name}: {r.score:.2f} ({'PASS' if r.passed else 'FAIL'}) - {r.reasoning}"
        )


# =======================================================================
# 5. Direct Agent Step Evaluation
# =======================================================================


def demo_direct_agent() -> None:
    print("\n" + "=" * 60)
    print("5. Direct Agent Step Evaluation")
    print("=" * 60)

    model_caller = MockModelCaller(
        [
            "SCORE: 0.9\nREASONING: Consistent",
            "SCORE: 0.8\nREASONING: Efficient",
        ]
    )

    @dataclass
    class MockStep:
        index: int
        text: str
        tool_calls: tuple[Any, ...] = ()

    steps = [
        MockStep(index=1, text="I'll use the add tool", tool_calls=()),
        MockStep(index=2, text="Result is 42", tool_calls=()),
    ]

    from evaluation_framework.evaluators.agent import (
        ExecutionEfficiency,
        LogicalConsistency,
    )

    evaluators: list[Evaluator] = [
        LogicalConsistency(model_caller),
        ExecutionEfficiency(model_caller=model_caller, optimal_steps=2),
    ]

    results = evaluate_steps(steps, evaluators, task="Calculate 20 + 22")
    for r in results:
        print(f"  {r.name}: {r.score:.2f} ({'PASS' if r.passed else 'FAIL'})")


# =======================================================================
# Main
# =======================================================================

if __name__ == "__main__":
    demo_deterministic()
    demo_rag_evaluation()
    demo_agent_evaluation()
    demo_direct_rag()
    demo_direct_agent()
    print("\n" + "=" * 60)
    print("All demos completed successfully!")
    print("=" * 60)
