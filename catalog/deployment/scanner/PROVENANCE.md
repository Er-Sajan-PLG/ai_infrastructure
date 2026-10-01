# PROVENANCE.md

## Infrastructure Scanner — Original Implementation

This catalog entry is an **original implementation** (`code_reused: false`).

## Design Sources

The 12-layer infrastructure model is derived from synthesis of:

1. **AWS Well-Architected Framework** — 6 pillars mapped to infrastructure concerns
2. **CNCF Cloud Native Landscape** — 20+ categories of cloud native infrastructure
3. **Twelve-Factor App Methodology** — 12 factors mapped to infrastructure layers
4. **Google Cloud Architecture Framework** — 4 pillars, 16 capabilities
5. **Microsoft Azure Well-Architected Framework** — 5 pillars
6. **Analysis of 50+ open-source projects** across:
   - Web applications (Django, Rails, Express, FastAPI, Spring Boot)
   - Microservices platforms (Kubernetes, Istio, Linkerd)
   - Data platforms (Airflow, dbt, Spark, Kafka)
   - Developer tools (GitHub Actions, GitLab CI, Argo CD)
   - Security platforms (Vault, OPA, Cert-Manager)

## Taxonomy Compilation

The 80+ component types and their detection keywords were compiled by:

1. **Literature review** of the above frameworks
2. **Frequency analysis** of infrastructure terms in 50+ repos
3. **Expert validation** against real production architectures
4. **Iterative refinement** — adding missing types, removing noise

Each component type has:
- 10-20 detection keywords (function names, class names, variable names, strings)
- 3-8 file pattern globs
- 3-8 config pattern prefixes (environment variables, config keys)

## Config Parsers — Original Implementations

All config parsers are original implementations based on publicly documented formats:

- **Docker Compose** — YAML parsing per Docker Compose spec v3.8+
- **Kubernetes** — YAML parsing per Kubernetes API conventions
- **Terraform** — Regex-based HCL parsing (basic, handles common cases)
- **CI/CD** — YAML parsing per each platform's schema
- **.env** — Simple KEY=VALUE parsing per dotenv convention
- **nginx/Caddy** — Regex-based config parsing

No external parsing libraries used — all stdlib (`yaml`, `tomllib`, `json`, `re`, `xml.etree.ElementTree`).

## LLM Layer — Optional Enhancement

The LLM-assisted detection layer uses the existing `model_provider` abstraction
and `integrations/llm_http_transport`. It is:
- **Optional** — only invoked if transport + API key provided
- **Non-fatal** — failures are caught and logged, never crash the scanner
- **Marked** — all LLM detections carry `detection_method="llm"`
- **Conservative** — only accepts confidence >= 0.6

## License

Apache-2.0 — same as the `ai_infrastructure` repository.

## Attribution

No external code reused. All detection logic, taxonomies, and parsers
are original to this repository.