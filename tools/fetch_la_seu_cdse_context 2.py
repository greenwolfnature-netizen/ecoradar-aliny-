"""Download coarse official CDSE context rasters for La Seu d'Urgell.

The connector preserves native scientific scale: outputs are deliberately tiny
context grids and are never suitable for street mapping. It performs no final
indicator aggregation.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
from rasterio.io import MemoryFile

from fetch_la_seu_cdse_sentinel2 import _credentials, _token


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
RAW = PROJECT / "raw" / "cdse_context"
METADATA = PROJECT / "metadata" / "cdse_context_connector.json"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

PRODUCTS = {
    "night_lst": {
        "data_type": "byoc-12225aec-26dd-4e2c-bbfd-994c253c1ba8",
        "band": "LST",
        "bounds": [1.40, 42.32, 1.52, 42.40],
        "width": 4,
        "height": 4,
        "hour_utc": 0,
        "lookback_days": 20,
        "source": "CLMS Land Surface Temperature global 3 km hourly v3",
        "official_url": "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/clms/bio-geophysical-parameters/temperature-and-reflectance/land-surface-temperature/lst_global_3km_hourly_v3.html",
        "native_resolution": "approximately 3 km",
        "temporal_resolution": "hourly",
        "units": "encoded INT16; K = DN*0.01 + 273.15",
    },
    "soil_moisture": {
        "data_type": "byoc-df9e9783-f580-433a-b798-3acd2760b94e",
        "band": "SSM",
        "bounds": [1.42, 42.33, 1.50, 42.39],
        "width": 6,
        "height": 6,
        "hour_utc": 12,
        "lookback_days": 20,
        "source": "CLMS Surface Soil Moisture Europe 1 km daily v1",
        "official_url": "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/clms/bio-geophysical-parameters/soil-moisture/surface-soil-moisture/ssm_europe_1km_daily_v1.html",
        "native_resolution": "1 km",
        "temporal_resolution": "daily",
        "units": "encoded UINT8; percent saturation = DN*0.5",
    },
    "no2": {
        "data_type": "sentinel-5p-l2",
        "band": "NO2",
        "bounds": [1.35, 42.27, 1.57, 42.45],
        "width": 4,
        "height": 4,
        "hour_utc": 12,
        "lookback_days": 20,
        "source": "Copernicus Sentinel-5P TROPOMI Level-2 NO2",
        "official_url": "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S5PL2.html",
        "native_resolution": "kilometric swath; substantially coarser than streets",
        "temporal_resolution": "daily overpass",
        "units": "mol/m2 tropospheric column",
        "processing": {"minQa": 75},
    },
}


def _request_payload(definition: dict, date: datetime) -> dict:
    start = date.replace(hour=definition["hour_utc"], minute=0, second=0, microsecond=0)
    if definition["data_type"] == "sentinel-5p-l2" or definition["band"] == "SSM":
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    else:
        end = start + timedelta(hours=1)
    data = {
        "type": definition["data_type"],
        "dataFilter": {
            "timeRange": {
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": end.isoformat().replace("+00:00", "Z"),
            },
            "mosaickingOrder": "mostRecent",
        },
    }
    if definition.get("processing"):
        data["processing"] = definition["processing"]
    band = definition["band"]
    evalscript = f"""//VERSION=3
function setup() {{
  return {{input: [\"{band}\", \"dataMask\"], output: {{bands: 2, sampleType: \"FLOAT32\"}}}};
}}
function evaluatePixel(s) {{ return [s.{band}, s.dataMask]; }}
"""
    return {
        "input": {
            "bounds": {
                "bbox": definition["bounds"],
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [data],
        },
        "output": {
            "width": definition["width"],
            "height": definition["height"],
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
        },
        "evalscript": evalscript,
    }


def _download(token: str, payload: dict) -> bytes:
    request = Request(
        PROCESS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/tiff",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=300) as response:
            return response.read()
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"CDSE context Process API failed ({error.code}): {body[:1000]}") from error


def _valid_count(content: bytes) -> tuple[int, float, float]:
    with MemoryFile(content) as memory:
        with memory.open() as source:
            values, mask = source.read()
    valid = (mask > 0) & np.isfinite(values)
    if not np.any(valid):
        return 0, float("nan"), float("nan")
    return int(valid.sum()), float(np.min(values[valid])), float(np.max(values[valid]))


def fetch(credentials_file: str | None) -> dict:
    client_id, client_secret = _credentials(credentials_file)
    if not client_id or not client_secret:
        raise RuntimeError("Missing COPERNICUS_CLIENT_ID/COPERNICUS_CLIENT_SECRET or credentials file.")
    token = _token(client_id, client_secret)
    RAW.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    datasets = {}
    for key, definition in PRODUCTS.items():
        selected = None
        errors = []
        for offset in range(1, definition["lookback_days"] + 1):
            date = today - timedelta(days=offset)
            payload = _request_payload(definition, date)
            try:
                content = _download(token, payload)
                valid_count, minimum, maximum = _valid_count(content)
            except RuntimeError as error:
                errors.append({"date": date.date().isoformat(), "error": str(error)})
                continue
            if valid_count == 0:
                continue
            path = RAW / f"{key}_{date.date().isoformat()}.tif"
            path.write_bytes(content)
            selected = {
                "source": definition["source"],
                "official_url": definition["official_url"],
                "service_type": "OAuth2 + Sentinel Hub Process API",
                "data_type": definition["data_type"],
                "band": definition["band"],
                "reference_date": date.date().isoformat(),
                "request": payload,
                "raw_path": str(path.relative_to(ROOT)),
                "crs": "EPSG:4326",
                "native_resolution": definition["native_resolution"],
                "output_grid": f"{definition['width']}x{definition['height']} context cells",
                "temporal_resolution": definition["temporal_resolution"],
                "units": definition["units"],
                "valid_cells": valid_count,
                "raw_minimum": minimum,
                "raw_maximum": maximum,
                "license": "Copernicus data policy; free, full and open use with attribution",
                "connector_status": "verified",
                "credentials": "CDSE OAuth2 client_credentials; secret not persisted",
                "map_policy": "context aggregate only; never render as a street raster",
            }
            break
        if selected is None:
            datasets[key] = {
                "source": definition["source"],
                "official_url": definition["official_url"],
                "connector_status": "service_unavailable",
                "attempted_days": definition["lookback_days"],
                "errors": errors[-3:],
                "map_policy": "not included",
            }
        else:
            datasets[key] = selected
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "organization": "Copernicus Data Space Ecosystem / CLMS / ESA",
        "responsibility": "download_and_normalize_context_grids_only",
        "datasets": datasets,
    }
    METADATA.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials-file")
    parser.add_argument("--delete-credentials-file", action="store_true")
    args = parser.parse_args()
    try:
        result = fetch(args.credentials_file)
        print(json.dumps({key: value.get("connector_status") for key, value in result["datasets"].items()}, ensure_ascii=False, indent=2))
    finally:
        if args.delete_credentials_file and args.credentials_file:
            Path(args.credentials_file).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
