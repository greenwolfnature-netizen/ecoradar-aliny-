"""Calculate the integrated EcoRadar wildfire-danger reading for Alinyà.

This is an Analysis Engine product, not a connector and not an official daily
danger layer. It combines the verified Generalitat 2024 structural-danger map
with observed Landsat surface temperature, Sentinel-2 NDMI, mapped vegetation
type and the existing topography/access/history concurrence score.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from shapely.geometry import mapping

from calculate_la_seu_sentinel2_indicators import _write_raster, _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"
OFFICIAL = PROJECT / "raw" / "incendis" / "perill_basic_2024" / "PERILLBASICINCENDI.tif"
if not OFFICIAL.is_file():
    # Transitional fallback for the multi-project workspace. The standalone
    # Alinyà repository contains its own official source copy.
    OFFICIAL = ROOT / "projectes" / "LaSeu_Urba" / "raw" / "incendis" / "perill_basic_2024" / "PERILLBASICINCENDI.tif"
LST = PROJECT / "processed" / "landsat" / "landsat_lst.tif"
NDMI = PROJECT / "processed" / "teledeteccio" / "ndmi.tif"
LANDCOVER = PROJECT / "maps" / "incendis" / "condicions_cobertes_alinya.geojson"
CONCURRENCE = PROJECT / "maps" / "incendis_similarity" / "similitud_condicions_incendi_alinya.geojson"
OUT_TIF = PROJECT / "processed" / "incendis" / "perill_integrat_ecoradar.tif"
OUT_WEBP = PROJECT / "maps" / "incendis" / "perill_integrat_ecoradar.webp"
OUT_JSON = PROJECT / "indicators" / "perill_integrat_ecoradar.json"
META_JSON = PROJECT / "metadata" / "perill_integrat_ecoradar.json"
CRS = "EPSG:25831"
RES = 100.0

WEIGHTS = {
    "official_structural_2024": 0.30,
    "surface_temperature": 0.20,
    "vegetation_dryness_ndmi": 0.20,
    "vegetation_type_fuel_potential": 0.20,
    "territorial_concurrence": 0.10,
}

FUEL_SCORES = {
    "Aigua": 0.00,
    "Roquissars / sol nu": 0.10,
    "Vies i nuclis": 0.15,
    "Conreus": 0.40,
    "Prats i herbassars": 0.55,
    "Matollar": 0.90,
    "Bosc": 1.00,
}


def _grid():
    study = gpd.read_file(STUDY).to_crs(CRS)
    minx, miny, maxx, maxy = (float(v) for v in study.total_bounds)
    left = math.floor(minx / RES) * RES
    top = math.ceil(maxy / RES) * RES
    width = math.ceil((maxx - left) / RES)
    height = math.ceil((top - miny) / RES)
    transform = from_origin(left, top, RES, RES)
    mask = geometry_mask(
        [mapping(g) for g in study.geometry if g is not None],
        out_shape=(height, width), transform=transform, invert=True,
    )
    return study, (height, width), transform, mask


def _reproject(path: Path, shape, transform, resampling: Resampling) -> np.ndarray:
    destination = np.full(shape, np.nan, dtype="float32")
    with rasterio.open(path) as src:
        source = src.read(1)
        source_nodata = src.nodata
        reproject(
            source=source,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=source_nodata,
            dst_transform=transform,
            dst_crs=CRS,
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return destination


def _robust_scale(values: np.ndarray, mask: np.ndarray, *, inverse=False):
    valid = mask & np.isfinite(values)
    p10, p90 = (float(v) for v in np.nanpercentile(values[valid], [10, 90]))
    scaled = np.clip((values - p10) / max(p90 - p10, 1e-6), 0, 1)
    if inverse:
        scaled = 1 - scaled
    return np.where(valid, scaled, np.nan).astype("float32"), p10, p90


def _rgba(index: np.ndarray, valid: np.ndarray) -> np.ndarray:
    rgba = np.zeros((*index.shape, 4), dtype="uint8")
    classes = [
        (index < 0.25, (44, 123, 182)),
        ((index >= 0.25) & (index < 0.50), (240, 230, 91)),
        ((index >= 0.50) & (index < 0.70), (243, 154, 56)),
        (index >= 0.70, (139, 30, 45)),
    ]
    for selected, color in classes:
        selected &= valid
        rgba[selected, 0] = color[0]
        rgba[selected, 1] = color[1]
        rgba[selected, 2] = color[2]
        rgba[selected, 3] = 235
    return rgba


def calculate() -> dict:
    study, shape, transform, study_mask = _grid()
    official_raw = _reproject(OFFICIAL, shape, transform, Resampling.nearest)
    official_valid = study_mask & np.isfinite(official_raw) & (official_raw >= 1) & (official_raw <= 10)
    official = np.where(official_valid, (official_raw - 1) / 9, np.nan).astype("float32")

    lst_raw = _reproject(LST, shape, transform, Resampling.bilinear)
    temperature, temp_p10, temp_p90 = _robust_scale(lst_raw, study_mask)
    ndmi_raw = _reproject(NDMI, shape, transform, Resampling.bilinear)
    dryness, ndmi_p10, ndmi_p90 = _robust_scale(ndmi_raw, study_mask, inverse=True)

    covers = gpd.read_file(LANDCOVER).to_crs(CRS)
    fuel = rasterize(
        ((mapping(row.geometry), FUEL_SCORES.get(row.condicio, np.nan)) for row in covers.itertuples()),
        out_shape=shape, transform=transform, fill=np.nan, dtype="float32",
    )
    fuel = np.where(study_mask, fuel, np.nan)

    concurrence_gdf = gpd.read_file(CONCURRENCE).to_crs(CRS)
    concurrence = rasterize(
        ((mapping(row.geometry), float(row.similitud_score)) for row in concurrence_gdf.itertuples()),
        out_shape=shape, transform=transform, fill=np.nan, dtype="float32",
    )
    concurrence = np.where(study_mask, np.clip(concurrence, 0, 1), np.nan)

    components = {
        "official_structural_2024": official,
        "surface_temperature": temperature,
        "vegetation_dryness_ndmi": dryness,
        "vegetation_type_fuel_potential": fuel,
        "territorial_concurrence": concurrence,
    }
    numerator = np.zeros(shape, dtype="float32")
    denominator = np.zeros(shape, dtype="float32")
    for key, component in components.items():
        available = study_mask & np.isfinite(component)
        numerator[available] += WEIGHTS[key] * component[available]
        denominator[available] += WEIGHTS[key]
    valid = study_mask & (denominator > 0)
    integrated = np.where(valid, numerator / denominator, np.nan).astype("float32")
    coverage_pct = float(100 * valid.sum() / study_mask.sum())
    if coverage_pct < 99.9:
        raise RuntimeError(f"Integrated fire reading covers only {coverage_pct:.2f}%")

    profile = {
        "driver": "GTiff", "height": shape[0], "width": shape[1], "count": 1,
        "dtype": "float32", "crs": CRS, "transform": transform,
        "nodata": -9999.0, "compress": "deflate",
    }
    _write_raster(OUT_TIF, np.where(valid, integrated, -9999).astype("float32"), profile)
    _write_webp(OUT_WEBP, _rgba(integrated, valid))

    pixel_area_ha = RES * RES / 10_000
    class_masks = {
        "baix": valid & (integrated < 0.25),
        "moderat": valid & (integrated >= 0.25) & (integrated < 0.50),
        "alt": valid & (integrated >= 0.50) & (integrated < 0.70),
        "molt_alt": valid & (integrated >= 0.70),
    }
    distribution = {
        key: {
            "cells": int(selected.sum()),
            "area_ha": round(float(selected.sum() * pixel_area_ha), 1),
            "share_pct": round(float(100 * selected.sum() / valid.sum()), 1),
        }
        for key, selected in class_masks.items()
    }
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "indicator": "integrated_structural_wildfire_danger_ecoradar",
        "status": "verified_analysis",
        "scope": "Muntanya d'Alinyà",
        "crs": CRS,
        "resolution_m": RES,
        "coverage_pct": round(coverage_pct, 2),
        "formula": "weighted mean of available normalized components; weights renormalized where the official forest-only raster has NoData",
        "weights": WEIGHTS,
        "components": {
            "official_structural_2024": "Generalitat Mapa bàsic de perill d'incendi forestal 2024, values 1-10 normalized to 0-1",
            "surface_temperature": f"Landsat warm-season composite robust-scaled between study P10={temp_p10:.2f} C and P90={temp_p90:.2f} C",
            "vegetation_dryness_ndmi": f"inverse Sentinel-2 NDMI robust-scaled between study P10={ndmi_p10:.3f} and P90={ndmi_p90:.3f}",
            "vegetation_type_fuel_potential": FUEL_SCORES,
            "territorial_concurrence": "existing 0-1 score combining cover, habitat, slope, aspect, elevation and access similarity to historical fires",
        },
        "thresholds": {"baix": "<0.25", "moderat": "0.25-<0.50", "alt": "0.50-<0.70", "molt_alt": ">=0.70"},
        "statistics": {
            "minimum": round(float(np.nanmin(integrated[valid])), 3),
            "median": round(float(np.nanmedian(integrated[valid])), 3),
            "maximum": round(float(np.nanmax(integrated[valid])), 3),
            "distribution": distribution,
        },
        "outputs": {
            "tif": str(OUT_TIF.relative_to(PROJECT)),
            "webp": str(OUT_WEBP.relative_to(PROJECT)),
        },
        "limitations": [
            "EcoRadar integrated structural reading; not the official daily danger, Pla Alfa, ignition probability or emergency alert.",
            "Fuel-potential scores are explicit analytical assumptions by land-cover class and require field validation of fuel load and vertical structure.",
            "Landsat temperature is a warm-season surface composite and NDMI is a relative spectral moisture proxy, not fine-fuel moisture.",
        ],
    }
    OUT_JSON.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    META_JSON.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    print(json.dumps(calculate(), ensure_ascii=False, indent=2))
