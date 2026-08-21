"""Render the Alinyà base-map relief from the verified ICGC 5 m DEM.

OpenStreetMap supplies the access network and mapped features but no elevation
model. This analysis product creates a neutral hypsometric hillshade from ICGC
and is displayed together with the existing OSM vectors.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds

from calculate_la_seu_expanded_indicators import _to_web_grid
from calculate_la_seu_sentinel2_indicators import _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
DEM = PROJECT / "raw" / "terrain" / "icgc_dem_5m_alinya_window.tif"
OUT = PROJECT / "maps" / "topografia" / "relleu_icgc.webp"
META = PROJECT / "metadata" / "relleu_base_icgc_osm.json"


def _colorize(elevation: np.ndarray, hillshade: np.ndarray, valid: np.ndarray, low: float, high: float):
    scaled = np.clip((elevation - low) / max(high - low, 1e-6), 0, 1)
    stops = np.array([0.0, 0.35, 0.70, 1.0], dtype="float32")
    colors = np.array([
        [203, 190, 151],
        [161, 184, 135],
        [181, 181, 159],
        [232, 229, 218],
    ], dtype="float32")
    rgb = np.stack([np.interp(scaled, stops, colors[:, band]) for band in range(3)], axis=-1)
    light = 0.58 + 0.54 * np.clip(hillshade / 255.0, 0, 1)
    rgb = np.nan_to_num(np.clip(rgb * light[..., None], 0, 255), nan=0).astype("uint8")
    rgba = np.zeros((*elevation.shape, 4), dtype="uint8")
    rgba[..., :3] = rgb
    rgba[..., 3] = np.where(valid, 238, 0).astype("uint8")
    return rgba


def calculate() -> dict:
    with rasterio.open(DEM) as src:
        dem = src.read(1).astype("float32")
        profile = src.profile.copy()
        nodata = src.nodata
        bbox = tuple(float(v) for v in transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21))
    valid = np.isfinite(dem) if nodata is None else np.isfinite(dem) & (dem != nodata)
    dem_nan = np.where(valid, dem, np.nan)
    fill = float(np.nanmedian(dem_nan))
    working = np.where(valid, dem, fill)
    y_gradient, x_gradient = np.gradient(working, abs(profile["transform"].e), profile["transform"].a)
    slope = np.pi / 2 - np.arctan(np.hypot(x_gradient, y_gradient))
    aspect = np.arctan2(-x_gradient, y_gradient)
    azimuth = np.deg2rad(315.0)
    altitude = np.deg2rad(45.0)
    hillshade = 255 * (
        np.sin(altitude) * np.sin(slope)
        + np.cos(altitude) * np.cos(slope) * np.cos(azimuth - aspect)
    )
    hillshade = np.clip(hillshade, 0, 255).astype("float32")

    elevation_web, elevation_valid = _to_web_grid(
        dem_nan, valid, profile, bbox, 20, resampling=Resampling.bilinear
    )
    shade_web, shade_valid = _to_web_grid(
        hillshade, valid, profile, bbox, 20, resampling=Resampling.bilinear
    )
    web_valid = elevation_valid & shade_valid & np.isfinite(elevation_web) & np.isfinite(shade_web)
    displayed_elevation = elevation_web[web_valid]
    low, high = (float(v) for v in np.nanpercentile(displayed_elevation, [2, 98]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    _write_webp(OUT, _colorize(elevation_web, shade_web, web_valid, low, high))

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Muntanya d'Alinyà i context topogràfic immediat",
        "source": "ICGC Model d'elevacions del terreny 5 m",
        "source_file": str(DEM.relative_to(PROJECT)),
        "osm_role": "OpenStreetMap supplies access paths and mapped features; it does not supply the elevation raster",
        "method": "Hypsometric tint plus analytical hillshade from the unmasked ICGC window; azimuth 315 degrees, altitude 45 degrees",
        "display_resolution_m": 20,
        "elevation_m": {
            "minimum": round(float(np.nanmin(displayed_elevation)), 1),
            "median": round(float(np.nanmedian(displayed_elevation)), 1),
            "maximum": round(float(np.nanmax(displayed_elevation)), 1),
        },
        "bbox_epsg4326": bbox,
        "output": str(OUT.relative_to(PROJECT)),
        "status": "verified_analysis",
        "limitations": "Context relief may be visible outside the study boundary and in enclaves; analytical EcoRadar layers remain clipped to the validated study area. Not a contour map or a substitute for field navigation",
    }
    META.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    print(json.dumps(calculate(), ensure_ascii=False, indent=2))
