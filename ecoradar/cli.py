"""Command-line entry point for the EcoRadar base engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ecoradar.connectors.registry import get_connector
from ecoradar.core.project import create_project_workspace
from ecoradar.core.study_area import load_study_area, prepare_study_area_project


def main() -> None:
    parser = argparse.ArgumentParser(prog="ecoradar")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-project", help="Create a project workspace")
    init_parser.add_argument("site_name")
    init_parser.add_argument("--root", default="ecoradar_projectes")
    init_parser.add_argument("--municipality")
    init_parser.add_argument("--comarca")
    init_parser.add_argument("--space-type", default="mixed")
    init_parser.add_argument("--objective", default="general_planning")

    area_parser = subparsers.add_parser("inspect-area", help="Load and validate a study area")
    area_parser.add_argument("path")
    area_parser.add_argument("--name")
    area_parser.add_argument("--metric-crs", default="EPSG:25831")
    area_parser.add_argument("--repair-geometry", action="store_true")
    area_parser.add_argument("--layer")

    connector_parser = subparsers.add_parser(
        "test-empty-cobertes-sol",
        help="Run the empty land-cover connector against a study area",
    )
    connector_parser.add_argument("path")
    connector_parser.add_argument("--name")
    connector_parser.add_argument("--metric-crs", default="EPSG:25831")
    connector_parser.add_argument("--layer")

    prepare_parser = subparsers.add_parser(
        "prepare-study-area",
        help="Prepare a real study-area layer inside a project folder",
    )
    prepare_parser.add_argument("path")
    prepare_parser.add_argument("--project-name", default="Alinya")
    prepare_parser.add_argument("--projects-root", default="projectes")
    prepare_parser.add_argument("--metric-crs", default="EPSG:25831")
    prepare_parser.add_argument("--repair-geometry", action="store_true")
    prepare_parser.add_argument("--layer")
    prepare_parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()

    if args.command == "init-project":
        workspace = create_project_workspace(
            args.site_name,
            root=args.root,
            municipality=args.municipality,
            comarca=args.comarca,
            space_type=args.space_type,
            diagnostic_objective=args.objective,
        )
        print(
            json.dumps(
                {
                    "site_slug": workspace.site_slug,
                    "root": str(workspace.root),
                    "manifest_path": str(workspace.manifest_path),
                },
                indent=2,
            )
        )
        return

    if args.command == "inspect-area":
        area = load_study_area(
            Path(args.path),
            name=args.name,
            metric_crs=args.metric_crs,
            repair_geometry=args.repair_geometry,
            layer=args.layer,
        )
        print(_area_to_json(area))
        return

    if args.command == "test-empty-cobertes-sol":
        area = load_study_area(
            Path(args.path),
            name=args.name,
            metric_crs=args.metric_crs,
            layer=args.layer,
        )
        result = get_connector("cobertes_sol_empty").run(area)
        print(
            json.dumps(
                {
                    "connector_id": result.connector_id,
                    "status": result.status,
                    "metadata": result.metadata,
                    "warnings": result.warnings,
                },
                indent=2,
            )
        )
        return

    if args.command == "prepare-study-area":
        prepared = prepare_study_area_project(
            Path(args.path),
            project_name=args.project_name,
            projects_root=args.projects_root,
            metric_crs=args.metric_crs,
            repair_geometry=args.repair_geometry,
            layer=args.layer,
            overwrite=args.overwrite,
        )
        print(
            json.dumps(
                {
                    "project_root": str(prepared.project_root),
                    "processed_path": str(prepared.processed_path),
                    "metadata_path": str(prepared.metadata_path),
                    "original_crs": prepared.study_area.input_crs,
                    "final_crs": prepared.study_area.metric_crs,
                    "surface_ha": prepared.study_area.area_ha,
                    "perimeter_m": prepared.study_area.perimeter_m,
                    "detected_errors": prepared.study_area.warnings,
                },
                indent=2,
            )
        )


def _area_to_json(area: object) -> str:
    payload = {
        "name": getattr(area, "name"),
        "source_path": str(getattr(area, "source_path")),
        "input_crs": getattr(area, "input_crs"),
        "metric_crs": getattr(area, "metric_crs"),
        "feature_count": getattr(area, "feature_count"),
        "area_ha": getattr(area, "area_ha"),
        "perimeter_m": getattr(area, "perimeter_m"),
        "bounds": getattr(area, "bounds"),
        "warnings": getattr(area, "warnings"),
    }
    return json.dumps(payload, indent=2)


if __name__ == "__main__":
    main()
