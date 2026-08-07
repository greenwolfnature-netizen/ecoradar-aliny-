"""Project context and path conventions for EcoRadar.

This module is the common entry point for engines that operate on an existing
EcoRadar project. It does not download data, calculate indicators, or generate
reports by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectPaths:
    """Canonical folders for one EcoRadar project."""

    root: Path
    raw: Path
    processed: Path
    indicators: Path
    maps: Path
    metadata: Path
    reports: Path
    exports: Path


@dataclass(frozen=True)
class ProjectContext:
    """Resolved context for a prepared EcoRadar project."""

    project_name: str
    project_root: Path
    paths: ProjectPaths
    study_area_path: Path
    study_area_metadata_path: Path

    @classmethod
    def from_root(cls, project_root: str | Path) -> "ProjectContext":
        root = Path(project_root).expanduser().resolve()
        metadata = root / "metadata"
        study_area_metadata = metadata / "study_area_metadata.json"
        project_name = root.name
        if study_area_metadata.exists():
            payload = json.loads(study_area_metadata.read_text(encoding="utf-8"))
            project_name = str(payload.get("project_name") or project_name)

        return cls(
            project_name=project_name,
            project_root=root,
            paths=ProjectPaths(
                root=root,
                raw=root / "raw",
                processed=root / "processed",
                indicators=root / "indicators",
                maps=root / "maps",
                metadata=metadata,
                reports=root / "reports",
                exports=root / "exports",
            ),
            study_area_path=root / "processed" / "study_area.gpkg",
            study_area_metadata_path=study_area_metadata,
        )

    def ensure_output_dirs(self) -> None:
        """Create standard output folders if they are missing."""

        for directory in (
            self.paths.raw,
            self.paths.processed,
            self.paths.indicators,
            self.paths.maps,
            self.paths.metadata,
            self.paths.reports,
            self.paths.exports,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def read_json(self, relative_path: str | Path, default: Any | None = None) -> Any:
        path = self.project_root / relative_path
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def read_csv(self, relative_path: str | Path) -> list[dict[str, str]]:
        path = self.project_root / relative_path
        if not path.exists():
            return []
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def write_json(self, relative_path: str | Path, payload: Any) -> Path:
        path = self.project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path
