"""Build Alinyà's public daily-reading registry from verified local outputs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
XEMA = PROJECT / "raw" / "meteocat_xema" / "Y4_observations.csv"
XEMA_METADATA = PROJECT / "raw" / "meteocat_xema" / "Y4_metadata.json"
WIND_XEMA = PROJECT / "raw" / "meteocat_xema" / "CJ_wind_observations.csv"
WIND_XEMA_METADATA = PROJECT / "raw" / "meteocat_xema" / "CJ_wind_metadata.json"
FIRE_CONFIG = ROOT / "config" / "current_fire_danger.json"
OUTPUT = PROJECT / "indicators" / "daily_readings.json"
METADATA = PROJECT / "metadata" / "daily_readings.json"
LOCAL_TZ = ZoneInfo("Europe/Madrid")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _as_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _run_checked_at() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        parsed = _as_utc(configured)
        if parsed is None:
            raise ValueError("ECORADAR_CHECKED_AT_UTC is not a valid ISO-8601 instant")
        return parsed
    return datetime.now(timezone.utc)


def _public_status(data_at: datetime | None, checked_at: datetime) -> tuple[str, str]:
    if data_at is None:
        return "unavailable", "dada no disponible"
    if data_at.astimezone(LOCAL_TZ).date() == checked_at.astimezone(LOCAL_TZ).date():
        return "updated_today", "actualitzada avui"
    return "last_available", "última dada disponible"


def _entry(
    *,
    label: str,
    value: str,
    source: str,
    data_at: datetime | None,
    checked_at: datetime,
    quality: str,
    note: str,
    value_numeric: float | None = None,
    unit: str | None = None,
    temporal_kind: str = "observation",
    period_start_utc: str | None = None,
    period_end_utc: str | None = None,
    status_override: tuple[str, str] | None = None,
) -> dict:
    status_code, status = status_override or _public_status(data_at, checked_at)
    return {
        "label": label,
        "value": value,
        "value_numeric": value_numeric,
        "unit": unit,
        "source": source,
        "data_at_utc": data_at.isoformat().replace("+00:00", "Z") if data_at else None,
        "temporal_kind": temporal_kind,
        "period_start_utc": period_start_utc,
        "period_end_utc": period_end_utc,
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "status_code": status_code,
        "status": status,
        "quality": quality,
        "note": note,
    }


def _missing(label: str, source: str, checked_at: datetime, note: str) -> dict:
    return _entry(
        label=label,
        value="dada no disponible",
        source=source,
        data_at=None,
        checked_at=checked_at,
        quality="no disponible amb les fonts verificades",
        note=note,
    )


def _source_check(
    *,
    label: str,
    organization: str,
    status: str,
    checked_at: datetime,
    data_at: datetime | None,
    service: str,
    note: str,
) -> dict:
    return {
        "label": label,
        "organization": organization,
        "status": status,
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "data_at_utc": data_at.isoformat().replace("+00:00", "Z") if data_at else None,
        "service": service,
        "note": note,
    }


def _checked_during_run(generated_at: datetime | None, checked_at: datetime) -> bool:
    return bool(generated_at and abs((generated_at - checked_at).total_seconds()) <= 12 * 3600)


def _xema_inputs(config: dict) -> tuple[pd.DataFrame, dict[str, dict]]:
    frames = [pd.read_csv(XEMA, dtype={"codi_variable": str, "codi_estat": str})]
    if WIND_XEMA.is_file():
        frames.append(pd.read_csv(WIND_XEMA, dtype={"codi_variable": str, "codi_estat": str}))
    frame = pd.concat(frames, ignore_index=True)
    frame["data_lectura"] = pd.to_datetime(frame["data_lectura"], utc=True)
    frame["valor_lectura"] = pd.to_numeric(frame["valor_lectura"], errors="coerce")
    frame["codi_estat"] = frame["codi_estat"].fillna("")
    frame = frame.dropna(subset=["valor_lectura", "data_lectura"]).sort_values("data_lectura")
    latest: dict[str, dict] = {}
    for name, code in config["xema"]["variables"].items():
        rows = frame[frame["codi_variable"] == str(code)]
        if rows.empty:
            continue
        row = rows.iloc[-1]
        latest[name] = {
            "value": float(row["valor_lectura"]),
            "data_at": row["data_lectura"].to_pydatetime(),
            "validation": str(row["codi_estat"]),
        }
    return frame, latest


def _quality(*records: dict) -> str:
    states = {record.get("validation", "") for record in records}
    return "validada" if states == {"V"} else "provisional XEMA"


def _apparent_temperature(temperature_c: float, humidity_pct: float, wind_ms: float) -> float:
    vapour = humidity_pct / 100 * 6.105 * math.exp(17.27 * temperature_c / (237.7 + temperature_c))
    return temperature_c + 0.33 * vapour - 0.70 * wind_ms - 4.0


def calculate() -> dict:
    checked_at = _run_checked_at()
    fire_config = _read_json(FIRE_CONFIG)
    frame, latest = _xema_inputs(fire_config)
    current_fire = _read_json(PROJECT / "indicators" / "current_fire_danger.json")
    station_source = "Meteocat XEMA · estació Y4 Alinyà"
    readings: dict[str, dict] = {}

    temperature = latest.get("air_temperature_c")
    humidity = latest.get("relative_humidity_pct")
    wind = latest.get("wind_speed_ms")
    wind_gust = latest.get("wind_gust_ms")
    if temperature:
        readings["air_temperature"] = _entry(
            label="Temperatura de l'aire",
            value=f"{temperature['value']:.1f} °C".replace(".", ","),
            value_numeric=round(temperature["value"], 1),
            unit="°C",
            source=station_source,
            data_at=temperature["data_at"],
            checked_at=checked_at,
            quality=_quality(temperature),
            note="Observació puntual de l'estació Y4; no representa cada vessant de la Muntanya d'Alinyà.",
        )
    else:
        readings["air_temperature"] = _missing(
            "Temperatura de l'aire", station_source, checked_at, "L'estació Y4 no ha retornat la variable 32."
        )
    if wind_gust:
        gust_kmh = wind_gust["value"] * 3.6
        readings["wind_gust"] = _entry(
            label="Ratxa de vent",
            value=f"{gust_kmh:.1f} km/h".replace(".", ","),
            value_numeric=round(gust_kmh, 1),
            unit="km/h",
            source="Meteocat XEMA · estació CJ Organyà · 9,2 km de Y4",
            data_at=wind_gust["data_at"],
            checked_at=checked_at,
            quality=_quality(wind_gust),
            note="Ratxa puntual de l'estació oficial de context; no representa el vent de cada vall o carena d'Alinyà.",
        )
    else:
        readings["wind_gust"] = _missing(
            "Ratxa de vent", "Meteocat XEMA · estació CJ Organyà", checked_at,
            "La font no ha retornat una ratxa vàlida; no s'interpreta com absència de ratxes.",
        )
    if humidity:
        readings["relative_humidity"] = _entry(
            label="Humitat relativa",
            value=f"{humidity['value']:.0f} %",
            value_numeric=round(humidity["value"], 1),
            unit="%",
            source=station_source,
            data_at=humidity["data_at"],
            checked_at=checked_at,
            quality=_quality(humidity),
            note="Observació puntual; no és una malla territorial d'humitat.",
        )
    else:
        readings["relative_humidity"] = _missing(
            "Humitat relativa", station_source, checked_at, "L'estació Y4 no ha retornat la variable 33."
        )
    if wind:
        wind_kmh = wind["value"] * 3.6
        readings["wind"] = _entry(
            label="Vent",
            value=f"{wind_kmh:.1f} km/h".replace(".", ","),
            value_numeric=round(wind_kmh, 1),
            unit="km/h",
            source="Meteocat XEMA · estació CJ Organyà · 9,2 km de Y4",
            data_at=wind["data_at"],
            checked_at=checked_at,
            quality=_quality(wind),
            note="Context puntual de l'estació més propera amb vent; no és vent mesurat dins Alinyà ni un camp per a valls i carenes.",
        )
    else:
        readings["wind"] = _missing(
            "Vent",
            "Meteocat XEMA · estació CJ Organyà",
            checked_at,
            "L'extracte públic actual de l'estació Y4 no conté la variable 30; no s'interpreta com vent nul.",
        )

    precipitation_code = str(fire_config["xema"]["variables"]["precipitation_mm"])
    precipitation_rows = frame[frame["codi_variable"] == precipitation_code].copy()
    if not precipitation_rows.empty:
        precipitation_rows["local_date"] = precipitation_rows["data_lectura"].dt.tz_convert(LOCAL_TZ).dt.date
        latest_day = precipitation_rows["local_date"].iloc[-1]
        day_rows = precipitation_rows[precipitation_rows["local_date"] == latest_day]
        precipitation = float(day_rows["valor_lectura"].sum())
        last_row = day_rows.iloc[-1]
        readings["precipitation"] = _entry(
            label="Precipitació",
            value=f"{precipitation:.1f} mm".replace(".", ","),
            value_numeric=round(precipitation, 1),
            unit="mm",
            source=station_source,
            data_at=last_row["data_lectura"].to_pydatetime(),
            checked_at=checked_at,
            quality=_quality({"validation": str(last_row["codi_estat"])}),
            note=f"Acumulació dels períodes XEMA disponibles del {latest_day.isoformat()}.",
        )
    else:
        readings["precipitation"] = _missing(
            "Precipitació", station_source, checked_at, "L'estació Y4 no ha retornat la variable 35."
        )

    accumulated = current_fire.get("meteorology_context", {}).get("precipitation_accumulated", {})
    accumulated_at = _as_utc(accumulated.get("data_at_utc"))
    accumulated_specs = (
        ("precipitation_7d", "Precipitació últims 7 dies", "last_7_days_mm", "mm"),
        ("precipitation_30d", "Precipitació últims 30 dies", "last_30_days_mm", "mm"),
        ("days_without_significant_rain", "Dies sense pluja significativa", "days_without_significant_rain", "dies"),
    )
    for key, label, field, unit in accumulated_specs:
        value = accumulated.get(field)
        if value is None or accumulated_at is None:
            readings[key] = _missing(label, station_source, checked_at, "Cobertura temporal insuficient a la sèrie XEMA; no s'emplena amb zeros.")
            continue
        readings[key] = _entry(
            label=label,
            value=f"{float(value):.1f} {unit}".replace(".0 dies", " dies").replace(".", ","),
            value_numeric=round(float(value), 1),
            unit=unit,
            source=station_source,
            data_at=accumulated_at,
            checked_at=checked_at,
            quality="derivada de períodes XEMA amb cobertura ≥80 %",
            note=accumulated.get("method", "Acumulació observada XEMA.") + (" Llindar de pluja significativa: 1,0 mm/dia." if field == "days_without_significant_rain" else ""),
        )

    pla_alfa = current_fire.get("pla_alfa", {})
    pla_level = pla_alfa.get("level")
    pla_date = _as_utc(pla_alfa.get("data_at_utc"))
    readings["pla_alfa"] = (
        _entry(
            label="Pla Alfa",
            value=f"Nivell {int(pla_level)} · {pla_alfa.get('label', '—')}",
            value_numeric=float(pla_level),
            unit="nivell oficial 0–4",
            source="Cos d'Agents Rurals / Generalitat de Catalunya",
            data_at=pla_date,
            checked_at=checked_at,
            quality="dada oficial municipal",
            note="Nivell operatiu oficial de Fígols i Alinyà; no és un càlcul EcoRadar ni entra numèricament a l'índex 0–100.",
        )
        if pla_level is not None and pla_date
        else _missing("Pla Alfa", "Cos d'Agents Rurals / Generalitat de Catalunya", checked_at, "No hi ha una última dada oficial local disponible.")
    )

    landsat = _read_json(PROJECT / "metadata" / "landsat_connector.json")
    surface_selection = _read_json(PROJECT / "metadata" / "current_surface_temperature.json")
    selected_surface = surface_selection.get("selected", {})
    satellite = _read_json(PROJECT / "indicators" / "teledeteccio_satellite_layers.json")
    lst_metric = satellite.get("surface_temperature", {}).get("metrics_c", {})
    lst_value = lst_metric.get("median")
    lst_temporal_kind = selected_surface.get("temporal_kind", "single_observation")
    lst_date = _as_utc(selected_surface.get("acquired_at_utc")) if lst_temporal_kind == "single_observation" else None
    lst_source = selected_surface.get("source", "Temperatura superficial detallada")
    readings["surface_temperature"] = (
        _entry(
            label="Temperatura superficial",
            value=f"{float(lst_value):.1f} °C".replace(".", ","),
            value_numeric=round(float(lst_value), 1),
            unit="°C",
            source=lst_source,
            data_at=lst_date,
            checked_at=checked_at,
            quality=selected_surface.get("quality", "control de qualitat satel·litari aplicat"),
            note=(
                "Observació detallada QA-vàlida; no és temperatura de l'aire."
                if lst_temporal_kind == "single_observation"
                else "Compost multitemporal de 26 escenes: descriu el patró tèrmic del període i no una observació del darrer dia component."
            ),
            temporal_kind=lst_temporal_kind,
            period_start_utc=selected_surface.get("period_start_utc"),
            period_end_utc=selected_surface.get("period_end_utc"),
            status_override=("period_context", "context del període") if lst_temporal_kind == "multitemporal_composite" else None,
        )
        if lst_value is not None and (lst_date or selected_surface.get("period_end_utc"))
        else _missing(
            "Temperatura superficial",
            "USGS Landsat / NASA ECOSTRESS",
            checked_at,
            "No hi ha cap composició local vàlida processada.",
        )
    )

    sentinel = _read_json(PROJECT / "indicators" / "teledeteccio_sentinel2.json")
    sentinel_date = _as_utc(sentinel.get("acquired_at_utc"))
    for key, label in (("ndmi", "NDMI"), ("ndvi", "NDVI"), ("albedo", "Albedo")):
        metric = sentinel.get("metrics", {}).get(key, {})
        value = metric.get("median")
        readings[key] = (
            _entry(
                label=label,
                value=f"{float(value):.3f}".replace(".", ","),
                value_numeric=round(float(value), 3),
                unit="índex",
                source="Copernicus Sentinel-2 MSI L2A",
                data_at=sentinel_date,
                checked_at=checked_at,
                quality="màscara SCL aplicada",
                note="Mediana de l'àmbit de l'última escena local vàlida.",
            )
            if value is not None and sentinel_date
            else _missing(label, "Copernicus Sentinel-2 MSI L2A", checked_at, "No hi ha cap escena local vàlida.")
        )

    context = _read_json(PROJECT / "indicators" / "contextual_environment.json")
    pm25 = context.get("pm25", {})
    pm25_date = _as_utc(pm25.get("reference_time_utc"))
    pm25_value = pm25.get("value_ug_m3")
    readings["air_quality"] = (
        _entry(
            label="Qualitat de l'aire",
            value=f"PM2,5 · {float(pm25_value):.2f} µg/m³".replace(".", ","),
            value_numeric=round(float(pm25_value), 2),
            unit="µg/m³ PM2,5",
            source="Copernicus CAMS European air-quality forecast",
            data_at=pm25_date,
            checked_at=checked_at,
            quality="model 0,1° (~10 km)",
            note="Context modelitzat supramunicipal; no és una estació local ni una concentració de sender o nucli.",
        )
        if pm25_value is not None and pm25_date
        else _missing("Qualitat de l'aire", "Copernicus CAMS", checked_at, "El servei no ha retornat PM2,5 vàlid.")
    )

    if temperature and humidity and wind:
        apparent = _apparent_temperature(temperature["value"], humidity["value"], wind["value"])
        readings["thermal_comfort"] = _entry(
            label="Confort tèrmic contextual",
            value=f"{apparent:.1f} °C aparents".replace(".", ","),
            value_numeric=round(apparent, 1),
            unit="°C aparents",
            source="Derivat EcoRadar · temperatura aparent de Steadman amb XEMA",
            data_at=min(temperature["data_at"], humidity["data_at"], wind["data_at"]),
            checked_at=checked_at,
            quality=_quality(temperature, humidity, wind),
            note="Estimació puntual; no és UTCI, WBGT, exposició individual ni risc clínic.",
        )
    else:
        readings["thermal_comfort"] = _missing(
            "Confort tèrmic contextual",
            "Derivat de temperatura, humitat i vent XEMA",
            checked_at,
            "Falta almenys una de les tres entrades; no es calcula un valor parcial.",
        )

    shade = _read_json(PROJECT / "indicators" / "daily_shade.json")
    shade_value = shade.get("value", {}).get("shade_pct")
    shade_date = _as_utc(shade.get("data_at_utc"))
    readings["terrain_shade"] = (
        _entry(
            label="Ombra topogràfica diària · 15 h",
            value=f"{float(shade_value):.1f} %".replace(".", ","),
            value_numeric=round(float(shade_value), 1),
            unit="%",
            source="ICGC MDT 5 m + posició solar calculada",
            data_at=shade_date,
            checked_at=checked_at,
            quality="derivada verificada",
            note="Considera pendent i orientació del relleu; no incorpora arbres, edificis ni horitzó llunyà.",
        )
        if shade_value is not None and shade_date
        else _missing("Ombra topogràfica diària · 15 h", "ICGC MDT 5 m", checked_at, "No hi ha càlcul diari vàlid.")
    )

    fire_summary = current_fire.get("summary", {})
    fire_date = _as_utc(fire_summary.get("latest_update_utc"))
    fire_value = fire_summary.get("mean_index_0_100")
    readings["current_fire_danger"] = (
        _entry(
            label="Perill actual d'incendi",
            value=f"{float(fire_value):.1f}/100 · {fire_summary.get('predominant_category', '—')}".replace(".", ","),
            value_numeric=round(float(fire_value), 1),
            unit="índex 0–100",
            source="Índex EcoRadar derivat · fonts detallades a la lectura",
            data_at=fire_date,
            checked_at=checked_at,
            quality=f"confiança del producte {fire_summary.get('confidence', 'no disponible')} · {fire_summary.get('confidence_pct', '—')} %",
            note="No és una alerta oficial ni substitueix el Pla Alfa.",
        )
        if fire_value is not None and fire_date
        else _missing("Perill actual d'incendi", "Índex EcoRadar derivat", checked_at, "No hi ha càlcul vàlid.")
    )

    counts = {name: 0 for name in ("updated_today", "last_available", "period_context", "unavailable")}
    for reading in readings.values():
        counts[reading["status_code"]] += 1

    xema_data_at = max((item["data_at"] for item in latest.values()), default=None)
    xema_generated = _as_utc(_read_json(XEMA_METADATA).get("generated_at_utc"))
    wind_xema_metadata = _read_json(WIND_XEMA_METADATA)
    wind_xema_generated = _as_utc(wind_xema_metadata.get("latest_catalog_check_utc") or wind_xema_metadata.get("generated_at_utc"))
    wind_data_at = wind.get("data_at") if wind else None
    cams_generated = _as_utc(context.get("generated_at_utc"))
    landsat_generated = _as_utc(landsat.get("latest_catalog_check_utc") or landsat.get("generated_at_utc"))
    ecostress = _read_json(PROJECT / "metadata" / "ecostress_connector.json")
    ecostress_generated = _as_utc(ecostress.get("latest_catalog_check_utc") or ecostress.get("generated_at_utc"))
    sentinel_connector = _read_json(PROJECT / "metadata" / "sentinel2_cdse_connector.json")
    sentinel_generated = _as_utc(
        sentinel_connector.get("latest_catalog_check_utc")
        or sentinel_connector.get("generated_at_utc")
    )
    sentinel_has_credentials = bool(
        os.environ.get("COPERNICUS_CLIENT_ID")
        and os.environ.get("COPERNICUS_CLIENT_SECRET")
    )
    forestdrought = _read_json(PROJECT / "metadata" / "creaf_forestdrought_connector.json")
    forestdrought_generated = _as_utc(
        forestdrought.get("latest_catalog_check_utc") or forestdrought.get("generated_at_utc")
    )
    forestdrought_date = _as_utc(forestdrought.get("data_at_utc"))
    pla_checked = _as_utc(pla_alfa.get("checked_at_utc"))
    source_checks = {
        "meteocat_xema": _source_check(
            label="Meteocat XEMA · estació Y4",
            organization="Servei Meteorològic de Catalunya / Generalitat de Catalunya",
            status="verified" if xema_data_at and _checked_during_run(xema_generated, checked_at) else "service_unavailable",
            checked_at=checked_at,
            data_at=xema_data_at,
            service="Socrata API · nzvn-apee",
            note="Consulta oficial; les variables absents es declaren i no es converteixen en zero.",
        ),
        "meteocat_xema_wind": _source_check(
            label="Meteocat XEMA · vent CJ Organyà",
            organization="Servei Meteorològic de Catalunya / Generalitat de Catalunya",
            status="verified" if wind_data_at and _checked_during_run(wind_xema_generated, checked_at) else "service_unavailable",
            checked_at=checked_at,
            data_at=wind_data_at,
            service="Socrata API · nzvn-apee",
            note="Estació oficial més propera amb vent, a 9,2 km de Y4; context puntual, no mesura dins Alinyà.",
        ),
        "cams_pm25": _source_check(
            label="CAMS · PM2,5 europeu",
            organization="Copernicus Atmosphere Monitoring Service / ECMWF",
            status="verified" if pm25_date and _checked_during_run(cams_generated, checked_at) else "service_unavailable",
            checked_at=checked_at,
            data_at=pm25_date,
            service="WMS 1.3.0 GetFeatureInfo",
            note="Context modelitzat a aproximadament 10 km; no és una estació local.",
        ),
        "landsat_surface_temperature": _source_check(
            label="Landsat 8/9 Collection 2 Level-2 ST",
            organization="United States Geological Survey",
            status=landsat.get("connector_status", "verified") if _checked_during_run(landsat_generated, checked_at) else "service_unavailable",
            checked_at=checked_at,
            data_at=lst_date,
            service=landsat.get("service_type", "STAC + COG"),
            note="La consulta és diària; la composició només canvia amb una escena QA-vàlida nova.",
        ),
        "ecostress_surface_temperature": _source_check(
            label="ECOSTRESS L2T V3 · temperatura superficial",
            organization="NASA/JPL ECOSTRESS / NASA LP DAAC",
            status=(
                ecostress.get("connector_status", "requires_credentials")
                if _checked_during_run(ecostress_generated, checked_at)
                else "requires_credentials" if not os.environ.get("EARTHDATA_TOKEN")
                else "service_unavailable"
            ),
            checked_at=checked_at,
            data_at=_as_utc(ecostress.get("acquired_at_utc")),
            service="NASA CMR Search + Earthdata protected COG",
            note="La consulta de catàleg és diària; només una escena local nova i QA-vàlida pot substituir Landsat.",
        ),
        "creaf_forestdrought": _source_check(
            label="ForestDrought · sequera forestal i potencial de foc",
            organization="CREAF / Ecosystem Modelling Facility",
            status=(
                forestdrought.get("connector_status", "service_unavailable")
                if _checked_during_run(forestdrought_generated, checked_at)
                else "service_unavailable"
            ),
            checked_at=checked_at,
            data_at=forestdrought_date,
            service="repositori HTTPS GeoPackage daily_modelled_forests",
            note="Model forestal de 500 × 500 m; la data del model es conserva separada de la comprovació diària.",
        ),
        "terrain_shade": _source_check(
            label="Ombra topogràfica diària · 15 h",
            organization="EcoRadar sobre ICGC MDT 5 m",
            status="verified" if shade_value is not None and shade_date else "service_unavailable",
            checked_at=checked_at,
            data_at=shade_date,
            service="Analysis Engine EcoRadar",
            note="Derivat diari de relleu i posició solar; no incorpora arbres, edificis ni horitzó llunyà.",
        ),
        "sentinel2_indices": _source_check(
            label="Sentinel-2 L2A · NDVI, NDMI i albedo",
            organization="Copernicus / ESA",
            status=(
                sentinel_connector.get("connector_status", "verified")
                if sentinel_date and _checked_during_run(sentinel_generated, checked_at)
                else "requires_credentials" if not sentinel_has_credentials
                else "service_unavailable"
            ),
            checked_at=checked_at,
            data_at=sentinel_date,
            service="CDSE STAC + Process API",
            note="Requereix credencials CDSE per actualitzar l'escena analítica.",
        ),
        "current_fire_danger": _source_check(
            label="Perill actual d'incendi · índex EcoRadar",
            organization="EcoRadar sobre fonts oficials documentades",
            status="verified" if fire_value is not None and fire_date else "service_unavailable",
            checked_at=checked_at,
            data_at=fire_date,
            service="Analysis Engine EcoRadar",
            note="Indicador derivat; no és una alerta oficial ni substitueix el Pla Alfa.",
        ),
        "pla_alfa": _source_check(
            label="Pla Alfa · Fígols i Alinyà",
            organization="Cos d'Agents Rurals / Generalitat de Catalunya",
            status="verified" if pla_level is not None and pla_date and _checked_during_run(pla_checked, checked_at) else "service_unavailable",
            checked_at=checked_at,
            data_at=pla_date,
            service="ArcGIS FeatureServer oficial · vista municipal Avui",
            note="Nivell oficial 0–4; es mostra en paral·lel i no es converteix en puntuació EcoRadar.",
        ),
    }
    payload = {
        "schema_version": "1.0",
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "station": {"code": "Y4", "name": "Alinyà", "wind_context_station": {"code": "CJ", "name": "Organyà", "distance_km": 9.2}},
        "status_counts": counts,
        "source_checks": source_checks,
        "readings": readings,
        "structural_layers_not_recalculated_daily": [
            "relleu",
            "pendent",
            "orientació",
            "cobertes del sòl",
            "hàbitats HIC",
            "xarxa hidrogràfica",
            "connectivitat ecològica",
            "incendis històrics",
            "perill estructural d'incendi",
        ],
        "methodology": "docs/data_sources/alinya_daily_readings.md",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = calculate()
    print(json.dumps({"checked_at_utc": result["checked_at_utc"], "status_counts": result["status_counts"]}, ensure_ascii=False, indent=2))
