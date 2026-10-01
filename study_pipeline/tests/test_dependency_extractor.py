"""Tests for dependency_extractor.py."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from study_pipeline.dependency_extractor import (
    Dependency,
    categorize_dependency,
    extract_dependencies,
    normalize_version,
    parse_go_dependencies,
    parse_java_dependencies,
    parse_javascript_dependencies,
    parse_python_dependencies,
    parse_rust_dependencies,
)


def test_normalize_version() -> None:
    assert normalize_version("2.0.0") == "2.0.0"
    assert normalize_version(">=2.0.0") == "2.0.0"
    assert normalize_version("~1.0.0") == "1.0.0"
    assert normalize_version("^1.0.0") == "1.0.0"
    assert normalize_version(">=2.0,<3.0") == "2.0,<3.0"
    assert normalize_version("==2.0.0") == "2.0.0"
    assert normalize_version(None) is None
    assert normalize_version("") is None


def test_categorize_dependency() -> None:
    # Python web frameworks
    assert categorize_dependency("fastapi", "python") == "web-framework"
    assert categorize_dependency("flask", "python") == "web-framework"
    assert categorize_dependency("django", "python") == "web-framework"
    # Python ORMs
    assert categorize_dependency("sqlalchemy", "python") == "orm"
    assert categorize_dependency("prisma", "python") == "orm"
    # Python testing
    assert categorize_dependency("pytest", "python") == "testing"
    assert categorize_dependency("hypothesis", "python") == "testing"
    # Python HTTP clients
    assert categorize_dependency("httpx", "python") == "http-client"
    assert categorize_dependency("requests", "python") == "http-client"
    # JS frameworks
    assert categorize_dependency("express", "javascript") == "web-framework"
    assert categorize_dependency("nextjs", "javascript") == "web-framework"
    assert categorize_dependency("react", "javascript") == "web-framework"
    # Go frameworks
    assert categorize_dependency("gin", "go") == "web-framework"
    # Java frameworks
    assert categorize_dependency("spring-boot", "java") == "web-framework"
    # Unknown -> utility
    assert categorize_dependency("unknown-package", "python") == "utility"
    # Language-specific heuristic
    assert categorize_dependency("django-extensions", "python") == "web-framework"
    assert categorize_dependency("pytest-cov", "python") == "testing"


def test_parse_python_dependencies_pyproject() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text("""
[project]
name = "test"
dependencies = [
    "requests>=2.28",
    "pydantic==2.0.0",
    "flask",
]

[tool.poetry.dependencies]
python = "^3.11"
httpx = "0.25"
""")
        deps = parse_python_dependencies(root)
        names = {d.name for d in deps}
        assert "requests" in names
        assert "pydantic" in names
        assert "flask" in names
        assert "httpx" in names
        # Check python is excluded
        assert "python" not in names
        # Check categories
        for dep in deps:
            assert dep.language == "python"
            assert dep.category is not None


def test_parse_python_dependencies_requirements() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "requirements.txt").write_text("""
requests>=2.28
pydantic==2.0.0
flask
""")
        deps = parse_python_dependencies(root)
        names = {d.name for d in deps}
        assert "requests" in names
        assert "pydantic" in names
        assert "flask" in names
        for dep in deps:
            assert dep.language == "python"
            assert dep.is_dev is False


def test_parse_python_dependencies_requirements_dev() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "requirements-dev.txt").write_text("""
pytest>=7.0
pytest-cov
""")
        deps = parse_python_dependencies(root)
        names = {d.name for d in deps}
        assert "pytest" in names
        for dep in deps:
            assert dep.is_dev is True


def test_parse_javascript_dependencies_package_json() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "package.json").write_text("""{
    "name": "test",
    "dependencies": {
        "express": "^4.18.0",
        "lodash": "4.17.21"
    },
    "devDependencies": {
        "jest": "^29.0.0",
        "typescript": "~5.0.0"
    },
    "optionalDependencies": {
        "fsevents": "^2.3.2"
    }
}""")
        deps = parse_javascript_dependencies(root)
        names = {d.name for d in deps}
        assert "express" in names
        assert "lodash" in names
        assert "jest" in names
        assert "typescript" in names
        assert "fsevents" in names
        for dep in deps:
            if dep.name in ("jest", "typescript"):
                assert dep.is_dev is True
            else:
                assert dep.is_dev is False
            assert dep.language == "javascript"
            assert dep.category is not None


def test_parse_go_dependencies() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "go.mod").write_text("""module example.com/test

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/stretchr/testify v1.8.4 // indirect
    golang.org/x/text v0.12.0
)
""")
        deps = parse_go_dependencies(root)
        names = {d.name for d in deps}
        assert "github.com/gin-gonic/gin" in names
        assert "github.com/stretchr/testify" in names
        assert "golang.org/x/text" in names
        for dep in deps:
            if dep.name == "github.com/stretchr/testify":
                assert dep.is_dev is True  # indirect
            else:
                assert dep.is_dev is False
            assert dep.language == "go"
            assert dep.category is not None


def test_parse_rust_dependencies() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Cargo.toml").write_text("""[package]
name = "test"
version = "0.1.0"

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
tempfile = "3.0"
""")
        deps = parse_rust_dependencies(root)
        names = {d.name for d in deps}
        assert "serde" in names
        assert "tokio" in names
        assert "tempfile" in names
        for dep in deps:
            if dep.name == "tempfile":
                assert dep.is_dev is True
            else:
                assert dep.is_dev is False
            assert dep.language == "rust"
            assert dep.category is not None


def test_parse_java_dependencies_pom() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test</artifactId>
    <version>1.0</version>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <version>3.0.0</version>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <version>42.6.0</version>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.9.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>""")
        deps = parse_java_dependencies(root)
        names = {d.name for d in deps}
        assert "org.springframework.boot:spring-boot-starter-web" in names
        assert "org.postgresql:postgresql" in names
        assert "org.junit.jupiter:junit-jupiter" in names
        for dep in deps:
            if dep.name == "org.junit.jupiter:junit-jupiter":
                assert dep.is_dev is True  # test scope
            else:
                assert dep.is_dev is False
            assert dep.language == "java"
            assert dep.category is not None


