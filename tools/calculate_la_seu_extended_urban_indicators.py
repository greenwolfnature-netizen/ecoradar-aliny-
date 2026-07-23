"""Calculate verified extended urban indicators for the La Seu EcoRadar map."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
CLMS = PROJECT / "processed" / "copernicus_hrl"
DERIVED = PROJECT / "processed" / "extended_indicators"
MAPS = PROJECT / "maps"
INDICATORS = PROJECT / "indicators" / "extended_urban_indicators.json"
METADATA = PROJECT / "metadata" / "extended_indicators_manifest.json"
LAYER_MANIFEST = PROJECT / "metadata" / "layer_manifest.json"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
LIDAR_ARRAYS = PROJECT / "processed" / "lidar_core_arrays.npz"
LANDSAT_ARRAYS = PROJECT / "processed" / "landsat_lst_core.npz"


def _read(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as source:
        return source.read(1), source.profile.copy()


def _write_raster(path: Path, values: np.ndarray, profile: dict, *, dtype: str, nodata) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = profile.copy()
    output.update(driver="GTiff", dtype=dtype, count=1, nodata=nodata, compress="deflate", tiled=False)
    with rasterio.open(path, "w", **output) as target:
        target.write(values.astype(dtype), 1)


def _rgba_continuous(values: np.ndarray, stops: list[float], colors: list[tuple[int, int, int]], valid=None, alpha=215) -> np.ndarray:
    valid = np.isfinite(values) if valid is None else (valid & np.isfinite(values))
    rgba = np.zeros((*values.shape, 4), dtype="uint8")
    clipped = np.clip(values, stops[0], stops[-1])
    for index in range(len(stops) - 1):
        lower, upper = stops[index], stops[index + 1]
        mask = valid & (clipped >= lower) & (clipped <= upper if index == len(stops) - 2 else clipped < upper)
        if not np.any(mask):
            continue
        ratio = (clipped[mask] - lower) / max(upper - lower, 1e-9)
        start = np.asarray(colors[index], dtype="float64")
        end = np.asarray(colors[index + 1], dtype="float64")
        rgba[mask, :3] = np.round(start + ratio[:, None] * (end - start)).astype("uint8")
        rgba[mask, 3] = alpha
    return rgba


def _write_png(path: Path, rgba: np.ndarray) -> None:
    with rasterio.open(
        path,
        "w",
        driver="PNG",
        width=rgba.shape[1],
        height=rgba.shape[0],
        count=4,
        dtype="uint8",
    ) as target:
        for band in range(4):
            target.write(rgba[..., band], band + 1)


def _reproject_array(values, source_profile, destination_shape, destination_transform, destination_crs, *, resampling) -> np.ndarray:
    destination = np.full(destination_shape, np.nan, dtype="float32")
    reproject(
        source=values.astype("float32"),
        destination=destination,
        src_transform=source_profile["transform"],
        src_crs=source_profile["crs"],
        dst_transform=destination_transform,
        dst_crs=destination_crs,
        src_nodata=255,
        dst_nodata=np.nan,
        resampling=resampling,
    )
    return destination


def calculate() -> dict:
    DERIVED.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)

    imd, profile = _read(CLMS / "imperviousness_2021.tif")
    tcd18, _ = _read(CLMS / "tree_cover_density_2018.tif")
    tcd23, _ = _read(CLMS / "tree_cover_density_2023.tif")
    herb23, _ = _read(CLMS / "herbaceous_cover_2023.tif")
    imd_f = imd.astype("float32")

    vegetation = ((tcd23 > 0) | (herb23 == 1)).astype("uint8")
    tree_change = tcd23.astype("int16") - tcd18.astype("int16")

    lidar = np.load(LIDAR_ARRAYS)
    layer_manifest = json.loads(LAYER_MANIFEST.read_text())
    lidar_bounds = layer_manifest["lidar"]["bbox_epsg25831"]
    slope = lidar["terrain_slope"].astype("float32")
    slope_profile = {
        "transform": from_bounds(*lidar_bounds, slope.shape[1], slope.shape[0]),
        "crs": "EPSG:25831",
    }
    slope_on_clms = _reproject_array(
        slope,
        slope_profile,
        imd.shape,
        profile["transform"],
        profile["crs"],
        resampling=Resampling.bilinear,
    )
    slope_component = np.clip(np.nan_to_num(slope_on_clms, nan=0.0), 0, 30) / 30 * 100
    runoff_proxy = 0.75 * imd_f + 0.25 * slope_component

    landsat = np.load(LANDSAT_ARRAYS)
    lst = landsat["lst_c"].astype("float32")
    lst_valid = landsat["valid"].astype(bool)
    lst_bounds = [float(value) for value in landsat["bounds"]]
    lst_crs = str(landsat["crs"].item())
    lst_transform = from_bounds(*lst_bounds, lst.shape[1], lst.shape[0])
    imd_on_lst = _reproject_array(imd_f, profile, lst.shape, lst_transform, lst_crs, resampling=Resampling.average)
    veg_on_lst = _reproject_array(vegetation.astype("float32"), profile, lst.shape, lst_transform, lst_crs, resampling=Resampling.average)

    urban = lst_valid & np.isfinite(imd_on_lst) & (imd_on_lst >= 50)
    reference = lst_valid & np.isfinite(imd_on_lst) & np.isfinite(veg_on_lst) & (imd_on_lst <= 10) & (veg_on_lst >= 0.50)
    if urban.sum() < 20:
        urban = lst_valid & np.isfinite(imd_on_lst) & (imd_on_lst >= 30)
    if reference.sum() < 20:
        reference = lst_valid & np.isfinite(imd_on_lst) & np.isfinite(veg_on_lst) & (imd_on_lst <= 20) & (veg_on_lst >= 0.25)
    if urban.sum() < 10 or reference.sum() < 10:
        raise RuntimeError("Not enough urban and vegetated reference pixels to calculate the surface heat-island proxy.")
    urban_median = float(np.median(lst[urban]))
    reference_median = float(np.median(lst[reference]))
    suhi_intensity = urban_median - reference_median
    suhi_anomaly = np.where(lst_valid, lst - reference_median, np.nan).astype("float32")

    _write_raster(DERIVED / "vegetation_cover_2023.tif", vegetation, profile, dtype="uint8", nodata=255)
    _write_raster(DERIVED / "tree_cover_change_2018_2023.tif", tree_change, profile, dtype="int16", nodata=-32768)
    _write_raster(DERIVED / "runoff_potential_proxy.tif", runoff_proxy, profile, dtype="float32", nodata=-9999.0)
    lst_profile = {
        "driver": "GTiff",
        "height": lst.shape[0],
        "width": lst.shape[1],
        "count": 1,
        "crs": lst_crs,
        "transform": lst_transform,
    }
    _write_raster(DERIVED / "surface_uhi_anomaly.tif", np.where(np.isfinite(suhi_anomaly), suhi_anomaly, -9999), lst_profile, dtype="float32", nodata=-9999.0)

    imd_rgba = _rgba_continuous(imd_f, [0, 10, 30, 60, 100], [(238, 239, 226), (215, 217, 189), (238, 184, 92), (221, 102, 55), (137, 33, 46)], valid=np.ones(imd.shape, dtype=bool), alpha=220)
    vegetation_rgba = np.zeros((*vegetation.shape, 4), dtype="uint8")
    vegetation_rgba[vegetation == 0] = (236, 233, 222, 95)
    vegetation_rgba[vegetation == 1] = (63, 132, 66, 220)
    tree_rgba = _rgba_continuous(tree_change.astype("float32"), [-40, -10, 0, 10, 40], [(151, 42, 42), (222, 129, 83), (231, 229, 218), (113, 175, 104), (24, 105, 63)], valid=np.ones(tree_change.shape, dtype=bool), alpha=225)
    runoff_rgba = _rgba_continuous(runoff_proxy, [0, 20, 40, 60, 80, 100], [(54, 127, 163), (104, 170, 165), (203, 205, 126), (241, 174, 74), (213, 90, 50), (126, 35, 55)], valid=np.ones(runoff_proxy.shape, dtype=bool), alpha=220)
    uhi_rgba = _rgba_continuous(suhi_anomaly, [-10, -4, 0, 4, 10], [(44, 107, 150), (116, 176, 187), (239, 237, 219), (229, 142, 72), (165, 43, 45)], valid=lst_valid, alpha=220)
    _write_png(MAPS / "copernicus_imperviousness_2021.png", imd_rgba)
    _write_png(MAPS / "copernicus_vegetation_cover_2023.png", vegetation_rgba)
    _write_png(MAPS / "copernicus_tree_change_2018_2023.png", tree_rgba)
    _write_png(MAPS / "runoff_potential_proxy.png", runoff_rgba)
    _write_png(MAPS / "surface_uhi_proxy.png", uhi_rgba)

    metrics = {
        "surface_uhi_proxy_c": round(suhi_intensity, 1),
        "surface_uhi_urban_median_c": round(urban_median, 1),
        "surface_uhi_reference_median_c": round(reference_median, 1),
        "surface_uhi_urban_pixels": int(urban.sum()),
        "surface_uhi_reference_pixels": int(reference.sum()),
        "imperviousness_mean_pct": round(float(np.mean(imd_f)), 1),
        "imperviousness_area_ge_50_pct": round(float(np.mean(imd_f >= 50) * 100), 1),
        "vegetation_cover_area_pct": round(float(np.mean(vegetation == 1) * 100), 1),
        "tree_density_mean_2018_pct": round(float(np.mean(tcd18)), 1),
        "tree_density_mean_2023_pct": round(float(np.mean(tcd23)), 1),
        "tree_density_change_2018_2023_pp": round(float(np.mean(tcd23) - np.mean(tcd18)), 1),
        "tree_loss_cells_ge_10pp_pct": round(float(np.mean(tree_change <= -10) * 100), 1),
        "tree_gain_cells_ge_10pp_pct": round(float(np.mean(tree_change >= 10) * 100), 1),
        "runoff_proxy_mean_0_100": round(float(np.mean(runoff_proxy)), 1),
    }
    project_manifest = json.loads(PROJECT_MANIFEST.read_text())
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "study_area": project_manifest["study_area"],
        "metrics": metrics,
        "methods": {
            "surface_uhi_proxy": "Median Landsat LST of IMD>=50% pixels minus median LST of IMD<=10% and vegetation>=50% pixels; thresholds relax only if sample count is insufficient.",
            "vegetation_cover": "Area fraction where CLMS TCD 2023 is greater than zero or HRL Herbaceous Cover 2023 equals one.",
            "tree_change": "Per-cell TCD 2023 minus TCD 2018; requested 2025 endpoint was not available.",
            "runoff_proxy": "0.75 * HRL imperviousness density + 0.25 * terrain slope normalized at 30 degrees; relative screening index only.",
        },
        "limitations": {
            "surface_uhi_proxy": "Single daytime surface-temperature scene; not air temperature, night UHI, exposure or health outcome.",
            "vegetation_cover": "Presence-based coverage; not leaf area, ecological quality or accessibility.",
            "tree_change": "Product-to-product classification differences may contribute to apparent change.",
            "runoff_proxy": "No design rainfall, soil, sewer network, flow routing or hydrological calibration.",
        },
        "outputs": {
            "imperviousness_png": "maps/copernicus_imperviousness_2021.png",
            "vegetation_png": "maps/copernicus_vegetation_cover_2023.png",
            "tree_change_png": "maps/copernicus_tree_change_2018_2023.png",
            "runoff_png": "maps/runoff_potential_proxy.png",
            "surface_uhi_png": "maps/surface_uhi_proxy.png",
        },
    }
    INDICATORS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    included = layer_manifest.setdefault("layers_included", [])
    for layer in [
        "illa_calor_superficial_proxy",
        "impermeabilitzacio_copernicus_hrl_2021",
        "cobertura_vegetal_copernicus_hrl_2023",
        "canvi_cobertura_arboria_copernicus_2018_2023",
        "escorrentia_potencial_relativa",
    ]:
        if layer not in included:
            included.append(layer)
    layer_manifest["layers_omitted"] = [item for item in layer_manifest.get("layers_omitted", []) if item != "impermeabilitzacio_copernicus"]
    layer_manifest["extended_indicators"] = payload
    LAYER_MANIFEST.write_text(json.dumps(layer_manifest, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    payload = calculate()
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))
    print(INDICATORS)


if __name__ == "__main__":
    main()
