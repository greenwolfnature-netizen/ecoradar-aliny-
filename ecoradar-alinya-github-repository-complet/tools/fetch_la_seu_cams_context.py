"""Fetch a non-street PM2.5 context value from the official CAMS public WMS."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
RAW = PROJECT / "raw" / "cams"
OUTPUT = PROJECT / "indicators" / "contextual_environment.json"
LAYER_MANIFEST = PROJECT / "metadata" / "layer_manifest.json"
ENDPOINT = "https://eccharts.ecmwf.int/wms/"
LAYER = "composition_europe_pm2p5_forecast_surface"


def _get(parameters: dict) -> tuple[str, str]:
    url = ENDPOINT + "?" + urlencode(parameters)
    with urlopen(url, timeout=180) as response:
        return response.read().decode("utf-8"), url


def _default_time(capabilities: str) -> str:
    root = ET.fromstring(capabilities)
    namespace = {"wms": "http://www.opengis.net/wms"}
    for layer in root.findall(".//wms:Layer", namespace):
        name = layer.findtext("wms:Name", namespaces=namespace)
        if name != LAYER:
            continue
        for dimension in layer.findall("wms:Dimension", namespace):
            if dimension.attrib.get("name") == "time":
                return dimension.attrib["default"]
    raise RuntimeError("CAMS WMS did not expose a default time for the PM2.5 layer.")


def fetch() -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    capabilities, capabilities_url = _get(
        {"token": "public", "service": "WMS", "request": "GetCapabilities", "version": "1.3.0"}
    )
    reference_time = _default_time(capabilities)
    parameters = {
        "token": "public",
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetFeatureInfo",
        "crs": "EPSG:4326",
        "bbox": "42.30,1.40,42.42,1.54",
        "width": 101,
        "height": 101,
        "i": 50,
        "j": 50,
        "layers": LAYER,
        "query_layers": LAYER,
        "time": reference_time,
        "info_format": "text/plain",
    }
    response, query_url = _get(parameters)
    patterns = {
        "value_ug_m3": r"Value:\s*([0-9.+-]+)",
        "input_latitude": r"Input latitude:\s*([0-9.+-]+)",
        "input_longitude": r"Input longitude:\s*([0-9.+-]+)",
        "grid_latitude": r"Grid point latitude:\s*([0-9.+-]+)",
        "grid_longitude": r"Grid point longitude:\s*([0-9.+-]+)",
        "distance_km": r"Distance:\s*([0-9.+-]+)",
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, response)
        if not match:
            raise RuntimeError(f"CAMS GetFeatureInfo response is missing {key}.")
        values[key] = float(match.group(1))
    raw_path = RAW / f"pm25_context_{reference_time[:10]}.txt"
    raw_path.write_text(response)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["pm25"] = {
            "value_ug_m3": round(values["value_ug_m3"], 2),
            "reference_time_utc": reference_time,
            "input_point_epsg4326": [values["input_longitude"], values["input_latitude"]],
            "nearest_grid_point_epsg4326": [values["grid_longitude"], values["grid_latitude"]],
            "distance_to_grid_point_km": round(values["distance_km"], 2),
            "source": "CAMS European air quality forecast, ensemble PM2.5 surface layer",
            "organization": "Copernicus Atmosphere Monitoring Service / ECMWF",
            "official_urls": {
                "dataset": "https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts",
                "wms_documentation": "https://confluence.ecmwf.int/spaces/CKB/pages/208502268/WMS+for+CAMS+Global+and+European+air+quality+products",
                "capabilities": capabilities_url,
                "query": query_url,
            },
            "service_type": "WMS 1.3.0 GetFeatureInfo",
            "spatial_resolution": "0.1 degree, approximately 10 km",
            "temporal_resolution": "hourly operational analysis/forecast field",
            "license": "CC BY; Copernicus/ECMWF attribution required",
            "connector_status": "verified",
            "credentials": "none; official public WMS token",
            "interpretation": "Supramunicipal model context only. It is not an observation at La Seu d'Urgell and must not be mapped or interpreted at street level.",
            "raw_response": str(raw_path.relative_to(ROOT)),
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    manifest = json.loads(LAYER_MANIFEST.read_text())
    included = manifest.setdefault("layers_included", [])
    if "context_pm25_cams_10km" not in included:
        included.append("context_pm25_cams_10km")
    manifest["cams_context"] = payload["pm25"]
    LAYER_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    print(json.dumps(fetch()["pm25"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
