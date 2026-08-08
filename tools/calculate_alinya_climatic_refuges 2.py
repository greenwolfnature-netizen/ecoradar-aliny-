#!/usr/bin/env python3
"""Derive and render potential climatic refuges for the Alinya study area.

This is an Analysis Engine product. It combines already normalized satellite
layers and does not download or replace any official source. The output is a
relative screening layer, not a field-validated climatic-refuge inventory.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from shapely.geometry import mapping


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
NDVI = PROJECT / "processed" / "teledeteccio" / "ndvi.tif"
NDMI = PROJECT / "processed" / "teledeteccio" / "ndmi.tif"
LST = PROJECT / "processed" / "landsat" / "landsat_lst.tif"
STUDY = PROJECT / "processed" / "study_area.gpkg"
SPRINGS = PROJECT / "raw" / "hidrologia" / "fonts.geojson"
DRAINAGE = PROJECT / "raw" / "hidrologia" / "eixos_drenatge.geojson"
RIVERS = PROJECT / "raw" / "hidrologia" / "rius_aca_che.geojson"
BASE_MAP = PROJECT / "maps" / "producte" / "mapa_base_alinya.png"

DERIVED = PROJECT / "processed" / "teledeteccio" / "refugis_climatics_potencials.tif"
WEBP = PROJECT / "maps" / "teledeteccio" / "refugis_climatics_potencials.webp"
PRODUCT_MAP = PROJECT / "maps" / "producte" / "mapa_refugis_climatics_alinya.png"
METADATA = PROJECT / "indicators" / "refugis_climatics_potencials.json"

WEIGHTS = {"frescor_lst": 0.50, "humitat_ndmi": 0.30, "vigor_ndvi": 0.20}
THRESHOLDS = {"suport": 0.50, "alt": 0.65, "molt_alt": 0.80}


def read_raster(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as source:
        values = source.read(1).astype("float32")
        profile = source.profile.copy()
        nodata = source.nodata
    valid = np.isfinite(values)
    if nodata is not None:
        valid &= values != nodata
    return np.where(valid, values, np.nan), profile


def normalize(values: np.ndarray, low: float, high: float) -> np.ndarray:
    return np.clip((values - low) / max(high - low, 1e-9), 0.0, 1.0)


def write_rgba(path: Path, rgba: np.ndarray, driver: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    options = {"QUALITY": 88} if driver == "WEBP" else {}
    with rasterio.open(
        path,
        "w",
        driver=driver,
        width=rgba.shape[1],
        height=rgba.shape[0],
        count=4,
        dtype="uint8",
        **options,
    ) as target:
        for band in range(4):
            target.write(rgba[..., band], band + 1)


def refuge_rgba(index: np.ndarray, valid: np.ndarray) -> np.ndarray:
    rgba = np.zeros((*index.shape, 4), dtype="uint8")
    classes = [
        (valid & (index < THRESHOLDS["suport"]), (225, 229, 211, 38)),
        (valid & (index >= THRESHOLDS["suport"]) & (index < THRESHOLDS["alt"]), (151, 199, 186, 145)),
        (valid & (index >= THRESHOLDS["alt"]) & (index < THRESHOLDS["molt_alt"]), (50, 139, 159, 190)),
        (valid & (index >= THRESHOLDS["molt_alt"]), (31, 73, 125, 225)),
    ]
    for mask, color in classes:
        rgba[mask] = color
    return rgba


def overlay_hydrology(rgba: np.ndarray, profile: dict) -> np.ndarray:
    """Burn the clipped official hydrology context into the web raster."""
    study_metric = gpd.read_file(STUDY).to_crs(25831)
    target_crs = profile["crs"]
    springs = gpd.read_file(PROJECT / "processed" / "hidrologia.gpkg", layer="fonts").to_crs(25831)
    springs.geometry = springs.geometry.buffer(45)
    springs = springs.to_crs(target_crs)
    hydro_geometries = []
    for layer_name in ("eixos_drenatge", "rius_aca_che"):
        layer = gpd.read_file(PROJECT / "processed" / "hidrologia.gpkg", layer=layer_name).to_crs(25831)
        clipped = gpd.clip(layer, study_metric)
        if not clipped.empty:
            clipped.geometry = clipped.geometry.buffer(18)
            hydro_geometries.extend(clipped.to_crs(target_crs).geometry.tolist())
    if hydro_geometries:
        hydro_mask = rasterize(
            [(mapping(geometry), 1) for geometry in hydro_geometries],
            out_shape=rgba.shape[:2],
            transform=profile["transform"],
            fill=0,
            all_touched=True,
        ).astype(bool)
        rgba[hydro_mask] = (47, 126, 171, 245)
    if not springs.empty:
        spring_mask = rasterize(
            [(mapping(geometry), 1) for geometry in springs.geometry],
            out_shape=rgba.shape[:2],
            transform=profile["transform"],
            fill=0,
            all_touched=True,
        ).astype(bool)
        rgba[spring_mask] = (14, 79, 122, 255)
    return rgba


def resize_bands(values: np.ndarray, height: int, width: int, resampling: Resampling) -> np.ndarray:
    bands = values.shape[0]
    output = np.zeros((bands, height, width), dtype=values.dtype)
    for band in range(bands):
        reproject(
            values[band],
            output[band],
            src_transform=from_bounds(0, 0, values.shape[2], values.shape[1], values.shape[2], values.shape[1]),
            src_crs="EPSG:3857",
            dst_transform=from_bounds(0, 0, values.shape[2], values.shape[1], width, height),
            dst_crs="EPSG:3857",
            resampling=resampling,
        )
    return output


def product_map(rgba: np.ndarray, bounds: tuple[float, float, float, float]) -> None:
    with rasterio.open(BASE_MAP) as base_source:
        base = base_source.read().astype("float32")
    height, width = base.shape[1:]
    overlay = resize_bands(np.moveaxis(rgba, -1, 0), height, width, Resampling.nearest)
    alpha = overlay[3:4] / 255.0
    composed = base[:3] * (1.0 - alpha) + overlay[:3] * alpha

    study = gpd.read_file(STUDY).to_crs(4326)
    springs = gpd.read_file(SPRINGS).to_crs(25831)
    springs = springs[springs.geometry.within(gpd.read_file(STUDY).to_crs(25831).geometry.iloc[0])].copy()
    springs.geometry = springs.geometry.buffer(45).to_crs(4326)
    hydro_parts = []
    for source_path in (DRAINAGE, RIVERS):
        layer = gpd.read_file(source_path).to_crs(25831)
        clipped = gpd.clip(layer, gpd.read_file(STUDY).to_crs(25831))
        if not clipped.empty:
            clipped.geometry = clipped.geometry.buffer(18)
            hydro_parts.extend(clipped.to_crs(4326).geometry.tolist())

    transform = from_bounds(*bounds, width, height)
    if hydro_parts:
        hydro_mask = rasterize([(mapping(geom), 1) for geom in hydro_parts], out_shape=(height, width), transform=transform, fill=0, all_touched=True).astype(bool)
        composed[:, hydro_mask] = np.asarray([47, 126, 171], dtype="float32")[:, None]
    if not springs.empty:
        spring_mask = rasterize([(mapping(geom), 1) for geom in springs.geometry], out_shape=(height, width), transform=transform, fill=0, all_touched=True).astype(bool)
        composed[:, spring_mask] = np.asarray([14, 79, 122], dtype="float32")[:, None]
    boundary = gpd.read_file(STUDY).to_crs(25831).geometry.boundary.buffer(12).to_crs(4326)
    boundary_mask = rasterize([(mapping(geom), 1) for geom in boundary], out_shape=(height, width), transform=transform, fill=0, all_touched=True).astype(bool)
    composed[:, boundary_mask] = np.asarray([13, 59, 46], dtype="float32")[:, None]

    output = np.clip(composed, 0, 255).astype("uint8")
    PRODUCT_MAP.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(PRODUCT_MAP, "w", driver="PNG", width=width, height=height, count=3, dtype="uint8") as target:
        target.write(output)


def calculate() -> dict:
    ndvi, profile = read_raster(NDVI)
    ndmi, ndmi_profile = read_raster(NDMI)
    if ndmi.shape != ndvi.shape or ndmi_profile["transform"] != profile["transform"]:
        raise RuntimeError("NDVI and NDMI must use the same normalized grid")

    lst, lst_profile = read_raster(LST)
    lst_on_grid = np.full(ndvi.shape, np.nan, dtype="float32")
    reproject(
        lst,
        lst_on_grid,
        src_transform=lst_profile["transform"],
        src_crs=lst_profile["crs"],
        src_nodata=np.nan,
        dst_transform=profile["transform"],
        dst_crs=profile["crs"],
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )

    study = gpd.read_file(STUDY).to_crs(profile["crs"])
    study_mask = geometry_mask([mapping(geom) for geom in study.geometry], out_shape=ndvi.shape, transform=profile["transform"], invert=True)
    valid = study_mask & np.isfinite(ndvi) & np.isfinite(ndmi) & np.isfinite(lst_on_grid) & (ndvi >= 0.30)

    sentinel = json.loads((PROJECT / "indicators" / "teledeteccio_sentinel2.json").read_text(encoding="utf-8"))
    satellite = json.loads((PROJECT / "indicators" / "teledeteccio_satellite_layers.json").read_text(encoding="utf-8"))
    ndvi_stats = sentinel["metrics"]["ndvi"]
    ndmi_stats = sentinel["metrics"]["ndmi"]
    lst_stats = satellite["surface_temperature"]["metrics_c"]

    coolness = 1.0 - normalize(lst_on_grid, lst_stats["p10"], lst_stats["p90"])
    moisture = normalize(ndmi, ndmi_stats["p10"], ndmi_stats["p90"])
    vigor = normalize(ndvi, ndvi_stats["p10"], ndvi_stats["p90"])
    index = WEIGHTS["frescor_lst"] * coolness + WEIGHTS["humitat_ndmi"] * moisture + WEIGHTS["vigor_ndvi"] * vigor
    index = np.where(valid, index, np.nan).astype("float32")

    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    output_profile = profile.copy()
    output_profile.update(driver="GTiff", count=1, dtype="float32", nodata=-9999.0, compress="deflate")
    with rasterio.open(DERIVED, "w", **output_profile) as target:
        target.write(np.where(np.isfinite(index), index, -9999.0), 1)

    rgba = overlay_hydrology(refuge_rgba(index, valid), profile)
    write_rgba(WEBP, rgba, "WEBP")
    bounds = tuple(float(value) for value in study.total_bounds)
    product_map(rgba, bounds)

    valid_count = int(valid.sum())
    distribution = {}
    class_masks = {
        "suport": valid & (index >= THRESHOLDS["suport"]) & (index < THRESHOLDS["alt"]),
        "alt": valid & (index >= THRESHOLDS["alt"]) & (index < THRESHOLDS["molt_alt"]),
        "molt_alt": valid & (index >= THRESHOLDS["molt_alt"]),
    }
    for name, mask in class_masks.items():
        distribution[name] = {
            "pixels": int(mask.sum()),
            "share_of_vegetated_valid_pct": round(100.0 * float(mask.sum()) / max(valid_count, 1), 1),
        }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Muntanya d'Alinya",
        "status": "verified_analysis",
        "name": "Potencial relatiu de refugi climatic",
        "sources": {
            "temperature": satellite["surface_temperature"]["source"],
            "temperature_period": satellite["surface_temperature"]["date_range"],
            "ndmi_ndvi": f"Copernicus Sentinel-2 L2A {sentinel['source_scene']}",
            "hydrology_context": "ACA and project-normalized official hydrology layers",
        },
        "method": {
            "formula": "0.50*frescor_LST + 0.30*humitat_NDMI + 0.20*vigor_NDVI",
            "normalization": "Each component clipped to its documented P10-P90 interval within Alinya",
            "vegetation_filter": "NDVI >= 0.30",
            "weights": WEIGHTS,
            "thresholds": THRESHOLDS,
        },
        "distribution": distribution,
        "high_or_very_high_share_of_vegetated_valid_pct": round(
            distribution["alt"]["share_of_vegetated_valid_pct"] + distribution["molt_alt"]["share_of_vegetated_valid_pct"], 1
        ),
        "outputs": {
            "geotiff": str(DERIVED.relative_to(PROJECT)),
            "webp": str(WEBP.relative_to(PROJECT)),
            "product_map": str(PRODUCT_MAP.relative_to(PROJECT)),
        },
        "limitations": (
            "Relative screening layer based on a two-summer daytime LST composite and one Sentinel-2 date. "
            "It is not air temperature, a climatic normal, microclimate monitoring or a field-validated refuge inventory. "
            "Weights and thresholds are explicit EcoRadar analysis assumptions."
        ),
    }
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(calculate(), ensure_ascii=False, indent=2))
