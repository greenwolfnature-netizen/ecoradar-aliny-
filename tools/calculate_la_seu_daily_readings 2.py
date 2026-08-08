"""Build the public daily-reading registry from verified observations and outputs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
XEMA = PROJECT / "raw" / "meteocat_xema" / "CD_observations.csv"
CONFIG = ROOT / "config" / "current_fire_danger.json"
OUTPUT = PROJECT / "indicators" / "daily_readings.json"
METADATA = PROJECT / "metadata" / "daily_readings.json"
LOCAL_TZ = ZoneInfo("Europe/Madrid")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _run_checked_at() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        parsed = _as_utc(configured)
        if parsed is None:
            raise ValueError("ECORADAR_CHECKED_AT_UTC is not a valid ISO-8601 instant")
        return parsed
    return datetime.now(timezone.utc)


def _as_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


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
) -> dict:
    status_code, status = _public_status(data_at, checked_at)
    return {
        "label": label,
        "value": value,
        "value_numeric": value_numeric,
        "unit": unit,
        "source": source,
        "data_at_utc": data_at.isoformat().replace("+00:00", "Z") if data_at else None,
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
        quality="no calculable amb les fonts locals verificades",
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
    if generated_at is None:
        return False
    return abs((generated_at - checked_at).total_seconds()) <= 12 * 3600


def _xema_inputs(config: dict) -> tuple[pd.DataFrame, dict[str, dict]]:
    frame = pd.read_csv(XEMA, dtype={"codi_variable": str, "codi_estat": str})
    frame["data_lectura"] = pd.to_datetime(frame["data_lectura"], utc=True)
    frame["valor_lectura"] = pd.to_numeric(frame["valor_lectura"], errors="coerce")
    frame["codi_estat"] = frame["codi_estat"].fillna("")
    frame = frame.dropna(subset=["valor_lectura", "data_lectura"]).sort_values("data_lectura")
    latest: dict[str, dict] = {}
    for name, code in config["xema"]["variables"].items():
        rows = frame[frame["codi_variable"] == str(code)]
        if len(rows):
            row = rows.iloc[-1]
            latest[name] = {
                "value": float(row["valor_lectura"]),
                "data_at": row["data_lectura"].to_pydatetime(),
                "validation": str(row["codi_estat"]),
            }
    return frame, latest


def _validation_label(*records: dict) -> str:
    states = {record.get("validation", "") for record in records}
    return "validada" if states == {"V"} else "provisional XEMA"


def _apparent_temperature(temperature_c: float, relative_humidity_pct: float, wind_ms: float) -> float:
    vapour_pressure_hpa = (
        relative_humidity_pct / 100
        * 6.105
        * math.exp(17.27 * temperature_c / (237.7 + temperature_c))
    )
    return temperature_c + 0.33 * vapour_pressure_hpa - 0.70 * wind_ms - 4.0


def calculate() -> dict:
    checked_at = _run_checked_at()
    config = _read_json(CONFIG)
    frame, latest = _xema_inputs(config)
    station_source = "Meteocat XEMA · estació CD (la Seu d'Urgell - Bellestar)"
    readings: dict[str, dict] = {}

    temperature = latest.get("air_temperature_c")
    humidity = latest.get("relative_humidity_pct")
    wind = latest.get("wind_speed_ms")
    if temperature:
        readings["air_temperature"] = _entry(
            label="Temperatura de l'aire",
            value=f"{temperature['value']:.1f} °C".replace(".", ","),
            value_numeric=round(temperature["value"], 1), unit="°C",
            source=station_source, data_at=temperature["data_at"], checked_at=checked_at,
            quality=_validation_label(temperature),
            note="Observació puntual en garita meteorològica; no és temperatura de cada carrer.",
        )
    else:
        readings["air_temperature"] = _missing("Temperatura de l'aire", station_source, checked_at, "L'estació no ha retornat la variable 32.")
    if humidity:
        readings["relative_humidity"] = _entry(
            label="Humitat relativa",
            value=f"{humidity['value']:.0f} %",
            value_numeric=round(humidity["value"], 1), unit="%",
            source=station_source, data_at=humidity["data_at"], checked_at=checked_at,
            quality=_validation_label(humidity),
            note="Observació puntual; no és una malla urbana d'humitat.",
        )
    else:
        readings["relative_humidity"] = _missing("Humitat relativa", station_source, checked_at, "L'estació no ha retornat la variable 33.")
    if wind:
        wind_kmh = wind["value"] * 3.6
        gust = latest.get("wind_gust_ms")
        direction = latest.get("wind_direction_deg")
        extras = []
        if gust:
            extras.append(f"ratxa {gust['value'] * 3.6:.1f} km/h".replace(".", ","))
        if direction:
            extras.append(f"direcció {direction['value']:.0f}°")
        readings["wind"] = _entry(
            label="Vent",
            value=f"{wind_kmh:.1f} km/h".replace(".", ","),
            value_numeric=round(wind_kmh, 1), unit="km/h",
            source=station_source, data_at=wind["data_at"], checked_at=checked_at,
            quality=_validation_label(wind),
            note=(" · ".join(extras) + ". " if extras else "") + "Mesura puntual a 10 m; no és un camp de vent urbà.",
        )
    else:
        readings["wind"] = _missing("Vent", station_source, checked_at, "L'estació no ha retornat la variable 30.")

    precipitation_code = str(config["xema"]["variables"]["precipitation_mm"])
    precipitation_rows = frame[frame["codi_variable"] == precipitation_code].copy()
    if len(precipitation_rows):
        precipitation_rows["local_date"] = precipitation_rows["data_lectura"].dt.tz_convert(LOCAL_TZ).dt.date
        latest_day = precipitation_rows["local_date"].iloc[-1]
        day_rows = precipitation_rows[precipitation_rows["local_date"] == latest_day]
        precipitation = float(day_rows["valor_lectura"].sum())
        last_row = day_rows.iloc[-1]
        readings["precipitation"] = _entry(
            label="Precipitació",
            value=f"{precipitation:.1f} mm".replace(".", ","),
            value_numeric=round(precipitation, 1), unit="mm",
            source=station_source,
            data_at=last_row["data_lectura"].to_pydatetime(), checked_at=checked_at,
            quality=_validation_label({"validation": str(last_row["codi_estat"])}),
            note=f"Acumulació dels períodes XEMA disponibles del {latest_day.isoformat()}; pot ser parcial si el dia encara no ha acabat.",
        )
    else:
        readings["precipitation"] = _missing("Precipitació", station_source, checked_at, "L'estació no ha retornat la variable 35.")

    landsat = _read_json(PROJECT / "metadata" / "landsat_expanded_connector.json")
    expanded = _read_json(PROJECT / "indicators" / "expanded_scope_indicators.json")
    lst_value = expanded.get("metrics", {}).get("land_surface_temperature_c", {}).get("mean")
    lst_date = _as_utc(landsat.get("acquired_at_utc"))
    readings["surface_temperature"] = (
        _entry(
            label="Temperatura superficial",
            value=f"{float(lst_value):.1f} °C".replace(".", ","),
            value_numeric=round(float(lst_value), 1), unit="°C",
            source="USGS Landsat Collection 2 Level-2 ST",
            data_at=lst_date, checked_at=checked_at, quality="QA_PIXEL aplicada",
            note="Mitjana de l'àmbit de l'última escena local vàlida; no és temperatura de l'aire.",
        ) if lst_value is not None and lst_date else
        _missing("Temperatura superficial", "USGS Landsat Collection 2 Level-2 ST", checked_at, "No hi ha cap escena local vàlida processada.")
    )

    sentinel = _read_json(PROJECT / "indicators" / "sentinel2_expanded_indicators.json")
    sentinel_date = _as_utc(sentinel.get("acquired_at_utc"))
    for key, label in (("ndmi", "NDMI"), ("ndvi", "NDVI"), ("albedo", "Albedo")):
        value = sentinel.get("metrics", {}).get(key, {}).get("median")
        readings[key] = (
            _entry(
                label=label,
                value=f"{float(value):.3f}".replace(".", ","),
                value_numeric=round(float(value), 3), unit="índex",
                source="Copernicus Sentinel-2 MSI L2A",
                data_at=sentinel_date, checked_at=checked_at, quality="màscara SCL aplicada",
                note="Mediana de l'àmbit de l'última escena sense núvols vàlida.",
            ) if value is not None and sentinel_date else
            _missing(label, "Copernicus Sentinel-2 MSI L2A", checked_at, "No hi ha cap escena local vàlida processada.")
        )

    context = _read_json(PROJECT / "indicators" / "contextual_environment.json")
    pm25 = context.get("pm25", {})
    pm25_date = _as_utc(pm25.get("reference_time_utc"))
    pm25_value = pm25.get("value_ug_m3")
    readings["air_quality"] = (
        _entry(
            label="Qualitat de l'aire",
            value=f"PM2,5 · {float(pm25_value):.2f} µg/m³".replace(".", ","),
            value_numeric=round(float(pm25_value), 2), unit="µg/m³ PM2,5",
            source="Copernicus CAMS European air-quality forecast",
            data_at=pm25_date, checked_at=checked_at, quality="model 0,1° (~10 km)",
            note="Context supramunicipal modelitzat; no és una estació local ni una concentració de carrer.",
        ) if pm25_value is not None and pm25_date else
        _missing("Qualitat de l'aire", "Copernicus CAMS", checked_at, "El servei no ha retornat cap camp PM2,5 vàlid.")
    )

    if temperature and humidity and wind:
        apparent = _apparent_temperature(temperature["value"], humidity["value"], wind["value"])
        comfort_date = min(temperature["data_at"], humidity["data_at"], wind["data_at"])
        readings["thermal_comfort"] = _entry(
            label="Confort tèrmic",
            value=f"{apparent:.1f} °C aparents".replace(".", ","),
            value_numeric=round(apparent, 1), unit="°C aparents",
            source="Derivat EcoRadar · temperatura aparent de Steadman amb XEMA",
            data_at=comfort_date, checked_at=checked_at,
            quality=_validation_label(temperature, humidity, wind),
            note="Estimació per a una persona adulta a l'ombra; no és UTCI, WBGT, exposició individual ni risc clínic.",
        )
    else:
        readings["thermal_comfort"] = _missing("Confort tèrmic", "Derivat de temperatura, humitat i vent XEMA", checked_at, "Falta almenys una de les tres entrades necessàries.")

    shade = _read_json(PROJECT / "indicators" / "daily_shade.json")
    shade_date = _as_utc(shade.get("data_at_utc"))
    shade_value = shade.get("value", {}).get("shade_pct")
    readings["shade"] = (
        _entry(
            label="Ombra",
            value=f"{float(shade_value):.1f} %".replace(".", ","),
            value_numeric=round(float(shade_value), 1), unit="%",
            source="ICGC LiDAR Territorial v3.1 + posició solar",
            data_at=shade_date, checked_at=checked_at, quality="model directe a 2 m",
            note=f"Càlcul per a {shade.get('data_at_local', 'la data i hora indicades')}; inclou relleu, edificis i arbres LiDAR.",
        ) if shade_value is not None and shade_date else
        _missing("Ombra", "ICGC LiDAR Territorial v3.1 + posició solar", checked_at, "No s'ha generat el càlcul diari d'ombra.")
    )

    readings["cool_streets"] = _missing(
        "Carrers frescos", "Ajuntament / inventari d'arbrat i observació microclimàtica local", checked_at,
        "No hi ha inventari municipal georeferenciat d'arbrat ni mesures tèrmiques de carrer; no s'etiqueten carrers amb un proxy no validat.",
    )
    readings["climate_refuge_utility"] = _missing(
        "Utilitat climàtica dels refugis", "Ajuntament de la Seu d'Urgell", checked_at,
        "No s'ha publicat una xarxa municipal georeferenciada de refugis amb horaris, capacitat i condicions interiors verificables.",
    )

    current_fire = _read_json(PROJECT / "indicators" / "current_fire_danger.json")
    fire_summary = current_fire.get("summary", {})
    fire_date = _as_utc(fire_summary.get("latest_update_utc"))
    fire_value = fire_summary.get("mean_index_0_100")
    readings["current_fire_danger"] = (
        _entry(
            label="Perill actual d'incendi",
            value=f"{float(fire_value):.1f}/100 · {fire_summary.get('predominant_category', '—')}".replace(".", ","),
            value_numeric=round(float(fire_value), 1), unit="índex 0–100",
            source="Índex EcoRadar derivat · fonts detallades a la lectura",
            data_at=fire_date, checked_at=checked_at,
            quality=f"confiança {fire_summary.get('confidence', 'no disponible')} · {fire_summary.get('confidence_pct', '—')} %",
            note="No és una alerta oficial ni substitueix el Pla Alfa.",
        ) if fire_value is not None and fire_date else
        _missing("Perill actual d'incendi", "Índex EcoRadar derivat", checked_at, "No hi ha cap càlcul vàlid disponible.")
    )
    readings["current_runoff_or_flood"] = _missing(
        "Escorrentia o inundació actual", "XEMA + xarxes hidrològiques oficials", checked_at,
        "La precipitació puntual, el proxy estructural d'escorrentia i la làmina SNCZI T=100 no permeten afirmar una situació actual sense model hidrològic o aforament representatiu verificat.",
    )

    counts = {name: 0 for name in ("updated_today", "last_available", "unavailable")}
    for reading in readings.values():
        counts[reading["status_code"]] += 1
    xema_data_at = max(
        (record["data_at"] for record in latest.values() if record.get("data_at")),
        default=None,
    )
    xema_metadata = _read_json(PROJECT / "raw" / "meteocat_xema" / "CD_metadata.json")
    xema_generated = _as_utc(xema_metadata.get("generated_at_utc"))
    cams_generated = _as_utc(context.get("generated_at_utc"))
    landsat_generated = _as_utc(
        landsat.get("latest_catalog_check_utc") or landsat.get("generated_at_utc")
    )
    sentinel_connector = _read_json(PROJECT / "metadata" / "sentinel2_cdse_expanded_connector.json")
    sentinel_generated = _as_utc(
        sentinel_connector.get("latest_catalog_check_utc")
        or sentinel_connector.get("generated_at_utc")
    )
    sentinel_has_credentials = bool(
        os.environ.get("COPERNICUS_CLIENT_ID")
        and os.environ.get("COPERNICUS_CLIENT_SECRET")
    )
    source_checks = {
        "meteocat_xema": _source_check(
            label="Meteocat XEMA · estació CD",
            organization="Servei Meteorològic de Catalunya / Generalitat de Catalunya",
            status="verified" if xema_data_at and _checked_during_run(xema_generated, checked_at) else "service_unavailable",
            checked_at=checked_at,
            data_at=xema_data_at,
            service="Socrata API · nzvn-apee",
            note="Consulta oficial de temperatura, humitat, vent i precipitació.",
        ),
        "cams_pm25": _source_check(
            label="CAMS · PM2,5 europeu",
            organization="Copernicus Atmosphere Monitoring Service / ECMWF",
            status="verified" if pm25_date and _checked_during_run(cams_generated, checked_at) else "service_unavailable",
            checked_at=checked_at,
            data_at=pm25_date,
            service="WMS 1.3.0 GetFeatureInfo",
            note="Context modelitzat a aproximadament 10 km; no és una estació urbana.",
        ),
        "landsat_surface_temperature": _source_check(
            label="Landsat Collection 2 Level-2 ST",
            organization="United States Geological Survey",
            status=landsat.get("connector_status", "verified") if _checked_during_run(landsat_generated, checked_at) else "service_unavailable",
            checked_at=checked_at,
            data_at=lst_date,
            service=landsat.get("service_type", "STAC + COG"),
            note="La consulta de catàleg és diària; el valor només canvia amb una escena QA-vàlida nova.",
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
        "lidar_daily_shade": _source_check(
            label="Ombra diària amb LiDAR ICGC",
            organization="Institut Cartogràfic i Geològic de Catalunya",
            status="verified" if shade_value is not None and shade_date else "service_unavailable",
            checked_at=checked_at,
            data_at=shade_date,
            service="Càlcul EcoRadar sobre LiDAR Territorial v3.1",
            note="La geometria LiDAR és estructural; la posició solar i l'ombra es recalculen cada dia.",
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
        "municipal_local_layers": _source_check(
            label="Arbrat i refugis climàtics municipals",
            organization="Ajuntament de la Seu d'Urgell",
            status="blocked",
            checked_at=checked_at,
            data_at=None,
            service="Dades obertes municipals",
            note="No s'ha verificat cap inventari públic georeferenciat suficient per a aquestes lectures.",
        ),
    }
    payload = {
        "schema_version": "1.0",
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "station": {"code": "CD", "name": "la Seu d'Urgell - Bellestar"},
        "status_counts": counts,
        "source_checks": source_checks,
        "readings": readings,
        "structural_layers_not_recalculated_daily": [
            "pendent", "orientació", "relleu", "impermeabilització",
            "zones inundables oficials", "escorrentia potencial", "edificis",
            "xarxa viària", "zones verdes", "equipaments", "perill estructural d'incendi",
        ],
        "methodology": "docs/data_sources/urban_daily_readings.md",
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    payload = calculate()
    print(json.dumps({"checked_at_utc": payload["checked_at_utc"], "status_counts": payload["status_counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
