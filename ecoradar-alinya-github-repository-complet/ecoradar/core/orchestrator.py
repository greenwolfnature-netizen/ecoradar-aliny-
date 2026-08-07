"""EcoRadar full pipeline orchestrator.

The orchestrator wires together existing EcoRadar modules. It does not create
new connectors, indicators, diagnosis rules, recommendations or report logic.
It only controls execution order, validates hand-offs between steps and writes
traceability reports for each run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import unicodedata
from typing import Any, Callable

from ecoradar.core.study_area import load_study_area
from ecoradar.datastore.project_store import build_project_datastore
from ecoradar.diagnosis.engine import run_diagnosis_engine
from ecoradar.indicators.engine import run_indicator_engine
from ecoradar.recommendations.engine import run_recommendation_engine
from ecoradar.sources.data_source_manager import run_data_source_manager
from ecoradar.sources.mandatory_copernicus import ensure_mandatory_copernicus, required_copernicus_outputs
from ecoradar.validation.engine import ensure_validation_passed, run_validation_engine


REPORT_JSON = "metadata/ecoradar_execution_report.json"
REPORT_MD = "reports/ecoradar_execution_report.md"


def _slugify_project(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    return slug or "projecte"


@dataclass(frozen=True)
class PipelineStep:
    """One orchestrated EcoRadar step."""

    number: int
    name: str
    critical: bool
    status: str
    duration_seconds: float
    started_at: str
    finished_at: str
    outputs: tuple[str, ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ConnectorTask:
    """Existing connector or connector output set managed by the orchestrator."""

    id: str
    module: str
    outputs: tuple[str, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)
    requires_credentials: bool = False


CONNECTOR_TASKS: tuple[ConnectorTask, ...] = (
    ConnectorTask(
        id="connector_icgc_cobertes_sol",
        module="ecoradar.connectors.connector_icgc_cobertes_sol",
        outputs=(
            "processed/cobertes_sol.gpkg",
            "indicators/cobertes_sol_resum.csv",
            "metadata/cobertes_sol_metadata.json",
        ),
    ),
    ConnectorTask(
        id="connector_habitats",
        module="ecoradar.connectors.connector_habitats",
        outputs=(
            "processed/habitats.gpkg",
            "indicators/habitats_resum.csv",
            "metadata/habitats_metadata.json",
        ),
    ),
    ConnectorTask(
        id="connector_icgc_dem_mdt",
        module="ecoradar.connectors.connector_icgc_dem_mdt",
        outputs=(
            "processed/terrain/dem.tif",
            "processed/terrain/slope.tif",
            "processed/terrain/aspect.tif",
            "metadata/terrain_metadata.json",
        ),
    ),
    ConnectorTask(
        id="connector_aca_hidrologia",
        module="ecoradar.connectors.connector_aca_hidrologia",
        outputs=(
            "processed/hidrologia.gpkg",
            "indicators/hidrologia_resum.csv",
            "metadata/hidrologia_metadata.json",
        ),
        kwargs={"refresh": False},
    ),
    ConnectorTask(
        id="connector_incendis_historial",
        module="ecoradar.connectors.connector_incendis_historial",
        outputs=(
            "processed/incendis.gpkg",
            "indicators/incendis_resum.csv",
            "metadata/incendis_metadata.json",
        ),
        kwargs={"refresh": False},
    ),
    ConnectorTask(
        id="connector_connectivitat_ecologica",
        module="ecoradar.connectors.connector_connectivitat_ecologica",
        outputs=(
            "processed/connectivitat.gpkg",
            "indicators/connectivitat_resum.csv",
            "metadata/connectivitat_metadata.json",
        ),
        kwargs={"refresh": False},
    ),
    ConnectorTask(
        id="connector_recreational_pressure_osm",
        module="ecoradar.connectors.connector_recreational_pressure_osm",
        outputs=(
            "processed/recreational_pressure.gpkg",
            "indicators/recreational_pressure_resum.csv",
            "metadata/recreational_pressure_metadata.json",
        ),
        kwargs={"refresh": False},
    ),
    ConnectorTask(
        id="connector_biodiversitat",
        module="ecoradar.connectors.connector_biodiversitat",
        outputs=(
            "processed/biodiversitat.gpkg",
            "indicators/biodiversitat_resum.csv",
            "metadata/biodiversitat_metadata.json",
        ),
    ),
    ConnectorTask(
        id="connector_copernicus_teledeteccio",
        module="ecoradar.connectors.connector_copernicus_teledeteccio",
        outputs=required_copernicus_outputs(),
        requires_credentials=True,
    ),
)


class EcoRadarPipelineError(RuntimeError):
    """Raised when a critical pipeline step cannot complete."""


class EcoRadarOrchestrator:
    """Run the complete EcoRadar workflow with explicit traceability."""

    def __init__(
        self,
        project_root: str | Path = "projectes/Alinya",
        *,
        refresh_connectors: bool = False,
        generate_documents: bool = True,
    ) -> None:
        self.project_root = Path(project_root)
        self.refresh_connectors = refresh_connectors
        self.generate_documents = generate_documents
        self.steps: list[PipelineStep] = []
        self.created_files: list[str] = []
        self.errors: list[dict[str, str]] = []

    def run(self) -> dict[str, Any]:
        """Execute the full EcoRadar workflow and return the run report."""

        self._ensure_project_dirs()
        aborted = False
        try:
            self._run_step(1, "Carregar l'àrea d'estudi", True, self._load_study_area)
            self._run_step(2, "Executar el Data Source Manager", True, self._run_data_source_manager)
            self._run_step(3, "Validar totes les fonts", True, self._validate_sources)
            self._run_step(4, "Executar els connectors disponibles", True, self._run_connectors)
            self._run_step(5, "Processar i normalitzar les dades", True, self._validate_processed_data)
            self._run_step(6, "Crear el Project Datastore", True, self._build_datastore)
            self._run_step(7, "Calcular els indicadors EcoRadar Core", True, self._run_indicators)
            self._run_step(8, "Executar el Motor de Diagnosi", True, self._run_diagnosis)
            self._run_step(9, "Executar el Motor de Recomanacions", True, self._run_recommendations)
            self._run_step(10, "Executar el Mòdul de Validació", True, self._run_validation)
            self._run_step(11, "Generar la Fitxa EcoRadar executiva", True, self._generate_fitxa)
            self._run_step(12, "Generar l'Informe de Diagnosi Ecològica Integrada", True, self._generate_technical_report)
        except EcoRadarPipelineError:
            aborted = True
        finally:
            self._run_step(
                13,
                "Generar tots els fitxers de traçabilitat",
                False,
                lambda: self._write_execution_report(aborted=aborted),
            )

        report = self._execution_payload(aborted=aborted)
        if aborted:
            raise EcoRadarPipelineError(self._abort_message(report))
        return report

    def _run_step(
        self,
        number: int,
        name: str,
        critical: bool,
        action: Callable[[], dict[str, Any]],
    ) -> PipelineStep:
        started_perf = time.perf_counter()
        started_at = _now()
        try:
            result = action()
            finished_at = _now()
            step = PipelineStep(
                number=number,
                name=name,
                critical=critical,
                status=result.get("status", "ok"),
                duration_seconds=round(time.perf_counter() - started_perf, 3),
                started_at=started_at,
                finished_at=finished_at,
                outputs=tuple(result.get("outputs", ())),
                summary=result.get("summary", {}),
            )
        except Exception as exc:
            finished_at = _now()
            error = f"{type(exc).__name__}: {exc}"
            self.errors.append({"step": name, "error": error, "traceback": traceback.format_exc()})
            step = PipelineStep(
                number=number,
                name=name,
                critical=critical,
                status="failed",
                duration_seconds=round(time.perf_counter() - started_perf, 3),
                started_at=started_at,
                finished_at=finished_at,
                error=error,
            )
            self.steps.append(step)
            if critical:
                raise EcoRadarPipelineError(error) from exc
            return step

        self.steps.append(step)
        if critical and step.status in {"failed", "blocked"}:
            raise EcoRadarPipelineError(f"Critical step failed: {name}")
        return step

    def _load_study_area(self) -> dict[str, Any]:
        study_area_path = self.project_root / "processed" / "study_area.gpkg"
        if not study_area_path.exists():
            raise FileNotFoundError(study_area_path)
        area = load_study_area(study_area_path, name=self.project_root.name, repair_geometry=False)
        return {
            "outputs": (str(study_area_path),),
            "summary": {
                "crs": area.metric_crs,
                "feature_count": area.feature_count,
                "surface_ha": area.area_ha,
                "perimeter_m": area.perimeter_m,
                "warnings": list(area.warnings),
            },
        }

    def _run_data_source_manager(self) -> dict[str, Any]:
        result = run_data_source_manager(self.project_root)
        outputs = (
            result.data_availability_report,
            result.data_availability_markdown,
            result.connectors_status_report,
            result.indicators_completeness_report,
        )
        self.created_files.extend(outputs)
        return {"outputs": outputs, "summary": result.summary}

    def _validate_sources(self) -> dict[str, Any]:
        required = (
            "metadata/data_availability_report.json",
            "metadata/connectors_status_report.json",
            "metadata/indicators_completeness_report.json",
        )
        self._ensure_files(required)
        availability = _read_json(self.project_root / "metadata" / "data_availability_report.json")
        connectors = _read_json(self.project_root / "metadata" / "connectors_status_report.json")
        sources = availability.get("sources", [])
        failed = [row for row in sources if str(row.get("status", "")).lower() in {"failed", "service_unavailable"}]
        credentials = [row for row in sources if "credential" in str(row.get("status", "")).lower()]
        return {
            "outputs": tuple(str(self.project_root / item) for item in required),
            "summary": {
                "source_count": len(sources),
                "failed_sources": len(failed),
                "credential_sources": len(credentials),
                "connector_count": len(connectors.get("connectors", [])),
            },
        }

    def _run_connectors(self) -> dict[str, Any]:
        connector_results: list[dict[str, Any]] = []
        hard_failures: list[str] = []

        for task in CONNECTOR_TASKS:
            result = self._run_connector_task(task)
            connector_results.append(result)
            if result["status"] == "failed_missing_outputs":
                hard_failures.append(task.id)
            if task.id == "connector_copernicus_teledeteccio":
                try:
                    ensure_mandatory_copernicus(self.project_root)
                except Exception as exc:
                    hard_failures.append(f"{task.id}: {exc}")

        if hard_failures:
            raise RuntimeError(f"Connectors without usable outputs: {', '.join(hard_failures)}")

        outputs = tuple(
            path
            for result in connector_results
            for path in result.get("outputs", [])
            if path
        )
        return {
            "outputs": outputs,
            "summary": {
                "connectors": connector_results,
                "status_counts": _counts(row["status"] for row in connector_results),
            },
        }

    def _run_connector_task(self, task: ConnectorTask) -> dict[str, Any]:
        existing_outputs = self._existing_outputs(task.outputs)
        if len(existing_outputs) == len(task.outputs) and not self.refresh_connectors:
            return {
                "id": task.id,
                "status": "cached_validated",
                "outputs": existing_outputs,
                "message": "Existing processed outputs validated; connector was not re-run to avoid duplicate downloads.",
            }

        try:
            module = importlib.import_module(task.module)
            run_connector = getattr(module, "run_connector")
            result = run_connector(**task.kwargs)
            outputs = self._existing_outputs(task.outputs)
            return {
                "id": task.id,
                "status": "executed",
                "outputs": outputs,
                "result": _safe_json(result),
            }
        except Exception as exc:
            outputs = self._existing_outputs(task.outputs)
            status = "failed_with_existing_outputs" if outputs else "failed_missing_outputs"
            if task.requires_credentials:
                status = "blocked_requires_credentials" if not outputs else "blocked_with_existing_outputs"
            return {
                "id": task.id,
                "status": status,
                "outputs": outputs,
                "message": f"{type(exc).__name__}: {exc}",
            }

    def _validate_processed_data(self) -> dict[str, Any]:
        required = (
            "processed/study_area.gpkg",
            "processed/cobertes_sol.gpkg",
            "processed/habitats.gpkg",
            "processed/biodiversitat.gpkg",
            "processed/recreational_pressure.gpkg",
        )
        optional = (
            "processed/hidrologia.gpkg",
            "processed/connectivitat.gpkg",
            "processed/incendis.gpkg",
            "processed/terrain/dem.tif",
        )
        missing_required = [item for item in required if not (self.project_root / item).exists()]
        if missing_required:
            raise FileNotFoundError(f"Missing processed data: {', '.join(missing_required)}")
        ensure_mandatory_copernicus(self.project_root)
        missing_optional = [item for item in optional if not (self.project_root / item).exists()]
        return {
            "outputs": tuple(
                str(self.project_root / item)
                for item in tuple(required) + required_copernicus_outputs()
                if (self.project_root / item).exists()
            ),
            "summary": {
                "required_processed_layers": len(required),
                "mandatory_copernicus_outputs": len(required_copernicus_outputs()),
                "optional_missing": missing_optional,
                "normalization_policy": "Validated existing processed outputs; no analysis performed in connector stage.",
            },
        }

    def _run_indicators(self) -> dict[str, Any]:
        result = run_indicator_engine(self.project_root)
        outputs = (result["csv"], result["json"], result["report_json"], result["report_md"])
        self.created_files.extend(outputs)
        return {"outputs": outputs, "summary": result}

    def _build_datastore(self) -> dict[str, Any]:
        datastore = build_project_datastore(self.project_root)
        outputs = (datastore.path, datastore.sqlite_path)
        self.created_files.extend(outputs)
        return {
            "outputs": outputs,
            "summary": {
                "asset_count": len(datastore.assets),
                "available_assets": sum(1 for item in datastore.assets if item.get("exists")),
            },
        }

    def _run_diagnosis(self) -> dict[str, Any]:
        result = run_diagnosis_engine(self.project_root)
        outputs = (result["json"], result["markdown"], result["report"])
        self.created_files.extend(outputs)
        return {"outputs": outputs, "summary": result}

    def _run_recommendations(self) -> dict[str, Any]:
        result = run_recommendation_engine(self.project_root)
        outputs = (
            result["recommendations_json"],
            result["recommendations_markdown"],
            result["priority_matrix_json"],
            result["priority_matrix_csv"],
        )
        self.created_files.extend(outputs)
        return {"outputs": outputs, "summary": result}

    def _run_validation(self) -> dict[str, Any]:
        result = run_validation_engine(self.project_root)
        outputs = (
            result["technical_validation"],
            result["ecological_validation"],
            result["field_validation_checklist"],
            result["recommendations_validation"],
            result["validation_report"],
        )
        self.created_files.extend(outputs)
        gate = result["final_outputs_gate"]
        if not gate.get("fitxa_and_final_report_allowed"):
            return {
                "status": "blocked",
                "outputs": outputs,
                "summary": result,
            }
        return {"outputs": outputs, "summary": result}

    def _generate_fitxa(self) -> dict[str, Any]:
        if not self.generate_documents:
            return {"status": "skipped", "summary": {"reason": "Document generation disabled"}}
        ensure_validation_passed(self.project_root)
        slug = _slugify_project(self.project_root.name)
        code = f"""
