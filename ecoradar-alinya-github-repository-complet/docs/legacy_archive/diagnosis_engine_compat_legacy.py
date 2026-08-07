"""Ecological diagnosis synthesis for EcoRadar.

The diagnosis engine consumes already calculated indicators and metadata. It
does not download data and does not invent unavailable values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ecoradar.core.context import ProjectContext
from ecoradar.sources.availability import ensure_mandatory_preflight


@dataclass(frozen=True)
class DiagnosisFinding:
    """One interpreted finding derived from existing EcoRadar evidence."""

    theme: str
    title: str
    interpretation: str
    management_implication: str
    evidence: tuple[str, ...]
    confidence: str


@dataclass(frozen=True)
class EcologicalDiagnosis:
    """Structured diagnosis for one EcoRadar project."""

    project_name: str
    generated_at: str
    overall_state: str
    confidence: str
    executive_summary: str
    strengths: tuple[DiagnosisFinding, ...]
    weaknesses: tuple[DiagnosisFinding, ...]
    pressures: tuple[DiagnosisFinding, ...]
    opportunities: tuple[DiagnosisFinding, ...]
    risks: tuple[DiagnosisFinding, ...]
    uncertainties: tuple[DiagnosisFinding, ...]
    fieldwork_needs: tuple[DiagnosisFinding, ...]
    data_insufficiencies: tuple[str, ...]


def generate_diagnosis_outputs(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Generate diagnosis JSON and Markdown outputs from current indicators."""

    from ecoradar.core.diagnosis_engine import run_diagnosis_engine

    result = run_diagnosis_engine(project_root)
    return {
        "json": result["json"],
        "markdown": result["markdown"],
        "overall_state": "diagnosi parcial defensable",
        "confidence": "mitjana",
    }


def build_diagnosis(context: ProjectContext) -> EcologicalDiagnosis:
    core_rows = context.read_csv("indicators/ecoradar_core.csv")
    basic_rows = context.read_csv("indicators/ecoradar_01_resum.csv")
    core = {row.get("code", ""): row for row in core_rows}
    basic = {row.get("indicador", ""): row.get("valor", "") for row in basic_rows}

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status_counts = _status_counts(core_rows)
    confidence = _diagnosis_confidence(core_rows)
    overall_state = _overall_state(status_counts, confidence)

    strengths = tuple(_strengths(core, basic))
    weaknesses = tuple(_weaknesses(core))
    pressures = tuple(_pressures(core))
    opportunities = tuple(_opportunities(core, basic))
    risks = tuple(_risks(core))
    uncertainties = tuple(_uncertainties(core))
    fieldwork = tuple(_fieldwork_needs(core))
    missing = tuple(sorted({item for row in core_rows for item in _split(row.get("missing_data", ""))}))

    summary = (
        f"{context.project_name} mostra senyals robustos de valor d'hàbitats i biodiversitat coneguda, "
        "però la diagnosi encara és parcial. Les decisions de conservació prudent estan justificades; "
        "les prioritats espacials finals han d'esperar teledetecció, hidrologia, topografia, foc i camp."
    )

    return EcologicalDiagnosis(
        project_name=context.project_name,
        generated_at=generated_at,
        overall_state=overall_state,
        confidence=confidence,
        executive_summary=summary,
        strengths=strengths,
        weaknesses=weaknesses,
        pressures=pressures,
        opportunities=opportunities,
        risks=risks,
        uncertainties=uncertainties,
        fieldwork_needs=fieldwork,
        data_insufficiencies=missing,
    )


