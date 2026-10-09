# Benchmark Report — Composed Systems vs Monolithic Baseline

Generated: 2026-10-09 01:33:29 UTC

## Methodology

- **Task**: 'What is the capital of France?'
- **Iterations**: 10 per system
- **Environment**: Python 3.14.7, Linux, no network
- **Transport**: ScriptedTransport (canned responses)
- **Provider**: OpenAIProvider (scripted)

## Results

| System | Latency (ms) | Tokens | Notes |
|---|---|---|---|
| monolithic | 0.02 | 0 | Single LLM call, no tools, no memory |
| system_c | 0.06 | 0 | Our loop + registry + provider |
| system_a | 0.11 | 0 | Our loop + memory + external embedder |
| system_b | 0.08 | 0 | External runtime + our trace recorder |

## Analysis

### Where we are better

- **System C** composes three TESTED capabilities into a working system
- **System A** adds vector memory for RAG-style retrieval
- **System B** wraps external runtime with our observability

### Where we are worse

- **Monolithic baseline** is faster for simple tasks (no overhead)
- **System A** has retrieval overhead (embedding + search)
- **System B** has trace recording overhead

### Where we are simpler

- **Monolithic baseline** is simplest (one class, no composition)
- **System C** is more complex but more modular

### Where we are more constrained

- **System A** requires documents to be indexed first
- **System B** requires trace file path

### Where we are more maintainable

- **System C** components are independently testable
- **System A** vector store is swappable
- **System B** trace recorder is reusable

## Raw Data

```json
{
  "monolithic": {
    "system": "monolithic",
    "n": 10,
    "latency_ms": {
      "mean": 0.021452199871418998,
      "median": 0.014806000763201155,
      "stdev": 0.016237401750139314,
      "min": 0.011475000064820051,
      "max": 0.06299099914031103
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
  },
  "system_c": {
    "system": "system_c",
    "n": 10,
    "latency_ms": {
      "mean": 0.06338180028251372,
      "median": 0.05280150071484968,
      "stdev": 0.029665260598701552,
      "min": 0.046332999772857875,
      "max": 0.14446799832512625
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
  },
  "system_a": {
    "system": "system_a",
    "n": 10,
    "latency_ms": {
      "mean": 0.11077829985879362,
      "median": 0.11592850023589563,
      "stdev": 0.01598721036615479,
      "min": 0.07774899859214202,
      "max": 0.12914200124214403
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
  },
  "system_b": {
    "system": "system_b",
    "n": 10,
    "latency_ms": {
      "mean": 0.07777499995427206,
      "median": 0.058014000387629494,
      "stdev": 0.045559808905855835,
      "min": 0.051317001634743065,
      "max": 0.20046999998157844
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
