# Evaluation Framework Specification

**Status:** DESIGNED
**Version:** 1.0
**Related ADR:** ADR-0037

## 1. Overview

The Evaluation Framework provides a protocol-first, composable system for evaluating AI agent outputs, RAG pipelines, and tool interactions. It follows the repository's core principles: zero runtime dependencies, injected seams, protocol over concrete types, and deterministic evaluators first.

## 2. Core Protocols

### 2.1 EvaluationResult

```python
@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """The result of a single evaluation.

    Attributes:
        name: The evaluator's name.
        score: Normalized score in [0, 1]. 1 = perfect, 0 = complete failure.
        passed: Whether the evaluation passes the threshold.
        reasoning: Human-readable explanation (optional).
        metadata: Additional structured data (optional).
        threshold: The pass/fail threshold used.
    """
    name: str
    score: float
    passed: bool
    reasoning: str | None = None
    metadata: Mapping[str, Any] | None = None
    threshold: float = 0.5
```

### 2.2 Evaluator Protocol

```python
@runtime_checkable
class Evaluator(Protocol):
    """A single evaluation criterion.

    Implementations must be pure functions of their inputs — no hidden state,
    no network calls, no model calls unless explicitly injected via constructor.
    """

    @property
    def name(self) -> str:
        """Unique evaluator identifier."""

    def evaluate(
        self,
        *,
        input: Any,           # The input to the system (query, task, etc.)
        output: Any,          # The system's output (answer, tool result, etc.)
        context: Any | None = None,  # Additional context (retrieved docs, trace, etc.)
    ) -> EvaluationResult:
        """Evaluate the output against the input and context."""
```

### 2.3 EvaluationSuite

```python
@dataclass(frozen=True, slots=True)
class EvaluationSuite:
    """A named collection of evaluators with aggregation.

    Attributes:
        name: Suite identifier.
        evaluators: Ordered list of (evaluator, weight) pairs.
        aggregation: How to combine scores — "weighted_average", "pass_fail", "min", "max".
        pass_threshold: Overall pass threshold for the suite.
    """
    name: str
    evaluators: tuple[tuple[Evaluator, float], ...]
    aggregation: Literal["weighted_average", "pass_fail", "min", "max"] = "weighted_average"
    pass_threshold: float = 0.5

    def run(
        self,
        *,
        input: Any,
        output: Any,
        context: Any | None = None,
    ) -> SuiteResult:
        """Run all evaluators and aggregate."""
        ...

@dataclass(frozen=True, slots=True)
class SuiteResult:
    """Aggregated result of an evaluation suite."""
    suite_name: str
    overall_score: float
    overall_passed: bool
    results: tuple[EvaluationResult, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

## 3. Deterministic Evaluators (Zero Model Calls)

### 3.1 SchemaValidator

Validates that output conforms to a JSON Schema.

```python
class SchemaValidator:
    """Validates output against a JSON Schema (using tool_registry's subset)."""

    def __init__(self, schema: Mapping[str, Any], *, threshold: float = 1.0):
        ...

    def evaluate(self, *, input: Any, output: Any, context: Any = None) -> EvaluationResult:
        # Returns score 1.0 if valid, 0.0 if invalid
        # reasoning lists validation errors
```

### 3.2 LengthValidator

Validates output length constraints.

```python
class LengthValidator:
    """Validates output length in characters or tokens."""

    def __init__(
        self,
        *,
        min_chars: int | None = None,
        max_chars: int | None = None,
        min_tokens: int | None = None,
        max_tokens: int | None = None,
        tokenizer: Callable[[str], list[int]] | None = None,
        threshold: float = 1.0,
    ):
        ...

    def evaluate(self, *, input: Any, output: str, context: Any = None) -> EvaluationResult:
        # Score = 1.0 if within bounds, linear decay outside bounds
