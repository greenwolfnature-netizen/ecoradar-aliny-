"""Calculate NDVI, NDMI and broadband albedo from normalized Sentinel-2 L2A."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.features import geometry_mask


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
SOURCE = PROJECT / "processed" / "sentinel2_cdse" / "sentinel2_l2a_reflectance_quality.tif"
DERIVED = PROJECT / "processed" / "sentinel2_indicators"
MAPS = PROJECT / "maps"
INDICATORS = PROJECT / "indicators" / "sentinel2_urban_indicators.json"
CONNECTOR_METADATA = PROJECT / "metadata" / "sentinel2_cdse_connector.json"
MANIFEST = PROJECT / "metadata" / "sentinel2_indicators_manifest.json"
LAYER_MANIFEST = PROJECT / "metadata" / "layer_manifest.json"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"


def _write_raster(path: Path, values: np.ndarray, profile: dict) -> None:
    output = profile.copy()
    output.update(driver="GTiff", count=1, dtype="float32", nodata=-9999.0, compress="deflate")
    with rasterio.open(path, "w", **output) as target:
        target.write(np.where(np.isfinite(values), values, -9999.0).astype("float32"), 1)


def _rgba(values, stops, colors, valid, alpha=220):
    rgba = np.zeros((*values.shape, 4), dtype="uint8")
    clipped = np.clip(values, stops[0], stops[-1])
    for index in range(len(stops) - 1):
        low, high = stops[index], stops[index + 1]
        mask = valid & (clipped >= low) & (clipped <= high if index == len(stops) - 2 else clipped < high)
        if not np.any(mask):
            continue
        ratio = (clipped[mask] - low) / max(high - low, 1e-9)
        start = np.asarray(colors[index], dtype="float64")
        end = np.asarray(colors[index + 1], dtype="float64")
        rgba[mask, :3] = np.round(start + ratio[:, None] * (end - start)).astype("uint8")
        rgba[mask, 3] = alpha
    return rgba


def _write_png(path: Path, rgba: np.ndarray) -> None:
    with rasterio.open(path, "w", driver="PNG", width=rgba.shape[1], height=rgba.shape[0], count=4, dtype="uint8") as target:
        for band in range(4):
            target.write(rgba[..., band], band + 1)


def _write_webp(path: Path, rgba: np.ndarray) -> None:
    with rasterio.open(
        path,
        "w",
        driver="WEBP",
        width=rgba.shape[1],
        height=rgba.shape[0],
        count=4,
        dtype="uint8",
        QUALITY=80,
    ) as target:
        for band in range(4):
            target.write(rgba[..., band], band + 1)


def _stats(values, valid):
    selected = values[valid]
    return {
        "mean": round(float(np.mean(selected)), 3),
        "median": round(float(np.median(selected)), 3),
        "p10": round(float(np.percentile(selected, 10)), 3),
        "p90": round(float(np.percentile(selected, 90)), 3),
    }


def calculate() -> dict:
    if not SOURCE.exists():
        raise RuntimeError("Normalized Sentinel-2 source is missing; run fetch_la_seu_cdse_sentinel2.py first.")
    DERIVED.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    connector = json.loads(CONNECTOR_METADATA.read_text())

    with rasterio.open(SOURCE) as source:
        b02, b04, b08, b11, b12, scl, data_mask = source.read()
        profile = source.profile.copy()

    project_manifest = json.loads(PROJECT_MANIFEST.read_text())
    minlon, minlat, maxlon, maxlat = project_manifest["study_area"]["analysis_core_bbox_epsg4326"]
    transformer = Transformer.from_crs(4326, profile["crs"], always_xy=True)
    ring = [
        transformer.transform(minlon, minlat),
        transformer.transform(minlon, maxlat),
        transformer.transform(maxlon, maxlat),
        transformer.transform(maxlon, minlat),
        transformer.transform(minlon, minlat),
    ]
    core_mask = geometry_mask(
        [{"type": "Polygon", "coordinates": [ring]}],
        out_shape=b02.shape,
        transform=profile["transform"],
        invert=True,
    )

    scl = np.rint(scl).astype("uint8")
    valid = (
        core_mask
        & (data_mask >= 0.5)
        & np.isin(scl, [4, 5, 6])
        & np.isfinite(b02) & np.isfinite(b04) & np.isfinite(b08)
        & np.isfinite(b11) & np.isfinite(b12)
        & (b02 >= 0) & (b04 >= 0) & (b08 >= 0) & (b11 >= 0) & (b12 >= 0)
    )
    ndvi_denominator = b08 + b04
    ndmi_denominator = b08 + b11
    ndvi = np.full(b08.shape, np.nan, dtype="float32")
    ndmi = np.full(b08.shape, np.nan, dtype="float32")
    np.divide(b08 - b04, ndvi_denominator, out=ndvi, where=valid & (np.abs(ndvi_denominator) > 1e-6))
    np.divide(b08 - b11, ndmi_denominator, out=ndmi, where=valid & (np.abs(ndmi_denominator) > 1e-6))
    albedo = 0.356 * b02 + 0.130 * b04 + 0.373 * b08 + 0.085 * b11 + 0.072 * b12 - 0.0018
    albedo = np.where(valid & (albedo >= 0) & (albedo <= 1), albedo, np.nan)
    valid_ndvi = np.isfinite(ndvi)
    valid_ndmi = np.isfinite(ndmi)
    valid_albedo = np.isfinite(albedo)
    if min(valid_ndvi.sum(), valid_ndmi.sum(), valid_albedo.sum()) < 100:
        raise RuntimeError("Too few cloud-free Sentinel-2 pixels remain after SCL quality masking.")

    _write_raster(DERIVED / "ndvi_sentinel2.tif", ndvi, profile)
    _write_raster(DERIVED / "ndmi_sentinel2.tif", ndmi, profile)
    _write_raster(DERIVED / "albedo_sentinel2.tif", albedo, profile)
    _write_webp(MAPS / "sentinel2_ndvi.webp", _rgba(ndvi, [-0.2, 0.1, 0.3, 0.55, 0.85], [(128, 88, 61), (216, 193, 123), (188, 211, 125), (91, 157, 74), (22, 94, 50)], valid_ndvi))
    _write_webp(MAPS / "sentinel2_ndmi.webp", _rgba(ndmi, [-0.5, -0.15, 0.05, 0.25, 0.55], [(166, 87, 47), (224, 166, 82), (225, 218, 157), (103, 170, 154), (34, 102, 145)], valid_ndmi))
    _write_webp(MAPS / "sentinel2_albedo.webp", _rgba(albedo, [0.05, 0.12, 0.20, 0.30, 0.45], [(45, 59, 71), (94, 111, 116), (159, 163, 151), (218, 206, 168), (249, 239, 207)], valid_albedo))

    pixel_area_m2 = abs(profile["transform"].a * profile["transform"].e)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_scene": connector["scene_id"],
        "acquired_at_utc": connector["acquired_at_utc"],
        "source": connector["source"],
        "official_urls": connector["official_urls"],
        "license": connector["license"],
        "crs": str(profile["crs"]),
        "output_resolution_m": 10,
        "native_band_resolution_m": {"B02": 10, "B04": 10, "B08": 10, "B11": 20, "B12": 20},
        "valid_pixels": int(valid.sum()),
        "valid_area_ha": round(float(valid.sum() * pixel_area_m2 / 10000), 1),
        "metrics": {
            "ndvi": _stats(ndvi, valid_ndvi),
            "ndmi": _stats(ndmi, valid_ndmi),
            "albedo": _stats(albedo, valid_albedo),
        },
        "methods": {
            "ndvi": "(B08 - B04) / (B08 + B04), using Sentinel-2 L2A bottom-of-atmosphere reflectance.",
            "ndmi": "(B08 - B11) / (B08 + B11), using Sentinel-2 L2A bottom-of-atmosphere reflectance; B11 bilinearly resampled from 20 m to the 10 m output grid.",
            "albedo": "0.356*B02 + 0.130*B04 + 0.373*B08 + 0.085*B11 + 0.072*B12 - 0.0018; Sentinel-2 narrow-to-broadband adaptation documented by Naegeli et al. (2017), DOI 10.3390/rs9020110.",
            "quality_mask": "Only dataMask=1 and SCL classes 4 vegetation, 5 bare/not vegetated and 6 water; clouds, cirrus, shadows, snow, defective and unclassified pixels excluded.",
        },
        "limitations": {
            "scene": "Single clear-sky acquisition; values are surface optical conditions at acquisition time, not seasonal climatology.",
            "ndvi": "Sensitive to soil background and saturation in dense vegetation; not a direct measure of biodiversity or canopy health.",
            "ndmi": "Relative canopy/vegetation moisture proxy, not volumetric soil moisture or irrigation demand.",
            "albedo": "Broadband estimate from a published spectral conversion; not an in-situ radiometric measurement. Mixed 10/20 m bands limit effective detail.",
        },
        "outputs": {
            "ndvi_tif": "processed/sentinel2_indicators/ndvi_sentinel2.tif",
            "ndmi_tif": "processed/sentinel2_indicators/ndmi_sentinel2.tif",
            "albedo_tif": "processed/sentinel2_indicators/albedo_sentinel2.tif",
            "ndvi_webp": "maps/sentinel2_ndvi.webp",
            "ndmi_webp": "maps/sentinel2_ndmi.webp",
            "albedo_webp": "maps/sentinel2_albedo.webp",
        },
    }
    INDICATORS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    layer_manifest = json.loads(LAYER_MANIFEST.read_text())
    included = layer_manifest.setdefault("layers_included", [])
    for layer in ["ndvi_sentinel2_l2a", "ndmi_sentinel2_l2a", "albedo_sentinel2_l2a"]:
        if layer not in included:
            included.append(layer)
    layer_manifest["sentinel2_indicators"] = payload
    LAYER_MANIFEST.write_text(json.dumps(layer_manifest, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    payload = calculate()
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
