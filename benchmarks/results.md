# Benchmark Report — Composed Systems vs Monolithic Baselines

Generated: 2026-10-16 08:19:29 UTC

## Methodology

- **Task**: 'What is the capital of France?'
- **Iterations**: 10 per system
- **Environment**: Python 3.14.7, Linux-6.18.55-1-lts-x86_64-with-glibc2.44, no network
- **Transport**: `ScriptedTransport` (canned responses, shared by every row)
- **Provider**: `OpenAIProvider` (scripted)

**Baselines.** `monolithic` is the bare single-call chain. `monolithic_rag` is the inlined retrieval chain — retrieval, prompt construction and the model call in one class. Both model monolithic shapes described in the study corpus (`study_pipeline/studied_repos/`); no third-party framework is installed or executed (zero-runtime-deps; ADR-0021 Decision 1). The numbers below compare composition overhead under an identical transport, not framework quality.

**Token counts are fixture values.** Every scripted response declares 30 prompt + 5 completion tokens; the transport performs no tokenization. The column shows whether each system's usage *accounting* path works, not real token economics.

## Results

| System | Latency (ms) | Tokens (fixture) | Notes |
|---|---|---|---|
| monolithic | 0.02 | 35 | Single LLM call, no tools, no memory |
| monolithic_rag | 0.02 | 35 | Inlined retrieval chain: retrieve + prompt + call in one class |
| system_c | 0.07 | 35 | Our loop + registry + provider |
| system_a | 0.10 | 35 | Our loop + memory + external embedder |
| system_b | 0.08 | 0 | External runtime + our trace recorder (no usage tracking) |

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
      "mean": 0.02417959985905327,
      "median": 0.01711599725240376,
      "stdev": 0.016278009434593628,
      "min": 0.013642002159031108,
      "max": 0.06331799886538647
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
      "mean": 0.023778199829393998,
      "median": 0.020004001271445304,
      "stdev": 0.008028208705833761,
      "min": 0.018676997569855303,
      "max": 0.044162999984109774
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
      "mean": 0.06571690028067678,
      "median": 0.052523000704240985,
      "stdev": 0.03345495583734442,
      "min": 0.04973999966750853,
      "max": 0.15868999980739318
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
      "mean": 0.09605190025467891,
      "median": 0.0842454992380226,
      "stdev": 0.02737249309213324,
      "min": 0.07460499909939244,
      "max": 0.14721700063091703
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
      "mean": 0.07825190041330643,
      "median": 0.06115200085332617,
      "stdev": 0.04788294564452714,
      "min": 0.050714003009488806,
      "max": 0.20868600040557794
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
