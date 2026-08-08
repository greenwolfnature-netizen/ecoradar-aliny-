"""Calculate expanded-scope NDVI, NDMI and broadband albedo from Sentinel-2."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask

from calculate_la_seu_sentinel2_indicators import _rgba, _stats, _write_raster, _write_webp
from calculate_la_seu_expanded_indicators import _to_web_grid


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
SOURCE = PROJECT / "processed" / "sentinel2_cdse_expanded" / "sentinel2_l2a_reflectance_quality.tif"
DERIVED = PROJECT / "processed" / "sentinel2_indicators_expanded"
MAPS = PROJECT / "maps"
INDICATORS = PROJECT / "indicators" / "sentinel2_expanded_indicators.json"
CONNECTOR_METADATA = PROJECT / "metadata" / "sentinel2_cdse_expanded_connector.json"
MANIFEST = PROJECT / "metadata" / "sentinel2_expanded_indicators_manifest.json"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"


def calculate() -> dict:
    if not SOURCE.exists():
        raise RuntimeError("Expanded normalized Sentinel-2 source is missing.")
    DERIVED.mkdir(parents=True, exist_ok=True)
    connector = json.loads(CONNECTOR_METADATA.read_text())
    project = json.loads(PROJECT_MANIFEST.read_text())
    bbox = tuple(float(value) for value in project["study_area"]["expanded_urban_bbox_epsg4326"])
    with rasterio.open(SOURCE) as source:
        b02, b04, b08, b11, b12, scl, data_mask = source.read()
        profile = source.profile.copy()

    transformer = Transformer.from_crs(4326, profile["crs"], always_xy=True)
    ring = [
        transformer.transform(bbox[0], bbox[1]),
        transformer.transform(bbox[0], bbox[3]),
        transformer.transform(bbox[2], bbox[3]),
        transformer.transform(bbox[2], bbox[1]),
        transformer.transform(bbox[0], bbox[1]),
    ]
    scope_mask = geometry_mask(
        [{"type": "Polygon", "coordinates": [ring]}],
        out_shape=b02.shape,
        transform=profile["transform"],
        invert=True,
    )
    scl = np.rint(scl).astype("uint8")
    valid = (
        scope_mask
        & (data_mask >= 0.5)
        & np.isin(scl, [4, 5, 6])
        & np.isfinite(b02) & np.isfinite(b04) & np.isfinite(b08)
        & np.isfinite(b11) & np.isfinite(b12)
        & (b02 >= 0) & (b04 >= 0) & (b08 >= 0) & (b11 >= 0) & (b12 >= 0)
    )
    ndvi = np.full(b08.shape, np.nan, dtype="float32")
    ndmi = np.full(b08.shape, np.nan, dtype="float32")
    ndvi_denominator = b08 + b04
    ndmi_denominator = b08 + b11
    np.divide(b08 - b04, ndvi_denominator, out=ndvi, where=valid & (np.abs(ndvi_denominator) > 1e-6))
    np.divide(b08 - b11, ndmi_denominator, out=ndmi, where=valid & (np.abs(ndmi_denominator) > 1e-6))
    albedo = 0.356 * b02 + 0.130 * b04 + 0.373 * b08 + 0.085 * b11 + 0.072 * b12 - 0.0018
    albedo = np.where(valid & (albedo >= 0) & (albedo <= 1), albedo, np.nan)
    valid_ndvi = np.isfinite(ndvi)
    valid_ndmi = np.isfinite(ndmi)
    valid_albedo = np.isfinite(albedo)
    if min(valid_ndvi.sum(), valid_ndmi.sum(), valid_albedo.sum()) < 100:
        raise RuntimeError("Too few cloud-free expanded-scope Sentinel-2 pixels remain after SCL masking.")

    _write_raster(DERIVED / "ndvi_sentinel2_expanded.tif", ndvi, profile)
    _write_raster(DERIVED / "ndmi_sentinel2_expanded.tif", ndmi, profile)
    _write_raster(DERIVED / "albedo_sentinel2_expanded.tif", albedo, profile)
    ndvi_web, ndvi_web_valid = _to_web_grid(ndvi, valid_ndvi, profile, bbox, 10, resampling=Resampling.bilinear)
    ndmi_web, ndmi_web_valid = _to_web_grid(ndmi, valid_ndmi, profile, bbox, 10, resampling=Resampling.bilinear)
    albedo_web, albedo_web_valid = _to_web_grid(albedo, valid_albedo, profile, bbox, 10, resampling=Resampling.bilinear)
    _write_webp(MAPS / "sentinel2_ndvi_expanded.webp", _rgba(ndvi_web, [-0.2, 0.1, 0.3, 0.55, 0.85], [(128, 88, 61), (216, 193, 123), (188, 211, 125), (91, 157, 74), (22, 94, 50)], ndvi_web_valid))
    _write_webp(MAPS / "sentinel2_ndmi_expanded.webp", _rgba(ndmi_web, [-0.5, -0.15, 0.05, 0.25, 0.55], [(166, 87, 47), (224, 166, 82), (225, 218, 157), (103, 170, 154), (34, 102, 145)], ndmi_web_valid))
    _write_webp(MAPS / "sentinel2_albedo_expanded.webp", _rgba(albedo_web, [0.05, 0.12, 0.20, 0.30, 0.45], [(45, 59, 71), (94, 111, 116), (159, 163, 151), (218, 206, 168), (249, 239, 207)], albedo_web_valid))

    pixel_area_m2 = abs(profile["transform"].a * profile["transform"].e)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "product_scope": "La Seu d'Urgell, Castellciutat and Sant Antoni",
        "study_bbox_epsg4326": bbox,
        "source_scene": connector["scene_id"],
        "acquired_at_utc": connector["acquired_at_utc"],
        "source": connector["source"],
        "official_urls": connector["official_urls"],
        "license": connector["license"],
        "credentials": connector["credentials"],
        "crs": str(profile["crs"]),
        "output_resolution_m": 10,
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
            "ndmi": "(B08 - B11) / (B08 + B11), with B11 bilinearly resampled from 20 m to the 10 m output grid.",
            "albedo": "0.356*B02 + 0.130*B04 + 0.373*B08 + 0.085*B11 + 0.072*B12 - 0.0018; Sentinel-2 adaptation documented by Naegeli et al. (2017), DOI 10.3390/rs9020110.",
            "quality_mask": "Only source-valid pixels and SCL classes 4 vegetation, 5 bare/not vegetated and 6 water; clouds, cirrus, shadows, snow, defective and unclassified pixels excluded.",
            "reflectance_normalization": connector["normalization"],
        },
        "limitations": {
            "scene": "Single clear-sky acquisition; values are surface optical conditions at acquisition time, not seasonal climatology.",
            "ndvi": "Sensitive to soil background and saturation in dense vegetation; not a direct measure of biodiversity or canopy health.",
            "ndmi": "Relative canopy/vegetation moisture proxy, not volumetric soil moisture or irrigation demand.",
            "albedo": "Broadband estimate from a published spectral conversion; not an in-situ radiometric measurement. Mixed 10/20 m bands limit effective detail.",
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
    payload = calculate()
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
