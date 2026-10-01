"""Tests for config file parsers."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# The entry lives at catalog/deployment/scanner/tests/, so the importable
# parent is catalog/deployment/ -- tests/ -> scanner/ -> deployment/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scanner.config_parsers import (
    parse_all_configs,
    parse_caddy_config,
    parse_ci_cd_configs,
    parse_docker_compose,
    parse_env_files,
    parse_kubernetes_manifests,
    parse_nginx_config,
    parse_terraform_files,
)

# ---------------------------------------------------------------------------
# Docker Compose Tests
# ---------------------------------------------------------------------------


def test_parse_docker_compose_postgres() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        compose = root / "docker-compose.yml"
        compose.write_text("""
services:
  db:
    image: postgres:15
  web:
    image: nginx:latest
""")
        comps = parse_docker_compose(root)
        names = [c.name for c in comps]
        assert any("PostgreSQL" in n for n in names)
        assert any("NGINX" in n for n in names)


def test_parse_docker_compose_redis() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docker-compose.yml").write_text("""
services:
  cache:
    image: redis:7-alpine
""")
        comps = parse_docker_compose(Path(tmp))
        names = [c.name for c in comps]
        assert any("Redis" in n for n in names)


def test_parse_docker_compose_multiple() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docker-compose.yml").write_text("""
services:
  postgres:
    image: postgres:15
  redis:
    image: redis:7
  kafka:
    image: confluentinc/cp-kafka:7.5.0
""")
        comps = parse_docker_compose(Path(tmp))
        layers = {c.layer for c in comps}
        assert "data" in layers
        assert "state" in layers
        assert "communication" in layers


def test_parse_docker_compose_skips_git() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        git_dir = root / ".git"
        git_dir.mkdir()
        (git_dir / "docker-compose.yml").write_text("""
services:
  db:
    image: postgres:15
""")
        comps = parse_docker_compose(Path(tmp))
        assert len(comps) == 0  # Should skip .git directory


# ---------------------------------------------------------------------------
# Kubernetes Manifest Tests
# ---------------------------------------------------------------------------


def test_parse_k8s_ingress() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ingress.yaml").write_text("""
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  namespace: production
spec:
  rules:
  - host: example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web
            port:
              number: 80
""")
        comps = parse_kubernetes_manifests(Path(tmp))
        ingress_comps = [c for c in comps if c.component_type == "reverse_proxy"]
        assert len(ingress_comps) >= 1
        assert "Ingress" in ingress_comps[0].name


def test_parse_k8s_deployment() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "deployment.yaml").write_text("""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: web
        image: nginx:latest
""")
        comps = parse_kubernetes_manifests(Path(tmp))
        deploy_comps = [c for c in comps if c.component_type == "containerization"]
        assert len(deploy_comps) >= 1


def test_parse_k8s_secret() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "secret.yaml").write_text("""
apiVersion: v1
kind: Secret
metadata:
  name: api-keys
  namespace: production
type: Opaque
data:
  api-key: YWJjZGVm
""")
        comps = parse_kubernetes_manifests(Path(tmp))
        secret_comps = [c for c in comps if c.component_type == "secrets_management"]
        assert len(secret_comps) >= 1


def test_parse_k8s_configmap() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "configmap.yaml").write_text("""
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: default
data:
  LOG_LEVEL: info
""")
        comps = parse_kubernetes_manifests(Path(tmp))
        config_comps = [c for c in comps if c.component_type == "ci_cd_pipeline"]
        assert len(config_comps) >= 1


def test_parse_k8s_hpa() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "hpa.yaml").write_text("""
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web
  minReplicas: 3
  maxReplicas: 10
""")
        comps = parse_kubernetes_manifests(Path(tmp))
        hpa_comps = [c for c in comps if c.component_type == "deployment"]
        assert len(hpa_comps) >= 1


def test_parse_k8s_networkpolicy() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "networkpolicy.yaml").write_text("""
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
""")
        comps = parse_kubernetes_manifests(Path(tmp))
        sec_comps = [c for c in comps if c.component_type == "waf"]
        assert len(sec_comps) >= 1


def test_parse_k8s_skips_git() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        git_dir = root / ".git"
        git_dir.mkdir()
        (git_dir / "deployment.yaml").write_text("""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
