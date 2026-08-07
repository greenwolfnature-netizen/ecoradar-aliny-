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
CHE_STREAMFLOW = PROJECT / "raw" / "che_saih" / "A022_A023_current.csv"
CHE_STREAMFLOW_METADATA = PROJECT / "raw" / "che_saih" / "che_saih_streamflow.json"
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
    methodology: str | None = None,
    limitations: list[str] | None = None,
    details: dict | None = None,
) -> dict:
    status_code, status = _public_status(data_at, checked_at)
    entry = {
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
    if methodology:
        entry["methodology"] = methodology
    if limitations:
        entry["limitations"] = limitations
    if details:
        entry["details"] = details
    return entry


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


def _reading_interpretation(key: str, item: dict) -> str:
    """Return a concise, non-clinical interpretation of a published reading."""
    if item.get("status_code") == "unavailable" or item.get("value_numeric") is None:
        return (
            "No hi ha prou dades verificades per interpretar aquesta lectura. "
            "Es conserva visible per fer explícita la manca d'informació."
        )

    value = float(item["value_numeric"])
    ca = lambda decimals: f"{value:.{decimals}f}".replace(".", ",")
    if key == "air_temperature":
        return (
            f"{ca(1)} °C és la temperatura de l'aire observada a Bellestar. "
            "No és automàticament bona o dolenta: cal llegir-la amb la humitat, "
            "el vent, la radiació i la temperatura aparent."
        )
    if key == "relative_humidity":
        return (
            f"{ca(0)} % indica la proporció d'humitat de l'aire a l'estació. "
            "A l'exterior modifica l'evaporació i la sensació tèrmica, però no té "
            "una categoria universal de bona o dolenta per si sola."
        )
    if key == "wind":
        return (
            f"{ca(1)} km/h és la velocitat observada a 10 m. El vent pot "
            "afavorir ventilació i refredament, però l'efecte depèn de les ratxes, "
            "la direcció, l'exposició i la forma urbana."
        )
    if key == "precipitation":
        if value <= 0:
            return (
                "0 mm vol dir que no s'ha registrat precipitació en els períodes "
                "disponibles del dia; no és una previsió del que pot ploure després."
            )
        return (
            f"{ca(1)} mm és l'acumulació registrada en els períodes disponibles "
            "del dia. Pot ser parcial mentre el dia no hagi acabat."
        )
    if key in {"river_flow_valira", "river_flow_segre"}:
        return (
            f"{ca(2)} m³/s és el cabal provisional al punt d'aforament. "
            "Sense llindars oficials específics no es classifica com a normal o alt; "
            "cal valorar-ne la tendència i els avisos de la CHE."
        )
    if key == "surface_temperature":
        level = "relativament fresca" if value <= 40 else "càlida" if value < 52 else "molt calenta"
        return (
            f"{ca(1)} °C és la mitjana superficial de l'escena i correspon a una "
            f"superfície {level} dins l'escala cromàtica EcoRadar. No és temperatura "
            "de l'aire ni un llindar sanitari."
        )
    if key == "ndvi":
        level = (
            "molt baix" if value <= 0.1 else
            "baix" if value < 0.3 else
            "intermedi" if value < 0.55 else
            "alt" if value < 0.85 else
            "molt alt"
        )
        return (
            f"La mitjana NDVI {ca(3)} se situa en el tram {level} de la llegenda "
            "EcoRadar: valors més alts solen indicar més vigor vegetal. No mesura "
            "biodiversitat ni l'estat de cada arbre."
        )
    if key == "ndmi":
        level = "sec relatiu" if value < 0 else "intermedi" if value < 0.2 else "humit relatiu"
        return (
            f"La mitjana NDMI {ca(3)} indica un estat {level} en aquesta escena. "
            "Compara humitat relativa de la vegetació i no equival a humitat "
            "volumètrica del sòl."
        )
    if key == "albedo":
        return (
            f"La mitjana {ca(3)} equival aproximadament a reflectir el "
            f"{f'{value * 100:.1f}'.replace('.', ',')} % de la radiació solar d'ona curta en el model. "
            "Un albedo més alt reflecteix més energia, però no determina sol el confort."
        )
    if key == "air_quality":
        relation = "per sota" if value < 15 else "igual o per sobre"
        return (
            f"PM2,5 {ca(2)} µg/m³ queda {relation} de la referència OMS 2021 de "
            "15 µg/m³ per a la mitjana de 24 hores. Com que és un camp CAMS horari "
            "modelitzat a uns 10 km, no permet afirmar que l'aire sigui bo o dolent "
            "ni verificar el compliment de la guia."
        )
    if key == "thermal_comfort":
        relation = "per sota" if value < 32 else "al nivell o per sobre"
        return (
            f"{ca(1)} °C aparents queda {relation} del llindar operatiu EcoRadar "
            "de 32 °C per al cribratge de calor. No és UTCI, WBGT ni una valoració clínica."
        )
    if key == "shade":
        return (
            f"{ca(1)} % és la part modelitzada de l'àmbit amb ombra directa a "
            "la data i hora indicades. Un percentatge més alt significa més superfície "
            "protegida en aquell instant, no durant tot el dia."
        )
    if key == "cool_streets":
        return (
            f"La puntuació mitjana és {ca(1)}/100. Les classes alta, mitjana i "
            "baixa expressen potencial de frescor combinat; no són temperatures "
            "mesurades als carrers."
        )
    if key == "climate_refuge_utility":
        return (
            f"La puntuació mitjana dels candidats és {ca(1)}/100. Un valor més "
            "alt indica més utilitat climàtica potencial, però cap espai és un refugi "
            "oficial sense validació municipal."
        )
    if key == "current_fire_danger":
        return (
            f"{ca(1)}/100 és la mitjana de l'índex EcoRadar actual. La categoria "
            "resumeix els factors disponibles, però no és una alerta oficial ni "
            "substitueix el Pla Alfa."
        )
    if key == "current_runoff_or_flood":
        return (
            f"{ca(1)}/100 és un cribratge hidrològic combinat. La categoria "
            "necessita corroboració de cabal, nivell i precipitació i no confirma "
            "una inundació ni substitueix els avisos oficials."
        )
    return (
        "El valor s'ha d'interpretar amb la font, la data, la metodologia i les "
        "limitacions que figuren en aquesta mateixa fitxa."
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


def _che_streamflow_inputs() -> dict[str, dict]:
    if not CHE_STREAMFLOW.exists():
        return {}
    frame = pd.read_csv(CHE_STREAMFLOW, dtype={"station_code": str})
    required = {"station_code", "river", "discharge_m3_s", "observed_at_utc"}
    missing = required.difference(frame.columns)
    if missing:
        raise RuntimeError(f"CHE/SAIH streamflow file missing columns: {sorted(missing)}")
    frame["discharge_m3_s"] = pd.to_numeric(frame["discharge_m3_s"], errors="coerce")
    frame["observed_at_utc"] = pd.to_datetime(frame["observed_at_utc"], utc=True)
    frame = frame.dropna(subset=["station_code", "discharge_m3_s", "observed_at_utc"])
    latest: dict[str, dict] = {}
    for station_code in ("A022", "A023"):
        rows = frame[frame["station_code"] == station_code].sort_values("observed_at_utc")
        if len(rows):
            row = rows.iloc[-1]
            latest[station_code] = {
                "river": str(row["river"]),
                "value": float(row["discharge_m3_s"]),
                "data_at": row["observed_at_utc"].to_pydatetime(),
                "latitude": (
                    float(row["latitude"])
                    if "latitude" in row.index and pd.notna(row["latitude"])
                    else None
                ),
                "longitude": (
                    float(row["longitude"])
                    if "longitude" in row.index and pd.notna(row["longitude"])
                    else None
                ),
            }
    return latest


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

    streamflows = _che_streamflow_inputs()
    for station_code, key, river in (
        ("A022", "river_flow_valira", "Valira"),
        ("A023", "river_flow_segre", "Segre"),
    ):
        flow = streamflows.get(station_code)
        source = f"CHE · SAIH Ebre · estació {station_code} ({river})"
        readings[key] = (
            _entry(
                label=f"Cabal del {river}",
                value=f"{flow['value']:.2f} m³/s".replace(".", ","),
                value_numeric=round(flow["value"], 3),
                unit="m³/s",
                source=source,
                data_at=flow["data_at"],
                checked_at=checked_at,
                quality="dada provisional SAIH",
                note=(
                    "Observació puntual a l'estació d'aforament. Dada de temps real "
                    "provisional i subjecta a revisió de la CHE; no és una alerta "
                    "d'inundació ni representa tot el tram fluvial."
                ),
            )
            if flow
            else _missing(
                f"Cabal del {river}",
                source,
                checked_at,
                f"L'estació {station_code} no ha retornat cap cabal actual normalitzable.",
            )
        )

    surface_selection = _read_json(
        PROJECT / "metadata" / "current_surface_temperature.json"
    ).get("selected", {})
    expanded = _read_json(PROJECT / "indicators" / "expanded_scope_indicators.json")
    lst_value = expanded.get("metrics", {}).get("land_surface_temperature_c", {}).get("mean")
    lst_date = _as_utc(surface_selection.get("acquired_at_utc"))
    lst_source = surface_selection.get(
        "source",
        "Font detallada de temperatura superficial no disponible",
    )
    lst_quality = surface_selection.get("quality", "QA aplicada")
    readings["surface_temperature"] = (
        _entry(
            label="Temperatura superficial",
            value=f"{float(lst_value):.1f} °C".replace(".", ","),
            value_numeric=round(float(lst_value), 1), unit="°C",
            source=lst_source,
            data_at=lst_date, checked_at=checked_at, quality=lst_quality,
            note="Mitjana de l'àmbit de l'última escena local vàlida; no és temperatura de l'aire.",
        ) if lst_value is not None and lst_date else
        _missing("Temperatura superficial", "Landsat / ECOSTRESS", checked_at, "No hi ha cap escena local detallada i QA-vàlida processada.")
    )

    sentinel = _read_json(PROJECT / "indicators" / "sentinel2_expanded_indicators.json")
    sentinel_date = _as_utc(sentinel.get("acquired_at_utc"))
    for key, label in (("ndmi", "NDMI"), ("ndvi", "NDVI"), ("albedo", "Albedo")):
        value = sentinel.get("metrics", {}).get(key, {}).get("mean")
        readings[key] = (
            _entry(
                label=label,
                value=f"{float(value):.3f}".replace(".", ","),
                value_numeric=round(float(value), 3), unit="índex",
                source="Copernicus Sentinel-2 MSI L2A",
                data_at=sentinel_date, checked_at=checked_at, quality="màscara SCL aplicada",
                note="Mitjana de l'àmbit de l'última escena sense núvols vàlida.",
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

    urban_potential = _read_json(PROJECT / "indicators" / "urban_potential_services.json")
    cool = urban_potential.get("cool_streets", {})
    cool_dates = urban_potential.get("data_dates", {})
    cool_data_at = _as_utc(cool_dates.get("shade")) or _as_utc(cool_dates.get("surface_temperature"))
    cool_counts = cool.get("class_counts", {})
    readings["cool_streets"] = (
        _entry(
            label="Potencial de frescor dels carrers",
            value=(
                f"{int(cool_counts.get('alt', 0))} trams amb potencial alt · "
                f"{int(cool_counts.get('mitjà', 0))} mitjà · "
                f"{int(cool_counts.get('baix', 0))} baix"
            ),
            value_numeric=float(cool.get("mean_score_0_100")),
            unit="índex 0–100",
            source="Indicador EcoRadar · ICGC LiDAR + LST detallada + Copernicus HRL + OSM",
            data_at=cool_data_at,
            checked_at=checked_at,
            quality=(
                f"confiança mitjana · {cool.get('mean_confidence_pct', '—')} %"
            ).replace(".", ","),
            note=(
                f"{cool.get('segments', 0)} trams de fins a 75 m. És potencial derivat, "
                "no una temperatura mesurada al carrer."
            ),
            methodology=cool.get(
                "methodology_text",
                "Metodologia documentada a la fitxa tècnica de l'indicador.",
            ),
            limitations=cool.get("limitations", []),
            details={
                "class_counts": cool_counts,
                "class_lengths_km": cool.get("class_lengths_km"),
                "weights": cool.get("weights"),
                "thresholds": cool.get("thresholds"),
                "component_dates": cool_dates,
                "methodology_document": urban_potential.get("methodology"),
                "output": cool.get("output"),
            },
        )
        if cool.get("segments") and cool_data_at
        else _missing(
            "Potencial de frescor dels carrers",
            "Indicador EcoRadar · LiDAR, temperatura, HRL i OSM",
            checked_at,
            "El càlcul per trams encara no ha produït cap resultat vàlid.",
        )
    )
    utility = urban_potential.get("climate_utility_candidates", {})
    utility_counts = utility.get("class_counts", {})
    readings["climate_refuge_utility"] = (
        _entry(
            label="Utilitat climàtica potencial dels equipaments",
            value=(
                f"{int(utility.get('candidate_count', 0))} candidats · "
                f"{int(utility_counts.get('alt', 0))} amb utilitat alta · "
                f"{int(utility_counts.get('mitjà', 0))} mitjana"
            ),
            value_numeric=float(utility.get("mean_score_0_100")),
            unit="índex 0–100",
            source="Indicador EcoRadar · equipaments i verd OSM + LiDAR + LST + accessibilitat",
            data_at=cool_data_at,
            checked_at=checked_at,
            quality=(
                f"confiança mitjana · {utility.get('mean_confidence_pct', '—')} %"
            ).replace(".", ","),
            note=(
                "Són equipaments públics i espais verds candidats. Cap element "
                "s'etiqueta com a refugi climàtic oficial sense validació municipal."
            ),
            methodology=utility.get(
                "methodology_text",
                "Metodologia documentada a la fitxa tècnica de l'indicador.",
            ),
            limitations=utility.get("limitations", []),
            details={
                "class_counts": utility_counts,
                "weights": utility.get("weights"),
                "thresholds": utility.get("thresholds"),
                "component_dates": cool_dates,
                "vulnerable_population_component": utility.get("vulnerable_population_component"),
                "official_refuge_status": utility.get("official_refuge_status"),
                "methodology_document": urban_potential.get("methodology"),
                "output": utility.get("output"),
            },
        )
        if utility.get("candidate_count") and cool_data_at
        else _missing(
            "Utilitat climàtica potencial dels equipaments",
            "Indicador EcoRadar · equipaments, espais verds i capes climàtiques",
            checked_at,
            "El càlcul de candidats encara no ha produït cap resultat vàlid.",
        )
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
    hydrology = _read_json(PROJECT / "indicators" / "current_hydrological_situation.json")
    hydrology_date = _as_utc(hydrology.get("data_at_utc"))
    hydrology_score = hydrology.get("score_0_100")
    readings["current_runoff_or_flood"] = (
        _entry(
            label="Situació hidrològica actual",
            value=f"{hydrology.get('category', '—')} · {float(hydrology_score):.1f}/100".replace(".", ","),
            value_numeric=round(float(hydrology_score), 1),
            unit="índex 0–100",
            source="Indicador EcoRadar · CHE A022/A023 + XEMA + Meteocat + SNCZI + escorrentia",
            data_at=hydrology_date,
            checked_at=checked_at,
            quality=(
                f"confiança {hydrology.get('confidence', '—')} · "
                f"{hydrology.get('confidence_pct', '—')} %"
            ).replace(".", ","),
            note=(
                "Cribratge contextual: no afirma que hi hagi una inundació actual "
                "i no substitueix els avisos oficials."
            ),
            methodology=hydrology.get(
                "methodology_text",
                "Metodologia documentada a la fitxa tècnica de l'indicador.",
            ),
            limitations=hydrology.get("limitations", []),
            details={
                "stations": hydrology.get("stations"),
                "precipitation": hydrology.get("precipitation"),
                "components_0_100": hydrology.get("components_0_100"),
                "weights": hydrology.get("weights"),
                "thresholds": hydrology.get("thresholds"),
                "territorial_context": hydrology.get("territorial_context"),
                "guardrail_applied": hydrology.get("guardrail_applied"),
                "methodology_document": hydrology.get("methodology"),
            },
        )
        if hydrology_score is not None and hydrology_date
        else _missing(
            "Situació hidrològica actual",
            "CHE/SAIH + XEMA + Meteocat + MITECO-SNCZI",
            checked_at,
            "El càlcul hidrològic combinat encara no ha produït cap resultat vàlid.",
        )
    )

    counts = {name: 0 for name in ("updated_today", "last_available", "unavailable")}
    for key, reading in readings.items():
        reading["interpretation"] = _reading_interpretation(key, reading)
        counts[reading["status_code"]] += 1
    xema_data_at = max(
        (record["data_at"] for record in latest.values() if record.get("data_at")),
        default=None,
    )
    xema_metadata = _read_json(PROJECT / "raw" / "meteocat_xema" / "CD_metadata.json")
    xema_generated = _as_utc(xema_metadata.get("generated_at_utc"))
    che_metadata = _read_json(CHE_STREAMFLOW_METADATA)
    che_generated = _as_utc(che_metadata.get("generated_at_utc"))
    che_data_at = max(
        (record["data_at"] for record in streamflows.values() if record.get("data_at")),
        default=None,
    )
    cams_generated = _as_utc(context.get("generated_at_utc"))
    landsat = _read_json(PROJECT / "metadata" / "landsat_expanded_connector.json")
    ecostress = _read_json(PROJECT / "metadata" / "ecostress_expanded_connector.json")
    creaf = _read_json(PROJECT / "metadata" / "creaf_forestdrought_connector.json")
    landsat_generated = _as_utc(landsat.get("latest_catalog_check_utc") or landsat.get("generated_at_utc"))
    ecostress_generated = _as_utc(ecostress.get("latest_catalog_check_utc") or ecostress.get("generated_at_utc"))
    creaf_generated = _as_utc(creaf.get("latest_catalog_check_utc") or creaf.get("generated_at_utc"))
    creaf_date = _as_utc(creaf.get("data_at_utc"))
    forecast_metadata = _read_json(
        PROJECT / "raw" / "meteocat_forecast" / "meteocat_municipal_forecast.json"
    )
    forecast_generated = _as_utc(forecast_metadata.get("generated_at_utc"))
    forecast_data_at = _as_utc(forecast_metadata.get("latest_issue_utc"))
    urban_potential_generated = _as_utc(urban_potential.get("generated_at_utc"))
    hydrology_generated = _as_utc(hydrology.get("checked_at_utc"))
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
        "che_saih_streamflow": _source_check(
            label="CHE / SAIH Ebre · cabals A022 i A023",
            organization="Confederació Hidrogràfica de l'Ebre / MITECO",
            status=(
                "verified"
                if len(streamflows) == 2 and _checked_during_run(che_generated, checked_at)
                else "service_unavailable"
            ),
            checked_at=checked_at,
            data_at=che_data_at,
            service="Valors actuals d'estacions d'aforament · font cada 15 minuts",
            note="Observacions puntuals provisionals; no són alertes d'inundació.",
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
        "ecostress_surface_temperature": _source_check(
            label="ECOSTRESS L2T LST V3",
            organization="NASA/JPL ECOSTRESS / NASA LP DAAC",
            status=(
                ecostress.get("connector_status", "requires_credentials")
                if _checked_during_run(ecostress_generated, checked_at)
                else "requires_credentials"
            ),
            checked_at=checked_at,
            data_at=_as_utc(ecostress.get("acquired_at_utc")),
            service="NASA CMR Search + Earthdata protected COG",
            note="Alternativa detallada de 70 m; només es selecciona després de descàrrega i QA local.",
        ),
        "creaf_forestdrought": _source_check(
            label="ForestDrought · sequera i potencial de foc",
            organization="CREAF, Ecosystem Modelling Facility (EMF)",
            status=(
                creaf.get("connector_status", "service_unavailable")
                if _checked_during_run(creaf_generated, checked_at)
                else "service_unavailable"
            ),
            checked_at=checked_at,
            data_at=creaf_date,
            service="Repositori públic de GeoPackage diaris · 500 m",
            note="Model forestal de procés; proveïdor de dades CREAF/EMF, no alerta operativa ni detall de carrer.",
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
        "meteocat_municipal_forecast": _source_check(
            label="Meteocat · previsió municipal de precipitació",
            organization="Servei Meteorològic de Catalunya / Generalitat de Catalunya",
            status=(
                "verified"
                if forecast_data_at and _checked_during_run(forecast_generated, checked_at)
                else "service_unavailable"
            ),
            checked_at=checked_at,
            data_at=forecast_data_at,
            service="JSON públic del giny oficial · municipi 252038",
            note="Previsió municipal operativa; no és una observació, una malla de carrers ni un avís.",
        ),
        "urban_potential_services": _source_check(
            label="Potencial de frescor i utilitat climàtica",
            organization="EcoRadar sobre ICGC, Copernicus, USGS/NASA i OSM",
            status=(
                "verified"
                if cool.get("segments")
                and utility.get("candidate_count")
                and urban_potential_generated
                else "service_unavailable"
            ),
            checked_at=checked_at,
            data_at=cool_data_at,
            service="Analysis Engine EcoRadar per trams i candidats",
            note="Indicadors derivats; no són temperatura mesurada ni refugis oficials.",
        ),
        "current_hydrological_situation": _source_check(
            label="Situació hidrològica actual",
            organization="EcoRadar sobre CHE, Meteocat, MITECO-SNCZI, Copernicus i ICGC",
            status=(
                "verified"
                if hydrology_score is not None and _checked_during_run(hydrology_generated, checked_at)
                else "service_unavailable"
            ),
            checked_at=checked_at,
            data_at=hydrology_date,
            service="Analysis Engine EcoRadar amb regles de corroboració",
            note="Cribratge contextual; no afirma inundació actual ni substitueix avisos oficials.",
        ),
        "municipal_local_layers": _source_check(
            label="Validació municipal i població vulnerable de detall",
            organization="Ajuntament de la Seu d'Urgell",
            status="blocked",
            checked_at=checked_at,
            data_at=None,
            service="Dades obertes municipals",
            note="No s'ha verificat una capa espacial de població vulnerable ni una validació municipal dels equipaments candidats.",
        ),
    }
    payload = {
        "schema_version": "1.0",
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "station": {"code": "CD", "name": "la Seu d'Urgell - Bellestar"},
        "hydrological_stations": [
            {
                "code": station_code,
                "river": river,
                "organization": "CHE / SAIH Ebre",
                "reading_key": reading_key,
                "coordinates_epsg4326": (
                    [
                        streamflows[station_code]["longitude"],
                        streamflows[station_code]["latitude"],
                    ]
                    if streamflows.get(station_code)
                    and streamflows[station_code].get("longitude") is not None
                    and streamflows[station_code].get("latitude") is not None
                    else None
                ),
            }
            for station_code, river, reading_key in (
                ("A022", "Valira", "river_flow_valira"),
                ("A023", "Segre", "river_flow_segre"),
            )
        ],
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
