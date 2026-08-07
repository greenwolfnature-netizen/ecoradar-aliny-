"""Project workspace creation for EcoRadar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unicodedata


PROJECT_DIRS = [
    "area_estudi",
    "data/raw",
    "data/processed",
    "data/fieldwork",
    "maps",
    "indicators",
    "reports",
    "media/photos",
    "media/drone",
    "media/audio",
    "media/thermal",
    "media/cameratrap",
    "metadata",
    "exports",
]


@dataclass(frozen=True)
class ProjectWorkspace:
    """Created EcoRadar project workspace."""

    site_name: str
    site_slug: str
    root: Path
    manifest_path: Path


def slugify_site_name(site_name: str) -> str:
    """Return a stable lowercase ASCII project slug."""

    normalized = unicodedata.normalize("NFKD", site_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    if not slug:
        raise ValueError("site_name must contain at least one letter or number")
    return slug


def create_project_workspace(
    site_name: str,
    root: str | Path = "ecoradar_projectes",
    municipality: str | None = None,
    comarca: str | None = None,
    space_type: str = "mixed",
    diagnostic_objective: str = "general_planning",
    overwrite: bool = False,
) -> ProjectWorkspace:
    """Create the base EcoRadar project folder structure and manifest."""

    site_slug = slugify_site_name(site_name)
    root_path = Path(root).resolve()
    project_root = root_path / site_slug

    if project_root.exists() and not overwrite:
        raise FileExistsError(
            f"Project workspace already exists: {project_root}. "
            "Use overwrite=True only for intentional replacement."
        )

    for relative_dir in PROJECT_DIRS:
        (project_root / relative_dir).mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "project_id": site_slug,
        "site_name": site_name,
        "municipality": municipality,
        "comarca": comarca,
        "created_at": now,
        "updated_at": now,
        "space_type": space_type,
        "diagnostic_objective": diagnostic_objective,
        "study_area": None,
        "paths": {
            "area_estudi": "area_estudi",
            "raw_data": "data/raw",
            "processed_data": "data/processed",
            "fieldwork": "data/fieldwork",
            "maps": "maps",
            "indicators": "indicators",
            "reports": "reports",
            "metadata": "metadata",
            "exports": "exports",
        },
        "source_gates": [],
    }

    manifest_path = project_root / "metadata" / "project_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return ProjectWorkspace(
        site_name=site_name,
        site_slug=site_slug,
        root=project_root,
        manifest_path=manifest_path,
    )

