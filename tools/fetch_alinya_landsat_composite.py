"""Build a cloud-screened summer Landsat LST composite for all of Alinyà.

The connector queries the Planetary Computer mirror of the official USGS
Landsat Collection 2 Level-2 catalogue, reads only ST_B10 and QA_PIXEL over the
study area, applies the official scale/offset and QA mask, and writes a 30 m
median composite. It performs no fire analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds as window_from_bounds
from shapely.geometry import mapping


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"
OUTPUT_DIR = PROJECT / "processed" / "landsat"
OUTPUT_TIF = OUTPUT_DIR / "landsat_lst.tif"
METADATA = PROJECT / "metadata" / "landsat_connector.json"
SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
DATE_RANGE = "2025-06-01T00:00:00Z/2026-09-15T23:59:59Z"
TARGET_CRS = "EPSG:32631"
RESOLUTION = 30.0


def _json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def _signed(href: str) -> str:
    return str(_json(SIGN_URL + "?" + urlencode({"href": href}))["href"])


def _read_to_grid(href: str, bounds4326: tuple[float, ...], shape, transform, *, fill, dtype):
    with rasterio.open(_signed(href)) as src:
        transformer = Transformer.from_crs(4326, src.crs, always_xy=True)
        corners = [
            transformer.transform(x, y)
            for x in (bounds4326[0], bounds4326[2])
            for y in (bounds4326[1], bounds4326[3])
        ]
        source_bounds = (
            min(x for x, _ in corners), min(y for _, y in corners),
            max(x for x, _ in corners), max(y for _, y in corners),
        )
        window = window_from_bounds(*source_bounds, src.transform).round_offsets().round_lengths()
        source = src.read(1, window=window, boundless=True, fill_value=fill)
        destination = np.full(shape, fill, dtype=dtype)
        reproject(
            source=source,
            destination=destination,
            src_transform=src.window_transform(window),
            src_crs=src.crs,
            src_nodata=fill,
            dst_transform=transform,
            dst_crs=TARGET_CRS,
            dst_nodata=fill,
            resampling=Resampling.nearest,
        )
    return destination


def fetch() -> dict:
    study = gpd.read_file(STUDY).to_crs(TARGET_CRS)
    study4326 = study.to_crs(4326)
    bbox4326 = tuple(float(v) for v in study4326.total_bounds)
    minx, miny, maxx, maxy = (float(v) for v in study.total_bounds)
    left = math.floor(minx / RESOLUTION) * RESOLUTION
    top = math.ceil(maxy / RESOLUTION) * RESOLUTION
    width = math.ceil((maxx - left) / RESOLUTION)
    height = math.ceil((top - miny) / RESOLUTION)
    transform = from_origin(left, top, RESOLUTION, RESOLUTION)
    shape = (height, width)
    study_mask = geometry_mask(
        [mapping(g) for g in study.geometry if g is not None],
        out_shape=shape,
        transform=transform,
        invert=True,
    )

    search = _json(
        SEARCH_URL,
        {
            "collections": ["landsat-c2-l2"],
            "bbox": list(bbox4326),
            "datetime": DATE_RANGE,
            "query": {
                "platform": {"in": ["landsat-8", "landsat-9"]},
                "eo:cloud_cover": {"lt": 95},
            },
            "limit": 100,
        },
    )
    items = [
        item for item in search.get("features", [])
        if "lwir11" in item.get("assets", {}) and "qa_pixel" in item.get("assets", {})
        and item.get("properties", {}).get("landsat:correction") == "L2SP"
        and int(item.get("properties", {}).get("datetime", "0000-01")[5:7]) in {6, 7, 8, 9}
    ]
    items.sort(key=lambda item: (float(item["properties"].get("eo:cloud_cover", 100)), item["properties"]["datetime"]))
    if not items:
        raise RuntimeError("No Landsat 8/9 L2SP surface-temperature scenes found")

    layers = []
    scene_rows = []
    invalid_bits = sum(1 << bit for bit in range(6))
    for item in items:
        st_asset = item["assets"]["lwir11"]
        qa_asset = item["assets"]["qa_pixel"]
        band_meta = st_asset["raster:bands"][0]
        nodata = int(band_meta["nodata"])
        st_dn = _read_to_grid(
            st_asset["href"], bbox4326, shape, transform,
            fill=nodata, dtype="uint16",
        )
        qa = _read_to_grid(
            qa_asset["href"], bbox4326, shape, transform,
            fill=1, dtype="uint16",
        )
        valid = study_mask & (st_dn != nodata) & ((qa & invalid_bits) == 0)
        values = st_dn.astype("float64") * float(band_meta["scale"]) + float(band_meta["offset"]) - 273.15
        valid &= np.isfinite(values) & (values > -20) & (values < 80)
        layer = np.where(valid, values, np.nan).astype("float32")
        layers.append(layer)
        scene_rows.append({
            "item_id": item["id"],
            "acquired_at_utc": item["properties"]["datetime"],
            "scene_cloud_cover_pct": float(item["properties"].get("eo:cloud_cover", 0)),
            "valid_study_pixels": int(valid.sum()),
            "valid_study_pct": round(float(100 * valid.sum() / study_mask.sum()), 2),
        })

    with np.errstate(all="ignore"):
        composite = np.nanmedian(np.stack(layers), axis=0)
    composite_valid = study_mask & np.isfinite(composite)
    coverage_pct = float(100 * composite_valid.sum() / study_mask.sum())
    if coverage_pct < 99.9:
        raise RuntimeError(f"Summer LST composite covers only {coverage_pct:.2f}% of the study area")
    output = np.where(composite_valid, composite, -9999.0).astype("float32")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff", "height": height, "width": width, "count": 1,
        "dtype": "float32", "crs": TARGET_CRS, "transform": transform,
        "nodata": -9999.0, "compress": "deflate",
    }
    with rasterio.open(OUTPUT_TIF, "w", **profile) as dst:
        dst.write(output, 1)
        dst.update_tags(
            source="USGS Landsat 8/9 Collection 2 Level-2 Surface Temperature",
            method="Per-pixel median of QA-screened summer observations",
            date_range=DATE_RANGE,
        )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "connector": "landsat_usgs_c2_l2_summer_composite",
        "responsibility": "download_and_normalize_only",
        "scope": "Muntanya d'Alinyà",
        "study_bbox_epsg4326": bbox4326,
        "source": "USGS Landsat 8/9 Collection 2 Level-2 Surface Temperature",
        "organization": "United States Geological Survey",
        "official_catalog_url": "https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-sr",
        "access_mirror_search_url": SEARCH_URL,
        "service_type": "STAC plus signed Cloud Optimized GeoTIFF range reads",
        "license": "USGS Landsat data are in the public domain",
        "date_range": DATE_RANGE,
        "scene_count": len(scene_rows),
        "scenes": scene_rows,
        "crs": TARGET_CRS,
        "resolution_m": RESOLUTION,
        "variables": ["ST_B10", "QA_PIXEL"],
        "normalization": "LST_C = ST_B10 * scale + offset - 273.15; QA bits 0-5 excluded",
        "composite_method": "Per-pixel median of every valid QA-screened summer observation",
        "study_pixels": int(study_mask.sum()),
        "valid_pixels": int(composite_valid.sum()),
        "study_coverage_pct": round(coverage_pct, 3),
        "normalized_tif": str(OUTPUT_TIF.relative_to(ROOT)),
        "sha256": hashlib.sha256(OUTPUT_TIF.read_bytes()).hexdigest(),
        "connector_status": "verified",
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
