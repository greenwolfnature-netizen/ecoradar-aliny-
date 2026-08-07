"""EcoRadar project datastore manifest.

The current EcoRadar projects still contain GeoPackages, rasters, CSV and JSON
outputs produced by specialized modules. This datastore manifest creates one
official inventory for a project so downstream code does not need to discover
files ad hoc.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


DATASTORE_JSON = "datastore/project_datastore.json"
DATASTORE_SQLITE = "datastore/ecoradar_project.sqlite"


@dataclass(frozen=True)
class ProjectDatastore:
    """Official datastore manifest for one EcoRadar project."""

    project: str
    path: str
    sqlite_path: str
    generated_at: str
    assets: tuple[dict[str, Any], ...]


ASSET_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("study_area", "processed/study_area.gpkg", "vector"),
    ("land_cover", "processed/cobertes_sol.gpkg", "vector"),
    ("habitats", "processed/habitats.gpkg", "vector"),
    ("biodiversity", "processed/biodiversitat.gpkg", "vector"),
    ("human_pressure", "processed/recreational_pressure.gpkg", "vector"),
    ("hydrology", "processed/hidrologia.gpkg", "vector"),
    ("connectivity", "processed/connectivitat.gpkg", "vector"),
    ("fires", "processed/incendis.gpkg", "vector"),
    ("terrain_dem", "processed/terrain/dem.tif", "raster"),
    ("terrain_slope", "processed/terrain/slope.tif", "raster"),
    ("terrain_aspect", "processed/terrain/aspect.tif", "raster"),
    ("sentinel_ndvi", "processed/teledeteccio/ndvi.tif", "raster"),
    ("sentinel_ndmi", "processed/teledeteccio/ndmi.tif", "raster"),
    ("sentinel_ndwi", "processed/teledeteccio/ndwi.tif", "raster"),
    ("sentinel_nbr", "processed/teledeteccio/nbr.tif", "raster"),
    ("lst_or_equivalent", "processed/teledeteccio/lst.tif", "raster"),
    ("sentinel_ndvi_map", "maps/teledeteccio/ndvi.png", "map"),
    ("sentinel_ndmi_map", "maps/teledeteccio/ndmi.png", "map"),
    ("sentinel_ndwi_map", "maps/teledeteccio/ndwi.png", "map"),
    ("sentinel_nbr_map", "maps/teledeteccio/nbr.png", "map"),
    ("lst_or_equivalent_map", "maps/teledeteccio/lst.png", "map"),
    ("teledetection_summary", "indicators/teledeteccio_resum.csv", "summary_csv"),
    ("teledetection_metadata", "metadata/teledeteccio_metadata.json", "metadata_json"),
    ("teledetection_stats", "metadata/teledeteccio_stats.json", "metadata_json"),
    ("teledetection_percentiles", "metadata/teledeteccio_percentiles.json", "metadata_json"),
    ("teledetection_classification", "metadata/teledeteccio_classification.json", "metadata_json"),
    ("teledetection_ecological_summary", "metadata/teledeteccio_ecological_summary.json", "metadata_json"),
    ("core_indicators", "indicators/ecoradar_core_indicators.json", "indicator_json"),
    ("diagnosis", "diagnosis/ecoradar_diagnosis.json", "diagnosis_json"),
    ("recommendations", "recommendations/recommendations.json", "recommendations_json"),
    ("validation", "validation/technical_validation.json", "validation_json"),
)


def build_project_datastore(project_root: str | Path = "projectes/Alinya") -> ProjectDatastore:
    """Create the official project datastore manifest."""

    root = Path(project_root)
    datastore_dir = root / "datastore"
    datastore_dir.mkdir(parents=True, exist_ok=True)
    assets = []
    for asset_id, relative, asset_type in ASSET_PATTERNS:
        path = root / relative
        assets.append(
            {
                "id": asset_id,
                "relative_path": relative,
                "type": asset_type,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
            }
        )
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "project": root.name,
        "generated_at": generated_at,
        "policy": "Official EcoRadar project datastore manifest. Modules should read registered assets instead of discovering arbitrary CSV/JSON files.",
        "assets": assets,
    }
    path = root / DATASTORE_JSON
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_sqlite(root / DATASTORE_SQLITE, root.name, generated_at, assets)
    return ProjectDatastore(
        project=root.name,
        path=str(path),
        sqlite_path=str(root / DATASTORE_SQLITE),
        generated_at=generated_at,
        assets=tuple(assets),
    )


def _write_sqlite(path: Path, project: str, generated_at: str, assets: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS datastore_assets (
                id TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                type TEXT NOT NULL,
                exists_flag INTEGER NOT NULL,
                size_bytes INTEGER,
                generated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("DELETE FROM datastore_assets")
        connection.executemany(
            """
            INSERT INTO datastore_assets
            (id, project, relative_path, type, exists_flag, size_bytes, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    project,
                    item["relative_path"],
                    item["type"],
                    1 if item["exists"] else 0,
                    item["size_bytes"],
                    generated_at,
                )
                for item in assets
            ],
        )
        connection.commit()
