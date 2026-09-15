#!/usr/bin/env python3
"""Report the real state of the repository, and detect drift from its claims.

Charter §4 states the hardest rule in this repository: lifecycle status must
always reflect what artifacts *actually exist*. A ``status: TESTED`` entry with
no test file is a bug in the taxonomy, not a detail to fix later.

This script is the mechanical half of that rule. It reads TAXONOMY.md, compares
each capability's claimed status against the filesystem, and prints both a
summary and every inconsistency it can detect. It does not judge research
quality; it cannot. It only refuses to let the repository lie about structure.

Usage:
    python scripts/repo_status.py [--root PATH] [--quiet]

Exit codes:
    0  no drift detected
    1  drift detected (claimed status exceeds artifacts on disk)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The lifecycle order from charter §4. Index in this tuple is the stage number.
LIFECYCLE: tuple[str, ...] = (
    "DISCOVERED",
    "RESEARCHED",
    "UNDERSTOOD",
    "DESIGNED",
    "DECIDED",
    "PROTOTYPED",
    "IMPLEMENTED",
    "TESTED",
    "BENCHMARKED",
    "INTEGRATED",
    "MATURE",
    "DEPRECATED",
)

STAGE_INDEX: dict[str, int] = {stage: i for i, stage in enumerate(LIFECYCLE)}

# Artifact requirements per stage. A capability claiming stage N must have the
# artifacts required at every stage up to and including N. Each requirement is
# (description, checker). Matches charter §4, §14, §21.
NULL_ARTIFACT = ("", "null", "none", "n/a", "pending")

# Statuses that legitimately have no artifacts at all.
PRE_ARTIFACT_STAGES: frozenset[str] = frozenset({"DISCOVERED", "RESEARCHED"})


@dataclass
class Capability:
    """A single capability parsed out of TAXONOMY.md."""

    id: str
    name: str
    category: str
    status: str
    implementation: str
    tests: str
    benchmarks: str
    research_records: str
    decision: str
    depends_on: list[str] = field(default_factory=list)
    line: int = 0

    @property
    def stage(self) -> int:
        """Numeric lifecycle stage, or -1 when the status is unrecognized."""
        return STAGE_INDEX.get(self.status, -1)


@dataclass
class Drift:
    """One inconsistency between a claim and the filesystem."""

    capability_id: str
    claimed: str
    message: str
    severity: str  # "error" | "warning"


def _is_absent(value: str) -> bool:
    """True when a taxonomy field is empty or an explicit placeholder."""
    return value.strip().lower() in NULL_ARTIFACT


def _parse_capabilities(taxonomy_text: str) -> list[Capability]:
    """Extract capability entries from the TAXONOMY.md YAML block.

    This is a deliberately small, targeted parser rather than a YAML
    dependency: charter §20 lists unnecessary dependencies as something to
    avoid, and the taxonomy format is under this repository's control.
    """
    capabilities: list[Capability] = []
    current: dict[str, object] | None = None
    in_block = False
    line_no = 0
    list_key: str | None = None

    for raw_line in taxonomy_text.splitlines():
        line_no += 1
        stripped = raw_line.strip()

        if stripped.startswith("```yaml"):
            in_block = True
            continue
        if in_block and stripped.startswith("```"):
            in_block = False
            if current is not None:
                capabilities.append(_finalize(current, line_no))
                current = None
            continue
        if not in_block:
            continue

        if stripped.startswith("#") or not stripped:
            continue

        # A new capability begins with "- id:".
        match = re.match(r"^-\s+id:\s*(.+?)\s*$", stripped)
        if match:
            if current is not None:
                capabilities.append(_finalize(current, line_no))
            current = {"id": match.group(1).strip(), "_line": line_no}
            list_key = None
            continue

        if current is None:
            continue

        # A list item under a previously seen key (e.g. depends_on entries).
        item_match = re.match(r"^-\s+(.+?)\s*$", stripped)
        if item_match and list_key is not None:
            existing = current.setdefault(list_key, [])
            if isinstance(existing, list):
                existing.append(item_match.group(1).strip())
            continue

        key_match = re.match(r"^([A-Za-z_]+):\s*(.*)$", stripped)
        if not key_match:
            continue
        key, value = key_match.group(1), key_match.group(2).strip()
        value = value.split("#", 1)[0].strip() if not value.startswith("[") else value

        if value == "" or value == "[]":
            # `key:` with no value is ambiguous in YAML: it may be an empty
            # scalar or the head of a block list. Seed it as a list so that a
            # following "- item" line appends correctly; _finalize converts an
            # empty list to the empty string for scalar fields.
            current[key] = []
            list_key = key
            continue

        list_key = None
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            current[key] = (
                [v.strip() for v in inner.split(",") if v.strip()] if inner else []
            )
            continue
        current[key] = value.strip("'\"")

    if current is not None:
        capabilities.append(_finalize(current, line_no))

    return capabilities


def _finalize(raw: dict[str, object], line_no: int) -> Capability:
    """Convert a parsed mapping into a Capability."""

    def _text(key: str) -> str:
        value = raw.get(key, "")
        if isinstance(value, list):
            return ",".join(str(v) for v in value)
        return str(value)

    depends = raw.get("depends_on", [])
    return Capability(
        id=_text("id"),
        name=_text("name"),
        category=_text("category"),
        status=_text("status").upper(),
        implementation=_text("implementation"),
        tests=_text("tests"),
        benchmarks=_text("benchmarks"),
        research_records=_text("research_records"),
        decision=_text("decision"),
        depends_on=[str(d) for d in depends] if isinstance(depends, list) else [],
        line=line_no,
    )


def check_capability(cap: Capability, root: Path) -> list[Drift]:
    """Compare one capability's claims against artifacts on disk."""
    drifts: list[Drift] = []
    stage = cap.stage

    if stage < 0:
        drifts.append(
            Drift(
                cap.id,
                cap.status,
                f"unrecognized lifecycle status {cap.status!r}; "
                f"must be one of {', '.join(LIFECYCLE)}",
                "error",
            )
        )
        return drifts

    claimed = cap.status

    # DECIDED or later requires a recorded decision and an ADR reference.
    if stage >= STAGE_INDEX["DECIDED"] and (
        _is_absent(cap.decision) or cap.decision.lower() == "pending"
    ):
        drifts.append(
            Drift(
                cap.id,
                claimed,
                "claims DECIDED or later but 'decision' is still unset/pending "
                "(charter §8, §12)",
                "error",
            )
        )

    # DESIGNED or later requires a specification artifact.
    if stage >= STAGE_INDEX["DESIGNED"]:
        spec = root / "specifications" / f"{cap.id}.md"
        if not spec.is_file():
            drifts.append(
                Drift(
                    cap.id,
                    claimed,
                    f"claims {claimed} but no specification exists at "
                    f"specifications/{cap.id}.md",
                    "error",
                )
            )

    # RESEARCHED or later requires research records that actually exist.
    #
    # This previously only checked that the field was non-empty, so a taxonomy
    # entry could cite a research record that did not exist on disk and still
    # pass the drift check — the same class of bug as the empty-tests/ hole in
    # validate_catalog.py (ADR-0004). Existence is not evidence; presence is.
    if stage >= STAGE_INDEX["RESEARCHED"] and _is_absent(cap.research_records):
        drifts.append(
            Drift(
                cap.id,
                claimed,
                "claims RESEARCHED or later but 'research_records' is empty "
                "(charter §5, §6)",
                "error",
            )
        )
    elif stage >= STAGE_INDEX["RESEARCHED"]:
        missing = [
            record
            for record in (
                part.strip().strip("\"'") for part in cap.research_records.split(",")
            )
            if record and not (root / record).is_file()
        ]
        if missing:
            drifts.append(
                Drift(
                    cap.id,
                    claimed,
                    f"claims {claimed} but research record(s) do not exist: "
                    f"{', '.join(missing)}",
                    "error",
                )
            )

    # IMPLEMENTED or later requires an implementation path that exists.
    if stage >= STAGE_INDEX["IMPLEMENTED"]:
        if _is_absent(cap.implementation):
            drifts.append(
                Drift(
                    cap.id,
                    claimed,
                    f"claims {claimed} but 'implementation' is empty",
                    "error",
                )
            )
        else:
            impl = root / cap.implementation
            if not impl.exists():
                drifts.append(
                    Drift(
                        cap.id,
                        claimed,
                        f"claims {claimed} but implementation path does not exist: "
                        f"{cap.implementation}",
                        "error",
                    )
                )

    # TESTED or later requires a test artifact that exists.
    if stage >= STAGE_INDEX["TESTED"]:
        if _is_absent(cap.tests):
            drifts.append(
                Drift(
                    cap.id,
                    claimed,
                    f"claims {claimed} but 'tests' is empty — the exact failure "
                    f"charter §4 calls a taxonomy bug",
                    "error",
                )
            )
        else:
            tests = root / cap.tests
            if not tests.exists():
                drifts.append(
                    Drift(
                        cap.id,
                        claimed,
                        f"claims {claimed} but test path does not exist: {cap.tests}",
                        "error",
                    )
                )

    # BENCHMARKED or later requires benchmark artifacts.
    if stage >= STAGE_INDEX["BENCHMARKED"] and _is_absent(cap.benchmarks):
        drifts.append(
            Drift(
                cap.id,
                claimed,
                f"claims {claimed} but 'benchmarks' is empty (charter §19)",
                "error",
            )
        )

    # Pre-artifact stages should not over-claim artifacts either.
    if cap.status in PRE_ARTIFACT_STAGES and not _is_absent(cap.implementation):
        drifts.append(
            Drift(
                cap.id,
                claimed,
                f"status is {claimed} (pre-implementation) but an implementation "
                f"path is already recorded: {cap.implementation}",
                "warning",
            )
        )

    return drifts


