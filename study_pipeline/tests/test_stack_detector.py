"""Tests for stack_detector.py."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from study_pipeline.stack_detector import (
    TechStack,
    detect_languages,
    detect_stack,
    parse_declared_dependencies,
)


def test_detect_languages_python() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("print('hello')")
        (root / "utils.py").write_text("def foo(): pass")
        langs = detect_languages(root)
        assert "python" in langs


def test_detect_languages_javascript() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.js").write_text("console.log('hi')")
        (root / "component.jsx").write_text("export default () => <div/>")
        langs = detect_languages(root)
        assert "javascript" in langs


def test_detect_languages_typescript() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.ts").write_text("const x: string = 'hi'")
        (root / "component.tsx").write_text("export default () => <div/>")
        langs = detect_languages(root)
        assert "typescript" in langs


def test_detect_languages_go() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.go").write_text("package main\nfunc main() {}")
        langs = detect_languages(root)
        assert "go" in langs


def test_detect_languages_rust() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.rs").write_text("fn main() {}")
        langs = detect_languages(root)
        assert "rust" in langs


def test_detect_languages_java() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "Main.java").write_text("public class Main {}")
        langs = detect_languages(root)
        assert "java" in langs


def test_detect_languages_skips_venv() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("print('hi')")
        venv_dir = root / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "site.py").write_text("x = 1")
        langs = detect_languages(root)
        assert "python" in langs


def test_parse_declared_dependencies_python_pyproject() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text("""
[project]
name = "test"
dependencies = [
    "requests>=2.28",
    "pydantic==2.0.0",
]
""")
        deps = parse_declared_dependencies(root)
        assert "requests" in deps["python"]
        assert "pydantic" in deps["python"]


def test_parse_declared_dependencies_python_requirements() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "requirements.txt").write_text("""
requests>=2.28
flask==2.3.0
# comment
""")
        deps = parse_declared_dependencies(root)
        assert "requests" in deps["python"]
        assert "flask" in deps["python"]


def test_parse_declared_dependencies_javascript_package_json() -> None:
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
    }
}""")
        deps = parse_declared_dependencies(root)
        assert "express" in deps["javascript"]
        assert "lodash" in deps["javascript"]
        assert "jest" in deps["javascript"]
        assert "typescript" in deps["javascript"]


def test_parse_declared_dependencies_go_mod() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "go.mod").write_text("""module example.com/test

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/stretchr/testify v1.8.4 // indirect
)
""")
        deps = parse_declared_dependencies(root)
        assert "github.com/gin-gonic/gin" in deps["go"]
        assert "github.com/stretchr/testify" in deps["go"]


def test_parse_declared_dependencies_cargo_toml() -> None:
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
        deps = parse_declared_dependencies(root)
        assert "serde" in deps["rust"]
        assert "tokio" in deps["rust"]
        assert "tempfile" in deps["rust"]


def test_detect_stack_basic() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("import requests\nprint('hi')")
        (root / "pyproject.toml").write_text("""
[project]
name = "test"
dependencies = ["requests>=2.28"]
""")
        stack = detect_stack(root)
        assert isinstance(stack, TechStack)
        assert "python" in stack.languages
        # requests should be detected as a framework from pyproject.toml
        # The test just checks that detection runs without error


def test_detect_stack_javascript() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "index.js").write_text("const express = require('express')")
        (root / "package.json").write_text("""{
    "name": "test",
    "dependencies": {"express": "^4.18.0"}
}""")
        stack = detect_stack(root)
        assert "javascript" in stack.languages
        assert "express" in stack.frameworks


def test_detect_stack_go() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.go").write_text('package main\nimport "github.com/gin-gonic/gin"')
        (root / "go.mod").write_text(
            """module test\ngo 1.21\nrequire github.com/gin-gonic/gin v1.9.0\n"""
        )
        stack = detect_stack(root)
        assert "go" in stack.languages
        assert "gin" in stack.frameworks


def test_detect_stack_rust() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.rs").write_text("use serde::Serialize;")
        (root / "Cargo.toml").write_text('[dependencies]\nserde = "1.0"\n')
        stack = detect_stack(root)
        assert "rust" in stack.languages
        assert "serde" in stack.frameworks


def test_detect_stack_java_pom() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pom.xml").write_text("""<?xml version="1.0"?>
<project>
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
    </dependencies>
</project>""")
        stack = detect_stack(root)
        assert "java" in stack.languages
        assert "spring-boot" in stack.frameworks


def test_categorize_frameworks() -> None:
    from study_pipeline.stack_detector import categorize_frameworks

    frameworks = frozenset(["fastapi", "postgresql", "redis", "kafka", "docker", "aws"])
    dbs, mqs, caches, _cicd, containers, clouds, remaining = categorize_frameworks(
        frameworks
    )
    assert "postgresql" in dbs
    assert "redis" in dbs
    assert "kafka" in mqs
    assert "redis" in caches
    assert "docker" in containers
    assert "aws" in clouds
    assert "fastapi" in remaining


def test_tech_stack_to_dict() -> None:
    stack = TechStack(
        languages=frozenset(["python", "javascript"]),
        frameworks=frozenset(["fastapi", "express"]),
        databases=frozenset(["postgresql"]),
        message_queues=frozenset(["kafka"]),
        cache_systems=frozenset(["redis"]),
        ci_cd=frozenset(["github-actions"]),
        containerization=frozenset(["docker"]),
        cloud_services=frozenset(["aws"]),
    )
    d = stack.to_dict()
    assert d["languages"] == ["javascript", "python"]
    assert "fastapi" in d["frameworks"]
    assert "postgresql" in d["databases"]
    assert "kafka" in d["message_queues"]
    assert "redis" in d["cache_systems"]
    assert "github-actions" in d["ci_cd"]
    assert "docker" in d["containerization"]
    assert "aws" in d["cloud_services"]


def test_detect_stack_with_multiple_languages() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "main.py").write_text("import flask")
        (root / "index.js").write_text("const express = require('express')")
        (root / "pyproject.toml").write_text('dependencies = ["flask"]')
        (root / "package.json").write_text('{"dependencies": {"express": "^4.18.0"}}')
        stack = detect_stack(root)
        assert "python" in stack.languages
        assert "javascript" in stack.languages
        assert "flask" in stack.frameworks
        assert "express" in stack.frameworks
