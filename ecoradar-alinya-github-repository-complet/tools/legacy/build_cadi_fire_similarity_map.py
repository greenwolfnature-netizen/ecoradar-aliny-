"""Build a fire-condition similarity map for the Cadi massif working area.

This is not a fire-probability model and it is not an EcoRadar connector. It
creates a traceable project artifact from official/verified sources already
documented in the Data Engine inventory.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from affine import Affine
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Point, Polygon, box


PROJECT = Path("projectes/Cadi")
OUT_RAW_BOUNDARY = PROJECT / "raw/study_area"
OUT_RAW_FIRES = PROJECT / "raw/incendis"
OUT_RAW_HABITATS = PROJECT / "raw/habitats"
OUT_RAW_ACCESS = PROJECT / "raw/recreational_pressure"
OUT_RAW_TERRAIN = PROJECT / "raw/terrain"
OUT_RAW_BOMBERS = PROJECT / "raw/bombers"
OUT_RAW_COPERNICUS = PROJECT / "raw/copernicus"
OUT_PROC = PROJECT / "processed"
OUT_PROC_FIRES = OUT_PROC / "incendis"
OUT_PROC_SIM = OUT_PROC / "incendis_similarity"
OUT_MAPS = PROJECT / "maps/incendis_similarity"
OUT_META = PROJECT / "metadata/incendis_similarity"
OUT_IND = PROJECT / "indicators/incendis_similarity"

TODAY = "2026-07-07"
TARGET_CRS = "EPSG:25831"
WGS84 = "EPSG:4326"
LOCAL_TZ = ZoneInfo("Europe/Madrid")

ESPAIS_WFS = "https://sig.gencat.cat/ows/ESPAIS_NATURALS/wfs"
PARCS_LAYER = "ESPAIS_NATURALS:ESPAISNATURALS_PARCSNATURALS"
FIRES_WFS = "https://sig.gencat.cat/ows/VEGETACIO/wfs"
FIRES_LAYER = "VEGETACIO:VEGETACIO_INCENDIS"
HABITATS_WFS = "https://sig.gencat.cat/ows/wfs"
HABITATS_LAYER = "HABITATS_TERRESTPOL"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
BOMBERS_API = "https://analisi.transparenciacatalunya.cat/resource/g2ay-3vnj.json"
BOMBERS_ARCGIS_EXPERIENCE_URL = "https://experience.arcgis.com/experience/f6172fd2d6974bc0a8c51e3a6bc2a735"
BOMBERS_ARCGIS_ITEM_API = "https://www.arcgis.com/sharing/rest/content/items/f6172fd2d6974bc0a8c51e3a6bc2a735"
BOMBERS_ARCGIS_EXPERIENCE_CONFIG_API = f"{BOMBERS_ARCGIS_ITEM_API}/data"
BOMBERS_ARCGIS_LAYER_URL = (
    "https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services/"
    "ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW/FeatureServer/0"
)
EFFIS_DRF_DATASETS_API = "https://api.effis.emergency.copernicus.eu/rest/drf/datasets/"
DEM_URL = (
    "https://datacloud.icgc.cat/datacloud/model-elevacions-terreny/tif_unzip/"
    "model-elevacions-terreny-topografic-catalunya-5m-2009-2018.tif"
)

CELL_SIZE_M = 300.0
DEM_TARGET_RES_M = 20.0
MIN_FIRE_AREA_M2 = 1000.0
FIRE_CONTEXT_BUFFER_M = 5000.0


def ensure_dirs() -> None:
    for path in [
        OUT_RAW_BOUNDARY,
        OUT_RAW_FIRES,
        OUT_RAW_HABITATS,
        OUT_RAW_ACCESS,
        OUT_RAW_TERRAIN,
        OUT_RAW_BOMBERS,
        OUT_RAW_COPERNICUS,
        OUT_PROC,
        OUT_PROC_FIRES,
        OUT_PROC_SIM,
        OUT_MAPS,
        OUT_META,
        OUT_IND,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def fetch_bytes(url: str, *, method: str = "GET", data: bytes | None = None, timeout: int = 240) -> bytes:
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/json, image/tiff, */*",
            "Content-Type": "application/x-www-form-urlencoded" if data is not None else "text/plain",
            "User-Agent": "EcoRadar/0.1 source-traceability-map",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()
    if payload.lstrip().startswith(b"<") and b"ExceptionReport" in payload[:2000]:
        raise RuntimeError(payload[:2000].decode("utf-8", "replace"))
    return payload


def fetch_json_with_cache(url: str, path: Path, *, timeout: int = 90) -> dict[str, object]:
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8"))
    data = json.loads(fetch_bytes(url, timeout=timeout).decode("utf-8"))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def epoch_ms_to_iso_local(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        milliseconds = int(float(value))
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).astimezone(LOCAL_TZ).replace(microsecond=0).isoformat()


def load_bombers_context() -> dict[str, object]:
    """Fetch official Bombers tabular context for the Cadí-Moixeró counties.

    The dataset has no coordinates or perimeters, so these records are never
    used as mapped fire geometry or as similarity predictors.
    """

    raw_path = OUT_RAW_BOMBERS / "bombers_incendis_vegetacio_cadi_comarques_2019_2026.json"
    summary_path = OUT_IND / "bombers_incendis_vegetacio_context.csv"
    comarques = ["Alt Urgell", "Berguedà", "Cerdanya"]
    if raw_path.exists() and raw_path.stat().st_size > 0:
        records = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        params = {
            "$limit": "5000",
            "$select": "nom_comarca, any, tal_nom_alarma, count(*) as n",
            "$where": "tga_nom_grupo='incendi vegetació' AND nom_comarca in('Alt Urgell','Berguedà','Cerdanya') AND any >= 2019",
            "$group": "nom_comarca, any, tal_nom_alarma",
            "$order": "any DESC, nom_comarca, n DESC",
        }
        url = f"{BOMBERS_API}?{urlencode(params)}"
        records = json.loads(fetch_bytes(url, timeout=90).decode("utf-8"))
        raw_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    df = pd.DataFrame(records)
    if df.empty:
        summary = pd.DataFrame(columns=["nom_comarca", "any", "tal_nom_alarma", "n"])
        total_actions = 0
        latest_year = None
        totals_by_comarca: dict[str, int] = {}
        totals_by_year: dict[str, int] = {}
    else:
        df["n"] = df["n"].astype(int)
        summary = df.sort_values(["any", "nom_comarca", "tal_nom_alarma"], ascending=[False, True, True])
        total_actions = int(df["n"].sum())
        latest_year = str(df["any"].astype(int).max())
        totals_by_comarca = {str(k): int(v) for k, v in df.groupby("nom_comarca")["n"].sum().sort_index().to_dict().items()}
        totals_by_year = {str(k): int(v) for k, v in df.groupby("any")["n"].sum().sort_index(ascending=False).to_dict().items()}
    summary.to_csv(summary_path, index=False)

    return {
        "status": "blocked",
        "source_use": "official_tabular_context_no_geometry",
        "source": "Actuacions dels Bombers de la Generalitat",
        "api": BOMBERS_API,
        "raw_path": str(raw_path),
        "summary_path": str(summary_path),
        "comarques": comarques,
        "period": "2019-2026",
        "rows": int(len(records)),
        "total_vegetation_fire_actions": total_actions,
        "latest_year": latest_year,
        "totals_by_comarca": totals_by_comarca,
        "totals_by_year": totals_by_year,
        "limitations": [
            "The dataset is official and public but tabular; it does not expose incident coordinates or burned perimeters.",
            "Counts are by county and alarm type, so they are context only and are not used as mapped fire locations.",
        ],
    }


def load_bombers_arcgis_viewer_context(study: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict[str, object]]:
    """Fetch public operational IV points from the official Bombers ArcGIS viewer.

    This is source-traceability context only. The layer exposes current point
    incidents, not historical burned perimeters, and is never used in the
    environmental similarity score.
    """

    item_path = OUT_RAW_BOMBERS / "bombers_arcgis_experience_item.json"
    config_path = OUT_RAW_BOMBERS / "bombers_arcgis_experience_config.json"
    layer_path = OUT_RAW_BOMBERS / "bombers_arcgis_visor_iv_layer_metadata.json"
    raw_query_path = OUT_RAW_BOMBERS / f"bombers_arcgis_visor_iv_cadi_context_{TODAY}.json"
    processed_path = OUT_PROC_SIM / "bombers_arcgis_visor_iv_context.gpkg"
    summary_path = OUT_IND / "bombers_arcgis_visor_context.csv"

    item = fetch_json_with_cache(f"{BOMBERS_ARCGIS_ITEM_API}?f=json", item_path)
    fetch_json_with_cache(f"{BOMBERS_ARCGIS_EXPERIENCE_CONFIG_API}?f=json", config_path)
    layer = fetch_json_with_cache(f"{BOMBERS_ARCGIS_LAYER_URL}?f=pjson", layer_path)

    study_geom = study.geometry.union_all()
    context_geom = study_geom.buffer(FIRE_CONTEXT_BUFFER_M)
    xmin, ymin, xmax, ymax = [float(v) for v in context_geom.bounds]
    fields = [
        "ACT_NUM_ACTUACIO",
        "ACT_DAT_ACTUACIO",
        "TAL_COD_ALARMA1",
        "TAL_DESC_ALARMA1",
        "TAL_COD_ALARMA2",
        "TAL_DESC_ALARMA2",
        "ACT_SITUACIO",
        "ACT_DAT_ACTUAL",
        "ACT_DAT_INICI",
        "ACT_DAT_FI",
        "ACT_URGENT",
        "MUNICIPI_DPX",
        "MUNICIPI_SIG",
        "DATA_ACT",
        "ACT_NUM_VEH",
        "COM_FASE",
        "OBJECTID",
    ]
    params = {
        "f": "json",
        "where": "1=1",
        "outFields": ",".join(fields),
        "returnGeometry": "true",
        "geometry": f"{xmin:.0f},{ymin:.0f},{xmax:.0f},{ymax:.0f}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "25831",
        "outSR": "25831",
        "spatialRel": "esriSpatialRelIntersects",
    }
    query_url = f"{BOMBERS_ARCGIS_LAYER_URL}/query?{urlencode(params)}"
    raw = json.loads(fetch_bytes(query_url, timeout=90).decode("utf-8"))
    raw["_ecoradar"] = {
        "queried_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "query_url": query_url,
        "source_use": "operational_viewer_context_only",
    }
    raw_query_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    records: list[dict[str, object]] = []
    for feature in raw.get("features", []):
        attrs = feature.get("attributes") or {}
        geom = feature.get("geometry") or {}
        x, y = geom.get("x"), geom.get("y")
        if x is None or y is None:
            continue
        record = {field: attrs.get(field) for field in fields}
        record["x_25831"] = float(x)
        record["y_25831"] = float(y)
        record["geometry"] = Point(float(x), float(y))
        records.append(record)

    if records:
        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=TARGET_CRS)
        gdf["inside_context_5km"] = gdf.geometry.intersects(context_geom)
        gdf = gdf[gdf["inside_context_5km"]].copy()
    else:
        gdf = gpd.GeoDataFrame({field: [] for field in fields}, geometry=[], crs=TARGET_CRS)

    if gdf.empty:
        for col in [
            "inside_strict_area",
            "distance_to_study_m",
            "ACT_DAT_ACTUACIO_iso_local",
            "ACT_DAT_ACTUAL_iso_local",
            "ACT_DAT_INICI_iso_local",
            "ACT_DAT_FI_iso_local",
            "DATA_ACT_iso_local",
        ]:
            gdf[col] = []
    else:
        gdf["inside_strict_area"] = gdf.geometry.intersects(study_geom)
        gdf["distance_to_study_m"] = gdf.geometry.distance(study_geom)
        for date_col in ["ACT_DAT_ACTUACIO", "ACT_DAT_ACTUAL", "ACT_DAT_INICI", "ACT_DAT_FI", "DATA_ACT"]:
            gdf[f"{date_col}_iso_local"] = gdf[date_col].map(epoch_ms_to_iso_local)

    if processed_path.exists():
        processed_path.unlink()
    if not gdf.empty:
        gdf.to_file(processed_path, layer="bombers_visor_iv_context", driver="GPKG")

    summary_columns = [
        "ACT_NUM_ACTUACIO",
        "TAL_DESC_ALARMA2",
        "COM_FASE",
        "MUNICIPI_DPX",
        "MUNICIPI_SIG",
        "ACT_NUM_VEH",
        "ACT_DAT_ACTUACIO_iso_local",
        "DATA_ACT_iso_local",
        "inside_strict_area",
        "distance_to_study_m",
        "x_25831",
        "y_25831",
    ]
    for col in summary_columns:
        if col not in gdf.columns:
            gdf[col] = []
    gdf.drop(columns="geometry").reindex(columns=summary_columns).to_csv(summary_path, index=False)

    def counts(column: str) -> dict[str, int]:
        if gdf.empty or column not in gdf.columns:
            return {}
        return {
            str(k if pd.notna(k) and k != "" else "sense_dada"): int(v)
            for k, v in gdf[column].value_counts(dropna=False).sort_index().to_dict().items()
        }

    features_summary = []
    for _, row in gdf.iterrows():
        features_summary.append(
            {
                "actuacio": str(row.get("ACT_NUM_ACTUACIO", "")),
                "municipi": str(row.get("MUNICIPI_DPX", row.get("MUNICIPI_SIG", ""))),
                "alarm_type": str(row.get("TAL_DESC_ALARMA2", "")),
                "phase": str(row.get("COM_FASE", "")),
                "vehicles": None if pd.isna(row.get("ACT_NUM_VEH", np.nan)) else int(row.get("ACT_NUM_VEH")),
                "actuacio_date_local": row.get("ACT_DAT_ACTUACIO_iso_local"),
                "data_actualitzacio_local": row.get("DATA_ACT_iso_local"),
                "inside_strict_area": bool(row.get("inside_strict_area", False)),
                "distance_to_study_m": float(row.get("distance_to_study_m", 0.0)),
                "x_25831": float(row.geometry.x),
                "y_25831": float(row.geometry.y),
            }
        )

    layer_fields = [str(field.get("name", "")) for field in layer.get("fields", [])]
    context = {
        "status": "pending_verification",
        "source_use": "official_operational_viewer_context_only",
        "source": str(item.get("title", "Bombers - Visor d'actuacions incendis PRO")),
        "owner": str(item.get("owner", "AdminInterior")),
        "experience_url": BOMBERS_ARCGIS_EXPERIENCE_URL,
        "feature_layer_url": BOMBERS_ARCGIS_LAYER_URL,
        "raw_item_path": str(item_path),
        "raw_experience_config_path": str(config_path),
        "raw_layer_metadata_path": str(layer_path),
        "raw_query_path": str(raw_query_path),
        "processed_path": str(processed_path) if not gdf.empty else None,
        "summary_path": str(summary_path),
        "geometry_type": str(layer.get("geometryType", "esriGeometryPoint")),
        "crs": TARGET_CRS,
        "server_definition_query": str(layer.get("viewDefinitionQuery") or layer.get("definitionQuery") or ""),
        "cache_max_age_seconds": layer.get("cacheMaxAge"),
        "available_fields": layer_fields,
        "feature_count_context_5km": int(len(gdf)),
        "feature_count_inside_strict_area": int(gdf["inside_strict_area"].sum()) if not gdf.empty else 0,
        "phase_counts": counts("COM_FASE"),
        "alarm_type_counts": counts("TAL_DESC_ALARMA2"),
        "municipality_counts": counts("MUNICIPI_DPX"),
        "features": features_summary,
        "limitations": [
            "The ArcGIS viewer exposes operational IV point incidents; it is not a historical burned-area or perimeter layer.",
            "The layer is used only as current public Bombers context and is not included in the environmental similarity score.",
            "Licence, data-retention policy and the exact relationship with IncendisCAT still need formal confirmation before any connector-grade use.",
        ],
    }
    return gdf, context


def load_copernicus_context() -> dict[str, object]:
    """Fetch the public EFFIS/Copernicus data-request catalogue.

    The public endpoint lists requestable datasets and formats. It is not used
    as a local geospatial layer because product requests/downloads are handled
    through the EFFIS data-request workflow.
    """

    raw_path = OUT_RAW_COPERNICUS / "effis_drf_datasets_catalog.json"
    if raw_path.exists() and raw_path.stat().st_size > 0:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        data = json.loads(fetch_bytes(EFFIS_DRF_DATASETS_API, timeout=90).decode("utf-8"))
        raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    datasets = data.get("datasets", [])
    file_types = data.get("file_types", [])
    matching = data.get("matching", {})
    return {
        "status": "verified",
        "source_use": "public_catalog_verified_not_local_layer",
        "source": "EFFIS / Copernicus Emergency Management Service Data Request Form",
        "api": EFFIS_DRF_DATASETS_API,
        "raw_path": str(raw_path),
        "datasets": datasets,
        "file_types": file_types,
        "matching": matching,
        "dataset_codes": [str(item.get("code", "")) for item in datasets],
        "dataset_names": [str(item.get("name", "")) for item in datasets],
        "limitations": [
            "The public endpoint verifies the available EFFIS requestable datasets and output formats.",
            "No EFFIS/Copernicus product geometry was downloaded or used in the similarity score in this run.",
        ],
    }


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def download_wfs_geojson(
    base_url: str,
    layer: str,
    output_path: Path,
    *,
    bbox: tuple[float, float, float, float] | None = None,
    count: int = 5000,
) -> Path:
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    all_features: list[dict[str, object]] = []
    start = 0
    crs = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25831"}}
    while True:
        params: list[tuple[str, object]] = [
            ("service", "WFS"),
            ("version", "2.0.0"),
            ("request", "GetFeature"),
            ("typeNames", layer),
            ("outputFormat", "application/json"),
            ("srsName", TARGET_CRS),
            ("count", count),
            ("startIndex", start),
        ]
        if bbox is not None:
            xmin, ymin, xmax, ymax = bbox
            params.append(("BBOX", f"{xmin},{ymin},{xmax},{ymax},{TARGET_CRS}"))
        url = f"{base_url}?{urlencode(params)}"
        payload = fetch_bytes(url)
        if payload.lstrip().startswith(b"<"):
            raise RuntimeError(payload[:2000].decode("utf-8", "replace"))
        page = json.loads(payload.decode("utf-8"))
        features = page.get("features", [])
        all_features.extend(features)
        crs = page.get("crs", crs)
        returned = int(page.get("numberReturned", len(features)) or len(features))
        matched = page.get("numberMatched")
        if returned < count:
            break
        if isinstance(matched, int) and start + returned >= matched:
            break
        start += returned

    output = {
        "type": "FeatureCollection",
        "features": all_features,
        "totalFeatures": len(all_features),
        "numberMatched": len(all_features),
        "numberReturned": len(all_features),
        "timeStamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "crs": crs,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    return output_path


def load_study_area() -> gpd.GeoDataFrame:
    raw_path = download_wfs_geojson(
        ESPAIS_WFS,
        PARCS_LAYER,
        OUT_RAW_BOUNDARY / "espaisnaturals_parcsnaturals.geojson",
        count=200,
    )
    parcs = gpd.read_file(raw_path).to_crs(TARGET_CRS)
    if parcs.empty:
        raise RuntimeError("No protected-area features were returned by the official WFS")

    name_col = "NOM_ESPAI" if "NOM_ESPAI" in parcs.columns else parcs.columns[0]
    normalized = parcs[name_col].map(normalize_text)
    mask = normalized.str.contains("cadi", na=False) & normalized.str.contains("moixero", na=False)
    selected = parcs[mask].copy()
    if selected.empty:
        names = ", ".join(sorted(str(v) for v in parcs[name_col].dropna().head(20)))
        raise RuntimeError(f"Could not identify Parc Natural del Cadí-Moixeró in official WFS. Sample names: {names}")

    selected["study_area_basis"] = "Official protected-area polygon used as proxy for 'massís de la serra del Cadí'"
    selected["source_layer"] = PARCS_LAYER
    selected["source_url"] = ESPAIS_WFS
    selected = selected[selected.geometry.notna() & ~selected.geometry.is_empty].copy()
    selected.loc[~selected.geometry.is_valid, "geometry"] = selected.loc[~selected.geometry.is_valid, "geometry"].make_valid()

    study_out = OUT_PROC / "study_area.gpkg"
    if study_out.exists():
        study_out.unlink()
    selected.to_file(study_out, layer="study_area", driver="GPKG")
    return selected


def parse_fire_year(value: object) -> int | None:
    text = "" if value is None else str(value)
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if not match:
        return None
    year = int(match.group(3))
    if year < 100:
        year += 2000 if year <= 30 else 1900
    return year


def load_fire_perimeters(study: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    study_geom = study.geometry.union_all()
    context_geom = study_geom.buffer(FIRE_CONTEXT_BUFFER_M)
    xmin, ymin, xmax, ymax = [float(v) for v in context_geom.bounds]
    raw_path = download_wfs_geojson(
        FIRES_WFS,
        FIRES_LAYER,
        OUT_RAW_FIRES / "vegetacio_incendis_cadi_context_5km_bbox.geojson",
        bbox=(xmin, ymin, xmax, ymax),
        count=5000,
    )
    source = gpd.read_file(raw_path).to_crs(TARGET_CRS)
    if source.empty:
        clipped = gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=TARGET_CRS)
    else:
        source = source[source.geometry.notna() & ~source.geometry.is_empty].copy()
        source.loc[~source.geometry.is_valid, "geometry"] = source.loc[~source.geometry.is_valid, "geometry"].make_valid()
        clipped = gpd.clip(source, context_geom)
        clipped = clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty].copy()

    if clipped.empty:
        clipped["area_ha_context"] = []
        clipped["area_ha_dins_cadi"] = []
        clipped["distance_to_study_m"] = []
        clipped["inside_strict_area"] = []
        clipped["any_foc"] = []
        clipped["etiqueta_foc"] = []
    else:
        clipped["area_ha_context"] = clipped.geometry.area / 10000
        clipped["area_ha_dins_cadi"] = clipped.geometry.intersection(study_geom).area / 10000
        clipped["distance_to_study_m"] = clipped.geometry.distance(study_geom)
        clipped["inside_strict_area"] = clipped["area_ha_dins_cadi"] > 0
        clipped = clipped[clipped.geometry.area >= MIN_FIRE_AREA_M2].copy()
        clipped["any_foc"] = clipped.get("DATES_FOC", pd.Series(index=clipped.index, dtype=object)).map(parse_fire_year)
        clipped["etiqueta_foc"] = clipped["any_foc"].map(lambda v: "s/d" if pd.isna(v) else str(int(v)))
        clipped["font"] = "Generalitat de Catalunya WFS VEGETACIO:VEGETACIO_INCENDIS"

    out = OUT_PROC_FIRES / "incendis_historics_cadi_context_5km.gpkg"
    if out.exists():
        out.unlink()
    clipped.to_file(out, layer="incendis_historics_context", driver="GPKG")
    return clipped


def habitat_group(row: pd.Series) -> str:
    text = " ".join(
        normalize_text(row.get(col, ""))
        for col in ["GRUP_CA", "TIPUS_CA", "SUBTIP_CA", "CORINE_CA"]
        if col in row
    )
    if "bosc" in text or "pined" in text or "faged" in text or "roured" in text:
        return "Bosc"
    if "matollar" in text or "landa" in text or "boixed" in text or "ginestar" in text or "savinos" in text:
        return "Matollar"
    if "prat" in text or "herbacia" in text or "herbassar" in text or "jonquera" in text:
        return "Prats i herbassars"
    if "conreu" in text or "culti" in text or "feixa" in text:
        return "Conreus"
    if "aigua" in text or "fontinal" in text or "mollera" in text or "estany" in text or "riu" in text:
        return "Aigua / zones humides"
    if "roquissar" in text or "tarter" in text or "cingler" in text or "pedrus" in text or "rupicol" in text:
        return "Roquissars / sol nu"
    return "Altres"


def load_habitats(study: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    context_geom = study.geometry.union_all().buffer(FIRE_CONTEXT_BUFFER_M)
    xmin, ymin, xmax, ymax = [float(v) for v in context_geom.bounds]
    raw_path = download_wfs_geojson(
        HABITATS_WFS,
        HABITATS_LAYER,
        OUT_RAW_HABITATS / "habitats_terrestres_v3_cadi_context_5km_bbox.geojson",
        bbox=(xmin, ymin, xmax, ymax),
        count=5000,
    )
    source = gpd.read_file(raw_path).to_crs(TARGET_CRS)
    source = source[source.geometry.notna() & ~source.geometry.is_empty].copy()
    source.loc[~source.geometry.is_valid, "geometry"] = source.loc[~source.geometry.is_valid, "geometry"].make_valid()
    clipped = gpd.clip(source, context_geom)
    clipped = clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty].copy()
    if clipped.empty:
        raise RuntimeError("No terrestrial habitat polygons were found inside the Cadi study area")

    clipped["condicio"] = clipped.apply(habitat_group, axis=1)
    clipped["superficie_ha"] = clipped.geometry.area / 10000
    keep = [
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
        "AMENACA",
        "VGI",
        "condicio",
        "superficie_ha",
        "geometry",
    ]
    for col in keep:
        if col not in clipped.columns and col != "geometry":
            clipped[col] = None
    out = OUT_PROC / "habitats.gpkg"
    if out.exists():
        out.unlink()
    clipped[[col for col in keep if col in clipped.columns]].to_file(out, layer="habitats", driver="GPKG")
    return clipped


def overpass_query(study: gpd.GeoDataFrame) -> str:
    context = gpd.GeoDataFrame(geometry=[study.geometry.union_all().buffer(FIRE_CONTEXT_BUFFER_M)], crs=TARGET_CRS)
    west, south, east, north = context.to_crs(WGS84).total_bounds
    bbox = f"{south},{west},{north},{east}"
    return f"""