def check_dependencies(caps: list[Capability]) -> list[Drift]:
    """Verify every depends_on target exists and is not behind its dependent."""
    drifts: list[Drift] = []
    by_id = {c.id: c for c in caps}

    for cap in caps:
        for dep in cap.depends_on:
            target = by_id.get(dep)
            if target is None:
                drifts.append(
                    Drift(
                        cap.id,
                        cap.status,
                        f"depends_on references unknown capability id {dep!r}",
                        "error",
                    )
                )
                continue
            # A dependency may not be at an earlier stage than its dependent
            # beyond the research stages, where ordering is not meaningful yet.
            if (
                cap.stage >= STAGE_INDEX["DESIGNED"]
                and target.stage < STAGE_INDEX["RESEARCHED"]
            ):
                drifts.append(
                    Drift(
                        cap.id,
                        cap.status,
                        f"{cap.id} is at {cap.status} but its dependency "
                        f"{dep!r} is only at {target.status}",
                        "warning",
                    )
                )

    return drifts


def count_catalog_entries(root: Path) -> int:
    """Count catalog entries present on disk."""
    catalog = root / "catalog"
    if not catalog.is_dir():
        return 0
    total = 0
    for category in sorted(p for p in catalog.iterdir() if p.is_dir()):
        total += sum(
            1
            for p in category.iterdir()
            if p.is_dir() and not p.name.startswith((".", "_"))
        )
    return total


