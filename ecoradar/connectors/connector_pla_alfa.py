"""Download and normalize the official municipal Pla Alfa level for Alinyà.

The connector only queries the public official ArcGIS service and returns a
DataFrame. It does not calculate or alter EcoRadar fire danger.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SERVICE = (
    "https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services/"
    "Pla_Alfa_Municipal_Avui_FL_alternatiu_VW/FeatureServer/0"
)
MUNICIPALITY_CODE = "259084"
MUNICIPALITY_NAME = "Fígols i Alinyà"
OUT_DIR = ROOT / "projectes" / "Alinya" / "raw" / "pla_alfa"
OUT_DATA = OUT_DIR / "figols_alinya_current.json"
OUT_METADATA = ROOT / "projectes" / "Alinya" / "metadata" / "pla_alfa_connector.json"


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_current_level() -> tuple[pd.DataFrame, dict]:
    """Return the current official municipal record and layer metadata."""
    metadata = _get_json(f"{SERVICE}?f=json")
    params = urlencode(
        {
            "where": f"CODIMUNI='{MUNICIPALITY_CODE}'",
            "outFields": "CODIMUNI,NOMMUNI,NOMCOMAR,PERIL_M",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    payload = _get_json(f"{SERVICE}/query?{params}")
    if payload.get("error"):
        raise RuntimeError(f"Pla Alfa service error: {payload['error']}")
    rows = [feature.get("attributes", {}) for feature in payload.get("features", [])]
    frame = pd.DataFrame.from_records(rows)
    required = {"CODIMUNI", "NOMMUNI", "NOMCOMAR", "PERIL_M"}
    if frame.empty or not required.issubset(frame.columns):
        raise RuntimeError("Official Pla Alfa query returned no complete municipal record")
    frame["CODIMUNI"] = frame["CODIMUNI"].astype(str)
    frame["PERIL_M"] = pd.to_numeric(frame["PERIL_M"], errors="raise").astype(int)
    row = frame.iloc[0]
    if row["CODIMUNI"] != MUNICIPALITY_CODE or row["NOMMUNI"] != MUNICIPALITY_NAME:
        raise RuntimeError("Official Pla Alfa response does not match Fígols i Alinyà")
    if not 0 <= int(row["PERIL_M"]) <= 4:
        raise RuntimeError("Official Pla Alfa level is outside the documented 0-4 range")
    return frame, metadata


def _checked_at() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        value = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def run() -> dict:
    frame, metadata = fetch_current_level()
    row = frame.iloc[0]
    checked_at = _checked_at()
    edit_ms = (metadata.get("editingInfo") or {}).get("dataLastEditDate")
    data_at = (
        datetime.fromtimestamp(float(edit_ms) / 1000, tz=timezone.utc)
        if edit_ms is not None
        else None
    )
    levels = {
        0: "baix",
        1: "moderat",
        2: "alt",
        3: "molt alt",
        4: "extrem",
    }
    result = {
        "schema_version": "1.0",
        "source_type": "official_operational_level",
        "official": True,
        "organization": "Cos d'Agents Rurals / Generalitat de Catalunya",
        "municipality_code": str(row["CODIMUNI"]),
        "municipality": str(row["NOMMUNI"]),
        "county": str(row["NOMCOMAR"]),
        "level": int(row["PERIL_M"]),
        "label": levels[int(row["PERIL_M"])],
        "data_at_utc": data_at.isoformat().replace("+00:00", "Z") if data_at else None,
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "status": "verified",
        "source_url": SERVICE,
        "official_page": "https://interior.gencat.cat/ca/arees_dactuacio/agents-rurals/pla-alfa/index.html",
        "service_item_id": "02c89a3c7f9a4b269aa3ddd117d48691",
        "note": "Nivell operatiu oficial municipal; no és un càlcul EcoRadar ni s'incorpora numèricament a l'índex 0-100.",
    }
    metadata_result = {
        **result,
        "connector": "pla_alfa_official_arcgis",
        "responsibility": "download_and_normalize_only",
        "service_last_edit_epoch_ms": edit_ms,
        "output": str(OUT_DATA.relative_to(ROOT)),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_METADATA.parent.mkdir(parents=True, exist_ok=True)
    OUT_DATA.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_METADATA.write_text(json.dumps(metadata_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
