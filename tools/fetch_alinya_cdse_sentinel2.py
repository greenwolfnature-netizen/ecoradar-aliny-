"""Download and normalize Sentinel-2 L2A for the Muntanya d'Alinyà.

This connector reuses the verified CDSE OAuth/Catalog/Process implementation
used by EcoRadar La Seu while replacing only the study area and output paths.
It performs no indicator analysis.
"""

from __future__ import annotations

import argparse
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
        discovery = discover(args.start, args.end, args.max_cloud)
        if args.catalog_only:
            print(json.dumps(discovery, ensure_ascii=False, indent=2))
            return
        record = cdse.fetch(
            args.start,
            args.end,
            args.max_cloud,
            args.credentials_file,
            max_candidates=args.max_candidates,
            minimum_aoi_coverage_pct=args.minimum_aoi_coverage_pct,
        )
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
