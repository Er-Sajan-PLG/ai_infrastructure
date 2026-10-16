"""Benchmark: composed systems vs monolithic baselines.

Measures latency and token accounting for our three composed systems
(System C, System A, System B) against two monolithic baselines:

- ``monolithic`` — the bare single-call chain (no tools, no memory).
- ``monolithic_rag`` — the inlined retrieval chain: retrieval, prompt
  construction and the model call inside one class.

Both baselines model monolithic shapes observed in the study corpus
(``study_pipeline/studied_repos/``); no third-party framework is installed or
executed (zero-runtime-deps; ADR-0021 Decision 1). What varies between rows
is composition, not functionality for its own sake: the scripted transport is
shared, so the measured difference is per-layer overhead.

Records methodology and environment per charter §19.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
for _sub in (
    "catalog/models",
    "catalog/tools",
    "catalog/agents",
    "catalog/memory",
    "catalog/observability",
    "integrations",
):
    sys.path.insert(0, str(_ROOT / _sub))

from agent_loop_end_to_end.scripted_transport import (  # noqa: E402
    MODEL,
    ScriptedTransport,
    openai_response,
)
from model_provider import ChatRequest, Message, Role, TextBlock, chat  # noqa: E402
from model_provider.providers import OpenAIProvider  # noqa: E402

#: Fixture token counts declared on every scripted response. The scripted
#: transport performs no tokenization; these numbers exercise each system's
#: usage *accounting* path and must not be read as measured token economics.
FIXTURE_PROMPT_TOKENS = 30
FIXTURE_COMPLETION_TOKENS = 5


def _text_response() -> Any:
    """A scripted response carrying the fixture usage block."""
    return openai_response(
        text="Paris",
        prompt_tokens=FIXTURE_PROMPT_TOKENS,
        completion_tokens=FIXTURE_COMPLETION_TOKENS,
    )


class MonolithicBaseline:
    """A simple monolithic agent — no composition, no modularity.

    This is the first baseline: a single class that does one thing inline.
    It is intentionally simple and not modular.
    """

    def __init__(self, transport: ScriptedTransport, provider: OpenAIProvider) -> None:
        self._transport = transport
        self._provider = provider

    def run(self, task: str) -> dict[str, Any]:
        """Run the monolithic agent: one LLM call, no tools, no memory."""
        start = time.perf_counter()
        response = chat(
            ChatRequest(
                model=MODEL,
                messages=[Message(role=Role.USER, content=(TextBlock(text=task),))],
            ),
            provider=self._provider,
            transport=self._transport,
            api_key="scripted-key",
        )
        elapsed = time.perf_counter() - start
        return {
            "answer": response.text,
            "latency_ms": elapsed * 1000,
            "tokens": response.usage.total_tokens if response.usage else 0,
            "tool_calls": 0,
        }


class MonolithicRagBaseline:
    """The inlined retrieval chain — the framework-shaped monolith.

    One class performing retrieval, prompt construction and the model call
    inline. Models the classic single-file "stuff the context" chain shape:
    no embedding layer, no vector store, no separable components. This is the
    second baseline, comparable to System A at a coarser level of function
    (retrieve, then answer) so composition overhead has two reference points.
    """

    def __init__(
        self,
        transport: ScriptedTransport,
        provider: OpenAIProvider,
        documents: dict[str, str],
    ) -> None:
        self._transport = transport
        self._provider = provider
        self._documents = documents

    def run(self, task: str) -> dict[str, Any]:
        """Retrieve inline, build the prompt inline, make one call."""
        start = time.perf_counter()
        context = self._retrieve_inline(task)
        prompt = (
            "Answer the question using the context.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {task}"
        )
        response = chat(
            ChatRequest(
                model=MODEL,
                messages=[Message(role=Role.USER, content=(TextBlock(text=prompt),))],
            ),
            provider=self._provider,
            transport=self._transport,
            api_key="scripted-key",
        )
        elapsed = time.perf_counter() - start
        return {
            "answer": response.text,
            "latency_ms": elapsed * 1000,
            "tokens": response.usage.total_tokens if response.usage else 0,
            "tool_calls": 0,
        }

    def _retrieve_inline(self, task: str) -> str:
        """Keyword-overlap scan over documents — nothing separable about it."""

        def words(text: str) -> set[str]:
            return {w.lower().strip("?.,!") for w in text.split()}

        task_words = words(task)
        hits = [text for text in self._documents.values() if task_words & words(text)]
        return " ".join(hits) if hits else "(no context)"


def build_monolithic(responses: list[Any]) -> Any:
    """Build the bare monolithic baseline with scripted transport."""
    transport = ScriptedTransport(responses)
    provider = OpenAIProvider()
    return MonolithicBaseline(transport, provider)


def build_monolithic_rag(responses: list[Any], documents: dict[str, str]) -> Any:
    """Build the inlined retrieval chain with scripted transport."""
    transport = ScriptedTransport(responses)
    provider = OpenAIProvider()
    return MonolithicRagBaseline(transport, provider, documents)


def build_system_c(responses: list[Any]) -> Any:
    """Build System C with scripted transport."""
    from system_c_internal.system import build_system_c

    return build_system_c(responses)


def build_system_a(responses: list[Any], documents: dict[str, str]) -> Any:
    """Build System A with scripted transport and documents."""
    from system_a_partial.system import build_system_a

    return build_system_a(responses, documents)


def build_system_b(responses: list[Any], trace_path: str) -> Any:
    """Build System B with scripted transport and trace recorder."""
    from system_b_mixed.system import build_system_b

    return build_system_b(responses, trace_path)


#: Systems whose ``run`` returns ``(latency_ms, tokens, answer)`` and which
#: therefore share one code path. Keep keys in step with ``run_benchmarks``.
_DICT_RUNNERS = frozenset({"monolithic", "monolithic_rag"})


def benchmark_system(
    name: str, system_factory: Any, task: str, n: int = 10
) -> dict[str, Any]:
    """Run a system n times and measure latency and token usage.

    A factory is used so each iteration gets a fresh instance (some systems
    hold state that cannot be reused across runs).
    """
    latencies: list[float] = []
    tokens: list[int] = []
    answers: list[str] = []

    for _ in range(n):
        system = system_factory()
        start = time.perf_counter()
        if name in _DICT_RUNNERS:
            result = system.run(task)
            latency = result["latency_ms"]
            token_count = result["tokens"]
            answer = result["answer"]
        elif name == "system_c":
            result = system.run(task)
            latency = (time.perf_counter() - start) * 1000
            token_count = result.usage.total_tokens if result.usage else 0
            answer = result.final_text
        elif name == "system_a":
            result = system.answer(task)
            latency = (time.perf_counter() - start) * 1000
            token_count = result.usage.total_tokens if result.usage else 0
            answer = result.final_text
        elif name == "system_b":
            result = system.run(task)
            latency = (time.perf_counter() - start) * 1000
            token_count = 0  # System B doesn't track usage
            answer = result["answer"]
        else:
            raise ValueError(f"unknown system: {name}")

        latencies.append(latency)
        tokens.append(token_count)
        answers.append(answer)

    return {
        "system": name,
        "n": n,
        "latency_ms": {
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            "min": min(latencies),
            "max": max(latencies),
        },
        "tokens": {
            "mean": statistics.mean(tokens),
            "total": sum(tokens),
        },
        "answers": answers,
    }


def run_benchmarks(n: int = 10) -> dict[str, Any]:
    """Run all benchmarks and return results.

    System B's trace file is written under a temporary directory: a benchmark
    run must not leave artifacts in the repository tree.
    """
    task = "What is the capital of France?"
    documents = {
        "doc1": "The capital of France is Paris.",
        "doc2": "The capital of Japan is Tokyo.",
        "doc3": "The capital of the UK is London.",
    }

    # Enough responses for n iterations of every system (each run consumes one).
    responses = [_text_response() for _ in range(n)]

    results = {
        "monolithic": benchmark_system(
            "monolithic", lambda: build_monolithic(responses), task, n
        ),
        "monolithic_rag": benchmark_system(
            "monolithic_rag",
            lambda: build_monolithic_rag(responses, documents),
            task,
            n,
        ),
        "system_c": benchmark_system(
            "system_c", lambda: build_system_c(responses), task, n
        ),
        "system_a": benchmark_system(
            "system_a", lambda: build_system_a(responses, documents), task, n
        ),
    }

    with tempfile.TemporaryDirectory() as tmp:
        trace_path = str(Path(tmp) / "benchmark_trace.jsonl")
        results["system_b"] = benchmark_system(
            "system_b",
            lambda: build_system_b(responses, trace_path),
            task,
            n,
        )

    return results


def render_benchmark_report(results: dict[str, Any]) -> str:
    """Render benchmark results as a Markdown report."""
    iterations = results["monolithic"]["n"]
    lines = [
        "# Benchmark Report — Composed Systems vs Monolithic Baselines",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC",
        "",
        "## Methodology",
        "",
        "- **Task**: 'What is the capital of France?'",
        f"- **Iterations**: {iterations} per system",
        (
            f"- **Environment**: Python {platform.python_version()}, "
            f"{platform.platform()}, no network"
        ),
        "- **Transport**: `ScriptedTransport` (canned responses, shared by every row)",
        "- **Provider**: `OpenAIProvider` (scripted)",
        "",
        "**Baselines.** `monolithic` is the bare single-call chain. "
        "`monolithic_rag` is the inlined retrieval chain — retrieval, prompt "
        "construction and the model call in one class. Both model monolithic "
        "shapes described in the study corpus "
        "(`study_pipeline/studied_repos/`); no third-party framework is "
        "installed or executed (zero-runtime-deps; ADR-0021 Decision 1). The "
        "numbers below compare composition overhead under an identical "
        "transport, not framework quality.",
        "",
        "**Token counts are fixture values.** Every scripted response declares "
        f"{FIXTURE_PROMPT_TOKENS} prompt + {FIXTURE_COMPLETION_TOKENS} "
        "completion tokens; the transport performs no tokenization. The "
        "column shows whether each system's usage *accounting* path works, "
        "not real token economics.",
        "",
        "## Results",
        "",
        "| System | Latency (ms) | Tokens (fixture) | Notes |",
        "|---|---|---|---|",
    ]

    for name, result in results.items():
        latency = result["latency_ms"]["mean"]
        tokens = result["tokens"]["mean"]
        notes = {
            "monolithic": "Single LLM call, no tools, no memory",
            "monolithic_rag": "Inlined retrieval chain: retrieve + prompt + call in one class",
            "system_c": "Our loop + registry + provider",
            "system_a": "Our loop + memory + external embedder",
            "system_b": "External runtime + our trace recorder (no usage tracking)",
        }.get(name, "")
        lines.append(f"| {name} | {latency:.2f} | {tokens:.0f} | {notes} |")

    lines.extend(
        [
            "",
            "## Analysis",
            "",
            "### Where we are better",
            "",
            "- **System C** composes three TESTED capabilities into a working system",
            "- **System A** adds vector memory for RAG-style retrieval",
            "- **System B** wraps external runtime with our observability",
            "- **System A/C** account token usage from provider responses; "
            "System B's external runtime reports none (recorded, not hidden)",
            "",
            "### Where we are worse",
            "",
            "- **Monolithic baselines** are faster for simple tasks (no per-layer overhead)",
            "- **System A** has retrieval overhead (embedding + search) that "
            "`monolithic_rag`'s keyword scan does not pay",
            "- **System B** has trace recording overhead",
            "",
            "### Where we are simpler",
            "",
            "- **Monolithic baselines** are simplest (one class, no composition)",
            "- **System C** is more complex but more modular",
            "",
            "### Where we are more constrained",
            "",
            "- **System A** requires documents to be indexed first",
            "- **System B** requires a trace file path",
            "",
            "### Where we are more maintainable",
            "",
            "- **System C** components are independently testable",
            "- **System A** vector store is swappable; `monolithic_rag`'s "
            "keyword scan is hard-wired to its documents dict",
            "- **System B** trace recorder is reusable",
            "",
            "## Raw Data",
            "",
            "```json",
            json.dumps(results, indent=2, default=str),
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    """Run benchmarks and write report."""
    results = run_benchmarks(n=10)
    report = render_benchmark_report(results)

    output_path = Path(__file__).parent / "results.md"
    output_path.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