import shutil
from ecoradar.reporting import client_report_a4 as module
module.configure_project(r'''{self.project_root}''')
module.REPORTS.mkdir(parents=True, exist_ok=True)
module.OUTPUT.mkdir(parents=True, exist_ok=True)
data = module.prepare_inputs()
module.build_report(module.FITXA_PATH, data, include_all_pages=False)
shutil.copy2(module.FITXA_PATH, module.OUTPUT_FITXA_PATH)
print(module.FITXA_PATH)
"""
        self._run_document_python(code)
        outputs = (
            str(self.project_root / "reports" / f"fitxa_ecoradar_{slug}_a4.pdf"),
            str(Path("output/pdf") / f"fitxa_ecoradar_{slug}_a4.pdf"),
        )
        self._ensure_absolute_or_relative_files(outputs)
        self.created_files.extend(outputs)
        return {"outputs": outputs, "summary": {"format": "A4 portrait", "pages": "executive summary fitxa"}}

    def _generate_technical_report(self) -> dict[str, Any]:
        if not self.generate_documents:
            return {"status": "skipped", "summary": {"reason": "Document generation disabled"}}
        ensure_validation_passed(self.project_root)
        slug = _slugify_project(self.project_root.name)
        fitxa = self.project_root / "reports" / f"fitxa_ecoradar_{slug}_a4.pdf"
        if not fitxa.exists():
            raise FileNotFoundError(
                f"L'informe de diagnosi s'ha de generar després de la Fitxa EcoRadar: {fitxa}"
            )
        code = f"""
