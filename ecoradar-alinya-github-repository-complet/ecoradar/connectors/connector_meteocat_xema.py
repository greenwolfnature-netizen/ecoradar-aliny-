"""Download and normalize public XEMA station observations.

The connector has one responsibility: read the official Generalitat Socrata
dataset, normalize its tabular fields and return a DataFrame. It performs no
fire-danger analysis.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "current_fire_danger.json"
def fetch_station(
    station_code: str,
    *,
    history_days: int,
    dataset_id: str = "nzvn-apee",
    variable_codes: tuple[str, ...] = ("30", "31", "32", "33", "35", "50", "51"),
) -> pd.DataFrame:
    start = datetime.now(timezone.utc) - timedelta(days=history_days)
    variable_clause = " OR ".join(f"codi_variable='{value}'" for value in variable_codes)
    where = (
        f"codi_estacio='{station_code}' AND "
        f"data_lectura>='{start.strftime('%Y-%m-%dT%H:%M:%S')}' AND "
        f"({variable_clause})"
    )
    params = urlencode(
        {
            "$limit": 20000,
            "$order": "data_lectura ASC",
            "$where": where,
        }
    )
    url = f"https://analisi.transparenciacatalunya.cat/resource/{dataset_id}.json?{params}"
    with urlopen(url, timeout=180) as response:
        records = json.loads(response.read().decode("utf-8"))
    frame = pd.DataFrame.from_records(records)
    required = {
        "codi_estacio",
        "codi_variable",
        "data_lectura",
        "valor_lectura",
        "codi_base",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise RuntimeError(f"XEMA response missing columns: {sorted(missing)}")
    frame = frame.reindex(
        columns=[
            "codi_estacio",
            "codi_variable",
            "data_lectura",
            "valor_lectura",
            "codi_estat",
            "codi_base",
        ]
    )
    frame["data_lectura"] = pd.to_datetime(frame["data_lectura"], utc=True)
    frame["valor_lectura"] = pd.to_numeric(frame["valor_lectura"], errors="coerce")
    frame["codi_estat"] = frame["codi_estat"].fillna("")
    return frame.dropna(subset=["valor_lectura"]).sort_values("data_lectura")


def run(location: str) -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    station = config["stations"][location]
    xema = config["xema"]
    out_dir = ROOT / "projectes" / station["project"] / "raw" / "meteocat_xema"
    frame = fetch_station(
        station["code"],
        history_days=int(xema["history_days"]),
        dataset_id=xema["dataset_id"],
        variable_codes=tuple(str(value) for value in xema["variables"].values()),
    )
    if frame.empty:
        raise RuntimeError(f"No XEMA observations returned for station {station['code']}")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{station['code']}_observations.csv"
    metadata_path = out_dir / f"{station['code']}_metadata.json"
    export = frame.copy()
    export["data_lectura"] = export["data_lectura"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    export.to_csv(csv_path, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "connector": "meteocat_xema_socrata",
        "responsibility": "download_and_normalize_only",
        "source": "Dades meteorològiques de la XEMA",
        "organization": "Servei Meteorològic de Catalunya / Generalitat de Catalunya",
        "official_dataset": f"https://analisi.transparenciacatalunya.cat/d/{xema['dataset_id']}",
        "station_code": station["code"],
        "station_name": station["name"],
        "records": int(len(export)),
        "first_observation_utc": export["data_lectura"].iloc[0],
        "last_observation_utc": export["data_lectura"].iloc[-1],
        "variables": xema["variables"],
        "validation_note": "Blank codi_estat means validation has not started; T means pending; V means validated.",
        "connector_status": "verified",
        "output_csv": str(csv_path.relative_to(ROOT)),
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--location", choices=("la_seu_urba", "alinya"), default="la_seu_urba")
    args = parser.parse_args()
    print(json.dumps(run(args.location), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
