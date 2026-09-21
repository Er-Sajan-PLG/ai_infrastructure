# ADR-0026 — Evaluator/Verifier Separation: Assessment vs. Truth

- **Status:** Accepted
- **Date:** 2026-09-21
- **Supersedes:** —
- **Superseded by:** —

## Context

The 18-repository study revealed that **evaluation** (assessing quality against
criteria) and **verification** (checking claims against independent evidence)
are architecturally distinct responsibilities. Our projects conflate them or
implement neither.

Currently:
- **JARVIS**: No evaluator or verifier. Worker output is trusted.
- **PROFESSOR-J**: No evaluator or verifier. Research output is trusted.
- **STEMMA**: Schema validation exists (structural), but no semantic evaluation
  of AI-extracted content and no verification against source evidence.
- **LearningHub**: Content verification exists (schema), but no evaluator for
  AI-generated quiz/explanation quality.

### Source evidence

Two independent repositories demonstrate evaluator architecture:

1. **Ragas** (`src/ragas/metrics/base.py`): `SingleTurnMetric` base class with
   `MetricWithLLM` and `MetricWithEmbeddings`. Each metric consumes a
   `SingleTurnSample` and produces a score. Metrics are composable, deterministic
   or LLM-based, and operate against execution records — not against raw code.

2. **Phoenix-evals** (`packages/phoenix-evals/`): LLM-as-judge metrics
   (correctness, faithfulness, hallucination) with separate `evaluators/`,
   `metrics/`, and `llm/` packages. Evaluators consume traces and produce
   evaluation results.

Neither repository has a **verifier** in the sense of checking a claim against
source evidence. Ragas evaluates answer quality; Phoenix evaluates trace quality.
STEMMA needs something different: does the extracted relationship actually appear
in the source document?

### The problem this solves

Without evaluator/verifier separation:

- Evaluation scores get treated as truth (LLM judge says 0.9 → canonical?)
- No independent check that AI output matches source material
- No disagreement detection between multiple evaluators
- No confidence scoring for human reviewers

### What it is NOT

This is NOT:
- **Evaluation only** (Ragas) — we also need verification against sources
- **Schema validation** (current STEMMA) — that checks structure, not semantics
- **Human review** (current STEMMA gate) — humans need evidence to review, not raw output
- **Unit testing** (current test suites) — that checks code, not AI output quality

Evaluation = does the output satisfy criteria?
Verification = does the claim match independent evidence?

## Decision

Implement evaluator and verifier as separate architectural components across
projects that produce AI-generated content.

### Evaluator contract (all projects)

```python
@dataclass
class EvaluationInput:
    """What is being evaluated."""
    output: Any           # The AI-generated content
    context: dict         # Additional context (input, trace, evidence)
    criteria: list[str]   # What dimensions to evaluate

@dataclass
class EvaluationResult:
    """The assessment."""
    scores: dict[str, float]    # Per-criterion scores
    confidence: float           # Evaluator confidence
    reasoning: str             # Why these scores
    evaluator: str              # Which evaluator produced this
    version: str                # Evaluator version for reproducibility

class Evaluator(Protocol):
    async def evaluate(self, input: EvaluationInput) -> EvaluationResult: ...
```

### Verifier contract (STEMMA-specific)

```python
@dataclass
class VerificationInput:
    """What is being verified."""
    claim: str              # The extracted claim
    source_ref: str         # Reference to source material
    evidence_chain: list    # Steps from source → claim

@dataclass
class VerificationResult:
    """The verdict."""
    supported: bool         # Is the claim supported by evidence?
    evidence_locations: list # Where in the source
    confidence: float       # How confident is the verifier
    conflicts: list         # Contradictory evidence found

class Verifier(Protocol):
    async def verify(self, input: VerificationInput) -> VerificationResult: ...
```

### Project mapping

| Project | Evaluator | Verifier |
|---------|-----------|----------|
| JARVIS | Worker output quality (action correctness, result completeness) | N/A (workers don't make factual claims) |
| PROFESSOR-J | Research output quality (coherence, source alignment) | N/A (research is generative, not extractive) |
| STEMMA | Content quality (completeness, accuracy against schema) | Source verification (does relationship appear in source?) |
| LearningHub | Quiz/explanation quality (pedagogical effectiveness, correctness) | Content accuracy against STEMMA canonical source |

## Consequences

### Positive
- Evaluation and verification have independent contracts and failure modes
- Multiple evaluators can run and compare (disagreement detection)
- Verifier failures escalate to human review with evidence locations
- LLM judges are clearly labeled as evaluators, not authorities

### Negative
- Two contracts to maintain instead of one
- Evaluator LLM calls add cost and latency
- Verifier requires access to source material (storage, retrieval)
- Calibration: evaluator scores need grounding (not absolute truth)

### Neutral
- Evaluator can be deterministic (rule-based) or LLM-based
- Verifier can be source-lookup, embedding similarity, or LLM-as-judge
- Both attach to the execution evidence plane (ADR-0025)

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| Ragas-style metrics only | Evaluates quality but doesn't verify against sources; STEMMA needs both |
| LLM-as-judge as authority | LLM judges are not truth; they are instruments with known error rates |
| Human-only review | Too slow for scale; humans need evaluator/verifier output to review efficiently |
| Combined evaluator+verifier | Different failure modes, different contracts, different escalation paths; separating is safer |

## References

- Ragas: `src/ragas/metrics/_answer_correctness.py` (LLM-as-judge with TP/FP/FN classification)
- Phoenix-evals: `packages/phoenix-evals/src/phoenix/evals/` (separate evaluator/metric/llm packages)
- SWE-agent: `sweagent/types.py` (StepOutput feeds evaluation)
- TruLens: `src/feedback/` (feedback functions are evaluators, not authorities)
