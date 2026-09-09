"""Calculate Alinyà vegetation-cover and Landsat display layers from normalized sources."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from shapely.geometry import mapping

from calculate_la_seu_expanded_indicators import _stats, _to_web_grid
from calculate_la_seu_extended_urban_indicators import _rgba_continuous, _write_png
from calculate_la_seu_sentinel2_indicators import _write_raster, _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"
CLMS = PROJECT / "processed" / "copernicus_hrl"
SURFACE_SELECTION = PROJECT / "metadata" / "current_surface_temperature.json"
DERIVED = PROJECT / "processed" / "teledeteccio"
MAPS = PROJECT / "maps" / "teledeteccio"
OUTPUT = PROJECT / "indicators" / "teledeteccio_satellite_layers.json"


def _read(path):
    with rasterio.open(path) as src:
        return src.read(1), src.profile.copy()


def _study_mask(profile, shape):
    study = gpd.read_file(STUDY).to_crs(profile["crs"])
    return geometry_mask([mapping(g) for g in study.geometry if g is not None], out_shape=shape, transform=profile["transform"], invert=True)


def calculate() -> dict:
    study4326 = gpd.read_file(STUDY).to_crs(4326)
    bbox = tuple(float(v) for v in study4326.total_bounds)
    tcd, clms_profile = _read(CLMS / "tree_cover_density_2023.tif")
    herb, _ = _read(CLMS / "herbaceous_cover_2023.tif")
    clms_mask = _study_mask(clms_profile, tcd.shape)
    clms_valid = clms_mask & (tcd <= 100) & (herb <= 1)
    vegetation = ((tcd > 0) | (herb == 1)) & clms_valid
    selection = json.loads(SURFACE_SELECTION.read_text(encoding="utf-8"))["selected"]
    source_metadata = json.loads((ROOT / selection["source_metadata"]).read_text(encoding="utf-8"))
    surface_path = ROOT / selection["normalized_tif"]
    with rasterio.open(surface_path) as src:
        lst = src.read(1)
        lst_profile = src.profile.copy()
    lst_valid = _study_mask(lst_profile, lst.shape) & np.isfinite(lst) & (lst != lst_profile.get("nodata", -9999))
    lst = np.where(lst_valid, lst, np.nan)
    DERIVED.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    _write_raster(DERIVED / "vegetation_cover_2023.tif", vegetation.astype("float32"), clms_profile)
    veg_web, veg_valid = _to_web_grid(vegetation.astype("float32"), clms_valid, clms_profile, bbox, 10, resampling=Resampling.average)
    lst_web, lst_web_valid = _to_web_grid(lst, lst_valid, lst_profile, bbox, 30, resampling=Resampling.bilinear)
    veg_rgba = _rgba_continuous(veg_web, [0,.1,.5,1], [(236,233,222),(196,220,176),(99,162,90),(40,111,55)], valid=veg_valid, alpha=220)
    lst_rgba = _rgba_continuous(lst_web, [20,24,28,32,36,40], [(42,127,96),(166,199,84),(250,204,70),(244,141,40),(214,65,39),(126,24,54)], valid=lst_web_valid, alpha=230)
    _write_webp(MAPS / "vegetation_cover_2023.webp", veg_rgba)
    _write_webp(MAPS / "landsat_lst.webp", lst_rgba)
    pixel_area_ha = abs(clms_profile["transform"].a * clms_profile["transform"].e) / 10000
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "scope":"Muntanya d'Alinyà", "study_bbox_epsg4326":bbox,
        "vegetation_cover": {"source":"CLMS HRL Tree Cover Density 2023 + Herbaceous Cover 2023", "method":"TCD 2023 > 0 or Herbaceous Cover 2023 = 1", "covered_area_ha":round(float(vegetation.sum()*pixel_area_ha),1), "covered_pct":round(float(100*vegetation.sum()/clms_valid.sum()),1), "valid_pixels":int(clms_valid.sum())},
        "surface_temperature": {
            "source": selection["source"],
            "source_key": selection["source_key"],
            "temporal_kind": selection.get("temporal_kind", "single_observation"),
            "acquired_at_utc": selection.get("acquired_at_utc"),
            "period_start_utc": selection.get("period_start_utc"),
            "period_end_utc": selection.get("period_end_utc"),
            "resolution_m": selection["resolution_m"],
            "quality": selection["quality"],
            "date_range": source_metadata.get("date_range") or selection.get("acquired_at_utc"),
            "scene_count": source_metadata.get("scene_count", 1),
            "contributing_scene_count": selection.get("contributing_scene_count"),
            "composite_method": source_metadata.get("composite_method", "single locally QA-valid acquisition"),
            "coverage_pct": source_metadata.get("study_coverage_pct", 100.0),
            "metrics_c": _stats(lst,lst_valid,1),
            "valid_pixels": int(lst_valid.sum()),
        },
        "outputs":{"vegetation":"maps/teledeteccio/vegetation_cover_2023.webp", "temperature":"maps/teledeteccio/landsat_lst.webp"},
        "limitations":{"vegetation":"coverage presence, not biodiversity, habitat quality or fuel load", "temperature":"detailed satellite surface temperature; a multitemporal median is period context and never a single-date observation; it is not air temperature, personal exposure or a climatic normal"},
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    print(json.dumps(calculate(), ensure_ascii=False, indent=2))
