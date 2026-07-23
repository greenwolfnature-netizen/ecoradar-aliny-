"""Fetch and normalize the verified Landsat LST source for the expanded viewer.

The connector reads the same official USGS Collection 2 Level-2 item already
documented for La Seu. The Planetary Computer URL is only the access mirror for
the unchanged USGS product. This module performs source access, QA masking and
unit normalization; it does not calculate urban indicators.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.transform import from_bounds
from rasterio.windows import from_bounds as window_from_bounds


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
OUTPUT_DIR = PROJECT / "processed" / "landsat_expanded"
OUTPUT_TIF = OUTPUT_DIR / "landsat_lst_expanded.tif"
OUTPUT_NPZ = OUTPUT_DIR / "landsat_lst_expanded.npz"
METADATA = PROJECT / "metadata" / "landsat_expanded_connector.json"

SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"


def _read_json(url: str) -> dict:
    with urlopen(url, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def _signed(href: str) -> str:
    return str(_read_json(f"{SIGN_URL}?{urlencode({'href': href})}")["href"])


def _search_items(bbox: tuple[float, ...], *, lookback_days: int = 80, max_cloud: float = 25.0) -> tuple[list[dict], str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    parameters = {
        "collections": "landsat-c2-l2",
        "bbox": ",".join(str(value) for value in bbox),
        "datetime": f"{start.isoformat().replace('+00:00', 'Z')}/{end.isoformat().replace('+00:00', 'Z')}",
        "limit": 100,
    }
    url = SEARCH_URL + "?" + urlencode(parameters)
    payload = _read_json(url)
    candidates = [
        item for item in payload.get("features", [])
        if "lwir11" in item.get("assets", {})
        and "qa_pixel" in item.get("assets", {})
        and float(item.get("properties", {}).get("eo:cloud_cover", 100)) <= max_cloud
    ]
    candidates.sort(key=lambda item: item["properties"]["datetime"], reverse=True)
    if not candidates:
        raise RuntimeError("No recent Landsat C2 L2 surface-temperature candidates passed the scene cloud threshold.")
    return candidates, url


def _record_catalog_check(existing: dict) -> dict:
    payload = {
        **existing,
        "updated": False,
        "latest_catalog_check_utc": datetime.now(timezone.utc).isoformat(),
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def fetch() -> dict:
    manifest = json.loads(PROJECT_MANIFEST.read_text())
    bbox = tuple(float(v) for v in manifest["study_area"]["expanded_urban_bbox_epsg4326"])
    items, search_url = _search_items(bbox)
    existing = json.loads(METADATA.read_text(encoding="utf-8")) if METADATA.exists() else {}
    existing_time = existing.get("acquired_at_utc", "")
    selected = None
    for item in items:
        acquired_at = item["properties"]["datetime"]
        if existing_time and acquired_at <= existing_time and OUTPUT_TIF.exists() and OUTPUT_NPZ.exists():
            return _record_catalog_check(existing)
        st_asset = item["assets"]["lwir11"]
        qa_asset = item["assets"]["qa_pixel"]
        st_href = _signed(st_asset["href"])
        qa_href = _signed(qa_asset["href"])
        scale = float(st_asset["raster:bands"][0]["scale"])
        offset = float(st_asset["raster:bands"][0]["offset"])
        nodata = int(st_asset["raster:bands"][0]["nodata"])
        try:
            with rasterio.open(st_href) as source:
                transformer = Transformer.from_crs(4326, source.crs, always_xy=True)
                projected = [
                    transformer.transform(x, y)
                    for x in (bbox[0], bbox[2])
                    for y in (bbox[1], bbox[3])
                ]
                bounds = (
                    min(x for x, _ in projected), min(y for _, y in projected),
                    max(x for x, _ in projected), max(y for _, y in projected),
                )
                window = window_from_bounds(*bounds, source.transform).round_offsets().round_lengths()
                st_dn = source.read(1, window=window)
                source_bounds = rasterio.windows.bounds(window, source.transform)
                source_crs = source.crs
            with rasterio.open(qa_href) as source:
                qa = source.read(1, window=window)
        except Exception:
            continue
        invalid_bits = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5)
        valid = (st_dn != nodata) & ((qa & invalid_bits) == 0)
        if int(valid.sum()) < 100:
            continue
        values = st_dn.astype("float64") * scale + offset - 273.15
        selected = (item, valid, values, source_bounds, source_crs)
        break
    if selected is None:
        if existing and OUTPUT_TIF.exists() and OUTPUT_NPZ.exists():
            return _record_catalog_check(existing)
        raise RuntimeError("No recent Landsat scene contained at least 100 QA-valid local pixels.")
    item, valid, values, source_bounds, source_crs = selected
    normalized = np.where(valid, values, -9999.0).astype("float32")
    output_transform = from_bounds(*source_bounds, st_dn.shape[1], st_dn.shape[0])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": st_dn.shape[0],
        "width": st_dn.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": source_crs,
        "transform": output_transform,
        "nodata": -9999.0,
        "compress": "deflate",
    }
    with rasterio.open(OUTPUT_TIF, "w", **profile) as target:
        target.write(normalized, 1)
    np.savez_compressed(
        OUTPUT_NPZ,
        lst_c=values.astype("float32"),
        valid=valid,
        bounds=np.asarray(source_bounds, dtype="float64"),
        crs=np.asarray(str(source_crs)),
    )
    checksum = hashlib.sha256(OUTPUT_TIF.read_bytes()).hexdigest()
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "connector": "landsat_usgs_c2_l2_expanded",
        "responsibility": "download_and_normalize_only",
        "scope": "La Seu d'Urgell, Castellciutat and Sant Antoni",
        "study_bbox_epsg4326": bbox,
        "source": "USGS Landsat Collection 2 Level-2 Surface Temperature",
        "organization": "United States Geological Survey",
        "item_id": item["id"],
        "acquired_at_utc": item["properties"]["datetime"],
        "cloud_cover_scene_pct": float(item["properties"]["eo:cloud_cover"]),
        "official_catalog_url": "https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-st/items/" + item["id"],
        "access_mirror_search_url": search_url,
        "service_type": "STAC plus signed Cloud Optimized GeoTIFF range reads",
        "license": "USGS Landsat data are in the public domain",
        "crs": str(source_crs),
        "resolution_m": 30,
        "variables": ["ST_B10", "QA_PIXEL"],
        "normalization": "LST_C = ST_B10 * scale + offset - 273.15; QA bits 0-5 excluded",
        "valid_pixels": int(valid.sum()),
        "normalized_tif": str(OUTPUT_TIF.relative_to(ROOT)),
        "normalized_npz": str(OUTPUT_NPZ.relative_to(ROOT)),
        "sha256": checksum,
        "connector_status": "verified",
        "updated": True,
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    payload = fetch()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
