"""Compatibility entry points for EcoRadar recommendations.

The official recommendation implementation lives in
`ecoradar.core.recommendation_engine`. This module intentionally keeps only the
public compatibility function used by older callers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ecoradar.core.recommendation_engine import run_recommendation_engine


def generate_recommendation_outputs(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Generate official recommendation outputs using the central engine."""

    result = run_recommendation_engine(project_root)
    return {
        "json": result["recommendations_json"],
        "csv": result["priority_matrix_csv"],
        "markdown": result["recommendations_markdown"],
        "recommendation_count": result["recommendation_count"],
    }

