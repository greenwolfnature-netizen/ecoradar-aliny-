"""Calculate the derived current wildfire-danger reading for Alinyà.

This Analysis Engine module combines the verified Alinyà structural analysis
inputs with the latest normalized XEMA observations. It is not an official
alert and does not replace Pla Alfa or official daily danger products.
"""

from __future__ import annotations

from datetime import datetime, timezone
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

from calculate_alinya_integrated_fire_danger import (
    CRS,
    FUEL_SCORES,
    OFFICIAL,
    RES,
    _grid,
    _reproject,
    _robust_scale,
)
from calculate_la_seu_current_fire_danger import _latest_weather
from calculate_la_seu_sentinel2_indicators import _write_raster, _write_webp


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
CONFIG_PATH = ROOT / "config" / "alinya_current_fire_danger.json"
LST = PROJECT / "processed" / "landsat" / "landsat_lst.tif"
NDMI = PROJECT / "processed" / "teledeteccio" / "ndmi.tif"
LANDCOVER = PROJECT / "maps" / "incendis" / "condicions_cobertes_alinya.geojson"
CONCURRENCE = PROJECT / "maps" / "incendis_similarity" / "similitud_condicions_incendi_alinya.geojson"
SLOPE = PROJECT / "processed" / "terrain" / "slope.tif"
ASPECT = PROJECT / "processed" / "terrain" / "aspect.tif"
METEO = PROJECT / "raw" / "meteocat_xema" / "Y4_observations.csv"
METEO_METADATA = PROJECT / "raw" / "meteocat_xema" / "Y4_metadata.json"
SENTINEL_METADATA = PROJECT / "indicators" / "teledeteccio_sentinel2.json"
LANDSAT_METADATA = PROJECT / "metadata" / "landsat_connector.json"
CONCURRENCE_METADATA = PROJECT / "metadata" / "perill_integrat_ecoradar.json"
OUT_DIR = PROJECT / "processed" / "incendis" / "current_fire_danger"
OUT_TIF = OUT_DIR / "current_fire_danger_0_100.tif"
OUT_WEBP = PROJECT / "maps" / "incendis" / "current_fire_danger.webp"
OUT_GEOJSON = PROJECT / "maps" / "incendis" / "current_fire_danger_cells.geojson"
OUT_INDICATOR = PROJECT / "indicators" / "current_fire_danger.json"
OUT_METADATA = PROJECT / "metadata" / "current_fire_danger.json"

LABELS = {
    "official_structural_2024": "Perill estructural elevat",
    "surface_temperature": "Temperatura superficial elevada",
    "vegetation_dryness_ndmi": "Vegetació seca",
    "vegetation_type_fuel_potential": "Coberta amb més potencial de combustible",
    "territorial_concurrence": "Concurrència territorial elevada",
    "wind": "Vent fort",
    "relative_humidity_inverse": "Humitat relativa baixa",
}

COVER_LABELS = {index: name for index, name in enumerate(FUEL_SCORES, start=1)}


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


def _freshness(reference: str | None, full_days: float, zero_days: float, now: datetime) -> float:
    if not reference:
        return 0.0
    instant = datetime.fromisoformat(reference.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - instant).total_seconds() / 86400)
    if age_days <= full_days:
        return 1.0
    if age_days >= zero_days:
        return 0.0
    return 1 - (age_days - full_days) / (zero_days - full_days)


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


def _source_reliability(key: str, reference: str | None, config: dict, now: datetime) -> float:
    settings = config["confidence"][key]
    freshness = _freshness(
        reference,
        float(settings["freshness_full_days"]),
        float(settings["freshness_zero_days"]),
        now,
    )
    return (
        freshness
        * float(settings["spatial_representativeness"])
        * float(settings["source_quality"])
    )


