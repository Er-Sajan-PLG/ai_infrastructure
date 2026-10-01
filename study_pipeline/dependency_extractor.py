"""Deterministic dependency extraction for studied repositories.

WHAT THIS EXTRACTS
------------------
Structured dependency data from manifest files: name, version, category,
language, and dev/prod classification. No LLM calls, no resolution, no
network access — only static parsing of declared manifests.

The output is a tuple of `Dependency` frozen dataclasses, designed to be
included in the study report alongside the stack detection.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Dependency:
    """A single declared dependency with metadata."""

    name: str
    version: str | None
    category: str
    language: str
    is_dev: bool

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for report serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "language": self.language,
            "is_dev": self.is_dev,
        }


# ---------------------------------------------------------------------------
# Category keywords for auto-categorization
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "web-framework": (
        "fastapi",
        "flask",
        "django",
        "starlette",
        "aiohttp",
        "quart",
        "tornado",
        "sanic",
        "express",
        "koa",
        "fastify",
        "nestjs",
        "gin",
        "echo",
        "fiber",
        "chi",
        "actix-web",
        "axum",
        "rocket",
        "warp",
        "spring-boot",
        "micronaut",
        "quarkus",
        "rails",
        "laravel",
        "symfony",
        "nextjs",
        "nuxt",
        "vue",
        "svelte",
        "angular",
        "react",
        "sveltekit",
    ),
    "orm": (
        "sqlalchemy",
        "tortoise-orm",
        "prisma",
        "gorm",
        "sqlx",
        "diesel",
        "sequelize",
        "typeorm",
        "mongoose",
        "drizzle-orm",
        "knex",
        "bookshelf",
        "waterline",
        "hibernate",
        "mybatis",
        "jdbi",
        "jdbctemplate",
        "entity-framework",
        "ef-core",
    ),
    "database-driver": (
        "psycopg2",
        "pg8000",
        "asyncpg",
        "pymysql",
        "mysqlclient",
        "mysql-connector",
        "pymongo",
        "motor",
        "redis",
        "redis-py",
        "cassandra-driver",
        "elasticsearch",
        "elasticsearch-dsl",
        "sqlite3",
        "pysqlite",
        "pyodbc",
        "cx-oracle",
        "ibm-db",
        "psycopg",
        "aiopg",
        "asyncmy",
        "aiomysql",
    ),
    "testing": (
        "pytest",
        "vitest",
        "jest",
        "mocha",
        "jasmine",
        "cypress",
        "playwright",
        "selenium",
        "webdriverio",
        "testcafe",
        "unittest",
        "doctest",
        "tox",
        "coverage",
        "pytest-cov",
        "hypothesis",
        "factory-boy",
        "faker",
        "mock",
        "pytest-mock",
        "junit",
        "testng",
        "mockito",
        "assertj",
        "spock",
        "scalatest",
        "rspec",
        "minitest",
        "cucumber",
        "godog",
    ),
    "auth": (
        "authlib",
        "python-jose",
        "pyjwt",
        "passlib",
        "bcrypt",
        "argon2",
        "django-allauth",
        "fastapi-users",
        "next-auth",
        "clerk",
        "firebase-admin",
        "aws-cognito",
        "okta",
        "keycloak",
        "spring-security",
        "keycloak-spring-boot-starter",
    ),
    "http-client": (
        "httpx",
        "requests",
        "aiohttp",
        "httplib2",
        "urllib3",
        "axios",
        "ky",
        "superagent",
        "got",
        "node-fetch",
        "okhttp",
        "retrofit",
        "feign",
        "resttemplate",
    ),
    "serialization": (
        "pydantic",
        "marshmallow",
        "serde",
        "serde_json",
        "serde_yaml",
        "toml",
        "tomli",
        "tomllib",
        "yaml",
        "pyyaml",
        "orjson",
        "ujson",
        "simplejson",
        "msgpack",
        "protobuf",
        "protobuf-python",
        "avro",
        "thrift",
        "capnproto",
    ),
    "config": (
        "pydantic-settings",
        "python-dotenv",
        "dotenv",
        "configparser",
        "confluent-kafka",
        "aiokafka",
        "kafka-python",
        "pika",
        "aio-pika",
        "celery",
        "dramatiq",
        "huey",
        "rq",
        "redis-rq",
    ),
    "logging": (
        "loguru",
        "structlog",
        "python-json-logger",
        "sentry-sdk",
        "rollbar",
        "bugsnag",
        "airbrake",
        "logstash",
        "fluent-logger",
        "winston",
        "bunyan",
        "pino",
        "zap",
        "logrus",
        "zerolog",
        "slf4j",
        "logback",
        "log4j",
        "micrometer",
    ),
    "monitoring": (
        "prometheus-client",
        "opentelemetry",
        "datadog",
        "newrelic",
        "elastic-apm",
        "statsd",
        "graphite",
        "influxdb",
        "telegraf",
        "jaeger-client",
        "zipkin",
        "skywalking",
    ),
    "cloud-sdk": (
        "boto3",
        "botocore",
        "aws-cdk",
        "google-cloud",
        "google-auth",
        "azure-sdk",
        "azure-identity",
        "azure-mgmt",
        "oci",
        "ibm-cloud",
    ),
    "container": (
        "docker",
        "docker-py",
        "kubernetes",
        "k8s",
        "helm",
        "kustomize",
        "kind",
        "minikube",
        "kubectl",
        "podman",
        "buildah",
    ),
    "ci-cd": (
        "github-actions",
        "gitlab-ci",
        "circleci",
        "jenkins",
        "azure-pipelines",
        "travis",
        "drone",
        "woodpecker",
        "tekton",
        "argo",
        "spinnaker",
    ),
    "ml-framework": (
        "torch",
        "tensorflow",
        "jax",
        "flax",
        "keras",
        "scikit-learn",
        "xgboost",
        "lightgbm",
        "catboost",
        "onnx",
        "onnxruntime",
        "transformers",
        "accelerate",
        "peft",
        "trl",
        "langchain",
        "llama-index",
        "ragas",
        "phoenix",
        "trulens",
        "deepeval",
    ),
    "data-processing": (
        "pandas",
        "numpy",
        "polars",
        "dask",
        "ray",
        "modin",
        "vaex",
        "duckdb",
        "pyarrow",
        "parquet",
        "avro",
        "orc",
        "csv",
        "jsonlines",
    ),
    "async-runtime": (
        "asyncio",
        "uvloop",
        "trio",
        "anyio",
        "tokio",
        "async-std",
        "smol",
        "futures",
        "concurrent",
        "threading",
        "multiprocessing",
    ),
    "cli": (
        "click",
        "typer",
        "argparse",
        "clap",
        "structopt",
        "argh",
        "fire",
        "cmd2",
        "prompt-toolkit",
        "rich",
        "textual",
        "tqdm",
    ),
    "utility": (
        "pydantic",
        "attrs",
        "dataclasses",
        "dataclass-wizard",
        "msgspec",
        "orjson",
        "ujson",
        "python-dateutil",
        "pendulum",
        "arrow",
        "humanize",
        "inflect",
        "slugify",
        "unidecode",
    ),
}

# Build reverse mapping for fast lookup
_KEYWORD_TO_CATEGORY: Final[dict[str, str]] = {}
for cat, keywords in CATEGORY_KEYWORDS.items():
    for kw in keywords:
        _KEYWORD_TO_CATEGORY[kw.lower()] = cat


def categorize_dependency(name: str, language: str) -> str:
    """Auto-categorize a dependency by name."""
    name_lower = name.lower()

    # Direct keyword match
    for keyword, category in _KEYWORD_TO_CATEGORY.items():
        if keyword in name_lower:
            return category

    # Language-specific heuristics
    if language == "python":
        if name_lower.startswith(("django-", "flask-", "fastapi-")):
            return "web-framework"
        if name_lower.startswith(("pytest-", "test-")):
            return "testing"
        if name_lower.endswith(("-client", "-sdk", "-api")):
            return "http-client"
    elif language in ("javascript", "typescript"):
        if name_lower.startswith("@") and "/types-" in name_lower:
            return "types"
        if name_lower.startswith(("eslint-", "prettier-", "@types/")):
            return "tooling"

    return "utility"


# ---------------------------------------------------------------------------
# Version normalization
# ---------------------------------------------------------------------------


def normalize_version(version: str | None) -> str | None:
    """Normalize version string to a consistent format."""
    if not version:
        return None
    # Strip common prefixes
    version = version.strip()
    for prefix in ("^", "~", ">=", "<=", ">", "<", "==", "!="):
        if version.startswith(prefix):
            version = version[len(prefix) :]
            break
    # Handle npm-style version ranges
    if "||" in version:
        version = version.split("||")[0].strip()
    if " " in version and not version.startswith("file:"):
        version = version.split(" ")[0]
    return version if version else None


# ---------------------------------------------------------------------------
# Parser implementations
# ---------------------------------------------------------------------------


def parse_python_dependencies(repo_path: Path) -> list[Dependency]:
    """Parse Python dependencies from pyproject.toml, requirements.txt, etc."""
    dependencies = []

    # pyproject.toml
    for pyproject in repo_path.rglob("pyproject.toml"):
        if any(part in {".git", ".venv", "venv", "env"} for part in pyproject.parts):
            continue
        try:
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            # [project.dependencies] - standard PEP 621
            for dep in data.get("project", {}).get("dependencies", []):
                name = (
                    dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip()
                )
                version = None
                # Try to extract version from specifier
                if "==" in dep:
                    version = dep.split("==")[-1].strip()
                elif ">=" in dep:
                    version = dep.split(">=")[-1].split(",")[0].strip()
                dependencies.append(
                    Dependency(
                        name=name,
                        version=normalize_version(version),
                        category=categorize_dependency(name, "python"),
                        language="python",
                        is_dev=False,
                    )
                )
            # Top-level dependencies (uv/pip format)
            for dep in data.get("dependencies", []):
                name = (
                    dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip()
                )
                version = None
                if "==" in dep:
                    version = dep.split("==")[-1].strip()
                elif ">=" in dep:
                    version = dep.split(">=")[-1].split(",")[0].strip()
                dependencies.append(
                    Dependency(
                        name=name,
                        version=normalize_version(version),
                        category=categorize_dependency(name, "python"),
                        language="python",
                        is_dev=False,
                    )
                )
            # [tool.poetry.dependencies]
            for name, spec in (
                data.get("tool", {}).get("poetry", {}).get("dependencies", {}).items()
            ):
                if name == "python":
                    continue
                version = None
                if isinstance(spec, str):
                    version = normalize_version(spec)
                elif isinstance(spec, dict) and "version" in spec:
                    version = normalize_version(spec["version"])
                dependencies.append(
                    Dependency(
                        name=name,
                        version=version,
                        category=categorize_dependency(name, "python"),
                        language="python",
                        is_dev=False,
                    )
                )
            # [tool.uv.dependencies]
            for name, spec in (
                data.get("tool", {}).get("uv", {}).get("dependencies", {}).items()
            ):
                version = normalize_version(spec) if isinstance(spec, str) else None
                dependencies.append(
                    Dependency(
                        name=name,
                        version=version,
                        category=categorize_dependency(name, "python"),
                        language="python",
                        is_dev=False,
                    )
                )
        except (tomllib.TOMLDecodeError, OSError):
            pass

    # requirements*.txt
    for req_file in repo_path.rglob("requirements*.txt"):
        if any(part in {".git", ".venv", "venv", "env"} for part in req_file.parts):
            continue
        try:
            for line in req_file.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "-")):
                    continue
                # Handle -r requirements.txt includes (skip for now)
                if line.startswith("-r"):
                    continue
                # Parse name and version
                name = (
                    line.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip()
                )
                version = None
                if "==" in line:
                    version = line.split("==")[-1].split(";")[0].strip()
                elif ">=" in line:
                    version = line.split(">=")[-1].split(",")[0].strip()
                dependencies.append(
                    Dependency(
                        name=name,
                        version=normalize_version(version),
                        category=categorize_dependency(name, "python"),
                        language="python",
                        is_dev="dev" in req_file.name.lower()
                        or "test" in req_file.name.lower(),
                    )
                )
        except OSError:
            pass

    return dependencies


def parse_javascript_dependencies(repo_path: Path) -> list[Dependency]:
    """Parse JavaScript/TypeScript dependencies from package.json."""
    dependencies = []

    for pkg_file in repo_path.rglob("package.json"):
        if any(part in {".git", "node_modules"} for part in pkg_file.parts):
            continue
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            # Production dependencies
            for name, version in data.get("dependencies", {}).items():
                dependencies.append(
                    Dependency(
                        name=name,
                        version=normalize_version(version),
                        category=categorize_dependency(name, "javascript"),
                        language="javascript",
                        is_dev=False,
                    )
                )
            # Dev dependencies
            for name, version in data.get("devDependencies", {}).items():
                dependencies.append(
                    Dependency(
                        name=name,
                        version=normalize_version(version),
                        category=categorize_dependency(name, "javascript"),
                        language="javascript",
                        is_dev=True,
                    )
                )
            # Optional dependencies
            for name, version in data.get("optionalDependencies", {}).items():
                dependencies.append(
                    Dependency(
                        name=name,
                        version=normalize_version(version),
                        category=categorize_dependency(name, "javascript"),
                        language="javascript",
                        is_dev=False,
                    )
                )
        except (json.JSONDecodeError, OSError):
            pass

    return dependencies


def parse_go_dependencies(repo_path: Path) -> list[Dependency]:
    """Parse Go dependencies from go.mod."""
    dependencies = []

    for go_mod in repo_path.rglob("go.mod"):
        if any(part in {".git"} for part in go_mod.parts):
            continue
        try:
            content = go_mod.read_text(encoding="utf-8")
            # Parse require blocks
            import re

            # Multi-line require blocks
            for match in re.finditer(r"require\s+\((.*?)\)", content, re.DOTALL):
                for line in match.group(1).splitlines():
                    line = line.strip()
                    if line and not line.startswith("//"):
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]
                            if version.endswith("// indirect"):
                                version = version[:-12].strip()
                            dependencies.append(
                                Dependency(
                                    name=name,
                                    version=normalize_version(version),
                                    category=categorize_dependency(name, "go"),
                                    language="go",
                                    is_dev="indirect" in line,
                                )
                            )
            # Single-line requires
            for match in re.finditer(r"require\s+([^\s]+)\s+([^\s]+)", content):
                name = match.group(1)
                version = match.group(2)
                dependencies.append(
                    Dependency(
                        name=name,
                        version=normalize_version(version),
                        category=categorize_dependency(name, "go"),
                        language="go",
                        is_dev=False,
                    )
                )
        except OSError:
            pass

    return dependencies


def parse_rust_dependencies(repo_path: Path) -> list[Dependency]:
    """Parse Rust dependencies from Cargo.toml."""
    dependencies = []

    for cargo in repo_path.rglob("Cargo.toml"):
        if any(part in {".git", "target"} for part in cargo.parts):
            continue
        try:
            with cargo.open("rb") as f:
                data = tomllib.load(f)
            # [dependencies]
            for name, spec in data.get("dependencies", {}).items():
                version = None
                if isinstance(spec, str):
                    version = normalize_version(spec)
                elif isinstance(spec, dict) and "version" in spec:
                    version = normalize_version(spec["version"])
                dependencies.append(
                    Dependency(
                        name=name,
                        version=version,
                        category=categorize_dependency(name, "rust"),
                        language="rust",
                        is_dev=False,
                    )
                )
            # [dev-dependencies]
            for name, spec in data.get("dev-dependencies", {}).items():
                version = None
                if isinstance(spec, str):
                    version = normalize_version(spec)
                elif isinstance(spec, dict) and "version" in spec:
                    version = normalize_version(spec["version"])
                dependencies.append(
                    Dependency(
                        name=name,
                        version=version,
                        category=categorize_dependency(name, "rust"),
                        language="rust",
                        is_dev=True,
                    )
                )
        except (tomllib.TOMLDecodeError, OSError):
            pass

    return dependencies


def parse_java_dependencies(repo_path: Path) -> list[Dependency]:
    """Parse Java dependencies from pom.xml and build.gradle."""
    dependencies = []

    # pom.xml
    for pom in repo_path.rglob("pom.xml"):
        if any(part in {".git", "target"} for part in pom.parts):
            continue
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(pom)  # noqa: S314 -- local trusted pom.xml
            ns_uri = "http://maven.apache.org/POM/4.0.0"
            # Use full namespace URI in XPath since pom.xml typically has default namespace
            for dep in tree.findall(f".//{{{ns_uri}}}dependency"):
                group_id = dep.find(f"{{{ns_uri}}}groupId")
                artifact_id = dep.find(f"{{{ns_uri}}}artifactId")
                version = dep.find(f"{{{ns_uri}}}version")
                scope = dep.find(f"{{{ns_uri}}}scope")
                if (
                    group_id is not None
                    and artifact_id is not None
                    and group_id.text is not None
                    and artifact_id.text is not None
                ):
                    name = f"{group_id.text}:{artifact_id.text}"
                    v = version.text if version is not None else None
                    is_dev = scope is not None and scope.text in ("test", "provided")
                    dependencies.append(
                        Dependency(
                            name=name,
                            version=normalize_version(v),
                            category=categorize_dependency(artifact_id.text, "java"),
                            language="java",
                            is_dev=is_dev,
                        )
                    )
        except (ET.ParseError, OSError):
            pass

    # build.gradle (basic)
    for gradle in repo_path.rglob("build.gradle*"):
        if any(part in {".git", "build"} for part in gradle.parts):
            continue
        try:
            content = gradle.read_text(encoding="utf-8", errors="ignore")
            # Look for implementation "group:artifact:version"
            for match in re.finditer(r'implementation\s+["\']([^"\']+)["\']', content):
                dep_str = match.group(1)
                parts = dep_str.split(":")
                if len(parts) >= 2:
                    name = f"{parts[0]}:{parts[1]}"
                    gradle_version: str | None = parts[2] if len(parts) > 2 else None
                    dependencies.append(
                        Dependency(
                            name=name,
                            version=normalize_version(gradle_version),
                            category=categorize_dependency(parts[1], "java"),
                            language="java",
                            is_dev=False,
                        )
                    )
            # Also check testImplementation
            for match in re.finditer(
                r'testImplementation\s+["\']([^"\']+)["\']', content
            ):
                dep_str = match.group(1)
                parts = dep_str.split(":")
                if len(parts) >= 2:
                    name = f"{parts[0]}:{parts[1]}"
                    gradle_version = parts[2] if len(parts) > 2 else None
                    dependencies.append(
                        Dependency(
                            name=name,
                            version=normalize_version(gradle_version),
                            category=categorize_dependency(parts[1], "java"),
                            language="java",
                            is_dev=True,
                        )
                    )
        except OSError:
            pass

    return dependencies


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def extract_dependencies(repo_path: Path) -> tuple[Dependency, ...]:
    """Extract all declared dependencies from a repository."""
    all_deps = []

    all_deps.extend(parse_python_dependencies(repo_path))
    all_deps.extend(parse_javascript_dependencies(repo_path))
    all_deps.extend(parse_go_dependencies(repo_path))
    all_deps.extend(parse_rust_dependencies(repo_path))
    all_deps.extend(parse_java_dependencies(repo_path))

    # Deduplicate by name+language (keep first occurrence)
    seen: set[tuple[str, str]] = set()
    unique_deps = []
    for dep in all_deps:
        key = (dep.name.lower(), dep.language)
        if key not in seen:
            seen.add(key)
            unique_deps.append(dep)

    return tuple(unique_deps)
