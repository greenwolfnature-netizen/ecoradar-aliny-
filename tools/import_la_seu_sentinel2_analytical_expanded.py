"""Import the authenticated CDSE analytical GeoTIFF for the expanded urban scope.

The Copernicus Browser evalscript applies the documented NDVI, NDMI and
broadband-albedo formulas to Sentinel-2 L2A BOA reflectance, masks SCL classes
outside 4/5/6, and encodes the three results into an 8-bit RGBA GeoTIFF. This
script only decodes that documented transport encoding, crops the operational
study rectangle and writes the project indicator artefacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds

from calculate_la_seu_expanded_indicators import _to_web_grid
from calculate_la_seu_sentinel2_indicators import _rgba, _stats, _write_raster, _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
DERIVED = PROJECT / "processed" / "sentinel2_indicators_expanded"
RAW = PROJECT / "raw" / "sentinel2_cdse_expanded"
MAPS = PROJECT / "maps"
INDICATORS = PROJECT / "indicators" / "sentinel2_expanded_indicators.json"
CONNECTOR_METADATA = PROJECT / "metadata" / "sentinel2_cdse_expanded_connector.json"
MANIFEST = PROJECT / "metadata" / "sentinel2_expanded_indicators_manifest.json"
SCENE_ID = "S2A_MSIL2A_20260707T103701_N0512_R008_T31TCG_20260707T190508"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _crop_window(dataset, bbox4326: tuple[float, float, float, float]) -> tuple[Window, list[tuple[float, float]]]:
    transformer = Transformer.from_crs(4326, dataset.crs, always_xy=True)
    ring = [
        transformer.transform(bbox4326[0], bbox4326[1]),
        transformer.transform(bbox4326[0], bbox4326[3]),
        transformer.transform(bbox4326[2], bbox4326[3]),
        transformer.transform(bbox4326[2], bbox4326[1]),
        transformer.transform(bbox4326[0], bbox4326[1]),
    ]
    minx = min(point[0] for point in ring)
    miny = min(point[1] for point in ring)
    maxx = max(point[0] for point in ring)
    maxy = max(point[1] for point in ring)
    raw = from_bounds(minx, miny, maxx, maxy, transform=dataset.transform)
    col0 = max(0, math.floor(raw.col_off))
    row0 = max(0, math.floor(raw.row_off))
    col1 = min(dataset.width, math.ceil(raw.col_off + raw.width))
    row1 = min(dataset.height, math.ceil(raw.row_off + raw.height))
    if col1 <= col0 or row1 <= row0:
        raise RuntimeError("The CDSE analytical export does not intersect the expanded EcoRadar scope.")
    return Window(col0, row0, col1 - col0, row1 - row0), ring


def import_analytical(source: Path) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)
    project = json.loads(PROJECT_MANIFEST.read_text())
    bbox = tuple(float(value) for value in project["study_area"]["expanded_urban_bbox_epsg4326"])
    with rasterio.open(source) as dataset:
        if dataset.count != 4 or dataset.dtypes[0] != "uint8":
            raise RuntimeError("Expected the documented four-band UINT8 CDSE analytical GeoTIFF.")
        if dataset.crs is None:
            raise RuntimeError("The CDSE analytical GeoTIFF has no CRS.")
        window, ring = _crop_window(dataset, bbox)
        encoded = dataset.read(window=window)
        transform = dataset.window_transform(window)
        profile = dataset.profile.copy()
        profile.update(width=int(window.width), height=int(window.height), transform=transform)
        source_bounds = tuple(float(value) for value in dataset.bounds)
        source_resolution = tuple(float(value) for value in dataset.res)

    scope_mask = geometry_mask(
        [{"type": "Polygon", "coordinates": [ring]}],
        out_shape=(int(window.height), int(window.width)),
        transform=transform,
        invert=True,
    )
    valid = scope_mask & (encoded[3] == 255)
    ndvi = np.where(valid, 2.0 * encoded[0].astype("float32") / 255.0 - 1.0, np.nan)
    ndmi = np.where(valid, 2.0 * encoded[1].astype("float32") / 255.0 - 1.0, np.nan)
    albedo = np.where(valid, encoded[2].astype("float32") / 255.0, np.nan)
    valid_ndvi = valid & np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)
    valid_ndmi = valid & np.isfinite(ndmi) & (ndmi >= -1) & (ndmi <= 1)
    valid_albedo = valid & np.isfinite(albedo) & (albedo >= 0) & (albedo <= 1)
    ndvi = np.where(valid_ndvi, ndvi, np.nan)
    ndmi = np.where(valid_ndmi, ndmi, np.nan)
    albedo = np.where(valid_albedo, albedo, np.nan)
    if min(valid_ndvi.sum(), valid_ndmi.sum(), valid_albedo.sum()) < 100:
        raise RuntimeError("Too few valid CDSE pixels remain after the documented SCL mask and scope crop.")

    DERIVED.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    raw_copy = RAW / f"{SCENE_ID}_analytical_uint8.tif"
    if source.resolve() != raw_copy.resolve():
        shutil.copy2(source, raw_copy)
    _write_raster(DERIVED / "ndvi_sentinel2_expanded.tif", ndvi, profile)
    _write_raster(DERIVED / "ndmi_sentinel2_expanded.tif", ndmi, profile)
    _write_raster(DERIVED / "albedo_sentinel2_expanded.tif", albedo, profile)

    ndvi_web, ndvi_web_valid = _to_web_grid(ndvi, valid_ndvi, profile, bbox, 10, resampling=Resampling.bilinear)
    ndmi_web, ndmi_web_valid = _to_web_grid(ndmi, valid_ndmi, profile, bbox, 10, resampling=Resampling.bilinear)
    albedo_web, albedo_web_valid = _to_web_grid(albedo, valid_albedo, profile, bbox, 10, resampling=Resampling.bilinear)
    _write_webp(MAPS / "sentinel2_ndvi_expanded.webp", _rgba(ndvi_web, [-0.2, 0.1, 0.3, 0.55, 0.85], [(128, 88, 61), (216, 193, 123), (188, 211, 125), (91, 157, 74), (22, 94, 50)], ndvi_web_valid))
    _write_webp(MAPS / "sentinel2_ndmi_expanded.webp", _rgba(ndmi_web, [-0.5, -0.15, 0.05, 0.25, 0.55], [(166, 87, 47), (224, 166, 82), (225, 218, 157), (103, 170, 154), (34, 102, 145)], ndmi_web_valid))
    _write_webp(MAPS / "sentinel2_albedo_expanded.webp", _rgba(albedo_web, [0.05, 0.12, 0.20, 0.30, 0.45], [(45, 59, 71), (94, 111, 116), (159, 163, 151), (218, 206, 168), (249, 239, 207)], albedo_web_valid))

    pixel_area_m2 = abs(transform.a * transform.e)
    source_hash = _sha256(raw_copy)
    generated = datetime.now(timezone.utc).isoformat()
    connector = {
        "generated_at_utc": generated,
        "source": "Copernicus Sentinel-2 MSI Level-2A",
        "organization": "European Union Copernicus programme / ESA",
        "scene_id": SCENE_ID,
        "acquired_at_utc": "2026-07-07T10:37:01.024000Z",
        "source_file": str(raw_copy.relative_to(ROOT)),
        "source_sha256": source_hash,
        "official_urls": {
            "stac": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
            "browser": "https://browser.dataspace.copernicus.eu/",
            "process_api": "https://sh.dataspace.copernicus.eu/api/v1/process",
        },
        "service_type": "authenticated CDSE Copernicus Browser analytical GeoTIFF export",
        "credentials": "free CDSE user session required; no credential is stored in the project",
        "license": "Copernicus Sentinel data policy: free, full and open use with attribution",
        "connector_status": "verified",
        "study_bbox_epsg4326": bbox,
        "crs": str(profile["crs"]),
        "export_bounds": source_bounds,
        "export_grid_resolution_m": source_resolution,
        "native_resolution_m": {"B02": 10, "B04": 10, "B08": 10, "B11": 20, "B12": 20, "SCL": 20},
        "transport_encoding": {
            "band_1": "round(255 * clamp((NDVI + 1) / 2)); decoded as 2 * DN / 255 - 1",
            "band_2": "round(255 * clamp((NDMI + 1) / 2)); decoded as 2 * DN / 255 - 1",
            "band_3": "round(255 * clamp(albedo)); decoded as DN / 255",
            "band_4": "255 for dataMask=1 and SCL in {4,5,6}; 0 otherwise",
            "quantization_step_ndvi_ndmi": round(2 / 255, 8),
            "quantization_step_albedo": round(1 / 255, 8),
        },
    }
    CONNECTOR_METADATA.write_text(json.dumps(connector, ensure_ascii=False, indent=2) + "\n")

    payload = {
        "generated_at_utc": generated,
        "product_scope": "La Seu d'Urgell, Castellciutat and Sant Antoni",
        "study_bbox_epsg4326": bbox,
        "source_scene": SCENE_ID,
        "acquired_at_utc": connector["acquired_at_utc"],
        "source": connector["source"],
        "official_urls": connector["official_urls"],
        "license": connector["license"],
        "credentials": connector["credentials"],
        "crs": str(profile["crs"]),
        "export_grid_resolution_m": round(float(np.mean(source_resolution)), 2),
        "effective_resolution_m": {"ndvi": 10, "ndmi": 20, "albedo": 20},
        "native_band_resolution_m": connector["native_resolution_m"],
        "valid_pixels": int(valid.sum()),
        "valid_area_ha": round(float(valid.sum() * pixel_area_m2 / 10000), 1),
        "metrics": {
            "ndvi": _stats(ndvi, valid_ndvi),
            "ndmi": _stats(ndmi, valid_ndmi),
            "albedo": _stats(albedo, valid_albedo),
        },
        "methods": {
            "ndvi": "(B08 - B04) / (B08 + B04), using Sentinel-2 L2A bottom-of-atmosphere reflectance.",
            "ndmi": "(B08 - B11) / (B08 + B11); B11 has 20 m native resolution.",
            "albedo": "0.356*B02 + 0.130*B04 + 0.373*B08 + 0.085*B11 + 0.072*B12 - 0.0018; Sentinel-2 adaptation documented by Naegeli et al. (2017), DOI 10.3390/rs9020110.",
            "quality_mask": "Only dataMask=1 and SCL classes 4 vegetation, 5 bare/not vegetated and 6 water; clouds, cirrus, shadows, snow, defective and unclassified pixels excluded.",
            "transport": "Formulas executed in the official authenticated CDSE Browser; values decoded locally from the documented UINT8 analytical transport encoding.",
        },
        "quantization": connector["transport_encoding"],
        "limitations": {
            "scene": "Single clear-sky acquisition; values describe surface optical conditions at acquisition time, not a seasonal climatology.",
            "ndvi": "Sensitive to soil background and saturation in dense vegetation; not a direct measure of biodiversity or canopy health.",
            "ndmi": "Relative canopy/vegetation moisture proxy, not volumetric soil moisture or irrigation demand.",
            "albedo": "Published broadband estimate, not an in-situ radiometric measurement. Mixed 10/20 m bands and documented 8-bit transport quantization limit effective detail.",
        },
        "outputs": {
            "ndvi_tif": "processed/sentinel2_indicators_expanded/ndvi_sentinel2_expanded.tif",
            "ndmi_tif": "processed/sentinel2_indicators_expanded/ndmi_sentinel2_expanded.tif",
            "albedo_tif": "processed/sentinel2_indicators_expanded/albedo_sentinel2_expanded.tif",
            "ndvi_webp": "maps/sentinel2_ndvi_expanded.webp",
            "ndmi_webp": "maps/sentinel2_ndmi_expanded.webp",
            "albedo_webp": "maps/sentinel2_albedo_expanded.webp",
        },
    }
    INDICATORS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Four-band UINT8 analytical GeoTIFF exported from CDSE Browser")
    args = parser.parse_args()
    payload = import_analytical(args.source.expanduser().resolve())
    print(json.dumps({"valid_pixels": payload["valid_pixels"], "metrics": payload["metrics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
