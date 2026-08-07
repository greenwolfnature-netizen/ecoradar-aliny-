"""Calculate the EcoRadar current hydrological-situation screening.

The module combines normalized source outputs. It is not a flood-warning
connector and never infers an ongoing flood from discharge alone.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
CHE = PROJECT / "raw" / "che_saih" / "A022_A023_current.csv"
CHE_METADATA = PROJECT / "raw" / "che_saih" / "che_saih_streamflow.json"
XEMA = PROJECT / "raw" / "meteocat_xema" / "CD_observations.csv"
FORECAST = PROJECT / "raw" / "meteocat_forecast" / "la_seu_precipitation_hourly.csv"
FORECAST_METADATA = PROJECT / "raw" / "meteocat_forecast" / "meteocat_municipal_forecast.json"
EXPANDED = PROJECT / "indicators" / "expanded_scope_indicators.json"
SNCZI = PROJECT / "metadata" / "snczi_q100_expanded.json"
OUTPUT = PROJECT / "indicators" / "current_hydrological_situation.json"
METADATA = PROJECT / "metadata" / "current_hydrological_situation.json"

WEIGHTS = {
    "recent_precipitation": 0.25,
    "forecast_precipitation": 0.25,
    "discharge_trend": 0.25,
    "level_trend": 0.10,
    "structural_sensitivity": 0.15,
}
THRESHOLDS = {
    "normal": "<25",
    "vigilància": "25-49.9",
    "elevada": "50-74,9 amb corroboració de precipitació observada o prevista",
    "molt elevada": (
        ">=75 amb una corroboració més intensa de precipitació observada o prevista"
    ),
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _checked_at() -> datetime:
    value = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if value:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _iso(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.to_datetime(value, utc=True).isoformat().replace("+00:00", "Z")


def _parse_sequence(value) -> list[float]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        sequence = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [float(item) for item in sequence if item is not None and np.isfinite(float(item))]


def _trend(sequence: list[float]) -> dict:
    if len(sequence) < 6:
        return {
            "available": False,
            "direction": "no calculable",
            "change_pct": None,
            "score_0_100": None,
            "samples": len(sequence),
        }
    width = min(5, len(sequence) // 2)
    first = float(np.median(sequence[:width]))
    last = float(np.median(sequence[-width:]))
    change = (last - first) / max(abs(first), 0.01) * 100
    if change > 10:
        direction = "ascendent"
    elif change < -10:
        direction = "descendent"
    else:
        direction = "estable"
    score = max(0.0, min(100.0, (change - 5.0) / 45.0 * 100.0))
    return {
        "available": True,
        "direction": direction,
        "change_pct": round(change, 1),
        "score_0_100": round(score, 1),
        "samples": len(sequence),
        "timestamp_limitation": (
            "la seqüència pública no inclou una marca temporal individual "
            "per a cada mostra"
        ),
    }


def _rain_score(mm: float | None) -> float | None:
    if mm is None or not np.isfinite(mm):
        return None
    return round(max(0.0, min(100.0, mm / 60.0 * 100.0)), 1)


def _weighted(components: dict[str, float | None]) -> tuple[float, float]:
    available = [(key, value) for key, value in components.items() if value is not None]
    weight = sum(WEIGHTS[key] for key, _ in available)
    if weight <= 0:
        raise RuntimeError("No hydrological component is available")
    score = sum(float(value) * WEIGHTS[key] for key, value in available) / weight
    return round(score, 1), round(weight * 100, 1)


def _category(score: float, observed_mm: float | None, forecast_24h_mm: float | None) -> tuple[str, str | None]:
    category = (
        "molt elevada" if score >= 75
        else "elevada" if score >= 50
        else "vigilància" if score >= 25
        else "normal"
    )
    corroborated_elevated = (observed_mm or 0) >= 20 or (forecast_24h_mm or 0) >= 30
    corroborated_very_high = (observed_mm or 0) >= 40 or (forecast_24h_mm or 0) >= 60
    rule_note = None
    if category == "molt elevada" and not corroborated_very_high:
        category = "vigilància"
        rule_note = "La classe molt elevada no s'activa sense corroboració de pluja observada o prevista."
    elif category == "elevada" and not corroborated_elevated:
        category = "vigilància"
        rule_note = "La classe elevada no s'activa només per cabal, nivell o sensibilitat territorial."
    return category, rule_note


def calculate() -> dict:
    checked_at = _checked_at()
    if not CHE.exists():
        raise FileNotFoundError(CHE)
    che = pd.read_csv(CHE, dtype={"station_code": str})
    required = {"station_code", "river", "discharge_m3_s", "level_m", "observed_at_utc"}
    missing = required.difference(che.columns)
    if missing:
        raise RuntimeError(f"CHE normalized file lacks fields: {sorted(missing)}")
    station_records = []
    flow_trends = []
    level_trends = []
    data_instants: list[pd.Timestamp] = []
    che_rain = []
    for row in che.itertuples(index=False):
        flow_trend = _trend(_parse_sequence(getattr(row, "recent_flow_values_json", None)))
        level_trend = _trend(_parse_sequence(getattr(row, "recent_level_values_json", None)))
        if flow_trend["score_0_100"] is not None:
            flow_trends.append(flow_trend["score_0_100"])
        if level_trend["score_0_100"] is not None:
            level_trends.append(level_trend["score_0_100"])
        observed = pd.to_datetime(row.observed_at_utc, utc=True)
        data_instants.append(observed)
        rain_value = getattr(row, "precipitation_24h_mm", None)
        if rain_value is not None and not pd.isna(rain_value):
            che_rain.append(float(rain_value))
        station_records.append(
            {
                "station_code": row.station_code,
                "river": row.river,
                "discharge_m3_s": round(float(row.discharge_m3_s), 3),
                "level_m": round(float(row.level_m), 3),
                "observed_at_utc": _iso(row.observed_at_utc),
                "provisional": True,
                "discharge_trend": flow_trend,
                "level_trend": level_trend,
            }
        )

    xema_rain_24h = None
    xema_latest = None
    if XEMA.exists():
        xema = pd.read_csv(XEMA, dtype={"codi_variable": str})
        xema["data_lectura"] = pd.to_datetime(xema["data_lectura"], utc=True)
        xema["valor_lectura"] = pd.to_numeric(xema["valor_lectura"], errors="coerce")
        rain = xema[(xema["codi_variable"] == "35") & xema["valor_lectura"].notna()].copy()
        if len(rain):
            xema_latest = rain["data_lectura"].max()
            xema_rain_24h = float(
                rain[rain["data_lectura"] > xema_latest - pd.Timedelta(hours=24)]["valor_lectura"].sum()
            )
            data_instants.append(xema_latest)
    observed_rain = max([value for value in [xema_rain_24h, *che_rain] if value is not None], default=None)

    forecast_24h = None
    forecast_48h = None
    forecast_issue = None
    if FORECAST.exists():
        forecast = pd.read_csv(FORECAST)
        forecast["valid_at_utc"] = pd.to_datetime(forecast["valid_at_utc"], utc=True)
        forecast["issued_at_utc"] = pd.to_datetime(forecast["issued_at_utc"], utc=True)
        forecast["precipitation_mm"] = pd.to_numeric(forecast["precipitation_mm"], errors="coerce")
        forecast = forecast.dropna(subset=["precipitation_mm", "valid_at_utc"])
        if len(forecast):
            forecast_issue = forecast["issued_at_utc"].max()
            start = max(pd.Timestamp(checked_at), forecast["valid_at_utc"].min())
            forecast_24h = float(
                forecast[
                    (forecast["valid_at_utc"] >= start)
                    & (forecast["valid_at_utc"] < start + pd.Timedelta(hours=24))
                ]["precipitation_mm"].sum()
            )
            forecast_48h = float(
                forecast[
                    (forecast["valid_at_utc"] >= start)
                    & (forecast["valid_at_utc"] < start + pd.Timedelta(hours=48))
                ]["precipitation_mm"].sum()
            )
            data_instants.append(forecast_issue)

    expanded = _read_json(EXPANDED)
    runoff = expanded.get("metrics", {}).get("runoff_proxy_mean_0_100")
    flood_present = SNCZI.exists() and bool(_read_json(SNCZI).get("output"))
    structural = (
        round(min(100.0, 0.7 * float(runoff) + (20.0 if flood_present else 0.0)), 1)
        if runoff is not None
        else 20.0 if flood_present
        else None
    )
    components = {
        "recent_precipitation": _rain_score(observed_rain),
        "forecast_precipitation": _rain_score(forecast_24h),
        "discharge_trend": round(float(np.mean(flow_trends)), 1) if flow_trends else None,
        "level_trend": round(float(np.mean(level_trends)), 1) if level_trends else None,
        "structural_sensitivity": structural,
    }
    score, completeness = _weighted(components)
    category, guardrail_note = _category(score, observed_rain, forecast_24h)
    confidence_pct = round(min(74.0, completeness * 0.75), 1)
    confidence = "alta" if confidence_pct >= 75 else "mitjana" if confidence_pct >= 55 else "baixa"
    latest_data = max(data_instants) if data_instants else pd.Timestamp(checked_at)
    payload = {
        "schema_version": "1.0",
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "data_at_utc": latest_data.isoformat().replace("+00:00", "Z"),
        "label": "Situació hidrològica actual",
        "indicator_type": (
            "Cribratge contextual derivat EcoRadar; no és un avís oficial"
        ),
        "score_0_100": score,
        "category": category,
        "confidence": confidence,
        "confidence_pct": confidence_pct,
        "component_completeness_pct": completeness,
        "components_0_100": components,
        "weights": WEIGHTS,
        "thresholds": THRESHOLDS,
        "stations": station_records,
        "precipitation": {
            "observed_24h_mm": round(observed_rain, 1) if observed_rain is not None else None,
            "xema_data_at_utc": _iso(xema_latest),
            "forecast_next_24h_mm": round(forecast_24h, 1) if forecast_24h is not None else None,
            "forecast_next_48h_mm": round(forecast_48h, 1) if forecast_48h is not None else None,
            "forecast_issued_at_utc": _iso(forecast_issue),
        },
        "territorial_context": {
            "runoff_potential_mean_0_100": runoff,
            "snczi_q100_zones_present_in_scope": flood_present,
            "interpretation": (
                "Només expressa sensibilitat estructural; no demostra que hi "
                "hagi una inundació actual."
            ),
        },
        "guardrail_applied": guardrail_note,
        "official_warning_integrated": False,
        "sources": [
            "CHE/SAIH Ebre: cabal i nivell actuals de les estacions A022 i A023",
            "Meteocat XEMA: precipitació recent de l'estació CD",
            "Meteocat: previsió municipal de precipitació 252038",
            "MITECO SNCZI Q100",
            (
                "Indicador EcoRadar de potencial d'escorrentia derivat de la "
                "impermeabilització Copernicus i el pendent LiDAR de l'ICGC"
            ),
        ],
        "methodology_text": (
            "Índex ponderat: precipitació recent 25 %, precipitació prevista "
            "25 %, tendència del cabal 25 %, tendència del nivell 10 % i "
            "sensibilitat estructural 15 %. Les classes elevada i molt elevada "
            "requereixen corroboració de precipitació observada o prevista."
        ),
        "methodology": "docs/data_sources/la_seu_current_hydrological_situation.md",
        "limitations": [
            (
                "El servei actual consultat no publica llindars oficials d'avís "
                "específics per a aquestes estacions."
            ),
            (
                "Els valors actuals de la CHE són provisionals i estan subjectes "
                "a revisió hidrològica."
            ),
            (
                "Les mostres dels minigràfics públics de la CHE no tenen una "
                "marca temporal individual; només se'n calcula una direcció "
                "recent qualitativa."
            ),
            (
                "La previsió de Meteocat és municipal i no descriu la "
                "precipitació a escala de carrer."
            ),
            (
                "El potencial d'escorrentia i les zones Q100 són context "
                "estructural, no evidència d'un episodi actual."
            ),
            (
                "La lectura no afirma que hi hagi una inundació i no substitueix "
                "els avisos oficials de la CHE, l'ACA, Meteocat o Protecció Civil."
            ),
        ],
        "source_metadata": {
            "che": str(CHE_METADATA.relative_to(ROOT)),
            "forecast": str(FORECAST_METADATA.relative_to(ROOT)),
            "snczi": str(SNCZI.relative_to(ROOT)),
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    payload = calculate()
    print(
        json.dumps(
            {
                "category": payload["category"],
                "score_0_100": payload["score_0_100"],
                "confidence_pct": payload["confidence_pct"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
