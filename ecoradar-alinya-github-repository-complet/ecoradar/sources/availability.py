"""Mandatory EcoRadar data availability gate.

This module checks the central source catalogue before EcoRadar Core,
diagnosis, recommendations or report generation. It does not download data,
does not run analysis and never creates substitute values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "data_sources.yaml"
DIRECT_CONNECTORS = {
    "ecoradar.core.study_area",
    "connector_icgc_cobertes_sol",
    "connector_habitats",
    "connector_biodiversitat",
    "connector_recreational_pressure_osm",
    "connector_icgc_dem_mdt",
    "connector_aca_hidrologia",
    "connector_connectivitat_ecologica",
    "connector_incendis_historial",
}

AVAILABILITY_JSON = "metadata/data_availability_report.json"
AVAILABILITY_MD = "reports/data_availability_report.md"
CONNECTORS_JSON = "metadata/connectors_status_report.json"
COMPLETENESS_JSON = "metadata/indicators_completeness_report.json"


@dataclass(frozen=True)
class AvailabilityPaths:
    data_availability_json: Path
    data_availability_markdown: Path
    connectors_status_json: Path
    indicators_completeness_json: Path


def load_data_sources(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load the central source catalogue.

    The file uses JSON-compatible YAML so EcoRadar does not need a runtime YAML
    dependency for the mandatory gate.
    """

    path = Path(config_path)
    return json.loads(path.read_text(encoding="utf-8"))


