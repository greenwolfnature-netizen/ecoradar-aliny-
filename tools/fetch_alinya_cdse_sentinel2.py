"""Download and normalize Sentinel-2 L2A for the Muntanya d'Alinyà.

This connector reuses the verified CDSE OAuth/Catalog/Process implementation
used by EcoRadar La Seu while replacing only the study area and output paths.
It performs no indicator analysis.
"""

from __future__ import annotations

import argparse
import hashlib
from urllib.error import HTTPError
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.transform import from_bounds
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
from shapely.geometry import shape

import fetch_la_seu_cdse_sentinel2 as cdse


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"
CATALOG_CHECK = PROJECT / "metadata" / "sentinel2_cdse_catalog_check.json"


def _study_bbox() -> tuple[float, float, float, float]:
    values = gpd.read_file(STUDY).to_crs(4326).total_bounds
    return tuple(float(value) for value in values)


def _configure() -> None:
    cdse.PROJECT = PROJECT
    cdse.RAW = PROJECT / "raw" / "sentinel2_cdse_official"
    cdse.PROCESSED = PROJECT / "processed" / "sentinel2_cdse"
    cdse.METADATA = PROJECT / "metadata" / "sentinel2_cdse_automated_connector.json"
    cdse.SCOPE = "alinya"
    cdse._study_bbox = _study_bbox
    cdse.STUDY_GEOMETRY_PROVIDER = lambda crs: list(gpd.read_file(STUDY).to_crs(crs).geometry)


def discover(start: str, end: str, max_cloud: float) -> dict:
    """Record public catalogue candidates without claiming SCL/QA validation."""
    study = gpd.read_file(STUDY).to_crs(4326).geometry.union_all()
    bbox = _study_bbox()
    query = {
        "collections": "sentinel-2-l2a",
        "bbox": ",".join(str(value) for value in bbox),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": 100,
    }
    query_url = cdse.STAC_SEARCH + "?" + urlencode(query)
    payload = cdse._json_request(query_url)
    candidates = []
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        footprint = feature.get("geometry")
        cloud = properties.get("eo:cloud_cover")
        if footprint is None or cloud is None or float(cloud) > max_cloud:
            continue
        geometry = shape(footprint)
        intersection_pct = 100.0 * geometry.intersection(study).area / max(study.area, 1e-12)
        if intersection_pct < 99.99:
            continue
        candidates.append(
            {
                "scene_id": feature.get("id"),
                "acquired_at_utc": properties.get("datetime"),
                "scene_cloud_cover_pct": cloud,
                "footprint_coverage_pct": round(intersection_pct, 2),
                "actual_aoi_scl_coverage_pct": None,
                "qa_status": "requires_authenticated_process_api",
            }
        )
    candidates.sort(key=lambda item: cdse._parse_utc(item["acquired_at_utc"]), reverse=True)
    credentials_present = bool(os.getenv("COPERNICUS_CLIENT_ID") and os.getenv("COPERNICUS_CLIENT_SECRET"))
    record = {
        "schema_version": "1.0",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Copernicus Data Space Ecosystem Sentinel-2 L2A STAC",
        "official_url": query_url,
        "search_period": {"start": start, "end": end},
        "maximum_tile_cloud_pct": max_cloud,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "connector_status": "ready_for_authenticated_qa" if credentials_present else "requires_credentials",
        "missing_requirements": [] if credentials_present else ["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"],
        "limitation": (
            "The public catalogue exposes footprint and tile cloud metadata only. "
            "Actual valid coverage inside Alinyà must be evaluated from SCL/dataMask through the authenticated Process API before selection."
        ),
    }
    CATALOG_CHECK.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_CHECK.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