spec:
  replicas: 1
""")
        comps = parse_kubernetes_manifests(Path(tmp))
        assert len(comps) == 0


# ---------------------------------------------------------------------------
# Terraform Tests
# ---------------------------------------------------------------------------


def test_parse_terraform_aws_rds() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.tf").write_text("""
resource "aws_db_instance" "primary" {
  engine               = "postgres"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  username             = "admin"
  password             = var.db_password
}
""")
        comps = parse_terraform_files(Path(tmp))
        rds_comps = [c for c in comps if c.component_type == "relational_database"]
        assert len(rds_comps) >= 1
        assert "AWS RDS" in rds_comps[0].name


def test_parse_terraform_aws_s3() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.tf").write_text("""
resource "aws_s3_bucket" "assets" {
  bucket = "my-assets-bucket"
}
""")
        comps = parse_terraform_files(Path(tmp))
        s3_comps = [c for c in comps if c.component_type == "object_storage"]
        assert len(s3_comps) >= 1


def test_parse_terraform_aws_elasticache() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.tf").write_text("""
resource "aws_elasticache_cluster" "cache" {
  cluster_id           = "my-cache"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
}
""")
        comps = parse_terraform_files(Path(tmp))
        cache_comps = [c for c in comps if c.component_type == "cache_layer"]
        assert len(cache_comps) >= 1


def test_parse_terraform_gcp_sql() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.tf").write_text("""
resource "google_sql_database_instance" "primary" {
  database_version = "POSTGRES_15"
  region           = "us-central1"
}
""")
        comps = parse_terraform_files(Path(tmp))
        sql_comps = [c for c in comps if c.component_type == "relational_database"]
        assert len(sql_comps) >= 1


def test_parse_terraform_azure_postgres() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.tf").write_text("""
resource "azurerm_postgresql_server" "primary" {
  name                = "my-postgres"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}
""")
        comps = parse_terraform_files(Path(tmp))
        pg_comps = [c for c in comps if c.component_type == "relational_database"]
        assert len(pg_comps) >= 1


def test_parse_terraform_multiple() -> None:
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
        comps = parse_terraform_files(Path(tmp))
        layers = {c.layer for c in comps}
        assert "data" in layers
        assert "state" in layers


def test_parse_terraform_skips_git() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        git_dir = root / ".git"
        git_dir.mkdir()
        (git_dir / "main.tf").write_text("""
resource "aws_db_instance" "test" {
  engine = "postgres"
}
""")
        comps = parse_terraform_files(Path(tmp))
        assert len(comps) == 0


# ---------------------------------------------------------------------------
# CI/CD Tests
# ---------------------------------------------------------------------------


def test_parse_github_actions() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        wf_dir = root / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("""
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
""")
        comps = parse_ci_cd_configs(Path(tmp))
        gh_comps = [c for c in comps if "GitHub Actions" in c.name]
        assert len(gh_comps) >= 1
        assert (
            "2 job(s)" in gh_comps[0].description
            or "1 job(s)" in gh_comps[0].description
        )


def test_parse_gitlab_ci() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".gitlab-ci.yml").write_text("""
stages:
  - test
  - deploy

test:
  stage: test
  script:
    - pytest

deploy:
  stage: deploy
  script:
    - kubectl apply -f k8s/
