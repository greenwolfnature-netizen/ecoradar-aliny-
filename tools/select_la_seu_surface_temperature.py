"""Select the freshest normalized detailed LST source for La Seu.

Only sources with local normalized rasters are eligible. Coarse contextual
products such as CLMS 3 km LST and ERA5-Land are deliberately excluded.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
OUTPUT = PROJECT / "metadata" / "current_surface_temperature.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _candidate(
    *,
    key: str,
    metadata_path: Path,
    default_label: str,
    default_organization: str,
    default_quality: str,
) -> dict | None:
    metadata = _read(metadata_path)
    acquired = metadata.get("acquired_at_utc")
    tif = ROOT / str(metadata.get("normalized_tif", ""))
    npz = ROOT / str(metadata.get("normalized_npz", ""))
    if (
        metadata.get("connector_status") != "verified"
        or not acquired
        or not tif.is_file()
        or not npz.is_file()
    ):
        return None
    return {
        "source_key": key,
        "source": metadata.get("source", default_label),
        "organization": metadata.get("organization", default_organization),
        "acquired_at_utc": acquired,
        "resolution_m": metadata.get("resolution_m"),
        "normalized_tif": tif.relative_to(ROOT).as_posix(),
        "normalized_npz": npz.relative_to(ROOT).as_posix(),
        "quality": default_quality,
        "license": metadata.get("license"),
        "source_metadata": metadata_path.relative_to(ROOT).as_posix(),
    }


def select() -> dict:
    candidates = [
        candidate
        for candidate in (
            _candidate(
                key="landsat",
                metadata_path=PROJECT / "metadata" / "landsat_expanded_connector.json",
                default_label="USGS Landsat Collection 2 Level-2 Surface Temperature",
                default_organization="United States Geological Survey",
                default_quality="QA_PIXEL applied",
            ),
            _candidate(
                key="ecostress",
                metadata_path=PROJECT / "metadata" / "ecostress_expanded_connector.json",
                default_label="NASA/JPL ECOSTRESS L2T Land Surface Temperature V3",
                default_organization="NASA/JPL ECOSTRESS; NASA LP DAAC",
                default_quality="mandatory QC, cloud and water masks applied",
            ),
        )
        if candidate is not None
    ]
    if not candidates:
        raise RuntimeError("No normalized detailed surface-temperature source is available.")
    selected = max(candidates, key=lambda item: _instant(item["acquired_at_utc"]))
    payload = {
        "schema_version": "1.0",
        "selection_rule": "freshest normalized QA-valid local detailed LST; coarse contextual products are excluded",
        "selected": selected,
        "eligible_sources": [
            {
                "source_key": item["source_key"],
                "source": item["source"],
                "acquired_at_utc": item["acquired_at_utc"],
                "resolution_m": item["resolution_m"],
            }
            for item in sorted(
                candidates,
                key=lambda item: _instant(item["acquired_at_utc"]),
                reverse=True,
            )
        ],
    }
    previous = _read(OUTPUT)
    if previous != payload:
        OUTPUT.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return payload


def main() -> None:
    print(json.dumps(select(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
