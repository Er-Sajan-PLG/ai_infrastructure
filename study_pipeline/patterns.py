"""Candidate pattern extraction — static, evidence-based, no execution.

WHAT A "PATTERN" IS HERE
------------------------
A named piece of infrastructure machinery that a project built, identified from
*structural evidence* and described in terms of where the evidence is.

This module does **not** claim to understand what a project does. It reports
what is present, where, and how strong the signal is, so a human or agent
session can read the report and do the understanding. That division is
deliberate (ADR-0021 Decision 2): understanding is the step where judgement is
required, and a script cannot supply it.

Every candidate therefore carries:
  * a **confidence** derived from the evidence, not from a heuristic score;
  * the **evidence paths** that produced it, so a reader can check the claim;
  * **limitations**, stating what the signal cannot tell you.

Confidence is deliberately conservative. A directory named `router/` is weak
evidence of a routing abstraction — it is a naming convention — so it is
`WEAK` and says so, rather than being promoted to a finding a report would
present as established.

WHAT IS DELIBERATELY NOT DETECTED
---------------------------------
No attempt is made to extract function signatures, class hierarchies, or
call graphs. Those are the parts that would look most impressive in a report
and are exactly the parts most likely to be *wrong* without executing the code
or building a real parser — and building one means either a runtime dependency
(ADR-0021 rejects) or a hand-rolled parser that will silently mis-handle the
first non-trivial file it meets. Names, paths, and manifest contents are
honest signals. Invented structure is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Final

from study_pipeline.inventory import Inventory

#: Marker filenames whose presence identifies a studied repository, used to
#: store the per-repo detection rules below. Kept as a plain dict so adding a
#: detector is a data change rather than a code change.
MAX_EVIDENCE_PATHS: Final = 8


class Confidence(Enum):
    """How much the evidence supports calling something a pattern.

    Ordered strongest to weakest. The labels are the vocabulary the report
    uses, and they exist so a reader is never shown a list of undifferentiated
    "findings" where a directory name and a whole subsystem look alike.
    """

    #: A dedicated directory holding multiple modules, plus a matching test
    #: directory or a manifest entry. Structural machinery, not a stray file.
    STRONG = "strong"

    #: A dedicated directory with at least one module, or a manifest entry
    #: declaring a dependency that exists only to provide this capability.
    MODERATE = "moderate"

    #: A conventional directory or file name. Could be a real abstraction, a
    #: stub, or an empty placeholder — the name alone cannot distinguish them.
    WEAK = "weak"


@dataclass(frozen=True, slots=True)
class Candidate:
    """A candidate infrastructure pattern found by structural inspection."""

    pattern_id: str
    name: str
    category: str
    confidence: Confidence
    evidence_paths: tuple[str, ...]
    evidence_kind: str
    limitations: str

    @property
    def is_reportable(self) -> bool:
        """Whether this belongs in a report's findings list.

        Everything found is reportable; the confidence is what varies. Filtering
        weak signals out entirely would hide the naming conventions that inform
        a reader's picture of a project.
        """
        return bool(self.evidence_paths)


# ---------------------------------------------------------------------------
# Detection rules
# ---------------------------------------------------------------------------
#
# Each rule maps a set of name fragments to a pattern. The design choices:
#
#   * Match on DIRECTORY NAMES and MANIFEST CONTENT, not on file contents. A
#     directory named `cache/` is evidence; a file containing the word "cache"
#     is noise, because the word appears in comments, docstrings and type
#     names.
#
#   * Fragments are matched against path COMPONENTS, so `src/foo/cache` is
#     found without the rule knowing about `src/`.
#
#   * Each rule states its own limitation. A detector that cannot say what it
#     fails to see invites a reader to over-trust it.


@dataclass(frozen=True, slots=True)
class _Rule:
    pattern_id: str
    name: str
    category: str
    fragments: tuple[str, ...]
    evidence_kind: str
    limitations: str
    #: Manifest requirement substrings that also count as evidence.
    manifest_hints: tuple[str, ...] = ()


_RULES: Final[tuple[_Rule, ...]] = (
    _Rule(
        pattern_id="retrieval",
        name="Retrieval / vector search",
        category="retrieval",
        fragments=(
            "retriev",
            "vector",
            "embedding",
            "embeddings",
            "similarity",
            "rerank",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "Presence of a retrieval directory says nothing about the algorithm, "
            "the index type, or whether it is wired into anything. Read the "
            "modules to establish that."
        ),
        manifest_hints=(
            "faiss",
            "chromadb",
            "pinecone",
            "qdrant",
            "weaviate",
            "lancedb",
        ),
    ),
    _Rule(
        pattern_id="memory",
        name="Memory / state persistence",
        category="memory",
        fragments=(
            "memory",
            "memories",
            "session",
            "sessions",
            "checkpoint",
            "persistence",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "A `memory/` directory is frequently a stub in an early project. "
            "Check module size before treating it as implemented machinery."
        ),
        manifest_hints=("redis", "sqlalchemy", "psycopg", "pymongo"),
    ),
    _Rule(
        pattern_id="tool-registry",
        name="Tool / function registry",
        category="tools",
        fragments=(
            "tool",
            "tools",
            "function",
            "functions",
            "actions",
            "skills",
            "plugin",
            "plugins",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "Cannot distinguish a decorator-based registry from a plain dict of "
            "callables, which are very different designs."
        ),
        manifest_hints=("jsonschema", "pydantic"),
    ),
    _Rule(
        pattern_id="model-provider",
        name="Model provider abstraction",
        category="models",
        fragments=(
            "provider",
            "providers",
            "llm",
            "llms",
            "model",
            "models",
            "completion",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "Most projects have one provider module. The interesting question — "
            "whether more than one provider is actually supported — requires "
            "reading the modules, not the directory name."
        ),
        manifest_hints=(
            "openai",
            "anthropic",
            "litellm",
            "google-generativeai",
            "cohere",
            "ollama",
        ),
    ),
    _Rule(
        pattern_id="agent-loop",
        name="Agent loop / orchestration",
        category="agents",
        fragments=(
            "agent",
            "agents",
            "loop",
            "runner",
            "executor",
            "orchestrat",
            "workflow",
            "graph",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "'Agent' is used for anything from a 20-line ReAct loop to a full "
            "planning system. The name carries almost no information."
        ),
        manifest_hints=(
            "langgraph",
            "langchain",
            "autogen",
            "crewai",
            "llama-index",
            "dspy",
        ),
    ),
    _Rule(
        pattern_id="protocol-client",
        name="Protocol client (MCP / tool protocol)",
        category="protocols",
        fragments=(
            "mcp",
            "protocol",
            "protocols",
            "transport",
            "client",
            "clients",
            "server",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "`client/` is overwhelmingly an HTTP client in most projects, not a "
            "protocol abstraction. Treat this category as the weakest signal."
        ),
        manifest_hints=("mcp", "modelcontextprotocol", "fastmcp"),
    ),
    _Rule(
        pattern_id="observability",
        name="Observability / tracing",
        category="observability",
        fragments=(
            "trace",
            "traces",
            "tracing",
            "observability",
            "telemetry",
            "instrument",
            "logging",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "A project that calls `logging.info` everywhere has the name without "
            "the abstraction. The distinction matters and is not visible here."
        ),
        manifest_hints=(
            "opentelemetry",
            "langfuse",
            "langsmith",
            "mlflow",
            "arize",
            "phoenix",
        ),
    ),
    _Rule(
        pattern_id="evaluation",
        name="Evaluation / benchmarking harness",
        category="evaluation",
        fragments=(
            "eval",
            "evals",
            "evaluation",
            "benchmark",
            "benchmarks",
            "metrics",
            "judge",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "Cannot tell a maintained evaluation suite from a stale script "
            "directory. Check the commit dates before adopting the design."
        ),
        manifest_hints=("deepeval", "ragas", "promptfoo"),
    ),
    _Rule(
        pattern_id="guardrails",
        name="Safety / guardrails",
        category="guardrails",
        fragments=(
            "guardrail",
            "guardrails",
            "safety",
            "moderation",
            "validator",
            "validators",
            "policy",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "A validation module frequently validates request SHAPE, not model "
            "output. Conflating the two is the common misreading."
        ),
        manifest_hints=("guardrails-ai", "nemoguardrails"),
    ),
    _Rule(
        pattern_id="rate-limiting",
        name="Rate limiting / retry policy",
        category="reliability",
        fragments=(
            "ratelimit",
            "rate_limit",
            "backoff",
            "retry",
            "retries",
            "throttle",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=("Frequently inlined into a client. Absence means little."),
        manifest_hints=("tenacity", "backoff", "limits", "aiolimiter"),
    ),
    _Rule(
        pattern_id="chunking",
        name="Document ingestion / chunking",
        category="retrieval",
        fragments=(
            "chunk",
            "chunking",
            "splitter",
            "splitters",
            "loader",
            "loaders",
            "ingest",
            "parser",
            "parsers",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "Chunking strategies are usually small and embedded rather than in "
            "their own module, so absence here is not evidence of absence."
        ),
        manifest_hints=(
            "unstructured",
            "pypdf",
            "langchain-text-splitters",
            "tiktoken",
        ),
    ),
    _Rule(
        pattern_id="config",
        name="Configuration / settings management",
        category="config",
        fragments=("config", "configs", "settings", "conf"),
        evidence_kind="directory evidence",
        limitations=(
            "Near-universal and rarely a distinguishing design. Reported for "
            "completeness, not as an adoption candidate."
        ),
        manifest_hints=("pydantic-settings", "dynaconf", "hydra-core"),
    ),
    _Rule(
        pattern_id="caching",
        name="Caching layer",
        category="caching",
        fragments=("cache", "caching", "memoize"),
        evidence_kind="directory or manifest evidence",
        limitations=(
            "A caching module is frequently small and inlined into a client "
            "rather than given its own directory, so absence means little. "
            "Deliberately does NOT match a bare `store`: `vector_stores/` and "
            "`graph_stores/` are data stores, not caches, and matching them "
            "reported LlamaIndex's storage layers as a caching layer."
        ),
        manifest_hints=("diskcache", "cachetools", "redis"),
    ),
    _Rule(
        pattern_id="rate-limiting",
        name="Rate limiting / retry policy",
        category="reliability",
        fragments=(
            "ratelimit",
            "rate_limit",
            "backoff",
            "retry",
            "retries",
            "throttle",
        ),
        evidence_kind="directory or manifest evidence",
        limitations=("Frequently inlined into a client. Absence means little."),
        manifest_hints=("tenacity", "backoff", "limits", "aiolimiter"),
    ),
)

#: Path components that are about HOW a repository is maintained, not about
#: what it is. A directory under one of these is never evidence of an
#: infrastructure pattern, whatever its name matches.
_NON_DESIGN_DIRS: Final[frozenset[str]] = frozenset(
    {
        # Documentation and examples: a `cache/` under docs/ is a tutorial.
        "docs",
        "doc",
        "documentation",
        "examples",
        "example",
        "samples",
        "tutorial",
        "tutorials",
        # Test trees: a `retrieval/` under tests/ is a fixture.
        "test",
        "tests",
        "testing",
        "spec",
        "specs",
        # CI and tooling configuration. Found as a false positive: the fragment
        # "workflow" matched `.github/workflows/`.
        ".github",
        ".gitlab",
        ".circleci",
        ".devcontainer",
        "workflows",
        # Caches and build output.
        ".import_linter_cache",
        ".uv-cache",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "htmlcov",
        "build",
        "dist",
        # Vendored third-party code is not this project's design.
        "vendor",
        "vendored",
        "third_party",
        "node_modules",
    }
)

_MANIFEST_STOPWORDS: Final[frozenset[str]] = frozenset(
    {"extras", "peer", "python", "require", "optional"}
)


def _requirement_name(requirement: str) -> str:
    """Extract the distribution name from a requirement string.

    `[extras] pytest>=8,<9` becomes `pytest`. Done by hand rather than with
    `packaging`, which is not a declared dependency of this package — the
    pipeline parses declared strings, it does not resolve them (ADR-0021).
    """
    text = requirement.strip()
    # Strip our own grouping labels.
    while text.startswith("["):
        closing = text.find("]")
        if closing == -1:
            break
        text = text[closing + 1 :].strip()
    # Strip extras, version specifiers, markers, spaces.
    for separator in ("[", ">", "<", "=", "!", "~", ";", " ", "("):
        index = text.find(separator)
        if index != -1:
            text = text[:index]
    return text.strip().lower().replace("_", "-")


def _manifest_matches(inventory: Inventory, hints: tuple[str, ...]) -> tuple[str, ...]:
    """Requirement names from the inventory that match any hint."""
    if not hints:
        return ()
    found: list[str] = []
    for requirement in inventory.declared_dependencies:
        name = _requirement_name(requirement)
        if not name or name in _MANIFEST_STOPWORDS:
            continue
        if any(hint in name for hint in hints):
            found.append(name)
    return tuple(dict.fromkeys(found))


def _matching_directories(
    directories: tuple[str, ...], fragments: tuple[str, ...]
) -> tuple[str, ...]:
    """Directories whose name contains any fragment, shallowest first.

    Matching is on path COMPONENTS rather than substrings of the whole path, so
    `docs/caching.md` cannot match a `cache` fragment as though it were a
    module, and a directory is only reported once.
    """
    matches: list[str] = []
    for directory in directories:
        components = [part.lower() for part in directory.split("/")]
        # Skip infrastructure and documentation trees. These are FALSE
        # POSITIVES, found by running this on a repository whose shape was
        # known: `.github/workflows/` matched the agent-loop rule through the
        # fragment "workflow", reporting a CI pipeline as an orchestration
        # loop. A detector that cannot tell CI from a subsystem produces a
        # report that reads as authoritative and is wrong.
        #
        # This checks ALL components rather than `components[:-1]`: the CI case
        # is a directory that IS `.github/workflows`, so excluding the final
        # component would miss it entirely.
        if any(component in _NON_DESIGN_DIRS for component in components):
            continue
        if any(
            fragment in component for component in components for fragment in fragments
        ):
            matches.append(directory)

    # Shallowest first: `src/cache` is more likely the real one than
    # `src/a/b/cache`, and a reader has limited attention.
    matches.sort(key=lambda path: (path.count("/"), path))
    return tuple(matches)


def _confidence_for(
    directories: tuple[str, ...],
    manifest_evidence: tuple[str, ...],
    inventory: Inventory,
) -> Confidence:
    """Derive confidence from the evidence, not from a scoring formula.

    The rule is deliberately simple and statable in one sentence, because a
    reader must be able to audit why something was rated what it was.

    A dedicated directory holding several modules, or independent evidence
    from two sources, is STRONG. A directory with at least one module, or a
    manifest entry alone, is MODERATE. A bare directory name is WEAK.
    """
    module_count = sum(
        1 for directory in directories if _directory_has_modules(directory, inventory)
    )

    if module_count >= 2 or (directories and manifest_evidence):
        return Confidence.STRONG
    if module_count == 1 or manifest_evidence:
        return Confidence.MODERATE
    return Confidence.WEAK


def _directory_has_modules(directory: str, inventory: Inventory) -> bool:
    """Whether a directory appears to hold importable modules.

    Uses the package list and the test layout as proxies: a directory that
    contains an `__init__.py` is a package (so it has modules by construction),
    and one named in the test layout has tests. Both are structural facts from
    the inventory rather than a second walk of the tree.
    """
    if any(
        package == directory or package.startswith(f"{directory}/")
        for package in inventory.packages
    ):
        return True
    return any(test_dir.startswith(f"{directory}/") for test_dir in inventory.test_dirs)


def extract_candidates(inventory: Inventory) -> tuple[Candidate, ...]:
    """Find candidate patterns in an inventory.

    Pure: takes an :class:`~study_pipeline.inventory.Inventory` and returns
    candidates. Ordered STRONG first, then by pattern id, so a report's most
    defensible findings appear first.
    """
    candidates: list[Candidate] = []

    for rule in _RULES:
        directories = _matching_directories(inventory.directories, rule.fragments)
        manifest_evidence = _manifest_matches(inventory, rule.manifest_hints)

        if not directories and not manifest_evidence:
            continue

        evidence: list[str] = []
        for directory in directories[:MAX_EVIDENCE_PATHS]:
            evidence.append(f"{directory}/")
        for name in manifest_evidence[:MAX_EVIDENCE_PATHS]:
            evidence.append(f"declared dependency: {name}")

        candidates.append(
            Candidate(
                pattern_id=rule.pattern_id,
                name=rule.name,
                category=rule.category,
                confidence=_confidence_for(directories, manifest_evidence, inventory),
                evidence_paths=tuple(evidence[:MAX_EVIDENCE_PATHS]),
                evidence_kind=rule.evidence_kind,
                limitations=rule.limitations,
            )
        )

    order = {Confidence.STRONG: 0, Confidence.MODERATE: 1, Confidence.WEAK: 2}
    candidates.sort(key=lambda c: (order[c.confidence], c.pattern_id))
    return tuple(candidates)


def summarise(candidates: tuple[Candidate, ...]) -> dict[str, int]:
    """Count candidates by confidence, for a report header."""
    counts = {confidence.value: 0 for confidence in Confidence}
    for candidate in candidates:
        counts[candidate.confidence.value] += 1
    return counts


# NOTE ON CATEGORIES: pattern rules above declare a `category` string, and the
# classifier (study_pipeline/classify) is what checks it against the REAL
# taxonomy by parsing TAXONOMY.md. This module deliberately does not carry a
# list of valid categories.
#
# It did, briefly, and the list was wrong in both directions: it omitted `mcp`,
# which the taxonomy has, and it invented `performance` and `reliability`,
# which it does not. A constant that duplicates the taxonomy drifts from it,
# and a classifier consulting a stale constant produces confident, authoritative
# output that is incorrect. Read the taxonomy from the file (ADR-0021).

_SLUG_RE: Final = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Turn arbitrary text into a taxonomy-safe identifier.

    Proposed pattern ids must be usable as `TAXONOMY.md` ids, which are
    lower-case and hyphenated.
    """
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return slug or "unnamed"
