"""Tests for the main scanner."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

# The entry lives at catalog/infrastructure/scanner/tests/, so the importable
# parent is catalog/infrastructure/ -- tests/ -> scanner/ -> infrastructure/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scanner import InfrastructureScanner, scan_keywords

# ---------------------------------------------------------------------------
# Keyword Scanner Tests
# ---------------------------------------------------------------------------


def test_scan_keywords_postgresql() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "models.py").write_text("""
import psycopg2
from sqlalchemy import create_engine

engine = create_engine("postgresql://localhost/db")
conn = psycopg2.connect("postgresql://user:pass@localhost/db")
""")
        comps = scan_keywords(Path(tmp))
        pg_comps = [c for c in comps if c.component_type == "relational_database"]
        assert len(pg_comps) >= 1


def test_scan_keywords_redis() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "cache.py").write_text("""
import redis

client = redis.Redis(host='localhost', port=6379)
client.set('key', 'value')
""")
        comps = scan_keywords(Path(tmp))
        redis_comps = [c for c in comps if c.component_type == "cache_layer"]
        assert len(redis_comps) >= 1


def test_scan_keywords_stripe() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "payment.py").write_text("""
import stripe

stripe.api_key = "sk_test_abc"
charge = stripe.Charge.create(amount=1000, currency="usd")
""")
        comps = scan_keywords(Path(tmp))
        stripe_comps = [
            c
            for c in comps
            if "stripe" in c.component_type.lower()
            or "payment" in c.component_type.lower()
        ]
        assert len(stripe_comps) >= 1


def test_scan_keywords_skips_test_dirs() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Main code
        (root / "main.py").write_text("import stripe\nstripe.Charge.create()")
        # Test file - should be skipped or lower confidence
        tests_dir = root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_payment.py").write_text(
            "import stripe\nstripe.Charge.create()"
        )

        comps = scan_keywords(Path(tmp))
        # Main code should be detected
        assert len(comps) >= 1


def test_scan_keywords_jwt() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "auth.py").write_text("""
import jwt

token = jwt.encode({"user_id": 123}, "secret", algorithm="HS256")
decoded = jwt.decode(token, "secret", algorithms=["HS256"])
""")
        comps = scan_keywords(Path(tmp))
        jwt_comps = [
            c
            for c in comps
            if "jwt" in c.component_type.lower() or "auth" in c.component_type.lower()
        ]
        assert len(jwt_comps) >= 1


# ---------------------------------------------------------------------------
# Full Scanner Tests
# ---------------------------------------------------------------------------


def test_scanner_basic() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("""
import psycopg2
import redis

engine = create_engine("postgresql://localhost/db")
client = redis.Redis()
""")
        (root / ".env").write_text(
            "DATABASE_URL=postgresql://localhost/db\nREDIS_URL=redis://localhost:6379\n"
        )

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        assert infra_map.total_components >= 2
        assert infra_map.layers_covered >= 1
        assert "data" in infra_map.layer_summary or "state" in infra_map.layer_summary


def test_scanner_with_docker_compose() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docker-compose.yml").write_text("""
services:
  db:
    image: postgres:15
  cache:
    image: redis:7
  kafka:
    image: confluentinc/cp-kafka:7.5.0
""")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        assert infra_map.total_components >= 3
        set(infra_map.layer_summary.keys())
        assert "data" in infra_map.layer_summary
        assert "state" in infra_map.layer_summary
        assert "communication" in infra_map.layer_summary


def test_scanner_with_k8s() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "deployment.yaml").write_text("""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
---
apiVersion: v1
kind: Service
metadata:
  name: web-svc
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-ingress
spec:
  rules:
  - host: example.com
