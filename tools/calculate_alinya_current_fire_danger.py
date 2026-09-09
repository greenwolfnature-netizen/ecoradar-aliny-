"""Calculate the derived current wildfire-danger reading for Alinyà.

This Analysis Engine module combines the verified Alinyà structural analysis
inputs with the latest normalized XEMA observations. It is not an official
alert and does not replace Pla Alfa or official daily danger products.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import array_bounds
from rasterio.warp import Resampling, transform_bounds
from shapely.geometry import box, mapping
from shapely.ops import transform as transform_geometry
from zoneinfo import ZoneInfo

from calculate_alinya_integrated_fire_danger import CRS, OFFICIAL, RES, _grid, _reproject
from calculate_la_seu_current_fire_danger import _latest_weather, _moving_mean, _robust_scale
from calculate_la_seu_sentinel2_indicators import _write_raster, _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
CONFIG_PATH = ROOT / "config" / "current_fire_danger.json"
SURFACE_TEMPERATURE_META = PROJECT / "metadata" / "current_surface_temperature.json"
NDMI = PROJECT / "processed" / "teledeteccio" / "ndmi.tif"
TREE_COVER = PROJECT / "processed" / "copernicus_hrl" / "tree_cover_density_2023.tif"
HERBACEOUS_COVER = PROJECT / "processed" / "copernicus_hrl" / "herbaceous_cover_2023.tif"
CREAF_FORESTDROUGHT = PROJECT / "raw" / "creaf_forestdrought" / "forestdrought_latest.geojson"
CREAF_META = PROJECT / "metadata" / "creaf_forestdrought_connector.json"
SLOPE = PROJECT / "processed" / "terrain" / "slope.tif"
ASPECT = PROJECT / "processed" / "terrain" / "aspect.tif"
METEO = PROJECT / "raw" / "meteocat_xema" / "Y4_observations.csv"
METEO_METADATA = PROJECT / "raw" / "meteocat_xema" / "Y4_metadata.json"
WIND_METEO = PROJECT / "raw" / "meteocat_xema" / "CJ_wind_observations.csv"
WIND_METEO_METADATA = PROJECT / "raw" / "meteocat_xema" / "CJ_wind_metadata.json"
PLA_ALFA = PROJECT / "raw" / "pla_alfa" / "figols_alinya_current.json"
SENTINEL_METADATA = PROJECT / "indicators" / "teledeteccio_sentinel2.json"
LANDSAT_METADATA = PROJECT / "metadata" / "landsat_connector.json"
TERRAIN_METADATA = PROJECT / "metadata" / "terrain_metadata.json"
OUT_DIR = PROJECT / "processed" / "incendis" / "current_fire_danger"
OUT_TIF = OUT_DIR / "current_fire_danger_0_100.tif"
OUT_WEBP = PROJECT / "maps" / "incendis" / "current_fire_danger.webp"
OUT_GEOJSON = PROJECT / "maps" / "incendis" / "current_fire_danger_cells.geojson"
OUT_INDICATOR = PROJECT / "indicators" / "current_fire_danger.json"
OUT_METADATA = PROJECT / "metadata" / "current_fire_danger.json"

LABELS = {
    "creaf_fire_potential": "Potencial de foc ForestDrought elevat",
    "structural": "Perill estructural elevat",
    "ndmi_dryness": "Vegetació seca",
    "surface_temperature": "Temperatura superficial elevada",
    "vegetation_continuity": "Massa vegetal contínua",
    "wind": "Vent fort",
    "relative_humidity_inverse": "Humitat relativa baixa",
    "slope": "Pendent pronunciat",
    "aspect": "Exposició de solana",
}
LOCAL_TZ = ZoneInfo("Europe/Madrid")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _checked_at() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        instant = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        return instant.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _category(value: float) -> str:
    if value <= 20:
        return "molt baix"
    if value <= 40:
        return "baix"
    if value <= 60:
        return "moderat"
    if value <= 80:
        return "alt"
    if value <= 90:
        return "molt alt"
    return "extrem"


def _confidence_label(value: float) -> str:
    if value >= 75:
        return "alta"
    if value >= 50:
        return "mitjana"
    return "baixa"


def _parse_reference(reference: str | None) -> datetime | None:
    if not reference:
        return None
    instant = datetime.fromisoformat(reference.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


def _freshness_assessment(reference: str | None, policy: dict, now: datetime) -> dict:
    """Return the temporal eligibility of one component without altering its value."""
    kind = policy.get("kind")
    if kind == "structural":
        return {
            "kind": "structural",
            "status": "estructural",
            "status_label": "estructural · vigent",
            "age_hours": None,
            "factor": 1.0,
            "full_weight_max_age_hours": None,
            "exclude_after_hours": None,
            "rationale": policy.get("rationale"),
        }
    if kind != "dynamic":
        raise RuntimeError(f"Unknown Alinyà freshness kind: {kind!r}")
    instant = _parse_reference(reference)
    full_hours = float(policy["full_weight_max_age_hours"])
    zero_hours = float(policy["exclude_after_hours"])
    if zero_hours <= full_hours:
        raise RuntimeError("Freshness exclusion threshold must exceed the full-weight threshold.")
    if instant is None:
        age_hours = None
        factor = 0.0
        status = "too_old"
        status_label = "dada no disponible · pes exclòs"
    else:
        age_hours = max(0.0, (now - instant).total_seconds() / 3600)
        if age_hours <= full_hours:
            factor = 1.0
            status = "current"
            status_label = "actual · pes complet"
        elif age_hours >= zero_hours:
            factor = 0.0
            status = "too_old"
            status_label = "massa antiga · pes exclòs"
        else:
            factor = 1 - (age_hours - full_hours) / (zero_hours - full_hours)
            status = "recent"
            status_label = f"recent · pes reduït al {factor * 100:.0f} %"
    return {
        "kind": "dynamic",
        "status": status,
        "status_label": status_label,
        "age_hours": None if age_hours is None else round(age_hours, 1),
        "factor": round(float(factor), 6),
        "full_weight_max_age_hours": full_hours,
        "exclude_after_hours": zero_hours,
        "rationale": policy.get("rationale"),
    }


def _context_freshness(reference: str | None, policy: dict, now: datetime) -> dict:
    """Classify non-scored operational context with explicit timestamps."""
    instant = _parse_reference(reference)
    current_hours = float(policy["current_max_age_hours"])
    too_old_hours = float(policy["too_old_after_hours"])
    age_hours = None if instant is None else max(0.0, (now - instant).total_seconds() / 3600)
    if age_hours is None:
        status, label = "unavailable", "dada no disponible"
    elif age_hours <= current_hours:
        status, label = "current", "actual"
    elif age_hours < too_old_hours:
        status, label = "recent", "recent"
    else:
        status, label = "too_old", "massa antiga"
    return {
        "status": status,
        "status_label": label,
        "age_hours": None if age_hours is None else round(age_hours, 1),
        "current_max_age_hours": current_hours,
        "too_old_after_hours": too_old_hours,
    }


def _orientation(degrees: float) -> tuple[str, str]:
    directions = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
    cardinal = directions[int(((degrees % 360) + 22.5) // 45) % 8]
    exposure = "solana" if 112.5 <= degrees % 360 <= 247.5 else "obaga"
    return cardinal, exposure


def _rgba(index: np.ndarray, valid: np.ndarray) -> np.ndarray:
    stops = np.asarray([0, 20, 40, 60, 80, 90, 100], dtype="float32")
    colours = np.asarray(
        [
            (47, 143, 78),
            (168, 201, 74),
            (240, 216, 75),
            (239, 139, 44),
            (212, 61, 47),
            (113, 29, 45),
            (113, 29, 45),
        ],
        dtype="float32",
    )
    rgba = np.zeros((*index.shape, 4), dtype="uint8")
    for channel in range(3):
        rgba[..., channel] = np.interp(np.nan_to_num(index), stops, colours[:, channel]).astype("uint8")
    rgba[..., 3] = np.where(valid, 235, 0).astype("uint8")
    return rgba


def _latest_landsat_scene(metadata: dict) -> str:
    dates = [scene.get("acquired_at_utc") for scene in metadata.get("scenes", []) if scene.get("valid_study_pixels", 0)]
    return max(dates)


def _creaf_arrays(shape, transform, study_mask) -> dict[str, np.ndarray]:
    source = _read_json(CREAF_FORESTDROUGHT)
    from_wgs84 = Transformer.from_crs(4326, 25830, always_xy=True).transform
    to_grid = Transformer.from_crs(25830, CRS, always_xy=True).transform
    fields = ("SFP", "CFP", "DDS", "LFMC", "DFMC", "REW")
    shapes = {field: [] for field in fields}
    for feature in source.get("features", []):
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            continue
        centre_x, centre_y = from_wgs84(float(coordinates[0]), float(coordinates[1]))
        footprint = transform_geometry(
            to_grid,
            box(centre_x - 250, centre_y - 250, centre_x + 250, centre_y + 250),
        )
        properties = feature.get("properties") or {}
        for field in fields:
            value = properties.get(field)
            if value is not None and np.isfinite(float(value)):
                shapes[field].append((mapping(footprint), float(value)))
    arrays = {}
    for field, values in shapes.items():
        arrays[field] = rasterize(
            values, out_shape=shape, transform=transform, fill=np.nan,
            dtype="float32", all_touched=False,
        )
        arrays[field] = np.where(study_mask, arrays[field], np.nan)
    if not np.isfinite(arrays["SFP"]).any() and not np.isfinite(arrays["CFP"]).any():
        raise RuntimeError("ForestDrought contains no usable SFP or CFP cells in Alinyà.")
    return arrays


def _fill_local_gaps(values: np.ndarray, mask: np.ndarray, passes: int = 3) -> np.ndarray:
    """Fill only small rasterization gaps from adjacent valid 100 m cells."""
    result = values.astype("float32").copy()
    for _ in range(passes):
        missing = mask & ~np.isfinite(result)
        if not missing.any():
            break
        padded = np.pad(result, 1, constant_values=np.nan)
        neighbours = np.stack(
            [
                padded[dr : dr + result.shape[0], dc : dc + result.shape[1]]
                for dr in range(3)
                for dc in range(3)
                if (dr, dc) != (1, 1)
            ]
        )
        finite = np.isfinite(neighbours)
        count = finite.sum(axis=0)
        local = np.full(result.shape, np.nan, dtype="float32")
        np.divide(
            np.where(finite, neighbours, 0).sum(axis=0),
            count,
            out=local,
            where=count > 0,
        )
        fill = missing & np.isfinite(local)
        result[fill] = local[fill]
    return np.where(mask, result, np.nan)


def _precipitation_context(frame: pd.DataFrame, precipitation_code: str) -> dict:
    """Summarize observed rain without treating missing periods as zero rain."""
    rows = frame[
        (frame["codi_estacio"].astype(str) == "Y4")
        & (frame["codi_variable"].astype(str) == str(precipitation_code))
    ].copy()
    if rows.empty:
        return {
            "status": "unavailable",
            "data_at_utc": None,
            "recent_24h_mm": None,
            "last_7_days_mm": None,
            "last_30_days_mm": None,
            "days_without_significant_rain": None,
        }
    rows["data_lectura"] = pd.to_datetime(rows["data_lectura"], utc=True)
    rows["valor_lectura"] = pd.to_numeric(rows["valor_lectura"], errors="coerce")
    rows = rows.dropna(subset=["data_lectura", "valor_lectura"]).sort_values("data_lectura")
    anchor = rows["data_lectura"].max()

    def observed_sum(days: int, minimum_coverage: float) -> float | None:
        selected = rows[(rows["data_lectura"] > anchor - pd.Timedelta(days=days)) & (rows["data_lectura"] <= anchor)]
        # XEMA Y4 publishes 30-minute precipitation periods. Refuse an
        # accumulation when the record is too incomplete for the requested span.
        if len(selected) < int(days * 48 * minimum_coverage):
            return None
        return round(float(selected["valor_lectura"].sum()), 1)

    local = rows.set_index("data_lectura").tz_convert(LOCAL_TZ)
    daily = local["valor_lectura"].resample("D").agg(["sum", "count"])
    dry_days = 0
    significant_threshold = 1.0
    daily_rows = list(daily.itertuples())
    if daily_rows and int(daily_rows[-1].count) < 40:
        if float(daily_rows[-1].sum) >= significant_threshold:
            daily_rows = []
        else:
            daily_rows = daily_rows[:-1]
    for day in reversed(daily_rows):
        if int(day.count) < 40:
            break
        if float(day.sum) >= significant_threshold:
            break
        dry_days += 1
    return {
        "status": "available",
        "data_at_utc": anchor.to_pydatetime().isoformat().replace("+00:00", "Z"),
        "recent_24h_mm": observed_sum(1, 0.80),
        "last_7_days_mm": observed_sum(7, 0.80),
        "last_30_days_mm": observed_sum(30, 0.80),
        "days_without_significant_rain": dry_days,
        "significant_rain_threshold_mm_day": significant_threshold,
        "station": "Meteocat XEMA · Y4 Alinyà",
        "method": "Suma de períodes XEMA de 30 minuts fins a l'última observació; s'oculta si la cobertura és inferior al 80%.",
        "climatology_comparison": None,
        "climatology_note": "No es mostra anomalia climàtica: no hi ha una normal oficial homogènia de Y4 verificada i integrada.",
    }


def calculate() -> dict:
    now = _checked_at()
    config = _read_json(CONFIG_PATH)
    weights = config["weights"]
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise RuntimeError("Alinyà current-fire weights must sum to 1")

    study, shape, transform, study_mask = _grid()
    study_geometry = study.geometry.union_all()

    percentiles = config["normalization"]["robust_percentiles"]
    official_raw = _reproject(OFFICIAL, shape, transform, Resampling.nearest)
    official_valid = study_mask & np.isfinite(official_raw) & (official_raw >= 1) & (official_raw <= 10)
    structural = np.where(official_valid, (official_raw - 1) / 9 * 100, np.nan).astype("float32")

    surface_selection = _read_json(SURFACE_TEMPERATURE_META)["selected"]
    lst_path = ROOT / surface_selection["normalized_tif"]
    lst_raw = _reproject(lst_path, shape, transform, Resampling.bilinear)
    temperature, temp_p10, temp_p90 = _robust_scale(lst_raw, study_mask, percentiles)
    ndmi_raw = _reproject(NDMI, shape, transform, Resampling.average)
    dryness, ndmi_p10, ndmi_p90 = _robust_scale(ndmi_raw, study_mask, percentiles, inverse=True)

    creaf_raw = _creaf_arrays(shape, transform, study_mask)
    creaf_fire_potential = (np.fmax(creaf_raw["SFP"], creaf_raw["CFP"]) / 9 * 100).astype("float32")

    tree_presence = _reproject(TREE_COVER, shape, transform, Resampling.average)
    herbaceous_presence = _reproject(HERBACEOUS_COVER, shape, transform, Resampling.average)
    vegetation_fraction = np.clip(np.maximum(tree_presence / 100, herbaceous_presence), 0, 1) * 100
    vegetation_valid = study_mask & np.isfinite(vegetation_fraction)
    continuity = _moving_mean(
        vegetation_fraction,
        vegetation_valid,
        int(config["normalization"]["continuity_window_cells"]),
    )
    vegetation = (
        vegetation_fraction * float(config["normalization"]["vegetation_cell_fraction"])
        + continuity * float(config["normalization"]["vegetation_neighbourhood_fraction"])
    ).astype("float32")

    slope_deg = _fill_local_gaps(
        _reproject(SLOPE, shape, transform, Resampling.nearest), study_mask
    )
    slope, slope_low, slope_high = _robust_scale(slope_deg, study_mask, percentiles)
    aspect_source = _reproject(ASPECT, shape, transform, Resampling.nearest)
    aspect_sin = _fill_local_gaps(np.sin(np.radians(aspect_source)), study_mask)
    aspect_cos = _fill_local_gaps(np.cos(np.radians(aspect_source)), study_mask)
    aspect_deg = (np.degrees(np.arctan2(aspect_sin, aspect_cos)) + 360) % 360
    aspect = ((1 - np.cos(np.radians(aspect_deg))) / 2 * 100).astype("float32")

    weather_frames = [pd.read_csv(METEO)]
    if WIND_METEO.is_file():
        weather_frames.append(pd.read_csv(WIND_METEO))
    weather_frame = pd.concat(weather_frames, ignore_index=True)
    weather_config = {
        "xema": {
            "variables": {
                "air_temperature_c": "32",
                "wind_speed_ms": "30",
                "wind_direction_deg": "31",
                "relative_humidity_pct": "33",
                "precipitation_mm": "35",
                "wind_gust_ms": "50",
                "wind_gust_direction_deg": "51",
            }
        },
        "normalization": {"robust_percentiles": percentiles},
    }
    weather, weather_scales = _latest_weather(weather_frame, weather_config)
    wind_value = weather.get("wind_speed_ms", {}).get("value")
    humidity_value = weather.get("relative_humidity_pct", {}).get("value")
    wind_score = weather_scales.get("wind_speed_ms")
    gust_score = weather_scales.get("wind_gust_ms")
    if gust_score is not None:
        wind_score = gust_score if wind_score is None else max(wind_score, gust_score)
    humidity_score = weather_scales.get("relative_humidity_pct")
    if humidity_score is not None:
        humidity_score = 100 - humidity_score
    wind = np.full(shape, wind_score if wind_score is not None else np.nan, dtype="float32")
    humidity = np.full(shape, humidity_score if humidity_score is not None else np.nan, dtype="float32")
    precipitation_context = _precipitation_context(
        weather_frame, weather_config["xema"]["variables"]["precipitation_mm"]
    )
    pla_alfa = _read_json(PLA_ALFA) if PLA_ALFA.is_file() else {
        "official": True,
        "municipality": "Fígols i Alinyà",
        "level": None,
        "label": "dada no disponible",
        "data_at_utc": None,
        "checked_at_utc": now.isoformat().replace("+00:00", "Z"),
        "status": "service_unavailable",
        "note": "No hi ha cap última dada oficial Pla Alfa disponible localment.",
    }

    sentinel_metadata = _read_json(SENTINEL_METADATA)
    landsat_metadata = _read_json(LANDSAT_METADATA)
    creaf_metadata = _read_json(CREAF_META)
    wind_timestamps = [
        item.get("timestamp_utc")
        for item in (weather.get("wind_speed_ms", {}), weather.get("wind_gust_ms", {}))
        if item.get("timestamp_utc")
    ]
    references = {
        "creaf_fire_potential": creaf_metadata.get("data_at_utc"),
        "structural": "2024-01-01T00:00:00Z",
        "ndmi_dryness": sentinel_metadata["acquired_at_utc"],
        # A multitemporal composite has a period, not an observation timestamp.
        # It remains available as cartographic context but cannot receive the
        # freshness weight of its newest component scene.
        "surface_temperature": (
            surface_selection.get("acquired_at_utc")
            if surface_selection.get("temporal_kind", "single_observation") == "single_observation"
            else None
        ),
        "vegetation_continuity": "2023-12-31T00:00:00Z",
        "wind": max(wind_timestamps) if wind_timestamps else None,
        "relative_humidity_inverse": weather.get("relative_humidity_pct", {}).get("timestamp_utc"),
        "slope": "2023-12-31T00:00:00Z",
        "aspect": "2023-12-31T00:00:00Z",
    }
    freshness_policy = config.get("alinya_freshness_policy") or {}
    missing_policies = sorted(set(weights) - set(freshness_policy))
    if missing_policies:
        raise RuntimeError(f"Missing Alinyà freshness policies: {', '.join(missing_policies)}")
    freshness = {
        key: _freshness_assessment(references[key], freshness_policy[key], now)
        for key in weights
    }
    effective_weights = {
        key: float(weights[key]) * float(freshness[key]["factor"])
        for key in weights
    }
    if effective_weights["wind"] + effective_weights["relative_humidity_inverse"] <= 0:
        raise RuntimeError(
            "No current or recent XEMA wind/humidity is available; keep the last valid current-fire product."
        )
    eligible_weight = sum(effective_weights.values())
    if eligible_weight <= 0:
        raise RuntimeError("No temporally eligible component remains for current fire danger.")

    context_policy = config["alinya_context_freshness"]
    meteo_reference = max(
        (
            item.get("timestamp_utc")
            for item in weather.values()
            if isinstance(item, dict) and item.get("timestamp_utc")
        ),
        default=None,
    )
    meteorology_freshness = _context_freshness(
        meteo_reference, context_policy["meteorology"], now
    )
    precipitation_context["freshness"] = _context_freshness(
        precipitation_context.get("data_at_utc"), context_policy["meteorology"], now
    )
    pla_alfa = dict(pla_alfa)
    pla_alfa["freshness"] = _context_freshness(
        pla_alfa.get("data_at_utc"), context_policy["pla_alfa"], now
    )

    components = {
        "creaf_fire_potential": creaf_fire_potential,
        "structural": structural,
        "ndmi_dryness": dryness,
        "surface_temperature": temperature,
        "vegetation_continuity": vegetation,
        "wind": wind,
        "relative_humidity_inverse": humidity,
        "slope": slope,
        "aspect": aspect,
    }
    denominator = np.zeros(shape, dtype="float32")
    numerator = np.zeros(shape, dtype="float32")
    available: dict[str, np.ndarray] = {}
    for key, values in components.items():
        present = study_mask & np.isfinite(values) & (effective_weights[key] > 0)
        available[key] = present
        denominator[present] += effective_weights[key]
        numerator[present] += effective_weights[key] * values[present]
    valid = study_mask & (denominator > 0)
    final = np.full(shape, np.nan, dtype="float32")
    np.divide(numerator, denominator, out=final, where=valid)

    contributions: dict[str, np.ndarray] = {}
    for key, values in components.items():
        contribution = np.full(shape, np.nan, dtype="float32")
        np.divide(
            values * effective_weights[key],
            denominator,
            out=contribution,
            where=available[key] & (denominator > 0),
        )
        contributions[key] = contribution
    quality = {key: 1.0 for key in weights}
    for key, weather_key in (("wind", "wind_speed_ms"), ("relative_humidity_inverse", "relative_humidity_pct")):
        code = weather.get(weather_key, {}).get("validation_code")
        quality[key] = 1.0 if code == "V" else 0.8 if code in ("", "T") else 0.0
    confidence_numerator = np.zeros(shape, dtype="float32")
    for key in weights:
        temporal_factor = float(freshness[key]["factor"])
        reliability = temporal_factor * float(config["spatial_representativeness"][key]) * quality[key]
        confidence_numerator[available[key]] += float(weights[key]) * reliability
    confidence = np.where(study_mask, confidence_numerator * 100, np.nan)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": shape[0],
        "width": shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": CRS,
        "transform": transform,
        "nodata": -9999.0,
        "compress": "deflate",
    }
    _write_raster(OUT_TIF, np.where(valid, final, -9999).astype("float32"), profile)
    _write_webp(OUT_WEBP, _rgba(final, valid))

    to_wgs84 = Transformer.from_crs(CRS, 4326, always_xy=True).transform
    features = []
    area_by_category = {
        label: 0.0
        for label in ("molt baix", "baix", "moderat", "alt", "molt alt", "extrem")
    }
    for row, col in zip(*np.where(valid)):
        left, top = rasterio.transform.xy(transform, row, col, offset="ul")
        right, bottom = left + transform.a, top + transform.e
        cell = box(min(left, right), min(bottom, top), max(left, right), max(bottom, top))
        clipped = cell.intersection(study_geometry)
        if clipped.is_empty:
            continue
        index = float(final[row, col])
        category = _category(index)
        area_ha = clipped.area / 10_000
        area_by_category[category] += area_ha
        ranked = sorted(
            (
                (key, float(values[row, col]))
                for key, values in contributions.items()
                if np.isfinite(values[row, col])
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        dominant = [key for key, _ in ranked[:3]]
        aspect_value = float(aspect_deg[row, col]) if np.isfinite(aspect_deg[row, col]) else None
        cardinal, exposure = _orientation(aspect_value) if aspect_value is not None else (None, None)
        props = {
            "cell_id": f"AL-FD-{row:02d}-{col:03d}",
            "index_0_100": round(index, 2),
            "category": category,
            "updated_at_utc": now.isoformat().replace("+00:00", "Z"),
            "confidence_pct": round(float(confidence[row, col]), 1),
            "confidence": _confidence_label(float(confidence[row, col])),
            "complete": bool(
                math.isclose(
                    float(denominator[row, col]), eligible_weight, abs_tol=1e-6
                )
            ),
            "available_weight_pct": round(
                float(denominator[row, col]) / eligible_weight * 100, 1
            ),
            "eligible_base_weight_pct": round(eligible_weight * 100, 1),
            "area_ha": round(area_ha, 4),
            "raw": {
                "official_structural_1_10": round(float(official_raw[row, col]), 2) if official_valid[row, col] else None,
                "surface_temperature_c": round(float(lst_raw[row, col]), 2) if np.isfinite(lst_raw[row, col]) else None,
                "ndmi": round(float(ndmi_raw[row, col]), 4) if np.isfinite(ndmi_raw[row, col]) else None,
                "creaf_sfp_0_9": round(float(creaf_raw["SFP"][row, col]), 2) if np.isfinite(creaf_raw["SFP"][row, col]) else None,
                "creaf_cfp_0_9": round(float(creaf_raw["CFP"][row, col]), 2) if np.isfinite(creaf_raw["CFP"][row, col]) else None,
                "creaf_fire_potential_0_9": round(float(np.fmax(creaf_raw["SFP"][row, col], creaf_raw["CFP"][row, col])), 2) if np.isfinite(creaf_fire_potential[row, col]) else None,
                "vegetation_continuity_0_100": round(float(vegetation[row, col]), 1) if np.isfinite(vegetation[row, col]) else None,
                "slope_deg": round(float(slope_deg[row, col]), 1) if np.isfinite(slope_deg[row, col]) else None,
                "aspect_deg": round(aspect_value, 1) if aspect_value is not None else None,
                "aspect_cardinal": cardinal,
                "aspect_exposure": exposure,
                "wind_speed_kmh": round(float(wind_value) * 3.6, 1) if wind_value is not None else None,
                "wind_gust_kmh": round(float(weather.get("wind_gust_ms", {}).get("value")) * 3.6, 1) if weather.get("wind_gust_ms", {}).get("value") is not None else None,
                "relative_humidity_pct": round(float(humidity_value), 1) if humidity_value is not None else None,
            },
            "normalized": {
                key: round(float(values[row, col]), 2) if np.isfinite(values[row, col]) else None
                for key, values in components.items()
            },
            "contributions": {
                key: round(float(values[row, col]), 2) if np.isfinite(values[row, col]) else None
                for key, values in contributions.items()
            },
            "dominant_variables": dominant,
            "dominant_labels": [LABELS[key] for key in dominant],
            "source_dates": references,
            "source_freshness": freshness,
            "temporally_excluded_variables": [
                key for key, item in freshness.items() if item["factor"] <= 0
            ],
        }
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(transform_geometry(to_wgs84, clipped)),
                "properties": props,
            }
        )
    OUT_GEOJSON.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    average_index = float(np.nanmean(final[valid]))
    maximum_index = float(np.nanmax(final[valid]))
    global_confidence = float(np.nanmean(confidence[valid]))
    category_areas = pd.Series(
        {key: value for key, value in area_by_category.items()}
    )
    predominant = str(category_areas.idxmax())
    general_contributions = {}
    for key, values in contributions.items():
        selected = values[valid & np.isfinite(values)]
        if selected.size:
            general_contributions[key] = float(np.mean(selected))
    general_dominant = [
        key
        for key, _ in sorted(
            general_contributions.items(), key=lambda item: item[1], reverse=True
        )[:3]
    ]
    total_area = sum(area_by_category.values())
    study_area_ha = float(study_geometry.area / 10_000)
    no_data_area_ha = max(0.0, study_area_ha - total_area)
    valid_coverage_pct = 100.0 * total_area / study_area_ha if study_area_ha else 0.0
    very_high_area = area_by_category["molt alt"] + area_by_category["extrem"]

    variable_status = {
        "creaf_fire_potential": {
            "value": f"mediana {float(np.nanmedian(creaf_fire_potential[np.isfinite(creaf_fire_potential)])):.1f}/100",
            "source": "CREAF/EMF · ForestDrought daily modelled forests",
        },
        "structural": {
            "value": f"mediana {float(np.nanmedian(official_raw[official_valid & study_mask])):.1f}/10",
            "source": "Generalitat · perill bàsic 2024",
        },
        "ndmi_dryness": {
            "value": f"mediana {float(np.nanmedian(ndmi_raw[study_mask & np.isfinite(ndmi_raw)])):.3f}",
            "source": "Copernicus Sentinel-2 L2A",
        },
        "surface_temperature": {
            "value": f"mediana {float(np.nanmedian(lst_raw[study_mask & np.isfinite(lst_raw)])):.1f} °C",
            "source": surface_selection["source"],
            "temporal_kind": surface_selection.get("temporal_kind", "single_observation"),
            "period_start_utc": surface_selection.get("period_start_utc"),
            "period_end_utc": surface_selection.get("period_end_utc"),
            "component_scene_count": surface_selection.get("component_scene_count", 1),
        },
        "vegetation_continuity": {
            "value": f"mitjana {float(np.nanmean(vegetation[study_mask & np.isfinite(vegetation)])):.1f}/100",
            "source": "Copernicus CLMS HRL 2023",
        },
        "wind": {
            "value": (
                f"vent {float(wind_value) * 3.6:.1f} km/h · ratxa {float(weather['wind_gust_ms']['value']) * 3.6:.1f} km/h"
                if wind_value is not None and weather.get("wind_gust_ms", {}).get("value") is not None
                else f"vent {float(wind_value) * 3.6:.1f} km/h" if wind_value is not None
                else f"ratxa {float(weather['wind_gust_ms']['value']) * 3.6:.1f} km/h" if weather.get("wind_gust_ms", {}).get("value") is not None
                else "dada no disponible"
            ),
            "source": "Meteocat XEMA · CJ Organyà · 9,2 km de Y4 · el component usa el màxim normalitzat entre vent i ratxa",
        },
        "relative_humidity_inverse": {
            "value": f"{float(humidity_value):.0f} %" if humidity_value is not None else "dada no disponible",
            "source": "Meteocat XEMA · Y4 Alinyà",
        },
        "slope": {
            "value": f"mediana {float(np.nanmedian(slope_deg[study_mask & np.isfinite(slope_deg)])):.1f}°",
            "source": "ICGC · model d'elevacions del terreny 5 m",
        },
        "aspect": {
            "value": "exposició de solana derivada 0–100",
            "source": "ICGC · model d'elevacions del terreny 5 m",
        },
    }
    for key, item in variable_status.items():
        reference = references[key]
        validation_code = ""
        if key == "wind":
            validation_code = weather.get("wind_speed_ms", {}).get("validation_code", "")
        elif key == "relative_humidity_inverse":
            validation_code = weather.get("relative_humidity_pct", {}).get("validation_code", "")
        item.update(
            date_utc=reference,
            weight_pct=round(float(effective_weights[key]) * 100, 1),
            base_weight_pct=round(float(weights[key]) * 100, 1),
            freshness_factor_pct=round(float(freshness[key]["factor"]) * 100, 1),
            temporal_status=freshness[key]["status"],
            temporal_status_label=freshness[key]["status_label"],
            age_hours=freshness[key]["age_hours"],
            freshness_kind=freshness[key]["kind"],
            full_weight_max_age_hours=freshness[key]["full_weight_max_age_hours"],
            exclude_after_hours=freshness[key]["exclude_after_hours"],
            quality=(
                "no disponible"
                if reference is None
                else "provisional"
                if key in ("wind", "relative_humidity_inverse") and validation_code != "V"
                else "verificada"
            ),
            update_status=freshness[key]["status_label"],
        )

    latest_update = max(reference for reference in references.values() if reference)
    west, south, east, north = array_bounds(shape[0], shape[1], transform)
    raster_bbox_epsg4326 = list(
        transform_bounds(CRS, "EPSG:4326", west, south, east, north, densify_pts=21)
    )
    payload = {
        "schema_version": "1.0",
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "checked_at_utc": now.isoformat().replace("+00:00", "Z"),
        "reading": "Perill d'incendi actual",
        "scope": "Muntanya d'Alinyà",
        "status": "completa" if all(item["properties"]["complete"] for item in features) else "incompleta en algunes cel·les",
        "official_alert": False,
        "grid": {
            "crs": CRS,
            "resolution_m": RES,
            "cells": len(features),
            "bbox_epsg4326": raster_bbox_epsg4326,
            "geojson": str(OUT_GEOJSON.relative_to(ROOT)),
            "raster": str(OUT_TIF.relative_to(ROOT)),
            "webp": str(OUT_WEBP.relative_to(ROOT)),
        },
        "summary": {
            "mean_index_0_100": round(average_index, 1),
            "predominant_category": predominant,
            "maximum_index_0_100": round(maximum_index, 1),
            "maximum_category": _category(maximum_index),
            "area_by_category_ha": {
                key: round(value, 2) for key, value in area_by_category.items()
            },
            "study_area_ha": round(study_area_ha, 2),
            "valid_area_ha": round(total_area, 2),
            "no_data_area_ha": round(no_data_area_ha, 2),
            "valid_coverage_pct": round(valid_coverage_pct, 1),
            "coverage_denominator": "entire study-area polygon",
            "very_high_or_extreme_area_pct": round(
                100 * very_high_area / total_area, 1
            ),
            "dominant_variables": general_dominant,
            "dominant_labels": [LABELS[key] for key in general_dominant],
            "latest_update_utc": latest_update,
            "confidence_pct": round(global_confidence, 1),
            "confidence": _confidence_label(global_confidence),
            "eligible_base_weight_pct": round(eligible_weight * 100, 1),
            "temporally_excluded_variables": [
                key for key, item in freshness.items() if item["factor"] <= 0
            ],
        },
        "weather": weather,
        "meteorology_context": {
            "air_temperature": weather.get("air_temperature_c"),
            "relative_humidity": weather.get("relative_humidity_pct"),
            "wind": weather.get("wind_speed_ms"),
            "wind_gust": weather.get("wind_gust_ms"),
            "precipitation_latest_period": weather.get("precipitation_mm"),
            "precipitation_accumulated": precipitation_context,
            "freshness": meteorology_freshness,
            "spatial_scope_note": "Y4 aporta temperatura, humitat i pluja; el vent i les ratxes provenen de CJ Organyà, a 9,2 km. Són contextos puntuals aplicats a l'àmbit i no una malla de 100 m.",
        },
        "pla_alfa": pla_alfa,
        "variables_today": variable_status,
        "normalization": {
            "method": "P5-P95 dins Alinyà per LST, NDMI i pendent; P5-P95 sobre 35 dies XEMA. El pes base de cada variable dinàmica es multiplica pel seu factor de frescor i els pesos temporalment elegibles i espacialment disponibles es renormalitzen; una dada absent o massa antiga mai es converteix en zero.",
            "ndmi_p10_p90": [round(ndmi_p10, 4), round(ndmi_p90, 4)],
            "lst_c_p10_p90": [round(temp_p10, 2), round(temp_p90, 2)],
            "slope_deg_p05_p95": [round(slope_low, 2), round(slope_high, 2)],
        },
        "weights": weights,
        "effective_weights": effective_weights,
        "freshness_policy": freshness_policy,
        "methodology": "docs/data_sources/fire/current-wildfire-danger-alinya.md",
        "sources": {
            "meteocat": _read_json(METEO_METADATA),
            "meteocat_wind": _read_json(WIND_METEO_METADATA),
            "sentinel2": sentinel_metadata,
            "landsat": landsat_metadata,
            "surface_temperature_selection": surface_selection,
            "forestdrought": creaf_metadata,
            "pla_alfa": pla_alfa,
            "terrain": _read_json(TERRAIN_METADATA),
        },
        "limitations": [
            "Índex EcoRadar derivat; no és una alerta oficial ni substitueix el Pla Alfa o el mapa diari oficial.",
            "El Pla Alfa es mostra en paral·lel com a nivell operatiu municipal oficial i no s'afegeix numèricament a l'índex EcoRadar, per evitar doble recompte i falsa precisió.",
            "La humitat XEMA Y4 i el vent XEMA CJ Organyà són observacions puntuals; CJ és a 9,2 km de Y4 i cap estació representa cada vessant d'un àmbit de 5.464 ha.",
            "Una variable XEMA absent es marca com a no disponible i el pes es renormalitza; no es converteix en zero.",
            "Les variables dinàmiques massa antigues s'exclouen de l'índex actual i només es conserven com a context; dins la franja recent el seu pes es redueix linealment segons la política documentada.",
            "La temperatura superficial no és temperatura de l'aire i l'NDMI és un proxy relatiu, no humitat fina del combustible.",
            "ForestDrought és un model forestal de 500 m; no és una observació, una ignició ni una alerta oficial.",
            "La continuïtat vegetal HRL és horitzontal i no quantifica càrrega, espècie ni estructura vertical del combustible.",
        ],
    }
    OUT_INDICATOR.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    OUT_METADATA.write_text(
        json.dumps(
            {
                "source_gate": "verified",
                "checked_at_utc": payload["checked_at_utc"],
                "config": str(CONFIG_PATH.relative_to(ROOT)),
                "inputs": {
                    "official_structural": str(OFFICIAL.relative_to(ROOT)),
                    "surface_temperature": str(lst_path.relative_to(ROOT)),
                    "ndmi": str(NDMI.relative_to(ROOT)),
                    "tree_cover": str(TREE_COVER.relative_to(ROOT)),
                    "herbaceous_cover": str(HERBACEOUS_COVER.relative_to(ROOT)),
                    "forestdrought": str(CREAF_FORESTDROUGHT.relative_to(ROOT)),
                    "slope": str(SLOPE.relative_to(ROOT)),
                    "aspect": str(ASPECT.relative_to(ROOT)),
                    "meteorology": str(METEO.relative_to(ROOT)),
                    "wind_meteorology": str(WIND_METEO.relative_to(ROOT)),
                },
                "result": payload,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    print(json.dumps(calculate()["summary"], ensure_ascii=False, indent=2))
