"""Download and normalize verified CLMS HRL WMS rasters for La Seu d'Urgell.

This source connector performs no indicator calculations. It records the exact
WMS requests, preserves the official responses under raw/ and writes normalized
single-band GeoTIFFs under processed/ for the analysis engine.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
RAW = PROJECT / "raw" / "copernicus_hrl"
PROCESSED = PROJECT / "processed" / "copernicus_hrl"
METADATA = PROJECT / "metadata" / "copernicus_hrl_connector.json"
SUMMARY = PROJECT / "metadata" / "copernicus_hrl_connector.csv"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"

TARGET_CRS = "EPSG:3035"
RESOLUTION_M = 10

SCOPE_CONFIG = {
    "core": {
        "bbox_key": "analysis_core_bbox_epsg4326",
        "raw": RAW,
        "processed": PROCESSED,
        "metadata": METADATA,
        "summary": SUMMARY,
    },
    "expanded": {
        "bbox_key": "expanded_urban_bbox_epsg4326",
        "raw": PROJECT / "raw" / "copernicus_hrl_expanded",
        "processed": PROJECT / "processed" / "copernicus_hrl_expanded",
        "metadata": PROJECT / "metadata" / "copernicus_hrl_expanded_connector.json",
        "summary": PROJECT / "metadata" / "copernicus_hrl_expanded_connector.csv",
    },
}

LAYERS = {
    "imperviousness_2021": {
        "endpoint": "https://geoserver.geoville.com/geoserver/nvlcc_2021/wms",
        "layer": "HRL_NVLCC_IMD_10m",
        "source": "CLMS HRL Imperviousness Density 2021",
        "official_url": "https://land.copernicus.eu/en/products/high-resolution-layer-imperviousness/imperviousness-density-2021",
        "values": "0-100 percent sealed surface density",
    },
    "tree_cover_density_2018": {
        "endpoint": "https://geoserver.vlcc.geoville.com/geoserver/ows",
        "layer": "HRL_TCF:TCD_S2018",
        "source": "CLMS HRL Tree Cover Density 2018",
        "official_url": "https://land.copernicus.eu/en/products/high-resolution-layer-forests-and-tree-cover",
        "values": "0-100 percent tree cover density",
    },
    "tree_cover_density_2023": {
        "endpoint": "https://geoserver.vlcc.geoville.com/geoserver/ows",
        "layer": "HRL_TCF:TCD_S2023",
        "source": "CLMS HRL Tree Cover Density 2023",
        "official_url": "https://land.copernicus.eu/en/products/high-resolution-layer-forests-and-tree-cover",
        "values": "0-100 percent tree cover density",
    },
    "herbaceous_cover_2023": {
        "endpoint": "https://geoserver.vlcc.geoville.com/geoserver/ows",
        "layer": "HRL_GRA:HER_S2023",
        "source": "CLMS HRL Herbaceous Cover 2023",
        "official_url": "https://land.copernicus.eu/en/products/high-resolution-layer-grasslands",
        "values": "binary herbaceous cover presence",
    },
}


def _study_bbox(bbox_key: str) -> tuple[float, float, float, float]:
    manifest = json.loads(PROJECT_MANIFEST.read_text())
    return tuple(float(value) for value in manifest["study_area"][bbox_key])


def _target_grid(bbox4326: tuple[float, float, float, float]):
    transformer = Transformer.from_crs(4326, TARGET_CRS, always_xy=True)
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


def _download(url: str, path: Path) -> str:
    content = urlopen(url, timeout=180).read()
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def fetch_layers(scope: str = "core") -> pd.DataFrame:
    config = SCOPE_CONFIG[scope]
    raw_dir = config["raw"]
    processed_dir = config["processed"]
    metadata_path = config["metadata"]
    summary_path = config["summary"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    bbox4326 = _study_bbox(str(config["bbox_key"]))
    bounds, width, height = _target_grid(bbox4326)
    records: list[dict] = []

    for key, definition in LAYERS.items():
        parameters = {
            "service": "WMS",
            "version": "1.1.1",
            "request": "GetMap",
            "layers": definition["layer"],
            "styles": "",
            "srs": TARGET_CRS,
            "bbox": ",".join(str(value) for value in bounds),
            "width": width,
            "height": height,
            "format": "image/geotiff",
            "transparent": "false",
        }
        query_url = definition["endpoint"] + "?" + urlencode(parameters)
        raw_path = raw_dir / f"{key}.tif"
        checksum = _download(query_url, raw_path)

        with rasterio.open(raw_path) as source:
            values = source.read(1)
            profile = source.profile.copy()
        profile.update(
            driver="GTiff",
            dtype="uint8",
            count=1,
            nodata=255,
            compress="deflate",
            tiled=False,
        )
        normalized_path = processed_dir / f"{key}.tif"
        with rasterio.open(normalized_path, "w", **profile) as target:
            target.write(values.astype("uint8"), 1)

        records.append(
            {
                "dataset": key,
                "source": definition["source"],
                "organization": "Copernicus Land Monitoring Service / European Environment Agency",
                "official_url": definition["official_url"],
                "service_type": "WMS GetMap",
                "format": "GeoTIFF uint8",
                "crs": TARGET_CRS,
                "resolution_m": RESOLUTION_M,
                "variables": definition["values"],
                "update_frequency": "annual or three-yearly according to product",
                "license": "Copernicus data policy",
                "connector_status": "verified",
                "query_url": query_url,
                "raw_path": str(raw_path.relative_to(ROOT)),
                "normalized_path": str(normalized_path.relative_to(ROOT)),
                "sha256": checksum,
                "minimum": int(values.min()),
                "maximum": int(values.max()),
            }
        )

    frame = pd.DataFrame.from_records(records)
    frame.to_csv(summary_path, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "connector": "clms_hrl_wms",
        "responsibility": "download_and_normalize_only",
        "scope": scope,
        "study_bbox_epsg4326": bbox4326,
        "target_bounds_epsg3035": bounds,
        "width": width,
        "height": height,
        "datasets": records,
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=sorted(SCOPE_CONFIG), default="core")
    args = parser.parse_args()
    frame = fetch_layers(args.scope)
    print(frame[["dataset", "minimum", "maximum", "normalized_path"]].to_string(index=False))
    print(SCOPE_CONFIG[args.scope]["metadata"])


if __name__ == "__main__":
    main()
