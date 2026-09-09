"""Build the allowlisted public bundle for the Alinyà Netlify site."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
DEFAULT_OUTPUT = ROOT / "public"

ROOT_FILES = (
    "index.html",
    "THIRD_PARTY_NOTICES.md",
    "metadata/current_fire_danger.json",
    "metadata/daily_history.json",
    "metadata/daily_readings.json",
    "history/daily_readings_checks.jsonl",
    "history/daily_readings_observations.jsonl",
)

VENDOR_FILES = (
    "d3.min.js",
    "ecoradar-alinya-report-profiles.js",
    "ecoradar-reading-report.js",
    "html2pdf.bundle.min.js",
    "html2pdf.bundle.min.js.LICENSE.txt",
)

PROJECT_FILES = (
    "maps/ecoradar_alinya_interactiu-v2.html",
    "maps/ecoradar_memoria_foc_alinya_interactiu.html",
    "reports/fitxa_ecoradar_alinya_a4.pdf",
    "reports/fitxa_ecoradar_alinya_v1.pdf",
    "reports/informe_ecoradar_alinya_a4_client.pdf",
    "reports/informe_ecoradar_alinya_plantilla_urba_cos.pdf",
    "reports/informe_complet_muntanya_alinya.pdf",
)

PROJECT_TREES = (
    "assets/branding",
    "diagnosis",
    "indicators",
    "maps/ecoradar-alinya-netlify-v2",
    "maps/ecoradar_core",
    "maps/incendis",
    "maps/incendis_similarity",
    "maps/producte",
    "maps/teledeteccio",
    "maps/topografia",
    "recommendations",
)

PROJECT_METADATA_FILES = (
    "biodiversitat_metadata.json",
    "biodiversity_ecology_metadata.json",
    "biodiversity_habitat_pilot_metadata.json",
    "cobertes_sol_metadata.json",
    "connectivitat_metadata.json",
    "connectors_status_report.json",
    "copernicus_hrl_connector.json",
    "creaf_forestdrought_connector.json",
    "current_fire_danger.json",
    "current_surface_temperature.json",
    "daily_history.json",
    "daily_readings.json",
    "data_availability_report.json",
    "data_sources_matrix.csv",
    "data_sources_matrix.json",
    "data_sources_matrix.md",
    "diagnosis_engine_report.json",
    "ecoradar_core_metadata.json",
    "ecoradar_diagnosis.json",
    "ecoradar_indicators_metadata.json",
    "ecostress_connector.json",
    "habitats_metadata.json",
    "hidrologia_metadata.json",
    "incendis_metadata.json",
    "indicator_engine_report.json",
    "indicators_completeness_report.json",
    "landsat_connector.json",
    "perill_integrat_ecoradar.json",
    "pla_alfa_connector.json",
    "reading_registry.json",
    "recreational_pressure_metadata.json",
    "relleu_base_icgc_osm.json",
    "sentinel2_cdse_catalog_check.json",
    "sentinel2_cdse_connector.json",
    "study_area_metadata.json",
    "teledeteccio_metadata.json",
    "terrain_metadata.json",
)


def _copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Missing required public asset: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Missing required public asset tree: {source}")
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", "*.pyo", "*.zip"),
    )


def build_public_site(output: Path = DEFAULT_OUTPUT) -> Path:
    """Create a clean public directory containing only current Alinyà outputs."""

    resolved = output.resolve()
    if resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents and resolved.name != "public":
        raise ValueError(f"Unsafe public output directory: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    for relative in ROOT_FILES:
        _copy_file(ROOT / relative, output / relative)
    for name in VENDOR_FILES:
        _copy_file(ROOT / "vendor" / name, output / "vendor" / name)
    for relative in PROJECT_FILES:
        _copy_file(PROJECT / relative, output / "projectes" / "Alinya" / relative)
    for relative in PROJECT_TREES:
        _copy_tree(PROJECT / relative, output / "projectes" / "Alinya" / relative)
    for name in PROJECT_METADATA_FILES:
        _copy_file(
            PROJECT / "metadata" / name,
            output / "projectes" / "Alinya" / "metadata" / name,
        )

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(build_public_site(args.output))


if __name__ == "__main__":
    main()
