# Research: Infrastructure Scanner

**Date:** 2026-10-01
**Category:** deployment
**Status:** RESEARCHED

---

## 1. Problem Statement

How do we automatically detect and classify the infrastructure components
used by a software repository, without executing any code or requiring
external services?

## 2. Existing Approaches

### 2.1 Manual Code Archaeology

The traditional approach: a developer reads the repo, identifies configs,
reads imports, and manually catalogs infrastructure. **Pros:** accurate.
**Cons:** slow, non-reproducible, doesn't scale.

### 2.2 Dependency Scanners (e.g., `pip-audit`, `npm audit`)

These tools detect dependencies from manifest files (package.json, requirements.txt).
**Pros:** accurate for declared dependencies. **Cons:** only detect declared
deps, not actual infrastructure usage (e.g., a repo may use Redis without
declaring it in requirements.txt if it's a transitive dep).

### 2.3 SAST Tools (e.g., `bandit`, `semgrep`)

These tools scan for security issues, not infrastructure. **Pros:** finds
security-relevant patterns. **Cons:** not designed for infrastructure detection.

### 2.4 Cloud Custodian / Terraform Scanner

Cloud-specific tools that scan IaC files. **Pros:** accurate for cloud resources.
**Cons:** only work for specific cloud providers; don't detect non-IaC infrastructure.

### 2.5 Our Approach: Multi-Layer Deterministic Scanner

Three layers: keyword scanning, config parsing, optional LLM. **Pros:** works
offline, no dependencies, deterministic, covers 12 layers. **Cons:** heuristic
(may miss novel patterns), LLM layer requires API key.

## 3. Design Decisions

### D-1: Why 12 layers?

Derived from synthesis of:
- AWS Well-Architected Framework (6 pillars)
- CNCF Cloud Native Landscape (20+ categories)
- Twelve-Factor App Methodology (12 factors)
- Google Cloud Architecture Framework (4 pillars, 16 capabilities)
- Microsoft Azure Well-Architected Framework (5 pillars)

The 12 layers are a pragmatic synthesis — not a standard, but useful for
navigation (charter §2).

### D-2: Why keyword + config parsing (not AST)?

AST parsing would be more accurate but:
- Requires `tree-sitter` or similar (runtime dependency)
- Overkill for config files (YAML, HCL, nginx conf)
- Keyword scanning covers 80% of cases with 20% of the complexity

### D-3: Why optional LLM layer?

Some infrastructure is ambiguous from static analysis alone (e.g., a custom
wrapper around a database). The LLM layer:
- Is opt-in (requires transport + API key)
- Marks detections with `detection_method="llm"`
- Never blocks the scanner if it fails

### D-4: Why stdlib-only?

Consistent with repository principle (ADR-0006, §20). The scanner uses:
- `pathlib` for filesystem
- `re` for pattern matching
- `tomllib` for TOML (Python 3.12+)
- `json` for JSON
- `xml.etree.ElementTree` for XML
- `yaml` is NOT used (would be a dependency); YAML configs are parsed with
  regex-based heuristics for common patterns

## 4. Component Taxonomy

80+ component types across 12 layers. Each has:
- 10–20 detection keywords (function names, class names, variable names, strings)
- 3–8 file pattern globs
- 3–8 config pattern prefixes (environment variables, config keys)

Compiled by:
1. Literature review of the above frameworks
2. Frequency analysis of infrastructure terms in 50+ repos
3. Expert validation against real production architectures
4. Iterative refinement — adding missing types, removing noise

## 5. Confidence Scoring

| Detection Method | Confidence |
|---|---|
| Exact env var match | 0.85 |
| Prefix env var match | 0.75 |
| Config file parse | 0.90 |
| Keyword match (single) | 0.60 |
| Keyword match (multiple files) | 0.80 |
| LLM detection | 0.60–0.90 (LLM-reported) |

## 6. Open Questions

1. **Should we add AST-based parsing for Python files?** — Deferred; keyword
   scanning covers most cases. Revisit if false positive rate is high.
2. **Should we support more config formats?** — Currently: docker-compose,
   K8s, Terraform, CI/CD, .env, nginx/Caddy. Could add: Ansible, Pulumi, CDK.
3. **Should the LLM layer be removed?** — No; it's opt-in and useful for
   ambiguous cases. But it should never be required.

## 7. References

- AWS Well-Architected Framework
- CNCF Cloud Native Landscape
- Twelve-Factor App Methodology
- Google Cloud Architecture Framework
- Microsoft Azure Well-Architected Framework
- Analysis of 50+ open-source projects across domains
