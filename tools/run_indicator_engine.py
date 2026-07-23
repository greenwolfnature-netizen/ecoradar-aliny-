"""Run EcoRadar Step 3 indicator engine.

This script creates indicator tables only. It does not generate diagnosis,
recommendations, maps, fitxa, Markdown reports or PDFs.
"""

from __future__ import annotations

import argparse
import json

from ecoradar.indicators.engine import run_indicator_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar indicator engine")
    parser.add_argument("--project", default="projectes/Alinya")
    args = parser.parse_args()

    result = run_indicator_engine(args.project)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
