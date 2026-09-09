"""Download and normalize Sentinel-2 L2A bands from the official CDSE APIs.

This connector only selects a verified scene, downloads source bands through
the authenticated Sentinel Hub Process API and normalizes them into one
GeoTIFF. Indicator calculations live in the analysis script.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pyproj import Transformer
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely.ops import transform as shapely_transform
from shapely.geometry import box, shape


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
RAW = PROJECT / "raw" / "sentinel2_cdse"
PROCESSED = PROJECT / "processed" / "sentinel2_cdse"
METADATA = PROJECT / "metadata" / "sentinel2_cdse_connector.json"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"

STAC_SEARCH = "https://stac.dataspace.copernicus.eu/v1/search"
TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
TARGET_CRS = "EPSG:32631"
RESOLUTION_M = 10
BANDS = ["B02", "B04", "B08", "B11", "B12", "SCL", "dataMask"]
SCOPE = "core"
STUDY_GEOMETRY_PROVIDER = None


def _configure_scope(scope: str) -> None:
    global SCOPE, RAW, PROCESSED, METADATA
    SCOPE = scope
    if scope == "expanded":
        RAW = PROJECT / "raw" / "sentinel2_cdse_expanded"
        PROCESSED = PROJECT / "processed" / "sentinel2_cdse_expanded"
        METADATA = PROJECT / "metadata" / "sentinel2_cdse_expanded_connector.json"


def _parse_utc(value: str) -> datetime:
    normalized = value[:-1] if value.endswith("Z") else value
    for pattern in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(normalized, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _json_request(url: str, *, data: bytes | None = None, headers: dict | None = None) -> dict:
    request = Request(url, data=data, headers=headers or {})
    try:
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read())
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Official API request failed ({error.code}): {body[:800]}") from error


def _study_bbox() -> tuple[float, float, float, float]:
    manifest = json.loads(PROJECT_MANIFEST.read_text())
    key = "expanded_urban_bbox_epsg4326" if SCOPE == "expanded" else "analysis_core_bbox_epsg4326"
    return tuple(float(value) for value in manifest["study_area"][key])


def _target_grid(bbox4326: tuple[float, float, float, float]):
    transformer = Transformer.from_crs(4326, 32631, always_xy=True)
    coordinates = [
        transformer.transform(x, y)
        for x in (bbox4326[0], bbox4326[2])
        for y in (bbox4326[1], bbox4326[3])
    ]
    minx = math.floor(min(x for x, _ in coordinates) / RESOLUTION_M) * RESOLUTION_M
    miny = math.floor(min(y for _, y in coordinates) / RESOLUTION_M) * RESOLUTION_M
    maxx = math.ceil(max(x for x, _ in coordinates) / RESOLUTION_M) * RESOLUTION_M
    maxy = math.ceil(max(y for _, y in coordinates) / RESOLUTION_M) * RESOLUTION_M
    width = int(round((maxx - minx) / RESOLUTION_M))
    height = int(round((maxy - miny) / RESOLUTION_M))
    return (minx, miny, maxx, maxy), width, height


def _search_scene(bbox4326, start: str, end: str, max_cloud: float) -> tuple[dict, str]:
    parameters = {
        "collections": "sentinel-2-l2a",
        "bbox": ",".join(str(value) for value in bbox4326),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": 100,
    }
    query_url = STAC_SEARCH + "?" + urlencode(parameters)
    payload = _json_request(query_url)
    aoi = box(*bbox4326)
    candidates = []
    for feature in payload.get("features", []):
        cloud = feature.get("properties", {}).get("eo:cloud_cover")
        geometry = feature.get("geometry")
        if cloud is None or cloud > max_cloud or not geometry:
            continue
        footprint = shape(geometry)
        if footprint.covers(aoi):
            candidates.append(feature)
    if not candidates:
        raise RuntimeError(
            "No official Sentinel-2 L2A scene fully covering the analysis area "
            f"was found between {start} and {end} with cloud cover <= {max_cloud}%."
        )
    candidates.sort(
        key=lambda item: (
            -_parse_utc(item["properties"]["datetime"]).timestamp(),
            float(item["properties"].get("eo:cloud_cover", 100)),
        )
    )
    return candidates[0], query_url


def _search_scenes_catalog(token: str, bbox4326, start: str, end: str, max_cloud: float) -> tuple[list[dict], dict]:
    search = {
        "collections": ["sentinel-2-l2a"],
        "bbox": list(bbox4326),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": 100,
    }
    payload = _json_request(
        CATALOG_URL,
        data=json.dumps(search).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    aoi = box(*bbox4326)
    candidates = []
    for feature in payload.get("features", []):
        cloud = feature.get("properties", {}).get("eo:cloud_cover")
        geometry = feature.get("geometry")
        if cloud is None or cloud > max_cloud or not geometry:
            continue
        if shape(geometry).covers(aoi):
            candidates.append(feature)
    if not candidates:
        raise RuntimeError(
            "The authenticated CDSE Catalog API returned no Sentinel-2 L2A scene "
            f"fully covering the area between {start} and {end} with cloud <= {max_cloud}%."
        )
    candidates.sort(
        key=lambda item: (
            -_parse_utc(item["properties"]["datetime"]).timestamp(),
            float(item["properties"].get("eo:cloud_cover", 100)),
        )
    )
    return candidates, search


def _scope_mask(profile: dict, bbox4326: tuple[float, float, float, float]):
    if STUDY_GEOMETRY_PROVIDER is not None:
        geometries = STUDY_GEOMETRY_PROVIDER(profile["crs"])
    else:
        transformer = Transformer.from_crs(4326, profile["crs"], always_xy=True)
        geometries = [shapely_transform(transformer.transform, box(*bbox4326))]
    return geometry_mask(
        [geometry.__geo_interface__ for geometry in geometries if geometry is not None],
        out_shape=(profile["height"], profile["width"]),
        transform=profile["transform"],
        invert=True,
    )


def _quality_metrics(path: Path, bbox4326: tuple[float, float, float, float]) -> dict:
    with rasterio.open(path) as source:
        scl, data_mask = source.read()
        scope = _scope_mask(source.profile, bbox4326)
    scope_pixels = int(scope.sum())
    scl = scl.round().astype("uint8")
    valid = scope & (data_mask > 0) & np.isin(scl, [4, 5, 6])
    valid_pixels = int(valid.sum())
    return {
        "scope_pixels": scope_pixels,
        "valid_aoi_pixels": valid_pixels,
        "valid_aoi_coverage_pct": round(100.0 * valid_pixels / max(scope_pixels, 1), 2),
        "invalid_or_masked_aoi_pixels": scope_pixels - valid_pixels,
        "accepted_scl_classes": [4, 5, 6],
    }


def _archive_existing(normalized_path: Path) -> None:
    if not METADATA.exists() or not normalized_path.exists():
        return
    existing = json.loads(METADATA.read_text(encoding="utf-8"))
    scene_id = str(existing.get("scene_id") or "unknown_scene")
    archive = PROJECT / "history" / "sentinel2" / scene_id
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(normalized_path, archive / normalized_path.name)
    shutil.copy2(METADATA, archive / "connector_metadata.json")


def _token(client_id: str, client_secret: str) -> str:
    body = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode()
    payload = _json_request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("CDSE OAuth response did not contain an access token.")
    return access_token


def _process_request(token: str, payload: dict, destination: Path) -> str:
    request = Request(
        PROCESS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/tiff",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=300) as response:
            content = response.read()
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"CDSE Process API failed ({error.code}): {body[:1200]}") from error
    destination.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _payload(bounds, width, height, acquired_at: str, evalscript: str, *, resampling: str) -> dict:
    acquired = _parse_utc(acquired_at)
    start = (acquired - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    end = (acquired + timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    return {
        "input": {
            "bounds": {
                "bbox": list(bounds),
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/32631"},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": start, "to": end},
                        "mosaickingOrder": "leastCC",
                        "maxCloudCoverage": 100,
                    },
                    "processing": {"upsampling": resampling, "downsampling": resampling},
                }
            ],
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [
                {"identifier": "default", "format": {"type": "image/tiff"}}
            ],
        },
        "evalscript": evalscript,
    }


SPECTRAL_EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["B02", "B04", "B08", "B11", "B12"], units: "REFLECTANCE"}],
    output: {bands: 5, sampleType: "FLOAT32"}
  };
}
function evaluatePixel(s) { return [s.B02, s.B04, s.B08, s.B11, s.B12]; }
"""

