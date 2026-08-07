"""Select Alinyà's freshest normalized, QA-valid detailed LST source."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
OUTPUT = PROJECT / "metadata" / "current_surface_temperature.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _landsat() -> dict | None:
    metadata_path = PROJECT / "metadata" / "landsat_connector.json"
    metadata = _read(metadata_path)
    scenes = [
        scene for scene in metadata.get("scenes", [])
        if scene.get("valid_study_pixels", 0) and scene.get("acquired_at_utc")
    ]
    tif = PROJECT / "processed" / "landsat" / "landsat_lst.tif"
    if not scenes or not tif.is_file():
        return None
    acquired = max(scene["acquired_at_utc"] for scene in scenes)
    return {
        "source_key": "landsat",
        "source": metadata.get("source", "USGS Landsat Collection 2 Level-2 Surface Temperature"),
        "organization": "United States Geological Survey",
        "acquired_at_utc": acquired,
        "resolution_m": 30,
        "normalized_tif": tif.relative_to(ROOT).as_posix(),
        "quality": "QA_PIXEL applied; median composition of valid summer observations",
        "source_metadata": metadata_path.relative_to(ROOT).as_posix(),
    }


def _ecostress() -> dict | None:
    metadata_path = PROJECT / "metadata" / "ecostress_connector.json"
    metadata = _read(metadata_path)
    tif = ROOT / str(metadata.get("normalized_tif", ""))
    if metadata.get("connector_status") != "verified" or not metadata.get("acquired_at_utc") or not tif.is_file():
        return None
    return {
        "source_key": "ecostress",
        "source": metadata.get("source", "NASA/JPL ECOSTRESS L2T Land Surface Temperature V3"),
        "organization": metadata.get("organization", "NASA/JPL ECOSTRESS; NASA LP DAAC"),
        "acquired_at_utc": metadata["acquired_at_utc"],
        "resolution_m": metadata.get("resolution_m", 70),
        "normalized_tif": tif.relative_to(ROOT).as_posix(),
        "quality": "mandatory QC, cloud and water masks applied",
        "source_metadata": metadata_path.relative_to(ROOT).as_posix(),
    }


def select() -> dict:
    candidates = [item for item in (_landsat(), _ecostress()) if item]
    if not candidates:
        raise RuntimeError("No normalized detailed surface-temperature source is available for Alinyà.")
    selected = max(candidates, key=lambda item: _instant(item["acquired_at_utc"]))
    payload = {
        "schema_version": "1.0",
        "selection_rule": "freshest normalized QA-valid local detailed LST; coarse contextual products are excluded",
        "selected": selected,
        "eligible_sources": [
            {key: item[key] for key in ("source_key", "source", "acquired_at_utc", "resolution_m")}
            for item in sorted(candidates, key=lambda item: _instant(item["acquired_at_utc"]), reverse=True)
        ],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(select(), ensure_ascii=False, indent=2))
