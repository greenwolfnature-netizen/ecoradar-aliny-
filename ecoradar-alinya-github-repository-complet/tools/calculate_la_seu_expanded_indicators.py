"""Calculate all defensible street-scale indicators for the expanded urban scope."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject
from shapely.geometry import box, mapping

from calculate_la_seu_extended_urban_indicators import _rgba_continuous, _write_png
from calculate_la_seu_sentinel2_indicators import _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
MANIFEST = PROJECT / "metadata" / "project_manifest.json"
CLMS = PROJECT / "processed" / "copernicus_hrl_expanded"
LANDSAT = PROJECT / "processed" / "landsat_expanded" / "landsat_lst_expanded.npz"
LIDAR = PROJECT / "processed" / "lidar_expanded_arrays.npz"
LIDAR_METADATA = PROJECT / "metadata" / "lidar_expanded_analysis.json"
MAPS = PROJECT / "maps"
DERIVED = PROJECT / "processed" / "expanded_scope_indicators"
OUTPUT = PROJECT / "indicators" / "expanded_scope_indicators.json"
METADATA = PROJECT / "metadata" / "expanded_scope_layers.json"
LAYER_MANIFEST = PROJECT / "metadata" / "layer_manifest.json"
SOLAR_OUTPUT = PROJECT / "processed" / "solar_roof_screening_expanded.geojson"
SOLAR_SUMMARY = PROJECT / "indicators" / "solar_roof_screening_expanded_summary.json"
FIRE_TIF = PROJECT / "processed" / "fire_danger_structural_2024.tif"

SOLAR_CLASS_DEFINITIONS = {
    "favorable": {
        "priority": 1,
        "label": "Millor aptitud geomètrica",
        "criteria": (
            "Pendent ≤10° amb qualsevol orientació, o pendent ≤45° i "
            "orientació entre 135° i 225° (sud-est–sud-oest)."
        ),
        "decision": (
            "Primera prioritat per estudiar l’aprofitament fotovoltaic."
        ),
    },
    "condicionada": {
        "priority": 2,
        "label": "Aptitud geomètrica condicionada",
        "criteria": (
            "Pendent ≤45° i orientació entre 90° i 270° (est–oest), "
            "sense complir la classe favorable."
        ),
        "decision": (
            "Segona prioritat; requereix comprovar disposició, ombres i rendiment."
        ),
    },
    "baixa": {
        "priority": 3,
        "label": "Aptitud geomètrica baixa",
        "criteria": (
            "Pendent >45° o orientació fora de l’arc est–sud–oest."
        ),
        "decision": (
            "Prioritat baixa en el cribratge; només s’ha d’estudiar amb "
            "condicions tècniques específiques."
        ),
    },
}


def _read(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as source:
        return source.read(1), source.profile.copy()


def _scope_mask(shape, transform, crs, bbox4326) -> np.ndarray:
    transformer = Transformer.from_crs(4326, crs, always_xy=True)
    ring = [
        transformer.transform(bbox4326[0], bbox4326[1]),
        transformer.transform(bbox4326[0], bbox4326[3]),
        transformer.transform(bbox4326[2], bbox4326[3]),
        transformer.transform(bbox4326[2], bbox4326[1]),
        transformer.transform(bbox4326[0], bbox4326[1]),
    ]
    return geometry_mask(
        [{"type": "Polygon", "coordinates": [ring]}],
        out_shape=shape,
        transform=transform,
        invert=True,
        all_touched=False,
    )


def _reproject(values, source_profile, shape, transform, crs, *, resampling, src_nodata=None):
    destination = np.full(shape, np.nan, dtype="float32")
    reproject(
        source=values.astype("float32"),
        destination=destination,
        src_transform=source_profile["transform"],
        src_crs=source_profile["crs"],
        dst_transform=transform,
        dst_crs=crs,
        src_nodata=src_nodata,
        dst_nodata=np.nan,
        resampling=resampling,
    )
    return destination


def _write_tif(path: Path, values: np.ndarray, profile: dict, nodata=-9999.0) -> None:
    output = profile.copy()
    output.update(driver="GTiff", dtype="float32", count=1, nodata=nodata, compress="deflate")
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **output) as target:
        target.write(np.where(np.isfinite(values), values, nodata).astype("float32"), 1)


def _binary_rgba(mask: np.ndarray, valid: np.ndarray, on, off=(236, 233, 222, 80), alpha=220):
    rgba = np.zeros((*mask.shape, 4), dtype="uint8")
    rgba[valid & ~mask] = (*off[:3], off[3] if len(off) == 4 else 80)
    rgba[valid & mask] = (*on, alpha)
    return rgba


def _fire_rgba(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    colors_by_level = {
        1: (44, 123, 182), 2: (99, 169, 196), 3: (154, 203, 156),
        4: (201, 221, 120), 5: (240, 230, 91), 6: (247, 200, 75),
        7: (243, 154, 56), 8: (231, 111, 46), 9: (204, 61, 47), 10: (139, 30, 45),
    }
    rgba = np.zeros((*values.shape, 4), dtype="uint8")
    rounded = np.where(valid, np.rint(values), 0).astype("uint8")
    for level, color in colors_by_level.items():
        selected = valid & (rounded == level)
        rgba[selected] = (*color, 225)
    return rgba


def _stats(values: np.ndarray, valid: np.ndarray, digits=1) -> dict:
    selected = values[valid]
    return {
        "mean": round(float(np.mean(selected)), digits),
        "median": round(float(np.median(selected)), digits),
        "p10": round(float(np.percentile(selected, 10)), digits),
        "p90": round(float(np.percentile(selected, 90)), digits),
        "minimum": round(float(np.min(selected)), digits),
        "maximum": round(float(np.max(selected)), digits),
    }


def _block_mean(values: np.ndarray, valid: np.ndarray, factor: int = 4) -> tuple[np.ndarray, np.ndarray]:
    rows = int(math.ceil(values.shape[0] / factor) * factor)
    cols = int(math.ceil(values.shape[1] / factor) * factor)
    padded = np.full((rows, cols), np.nan, dtype="float32")
    padded[: values.shape[0], : values.shape[1]] = np.where(valid, values, np.nan)
    blocks = padded.reshape(rows // factor, factor, cols // factor, factor)
    counts = np.isfinite(blocks).sum(axis=(1, 3))
    totals = np.nansum(blocks, axis=(1, 3))
    mean = np.divide(totals, counts, out=np.full(totals.shape, np.nan, dtype="float32"), where=counts > 0)
    return mean, counts > 0


def _to_web_grid(
    values: np.ndarray,
    valid: np.ndarray,
    source_profile: dict,
    bbox4326,
    resolution_m: float,
    *,
    resampling: Resampling,
) -> tuple[np.ndarray, np.ndarray]:
    middle_latitude = (float(bbox4326[1]) + float(bbox4326[3])) / 2
    width = max(1, int(math.ceil((float(bbox4326[2]) - float(bbox4326[0])) * 111320 * math.cos(math.radians(middle_latitude)) / resolution_m)))
    height = max(1, int(math.ceil((float(bbox4326[3]) - float(bbox4326[1])) * 111320 / resolution_m)))
    transform = from_bounds(*bbox4326, width, height)
    destination = np.full((height, width), np.nan, dtype="float32")
    reproject(
        source=np.where(valid, values, np.nan).astype("float32"),
        destination=destination,
        src_transform=source_profile["transform"],
        src_crs=source_profile["crs"],
        dst_transform=transform,
        dst_crs="EPSG:4326",
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=resampling,
    )
    destination_valid = np.zeros((height, width), dtype="uint8")
    reproject(
        source=valid.astype("uint8"),
        destination=destination_valid,
        src_transform=source_profile["transform"],
        src_crs=source_profile["crs"],
        dst_transform=transform,
        dst_crs="EPSG:4326",
        src_nodata=0,
        dst_nodata=0,
        resampling=Resampling.nearest,
    )
    return destination, destination_valid.astype(bool) & np.isfinite(destination)


def _solar_screening(lidar, lidar_bounds, bbox4326) -> dict:
    buildings = gpd.read_file(PROJECT / "processed" / "buildings_cadastre.geojson", engine="pyogrio")
    buildings = buildings[buildings.geometry.intersects(box(*bbox4326))].copy().to_crs(25831)
    dsm = lidar["dsm"]
    valid_grid = lidar["valid"].astype(bool)
    surface_slope = lidar["surface_slope"].astype("float32")
    surface_aspect = lidar["surface_aspect"].astype("float32")
    nrows, ncols = dsm.shape
    xmin, ymin, xmax, ymax = lidar_bounds
    resolution = (xmax - xmin) / ncols
    transform = from_bounds(*lidar_bounds, ncols, nrows)
    records = []
    for row in buildings.itertuples():
        geom = row.geometry
        minx, miny, maxx, maxy = geom.bounds
        c0 = max(0, int(math.floor((minx - xmin) / resolution)))
        c1 = min(ncols, int(math.ceil((maxx - xmin) / resolution)) + 1)
        r0 = max(0, int(math.floor((ymax - maxy) / resolution)))
        r1 = min(nrows, int(math.ceil((ymax - miny) / resolution)) + 1)
        if r1 <= r0 or c1 <= c0:
            continue
        window_transform = rasterio.windows.transform(
            rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0), transform
        )
        inside = geometry_mask(
            [mapping(geom)],
            out_shape=(r1 - r0, c1 - c0),
            transform=window_transform,
            invert=True,
        )
        valid = valid_grid[r0:r1, c0:c1] & inside
        if int(valid.sum()) < 3:
            continue
        slope_values = surface_slope[r0:r1, c0:c1][valid]
        aspect_values = surface_aspect[r0:r1, c0:c1][valid]
        slope = float(np.nanmedian(slope_values))
        weights = np.maximum(slope_values, 1.0)
        radians = np.radians(aspect_values)
        aspect = (
            math.degrees(math.atan2(
                float(np.average(np.sin(radians), weights=weights)),
                float(np.average(np.cos(radians), weights=weights)),
            )) + 360.0
        ) % 360.0
        if slope <= 10.0 or (slope <= 45.0 and 135.0 <= aspect <= 225.0):
            solar_class = "favorable"
        elif slope <= 45.0 and 90.0 <= aspect <= 270.0:
            solar_class = "condicionada"
        else:
            solar_class = "baixa"
        records.append({
            "cadastre_id": getattr(row, "cadastre_id", None),
            "footprint_m2": round(float(geom.area), 1),
            "lidar_cells": int(valid.sum()),
            "median_slope_deg": round(slope, 1),
            "mean_aspect_deg": round(aspect, 1),
            "solar_screen": solar_class,
            "geometry": geom,
        })
    roofs = gpd.GeoDataFrame(records, geometry="geometry", crs=25831).to_crs(4326)
    roofs.to_file(SOLAR_OUTPUT, driver="GeoJSON", engine="pyogrio")
    summary = {
        "evaluated_buildings": int(len(roofs)),
        "classes": {str(k): int(v) for k, v in roofs["solar_screen"].value_counts().to_dict().items()},
        "priority_order": ["favorable", "condicionada", "baixa"],
        "class_definitions": SOLAR_CLASS_DEFINITIONS,
        "method_note": "Expanded geometric screening using cadastral footprints and 2 m LiDAR surface slope/aspect; not a photovoltaic feasibility study.",
        "scope": "La Seu d'Urgell, Castellciutat and Sant Antoni",
    }
    SOLAR_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def _feature_counts(bbox4326) -> dict:
    scope = box(*bbox4326)
    sources = {
        "cadastre_buildings": "buildings_cadastre.geojson",
        "green_features_osm": "green_spaces_osm.geojson",
        "mobility_segments_osm": "mobility_osm.geojson",
        "facility_points_osm": "facilities_osm.geojson",
        "water_features_osm": "water_osm.geojson",
    }
    return {
        name: int(
            gpd.read_file(PROJECT / "processed" / filename, engine="pyogrio")
            .geometry.intersects(scope).sum()
        )
        for name, filename in sources.items()
    }


def calculate() -> dict:
    MAPS.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    project = json.loads(MANIFEST.read_text())
    bbox = tuple(float(v) for v in project["study_area"]["expanded_urban_bbox_epsg4326"])

    imd, clms_profile = _read(CLMS / "imperviousness_2021.tif")
    tcd18, _ = _read(CLMS / "tree_cover_density_2018.tif")
    tcd23, _ = _read(CLMS / "tree_cover_density_2023.tif")
    herb23, _ = _read(CLMS / "herbaceous_cover_2023.tif")
    clms_scope = _scope_mask(imd.shape, clms_profile["transform"], clms_profile["crs"], bbox)
    clms_valid = clms_scope & (imd <= 100) & (tcd18 <= 100) & (tcd23 <= 100) & (herb23 <= 1)
    imd_f = np.where(clms_valid, imd.astype("float32"), np.nan)
    vegetation = ((tcd23 > 0) | (herb23 == 1)) & clms_valid
    tree_change = np.where(clms_valid, tcd23.astype("float32") - tcd18.astype("float32"), np.nan)

    lidar = np.load(LIDAR)
    lidar_metadata = json.loads(LIDAR_METADATA.read_text())
    lidar_bounds = [float(v) for v in lidar["bounds"]]
    lidar_slope = lidar["terrain_slope"].astype("float32")
    lidar_dtm = lidar["dtm"].astype("float32")
    lidar_valid = lidar["valid"].astype(bool)
    lidar_scope = lidar["scope_mask"].astype(bool)
    lidar_profile = {
        "transform": from_bounds(*lidar_bounds, lidar_slope.shape[1], lidar_slope.shape[0]),
        "crs": "EPSG:25831",
    }
    solar = _solar_screening(lidar, lidar_bounds, bbox)
    slope_on_clms = _reproject(
        np.where(lidar_valid, lidar_slope, np.nan),
        lidar_profile,
        imd.shape,
        clms_profile["transform"],
        clms_profile["crs"],
        resampling=Resampling.bilinear,
    )
    runoff = np.where(
        clms_valid,
        0.75 * imd_f + 0.25 * (np.clip(np.nan_to_num(slope_on_clms, nan=0.0), 0, 30) / 30 * 100),
        np.nan,
    )

    landsat = np.load(LANDSAT)
    lst = landsat["lst_c"].astype("float32")
    lst_valid = landsat["valid"].astype(bool)
    lst_bounds = [float(v) for v in landsat["bounds"]]
    lst_crs = str(landsat["crs"].item())
    lst_transform = from_bounds(*lst_bounds, lst.shape[1], lst.shape[0])
    lst_scope = _scope_mask(lst.shape, lst_transform, lst_crs, bbox)
    lst_valid &= lst_scope & np.isfinite(lst)
    imd_on_lst = _reproject(imd_f, clms_profile, lst.shape, lst_transform, lst_crs, resampling=Resampling.average)
    veg_on_lst = _reproject(vegetation.astype("float32"), clms_profile, lst.shape, lst_transform, lst_crs, resampling=Resampling.average)
    urban = lst_valid & np.isfinite(imd_on_lst) & (imd_on_lst >= 50)
    reference = lst_valid & np.isfinite(imd_on_lst) & np.isfinite(veg_on_lst) & (imd_on_lst <= 10) & (veg_on_lst >= 0.50)
    if urban.sum() < 20:
        urban = lst_valid & np.isfinite(imd_on_lst) & (imd_on_lst >= 30)
    if reference.sum() < 20:
        reference = lst_valid & np.isfinite(imd_on_lst) & np.isfinite(veg_on_lst) & (imd_on_lst <= 20) & (veg_on_lst >= 0.25)
    if urban.sum() < 10 or reference.sum() < 10:
        raise RuntimeError("Insufficient valid urban/reference pixels for expanded SUHI screening.")
    urban_median = float(np.median(lst[urban]))
    reference_median = float(np.median(lst[reference]))
    suhi = np.where(lst_valid, lst - reference_median, np.nan)

    _write_tif(DERIVED / "runoff_potential_proxy.tif", runoff, clms_profile)
    _write_tif(DERIVED / "surface_uhi_anomaly.tif", suhi, {
        "height": lst.shape[0], "width": lst.shape[1], "transform": lst_transform, "crs": lst_crs,
    })
    _write_tif(DERIVED / "tree_cover_change_2018_2023.tif", tree_change, clms_profile)

    _write_png(MAPS / "expanded_copernicus_imperviousness_2021.png", _rgba_continuous(
        imd_f, [0, 10, 30, 60, 100], [(238, 239, 226), (215, 217, 189), (238, 184, 92), (221, 102, 55), (137, 33, 46)], valid=clms_valid, alpha=220))
    _write_png(MAPS / "expanded_copernicus_vegetation_cover_2023.png", _binary_rgba(vegetation, clms_valid, (63, 132, 66)))
    _write_png(MAPS / "expanded_copernicus_tree_change_2018_2023.png", _rgba_continuous(
        tree_change, [-40, -10, 0, 10, 40], [(151, 42, 42), (222, 129, 83), (231, 229, 218), (113, 175, 104), (24, 105, 63)], valid=clms_valid, alpha=225))
    _write_png(MAPS / "expanded_runoff_potential_proxy.png", _rgba_continuous(
        runoff, [0, 20, 40, 60, 80, 100], [(54, 127, 163), (104, 170, 165), (203, 205, 126), (241, 174, 74), (213, 90, 50), (126, 35, 55)], valid=clms_valid, alpha=220))
    _write_png(MAPS / "expanded_surface_uhi_proxy.png", _rgba_continuous(
        suhi, [-10, -4, 0, 4, 10], [(44, 107, 150), (116, 176, 187), (239, 237, 219), (229, 142, 72), (165, 43, 45)], valid=lst_valid, alpha=220))
    _write_png(MAPS / "expanded_landsat_lst.png", _rgba_continuous(
        lst, [34, 39, 44, 49, 54, 59], [(42, 127, 96), (166, 199, 84), (250, 204, 70), (244, 141, 40), (214, 65, 39), (126, 24, 54)], valid=lst_valid, alpha=220))

    shade = lidar["shade"].astype(bool)
    canopy = lidar["canopy"].astype(bool)
    shade_rgba = _binary_rgba(shade, lidar_scope & lidar_valid, (32, 102, 67), off=(248, 248, 243, 28), alpha=205)
    canopy_rgba = _binary_rgba(canopy, lidar_scope & lidar_valid, (64, 123, 61), off=(248, 248, 243, 28), alpha=215)
    _write_png(MAPS / "expanded_lidar_shade.png", shade_rgba)
    _write_webp(MAPS / "expanded_lidar_shade.webp", shade_rgba)
    _write_png(MAPS / "expanded_lidar_canopy.png", canopy_rgba)
    _write_webp(MAPS / "expanded_lidar_canopy.webp", canopy_rgba)
    slope_rgba = _rgba_continuous(
        lidar_slope, [0, 3, 8, 15, 25, 40], [(234, 239, 225), (190, 210, 162), (221, 197, 118), (209, 143, 77), (158, 82, 59), (92, 48, 55)], valid=lidar_scope & lidar_valid, alpha=220)
    _write_png(MAPS / "expanded_lidar_slope.png", slope_rgba)
    _write_webp(MAPS / "expanded_lidar_slope.webp", slope_rgba)
    web_valid_source = lidar_scope & lidar_valid
    shade_web, shade_web_valid = _to_web_grid(
        shade.astype("float32"), web_valid_source, lidar_profile, bbox, 8, resampling=Resampling.average)
    canopy_web, canopy_web_valid = _to_web_grid(
        canopy.astype("float32"), web_valid_source, lidar_profile, bbox, 8, resampling=Resampling.average)
    slope_web, slope_web_valid = _to_web_grid(
        lidar_slope, web_valid_source, lidar_profile, bbox, 8, resampling=Resampling.average)
    terrain_source_valid = lidar_scope & np.isfinite(lidar_dtm)
    terrain_dy, terrain_dx = np.gradient(lidar_dtm, 2.0, 2.0)
    terrain_slope = np.arctan(np.hypot(terrain_dx, terrain_dy))
    terrain_aspect = np.arctan2(-terrain_dx, terrain_dy)
    sun_azimuth = np.radians(315.0)
    sun_elevation = np.radians(45.0)
    terrain_hillshade = (
        np.sin(sun_elevation) * np.cos(terrain_slope)
        + np.cos(sun_elevation) * np.sin(terrain_slope)
        * np.cos(sun_azimuth - terrain_aspect)
    )
    terrain_hillshade = np.clip((terrain_hillshade + 1.0) / 2.0, 0.0, 1.0)
    terrain_web, terrain_web_valid = _to_web_grid(
        terrain_hillshade.astype("float32"),
        terrain_source_valid,
        lidar_profile,
        bbox,
        8,
        resampling=Resampling.average,
    )
    _write_png(MAPS / "expanded_lidar_terrain_web.png", _rgba_continuous(
        terrain_web,
        [0, 0.35, 0.5, 0.65, 1],
        [(105, 112, 99), (174, 181, 164), (218, 221, 207), (239, 237, 224), (255, 253, 244)],
        valid=terrain_web_valid,
        alpha=92,
    ))
    _write_png(MAPS / "expanded_lidar_shade_web.png", _rgba_continuous(
        shade_web, [0, 0.1, 0.5, 1], [(245, 247, 240), (176, 211, 204), (82, 153, 125), (25, 87, 61)], valid=shade_web_valid, alpha=220))
    _write_png(MAPS / "expanded_lidar_canopy_web.png", _rgba_continuous(
        canopy_web, [0, 0.1, 0.5, 1], [(245, 247, 240), (196, 221, 173), (104, 165, 91), (34, 105, 56)], valid=canopy_web_valid, alpha=220))
    _write_png(MAPS / "expanded_lidar_slope_web.png", _rgba_continuous(
        slope_web, [0, 3, 8, 15, 25, 40], [(234, 239, 225), (190, 210, 162), (221, 197, 118), (209, 143, 77), (158, 82, 59), (92, 48, 55)], valid=slope_web_valid, alpha=220))

    imd_web, imd_web_valid = _to_web_grid(imd_f, clms_valid, clms_profile, bbox, 10, resampling=Resampling.average)
    vegetation_web, vegetation_web_valid = _to_web_grid(
        vegetation.astype("float32"), clms_valid, clms_profile, bbox, 10, resampling=Resampling.average)
    tree_web, tree_web_valid = _to_web_grid(tree_change, clms_valid, clms_profile, bbox, 10, resampling=Resampling.average)
    runoff_web, runoff_web_valid = _to_web_grid(runoff, clms_valid, clms_profile, bbox, 10, resampling=Resampling.average)
    lst_profile = {"transform": lst_transform, "crs": lst_crs}
    lst_web, lst_web_valid = _to_web_grid(lst, lst_valid, lst_profile, bbox, 30, resampling=Resampling.bilinear)
    suhi_web, suhi_web_valid = _to_web_grid(suhi, lst_valid, lst_profile, bbox, 30, resampling=Resampling.bilinear)
    _write_png(MAPS / "expanded_copernicus_imperviousness_2021_web.png", _rgba_continuous(
        imd_web, [0, 10, 30, 60, 100], [(238, 239, 226), (215, 217, 189), (238, 184, 92), (221, 102, 55), (137, 33, 46)], valid=imd_web_valid, alpha=220))
    _write_png(MAPS / "expanded_copernicus_vegetation_cover_2023_web.png", _rgba_continuous(
        vegetation_web, [0, 0.1, 0.5, 1], [(236, 233, 222), (196, 220, 176), (99, 162, 90), (40, 111, 55)], valid=vegetation_web_valid, alpha=220))
    _write_png(MAPS / "expanded_copernicus_tree_change_2018_2023_web.png", _rgba_continuous(
        tree_web, [-40, -10, 0, 10, 40], [(151, 42, 42), (222, 129, 83), (231, 229, 218), (113, 175, 104), (24, 105, 63)], valid=tree_web_valid, alpha=225))
    _write_png(MAPS / "expanded_runoff_potential_proxy_web.png", _rgba_continuous(
        runoff_web, [0, 20, 40, 60, 80, 100], [(54, 127, 163), (104, 170, 165), (203, 205, 126), (241, 174, 74), (213, 90, 50), (126, 35, 55)], valid=runoff_web_valid, alpha=220))
    _write_png(MAPS / "expanded_landsat_lst_web.png", _rgba_continuous(
        lst_web, [34, 39, 44, 49, 54, 59], [(42, 127, 96), (166, 199, 84), (250, 204, 70), (244, 141, 40), (214, 65, 39), (126, 24, 54)], valid=lst_web_valid, alpha=220))
    _write_png(MAPS / "expanded_surface_uhi_proxy_web.png", _rgba_continuous(
        suhi_web, [-10, -4, 0, 4, 10], [(44, 107, 150), (116, 176, 187), (239, 237, 219), (229, 142, 72), (165, 43, 45)], valid=suhi_web_valid, alpha=220))
    with rasterio.open(FIRE_TIF) as fire_source:
        fire_values = fire_source.read(1)
        fire_profile = fire_source.profile.copy()
        fire_valid = np.isin(fire_values, np.arange(1, 11))
    fire_web, fire_web_valid = _to_web_grid(
        fire_values.astype("float32"), fire_valid, fire_profile, bbox, 100, resampling=Resampling.nearest)
    _write_png(MAPS / "expanded_fire_danger_structural_2024_web.png", _fire_rgba(fire_web, fire_web_valid))

    metrics = {
        "shade_pct": lidar_metadata["shade_pct"],
        "canopy_cover_pct": lidar_metadata["canopy_cover_pct"],
        "terrain_slope_median_deg": lidar_metadata["terrain_slope_median_deg"],
        "land_surface_temperature_c": _stats(lst, lst_valid),
        "surface_uhi_proxy_c": round(urban_median - reference_median, 1),
        "surface_uhi_urban_median_c": round(urban_median, 1),
        "surface_uhi_reference_median_c": round(reference_median, 1),
        "surface_uhi_urban_pixels": int(urban.sum()),
        "surface_uhi_reference_pixels": int(reference.sum()),
        "imperviousness_mean_pct": round(float(np.nanmean(imd_f)), 1),
        "imperviousness_area_ge_50_pct": round(float(np.mean(imd_f[clms_valid] >= 50) * 100), 1),
        "vegetation_cover_area_pct": round(float(np.mean(vegetation[clms_valid]) * 100), 1),
        "tree_density_mean_2018_pct": round(float(np.mean(tcd18[clms_valid])), 1),
        "tree_density_mean_2023_pct": round(float(np.mean(tcd23[clms_valid])), 1),
        "tree_density_change_2018_2023_pp": round(float(np.mean(tree_change[clms_valid])), 1),
        "tree_loss_cells_ge_10pp_pct": round(float(np.mean(tree_change[clms_valid] <= -10) * 100), 1),
        "tree_gain_cells_ge_10pp_pct": round(float(np.mean(tree_change[clms_valid] >= 10) * 100), 1),
        "runoff_proxy_mean_0_100": round(float(np.nanmean(runoff)), 1),
        "solar_roof_screening": solar,
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "product_scope": "La Seu d'Urgell, Castellciutat and Sant Antoni",
        "study_bbox_epsg4326": bbox,
        "study_area_ha": project["study_area"]["expanded_urban_area_ha"],
        "scope_type": project["study_area"]["expanded_urban_scope_note"],
        "metrics": metrics,
        "feature_counts": _feature_counts(bbox),
        "methods": {
            "shade": "ICGC classified LiDAR, 2 m DSM/DTM, direct-sun obstruction for 2026-06-21 15:00 CEST.",
            "canopy": "Presence of ICGC LiDAR vegetation classes 4 and 5 in valid 2 m cells.",
            "surface_uhi_proxy": "Median Landsat LST at CLMS IMD>=50% minus vegetated reference at IMD<=10% and vegetation>=50%; relaxed thresholds only if samples are insufficient.",
            "vegetation_cover": "TCD 2023 > 0 or HRL Herbaceous Cover 2023 = 1.",
            "tree_change": "TCD 2023 minus TCD 2018 per 10 m cell; 2025 endpoint unavailable.",
            "runoff_proxy": "0.75 * CLMS imperviousness + 0.25 * LiDAR slope normalized at 30 degrees.",
        },
        "limitations": {
            "scope": "Operational rectangular study area, not an administrative boundary.",
            "lst": "Single daytime surface-temperature scene; not air temperature, personal exposure or night heat.",
            "shade": "One modelled summer instant; not seasonal shade or physiological thermal comfort.",
            "tree_change": "Classification differences between products can contribute to apparent change.",
            "runoff": "Relative screening without design rainfall, soils, sewers, flow routing or calibration.",
        },
        "source_metadata": {
            "lidar": "metadata/lidar_expanded_analysis.json",
            "landsat": "metadata/landsat_expanded_connector.json",
            "clms": "metadata/copernicus_hrl_expanded_connector.json",
            "fire": "metadata/fire_danger_structural_2024.json",
        },
        "maps": {
            "terrain_background_web_8m": "maps/expanded_lidar_terrain_web.png",
            "shade": "maps/expanded_lidar_shade.png",
            "shade_web": "maps/expanded_lidar_shade.webp",
            "shade_web_8m": "maps/expanded_lidar_shade_web.png",
            "canopy": "maps/expanded_lidar_canopy.png",
            "canopy_web": "maps/expanded_lidar_canopy.webp",
            "canopy_web_8m": "maps/expanded_lidar_canopy_web.png",
            "slope": "maps/expanded_lidar_slope.png",
            "slope_web": "maps/expanded_lidar_slope.webp",
            "slope_web_8m": "maps/expanded_lidar_slope_web.png",
            "lst": "maps/expanded_landsat_lst.png",
            "lst_web": "maps/expanded_landsat_lst_web.png",
            "surface_uhi": "maps/expanded_surface_uhi_proxy.png",
            "surface_uhi_web": "maps/expanded_surface_uhi_proxy_web.png",
            "imperviousness": "maps/expanded_copernicus_imperviousness_2021.png",
            "imperviousness_web": "maps/expanded_copernicus_imperviousness_2021_web.png",
            "vegetation": "maps/expanded_copernicus_vegetation_cover_2023.png",
            "vegetation_web": "maps/expanded_copernicus_vegetation_cover_2023_web.png",
            "tree_change": "maps/expanded_copernicus_tree_change_2018_2023.png",
            "tree_change_web": "maps/expanded_copernicus_tree_change_2018_2023_web.png",
            "runoff": "maps/expanded_runoff_potential_proxy.png",
            "runoff_web": "maps/expanded_runoff_potential_proxy_web.png",
            "fire_web": "maps/expanded_fire_danger_structural_2024_web.png",
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    layer_manifest = json.loads(LAYER_MANIFEST.read_text())
    layer_manifest["expanded_scope"] = payload
    LAYER_MANIFEST.write_text(json.dumps(layer_manifest, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    payload = calculate()
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
