"""Run the full EcoRadar orchestrated workflow."""

from __future__ import annotations

import argparse
import json

from ecoradar.core.orchestrator import run_ecoradar_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete EcoRadar pipeline")
    parser.add_argument("--project", default="projectes/Alinya")
    parser.add_argument(
        "--refresh-connectors",
        action="store_true",
        help="Re-run connectors instead of validating existing processed outputs.",
    )
    parser.add_argument(
        "--skip-documents",
        action="store_true",
        help="Run data, indicators, diagnosis and recommendations without Fitxa/PDF generation.",
    )
    args = parser.parse_args()

    result = run_ecoradar_pipeline(
        args.project,
        refresh_connectors=args.refresh_connectors,
        generate_documents=not args.skip_documents,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

