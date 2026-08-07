"""Download and normalize the official Meteocat municipal precipitation forecast."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
OUTPUT_DIR = PROJECT / "raw" / "meteocat_forecast"
MUNICIPALITY_CODE = "252038"
MUNICIPALITY_NAME = "la Seu d'Urgell"
URL = (
    "https://static-m.meteo.cat/ginys/models/postProcessament/variables/"
    "prec_acum/intervals/1/prec_acum-{day}_1h.json"
)
USER_AGENT = "EcoRadar/1.0 (+https://github.com/greenwolfnature-netizen/ecoradar-seu)"


def _checked_at_utc() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        return datetime.fromisoformat(configured.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def normalize_forecast_payload(payload: dict, day: int) -> pd.DataFrame:
    """Select one municipality and return its source forecast values."""

    municipalities = payload.get("municipis")
    if not isinstance(municipalities, list):
        raise RuntimeError("Meteocat response has no municipis list")
    municipality = next(
        (item for item in municipalities if str(item.get("codi")) == MUNICIPALITY_CODE),
        None,
    )
    if municipality is None:
        raise RuntimeError(f"Meteocat response has no municipality {MUNICIPALITY_CODE}")
    issued_at = payload.get("dataSortida")
    records = []
    for item in municipality.get("valors", []):
        try:
            value = float(item["valor"])
            valid_at = pd.to_datetime(item["data"], utc=True)
        except (KeyError, TypeError, ValueError):
            continue
        records.append(
            {
                "municipality_code": MUNICIPALITY_CODE,
                "municipality_name": municipality.get("nom") or MUNICIPALITY_NAME,
                "forecast_day_file": day,
                "precipitation_mm": value,
                "valid_at_utc": valid_at.isoformat().replace("+00:00", "Z"),
                "issued_at_utc": pd.to_datetime(issued_at, utc=True).isoformat().replace("+00:00", "Z"),
                "source_variable_code": payload.get("codiVariable"),
                "source_variable_name": payload.get("nomVariable"),
                "source_unit": payload.get("unitat"),
            }
        )
    if not records:
        raise RuntimeError(f"Meteocat day {day} contains no valid forecast values")
    return pd.DataFrame.from_records(records)


def _download(day: int) -> dict:
    request = Request(URL.format(day=day), headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected Meteocat response for day {day}")
    return payload


def fetch_forecast(days: tuple[int, ...] = (1, 2, 3)) -> pd.DataFrame:
    frames = [normalize_forecast_payload(_download(day), day) for day in days]
    frame = pd.concat(frames, ignore_index=True)
    frame["valid_at_utc"] = pd.to_datetime(frame["valid_at_utc"], utc=True)
    frame = frame.sort_values(["valid_at_utc", "forecast_day_file"]).drop_duplicates(
        subset=["valid_at_utc"], keep="first"
    )
    frame["valid_at_utc"] = frame["valid_at_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return frame.reset_index(drop=True)


def run() -> dict:
    checked_at = _checked_at_utc()
    frame = fetch_forecast()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "la_seu_precipitation_hourly.csv"
    metadata_path = OUTPUT_DIR / "meteocat_municipal_forecast.json"
    frame.to_csv(csv_path, index=False)
    payload = {
        "generated_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "connector": "meteocat_municipal_precipitation_forecast",
        "responsibility": "download_and_normalize_only",
        "source": "Predicció municipal de Meteocat",
        "organization": "Servei Meteorològic de Catalunya / Generalitat de Catalunya",
        "official_url": f"https://www.meteo.cat/prediccio/municipal/{MUNICIPALITY_CODE}",
        "service_type": "public first-party JSON used by the official municipal widget",
        "update_frequency": "operational forecast; source issue timestamp retained",
        "credentials_required": False,
        "usage_license": "No specific reuse licence identified in the inspected widget endpoint; Meteocat attribution retained.",
        "connector_status": "verified",
        "municipality_code": MUNICIPALITY_CODE,
        "records": int(len(frame)),
        "latest_issue_utc": frame["issued_at_utc"].max(),
        "latest_valid_time_utc": frame["valid_at_utc"].max(),
        "output_csv": str(csv_path.relative_to(ROOT)),
        "methodology": "docs/data_sources/meteocat_municipal_precipitation_forecast_la_seu.md",
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
