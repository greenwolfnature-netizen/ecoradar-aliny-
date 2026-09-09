"""Official terrestrial habitats connector for EcoRadar.

This connector uses the Generalitat de Catalunya Hipermapa WFS polygon and
point layers. Point habitats are preserved for traceability but do not enter
the polygon-area summary or any existing EcoRadar score.
"""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd


PROJECT_ROOT = Path("projectes/Alinya")
STUDY_AREA_PATH = PROJECT_ROOT / "processed" / "study_area.gpkg"
RAW_DIR = PROJECT_ROOT / "raw" / "habitats"
RAW_GEOJSON_PATH = RAW_DIR / "habitats_terrestres_v3_alinya_bbox.geojson"
RAW_POINTS_PATH = RAW_DIR / "habitats_terrestres_v3_punts_alinya_bbox.geojson"
PROCESSED_PATH = PROJECT_ROOT / "processed" / "habitats.gpkg"
SUMMARY_PATH = PROJECT_ROOT / "indicators" / "habitats_resum.csv"
METADATA_PATH = PROJECT_ROOT / "metadata" / "habitats_metadata.json"

SOURCE_ID = "biodiversity_habitats_terrestres_v3"
SOURCE_NAME = "Cartografia dels habitats terrestres, versio 3 (2019/2024)"
SOURCE_PAGE_URL = (
    "https://mediambient.gencat.cat/ca/05_ambits_dactuacio/patrimoni_natural/"
    "sistemes_dinformacio/habitats/habitats_terrestres/mapa-dels-habitats-terrestres/"
    "cartografia-dels-habitats-versio-3-2025/"
)
WFS_URL = "https://sig.gencat.cat/ows/wfs"
LAYER_NAME = "HABITATS_TERRESTPOL"
POINT_LAYER_NAME = "HABITATS:HABITATS_TERRESTPNT"
TARGET_CRS = "EPSG:25831"

KEEP_COLUMNS = [
    "id",
    "ID",
    "COD_GRUP",
    "GRUP_CA",
    "COD_TIPUS",
    "TIPUS_CA",
    "COD_SUBTIP",
    "SUBTIP_CA",
    "COD_CORINE",
    "CORINE_CA",
    "COD_HIC",
    "HIC_CA",
    "HIC_PRIOR",
    "COD_EUNIS",
    "EUNIS_EN",
    "COD_LPEHT",
    "LPEHT_ES",
    "AMENACA",
    "VGI",
    "AREA_M2",
    "PERCEN_POL",
    "geometry",
]


def main() -> None:
    result = run_connector()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_connector() -> dict[str, object]:
    _ensure_dirs()
    study_area = _load_study_area()
    raw_path = _download_source_if_needed(study_area)
    raw_points_path = _download_layer_if_needed(study_area, POINT_LAYER_NAME, RAW_POINTS_PATH)
    source = gpd.read_file(raw_path).to_crs(TARGET_CRS)
    clipped = _clip_to_study_area(source, study_area)
    point_source = gpd.read_file(raw_points_path).to_crs(TARGET_CRS)
    clipped_points = _clip_to_study_area(point_source, study_area)
    clipped_points = _unique_field_names(clipped_points)

    if clipped.empty:
        raise RuntimeError("No terrestrial habitat polygons were found inside the study area")

    clipped = _normalize_output_columns(clipped)
    if PROCESSED_PATH.exists():
        PROCESSED_PATH.unlink()
    clipped.to_file(PROCESSED_PATH, layer="habitats", driver="GPKG")
    if not clipped_points.empty:
        clipped_points.to_file(PROCESSED_PATH, layer="habitats_punts", driver="GPKG", mode="a")

    study_area_ha = float(study_area.geometry.union_all().area / 10000)
    summary_rows = _write_summary(clipped, study_area_ha)
    metadata = _write_metadata(study_area, source, clipped, raw_path, point_source, clipped_points, raw_points_path)

    return {
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "metadata_path": str(METADATA_PATH),
        "raw_path": str(raw_path),
        "features_downloaded": int(len(source)),
        "features_clipped": int(len(clipped)),
        "point_features_downloaded": int(len(point_source)),
        "point_features_clipped": int(len(clipped_points)),
        "habitats": len(summary_rows),
        "surface_ha": float(clipped.geometry.area.sum() / 10000),
        "metadata": metadata,
    }


