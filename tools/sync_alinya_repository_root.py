"""Synchronize Alinyà's Netlify package into a standalone repository root."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "projectes" / "Alinya" / "maps" / "ecoradar-alinya-netlify-v2"
MARKER = ".ecoradar-alinya-repository"
ROOT_FILES = ("index.html", "netlify.toml", "THIRD_PARTY_NOTICES.md")
ROOT_DIRECTORIES = ("metadata", "history", "netlify", "vendor")
DEPLOYMENT_DOCS = (
    "current-fire-danger-source.md",
    "data-sources-matrix.md",
    "fire-source.md",
    "alinya-daily-readings-source.md",
)


def _copy_directory(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)


def sync(repository_root: Path) -> list[Path]:
    repository_root = repository_root.resolve()
    if not (repository_root / MARKER).is_file():
        raise RuntimeError(
            f"Refusing to synchronize {repository_root}: missing {MARKER}. "
            "Use the standalone Alinyà GitHub repository package."
        )
    if not PACKAGE.is_dir():
        raise FileNotFoundError(f"Netlify package not found: {PACKAGE}")

    copied: list[Path] = []
    for name in ROOT_FILES:
        source = PACKAGE / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = repository_root / name
        if (
            name == "netlify.toml"
            and target.is_file()
            and "tools/build_alinya_public_site.py" in target.read_text(encoding="utf-8")
        ):
            copied.append(target)
            continue
        shutil.copy2(source, target)
        copied.append(target)

    for name in ROOT_DIRECTORIES:
        source = PACKAGE / name
        if not source.is_dir():
            raise FileNotFoundError(source)
        target = repository_root / name
        _copy_directory(source, target)
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
    parser.add_argument("--repository-root", type=Path, required=True)
    args = parser.parse_args()
    copied = sync(args.repository_root)
    print(f"Synchronized {len(copied)} deployment entries into {args.repository_root.resolve()}")


if __name__ == "__main__":
    main()
