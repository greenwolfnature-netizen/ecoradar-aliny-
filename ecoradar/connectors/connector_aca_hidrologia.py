"""ACA / Gencat water connector for EcoRadar.

Downloads official water-related WFS layers from `sig.gencat.cat/ows/AIGUA`,
clips them to the Alinya study area and stores normalized layers in a single
GeoPackage. This connector creates source summaries and validation metadata
only; it does not calculate EcoRadar indicators.
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
import pandas as pd


PROJECT_ROOT = Path("projectes/Alinya")
STUDY_AREA_PATH = PROJECT_ROOT / "processed" / "study_area.gpkg"
RAW_DIR = PROJECT_ROOT / "raw" / "hidrologia"
PROCESSED_PATH = PROJECT_ROOT / "processed" / "hidrologia.gpkg"
SUMMARY_PATH = PROJECT_ROOT / "indicators" / "hidrologia_resum.csv"
METADATA_PATH = PROJECT_ROOT / "metadata" / "hidrologia_metadata.json"
VALIDATION_PATH = PROJECT_ROOT / "metadata" / "validations" / "connector_aca_hidrologia_validation.json"

TARGET_CRS = "EPSG:25831"
WFS_URL = "https://sig.gencat.cat/ows/AIGUA/wfs"
SOURCE_PAGE = "https://aca.gencat.cat/"

LAYERS = [
    {
        "id": "rius_aca_che",
        "type_name": "AIGUA:AIGUA_RIUS_ACA_CHE",
        "theme": "courses",
        "description": "Rius ACA/CHE",
    },
    {
        "id": "eixos_drenatge",
        "type_name": "AIGUA:AIGUA_EIXOS_DRENATGE_ASDT",
        "theme": "drainage_axes",
        "description": "Eixos de drenatge ASDT",
    },
    {
        "id": "fonts",
        "type_name": "AIGUA:AIGUA_FONTS",
        "theme": "springs",
        "description": "Fonts",
    },
    {
        "id": "masses_rius",
        "type_name": "AIGUA:AIGUA_CONQUES_MASSES_RIUS",
        "theme": "river_water_bodies",
        "description": "Conques i masses de rius",
    },
    {
        "id": "preses_basses",
        "type_name": "AIGUA:AIGUA_PRESES_BASSES",
        "theme": "ponds_reservoirs",
        "description": "Preses i basses",
    },
    {
        "id": "estanys",
        "type_name": "AIGUA:AIGUA_MA_ESTANYS",
        "theme": "lakes",
        "description": "Masses d'aigua estanys",
    },
    {
        "id": "zones_humides_estanys",
        "type_name": "AIGUA:AIGUA_PDG_ZH_ESTANYS_CIC_222",
        "theme": "wetlands_lakes",
        "description": "Zones humides i estanys del pla de gestió",
    },
]


def main() -> None:
    result = run_connector()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_connector(*, refresh: bool = False) -> dict[str, Any]:
    _ensure_dirs()
    study_area = _load_study_area()
    summaries: list[dict[str, Any]] = []
    processed_layers: dict[str, str] = {}

    if PROCESSED_PATH.exists():
        PROCESSED_PATH.unlink()

    for layer in LAYERS:
        raw_path = _raw_path(layer["id"])
        if refresh or not raw_path.exists():
            _download_layer(layer, study_area, raw_path)
        gdf = _read_layer(raw_path, study_area)
        clipped = _clip_layer(gdf, study_area)
        normalized = _normalize_layer(clipped, layer)
        if not normalized.empty:
            normalized.to_file(PROCESSED_PATH, layer=layer["id"], driver="GPKG")
            processed_layers[layer["id"]] = str(PROCESSED_PATH)
        summaries.append(_layer_summary(layer, normalized, raw_path))

    _write_summary(summaries)
    metadata = _write_metadata(study_area, summaries, processed_layers)
    validation = _write_validation(metadata)
    return {
        "status": validation["status"],
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "metadata_path": str(METADATA_PATH),
        "validation_path": str(VALIDATION_PATH),
        "layers": summaries,
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


def _raw_path(layer_id: str) -> Path:
    return RAW_DIR / f"{layer_id}.geojson"


def _download_layer(layer: dict[str, str], study_area: gpd.GeoDataFrame, output_path: Path) -> None:
    xmin, ymin, xmax, ymax = [float(value) for value in study_area.total_bounds]
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer["type_name"],
        "outputFormat": "application/json",
        "srsName": TARGET_CRS,
        "BBOX": f"{xmin},{ymin},{xmax},{ymax},{TARGET_CRS}",
    }
    url = f"{WFS_URL}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json,*/*",
            "User-Agent": "EcoRadar/0.1 ACA hydrology connector",
        },
    )
    with urlopen(request, timeout=120) as response:
        payload = response.read()
    if payload.lstrip().startswith(b"<"):
        raise RuntimeError(payload[:1000].decode("utf-8", "ignore"))
    output_path.write_bytes(payload)


def _read_layer(path: Path, study_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
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
    return gdf.to_crs(study_area.crs)


def _clip_layer(gdf: gpd.GeoDataFrame, study_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    invalid = ~gdf.geometry.is_valid
    if bool(invalid.any()):
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].make_valid()
    clipped = gpd.clip(gdf, study_area.geometry.union_all())
    return clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty].copy()


def _normalize_layer(gdf: gpd.GeoDataFrame, layer: dict[str, str]) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=TARGET_CRS)
    output = gdf.copy()
    output["ecoradar_layer"] = layer["id"]
    output["ecoradar_theme"] = layer["theme"]
    output["ecoradar_source"] = layer["type_name"]
    output["source_url"] = WFS_URL
    output["feature_area_ha"] = output.geometry.area / 10000
    output["feature_length_km"] = output.geometry.length / 1000
    return output


def _layer_summary(layer: dict[str, str], gdf: gpd.GeoDataFrame, raw_path: Path) -> dict[str, Any]:
    if gdf.empty:
        geometry_types: list[str] = []
        count = 0
        length_km = 0.0
        area_ha = 0.0
    else:
        geometry_types = sorted({str(value) for value in gdf.geometry.geom_type.unique()})
        count = int(len(gdf))
        length_km = float(gdf.geometry.length.sum() / 1000)
        area_ha = float(gdf.geometry.area.sum() / 10000)
    return {
        "layer_id": layer["id"],
        "type_name": layer["type_name"],
        "theme": layer["theme"],
        "description": layer["description"],
        "raw_path": str(raw_path),
        "feature_count": count,
        "geometry_types": geometry_types,
        "length_km": round(length_km, 4),
        "area_ha": round(area_ha, 4),
    }


def _write_summary(rows: list[dict[str, Any]]) -> None:
    with SUMMARY_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "layer_id",
                "type_name",
                "theme",
                "description",
                "feature_count",
                "geometry_types",
                "length_km",
                "area_ha",
                "raw_path",
            ],
        )
        writer.writeheader()
        for row in rows:
            serialized = row.copy()
            serialized["geometry_types"] = ";".join(row["geometry_types"])
            writer.writerow(serialized)


def _write_metadata(
    study_area: gpd.GeoDataFrame,
    summaries: list[dict[str, Any]],
    processed_layers: dict[str, str],
) -> dict[str, Any]:
    metadata = {
        "project": "Alinya",
        "source": "ACA / Gencat AIGUA WFS",
        "responsible_organization": "Agència Catalana de l'Aigua / Generalitat de Catalunya",
        "url": SOURCE_PAGE,
        "service_url": WFS_URL,
        "service_type": "WFS 2.0.0",
        "query_date": datetime.now(timezone.utc).isoformat(),
        "crs": TARGET_CRS,
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
        "layers": summaries,
        "processed_path": str(PROCESSED_PATH),
        "processed_layers": processed_layers,
        "summary_path": str(SUMMARY_PATH),
        "limitations": [
            "Some official WFS layers can legitimately return zero features inside the study area.",
            "The connector stores source geometry and simple length/area summaries only; it does not classify ecological water functionality.",
            "Springs, ponds and wetlands require field validation before management decisions.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


def _write_validation(metadata: dict[str, Any]) -> dict[str, Any]:
    total_features = sum(int(row["feature_count"]) for row in metadata["layers"])
    required_layers_with_data = [
        row["layer_id"]
        for row in metadata["layers"]
        if row["layer_id"] in {"rius_aca_che", "eixos_drenatge", "fonts", "masses_rius"} and row["feature_count"] > 0
    ]
    status = "completed" if total_features > 0 and len(required_layers_with_data) >= 2 else "partial"
    validation = {
        "connector": "connector_aca_hidrologia",
        "project": "Alinya",
        "validated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "can_advance_to_next_connector": status in {"completed", "partial"},
        "source": metadata["source"],
        "service_url": WFS_URL,
        "total_features": total_features,
        "required_layers_with_data": required_layers_with_data,
        "outputs": {
            "processed": str(PROCESSED_PATH),
            "summary": str(SUMMARY_PATH),
            "metadata": str(METADATA_PATH),
        },
        "checks": {
            "processed_exists": PROCESSED_PATH.exists(),
            "summary_exists": SUMMARY_PATH.exists(),
            "metadata_exists": METADATA_PATH.exists(),
            "has_any_water_features": total_features > 0,
            "has_courses_or_drainage": any(layer in required_layers_with_data for layer in ["rius_aca_che", "eixos_drenatge"]),
            "has_springs": "fonts" in required_layers_with_data,
        },
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return validation


if __name__ == "__main__":
    main()