# Source inventory (verified 2026-09-10 before implementation):
# Mission/level: ESA / European Commission Copernicus Sentinel-2 L2A.
# Access provider: Element 84 Earth Search / AWS; public STAC + HTTPS COG.
# Catalogue: https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a
# Provider documentation: https://github.com/Element84/earth-search/blob/main/README.md
# Also verified: sentinel-2-c1-l2a, same ESA L2A products with consistent COG offsets.
# Licence: https://registry.opendata.aws/sentinel-2-l2a-cogs/ (Copernicus open data).
# CRS: native tile UTM from each COG; normalized to the existing EPSG:32631 grid.
# Variables: B02/B04/B08 (10 m), B11/B12/SCL (20 m); scene-based acquisitions,
# nominal revisit about five days, checked on each existing daily workflow run.
# Example: GET /v1/search?collections=sentinel-2-l2a&bbox=<AOI>&datetime=<interval>
# Scale/offset: asset raster:bands; negative reflectance clamped to zero to match
# existing Sentinel Hub REFLECTANCE / harmonizeValues=true (no formula changes).
# Reference: https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l2a/
EARTH_SEARCH = "https://earth-search.aws.element84.com/v1/search"
EARTH_ASSETS = ["blue", "red", "nir", "swir16", "swir22"]
QA_METHOD = "SCL nearest-neighbour; classes 4,5,6; all-band nodata mask inside exact AOI"


def _oauth_unavailable(error: Exception) -> bool:
    """Only an authentication failure at the CDSE token endpoint opens fallback."""
    cause = error
    while cause is not None:
        if isinstance(cause, HTTPError) and cause.filename == cdse.TOKEN_URL:
            return cause.code == 401 or "unauthorized_client" in str(error).lower()
        cause = cause.__cause__
    return False


def _earth_candidates(end: str, max_cloud: float) -> tuple[list[dict], dict]:
    # Search the complete requested period, not only the default 45-day window.
    query = {"collections": "sentinel-2-l2a,sentinel-2-c1-l2a", "bbox": ",".join(map(str, _study_bbox())),
             "datetime": f"2026-07-08T00:00:00Z/{end}T23:59:59Z", "limit": 100}
    url = EARTH_SEARCH + "?" + urlencode(query)
    seen_pages, items = set(), {}
    while url:
        if url in seen_pages:
            raise RuntimeError("Earth Search repeated a pagination link; catalogue incomplete.")
        seen_pages.add(url)
        page = cdse._json_request(url)
        for item in page.get("features", []):
            items[item["id"]] = item
        url = next((link["href"] for link in page.get("links", []) if link["rel"] == "next"), None)
    aoi = shape(gpd.read_file(STUDY).to_crs(4326).geometry.union_all().__geo_interface__)
    candidates = []
    for item in items.values():
        props = item["properties"]
        cloud = props.get("eo:cloud_cover")
        if cloud is None or not 0 <= float(cloud) <= max_cloud:
            continue
        if not item.get("geometry") or not shape(item["geometry"]).covers(aoi):
            continue
        if cdse._parse_utc(props["datetime"]) <= cdse._parse_utc("2026-07-07T23:59:59Z"):
            continue
        candidates.append(item)
    candidates.sort(key=lambda item: (-cdse._parse_utc(item["properties"]["datetime"]).timestamp(),
                                       float(item["properties"]["eo:cloud_cover"]),
                                       item.get("collection") != "sentinel-2-c1-l2a", item["id"]))
    return candidates, {"query": query, "total_scenes": len(items), "eligible_scenes": len(candidates),
                        "pages": len(seen_pages), "complete": True}


def _earth_band(asset: dict, profile: dict, *, spectral: bool) -> np.ndarray:
    href = asset["href"]
    if not href.startswith("https://"):
        raise RuntimeError("Earth Search asset is not publicly accessible over HTTPS.")
    bands = asset.get("raster:bands", [])
    if spectral and (not bands or "scale" not in bands[0] or "offset" not in bands[0]):
        raise RuntimeError("Missing explicit reflectance scale/offset; cannot preserve methodology.")
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY=3,
                      GDAL_HTTP_TIMEOUT=120, AWS_NO_SIGN_REQUEST="YES"):
        with rasterio.open(href) as source:
            with WarpedVRT(source, crs=profile["crs"], transform=profile["transform"],
                           width=profile["width"], height=profile["height"], dtype="float32",
                           src_nodata=source.nodata, nodata=float("nan"),
                           resampling=Resampling.bilinear if spectral else Resampling.nearest) as vrt:
                values = vrt.read(1, masked=True).filled(np.nan)
    if spectral:
        values = np.maximum(values * float(bands[0]["scale"]) + float(bands[0]["offset"]), 0)
    return values.astype("float32")


