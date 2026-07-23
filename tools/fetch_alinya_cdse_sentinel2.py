"""Download and normalize Sentinel-2 L2A for the Muntanya d'Alinyà.

This connector reuses the verified CDSE OAuth/Catalog/Process implementation
used by EcoRadar La Seu while replacing only the study area and output paths.
It performs no indicator analysis.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import geopandas as gpd

import fetch_la_seu_cdse_sentinel2 as cdse


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"


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


def main() -> None:
    parser = argparse.ArgumentParser()
    default_end = datetime.now(timezone.utc).date()
    parser.add_argument("--start", default=str(default_end - timedelta(days=45)))
    parser.add_argument("--end", default=str(default_end))
    parser.add_argument("--max-cloud", type=float, default=10.0)
    parser.add_argument("--credentials-file")
    parser.add_argument("--delete-credentials-file", action="store_true")
    args = parser.parse_args()
    _configure()
    try:
        record = cdse.fetch(args.start, args.end, args.max_cloud, args.credentials_file)
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