[out:json][timeout:240];
(
  way["highway"~"^(path|track|footway|bridleway|cycleway|service|unclassified|residential|tertiary|secondary|primary)$"]({bbox});
);
out geom;
"""


def load_access(study: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, str]:
    raw_path = OUT_RAW_ACCESS / "overpass_osm_raw.json"
    if raw_path.exists() and raw_path.stat().st_size > 0:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        query = overpass_query(study)
        payload = urlencode({"data": query}).encode("utf-8")
        try:
            raw = json.loads(fetch_bytes(OVERPASS_URL, method="POST", data=payload, timeout=360).decode("utf-8"))
            raw["_ecoradar"] = {
                "downloaded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "source": "OpenStreetMap via Overpass API",
                "url": OVERPASS_URL,
            }
            raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            empty = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=TARGET_CRS)
            return empty, f"service_unavailable: {exc}"

    records: list[dict[str, object]] = []
    for element in raw.get("elements", []):
        tags = element.get("tags") or {}
        if element.get("type") != "way" or "highway" not in tags:
            continue
        coords = [(node["lon"], node["lat"]) for node in element.get("geometry", []) if "lon" in node and "lat" in node]
        if len(coords) < 2:
            continue
        records.append(
            {
                "osm_type": "way",
                "osm_id": str(element.get("id", "")),
                "name": str(tags.get("name", "")),
                "highway": str(tags.get("highway", "")),
                "surface": str(tags.get("surface", "")),
                "access": str(tags.get("access", "")),
                "geometry": LineString(coords),
            }
        )
    lines = gpd.GeoDataFrame(records, geometry="geometry", crs=WGS84)
    if lines.empty:
        lines = gpd.GeoDataFrame(
            {col: [] for col in ["osm_type", "osm_id", "name", "highway", "surface", "access", "geometry"]},
            geometry="geometry",
            crs=WGS84,
        )
    context_geom = study.geometry.union_all().buffer(FIRE_CONTEXT_BUFFER_M)
    lines = gpd.clip(lines.to_crs(TARGET_CRS), context_geom)
    lines = lines[lines.geometry.notna() & ~lines.geometry.is_empty].copy()
    lines["length_km"] = lines.geometry.length / 1000 if not lines.empty else []

    out = OUT_PROC / "recreational_pressure.gpkg"
    if out.exists():
        out.unlink()
    lines.to_file(out, layer="osm_paths_tracks_roads", driver="GPKG")
    return lines, "verified"


def read_or_download_dem(study: gpd.GeoDataFrame) -> Path:
    out_path = OUT_RAW_TERRAIN / "icgc_dem_20m_cadi_context_5km_window.tif"
    if out_path.exists():
        return out_path

    context_geom = study.geometry.union_all().buffer(FIRE_CONTEXT_BUFFER_M)
    minx, miny, maxx, maxy = [float(v) for v in context_geom.bounds]
    margin = 300.0
    with rasterio.open(DEM_URL) as src:
        window = from_bounds(minx - margin, miny - margin, maxx + margin, maxy + margin, src.transform)
        factor = max(1.0, DEM_TARGET_RES_M / float(src.res[0]))
        out_height = max(1, int(round(window.height / factor)))
        out_width = max(1, int(round(window.width / factor)))
        data = src.read(1, window=window, out_shape=(out_height, out_width), resampling=Resampling.bilinear, masked=True)
        transform = src.window_transform(window) * Affine.scale(window.width / out_width, window.height / out_height)
        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            height=out_height,
            width=out_width,
            transform=transform,
            compress="deflate",
            predictor=2,
            tiled=True,
        )
        nodata = src.nodata if src.nodata is not None else -9999
        profile.update(nodata=nodata)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data.filled(nodata), 1)
    return out_path


def derive_topography(dem_path: Path) -> tuple[Path, Path]:
    slope_path = OUT_PROC_SIM / "pendent_icgc_derived_cadi_context_5km.tif"
    aspect_path = OUT_PROC_SIM / "orientacio_icgc_derived_cadi_context_5km.tif"
    if slope_path.exists() and aspect_path.exists():
        return slope_path, aspect_path

    with rasterio.open(dem_path) as src:
        z = src.read(1).astype("float32")
        nodata = src.nodata
        if nodata is not None:
            z[z == nodata] = np.nan
        res_x, res_y = src.res
        dz_dy, dz_dx = np.gradient(z, res_y, res_x)
        slope = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))).astype("float32")
        aspect = (np.degrees(np.arctan2(dz_dx, -dz_dy)) + 360.0) % 360.0
        aspect = aspect.astype("float32")
        slope[np.isnan(z)] = -9999
        aspect[np.isnan(z)] = -9999
        profile = src.profile.copy()
        profile.update(dtype="float32", nodata=-9999, compress="deflate", predictor=2)
        with rasterio.open(slope_path, "w", **profile) as dst:
            dst.write(slope, 1)
        with rasterio.open(aspect_path, "w", **profile) as dst:
            dst.write(aspect, 1)
    return slope_path, aspect_path


def sample_raster(path: Path, points: list[Point]) -> list[float]:
    with rasterio.open(path) as src:
        values = []
        for (value,) in src.sample([(p.x, p.y) for p in points]):
            val = float(value)
            if src.nodata is not None and val == src.nodata:
                val = float("nan")
            values.append(val)
    return values


def aspect_class(degrees: float | None) -> str:
    if degrees is None or np.isnan(degrees):
        return "sense_dada"
    if degrees >= 315 or degrees < 45:
        return "N"
    if degrees < 135:
        return "E"
    if degrees < 225:
        return "S"
    return "W"


def slope_class(degrees: float | None) -> str:
    if degrees is None or np.isnan(degrees):
        return "sense_dada"
    if degrees < 10:
        return "suau"
    if degrees < 25:
        return "mitjana"
    if degrees < 35:
        return "forta"
    return "molt_forta"


def distance_score(value: float, samples: list[float]) -> float:
    if not samples or np.isnan(value):
        return 0.0
    med = float(np.median(samples))
    spread = max(float(np.std(samples)), 100.0)
    return float(max(0.0, 1.0 - abs(value - med) / (spread * 3.0)))


def numeric_similarity(value: float, samples: list[float], floor: float) -> float:
    if not samples or np.isnan(value):
        return 0.0
    med = float(np.median(samples))
    spread = max(float(np.std(samples)), floor)
    return float(max(0.0, 1.0 - abs(value - med) / (spread * 2.5)))


def circular_aspect_similarity(value: float, samples: list[float]) -> float:
    if not samples or np.isnan(value):
        return 0.0
    radians = np.deg2rad(samples)
    mean_angle = math.degrees(math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean())))
    if mean_angle < 0:
        mean_angle += 360
    diff = abs((value - mean_angle + 180) % 360 - 180)
    return float(max(0.0, 1.0 - diff / 90.0))


def build_grid(study_geom, size: float = CELL_SIZE_M) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = study_geom.bounds
    rows = []
    y = miny
    idx = 0
    while y < maxy:
        x = minx
        while x < maxx:
            geom = box(x, y, min(x + size, maxx), min(y + size, maxy)).intersection(study_geom)
            if not geom.is_empty and geom.area > size * size * 0.08:
                rows.append({"cell_id": idx, "geometry": geom})
                idx += 1
            x += size
        y += size
    return gpd.GeoDataFrame(rows, crs=TARGET_CRS)


def enrich_fire_and_grid(
    fires: gpd.GeoDataFrame,
    habitats: gpd.GeoDataFrame,
    access: gpd.GeoDataFrame,
    dem_path: Path,
    slope_path: Path,
    aspect_path: Path,
    study_geom,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    if fires.empty:
        raise RuntimeError("No official historical burned polygons are available inside the selected Cadi area")

    fires = fires.copy()
    fires["sample_point"] = fires.representative_point()
    fire_points = list(fires["sample_point"])
    fires["slope_deg"] = sample_raster(slope_path, fire_points)
    fires["aspect_deg"] = sample_raster(aspect_path, fire_points)
    fires["elevation_m"] = sample_raster(dem_path, fire_points)
    fires["aspect_class"] = fires["aspect_deg"].apply(aspect_class)
    fires["slope_class"] = fires["slope_deg"].apply(slope_class)
    if access.empty:
        fires["distance_to_access_m"] = np.nan
        access_union = None
    else:
        access_union = access.geometry.union_all()
        fires["distance_to_access_m"] = fires.geometry.distance(access_union)

    id_col = "OBJECTID" if "OBJECTID" in fires.columns else "id"
    fire_join = gpd.GeoDataFrame(fires[[id_col]].copy(), geometry=fires["sample_point"], crs=fires.crs)
    fire_hab = gpd.sjoin(fire_join, habitats[["condicio", "COD_CORINE", "CORINE_CA", "geometry"]], how="left", predicate="within")
    hab_once = fire_hab.drop_duplicates(id_col).set_index(id_col)
    fires["vegetation_group"] = fires[id_col].map(hab_once["condicio"].to_dict()).fillna("sense_dada")
    fires["COD_CORINE"] = fires[id_col].map(hab_once["COD_CORINE"].to_dict()).fillna("sense_dada")
    fires["CORINE_CA"] = fires[id_col].map(hab_once["CORINE_CA"].to_dict()).fillna("sense_dada")

    grid = build_grid(study_geom)
    grid["sample_point"] = grid.representative_point()
    grid_points = list(grid["sample_point"])
    grid["slope_deg"] = sample_raster(slope_path, grid_points)
    grid["aspect_deg"] = sample_raster(aspect_path, grid_points)
    grid["elevation_m"] = sample_raster(dem_path, grid_points)
    grid["aspect_class"] = grid["aspect_deg"].apply(aspect_class)
    grid["slope_class"] = grid["slope_deg"].apply(slope_class)
    if access_union is None:
        grid["distance_to_access_m"] = np.nan
    else:
        grid["distance_to_access_m"] = grid.geometry.distance(access_union)

    grid_join = gpd.GeoDataFrame(grid[["cell_id"]].copy(), geometry=grid["sample_point"], crs=grid.crs)
    grid_hab = gpd.sjoin(grid_join, habitats[["condicio", "COD_CORINE", "CORINE_CA", "geometry"]], how="left", predicate="within")
    grid_once = grid_hab.drop_duplicates("cell_id").set_index("cell_id")
    grid["vegetation_group"] = grid["cell_id"].map(grid_once["condicio"].to_dict()).fillna("sense_dada")
    grid["COD_CORINE"] = grid["cell_id"].map(grid_once["COD_CORINE"].to_dict()).fillna("sense_dada")

    fire_groups = set(fires["vegetation_group"])
    fire_habs = set(fires["COD_CORINE"])
    fire_aspects = [float(v) for v in fires["aspect_deg"] if pd.notna(v)]
    fire_slopes = [float(v) for v in fires["slope_deg"] if pd.notna(v)]
    fire_elev = [float(v) for v in fires["elevation_m"] if pd.notna(v)]
    fire_dist = [float(v) for v in fires["distance_to_access_m"] if pd.notna(v)]

    grid["score_vegetacio"] = grid["vegetation_group"].apply(lambda x: 1.0 if x in fire_groups else 0.0)
    grid["score_habitat"] = grid["COD_CORINE"].apply(lambda x: 1.0 if x in fire_habs else 0.0)
    grid["score_pendent"] = grid["slope_deg"].apply(lambda v: numeric_similarity(float(v), fire_slopes, 7.0))
    grid["score_orientacio"] = grid["aspect_deg"].apply(lambda v: circular_aspect_similarity(float(v), fire_aspects))
    grid["score_altitud"] = grid["elevation_m"].apply(lambda v: numeric_similarity(float(v), fire_elev, 175.0))
    grid["score_accessibilitat"] = grid["distance_to_access_m"].apply(lambda v: distance_score(float(v), fire_dist))

    weights = {
        "score_vegetacio": 0.24,
        "score_habitat": 0.18,
        "score_pendent": 0.18,
        "score_orientacio": 0.14,
        "score_altitud": 0.12,
        "score_accessibilitat": 0.14,
    }
    if not fire_dist:
        weights.pop("score_accessibilitat")
    total_weight = sum(weights.values())
    grid["similitud_score"] = sum((weight / total_weight) * grid[col] for col, weight in weights.items())
    grid["classe_similitud"] = pd.cut(
        grid["similitud_score"],
        bins=[-0.01, 0.34, 0.52, 0.72, 1.01],
        labels=["baixa", "mitjana", "mitjana_alta", "alta"],
    ).astype(str)
    grid["area_ha"] = grid.geometry.area / 10000
    fires = fires.drop(columns=["sample_point"])
    grid = grid.drop(columns=["sample_point"])
    return fires, grid


def normalize_for_svg(bounds, box_area):
    minx, miny, maxx, maxy = bounds
    left, top, width, height = box_area
    scale = min(width / (maxx - minx), height / (maxy - miny))
    actual_w = (maxx - minx) * scale
    actual_h = (maxy - miny) * scale
    left += (width - actual_w) / 2
    top += (height - actual_h) / 2

    def xy(x, y):
        return left + (x - minx) * scale, top + (maxy - y) * scale

    return xy, left, top, actual_w, actual_h


def ring_path(coords, xy):
    pts = list(coords)
    if not pts:
        return ""
    x0, y0 = xy(*pts[0])
    d = [f"M {x0:.2f} {y0:.2f}"]
    for x, y, *_ in pts[1:]:
        X, Y = xy(x, y)
        d.append(f"L {X:.2f} {Y:.2f}")
    d.append("Z")
    return " ".join(d)


def polygon_paths(geom, xy):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        d = ring_path(geom.exterior.coords, xy)
        for interior in geom.interiors:
            d += " " + ring_path(interior.coords, xy)
        return [d]
    if isinstance(geom, MultiPolygon):
        out = []
        for part in geom.geoms:
            out.extend(polygon_paths(part, xy))
        return out
    if isinstance(geom, GeometryCollection):
        out = []
        for part in geom.geoms:
            out.extend(polygon_paths(part, xy))
        return out
    return []


def line_paths(geom, xy):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        coords = list(geom.coords)
        if len(coords) < 2:
            return []
        x0, y0 = xy(*coords[0])
        d = [f"M {x0:.2f} {y0:.2f}"]
        for x, y, *_ in coords[1:]:
            X, Y = xy(x, y)
            d.append(f"L {X:.2f} {Y:.2f}")
        return [" ".join(d)]
    if isinstance(geom, MultiLineString):
        out = []
        for part in geom.geoms:
            out.extend(line_paths(part, xy))
        return out
    if isinstance(geom, GeometryCollection):
        out = []
        for part in geom.geoms:
            out.extend(line_paths(part, xy))
        return out
    return []


def score_color(score: float) -> str:
    if score >= 0.72:
        return "#c43d32"
    if score >= 0.52:
        return "#e6863a"
    if score >= 0.34:
        return "#e3c85d"
    return "#d7dfbf"


def build_svg(study, grid, fires, habitat_base, access, bombers_viewer, metadata):
    width, height = 1280, 1280
    minx, miny, maxx, maxy = study.total_bounds
    bounds = (minx - 1000, miny - 1000, maxx + 1000, maxy + 1000)
    xy, left, top, aw, ah = normalize_for_svg(bounds, (54, 105, 855, 735))

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    svg.append('<rect width="100%" height="100%" fill="#f6f4ee"/>')
    svg.append('<text x="54" y="44" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#173f35">Serra del Cadí · similitud ambiental amb incendis històrics</text>')
    svg.append('<text x="54" y="70" font-family="Arial, sans-serif" font-size="14" fill="#5f665c">Àmbit operatiu: Parc Natural del Cadí-Moixeró. Capa heurística, no probabilitat oficial.</text>')
    svg.append(f'<rect x="{left-8:.1f}" y="{top-8:.1f}" width="{aw+16:.1f}" height="{ah+16:.1f}" fill="#ffffff" stroke="#d4d0c5"/>')
    svg.append(f'<defs><clipPath id="mainclip"><rect x="{left-8:.1f}" y="{top-8:.1f}" width="{aw+16:.1f}" height="{ah+16:.1f}"/></clipPath></defs>')
    svg.append('<g clip-path="url(#mainclip)">')

    base_colors = {
        "Bosc": "#52785a",
        "Matollar": "#c58b43",
        "Prats i herbassars": "#9dbb68",
        "Conreus": "#d8c96a",
        "Aigua / zones humides": "#77a8c8",
        "Roquissars / sol nu": "#d8d1c2",
        "Altres": "#ece7dd",
    }
    for _, row in habitat_base.iterrows():
        for d in polygon_paths(row.geometry.simplify(60, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="{base_colors.get(row.condicio, "#eee")}" stroke="#ffffff" stroke-width="0.2" opacity="0.54"/>')

    for _, row in grid.iterrows():
        color = score_color(float(row.similitud_score))
        for d in polygon_paths(row.geometry.simplify(8, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="{color}" stroke="none" opacity="0.46"/>')

    for geom in access.geometry if not access.empty else []:
        for d in line_paths(geom.simplify(20, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="none" stroke="#2d2b28" stroke-width="0.55" opacity="0.32" stroke-linecap="round"/>')

    if bombers_viewer is not None and not bombers_viewer.empty:
        for _, row in bombers_viewer.iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            x, y = xy(row.geometry.x, row.geometry.y)
            svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8.5" fill="#5b3c88" stroke="#ffffff" stroke-width="2.2" opacity="0.96"/>')
            svg.append(f'<text x="{x:.1f}" y="{y+3.3:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="8.5" font-weight="700" fill="#ffffff">IV</text>')

    for _, row in fires.iterrows():
        for d in polygon_paths(row.geometry.simplify(8, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="#d7382f" fill-opacity="0.63" stroke="#7d1712" stroke-width="1.8"/>')

    for geom in study.geometry:
        for d in polygon_paths(geom.simplify(18, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="none" stroke="#173f35" stroke-width="2.8"/>')
    svg.append("</g>")

    label_rows = fires.sort_values("area_ha_context", ascending=False).head(16)
    for _, row in label_rows.iterrows():
        p = row.geometry.representative_point()
        x, y = xy(p.x, p.y)
        x = min(max(x, left + 28), left + aw - 28)
        y = min(max(y, top + 34), top + ah - 12)
        label = str(row.etiqueta_foc)
        svg.append(f'<rect x="{x-23:.1f}" y="{y-30:.1f}" width="46" height="21" rx="10" fill="#fff8f0" stroke="#8f1712" stroke-width="1.1"/>')
        svg.append(f'<text x="{x:.1f}" y="{y-15.2:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" font-weight="700" fill="#7d1712">{label}</text>')

    x0, _ = xy(0, 0)
    x1, _ = xy(5000, 0)
    bx, by = left + 22, top + ah - 30
    svg.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx+abs(x1-x0):.1f}" y2="{by:.1f}" stroke="#173f35" stroke-width="4"/>')
    svg.append(f'<text x="{bx+abs(x1-x0)/2:.1f}" y="{by-9:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#173f35">5 km</text>')

    panel_x = 940
    svg.append(f'<rect x="{panel_x}" y="106" width="290" height="770" rx="7" fill="#ffffff" stroke="#d4d0c5"/>')
    svg.append(f'<text x="{panel_x+20}" y="140" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#173f35">Capes de similitud</text>')
    legend = [
        ("Alta similitud", "#c43d32", "condicions molt concurrents"),
        ("Mitjana-alta", "#e6863a", "força coincidència"),
        ("Mitjana", "#e3c85d", "coincidència parcial"),
        ("Baixa", "#d7dfbf", "poca semblança"),
    ]
    y = 172
    for title, color, desc in legend:
        svg.append(f'<rect x="{panel_x+22}" y="{y-14}" width="18" height="18" fill="{color}" opacity="0.72"/>')
        svg.append(f'<text x="{panel_x+50}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">{title}</text>')
        svg.append(f'<text x="{panel_x+50}" y="{y+16}" font-family="Arial, sans-serif" font-size="10.5" fill="#6b7068">{desc}</text>')
        y += 43
    y += 8
    svg.append(f'<text x="{panel_x+20}" y="{y}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#173f35">Variables usades</text>')
    y += 24
    variables = [
        "Perímetres oficials d'incendi",
        "Hàbitats terrestres v3",
        "Vegetació agrupada per hàbitat",
        "Pendent, orientació i altitud ICGC",
        "Distància a pistes/camins OSM",
    ]
    if metadata["access_status"] != "verified":
        variables[-1] = "Accessos OSM no incorporats"
    for item in variables:
        svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">• {item}</text>')
        y += 21
    y += 10
    svg.append(f'<text x="{panel_x+20}" y="{y}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#173f35">Històric oficial</text>')
    y += 24
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">{metadata["official_fire_polygons_used"]} perímetres en context 5 km</text>')
    y += 20
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">{metadata["official_fire_polygons_inside_strict_area"]} dins el límit estricte</text>')
    y += 20
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">{metadata["official_fire_area_context_ha"]:.1f} ha cremades en context</text>')
    y += 20
    years = metadata["fire_years_label"]
    for chunk in [years[i : i + 35] for i in range(0, len(years), 35)][:3]:
        svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#6b7068">Anys: {chunk}</text>')
        y += 18
    fire_origin = metadata["official_fire_origin"]
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="10.8" fill="#6b7068">{fire_origin["data_source_legend"]}</text>')
    y += 17
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="10.8" fill="#6b7068">{fire_origin["cause_legend"]}</text>')
    y += 17
    y += 8
    bombers = metadata["bombers_context"]
    bombers_viewer_meta = metadata["bombers_arcgis_viewer_context"]
    copernicus = metadata["copernicus_context"]
    svg.append(f'<text x="{panel_x+20}" y="{y}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#173f35">Context públic</text>')
    y += 22
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#373d36">Bombers hist.: {bombers["total_vegetation_fire_actions"]} act. 2019-2026</text>')
    y += 18
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#6b7068">Alt Urgell, Berguedà i Cerdanya</text>')
    y += 18
    viewer_count = int(bombers_viewer_meta.get("feature_count_context_5km", 0))
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#373d36">Visor Bombers: {viewer_count} IV en context</text>')
    y += 18
    if viewer_count:
        phase_label = "; ".join(
            f"{key}: {value}" for key, value in bombers_viewer_meta.get("phase_counts", {}).items()
        )[:34]
        svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#6b7068">Fase visor: {phase_label}</text>')
        y += 18
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#6b7068">punt operatiu, no perímetre</text>')
    y += 18
    dataset_label = ", ".join(copernicus.get("dataset_codes", [])[:3])
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#373d36">Copernicus/EFFIS: {dataset_label}</text>')
    y += 18
    svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#6b7068">catàleg públic, no capa local</text>')
    y += 28
    svg.append(f'<text x="{panel_x+20}" y="{y}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#173f35">Límit metodològic</text>')
    y += 22
    notes = [
        "Alta similitud = prioritat de camp.",
        "No estima probabilitat ni intensitat.",
        "Decisió: verificar combustible,",
        "humitat, vent, Pla Alfa i aigua.",
    ]
    for note in notes:
        svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#5f665c">{note}</text>')
        y += 18

    lx, ly, lw, lh = 54, 890, 1172, 280
    svg.append(f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" rx="7" fill="#ffffff" stroke="#d4d0c5"/>')
    svg.append(f'<text x="{lx+20}" y="{ly+34}" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#173f35">Lectura prudent per treball de camp</text>')
    lines = [
        ("Concurrència", "La capa ressalta zones semblants als perímetres històrics en vegetació, hàbitat, pendent, orientació, altitud i accessibilitat."),
        ("Ús correcte", "Serveix per prioritzar revisió de camp i preguntes de gestió; no per afirmar on cremarà."),
        ("Dependències", "Abans de probabilitat calen meteo, humitat/NDMI, Pla Alfa, punts d’aigua i validació de combustible."),
        ("Traçabilitat", "El visor de Bombers és context operatiu; no és font d'històric ni de recuperació ecològica."),
    ]
    y = ly + 66
    for head, text in lines:
        svg.append(f'<text x="{lx+22}" y="{y}" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#173f35">{head}</text>')
        svg.append(f'<text x="{lx+132}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">{text}</text>')
        y += 44
    svg.append('<text x="54" y="1232" font-family="Arial, sans-serif" font-size="10.5" fill="#5f665c">Fonts: WFS Generalitat incendis/espais/hàbitats; DEM ICGC; OSM/Overpass; Bombers g2ay-3vnj i visor ArcGIS; EFFIS/Copernicus DRF. Consulta: 2026-07-07.</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def write_outputs(
    study,
    fires,
    habitats,
    access,
    bombers_viewer,
    dem_path,
    slope_path,
    aspect_path,
    grid,
    access_status,
    bombers_context,
    bombers_arcgis_viewer_context,
    copernicus_context,
):
    fires_out = OUT_PROC_SIM / "incendis_historics_amb_condicions.gpkg"
    grid_out = OUT_PROC_SIM / "similitud_condicions_incendi_cadi.gpkg"
    if fires_out.exists():
        fires_out.unlink()
    if grid_out.exists():
        grid_out.unlink()
    fires.to_file(fires_out, layer="incendis_condicions", driver="GPKG")
    grid.to_file(grid_out, layer="similitud_condicions", driver="GPKG")
    grid.to_file(OUT_MAPS / "similitud_condicions_incendi_cadi.geojson", driver="GeoJSON")

    years = sorted({int(v) for v in fires["any_foc"].dropna().tolist()})
    if years:
        year_label = ", ".join(str(v) for v in years)
    else:
        year_label = "sense data oficial llegible"

    area_by_class = (
        grid.groupby("classe_similitud", observed=False)["area_ha"].sum().sort_index().to_dict()
        if not grid.empty
        else {}
    )
    fire_sample_summary = []
    for _, row in fires.sort_values("area_ha_context", ascending=False).iterrows():
        fire_sample_summary.append(
            {
                "year": str(row.get("etiqueta_foc", "s/d")),
                "objectid": str(row.get("OBJECTID", row.get("id", ""))),
                "area_ha_context": float(row.get("area_ha_context", 0.0)),
                "area_ha_inside_strict_area": float(row.get("area_ha_dins_cadi", 0.0)),
                "distance_to_study_m": float(row.get("distance_to_study_m", 0.0)),
                "vegetation_group": str(row.get("vegetation_group", "")),
                "habitat_corine": str(row.get("COD_CORINE", "")),
                "slope_deg": float(row.get("slope_deg", np.nan)),
                "slope_class": str(row.get("slope_class", "")),
                "aspect_deg": float(row.get("aspect_deg", np.nan)),
                "aspect_class": str(row.get("aspect_class", "")),
                "elevation_m": float(row.get("elevation_m", np.nan)),
                "distance_to_access_m": None
                if pd.isna(row.get("distance_to_access_m", np.nan))
                else float(row.get("distance_to_access_m")),
            }
        )
    origin_candidate_fields = [
        col
        for col in fires.columns
        if any(token in normalize_text(col) for token in ["causa", "origen", "ignicio", "ignicion", "punt_inici"])
    ]
    origin_values_by_field = {}
    for col in origin_candidate_fields:
        values = sorted({str(value) for value in fires[col].dropna().tolist() if str(value).strip()})
        if values:
            origin_values_by_field[col] = values[:6]
    if origin_values_by_field:
        cause_label = "; ".join(
            f"{field}: {', '.join(values[:3])}" for field, values in origin_values_by_field.items()
        )[:48]
    else:
        cause_label = "Causa ignició: no disponible"

    metadata = {
        "created_at": TODAY,
        "status": "environmental_similarity_not_fire_probability",
        "study_area_assumption": "Official Parc Natural del Cadí-Moixeró polygon used as the operational proxy for 'massís de la serra del Cadí'.",
        "cell_size_m": CELL_SIZE_M,
        "dem_working_resolution_m": DEM_TARGET_RES_M,
        "study_area_ha": float(study.geometry.union_all().area / 10000),
        "official_fire_polygons_used": int(len(fires)),
        "official_fire_polygons_inside_strict_area": int(fires["inside_strict_area"].sum()) if not fires.empty else 0,
        "official_fire_area_context_ha": float(fires["area_ha_context"].sum()) if not fires.empty else 0.0,
        "official_fire_area_inside_strict_ha": float(fires["area_ha_dins_cadi"].sum()) if not fires.empty else 0.0,
        "fire_years_label": year_label,
        "fire_sample_summary": fire_sample_summary,
        "official_fire_origin": {
            "data_source_legend": "Origen dades: WFS Generalitat",
            "data_source_detail": "VEGETACIO:VEGETACIO_INCENDIS",
            "candidate_origin_fields": origin_candidate_fields,
            "origin_values_by_field": origin_values_by_field,
            "cause_legend": cause_label,
            "cause_available": bool(origin_values_by_field),
        },
        "similarity_area_by_class_ha": {str(k): float(v) for k, v in area_by_class.items()},
        "access_status": access_status,
        "access_features": int(len(access)) if access_status == "verified" else 0,
        "bombers_context": bombers_context,
        "bombers_arcgis_viewer_context": bombers_arcgis_viewer_context,
        "copernicus_context": copernicus_context,
        "method": {
            "description": "Heuristic similarity to official local burned polygons; not a probability model.",
            "variables": [
                "habitat-derived vegetation group",
                "CORINE habitat code",
                "slope",
                "aspect",
                "elevation",
                "distance to OSM mapped access lines when available",
            ],
            "weights": {
                "vegetation_group": 0.24,
                "corine_habitat": 0.18,
                "slope": 0.18,
                "aspect": 0.14,
                "elevation": 0.12,
                "distance_to_access": 0.14 if access_status == "verified" else 0.0,
            },
        },
        "sources": [
            {
                "name": "Parc Natural del Cadí-Moixeró / ESPAISNATURALS_PARCSNATURALS",
                "organization": "Generalitat de Catalunya, Direccio General de Politiques Ambientals i Medi Natural",
                "status": "verified",
                "service_type": "WFS",
                "crs": TARGET_CRS,
                "path": str(OUT_PROC / "study_area.gpkg"),
            },
            {
                "name": "Superficies afectades per incendis forestals v1.1 / VEGETACIO:VEGETACIO_INCENDIS",
                "organization": "Generalitat de Catalunya / DACC / ICGC / Cos d'Agents Rurals",
                "status": "verified",
                "service_type": "WFS",
                "crs": TARGET_CRS,
                "path": str(OUT_PROC_FIRES / "incendis_historics_cadi_context_5km.gpkg"),
            },
            {
                "name": "Cartografia dels habitats terrestres, versio 3 / HABITATS_TERRESTPOL",
                "organization": "Generalitat de Catalunya",
                "status": "verified",
                "service_type": "WFS",
                "crs": TARGET_CRS,
                "path": str(OUT_PROC / "habitats.gpkg"),
            },
            {
                "name": "Model d'elevacions del terreny de Catalunya 5 m",
                "organization": "Institut Cartografic i Geologic de Catalunya",
                "status": "verified",
                "service_type": "COG/GeoTIFF",
                "crs": TARGET_CRS,
                "url": DEM_URL,
                "path": str(dem_path),
                "derived_layers": [str(slope_path), str(aspect_path)],
            },
            {
                "name": "OpenStreetMap via Overpass API",
                "organization": "OpenStreetMap contributors / Overpass community",
                "status": access_status,
                "service_type": "REST API",
                "crs": WGS84,
                "path": str(OUT_PROC / "recreational_pressure.gpkg"),
            },
            {
                "name": "Actuacions dels Bombers de la Generalitat",
                "organization": "Departament d'Interior / Direccio General de Prevencio, Extincio d'Incendis i Salvaments",
                "status": bombers_context["status"],
                "service_type": "Socrata REST API",
                "crs": "no geometry; administrative/tabular records",
                "url": BOMBERS_API,
                "path": bombers_context["raw_path"],
                "summary_path": bombers_context["summary_path"],
                "source_use": bombers_context["source_use"],
            },
            {
                "name": "Bombers - Visor d'actuacions incendis PRO / ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW",
                "organization": "Departament d'Interior / Bombers de la Generalitat",
                "status": bombers_arcgis_viewer_context["status"],
                "service_type": "ArcGIS Experience / ArcGIS FeatureServer",
                "crs": TARGET_CRS,
                "url": bombers_arcgis_viewer_context["feature_layer_url"],
                "experience_url": bombers_arcgis_viewer_context["experience_url"],
                "path": bombers_arcgis_viewer_context["raw_query_path"],
                "summary_path": bombers_arcgis_viewer_context["summary_path"],
                "source_use": bombers_arcgis_viewer_context["source_use"],
            },
            {
                "name": "EFFIS / Copernicus Emergency Management Service Data Request Form catalogue",
                "organization": "Copernicus Emergency Management Service / Joint Research Centre",
                "status": copernicus_context["status"],
                "service_type": "REST API public catalogue / data request workflow",
                "crs": "product dependent; no local product geometry downloaded",
                "url": EFFIS_DRF_DATASETS_API,
                "path": copernicus_context["raw_path"],
                "source_use": copernicus_context["source_use"],
            },
        ],
        "not_used": [
            "IncendisCAT: not used as a data source.",
            "Pla Alfa: pending exact official technical endpoint verification.",
            "Bombers ArcGIS viewer: used only as current operational point context; not used as historical perimeter evidence, ecological recovery evidence or similarity-score input.",
            "EFFIS/Copernicus product layers: public data-request catalogue incorporated as context only; no EFFIS product geometry was downloaded or used in the similarity score.",
            "Meteocat/AEMET: require credentials before implementation.",
            "Sentinel NDMI/NDVI: requires Copernicus credentials.",
            "Hydrology/water points: pending exact official layer.",
            "ICGC Cobertes del Sol 1 m: verified source but not downloaded here because the full park-scale WCS pull would be disproportionately heavy; terrestrial habitats are used for vegetation grouping.",
        ],
    }
    (OUT_META / "similitud_condicions_incendi_cadi_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pd.DataFrame(
        [{"metric": "area_ha_" + str(cls), "value": float(area)} for cls, area in metadata["similarity_area_by_class_ha"].items()]
    ).to_csv(OUT_IND / "similitud_condicions_resum.csv", index=False)

    habitat_base = habitats.dissolve(by="condicio", as_index=False, aggfunc="first")[["condicio", "geometry"]]
    svg = build_svg(study, grid, fires, habitat_base, access, bombers_viewer, metadata)
    svg_path = OUT_MAPS / "mapa_similitud_condicions_incendi_cadi.svg"
    svg_path.write_text(svg, encoding="utf-8")
    ET.fromstring(svg)

    readme = f"""# Similitud ambiental amb incendis historics - Serra del Cadi

