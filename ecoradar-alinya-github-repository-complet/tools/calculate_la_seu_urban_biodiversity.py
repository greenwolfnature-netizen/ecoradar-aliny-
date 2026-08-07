"""Calculate a transparent urban-biodiversity potential for the expanded scope.

The output is a relative screening layer derived only from source layers already
verified in the La Seu urban project. It is not an observation layer and does
not infer species presence, abundance or refuges.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, rasterize
from shapely.geometry import box

from calculate_la_seu_expanded_indicators import _to_web_grid


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
CLMS = PROJECT / "processed" / "copernicus_hrl_expanded"
WATER = PROJECT / "processed" / "water_osm.geojson"
DERIVED = PROJECT / "processed" / "urban_biodiversity"
MAPS = PROJECT / "maps"
INDICATOR = PROJECT / "indicators" / "biodiversity_urban_potential.json"
METADATA = PROJECT / "metadata" / "biodiversity_urban_potential.json"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"


def _read(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as source:
        return source.read(1), source.profile.copy()


def _scope_mask(profile: dict, shape: tuple[int, int], bbox4326: list[float]) -> np.ndarray:
    transformer = Transformer.from_crs(4326, profile["crs"], always_xy=True)
    ring = [[
        list(transformer.transform(bbox4326[0], bbox4326[1])),
        list(transformer.transform(bbox4326[0], bbox4326[3])),
        list(transformer.transform(bbox4326[2], bbox4326[3])),
        list(transformer.transform(bbox4326[2], bbox4326[1])),
        list(transformer.transform(bbox4326[0], bbox4326[1])),
    ]]
    return geometry_mask(
        [{"type": "Polygon", "coordinates": ring}],
        out_shape=shape,
        transform=profile["transform"],
        invert=True,
        all_touched=False,
    )


def _local_fraction(mask: np.ndarray, valid: np.ndarray, radius: int) -> np.ndarray:
    """Return the valid-cell fraction in a square moving window."""

    def window_sum(values: np.ndarray) -> np.ndarray:
        padded = np.pad(values.astype("float32"), ((1, 0), (1, 0)))
        integral = padded.cumsum(axis=0).cumsum(axis=1)
        rows = np.arange(mask.shape[0])
        cols = np.arange(mask.shape[1])
        top = np.maximum(rows - radius, 0)
        bottom = np.minimum(rows + radius + 1, mask.shape[0])
        left = np.maximum(cols - radius, 0)
        right = np.minimum(cols + radius + 1, mask.shape[1])
        return (
            integral[bottom[:, None], right[None, :]]
            - integral[top[:, None], right[None, :]]
            - integral[bottom[:, None], left[None, :]]
            + integral[top[:, None], left[None, :]]
        )

    numerator = window_sum(mask & valid)
    denominator = window_sum(valid)
    return np.divide(
        numerator,
        denominator,
        out=np.zeros(mask.shape, dtype="float32"),
        where=denominator > 0,
    )


def _water_distance_m(profile: dict, shape: tuple[int, int], bbox4326: list[float]) -> np.ndarray:
    water = gpd.read_file(WATER, engine="pyogrio")
    water = water[water.geometry.intersects(box(*bbox4326))].copy().to_crs(profile["crs"])
    water = water[~water.geometry.is_empty & water.geometry.notna()]
    if water.empty:
        return np.full(shape, np.inf, dtype="float32")
    water_mask = rasterize(
        [(geometry, 1) for geometry in water.geometry],
        out_shape=shape,
        transform=profile["transform"],
        fill=0,
        all_touched=True,
        dtype="uint8",
    ).astype(bool)
    water_rows, water_cols = np.nonzero(water_mask)
    if not len(water_rows):
        return np.full(shape, np.inf, dtype="float32")

    transform = profile["transform"]
    xs = transform.c + (np.arange(shape[1]) + 0.5) * transform.a
    ys = transform.f + (np.arange(shape[0]) + 0.5) * transform.e
    grid_y, grid_x = np.meshgrid(ys, xs, indexing="ij")
    targets = np.column_stack((grid_x.ravel(), grid_y.ravel())).astype("float32")
    sources = np.column_stack((xs[water_cols], ys[water_rows])).astype("float32")
    minimum_squared = np.full(len(targets), np.inf, dtype="float64")
    for target_start in range(0, len(targets), 2048):
        target_chunk = targets[target_start : target_start + 2048]
        chunk_minimum = np.full(len(target_chunk), np.inf, dtype="float64")
        for source_start in range(0, len(sources), 512):
            delta = target_chunk[:, None, :] - sources[None, source_start : source_start + 512, :]
            chunk_minimum = np.minimum(chunk_minimum, np.min(np.sum(delta * delta, axis=2), axis=1))
        minimum_squared[target_start : target_start + len(target_chunk)] = chunk_minimum
    return np.sqrt(minimum_squared).reshape(shape).astype("float32")


def _rgba(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    stops = [0.0, 25.0, 50.0, 75.0, 100.0]
    colors = np.asarray(
        [(232, 223, 198), (194, 202, 151), (140, 174, 101), (70, 130, 73), (28, 98, 65)],
        dtype="float64",
    )
    rgba = np.zeros((*values.shape, 4), dtype="uint8")
    clipped = np.clip(values, stops[0], stops[-1])
    for index in range(len(stops) - 1):
        low, high = stops[index], stops[index + 1]
        selected = valid & (clipped >= low) & (clipped <= high if index == len(stops) - 2 else clipped < high)
        if not selected.any():
            continue
        ratio = (clipped[selected] - low) / (high - low)
        rgba[selected, :3] = np.round(colors[index] + ratio[:, None] * (colors[index + 1] - colors[index])).astype("uint8")
        rgba[selected, 3] = 220
    return rgba


def _write_tif(path: Path, values: np.ndarray, profile: dict) -> None:
    output = profile.copy()
    output.update(driver="GTiff", count=1, dtype="float32", nodata=-9999.0, compress="deflate")
    with rasterio.open(path, "w", **output) as target:
        target.write(np.where(np.isfinite(values), values, -9999.0).astype("float32"), 1)


def _reduce_average(values: np.ndarray, valid: np.ndarray, factor: int = 3) -> tuple[np.ndarray, np.ndarray]:
    rows = int(np.ceil(values.shape[0] / factor) * factor)
    cols = int(np.ceil(values.shape[1] / factor) * factor)
    padded_values = np.zeros((rows, cols), dtype="float32")
    padded_valid = np.zeros((rows, cols), dtype=bool)
    padded_values[: values.shape[0], : values.shape[1]] = np.nan_to_num(values, nan=0.0)
    padded_valid[: valid.shape[0], : valid.shape[1]] = valid
    value_blocks = padded_values.reshape(rows // factor, factor, cols // factor, factor)
    valid_blocks = padded_valid.reshape(rows // factor, factor, cols // factor, factor)
    counts = valid_blocks.sum(axis=(1, 3))
    sums = (value_blocks * valid_blocks).sum(axis=(1, 3))
    reduced = np.divide(sums, counts, out=np.full(sums.shape, np.nan, dtype="float32"), where=counts > 0)
    return reduced, counts > 0


def _reduce_mask(mask: np.ndarray, factor: int = 3) -> np.ndarray:
    rows = int(np.ceil(mask.shape[0] / factor) * factor)
    cols = int(np.ceil(mask.shape[1] / factor) * factor)
    padded = np.zeros((rows, cols), dtype=bool)
    padded[: mask.shape[0], : mask.shape[1]] = mask
    return padded.reshape(rows // factor, factor, cols // factor, factor).any(axis=(1, 3))


def _pattern_overlay(mask: np.ndarray, color: tuple[int, int, int], pattern: str) -> np.ndarray:
    row, col = np.indices(mask.shape)
    patterns = {
        "forward": (row + col) % 8 == 0,
        "backward": (row - col) % 8 == 0,
        "dots": (row % 5 == 2) & (col % 5 == 2),
        "vertical": col % 7 == 0,
        "cross": (((row % 8) == 4) & ((col % 8) >= 3) & ((col % 8) <= 5))
        | (((col % 8) == 4) & ((row % 8) >= 3) & ((row % 8) <= 5)),
    }
    selected = mask & patterns[pattern]
    rgba = np.zeros((*mask.shape, 4), dtype="uint8")
    rgba[selected] = (*color, 225)
    return rgba


def _write_webp(path: Path, rgba: np.ndarray) -> None:
    with rasterio.open(
        path,
        "w",
        driver="WEBP",
        width=rgba.shape[1],
        height=rgba.shape[0],
        count=4,
        dtype="uint8",
        QUALITY=60,
    ) as target:
        for band in range(4):
            target.write(rgba[..., band], band + 1)


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


def calculate() -> dict:
    DERIVED.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    project = json.loads(PROJECT_MANIFEST.read_text())
    bbox = project["study_area"]["expanded_urban_bbox_epsg4326"]

    imperviousness, profile = _read(CLMS / "imperviousness_2021.tif")
    tree_cover, _ = _read(CLMS / "tree_cover_density_2023.tif")
    herbaceous, _ = _read(CLMS / "herbaceous_cover_2023.tif")
    valid = _scope_mask(profile, imperviousness.shape, bbox)
    valid &= (imperviousness <= 100) & (tree_cover <= 100) & (herbaceous <= 1)
    vegetation = valid & ((tree_cover > 0) | (herbaceous == 1))
    connectivity = _local_fraction(vegetation, valid, radius=10)
    distance_to_water = _water_distance_m(profile, imperviousness.shape, bbox)

    vegetation_component = vegetation.astype("float32")
    tree_component = np.clip(tree_cover.astype("float32") / 100.0, 0, 1)
    connectivity_component = np.clip(connectivity, 0, 1)
    water_component = np.clip(1.0 - distance_to_water / 300.0, 0, 1)
    permeability_component = 1.0 - np.clip(imperviousness.astype("float32") / 100.0, 0, 1)
    potential = 100.0 * (
        vegetation_component
        + tree_component
        + connectivity_component
        + water_component
        + permeability_component
    ) / 5.0
    potential = np.where(valid, potential, np.nan).astype("float32")

    green_connectivity_values = connectivity[vegetation]
    connected_threshold = float(np.percentile(green_connectivity_values, 75))
    isolated_threshold = float(np.percentile(green_connectivity_values, 25))
    potential_threshold = float(np.percentile(potential[valid], 75))
    green_corridor = vegetation & (connectivity >= connected_threshold)
    fluvial_corridor = vegetation & (distance_to_water <= 100.0)
    isolated_green = vegetation & (connectivity <= isolated_threshold)
    structural_barrier = valid & (imperviousness >= 50)
    field_priority = valid & (potential >= potential_threshold)

    # All web rasters must use the exact EPSG:4326 study rectangle expected by
    # the interactive SVG. Reducing the native EPSG:3035 grid directly and then
    # stretching it over a longitude/latitude box displaced the biodiversity
    # layer and left stepped transparent margins.
    potential_web, valid_web = _to_web_grid(
        potential,
        valid,
        profile,
        bbox,
        10,
        resampling=Resampling.bilinear,
    )
    overlay_masks = {}
    for key, mask in {
        "green_corridor": green_corridor,
        "fluvial_corridor": fluvial_corridor,
        "isolated_green": isolated_green,
        "structural_barrier": structural_barrier,
        "field_priority": field_priority,
    }.items():
        web_values, web_valid = _to_web_grid(
            mask.astype("float32"),
            valid,
            profile,
            bbox,
            10,
            resampling=Resampling.nearest,
        )
        overlay_masks[key] = web_valid & (web_values >= 0.5)
    overlays = {
        "biodiversity_green_corridor.png": _pattern_overlay(overlay_masks["green_corridor"], (28, 98, 65), "forward"),
        "biodiversity_fluvial_corridor.png": _pattern_overlay(overlay_masks["fluvial_corridor"], (48, 128, 161), "backward"),
        "biodiversity_isolated_green.png": _pattern_overlay(overlay_masks["isolated_green"], (207, 143, 55), "dots"),
        "biodiversity_structural_barrier.png": _pattern_overlay(overlay_masks["structural_barrier"], (76, 78, 78), "vertical"),
        "biodiversity_field_priority.png": _pattern_overlay(overlay_masks["field_priority"], (105, 64, 154), "cross"),
    }

    _write_tif(DERIVED / "biodiversity_urban_potential.tif", potential, profile)
    _write_webp(MAPS / "biodiversity_urban_potential.webp", _rgba(potential_web, valid_web))
    for filename, overlay in overlays.items():
        _write_png(MAPS / filename, overlay)

    pixel_area_ha = abs(profile["transform"].a * profile["transform"].e) / 10000.0
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "indicator": "Biodiversitat urbana — potencial ecològic relatiu",
        "status": "verified",
        "data_type": "derived_potential",
        "scope": "La Seu d'Urgell, Castellciutat i Sant Antoni",
        "study_bbox_epsg4326": bbox,
        "crs": str(profile["crs"]),
        "analysis_resolution_m": 10,
        "web_raster_shape": [int(potential_web.shape[0]), int(potential_web.shape[1])],
        "metrics": {
            "valid_area_ha": round(float(valid.sum()) * pixel_area_ha, 1),
            "potential_mean_0_100": round(float(np.nanmean(potential)), 1),
            "potential_median_0_100": round(float(np.nanmedian(potential)), 1),
            "high_potential_threshold_p75": round(potential_threshold, 1),
            "high_potential_area_ha": round(float(field_priority.sum()) * pixel_area_ha, 1),
            "potential_green_corridor_area_ha": round(float(green_corridor.sum()) * pixel_area_ha, 1),
            "potential_fluvial_corridor_area_ha": round(float(fluvial_corridor.sum()) * pixel_area_ha, 1),
            "potential_isolated_green_area_ha": round(float(isolated_green.sum()) * pixel_area_ha, 1),
            "structural_urban_barrier_area_ha": round(float(structural_barrier.sum()) * pixel_area_ha, 1),
        },
        "method": {
            "formula": "100 * mean(vegetation presence, tree-cover density, green-window fraction, water proximity, soil permeability)",
            "weights": {
                "vegetation_presence": 0.2,
                "tree_cover_density": 0.2,
                "green_connectivity_window_210m": 0.2,
                "water_proximity_300m": 0.2,
                "soil_permeability": 0.2,
            },
            "vegetation_presence": "CLMS TCD 2023 > 0 or HRL Herbaceous Cover 2023 = 1.",
            "green_connectivity": "Fraction of vegetated valid cells in a 21 x 21 cell moving window (approximately 210 x 210 m).",
            "water_proximity": "Linear distance-decay from mapped OSM water: 1 at water and 0 at 300 m.",
            "soil_permeability": "1 - CLMS Imperviousness Density 2021 / 100.",
            "potential_green_corridor": "Vegetated cells in the upper quartile of the local green-connectivity distribution.",
            "potential_fluvial_corridor": "Vegetated cells within 100 m of an OSM water geometry.",
            "potential_isolated_green": "Vegetated cells in the lower quartile of the local green-connectivity distribution.",
            "structural_urban_barrier": "Cells with CLMS Imperviousness Density >= 50%.",
            "field_validation_priority": "Upper quartile of the calculated general potential; no biological observation is inferred.",
        },
        "thresholds": {
            "vegetation_presence": "TCD 2023 > 0% or Herbaceous Cover 2023 = 1",
            "green_connectivity_window_cells": 21,
            "green_connectivity_window_approx_m": 210,
            "potential_green_corridor_connectivity_p75": round(connected_threshold, 4),
            "potential_isolated_green_connectivity_p25": round(isolated_threshold, 4),
            "potential_fluvial_corridor_max_distance_m": 100,
            "water_proximity_decay_max_distance_m": 300,
            "structural_urban_barrier_imperviousness_min_pct": 50,
            "field_validation_priority_potential_p75_0_100": round(potential_threshold, 1),
        },
        "sources": [
            {
                "name": "CLMS HRL Tree Cover Density 2023 and Herbaceous Cover 2023",
                "organization": "Copernicus Land Monitoring Service / European Environment Agency",
                "official_url": "https://land.copernicus.eu/en/products/high-resolution-layer-forests-and-tree-cover",
                "service": "Official WMS, locally stored GeoTIFF",
                "format": "GeoTIFF",
                "crs": "EPSG:3035",
                "resolution_m": 10,
                "variables": "Tree-cover density 0-100% and herbaceous-cover presence",
                "update_frequency": "annual product editions",
                "license": "Copernicus free, full and open data policy with attribution",
                "example_connection": "metadata/copernicus_hrl_expanded_connector.json",
                "status": "verified",
                "metadata": "metadata/copernicus_hrl_expanded_connector.json",
            },
            {
                "name": "CLMS HRL Imperviousness Density 2021",
                "organization": "Copernicus Land Monitoring Service / European Environment Agency",
                "official_url": "https://land.copernicus.eu/en/products/high-resolution-layer-imperviousness/imperviousness-density-2021",
                "service": "Official WMS, locally stored GeoTIFF",
                "format": "GeoTIFF",
                "crs": "EPSG:3035",
                "resolution_m": 10,
                "variables": "Imperviousness density 0-100%",
                "update_frequency": "multiannual product editions",
                "license": "Copernicus free, full and open data policy with attribution",
                "example_connection": "metadata/copernicus_hrl_expanded_connector.json",
                "status": "verified",
                "metadata": "metadata/copernicus_hrl_expanded_connector.json",
            },
            {
                "name": "OpenStreetMap water geometries",
                "organization": "OpenStreetMap contributors / OpenStreetMap Foundation",
                "official_url": "https://www.openstreetmap.org/",
                "service": "Previously verified local extract",
                "format": "GeoJSON",
                "crs": "EPSG:4326",
                "variables": "Mapped water lines and polygons",
                "update_frequency": "continuous community updates",
                "license": "ODbL 1.0",
                "example_connection": "processed/water_osm.geojson",
                "status": "verified",
                "metadata": "metadata/data_sources_matrix.md",
            },
        ],
        "local_evidence_sources": [
            {
                "name": "Catalan Butterfly Monitoring Scheme",
                "reference": "Itinerari 168 — Pla de les Forques",
                "evidence_type": "observed monitoring summary",
                "automated_connection": False,
                "raw_annual_dataset_in_project": False,
            },
            {
                "name": "Programa de Seguiment de Ratpenats",
                "reference": "Caixes refugi de la Seu d'Urgell",
                "evidence_type": "monitoring infrastructure summary",
                "automated_connection": False,
                "detailed_coordinates_published": False,
            },
            {
                "name": "Seguiment d'Amfibis Comuns de Catalunya (SACC)",
                "reference": "Programa de la Societat Catalana d'Herpetologia",
                "evidence_type": "official monitoring program; local quantitative results not incorporated",
                "automated_connection": False,
                "local_sampling_point_verified": False,
                "local_results_in_project": False,
            },
        ],
        "local_biodiversity_data": {
            "butterflies_cbms": {
                "information_type": "observed monitoring",
                "display_status": "Dades observades disponibles",
                "route": "CBMS 168 — Pla de les Forques",
                "municipality": "la Seu d'Urgell",
                "period_with_data": "2011-2025",
                "years_with_data": 15,
                "route_length_m": 1400,
                "sections": 12,
                "recorded_species": 81,
                "annual_mean_species": 35,
                "counted_individuals": 5873,
                "annual_mean_individuals": 392,
                "surveys": 188,
                "continuous_series_since": 2011,
                "source": "Catalan Butterfly Monitoring Scheme",
                "annual_values_incorporated": False,
                "species_list_incorporated": False,
                "scope_note": "Aquestes dades corresponen a l’itinerari del Pla de les Forques i no representen automàticament tot el nucli urbà.",
                "verification_basis": "Summary values supplied for this project update; no annual rows, trends or species-level list were incorporated.",
            },
            "bats": {
                "information_type": "monitoring infrastructure",
                "display_status": "Infraestructura disponible, sense ocupació confirmada",
                "active_refuge_boxes": 5,
                "box_names": ["la Seu A-seu1", "la Seu A-seu2", "la Seu A-seu3", "la Seu A-seu4", "la Seu A-seu5"],
                "all_active": True,
                "registered_reviews_per_box": 2,
                "public_registered_species": 0,
                "different_schwegler_models": 5,
                "installed_on": "trees",
                "occupancy_confirmed": False,
                "species_absence_inferred": False,
                "public_representation": "aggregated; no detailed coordinates",
                "source": "Programa de Seguiment de Ratpenats",
                "interpretation": "Hi ha infraestructura local de seguiment, però les dades públiques disponibles no confirmen ocupació ni permeten valorar la diversitat de ratpenats.",
            },
            "amphibians_sacc": {
                "information_type": "official monitoring program",
                "display_status": "Programa verificat — resultats locals quantitatius no incorporats",
                "source": "Seguiment d'Amfibis Comuns de Catalunya (SACC)",
                "coordinator": "Societat Catalana d'Herpetologia",
                "monitoring_period": "2023-present",
                "local_sampling_point_verified": False,
                "local_results_incorporated": False,
                "totals_displayed": False,
                "trends_displayed": False,
                "abundances_displayed": False,
                "species_lists_displayed": False,
                "availability_note": "No s'ha verificat cap punt SACC públic ni cap resultat quantitatiu dins l'àmbit EcoRadar de la Seu.",
                "interpretation": "La manca d'una exportació local SACC no significa zero observacions d'amfibis.",
            },
            "light_pollution": {
                "status": "service_unavailable",
                "display": "Capa local no incorporada",
                "incorporated_dataset": False,
                "interpretation": "No light barrier is mapped. Only the structural urban barrier from imperviousness is represented.",
            },
        },
        "limitations": [
            "This is a relative screening index, not a biodiversity inventory or habitat-suitability model calibrated with field data.",
            "The CBMS figures summarize route 168 only; no annual rows, trends or species list are incorporated and the route does not represent the entire urban area.",
            "Bat boxes are monitoring infrastructure, not fauna observations; zero publicly registered species does not demonstrate absence or non-occupancy.",
            "The SACC program is verified, but no public local sampling point or quantitative result was incorporated for the EcoRadar La Seu scope.",
            "No detailed bat-box coordinates are published.",
            "OSM water and green context can be incomplete and does not describe ecological quality or permanence of water.",
            "Potential corridors and isolated spaces are structural hypotheses that require field validation.",
            "Light barriers are not mapped because no verified local geospatial layer is incorporated.",
        ],
        "outputs": {
            "analysis_raster": "processed/urban_biodiversity/biodiversity_urban_potential.tif",
            "web_raster_base": "maps/biodiversity_urban_potential.webp",
            "web_overlays": {
                "potential_green_corridor": "maps/biodiversity_green_corridor.png",
                "potential_fluvial_corridor": "maps/biodiversity_fluvial_corridor.png",
                "potential_isolated_green": "maps/biodiversity_isolated_green.png",
                "structural_urban_barrier": "maps/biodiversity_structural_barrier.png",
                "field_validation_priority": "maps/biodiversity_field_priority.png",
            },
            "visual_encoding": "Continuous potential base plus transparent pattern overlays; overlaps remain visible instead of replacing the base value.",
        },
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    INDICATOR.write_text(text)
    METADATA.write_text(text)
    return payload


if __name__ == "__main__":
    result = calculate()
    print(INDICATOR)
    print(METADATA)
    print(MAPS / "biodiversity_urban_potential.webp")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