def test_parse_java_dependencies_gradle() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "build.gradle").write_text("""
dependencies {
    implementation "org.springframework.boot:spring-boot-starter-web:3.0.0"
    implementation "org.postgresql:postgresql:42.6.0"
    testImplementation "org.junit.jupiter:junit-jupiter:5.9.0"
}
""")
        deps = parse_java_dependencies(root)
        names = {d.name for d in deps}
        assert "org.springframework.boot:spring-boot-starter-web" in names
        assert "org.postgresql:postgresql" in names
        assert "org.junit.jupiter:junit-jupiter" in names
        for dep in deps:
            if dep.name == "org.junit.jupiter:junit-jupiter":
                assert dep.is_dev is True
            else:
                assert dep.is_dev is False


def test_extract_dependencies_deduplication() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Same dependency in both pyproject.toml and requirements.txt
        (root / "pyproject.toml").write_text("""
[project]
name = "test"
dependencies = ["requests>=2.28"]
""")
        (root / "requirements.txt").write_text("requests>=2.28\n")
        deps = extract_dependencies(Path(tmp))
        requests_deps = [d for d in deps if d.name == "requests"]
        assert len(requests_deps) == 1  # Deduplicated


def test_extract_dependencies_multi_language() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("import requests")
        (root / "pyproject.toml").write_text('dependencies = ["requests"]')
        (root / "index.js").write_text("const express = require('express')")
        (root / "package.json").write_text('{"dependencies": {"express": "^4.18.0"}}')
        deps = extract_dependencies(Path(tmp))
        names = {d.name for d in deps}
        assert "requests" in names
        assert "express" in names
        # Check languages
        langs = {d.language for d in deps}
        assert "python" in langs
        assert "javascript" in langs


def test_extract_dependencies_deduplication_cross_language() -> None:
    # Same package name in different languages should not deduplicate
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "package.json").write_text('{"dependencies": {"lodash": "4.17.21"}}')
        (root / "Cargo.toml").write_text('[dependencies]\nlodash = "0.1"\n')
        deps = extract_dependencies(Path(tmp))
        names = {d.name for d in deps}
        assert "lodash" in names
        # Should have two entries: one for JS, one for Rust
        lodash_deps = [d for d in deps if d.name == "lodash"]
        assert len(lodash_deps) == 2
        langs = {d.language for d in lodash_deps}
        assert "javascript" in langs
        assert "rust" in langs


def test_dependency_to_dict() -> None:
    dep = Dependency(
        name="requests",
        version="2.28.0",
        category="http-client",
        language="python",
        is_dev=False,
    )
    d = dep.to_dict()
    assert d["name"] == "requests"
    assert d["version"] == "2.28.0"
    assert d["category"] == "http-client"
    assert d["language"] == "python"
    assert d["is_dev"] is False
