"""Fetch and normalize the latest CREAF ForestDrought grid for La Seu.

The connector checks the public CREAF/EMF daily GeoPackage repository, reads
only the study-area subset and preserves the model date separately from the
time at which EcoRadar checked the service. It performs no EcoRadar analysis.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import geopandas as gpd
import pyogrio
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
MANIFEST = PROJECT / "metadata" / "project_manifest.json"
RAW_DIR = PROJECT / "raw" / "creaf_forestdrought"
OUTPUT_GEOJSON = RAW_DIR / "forestdrought_latest.geojson"
OUTPUT_CSV = RAW_DIR / "forestdrought_latest.csv"
METADATA = PROJECT / "metadata" / "creaf_forestdrought_connector.json"

APP_URL = "https://laboratoriforestal.creaf.cat/forestdrought_app/"
REPOSITORY = "https://data-emf.creaf.cat/public/gpkg/daily_modelled_forests"
FIELDS = ["date", "DDS", "LFMC", "DFMC", "SFP", "CFP", "REW"]
SOURCE_CRS = "EPSG:25830"


def _checked_at() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        value = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _exists(url: str) -> bool:
    request = Request(
        url,
        method="HEAD",
        headers={"User-Agent": "EcoRadar/1.0"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            return 200 <= response.status < 300
    except HTTPError as error:
        if error.code == 404:
            return False
        raise


def _latest_url(today: date, lookback_days: int = 30) -> tuple[date, str]:
    for days_back in range(lookback_days + 1):
        candidate = today - timedelta(days=days_back)
        url = f"{REPOSITORY}/{candidate:%Y%m%d}.gpkg"
        if _exists(url):
            return candidate, url
    raise RuntimeError(
        f"No CREAF ForestDrought GeoPackage was published in the {lookback_days + 1}-day search window."
    )


def _bbox_epsg25830() -> tuple[float, float, float, float]:
    manifest = _read_json(MANIFEST)
    west, south, east, north = (
        float(value)
        for value in manifest["study_area"]["expanded_urban_bbox_epsg4326"]
    )
    transformer = Transformer.from_crs(4326, 25830, always_xy=True)
    corners = [
        transformer.transform(x, y)
        for x in (west, east)
        for y in (south, north)
    ]
    return (
        min(x for x, _ in corners),
        min(y for _, y in corners),
        max(x for x, _ in corners),
        max(y for _, y in corners),
    )


def _read_remote_subset(
    source_url: str,
    model_date: date,
) -> gpd.GeoDataFrame:
    virtual_path = f"/vsicurl/{source_url}"
    layer = f"{model_date:%Y%m%d}"
    frame = pyogrio.read_dataframe(
        virtual_path,
        layer=layer,
        columns=FIELDS,
        bbox=_bbox_epsg25830(),
    )
    if frame.empty:
        raise RuntimeError(
            "The latest CREAF ForestDrought file has no forest grid cells in the expanded La Seu scope."
        )
    missing = [field for field in FIELDS if field not in frame.columns]
    if missing:
        raise RuntimeError(
            f"CREAF ForestDrought schema is missing required fields: {', '.join(missing)}"
        )
    if frame.crs is None:
        frame = frame.set_crs(SOURCE_CRS)
    elif frame.crs.to_string() != SOURCE_CRS:
        frame = frame.to_crs(SOURCE_CRS)
    return frame


def fetch() -> gpd.GeoDataFrame:
    checked = _checked_at()
    today_local = checked.astimezone(ZoneInfo("Europe/Madrid")).date()
    existing = _read_json(METADATA)
    try:
        model_date, source_url = _latest_url(today_local)
        frame = _read_remote_subset(source_url, model_date)
    except (HTTPError, URLError, OSError, RuntimeError) as error:
        fallback_exists = OUTPUT_GEOJSON.is_file()
        payload = {
            **existing,
            "latest_catalog_check_utc": _iso(checked),
            "connector_status": (
                "service_unavailable" if fallback_exists else "blocked"
            ),
            "status_note": (
                "CREAF/EMF could not be checked; the last normalized file is retained."
                if fallback_exists
                else "CREAF/EMF could not be checked and no normalized fallback exists."
            ),
            "error": str(error),
            "updated": False,
        }
        _write_json(METADATA, payload)
        if fallback_exists:
            return gpd.read_file(OUTPUT_GEOJSON)
        raise

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output = frame.to_crs(4326)
    output.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
    frame.drop(columns="geometry").to_csv(OUTPUT_CSV, index=False)
    payload = {
        "generated_at_utc": _iso(checked),
        "latest_catalog_check_utc": _iso(checked),
        "connector": "creaf_forestdrought_daily_modelled_forests",
        "responsibility": "discover_download_subset_and_normalize_only",
        "scope": "La Seu d'Urgell, Castellciutat and Sant Antoni",
        "source": "ForestDrought daily modelled forests",
        "organization": "CREAF, Ecosystem Modelling Facility (EMF)",
        "provider_role": "modelled forest drought and fire-potential data provider",
        "application_url": APP_URL,
        "repository_url": REPOSITORY + "/",
        "source_url": source_url,
        "service_type": "public HTTPS GeoPackage repository",
        "model_date": model_date.isoformat(),
        "data_at_utc": f"{model_date.isoformat()}T00:00:00Z",
        "crs": SOURCE_CRS,
        "cell_size_m": 500,
        "geometry_type": "forest grid cell centre points",
        "variables": FIELDS,
        "features": int(len(frame)),
        "normalized_geojson": str(OUTPUT_GEOJSON.relative_to(ROOT)),
        "normalized_csv": str(OUTPUT_CSV.relative_to(ROOT)),
        "usage_license": (
            "Public download and reuse stated by CREAF; formal license "
            "identifier pending verification."
        ),
        "connector_status": "verified",
        "status_note": (
            "Latest published model file found by descending date search. "
            "The model date is preserved separately from the daily check."
        ),
        "updated": existing.get("model_date") != model_date.isoformat(),
    }
    _write_json(METADATA, payload)
    return frame


def main() -> None:
    frame = fetch()
    metadata = _read_json(METADATA)
    print(
        json.dumps(
            {
                "connector_status": metadata.get("connector_status"),
                "checked_at_utc": metadata.get("latest_catalog_check_utc"),
                "model_date": metadata.get("model_date"),
                "features": len(frame),
                "source_url": metadata.get("source_url"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
