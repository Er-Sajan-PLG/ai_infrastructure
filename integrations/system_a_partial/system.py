"""System A — partial adoption composition.

Composes:
- our runtime: react-agent-loop (TESTED)
- our memory: vector-memory-store (TESTED)
- external provider: scripted OpenAI-shaped LLM (double)
- external embedding model: hashing embedder (double)

This is a RAG-style system: documents are embedded, stored in our vector
store, retrieved by similarity, and passed to our agent loop for answer
generation. The external components are doubles, but the composition
boundary is real — our components consume them through public interfaces.
"""

from __future__ import annotations

import hashlib
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
    "catalog/memory",
    "integrations",
):
    sys.path.insert(0, str(_ROOT / _sub))

from agent_loop_end_to_end.scripted_transport import (  # noqa: E402
    MODEL,
    ScriptedTransport,
    openai_response,
)
from model_provider import (  # noqa: E402
    Provider,
)
from model_provider.providers import OpenAIProvider  # noqa: E402
from react_agent_loop import (  # noqa: E402
    Agent,
    AgentResult,
    ProviderCaller,
    RegistryDispatcher,
    run,
)
from tool_registry import ToolId, ToolRegistry  # noqa: E402
from vector_store import SearchResult, VectorStore  # noqa: E402


class HashingEmbedder:
    """Simple hashing embedder — deterministic, no ML.

    Maps text to a fixed-dimension vector using feature hashing.
    This is a double for a real embedding model, but the interface
    is the same: text in, vector out.
    """

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    def embed(self, text: str) -> list[float]:
        """Embed text into a fixed-dimension vector."""
        vec = [0.0] * self._dim
        for token in text.lower().split():
            h = hashlib.sha256(token.encode()).hexdigest()
            idx = int(h, 16) % self._dim
            sign = 1.0 if int(h, 16) % 2 == 0 else -1.0
            vec[idx] += sign
        # Normalize
        import math

        mag = math.sqrt(sum(x * x for x in vec))
        if mag > 0:
            vec = [x / mag for x in vec]
        return vec


@dataclass
class SystemA:
    """A wired system: our runtime + our memory + external provider + external embedder."""

    vector_store: VectorStore
    embedder: HashingEmbedder
    transport: ScriptedTransport
    provider: Provider
    caller: ProviderCaller
    dispatcher: RegistryDispatcher
    agent: Agent

    def index_documents(self, documents: dict[str, str]) -> None:
        """Index documents into our vector store."""
        for doc_id, text in documents.items():
            embedding = self.embedder.embed(text)
            self.vector_store.add(doc_id, embedding, {"text": text})

    def retrieve(self, query: str, k: int = 3) -> list[SearchResult]:
        """Retrieve relevant documents from our vector store."""
        query_embedding = self.embedder.embed(query)
        return self.vector_store.search(query_embedding, k=k)

    def answer(self, query: str, **kwargs: Any) -> AgentResult:
        """Answer a query using RAG: retrieve documents, augment prompt, run agent."""
        results = self.retrieve(query)
        context = "\n\n".join(
            f"[Document {r.id}]: {r.metadata.get('text', '')}" for r in results
        )
        augmented_query = (
            f"Answer the question using the context below.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}"
        )
        return run(
            augmented_query,
            agent=self.agent,
            model_caller=self.caller,
            dispatcher=self.dispatcher,
            **kwargs,
        )


def build_system_a(
    responses: Sequence[Any] | None = None,
    documents: dict[str, str] | None = None,
) -> SystemA:
    """Assemble System A with scripted transport and optional documents.

    Args:
        responses: WireResponse objects to return, one per model call.
        documents: Optional documents to index at build time.

    Returns:
        A SystemA whose parts a test can inspect.
    """
    scripted = (
        list(responses) if responses is not None else [openai_response(text="ok")]
    )

    # Build a registry with a "retrieve" tool
    registry = ToolRegistry()
    registry.register(
        tool_id=ToolId("rag", "retrieve"),
        description="Retrieve relevant documents for a query.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        callable_=lambda *, _query: "retrieved",
    )

    vector_store = VectorStore(max_size=1000)
    embedder = HashingEmbedder(dim=64)
    transport = ScriptedTransport(scripted)
    provider = OpenAIProvider()

    system = SystemA(
        vector_store=vector_store,
        embedder=embedder,
        transport=transport,
        provider=provider,
        caller=ProviderCaller(
            provider=provider,
            transport=transport,
            api_key="scripted-key",
            model=MODEL,
        ),
        dispatcher=RegistryDispatcher(registry),
        agent=Agent(model=MODEL, system="You are a RAG assistant."),
    )

    if documents:
        system.index_documents(documents)

    return system