Status: `environmental_similarity_not_fire_probability`

Aquest producte compara l'ambit operatiu del Parc Natural del Cadi-Moixero amb les condicions observades als perimetres oficials d'incendi disponibles en una corona de context de 5 km. No es un model de probabilitat ni una prediccio operativa.

## Ambit

S'ha utilitzat el poligon oficial `ESPAIS_NATURALS:ESPAISNATURALS_PARCSNATURALS` corresponent al Parc Natural del Cadi-Moixero com a proxy operatiu de "massis de la serra del Cadi". Si cal un tall estrictament geomorfologic de la serra del Cadi, cal aportar o verificar un poligon oficial mes especific.

## Sortides

- `mapa_similitud_condicions_incendi_cadi.svg`: mapa visual.
- `similitud_condicions_incendi_cadi.geojson`: grid de similitud.
- `../../processed/incendis_similarity/similitud_condicions_incendi_cadi.gpkg`: capa processada.
- `../../processed/incendis_similarity/incendis_historics_amb_condicions.gpkg`: incendis de context amb atributs de mostra.
- `../../processed/incendis_similarity/bombers_arcgis_visor_iv_context.gpkg`: punts operatius IV del visor Bombers dins el context, si n'hi ha.
- `../../indicators/incendis_similarity/bombers_arcgis_visor_context.csv`: resum tabular del visor Bombers.
- `../../metadata/incendis_similarity/similitud_condicions_incendi_cadi_metadata.json`: metode, fonts i limitacions.

