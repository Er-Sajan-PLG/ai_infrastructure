"""Main infrastructure scanner — three-layer detection pipeline.

Layer 1: Keyword scanning (fast, broad)
Layer 2: Config file deep parsing (deterministic)
Layer 3: LLM-assisted detection (optional, for ambiguous cases)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    # Static-only dependency for the optional LLM layer: the scanner never
    # imports model_provider at runtime (it does so lazily inside a try
    # block), so the stdlib-only property holds. The annotation documents
    # the transport protocol the caller must satisfy.
    from model_provider.transport import Transport

from .config_parsers import parse_all_configs
from .models import INFRASTRUCTURE_LAYERS, InfraComponent, InfrastructureMap
from .taxonomy import INFRASTRUCTURE_TAXONOMY

# ---------------------------------------------------------------------------
# Keyword Scanner (Layer 1)
# ---------------------------------------------------------------------------

# Common programming identifiers that are NOT infrastructure
COMMON_FALSE_POSITIVES: Final[frozenset[str]] = frozenset(
    {
        "test",
        "tests",
        "testing",
        "spec",
        "specs",
        "mock",
        "stub",
        "fake",
        "example",
        "sample",
        "demo",
        "tutorial",
        "doc",
        "docs",
        "readme",
        "util",
        "utils",
        "helper",
        "helpers",
        "common",
        "shared",
        "base",
        "core",
        "main",
        "app",
        "application",
        "service",
        "services",
        "model",
        "models",
        "entity",
        "entities",
        "schema",
        "schemas",
        "controller",
        "controllers",
        "handler",
        "handlers",
        "route",
        "routes",
        "middleware",
        "interceptor",
        "interceptors",
        "exception",
        "exceptions",
        "error",
        "errors",
        "validation",
        "request",
        "response",
        "dto",
        "vo",
        "repository",
        "factory",
        "builder",
        "parser",
        "serializer",
        "deserializer",
        "converter",
        "transformer",
        "mapper",
    }
)


@dataclass(frozen=True, slots=True)
class KeywordMatch:
    """A keyword match with context."""

    component_type: str
    keyword: str
    file_path: str
    line_number: int
    context: str


def scan_keywords(repo_path: Path) -> list[InfraComponent]:
    """Layer 1: Fast keyword scanning across source files."""
    components = []
    matches_by_type: dict[str, list[KeywordMatch]] = {}

    # Build inverted index: keyword -> component_type
    keyword_to_types: dict[str, list[str]] = {}
    for comp_type, info in INFRASTRUCTURE_TAXONOMY.items():
        for kw in info["keywords"]:
            keyword_to_types.setdefault(kw.lower(), []).append(comp_type)

    # Skip directories
    skip_dirs = {
        ".git",
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
        "out",
    }

    # File extensions to scan
    code_extensions = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".scala",
        ".rb",
        ".php",
        ".cs",
        ".cpp",
        ".cc",
        ".c",
        ".h",
        ".hpp",
        ".swift",
        ".dart",
        ".r",
        ".sh",
        ".bash",
        ".sql",
        ".graphql",
        ".proto",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".xml",
        ".html",
        ".md",
        ".txt",
    }

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in skip_dirs for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in code_extensions and file_path.name not in {
            "Dockerfile",
            "Caddyfile",
            "Makefile",
        }:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            for line_num, line in enumerate(lines, 1):
                line_lower = line.lower()
                # Simple word boundary check
                words = set(re.findall(r"\b[a-z_][a-z0-9_]*\b", line_lower))

                for word in words:
                    if word in COMMON_FALSE_POSITIVES:
                        continue
                    if word in keyword_to_types:
                        for comp_type in keyword_to_types[word]:
                            match = KeywordMatch(
                                component_type=comp_type,
                                keyword=word,
                                file_path=str(file_path.relative_to(repo_path)),
                                line_number=line_num,
                                context=line.strip()[:200],
                            )
                            matches_by_type.setdefault(comp_type, []).append(match)

        except (OSError, UnicodeDecodeError):
            continue

    # Convert matches to components
    for comp_type, matches in matches_by_type.items():
        if comp_type not in INFRASTRUCTURE_TAXONOMY:
            continue

        info = INFRASTRUCTURE_TAXONOMY[comp_type]
        layer = info["layer"]

        # Deduplicate by file
        files_seen = set()
        unique_matches = []
        for m in matches:
            if m.file_path not in files_seen:
                files_seen.add(m.file_path)
                unique_matches.append(m)

        if not unique_matches:
            continue

        # Calculate confidence based on match count and diversity
        match_count = len(unique_matches)
        file_count = len(files_seen)

        # Base confidence from match count
        base_confidence = min(0.6, match_count * 0.1)
        # Boost for multiple files
        file_boost = min(0.2, file_count * 0.05)
        confidence = min(0.8, base_confidence + file_boost)

        # Get unique files and lines
        code_locations = tuple(
            f"{m.file_path}:{m.line_number}" for m in unique_matches[:20]
        )

        comp = InfraComponent(
            layer=layer,
            component_type=comp_type,
            name=f"{comp_type.replace('_', ' ').title()} (keyword scan)",
            description=f"Detected via {match_count} keyword match(es) across {file_count} file(s)",
            technologies=(),
            code_locations=code_locations,
            config_locations=(),
            confidence=confidence,
            detection_method="keyword",
        )
        components.append(comp)

    return components


# ---------------------------------------------------------------------------
# LLM-Assisted Detection (Layer 3) - Optional
# ---------------------------------------------------------------------------

LLM_SYSTEM_PROMPT = """You are an infrastructure analyst. Given a repository summary and detected components,
identify additional infrastructure components that keyword scanning might have missed.

