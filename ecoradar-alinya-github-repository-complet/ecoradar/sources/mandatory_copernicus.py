"""Mandatory Copernicus Sentinel gate for EcoRadar.

EcoRadar treats Sentinel-derived teledetection as a critical input. This gate
does not download data or create substitutes; it only verifies that the
official connector has produced the required real assets before indicators,
diagnosis or final products are allowed to run.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


REQUIRED_INDICES: tuple[str, ...] = ("ndvi", "ndmi", "ndwi", "nbr", "lst")
REQUIRED_REPORTS: tuple[str, ...] = (
    "indicators/teledeteccio_resum.csv",
    "metadata/teledeteccio_metadata.json",
    "metadata/teledeteccio_stats.json",
    "metadata/teledeteccio_percentiles.json",
    "metadata/teledeteccio_classification.json",
    "metadata/teledeteccio_ecological_summary.json",
    "metadata/validations/connector_copernicus_teledeteccio_validation.json",
)


class MandatoryCopernicusError(RuntimeError):
    """Raised when mandatory Copernicus assets are missing or invalid."""


def required_copernicus_outputs() -> tuple[str, ...]:
    """Return every path required by the mandatory Copernicus gate."""

    raster_outputs = tuple(f"processed/teledeteccio/{index}.tif" for index in REQUIRED_INDICES)
    map_outputs = tuple(f"maps/teledeteccio/{index}.png" for index in REQUIRED_INDICES)
    return raster_outputs + map_outputs + REQUIRED_REPORTS


def copernicus_gate_status(project_root: str | Path) -> dict[str, Any]:
    """Inspect mandatory Copernicus outputs for a project."""

    root = Path(project_root)
    required = required_copernicus_outputs()
    missing = [relative for relative in required if not (root / relative).exists()]
    summary_indices = _summary_indices(root / "indicators" / "teledeteccio_resum.csv")
    missing_summary_rows = [index for index in REQUIRED_INDICES if index not in summary_indices]
    metadata = _read_json(root / "metadata" / "teledeteccio_metadata.json")
    validation = _read_json(root / "metadata" / "validations" / "connector_copernicus_teledeteccio_validation.json")
    validation_status = str(validation.get("status", "")).lower()
    metadata_status = str(metadata.get("status", "")).lower()
    completed = (
        not missing
        and not missing_summary_rows
        and validation.get("can_advance_to_next_connector") is True
        and validation_status == "completed"
        and metadata_status == "completed"
    )
    return {
        "completed": completed,
        "required_indices": list(REQUIRED_INDICES),
        "required_outputs": list(required),
        "missing_outputs": missing,
        "missing_summary_rows": missing_summary_rows,
        "metadata_status": metadata.get("status"),
        "validation_status": validation.get("status"),
        "validation_message": validation.get("message"),
        "required_action": (
            "Execute connector_copernicus_teledeteccio with real Copernicus credentials and a validated LST/equivalent source."
        ),
    }


def ensure_mandatory_copernicus(project_root: str | Path) -> None:
    """Raise if mandatory Sentinel/Copernicus outputs are not ready."""

    status = copernicus_gate_status(project_root)
    if status["completed"]:
        return
    details = []
    if status["missing_outputs"]:
        details.append("missing outputs: " + ", ".join(status["missing_outputs"]))
    if status["missing_summary_rows"]:
        details.append("missing summary rows: " + ", ".join(status["missing_summary_rows"]))
    if status.get("validation_status"):
        details.append(f"validation status: {status['validation_status']}")
    message = "; ".join(details) if details else "mandatory Copernicus validation is not completed"
    raise MandatoryCopernicusError(
        "EcoRadar cannot continue without mandatory Copernicus Sentinel outputs "
        f"(NDVI, NDMI, NDWI, NBR and LST/equivalent): {message}."
    )


def _summary_indices(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as handle:
        return {str(row.get("index", "")).strip().lower() for row in csv.DictReader(handle)}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