""")
        comps = parse_ci_cd_configs(Path(tmp))
        gl_comps = [c for c in comps if "GitLab CI" in c.name]
        assert len(gl_comps) >= 1


def test_parse_jenkinsfile() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Jenkinsfile").write_text("""
pipeline {
    agent any
    stages {
        stage('Test') {
            steps {
                sh 'pytest'
            }
        }
    }
}
""")
        comps = parse_ci_cd_configs(Path(tmp))
        jenkins_comps = [c for c in comps if "Jenkins" in c.name]
        assert len(jenkins_comps) >= 1


# ---------------------------------------------------------------------------
# .env File Tests
# ---------------------------------------------------------------------------


def test_parse_env_database() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".env").write_text("""
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379
""")
        comps = parse_env_files(Path(tmp))
        names = {c.name for c in comps}
        assert any("Database Connection" in n for n in names)
        assert any("Redis Connection" in n for n in names)


def test_parse_env_stripe() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".env").write_text("""
STRIPE_SECRET_KEY=sk_test_abc
STRIPE_PUBLISHABLE_KEY=pk_test_abc
""")
        comps = parse_env_files(Path(tmp))
        names = {c.name for c in comps}
        assert any("Stripe" in n for n in names)


def test_parse_env_sentry() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".env").write_text("""
SENTRY_DSN=https://abc@sentry.io/123
""")
        comps = parse_env_files(Path(tmp))
        names = {c.name for c in comps}
        assert any("Sentry" in n for n in names)


def test_parse_env_prefix_match() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".env").write_text("""
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=secret
AWS_REGION=us-east-1
""")
        comps = parse_env_files(Path(tmp))
        names = {c.name for c in comps}
        assert any("AWS Credentials" in n for n in names)


# ---------------------------------------------------------------------------
# Web Server Config Tests
# ---------------------------------------------------------------------------


def test_parse_nginx_reverse_proxy() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "nginx.conf").write_text("""
server {
    listen 80;
    location / {
        proxy_pass http://backend;
    }
}
""")
        comps = parse_nginx_config(Path(tmp))
        names = {c.name for c in comps}
        assert any("Reverse Proxy" in n for n in names)


def test_parse_nginx_load_balancer() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "nginx.conf").write_text("""
upstream backend {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}
server {
    location / {
        proxy_pass http://backend;
    }
}
""")
        comps = parse_nginx_config(Path(tmp))
        types = {c.component_type for c in comps}
        assert "reverse_proxy" in types
        assert "load_balancer" in types


def test_parse_nginx_ssl() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "nginx.conf").write_text("""
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/cert.pem;
    ssl_certificate_key /etc/nginx/key.pem;
}
""")
        comps = parse_nginx_config(Path(tmp))
        types = {c.component_type for c in comps}
        assert "encryption" in types


def test_parse_nginx_rate_limiting() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "nginx.conf").write_text("""
http {
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    server {
        location /api/ {
            limit_req zone=api burst=20;
        }
    }
}
""")
        comps = parse_nginx_config(Path(tmp))
        types = {c.component_type for c in comps}
        assert "rate_limiting" in types


def test_parse_caddy_reverse_proxy() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Caddyfile").write_text("""
example.com {
    reverse_proxy localhost:8000
}
""")
        comps = parse_caddy_config(Path(tmp))
        types = {c.component_type for c in comps}
        assert "reverse_proxy" in types


def test_parse_caddy_https() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Caddyfile").write_text("""
example.com {
    tls email@example.com
}
""")
        comps = parse_caddy_config(Path(tmp))
        types = {c.component_type for c in comps}
        assert "encryption" in types


def test_parse_caddy_rate_limiting() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Caddyfile").write_text("""
example.com {
    rate_limit {
        zone requests 100r/s
    }
}
""")
        comps = parse_caddy_config(Path(tmp))
        types = {c.component_type for c in comps}
        assert "rate_limiting" in types


# ---------------------------------------------------------------------------
# Combined Tests
# ---------------------------------------------------------------------------


def test_parse_all_configs() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        # docker-compose
        (root / "docker-compose.yml").write_text("""
services:
  db:
    image: postgres:15
""")
        # k8s
        (root / "deployment.yaml").write_text("""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 1
""")
        # terraform
        (root / "main.tf").write_text("""
resource "aws_s3_bucket" "assets" {
  bucket = "my-bucket"
}
""")
        # env
        (root / ".env").write_text("DATABASE_URL=postgresql://localhost/db\n")
        # nginx
        (root / "nginx.conf").write_text("""
server { location / { proxy_pass http://backend; } }
""")

        comps = parse_all_configs(Path(tmp))
        assert len(comps) >= 5
        layers = {c.layer for c in comps}
        assert "data" in layers
        assert "deployment" in layers
        assert "delivery" in layers


def test_malformed_configs_handled_gracefully() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Invalid YAML
        (root / "docker-compose.yml").write_text("""
services:
  db:
    image: postgres
    invalid yaml: [unclosed
""")
        # Should not raise
        comps = parse_all_configs(Path(tmp))
        # Should still process other valid files
        assert isinstance(comps, list)