## Fonts incorporades

- Perimetres oficials d'incendi WFS Generalitat.
- Origen de dades dels focs: `{metadata["official_fire_origin"]["data_source_detail"]}`; `{metadata["official_fire_origin"]["cause_legend"]}`.
- Habitats terrestres v3 WFS Generalitat, usats per vegetacio/habitat.
- DEM ICGC per altitud, pendent i orientacio.
- Accessos OSM/Overpass si el servei ha estat disponible: `{access_status}`.
- Bombers Generalitat `g2ay-3vnj` com a resum tabular comarcal, sense geometria.
- Visor oficial Bombers ArcGIS com a context operatiu puntual IV: `{bombers_arcgis_viewer_context["feature_count_context_5km"]}` registres en context 5 km, estat font `{bombers_arcgis_viewer_context["status"]}`.
- EFFIS/Copernicus DRF com a cataleg public de datasets disponibles per sol.licitud.

## Limitacio

No s'han incorporat fonts bloquejades, pendents o amb credencials: IncendisCAT, Pla Alfa, Meteocat/AEMET, Sentinel NDMI/NDVI i hidrologia/punts d'aigua. Bombers `g2ay-3vnj`, el visor ArcGIS de Bombers i EFFIS/Copernicus s'han incorporat com a context public, no com a geometria historica d'incendis ni com a variable del score. La font ICGC Cobertes del Sol esta verificada, pero no s'ha descarregat en WCS 1 m per tot l'ambit per evitar una carrega desproporcionada en aquesta sortida de treball.
"""
    (OUT_MAPS / "README.md").write_text(readme, encoding="utf-8")
    return metadata


def main() -> None:
    ensure_dirs()
    study = load_study_area()
    study_geom = study.geometry.union_all()
    fires = load_fire_perimeters(study)
    habitats = load_habitats(study)
    access, access_status = load_access(study)
    bombers_context = load_bombers_context()
    bombers_viewer, bombers_arcgis_viewer_context = load_bombers_arcgis_viewer_context(study)
    copernicus_context = load_copernicus_context()
    dem_path = read_or_download_dem(study)
    slope_path, aspect_path = derive_topography(dem_path)
    fires_enriched, grid = enrich_fire_and_grid(fires, habitats, access, dem_path, slope_path, aspect_path, study_geom)
    metadata = write_outputs(
        study,
        fires_enriched,
        habitats,
        access,
        bombers_viewer,
        dem_path,
        slope_path,
        aspect_path,
        grid,
        access_status,
        bombers_context,
        bombers_arcgis_viewer_context,
        copernicus_context,
    )
    print(json.dumps(
        {
            "status": metadata["status"],
            "study_area_ha": metadata["study_area_ha"],
            "official_fire_polygons_used": metadata["official_fire_polygons_used"],
            "official_fire_polygons_inside_strict_area": metadata["official_fire_polygons_inside_strict_area"],
            "official_fire_area_context_ha": metadata["official_fire_area_context_ha"],
            "access_status": metadata["access_status"],
            "bombers_context_actions": metadata["bombers_context"]["total_vegetation_fire_actions"],
            "bombers_arcgis_viewer_features": metadata["bombers_arcgis_viewer_context"]["feature_count_context_5km"],
            "copernicus_context_datasets": metadata["copernicus_context"]["dataset_codes"],
            "map": str(OUT_MAPS / "mapa_similitud_condicions_incendi_cadi.svg"),
            "metadata": str(OUT_META / "similitud_condicions_incendi_cadi_metadata.json"),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