MASK_EVALSCRIPT = """//VERSION=3
function setup() {
  return {input: ["SCL", "dataMask"], output: {bands: 2, sampleType: "UINT8"}};
}
function evaluatePixel(s) { return [s.SCL, s.dataMask]; }
"""


def _credentials(credentials_file: str | None) -> tuple[str | None, str | None]:
    client_id = os.getenv("COPERNICUS_CLIENT_ID")
    client_secret = os.getenv("COPERNICUS_CLIENT_SECRET")
    if credentials_file:
        payload = json.loads(Path(credentials_file).read_text())
        client_id = payload.get("client_id")
        client_secret = payload.get("client_secret")
    return client_id, client_secret


def fetch(
    start: str,
    end: str,
    max_cloud: float,
    credentials_file: str | None = None,
    *,
    max_candidates: int = 8,
    minimum_aoi_coverage_pct: float = 85.0,
) -> dict:
    client_id, client_secret = _credentials(credentials_file)
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing CDSE OAuth credentials. Set COPERNICUS_CLIENT_ID and "
            "COPERNICUS_CLIENT_SECRET from a personal OAuth client created in "
            "the Copernicus Data Space Sentinel Hub dashboard."
        )

    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    bbox4326 = _study_bbox()
    bounds, width, height = _target_grid(bbox4326)
    token = _token(client_id, client_secret)
    candidates, catalog_query = _search_scenes_catalog(token, bbox4326, start, end, max_cloud)
    normalized_path = PROCESSED / "sentinel2_l2a_reflectance_quality.tif"
    evaluated = []
    for scene in candidates[:max_candidates]:
        scene_id = scene["id"]
        acquired_at = scene["properties"]["datetime"]
        mask_path = RAW / f"{scene_id}_quality.tif"
        mask_hash = _process_request(
            token,
            _payload(bounds, width, height, acquired_at, MASK_EVALSCRIPT, resampling="NEAREST"),
            mask_path,
        )
        evaluated.append({
            "feature": scene,
            "mask_path": mask_path,
            "mask_sha256": mask_hash,
            **_quality_metrics(mask_path, bbox4326),
        })
    valid_candidates = [item for item in evaluated if item["valid_aoi_coverage_pct"] >= minimum_aoi_coverage_pct]
    if not valid_candidates:
        best = max(evaluated, key=lambda item: item["valid_aoi_coverage_pct"], default=None)
        best_text = f"; best candidate covered {best['valid_aoi_coverage_pct']}%" if best else ""
        raise RuntimeError(
            "No recent Sentinel-2 L2A scene met the minimum actual SCL/dataMask "
            f"coverage of {minimum_aoi_coverage_pct}% inside the study polygon{best_text}."
        )
    valid_candidates.sort(
        key=lambda item: (
            -_parse_utc(item["feature"]["properties"]["datetime"]).timestamp(),
            -float(item["valid_aoi_coverage_pct"]),
            float(item["feature"]["properties"].get("eo:cloud_cover", 100)),
        )
    )
    selected = valid_candidates[0]
    scene = selected["feature"]
    scene_id = scene["id"]
    acquired_at = scene["properties"]["datetime"]
    if METADATA.exists() and normalized_path.exists():
        existing = json.loads(METADATA.read_text(encoding="utf-8"))
        if existing.get("scene_id") == scene_id:
            record = {
                **existing,
                "updated": False,
                "latest_catalog_check_utc": datetime.now(timezone.utc).isoformat(),
                "candidate_evaluations": [
                    {key: item[key] for key in ("valid_aoi_coverage_pct", "valid_aoi_pixels", "scope_pixels")}
                    | {
                        "scene_id": item["feature"]["id"],
                        "acquired_at_utc": item["feature"]["properties"]["datetime"],
                        "scene_cloud_cover_pct": item["feature"]["properties"].get("eo:cloud_cover"),
                    }
                    for item in evaluated
                ],
            }
            METADATA.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
            return record

    _archive_existing(normalized_path)
    spectral_path = RAW / f"{scene_id}_reflectance.tif"
    mask_path = selected["mask_path"]
    spectral_hash = _process_request(
        token,
        _payload(bounds, width, height, acquired_at, SPECTRAL_EVALSCRIPT, resampling="BILINEAR"),
        spectral_path,
    )
    mask_hash = selected["mask_sha256"]

    with rasterio.open(spectral_path) as spectral, rasterio.open(mask_path) as quality:
        if (spectral.width, spectral.height) != (quality.width, quality.height):
            raise RuntimeError("CDSE spectral and quality rasters have different grids.")
        data = spectral.read()
        masks = quality.read()
        if int((masks[1] > 0).sum()) < 100:
            raise RuntimeError(
                "The selected CDSE scene returned fewer than 100 valid pixels in the "
                "analysis area. Select an earlier lower-cloud acquisition instead of "
                "relaxing the quality mask."
            )
        profile = spectral.profile.copy()
        profile.update(driver="GTiff", count=7, dtype="float32", nodata=-9999.0, compress="deflate")
        with rasterio.open(normalized_path, "w", **profile) as target:
            target.write(data.astype("float32"), indexes=[1, 2, 3, 4, 5])
            target.write(masks.astype("float32"), indexes=[6, 7])
            for index, name in enumerate(BANDS, start=1):
                target.set_band_description(index, name)

    record = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "connector": "cdse_sentinel_hub_sentinel2_l2a",
        "responsibility": "select_download_and_normalize_only",
        "source": "Copernicus Sentinel-2 MSI Level-2A",
        "organization": "European Commission / ESA, Copernicus Data Space Ecosystem",
        "official_urls": {
            "stac": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
            "process_api": PROCESS_URL,
            "authentication": "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html",
        },
        "service_type": "public STAC selection + OAuth2 Client Credentials + Process API",
        "format": "GeoTIFF FLOAT32",
        "crs": TARGET_CRS,
        "resolution_m": RESOLUTION_M,
        "bands": BANDS,
        "native_resolution_m": {"B02": 10, "B04": 10, "B08": 10, "B11": 20, "B12": 20, "SCL": 20},
        "normalization": "Sentinel Hub returns bottom-of-atmosphere reflectance FLOAT32; SCL and dataMask are requested separately with nearest-neighbour resampling.",
        "spectral_units": "bottom-of-atmosphere reflectance",
        "scene_id": scene_id,
        "acquired_at_utc": acquired_at,
        "scene_cloud_cover_pct": scene["properties"].get("eo:cloud_cover"),
        "actual_aoi_qa": {
            key: selected[key]
            for key in ("scope_pixels", "valid_aoi_pixels", "valid_aoi_coverage_pct", "invalid_or_masked_aoi_pixels", "accepted_scl_classes")
        },
        "selection_rule": (
            "Evaluate up to the eight newest footprint-covering scenes with the actual "
            "SCL/dataMask pixels inside the study polygon; require at least "
            f"{minimum_aoi_coverage_pct}% valid coverage, then select the newest qualifying scene."
        ),
        "candidate_evaluations": [
            {key: item[key] for key in ("valid_aoi_coverage_pct", "valid_aoi_pixels", "scope_pixels")}
            | {
                "scene_id": item["feature"]["id"],
                "acquired_at_utc": item["feature"]["properties"]["datetime"],
                "scene_cloud_cover_pct": item["feature"]["properties"].get("eo:cloud_cover"),
                "selected": item is selected,
            }
            for item in evaluated
        ],
        "study_bbox_epsg4326": bbox4326,
        "target_bounds_epsg32631": bounds,
        "width": width,
        "height": height,
        "update_frequency": "Sentinel-2 nominal revisit approximately 5 days; this output is scene-based",
        "license": "Copernicus Sentinel data are free, full and open under the Copernicus data policy",
        "connector_status": "verified",
        "updated": True,
        "credentials": {
            "required": True,
            "flow": "OAuth2 client_credentials",
            "environment_variables": ["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"],
            "secrets_persisted": False,
        },
        "catalog_query": catalog_query,
        "raw_files": {
            str(spectral_path.relative_to(ROOT)): spectral_hash,
            str(mask_path.relative_to(ROOT)): mask_hash,
        },
        "normalized_path": str(normalized_path.relative_to(ROOT)),
    }
    METADATA.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    default_end = datetime.now(timezone.utc).date()
    parser.add_argument("--start", default=str(default_end - timedelta(days=45)))
    parser.add_argument("--end", default=str(default_end))
    parser.add_argument("--max-cloud", type=float, default=5.0)
    parser.add_argument("--credentials-file")
    parser.add_argument("--scope", choices=("core", "expanded"), default="core")
    parser.add_argument("--delete-credentials-file", action="store_true")
    args = parser.parse_args()
    _configure_scope(args.scope)
    try:
        record = fetch(args.start, args.end, args.max_cloud, args.credentials_file)
        print(json.dumps({key: record[key] for key in ("scene_id", "acquired_at_utc", "scene_cloud_cover_pct", "normalized_path")}, ensure_ascii=False, indent=2))
    finally:
        if args.delete_credentials_file and args.credentials_file:
            Path(args.credentials_file).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
