"""Build one complete, upload-ready GitHub repository ZIP for EcoRadar Alinyà."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from sync_alinya_repository_root import MARKER, sync as sync_repository_root


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
LA_SEU_RELEASE = (
    ROOT
    / "projectes"
    / "LaSeu_Urba"
    / "releases"
    / "ecoradar-la-seu-github-repository-complet"
)
RELEASES = PROJECT / "releases"
STAGING = RELEASES / "ecoradar-alinya-github-repository-complet"
ZIP_PATH = RELEASES / "ecoradar-alinya-github-repository-complet.zip"
NETLIFY_PACKAGE = PROJECT / "maps" / "ecoradar-alinya-netlify-v2"

ROOT_FILES = (
    ".env.example",
    ".gitignore",
    "AGENTS.md",
    "ECORADAR_EXECUTION_REPORT.md",
    "ECORADAR_FITXA_V1.md",
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
    "history/daily_readings_observations.jsonl",
    "history/daily_readings_checks.jsonl",
    "netlify/functions/daily-readings.mjs",
    "docs/data-sources-matrix.md",
    "docs/data_sources/alinya_daily_readings.md",
    "vendor/d3.min.js",
    ".github/workflows/update-current-fire-danger.yml",
    "tools/validate_alinya_daily_timestamps.py",
    "tools/sync_alinya_repository_root.py",
    "tests/js/test-daily-readings-api.mjs",
    "projectes/Alinya/indicators/daily_readings.json",
    "projectes/Alinya/indicators/daily_history.json",
    "projectes/Alinya/indicators/current_fire_danger.json",
    "projectes/Alinya/processed/study_area.gpkg",
    "projectes/Alinya/processed/incendis/current_fire_danger/current_fire_danger_0_100.tif",
    "projectes/Alinya/raw/meteocat_xema/Y4_observations.csv",
    "projectes/Alinya/raw/meteocat_xema/CJ_wind_observations.csv",
    "projectes/Alinya/raw/meteocat_xema/CJ_wind_metadata.json",
    "projectes/Alinya/raw/pla_alfa/figols_alinya_current.json",
    "projectes/Alinya/raw/incendis/perill_basic_2024/PERILLBASICINCENDI.tif",
    "projectes/Alinya/maps/ecoradar_alinya_interactiu-v2.html",
    "projectes/Alinya/maps/ecoradar-alinya-netlify-v2/index.html",
    "projectes/Alinya/reports/fitxa_ecoradar_alinya_v1.pdf",
    "projectes/Alinya/reports/informe_complet_muntanya_alinya.pdf",
)


def _ignored(path: Path, source_root: Path) -> bool:
    relative = path.relative_to(source_root)
    parts = relative.parts
    if any(part in {".DS_Store", "__pycache__", ".pycache"} for part in parts):
        return True
    if path.is_file() and path.suffix in {".pyc", ".pyo"}:
        return True
    if source_root == PROJECT:
        if parts and parts[0] == "releases":
            return True
        if parts[:2] == ("raw", "cobertes_sol"):
            return True
        if parts and parts[0] == "reports":
            return True
        if len(parts) >= 2 and parts[0] == "maps":
            name = parts[1]
            if path.is_file() and path.suffix == ".zip":
                return True
            if "backup" in name:
                return True
            if name in {
                "ecoradar-alinya-netlify",
                "ecoradar_alinya_interactiu.html",
                "ecoradar_alinya_interactiu-v1.html",
            }:
                return True
    return False


def _copy_tree(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        if _ignored(path, source):
            continue
        relative = path.relative_to(source)
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checked_at(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("checked_at_utc") or payload.get("generated_at_utc") or ""


def _files() -> list[Path]:
    return sorted(
        path
        for path in STAGING.rglob("*")
        if path.is_file() and path.name != "repository-manifest.json"
    )


def _prepare_project_specific_files() -> None:
    environment_example = STAGING / ".env.example"
    environment_example.write_text(
        environment_example.read_text(encoding="utf-8").replace(
            "/projectes/LaSeu_Urba", "/projectes/Alinya"
        ),
        encoding="utf-8",
    )

    branding = STAGING / "projectes" / "Alinya" / "assets" / "branding"
    branding.mkdir(parents=True, exist_ok=True)
    source_branding = ROOT / "projectes" / "LaSeu_Urba" / "assets" / "branding"
    for name in ("ecoradar_logo.png", "green_wolf_nature_logo.png", "green_wolf_nature_logo.svg"):
        shutil.copy2(source_branding / name, branding / name)

    official_target = (
        STAGING
        / "projectes"
        / "Alinya"
        / "raw"
        / "incendis"
        / "perill_basic_2024"
        / "PERILLBASICINCENDI.tif"
    )
    official_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT
        / "projectes"
        / "LaSeu_Urba"
        / "raw"
        / "incendis"
        / "perill_basic_2024"
        / "PERILLBASICINCENDI.tif",
        official_target,
    )

    reports = STAGING / "projectes" / "Alinya" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        PROJECT / "reports" / "releases" / "fitxa_ecoradar_alinya_v1.pdf",
        reports / "fitxa_ecoradar_alinya_v1.pdf",
    )
    shutil.copy2(
        PROJECT / "reports" / "informe_complet_muntanya_alinya-backup-20260721-six-axis-radar.pdf",
        reports / "informe_complet_muntanya_alinya.pdf",
    )

    current_config = STAGING / "config" / "current_fire_danger.json"
    payload = json.loads(current_config.read_text(encoding="utf-8"))
    payload["stations"] = {"alinya": payload["stations"]["alinya"]}
    current_config.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (STAGING / "vendor").mkdir(parents=True, exist_ok=True)
    shutil.copy2(LA_SEU_RELEASE / "vendor" / "d3.min.js", STAGING / "vendor" / "d3.min.js")
    shutil.copy2(
        ROOT / "netlify" / "functions" / "daily-readings-alinya.mjs",
        STAGING / "netlify" / "functions" / "daily-readings.mjs",
    )
    (STAGING / "netlify" / "functions" / "daily-readings-alinya.mjs").unlink(missing_ok=True)
    shutil.copy2(
        ROOT / "tests" / "js" / "test-daily-readings-api-alinya.mjs",
        STAGING / "tests" / "js" / "test-daily-readings-api.mjs",
    )
    repository_test = STAGING / "tests" / "js" / "test-daily-readings-api.mjs"
    repository_test.write_text(
        repository_test.read_text(encoding="utf-8").replace(
            "daily-readings-alinya.mjs", "daily-readings.mjs"
        ),
        encoding="utf-8",
    )
    (STAGING / "tests" / "js" / "test-daily-readings-api-alinya.mjs").unlink(missing_ok=True)


def _validate() -> dict:
    missing = [path for path in REQUIRED_PATHS if not (STAGING / path).is_file()]
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
        for path in _files()
        if path.stat().st_size >= 100 * 1024 * 1024
    ]
    if oversized:
        raise RuntimeError(f"GitHub 100 MiB file limit exceeded: {oversized}")

    packages = sorted(
        path.name
        for path in STAGING.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
    if packages != ["ecoradar"]:
        raise RuntimeError(f"Expected exactly one top-level Python package, found {packages}")

    pyproject = (STAGING / "pyproject.toml").read_text(encoding="utf-8")
    for fragment in (
        "[tool.setuptools.packages.find]",
        'include = ["ecoradar", "ecoradar.*"]',
        "namespaces = false",
    ):
        if fragment not in pyproject:
            raise RuntimeError(f"pyproject.toml is missing {fragment}")

    timestamps = {
        _checked_at(STAGING / "metadata" / "daily_readings.json"),
        _checked_at(STAGING / "metadata" / "daily_history.json"),
        _checked_at(STAGING / "metadata" / "current_fire_danger.json"),
        _checked_at(STAGING / "projectes" / "Alinya" / "indicators" / "daily_readings.json"),
        _checked_at(STAGING / "projectes" / "Alinya" / "indicators" / "daily_history.json"),
        _checked_at(STAGING / "projectes" / "Alinya" / "indicators" / "current_fire_danger.json"),
    }
    if len(timestamps) != 1 or not next(iter(timestamps)):
        raise RuntimeError(f"Inconsistent checked_at_utc values: {timestamps}")

    if _sha256(STAGING / "index.html") != _sha256(
        STAGING / "projectes" / "Alinya" / "maps" / "ecoradar-alinya-netlify-v2" / "index.html"
    ):
        raise RuntimeError("Root index.html differs from the synchronized Alinyà Netlify package.")

    workflow = (
        STAGING / ".github" / "workflows" / "update-current-fire-danger.yml"
    ).read_text(encoding="utf-8")
    for fragment in (
        "pip install -e .",
        "ECORADAR_CHECKED_AT_UTC",
        "sync_alinya_repository_root.py --repository-root .",
        "git push origin",
        "npx --yes netlify-cli deploy --prod --dir .",
    ):
        if fragment not in workflow:
            raise RuntimeError(f"Incomplete GitHub workflow: missing {fragment}")
    if "projectes/LaSeu_Urba" in workflow:
        raise RuntimeError("Standalone Alinyà workflow depends on La Seu project data.")
    if "if [ -e projectes/Alinya/processed/ecostress ]; then" not in workflow:
        raise RuntimeError("Alinyà workflow must guard the optional ECOSTRESS output directory.")
    commit_block = workflow.split("- name: Commit refreshed data", 1)[1]
    first_git_add = commit_block.split("if [ -e projectes/Alinya/processed/ecostress ]", 1)[0]
    if "projectes/Alinya/processed/ecostress" in first_git_add:
        raise RuntimeError("Optional ECOSTRESS output must not be part of the unconditional git add.")

    files = _files()
    return {
        "checked_at_utc": next(iter(timestamps)),
        "file_count": len(files),
        "uncompressed_bytes": sum(path.stat().st_size for path in files),
    }


def _write_manifest(validation: dict) -> None:
    entries = [
        {
            "path": path.relative_to(STAGING).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in _files()
    ]
    payload = {
        "schema_version": "1.0",
        "package": "EcoRadar — Muntanya d'Alinyà",
        "built_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "canonical_checked_at_utc": validation["checked_at_utc"],
        "archive_layout": "repository files are stored directly at ZIP root",
        "excluded_as_regenerable_or_non_operational": [
            "virtual environments, caches and secret files",
            "previous releases, backup PDFs, old interactive viewers and ZIP archives",
            "the six 46 MiB ICGC source-cover tiles; their normalized and mapped derivatives remain included",
            "all other EcoRadar study areas",
        ],
        "file_count_excluding_this_manifest": len(entries),
        "uncompressed_bytes_excluding_this_manifest": sum(item["bytes"] for item in entries),
        "files": entries,
    }
    (STAGING / "repository-manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _zip() -> None:
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(path for path in STAGING.rglob("*") if path.is_file()):
            archive.write(path, path.relative_to(STAGING).as_posix())


def build() -> dict:
    if not LA_SEU_RELEASE.is_dir():
        raise FileNotFoundError(LA_SEU_RELEASE)
    if not NETLIFY_PACKAGE.is_dir():
        raise FileNotFoundError(NETLIFY_PACKAGE)
    RELEASES.mkdir(parents=True, exist_ok=True)
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)

    for name in ROOT_FILES:
        source = ROOT / name if (ROOT / name).is_file() else LA_SEU_RELEASE / name
        shutil.copy2(source, STAGING / name)
    for name in ROOT_DIRECTORIES:
        source = ROOT / name if (ROOT / name).is_dir() else LA_SEU_RELEASE / name
        _copy_tree(source, STAGING / name)
    _copy_tree(PROJECT, STAGING / "projectes" / "Alinya")
    _prepare_project_specific_files()

    (STAGING / MARKER).write_text(
        "Standalone EcoRadar Alinyà repository. Required by the guarded root synchronizer.\n",
        encoding="utf-8",
    )
    shutil.copy2(
        ROOT / "docs" / "deployment" / "alinya_github_repository_readme.md",
        STAGING / "README.md",
    )
    workflow_target = STAGING / ".github" / "workflows" / "update-current-fire-danger.yml"
    workflow_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs" / "deployment" / "update-alinya-current-fire-danger.yml", workflow_target)

    sync_repository_root(STAGING)
    validation = _validate()
    _write_manifest(validation)
    _zip()
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        names = set(archive.namelist())
    if bad:
        raise RuntimeError(f"Corrupt ZIP member: {bad}")
    missing = [path for path in REQUIRED_PATHS if path not in names]
    if missing:
        raise RuntimeError(f"Required files absent from ZIP: {missing}")

    result = {
        **validation,
        "staging": str(STAGING),
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": _sha256(ZIP_PATH),
        "zip_members": len(names),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    build()
