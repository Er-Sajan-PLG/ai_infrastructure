"""Minimal example: index two documents and answer a question.

Runs with no network and no model: the embedder is a tiny keyword counter
and the generator echoes the prompt back, so what the pipeline sends is
visible in the output. Replace both with real implementations to use the
pipeline for actual RAG.

Run directly:

    python basic_usage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_CATALOG = Path(__file__).resolve().parents[3]
for _sub in ("retrieval", "memory", "models"):
    sys.path.insert(0, str(_CATALOG / _sub))

from basic_rag_pipeline import BasicRagPipeline  # noqa: E402
from vector_store import VectorStore  # noqa: E402


class BagOfWordsEmbedder:
    """Deterministic 3-dim double: counts of 'galaxy', 'volcano', 'recipe'."""

    VOCAB = ("galaxy", "volcano", "recipe")

    def embed(self, text: str) -> list[float]:
        lowered = text.lower()
        return [float(lowered.count(word)) for word in self.VOCAB]


class EchoGenerator:
    """Returns the prompt back, so what the model would see is the output."""

    def generate(self, prompt: str) -> str:
        return f"[echo]\n{prompt}"


pipeline = BasicRagPipeline(
    embedder=BagOfWordsEmbedder(),
    store=VectorStore(max_size=100),
    generator=EchoGenerator(),
)

chunks_indexed = pipeline.index(
    {
        "astro-notes": "The galaxy catalog lists thousands of galaxies.",
        "field-notes": "The volcano erupted; a recipe book survived.",
    }
)
print(f"Indexed {chunks_indexed} chunk(s)\n")

answer = pipeline.answer("what does the galaxy catalog list?", k=2)
print(answer.text)
print()
print("Citations (retrieval evidence, ranked):")
for citation in answer.citations:
    print(f"  {citation.chunk_id}  score={citation.score:.4f}  doc={citation.doc_id}")
