"""Official wildfire history connector for EcoRadar.

Uses the Generalitat `VEGETACIO` WFS burned-area layer for local fire
perimeters. EFFIS is consulted only as an official Copernicus dataset catalogue
unless a product-specific geometry download workflow has been verified.

The connector produces normalized source data and validation records. It does
not calculate fire risk, resilience scores or EcoRadar indicators.
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
RAW_DIR = PROJECT_ROOT / "raw" / "incendis"
RAW_GENCAT_PATH = RAW_DIR / "vegetacio_incendis_alinya_bbox.geojson"
RAW_EFFIS_CATALOG_PATH = RAW_DIR / "effis_drf_datasets.json"
PROCESSED_PATH = PROJECT_ROOT / "processed" / "incendis.gpkg"
SUMMARY_PATH = PROJECT_ROOT / "indicators" / "incendis_resum.csv"
METADATA_PATH = PROJECT_ROOT / "metadata" / "incendis_metadata.json"
VALIDATION_PATH = PROJECT_ROOT / "metadata" / "validations" / "connector_incendis_historial_validation.json"

TARGET_CRS = "EPSG:25831"
GENCAT_WFS_URL = "https://sig.gencat.cat/ows/VEGETACIO/wfs"
GENCAT_LAYER = "VEGETACIO:VEGETACIO_INCENDIS"
EFFIS_DRF_DATASETS_API = "https://api.effis.emergency.copernicus.eu/rest/drf/datasets/"


def main() -> None:
    result = run_connector()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_connector(*, refresh: bool = False) -> dict[str, Any]:
    _ensure_dirs()
    study_area = _load_study_area()
    if refresh or not RAW_GENCAT_PATH.exists():
        _download_gencat_fires(study_area)
    if refresh or not RAW_EFFIS_CATALOG_PATH.exists():
        _download_effis_catalog()

    fires = _read_and_clip_fires(study_area)
    fires = _normalize_fires(fires)
    effis_catalog = _read_effis_catalog()

    if PROCESSED_PATH.exists():
        PROCESSED_PATH.unlink()
    if not fires.empty:
        fires.to_file(PROCESSED_PATH, layer="incendis_historics", driver="GPKG")

    summary_rows = _write_summary(fires, effis_catalog)
    metadata = _write_metadata(study_area, fires, effis_catalog, summary_rows)
    validation = _write_validation(metadata)
    return {
        "status": validation["status"],
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "metadata_path": str(METADATA_PATH),
        "validation_path": str(VALIDATION_PATH),
        "features": int(len(fires)),
        "effis_catalog_datasets": len(effis_catalog),
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


def _download_gencat_fires(study_area: gpd.GeoDataFrame) -> None:
    xmin, ymin, xmax, ymax = [float(value) for value in study_area.total_bounds]
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": GENCAT_LAYER,
        "outputFormat": "application/json",
        "srsName": TARGET_CRS,
        "BBOX": f"{xmin},{ymin},{xmax},{ymax},{TARGET_CRS}",
    }
    url = f"{GENCAT_WFS_URL}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json,*/*",
            "User-Agent": "EcoRadar/0.1 fire-history connector",
        },
    )
    with urlopen(request, timeout=120) as response:
        payload = response.read()
    if payload.lstrip().startswith(b"<"):
        raise RuntimeError(payload[:1000].decode("utf-8", "ignore"))
    RAW_GENCAT_PATH.write_bytes(payload)


def _download_effis_catalog() -> None:
    request = Request(
        EFFIS_DRF_DATASETS_API,
        headers={
            "Accept": "application/json,*/*",
            "User-Agent": "EcoRadar/0.1 EFFIS catalogue check",
        },
    )
    with urlopen(request, timeout=120) as response:
        payload = response.read()
    if payload.lstrip().startswith(b"<"):
        raise RuntimeError(payload[:1000].decode("utf-8", "ignore"))
    RAW_EFFIS_CATALOG_PATH.write_bytes(payload)


def _read_and_clip_fires(study_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    try:
        source = gpd.read_file(RAW_GENCAT_PATH)
    except Exception:
        payload = json.loads(RAW_GENCAT_PATH.read_text(encoding="utf-8"))
        if not payload.get("features"):
            return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)
        raise
    if source.empty:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)
    if source.crs is None:
        source = source.set_crs(TARGET_CRS)
    source = source.to_crs(TARGET_CRS)
    source = source[source.geometry.notna() & ~source.geometry.is_empty].copy()
    invalid = ~source.geometry.is_valid
    if bool(invalid.any()):
        source.loc[invalid, "geometry"] = source.loc[invalid, "geometry"].make_valid()
    clipped = gpd.clip(source, study_area.geometry.union_all())
    return clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty].copy()


def _normalize_fires(fires: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if fires.empty:
        return fires
    output = fires.copy()
    output["source"] = "Generalitat de Catalunya VEGETACIO WFS"
    output["source_layer"] = GENCAT_LAYER
    output["area_ha"] = output.geometry.area / 10000
    output["fire_year"] = output.apply(_fire_year, axis=1)
    output["fire_date"] = output.apply(_fire_date, axis=1)
    return output


def _fire_year(row: Any) -> str:
    for key in ("any_foc", "ANY", "ANY_FOC", "DATES_FOC"):
        value = row.get(key)
        if value not in (None, ""):
            text = str(value)
            for token in text.replace("/", "-").split("-"):
                if token.isdigit() and len(token) == 4:
                    return token
            if text.isdigit() and len(text) == 4:
                return text
    return ""


def _fire_date(row: Any) -> str:
    for key in ("DATES_FOC", "DATA", "fire_date"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _read_effis_catalog() -> list[dict[str, Any]]:
    if not RAW_EFFIS_CATALOG_PATH.exists():
        return []
    payload = json.loads(RAW_EFFIS_CATALOG_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("datasets", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _write_summary(fires: gpd.GeoDataFrame, effis_catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {"metric": "gencat_fire_polygons", "value": int(len(fires)), "unit": "features"},
        {"metric": "gencat_burned_area_ha", "value": round(float(fires.geometry.area.sum() / 10000), 4) if not fires.empty else 0, "unit": "ha"},
        {"metric": "gencat_fire_years", "value": ", ".join(sorted({str(value) for value in fires.get("fire_year", []) if str(value)})), "unit": "years"},
        {"metric": "effis_catalog_datasets", "value": len(effis_catalog), "unit": "datasets"},
        {"metric": "effis_local_geometry_downloaded", "value": 0, "unit": "boolean"},
    ]
    with SUMMARY_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value", "unit"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _write_metadata(
    study_area: gpd.GeoDataFrame,
    fires: gpd.GeoDataFrame,
    effis_catalog: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    metadata = {
        "project": "Alinya",
        "source": "Superfícies afectades per incendis forestals v1.1",
        "responsible_organization": "Generalitat de Catalunya / Departament competent en medi natural / ICGC / Cos d'Agents Rurals",
        "service_url": GENCAT_WFS_URL,
        "layer": GENCAT_LAYER,
        "service_type": "WFS 2.0.0",
        "query_date": datetime.now(timezone.utc).isoformat(),
        "crs": TARGET_CRS,
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
        "raw_file": str(RAW_GENCAT_PATH),
        "processed_file": str(PROCESSED_PATH),
        "summary_file": str(SUMMARY_PATH),
        "features_clipped": int(len(fires)),
        "burned_area_ha": round(float(fires.geometry.area.sum() / 10000), 4) if not fires.empty else 0,
        "fire_years": sorted({str(value) for value in fires.get("fire_year", []) if str(value)}),
        "effis": {
            "status": "catalogue_only",
            "url": EFFIS_DRF_DATASETS_API,
            "raw_file": str(RAW_EFFIS_CATALOG_PATH),
            "dataset_count": len(effis_catalog),
            "local_geometry_downloaded": False,
        },
        "summary": summary_rows,
        "limitations": [
            "Gencat burned-area polygons describe historical perimeters, not current operational fire risk.",
            "EFFIS is included as a verified public catalogue only; no local EFFIS product geometry is used until product-specific request workflow, CRS, licence and schema are documented.",
            "IncendisCat is not used as an EcoRadar data source.",
            "The connector does not calculate fire probability or resilience indicators.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


def _write_validation(metadata: dict[str, Any]) -> dict[str, Any]:
    status = "completed" if metadata["features_clipped"] > 0 and RAW_EFFIS_CATALOG_PATH.exists() else "partial"
    validation = {
        "connector": "connector_incendis_historial",
        "project": "Alinya",
        "validated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "can_advance_to_next_connector": status in {"completed", "partial"},
        "source": metadata["source"],
        "outputs": {
            "processed": str(PROCESSED_PATH),
            "summary": str(SUMMARY_PATH),
            "metadata": str(METADATA_PATH),
            "effis_catalog": str(RAW_EFFIS_CATALOG_PATH),
        },
        "checks": {
            "processed_exists": PROCESSED_PATH.exists(),
            "summary_exists": SUMMARY_PATH.exists(),
            "metadata_exists": METADATA_PATH.exists(),
            "has_gencat_fire_polygons": metadata["features_clipped"] > 0,
            "has_effis_catalogue": RAW_EFFIS_CATALOG_PATH.exists(),
            "effis_local_geometry_downloaded": False,
            "incendiscat_not_used": True,
        },
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return validation


if __name__ == "__main__":
    main()
