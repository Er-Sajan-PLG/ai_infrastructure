# Provenance

- **Kind**: original
- **Based on**: None — independent implementation
- **License**: Apache-2.0
- **Notes**: Inspired-by (not derived-from) the rail concept in NeMo Guardrails
  and the PII pattern sets in Presidio; no code was executed or reused. The
  `Validator` protocol, `ValidationResult` shape, the `PASS`/`FLAG`/`REJECT`
  decision vocabulary and the `GuardrailPolicy`/`Rails` composition are an
  independent design per ADR-0038. Composes `tool-registry` (JSON Schema
  validation via `check_schema`/`validate_arguments`) through its public
  interface.
