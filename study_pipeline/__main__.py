"""CLI entry point for the study pipeline.

    python -m study_pipeline <repo-url> [more-urls...]

This is a thin CLI over the library (ADR-0021 Decision 4). All the logic lives
in the modules; this file parses arguments, sequences the stages, and prints
what happened. Keeping it thin is what makes the pipeline testable without
spawning a subprocess for every check.

WHAT IT WRITES
--------------
Markdown reports under `study_pipeline/studied_repos/`. Nothing else. It never
writes into `catalog/` or `integrations/` — enforced by a test over this file's
AST, not by convention (ADR-0021 Decision 2).
"""

from __future__ import annotations

import argparse
import sys
from typing import Final

from study_pipeline import __version__
from study_pipeline.classify import classify_all, load_taxonomy, proposal_summary
from study_pipeline.inventory import build_inventory
from study_pipeline.patterns import extract_candidates, summarise
from study_pipeline.report import build_report as assemble_report
from study_pipeline.report import render_report, report_path
from study_pipeline.workspace import (
    StudyError,
    repo_root,
    study_workspace,
    workspace_size_bytes,
)

#: Exit codes. Distinct values so a caller can tell "the study ran and found
#: nothing" from "the study did not run".
EXIT_OK: Final = 0
EXIT_STUDY_FAILED: Final = 1
EXIT_USAGE: Final = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="study_pipeline",
        description=(
            "Statically study an open-source AI infrastructure repository and "
            "write a structural report. The studied code is never executed, "
            "imported or installed (ADR-0021)."
        ),
        epilog=(
            "Reports are written under study_pipeline/studied_repos/. The "
            "pipeline does not write to catalog/ or integrations/."
        ),
    )
    parser.add_argument(
        "urls",
        nargs="+",
        metavar="REPO_URL",
        help="HTTPS URL of a repository on an allowed host (github.com, gitlab.com, codeberg.org).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Study and report to stdout without writing a file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the report path (or the report, with --dry-run).",
    )
    parser.add_argument(
        "--version", action="version", version=f"study_pipeline {__version__}"
    )
    return parser


def study_one(url: str, *, dry_run: bool, quiet: bool) -> int:
    """Study one repository end to end. Returns a process exit code."""
    root = repo_root()

    try:
        taxonomy = load_taxonomy(root)
    except FileNotFoundError as error:
        # A missing taxonomy means we cannot classify, and classifying against
        # a hardcoded fallback is the specific bug this pipeline already fixed
        # once. Refuse rather than guess.
        print(f"ERROR: {error}", file=sys.stderr)
        print(
            "The study pipeline classifies against TAXONOMY.md. Run it from "
            "inside the repository, or fix the missing file.",
            file=sys.stderr,
        )
        return EXIT_STUDY_FAILED

    try:
        with study_workspace(url) as clone:
            _stage(quiet, f"cloned {clone.slug} at {clone.commit[:8]}")
            inventory = build_inventory(clone.path)
            # "4 declared dependencies" for a 620-package monorepo is
            # misleading, so the qualifier travels with the number.
            dependency_note = " (root only)" if inventory.notes else ""
            _stage(
                quiet,
                f"  {inventory.total_files} files, "
                f"{len(inventory.declared_dependencies)} declared dependencies"
                f"{dependency_note}, {inventory.primary_language}",
            )

            candidates = extract_candidates(inventory)
            classifications = classify_all(candidates, taxonomy)
            counts = summarise(candidates)
            _stage(
                quiet,
                f"  patterns: {counts['strong']} strong, "
                f"{counts['moderate']} moderate, {counts['weak']} weak",
            )

            report = assemble_report(
                slug=clone.slug,
                url=clone.url,
                commit=clone.commit,
                size_bytes=clone.size_bytes,
                inventory=inventory,
                candidates=candidates,
                classifications=classifications,
                taxonomy=taxonomy,
            )
            text = render_report(report)

            if dry_run:
                print(text)
                return EXIT_OK

            destination = report_path(root, report)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")

            proposals = proposal_summary(classifications)["proposed"]
            if proposals and not quiet:
                print(f"  proposed new categories: {', '.join(proposals)}")
            print(destination.relative_to(root))
            return EXIT_OK

    except StudyError as error:
        # Expected, explained failures (refused URL, oversize clone, git
        # failure). Reported as a study failure, not a crash.
        print(f"ERROR studying {url}: {error}", file=sys.stderr)
        return EXIT_STUDY_FAILED


def _stage(quiet: bool, message: str) -> None:
    if not quiet:
        print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code rather than raising SystemExit."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.urls:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE

    failures = 0
    for url in args.urls:
        code = study_one(url, dry_run=args.dry_run, quiet=args.quiet)
        if code != EXIT_OK:
            failures += 1

    if failures and not args.quiet:
        print(
            f"{failures} of {len(args.urls)} stud(ies) failed. The workspace was "
            f"cleaned; current size {workspace_size_bytes()} bytes.",
            file=sys.stderr,
        )
    # Partial failure is a failure: a caller scripting this must not read a
    # half-done batch as success.
    return EXIT_STUDY_FAILED if failures else EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    raise SystemExit(main())