```

### 3.3 CitationCoverage

Evaluates whether RAG answers cite retrieved sources.

```python
class CitationCoverage:
    """Checks that answer references retrieved chunks."""

    def __init__(self, *, min_citations: int = 1, threshold: float = 0.5):
        ...

    def evaluate(
        self,
        *,
        input: str,           # The query
        output: RagAnswer,    # Answer with citations
        context: list[SearchResult] | None = None,  # Retrieved chunks
    ) -> EvaluationResult:
        # Score = min(1.0, actual_citations / min_citations)
        # reasoning = which chunks were cited vs available
```

### 3.4 ExactMatch

Exact string or normalized string matching.

```python
class ExactMatch:
    """Exact or normalized string matching for regression testing."""

    def __init__(
        self,
        expected: str,
        *,
        normalize: Callable[[str], str] | None = None,
        threshold: float = 1.0,
    ):
        ...

    def evaluate(self, *, input: Any, output: str, context: Any = None) -> EvaluationResult:
        # Score = 1.0 if match, 0.0 otherwise
```

### 3.5 ToolCallValidator

Validates that expected tool calls were made with correct arguments.

```python
class ToolCallValidator:
    """Validates tool call sequence against expected calls."""

    def __init__(
        self,
        expected_calls: list[tuple[str, Mapping[str, Any]]],  # (tool_name, args)
        *,
        order_matters: bool = True,
        threshold: float = 1.0,
    ):
        ...

    def evaluate(
        self,
        *,
        input: Any,
        output: AgentResult,  # Has steps with tool_calls
        context: Any = None,
    ) -> EvaluationResult:
        # Score based on match percentage
```

## 4. RAG Triad Evaluators (Require Injected ModelCaller)

These evaluators use an LLM to judge quality. The ModelCaller is injected at construction.

### 4.1 Faithfulness

> Does the answer stay faithful to the retrieved context?

```python
class Faithfulness:
    """LLM-as-judge: answer should not hallucinate beyond context."""

    def __init__(
        self,
        model_caller: ModelCaller,
        *,
        threshold: float = 0.7,
        prompt_template: str | None = None,
    ):
        ...

    def evaluate(
        self,
        *,
        input: str,           # The query
        output: str,          # The answer
        context: list[SearchResult],  # Retrieved chunks
    ) -> EvaluationResult:
        # Prompt: "Does the answer contain claims not supported by context?"
        # Score: 1.0 = fully faithful, 0.0 = hallucinated
```

### 4.2 AnswerRelevance

> Does the answer address the query?

```python
class AnswerRelevance:
    """LLM-as-judge: answer should be relevant to the query."""

    def __init__(
        self,
        model_caller: ModelCaller,
        *,
        threshold: float = 0.7,
    ):
        ...

    def evaluate(
        self,
        *,
        input: str,           # The query
        output: str,          # The answer
        context: Any = None,
    ) -> EvaluationResult:
        # Prompt: "Does this answer address the question?"
        # Score: 1.0 = directly answers, 0.0 = irrelevant
```

### 4.3 ContextPrecision

> Are the retrieved chunks relevant and in the right order?

```python
class ContextPrecision:
    """LLM-as-judge: top chunks should be relevant."""

    def __init__(
        self,
        model_caller: ModelCaller,
        *,
        threshold: float = 0.7,
    ):
        ...

    def evaluate(
        self,
        *,
        input: str,           # The query
        output: Any,          # Not used
        context: list[SearchResult],  # Retrieved chunks
    ) -> EvaluationResult:
        # For each chunk: "Is this relevant to the query?"
        # Score: average relevance, weighted by rank
```

### 4.4 ContextRecall

> Did retrieval find all necessary information?

```python
class ContextRecall:
    """LLM-as-judge: context should contain all info needed for answer."""

    def __init__(
        self,
        model_caller: ModelCaller,
        *,
        threshold: float = 0.7,
    ):
        ...

    def evaluate(
        self,
        *,
        input: str,           # The query
        output: str,          # The ground truth answer (if available) or generated answer
        context: list[SearchResult],  # Retrieved chunks
    ) -> EvaluationResult:
        # Prompt: "Can the answer be derived from the context?"
        # Score: 1.0 = all info present, 0.0 = critical info missing
