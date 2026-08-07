"""Run EcoRadar Step 5 diagnosis engine.

This script creates diagnosis artifacts only. It does not generate
recommendations, fitxes, final reports or PDFs.
"""

from __future__ import annotations

import argparse
import json

from ecoradar.diagnosis.engine import run_diagnosis_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar ecological diagnosis engine")
    parser.add_argument("--project", default="projectes/Alinya")
    args = parser.parse_args()

    result = run_diagnosis_engine(args.project)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
