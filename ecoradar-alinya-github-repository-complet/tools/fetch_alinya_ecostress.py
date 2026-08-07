"""Check and normalize official ECOSTRESS L2T V3 LST for Alinyà."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd

import fetch_la_seu_ecostress_expanded as connector


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
STUDY = PROJECT / "processed" / "study_area.gpkg"


def configure() -> tuple[float, float, float, float]:
    output = PROJECT / "processed" / "ecostress"
    connector.PROJECT = PROJECT
    connector.OUTPUT_DIR = output
    connector.OUTPUT_TIF = output / "ecostress_lst.tif"
    connector.OUTPUT_NPZ = output / "ecostress_lst.npz"
    connector.METADATA = PROJECT / "metadata" / "ecostress_connector.json"
    study = gpd.read_file(STUDY).to_crs(4326)
    return tuple(float(value) for value in study.total_bounds)


def main() -> None:
    bbox = configure()
    result = connector.fetch(bbox_override=bbox)
    if result.get("scope") != "Muntanya d'Alinyà":
        result["scope"] = "Muntanya d'Alinyà"
        connector.METADATA.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
