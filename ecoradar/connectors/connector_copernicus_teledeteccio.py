"""Copernicus teledetection connector for EcoRadar.

The connector is source-gated: Copernicus Data Space Sentinel Hub processing
requires OAuth client credentials. With credentials, it searches for a recent
low-cloud Sentinel-2 L2A summer scene over Alinya, requests NDVI, NDMI, NDWI and
NBR GeoTIFFs from the Processing API, clips them to the study area and writes
mandatory technical products. LST is mandatory as a real validated thermal
raster or equivalent; the connector must fail if it is not configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import argparse
import csv
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask

from ecoradar.sources.mandatory_copernicus import required_copernicus_outputs


PROJECT_ROOT = Path("projectes/Alinya")
STUDY_AREA_PATH = PROJECT_ROOT / "processed" / "study_area.gpkg"
RAW_DIR = PROJECT_ROOT / "raw" / "teledeteccio"
PROCESSED_DIR = PROJECT_ROOT / "processed" / "teledeteccio"
MAP_DIR = PROJECT_ROOT / "maps" / "teledeteccio"
SUMMARY_PATH = PROJECT_ROOT / "indicators" / "teledeteccio_resum.csv"
METADATA_PATH = PROJECT_ROOT / "metadata" / "teledeteccio_metadata.json"
STATS_PATH = PROJECT_ROOT / "metadata" / "teledeteccio_stats.json"
PERCENTILES_PATH = PROJECT_ROOT / "metadata" / "teledeteccio_percentiles.json"
CLASSIFICATION_PATH = PROJECT_ROOT / "metadata" / "teledeteccio_classification.json"
ECOLOGICAL_SUMMARY_PATH = PROJECT_ROOT / "metadata" / "teledeteccio_ecological_summary.json"
VALIDATION_PATH = PROJECT_ROOT / "metadata" / "validations" / "connector_copernicus_teledeteccio_validation.json"

TARGET_CRS = "EPSG:25831"
WGS84 = "EPSG:4326"
RESOLUTION_M = 20
MAX_CLOUD_COVER = 20

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
PUBLIC_STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
SOURCE_PAGE_URL = "https://dataspace.copernicus.eu/analyse/apis"

INDEX_DEFINITIONS: dict[str, dict[str, Any]] = {
    "ndvi": {
        "label": "NDVI",
        "description": "vigor i activitat fotosintètica de la vegetació",
        "breaks": [(-1.0, 0.2, "molt baix", (186, 190, 176)), (0.2, 0.4, "baix", (220, 197, 115)), (0.4, 0.6, "mitjà", (166, 194, 105)), (0.6, 0.8, "alt", (78, 143, 72)), (0.8, 1.0, "molt alt", (21, 89, 53))],
    },
    "ndmi": {
        "label": "NDMI",
        "description": "humitat de la vegetació i possible estrès hídric",
        "breaks": [(-1.0, -0.2, "molt sec", (179, 79, 58)), (-0.2, 0.0, "sec", (215, 147, 75)), (0.0, 0.2, "intermedi", (217, 200, 125)), (0.2, 0.4, "humit", (106, 168, 132)), (0.4, 1.0, "molt humit", (35, 104, 92))],
    },
    "ndwi": {
        "label": "NDWI",
        "description": "senyal d'aigua superficial o humitat associada",
        "breaks": [(-1.0, -0.3, "molt baix", (174, 133, 84)), (-0.3, 0.0, "baix", (218, 189, 113)), (0.0, 0.2, "intermedi", (161, 196, 173)), (0.2, 0.5, "alt", (79, 151, 178)), (0.5, 1.0, "molt alt", (35, 91, 138))],
    },
    "nbr": {
        "label": "NBR",
        "description": "estructura vegetada i senyal de severitat/alteració de coberta",
        "breaks": [(-1.0, 0.1, "molt baix", (120, 83, 65)), (0.1, 0.3, "baix", (194, 122, 79)), (0.3, 0.5, "mitjà", (219, 180, 103)), (0.5, 0.7, "alt", (111, 164, 95)), (0.7, 1.0, "molt alt", (41, 103, 65))],
    },
    "lst": {
        "label": "LST/equivalent",
        "description": "temperatura superficial o equivalent tèrmic validat",
        "breaks": [(-80.0, 15.0, "molt baixa", (61, 115, 145)), (15.0, 25.0, "baixa", (112, 163, 171)), (25.0, 35.0, "moderada", (218, 191, 116)), (35.0, 45.0, "alta", (211, 129, 76)), (45.0, 90.0, "molt alta", (157, 67, 67))],
    },
}


@dataclass(frozen=True)
class Credentials:
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class Scene:
    item_id: str
    capture_date: str
    cloud_cover: float | None


class MissingCredentials(RuntimeError):
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar Copernicus teledetection connector")
    parser.add_argument("--check", action="store_true", help="Validate local inputs and credential presence only")
    parser.add_argument("--start-date", help="ISO date. Defaults to the recent summer window.")
    parser.add_argument("--end-date", help="ISO date. Defaults to today.")
    args = parser.parse_args()

    try:
        result = run_connector(check_only=args.check, start_date=args.start_date, end_date=args.end_date)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except MissingCredentials as exc:
        print(f"connector_copernicus_teledeteccio blocked: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:
        print(f"connector_copernicus_teledeteccio failed: {exc}", file=sys.stderr)
        raise


def run_connector(
    *,
    check_only: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    _ensure_dirs()
    study_area = _load_study_area()
    start, end = _date_window(start_date, end_date)
    try:
        credentials = _load_credentials()
    except MissingCredentials as exc:
        public_scene, catalog_message = _try_public_stac_scene(study_area, start, end)
        status = "catalog_available_processing_requires_credentials" if public_scene else "blocked_requires_credentials"
        _write_blocked_metadata(study_area, start, end, str(exc), scene=public_scene, catalog_message=catalog_message)
        _write_validation_record(
            status=status,
            start=start,
            end=end,
            message=f"{catalog_message} {str(exc)}",
            outputs={},
            lst_status="not_available_until_operational_collection_mapping_is_configured",
            scene=public_scene,
        )
        return {
            "status": status,
            "study_area_path": str(STUDY_AREA_PATH),
            "metadata_path": str(METADATA_PATH),
            "start_date": start,
            "end_date": end,
            "credentials": "missing",
            "catalog_scene": public_scene.__dict__ if public_scene else None,
            "message": catalog_message,
            "required_credentials": ["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"],
            "lst": "not_available_until_operational_collection_mapping_is_configured",
        }

    if check_only:
        _write_validation_record(
            status="ready",
            start=start,
            end=end,
            message="Credentials are present; connector can attempt Copernicus Catalog and Processing API requests.",
            outputs={},
            lst_status="not_enabled_until_operational_collection_is_configured",
        )
        return {
            "status": "ready",
            "study_area_path": str(STUDY_AREA_PATH),
            "processed_dir": str(PROCESSED_DIR),
            "start_date": start,
            "end_date": end,
            "credentials": "present",
            "lst": "not_enabled_until_operational_collection_is_configured",
        }

    token = _get_access_token(credentials)
    scene = _search_sentinel2_scene(token, study_area, start, end)
    rows: list[dict[str, Any]] = []
    outputs: dict[str, str] = {}
    stats_payload: dict[str, Any] = {}
    percentiles_payload: dict[str, Any] = {}
    classification_payload: dict[str, Any] = {}
    ecological_payload: dict[str, Any] = {}

    try:
        for index_name, evalscript in _sentinel2_evalscripts().items():
            raw_path = RAW_DIR / f"{index_name}_{scene.capture_date}.tif"
            processed_path = PROCESSED_DIR / f"{index_name}.tif"
            if not raw_path.exists():
                payload = _build_process_payload(study_area, evalscript, scene.capture_date)
                _post_json_to_file(PROCESS_URL, token, payload, raw_path)
            summary = _clip_and_summarize(raw_path, processed_path, study_area, index_name)
            rows.append(_summary_row(index_name, summary, scene))
            stats_payload[index_name] = summary["stats"]
            percentiles_payload[index_name] = summary["percentiles"]
            classification_payload[index_name] = summary["classification"]
            ecological_payload[index_name] = summary["ecological_summary"]
            outputs[index_name] = str(processed_path)
            outputs[f"{index_name}_map"] = str(MAP_DIR / f"{index_name}.png")

        lst_status = _process_lst_equivalent(study_area, scene, rows, outputs, stats_payload, percentiles_payload, classification_payload, ecological_payload)
        _write_summary(rows)
        _write_sidecar_jsons(stats_payload, percentiles_payload, classification_payload, ecological_payload, scene)
        outputs.update(
            {
                "summary": str(SUMMARY_PATH),
                "stats": str(STATS_PATH),
                "percentiles": str(PERCENTILES_PATH),
                "classification": str(CLASSIFICATION_PATH),
                "ecological_summary": str(ECOLOGICAL_SUMMARY_PATH),
            }
        )
        metadata = _write_metadata(
            study_area=study_area,
            scene=scene,
            start=start,
            end=end,
            outputs=outputs,
            lst_status=lst_status,
        )
        outputs["metadata"] = str(METADATA_PATH)
        _write_validation_record(
            status="completed",
            start=start,
            end=end,
            message="NDVI, NDMI, NDWI, NBR and LST/equivalent products were generated from real validated inputs.",
            outputs=outputs,
            lst_status=lst_status,
            scene=scene,
        )
    except Exception as exc:
        _write_validation_record(
            status="failed",
            start=start,
            end=end,
            message=str(exc),
            outputs=outputs,
            lst_status="failed_or_missing",
            scene=scene,
        )
        raise

    return {
        "status": "completed",
        "processed_dir": str(PROCESSED_DIR),
        "summary_path": str(SUMMARY_PATH),
        "metadata_path": str(METADATA_PATH),
        "scene": scene.__dict__,
        "outputs": outputs,
        "metadata": metadata,
    }


def _ensure_dirs() -> None:
    for directory in (RAW_DIR, PROCESSED_DIR, MAP_DIR, SUMMARY_PATH.parent, METADATA_PATH.parent, VALIDATION_PATH.parent):
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


def _date_window(start_date: str | None, end_date: str | None) -> tuple[str, str]:
    today = date.today()
    end = _parse_date(end_date) if end_date else today
    if start_date:
        start = _parse_date(start_date)
    else:
        summer_start = date(end.year, 6, 1)
        start = summer_start if end >= summer_start else date(end.year - 1, 6, 1)
    if start > end:
        raise ValueError(f"Invalid date range: {start.isoformat()} is after {end.isoformat()}")
    return start.isoformat(), end.isoformat()


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _load_credentials() -> Credentials:
    client_id = os.environ.get("COPERNICUS_CLIENT_ID") or os.environ.get("SH_CLIENT_ID")
    client_secret = os.environ.get("COPERNICUS_CLIENT_SECRET") or os.environ.get("SH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise MissingCredentials(
            "set COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET from a Copernicus Data Space Sentinel Hub OAuth client"
        )
    return Credentials(client_id=client_id, client_secret=client_secret)


def _get_access_token(credentials: Credentials) -> str:
    body = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Copernicus token response did not include access_token")
    return str(token)


def _search_sentinel2_scene(token: str, study_area: gpd.GeoDataFrame, start: str, end: str) -> Scene:
    geometry = study_area.to_crs(WGS84).geometry.union_all().__geo_interface__
    payload = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "intersects": geometry,
        "limit": 50,
        "query": {"eo:cloud_cover": {"lte": MAX_CLOUD_COVER}},
    }
    request = Request(
        CATALOG_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(_http_error_text(exc)) from exc

    features = result.get("features", [])
    if not features:
        raise RuntimeError(f"No Sentinel-2 L2A scene found for {start} to {end} with cloud cover <= {MAX_CLOUD_COVER}%")
    features = sorted(features, key=lambda item: (item.get("properties", {}).get("eo:cloud_cover", 999), item.get("properties", {}).get("datetime", "")))
    selected = features[0]
    props = selected.get("properties", {})
    capture = str(props.get("datetime", ""))[:10]
    cloud = props.get("eo:cloud_cover")
    return Scene(item_id=str(selected.get("id", "")), capture_date=capture, cloud_cover=float(cloud) if cloud is not None else None)


def _try_public_stac_scene(study_area: gpd.GeoDataFrame, start: str, end: str) -> tuple[Scene | None, str]:
    """Query the official public CDSE STAC catalogue without downloading bands."""

    geometry_bounds = study_area.to_crs(WGS84).total_bounds
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [float(value) for value in geometry_bounds],
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": 20,
        "query": {"eo:cloud_cover": {"lte": MAX_CLOUD_COVER}},
    }
    request = Request(
        PUBLIC_STAC_SEARCH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return None, (
            "Copernicus public STAC catalogue could not be queried without credentials "
            f"({type(exc).__name__}: {exc})."
        )

    features = result.get("features", [])
    if not features:
        return None, (
            f"Copernicus public STAC catalogue was reachable, but no Sentinel-2 L2A scene "
            f"was found for {start} to {end} with cloud cover <= {MAX_CLOUD_COVER}%."
        )

    features = sorted(
        features,
        key=lambda item: (
            item.get("properties", {}).get("eo:cloud_cover", 999),
            item.get("properties", {}).get("datetime", ""),
        ),
    )
    selected = features[0]
    props = selected.get("properties", {})
    capture = str(props.get("datetime", ""))[:10]
    cloud = props.get("eo:cloud_cover")
    scene = Scene(
        item_id=str(selected.get("id", "")),
        capture_date=capture,
        cloud_cover=float(cloud) if cloud is not None else None,
    )
    return scene, (
        "Copernicus public STAC catalogue is reachable and has a candidate Sentinel-2 L2A "
        f"scene for the study area ({scene.item_id}, {scene.capture_date}, cloud cover {scene.cloud_cover}%). "
        "Band assets still require authorized HTTPS/S3 or Sentinel Hub processing credentials."
    )


def _build_process_payload(study_area: gpd.GeoDataFrame, evalscript: str, capture_date: str) -> dict[str, Any]:
    geometry = study_area.to_crs(TARGET_CRS).geometry.union_all().__geo_interface__
    bounds = [float(value) for value in study_area.total_bounds]
    width = max(1, int(np.ceil((bounds[2] - bounds[0]) / RESOLUTION_M)))
    height = max(1, int(np.ceil((bounds[3] - bounds[1]) / RESOLUTION_M)))
    return {
        "input": {
            "bounds": {
                "geometry": geometry,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/25831"},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{capture_date}T00:00:00Z",
                            "to": f"{capture_date}T23:59:59Z",
                        },
                        "maxCloudCoverage": MAX_CLOUD_COVER,
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
        },
        "evalscript": evalscript,
    }


def _post_json_to_file(url: str, token: str, payload: dict[str, Any], output_path: Path) -> None:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/tiff",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=240) as response:
            data = response.read()
    except HTTPError as exc:
        raise RuntimeError(_http_error_text(exc)) from exc
    if data.lstrip().startswith(b"{") or data.lstrip().startswith(b"<"):
        raise RuntimeError(data[:1000].decode("utf-8", "ignore"))
    output_path.write_bytes(data)


def _clip_and_summarize(raw_path: Path, processed_path: Path, study_area: gpd.GeoDataFrame, index_name: str) -> dict[str, Any]:
    with rasterio.open(raw_path) as dataset:
        mask_area = study_area.to_crs(dataset.crs) if dataset.crs else study_area
        geometries = [geom for geom in mask_area.geometry if geom is not None and not geom.is_empty]
        clipped, transform = mask(dataset, geometries, crop=True, filled=False)
        metadata = dataset.meta.copy()
    band = clipped[0].astype("float32")
    data = np.asarray(band.filled(np.nan), dtype="float32")
    data[~np.isfinite(data)] = np.nan

    metadata.update(
        {
            "driver": "GTiff",
            "height": data.shape[0],
            "width": data.shape[1],
            "count": 1,
            "dtype": "float32",
            "transform": transform,
            "nodata": np.nan,
            "compress": "deflate",
        }
    )
    with rasterio.open(processed_path, "w", **metadata) as destination:
        destination.write(data, 1)

    valid = data[np.isfinite(data)]
    if valid.size == 0:
        summary = {
            "stats": {"mean": None, "min": None, "max": None, "std": None, "valid_pixel_count": 0},
            "percentiles": {},
            "classification": {},
            "ecological_summary": "No hi ha píxels vàlids dins l'àrea d'estudi.",
        }
    else:
        percentiles = {
            f"p{percentile}": round(float(np.nanpercentile(valid, percentile)), 6)
            for percentile in (5, 10, 25, 50, 75, 90, 95)
        }
        classification = _classification_summary(valid, index_name)
        summary = {
            "stats": {
                "mean": round(float(np.nanmean(valid)), 6),
                "min": round(float(np.nanmin(valid)), 6),
                "max": round(float(np.nanmax(valid)), 6),
                "std": round(float(np.nanstd(valid)), 6),
                "valid_pixel_count": int(valid.size),
            },
            "percentiles": percentiles,
            "classification": classification,
            "ecological_summary": _ecological_summary(index_name, classification, percentiles),
        }
    _write_index_map(data, MAP_DIR / f"{index_name}.png", index_name)
    return summary


def _process_lst_equivalent(
    study_area: gpd.GeoDataFrame,
    scene: Scene,
    rows: list[dict[str, Any]],
    outputs: dict[str, str],
    stats_payload: dict[str, Any],
    percentiles_payload: dict[str, Any],
    classification_payload: dict[str, Any],
    ecological_payload: dict[str, Any],
) -> str:
    source = os.environ.get("ECORADAR_LST_RASTER_PATH") or os.environ.get("COPERNICUS_LST_RASTER_PATH")
    if not source:
        raise RuntimeError(
            "Mandatory LST/equivalent is not configured. Set ECORADAR_LST_RASTER_PATH to a real validated "
            "Copernicus/thermal raster before EcoRadar Core can run."
        )
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Configured LST/equivalent raster does not exist: {source_path}")
    processed_path = PROCESSED_DIR / "lst.tif"
    summary = _clip_and_summarize(source_path, processed_path, study_area, "lst")
    rows.append(_summary_row("lst", summary, scene))
    stats_payload["lst"] = summary["stats"]
    percentiles_payload["lst"] = summary["percentiles"]
    classification_payload["lst"] = summary["classification"]
    ecological_payload["lst"] = summary["ecological_summary"]
    outputs["lst"] = str(processed_path)
    outputs["lst_map"] = str(MAP_DIR / "lst.png")
    return f"completed_from_validated_raster:{source_path}"


def _summary_row(index_name: str, summary: dict[str, Any], scene: Scene) -> dict[str, Any]:
    stats = summary["stats"]
    percentiles = summary["percentiles"]
    classification = summary["classification"]
    dominant_class = classification.get("dominant_class")
    return {
        "index": index_name,
        "mean": stats.get("mean"),
        "min": stats.get("min"),
        "max": stats.get("max"),
        "std": stats.get("std"),
        "p05": percentiles.get("p5"),
        "p10": percentiles.get("p10"),
        "p25": percentiles.get("p25"),
        "p50": percentiles.get("p50"),
        "p75": percentiles.get("p75"),
        "p90": percentiles.get("p90"),
        "p95": percentiles.get("p95"),
        "dominant_class": dominant_class,
        "valid_pixel_count": stats.get("valid_pixel_count"),
        "image_date": scene.capture_date,
        "cloud_cover_percent": scene.cloud_cover,
        "ecological_summary": summary["ecological_summary"],
    }


def _write_summary(rows: list[dict[str, Any]]) -> None:
    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "index",
                "mean",
                "min",
                "max",
                "std",
                "p05",
                "p10",
                "p25",
                "p50",
                "p75",
                "p90",
                "p95",
                "dominant_class",
                "valid_pixel_count",
                "image_date",
                "cloud_cover_percent",
                "ecological_summary",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_sidecar_jsons(
    stats: dict[str, Any],
    percentiles: dict[str, Any],
    classification: dict[str, Any],
    ecological_summary: dict[str, Any],
    scene: Scene,
) -> None:
    base = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scene": scene.__dict__,
        "indices": list(INDEX_DEFINITIONS),
    }
    STATS_PATH.write_text(json.dumps({**base, "stats": stats}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PERCENTILES_PATH.write_text(json.dumps({**base, "percentiles": percentiles}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CLASSIFICATION_PATH.write_text(json.dumps({**base, "classification": classification}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ECOLOGICAL_SUMMARY_PATH.write_text(json.dumps({**base, "ecological_summary": ecological_summary}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _classification_summary(valid: np.ndarray, index_name: str) -> dict[str, Any]:
    breaks = INDEX_DEFINITIONS[index_name]["breaks"]
    total = int(valid.size)
    classes = []
    for low, high, label, _color in breaks:
        count = int(np.count_nonzero((valid >= low) & (valid < high)))
        classes.append({"class": label, "from": low, "to": high, "pixel_count": count, "percent": round(count / total * 100, 2) if total else 0.0})
    dominant = max(classes, key=lambda item: item["pixel_count"]) if classes else None
    return {
        "classes": classes,
        "dominant_class": dominant["class"] if dominant else None,
        "dominant_percent": dominant["percent"] if dominant else None,
    }


def _ecological_summary(index_name: str, classification: dict[str, Any], percentiles: dict[str, Any]) -> str:
    definition = INDEX_DEFINITIONS[index_name]
    dominant = classification.get("dominant_class") or "sense classe dominant"
    median = percentiles.get("p50")
    return (
        f"{definition['label']} indica principalment {definition['description']}; "
        f"la classe dominant és '{dominant}' i la mediana validada és {median}."
    )


def _write_index_map(data: np.ndarray, path: Path, index_name: str) -> None:
    breaks = INDEX_DEFINITIONS[index_name]["breaks"]
    rgb = np.full((3, data.shape[0], data.shape[1]), 245, dtype="uint8")
    valid = np.isfinite(data)
    for low, high, _label, color in breaks:
        mask_class = valid & (data >= low) & (data < high)
        for band, channel in enumerate(color):
            rgb[band][mask_class] = channel
    with rasterio.open(path, "w", driver="PNG", height=data.shape[0], width=data.shape[1], count=3, dtype="uint8") as dataset:
        dataset.write(rgb)


def _write_metadata(
    *,
    study_area: gpd.GeoDataFrame,
    scene: Scene,
    start: str,
    end: str,
    outputs: dict[str, str],
    lst_status: str,
) -> dict[str, Any]:
    metadata = {
        "project": "Alinya",
        "status": "completed",
        "source": "Copernicus Data Space Ecosystem / Sentinel Hub",
        "url": SOURCE_PAGE_URL,
        "products_used": ["Sentinel-2 L2A", "validated LST/equivalent raster"],
        "derived_products": ["NDVI", "NDMI", "NDWI", "NBR", "LST/equivalent"],
        "query_date": datetime.now(timezone.utc).isoformat(),
        "capture_date": scene.capture_date,
        "scene_id": scene.item_id,
        "spatial_resolution_m": RESOLUTION_M,
        "crs": TARGET_CRS,
        "cloud_cover_percent": scene.cloud_cover,
        "date_window": {"start": start, "end": end},
        "outputs": outputs,
        "lst_status": lst_status,
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
        "limitations": [
            "Requires Copernicus Data Space Sentinel Hub OAuth credentials.",
            "NDVI, NDMI, NDWI and NBR are standard spectral products derived from Sentinel-2 L2A bands through the Processing API.",
            "Cloud filtering uses catalogue cloud cover and Sentinel Hub least-cloud mosaicking; local cloud masks should be refined in a later Analysis Engine step.",
            "LST/equivalent must come from a real validated thermal raster; the connector does not synthesize temperature from Sentinel-2 bands.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def _write_blocked_metadata(
    study_area: gpd.GeoDataFrame,
    start: str,
    end: str,
    reason: str,
    *,
    scene: Scene | None = None,
    catalog_message: str | None = None,
) -> dict[str, Any]:
    status = "catalog_available_processing_requires_credentials" if scene else "blocked_requires_credentials"
    metadata = {
        "project": "Alinya",
        "status": status,
        "source": "Copernicus Data Space Ecosystem / Sentinel Hub",
        "url": SOURCE_PAGE_URL,
        "public_stac_url": PUBLIC_STAC_SEARCH_URL,
        "products_planned": ["Sentinel-2 L2A NDVI", "Sentinel-2 L2A NDMI", "Sentinel-2 L2A NDWI", "Sentinel-2 L2A NBR", "LST/equivalent"],
        "lst_status": "not_available_until_operational_collection_mapping_is_configured",
        "query_date": datetime.now(timezone.utc).isoformat(),
        "capture_date": scene.capture_date if scene else None,
        "scene_id": scene.item_id if scene else None,
        "spatial_resolution_m": RESOLUTION_M,
        "crs": TARGET_CRS,
        "cloud_cover_percent": scene.cloud_cover if scene else None,
        "date_window": {"start": start, "end": end},
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
        "required_credentials": ["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"],
        "blocker": reason,
        "catalog_status": catalog_message or "No public STAC catalogue status was recorded.",
        "limitations": [
            "The official public STAC catalogue can identify candidate Sentinel-2 L2A scenes without creating NDVI, NDMI, NDWI or NBR.",
            "No raster was downloaded because Copernicus Data Space Sentinel Hub OAuth credentials or authorized product download credentials are not configured.",
            "The connector must not create placeholder GeoTIFFs, maps or summary statistics without real validated inputs.",
            "LST/equivalent requires a real validated thermal raster before EcoRadar Core can run.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def _write_validation_record(
    *,
    status: str,
    start: str,
    end: str,
    message: str,
    outputs: dict[str, str],
    lst_status: str,
    scene: Scene | None = None,
) -> dict[str, Any]:
    expected_outputs = {
        relative: str(PROJECT_ROOT / relative)
        for relative in required_copernicus_outputs()
    }
    record = {
        "connector": "connector_copernicus_teledeteccio",
        "project": "Alinya",
        "validated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "can_advance_to_next_connector": status == "completed",
        "source": "Copernicus Data Space Ecosystem / Sentinel Hub",
        "official_documentation": {
            "authentication": "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html",
            "catalog_api": "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Catalog.html",
            "processing_api": "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process.html",
        },
        "products_requested": ["Sentinel-2 L2A NDVI", "Sentinel-2 L2A NDMI", "Sentinel-2 L2A NDWI", "Sentinel-2 L2A NBR", "LST/equivalent"],
        "date_window": {"start": start, "end": end},
        "required_credentials": ["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"],
        "message": message,
        "lst_status": lst_status,
        "scene": scene.__dict__ if scene else None,
        "expected_outputs": expected_outputs,
        "created_outputs": outputs,
        "missing_outputs": [
            path
            for path in expected_outputs.values()
            if not Path(path).exists()
        ],
        "validation_rule": "Do not generate NDVI, NDMI, NDWI, NBR, LST/equivalent, maps or summary statistics without real validated inputs.",
    }
    VALIDATION_PATH.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def _sentinel2_evalscripts() -> dict[str, str]:
    return {
        "ndvi": _evalscript("(B08 - B04) / (B08 + B04)"),
        "ndmi": _evalscript("(B08 - B11) / (B08 + B11)"),
        "ndwi": _evalscript("(B03 - B08) / (B03 + B08)"),
        "nbr": _evalscript("(B08 - B12) / (B08 + B12)"),
    }


def _evalscript(expression: str) -> str:
    return f"""//VERSION=3
function setup() {{
  return {{
    input: [{{ bands: ["B03", "B04", "B08", "B11", "B12", "dataMask"], units: "REFLECTANCE" }}],
    output: {{ bands: 1, sampleType: "FLOAT32" }}
  }};
}}

function evaluatePixel(sample) {{
  if (sample.dataMask === 0) {{
    return [NaN];
  }}
  let value = {expression};
  if (!isFinite(value)) {{
    return [NaN];
  }}
  return [value];
}}
"""


def _http_error_text(exc: HTTPError) -> str:
    body = exc.read().decode("utf-8", "ignore")
    return f"HTTP {exc.code}: {body[:1000]}"


if __name__ == "__main__":
    main()