import shutil
from ecoradar.reporting import client_report_a4 as module
module.configure_project(r'''{self.project_root}''')
module.REPORTS.mkdir(parents=True, exist_ok=True)
module.OUTPUT.mkdir(parents=True, exist_ok=True)
data = module.prepare_inputs()
module.build_report(module.REPORT_PATH, data, include_all_pages=True)
shutil.copy2(module.REPORT_PATH, module.OUTPUT_REPORT_PATH)
print(module.REPORT_PATH)
"""
        self._run_document_python(code)
        outputs = (
            str(self.project_root / "reports" / f"informe_ecoradar_{slug}_a4_client.pdf"),
            str(Path("output/pdf") / f"informe_ecoradar_{slug}_a4_client.pdf"),
        )
        self._ensure_absolute_or_relative_files(outputs)
        self.created_files.extend(outputs)
        return {
            "outputs": outputs,
            "summary": {
                "format": "A4 portrait",
                "pages": "integrated ecological diagnosis report",
                "product_role": "primary",
            },
        }

    def _write_execution_report(self, *, aborted: bool) -> dict[str, Any]:
        payload = self._execution_payload(aborted=aborted)
        json_path = self.project_root / REPORT_JSON
        md_path = self.project_root / REPORT_MD
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        md_path.write_text(_execution_markdown(payload), encoding="utf-8")
        self.created_files.extend((str(json_path), str(md_path)))
        return {"outputs": (str(json_path), str(md_path)), "summary": {"aborted": aborted}}

    def _execution_payload(self, *, aborted: bool) -> dict[str, Any]:
        availability = _read_json(self.project_root / "metadata" / "data_availability_report.json")
        indicators = (
            _read_json(self.project_root / "indicators" / "ecoradar_core_indicators.json")
            if self._step_completed(7)
            else {}
        )
        recommendations = (
            _read_json(self.project_root / "recommendations" / "recommendations.json")
            if self._step_completed(9)
            else {}
        )
        failed_states = {"failed", "service_unavailable", "fallida", "servei_no_disponible"}
        usable_states = {
            "ok",
            "works",
            "funciona",
            "available",
            "verified",
            "consultada_correctament",
            "implementat",
        }
        failed_sources = [
            row for row in availability.get("sources", []) if str(row.get("status", "")).lower() in failed_states
        ]
        used_sources = [
            row.get("source_id") or row.get("id") or row.get("name")
            for row in availability.get("sources", [])
            if str(row.get("status", "")).lower() in usable_states
        ]
        return {
            "project": self.project_root.name,
            "generated_at": _now(),
            "status": "aborted" if aborted else "completed",
            "modules_executed": [asdict(step) for step in self.steps],
            "total_duration_seconds": round(sum(step.duration_seconds for step in self.steps), 3),
            "sources_used": [item for item in used_sources if item],
            "sources_failed": failed_sources,
            "indicators_calculated": [
                {
                    "code": row.get("code"),
                    "name": row.get("name"),
                    "status": row.get("status"),
                    "confidence": row.get("confidence"),
                    "value_0_100": row.get("value_0_100"),
                }
                for row in indicators.get("indicators", [])
            ],
            "recommendations_generated": [
                {
                    "id": row.get("id"),
                    "title": row.get("title"),
                    "group": row.get("group"),
                    "priority": row.get("ecological_priority_score"),
                }
                for row in recommendations.get("recommendations", [])
            ],
            "files_created": sorted(set(self.created_files)),
            "errors_detected": self.errors,
        }

    def _step_completed(self, number: int) -> bool:
        return any(step.number == number and step.status == "ok" for step in self.steps)

    def _abort_message(self, report: dict[str, Any]) -> str:
        errors = report.get("errors_detected", [])
        if not errors:
            return "EcoRadar pipeline aborted without an error payload."
        last = errors[-1]
        return f"EcoRadar pipeline aborted at '{last.get('step')}': {last.get('error')}"

    def _ensure_project_dirs(self) -> None:
        for directory in ("metadata", "reports", "recommendations", "indicators"):
            (self.project_root / directory).mkdir(parents=True, exist_ok=True)

    def _ensure_files(self, relatives: tuple[str, ...]) -> None:
        missing = [item for item in relatives if not (self.project_root / item).exists()]
        if missing:
            raise FileNotFoundError(", ".join(missing))

    def _ensure_absolute_or_relative_files(self, paths: tuple[str, ...]) -> None:
        missing = []
        for item in paths:
            path = Path(item)
            candidate = path if path.is_absolute() else Path.cwd() / path
            if not candidate.exists():
                missing.append(item)
        if missing:
            raise FileNotFoundError(", ".join(missing))

    def _existing_outputs(self, relatives: tuple[str, ...]) -> list[str]:
        return [str(self.project_root / item) for item in relatives if (self.project_root / item).exists()]

    def _run_document_python(self, code: str) -> None:
        python = _document_python()
        env = os.environ.copy()
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(Path.cwd()) if not current_pythonpath else f"{Path.cwd()}{os.pathsep}{current_pythonpath}"
        completed = subprocess.run(
            [str(python), "-c", code],
            cwd=Path.cwd(),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"Document generation failed with {python}: {details}")


def run_ecoradar_pipeline(
    project_root: str | Path = "projectes/Alinya",
    *,
    refresh_connectors: bool = False,
    generate_documents: bool = True,
) -> dict[str, Any]:
    """Run the complete EcoRadar pipeline."""

    orchestrator = EcoRadarOrchestrator(
        project_root,
        refresh_connectors=refresh_connectors,
        generate_documents=generate_documents,
    )
    return orchestrator.run()


def _execution_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Informe d'execució EcoRadar",
        "",
        f"Projecte: `{payload['project']}`",
        f"Generat: `{payload['generated_at']}`",
        f"Estat: `{payload['status']}`",
        f"Temps total: `{payload['total_duration_seconds']}` segons",
        "",
        "## Mòduls executats",
        "",
        "| Pas | Mòdul | Estat | Temps (s) | Sortides | Error |",
        "|---:|---|---|---:|---:|---|",
    ]
    for step in payload["modules_executed"]:
        lines.append(
            "| {number} | {name} | {status} | {duration_seconds} | {outputs} | {error} |".format(
                number=step["number"],
                name=step["name"],
                status=step["status"],
                duration_seconds=step["duration_seconds"],
                outputs=len(step.get("outputs", [])),
                error=step.get("error") or "",
            )
        )
    lines.extend(
        [
            "",
            "## Fonts",
            "",
            f"- Fonts utilitzades o disponibles: `{len(payload['sources_used'])}`",
            f"- Fonts fallides: `{len(payload['sources_failed'])}`",
            "",
            "## Indicadors calculats",
            "",
            "| Codi | Nom | Estat | Confiança | Valor |",
            "|---|---|---|---|---:|",
        ]
    )
    for row in payload["indicators_calculated"]:
        lines.append(
            f"| {row.get('code')} | {row.get('name')} | {row.get('status')} | "
            f"{row.get('confidence')} | {row.get('value_0_100')} |"
        )
    lines.extend(["", "## Recomanacions generades", "", "| ID | Grup | Prioritat | Títol |", "|---|---|---:|---|"])
    for row in payload["recommendations_generated"]:
        lines.append(f"| {row.get('id')} | {row.get('group')} | {row.get('priority')} | {row.get('title')} |")
    lines.extend(["", "## Fitxers creats", ""])
    for path in payload["files_created"]:
        lines.append(f"- `{path}`")
    if payload["errors_detected"]:
        lines.extend(["", "## Errors detectats", ""])
        for error in payload["errors_detected"]:
            lines.append(f"- `{error.get('step')}`: {error.get('error')}")
    else:
        lines.extend(["", "## Errors detectats", "", "No s'han detectat errors crítics en aquesta execució."])
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


def _document_python() -> Path:
    """Return a Python runtime with ReportLab/PDF dependencies."""

    try:
        import reportlab  # noqa: F401

        return Path(sys.executable)
    except ModuleNotFoundError:
        bundled = (
            Path.home()
            / ".cache"
            / "codex-runtimes"
            / "codex-primary-runtime"
            / "dependencies"
            / "python"
            / "bin"
            / "python3"
        )
        if bundled.exists():
            return bundled
        raise


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