```

## 5. Agent Evaluators (Require Injected ModelCaller)

### 5.1 LogicalConsistency

> Does the agent's reasoning follow logically?

```python
class LogicalConsistency:
    """LLM-as-judge: reasoning steps should be coherent."""

    def __init__(self, model_caller: ModelCaller, *, threshold: float = 0.7):
        ...

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,  # Has steps with text and tool_calls
        context: Any = None,
    ) -> EvaluationResult:
        # Prompt: "Is the reasoning coherent? Any contradictions?"
        # Score based on step-by-step consistency
```

### 5.2 ExecutionEfficiency

> Did the agent take unnecessary steps?

```python
class ExecutionEfficiency:
    """Measures step efficiency vs optimal."""

    def __init__(self, *, optimal_steps: int | None = None, threshold: float = 0.7):
        ...

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: Any = None,
    ) -> EvaluationResult:
        # If optimal_steps known: score = optimal / actual
        # If not: heuristic based on repetition, backtracking
```

### 5.3 PlanAdherence

> Did the agent follow its stated plan?

```python
class PlanAdherence:
    """LLM-as-judge: execution should follow plan."""

    def __init__(self, model_caller: ModelCaller, *, threshold: float = 0.7):
        ...

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: str | None = None,  # The plan (if extracted)
    ) -> EvaluationResult:
        # If plan in context: check adherence
        # If not: infer plan from first steps, check rest
```

### 5.4 ToolSelection

> Did the agent choose the right tools?

```python
class ToolSelection:
    """LLM-as-judge: tool choice should be appropriate."""

    def __init__(self, model_caller: ModelCaller, *, threshold: float = 0.7):
        ...

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: list[ToolDescriptor] | None = None,  # Available tools
    ) -> EvaluationResult:
        # For each tool call: "Was this the right tool for this step?"
```

### 5.5 ToolCalling

> Did the agent call tools correctly?

```python
class ToolCalling:
    """Validates tool call arguments and result interpretation."""

    def __init__(self, *, threshold: float = 0.7):
        ...

    def evaluate(
        self,
        *,
        input: str,
        output: AgentResult,
        context: ToolRegistry | None = None,  # For schema validation
    ) -> EvaluationResult:
        # Check: valid args per schema, results used appropriately
        # Score: combination of schema validity + result usage
```

## 6. LLM-as-Judge Adapter

```python
class LLMJudgeAdapter:
    """Wraps any LLM-backed evaluator with a standard interface.

    Allows swapping judge models without changing evaluator code.
    """

    def __init__(
        self,
        model_caller: ModelCaller,
        *,
        judge_prompt: str,
        parse_fn: Callable[[str], tuple[float, str]],  # output -> (score, reasoning)
        threshold: float = 0.5,
    ):
        ...

    def evaluate(self, *, input: Any, output: Any, context: Any = None) -> EvaluationResult:
        # Build prompt with input/output/context
        # Call model_caller
        # Parse score and reasoning
        # Return EvaluationResult
```

## 7. Aggregation

```python
def weighted_average(results: list[tuple[EvaluationResult, float]]) -> float:
    """Weighted average of scores."""
    total_weight = sum(w for _, w in results)
    if total_weight == 0:
        return 0.0
    return sum(r.score * w for r, w in results) / total_weight

def pass_fail(results: list[EvaluationResult], threshold: float = 0.5) -> bool:
    """All must pass."""
    return all(r.passed for r in results)

def min_score(results: list[EvaluationResult]) -> float:
    """Worst score."""
    return min(r.score for r in results) if results else 0.0

def max_score(results: list[EvaluationResult]) -> float:
    """Best score."""
    return max(r.score for r in results) if results else 0.0
