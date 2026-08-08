"""Download and normalize official CLMS HRL 2023 vegetation layers for Alinyà."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import geopandas as gpd
import numpy as np
from pyproj import Transformer
import rasterio


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"
RAW = PROJECT / "raw" / "copernicus_hrl"
PROCESSED = PROJECT / "processed" / "copernicus_hrl"
METADATA = PROJECT / "metadata" / "copernicus_hrl_connector.json"
TARGET_CRS = "EPSG:3035"
RESOLUTION_M = 10

LAYERS = {
    "tree_cover_density_2023": {
        "endpoint": "https://geoserver.vlcc.geoville.com/geoserver/ows",
        "layer": "HRL_TCF:TCD_S2023",
        "source": "CLMS HRL Tree Cover Density 2023",
        "official_url": "https://land.copernicus.eu/en/products/high-resolution-layer-forests-and-tree-cover",
        "values": "0-100 percent tree-cover density",
    },
    "herbaceous_cover_2023": {
        "endpoint": "https://geoserver.vlcc.geoville.com/geoserver/ows",
        "layer": "HRL_GRA:HER_S2023",
        "source": "CLMS HRL Herbaceous Cover 2023",
        "official_url": "https://land.copernicus.eu/en/products/high-resolution-layer-grasslands",
        "values": "binary herbaceous-cover presence",
    },
}


def _bbox4326() -> tuple[float, float, float, float]:
    study = gpd.read_file(STUDY).to_crs(4326)
    return tuple(float(v) for v in study.total_bounds)


def _grid(bbox):
    transformer = Transformer.from_crs(4326, TARGET_CRS, always_xy=True)
    points = [transformer.transform(x, y) for x in (bbox[0], bbox[2]) for y in (bbox[1], bbox[3])]
    minx = math.floor(min(x for x, _ in points) / RESOLUTION_M) * RESOLUTION_M
    miny = math.floor(min(y for _, y in points) / RESOLUTION_M) * RESOLUTION_M
    maxx = math.ceil(max(x for x, _ in points) / RESOLUTION_M) * RESOLUTION_M
    maxy = math.ceil(max(y for _, y in points) / RESOLUTION_M) * RESOLUTION_M
    return (minx, miny, maxx, maxy), int((maxx-minx)/RESOLUTION_M), int((maxy-miny)/RESOLUTION_M)


def fetch() -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    bbox = _bbox4326()
    bounds, width, height = _grid(bbox)
    records = []
    for key, definition in LAYERS.items():
        params = {
            "service": "WMS", "version": "1.1.1", "request": "GetMap",
            "layers": definition["layer"], "styles": "", "srs": TARGET_CRS,
            "bbox": ",".join(str(v) for v in bounds), "width": width, "height": height,
            "format": "image/geotiff", "transparent": "false",
        }
        url = definition["endpoint"] + "?" + urlencode(params)
        raw_path = RAW / f"{key}.tif"
        content = urlopen(url, timeout=180).read()
        raw_path.write_bytes(content)
        with rasterio.open(raw_path) as src:
            values = src.read(1)
            profile = src.profile.copy()
        profile.update(driver="GTiff", dtype="uint8", count=1, nodata=255, compress="deflate", tiled=False)
        output = PROCESSED / f"{key}.tif"
        with rasterio.open(output, "w", **profile) as dst:
            dst.write(values.astype("uint8"), 1)
        records.append({
            "dataset": key, "source": definition["source"],
            "organization": "Copernicus Land Monitoring Service / European Environment Agency",
            "official_url": definition["official_url"], "service_type": "WMS GetMap",
            "format": "GeoTIFF uint8", "crs": TARGET_CRS, "resolution_m": RESOLUTION_M,
            "variables": definition["values"], "update_frequency": "three-yearly according to product",
            "license": "Copernicus data policy", "connector_status": "verified", "query_url": url,
            "raw_path": str(raw_path.relative_to(ROOT)), "normalized_path": str(output.relative_to(ROOT)),
            "sha256": hashlib.sha256(content).hexdigest(), "minimum": int(values.min()), "maximum": int(values.max()),
        })
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "connector": "clms_hrl_wms", "responsibility": "download_and_normalize_only",
        "scope": "Muntanya d'Alinyà", "study_bbox_epsg4326": bbox,
        "target_bounds_epsg3035": bounds, "width": width, "height": height, "datasets": records,
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
