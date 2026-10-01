#!/usr/bin/env python3
"""Quickstart for the Infrastructure Scanner.

Demonstrates offline scanning of a local repository.
Run with: python catalog/deployment/scanner/examples/quickstart.py [PATH]

Without arguments, scans this repository (ai_infrastructure).
With --llm flag and OPENAI_API_KEY, enables LLM-assisted detection.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scanner import InfrastructureScanner


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="infrastructure-scanner-quickstart",
        description="Scan a repository for 12-layer infrastructure components",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to scan (default: current directory)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Enable LLM-assisted detection (requires OPENAI_API_KEY and transport)",
    )
    parser.add_argument(
        "--layer",
        choices=[
            "identity",
            "transaction",
            "state",
            "data",
            "communication",
            "delivery",
            "observability",
            "security",
            "deployment",
            "integration",
            "user_experience",
            "governance",
        ],
        help="Scan only a specific layer",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}", file=sys.stderr)
        return 1

    # Setup LLM if requested
    llm_transport = None
    model_provider = None
    api_key = None

    if args.llm:
        import os

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print(
                "Error: --llm requires OPENAI_API_KEY environment variable",
                file=sys.stderr,
            )
            return 1
        try:
            from llm_http_transport.transport import UrllibTransport
            from model_provider.providers import OpenAIProvider

            llm_transport = UrllibTransport()
            model_provider = OpenAIProvider()
        except ImportError as e:
            print(f"Error: LLM dependencies not available: {e}", file=sys.stderr)
            return 1

    scanner = InfrastructureScanner(
        llm_transport=llm_transport,
        model_provider=model_provider,
        api_key=api_key,
    )

    print(f"Scanning: {repo_path}")
    if args.layer:
        print(f"Layer filter: {args.layer}")

    try:
        if args.layer:
            components = scanner.scan_layer(repo_path, args.layer)
            infra_map = None
        else:
            infra_map = scanner.scan(repo_path)
            components = infra_map.components

        if args.json:
            import json

            if infra_map:
                print(json.dumps(infra_map.to_dict(), indent=2))
            else:
                print(
                    json.dumps(
                        [
                            {
                                "layer": c.layer,
                                "component_type": c.component_type,
                                "name": c.name,
                                "description": c.description,
                                "technologies": list(c.technologies),
                                "code_locations": list(c.code_locations),
                                "config_locations": list(c.config_locations),
                                "confidence": c.confidence,
                                "detection_method": c.detection_method,
                            }
                            for c in components
                        ],
                        indent=2,
                    )
                )
            return 0

        # Pretty print
        if infra_map:
            print(f"\n{'='*60}")
            print(f"Infrastructure Map: {infra_map.repo_name}")
            print(f"{'='*60}")
            print(f"Layers covered: {infra_map.layers_covered}/12")
            print(f"Total components: {infra_map.total_components}")
            print("\nLayer Summary:")
            for layer, count in sorted(infra_map.layer_summary.items()):
                print(f"  {layer:20s}: {count}")

            print("\nCoverage:")
            coverage = scanner.get_coverage(infra_map)
            for layer, score in sorted(coverage.items()):
                bar = "█" * int(score * 20)
                print(f"  {layer:20s}: {bar} {score:.0%}")

            print(f"\nComponents ({len(infra_map.components)}):")
        else:
            print(f"\nComponents in layer '{args.layer}' ({len(components)}):")

        for comp in components:
            print(f"\n  [{comp.layer}] {comp.component_type}")
            print(f"    Name: {comp.name}")
            print(f"    Description: {comp.description}")
            if comp.technologies:
                print(f"    Technologies: {', '.join(comp.technologies)}")
            if comp.code_locations:
                print(f"    Code locations: {', '.join(comp.code_locations[:3])}")
                if len(comp.code_locations) > 3:
                    print(f"      ... and {len(comp.code_locations) - 3} more")
            if comp.config_locations:
                print(f"    Config locations: {', '.join(comp.config_locations[:3])}")
            print(f"    Confidence: {comp.confidence:.0%} ({comp.detection_method})")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
