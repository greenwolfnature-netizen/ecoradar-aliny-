"""Fetch the nearest verified XEMA wind observations used for Alinyà context."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ecoradar.connectors.connector_meteocat_xema import fetch_station


OUT_DIR = ROOT / "projectes" / "Alinya" / "raw" / "meteocat_xema"
CSV = OUT_DIR / "CJ_wind_observations.csv"
METADATA = OUT_DIR / "CJ_wind_metadata.json"


def _checked_at() -> datetime:
    value = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def fetch() -> dict:
    checked = _checked_at()
    frame = fetch_station(
        "CJ", history_days=35, variable_codes=("30", "31", "50", "51")
    )
    if frame.empty or not (frame["codi_variable"].astype(str) == "30").any():
        raise RuntimeError("XEMA CJ has no wind-speed observations in the requested period.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    export = frame.copy()
    export["data_lectura"] = export["data_lectura"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    export.to_csv(CSV, index=False)
    payload = {
        "generated_at_utc": checked.isoformat().replace("+00:00", "Z"),
        "latest_catalog_check_utc": checked.isoformat().replace("+00:00", "Z"),
        "connector": "meteocat_xema_socrata_nearest_wind",
        "responsibility": "download_and_normalize_only",
        "source": "Dades meteorològiques de la XEMA",
        "organization": "Servei Meteorològic de Catalunya / Generalitat de Catalunya",
        "official_dataset": "https://analisi.transparenciacatalunya.cat/d/nzvn-apee",
        "station_code": "CJ",
        "station_name": "Organyà",
        "station_coordinates_epsg4326": [1.33133, 42.21622],
        "reference_station": {"code": "Y4", "name": "Alinyà", "distance_km": 9.2},
        "variables": {"wind_speed_ms": "30", "wind_direction_deg": "31", "wind_gust_ms": "50", "wind_gust_direction_deg": "51"},
        "records": int(len(export)),
        "first_observation_utc": export["data_lectura"].iloc[0],
        "last_observation_utc": export["data_lectura"].iloc[-1],
        "connector_status": "verified",
        "limitation": "Observació puntual a Organyà, 9,2 km de Y4; no és vent mesurat dins la Muntanya d'Alinyà ni una superfície de vent.",
        "output_csv": str(CSV.relative_to(ROOT)),
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
