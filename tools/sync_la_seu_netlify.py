"""Synchronize the generated standalone EcoRadar Urban page to Netlify."""

from __future__ import annotations

import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
MAPS = PROJECT / "maps"
SOURCE = MAPS / "ecoradar_urba_la_seu_interactiu.html"
TARGET = MAPS / "ecoradar-la-seu-netlify"
FUNCTION_SOURCE = ROOT / "netlify" / "functions"


def sync() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    html = SOURCE.read_text(encoding="utf-8").replace(
        "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js",
        "./vendor/d3.min.js",
    )
    (TARGET / "index.html").write_text(html, encoding="utf-8")
    (TARGET / "metadata").mkdir(exist_ok=True)
    for name in (
        "current_fire_danger.json",
        "biodiversity_urban_potential.json",
        "daily_readings.json",
        "daily_history.json",
    ):
        source = PROJECT / "metadata" / name
        if source.exists():
            shutil.copy2(source, TARGET / "metadata" / name)
    (TARGET / "history").mkdir(exist_ok=True)
    for name in ("daily_readings_observations.jsonl", "daily_readings_checks.jsonl"):
        source = PROJECT / "history" / name
        if source.exists():
            shutil.copy2(source, TARGET / "history" / name)
    (TARGET / "docs").mkdir(exist_ok=True)
    shutil.copy2(PROJECT / "metadata" / "data_sources_matrix.md", TARGET / "docs" / "data-sources-matrix.md")
    shutil.copy2(ROOT / "docs" / "data_sources" / "fire" / "current-wildfire-danger-urban.md", TARGET / "docs" / "current-fire-danger-source.md")
    shutil.copy2(ROOT / "docs" / "data_sources" / "urban_daily_readings.md", TARGET / "docs" / "urban-daily-readings-source.md")
    target_functions = TARGET / "netlify" / "functions"
    target_functions.mkdir(parents=True, exist_ok=True)
    for source in FUNCTION_SOURCE.glob("*.mjs"):
        shutil.copy2(source, target_functions / source.name)
    summary = json.loads((PROJECT / "indicators" / "current_fire_danger.json").read_text(encoding="utf-8"))["summary"]
    print(json.dumps({"index": str((TARGET / 'index.html').relative_to(ROOT)), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    sync()
