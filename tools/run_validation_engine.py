"""Run EcoRadar validation checks for a project."""

from __future__ import annotations

import argparse
import json

from ecoradar.validation.engine import run_validation_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar validation engine")
    parser.add_argument("--project", default="projectes/Alinya")
    parser.add_argument(
        "--allow-partial-copernicus",
        action="store_true",
        help="Validate the dated scene and explicit unavailable states without requiring credentials.",
    )
    args = parser.parse_args()

    result = run_validation_engine(args.project, allow_partial_copernicus=args.allow_partial_copernicus)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
