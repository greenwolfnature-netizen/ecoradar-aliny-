"""Compatibility entry points for EcoRadar diagnosis.

The official diagnosis implementation lives in
`ecoradar.core.diagnosis_engine`. This module intentionally keeps only the
public compatibility function used by older callers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ecoradar.core.diagnosis_engine import run_diagnosis_engine


def generate_diagnosis_outputs(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Generate official diagnosis outputs using the central engine."""

    result = run_diagnosis_engine(project_root)
    return {
        "json": result["json"],
        "markdown": result["markdown"],
        "overall_state": "diagnosi parcial defensable",
        "confidence": "mitjana",
    }

