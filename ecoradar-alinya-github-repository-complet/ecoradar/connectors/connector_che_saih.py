"""Download and normalize current CHE/SAIH Ebro station observations.

The connector only accesses the official source, downloads the current values,
normalizes the two gauging-station records and returns a DataFrame. It performs
no hydrological analysis and derives no warning level.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
OUTPUT_DIR = PROJECT / "raw" / "che_saih"
ENDPOINT = "https://www.saihebro.com/api/ficha/procesarTablaValoresActuales?estacion={station}"
MINIGRAPH_ENDPOINT = "https://www.saihebro.com/api/ficha/getDatosMinigraficaSenal?tag={tag}&tipoTag={signal_type}"
LOCAL_TZ = ZoneInfo("Europe/Madrid")
USER_AGENT = "EcoRadar/1.0 (+https://github.com/greenwolfnature-netizen/ecoradar-seu)"

STATIONS = {
    "A022": {
        "station_name": "Riu Valira a la Seu d'Urgell",
        "river": "Valira",
        "signal_tag": "A022O65QRIO1",
        "level_tag": "A022O17NRIO1",
        "precipitation_24h_tag": "A022O83PA24H",
        "latitude": 42.360541,
        "longitude": 1.453061,
        "official_url": "https://www.saihebro.com/tiempo-real/estacion-aforos-A022-valira-seu",
    },
    "A023": {
        "station_name": "Riu Segre a la Seu d'Urgell",
        "river": "Segre",
        "signal_tag": "A023O65QRIO1",
        "level_tag": "A023O17NRIO1",
        "precipitation_24h_tag": None,
        "latitude": 42.352429,
        "longitude": 1.459758,
        "official_url": "https://www.saihebro.com/tiempo-real/estacion-aforos-A023-segre-seu",
    },
}


class _CurrentValuesParser(HTMLParser):
    """Collect the accessibility labels and signal link from each table row."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[dict[str, str]]] = []
        self._row: list[dict[str, str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._row.append(
                {
                    "aria_label": attributes.get("aria-label", ""),
                    "href": "",
                    "minigraph_endpoint": "",
                    "background": attributes.get("style", ""),
                }
            )
        elif tag == "a" and self._row:
            self._row[-1]["href"] = attributes.get("href", "")
        elif tag == "div" and self._row and attributes.get("url-ajax"):
            self._row[-1]["minigraph_endpoint"] = attributes["url-ajax"]

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _checked_at_utc() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        return datetime.fromisoformat(configured.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _parse_decimal(value: str) -> float:
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
    if not match:
        raise ValueError(f"SAIH value contains no number: {value!r}")
    return float(match.group(0).replace(",", "."))


def parse_current_streamflow(payload: dict, station_code: str) -> dict:
    """Normalize the current discharge row from one official response."""

    html = payload.get("VALORES_ACTUALES")
    if not isinstance(html, str) or not html.strip():
        raise RuntimeError(f"SAIH response for {station_code} has no VALORES_ACTUALES table")
    parser = _CurrentValuesParser()
    parser.feed(html)
    expected_tag = STATIONS[station_code]["signal_tag"]
    for row in parser.rows:
        labels = [cell["aria_label"] for cell in row]
        if not labels or not labels[0].lower().startswith("señal caudal "):
            continue
        hrefs = " ".join(cell["href"] for cell in row)
        if expected_tag not in hrefs:
            continue
        value_label = next((label[6:] for label in labels if label.startswith("Valor ")), None)
        date_label = next((label[6:] for label in labels if label.startswith("Fecha ")), None)
        if not value_label or not date_label:
            raise RuntimeError(f"Incomplete SAIH discharge row for {station_code}")
        observed_local = datetime.strptime(date_label, "%d/%m/%Y %H:%M").replace(tzinfo=LOCAL_TZ)
        observed_utc = observed_local.astimezone(timezone.utc)
        station = STATIONS[station_code]
        return {
            "station_code": station_code,
            "station_name": station["station_name"],
            "river": station["river"],
            "signal_tag": expected_tag,
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "discharge_m3_s": _parse_decimal(value_label),
            "observed_at_local": observed_local.isoformat(),
            "observed_at_utc": observed_utc.isoformat().replace("+00:00", "Z"),
            "provisional": True,
            "official_url": station["official_url"],
            "endpoint": ENDPOINT.format(station=station_code),
        }
    raise RuntimeError(f"No current discharge signal {expected_tag} found for {station_code}")


def parse_current_signals(payload: dict, station_code: str) -> dict[str, dict]:
    """Normalize all operational signals used by EcoRadar for one station.

    The returned values remain source observations. No thresholds, risk classes
    or trend interpretation are calculated in this connector.
    """

    html = payload.get("VALORES_ACTUALES")
    if not isinstance(html, str) or not html.strip():
        raise RuntimeError(f"SAIH response for {station_code} has no VALORES_ACTUALES table")
    parser = _CurrentValuesParser()
    parser.feed(html)
    parsed: dict[str, dict] = {}
    prefixes = {
        "discharge": "señal caudal ",
        "level": "señal nivel ",
        "precipitation_24h": "señal precip. 24h.",
    }
    for row in parser.rows:
        labels = [cell["aria_label"] for cell in row]
        if not labels:
            continue
        first = labels[0].lower()
        kind = next((name for name, prefix in prefixes.items() if first.startswith(prefix)), None)
        if kind is None:
            continue
        value_label = next((label[6:] for label in labels if label.startswith("Valor ")), None)
        date_label = next((label[6:] for label in labels if label.startswith("Fecha ")), None)
        trend_label = next((label[10:] for label in labels if label.startswith("Tendencia ")), None)
        if not value_label or not date_label:
            continue
        hrefs = " ".join(cell["href"] for cell in row)
        tag_match = re.search(r"([A-Z]\d{3}O[A-Z0-9]+)", hrefs)
        if not tag_match:
            continue
        observed_local = datetime.strptime(date_label, "%d/%m/%Y %H:%M").replace(tzinfo=LOCAL_TZ)
        observed_utc = observed_local.astimezone(timezone.utc)
        mini_path = next(
            (cell["minigraph_endpoint"] for cell in row if cell["minigraph_endpoint"]),
            "",
        )
        parsed[kind] = {
            "signal_kind": kind,
            "signal_tag": tag_match.group(1),
            "value": _parse_decimal(value_label),
            "unit": (
                "m3/s" if kind == "discharge"
                else "m" if kind == "level"
                else "mm"
            ),
            "observed_at_local": observed_local.isoformat(),
            "observed_at_utc": observed_utc.isoformat().replace("+00:00", "Z"),
            "source_trend": trend_label.lower() if trend_label else None,
            "minigraph_path": mini_path or None,
            "official_cell_style": next(
                (cell["background"] for cell in row if cell["background"]),
                None,
            ),
        }
    required = {"discharge", "level"}
    if not required.issubset(parsed):
        raise RuntimeError(
            f"SAIH response for {station_code} is missing signals: {sorted(required.difference(parsed))}"
        )
    return parsed


def _download_json(url: str) -> object:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _recent_values(signal: dict) -> list[float] | None:
    path = signal.get("minigraph_path")
    if not path:
        return None
    try:
        payload = _download_json(f"https://www.saihebro.com{path}")
    except Exception:
        return None
    if not isinstance(payload, list):
        return None
    values: list[float] = []
    for value in payload:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number:
            values.append(number)
    return values or None


def fetch_current_hydrology(
    station_codes: tuple[str, ...] = ("A022", "A023"),
) -> pd.DataFrame:
    """Download current discharge, level and available rainfall observations."""

    records = []
    for station_code in station_codes:
        if station_code not in STATIONS:
            raise ValueError(f"Unsupported SAIH station: {station_code}")
        payload = _download_json(ENDPOINT.format(station=station_code))
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected SAIH response for {station_code}")
        signals = parse_current_signals(payload, station_code)
        discharge = signals["discharge"]
        level = signals["level"]
        rain = signals.get("precipitation_24h")
        station = STATIONS[station_code]
        flow_recent = _recent_values(discharge)
        level_recent = _recent_values(level)
        records.append(
            {
                "station_code": station_code,
                "station_name": station["station_name"],
                "river": station["river"],
                "signal_tag": discharge["signal_tag"],
                "level_signal_tag": level["signal_tag"],
                "latitude": station["latitude"],
                "longitude": station["longitude"],
                "discharge_m3_s": discharge["value"],
                "level_m": level["value"],
                "precipitation_24h_mm": rain["value"] if rain else None,
                "observed_at_local": discharge["observed_at_local"],
                "observed_at_utc": discharge["observed_at_utc"],
                "level_observed_at_utc": level["observed_at_utc"],
                "precipitation_observed_at_utc": rain["observed_at_utc"] if rain else None,
                "source_flow_trend": discharge.get("source_trend"),
                "source_level_trend": level.get("source_trend"),
                "recent_flow_values_json": json.dumps(flow_recent) if flow_recent else None,
                "recent_level_values_json": json.dumps(level_recent) if level_recent else None,
                "recent_sequence_has_timestamps": False,
                "provisional": True,
                "official_url": station["official_url"],
                "endpoint": ENDPOINT.format(station=station_code),
            }
        )
    frame = pd.DataFrame.from_records(records)
    if frame.empty or set(frame["station_code"]) != set(station_codes):
        raise RuntimeError("SAIH did not return all requested hydrological stations")
    return frame.sort_values("station_code").reset_index(drop=True)


def fetch_current_streamflow(
    station_codes: tuple[str, ...] = ("A022", "A023"),
) -> pd.DataFrame:
    """Download both official station responses and return normalized records."""

    return fetch_current_hydrology(station_codes)


def run() -> dict:
    """Persist the normalized connector output and its source metadata."""

    checked_at = _checked_at_utc()
    frame = fetch_current_streamflow()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "A022_A023_current.csv"
    metadata_path = OUTPUT_DIR / "che_saih_streamflow.json"
    frame.to_csv(csv_path, index=False)
    payload = {
        "generated_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "connector": "che_saih_current_hydrology",
        "responsibility": "download_and_normalize_only",
        "source": "SAIH Ebro · valors actuals d'estacions d'aforament",
        "organization": "Confederació Hidrogràfica de l'Ebre / MITECO",
        "official_stations": {
            code: {
                "river": STATIONS[code]["river"],
                "official_url": STATIONS[code]["official_url"],
                "discharge_signal_tag": STATIONS[code]["signal_tag"],
                "level_signal_tag": STATIONS[code]["level_tag"],
                "precipitation_24h_signal_tag": STATIONS[code]["precipitation_24h_tag"],
            }
            for code in STATIONS
        },
        "service_type": "public HTTP current-values endpoint",
        "update_frequency": "15 minutes",
        "credentials_required": False,
        "usage_license": "Exact open-data license not declared on inspected endpoint; CHE/SAIH attribution retained.",
        "variables": [
            "instantaneous discharge",
            "instantaneous level",
            "24-hour station precipitation when published",
            "source trend glyph",
            "public recent minigraph samples without individual timestamps",
        ],
        "provisionality": "Real-time data are unfiltered, provisional and subject to CHE hydrological review.",
        "recent_series_limitation": "The public minigraph sequence has no individual timestamps. EcoRadar does not assign invented dates to it.",
        "connector_status": "verified",
        "records": int(len(frame)),
        "latest_observation_utc": frame["observed_at_utc"].max(),
        "output_csv": str(csv_path.relative_to(ROOT)),
        "methodology": "docs/data_sources/che_saih_streamflow_la_seu.md",
    }
    metadata_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
