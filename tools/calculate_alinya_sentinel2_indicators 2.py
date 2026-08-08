"""Calculate Alinyà NDVI, NDMI and albedo from normalized Sentinel-2 L2A."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import mapping

from calculate_la_seu_sentinel2_indicators import _rgba, _stats, _write_raster, _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"
SOURCE = PROJECT / "processed" / "sentinel2_cdse" / "sentinel2_l2a_reflectance_quality.tif"
DERIVED = PROJECT / "processed" / "teledeteccio"
MAPS = PROJECT / "maps" / "teledeteccio"
INDICATORS = PROJECT / "indicators" / "teledeteccio_sentinel2.json"
CONNECTOR = PROJECT / "metadata" / "sentinel2_cdse_automated_connector.json"


def calculate() -> dict:
    if not SOURCE.is_file():
        raise FileNotFoundError("Run fetch_alinya_cdse_sentinel2.py before calculating indicators.")
    connector = json.loads(CONNECTOR.read_text(encoding="utf-8"))
    with rasterio.open(SOURCE) as source:
        if source.count != 7:
            raise RuntimeError("The normalized CDSE raster must contain B02, B04, B08, B11, B12, SCL and dataMask.")
        b02, b04, b08, b11, b12, scl, data_mask = source.read()
        profile = source.profile.copy()

    study = gpd.read_file(STUDY).to_crs(profile["crs"])
    scope = geometry_mask(
        [mapping(geometry) for geometry in study.geometry if geometry is not None],
        out_shape=b02.shape,
        transform=profile["transform"],
        invert=True,
    )
    scl = np.rint(scl).astype("uint8")
    valid = (
        scope
        & (data_mask >= 0.5)
        & np.isin(scl, [4, 5, 6])
        & np.isfinite(b02)
        & np.isfinite(b04)
        & np.isfinite(b08)
        & np.isfinite(b11)
        & np.isfinite(b12)
        & (b02 >= 0)
        & (b04 >= 0)
        & (b08 >= 0)
        & (b11 >= 0)
        & (b12 >= 0)
    )
    ndvi = np.full(b08.shape, np.nan, dtype="float32")
    ndmi = np.full(b08.shape, np.nan, dtype="float32")
    np.divide(b08 - b04, b08 + b04, out=ndvi, where=valid & (np.abs(b08 + b04) > 1e-6))
    np.divide(b08 - b11, b08 + b11, out=ndmi, where=valid & (np.abs(b08 + b11) > 1e-6))
    albedo = 0.356 * b02 + 0.130 * b04 + 0.373 * b08 + 0.085 * b11 + 0.072 * b12 - 0.0018
    albedo = np.where(valid & (albedo >= 0) & (albedo <= 1), albedo, np.nan)
    valid_ndvi = np.isfinite(ndvi)
    valid_ndmi = np.isfinite(ndmi)
    valid_albedo = np.isfinite(albedo)
    if min(valid_ndvi.sum(), valid_ndmi.sum(), valid_albedo.sum()) < 100:
        raise RuntimeError("Too few quality-screened Sentinel-2 pixels remain inside Alinyà.")

    DERIVED.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    _write_raster(DERIVED / "ndvi.tif", ndvi, profile)
    _write_raster(DERIVED / "ndmi.tif", ndmi, profile)
    _write_raster(DERIVED / "albedo.tif", albedo, profile)
    _write_webp(MAPS / "ndvi.webp", _rgba(ndvi, [-0.2, 0.1, 0.3, 0.55, 0.85], [(128, 88, 61), (216, 193, 123), (188, 211, 125), (91, 157, 74), (22, 94, 50)], valid_ndvi))
    _write_webp(MAPS / "ndmi.webp", _rgba(ndmi, [-0.5, -0.15, 0.05, 0.25, 0.55], [(166, 87, 47), (224, 166, 82), (225, 218, 157), (103, 170, 154), (34, 102, 145)], valid_ndmi))
    _write_webp(MAPS / "albedo.webp", _rgba(albedo, [0.05, 0.12, 0.20, 0.30, 0.45], [(45, 59, 71), (94, 111, 116), (159, 163, 151), (218, 206, 168), (249, 239, 207)], valid_albedo))

    pixel_area_m2 = abs(profile["transform"].a * profile["transform"].e)
    bbox = tuple(float(value) for value in gpd.read_file(STUDY).to_crs(4326).total_bounds)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Muntanya d'Alinyà",
        "source_scene": connector["scene_id"],
        "acquired_at_utc": connector["acquired_at_utc"],
        "source": connector["source"],
        "official_urls": connector["official_urls"],
        "license": connector["license"],
        "study_bbox_epsg4326": bbox,
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
            "ndvi": "(B08 - B04) / (B08 + B04), Sentinel-2 L2A bottom-of-atmosphere reflectance.",
            "ndmi": "(B08 - B11) / (B08 + B11), with B11 resampled from 20 m to the 10 m output grid.",
            "albedo": "0.356*B02 + 0.130*B04 + 0.373*B08 + 0.085*B11 + 0.072*B12 - 0.0018; published Sentinel-2 narrow-to-broadband adaptation documented by Naegeli et al. (2017), DOI 10.3390/rs9020110.",
            "quality_mask": "dataMask=1 and SCL classes 4, 5 or 6; cloud, cirrus, shadow, snow and invalid classes excluded.",
        },
        "limitations": {
            "scene": "Single clear-sky acquisition; not a seasonal climatology.",
            "ndvi": "Vegetation-vigour proxy, not biodiversity or individual plant health.",
            "ndmi": "Relative vegetation-moisture proxy, not field fuel moisture or volumetric soil moisture.",
            "albedo": "Broadband spectral estimate, not in-situ radiometry; effective detail is limited by mixed 10/20 m input bands.",
        },
        "outputs": {
            "ndvi": "maps/teledeteccio/ndvi.webp",
            "ndmi": "maps/teledeteccio/ndmi.webp",
            "albedo": "maps/teledeteccio/albedo.webp",
        },
    }
    INDICATORS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(calculate(), ensure_ascii=False, indent=2))
