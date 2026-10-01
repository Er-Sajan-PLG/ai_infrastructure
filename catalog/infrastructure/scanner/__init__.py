"""Infrastructure Scanner — 12-layer infrastructure detection.

A reusable capability for detecting infrastructure components across all
12 layers of any software repository.

Detection Methods:
  Layer 1: Keyword scanning (fast, broad)
  Layer 2: Config file deep parsing (deterministic, stdlib-only)
  Layer 3: LLM-assisted detection (optional, for ambiguous cases)

Usage:
    from scanner import InfrastructureScanner
    from llm_http_transport.transport import UrllibTransport
    from model_provider import OpenAIProvider

    # Offline-only scan
    scanner = InfrastructureScanner()
    infra_map = scanner.scan(Path("/path/to/repo"))

    # With LLM-assisted detection (requires API key)
    transport = UrllibTransport()
    scanner = InfrastructureScanner(
        llm_transport=transport,
        api_key="your-openai-api-key"
    )
    infra_map = scanner.scan(Path("/path/to/repo"))

    # Access results
    print(f"Layers covered: {infra_map.layers_covered}/12")
    print(f"Total components: {infra_map.total_components}")
    for layer, count in infra_map.layer_summary.items():
        print(f"  {layer}: {count}")

    # Scan specific layer only
    data_components = scanner.scan_layer(Path("/path/to/repo"), "data")

Coverage:
    coverage = scanner.get_coverage(infra_map)
    for layer, score in coverage.items():
        print(f"  {layer}: {score:.0%}")
"""

from __future__ import annotations

from .models import INFRASTRUCTURE_LAYERS, InfraComponent, InfrastructureMap
from .scanner import InfrastructureScanner, scan_keywords
from .taxonomy import INFRASTRUCTURE_TAXONOMY, validate_taxonomy

__all__ = [
    "INFRASTRUCTURE_LAYERS",
    "INFRASTRUCTURE_TAXONOMY",
    "InfraComponent",
    "InfrastructureMap",
    "InfrastructureScanner",
    "scan_keywords",
    "validate_taxonomy",
]

__version__ = "0.1.0"