def fetch_earth_search(end: str, max_cloud: float, minimum_aoi_coverage_pct: float) -> dict:
    """Download and normalize one QA-valid scene; leave ecological analysis downstream."""
    candidates, catalogue = _earth_candidates(end, max_cloud)
    bbox = _study_bbox()
    bounds, width, height = cdse._target_grid(bbox)
    profile = {"driver": "GTiff", "crs": cdse.TARGET_CRS, "width": width, "height": height,
               "transform": from_bounds(*bounds, width, height), "count": 7,
               "dtype": "float32", "nodata": -9999.0, "compress": "deflate"}
    scope = cdse._scope_mask(profile, bbox)
    scope_pixels = int(scope.sum())
    if not scope_pixels:
        raise RuntimeError("Empty rasterized Alinya AOI.")
    evaluated = []
    for scene in candidates:
        assets = scene["assets"]
        if scene["properties"].get("earthsearch:boa_offset_applied") is True and any(
            float(assets[key].get("raster:bands", [{}])[0].get("offset", 0)) != 0
            for key in EARTH_ASSETS
        ):
            evaluated.append({"scene_id": scene["id"], "qa_status": "rejected_conflicting_radiometric_metadata"})
            continue
        # Missing assets or transport failures are errors, never proof of failed QA.
        scl = _earth_band(assets["scl"], profile, spectral=False)
        valid = scope & np.isfinite(scl) & np.isin(scl, [4, 5, 6])
        assessment = {"scene_id": scene["id"], "acquired_at_utc": scene["properties"]["datetime"],
                      "scene_cloud_cover_pct": scene["properties"]["eo:cloud_cover"],
                      "scl_valid_aoi_coverage_pct": round(100 * int(valid.sum()) / scope_pixels, 2)}
        evaluated.append(assessment)
        if 100 * int(valid.sum()) / scope_pixels < minimum_aoi_coverage_pct:
            assessment["qa_status"] = "rejected_scl_coverage"
            continue
        reflectance = [_earth_band(assets[key], profile, spectral=True) for key in EARTH_ASSETS]
        data_mask = np.isfinite(scl) & (scl != 0)
        for band in reflectance:
            data_mask &= np.isfinite(band)
        valid &= data_mask
        coverage = 100 * int(valid.sum()) / scope_pixels
        assessment["valid_aoi_coverage_pct"] = round(coverage, 2)
        if coverage < minimum_aoi_coverage_pct:
            assessment["qa_status"] = "rejected_all_band_nodata_coverage"
            continue
        assessment["qa_status"] = "validated"
        path = cdse.PROCESSED / "sentinel2_l2a_reflectance_quality.tif"
        if cdse.METADATA.exists() and path.exists():
            previous = json.loads(cdse.METADATA.read_text())
            if cdse._parse_utc(previous["acquired_at_utc"]) > cdse._parse_utc(scene["properties"]["datetime"]):
                raise RuntimeError("Earth Search would regress the last validated acquisition; preserving it.")
        record = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mission": "Sentinel-2", "data_level": "L2A", "provider": "Earth Search / AWS",
            "source_scene_id": scene["id"], "stac_collection": scene["collection"],
            "esa_product_uri": scene["properties"].get("s2:product_uri"), "acquisition_date": scene["properties"]["datetime"],
            "qa_method": QA_METHOD, "fallback_reason": "CDSE OAuth unavailable",
            "scene_id": scene["id"], "acquired_at_utc": scene["properties"]["datetime"],
            "scene_cloud_cover_pct": scene["properties"]["eo:cloud_cover"],
            "source": "Copernicus Sentinel-2 MSI Level-2A (Earth Search / AWS)",
            "organization": "ESA / European Commission; access via Element 84 / AWS",
            "official_urls": {"stac": EARTH_SEARCH, "provider": "https://registry.opendata.aws/sentinel-2-l2a-cogs/"},
            "license": "Copernicus free, full and open data policy",
            "connector": "alinya_sentinel2_earth_search_fallback", "connector_status": "verified",
            "responsibility": "select_download_and_normalize_only", "updated": True,
            "crs": cdse.TARGET_CRS, "resolution_m": 10, "bands": cdse.BANDS,
            "native_resolution_m": {"B02": 10, "B04": 10, "B08": 10, "B11": 20, "B12": 20, "SCL": 20},
            "normalization": "STAC asset scale/offset to BOA reflectance; clamp negatives as CDSE harmonizeValues=true; spectral bilinear, SCL nearest",
            "actual_aoi_qa": {"scope_pixels": scope_pixels, "valid_aoi_pixels": int(valid.sum()),
                              "valid_aoi_coverage_pct": round(coverage, 2), "accepted_scl_classes": [4, 5, 6]},
            "candidate_evaluations": evaluated, "catalogue": catalogue,
            "selection_rule": "Newest footprint-covering scene passing unchanged tile-cloud and actual AOI SCL/nodata thresholds; full paginated search since 2026-07-08",
            "maximum_tile_cloud_pct": max_cloud, "minimum_aoi_coverage_pct": minimum_aoi_coverage_pct,
            "normalized_path": str(path.relative_to(ROOT)),
            "source_assets": {key: assets[key] for key in EARTH_ASSETS + ["scl"]},
        }
        cdse.PROCESSED.mkdir(parents=True, exist_ok=True)
        cdse.METADATA.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".pending.tif")
        with rasterio.open(temporary, "w", **profile) as target:
            for index, band in enumerate(reflectance + [scl, data_mask.astype("float32")], 1):
                target.write(np.where(np.isfinite(band), band, -9999).astype("float32"), index)
                target.set_band_description(index, cdse.BANDS[index - 1])
        record["normalized_sha256"] = hashlib.sha256(temporary.read_bytes()).hexdigest()
        cdse._archive_existing(path)
        temporary.replace(path)
        cdse.METADATA.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        print(f"Earth Search validated {scene['id']}: AOI coverage {coverage:.2f}%", flush=True)
        return record
    proof = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "catalogue": catalogue,
             "candidate_evaluations": evaluated, "status": "no_qa_valid_scene",
             "fallback_reason": "CDSE OAuth unavailable"}
    CATALOG_CHECK.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_CHECK.with_name("sentinel2_earth_search_check.json").write_text(json.dumps(proof, indent=2) + "\n")
    raise RuntimeError("No post-2026-07-07 Earth Search scene passed QA; complete search recorded, last validated data preserved.")


