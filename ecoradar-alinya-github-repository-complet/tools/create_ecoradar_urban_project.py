"""Create a safe EcoRadar Urban project scaffold from the reusable template."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "projectes" / "_TEMPLATE_ECORADAR_URBA"
PROJECTS = ROOT / "projectes"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    if not slug:
        raise ValueError("The city name must contain at least one letter or number.")
    return slug


def bbox(values: list[float], label: str) -> list[float]:
    west, south, east, north = values
    if west >= east or south >= north:
        raise ValueError(f"{label} must follow WEST SOUTH EAST NORTH.")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError(f"{label} longitude values are outside EPSG:4326.")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError(f"{label} latitude values are outside EPSG:4326.")
    return [west, south, east, north]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Visible city name.")
    parser.add_argument("--project-id", required=True, help="Folder identifier, for example NOM_CIUTAT_Urba.")
    parser.add_argument(
        "--map-bbox",
        required=True,
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="General map extent in EPSG:4326.",
    )
    parser.add_argument(
        "--core-bbox",
        nargs=4,
        type=float,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Urban analysis extent in EPSG:4326. Defaults to the map extent and must then be reviewed.",
    )
    parser.add_argument("--metric-crs", default="EPSG:25831")
    parser.add_argument("--municipality-code")
    return parser.parse_args()


def replace_markers(project: Path, city_name: str, slug: str) -> None:
    replacements = {"{{CITY_NAME}}": city_name, "{{SLUG}}": slug}
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for source, target in replacements.items():
            text = text.replace(source, target)
        path.write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    map_bbox = bbox(args.map_bbox, "--map-bbox")
    core_bbox = bbox(args.core_bbox or args.map_bbox, "--core-bbox")
    if not (
        map_bbox[0] <= core_bbox[0] < core_bbox[2] <= map_bbox[2]
        and map_bbox[1] <= core_bbox[1] < core_bbox[3] <= map_bbox[3]
    ):
        raise ValueError("--core-bbox must be contained inside --map-bbox.")

    project_id = args.project_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_id):
        raise ValueError("--project-id may only contain letters, numbers, underscores and hyphens.")
    target = PROJECTS / project_id
    if target.exists():
        raise FileExistsError(f"Project already exists; nothing was overwritten: {target}")
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Urban template not found: {TEMPLATE}")

    slug = slugify(args.name)
    shutil.copytree(TEMPLATE, target)
    for directory in ("raw", "processed", "indicators", "maps", "reports"):
        (target / directory).mkdir(parents=True, exist_ok=True)
    replace_markers(target, args.name.strip(), slug)

    config = {
        "schema_version": "1.0",
        "project_id": project_id,
        "city_name": args.name.strip(),
        "slug": slug,
        "project_type": "EcoRadar Urba",
        "study_area": {
            "map_bbox_epsg4326": map_bbox,
            "analysis_core_bbox_epsg4326": core_bbox,
            "metric_crs": args.metric_crs,
        },
        "local_identifiers": {"municipality_code": args.municipality_code},
        "rules": {
            "verified_sources_only": True,
            "no_invented_values": True,
            "map_and_report_share_manifests": True,
        },
    }
    config_path = target / "config" / "project_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "project_id": project_id,
        "site_name": args.name.strip(),
        "project_type": "EcoRadar Urba",
        "methodology": "Source gate before implementation; verified local data only",
        "study_area": config["study_area"],
        "source_inventory": "metadata/data_sources_matrix.md",
        "validation_checklist": "validation/acceptance_checklist.md",
        "status": "source_inventory_pending",
    }
    manifest_path = target / "metadata" / "project_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(target)
    print(config_path)
    print(target / "metadata" / "data_sources_matrix.md")
    print("Next step: verify and document every official source before implementing connectors.")


if __name__ == "__main__":
    main()