def summarize(caps: list[Capability]) -> dict[str, int]:
    """Count capabilities per lifecycle stage."""
    counts: dict[str, int] = dict.fromkeys(LIFECYCLE, 0)
    for cap in caps:
        if cap.status in counts:
            counts[cap.status] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Report repository state and detect taxonomy drift."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root (default: parent of this script's directory)",
    )
    parser.add_argument("--quiet", action="store_true", help="print only problems")
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    taxonomy = root / "TAXONOMY.md"

    if not taxonomy.is_file():
        print(f"ERROR: TAXONOMY.md not found at {taxonomy}", file=sys.stderr)
        return 1

    caps = _parse_capabilities(taxonomy.read_text(encoding="utf-8"))

    drifts: list[Drift] = []
    for cap in caps:
        drifts.extend(check_capability(cap, root))
    drifts.extend(check_dependencies(caps))

    errors = [d for d in drifts if d.severity == "error"]
    warnings = [d for d in drifts if d.severity == "warning"]

    if args.json:
        print(
            json.dumps(
                {
                    "capabilities": len(caps),
                    "by_status": summarize(caps),
                    "catalog_entries": count_catalog_entries(root),
                    "errors": [d.__dict__ for d in errors],
                    "warnings": [d.__dict__ for d in warnings],
                },
                indent=2,
            )
        )
        return 1 if errors else 0

    if not args.quiet:
        print(f"Repository: {root.name}")
        print(f"Capabilities tracked: {len(caps)}")
        print(f"Catalog entries present: {count_catalog_entries(root)}")
        print()
        print("Lifecycle distribution:")
        counts = summarize(caps)
        for stage in LIFECYCLE:
            if counts[stage]:
                print(f"  {stage:<12} {counts[stage]}")
        print()

    if drifts:
        print(f"Governance drift: {len(errors)} error(s), {len(warnings)} warning(s)")
        for drift in drifts:
            label = "ERROR  " if drift.severity == "error" else "WARN   "
            print(f"  {label} [{drift.capability_id}] {drift.message}")
    elif not args.quiet:
        print("No governance drift detected.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