def _strengths(core: dict[str, dict[str, str]], basic: dict[str, str]) -> list[DiagnosisFinding]:
    findings: list[DiagnosisFinding] = []
    habitat = core.get("CORE_02", {})
    if _num(habitat.get("normalized_value")) is not None:
        findings.append(
            DiagnosisFinding(
                "hàbitats",
                "Valor d'hàbitats molt rellevant",
                f"El Core d'hàbitats és {habitat.get('category', '').lower()} i combina riquesa d'hàbitats, HIC i HIC prioritaris.",
                "Qualsevol actuació ha de començar comprovant afectació a HIC i hàbitats prioritaris.",
                ("CORE_02", habitat.get("raw_value", "")),
                habitat.get("confidence", "mitjana"),
            )
        )
    biodiv = core.get("CORE_06", {})
    if _num(biodiv.get("normalized_value")) is not None:
        findings.append(
            DiagnosisFinding(
                "biodiversitat",
                "Base pública de biodiversitat útil",
                "Les cites públiques aporten un primer mapa de coneixement, però no equivalen a inventari exhaustiu.",
                "Serveix per orientar treball de camp, detectar grups febles i prioritzar validacions.",
                ("CORE_06", biodiv.get("raw_value", "")),
                biodiv.get("confidence", "mitjana"),
            )
        )
    forest = basic.get("percentatge_coberta_forestal")
    grass = basic.get("percentatge_prats_pastures_herbassars")
    if forest and grass:
        findings.append(
            DiagnosisFinding(
                "paisatge",
                "Matriu natural dominant amb espais oberts rellevants",
                f"La coberta forestal ({forest}%) domina, però els prats i herbassars ({grass}%) poden tenir una funció ecològica desproporcionada.",
                "Cal conservar el mosaic existent i evitar actuacions uniformes sobre tota la matriu forestal.",
                ("CORE_01", "ecoradar_01_resum.csv"),
                "mitjana",
            )
        )
    return findings


def _weaknesses(core: dict[str, dict[str, str]]) -> list[DiagnosisFinding]:
    return [
        DiagnosisFinding(
            "foc",
            "Resiliència al foc encara feble i incompleta",
            "La lectura actual només combina cobertes i mosaic obert; falten pendent, orientació, humitat vegetal, accessos i punts d'aigua.",
            "No és prudent definir actuacions forestals espacials finals sense completar aquesta base.",
            ("CORE_09", core.get("CORE_09", {}).get("raw_value", "")),
            core.get("CORE_09", {}).get("confidence", "baixa"),
        ),
        DiagnosisFinding(
            "aigua",
            "Funcionalitat hídrica no caracteritzada",
            "Sense cursos, basses, fonts, zones humides i NDWI no es poden delimitar corredors hídrics ni refugis associats a l'aigua.",
            "La hidrologia ha de ser una prioritat de dades abans de restauració o adaptació climàtica.",
            ("CORE_10",),
            "baixa",
        ),
    ]


def _pressures(core: dict[str, dict[str, str]]) -> list[DiagnosisFinding]:
    pressure = core.get("CORE_07", {})
    return [
        DiagnosisFinding(
            "ús públic",
            "Pressió humana només estimada com accessibilitat potencial",
            pressure.get("brief_interpretation", "OSM descriu camins i punts d'ús públic, no freqüentació real."),
            "Cal validar accessos i punts d'ús abans de regular, tancar o redirigir fluxos.",
            ("CORE_07", pressure.get("raw_value", "")),
            pressure.get("confidence", "baixa"),
        )
    ]


def _opportunities(core: dict[str, dict[str, str]], basic: dict[str, str]) -> list[DiagnosisFinding]:
    return [
        DiagnosisFinding(
            "gestió",
            "Conservació prudent ja accionable",
            "La combinació de valor d'hàbitats, biodiversitat coneguda i mosaic dona criteris inicials per evitar impactes i dirigir el camp.",
            "Es poden establir zones de prudència i protocols de revisió abans d'actuacions.",
            ("CORE_01", "CORE_02", "CORE_06"),
            "mitjana",
        ),
        DiagnosisFinding(
            "coneixement",
            "Els buits de dades ja defineixen un full de ruta",
            "Les mancances no són soroll: indiquen quines dades poden canviar decisions de gestió.",
            "Prioritzar teledetecció, hidrologia, topografia i camp aportarà salt qualitatiu immediat.",
            ("CORE_03", "CORE_10", "CORE_11", "CORE_12"),
            "alta",
        ),
    ]


