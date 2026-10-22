"""Aggregation functions for evaluation suites.

Re-exports from protocols to avoid circular imports.
"""

from __future__ import annotations

from .protocols import (
    max_score,
    min_score,
    pass_fail,
    weighted_average,
)

__all__ = ["max_score", "min_score", "pass_fail", "weighted_average"]
