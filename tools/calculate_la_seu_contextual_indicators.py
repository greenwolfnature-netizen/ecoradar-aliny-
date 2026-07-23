"""Aggregate coarse CDSE context grids without inventing urban detail."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
CONNECTOR = PROJECT / "metadata" / "cdse_context_connector.json"
OUTPUT = PROJECT / "indicators" / "contextual_environment.json"
LAYER_MANIFEST = PROJECT / "metadata" / "layer_manifest.json"


def _aggregate(dataset: dict) -> tuple[float, int]:
    with rasterio.open(ROOT / dataset["raw_path"]) as source:
        values, mask = source.read()
    valid = (mask > 0) & np.isfinite(values)
    return float(np.median(values[valid])), int(valid.sum())


def calculate() -> dict:
    connector = json.loads(CONNECTOR.read_text())
    existing = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    for key, dataset in connector["datasets"].items():
        if dataset.get("connector_status") != "verified":
            continue
        median, cells = _aggregate(dataset)
        if key == "night_lst":
            kelvin = median * 0.01 + 273.15
            if not 180 <= kelvin <= 370:
                raise RuntimeError(f"Scaled CLMS LST value {kelvin} is outside a defensible Kelvin range.")
            existing[key] = {
                "value_c": round(kelvin - 273.15, 1),
                "value_k": round(kelvin, 2),
                "raw_median_dn": round(median, 1),
                "scaling": "K = DN*0.01 + 273.15, according to the official CLMS product metadata",
                "aggregation": f"spatial median of {cells} valid native-scale context cells",
                **dataset,
                "interpretation": "Night-time land surface temperature context; not air temperature and not street-scale exposure.",
            }
        elif key == "soil_moisture":
            percent = median * 0.5
            if not 0 <= percent <= 100:
                raise RuntimeError(f"Scaled CLMS SSM value {percent} is outside the documented 0-100% range.")
            existing[key] = {
                "value_pct_saturation": round(percent, 1),
                "raw_median_dn": round(median, 1),
                "scaling": "percent saturation = DN*0.5, according to the official CLMS product metadata",
                "aggregation": f"spatial median of {cells} valid native-scale context cells",
                **dataset,
                "interpretation": "Top-soil saturation context at 1 km; not NDMI, irrigation need or street-scale soil condition.",
            }
        elif key == "no2":
            if not -0.001 <= median <= 0.003:
                raise RuntimeError(f"Sentinel-5P NO2 value {median} is outside a defensible column range.")
            existing[key] = {
                "value_mol_m2": float(f"{median:.6g}"),
                "aggregation": f"spatial median of {cells} valid native-scale context cells",
                **dataset,
                "interpretation": "Tropospheric NO2 column context; not surface concentration in ug/m3 and not a street pollution map.",
            }
    existing["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    OUTPUT.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n")

    manifest = json.loads(LAYER_MANIFEST.read_text())
    included = manifest.setdefault("layers_included", [])
    for key in ("night_lst", "soil_moisture", "no2"):
        if key in existing:
            layer = f"context_{key}_coarse_official"
            if layer not in included:
                included.append(layer)
    manifest["coarse_context_indicators"] = {key: existing[key] for key in ("night_lst", "soil_moisture", "no2") if key in existing}
    manifest["layers_omitted"] = [
        "qualitat_aire_local_o_carrer" if item == "qualitat_aire" else item
        for item in manifest.get("layers_omitted", [])
    ]
    LAYER_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return existing


def main() -> None:
    result = calculate()
    summary = {
        "night_lst_c": result.get("night_lst", {}).get("value_c"),
        "soil_moisture_pct": result.get("soil_moisture", {}).get("value_pct_saturation"),
        "no2_mol_m2": result.get("no2", {}).get("value_mol_m2"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
