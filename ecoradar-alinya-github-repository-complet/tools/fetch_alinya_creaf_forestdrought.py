"""Normalize the latest official CREAF ForestDrought subset for Alinyà.

This connector reuses the verified CREAF/EMF transport implementation. It
only discovers, downloads, subsets and normalizes the source; it performs no
EcoRadar analysis.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer

import fetch_la_seu_creaf_forestdrought as connector


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"


def _bbox_epsg25830() -> tuple[float, float, float, float]:
    study = gpd.read_file(STUDY).to_crs(4326)
    west, south, east, north = (float(value) for value in study.total_bounds)
    transformer = Transformer.from_crs(4326, 25830, always_xy=True)
    corners = [
        transformer.transform(x, y)
        for x in (west, east)
        for y in (south, north)
    ]
    return (
        min(x for x, _ in corners),
        min(y for _, y in corners),
        max(x for x, _ in corners),
        max(y for _, y in corners),
    )


def configure() -> None:
    raw = PROJECT / "raw" / "creaf_forestdrought"
    connector.PROJECT = PROJECT
    connector.RAW_DIR = raw
    connector.OUTPUT_GEOJSON = raw / "forestdrought_latest.geojson"
    connector.OUTPUT_CSV = raw / "forestdrought_latest.csv"
    connector.METADATA = PROJECT / "metadata" / "creaf_forestdrought_connector.json"
    connector._bbox_epsg25830 = _bbox_epsg25830


def main() -> None:
    configure()
    frame = connector.fetch()
    metadata = json.loads(connector.METADATA.read_text(encoding="utf-8"))
    if metadata.get("scope") != "Muntanya d'Alinyà":
        metadata["scope"] = "Muntanya d'Alinyà"
        connector.METADATA.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "connector_status": metadata.get("connector_status"),
                "checked_at_utc": metadata.get("latest_catalog_check_utc"),
                "model_date": metadata.get("model_date"),
                "features": len(frame),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
