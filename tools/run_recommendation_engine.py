"""Run EcoRadar Step 6 recommendation engine.

This script creates recommendations and priority matrices only. It does not
generate fitxes, final reports or PDFs.
"""

from __future__ import annotations

import argparse
import json

from ecoradar.recommendations.engine import run_recommendation_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar recommendation engine")
    parser.add_argument("--project", default="projectes/Alinya")
    args = parser.parse_args()

    result = run_recommendation_engine(args.project)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
