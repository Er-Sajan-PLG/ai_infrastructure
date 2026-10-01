"""Deterministic tech stack detection for studied repositories.

WHAT THIS DETECTS
------------------
Languages, frameworks, databases, message queues, cache systems, CI/CD,
containerization, and cloud services — from static analysis only.

No LLM calls, no code execution, no dependency resolution. All signals come
from file extensions, manifest parsing, keyword scanning, and config file
inspection. This is a structural map, not a runtime profile.

The output is a `TechStack` frozen dataclass, designed to be included in the
study report alongside the inventory and pattern candidates.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class FrameworkSignature(TypedDict, total=False):
    """Type for framework detection signatures."""

    dependencies: list[str]
    imports: list[str]
    keywords: list[str]
    file_patterns: list[str]
    config_keywords: list[str]


@dataclass(frozen=True, slots=True)
class TechStack:
    """Detected technology stack of a repository."""

    languages: frozenset[str]
    frameworks: frozenset[str]
    databases: frozenset[str]
    message_queues: frozenset[str]
    cache_systems: frozenset[str]
    ci_cd: frozenset[str]
    containerization: frozenset[str]
    cloud_services: frozenset[str]

    def to_dict(self) -> dict[str, list[str]]:
        """Convert to dictionary for report serialization."""
        return {
            "languages": sorted(self.languages),
            "frameworks": sorted(self.frameworks),
            "databases": sorted(self.databases),
            "message_queues": sorted(self.message_queues),
            "cache_systems": sorted(self.cache_systems),
            "ci_cd": sorted(self.ci_cd),
            "containerization": sorted(self.containerization),
            "cloud_services": sorted(self.cloud_services),
        }


# ---------------------------------------------------------------------------
# Language detection (extends inventory.py's language stats)
# ---------------------------------------------------------------------------

LANGUAGE_EXTENSIONS: Final[dict[str, frozenset[str]]] = {
    "python": frozenset({".py", ".pyi", ".pyx", ".pxd", ".pxi"}),
    "javascript": frozenset({".js", ".jsx", ".mjs", ".cjs"}),
    "typescript": frozenset({".ts", ".tsx", ".mts", ".cts"}),
    "go": frozenset({".go"}),
    "rust": frozenset({".rs"}),
    "java": frozenset({".java"}),
    "kotlin": frozenset({".kt", ".kts"}),
    "scala": frozenset({".scala", ".sc"}),
    "ruby": frozenset({".rb", ".rake", ".gemspec"}),
    "php": frozenset({".php", ".phtml"}),
    "csharp": frozenset({".cs"}),
    "cpp": frozenset({".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}),
    "c": frozenset({".c", ".h"}),
    "swift": frozenset({".swift"}),
    "dart": frozenset({".dart"}),
    "r": frozenset({".r", ".R"}),
    "shell": frozenset({".sh", ".bash", ".zsh", ".fish"}),
    "dockerfile": frozenset({"Dockerfile", "dockerfile"}),
    "html": frozenset({".html", ".htm"}),
    "css": frozenset({".css", ".scss", ".sass", ".less"}),
    "yaml": frozenset({".yaml", ".yml"}),
    "json": frozenset({".json"}),
    "toml": frozenset({".toml"}),
    "xml": frozenset({".xml"}),
    "markdown": frozenset({".md", ".markdown"}),
    "sql": frozenset({".sql"}),
}


def detect_languages(repo_path: Path) -> frozenset[str]:
    """Detect languages from file extensions and key manifest files."""
    languages: set[str] = set()
    skip_dirs = {
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".uv-cache",
        ".cache",
        ".gradle",
        ".cargo",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".eggs",
        "build",
        "dist",
        ".next",
        ".nuxt",
        "target",
        "vendor",
    }

    # Count extensions
    ext_counts: dict[str, int] = {}

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        # Skip if any parent is in skip_dirs
        if any(part in skip_dirs for part in file_path.parts):
            continue

        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        if suffix or name in {"dockerfile"}:
            ext_key = suffix if suffix else name
            ext_counts[ext_key] = ext_counts.get(ext_key, 0) + 1

    # Map extensions to languages
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        if any(ext in ext_counts for ext in exts):
            languages.add(lang)

    # Heuristic: key manifest files imply their language
    if (repo_path / "pom.xml").exists():
        languages.add("java")
    if (repo_path / "build.gradle").exists() or (
        repo_path / "build.gradle.kts"
    ).exists():
        languages.add("java")
    if (repo_path / "Cargo.toml").exists():
        languages.add("rust")
    if (repo_path / "go.mod").exists():
        languages.add("go")
    if (repo_path / "package.json").exists():
        languages.add("javascript")
    if (repo_path / "pyproject.toml").exists() or (
        repo_path / "requirements.txt"
    ).exists():
        languages.add("python")

    return frozenset(languages)


# ---------------------------------------------------------------------------
# Framework signatures
# ---------------------------------------------------------------------------

FRAMEWORK_SIGNATURES: Final[dict[str, FrameworkSignature]] = {
    # Python web frameworks
    "fastapi": {
        "dependencies": ["fastapi"],
        "imports": ["fastapi"],
        "keywords": ["FastAPI"],
    },
    "flask": {
        "dependencies": ["flask"],
        "imports": ["flask"],
        "keywords": ["Flask"],
    },
    "django": {
        "dependencies": ["django"],
        "imports": ["django"],
        "keywords": ["Django"],
    },
    "starlette": {
        "dependencies": ["starlette"],
        "imports": ["starlette"],
        "keywords": ["Starlette"],
    },
    "aiohttp": {
        "dependencies": ["aiohttp"],
        "imports": ["aiohttp"],
        "keywords": ["aiohttp"],
    },
    "quart": {
        "dependencies": ["quart"],
        "imports": ["quart"],
        "keywords": ["Quart"],
    },
    "tornado": {
        "dependencies": ["tornado"],
        "imports": ["tornado"],
        "keywords": ["Tornado"],
    },
    "sanic": {
        "dependencies": ["sanic"],
        "imports": ["sanic"],
        "keywords": ["Sanic"],
    },
    # Python ORMs
    "sqlalchemy": {
        "dependencies": ["sqlalchemy"],
        "imports": ["sqlalchemy"],
        "keywords": ["SQLAlchemy"],
    },
    "tortoise-orm": {
        "dependencies": ["tortoise-orm", "tortoise"],
        "imports": ["tortoise"],
        "keywords": ["Tortoise ORM"],
    },
    "prisma": {
        "dependencies": ["prisma"],
        "imports": ["prisma"],
        "keywords": ["Prisma"],
    },
    # Python testing
    "pytest": {
        "dependencies": ["pytest"],
        "imports": ["pytest"],
        "keywords": ["pytest"],
    },
    "hypothesis": {
        "dependencies": ["hypothesis"],
        "imports": ["hypothesis"],
        "keywords": ["Hypothesis"],
    },
    # Python data/ML
    "pandas": {
        "dependencies": ["pandas"],
        "imports": ["pandas"],
        "keywords": ["pandas"],
    },
    "numpy": {
        "dependencies": ["numpy"],
        "imports": ["numpy"],
        "keywords": ["numpy"],
    },
    "scikit-learn": {
        "dependencies": ["scikit-learn", "sklearn"],
        "imports": ["sklearn"],
        "keywords": ["scikit-learn"],
    },
    "pytorch": {
        "dependencies": ["torch", "pytorch"],
        "imports": ["torch"],
        "keywords": ["PyTorch"],
    },
    "tensorflow": {
        "dependencies": ["tensorflow"],
        "imports": ["tensorflow"],
        "keywords": ["TensorFlow"],
    },
    "jax": {
        "dependencies": ["jax", "jaxlib"],
        "imports": ["jax"],
        "keywords": ["JAX"],
    },
    "langchain": {
        "dependencies": ["langchain"],
        "imports": ["langchain"],
        "keywords": ["LangChain"],
    },
    "llama-index": {
        "dependencies": ["llama-index", "llama_index"],
        "imports": ["llama_index"],
        "keywords": ["LlamaIndex"],
    },
    # Python async/concurrency
    "asyncio": {
        "dependencies": [],
        "imports": ["asyncio"],
        "keywords": ["asyncio"],
    },
    "uvloop": {
        "dependencies": ["uvloop"],
        "imports": ["uvloop"],
        "keywords": ["uvloop"],
    },
    # JavaScript/TypeScript frameworks
    "react": {
        "dependencies": ["react", "react-dom"],
        "imports": ["react"],
        "keywords": ["React"],
        "file_patterns": [r"\.jsx?$", r"\.tsx$"],
    },
    "nextjs": {
        "dependencies": ["next"],
        "imports": ["next"],
        "keywords": ["Next.js", "nextjs"],
        "file_patterns": [r"next\.config\.js", r"next\.config\.ts"],
    },
    "vue": {
        "dependencies": ["vue"],
        "imports": ["vue"],
        "keywords": ["Vue"],
        "file_patterns": [r"\.vue$"],
    },
    "svelte": {
        "dependencies": ["svelte"],
        "imports": ["svelte"],
        "keywords": ["Svelte"],
        "file_patterns": [r"\.svelte$"],
    },
    "angular": {
        "dependencies": ["@angular/core"],
        "imports": ["@angular"],
        "keywords": ["Angular"],
        "file_patterns": [r"angular\.json"],
    },
    "express": {
        "dependencies": ["express"],
        "imports": ["express"],
        "keywords": ["Express"],
    },
    "nestjs": {
        "dependencies": ["@nestjs/core"],
        "imports": ["@nestjs"],
        "keywords": ["NestJS"],
    },
    "vite": {
        "dependencies": ["vite"],
        "imports": [],
        "keywords": ["Vite"],
        "file_patterns": [r"vite\.config\.(js|ts)"],
    },
    "webpack": {
        "dependencies": ["webpack"],
        "imports": [],
        "keywords": ["webpack"],
        "file_patterns": [r"webpack\.config\.(js|ts)"],
    },
    "jest": {
        "dependencies": ["jest", "@jest/globals"],
        "imports": ["jest"],
        "keywords": ["Jest"],
    },
    "vitest": {
        "dependencies": ["vitest"],
        "imports": ["vitest"],
        "keywords": ["Vitest"],
    },
    "playwright": {
        "dependencies": ["playwright", "@playwright/test"],
        "imports": ["playwright"],
        "keywords": ["Playwright"],
    },
    "cypress": {
        "dependencies": ["cypress"],
        "imports": ["cypress"],
        "keywords": ["Cypress"],
    },
    # Go frameworks
    "gin": {
        "dependencies": ["github.com/gin-gonic/gin"],
        "imports": ["github.com/gin-gonic/gin"],
        "keywords": ["Gin"],
    },
    "echo": {
        "dependencies": ["github.com/labstack/echo/v4"],
        "imports": ["github.com/labstack/echo"],
        "keywords": ["Echo"],
    },
    "fiber": {
        "dependencies": ["github.com/gofiber/fiber/v2"],
        "imports": ["github.com/gofiber/fiber"],
        "keywords": ["Fiber"],
    },
    "chi": {
        "dependencies": ["github.com/go-chi/chi/v5"],
        "imports": ["github.com/go-chi/chi"],
        "keywords": ["Chi"],
    },
    "gorm": {
        "dependencies": ["gorm.io/gorm"],
        "imports": ["gorm.io/gorm"],
        "keywords": ["GORM"],
    },
    # Rust frameworks
    "actix-web": {
        "dependencies": ["actix-web"],
        "imports": ["actix_web"],
        "keywords": ["Actix-web"],
    },
    "axum": {
        "dependencies": ["axum"],
        "imports": ["axum"],
        "keywords": ["Axum"],
    },
    "rocket": {
        "dependencies": ["rocket"],
        "imports": ["rocket"],
        "keywords": ["Rocket"],
    },
    "warp": {
        "dependencies": ["warp"],
        "imports": ["warp"],
        "keywords": ["Warp"],
    },
    "tokio": {
        "dependencies": ["tokio"],
        "imports": ["tokio"],
        "keywords": ["Tokio"],
    },
    "sqlx": {
        "dependencies": ["sqlx"],
        "imports": ["sqlx"],
        "keywords": ["SQLx"],
    },
    "serde": {
        "dependencies": ["serde"],
        "imports": ["serde"],
        "keywords": ["Serde"],
    },
    # Java frameworks
    "spring-boot": {
        "dependencies": [
            "org.springframework.boot:spring-boot-starter",
            "org.springframework.boot:spring-boot-starter-web",
        ],
        "imports": ["org.springframework.boot"],
        "keywords": ["Spring Boot"],
        "file_patterns": [r"pom\.xml", r"build\.gradle"],
    },
    "micronaut": {
        "dependencies": ["io.micronaut:micronaut-core"],
        "imports": ["io.micronaut"],
        "keywords": ["Micronaut"],
    },
    "quarkus": {
        "dependencies": ["io.quarkus:quarkus-core"],
        "imports": ["io.quarkus"],
        "keywords": ["Quarkus"],
    },
    # Databases
    "postgresql": {
        "dependencies": [
            "psycopg2",
            "psycopg2-binary",
            "pg8000",
            "asyncpg",
            "postgresql",
        ],
        "imports": ["psycopg2", "asyncpg", "pg8000"],
        "keywords": ["PostgreSQL", "postgres"],
        "config_keywords": ["postgresql", "postgres", "psql"],
    },
    "mysql": {
        "dependencies": ["mysqlclient", "pymysql", "mysql-connector-python"],
        "imports": ["mysql", "pymysql"],
        "keywords": ["MySQL"],
        "config_keywords": ["mysql", "mariadb"],
    },
    "mongodb": {
        "dependencies": ["pymongo", "motor", "mongoengine"],
        "imports": ["pymongo", "motor", "mongoengine"],
        "keywords": ["MongoDB", "mongodb"],
        "config_keywords": ["mongodb", "mongo"],
    },
    "redis": {
        "dependencies": ["redis", "redis-py", "aredis", "redis.asyncio"],
        "imports": ["redis"],
        "keywords": ["Redis", "redis"],
        "config_keywords": ["redis"],
    },
    "sqlite": {
        "dependencies": ["sqlite3", "pysqlite3", "apsw"],
        "imports": ["sqlite3"],
        "keywords": ["SQLite", "sqlite"],
    },
    "elasticsearch": {
        "dependencies": ["elasticsearch", "elasticsearch-dsl"],
        "imports": ["elasticsearch"],
        "keywords": ["Elasticsearch", "elasticsearch"],
    },
    "cassandra": {
        "dependencies": ["cassandra-driver", "cassandra"],
        "imports": ["cassandra"],
        "keywords": ["Cassandra", "cassandra"],
    },
    "dynamodb": {
        "dependencies": ["boto3", "aioboto3"],
        "imports": ["boto3"],
        "keywords": ["DynamoDB", "dynamodb"],
    },
    # Message queues
    "kafka": {
        "dependencies": ["kafka-python", "confluent-kafka", "aiokafka"],
        "imports": ["kafka", "confluent_kafka", "aiokafka"],
        "keywords": ["Kafka", "kafka"],
        "config_keywords": ["kafka"],
    },
    "rabbitmq": {
        "dependencies": ["pika", "aio-pika", "amqp"],
        "imports": ["pika", "aio_pika"],
        "keywords": ["RabbitMQ", "rabbitmq"],
        "config_keywords": ["rabbitmq", "amqp"],
    },
    "sqS": {
        "dependencies": ["boto3", "aioboto3"],
        "imports": ["boto3"],
        "keywords": ["SQS", "sqs"],
        "config_keywords": ["sqs"],
    },
    "nats": {
        "dependencies": ["nats-py", "nats"],
        "imports": ["nats"],
        "keywords": ["NATS", "nats"],
        "config_keywords": ["nats"],
    },
    # Cache systems
    "memcached": {
        "dependencies": ["pymemcache", "python-memcached"],
        "imports": ["memcache", "pymemcache"],
        "keywords": ["Memcached", "memcached"],
        "config_keywords": ["memcached"],
    },
    # CI/CD
    "github-actions": {
        "file_patterns": [r"\.github/workflows/.*\.ya?ml$"],
        "keywords": ["GitHub Actions", "actions/"],
    },
    "gitlab-ci": {
        "file_patterns": [r"\.gitlab-ci\.ya?ml$"],
        "keywords": ["GitLab CI"],
    },
    "circleci": {
        "file_patterns": [r"\.circleci/config\.ya?ml$"],
        "keywords": ["CircleCI"],
    },
    "jenkins": {
        "file_patterns": [r"Jenkinsfile", r"jenkinsfile"],
        "keywords": ["Jenkins"],
    },
    "azure-pipelines": {
        "file_patterns": [r"azure-pipelines\.ya?ml$"],
        "keywords": ["Azure Pipelines"],
    },
    # Containerization
    "docker": {
        "file_patterns": [r"Dockerfile", r"docker-compose\.ya?ml$", r"compose\.ya?ml$"],
        "keywords": ["Docker", "docker"],
    },
    "kubernetes": {
        "file_patterns": [r"\.yaml$", r"\.yml$"],
        "keywords": ["apiVersion:", "kind:", "kubectl", "kubernetes", "k8s"],
        "config_keywords": ["kubernetes", "k8s"],
    },
    "helm": {
        "file_patterns": [r"Chart\.ya?ml$", r"values\.ya?ml$", r"helm/"],
        "keywords": ["Helm", "helm"],
    },
    # Cloud services
    "aws": {
        "dependencies": ["boto3", "botocore", "aws-cdk-lib", "cdktf"],
        "imports": ["boto3", "botocore", "aws_cdk", "cdktf"],
        "keywords": ["AWS", "Amazon Web Services"],
        "config_keywords": ["aws", "amazonaws"],
    },
    "gcp": {
        "dependencies": [
            "google-cloud-storage",
            "google-cloud-pubsub",
            "google-cloud-bigquery",
            "google-cloud-firestore",
        ],
        "imports": ["google.cloud", "google.auth"],
        "keywords": ["Google Cloud", "GCP"],
        "config_keywords": ["gcp", "googleapis"],
    },
    "azure": {
        "dependencies": ["azure-storage-blob", "azure-identity", "azure-mgmt-resource"],
        "imports": ["azure", "azure.identity"],
        "keywords": ["Azure", "Microsoft Azure"],
        "config_keywords": ["azure", "microsoftazure"],
    },
    # Cloud SDK specific
    "vercel": {
        "dependencies": ["vercel"],
        "keywords": ["Vercel"],
        "file_patterns": [r"vercel\.json"],
    },
    "netlify": {
        "file_patterns": [r"netlify\.toml", r"netlify\.ya?ml"],
        "keywords": ["Netlify"],
    },
}


def detect_frameworks(
    repo_path: Path,
    declared_deps: dict[str, list[str]],
    languages: frozenset[str],
) -> frozenset[str]:
    """Detect frameworks from dependencies, imports, and file patterns."""
    frameworks: set[str] = set()

    # Collect all dependency names (lowercase for matching)
    all_deps = set()
    for dep_list in declared_deps.values():
        for dep in dep_list:
            all_deps.add(dep.lower())

    # Collect imports from Python files (fast scan)
    imports = set()
    if "python" in languages:
        for py_file in repo_path.rglob("*.py"):
            if any(
                part in {".git", ".venv", "venv", "env", "node_modules", "__pycache__"}
                for part in py_file.parts
            ):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith(("import ", "from ")):
                        parts = (
                            stripped.replace("from ", "").replace("import ", "").split()
                        )
                        for part in parts:
                            if part and not part.startswith("."):
                                imports.add(part.split(".")[0].lower())
            except (OSError, UnicodeDecodeError):
                continue

    # Collect config file content for keywords
    config_content = ""
    config_files = (
        list(repo_path.rglob("*.yaml"))
        + list(repo_path.rglob("*.yml"))
        + list(repo_path.rglob("*.toml"))
        + list(repo_path.rglob("*.json"))
        + list(repo_path.rglob("*.ini"))
        + list(repo_path.rglob("*.cfg"))
        + list(repo_path.rglob("Dockerfile*"))
        + list(repo_path.rglob("docker-compose*"))
    )
    for config_file in config_files:
        if any(
            part in {".git", ".venv", "venv", "env", "node_modules"}
            for part in config_file.parts
        ):
            continue
        try:
            config_content += (
                config_file.read_text(encoding="utf-8", errors="ignore").lower() + "\n"
            )
        except (OSError, UnicodeDecodeError):
            continue

    # Check each framework signature
    for fw_name, sig in FRAMEWORK_SIGNATURES.items():
        matched = False

        # Check dependencies
        for dep in sig.get("dependencies", []):
            if dep.lower() in all_deps:
                matched = True
                break

        # Check imports
        if not matched:
            for imp in sig.get("imports", []):
                if imp.lower() in imports:
                    matched = True
                    break

        # Check file patterns
        if not matched:
            for pattern in sig.get("file_patterns", []):
                try:
                    if any(repo_path.rglob(pattern) for _ in [0]):
                        matched = True
                        break
                except OSError:
                    pass

        # Check keywords in config
        if not matched:
            for kw in sig.get("keywords", []):
                if kw.lower() in config_content:
                    matched = True
                    break

        # Check config keywords
        if not matched:
            for kw in sig.get("config_keywords", []):
                if kw.lower() in config_content:
                    matched = True
                    break

        if matched:
            frameworks.add(fw_name)

    return frozenset(frameworks)


# ---------------------------------------------------------------------------
# Categorize frameworks into databases, queues, caches, etc.
# ---------------------------------------------------------------------------

DATABASE_FRAMEWORKS: Final[frozenset[str]] = frozenset(
    {
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "sqlite",
        "elasticsearch",
        "cassandra",
        "dynamodb",
    }
)

MESSAGE_QUEUE_FRAMEWORKS: Final[frozenset[str]] = frozenset(
    {
        "kafka",
        "rabbitmq",
        "sqS",
        "nats",
    }
)

CACHE_FRAMEWORKS: Final[frozenset[str]] = frozenset(
    {
        "redis",
        "memcached",
    }
)

CICD_FRAMEWORKS: Final[frozenset[str]] = frozenset(
    {
        "github-actions",
        "gitlab-ci",
        "circleci",
        "jenkins",
        "azure-pipelines",
    }
)

CONTAINERIZATION_FRAMEWORKS: Final[frozenset[str]] = frozenset(
    {
        "docker",
        "kubernetes",
        "helm",
    }
)

CLOUD_FRAMEWORKS: Final[frozenset[str]] = frozenset(
    {
        "aws",
        "gcp",
        "azure",
        "vercel",
        "netlify",
    }
)


def categorize_frameworks(
    frameworks: frozenset[str],
) -> tuple[
    frozenset[str],  # databases
    frozenset[str],  # message_queues
    frozenset[str],  # cache_systems
    frozenset[str],  # ci_cd
    frozenset[str],  # containerization
    frozenset[str],  # cloud_services
    frozenset[str],  # remaining frameworks
]:
    """Categorize detected frameworks into infrastructure categories."""
    databases = frozenset(f for f in frameworks if f in DATABASE_FRAMEWORKS)
    message_queues = frozenset(f for f in frameworks if f in MESSAGE_QUEUE_FRAMEWORKS)
    cache_systems = frozenset(f for f in frameworks if f in CACHE_FRAMEWORKS)
    ci_cd = frozenset(f for f in frameworks if f in CICD_FRAMEWORKS)
    containerization = frozenset(
        f for f in frameworks if f in CONTAINERIZATION_FRAMEWORKS
    )
    cloud_services = frozenset(f for f in frameworks if f in CLOUD_FRAMEWORKS)

    # Remaining are application frameworks
    remaining = (
        frameworks
        - databases
        - message_queues
        - cache_systems
        - ci_cd
        - containerization
        - cloud_services
    )

    return (
        databases,
        message_queues,
        cache_systems,
        ci_cd,
        containerization,
        cloud_services,
        remaining,
    )


# ---------------------------------------------------------------------------
# Manifest parsing for declared dependencies
# ---------------------------------------------------------------------------


def parse_declared_dependencies(repo_path: Path) -> dict[str, list[str]]:
    """Parse declared dependencies from various manifest files."""
    deps: dict[str, list[str]] = {
        "python": [],
        "javascript": [],
        "go": [],
        "rust": [],
        "java": [],
        "ruby": [],
    }

    # Python: pyproject.toml, requirements.txt, setup.py, Pipfile
    for pyproject in repo_path.rglob("pyproject.toml"):
        if any(part in {".git", ".venv", "venv", "env"} for part in pyproject.parts):
            continue
        try:
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            # [project.dependencies]
            for dep in data.get("project", {}).get("dependencies", []):
                deps["python"].append(
                    dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip()
                )
            # [tool.poetry.dependencies]
            for dep in data.get("tool", {}).get("poetry", {}).get("dependencies", {}):
                if dep != "python":
                    deps["python"].append(dep)
            # [tool.uv.dependencies] or similar
            for dep in data.get("tool", {}).get("uv", {}).get("dependencies", {}):
                deps["python"].append(dep)
        except (tomllib.TOMLDecodeError, OSError):
            pass

    for req_file in repo_path.rglob("requirements*.txt"):
        if any(part in {".git", ".venv", "venv", "env"} for part in req_file.parts):
            continue
        try:
            for line in req_file.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    dep = (
                        line.split("[")[0]
                        .split(">")[0]
                        .split("<")[0]
                        .split("=")[0]
                        .strip()
                    )
                    if dep:
                        deps["python"].append(dep)
        except OSError:
            pass

    # JavaScript/TypeScript: package.json
    for pkg_file in repo_path.rglob("package.json"):
        if any(part in {".git", "node_modules"} for part in pkg_file.parts):
            continue
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            for dep in data.get("dependencies", {}):
                deps["javascript"].append(dep)
            for dep in data.get("devDependencies", {}):
                deps["javascript"].append(dep)
        except (json.JSONDecodeError, OSError):
            pass

    # Go: go.mod
    for go_mod in repo_path.rglob("go.mod"):
        if any(part in {".git"} for part in go_mod.parts):
            continue
        try:
            content = go_mod.read_text(encoding="utf-8")
            # Simple regex to extract require blocks
            import re

            for match in re.finditer(r"require\s+\((.*?)\)", content, re.DOTALL):
                for line in match.group(1).splitlines():
                    line = line.strip()
                    if line and not line.startswith("//"):
                        parts = line.split()
                        if parts:
                            deps["go"].append(parts[0])
            # Single-line requires
            for match in re.finditer(r"require\s+([^\s]+)\s+([^\s]+)", content):
                deps["go"].append(match.group(1))
        except OSError:
            pass

    # Rust: Cargo.toml
    for cargo in repo_path.rglob("Cargo.toml"):
        if any(part in {".git", "target"} for part in cargo.parts):
            continue
        try:
            with cargo.open("rb") as f:
                data = tomllib.load(f)
            for dep in data.get("dependencies", {}):
                deps["rust"].append(dep)
            for dep in data.get("dev-dependencies", {}):
                deps["rust"].append(dep)
        except (tomllib.TOMLDecodeError, OSError):
            pass

    # Java: pom.xml (basic extraction)
    for pom in repo_path.rglob("pom.xml"):
        if any(part in {".git", "target"} for part in pom.parts):
            continue
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(pom)  # noqa: S314 -- local trusted pom.xml
            ns = {"m": "http://maven.apache.org/POM/4.0.0"}
            for dep in tree.findall(".//m:dependency", ns):
                group_id = dep.find("m:groupId", ns)
                artifact_id = dep.find("m:artifactId", ns)
                if group_id is not None and artifact_id is not None:
                    deps["java"].append(f"{group_id.text}:{artifact_id.text}")
        except (ET.ParseError, OSError):
            pass

    # Java: build.gradle (basic)
    for gradle in repo_path.rglob("build.gradle*"):
        if any(part in {".git", "build"} for part in gradle.parts):
            continue
        try:
            content = gradle.read_text(encoding="utf-8", errors="ignore")
            # Look for implementation "group:artifact:version"
            import re

            for match in re.finditer(r'implementation\s+["\']([^"\']+)["\']', content):
                deps["java"].append(match.group(1))
            for match in re.finditer(r'compile\s+["\']([^"\']+)["\']', content):
                deps["java"].append(match.group(1))
        except OSError:
            pass

    return deps


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def detect_stack(repo_path: Path) -> TechStack:
    """Detect the technology stack of a repository."""
    # Detect languages first (from file extensions)
    languages = detect_languages(repo_path)

    # Parse declared dependencies
    declared_deps = parse_declared_dependencies(repo_path)

    # Detect frameworks from dependencies, imports, and config
    frameworks = detect_frameworks(repo_path, declared_deps, languages)

    # Categorize frameworks
    (
        databases,
        message_queues,
        cache_systems,
        ci_cd,
        containerization,
        cloud_services,
        app_frameworks,
    ) = categorize_frameworks(frameworks)

    # Add application frameworks to the main frameworks set
    all_frameworks = (
        app_frameworks
        | databases
        | message_queues
        | cache_systems
        | ci_cd
        | containerization
        | cloud_services
    )

    return TechStack(
        languages=languages,
        frameworks=all_frameworks,
        databases=databases,
        message_queues=message_queues,
        cache_systems=cache_systems,
        ci_cd=ci_cd,
        containerization=containerization,
        cloud_services=cloud_services,
    )