def run_data_availability_check(
    project_root: str | Path = ROOT / "projectes" / "Alinya",
    *,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Create mandatory source, connector and indicator completeness reports."""

    root = Path(project_root)
    metadata_dir = root / "metadata"
    reports_dir = root / "reports"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    config = load_data_sources(config_path)
    source_rows = _evaluate_sources(config, root)
    availability = _build_availability_report(config, root, source_rows)
    connectors = _build_connectors_report(source_rows)
    completeness = _build_completeness_report(config, source_rows)

    paths = AvailabilityPaths(
        data_availability_json=root / AVAILABILITY_JSON,
        data_availability_markdown=root / AVAILABILITY_MD,
        connectors_status_json=root / CONNECTORS_JSON,
        indicators_completeness_json=root / COMPLETENESS_JSON,
    )
    paths.data_availability_json.write_text(json.dumps(availability, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths.connectors_status_json.write_text(json.dumps(connectors, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths.indicators_completeness_json.write_text(json.dumps(completeness, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths.data_availability_markdown.write_text(_markdown(availability, connectors, completeness), encoding="utf-8")

    return {
        "data_availability_report": str(paths.data_availability_json),
        "data_availability_markdown": str(paths.data_availability_markdown),
        "connectors_status_report": str(paths.connectors_status_json),
        "indicators_completeness_report": str(paths.indicators_completeness_json),
        "summary": availability["summary"],
    }


def mandatory_preflight_exists(project_root: str | Path) -> bool:
    root = Path(project_root)
    return all(
        (root / rel).exists()
        for rel in (AVAILABILITY_JSON, CONNECTORS_JSON, COMPLETENESS_JSON)
    )


def ensure_mandatory_preflight(project_root: str | Path) -> None:
    if not mandatory_preflight_exists(project_root):
        raise RuntimeError(
            "EcoRadar mandatory data availability gate has not been executed. "
            "Run tools/run_data_availability_check.py before Core, diagnosis or reports."
        )


def _evaluate_sources(config: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in config.get("blocks", []):
        for source in block.get("sources", []):
            rows.append(_evaluate_source(block, source, project_root))
    return rows


def _evaluate_source(block: dict[str, Any], source: dict[str, Any], project_root: Path) -> dict[str, Any]:
    expected_outputs = source.get("expected_outputs", [])
    resolved_outputs = [_resolve_output(project_root, rel) for rel in expected_outputs]
    existing = [path for path in resolved_outputs if path.exists()]
    missing = [path for path in resolved_outputs if not path.exists()]
    credentials = source.get("requires_credentials", [])
    missing_credentials = [name for name in credentials if not os.environ.get(name)]
    connector = source.get("responsible_connector", "")
    access_type = str(source.get("access_type", "")).lower()

    if ("legal" in access_type or connector.startswith("blocked_")) and not existing:
        status = "legalment_condicionada"
        connector_status = "requereix intervenció manual"
    elif expected_outputs and len(existing) == len(expected_outputs):
        status = "consultada_correctament"
        connector_status = "implementat" if connector in DIRECT_CONNECTORS else _non_direct_connector_status(connector, access_type)
    elif missing_credentials:
        status = "requereix_credencials"
        connector_status = "requereix intervenció manual"
    elif existing:
        status = "parcial"
        connector_status = "parcial"
    elif "fitxer manual" in access_type or "consulta manual" in access_type:
        status = "manual_pendent"
        connector_status = "requereix intervenció manual"
    elif connector.startswith("pending_") or connector.startswith("blocked_"):
        status = "no_implementada"
        connector_status = "pendent" if connector.startswith("pending_") else "requereix intervenció manual"
    else:
        status = "fallida"
        connector_status = "fallit"

    downloaded = [str(path.relative_to(project_root)) for path in existing if path.is_file()]
    if any(path.is_dir() for path in existing):
        downloaded.extend(str(path.relative_to(project_root)) for path in existing if path.is_dir())

    return {
        "block_id": block.get("id"),
        "block_name": block.get("name"),
        "source_id": source.get("id"),
        "source_name": source.get("name"),
        "url": source.get("url"),
        "access_type": source.get("access_type"),
        "expected_format": source.get("expected_format"),
        "responsible_connector": connector,
        "connector_status": connector_status,
        "minimum_fields": source.get("minimum_fields", []),
        "feeds_indicators": source.get("feeds_indicators", []),
        "required": bool(source.get("required")),
        "status": status,
        "missing_credentials": missing_credentials,
        "downloaded_data": downloaded,
        "missing_outputs": [str(path.relative_to(project_root)) for path in missing],
        "on_failure": source.get("on_failure"),
        "error_message": source.get("error_message"),
        "confidence_if_missing": source.get("confidence_if_missing"),
    }


def _non_direct_connector_status(connector: str, access_type: str) -> str:
    if connector.startswith("pending_"):
        return "pendent"
    if connector.startswith("blocked_"):
        return "requereix intervenció manual"
    if "manual" in access_type:
        return "requereix intervenció manual"
    return "parcial"


def _build_availability_report(config: dict[str, Any], project_root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = _counts(row["status"] for row in rows)
    block_summaries = []
    for block in config.get("blocks", []):
        block_rows = [row for row in rows if row["block_id"] == block.get("id")]
        block_summaries.append(
            {
                "block_id": block.get("id"),
                "block_name": block.get("name"),
                "source_count": len(block_rows),
                "status_counts": _counts(row["status"] for row in block_rows),
            }
        )
    affected: dict[str, list[str]] = {}
    for row in rows:
        if row["status"] == "consultada_correctament":
            continue
        for indicator in row.get("feeds_indicators", []):
            affected.setdefault(indicator, []).append(str(row["source_id"]))

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project_root": str(project_root),
        "config": "config/data_sources.yaml",
        "policy": config.get("policy", {}),
        "summary": {
            "total_sources": len(rows),
            "status_counts": status_counts,
            "sources_ok": status_counts.get("consultada_correctament", 0),
            "sources_partial": status_counts.get("parcial", 0),
            "sources_failed": status_counts.get("fallida", 0),
            "sources_not_implemented": status_counts.get("no_implementada", 0),
            "sources_require_credentials": status_counts.get("requereix_credencials", 0),
            "sources_manual_pending": status_counts.get("manual_pendent", 0),
            "sources_legal_conditioned": status_counts.get("legalment_condicionada", 0),
        },
        "blocks": block_summaries,
        "sources": rows,
        "downloaded_data": sorted({item for row in rows for item in row["downloaded_data"]}),
        "unavailable_data": [
            {
                "source_id": row["source_id"],
                "source_name": row["source_name"],
                "status": row["status"],
                "required": row["required"],
                "affected_indicators": row["feeds_indicators"],
                "message": row["error_message"],
            }
            for row in rows
            if row["status"] != "consultada_correctament"
        ],
        "indicators_affected_by_missing_data": affected,
    }


def _build_connectors_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    connectors: dict[str, dict[str, Any]] = {}
    for row in rows:
        connector_id = row["responsible_connector"]
        current = connectors.setdefault(
            connector_id,
            {
                "connector": connector_id,
                "status": row["connector_status"],
                "sources": [],
                "downloaded_data": [],
                "missing_outputs": [],
                "requires_manual_intervention": False,
            },
        )
        current["sources"].append(row["source_id"])
        current["downloaded_data"].extend(row["downloaded_data"])
        current["missing_outputs"].extend(row["missing_outputs"])
        current["requires_manual_intervention"] = current["requires_manual_intervention"] or row["connector_status"] == "requereix intervenció manual"
        current["status"] = _merge_connector_status(current["status"], row["connector_status"])

    connector_list = sorted(connectors.values(), key=lambda item: item["connector"])
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "connectors": connector_list,
        "summary": _counts(item["status"] for item in connector_list),
    }


def _merge_connector_status(current: str, new: str) -> str:
    order = {
        "fallit": 5,
        "requereix intervenció manual": 4,
        "parcial": 3,
        "pendent": 2,
        "implementat": 1,
    }
    return current if order.get(current, 0) >= order.get(new, 0) else new


def _build_completeness_report(config: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    indicators = [f"CORE_{index:02d}" for index in range(1, 13)]
    by_indicator: dict[str, list[dict[str, Any]]] = {indicator: [] for indicator in indicators}
    for row in rows:
        for indicator in row.get("feeds_indicators", []):
            by_indicator.setdefault(indicator, []).append(row)

    report_rows = []
    for indicator in indicators:
        related = by_indicator.get(indicator, [])
        required = [row for row in related if row["required"]]
        denominator = len(required) or len(related)
        considered = required or related
        score = sum(_source_score(row["status"]) for row in considered)
        percent = round((score / denominator * 100), 1) if denominator else 0.0
        report_rows.append(
            {
                "indicator": indicator,
                "required_sources": [row["source_id"] for row in required],
                "all_sources": [row["source_id"] for row in related],
                "available_sources": [row["source_id"] for row in related if row["status"] == "consultada_correctament"],
                "partial_sources": [row["source_id"] for row in related if row["status"] == "parcial"],
                "missing_sources": [row["source_id"] for row in related if row["status"] not in {"consultada_correctament", "parcial"}],
                "data_available_percent": percent,
                "status": _indicator_status(percent),
                "confidence": _confidence(percent),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "indicators": report_rows,
        "summary": {
            "complete": sum(1 for row in report_rows if row["status"] == "DISPONIBLE"),
            "partial": sum(1 for row in report_rows if row["status"] == "PARCIAL"),
            "not_available": sum(1 for row in report_rows if row["status"] == "NO DISPONIBLE"),
        },
    }


def _source_score(status: str) -> float:
    if status == "consultada_correctament":
        return 1.0
    if status == "parcial":
        return 0.5
    return 0.0


def _indicator_status(percent: float) -> str:
    if percent >= 90:
        return "DISPONIBLE"
    if percent > 0:
        return "PARCIAL"
    return "NO DISPONIBLE"


def _confidence(percent: float) -> str:
    if percent >= 80:
        return "alta"
    if percent >= 50:
        return "mitjana"
    return "baixa"


def _markdown(availability: dict[str, Any], connectors: dict[str, Any], completeness: dict[str, Any]) -> str:
    lines = [
        "# Data Availability Report",
        "",
        f"Projecte: `{availability['project_root']}`",
        f"Generat: `{availability['generated_at']}`",
        "",
        "## Resum",
        "",
        "| Estat | Nombre |",
        "| --- | ---: |",
    ]
    for status, count in sorted(availability["summary"]["status_counts"].items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Fonts per bloc", "", "| Bloc | Fonts | Estat |", "| --- | ---: | --- |"])
    for block in availability["blocks"]:
        status = ", ".join(f"{key}: {value}" for key, value in sorted(block["status_counts"].items()))
        lines.append(f"| {block['block_name']} | {block['source_count']} | {status} |")

    lines.extend(["", "## Fonts consultades correctament", ""])
    ok = [row for row in availability["sources"] if row["status"] == "consultada_correctament"]
    lines.extend(_source_bullets(ok))

    lines.extend(["", "## Fonts fallides, no implementades, amb credencials o manuals pendents", ""])
    not_ok = [row for row in availability["sources"] if row["status"] != "consultada_correctament"]
    lines.extend(_source_bullets(not_ok))

    lines.extend(["", "## Dades descarregades o disponibles localment", ""])
    if availability["downloaded_data"]:
        lines.extend(f"- `{item}`" for item in availability["downloaded_data"])
    else:
        lines.append("- Cap dada disponible localment.")

    lines.extend(["", "## Indicadors afectats per dades mancants", "", "| Indicador | Completesa | Estat | Confiança | Fonts mancants |", "| --- | ---: | --- | --- | --- |"])
    for row in completeness["indicators"]:
        missing = ", ".join(row["missing_sources"]) or "-"
        lines.append(f"| {row['indicator']} | {row['data_available_percent']}% | {row['status']} | {row['confidence']} | {missing} |")

    lines.extend(["", "## Estat de connectors", "", "| Connector | Estat | Fonts |", "| --- | --- | --- |"])
    for connector in connectors["connectors"]:
        lines.append(f"| {connector['connector']} | {connector['status']} | {', '.join(connector['sources'])} |")
    lines.append("")
    return "\n".join(lines)


def _source_bullets(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["- Cap."]
    return [
        f"- **{row['block_name']} / {row['source_name']}**: `{row['status']}`; connector `{row['responsible_connector']}`; indicadors {', '.join(row['feeds_indicators']) or '-'}."
        for row in rows
    ]


def _resolve_output(project_root: Path, relative: str) -> Path:
    return project_root / relative.format(project=project_root.name)


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts
