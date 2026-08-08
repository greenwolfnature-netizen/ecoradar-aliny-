"""Crop the verified SNCZI Q100 WMS image to the expanded EcoRadar scope."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
SOURCE = PROJECT / "raw" / "inundabilitat" / "snczi_q100_la_seu_bbox.png"
OUTPUT = PROJECT / "maps" / "snczi_q100_expanded.png"
METADATA = PROJECT / "metadata" / "snczi_q100_expanded.json"
SOURCE_BBOX = (1.435, 42.335, 1.490, 42.375)


def crop() -> dict:
    project = json.loads((PROJECT / "metadata" / "project_manifest.json").read_text())
    bbox = tuple(float(value) for value in project["study_area"]["expanded_urban_bbox_epsg4326"])
    image = Image.open(SOURCE).convert("RGBA")
    width, height = image.size
    left = math.floor((bbox[0] - SOURCE_BBOX[0]) / (SOURCE_BBOX[2] - SOURCE_BBOX[0]) * width)
    right = math.ceil((bbox[2] - SOURCE_BBOX[0]) / (SOURCE_BBOX[2] - SOURCE_BBOX[0]) * width)
    top = math.floor((SOURCE_BBOX[3] - bbox[3]) / (SOURCE_BBOX[3] - SOURCE_BBOX[1]) * height)
    bottom = math.ceil((SOURCE_BBOX[3] - bbox[1]) / (SOURCE_BBOX[3] - SOURCE_BBOX[1]) * height)
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise RuntimeError("Expanded bbox falls outside the verified source WMS image.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.crop((left, top, right, bottom)).save(OUTPUT, optimize=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "SNCZI, zonas inundables T=100 years",
        "organization": "MITECO",
        "official_wms": "https://wms.mapama.gob.es/sig/agua/ZI_LaminasQ100",
        "source_image": str(SOURCE.relative_to(ROOT)),
        "source_bbox_epsg4326": SOURCE_BBOX,
        "study_bbox_epsg4326": bbox,
        "source_dimensions": [width, height],
        "crop_window_pixels": [left, top, right, bottom],
        "output_dimensions": list(Image.open(OUTPUT).size),
        "method": "Exact pixel crop of the already verified official WMS image; no interpolation or thematic reclassification.",
        "output": str(OUTPUT.relative_to(ROOT)),
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


if __name__ == "__main__":
    print(json.dumps(crop(), ensure_ascii=False, indent=2))