Return ONLY a JSON array of objects with these fields:
- component_type: string (use existing taxonomy types when possible)
- layer: string (one of: identity, transaction, state, data, communication, delivery, observability, security, deployment, integration, user_experience, governance)
- name: string
- description: string
- technologies: array of strings
- confidence: float (0.0-1.0)
- detection_method: "llm"

Only return components you are confident about (confidence >= 0.6).
Do not duplicate components already detected.
"""

LLM_USER_PROMPT_TEMPLATE = """Repository: {repo_name}
Files: {file_count}
Languages: {languages}

Already detected components:
{detected_summary}

Repository structure (top level):
{top_level}

Key files content (truncated):
{key_files}

Identify any infrastructure components that are likely present but not yet detected.
Focus on: configuration patterns, architectural patterns, third-party integrations,
deployment targets, and security/compliance indicators that keywords might miss."""


async def scan_with_llm(
    repo_path: Path,
    existing_components: list[InfraComponent],
    transport: Transport,
    api_key: str,
) -> list[InfraComponent]:
    """Layer 3: LLM-assisted detection for ambiguous cases.

    Args:
        repo_path: Path to repository
        existing_components: Already detected components
        transport: LLM transport instance
        model_provider: Model provider instance
        api_key: API key for the provider

    Returns:
        Additional components detected by LLM
    """
    # Build summary of existing components
    detected_by_layer: dict[str, list[str]] = {}
    for c in existing_components:
        detected_by_layer.setdefault(c.layer, []).append(c.component_type)

    detected_summary = "\n".join(
        f"  {layer}: {', '.join(types)}"
        for layer, types in sorted(detected_by_layer.items())
    )

    # Get top-level structure
    top_level = []
    for entry in repo_path.iterdir():
        if not entry.name.startswith("."):
            top_level.append(entry.name)
    top_level_str = ", ".join(top_level[:30])

    # Read key files (config, main entry points)
    key_files_content = []
    key_files = [
        "README.md",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Dockerfile",
        ".github/workflows",
        ".gitlab-ci.yml",
        "Jenkinsfile",
    ]

    for key_file in key_files:
        path = repo_path / key_file
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")[:2000]
                key_files_content.append(f"=== {key_file} ===\n{content}")
            except OSError:
                pass
        elif path.is_dir():
            files = list(path.glob("*.y*ml"))[:3]
            for f in files:
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")[:1000]
                    key_files_content.append(
                        f"=== {f.relative_to(repo_path)} ===\n{content}"
                    )
                except OSError:
                    pass

    key_files_str = "\n\n".join(key_files_content)[:8000]

    # Detect languages from extensions
    extensions = set()
    for f in repo_path.rglob("*"):
        if f.is_file() and f.suffix:
            extensions.add(f.suffix.lower())
    languages = ", ".join(
        sorted(
            ext
            for ext in extensions
            if ext
            in {".py", ".js", ".ts", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".cs"}
        )
    )

    prompt = LLM_USER_PROMPT_TEMPLATE.format(
        repo_name=repo_path.name,
        file_count=sum(1 for _ in repo_path.rglob("*") if _.is_file()),
        languages=languages,
        detected_summary=detected_summary,
        top_level=top_level_str,
        key_files=key_files_str,
    )

    try:
        from model_provider import ChatRequest, Message, Role, TextBlock, chat
        from model_provider.providers import OpenAIProvider

        response = chat(
            ChatRequest(
                model="gpt-4o-mini",
                messages=[
                    Message(
                        role=Role.SYSTEM, content=(TextBlock(text=LLM_SYSTEM_PROMPT),)
                    ),
                    Message(role=Role.USER, content=(TextBlock(text=prompt),)),
                ],
            ),
            provider=OpenAIProvider(),
            transport=transport,
            api_key=api_key,
        )

        import json

        llm_components = json.loads(response.text)

        # Convert to InfraComponent objects
        components = []
        for item in llm_components:
            if not all(
                k in item
                for k in (
                    "component_type",
                    "layer",
                    "name",
                    "description",
                    "confidence",
                )
            ):
                continue
            if item.get("confidence", 0) < 0.6:
                continue
            if item.get("layer") not in INFRASTRUCTURE_LAYERS:
                continue

            comp = InfraComponent(
                layer=item["layer"],
                component_type=item["component_type"],
                name=item["name"],
                description=item["description"],
                technologies=tuple(item.get("technologies", [])),
                code_locations=(),
                config_locations=(),
                confidence=float(item["confidence"]),
                detection_method="llm",
            )
            components.append(comp)

        return components

    except Exception:
        # LLM failures are non-fatal
        return []


# ---------------------------------------------------------------------------
# Main Scanner Class
# ---------------------------------------------------------------------------


class InfrastructureScanner:
    """Full 12-layer infrastructure scanner with three detection layers."""

    def __init__(
        self,
        llm_transport: Transport | None = None,
        model_provider: object | None = None,
        api_key: str | None = None,
    ):
        """
        Args:
            llm_transport: Optional LLM transport for Layer 3 detection
            model_provider: Optional model provider for LLM calls
            api_key: Optional API key for LLM calls
        """
        self._llm_transport = llm_transport
        self._model_provider = model_provider
        self._api_key = api_key

    def scan(self, repo_path: Path) -> InfrastructureMap:
        """Full 12-layer infrastructure scan.

        Runs all three detection layers and combines results.
        """
        repo_path = repo_path.resolve()

        # Layer 1: Keyword scanning
        keyword_components = scan_keywords(repo_path)

        # Layer 2: Config file parsing
        config_components = parse_all_configs(repo_path)

        # Combine and deduplicate
        all_components = self._deduplicate_components(
            keyword_components + config_components
        )

        # Layer 3: LLM-assisted (optional)
        llm_components = []
        if self._llm_transport and self._api_key:
            # Import here to avoid circular imports
            try:
                import asyncio

                llm_components = asyncio.run(
                    scan_with_llm(
                        repo_path,
                        all_components,
                        self._llm_transport,
                        self._api_key,
                    )
                )
            except Exception:
                pass

        all_components.extend(llm_components)

        # Final deduplication
        final_components = self._deduplicate_components(all_components)

        # Build infrastructure map
        layer_summary: dict[str, int] = {}
        for comp in final_components:
            layer_summary[comp.layer] = layer_summary.get(comp.layer, 0) + 1

        layers_covered = len(layer_summary)

        return InfrastructureMap(
            repo_name=repo_path.name,
            components=tuple(final_components),
            layers_covered=layers_covered,
            total_components=len(final_components),
            layer_summary=layer_summary,
        )

    def scan_layer(self, repo_path: Path, layer: str) -> tuple[InfraComponent, ...]:
        """Scan for a specific layer only."""
        if layer not in INFRASTRUCTURE_LAYERS:
            raise ValueError(
                f"Invalid layer: {layer}. Must be one of {INFRASTRUCTURE_LAYERS}"
            )

        full_map = self.scan(repo_path)
        return full_map.components_by_layer(layer)

    def get_coverage(self, infra_map: InfrastructureMap) -> dict[str, float]:
        """Return per-layer coverage scores (0.0-1.0)."""
        return infra_map.get_coverage()

    def _deduplicate_components(
        self, components: list[InfraComponent]
    ) -> list[InfraComponent]:
        """Deduplicate components by (layer, component_type, name similarity)."""
        seen: dict[tuple[str, str], InfraComponent] = {}

        for comp in components:
            key = (comp.layer, comp.component_type)
            if key not in seen:
                seen[key] = comp
            else:
                # Keep the one with higher confidence
                if comp.confidence > seen[key].confidence:
                    seen[key] = comp

        return list(seen.values())
