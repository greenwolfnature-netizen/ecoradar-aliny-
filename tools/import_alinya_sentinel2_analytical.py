"""Decode the authenticated CDSE analytical GeoTIFF for Muntanya d'Alinyà."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from shapely.geometry import mapping

from calculate_la_seu_expanded_indicators import _to_web_grid
from calculate_la_seu_sentinel2_indicators import _rgba, _stats, _write_raster, _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"
DERIVED = PROJECT / "processed" / "teledeteccio"
RAW = PROJECT / "raw" / "sentinel2_cdse"
MAPS = PROJECT / "maps" / "teledeteccio"
INDICATORS = PROJECT / "indicators" / "teledeteccio_sentinel2.json"
METADATA = PROJECT / "metadata" / "sentinel2_cdse_connector.json"
SCENE_ID = "S2A_MSIL2A_20260707T103701_N0512_R008_T31TCG_20260707T190508"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_analytical(source: Path) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)
    study4326 = gpd.read_file(STUDY).to_crs(4326)
    bbox = tuple(float(v) for v in study4326.total_bounds)
    with rasterio.open(source) as dataset:
        if dataset.count not in (3, 4) or dataset.dtypes[0] != "uint8" or dataset.crs is None:
            raise RuntimeError("Expected a georeferenced three- or four-band UINT8 CDSE analytical GeoTIFF.")
        study_projected = study4326.to_crs(dataset.crs)
        minx, miny, maxx, maxy = study_projected.total_bounds
        raw_window = from_bounds(minx, miny, maxx, maxy, transform=dataset.transform)
        col0, row0 = max(0, math.floor(raw_window.col_off)), max(0, math.floor(raw_window.row_off))
        col1 = min(dataset.width, math.ceil(raw_window.col_off + raw_window.width))
        row1 = min(dataset.height, math.ceil(raw_window.row_off + raw_window.height))
        if col1 <= col0 or row1 <= row0:
            raise RuntimeError("The CDSE export does not intersect Alinyà.")
        window = Window(col0, row0, col1-col0, row1-row0)
        encoded = dataset.read(window=window)
        transform = dataset.window_transform(window)
        profile = dataset.profile.copy()
        profile.update(width=int(window.width), height=int(window.height), transform=transform)
        export_bounds = tuple(float(v) for v in dataset.bounds)
        export_resolution = tuple(float(v) for v in dataset.res)

    scope_mask = geometry_mask(
        [mapping(geom) for geom in study_projected.geometry if geom is not None],
        out_shape=(int(window.height), int(window.width)), transform=transform, invert=True,
    )
    # Copernicus Browser's "Clip extra bands" option exports the three data
    # bands and removes alpha. Invalid SCL/dataMask pixels remain RGB 0/0/0.
    valid_transport = (encoded[3] == 255) if encoded.shape[0] == 4 else np.any(encoded[:3] != 0, axis=0)
    valid = scope_mask & valid_transport
    ndvi = np.where(valid, 2 * encoded[0].astype("float32") / 255 - 1, np.nan)
    ndmi = np.where(valid, 2 * encoded[1].astype("float32") / 255 - 1, np.nan)
    albedo = np.where(valid, encoded[2].astype("float32") / 255, np.nan)
    valid_ndvi = valid & np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)
    valid_ndmi = valid & np.isfinite(ndmi) & (ndmi >= -1) & (ndmi <= 1)
    valid_albedo = valid & np.isfinite(albedo) & (albedo >= 0) & (albedo <= 1)
    if min(valid_ndvi.sum(), valid_ndmi.sum(), valid_albedo.sum()) < 100:
        raise RuntimeError("Too few valid Sentinel-2 pixels remain after SCL and study-area masking.")
    DERIVED.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    raw_copy = RAW / f"{SCENE_ID}_analytical_uint8.tif"
    if source.resolve() != raw_copy.resolve():
        shutil.copy2(source, raw_copy)
    _write_raster(DERIVED / "ndvi.tif", ndvi, profile)
    _write_raster(DERIVED / "ndmi.tif", ndmi, profile)
    _write_raster(DERIVED / "albedo.tif", albedo, profile)
    ndvi_web, ndvi_web_valid = _to_web_grid(ndvi, valid_ndvi, profile, bbox, 10, resampling=Resampling.bilinear)
    ndmi_web, ndmi_web_valid = _to_web_grid(ndmi, valid_ndmi, profile, bbox, 10, resampling=Resampling.bilinear)
    albedo_web, albedo_web_valid = _to_web_grid(albedo, valid_albedo, profile, bbox, 10, resampling=Resampling.bilinear)
    _write_webp(MAPS / "ndvi.webp", _rgba(ndvi_web, [-.2,.1,.3,.55,.85], [(128,88,61),(216,193,123),(188,211,125),(91,157,74),(22,94,50)], ndvi_web_valid))
    _write_webp(MAPS / "ndmi.webp", _rgba(ndmi_web, [-.5,-.15,.05,.25,.55], [(166,87,47),(224,166,82),(225,218,157),(103,170,154),(34,102,145)], ndmi_web_valid))
    _write_webp(MAPS / "albedo.webp", _rgba(albedo_web, [.05,.12,.20,.30,.45], [(45,59,71),(94,111,116),(159,163,151),(218,206,168),(249,239,207)], albedo_web_valid))
    generated = datetime.now(timezone.utc).isoformat()
    connector = {
        "generated_at_utc": generated, "source": "Copernicus Sentinel-2 MSI Level-2A",
        "organization": "European Union Copernicus programme / ESA", "scene_id": SCENE_ID,
        "acquired_at_utc": "2026-07-07T10:37:01.024000Z", "source_file": str(raw_copy.relative_to(ROOT)),
        "source_sha256": _sha256(raw_copy),
        "official_urls": {"stac":"https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a", "browser":"https://browser.dataspace.copernicus.eu/", "process_api":"https://sh.dataspace.copernicus.eu/api/v1/process"},
        "service_type": "authenticated CDSE Browser analytical GeoTIFF export",
        "credentials": "free CDSE user session required; no credential stored", "license": "Copernicus Sentinel data policy",
        "connector_status": "verified", "study_bbox_epsg4326": bbox, "crs": str(profile["crs"]),
        "export_bounds": export_bounds, "export_grid_resolution": export_resolution,
        "transport_encoding": {"band_1":"NDVI encoded as round(255*((NDVI+1)/2))", "band_2":"NDMI encoded as round(255*((NDMI+1)/2))", "band_3":"albedo encoded as round(255*albedo)", "validity":"evalscript returns RGB 0/0/0 outside dataMask=1 and SCL {4,5,6}; Browser export used Clip extra bands"},
    }
    METADATA.write_text(json.dumps(connector, ensure_ascii=False, indent=2) + "\n")
    middle_latitude = (bbox[1] + bbox[3]) / 2
    pixel_area = abs(transform.a * transform.e) * 111320 * 111320 * math.cos(math.radians(middle_latitude))
    payload = {
        "generated_at_utc": generated, "scope": "Muntanya d'Alinyà", "source_scene": SCENE_ID,
        "acquired_at_utc": connector["acquired_at_utc"], "study_bbox_epsg4326": bbox,
        "valid_pixels": int(valid.sum()), "valid_area_ha": round(float(valid.sum()*pixel_area/10000),1),
        "metrics": {"ndvi":_stats(ndvi, valid_ndvi), "ndmi":_stats(ndmi, valid_ndmi), "albedo":_stats(albedo, valid_albedo)},
        "methods": {
            "ndvi":"(B08-B04)/(B08+B04), Sentinel-2 L2A bottom-of-atmosphere reflectance",
            "ndmi":"(B08-B11)/(B08+B11)",
            "albedo":"0.356*B02 + 0.130*B04 + 0.373*B08 + 0.085*B11 + 0.072*B12 - 0.0018",
            "quality_mask":"dataMask=1 and SCL classes 4, 5 or 6; cloud, cirrus, shadow, snow and invalid classes excluded",
        },
        "limitations": {"scene":"Single acquisition; not a seasonal climatology", "ndvi":"not biodiversity or individual plant health", "ndmi":"relative proxy, not field fuel moisture", "albedo":"broadband estimate, not in-situ radiometry"},
        "outputs": {"ndvi":"maps/teledeteccio/ndvi.webp", "ndmi":"maps/teledeteccio/ndmi.webp", "albedo":"maps/teledeteccio/albedo.webp"},
    }
    INDICATORS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print(json.dumps(import_analytical(args.source.expanduser().resolve()), ensure_ascii=False, indent=2))