def fetch_with_fallback(args) -> dict:
    try:
        return cdse.fetch(args.start, args.end, args.max_cloud, args.credentials_file,
                          max_candidates=args.max_candidates,
                          minimum_aoi_coverage_pct=args.minimum_aoi_coverage_pct)
    except RuntimeError as error:
        if not _oauth_unavailable(error):
            raise
        print("CDSE OAuth unavailable; using public Earth Search Sentinel-2 L2A.", flush=True)
        return fetch_earth_search(args.end, args.max_cloud, args.minimum_aoi_coverage_pct)


def main() -> None:
    parser = argparse.ArgumentParser()
    default_end = datetime.now(timezone.utc).date()
    parser.add_argument("--start", default=str(default_end - timedelta(days=45)))
    parser.add_argument("--end", default=str(default_end))
    parser.add_argument("--max-cloud", type=float, default=10.0)
    parser.add_argument("--credentials-file")
    parser.add_argument("--delete-credentials-file", action="store_true")
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--minimum-aoi-coverage-pct", type=float, default=85.0)
    args = parser.parse_args()
    _configure()
    try:
        if args.catalog_only:
            discovery = discover(args.start, args.end, args.max_cloud)
            print(json.dumps(discovery, ensure_ascii=False, indent=2))
            return
        record = fetch_with_fallback(args)
        print(
            json.dumps(
                {
                    key: record[key]
                    for key in (
                        "scene_id",
                        "acquired_at_utc",
                        "scene_cloud_cover_pct",
                        "normalized_path",
                    )
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        if args.delete_credentials_file and args.credentials_file:
            Path(args.credentials_file).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
