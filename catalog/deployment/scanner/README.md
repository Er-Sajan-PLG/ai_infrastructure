# Infrastructure Scanner

> **Status: `TESTED`** — Deterministic 12-layer infrastructure detection with optional LLM enhancement.

| | |
|---|---|
| **Capability** | [`infrastructure-scanner`](../../../TAXONOMY.md) (category: deployment) |
| **Specification** | [`specifications/infrastructure-scanner.md`](../../../specifications/infrastructure-scanner.md) |
| **Decision** | [ADR-0029](../../../docs/decisions/0029-infrastructure-scanner.md) — `IMPLEMENT` |
| **Research** | [`research/deployment/infrastructure-scanner.md`](../../../research/deployment/infrastructure-scanner.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — original, `code_reused: false` |
| **Depends on** | `catalog/models/model_provider` (for optional LLM layer), `integrations/llm_http_transport` (for optional LLM transport) |
| **Standards** | None claimed — detection is heuristic, not conformance |

## What it is

A deterministic infrastructure scanner that maps **all 12 layers** of a software repository's infrastructure:

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

## Why it exists

Infrastructure is implicit in most codebases — scattered across configs, imports,
environment variables, and architectural patterns. This scanner makes it
explicit, structured, and queryable.

Without it, answering "what infrastructure does this project use?" requires
manual code archaeology. With it, you get a structured `InfrastructureMap`
in seconds.

## How it works

Three detection layers, each adding precision:

### Layer 1: Keyword Scanning (Fast, Broad)
Scans source files for 80+ component type keywords across 12 layers.
~80 component types × 10-20 keywords each = ~1000 detection signals.
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

## Our implementations

This entry is itself the implementation — one scanner with three
detection layers, each independently usable:

- `scanner.py` — `InfrastructureScanner` orchestration plus Layer 1 keyword
  scanning (`scan_keywords`), Layer 3 LLM enhancement (`scan_with_llm`),
  deduplication, and coverage calculation.
- `config_parsers.py` — Layer 2 deterministic parsers: Docker Compose,
  Kubernetes manifests, Terraform resources, CI/CD configs, `.env` files,
  nginx/Caddy configs.
- `taxonomy.py` — the 80+ component-type taxonomy (`TaxonomyEntry`) across
  all 12 layers, with `validate_taxonomy()` pinning its invariants.
- `models.py` — `InfraComponent` / `InfrastructureMap` neutral types.

## What it produces

```python
from scanner import InfrastructureScanner
from pathlib import Path

scanner = InfrastructureScanner()
infra_map = scanner.scan(Path("/path/to/repo"))

print(infra_map.layers_covered)      # e.g., 9
print(infra_map.total_components)    # e.g., 34
print(infra_map.layer_summary)       # {'data': 5, 'deployment': 4, ...}

# Per-layer coverage (0.0-1.0)
coverage = scanner.get_coverage(infra_map)
# {'identity': 0.6, 'transaction': 0.0, ...}
```

Each `InfraComponent` includes:
- `layer` — which of the 12 layers
- `component_type` — specific type (e.g., "postgresql", "stripe")
- `name` — human-readable name
- `description` — what it does in this system
- `technologies` — concrete products detected
- `code_locations` — source files (for keyword detections)
- `config_locations` — config files (for manifest detections)
- `confidence` — 0.0-1.0
- `detection_method` — "keyword", "config_parse", "manifest", or "llm"

## When to use / When not to use

**Use it when:**
- You need to understand a repository's infrastructure quickly
- Building a generator that needs infrastructure context
- Auditing a codebase for compliance/security
- Comparing infrastructure across repositories

**Do not use it when:**
- You need runtime behavior analysis (this is static analysis only)
- You need exact version resolution (it reads declared, not resolved, deps)
- You need 100% recall (detection is heuristic, not exhaustive)

## Limitations

Stated here so they are not assumed away:

1. **Static only** — no runtime behavior, no network calls
2. **Declared, not resolved** — reads manifests, doesn't resolve versions
3. **Heuristic confidence** — keyword matches may produce false positives
3. **LLM optional** — Layer 3 requires API key and transport; offline-only otherwise
4. **Not exhaustive** — 80 component types cover common cases, not everything
5. **Layer boundaries blur** — some components span layers (e.g., Redis is both cache and queue)

## Testing

50+ tests covering:
- Keyword scanning precision/recall
- Docker Compose parsing with fixture files
- Kubernetes manifest parsing
- Terraform resource detection
- CI/CD config detection
- .env file parsing
- nginx/Caddy config parsing
- Full scanner on fixture repo structures
- Coverage calculation
- Graceful handling of missing/malformed configs
- LLM layer skipped when no transport provided

Run with:
```bash
.venv/bin/pytest catalog/deployment/scanner/tests -v
```

## References

- AWS Well-Architected Framework
- CNCF Cloud Native Landscape
- Twelve-Factor App Methodology
- Analysis of 50+ open-source projects across domains