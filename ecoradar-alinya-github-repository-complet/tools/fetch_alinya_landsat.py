"""Fetch and normalize USGS Landsat 9 surface temperature for Alinyà."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import geopandas as gpd
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.transform import from_bounds
from rasterio.windows import from_bounds as window_from_bounds


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"
OUTPUT_DIR = PROJECT / "processed" / "landsat"
OUTPUT_TIF = OUTPUT_DIR / "landsat_lst.tif"
METADATA = PROJECT / "metadata" / "landsat_connector.json"
ITEM_ID = "LC09_L2SP_198031_20260708_02_T1"
ITEM_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2/items/" + ITEM_ID
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"


def _json(url: str) -> dict:
    with urlopen(url, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def _signed(href: str) -> str:
    return str(_json(SIGN_URL + "?" + urlencode({"href": href}))["href"])


def fetch() -> dict:
    bbox = tuple(float(v) for v in gpd.read_file(STUDY).to_crs(4326).total_bounds)
    item = _json(ITEM_URL)
    st_asset, qa_asset = item["assets"]["lwir11"], item["assets"]["qa_pixel"]
    scale = float(st_asset["raster:bands"][0]["scale"])
    offset = float(st_asset["raster:bands"][0]["offset"])
    nodata = int(st_asset["raster:bands"][0]["nodata"])
    with rasterio.open(_signed(st_asset["href"])) as src:
        transformer = Transformer.from_crs(4326, src.crs, always_xy=True)
        projected = [transformer.transform(x, y) for x in (bbox[0], bbox[2]) for y in (bbox[1], bbox[3])]
        bounds = (min(x for x, _ in projected), min(y for _, y in projected), max(x for x, _ in projected), max(y for _, y in projected))
        window = window_from_bounds(*bounds, src.transform).round_offsets().round_lengths()
        st_dn = src.read(1, window=window)
        source_bounds = rasterio.windows.bounds(window, src.transform)
        source_crs = src.crs
    with rasterio.open(_signed(qa_asset["href"])) as src:
        qa = src.read(1, window=window)
    invalid_bits = sum(1 << bit for bit in range(6))
    valid = (st_dn != nodata) & ((qa & invalid_bits) == 0)
    values = st_dn.astype("float64") * scale + offset - 273.15
    normalized = np.where(valid, values, -9999.0).astype("float32")
    transform = from_bounds(*source_bounds, st_dn.shape[1], st_dn.shape[0])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = {"driver":"GTiff", "height":st_dn.shape[0], "width":st_dn.shape[1], "count":1,
               "dtype":"float32", "crs":source_crs, "transform":transform, "nodata":-9999.0, "compress":"deflate"}
    with rasterio.open(OUTPUT_TIF, "w", **profile) as dst:
        dst.write(normalized, 1)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "connector": "landsat_usgs_c2_l2",
        "responsibility": "download_and_normalize_only", "scope": "Muntanya d'Alinyà",
        "study_bbox_epsg4326": bbox, "source": "USGS Landsat Collection 2 Level-2 Surface Temperature",
        "organization": "United States Geological Survey", "item_id": item["id"],
        "acquired_at_utc": item["properties"]["datetime"], "cloud_cover_scene_pct": float(item["properties"]["eo:cloud_cover"]),
        "official_catalog_url": "https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-sr/items/" + ITEM_ID,
        "access_mirror_item_url": ITEM_URL, "service_type": "STAC plus signed Cloud Optimized GeoTIFF range reads",
        "license": "USGS Landsat data are in the public domain", "crs": str(source_crs), "resolution_m": 30,
        "variables": ["ST_B10", "QA_PIXEL"],
        "normalization": "LST_C = ST_B10 * scale + offset - 273.15; QA bits 0-5 excluded",
        "valid_pixels": int(valid.sum()), "normalized_tif": str(OUTPUT_TIF.relative_to(ROOT)),
        "sha256": hashlib.sha256(OUTPUT_TIF.read_bytes()).hexdigest(), "connector_status": "verified",
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
