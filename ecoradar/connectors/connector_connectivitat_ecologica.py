"""Ecological connectivity connector for EcoRadar.

Downloads official Generalitat `INFRAESTRUCTURA_VERDA` WFS layers, clips them to
the Alinya study area and stores normalized source layers. It does not calculate
EcoRadar connectivity indicators.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd


PROJECT_ROOT = Path("projectes/Alinya")
STUDY_AREA_PATH = PROJECT_ROOT / "processed" / "study_area.gpkg"
RAW_DIR = PROJECT_ROOT / "raw" / "connectivitat"
PROCESSED_PATH = PROJECT_ROOT / "processed" / "connectivitat.gpkg"
SUMMARY_PATH = PROJECT_ROOT / "indicators" / "connectivitat_resum.csv"
METADATA_PATH = PROJECT_ROOT / "metadata" / "connectivitat_metadata.json"
VALIDATION_PATH = PROJECT_ROOT / "metadata" / "validations" / "connector_connectivitat_ecologica_validation.json"

TARGET_CRS = "EPSG:25831"
WFS_URL = "https://sig.gencat.cat/ows/INFRAESTRUCTURA_VERDA/wfs"
SOURCE_PAGE = "https://mediambient.gencat.cat/"

LAYERS = [
    ("connectivitat_terrestre_index", "INFRAESTRUCTURA_VERDA:CONECO_INDX_CONNEC_TERR_GRAL", "terrestrial_connectivity_index"),
    ("connectors_fluvials_complementaris", "INFRAESTRUCTURA_VERDA:CONECO_CONNECTORS_FLUV_COMPL", "fluvial_connectors_complementary"),
    ("connectors_fluvials_principals", "INFRAESTRUCTURA_VERDA:CONECO_CONNECTORS_FLUV_PPAL", "fluvial_connectors_main"),
    ("connectors_terrestres_complementaris", "INFRAESTRUCTURA_VERDA:CONECO_CONNECTORS_TERR_COMPL", "terrestrial_connectors_complementary"),
    ("connectors_terrestres_principals", "INFRAESTRUCTURA_VERDA:CONECO_CONNECTORS_TERR_PPAL", "terrestrial_connectors_main"),
    ("zones_connectors_infraestructura_verda", "INFRAESTRUCTURA_VERDA:INFRAVERD_ZONES_CONNECTORS", "green_infrastructure_connector_zones"),
]


def main() -> None:
    result = run_connector()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_connector(*, refresh: bool = False) -> dict[str, Any]:
    _ensure_dirs()
    study_area = _load_study_area()
    if PROCESSED_PATH.exists():
        PROCESSED_PATH.unlink()
    rows: list[dict[str, Any]] = []

    for layer_id, type_name, theme in LAYERS:
        raw_path = RAW_DIR / f"{layer_id}.geojson"
        if refresh or not raw_path.exists():
            _download_layer(type_name, study_area, raw_path)
        gdf = _read_clip_normalize(raw_path, study_area, layer_id, type_name, theme)
        if not gdf.empty:
            gdf.to_file(PROCESSED_PATH, layer=layer_id, driver="GPKG")
        rows.append(_summary(layer_id, type_name, theme, raw_path, gdf))

    _write_summary(rows)
    metadata = _write_metadata(study_area, rows)
    validation = _write_validation(metadata)
    return {
        "status": validation["status"],
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "metadata_path": str(METADATA_PATH),
        "validation_path": str(VALIDATION_PATH),
        "layers": rows,
    }


def _ensure_dirs() -> None:
    for directory in (RAW_DIR, PROCESSED_PATH.parent, SUMMARY_PATH.parent, METADATA_PATH.parent, VALIDATION_PATH.parent):
        directory.mkdir(parents=True, exist_ok=True)


def _load_study_area() -> gpd.GeoDataFrame:
    if not STUDY_AREA_PATH.exists():
        raise FileNotFoundError(f"Study area not found: {STUDY_AREA_PATH}")
    study_area = gpd.read_file(STUDY_AREA_PATH).to_crs(TARGET_CRS)
    if study_area.empty:
        raise ValueError("Study area is empty")
    invalid = ~study_area.geometry.is_valid
    if bool(invalid.any()):
        raise ValueError("Study area has invalid geometries")
    return study_area


def _download_layer(type_name: str, study_area: gpd.GeoDataFrame, output_path: Path) -> None:
    xmin, ymin, xmax, ymax = [float(value) for value in study_area.total_bounds]
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_name,
        "outputFormat": "application/json",
        "srsName": TARGET_CRS,
        "BBOX": f"{xmin},{ymin},{xmax},{ymax},{TARGET_CRS}",
    }
    request = Request(
        f"{WFS_URL}?{urlencode(params)}",
        headers={"Accept": "application/json,*/*", "User-Agent": "EcoRadar/0.1 connectivity connector"},
    )
    with urlopen(request, timeout=180) as response:
        payload = response.read()
    if payload.lstrip().startswith(b"<"):
        raise RuntimeError(payload[:1000].decode("utf-8", "ignore"))
    output_path.write_bytes(payload)


def _read_clip_normalize(
    path: Path,
    study_area: gpd.GeoDataFrame,
    layer_id: str,
    type_name: str,
    theme: str,
) -> gpd.GeoDataFrame:
    try:
        gdf = gpd.read_file(path)
    except Exception:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload.get("features"):
            return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)
        raise
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)
    if gdf.crs is None:
        gdf = gdf.set_crs(TARGET_CRS)
    gdf = gdf.to_crs(TARGET_CRS)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    invalid = ~gdf.geometry.is_valid
    if bool(invalid.any()):
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].make_valid()
    clipped = gpd.clip(gdf, study_area.geometry.union_all())
    clipped = clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty].copy()
    if clipped.empty:
        return clipped
    clipped["ecoradar_layer"] = layer_id
    clipped["ecoradar_theme"] = theme
    clipped["ecoradar_source"] = type_name
    clipped["feature_area_ha"] = clipped.geometry.area / 10000
    clipped["feature_length_km"] = clipped.geometry.length / 1000
    return _sanitize_columns(clipped)


def _sanitize_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    output = gdf.copy()
    seen: dict[str, int] = {}
    columns: list[str] = []
    for column in output.columns:
        if column == output.geometry.name:
            columns.append(column)
            continue
        clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(column)).strip("_") or "field"
        clean = clean[:48]
        count = seen.get(clean, 0)
        seen[clean] = count + 1
        if count:
            clean = f"{clean[:44]}_{count}"
        columns.append(clean)
    output.columns = columns
    return output


def _summary(layer_id: str, type_name: str, theme: str, raw_path: Path, gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    if gdf.empty:
        geometry_types: list[str] = []
        feature_count = 0
        area_ha = 0.0
        length_km = 0.0
    else:
        geometry_types = sorted({str(value) for value in gdf.geometry.geom_type.unique()})
        feature_count = int(len(gdf))
        area_ha = float(gdf.geometry.area.sum() / 10000)
        length_km = float(gdf.geometry.length.sum() / 1000)
    return {
        "layer_id": layer_id,
        "type_name": type_name,
        "theme": theme,
        "raw_path": str(raw_path),
        "feature_count": feature_count,
        "geometry_types": geometry_types,
        "area_ha": round(area_ha, 4),
        "length_km": round(length_km, 4),
    }


def _write_summary(rows: list[dict[str, Any]]) -> None:
    with SUMMARY_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["layer_id", "type_name", "theme", "feature_count", "geometry_types", "area_ha", "length_km", "raw_path"],
        )
        writer.writeheader()
        for row in rows:
            serialized = row.copy()
            serialized["geometry_types"] = ";".join(row["geometry_types"])
            writer.writerow(serialized)


def _write_metadata(study_area: gpd.GeoDataFrame, rows: list[dict[str, Any]]) -> dict[str, Any]:
    metadata = {
        "project": "Alinya",
        "source": "Infraestructura Verda / Connectivitat ecològica",
        "responsible_organization": "Generalitat de Catalunya",
        "url": SOURCE_PAGE,
        "service_url": WFS_URL,
        "service_type": "WFS 2.0.0",
        "query_date": datetime.now(timezone.utc).isoformat(),
        "crs": TARGET_CRS,
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "layers": rows,
        "limitations": [
            "The connector stores official connectivity layers clipped to the study area.",
            "It does not calculate EcoRadar connectivity scores or corridor prioritization.",
            "Large polygon layers may include features selected by BBOX and then clipped locally.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


def _write_validation(metadata: dict[str, Any]) -> dict[str, Any]:
    total_features = sum(int(row["feature_count"]) for row in metadata["layers"])
    status = "completed" if total_features > 0 else "failed"
    validation = {
        "connector": "connector_connectivitat_ecologica",
        "project": "Alinya",
        "validated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "can_advance_to_next_connector": status == "completed",
        "source": metadata["source"],
        "outputs": {
            "processed": str(PROCESSED_PATH),
            "summary": str(SUMMARY_PATH),
            "metadata": str(METADATA_PATH),
        },
        "checks": {
            "processed_exists": PROCESSED_PATH.exists(),
            "summary_exists": SUMMARY_PATH.exists(),
            "metadata_exists": METADATA_PATH.exists(),
            "total_features": total_features,
            "has_connectivity_index": any(row["layer_id"] == "connectivitat_terrestre_index" and row["feature_count"] > 0 for row in metadata["layers"]),
            "has_connectors": any("connectors" in row["layer_id"] and row["feature_count"] > 0 for row in metadata["layers"]),
        },
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return validation


if __name__ == "__main__":
    main()
