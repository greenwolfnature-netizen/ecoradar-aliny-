"""Run the EcoRadar diagnosis pipeline for the prepared Alinya project.

By default this regenerates the analysis and product outputs from the current
prepared data. Use --refresh-data to run available verified connectors first.
Connectors that require credentials or unavailable/unverified sources are not
used to synthesize placeholder values.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ecoradar.core.data_availability import ensure_mandatory_preflight, run_data_availability_check


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
METADATA = PROJECT / "metadata"
RUN_METADATA = METADATA / "ecoradar_diagnosis_run_metadata.json"


def _step(name: str, func: Callable[[], Any]) -> dict[str, Any]:
    try:
        result = func()
        return {"name": name, "status": "ok", "result": result}
    except SystemExit as exc:
        return {"name": name, "status": "blocked", "reason": f"system_exit_{exc.code}"}
    except Exception as exc:
        return {"name": name, "status": "failed", "reason": str(exc)}


def refresh_connectors(*, refresh_network_cache: bool) -> list[dict[str, Any]]:
    """Run connector-grade sources that are already implemented for Alinya."""

    from connectors import connector_biodiversitat
    from connectors import connector_habitats
    from connectors import connector_icgc_cobertes_sol
    from connectors import connector_recreational_pressure_osm

    steps = [
        _step("cobertes_sol", connector_icgc_cobertes_sol.run_connector),
        _step("habitats", connector_habitats.run_connector),
        _step("biodiversitat", connector_biodiversitat.run_connector),
        _step("pressio_humana_osm", lambda: connector_recreational_pressure_osm.run_connector(refresh=refresh_network_cache)),
    ]

    has_copernicus_credentials = bool(os.environ.get("COPERNICUS_CLIENT_ID") and os.environ.get("COPERNICUS_CLIENT_SECRET"))
    if has_copernicus_credentials:
        from connectors import connector_copernicus_teledeteccio

        steps.append(_step("teledeteccio_copernicus", connector_copernicus_teledeteccio.run_connector))
    else:
        steps.append(
            {
                "name": "teledeteccio_copernicus",
                "status": "blocked",
                "reason": "missing Copernicus credentials; no placeholder values generated",
            }
        )
    return steps


def generate_products() -> dict[str, Any]:
    ensure_mandatory_preflight(PROJECT)

    from ecoradar.diagnosis.engine import generate_diagnosis_outputs
    from ecoradar.product.fitxa_value import generate_fitxa_value_outputs
    from ecoradar.recommendations.engine import generate_recommendation_outputs
    from tools import export_ecoradar_atlas_a3
    from tools import export_ecoradar_atlas_v2
    from tools import export_ecoradar_atlas_v3
    from tools import export_informe_diagnosi_fitxa_pdf
    from tools import export_ecoradar_product

    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        subprocess.run([str(venv_python), "-m", "ecoradar.analysis.core"], cwd=ROOT, env=env, check=True)
    else:
        from ecoradar.analysis.core import generate_core_outputs

        generate_core_outputs(PROJECT)

    diagnosis_outputs = generate_diagnosis_outputs(PROJECT)
    recommendation_outputs = generate_recommendation_outputs(PROJECT)
    fitxa_value_outputs = generate_fitxa_value_outputs(PROJECT)
    maps = export_ecoradar_product.render_maps()
    context = export_ecoradar_atlas_a3.build_context()
    export_informe_diagnosi_fitxa_pdf.draw_fitxa()
    export_ecoradar_atlas_a3.atlas_pdf(context, maps)
    export_ecoradar_atlas_a3.write_metadata(context, maps)
    export_ecoradar_atlas_v2.build_pdf(context, maps)
    export_ecoradar_atlas_v2.write_metadata(context, maps)
    export_ecoradar_atlas_v3.build_pdf(context, maps)
    export_ecoradar_atlas_v3.write_metadata(context, maps)

    return {
        "core": {
            "csv": str(PROJECT / "indicators" / "ecoradar_core.csv"),
            "json": str(PROJECT / "indicators" / "ecoradar_core.json"),
            "metadata": str(PROJECT / "metadata" / "ecoradar_core_metadata.json"),
            "maps_dir": str(PROJECT / "maps" / "ecoradar_core"),
        },
        "diagnosis": diagnosis_outputs,
        "recommendations": recommendation_outputs,
        "fitxa_value_gate": fitxa_value_outputs,
        "executive_sheet": str(export_informe_diagnosi_fitxa_pdf.FITXA_PDF),
        "executive_sheet_copy": str(export_informe_diagnosi_fitxa_pdf.OUTPUT_FITXA_PDF),
        "atlas_a3": str(export_ecoradar_atlas_a3.ATLAS_PDF),
        "atlas_a3_copy": str(export_ecoradar_atlas_a3.OUTPUT_ATLAS_PDF),
        "atlas_v2_a3": str(export_ecoradar_atlas_v2.ATLAS_V2_PDF),
        "atlas_v2_a3_copy": str(export_ecoradar_atlas_v2.OUTPUT_V2_PDF),
        "atlas_v3_a3": str(export_ecoradar_atlas_v3.ATLAS_V3_PDF),
        "atlas_v3_a3_copy": str(export_ecoradar_atlas_v3.OUTPUT_V3_PDF),
    }


def write_run_metadata(*, refresh_data: bool, connector_steps: list[dict[str, Any]], product_outputs: dict[str, Any]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project": "Alinyà",
        "refresh_data": refresh_data,
        "connector_steps": connector_steps,
        "product_outputs": product_outputs,
        "data_policy": "Real prepared data only. Missing connector outputs remain unavailable and are not estimated.",
    }
    METADATA.mkdir(parents=True, exist_ok=True)
    RUN_METADATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar diagnosis outputs for Alinya")
    parser.add_argument("--refresh-data", action="store_true", help="Run implemented verified connectors before regenerating outputs")
    parser.add_argument(
        "--refresh-network-cache",
        action="store_true",
        help="Ignore connector raw caches where supported. Use only with --refresh-data.",
    )
    args = parser.parse_args()

    connector_steps: list[dict[str, Any]] = []
    if args.refresh_data:
        connector_steps = refresh_connectors(refresh_network_cache=args.refresh_network_cache)

    run_data_availability_check(PROJECT)
    product_outputs = generate_products()
    write_run_metadata(refresh_data=args.refresh_data, connector_steps=connector_steps, product_outputs=product_outputs)
    print(json.dumps({"connectors": connector_steps, "products": product_outputs, "metadata": str(RUN_METADATA)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
