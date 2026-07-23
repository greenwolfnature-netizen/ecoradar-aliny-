"""Management recommendations derived from EcoRadar diagnosis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
from pathlib import Path
from typing import Any

from ecoradar.core.context import ProjectContext
from ecoradar.sources.availability import ensure_mandatory_preflight
from ecoradar.diagnosis.engine import build_diagnosis


@dataclass(frozen=True)
class ManagementRecommendation:
    """One technically justified management recommendation."""

    priority: int
    action_type: str
    objective: str
    justification: str
    location: str
    expected_ecological_benefit: str
    supporting_indicators: tuple[str, ...]
    confidence: str


def generate_recommendation_outputs(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    from ecoradar.core.recommendation_engine import run_recommendation_engine

    result = run_recommendation_engine(project_root)
    return {
        "json": result["recommendations_json"],
        "csv": result["priority_matrix_csv"],
        "markdown": result["recommendations_markdown"],
        "recommendation_count": result["recommendation_count"],
    }


def build_recommendations(context: ProjectContext) -> tuple[ManagementRecommendation, ...]:
    diagnosis = build_diagnosis(context)
    core_rows = context.read_csv("indicators/ecoradar_core.csv")
    core = {row.get("code", ""): row for row in core_rows}

    recommendations = [
        ManagementRecommendation(
            1,
            "conservar",
            "Protegir hàbitats d'interès i hàbitats prioritaris abans de qualsevol actuació.",
            core.get("CORE_02", {}).get("brief_interpretation", "El valor d'hàbitats és un dels senyals més forts de la diagnosi."),
            "Zones cartografiades com HIC o HIC prioritari dins l'àrea d'estudi.",
            "Reduir risc d'impacte sobre hàbitats de responsabilitat de conservació.",
            ("CORE_02",),
            core.get("CORE_02", {}).get("confidence", "mitjana"),
        ),
        ManagementRecommendation(
            2,
            "validar",
            "Validar prats, espais oberts i discontinuïtats que poden sostenir mosaic ecològic.",
            "El mosaic és parcialment favorable, però encara falta continuïtat espacial i lectura de camp.",
            "Espais oberts, ecotons i zones de contacte entre bosc, prats i matollars.",
            "Mantenir heterogeneïtat útil per biodiversitat, connectivitat i resiliència al foc.",
            ("CORE_01", "CORE_09"),
            "mitjana-baixa",
        ),
        ManagementRecommendation(
            3,
            "monitoritzar",
            "Comprovar accessos, punts d'ús públic i possibles concentracions de freqüentació.",
            core.get("CORE_07", {}).get("brief_interpretation", "La pressió humana només està representada com accessibilitat potencial."),
            "Camins, pistes, aparcaments i punts d'ús públic cartografiats.",
            "Evitar conflictes entre ús públic i conservació abans de proposar regulació.",
            ("CORE_07",),
            core.get("CORE_07", {}).get("confidence", "baixa"),
        ),
        ManagementRecommendation(
            4,
            "ampliar dades",
            "Incorporar teledetecció, hidrologia, DEM i històric de foc abans de prioritzar restauració.",
            "Els indicadors de vegetació, aigua, potencial de restauració i prioritat final no són calculables amb rigor.",
            "Tot l'àmbit; especialment zones forestals contínues, fondalades, riberes i espais oberts.",
            "Convertir una diagnosi preliminar en una priorització espacial fiable.",
            ("CORE_03", "CORE_05", "CORE_10", "CORE_11", "CORE_12"),
            "alta",
        ),
        ManagementRecommendation(
            5,
            "treball de camp",
            "Planificar mostreig dirigit per validar biodiversitat, microhàbitats i punts sensibles.",
            diagnosis.fieldwork_needs[0].interpretation if diagnosis.fieldwork_needs else "Les fonts públiques no certifiquen absències ni estat local.",
            "Zones amb HIC, accessos principals, punts d'aigua potencials i grups taxonòmics infrarepresentats.",
            "Millorar confiança de la diagnosi i evitar actuacions incompatibles amb espècies o hàbitats sensibles.",
            ("CORE_02", "CORE_06", "CORE_07"),
            "mitjana",
        ),
    ]
    return tuple(recommendations)


def _write_csv(context: ProjectContext, recommendations: tuple[ManagementRecommendation, ...]) -> Path:
    path = context.project_root / "indicators" / "ecoradar_recommendations.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(recommendations[0]).keys()))
        writer.writeheader()
        for recommendation in recommendations:
            row = asdict(recommendation)
            row["supporting_indicators"] = "; ".join(row["supporting_indicators"])
            writer.writerow(row)
    return path


def _write_markdown(context: ProjectContext, recommendations: tuple[ManagementRecommendation, ...]) -> Path:
    path = context.project_root / "reports" / "ecoradar_recommendations.md"
    lines = [f"# Recomanacions EcoRadar · {context.project_name}", ""]
    for recommendation in recommendations:
        lines.extend(
            [
                f"## {recommendation.priority}. {recommendation.action_type.title()}",
                "",
                f"Objectiu: {recommendation.objective}",
                "",
                f"Justificació: {recommendation.justification}",
                "",
                f"Localització: {recommendation.location}",
                "",
                f"Benefici ecològic esperat: {recommendation.expected_ecological_benefit}",
                "",
                f"Indicadors: {', '.join(recommendation.supporting_indicators)}",
                "",
                f"Confiança: {recommendation.confidence}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
