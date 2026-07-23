"""Synchronize the La Seu Netlify package into a GitHub repository root.

The command is intentionally guarded by a marker file so it cannot overwrite
the main multi-project EcoRadar workspace by accident. The repository package
builder creates that marker in the standalone La Seu release.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "projectes" / "LaSeu_Urba" / "maps" / "ecoradar-la-seu-netlify"
MARKER = ".ecoradar-la-seu-repository"
ROOT_FILES = ("index.html", "netlify.toml", "THIRD_PARTY_NOTICES.md")
ROOT_DIRECTORIES = ("metadata", "history", "netlify", "vendor")
DEPLOYMENT_DOCS = (
    "current-fire-danger-source.md",
    "data-sources-matrix.md",
    "fire-danger-source.md",
    "urban-daily-readings-source.md",
)


def copy_directory(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)


def sync(repository_root: Path) -> list[Path]:
    repository_root = repository_root.resolve()
    marker = repository_root / MARKER
    if not marker.is_file():
        raise RuntimeError(
            f"Refusing to synchronize {repository_root}: missing {MARKER}. "
            "Use the standalone GitHub repository package."
        )
    if not PACKAGE.is_dir():
        raise FileNotFoundError(f"Netlify package not found: {PACKAGE}")

    copied: list[Path] = []
    for name in ROOT_FILES:
        source = PACKAGE / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = repository_root / name
        shutil.copy2(source, target)
        copied.append(target)

    for name in ROOT_DIRECTORIES:
        source = PACKAGE / name
        if not source.is_dir():
            raise FileNotFoundError(source)
        target = repository_root / name
        copy_directory(source, target)
        copied.append(target)

    docs_target = repository_root / "docs"
    docs_target.mkdir(parents=True, exist_ok=True)
    for name in DEPLOYMENT_DOCS:
        source = PACKAGE / "docs" / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = docs_target / name
        shutil.copy2(source, target)
        copied.append(target)

    return copied


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository-root",
        type=Path,
        required=True,
        help=f"Standalone repository root containing {MARKER}.",
    )
    args = parser.parse_args()
    copied = sync(args.repository_root)
    print(f"Synchronized {len(copied)} root deployment entries into {args.repository_root.resolve()}")


if __name__ == "__main__":
    main()
