# Benchmark Report — Composed Systems vs Monolithic Baselines

Generated: 2026-10-21 01:45:30 UTC

## Methodology

- **Task**: 'What is the capital of France?'
- **Iterations**: 10 per system
- **Environment**: Python 3.14.8, Linux-6.18.55-1-lts-x86_64-with-glibc2.44, no network
- **Transport**: `ScriptedTransport` (canned responses, shared by every row)
- **Provider**: `OpenAIProvider` (scripted)

**Baselines.** `monolithic` is the bare single-call chain. `monolithic_rag` is the inlined retrieval chain — retrieval, prompt construction and the model call in one class. Both model monolithic shapes described in the study corpus (`study_pipeline/studied_repos/`); no third-party framework is installed or executed (zero-runtime-deps; ADR-0021 Decision 1). The numbers below compare composition overhead under an identical transport, not framework quality.

**Token counts are fixture values.** Every scripted response declares 30 prompt + 5 completion tokens; the transport performs no tokenization. The column shows whether each system's usage *accounting* path works, not real token economics.

## Results

| System | Latency (ms) | Tokens (fixture) | Notes |
|---|---|---|---|
| monolithic | 0.16 | 35 | Single LLM call, no tools, no memory |
| monolithic_rag | 0.10 | 35 | Inlined retrieval chain: retrieve + prompt + call in one class |
| system_c | 0.19 | 35 | Our loop + registry + provider |
| system_a | 0.13 | 35 | Our loop + memory + external embedder |
| system_b | 0.11 | 0 | External runtime + our trace recorder (no usage tracking) |

## Analysis

### Where we are better

- **System C** composes three TESTED capabilities into a working system
- **System A** adds vector memory for RAG-style retrieval
- **System B** wraps external runtime with our observability
- **System A/C** account token usage from provider responses; System B's external runtime reports none (recorded, not hidden)

### Where we are worse

- **Monolithic baselines** are faster for simple tasks (no per-layer overhead)
- **System A** has retrieval overhead (embedding + search) that `monolithic_rag`'s keyword scan does not pay
- **System B** has trace recording overhead

### Where we are simpler

- **Monolithic baselines** are simplest (one class, no composition)
- **System C** is more complex but more modular

### Where we are more constrained

- **System A** requires documents to be indexed first
- **System B** requires a trace file path

### Where we are more maintainable

- **System C** components are independently testable
- **System A** vector store is swappable; `monolithic_rag`'s keyword scan is hard-wired to its documents dict
- **System B** trace recorder is reusable

## Raw Data

```json
{
  "monolithic": {
    "system": "monolithic",
    "n": 10,
    "latency_ms": {
      "mean": 0.16067749966168776,
      "median": 0.08717449964024127,
      "stdev": 0.219527876841039,
      "min": 0.07060900679789484,
      "max": 0.7817220030119643
    },
    "tokens": {
      "mean": 35,
      "total": 350
    },
    "answers": [
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris"
    ]
  },
  "monolithic_rag": {
    "system": "monolithic_rag",
    "n": 10,
    "latency_ms": {
      "mean": 0.09770070028025657,
      "median": 0.08757549949223176,
      "stdev": 0.025822277753583832,
      "min": 0.08228399383369833,
      "max": 0.16585399862378836
    },
    "tokens": {
      "mean": 35,
      "total": 350
    },
    "answers": [
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris"
    ]
  },
  "system_c": {
    "system": "system_c",
    "n": 10,
    "latency_ms": {
      "mean": 0.18786549917422235,
      "median": 0.17405700054951012,
      "stdev": 0.07018764223669073,
      "min": 0.1333069958491251,
      "max": 0.3753749915631488
    },
    "tokens": {
      "mean": 35,
      "total": 350
    },
    "answers": [
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris"
    ]
  },
  "system_a": {
    "system": "system_a",
    "n": 10,
    "latency_ms": {
      "mean": 0.13362820318434387,
      "median": 0.12520600284915417,
      "stdev": 0.027886939445722896,
      "min": 0.11365600221324712,
      "max": 0.2058580139419064
    },
    "tokens": {
      "mean": 35,
      "total": 350
    },
    "answers": [
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris"
    ]
  },
  "system_b": {
    "system": "system_b",
    "n": 10,
    "latency_ms": {
      "mean": 0.10513059969525784,
      "median": 0.08430650632362813,
      "stdev": 0.05679400769934047,
      "min": 0.07525099499616772,
      "max": 0.26053500187117606
    },
    "tokens": {
      "mean": 0,
      "total": 0
    },
    "answers": [
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris",
      "Paris"
    ]
  }
}
```
