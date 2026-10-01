"""Config file parsers for infrastructure detection.

Parses docker-compose, Kubernetes, Terraform, CI/CD, .env, and web server configs.
All parsers are deterministic, stdlib-only, and handle malformed input gracefully.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import yaml

from .models import InfraComponent

# ---------------------------------------------------------------------------
# Docker Compose Parser
# ---------------------------------------------------------------------------

# Map docker-compose service images to infrastructure component types
COMPOSE_IMAGE_MAP: Final[dict[str, tuple[str, str, str]]] = {
    # Databases
    "postgres": ("data", "relational_database", "PostgreSQL"),
    "postgresql": ("data", "relational_database", "PostgreSQL"),
    "mysql": ("data", "relational_database", "MySQL"),
    "mariadb": ("data", "relational_database", "MariaDB"),
    "sqlite": ("data", "relational_database", "SQLite"),
    "mongodb": ("data", "document_database", "MongoDB"),
    "mongo": ("data", "document_database", "MongoDB"),
    "redis": ("state", "cache_layer", "Redis"),
    "memcached": ("state", "cache_layer", "Memcached"),
    "elasticsearch": ("data", "search_engine", "Elasticsearch"),
    "opensearch": ("data", "search_engine", "OpenSearch"),
    "solr": ("data", "search_engine", "Apache Solr"),
    "cassandra": ("data", "document_database", "Cassandra"),
    "couchdb": ("data", "document_database", "CouchDB"),
    "dynamodb": ("data", "document_database", "DynamoDB Local"),
    # Message Queues
    "rabbitmq": ("communication", "message_queue", "RabbitMQ"),
    "rabbit": ("communication", "message_queue", "RabbitMQ"),
    "kafka": ("communication", "message_queue", "Apache Kafka"),
    "zookeeper": ("communication", "message_queue", "ZooKeeper"),
    "nats": ("communication", "message_queue", "NATS"),
    "redis-stream": ("communication", "message_queue", "Redis Streams"),
    # Observability
    "prometheus": ("observability", "metrics", "Prometheus"),
    "grafana": ("observability", "metrics", "Grafana"),
    "jaeger": ("observability", "distributed_tracing", "Jaeger"),
    "zipkin": ("observability", "distributed_tracing", "Zipkin"),
    "tempo": ("observability", "distributed_tracing", "Grafana Tempo"),
    "loki": ("observability", "logging", "Grafana Loki"),
    "datadog": ("observability", "metrics", "Datadog"),
    "newrelic": ("observability", "metrics", "New Relic"),
    "sentry": ("observability", "error_tracking", "Sentry"),
    # Delivery
    "nginx": ("delivery", "reverse_proxy", "NGINX"),
    "traefik": ("delivery", "reverse_proxy", "Traefik"),
    "envoy": ("delivery", "reverse_proxy", "Envoy Proxy"),
    "haproxy": ("delivery", "load_balancer", "HAProxy"),
    "caddy": ("delivery", "reverse_proxy", "Caddy"),
    "kong": ("delivery", "api_gateway", "Kong"),
    "apisix": ("delivery", "api_gateway", "APISIX"),
    "ambassador": ("delivery", "api_gateway", "Ambassador"),
    "istio": ("delivery", "api_gateway", "Istio"),
    "linkerd": ("delivery", "api_gateway", "Linkerd"),
    # Security
    "vault": ("security", "secrets_management", "HashiCorp Vault"),
    "consul": ("security", "secrets_management", "Consul"),
    # CI/CD
    "jenkins": ("deployment", "ci_cd_pipeline", "Jenkins"),
    "gitlab-runner": ("deployment", "ci_cd_pipeline", "GitLab Runner"),
    "drone": ("deployment", "ci_cd_pipeline", "Drone CI"),
    "woodpecker": ("deployment", "ci_cd_pipeline", "Woodpecker CI"),
    "tekton": ("deployment", "ci_cd_pipeline", "Tekton"),
    "argo": ("deployment", "ci_cd_pipeline", "Argo CD"),
    # Feature flags
    "unleash": ("state", "feature_flag", "Unleash"),
    "flagsmith": ("state", "feature_flag", "Flagsmith"),
    # Others
    "minio": ("data", "object_storage", "MinIO"),
    "localstack": ("integration", "third_party_api", "LocalStack"),
    "postgrest": ("communication", "rest_api", "PostgREST"),
    "hasura": ("communication", "graphql_api", "Hasura"),
}


def parse_docker_compose(repo_path: Path) -> list[InfraComponent]:
    """Parse docker-compose.yml files for infrastructure components."""
    components = []

    for compose_file in repo_path.rglob("docker-compose*.y*ml"):
        if any(
            part in {".git", ".venv", "venv", "env", "node_modules"}
            for part in compose_file.parts
        ):
            continue
        try:
            content = compose_file.read_text(encoding="utf-8", errors="ignore")
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                continue

            services = data.get("services", {})
            for service_name, service_config in services.items():
                if not isinstance(service_config, dict):
                    continue

                image = service_config.get("image", "")
                if not image:
                    continue

                # Extract base image name (strip tag)
                base_image = image.split(":")[0].split("/")[-1].lower()

                # Check for exact match
                for key, (layer, comp_type, name) in COMPOSE_IMAGE_MAP.items():
                    if key in base_image:
                        comp = InfraComponent(
                            layer=layer,
                            component_type=comp_type,
                            name=f"{name} ({service_name})",
                            description=f"Docker Compose service '{service_name}' using image '{image}'",
                            technologies=(image,),
                            code_locations=(),
                            config_locations=(
                                str(compose_file.relative_to(repo_path)),
                            ),
                            confidence=0.9,
                            detection_method="manifest",
                        )
                        components.append(comp)
                        break
        except (yaml.YAMLError, OSError, AttributeError):
            continue

    return components


# ---------------------------------------------------------------------------
# Kubernetes Manifest Parser
# ---------------------------------------------------------------------------

K8S_KIND_MAP: Final[dict[str, tuple[str, str, str]]] = {
    # Delivery
    "Ingress": ("delivery", "reverse_proxy", "Kubernetes Ingress"),
    "IngressClass": ("delivery", "reverse_proxy", "Kubernetes Ingress Class"),
    "Gateway": ("delivery", "api_gateway", "Gateway API Gateway"),
    "HTTPRoute": ("delivery", "api_gateway", "Gateway API HTTPRoute"),
    "Service": ("delivery", "load_balancer", "Kubernetes Service"),
    # Config/Security
    "ConfigMap": ("deployment", "ci_cd_pipeline", "Kubernetes ConfigMap"),
    "Secret": ("security", "secrets_management", "Kubernetes Secret"),
    # Deployment
    "Deployment": ("deployment", "containerization", "Kubernetes Deployment"),
    "StatefulSet": ("deployment", "containerization", "Kubernetes StatefulSet"),
    "DaemonSet": ("deployment", "containerization", "Kubernetes DaemonSet"),
    "Job": ("deployment", "ci_cd_pipeline", "Kubernetes Job"),
    "CronJob": ("deployment", "ci_cd_pipeline", "Kubernetes CronJob"),
    # Storage
    "PersistentVolume": ("data", "relational_database", "Kubernetes PersistentVolume"),
    "PersistentVolumeClaim": ("data", "relational_database", "Kubernetes PVC"),
    "StorageClass": ("data", "relational_database", "Kubernetes StorageClass"),
    # Security
    "NetworkPolicy": ("security", "waf", "Kubernetes NetworkPolicy"),
    "Role": ("identity", "authorization", "Kubernetes RBAC Role"),
    "ClusterRole": ("identity", "authorization", "Kubernetes RBAC ClusterRole"),
    "RoleBinding": ("identity", "authorization", "Kubernetes RBAC RoleBinding"),
    "ClusterRoleBinding": (
        "identity",
        "authorization",
        "Kubernetes RBAC ClusterRoleBinding",
    ),
    # Scaling
    "HorizontalPodAutoscaler": ("deployment", "deployment", "Kubernetes HPA"),
    "VerticalPodAutoscaler": ("deployment", "deployment", "Kubernetes VPA"),
    # Service Mesh
    "VirtualService": ("delivery", "api_gateway", "Istio VirtualService"),
    "DestinationRule": ("delivery", "api_gateway", "Istio DestinationRule"),
    "IstioGateway": ("delivery", "api_gateway", "Istio Gateway"),
    "ServiceEntry": ("integration", "third_party_api", "Istio ServiceEntry"),
}


def parse_kubernetes_manifests(repo_path: Path) -> list[InfraComponent]:
    """Parse Kubernetes YAML manifests for infrastructure components."""
    components = []

    for yaml_file in repo_path.rglob("*.yaml"):
        if any(
            part in {".git", ".venv", "venv", "env", "node_modules", "__pycache__"}
            for part in yaml_file.parts
        ):
            continue
        # Also check .yml extension
        try:
            content = yaml_file.read_text(encoding="utf-8", errors="ignore")
            # Parse all documents in the YAML file
            for doc in yaml.safe_load_all(content):
                if not isinstance(doc, dict):
                    continue
                kind = doc.get("kind")
                if kind in K8S_KIND_MAP:
                    layer, comp_type, name = K8S_KIND_MAP[kind]
                    metadata = doc.get("metadata", {})
                    resource_name = metadata.get("name", "unnamed")
                    namespace = metadata.get("namespace", "default")

                    comp = InfraComponent(
                        layer=layer,
                        component_type=comp_type,
                        name=f"{name} ({resource_name})",
                        description=f"Kubernetes {kind} '{resource_name}' in namespace '{namespace}'",
                        technologies=("Kubernetes",),
                        code_locations=(),
                        config_locations=(str(yaml_file.relative_to(repo_path)),),
                        confidence=0.85,
                        detection_method="manifest",
                    )
                    components.append(comp)
        except (yaml.YAMLError, OSError, AttributeError):
            continue

    # Also check .yml files
    for yml_file in repo_path.rglob("*.yml"):
        if any(
            part in {".git", ".venv", "venv", "env", "node_modules", "__pycache__"}
            for part in yml_file.parts
        ):
            continue
        try:
            content = yml_file.read_text(encoding="utf-8", errors="ignore")
            for doc in yaml.safe_load_all(content):
                if not isinstance(doc, dict):
                    continue
                kind = doc.get("kind")
                if kind in K8S_KIND_MAP:
                    layer, comp_type, name = K8S_KIND_MAP[kind]
                    metadata = doc.get("metadata", {})
                    resource_name = metadata.get("name", "unnamed")
                    namespace = metadata.get("namespace", "default")

                    comp = InfraComponent(
                        layer=layer,
                        component_type=comp_type,
                        name=f"{name} ({resource_name})",
                        description=f"Kubernetes {kind} '{resource_name}' in namespace '{namespace}'",
                        technologies=("Kubernetes",),
                        code_locations=(),
                        config_locations=(str(yml_file.relative_to(repo_path)),),
                        confidence=0.85,
                        detection_method="manifest",
                    )
                    components.append(comp)
        except (yaml.YAMLError, OSError, AttributeError):
            continue

    return components


# ---------------------------------------------------------------------------
# Terraform Parser
# ---------------------------------------------------------------------------

TERRAFORM_RESOURCE_MAP: Final[dict[str, tuple[str, str, str]]] = {
    # AWS
    "aws_db_instance": ("data", "relational_database", "AWS RDS Instance"),
    "aws_rds_cluster": ("data", "relational_database", "AWS RDS Cluster"),
    "aws_elasticache_cluster": ("state", "cache_layer", "AWS ElastiCache"),
    "aws_elasticache_replication_group": (
        "state",
        "cache_layer",
        "AWS ElastiCache Replication Group",
    ),
    "aws_s3_bucket": ("data", "object_storage", "AWS S3 Bucket"),
    "aws_dynamodb_table": ("data", "document_database", "AWS DynamoDB Table"),
    "aws_redshift_cluster": ("data", "data_warehouse", "AWS Redshift"),
    "aws_elasticsearch_domain": ("data", "search_engine", "AWS Elasticsearch"),
    "aws_opensearch_domain": ("data", "search_engine", "AWS OpenSearch"),
    "aws_kinesis_stream": ("communication", "message_queue", "AWS Kinesis"),
    "aws_sqs_queue": ("communication", "message_queue", "AWS SQS"),
    "aws_sns_topic": ("communication", "message_queue", "AWS SNS"),
    "aws_msk_cluster": ("communication", "message_queue", "AWS MSK Kafka"),
    "aws_mq_broker": ("communication", "message_queue", "AWS MQ"),
    "aws_lb": ("delivery", "load_balancer", "AWS ALB/NLB"),
    "aws_alb": ("delivery", "load_balancer", "AWS ALB"),
    "aws_nlb": ("delivery", "load_balancer", "AWS NLB"),
    "aws_cloudfront_distribution": ("delivery", "cdn", "AWS CloudFront"),
    "aws_apigatewayv2_api": ("delivery", "api_gateway", "AWS API Gateway v2"),
    "aws_apigateway_rest_api": ("delivery", "api_gateway", "AWS API Gateway REST"),
    "aws_wafv2_web_acl": ("security", "waf", "AWS WAF"),
    "aws_cognito_user_pool": ("identity", "authentication", "AWS Cognito User Pool"),
    "aws_kms_key": ("security", "encryption", "AWS KMS Key"),
    "aws_secretsmanager_secret": (
        "security",
        "secrets_management",
        "AWS Secrets Manager",
    ),
    "aws_ecs_cluster": ("deployment", "containerization", "AWS ECS Cluster"),
    "aws_eks_cluster": ("deployment", "kubernetes", "AWS EKS Cluster"),
    "aws_ecr_repository": ("deployment", "artifact_registry", "AWS ECR Repository"),
    "aws_autoscaling_group": ("deployment", "deployment", "AWS Auto Scaling Group"),
    "aws_route53_zone": ("delivery", "cdn", "AWS Route53"),
    "aws_cloudwatch_log_group": ("observability", "logging", "AWS CloudWatch Logs"),
    "aws_cloudwatch_metric_alarm": ("observability", "metrics", "AWS CloudWatch Alarm"),
    # GCP
    "google_sql_database_instance": ("data", "relational_database", "GCP Cloud SQL"),
    "google_storage_bucket": ("data", "object_storage", "GCP Cloud Storage"),
    "google_firestore_database": ("data", "document_database", "GCP Firestore"),
    "google_spanner_instance": ("data", "relational_database", "GCP Spanner"),
    "google_bigquery_dataset": ("data", "data_warehouse", "GCP BigQuery"),
    "google_pubsub_topic": ("communication", "message_queue", "GCP Pub/Sub"),
    "google_cloud_run_service": ("deployment", "containerization", "GCP Cloud Run"),
    "google_kubernetes_engine_cluster": ("deployment", "kubernetes", "GCP GKE"),
    "google_artifact_registry_repository": (
        "deployment",
        "artifact_registry",
        "GCP Artifact Registry",
    ),
    "google_compute_ssl_policy": ("security", "encryption", "GCP SSL Policy"),
    "google_kms_key_ring": ("security", "encryption", "GCP KMS"),
    "google_secret_manager_secret": (
        "security",
        "secrets_management",
        "GCP Secret Manager",
    ),
    # Azure
    "azurerm_postgresql_server": ("data", "relational_database", "Azure PostgreSQL"),
    "azurerm_mysql_server": ("data", "relational_database", "Azure MySQL"),
    "azurerm_storage_account": ("data", "object_storage", "Azure Blob Storage"),
    "azurerm_cosmosdb_account": ("data", "document_database", "Azure Cosmos DB"),
    "azurerm_synapse_workspace": ("data", "data_warehouse", "Azure Synapse"),
    "azurerm_servicebus_namespace": (
        "communication",
        "message_queue",
        "Azure Service Bus",
    ),
    "azurerm_eventhub_namespace": (
        "communication",
        "message_queue",
        "Azure Event Hubs",
    ),
    "azurerm_lb": ("delivery", "load_balancer", "Azure Load Balancer"),
    "azurerm_application_gateway": (
        "delivery",
        "api_gateway",
        "Azure Application Gateway",
    ),
    "azurerm_front_door": ("delivery", "cdn", "Azure Front Door"),
    "azurerm_cdn_profile": ("delivery", "cdn", "Azure CDN"),
    "azurerm_key_vault": ("security", "secrets_management", "Azure Key Vault"),
    "azurerm_kubernetes_cluster": ("deployment", "kubernetes", "Azure AKS"),
    "azurerm_container_registry": (
        "deployment",
        "artifact_registry",
        "Azure Container Registry",
    ),
}


def parse_terraform_files(repo_path: Path) -> list[InfraComponent]:
    """Parse Terraform .tf files for infrastructure components."""
    components = []

    for tf_file in repo_path.rglob("*.tf"):
        if any(
            part in {".git", ".venv", "venv", "env", "node_modules"}
            for part in tf_file.parts
        ):
            continue
        try:
            content = tf_file.read_text(encoding="utf-8", errors="ignore")
            # Find resource blocks: resource "type" "name" { ... }
            # Simple regex - handles basic cases
            for match in re.finditer(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', content):
                resource_type = match.group(1)
                resource_name = match.group(2)

                if resource_type in TERRAFORM_RESOURCE_MAP:
                    layer, comp_type, name = TERRAFORM_RESOURCE_MAP[resource_type]
                    comp = InfraComponent(
                        layer=layer,
                        component_type=comp_type,
                        name=f"{name} ({resource_name})",
                        description=f"Terraform resource '{resource_type}' named '{resource_name}'",
                        technologies=("Terraform",),
                        code_locations=(),
                        config_locations=(str(tf_file.relative_to(repo_path)),),
                        confidence=0.9,
                        detection_method="manifest",
                    )
                    components.append(comp)
        except (OSError, AttributeError):
            continue

    return components


# ---------------------------------------------------------------------------
# CI/CD Config Parser
# ---------------------------------------------------------------------------

CI_CD_FILE_PATTERNS: Final[dict[str, tuple[str, str, str]]] = {
    ".github/workflows": ("deployment", "ci_cd_pipeline", "GitHub Actions"),
    ".gitlab-ci.yml": ("deployment", "ci_cd_pipeline", "GitLab CI"),
    "Jenkinsfile": ("deployment", "ci_cd_pipeline", "Jenkins"),
    ".circleci/config.yml": ("deployment", "ci_cd_pipeline", "CircleCI"),
    ".drone.yml": ("deployment", "ci_cd_pipeline", "Drone CI"),
    "azure-pipelines.yml": ("deployment", "ci_cd_pipeline", "Azure Pipelines"),
    "bitbucket-pipelines.yml": ("deployment", "ci_cd_pipeline", "Bitbucket Pipelines"),
    ".travis.yml": ("deployment", "ci_cd_pipeline", "Travis CI"),
    "buildkite.yml": ("deployment", "ci_cd_pipeline", "Buildkite"),
    "semaphore.yml": ("deployment", "ci_cd_pipeline", "Semaphore CI"),
    "codefresh.yml": ("deployment", "ci_cd_pipeline", "Codefresh"),
    "buddy.yml": ("deployment", "ci_cd_pipeline", "Buddy CI"),
    "teamcity-configs": ("deployment", "ci_cd_pipeline", "TeamCity"),
    "bamboo-specs": ("deployment", "ci_cd_pipeline", "Bamboo"),
    "concourse": ("deployment", "ci_cd_pipeline", "Concourse CI"),
    "woodpecker.yml": ("deployment", "ci_cd_pipeline", "Woodpecker CI"),
    "tekton": ("deployment", "ci_cd_pipeline", "Tekton"),
    "argo": ("deployment", "ci_cd_pipeline", "Argo"),
    "flux": ("deployment", "ci_cd_pipeline", "Flux CD"),
}


def parse_ci_cd_configs(repo_path: Path) -> list[InfraComponent]:
    """Parse CI/CD configuration files."""
    components = []

    # GitHub Actions
    github_workflows = repo_path / ".github" / "workflows"
    if github_workflows.exists():
        for wf_file in github_workflows.glob("*.y*ml"):
            try:
                content = wf_file.read_text(encoding="utf-8", errors="ignore")
                data = yaml.safe_load(content)
                if isinstance(data, dict):
                    jobs = data.get("jobs", {})
                    job_names = list(jobs.keys())
                    comp = InfraComponent(
                        layer="deployment",
                        component_type="ci_cd_pipeline",
                        name=f"GitHub Actions Workflow ({wf_file.stem})",
                        description=f"GitHub Actions workflow with {len(job_names)} job(s): {', '.join(job_names[:5])}",
                        technologies=("GitHub Actions",),
                        code_locations=(),
                        config_locations=(str(wf_file.relative_to(repo_path)),),
                        confidence=0.95,
                        detection_method="manifest",
                    )
                    components.append(comp)
            except (yaml.YAMLError, OSError):
                continue

    # GitLab CI
    gitlab_ci = repo_path / ".gitlab-ci.yml"
    if gitlab_ci.exists():
        try:
            content = gitlab_ci.read_text(encoding="utf-8", errors="ignore")
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                jobs = {
                    k: v
                    for k, v in data.items()
                    if isinstance(v, dict) and "script" in v
                }
                comp = InfraComponent(
                    layer="deployment",
                    component_type="ci_cd_pipeline",
                    name="GitLab CI Pipeline",
                    description=f"GitLab CI pipeline with {len(jobs)} job(s)",
                    technologies=("GitLab CI",),
                    code_locations=(),
                    config_locations=(str(gitlab_ci.relative_to(repo_path)),),
                    confidence=0.95,
                    detection_method="manifest",
                )
                components.append(comp)
        except (yaml.YAMLError, OSError):
            pass

    # Jenkinsfile
    jenkinsfile = repo_path / "Jenkinsfile"
    if jenkinsfile.exists():
        comp = InfraComponent(
            layer="deployment",
            component_type="ci_cd_pipeline",
            name="Jenkins Pipeline",
            description="Jenkins pipeline definition found",
            technologies=("Jenkins",),
            code_locations=(),
            config_locations=(str(jenkinsfile.relative_to(repo_path)),),
            confidence=0.9,
            detection_method="manifest",
        )
        components.append(comp)

    return components


# ---------------------------------------------------------------------------
# .env File Parser
# ---------------------------------------------------------------------------

ENV_VAR_MAP: Final[dict[str, tuple[str, str, str]]] = {
    # Databases
    "DATABASE_URL": ("data", "relational_database", "Database Connection"),
    "DB_URL": ("data", "relational_database", "Database Connection"),
    "POSTGRES_URL": ("data", "relational_database", "PostgreSQL Connection"),
    "MYSQL_URL": ("data", "relational_database", "MySQL Connection"),
    "MONGODB_URI": ("data", "document_database", "MongoDB Connection"),
    "REDIS_URL": ("state", "cache_layer", "Redis Connection"),
    "REDIS_URI": ("state", "cache_layer", "Redis Connection"),
    "MEMCACHED_URL": ("state", "cache_layer", "Memcached Connection"),
    # Search
    "ELASTICSEARCH_URL": ("data", "search_engine", "Elasticsearch Connection"),
    "OPENSEARCH_URL": ("data", "search_engine", "OpenSearch Connection"),
    "ALGOLIA_APP_ID": ("data", "search_engine", "Algolia"),
    "ALGOLIA_API_KEY": ("data", "search_engine", "Algolia"),
    "MEILISEARCH_HOST": ("data", "search_engine", "Meilisearch"),
    "MEILISEARCH_API_KEY": ("data", "search_engine", "Meilisearch"),
    # Message Queues
    "RABBITMQ_URL": ("communication", "message_queue", "RabbitMQ"),
    "KAFKA_BROKERS": ("communication", "message_queue", "Kafka"),
    "KAFKA_BOOTSTRAP_SERVERS": ("communication", "message_queue", "Kafka"),
    "NATS_URL": ("communication", "message_queue", "NATS"),
    "SQS_QUEUE_URL": ("communication", "message_queue", "AWS SQS"),
    "SNS_TOPIC_ARN": ("communication", "message_queue", "AWS SNS"),
    # Object Storage
    "AWS_S3_BUCKET": ("data", "object_storage", "AWS S3"),
    "S3_BUCKET": ("data", "object_storage", "AWS S3"),
    "GCS_BUCKET": ("data", "object_storage", "GCP Cloud Storage"),
    "AZURE_STORAGE_CONTAINER": ("data", "object_storage", "Azure Blob Storage"),
    "MINIO_ENDPOINT": ("data", "object_storage", "MinIO"),
    "MINIO_ACCESS_KEY": ("data", "object_storage", "MinIO"),
    "MINIO_SECRET_KEY": ("data", "object_storage", "MinIO"),
    # CDN/Delivery
    "CLOUDFLARE_ZONE_ID": ("delivery", "cdn", "Cloudflare"),
    "CLOUDFLARE_API_TOKEN": ("delivery", "cdn", "Cloudflare"),
    "CLOUDFRONT_DISTRIBUTION_ID": ("delivery", "cdn", "AWS CloudFront"),
    "CDN_URL": ("delivery", "cdn", "CDN"),
    # Auth
    "JWT_SECRET": ("identity", "authentication", "JWT Secret"),
    "JWT_PRIVATE_KEY": ("identity", "authentication", "JWT Private Key"),
    "JWT_PUBLIC_KEY": ("identity", "authentication", "JWT Public Key"),
    "OAUTH_CLIENT_ID": ("identity", "authentication", "OAuth Client ID"),
    "OAUTH_CLIENT_SECRET": ("identity", "authentication", "OAuth Client Secret"),
    "GOOGLE_CLIENT_ID": ("identity", "authentication", "Google OAuth"),
    "GOOGLE_CLIENT_SECRET": ("identity", "authentication", "Google OAuth"),
    "GITHUB_CLIENT_ID": ("identity", "authentication", "GitHub OAuth"),
    "GITHUB_CLIENT_SECRET": ("identity", "authentication", "GitHub OAuth"),
    "AUTH0_DOMAIN": ("identity", "authentication", "Auth0"),
    "AUTH0_CLIENT_ID": ("identity", "authentication", "Auth0 Client ID"),
    "AUTH0_CLIENT_SECRET": ("identity", "authentication", "Auth0 Client Secret"),
    "OKTA_DOMAIN": ("identity", "authentication", "Okta"),
    "OKTA_CLIENT_ID": ("identity", "authentication", "Okta Client ID"),
    "OKTA_CLIENT_SECRET": ("identity", "authentication", "Okta Client Secret"),
    # Payments
    "STRIPE_SECRET_KEY": ("transaction", "payment_gateway", "Stripe"),
    "STRIPE_PUBLISHABLE_KEY": ("transaction", "payment_gateway", "Stripe"),
    "PAYPAL_CLIENT_ID": ("transaction", "payment_gateway", "PayPal"),
    "PAYPAL_CLIENT_SECRET": ("transaction", "payment_gateway", "PayPal"),
    "BRAINTREE_MERCHANT_ID": ("transaction", "payment_gateway", "Braintree"),
    "BRAINTREE_PUBLIC_KEY": ("transaction", "payment_gateway", "Braintree"),
    "BRAINTREE_PRIVATE_KEY": ("transaction", "payment_gateway", "Braintree"),
    "ADYEN_API_KEY": ("transaction", "payment_gateway", "Adyen"),
    "RAZORPAY_KEY_ID": ("transaction", "payment_gateway", "Razorpay"),
    "RAZORPAY_KEY_SECRET": ("transaction", "payment_gateway", "Razorpay"),
    # Email/Communication
    "SENDGRID_API_KEY": ("communication", "third_party_api", "SendGrid"),
    "MAILGUN_API_KEY": ("communication", "third_party_api", "Mailgun"),
    "POSTMARK_API_TOKEN": ("communication", "third_party_api", "Postmark"),
    "AWS_SES_ACCESS_KEY": ("communication", "third_party_api", "AWS SES"),
    "TWILIO_ACCOUNT_SID": ("communication", "third_party_api", "Twilio"),
    "TWILIO_AUTH_TOKEN": ("communication", "third_party_api", "Twilio"),
    # Observability
    "SENTRY_DSN": ("observability", "error_tracking", "Sentry"),
    "DATADOG_API_KEY": ("observability", "metrics", "Datadog"),
    "DATADOG_APP_KEY": ("observability", "metrics", "Datadog"),
    "NEW_RELIC_LICENSE_KEY": ("observability", "metrics", "New Relic"),
    "NEW_RELIC_APP_NAME": ("observability", "metrics", "New Relic"),
    "GRAFANA_API_KEY": ("observability", "metrics", "Grafana"),
    "PROMETHEUS_URL": ("observability", "metrics", "Prometheus"),
    "JAEGER_ENDPOINT": ("observability", "distributed_tracing", "Jaeger"),
    "ZIPKIN_ENDPOINT": ("observability", "distributed_tracing", "Zipkin"),
    "OTEL_EXPORTER_OTLP_ENDPOINT": (
        "observability",
        "distributed_tracing",
        "OpenTelemetry",
    ),
    "OTEL_EXPORTER_JAEGER_ENDPOINT": ("observability", "distributed_tracing", "Jaeger"),
    # Secrets
    "VAULT_ADDR": ("security", "secrets_management", "HashiCorp Vault"),
    "VAULT_TOKEN": ("security", "secrets_management", "HashiCorp Vault"),
    "AWS_SECRET_ACCESS_KEY": ("security", "secrets_management", "AWS Secrets Manager"),
    "AWS_ACCESS_KEY_ID": ("security", "secrets_management", "AWS Credentials"),
    "AZURE_KEY_VAULT_URI": ("security", "secrets_management", "Azure Key Vault"),
    "GCP_PROJECT_ID": ("security", "secrets_management", "GCP Secret Manager"),
    "FASTLY_API_TOKEN": ("delivery", "cdn", "Fastly"),
    "AKAMAI_API_TOKEN": ("delivery", "cdn", "Akamai"),
    # Terraform
    "TF_VAR_": ("deployment", "iac", "Terraform Variable"),
    # Kubernetes
    "KUBECONFIG": ("deployment", "kubernetes", "Kubernetes Config"),
    # Feature Flags
    "LAUNCHDARKLY_SDK_KEY": ("state", "feature_flag", "LaunchDarkly"),
    "SPLIT_IO_API_KEY": ("state", "feature_flag", "Split.io"),
    "UNLEASH_API_TOKEN": ("state", "feature_flag", "Unleash"),
    "FLAGSMITH_API_KEY": ("state", "feature_flag", "Flagsmith"),
    # A/B Testing
    "OPTIMIZELY_SDK_KEY": ("user_experience", "ab_testing", "Optimizely"),
    "VWO_API_KEY": ("user_experience", "ab_testing", "VWO"),
    "AMPLITUDE_API_KEY": ("user_experience", "ab_testing", "Amplitude"),
    "MIXPANEL_TOKEN": ("user_experience", "ab_testing", "Mixpanel"),
    "POSTHOG_API_KEY": ("user_experience", "ab_testing", "PostHog"),
    # Webhooks
    "WEBHOOK_SECRET": ("integration", "webhook", "Webhook Secret"),
    "STRIPE_WEBHOOK_SECRET": ("integration", "webhook", "Stripe Webhook"),
    "GITHUB_WEBHOOK_SECRET": ("integration", "webhook", "GitHub Webhook"),
    # ML/AI
    "OPENAI_API_KEY": ("integration", "third_party_api", "OpenAI"),
    "ANTHROPIC_API_KEY": ("integration", "third_party_api", "Anthropic"),
    "GOOGLE_AI_API_KEY": ("integration", "third_party_api", "Google AI"),
    "COHERE_API_KEY": ("integration", "third_party_api", "Cohere"),
    "HUGGINGFACE_API_TOKEN": ("integration", "third_party_api", "Hugging Face"),
    # Cloud
    "AWS_REGION": ("deployment", "containerization", "AWS Region"),
    "GOOGLE_APPLICATION_CREDENTIALS": (
        "deployment",
        "containerization",
        "GCP Credentials",
    ),
    "AZURE_SUBSCRIPTION_ID": ("deployment", "containerization", "Azure Subscription"),
    "AZURE_TENANT_ID": ("deployment", "containerization", "Azure Tenant"),
    "AZURE_CLIENT_ID": ("deployment", "containerization", "Azure Client ID"),
    "AZURE_CLIENT_SECRET": ("deployment", "containerization", "Azure Client Secret"),
}


def parse_env_files(repo_path: Path) -> list[InfraComponent]:
    """Parse .env and .env.* files for infrastructure signals."""
    components = []

    for env_file in repo_path.rglob(".env*"):
        if any(
            part in {".git", ".venv", "venv", "env", "node_modules"}
            for part in env_file.parts
        ):
            continue
        try:
            content = env_file.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key = line.split("=")[0].strip()
                # Check exact match
                if key in ENV_VAR_MAP:
                    layer, comp_type, name = ENV_VAR_MAP[key]
                    comp = InfraComponent(
                        layer=layer,
                        component_type=comp_type,
                        name=f"{name} ({key})",
                        description=f"Environment variable '{key}' found in {env_file.name}",
                        technologies=(key,),
                        code_locations=(),
                        config_locations=(str(env_file.relative_to(repo_path)),),
                        confidence=0.85,
                        detection_method="config_parse",
                    )
                    components.append(comp)
                    continue
                # Check prefix match
                for prefix, (layer, comp_type, name) in ENV_VAR_MAP.items():
                    if prefix.endswith("_") and key.startswith(prefix):
                        comp = InfraComponent(
                            layer=layer,
                            component_type=comp_type,
                            name=f"{name} ({key})",
                            description=f"Environment variable '{key}' (prefix '{prefix}') found in {env_file.name}",
                            technologies=(key,),
                            code_locations=(),
                            config_locations=(str(env_file.relative_to(repo_path)),),
                            confidence=0.75,
                            detection_method="config_parse",
                        )
                        components.append(comp)
                        break
        except OSError:
            continue

    return components


# ---------------------------------------------------------------------------
# Web Server Config Parser
# ---------------------------------------------------------------------------


def parse_nginx_config(repo_path: Path) -> list[InfraComponent]:
    """Parse nginx configuration files."""
    components = []

    for nginx_file in repo_path.rglob("nginx*.conf"):
        if any(
            part in {".git", ".venv", "venv", "env", "node_modules"}
            for part in nginx_file.parts
        ):
            continue
        try:
            content = nginx_file.read_text(encoding="utf-8", errors="ignore")
            # Check for common nginx patterns
            detected = []

            if "proxy_pass" in content:
                detected.append(("delivery", "reverse_proxy", "NGINX Reverse Proxy"))
            if "upstream" in content:
                detected.append(
                    ("delivery", "load_balancer", "NGINX Upstream/Load Balancer")
                )
            if "ssl_certificate" in content or "ssl_certificate_key" in content:
                detected.append(("security", "encryption", "NGINX SSL/TLS Termination"))
            if "limit_req" in content or "limit_conn" in content:
                detected.append(("governance", "rate_limiting", "NGINX Rate Limiting"))
            if "proxy_cache" in content or "fastcgi_cache" in content:
                detected.append(("state", "cache_layer", "NGINX Caching"))

            for layer, comp_type, name in detected:
                comp = InfraComponent(
                    layer=layer,
                    component_type=comp_type,
                    name=f"{name} ({nginx_file.stem})",
                    description=f"NGINX config '{nginx_file.name}' with {comp_type} configuration",
                    technologies=("NGINX",),
                    code_locations=(),
                    config_locations=(str(nginx_file.relative_to(repo_path)),),
                    confidence=0.9,
                    detection_method="config_parse",
                )
                components.append(comp)
        except OSError:
            continue

    return components


def parse_caddy_config(repo_path: Path) -> list[InfraComponent]:
    """Parse Caddyfile configurations."""
    components = []

    for caddy_file in repo_path.rglob("Caddyfile*"):
        if any(
            part in {".git", ".venv", "venv", "env", "node_modules"}
            for part in caddy_file.parts
        ):
            continue
        try:
            content = caddy_file.read_text(encoding="utf-8", errors="ignore")
            detected = []

            if "reverse_proxy" in content:
                detected.append(("delivery", "reverse_proxy", "Caddy Reverse Proxy"))
            if "tls" in content or "https://" in content:
                detected.append(("security", "encryption", "Caddy Automatic HTTPS"))
            if "rate_limit" in content:
                detected.append(("governance", "rate_limiting", "Caddy Rate Limiting"))
            if "cache" in content:
                detected.append(("state", "cache_layer", "Caddy Caching"))

            for layer, comp_type, name in detected:
                comp = InfraComponent(
                    layer=layer,
                    component_type=comp_type,
                    name=f"{name} ({caddy_file.stem})",
                    description=f"Caddy config with {comp_type} configuration",
                    technologies=("Caddy",),
                    code_locations=(),
                    config_locations=(str(caddy_file.relative_to(repo_path)),),
                    confidence=0.9,
                    detection_method="config_parse",
                )
                components.append(comp)
        except OSError:
            continue

    return components


# ---------------------------------------------------------------------------
# Main Config Parser Orchestrator
# ---------------------------------------------------------------------------


def parse_all_configs(repo_path: Path) -> list[InfraComponent]:
    """Run all config parsers and combine results."""
    all_components = []

    all_components.extend(parse_docker_compose(repo_path))
    all_components.extend(parse_kubernetes_manifests(repo_path))
    all_components.extend(parse_terraform_files(repo_path))
    all_components.extend(parse_ci_cd_configs(repo_path))
    all_components.extend(parse_env_files(repo_path))
    all_components.extend(parse_nginx_config(repo_path))
    all_components.extend(parse_caddy_config(repo_path))

    return all_components