def calculate() -> dict:
    now = _checked_at()
    config = _read_json(CONFIG_PATH)
    weights = config["weights"]
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise RuntimeError("Alinyà current-fire weights must sum to 1")

    study, shape, transform, study_mask = _grid()
    study_geometry = study.geometry.union_all()
    study_mask = geometry_mask(
        [mapping(study_geometry)],
        out_shape=shape,
        transform=transform,
        invert=True,
        all_touched=True,
    )

    official_raw = _reproject(OFFICIAL, shape, transform, Resampling.nearest)
    official_valid = study_mask & np.isfinite(official_raw) & (official_raw >= 1) & (official_raw <= 10)
    official = np.where(official_valid, (official_raw - 1) / 9 * 100, np.nan).astype("float32")

    lst_raw = _reproject(LST, shape, transform, Resampling.bilinear)
    temperature_unit, temp_p10, temp_p90 = _robust_scale(lst_raw, study_mask)
    temperature = temperature_unit * 100
    ndmi_raw = _reproject(NDMI, shape, transform, Resampling.bilinear)
    dryness_unit, ndmi_p10, ndmi_p90 = _robust_scale(ndmi_raw, study_mask, inverse=True)
    dryness = dryness_unit * 100

    covers = gpd.read_file(LANDCOVER).to_crs(CRS)
    fuel = rasterize(
        ((mapping(row.geometry), FUEL_SCORES.get(row.condicio, np.nan) * 100) for row in covers.itertuples()),
        out_shape=shape,
        transform=transform,
        fill=np.nan,
        dtype="float32",
    )
    cover_code = rasterize(
        ((mapping(row.geometry), list(FUEL_SCORES).index(row.condicio) + 1) for row in covers.itertuples() if row.condicio in FUEL_SCORES),
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype="uint8",
    )
    fuel = np.where(study_mask, fuel, np.nan)

    concurrence_gdf = gpd.read_file(CONCURRENCE).to_crs(CRS)
    concurrence = rasterize(
        ((mapping(row.geometry), float(row.similitud_score) * 100) for row in concurrence_gdf.itertuples()),
        out_shape=shape,
        transform=transform,
        fill=np.nan,
        dtype="float32",
    )
    concurrence = np.where(study_mask, np.clip(concurrence, 0, 100), np.nan)
    slope = _reproject(SLOPE, shape, transform, Resampling.average)
    aspect = _reproject(ASPECT, shape, transform, Resampling.nearest)

    weather_frame = pd.read_csv(METEO)
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
        "normalization": {"robust_percentiles": config["normalization"]["weather_percentiles"]},
    }
    weather, weather_scales = _latest_weather(weather_frame, weather_config)
    wind_value = weather.get("wind_speed_ms", {}).get("value")
    humidity_value = weather.get("relative_humidity_pct", {}).get("value")
    wind_score = weather_scales.get("wind_speed_ms")
    humidity_score = weather_scales.get("relative_humidity_pct")
    if humidity_score is not None:
        humidity_score = 100 - humidity_score
    wind = np.full(shape, wind_score if wind_score is not None else np.nan, dtype="float32")
    humidity = np.full(shape, humidity_score if humidity_score is not None else np.nan, dtype="float32")

    components = {
        "official_structural_2024": official,
        "surface_temperature": temperature,
        "vegetation_dryness_ndmi": dryness,
        "vegetation_type_fuel_potential": fuel,
        "territorial_concurrence": concurrence,
        "wind": wind,
        "relative_humidity_inverse": humidity,
    }
    denominator = np.zeros(shape, dtype="float32")
    numerator = np.zeros(shape, dtype="float32")
    available: dict[str, np.ndarray] = {}
    for key, values in components.items():
        present = study_mask & np.isfinite(values)
        available[key] = present
        denominator[present] += float(weights[key])
        numerator[present] += float(weights[key]) * values[present]
    valid = study_mask & (denominator > 0)
    final = np.full(shape, np.nan, dtype="float32")
    np.divide(numerator, denominator, out=final, where=valid)

    contributions: dict[str, np.ndarray] = {}
    for key, values in components.items():
        contribution = np.full(shape, np.nan, dtype="float32")
        np.divide(
            values * float(weights[key]),
            denominator,
            out=contribution,
            where=available[key] & (denominator > 0),
        )
        contributions[key] = contribution

    sentinel_metadata = _read_json(SENTINEL_METADATA)
    landsat_metadata = _read_json(LANDSAT_METADATA)
    concurrence_metadata = _read_json(CONCURRENCE_METADATA)
    references = {
        "official_structural_2024": config["confidence"]["official_structural_2024"]["reference_utc"],
        "surface_temperature": _latest_landsat_scene(landsat_metadata),
        "vegetation_dryness_ndmi": sentinel_metadata["acquired_at_utc"],
        "vegetation_type_fuel_potential": config["confidence"]["vegetation_type_fuel_potential"]["reference_utc"],
        "territorial_concurrence": concurrence_metadata["generated_at_utc"],
        "wind": weather.get("wind_speed_ms", {}).get("timestamp_utc"),
        "relative_humidity_inverse": weather.get("relative_humidity_pct", {}).get("timestamp_utc"),
    }
    confidence = np.zeros(shape, dtype="float32")
    for key in weights:
        reliability = _source_reliability(key, references[key], config, now)
        confidence[available[key]] += float(weights[key]) * reliability * 100
    confidence = np.where(study_mask, confidence, np.nan)

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
        aspect_value = float(aspect[row, col]) if np.isfinite(aspect[row, col]) else None
        cardinal, exposure = _orientation(aspect_value) if aspect_value is not None else (None, None)
        props = {
            "cell_id": f"AL-FD-{row:02d}-{col:03d}",
            "index_0_100": round(index, 2),
            "category": category,
            "updated_at_utc": now.isoformat().replace("+00:00", "Z"),
            "confidence_pct": round(float(confidence[row, col]), 1),
            "confidence": _confidence_label(float(confidence[row, col])),
            "complete": bool(math.isclose(float(denominator[row, col]), 1.0, abs_tol=1e-6)),
            "available_weight_pct": round(float(denominator[row, col]) * 100, 1),
            "area_ha": round(area_ha, 4),
            "raw": {
                "official_structural_1_10": round(float(official_raw[row, col]), 2) if official_valid[row, col] else None,
                "surface_temperature_c": round(float(lst_raw[row, col]), 2) if np.isfinite(lst_raw[row, col]) else None,
                "ndmi": round(float(ndmi_raw[row, col]), 4) if np.isfinite(ndmi_raw[row, col]) else None,
                "fuel_potential_0_1": round(float(fuel[row, col]) / 100, 2) if np.isfinite(fuel[row, col]) else None,
                "cover_class": COVER_LABELS.get(int(cover_code[row, col])),
                "territorial_concurrence_0_1": round(float(concurrence[row, col]) / 100, 3) if np.isfinite(concurrence[row, col]) else None,
                "slope_deg": round(float(slope[row, col]), 1) if np.isfinite(slope[row, col]) else None,
                "aspect_deg": round(aspect_value, 1) if aspect_value is not None else None,
                "aspect_cardinal": cardinal,
                "aspect_exposure": exposure,
                "wind_speed_kmh": round(float(wind_value) * 3.6, 1) if wind_value is not None else None,
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
    very_high_area = area_by_category["molt alt"] + area_by_category["extrem"]

    variable_status = {
        "official_structural_2024": {
            "value": f"mediana {float(np.nanmedian(official_raw[official_valid & study_mask])):.1f}/10",
            "source": "Generalitat · perill bàsic 2024",
        },
        "surface_temperature": {
            "value": f"mediana {float(np.nanmedian(lst_raw[study_mask & np.isfinite(lst_raw)])):.1f} °C",
            "source": "USGS Landsat 8/9 C2 L2 · composició estival",
        },
        "vegetation_dryness_ndmi": {
            "value": f"mediana {float(np.nanmedian(ndmi_raw[study_mask & np.isfinite(ndmi_raw)])):.3f}",
            "source": "Copernicus Sentinel-2 L2A",
        },
        "vegetation_type_fuel_potential": {
            "value": f"potencial mitjà {float(np.nanmean(fuel[study_mask & np.isfinite(fuel)])) / 100:.2f}/1",
            "source": "ICGC · cobertes del sòl 2024",
        },
        "territorial_concurrence": {
            "value": f"mediana {float(np.nanmedian(concurrence[study_mask & np.isfinite(concurrence)])) / 100:.3f}/1",
            "source": "EcoRadar · fonts territorials oficials documentades",
        },
        "wind": {
            "value": f"{float(wind_value) * 3.6:.1f} km/h" if wind_value is not None else "dada no disponible",
            "source": "Meteocat XEMA · Y4 Alinyà",
        },
        "relative_humidity_inverse": {
            "value": f"{float(humidity_value):.0f} %" if humidity_value is not None else "dada no disponible",
            "source": "Meteocat XEMA · Y4 Alinyà",
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
            weight_pct=round(float(weights[key]) * 100),
            quality=(
                "no disponible"
                if reference is None
                else "provisional"
                if key in ("wind", "relative_humidity_inverse") and validation_code != "V"
                else "verificada"
            ),
            update_status=(
                "dada no disponible"
                if reference is None
                else "actualitzada avui"
                if reference[:10] == now.date().isoformat()
                else "última dada vàlida"
            ),
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
            "very_high_or_extreme_area_pct": round(
                100 * very_high_area / total_area, 1
            ),
            "dominant_variables": general_dominant,
            "dominant_labels": [LABELS[key] for key in general_dominant],
            "latest_update_utc": latest_update,
            "confidence_pct": round(global_confidence, 1),
            "confidence": _confidence_label(global_confidence),
        },
        "weather": weather,
        "variables_today": variable_status,
        "normalization": {
            "method": "P10-P90 within Alinyà for static rasters and P5-P95 over the 35-day XEMA history; missing variables are reweighted, never set to zero.",
            "ndmi_p10_p90": [round(ndmi_p10, 4), round(ndmi_p90, 4)],
            "lst_c_p10_p90": [round(temp_p10, 2), round(temp_p90, 2)],
        },
        "weights": weights,
        "methodology": "docs/data_sources/fire/current-wildfire-danger-alinya.md",
        "sources": {
            "meteocat": _read_json(METEO_METADATA),
            "sentinel2": sentinel_metadata,
            "landsat": landsat_metadata,
            "territorial": concurrence_metadata,
        },
        "limitations": [
            "Índex EcoRadar derivat; no és una alerta oficial ni substitueix el Pla Alfa o el mapa diari oficial.",
            "La meteorologia XEMA Y4 és una observació puntual i no representa cada vessant d'un àmbit de 5.464 ha.",
            "Una variable XEMA absent es marca com a no disponible i el pes es renormalitza; no es converteix en zero.",
            "La temperatura Landsat és una composició estival i l'NDMI és un proxy relatiu, no humitat fina del combustible.",
            "La coberta és un proxy de combustible que requereix validació de càrrega i estructura vertical al camp.",
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
                    "surface_temperature": str(LST.relative_to(ROOT)),
                    "ndmi": str(NDMI.relative_to(ROOT)),
                    "landcover": str(LANDCOVER.relative_to(ROOT)),
                    "concurrence": str(CONCURRENCE.relative_to(ROOT)),
                    "meteorology": str(METEO.relative_to(ROOT)),
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