```

## 8. TraceRecorder Integration

```python
def evaluate_trace(
    trace_path: Path,
    evaluators: list[Evaluator],
    *,
    model_caller: ModelCaller | None = None,
) -> list[EvaluationResult]:
    """Evaluate a full trace file."""
    # Parse JSONL trace
    # Reconstruct AgentResult / RagAnswer from trace
    # Run evaluators

def evaluate_steps(
    steps: list[Step],
    evaluators: list[Evaluator],
    *,
    model_caller: ModelCaller | None = None,
) -> list[EvaluationResult]:
    """Evaluate agent loop steps directly."""
    # Convert steps to AgentResult-like structure
    # Run evaluators
```

## 9. Pre-built Suites

```python
def rag_evaluation_suite(model_caller: ModelCaller | None = None) -> EvaluationSuite:
    """Standard RAG evaluation: citation coverage + RAG triad (if model_caller)."""
    evaluators = [
        (CitationCoverage(min_citations=1), 0.3),
    ]
    if model_caller:
        evaluators.extend([
            (Faithfulness(model_caller), 0.25),
            (AnswerRelevance(model_caller), 0.25),
            (ContextPrecision(model_caller), 0.1),
            (ContextRecall(model_caller), 0.1),
        ])
    return EvaluationSuite("rag_standard", tuple(evaluators))

def agent_evaluation_suite(model_caller: ModelCaller | None = None) -> EvaluationSuite:
    """Standard agent evaluation."""
    evaluators = [
        (ExecutionEfficiency(), 0.2),
        (ToolCalling(), 0.2),
    ]
    if model_caller:
        evaluators.extend([
            (LogicalConsistency(model_caller), 0.2),
            (PlanAdherence(model_caller), 0.2),
            (ToolSelection(model_caller), 0.2),
        ])
    return EvaluationSuite("agent_standard", tuple(evaluators))
```

## 10. Testing Requirements

### 9.1 Deterministic Evaluator Tests
- SchemaValidator: valid/invalid schemas, edge cases
- LengthValidator: char/token bounds, custom tokenizer
- CitationCoverage: zero/partial/full coverage
- ExactMatch: exact, normalized, case sensitivity
- ToolCallValidator: order matters/doesn't, partial match

### 9.2 RAG Triad Tests (with Mock ModelCaller)
- Faithfulness: hallucinated vs faithful answers
- AnswerRelevance: relevant vs irrelevant
- ContextPrecision: relevant top-k vs noise
- ContextRecall: complete vs missing context

### 9.3 Agent Evaluator Tests (with Mock ModelCaller)
- LogicalConsistency: coherent vs contradictory traces
- ExecutionEfficiency: optimal vs wasteful
- PlanAdherence: followed vs deviated
- ToolSelection: appropriate vs inappropriate
- ToolCalling: valid args vs invalid, result usage

### 9.4 Integration Tests
- Suite aggregation: weighted_average, pass_fail, min, max
- TraceRecorder integration: parse trace, evaluate
- Pre-built suites: rag_evaluation_suite, agent_evaluation_suite

## 11. Example Usage

```python
from evaluation import (
    CitationCoverage, ExactMatch, EvaluationSuite,
    rag_evaluation_suite, evaluate_trace
)
from model_provider import OpenAIProvider
from model_provider.transport import RecordingTransport

# Deterministic only
citation_eval = CitationCoverage(min_citations=1)
result = citation_eval.evaluate(
    input="What is AI?",
    output=RagAnswer(text="AI is...", citations=(Citation(chunk_id="doc#0", ...),)),
    context=[SearchResult(id="doc#0", ...)]
)

# With LLM judge (when ModelGateway available)
provider = OpenAIProvider()
transport = RecordingTransport(response=...)
model_caller = ProviderCaller(provider, transport, "test-key")

suite = rag_evaluation_suite(model_caller)
suite_result = suite.run(input="What is AI?", output=rag_answer, context=chunks)

# From trace file
results = evaluate_trace(Path("run.jsonl"), [citation_eval, ...])
```