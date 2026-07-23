"""Build one complete, upload-ready GitHub repository ZIP for EcoRadar La Seu."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from sync_la_seu_repository_root import MARKER, sync as sync_repository_root


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
RELEASES = PROJECT / "releases"
STAGING = RELEASES / "ecoradar-la-seu-github-repository-complet"
ZIP_PATH = RELEASES / "ecoradar-la-seu-github-repository-complet.zip"
NETLIFY_PACKAGE = PROJECT / "maps" / "ecoradar-la-seu-netlify"

ROOT_FILES = (
    ".env.example",
    ".gitignore",
    "AGENTS.md",
    "ECORADAR_EXECUTION_REPORT.md",
    "ECORADAR_FITXA_V1.md",
    "ECORADAR_URBA_NOVA_CIUTAT.md",
    "pyproject.toml",
)
ROOT_DIRECTORIES = ("config", "docs", "ecoradar", "netlify", "tests", "tools")
REQUIRED_PATHS = (
    "index.html",
    "netlify.toml",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "metadata/daily_readings.json",
    "metadata/current_fire_danger.json",
    "metadata/daily_history.json",
    "metadata/biodiversity_urban_potential.json",
    "history/daily_readings_observations.jsonl",
    "history/daily_readings_checks.jsonl",
    "netlify/functions/daily-readings.mjs",
    "docs/data-sources-matrix.md",
    "docs/data_sources/urban_daily_readings.md",
    "vendor/d3.min.js",
    ".github/workflows/update-current-fire-danger.yml",
    "tools/validate_la_seu_daily_timestamps.py",
    "tools/sync_la_seu_repository_root.py",
    "tests/js/test-daily-readings-api.mjs",
    "projectes/LaSeu_Urba/indicators/daily_readings.json",
    "projectes/LaSeu_Urba/indicators/daily_history.json",
    "projectes/LaSeu_Urba/indicators/current_fire_danger.json",
    "projectes/LaSeu_Urba/processed/lidar_expanded_arrays.npz",
    "projectes/LaSeu_Urba/processed/fire_danger_structural_2024.tif",
    "projectes/LaSeu_Urba/raw/meteocat_xema/CD_observations.csv",
    "projectes/LaSeu_Urba/maps/ecoradar_urba_la_seu_interactiu.html",
    "projectes/LaSeu_Urba/maps/ecoradar-la-seu-netlify/index.html",
)


def ignored(path: Path, source_root: Path) -> bool:
    relative = path.relative_to(source_root)
    parts = relative.parts
    if any(part in {".DS_Store", "__pycache__", ".pycache"} for part in parts):
        return True
    if path.is_file() and path.suffix in {".pyc", ".pyo"}:
        return True
    if source_root == PROJECT:
        if parts and parts[0] == "releases":
            return True
        if len(parts) >= 2 and parts[0] == "maps":
            if parts[1] == "ecoradar-la-seu-netlify-v7":
                return True
            if path.is_file() and path.suffix == ".zip":
                return True
    return False


def copy_tree(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        if ignored(path, source):
            continue
        relative = path.relative_to(source)
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def checked_at(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("checked_at_utc") or payload.get("generated_at_utc") or ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_files() -> list[Path]:
    return sorted(
        path
        for path in STAGING.rglob("*")
        if path.is_file() and path.name != "repository-manifest.json"
    )


def validate_staging() -> dict:
    missing = [relative for relative in REQUIRED_PATHS if not (STAGING / relative).is_file()]
    if missing:
        raise RuntimeError(f"Missing required repository files: {missing}")

    forbidden = [
        path.relative_to(STAGING).as_posix()
        for path in STAGING.rglob("*")
        if path.name in {".DS_Store", "__pycache__", ".pycache", ".env"}
        or path.suffix in {".pyc", ".pyo"}
    ]
    if forbidden:
        raise RuntimeError(f"Forbidden local files in repository package: {forbidden}")

    oversized = [
        (path.relative_to(STAGING).as_posix(), path.stat().st_size)
        for path in repository_files()
        if path.stat().st_size >= 100 * 1024 * 1024
    ]
    if oversized:
        raise RuntimeError(f"GitHub 100 MiB file limit exceeded: {oversized}")

    top_level_python_packages = sorted(
        path.name
        for path in STAGING.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
    if top_level_python_packages != ["ecoradar"]:
        raise RuntimeError(
            "The repository must contain exactly one top-level Python package: "
            f"found {top_level_python_packages}"
        )

    pyproject = (STAGING / "pyproject.toml").read_text(encoding="utf-8")
    required_packaging_fragments = (
        "[tool.setuptools.packages.find]",
        'include = ["ecoradar", "ecoradar.*"]',
        "namespaces = false",
    )
    missing_packaging = [
        fragment for fragment in required_packaging_fragments if fragment not in pyproject
    ]
    if missing_packaging:
        raise RuntimeError(
            "pyproject.toml does not constrain package discovery to ecoradar: "
            f"{missing_packaging}"
        )

    timestamps = {
        "root_daily_readings": checked_at(STAGING / "metadata" / "daily_readings.json"),
        "root_daily_history": checked_at(STAGING / "metadata" / "daily_history.json"),
        "root_current_fire_danger": checked_at(STAGING / "metadata" / "current_fire_danger.json"),
        "canonical_daily_readings": checked_at(
            STAGING / "projectes" / "LaSeu_Urba" / "indicators" / "daily_readings.json"
        ),
        "canonical_daily_history": checked_at(
            STAGING / "projectes" / "LaSeu_Urba" / "indicators" / "daily_history.json"
        ),
        "canonical_current_fire_danger": checked_at(
            STAGING / "projectes" / "LaSeu_Urba" / "indicators" / "current_fire_danger.json"
        ),
    }
    if len(set(timestamps.values())) != 1 or not next(iter(timestamps.values())):
        raise RuntimeError(f"Inconsistent checked_at_utc values: {timestamps}")

    if sha256(STAGING / "index.html") != sha256(
        STAGING / "projectes" / "LaSeu_Urba" / "maps" / "ecoradar-la-seu-netlify" / "index.html"
    ):
        raise RuntimeError("Root index.html differs from the synchronized Netlify package.")

    workflow = (STAGING / ".github" / "workflows" / "update-current-fire-danger.yml").read_text(
        encoding="utf-8"
    )
    required_workflow_fragments = (
        "pip install -e .",
        "ECORADAR_CHECKED_AT_UTC",
        "sync_la_seu_repository_root.py --repository-root .",
        "git push origin",
        "npx --yes netlify-cli deploy --prod --dir .",
    )
    absent = [fragment for fragment in required_workflow_fragments if fragment not in workflow]
    if absent:
        raise RuntimeError(f"Incomplete GitHub workflow: {absent}")
    if "projectes/Alinya" in workflow:
        raise RuntimeError("Standalone La Seu workflow still depends on the Alinyà project.")

    files = repository_files()
    return {
        "checked_at_utc": next(iter(timestamps.values())),
        "file_count": len(files),
        "uncompressed_bytes": sum(path.stat().st_size for path in files),
    }


def write_manifest(validation: dict) -> None:
    entries = [
        {
            "path": path.relative_to(STAGING).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in repository_files()
    ]
    payload = {
        "schema_version": "1.0",
        "package": "EcoRadar Urbà — La Seu d’Urgell, Castellciutat i Sant Antoni",
        "built_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "canonical_checked_at_utc": validation["checked_at_utc"],
        "archive_layout": "repository files are stored directly at ZIP root",
        "excluded_as_non_operational": [
            "virtual environments and caches",
            "secret files such as .env",
            "previous versioned Netlify folders and ZIP archives under projectes/LaSeu_Urba/maps",
            "other EcoRadar study areas, including projectes/Alinya",
            "temporary, output and marketing workspaces outside projectes/LaSeu_Urba",
        ],
        "file_count_excluding_this_manifest": len(entries),
        "uncompressed_bytes_excluding_this_manifest": sum(item["bytes"] for item in entries),
        "files": entries,
    }
    (STAGING / "repository-manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_zip() -> None:
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(path for path in STAGING.rglob("*") if path.is_file()):
            archive.write(path, path.relative_to(STAGING).as_posix())


def build() -> dict:
    if not NETLIFY_PACKAGE.is_dir():
        raise FileNotFoundError(NETLIFY_PACKAGE)
    RELEASES.mkdir(parents=True, exist_ok=True)
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)

    for name in ROOT_FILES:
        shutil.copy2(ROOT / name, STAGING / name)
    for name in ROOT_DIRECTORIES:
        copy_tree(ROOT / name, STAGING / name)
    copy_tree(PROJECT, STAGING / "projectes" / "LaSeu_Urba")

    (STAGING / MARKER).write_text(
        "Standalone EcoRadar La Seu repository. Required by the guarded root synchronizer.\n",
        encoding="utf-8",
    )
    shutil.copy2(
        ROOT / "docs" / "deployment" / "la_seu_github_repository_readme.md",
        STAGING / "README.md",
    )
    workflow_target = STAGING / ".github" / "workflows" / "update-current-fire-danger.yml"
    workflow_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs" / "deployment" / "update-current-fire-danger.yml", workflow_target)

    sync_repository_root(STAGING)
    validation = validate_staging()
    write_manifest(validation)
    build_zip()

    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_member = archive.testzip()
        names = set(archive.namelist())
    if bad_member:
        raise RuntimeError(f"Corrupt ZIP member: {bad_member}")
    zip_missing = [relative for relative in REQUIRED_PATHS if relative not in names]
    if zip_missing:
        raise RuntimeError(f"Required files absent from ZIP: {zip_missing}")

    result = {
        **validation,
        "staging": str(STAGING),
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "zip_members": len(names),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    build()
