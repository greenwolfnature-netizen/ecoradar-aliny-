"""Recalculate only the date-dependent shade layer from static LiDAR arrays."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from rasterio.enums import Resampling
from rasterio.transform import from_bounds

from calculate_la_seu_expanded_indicators import _binary_rgba, _to_web_grid
from calculate_la_seu_extended_urban_indicators import _rgba_continuous, _write_png
from calculate_la_seu_sentinel2_indicators import _write_webp
from calculate_la_seu_urban_metrics import _shadow_mask, _solar_position


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
SOURCE = PROJECT / "processed" / "lidar_expanded_arrays.npz"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
SOURCE_METADATA = PROJECT / "metadata" / "lidar_expanded_analysis.json"
OUTPUT = PROJECT / "indicators" / "daily_shade.json"
MAPS = PROJECT / "maps"
LOCAL_TZ = ZoneInfo("Europe/Madrid")


def calculate(target_date: date, local_clock: time) -> dict:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    project = json.loads(PROJECT_MANIFEST.read_text(encoding="utf-8"))
    source_metadata = json.loads(SOURCE_METADATA.read_text(encoding="utf-8"))
    bbox4326 = tuple(float(value) for value in project["study_area"]["expanded_urban_bbox_epsg4326"])
    local_datetime = datetime.combine(target_date, local_clock, tzinfo=LOCAL_TZ)
    solar_utc = local_datetime.astimezone(timezone.utc)
    latitude = (bbox4326[1] + bbox4326[3]) / 2
    longitude = (bbox4326[0] + bbox4326[2]) / 2
    solar_elevation, solar_azimuth = _solar_position(solar_utc, latitude, longitude)

    lidar = np.load(SOURCE)
    dsm = lidar["dsm"].astype("float32")
    dtm = lidar["dtm"].astype("float32")
    canopy = lidar["canopy"].astype(bool)
    valid = lidar["valid"].astype(bool)
    scope = lidar["scope_mask"].astype(bool)
    bounds = [float(value) for value in lidar["bounds"]]
    resolution = abs(float(lidar["transform"][0]))
    if solar_elevation <= 0:
        shade = valid & scope
        method_state = "sun_below_horizon"
    else:
        shade = _shadow_mask(
            dsm,
            dtm,
            canopy,
            resolution,
            solar_elevation,
            solar_azimuth,
        ) & scope
        method_state = "calculated"

    source_profile = {
        "transform": from_bounds(*bounds, dsm.shape[1], dsm.shape[0]),
        "crs": "EPSG:25831",
    }
    rgba = _binary_rgba(shade, valid & scope, (32, 102, 67), off=(248, 248, 243, 28), alpha=205)
    shade_web, shade_web_valid = _to_web_grid(
        shade.astype("float32"),
        valid & scope,
        source_profile,
        bbox4326,
        8,
        resampling=Resampling.average,
    )
    web_rgba = _rgba_continuous(
        shade_web,
        [0, 0.1, 0.5, 1],
        [(245, 247, 240), (176, 211, 204), (82, 153, 125), (25, 87, 61)],
        valid=shade_web_valid,
        alpha=220,
    )
    MAPS.mkdir(parents=True, exist_ok=True)
    _write_png(MAPS / "expanded_lidar_shade.png", rgba)
    _write_webp(MAPS / "expanded_lidar_shade.webp", rgba)
    _write_png(MAPS / "expanded_lidar_shade_web.png", web_rgba)

    valid_count = int((valid & scope).sum())
    payload = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_at_utc": solar_utc.isoformat().replace("+00:00", "Z"),
        "data_at_local": local_datetime.isoformat(),
        "status": "actualitzada avui",
        "value": {
            "shade_pct": round(float(shade[valid & scope].mean() * 100), 1),
            "solar_elevation_deg": round(float(solar_elevation), 1),
            "solar_azimuth_deg": round(float(solar_azimuth), 1),
        },
        "source": "ICGC LiDAR Territorial v3.1 + posició solar calculada",
        "source_data_period": source_metadata.get("source", "ICGC LiDAR Territorial v3.1, 2021-2023"),
        "inputs": ["relleu LiDAR", "edificis LiDAR", "arbres LiDAR", "data", "hora", "posició solar"],
        "method_state": method_state,
        "method": "Ombra directa sobre DSM/DTM de 2 m amb obstacles d'edificis i vegetació i posició solar de la data i hora indicades.",
        "valid_cells": valid_count,
        "limitations": "Model d'ombra directa per a un instant; no és confort fisiològic, temperatura de l'aire ni ombra acumulada del dia.",
        "outputs": {
            "png_2m": "maps/expanded_lidar_shade.png",
            "webp_2m": "maps/expanded_lidar_shade.webp",
            "png_8m": "maps/expanded_lidar_shade_web.png",
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(LOCAL_TZ).date().isoformat())
    parser.add_argument("--local-time", default="15:00")
    args = parser.parse_args()
    target_date = date.fromisoformat(args.date)
    local_clock = time.fromisoformat(args.local_time)
    payload = calculate(target_date, local_clock)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
