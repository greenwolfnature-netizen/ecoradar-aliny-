"""Resume the official-data workflow after CDSE credentials are available."""

from __future__ import annotations

import subprocess
import sys
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(script: str, *arguments: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / script), *arguments], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials-file")
    parser.add_argument("--delete-credentials-file", action="store_true")
    args = parser.parse_args()
    run("fetch_la_seu_cams_context.py")
    fetch_arguments = []
    if args.credentials_file:
        fetch_arguments.extend(["--credentials-file", args.credentials_file])
    run("fetch_la_seu_cdse_sentinel2.py", *fetch_arguments)
    run("calculate_la_seu_sentinel2_indicators.py")
    context_arguments = list(fetch_arguments)
    if args.delete_credentials_file:
        context_arguments.append("--delete-credentials-file")
    run("fetch_la_seu_cdse_context.py", *context_arguments)
    run("calculate_la_seu_contextual_indicators.py")
    run("render_la_seu_urban_map.py")


if __name__ == "__main__":
    main()
