# Evaluation & Verification Architecture

## what it is

Separate contracts for evaluating AI output quality (evaluator) and verifying
claims against independent evidence (verifier). Evaluators assess against
criteria; verifiers check against sources. Different failure modes, different
contracts, different escalation paths.

## why it exists

Without evaluator/verifier separation, evaluation scores get treated as truth,
claims are not checked against sources, and there is no disagreement detection.
This is needed for STEMMA canonicalization governance and JARVIS worker trust.

## status

Empty. First expected implementation: STEMMA verification pipeline.

## references

- ADR-0026: Evaluator/Verifier Separation
- Ragas `src/ragas/metrics/` — metric contracts, LLM-as-judge
- Phoenix-evals `packages/phoenix-evals/` — evaluation from traces