def _unique_field_names(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop case-insensitive duplicate fields rejected by GeoPackage/SQLite."""
    keep: list[str] = []
    seen: set[str] = set()
    for column in frame.columns:
        key = str(column).casefold()
        if key in seen and column != frame.geometry.name:
            continue
        keep.append(column)
        seen.add(key)
    return frame.loc[:, keep].copy()


def _ensure_dirs() -> None:
    for directory in (RAW_DIR, PROCESSED_PATH.parent, SUMMARY_PATH.parent, METADATA_PATH.parent):
        directory.mkdir(parents=True, exist_ok=True)


def _load_study_area() -> gpd.GeoDataFrame:
    if not STUDY_AREA_PATH.exists():
        raise FileNotFoundError(f"Study area not found: {STUDY_AREA_PATH}")
    study_area = gpd.read_file(STUDY_AREA_PATH).to_crs(TARGET_CRS)
    if study_area.empty:
        raise ValueError("Study area is empty")
    invalid = ~study_area.geometry.is_valid
    if bool(invalid.any()):
        raise ValueError("Study area has invalid geometries; repair it before running connector")
    return study_area


def _download_source_if_needed(study_area: gpd.GeoDataFrame) -> Path:
    return _download_layer_if_needed(study_area, LAYER_NAME, RAW_GEOJSON_PATH)


def _download_layer_if_needed(study_area: gpd.GeoDataFrame, layer_name: str, destination: Path) -> Path:
    if destination.exists() and destination.stat().st_size > 0:
        return destination

    xmin, ymin, xmax, ymax = [float(value) for value in study_area.total_bounds]
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer_name,
        "outputFormat": "application/json",
        "srsName": TARGET_CRS,
        "BBOX": f"{xmin},{ymin},{xmax},{ymax},{TARGET_CRS}",
    }
    url = f"{WFS_URL}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json, */*",
            "User-Agent": "EcoRadar/0.1 (+https://sig.gencat.cat)",
        },
    )
    with urlopen(request, timeout=180) as response:
        payload = response.read()
    if payload.lstrip().startswith(b"<"):
        raise RuntimeError(payload[:1000].decode("utf-8", "ignore"))
    destination.write_bytes(payload)
    return destination


def _clip_to_study_area(source: gpd.GeoDataFrame, study_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    source = source[source.geometry.notna() & ~source.geometry.is_empty].copy()
    invalid = ~source.geometry.is_valid
    if bool(invalid.any()):
        source.loc[invalid, "geometry"] = source.loc[invalid, "geometry"].make_valid()
    clipped = gpd.clip(source, study_area.geometry.union_all())
    clipped = clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty].copy()
    return clipped


def _normalize_output_columns(clipped: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    for column in KEEP_COLUMNS:
        if column not in clipped.columns and column != "geometry":
            clipped[column] = None
    output = clipped[[column for column in KEEP_COLUMNS if column in clipped.columns]].copy()
    output = output.rename(columns={"id": "source_feature_id", "ID": "source_numeric_id"})
    output["superficie_ha"] = output.geometry.area / 10000
    output["es_hic"] = output["COD_HIC"].map(_is_hic)
    output["es_prioritari"] = output["HIC_PRIOR"].map(_is_priority)
    return output


def _write_summary(clipped: gpd.GeoDataFrame, study_area_ha: float) -> list[dict[str, object]]:
    grouped = (
        clipped.assign(superficie_ha=clipped.geometry.area / 10000)
        .groupby(["COD_CORINE", "CORINE_CA", "es_hic", "es_prioritari"], dropna=False)["superficie_ha"]
        .sum()
        .reset_index()
        .sort_values(["superficie_ha", "COD_CORINE"], ascending=[False, True])
    )

    rows: list[dict[str, object]] = []
    for _, row in grouped.iterrows():
        surface = float(row["superficie_ha"])
        rows.append(
            {
                "codi_habitat": _clean_text(row["COD_CORINE"]),
                "nom_habitat": _clean_text(row["CORINE_CA"]),
                "superficie_ha": round(surface, 4),
                "percentatge_total": round((surface / study_area_ha) * 100, 4) if study_area_ha else 0,
                "es_hic": bool(row["es_hic"]),
                "es_prioritari": bool(row["es_prioritari"]),
            }
        )

    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "codi_habitat",
                "nom_habitat",
                "superficie_ha",
                "percentatge_total",
                "es_hic",
                "es_prioritari",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _write_metadata(
    study_area: gpd.GeoDataFrame,
    source: gpd.GeoDataFrame,
    clipped: gpd.GeoDataFrame,
    raw_path: Path,
    point_source: gpd.GeoDataFrame,
    clipped_points: gpd.GeoDataFrame,
    raw_points_path: Path,
) -> dict[str, object]:
    metadata = {
        "project": "Alinya",
        "source_id": SOURCE_ID,
        "source": SOURCE_NAME,
        "url": SOURCE_PAGE_URL,
        "service_url": WFS_URL,
        "layer": LAYER_NAME,
        "point_layer": POINT_LAYER_NAME,
        "query_date": datetime.now(timezone.utc).isoformat(),
        "crs": str(clipped.crs),
        "original_crs": str(source.crs),
        "scale_or_resolution": "Version 3 terrestrial habitat polygons; minimum polygon threshold 15000 m2 according to the official page.",
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
        "clipped_surface_ha": float(clipped.geometry.area.sum() / 10000),
        "features_downloaded": int(len(source)),
        "features_clipped": int(len(clipped)),
        "point_features_downloaded": int(len(point_source)),
        "point_features_clipped": int(len(clipped_points)),
        "raw_file": str(raw_path),
        "raw_points_file": str(raw_points_path),
        "processed_file": str(PROCESSED_PATH),
        "processed_layers": ["habitats"] + (["habitats_punts"] if not clipped_points.empty else []),
        "summary_file": str(SUMMARY_PATH),
        "limitations": [
            "The official page states that each polygon habitat is present in at least 75 percent of the polygon.",
            "Habitats smaller than 15000 m2 may be represented as points. They are retained in habitats_punts for traceability and do not enter polygon-area summaries or current RADAR formulas.",
            "The WFS BBOX response may return multipart habitat features beyond the study-area envelope; final outputs are clipped locally to the study-area geometry.",
            "Areas are calculated after clipping in EPSG:25831 and may differ from official AREA_M2 source attributes.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def _is_hic(value: object) -> bool:
    text = _clean_text(value)
    return bool(text and text != "-")


def _is_priority(value: object) -> bool:
    return _clean_text(value).lower() in {"si", "sí", "yes", "true", "1"}


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"connector_habitats failed: {exc}", file=sys.stderr)
        raise
