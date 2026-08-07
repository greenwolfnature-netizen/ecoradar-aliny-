"""Calculate the derived EcoRadar current wildfire-danger reading.

This Analysis Engine module consumes normalized official-source outputs. It is
not an official alert and does not replace Pla Alfa or official daily maps.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject
from shapely.geometry import box, mapping
from shapely.ops import transform as transform_geometry


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
CONFIG_PATH = ROOT / "config" / "current_fire_danger.json"
STRUCTURAL = PROJECT / "processed" / "fire_danger_structural_2024.tif"
NDMI = PROJECT / "processed" / "sentinel2_indicators_expanded" / "ndmi_sentinel2_expanded.tif"
TREE_COVER = PROJECT / "processed" / "copernicus_hrl_expanded" / "tree_cover_density_2023.tif"
HERBACEOUS_COVER = PROJECT / "processed" / "copernicus_hrl_expanded" / "herbaceous_cover_2023.tif"
LIDAR = PROJECT / "processed" / "lidar_expanded_arrays.npz"
METEO = PROJECT / "raw" / "meteocat_xema" / "CD_observations.csv"
SENTINEL_META = PROJECT / "indicators" / "sentinel2_expanded_indicators.json"
SURFACE_TEMPERATURE_META = PROJECT / "metadata" / "current_surface_temperature.json"
CREAF_FORESTDROUGHT = PROJECT / "raw" / "creaf_forestdrought" / "forestdrought_latest.geojson"
CREAF_META = PROJECT / "metadata" / "creaf_forestdrought_connector.json"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
OUT_DIR = PROJECT / "processed" / "current_fire_danger"
OUT_TIF = OUT_DIR / "current_fire_danger_0_100.tif"
OUT_GEOJSON = PROJECT / "maps" / "current_fire_danger_cells.geojson"
OUT_PNG = PROJECT / "maps" / "current_fire_danger.png"
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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_checked_at() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        parsed = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _reproject_raster(path: Path, shape: tuple[int, int], transform: Affine, *, resampling: Resampling) -> np.ndarray:
    result = np.full(shape, np.nan, dtype="float32")
    with rasterio.open(path) as source:
        reproject(
            source=source.read(1),
            destination=result,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=transform,
            dst_crs="EPSG:25831",
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return result


def _reproject_array(
    values: np.ndarray,
    source_transform: Affine,
    shape: tuple[int, int],
    target_transform: Affine,
    *,
    resampling: Resampling,
) -> np.ndarray:
    result = np.full(shape, np.nan, dtype="float32")
    reproject(
        source=values.astype("float32"),
        destination=result,
        src_transform=source_transform,
        src_crs="EPSG:25831",
        src_nodata=np.nan,
        dst_transform=target_transform,
        dst_crs="EPSG:25831",
        dst_nodata=np.nan,
        resampling=resampling,
    )
    return result


def _creaf_arrays(
    shape: tuple[int, int],
    transform: Affine,
    study_mask: np.ndarray,
) -> dict[str, np.ndarray]:
    """Rasterize native 500 m ForestDrought cells without interpolation."""

    source = _read_json(CREAF_FORESTDROUGHT)
    from_wgs84 = Transformer.from_crs(4326, 25830, always_xy=True).transform
    to_grid = Transformer.from_crs(25830, 25831, always_xy=True).transform
    fields = ("SFP", "CFP", "DDS", "LFMC", "DFMC", "REW")
    shapes: dict[str, list[tuple[dict, float]]] = {field: [] for field in fields}
    for feature in source.get("features", []):
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            continue
        centre_x, centre_y = from_wgs84(
            float(coordinates[0]),
            float(coordinates[1]),
        )
        footprint = transform_geometry(
            to_grid,
            box(
                centre_x - 250,
                centre_y - 250,
                centre_x + 250,
                centre_y + 250,
            ),
        )
        properties = feature.get("properties") or {}
        for field in fields:
            value = properties.get(field)
            if value is not None and np.isfinite(float(value)):
                shapes[field].append((mapping(footprint), float(value)))

    arrays: dict[str, np.ndarray] = {}
    for field, values in shapes.items():
        arrays[field] = rasterize(
            values,
            out_shape=shape,
            transform=transform,
            fill=np.nan,
            dtype="float32",
            all_touched=False,
        )
        arrays[field] = np.where(study_mask, arrays[field], np.nan)
    if not np.isfinite(arrays["SFP"]).any() and not np.isfinite(
        arrays["CFP"]
    ).any():
        raise RuntimeError(
            "The normalized CREAF ForestDrought subset contains no usable SFP or CFP cells."
        )
    return arrays


def _robust_scale(values: np.ndarray, mask: np.ndarray, percentiles: list[float], *, inverse: bool = False) -> tuple[np.ndarray, float, float]:
    valid = mask & np.isfinite(values)
    if not valid.any():
        return np.full(values.shape, np.nan, dtype="float32"), math.nan, math.nan
    low, high = (float(v) for v in np.nanpercentile(values[valid], percentiles))
    if not high > low:
        return np.full(values.shape, np.nan, dtype="float32"), low, high
    scaled = np.clip((values - low) / (high - low), 0, 1) * 100
    if inverse:
        scaled = 100 - scaled
    return np.where(valid, scaled, np.nan).astype("float32"), low, high


def _moving_mean(values: np.ndarray, valid: np.ndarray, width: int) -> np.ndarray:
    pad = width // 2
    padded_values = np.pad(np.where(valid, values, 0), pad)
    padded_valid = np.pad(valid.astype("float32"), pad)
    total = np.zeros_like(values, dtype="float32")
    count = np.zeros_like(values, dtype="float32")
    for row in range(width):
        for col in range(width):
            total += padded_values[row : row + values.shape[0], col : col + values.shape[1]]
            count += padded_valid[row : row + values.shape[0], col : col + values.shape[1]]
    result = np.full_like(values, np.nan, dtype="float32")
    np.divide(total, count, out=result, where=count > 0)
    return result


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


def _freshness(reference: str, limits: dict, now: datetime) -> float:
    instant = datetime.fromisoformat(reference.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    age = max(0.0, (now - instant).total_seconds() / 86400)
    full, zero = float(limits["full"]), float(limits["zero"])
    if age <= full:
        return 1.0
    if age >= zero:
        return 0.0
    return 1 - (age - full) / (zero - full)


def _orientation(degrees: float) -> tuple[str, str]:
    directions = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
    cardinal = directions[int(((degrees % 360) + 22.5) // 45) % 8]
    exposure = "solana" if 112.5 <= degrees % 360 <= 247.5 else "obaga"
    return cardinal, exposure


def _colour(value: np.ndarray, valid: np.ndarray) -> np.ndarray:
    stops = np.asarray([0, 20, 40, 60, 80, 90, 100], dtype="float32")
    colours = np.asarray(
        [(47, 143, 78), (168, 201, 74), (240, 216, 75), (239, 139, 44), (212, 61, 47), (113, 29, 45), (113, 29, 45)],
        dtype="float32",
    )
    rgba = np.zeros((*value.shape, 4), dtype="uint8")
    for channel in range(3):
        rgba[..., channel] = np.interp(np.nan_to_num(value), stops, colours[:, channel]).astype("uint8")
    rgba[..., 3] = np.where(valid, 235, 0).astype("uint8")
    return rgba


def _latest_weather(frame: pd.DataFrame, config: dict) -> tuple[dict, dict[str, float]]:
    codes = config["xema"]["variables"]
    frame["data_lectura"] = pd.to_datetime(frame["data_lectura"], utc=True)
    frame["codi_variable"] = frame["codi_variable"].astype(str)
    latest: dict[str, dict] = {}
    scales: dict[str, float] = {}
    p = config["normalization"]["robust_percentiles"]
    for name, code in codes.items():
        subset = frame[frame["codi_variable"] == str(code)].sort_values("data_lectura")
        if subset.empty:
            continue
        row = subset.iloc[-1]
        latest[name] = {
            "value": float(row["valor_lectura"]),
            "timestamp_utc": row["data_lectura"].isoformat().replace("+00:00", "Z"),
            "validation_code": "" if pd.isna(row.get("codi_estat", "")) else str(row.get("codi_estat", "")),
        }
        low, high = (float(v) for v in np.nanpercentile(subset["valor_lectura"].astype(float), p))
        if high > low:
            value = float(np.clip((float(row["valor_lectura"]) - low) / (high - low), 0, 1) * 100)
            scales[name] = value
            latest[name]["history_p05"] = low
            latest[name]["history_p95"] = high
    today = frame["data_lectura"].max().date()
    daily = frame[frame["data_lectura"].dt.date == today]
    for output, code, reducer in (
        ("daily_min_relative_humidity_pct", codes["relative_humidity_pct"], "min"),
        ("daily_max_wind_gust_ms", codes["wind_gust_ms"], "max"),
    ):
        values = daily.loc[daily["codi_variable"] == str(code), "valor_lectura"].astype(float)
        if not values.empty:
            latest[output] = float(values.min() if reducer == "min" else values.max())
    return latest, scales


def calculate() -> dict:
    now = _run_checked_at()
    config = _read_json(CONFIG_PATH)
    weights = config["weights"]
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise RuntimeError("Current-fire weights must sum to 1")

    with rasterio.open(STRUCTURAL) as source:
        structural_raw = source.read(1).astype("float32")
        transform = source.transform
        profile = source.profile.copy()
        shape = structural_raw.shape
        structural_valid = (structural_raw >= 1) & (structural_raw <= 10)

    manifest = _read_json(PROJECT_MANIFEST)
    bbox4326 = manifest["study_area"]["expanded_urban_bbox_epsg4326"]
    to_grid = Transformer.from_crs(4326, 25831, always_xy=True).transform
    study_geometry = transform_geometry(to_grid, box(*bbox4326))
    study_mask = geometry_mask([mapping(study_geometry)], out_shape=shape, transform=transform, invert=True)
    structural = np.where(structural_valid & study_mask, (structural_raw - 1) / 9 * 100, np.nan)

    percentiles = config["normalization"]["robust_percentiles"]
    surface_selection = _read_json(SURFACE_TEMPERATURE_META)["selected"]
    lst_path = ROOT / surface_selection["normalized_tif"]
    creaf_meta = _read_json(CREAF_META)
    creaf_raw = _creaf_arrays(shape, transform, study_mask)
    creaf_fire_potential = (
        np.fmax(creaf_raw["SFP"], creaf_raw["CFP"]) / 9 * 100
    ).astype("float32")
    ndmi_raw = _reproject_raster(NDMI, shape, transform, resampling=Resampling.bilinear)
    ndmi_dryness, ndmi_low, ndmi_high = _robust_scale(ndmi_raw, study_mask, percentiles, inverse=True)
    lst_raw = _reproject_raster(lst_path, shape, transform, resampling=Resampling.bilinear)
    temperature, lst_low, lst_high = _robust_scale(lst_raw, study_mask, percentiles)
    tree_presence = _reproject_raster(TREE_COVER, shape, transform, resampling=Resampling.average)
    herbaceous_presence = _reproject_raster(HERBACEOUS_COVER, shape, transform, resampling=Resampling.average)
    vegetation_fraction = np.clip(np.maximum(tree_presence / 100, herbaceous_presence), 0, 1) * 100
    vegetation_valid = study_mask & np.isfinite(vegetation_fraction)
    continuity = _moving_mean(vegetation_fraction, vegetation_valid, int(config["normalization"]["continuity_window_cells"]))
    vegetation = (
        vegetation_fraction * float(config["normalization"]["vegetation_cell_fraction"])
        + continuity * float(config["normalization"]["vegetation_neighbourhood_fraction"])
    ).astype("float32")

    lidar = np.load(LIDAR)
    lidar_transform = Affine(*[float(v) for v in lidar["transform"]])
    lidar_valid = lidar["valid"].astype(bool) & lidar["scope_mask"].astype(bool)
    slope_source = np.where(lidar_valid, lidar["terrain_slope"], np.nan)
    slope_deg = _reproject_array(slope_source, lidar_transform, shape, transform, resampling=Resampling.average)
    slope, slope_low, slope_high = _robust_scale(slope_deg, study_mask, percentiles)
    dtm = lidar["dtm"].astype("float32")
    dy, dx = np.gradient(dtm, 2.0, 2.0)
    aspect_source = (np.degrees(np.arctan2(-dx, dy)) + 360) % 360
    aspect_sin = _reproject_array(np.where(lidar_valid, np.sin(np.radians(aspect_source)), np.nan), lidar_transform, shape, transform, resampling=Resampling.average)
    aspect_cos = _reproject_array(np.where(lidar_valid, np.cos(np.radians(aspect_source)), np.nan), lidar_transform, shape, transform, resampling=Resampling.average)
    aspect_deg = (np.degrees(np.arctan2(aspect_sin, aspect_cos)) + 360) % 360
    aspect = ((1 - np.cos(np.radians(aspect_deg))) / 2 * 100).astype("float32")

    weather_frame = pd.read_csv(METEO)
    weather, weather_scales = _latest_weather(weather_frame, config)
    wind_value = weather.get("wind_speed_ms", {}).get("value")
    humidity_value = weather.get("relative_humidity_pct", {}).get("value")
    wind_score = weather_scales.get("wind_speed_ms")
    humidity_score = weather_scales.get("relative_humidity_pct")
    if humidity_score is not None:
        humidity_score = 100 - humidity_score
    wind = np.full(shape, wind_score if wind_score is not None else np.nan, dtype="float32")
    humidity = np.full(shape, humidity_score if humidity_score is not None else np.nan, dtype="float32")

    components = {
        "creaf_fire_potential": creaf_fire_potential,
        "structural": structural,
        "ndmi_dryness": ndmi_dryness,
        "surface_temperature": temperature,
        "vegetation_continuity": vegetation,
        "wind": wind,
        "relative_humidity_inverse": humidity,
        "slope": slope,
        "aspect": aspect,
    }
    denominator = np.zeros(shape, dtype="float32")
    numerator = np.zeros(shape, dtype="float32")
    available = {}
    for key, values in components.items():
        present = study_mask & np.isfinite(values)
        available[key] = present
        denominator[present] += float(weights[key])
        numerator[present] += float(weights[key]) * values[present]
    valid = study_mask & (denominator > 0)
    final = np.full(shape, np.nan, dtype="float32")
    np.divide(numerator, denominator, out=final, where=valid)
    contributions = {}
    for key, values in components.items():
        contribution = np.full(shape, np.nan, dtype="float32")
        np.divide(values * float(weights[key]), denominator, out=contribution, where=available[key] & (denominator > 0))
        contributions[key] = contribution

    sentinel_meta = _read_json(SENTINEL_META)
    references = {
        "creaf_fire_potential": creaf_meta["data_at_utc"],
        "structural": "2024-01-01T00:00:00Z",
        "ndmi_dryness": sentinel_meta["acquired_at_utc"],
        "surface_temperature": surface_selection["acquired_at_utc"],
        "vegetation_continuity": "2023-12-31T00:00:00Z",
        "wind": weather.get("wind_speed_ms", {}).get("timestamp_utc"),
        "relative_humidity_inverse": weather.get("relative_humidity_pct", {}).get("timestamp_utc"),
        "slope": "2023-12-31T00:00:00Z",
        "aspect": "2023-12-31T00:00:00Z",
    }
    quality = {key: 1.0 for key in weights}
    for key, weather_key in (("wind", "wind_speed_ms"), ("relative_humidity_inverse", "relative_humidity_pct")):
        code = weather.get(weather_key, {}).get("validation_code")
        quality[key] = 1.0 if code == "V" else 0.8 if code in ("", "T") else 0.0
    confidence_numerator = np.zeros(shape, dtype="float32")
    for key in weights:
        reference = references[key]
        freshness = _freshness(reference, config["freshness_days"][key], now) if reference else 0.0
        reliability = freshness * float(config["spatial_representativeness"][key]) * quality[key]
        confidence_numerator[available[key]] += float(weights[key]) * reliability
    confidence = np.where(study_mask, confidence_numerator * 100, np.nan)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    profile.update(dtype="float32", nodata=-9999.0, compress="deflate", count=1)
    with rasterio.open(OUT_TIF, "w", **profile) as target:
        target.write(np.where(valid, final, -9999).astype("float32"), 1)
    rgba = _colour(final, valid)
    with rasterio.open(
        OUT_PNG,
        "w",
        driver="PNG",
        width=shape[1],
        height=shape[0],
        count=4,
        dtype="uint8",
    ) as target:
        for band in range(4):
            target.write(rgba[..., band], band + 1)

    to_wgs84 = Transformer.from_crs(25831, 4326, always_xy=True).transform
    features = []
    area_by_category: dict[str, float] = {label: 0.0 for label in ("molt baix", "baix", "moderat", "alt", "molt alt", "extrem")}
    for row, col in zip(*np.where(valid)):
        left, top = rasterio.transform.xy(transform, row, col, offset="ul")
        right, bottom = left + transform.a, top + transform.e
        cell = box(min(left, right), min(bottom, top), max(left, right), max(bottom, top))
        clipped = cell.intersection(study_geometry)
        if clipped.is_empty:
            continue
        index = float(final[row, col])
        category = _category(index)
        area_ha = clipped.area / 10000
        area_by_category[category] += area_ha
        ranked = sorted(
            ((key, float(values[row, col])) for key, values in contributions.items() if np.isfinite(values[row, col])),
            key=lambda item: item[1],
            reverse=True,
        )
        dominant = [key for key, _ in ranked[:3]]
        angle = float(aspect_deg[row, col])
        cardinal, exposure = _orientation(angle) if np.isfinite(angle) else (None, None)
        props = {
            "cell_id": f"FD-{row:02d}-{col:02d}",
            "index_0_100": round(index, 2),
            "category": category,
            "updated_at_utc": now.isoformat(),
            "confidence_pct": round(float(confidence[row, col]), 1),
            "confidence": _confidence_label(float(confidence[row, col])),
            "complete": bool(math.isclose(float(denominator[row, col]), 1.0, abs_tol=1e-6)),
            "available_weight_pct": round(float(denominator[row, col]) * 100, 1),
            "area_ha": round(area_ha, 4),
            "raw": {
                "creaf_sfp_0_9": round(float(creaf_raw["SFP"][row, col]), 3) if np.isfinite(creaf_raw["SFP"][row, col]) else None,
                "creaf_cfp_0_9": round(float(creaf_raw["CFP"][row, col]), 3) if np.isfinite(creaf_raw["CFP"][row, col]) else None,
                "creaf_dds_pct": round(float(creaf_raw["DDS"][row, col]), 2) if np.isfinite(creaf_raw["DDS"][row, col]) else None,
                "creaf_lfmc_pct": round(float(creaf_raw["LFMC"][row, col]), 2) if np.isfinite(creaf_raw["LFMC"][row, col]) else None,
                "creaf_dfmc_pct": round(float(creaf_raw["DFMC"][row, col]), 2) if np.isfinite(creaf_raw["DFMC"][row, col]) else None,
                "creaf_rew_pct": round(float(creaf_raw["REW"][row, col]), 2) if np.isfinite(creaf_raw["REW"][row, col]) else None,
                "structural_1_10": round(float(structural_raw[row, col]), 2) if structural_valid[row, col] else None,
                "ndmi": round(float(ndmi_raw[row, col]), 4) if np.isfinite(ndmi_raw[row, col]) else None,
                "surface_temperature_c": round(float(lst_raw[row, col]), 2) if np.isfinite(lst_raw[row, col]) else None,
                "vegetation_cover_pct": round(float(vegetation_fraction[row, col]), 1) if np.isfinite(vegetation_fraction[row, col]) else None,
                "vegetation_continuity_pct": round(float(continuity[row, col]), 1) if np.isfinite(continuity[row, col]) else None,
                "slope_deg": round(float(slope_deg[row, col]), 2) if np.isfinite(slope_deg[row, col]) else None,
                "slope_pct": round(float(np.tan(np.radians(slope_deg[row, col])) * 100), 1) if np.isfinite(slope_deg[row, col]) else None,
                "aspect_deg": round(angle, 1) if np.isfinite(angle) else None,
                "aspect_cardinal": cardinal,
                "aspect_exposure": exposure,
                "wind_speed_kmh": round(float(wind_value) * 3.6, 1) if wind_value is not None else None,
                "relative_humidity_pct": round(float(humidity_value), 1) if humidity_value is not None else None,
            },
            "normalized": {key: round(float(values[row, col]), 2) if np.isfinite(values[row, col]) else None for key, values in components.items()},
            "contributions": {key: round(float(values[row, col]), 2) if np.isfinite(values[row, col]) else None for key, values in contributions.items()},
            "dominant_variables": dominant,
            "dominant_labels": [LABELS[key] for key in dominant],
            "source_dates": references,
        }
        features.append({"type": "Feature", "geometry": mapping(transform_geometry(to_wgs84, clipped)), "properties": props})
    OUT_GEOJSON.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    category_counts = pd.Series([feature["properties"]["category"] for feature in features]).value_counts()
    predominant = str(category_counts.index[0])
    general_contributions = {key: float(np.nanmean(values[valid])) for key, values in contributions.items()}
    general_dominant = [key for key, _ in sorted(general_contributions.items(), key=lambda item: item[1], reverse=True)[:3]]
    average_index = float(np.nanmean(final[valid]))
    global_confidence = float(np.nanmean(confidence[valid]))
    very_high_area = area_by_category["molt alt"] + area_by_category["extrem"]
    total_area = sum(area_by_category.values())
    latest_timestamp = max(reference for reference in references.values() if reference)
    variable_status = {
        "creaf_fire_potential": {
            "value": (
                f"SFP {float(np.nanmedian(creaf_raw['SFP'])):.1f}/9 · "
                f"CFP {float(np.nanmedian(creaf_raw['CFP'])):.1f}/9"
            ),
            "source": "CREAF/EMF · ForestDrought 500 m",
        },
        "structural": {"value": f"mediana {float(np.nanmedian(structural_raw[structural_valid & study_mask])):.1f}/10", "source": "Generalitat · perill bàsic 2024"},
        "ndmi_dryness": {"value": f"mediana {float(np.nanmedian(ndmi_raw[study_mask & np.isfinite(ndmi_raw)])):.3f}", "source": "Copernicus Sentinel-2 L2A"},
        "surface_temperature": {
            "value": f"mediana {float(np.nanmedian(lst_raw[study_mask & np.isfinite(lst_raw)])):.1f} °C",
            "source": surface_selection["source"],
        },
        "vegetation_continuity": {"value": f"coberta mitjana {float(np.nanmean(vegetation_fraction[vegetation_valid])):.1f} %", "source": "Copernicus CLMS HRL 2023"},
        "wind": {"value": f"{float(wind_value) * 3.6:.1f} km/h" if wind_value is not None else "dada no disponible", "source": "Meteocat XEMA · CD"},
        "relative_humidity_inverse": {"value": f"{float(humidity_value):.0f} %" if humidity_value is not None else "dada no disponible", "source": "Meteocat XEMA · CD"},
        "slope": {"value": f"mediana {float(np.nanmedian(slope_deg[study_mask & np.isfinite(slope_deg)])):.1f}°", "source": "ICGC LiDAR Territorial v3.1"},
        "aspect": {"value": "orientació derivada del MDT", "source": "ICGC LiDAR Territorial v3.1"},
    }
    for key, item in variable_status.items():
        item.update(
            date_utc=references[key],
            weight_pct=round(weights[key] * 100),
            quality="provisional" if key in ("wind", "relative_humidity_inverse") and quality[key] < 1 else "verificada",
            update_status="actualitzada avui" if references[key] and references[key][:10] == now.date().isoformat() else "última dada vàlida",
        )

    payload = {
        "generated_at_utc": now.isoformat(),
        "checked_at_utc": now.isoformat().replace("+00:00", "Z"),
        "reading": "Perill d'incendi actual",
        "status": "completa" if all(feature["properties"]["complete"] for feature in features) else "incompleta en algunes cel·les",
        "official_alert": False,
        "grid": {"crs": "EPSG:25831", "resolution_m": 100, "cells": len(features), "geojson": str(OUT_GEOJSON.relative_to(ROOT)), "raster": str(OUT_TIF.relative_to(ROOT))},
        "summary": {
            "mean_index_0_100": round(average_index, 1),
            "predominant_category": predominant,
            "maximum_index_0_100": round(float(np.nanmax(final[valid])), 1),
            "maximum_category": _category(float(np.nanmax(final[valid]))),
            "area_by_category_ha": {key: round(value, 2) for key, value in area_by_category.items()},
            "very_high_or_extreme_area_pct": round(100 * very_high_area / total_area, 1),
            "dominant_variables": general_dominant,
            "dominant_labels": [LABELS[key] for key in general_dominant],
            "latest_update_utc": latest_timestamp,
            "confidence_pct": round(global_confidence, 1),
            "confidence": _confidence_label(global_confidence),
        },
        "weather": weather,
        "variables_today": variable_status,
        "normalization": {
            "method": "P5-P95 robust scaling within the study area or the 35-day XEMA history; CREAF uses 100 × max(SFP, CFP) / 9; missing variables are reweighted, never set to zero.",
            "creaf_fire_potential": "100 × max(SFP, CFP) / 9 within each native 500 m model cell; no spatial interpolation",
            "ndmi_p05_p95": [round(ndmi_low, 4), round(ndmi_high, 4)],
            "lst_c_p05_p95": [round(lst_low, 2), round(lst_high, 2)],
            "slope_deg_p05_p95": [round(slope_low, 2), round(slope_high, 2)],
        },
        "weights": weights,
        "data_providers": [
            {
                "name": "CREAF, Ecosystem Modelling Facility (EMF)",
                "role": "ForestDrought modelled forest drought and fire-potential data provider",
                "source_url": creaf_meta["source_url"],
                "model_date": creaf_meta["model_date"],
                "checked_at_utc": creaf_meta["latest_catalog_check_utc"],
            }
        ],
        "limitations": [
            "Índex EcoRadar derivat; no és una alerta oficial ni substitueix el Pla Alfa o el mapa diari oficial.",
            "Vent i humitat són observacions puntuals de l'estació XEMA CD, no un camp meteorològic urbà modelitzat.",
            "NDMI i LST descriuen l'última adquisició vàlida disponible, no necessàriament el mateix instant que la meteorologia.",
            "La continuïtat vegetal és una mesura de cobertura cartogràfica, no càrrega de combustible validada al camp.",
            "ForestDrought és un model de procés a 500 m per a cel·les forestals; no és observació directa, dada de carrer, incendi actiu ni alerta operativa.",
            "La data del model ForestDrought es conserva separada de la data diària de comprovació i la publicació pot tenir retard.",
        ],
    }
    OUT_INDICATOR.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_METADATA.write_text(json.dumps({"source_gate": "verified", "checked_at_utc": payload["checked_at_utc"], "config": str(CONFIG_PATH.relative_to(ROOT)), "inputs": {"creaf_forestdrought": str(CREAF_FORESTDROUGHT.relative_to(ROOT)), "structural": str(STRUCTURAL.relative_to(ROOT)), "ndmi": str(NDMI.relative_to(ROOT)), "lst": str(lst_path.relative_to(ROOT)), "tree_cover": str(TREE_COVER.relative_to(ROOT)), "herbaceous_cover": str(HERBACEOUS_COVER.relative_to(ROOT)), "lidar": str(LIDAR.relative_to(ROOT)), "meteorology": str(METEO.relative_to(ROOT))}, "result": payload}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    payload = calculate()
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
