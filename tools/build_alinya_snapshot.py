#!/usr/bin/env python3
"""Build and stamp one versioned state shared by all Alinyà products.

The script does not calculate ecological scores. It records the inputs already
produced by the connectors/analysis steps, creates a deterministic snapshot id,
and stamps that id into every public product consumed by the viewer or reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
REGISTRY = PROJECT / "metadata" / "reading_registry.json"
SNAPSHOT_HISTORY = PROJECT / "history" / "snapshots"


def _read(relative: str) -> dict[str, Any]:
    path = PROJECT / relative
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("product", "stac", "api", "service", "process_api", "official_page"):
            if value.get(key):
                return str(value[key])
        for item in value.values():
            if isinstance(item, str) and item.startswith("https://"):
                return item
    return None


def _daily_record(key: str, item: dict[str, Any]) -> dict[str, Any]:
    support = {
        "air_temperature": ("station_point", None, "XEMA Y4 Alinyà"),
        "relative_humidity": ("station_point", None, "XEMA Y4 Alinyà"),
        "precipitation": ("station_point", None, "XEMA Y4 Alinyà"),
        "precipitation_7d": ("station_time_series", None, "XEMA Y4 Alinyà"),
        "precipitation_30d": ("station_time_series", None, "XEMA Y4 Alinyà"),
        "days_without_significant_rain": ("station_time_series", None, "XEMA Y4 Alinyà"),
        "wind": ("station_point_context", None, "XEMA CJ Organyà"),
        "wind_gust": ("station_point_context", None, "XEMA CJ Organyà"),
        "thermal_comfort": ("station_point_derived", None, "XEMA Y4/CJ"),
        "air_quality": ("model_grid_context", 10_000, "CAMS 0.1 degree"),
        "terrain_shade": ("study_area_raster", 5, "Alinyà polygon"),
        "surface_temperature": ("study_area_raster", 30, "Alinyà polygon"),
        "ndvi": ("study_area_raster", 10, "Alinyà polygon"),
        "ndmi": ("study_area_raster", 10, "Alinyà polygon"),
        "albedo": ("study_area_raster", 10, "Alinyà polygon"),
        "pla_alfa": ("municipality", None, "Fígols i Alinyà"),
        "current_fire_danger": ("study_area_grid", 100, "Alinyà polygon"),
    }.get(key, ("documented_source_support", None, "Alinyà"))
    source_url = {
        "air_temperature": "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json",
        "relative_humidity": "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json",
        "precipitation": "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json",
        "precipitation_7d": "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json",
        "precipitation_30d": "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json",
        "days_without_significant_rain": "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json",
        "wind": "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json",
        "wind_gust": "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json",
        "thermal_comfort": "docs/data_sources/alinya_daily_readings.md",
        "air_quality": "https://ads.atmosphere.copernicus.eu/",
        "terrain_shade": "https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Geoinformacio-cartografica/Altimetria",
        "surface_temperature": "https://landsatlook.usgs.gov/stac-server/",
        "ndvi": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
        "ndmi": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
        "albedo": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
        "pla_alfa": "https://interior.gencat.cat/ca/arees_dactuacio/agents-rurals/pla-alfa/",
        "current_fire_danger": "docs/data_sources/fire/current-wildfire-danger-alinya.md",
    }.get(key)
    update_frequency = {
        "air_temperature": "daily check; source subdaily", "relative_humidity": "daily check; source subdaily",
        "precipitation": "daily check; source subdaily", "precipitation_7d": "daily",
        "precipitation_30d": "daily", "days_without_significant_rain": "daily",
        "wind": "daily check; source subdaily", "wind_gust": "daily check; source subdaily",
        "thermal_comfort": "daily", "air_quality": "daily", "terrain_shade": "daily",
        "surface_temperature": "per new QA-valid scene", "ndvi": "per new QA-valid scene",
        "ndmi": "per new QA-valid scene", "albedo": "per new QA-valid scene",
        "pla_alfa": "daily", "current_fire_danger": "daily",
    }.get(key, "when source changes")
    return {
        "reading_id": key,
        "label": item.get("label", key),
        "measurement_kind": "synthetic_score" if key == "current_fire_danger" else "direct_or_derived_reading",
        "value": item.get("value"),
        "value_numeric": item.get("value_numeric"),
        "unit": item.get("unit"),
        "source": item.get("source"),
        "source_url": source_url,
        "data_at_utc": item.get("data_at_utc"),
        "temporal_kind": item.get("temporal_kind", "observation"),
        "period_start_utc": item.get("period_start_utc"),
        "period_end_utc": item.get("period_end_utc"),
        "checked_at_utc": item.get("checked_at_utc"),
        "resolution_m": support[1],
        "coverage": None,
        "spatial_support": support[0],
        "support_id": support[2],
        "grid_id": support[2] if support[1] else None,
        "mask_id": "study_area" if "study_area" in support[0] else None,
        "qa": item.get("quality"),
        "quality_verified": item.get("status_code") != "unavailable",
        "coverage_verified": support[0] in {"station_point", "station_point_context", "station_time_series", "municipality"},
        "validity": item.get("status"),
        "update_frequency": update_frequency,
        "compatibility": "Use only when period, support, grid and mask are compatible with the paired reading.",
        "note": item.get("note"),
    }


def _build_records() -> tuple[dict[str, Any], dict[str, Any]]:
    daily = _read("indicators/daily_readings.json")
    sentinel = _read("indicators/teledeteccio_sentinel2.json")
    sentinel_connector = _read("metadata/sentinel2_cdse_automated_connector.json") or _read("metadata/sentinel2_cdse_connector.json")
    satellite = _read("indicators/teledeteccio_satellite_layers.json")
    fire = _read("indicators/current_fire_danger.json")
    refuges = _read("indicators/refugis_climatics_potencials.json")
    core = _read("indicators/ecoradar_core_indicators.json")
    completeness = _read("metadata/indicators_completeness_report.json")
    study = _read("metadata/study_area_metadata.json")

    readings = {key: _daily_record(key, item) for key, item in daily.get("readings", {}).items()}
    sentinel_url = _source_url(sentinel.get("official_urls")) or _source_url(sentinel_connector.get("official_urls"))
    sentinel_crs = sentinel.get("crs") or sentinel_connector.get("crs")
    sentinel_coverage = sentinel.get("valid_coverage_pct")
    for key in ("ndvi", "ndmi", "albedo"):
        if key not in readings:
            continue
        readings[key].update(
            source_url=sentinel_url,
            resolution_m=sentinel.get("output_resolution_m", 10),
            coverage={
                "valid_area_ha": sentinel.get("valid_area_ha"),
                "valid_pct": sentinel_coverage,
                "denominator": "rasterized study polygon",
            },
            coverage_verified=sentinel_coverage is not None,
            grid_id=f"sentinel2:{sentinel.get('source_scene')}:{sentinel_crs}:10m",
            mask_id=f"SCL_4_5_6:{sentinel.get('source_scene')}",
            support_id="Alinyà study polygon",
            quality_verified=True,
            qa=sentinel.get("methods", {}).get("quality_mask"),
        )

    temperature = readings.get("surface_temperature")
    surface = satellite.get("surface_temperature", {})
    if temperature:
        temperature.update(
            source_url="https://landsatlook.usgs.gov/stac-server/",
            temporal_kind=surface.get("temporal_kind", temperature.get("temporal_kind")),
            data_at_utc=surface.get("acquired_at_utc"),
            period_start_utc=surface.get("period_start_utc"),
            period_end_utc=surface.get("period_end_utc"),
            resolution_m=surface.get("resolution_m"),
            coverage={"valid_pct": surface.get("coverage_pct"), "denominator": "rasterized study polygon"},
            coverage_verified=surface.get("coverage_pct") is not None,
            grid_id=f"surface_temperature:{surface.get('source_key')}:{surface.get('resolution_m')}m",
            mask_id="source_QA_and_study_area",
            support_id="Alinyà study polygon",
            quality_verified=True,
            qa=surface.get("quality"),
        )

    fire_record = readings.get("current_fire_danger")
    if fire_record:
        fire_record.update(
            coverage={
                "valid_area_ha": fire.get("summary", {}).get("valid_area_ha"),
                "no_data_area_ha": fire.get("summary", {}).get("no_data_area_ha"),
                "valid_pct": fire.get("summary", {}).get("valid_coverage_pct"),
                "denominator": fire.get("summary", {}).get("coverage_denominator"),
            },
            coverage_verified=fire.get("summary", {}).get("valid_coverage_pct") is not None,
            grid_id="current_fire_danger:EPSG25831:100m",
            mask_id="study_area_and_available_components",
            support_id="Alinyà study polygon",
            quality_verified=True,
            source_url="docs/data_sources/fire/current-wildfire-danger-alinya.md",
        )

    readings["climate_refuges"] = {
        "reading_id": "climate_refuges",
        "label": refuges.get("name"),
        "measurement_kind": "derived_screening",
        "value": refuges.get("high_or_very_high_share_of_vegetated_valid_pct"),
        "value_numeric": refuges.get("high_or_very_high_share_of_vegetated_valid_pct"),
        "unit": "% of vegetated valid denominator",
        "source": "EcoRadar derivation from LST, NDMI and NDVI",
        "source_url": None,
        "data_at_utc": None,
        "temporal_kind": "mixed_period_derived",
        "period_start_utc": surface.get("period_start_utc"),
        "period_end_utc": max(
            value for value in (surface.get("period_end_utc"), sentinel.get("acquired_at_utc")) if value
        ),
        "resolution_m": sentinel.get("output_resolution_m", 10),
        "coverage": refuges.get("denominator"),
        "spatial_support": "vegetated_valid_pixels",
        "support_id": "Alinyà study polygon",
        "grid_id": "sentinel2_grid:10m",
        "mask_id": "valid_LST_NDMI_NDVI_and_NDVI>=0.30",
        "qa": "All formula inputs valid; hydrology is display context only.",
        "quality_verified": True,
        "coverage_verified": bool(refuges.get("denominator")),
        "validity": "period context",
        "compatibility": "Mixed-period screening; not a current microclimate observation.",
        "note": refuges.get("limitations"),
    }

    by_complete = {item.get("indicator"): item for item in completeness.get("indicators", [])}
    core_records = {}
    for item in core.get("indicators", []):
        code = item.get("code")
        core_records[code] = {
            **item,
            "measurement_kind": item.get("measurement_kind", "synthetic_score"),
            "completeness": by_complete.get(code, {}),
        }

    sources = {
        "study_area": {
            "source": "User-supplied Instamaps export",
            "source_file": Path(str(study.get("source_path") or "")).name or None,
            "source_layer": study.get("source_layer"),
            "authority": None,
            "license": None,
            "provenance_status": "pending_verification",
            "crs": study.get("final_crs"),
            "coverage_ha": study.get("surface_ha"),
            "use": "analysis boundary and denominator",
        },
        "habitats": _read("metadata/habitats_metadata.json"),
        "biodiversity": _read("metadata/biodiversitat_metadata.json"),
        "historical_fires": _read("metadata/incendis_metadata.json"),
        "land_cover": _read("metadata/cobertes_sol_metadata.json"),
        "hydrology": _read("metadata/hidrologia_metadata.json"),
        "connectivity": _read("metadata/connectivitat_metadata.json"),
        "terrain": _read("metadata/terrain_metadata.json"),
        "sentinel2": sentinel_connector,
        "landsat": _read("metadata/landsat_connector.json"),
        "sentinel2_catalog_check": _read("metadata/sentinel2_cdse_catalog_check.json"),
    }
    structural_specs = {
        "vegetation": ("Cobertura vegetal", satellite.get("vegetation_cover", {}).get("covered_pct"), "%", sources["land_cover"], "study_area_raster", satellite.get("vegetation_cover", {}).get("source")),
        "habitats": ("Hàbitats cartografiats", sources["habitats"].get("features_clipped"), "polígons", sources["habitats"], "study_area_vectors", sources["habitats"].get("source")),
        "biodiversity": ("Registres públics normalitzats", sources["biodiversity"].get("records_normalized_after_clip"), "registres", sources["biodiversity"], "study_area_points", "GBIF + iNaturalist"),
        "connectivity": ("Connectivitat cartografiada", None, None, sources["connectivity"], "study_area_vectors", sources["connectivity"].get("source")),
        "access": ("Accessibilitat cartografiada", None, None, _read("metadata/recreational_pressure_metadata.json"), "study_area_lines", "OpenStreetMap / Overpass"),
        "publicUse": ("Punts d'ús públic cartografiats", None, None, _read("metadata/recreational_pressure_metadata.json"), "study_area_points", "OpenStreetMap / Overpass"),
        "water": ("Aigua i funcionalitat hídrica cartografiada", None, None, sources["hydrology"], "study_area_vectors", sources["hydrology"].get("source")),
        "historical_fires": ("Perímetres històrics d'incendi", sources["historical_fires"].get("features_clipped"), "perímetres", sources["historical_fires"], "study_area_vectors", sources["historical_fires"].get("source")),
    }
    for key, (label, value, unit, metadata, spatial_support, source_name) in structural_specs.items():
        readings[key] = {
            "reading_id": key,
            "label": label,
            "measurement_kind": "inventory_or_structural_context",
            **({"value": value, "value_numeric": value, "unit": unit} if value is not None else {}),
            "source": source_name or label,
            "source_url": metadata.get("service_url") or metadata.get("url"),
            "data_at_utc": None,
            "temporal_kind": "inventory_version",
            "period_start_utc": None,
            "period_end_utc": None,
            "checked_at_utc": metadata.get("query_date"),
            "update_frequency": "when official source version changes",
            "resolution_m": metadata.get("resolution_m"),
            "coverage": {"study_area_ha": metadata.get("study_area_surface_ha") or study.get("surface_ha")},
            "spatial_support": spatial_support,
            "support_id": "Alinyà study polygon",
            "grid_id": None,
            "mask_id": "study_area",
            "qa": "Official source geometry clipped to the documented study area",
            "quality_verified": bool(metadata),
            "coverage_verified": bool(metadata),
            "validity": "structural or inventory context",
            "compatibility": "Do not describe as current; use with the documented source version and spatial support.",
            "note": metadata.get("limitations"),
        }
    return {"daily": daily, "readings": readings, "core": core_records}, sources


def _snapshot_seed(products: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    daily = products["daily"]
    return {
        "checked_at_utc": daily.get("checked_at_utc"),
        "readings": {
            key: {
                field: item.get(field)
                for field in ("value_numeric", "value", "data_at_utc", "period_start_utc", "period_end_utc", "source", "qa")
            }
            for key, item in sorted(products["readings"].items())
        },
        "core": {
            key: {
                field: item.get(field)
                for field in ("value_0_100", "direct_value", "status", "confidence", "sources_used", "sources_absent")
            }
            for key, item in sorted(products["core"].items())
        },
        "source_dates": {
            key: value.get("query_date") or value.get("generated_at_utc") or value.get("created_at")
            for key, value in sorted(sources.items()) if isinstance(value, dict)
        },
    }


def _stamp(path: Path, snapshot_id: str) -> None:
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["snapshot_id"] = snapshot_id
    if path.name == "current_fire_danger.json" and isinstance(payload.get("result"), dict):
        payload["result"]["snapshot_id"] = snapshot_id
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build() -> dict[str, Any]:
    products, sources = _build_records()
    seed = _snapshot_seed(products, sources)
    digest = hashlib.sha256(json.dumps(seed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    snapshot_id = f"alinya-{digest[:16]}"
    if REGISTRY.exists():
        previous = json.loads(REGISTRY.read_text(encoding="utf-8"))
        previous_id = previous.get("snapshot_id")
        if previous_id and previous_id != snapshot_id:
            SNAPSHOT_HISTORY.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REGISTRY, SNAPSHOT_HISTORY / f"{previous_id}.json")
    registry = {
        "schema_version": "1.0",
        "snapshot_id": snapshot_id,
        "generated_at_utc": _iso_now(),
        "checked_at_utc": products["daily"].get("checked_at_utc"),
        "scope": "Muntanya d'Alinyà",
        "contract": "Single metadata state consumed by readings, RADAR, completeness, viewer and report generator.",
        "readings": products["readings"],
        "core_indicators": products["core"],
        "sources": sources,
    }
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stamp_paths = [
        "indicators/daily_readings.json", "metadata/daily_readings.json",
        "indicators/current_fire_danger.json", "metadata/current_fire_danger.json",
        "indicators/ecoradar_core_indicators.json", "metadata/indicator_engine_report.json",
        "metadata/indicators_completeness_report.json", "metadata/data_availability_report.json",
        "metadata/connectors_status_report.json", "indicators/teledeteccio_sentinel2.json",
        "indicators/teledeteccio_satellite_layers.json", "indicators/refugis_climatics_potencials.json",
        "metadata/current_surface_temperature.json",
        "metadata/biodiversity_habitat_pilot_metadata.json",
        "metadata/biodiversity_ecology_metadata.json",
        "indicators/biodiversity_habitat_pilot.geojson",
        "indicators/biodiversity_ecological_elements.geojson",
        "indicators/biodiversity_ecological_situations.geojson",
        "indicators/biodiversity_knowledge_coverage.geojson",
    ]
    for relative in stamp_paths:
        _stamp(PROJECT / relative, snapshot_id)
    cells = PROJECT / "maps" / "incendis" / "current_fire_danger_cells.geojson"
    if cells.exists():
        payload = json.loads(cells.read_text(encoding="utf-8"))
        payload["snapshot_id"] = snapshot_id
        for feature in payload.get("features", []):
            feature.setdefault("properties", {})["snapshot_id"] = snapshot_id
        cells.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return registry


if __name__ == "__main__":
    payload = build()
    print(json.dumps({"snapshot_id": payload["snapshot_id"], "readings": len(payload["readings"]), "core_indicators": len(payload["core_indicators"])}, ensure_ascii=False, indent=2))
