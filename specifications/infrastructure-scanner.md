# Infrastructure Scanner — Specification

**Status:** DESIGNED
**Category:** deployment
**Decision:** IMPLEMENT (ADR-0029)
**Provenance:** original (`code_reused: false`)

---

## 1. Problem

Infrastructure is implicit in most codebases — scattered across configs, imports,
environment variables, and architectural patterns. Answering "what infrastructure
does this project use?" requires manual code archaeology.

**Consumers:** AI agents that need to understand a repository's infrastructure
before generating code, auditing compliance, or comparing architectures.

## 2. Inputs / Outputs

**Inputs:** A filesystem path to a repository root.

**Outputs:** An `InfraMap` containing:
- `layers_covered` — count of distinct layers detected
- `total_components` — total infrastructure components found
- `layer_summary` — mapping of layer name to component count
- `components` — list of `InfraComponent` objects, each with:
  - `layer` — one of 12 infrastructure layers
  - `component_type` — specific type (e.g., "postgresql", "stripe")
  - `name` — human-readable name
  - `description` — what it does in this system
  - `technologies` — concrete products detected
  - `code_locations` — source files (for keyword detections)
  - `config_locations` — config files (for manifest detections)
  - `confidence` — 0.0–1.0
  - `detection_method` — "keyword", "config_parse", "manifest", or "llm"

## 3. Architecture

Three detection layers, each adding precision:

### Layer 1: Keyword Scanning (Fast, Broad)
Scans source files for 80+ component type keywords across 12 layers.
~80 component types × 10–20 keywords each = ~1000 detection signals.
Confidence based on match count and file diversity.

### Layer 2: Config File Parsing (Deterministic)
Parses infrastructure manifests directly:
- **docker-compose.yml** → service images → component types
- **Kubernetes manifests** → kinds (Ingress, Deployment, Secret, etc.)
- **Terraform** → resource types (aws_db_instance, google_sql_database, etc.)
- **CI/CD configs** (GitHub Actions, GitLab CI, Jenkins, etc.)
- **.env files** → environment variable mapping
- **nginx/Caddy** → reverse proxy, load balancer, rate limiting configs

### Layer 3: LLM-Assisted (Optional)
For ambiguous cases, sends repository summary to an LLM via the
`model_provider` abstraction. Only invoked when transport + API key provided.
Marks detections with `detection_method="llm"`.

All three layers are combined with deduplication. The scanner works
fully offline — LLM layer is purely optional enhancement.

## 4. The 12 Layers

1. **Identity** — Authentication, OAuth, SSO, MFA, RBAC, sessions, API keys
2. **Transaction** — Payments, billing, subscriptions, invoicing
3. **State** — Caching, sessions, distributed locks, feature flags
4. **Data** — Databases, search engines, object storage, ETL, backups
5. **Communication** — REST, GraphQL, gRPC, WebSocket, queues, events
6. **Delivery** — CDN, load balancer, reverse proxy, API gateway
7. **Observability** — Logging, metrics, tracing, error tracking
8. **Security** — Encryption, WAF, secrets, audit logs, compliance
9. **Deployment** — CI/CD, containers, Kubernetes, IaC, registries
10. **Integration** — Webhooks, 3rd-party APIs, SDKs, plugins
11. **User Experience** — i18n, a11y, feature flags, A/B testing
12. **Governance** — Rate limiting, quotas, multi-tenancy, compliance

## 5. Invariants

1. **Deterministic** — same input always produces same output (LLM layer excluded)
2. **Offline-first** — works without network; LLM layer is opt-in
3. **Non-destructive** — never modifies the scanned repository
4. **Stdlib-only** — zero runtime dependencies
5. **Bounded** — recursion depth capped; file size limits enforced
6. **Deduplicated** — same component detected by multiple layers appears once

## 6. Failure Modes

| Failure | Handling |
|---|---|
| Missing config file | Skipped silently |
| Malformed config | Parsed best-effort; partial results returned |
| Binary file encountered | Skipped (not text-decodable) |
| Deeply nested structure | Depth cap prevents stack overflow |
| LLM layer failure | Caught and logged; scanner continues without it |
| Permission denied | File skipped |

## 7. Security Implications

- **Read-only** — scanner never writes to the scanned repository
- **No execution** — never executes, imports, or installs scanned code
- **Path traversal** — all paths resolved within the given root
- **Secret detection** — detects secret env vars but never logs their values
- **LLM boundary** — if LLM layer is used, repository summary is sent to an external API

## 8. Scalability

- **File count** — tested up to 10,000 files
- **File size** — files >1 MB skipped for keyword scanning
- **Depth** — recursion capped at 10 levels
- **Performance** — ~1000 files scanned in <5 seconds (without LLM)

## 9. Testing Strategy

- **Unit tests** — each parser tested in isolation
- **Integration tests** — full scanner on fixture repo structures
- **Property-based** — arbitrary file trees produce valid InfraMap
- **Failure injection** — malformed configs, missing files, binary files
- **Deduplication** — same component from multiple layers appears once
- **LLM layer** — skipped when no transport provided

## 10. Alternatives Considered

| Alternative | Why Not |
|---|---|
| Use `tree-sitter` for parsing | Adds runtime dependency; overkill for config parsing |
| Use `pyyaml` for YAML | Already stdlib in Python 3.12+ (`tomllib`); yaml is dependency |
| Use `ripgrep` for keyword scanning | External binary; stdlib `rglob` is sufficient |
| Build a full AST-based analyzer | Complexity not earned; keyword + config parsing covers 80% |

## 11. Why This Implementation

- **Zero runtime dependencies** — consistent with repository principle (ADR-0006, §20)
- **Deterministic** — reproducible results, testable
- **Composable** — `InfraMap` can be consumed by other tools
- **Extensible** — new component types added to taxonomy without code changes
- **Honest** — confidence scores and detection methods are explicit