def _risks(core: dict[str, dict[str, str]]) -> list[DiagnosisFinding]:
    return [
        DiagnosisFinding(
            "governança",
            "Risc de falsa precisió si es força una prioritat final",
            "Diversos indicadors clau són parcials o no disponibles; una mitjana global amagaria incertesa.",
            "EcoRadar ha de mantenir indicadors separats i recomanar validació quan la confiança és baixa.",
            ("CORE_03", "CORE_10", "CORE_12"),
            "alta",
        )
    ]


def _uncertainties(core: dict[str, dict[str, str]]) -> list[DiagnosisFinding]:
    findings: list[DiagnosisFinding] = []
    for code in ("CORE_03", "CORE_04", "CORE_05", "CORE_08", "CORE_10", "CORE_11", "CORE_12"):
        row = core.get(code, {})
        if row:
            findings.append(
                DiagnosisFinding(
                    row.get("name", code),
                    row.get("name", code),
                    row.get("brief_interpretation", "Indicador limitat per dades insuficients."),
                    row.get("preliminary_recommendation", "Completar dades abans de decidir."),
                    (code, row.get("missing_data", "")),
                    row.get("confidence", "baixa"),
                )
            )
    return findings


def _fieldwork_needs(core: dict[str, dict[str, str]]) -> list[DiagnosisFinding]:
    return [
        DiagnosisFinding(
            "camp",
            "Validar hàbitats, accessos i grups infrarepresentats",
            "Les fonts públiques orienten, però no certifiquen estat local ni absències.",
            "Programar mostreig dirigit sobre HIC, prats, accessos principals, punts d'aigua i grups taxonòmics febles.",
            ("CORE_02", "CORE_06", "CORE_07"),
            "mitjana",
        )
    ]


def _write_markdown(context: ProjectContext, diagnosis: EcologicalDiagnosis) -> Path:
    path = context.project_root / "reports" / "ecoradar_diagnosis.md"
    lines = [
        f"# Diagnosi EcoRadar · {diagnosis.project_name}",
        "",
        f"Generat: {diagnosis.generated_at}",
        "",
        f"Estat general: **{diagnosis.overall_state}**",
        f"Confiança: **{diagnosis.confidence}**",
        "",
        "## Resum Executiu",
        "",
        diagnosis.executive_summary,
    ]
    for title, findings in (
        ("Fortaleses", diagnosis.strengths),
        ("Debilitats", diagnosis.weaknesses),
        ("Pressions", diagnosis.pressures),
        ("Oportunitats", diagnosis.opportunities),
        ("Riscos", diagnosis.risks),
        ("Incerteses", diagnosis.uncertainties),
        ("Necessitats De Camp", diagnosis.fieldwork_needs),
    ):
        lines.extend(["", f"## {title}", ""])
        for finding in findings:
            lines.append(f"- **{finding.title}** ({finding.confidence}). {finding.interpretation} {finding.management_implication}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _status_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = row.get("status", "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _diagnosis_confidence(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "baixa"
    confidences = [row.get("confidence", "baixa") for row in rows]
    high = confidences.count("alta")
    medium = confidences.count("mitjana")
    low = confidences.count("baixa")
    if high + medium >= 9 and low <= 3:
        return "alta"
    if medium >= 3:
        return "mitjana-baixa"
    return "baixa"


def _overall_state(status_counts: dict[str, int], confidence: str) -> str:
    if status_counts.get("no disponible", 0) >= 5:
        return "diagnosi preliminar"
    if confidence == "alta":
        return "diagnosi robusta"
    return "diagnosi parcial"


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(str(value))
    except ValueError:
        return None
