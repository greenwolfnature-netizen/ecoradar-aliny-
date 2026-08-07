"""Recalculate Alinyà's date-dependent topographic shade at 15:00 local time."""

from __future__ import annotations

from datetime import datetime, time, timezone
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import mapping

from calculate_la_seu_urban_metrics import _solar_position


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
DEM = PROJECT / "processed" / "terrain" / "dem.tif"
STUDY = PROJECT / "processed" / "study_area.gpkg"
OUTPUT = PROJECT / "indicators" / "daily_shade.json"
LOCAL_TZ = ZoneInfo("Europe/Madrid")


def _checked_at() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        parsed = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def calculate() -> dict:
    checked = _checked_at()
    local_date = checked.astimezone(LOCAL_TZ).date()
    local_datetime = datetime.combine(local_date, time(15, 0), tzinfo=LOCAL_TZ)
    solar_utc = local_datetime.astimezone(timezone.utc)
    study4326 = gpd.read_file(STUDY).to_crs(4326)
    west, south, east, north = (float(value) for value in study4326.total_bounds)
    latitude, longitude = (south + north) / 2, (west + east) / 2
    solar_elevation, solar_azimuth = _solar_position(solar_utc, latitude, longitude)

    with rasterio.open(DEM) as source:
        dem = source.read(1).astype("float32")
        profile = source.profile
    valid = np.isfinite(dem) & (dem != profile.get("nodata", -9999))
    study = gpd.read_file(STUDY).to_crs(profile["crs"])
    scope = geometry_mask(
        [mapping(geometry) for geometry in study.geometry if geometry is not None],
        out_shape=dem.shape,
        transform=profile["transform"],
        invert=True,
    )
    valid &= scope
    resolution_x = abs(float(profile["transform"].a))
    resolution_y = abs(float(profile["transform"].e))
    filled = np.where(valid, dem, np.nan)
    dy, dx = np.gradient(filled, resolution_y, resolution_x)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    elevation = math.radians(max(-90.0, min(90.0, solar_elevation)))
    azimuth = math.radians(solar_azimuth)
    incidence = (
        np.sin(elevation) * np.cos(slope)
        + np.cos(elevation) * np.sin(slope) * np.cos(azimuth - aspect)
    )
    shade = valid & ((incidence <= 0) if solar_elevation > 0 else True)
    shade_pct = round(float(100 * shade.sum() / valid.sum()), 1) if valid.any() else None
    payload = {
        "checked_at_utc": checked.isoformat().replace("+00:00", "Z"),
        "data_at_utc": solar_utc.isoformat().replace("+00:00", "Z"),
        "data_at_local": local_datetime.isoformat(),
        "value": {"shade_pct": shade_pct, "solar_elevation_deg": round(solar_elevation, 1), "solar_azimuth_deg": round(solar_azimuth, 1)},
        "source": "ICGC Model d'elevacions del terreny 5 m + posició solar calculada",
        "method": "Ombra topogràfica local a les 15.00 h segons la incidència solar sobre pendent i orientació del DEM.",
        "method_state": "calculated" if valid.any() else "unavailable",
        "limitations": "No incorpora ombres projectades per arbres o edificis ni l'horitzó llunyà; no és ombra acumulada del dia, confort tèrmic ni una mesura de camp.",
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(calculate(), ensure_ascii=False, indent=2))
