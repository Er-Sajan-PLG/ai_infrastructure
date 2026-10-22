"""ai_infrastructure — An independent AI infrastructure laboratory & reusable engineering foundation.

An independent, evolving AI infrastructure foundation: research repository, architectural
knowledge base, implementation library, interoperability layer, evaluation environment, and
reusable engineering foundation for AI systems.

Consumable piece-by-piece or via this unified package interface.
Standard library only; zero runtime dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure catalog category directories are discoverable for bare package imports
# per charter §31 and ADR-0017 / ADR-0036.
_ROOT = Path(__file__).resolve().parent
_CATALOG_CANDIDATES = (
    _ROOT / "catalog",
    _ROOT.parent / "catalog",
)
_CATALOG_DIR: Path | None = None
for _cand in _CATALOG_CANDIDATES:
    if _cand.is_dir():
        _CATALOG_DIR = _cand
        break

if _CATALOG_DIR is not None:
    _CATEGORIES = (
        "tools",
        "models",
        "agents",
        "observability",
        "protocols",
        "deployment",
        "memory",
        "retrieval",
        "evaluation",
        "guardrails",
    )
    for _cat in _CATEGORIES:
        _cat_path = str(_CATALOG_DIR / _cat)
        if _cat_path not in sys.path and (_CATALOG_DIR / _cat).is_dir():
            sys.path.insert(0, _cat_path)

# 1. Tools: tool-registry
# 8. Retrieval: basic-rag-pipeline
from basic_rag_pipeline import (  # noqa: E402
    BasicRagPipeline,
    Chunk,
    Citation,
    Embedder,
    Generator,
    ProviderGenerator,
    RagAnswer,
    build_prompt,
    chunk_text,
)

# 9. Evaluation: evaluation-framework
from evaluation_framework import (  # noqa: E402
    AnswerRelevance,
    CitationCoverage,
    ContextPrecision,
    ContextRecall,
    EvaluationResult,
    EvaluationSuite,
    Evaluator,
    ExactMatch,
    ExecutionEfficiency,
    Faithfulness,
    LengthValidator,
    LLMJudgeAdapter,
    LogicalConsistency,
    PlanAdherence,
    SchemaValidator,
    SuiteResult,
    ToolCalling,
    ToolCallValidator,
    ToolSelection,
    agent_evaluation_suite,
    evaluate_rag,
    evaluate_steps,
    evaluate_trace,
    rag_evaluation_suite,
)

# 4. Observability: execution-trace-recorder
from execution_trace_recorder import (  # noqa: E402
    Bounds,
    CaptureEverything,
    CaptureNothing,
    CapturePolicy,
    Clock,
    ModelCallHandle,
    Outcome,
    RecordKind,
    SystemClock,
    ToolCallHandle,
    TraceRecord,
    TraceRecorder,
    TraceRecorderError,
    WriteFailures,
)

# 5. Protocols: mcp-client
from mcp_client import (  # noqa: E402
    AllowAllApprovals,
    ApprovalPolicy,
    DenyAllApprovals,
    MCPClient,
    MCPError,
    MCPProtocolError,
    MCPServerDiedError,
    MCPTimeoutError,
    MCPToolFailure,
    MCPTransportError,
    ProjectionReport,
    project_tools,
)

# 2. Models: model-provider-abstraction
from model_provider import (  # noqa: E402
    AuthenticationError,
    BadRequestError,
    Block,
    ChatRequest,
    ChatResponse,
    ContentPolicyError,
    ContextLengthError,
    FinishDelta,
    FinishReason,
    Message,
    Provider,
    ProviderError,
    ProviderStream,
    ProviderTimeoutError,
    RateLimitError,
    RecordingTransport,
    Role,
    ServerError,
    StreamDelta,
    TextBlock,
    TextDelta,
    ToolCallAccumulator,
    ToolCallBlock,
    ToolCallDelta,
    ToolResultBlock,
    TranslationError,
    Transport,
    TransportError,
    Usage,
    UsageDelta,
    WireRequest,
    WireResponse,
    chat,
    collect_stream,
    stream,
)
from model_provider.providers import (  # noqa: E402
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
)

# 3. Agents: react-agent-loop
from react_agent_loop import (  # noqa: E402
    Agent,
    AgentResult,
    ProviderCaller,
    RegistryDispatcher,
    RepetitionTracker,
    StopReason,
    UnactionableToolError,
    run,
)

# 6. Deployment: infrastructure-scanner
from scanner import (  # noqa: E402
    INFRASTRUCTURE_LAYERS,
    INFRASTRUCTURE_TAXONOMY,
    InfraComponent,
    InfrastructureMap,
    InfrastructureScanner,
    scan_keywords,
    validate_taxonomy,
)
from tool_registry import (  # noqa: E402
    DuplicateToolError,
    FailureKind,
    InvalidSchemaError,
    Tool,
    ToolDescriptor,
    ToolFailure,
    ToolId,
    ToolNotFoundError,
    ToolRegistry,
    ToolRegistryError,
    ToolResult,
)

# 7. Memory: vector-memory-store
from vector_store import (  # noqa: E402
    SearchResult,
    VectorStore,
)

# 10. Guardrails: guardrails (deterministic half)
from guardrails import (  # noqa: E402
    AllowlistValidator,
    DenylistValidator,
    GuardrailDecision,
    GuardrailOutcome,
    GuardrailPolicy,
    JsonSchemaValidator,
    LengthBoundValidator,
    OneLineValidator,
    PiiKind,
    PIIValidator,
    Rails,
    RegexMatchValidator,
    Severity,
    ValidationResult,
    Validator,
    ValidJsonValidator,
)

__version__ = "0.0.1"

__all__ = [
    "INFRASTRUCTURE_LAYERS",
    "INFRASTRUCTURE_TAXONOMY",
    "Agent",
    "AgentResult",
    "AllowAllApprovals",
    "AllowlistValidator",
    "AnswerRelevance",
    "AnthropicProvider",
    "ApprovalPolicy",
    "AuthenticationError",
    "BadRequestError",
    "BasicRagPipeline",
    "Block",
    "Bounds",
    "CaptureEverything",
    "CaptureNothing",
    "CapturePolicy",
    "ChatRequest",
    "ChatResponse",
    "Chunk",
    "Citation",
    "CitationCoverage",
    "Clock",
    "ContentPolicyError",
    "ContextLengthError",
    "ContextPrecision",
    "ContextRecall",
    "DenyAllApprovals",
    "DenylistValidator",
    "DuplicateToolError",
    "Embedder",
    "EvaluationResult",
    "EvaluationSuite",
    "Evaluator",
    "ExactMatch",
    "ExecutionEfficiency",
    "FailureKind",
    "Faithfulness",
    "FinishDelta",
    "FinishReason",
    "GeminiProvider",
    "Generator",
    "GuardrailDecision",
    "GuardrailOutcome",
    "GuardrailPolicy",
    "InfraComponent",
    "InfrastructureMap",
    "InfrastructureScanner",
    "InvalidSchemaError",
    "JsonSchemaValidator",
    "LLMJudgeAdapter",
    "LengthBoundValidator",
    "LengthValidator",
    "LogicalConsistency",
    "MCPClient",
    "MCPError",
    "MCPProtocolError",
    "MCPServerDiedError",
    "MCPTimeoutError",
    "MCPToolFailure",
    "MCPTransportError",
    "Message",
    "ModelCallHandle",
    "OneLineValidator",
    "OpenAIProvider",
    "Outcome",
    "PIIValidator",
    "PiiKind",
    "PlanAdherence",
    "ProjectionReport",
    "Provider",
    "ProviderCaller",
    "ProviderError",
    "ProviderGenerator",
    "ProviderStream",
    "ProviderTimeoutError",
    "RagAnswer",
    "Rails",
    "RateLimitError",
    "RecordKind",
    "RecordingTransport",
    "RegexMatchValidator",
    "RegistryDispatcher",
    "RepetitionTracker",
    "Role",
    "SchemaValidator",
    "SearchResult",
    "ServerError",
    "Severity",
    "StopReason",
    "StreamDelta",
    "SuiteResult",
    "SystemClock",
    "TextBlock",
    "TextDelta",
    "Tool",
    "ToolCallAccumulator",
    "ToolCallBlock",
    "ToolCallDelta",
    "ToolCallHandle",
    "ToolCallValidator",
    "ToolCalling",
    "ToolDescriptor",
    "ToolFailure",
    "ToolId",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolResult",
    "ToolResultBlock",
    "ToolSelection",
    "TraceRecord",
    "TraceRecorder",
    "TraceRecorderError",
    "TranslationError",
    "Transport",
    "TransportError",
    "UnactionableToolError",
    "Usage",
    "UsageDelta",
    "ValidJsonValidator",
    "ValidationResult",
    "Validator",
    "VectorStore",
    "WireRequest",
    "WireResponse",
    "WriteFailures",
    "__version__",
    "agent_evaluation_suite",
    "build_prompt",
    "chat",
    "chunk_text",
    "collect_stream",
    "evaluate_rag",
    "evaluate_steps",
    "evaluate_trace",
    "exact_match_suite",
    "length_suite",
    "project_tools",
    "rag_evaluation_suite",
    "run",
    "scan_keywords",
    "schema_validation_suite",
    "stream",
    "tool_call_suite",
    "validate_taxonomy",
]
