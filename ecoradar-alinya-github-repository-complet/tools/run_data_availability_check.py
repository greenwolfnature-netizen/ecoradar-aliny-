"""Run the mandatory EcoRadar data availability check for a project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ecoradar.sources.data_source_manager import run_data_source_manager


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar DATA AVAILABILITY CHECK")
    parser.add_argument("--project", default=str(ROOT / "projectes" / "Alinya"), help="Project root path")
    parser.add_argument("--config", default=str(ROOT / "config" / "data_sources.yaml"), help="Central data source config")
    args = parser.parse_args()

    result = run_data_source_manager(args.project, config_path=args.config)
    print(json.dumps(result.__dict__, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