""")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        assert infra_map.total_components >= 3
        assert "deployment" in infra_map.layer_summary
        assert "delivery" in infra_map.layer_summary


def test_scanner_with_terraform() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.tf").write_text("""
resource "aws_db_instance" "primary" {
  engine = "postgres"
}
resource "aws_elasticache_cluster" "cache" {
  engine = "redis"
}
resource "aws_s3_bucket" "assets" {
  bucket = "my-assets"
}
""")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        assert infra_map.total_components >= 3
        assert "data" in infra_map.layer_summary
        assert "state" in infra_map.layer_summary


def test_scanner_with_env_file() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".env").write_text("""
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379
STRIPE_SECRET_KEY=sk_test_abc
SENTRY_DSN=https://abc@sentry.io/123
""")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        assert infra_map.total_components >= 4
        layers = set(infra_map.layer_summary.keys())
        assert "data" in layers
        assert "state" in layers
        assert "transaction" in layers
        assert "observability" in layers


def test_scanner_with_ci_cd() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        github_dir = root / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        (github_dir / "ci.yml").write_text("""
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build .
""")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        ci_comps = [
            c for c in infra_map.components if c.component_type == "ci_cd_pipeline"
        ]
        assert len(ci_comps) >= 1
        assert "GitHub Actions" in ci_comps[0].name


def test_scanner_with_nginx() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "nginx.conf").write_text("""
server {
    listen 80;
    location / {
        proxy_pass http://backend;
    }
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
}
""")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        comps = infra_map.components
        types = {c.component_type for c in comps}
        assert "reverse_proxy" in types
        assert "rate_limiting" in types


def test_scanner_with_caddy() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Caddyfile").write_text("""
example.com {
    reverse_proxy localhost:8000
    tls email@example.com
    rate_limit {
        zone requests 100r/s
    }
}
""")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        comps = infra_map.components
        types = {c.component_type for c in comps}
        assert "reverse_proxy" in types
        assert "encryption" in types
        assert "rate_limiting" in types


def test_scanner_with_env_prefix_match() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".env").write_text("""
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=secret
AWS_REGION=us-east-1
AWS_S3_BUCKET=my-bucket
""")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        names = {c.name for c in infra_map.components}
        assert any("AWS" in n for n in names)


def test_scanner_layer_filter() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("import psycopg2\nimport redis")
        (root / ".env").write_text(
            "DATABASE_URL=postgresql://localhost/db\nREDIS_URL=redis://localhost:6379"
        )

        scanner = InfrastructureScanner()
        data_comps = scanner.scan_layer(Path(tmp), "data")
        state_comps = scanner.scan_layer(Path(tmp), "state")

        # Should find components in both layers
        assert len(data_comps) >= 1
        assert len(state_comps) >= 1
        assert all(c.layer == "data" for c in data_comps)
        assert all(c.layer == "state" for c in state_comps)


def test_scanner_invalid_layer() -> None:
    scanner = InfrastructureScanner()
    with pytest.raises(ValueError):
        scanner.scan_layer(Path(), "invalid_layer")


def test_coverage_calculation() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("import psycopg2\nimport redis\nimport stripe")
        (root / ".env").write_text(
            "DATABASE_URL=postgresql://localhost/db\nREDIS_URL=redis://localhost:6379\nSTRIPE_SECRET_KEY=sk_test"
        )

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))
        coverage = scanner.get_coverage(infra_map)

        # All scores should be 0.0-1.0
        for _layer, score in coverage.items():
            assert 0.0 <= score <= 1.0

        # Layers with components should have > 0 coverage
        for layer, _count in infra_map.layer_summary.items():
            assert coverage[layer] > 0


def test_scanner_deduplication() -> None:
    """Same component detected by keyword and config should be deduplicated."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Both keyword scan and .env will detect PostgreSQL
        (root / "db.py").write_text(
            "import psycopg2\nconn = psycopg2.connect('postgresql://localhost/db')"
        )
        (root / ".env").write_text("DATABASE_URL=postgresql://localhost/db")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))

        pg_comps = [
            c for c in infra_map.components if c.component_type == "relational_database"
        ]
        # Should be deduplicated to 1
        assert len(pg_comps) == 1


def test_infrastructure_map_to_dict() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("import psycopg2")

        scanner = InfrastructureScanner()
        infra_map = scanner.scan(Path(tmp))
        d = infra_map.to_dict()

        assert d["repo_name"] == tmp.split("/")[-1]
        assert "layers_covered" in d
        assert "total_components" in d
        assert "layer_summary" in d
        assert "components" in d
        assert isinstance(d["components"], list)
