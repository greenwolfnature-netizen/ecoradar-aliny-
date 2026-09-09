"""EcoRadar report value gate.

Any new EcoRadar functionality should strengthen the Integrated Ecological
Diagnosis Report first. This module turns missing or partial evidence into a
ranked list of improvements for the full diagnosis; the Fitxa inherits those
improvements later as an executive summary, without downloading data or
inventing values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
from pathlib import Path
from typing import Any

from ecoradar.core.context import ProjectContext


@dataclass(frozen=True)
class FitxaValueItem:
    """One improvement candidate ranked by expected diagnosis value."""

    priority: int
    title: str
    fitxa_section: str
    decision_unlocked: str
    required_evidence: tuple[str, ...]
    supporting_indicators: tuple[str, ...]
    value_level: str
    implementation_note: str


def generate_fitxa_value_outputs(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Write report-first value-gate outputs for a project."""

    context = ProjectContext.from_root(project_root)
    context.ensure_output_dirs()
    items = build_fitxa_value_items(context)
    payload = {
        "project": context.project_name,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "principle": (
            "Prioritzar funcionalitats que reforcin la Fitxa EcoRadar i la capacitat de "
            "l'Informe de Diagnosi Ecològica Integrada per justificar-ne les conclusions."
        ),
        "items": [asdict(item) for item in items],
    }
    json_path = context.write_json("metadata/ecoradar_fitxa_value_gate.json", payload)
    csv_path = _write_csv(context, items)
    md_path = _write_markdown(context, items)
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
        "top_priority": items[0].title if items else None,
        "item_count": len(items),
    }


def build_fitxa_value_items(context: ProjectContext) -> tuple[FitxaValueItem, ...]:
    core_rows = context.read_csv("indicators/ecoradar_core_indicators.csv")
    core = {row.get("code", ""): row for row in core_rows}
    candidates = [
        _item(
            1,
            "Figura de protecció i context administratiu",
            "Capítol territorial, protecció, mapa resum i fonts",
            "Saber quin marc normatiu condiciona qualsevol actuació de gestió.",
            ("Espais protegits oficials", "Natura 2000/PEIN/ENPE si escau", "límits administratius"),
            ("study_area",),
            "molt alt",
            "No crear un connector nou fins confirmar integració amb fonts ja verificades; és la dada que reforça la lectura territorial de la Fitxa i després la seva justificació a l'informe.",
        ),
        _item(
            2,
            "Teledetecció de vegetació i humitat",
            "Capítols de vegetació, clima, vulnerabilitat i resum executiu",
            "Distingir zones amb vigor, estrès hídric i possibles refugis o vulnerabilitats.",
            _missing(core, "CORE_03", fallback=("NDVI", "NDMI", "NDWI", "LST")),
            ("CORE_03", "CORE_04", "CORE_05"),
            "molt alt",
            "Només executar quan hi hagi credencials Copernicus i productes reals; no generar ràsters substitutius.",
        ),
        _item(
            3,
            "Hidrologia funcional",
            "Capítol d'hidrologia, oportunitats, mapa de prioritats i actuacions",
            "Identificar corredors hídrics, punts d'aigua, refugis i restauració vinculada a l'aigua.",
            _missing(core, "CORE_10", fallback=("cursos fluvials", "fonts", "basses", "zones humides")),
            ("CORE_10", "CORE_04", "CORE_11"),
            "molt alt",
            "Prioritzar fonts oficials ACA/ICGC ja documentades abans de qualsevol model derivat.",
        ),
        _item(
            4,
            "Relleu, pendent i orientació",
            "Capítols de clima, foc, refugis climàtics i vulnerabilitat",
            "Separar solanes, obagues, pendents crítics i zones amb potencial microclimàtic.",
            ("DEM", "pendent", "orientació", "insolació potencial"),
            ("CORE_04", "CORE_05", "CORE_09"),
            "alt",
            "Derivar només de DEM oficial verificat; aporta valor visual i de gestió a l'informe i a la síntesi executiva posterior.",
        ),
        _item(
            5,
            "Històric d'incendis i continuïtat del combustible",
            "Capítol de foc, amenaces, mapa de prioritats i actuacions prioritàries",
            "Diferenciar on cal mantenir mosaic, reduir continuïtat o evitar actuacions que perjudiquin hàbitats.",
            _missing(core, "CORE_09", fallback=("incendis històrics", "continuïtat forestal", "combustible")),
            ("CORE_09", "CORE_01", "CORE_02"),
            "alt",
            "Respectar la Fire Data Rule: no usar IncendisCat com a font i verificar l'upstream oficial abans de connector.",
        ),
        _item(
            6,
            "Validació de camp dirigida",
            "Validació, confiança, fortaleses, pressions i actuacions",
            "Convertir una diagnosi preliminar en una diagnosi defensable davant gestors i propietat.",
            ("validació d'HIC", "accessos principals", "punts d'aigua", "grups infrarepresentats"),
            ("CORE_02", "CORE_06", "CORE_07"),
            "alt",
            "Ha d'entrar com a dades traçables, no com a text lliure dins l'informe.",
        ),
    ]
    return tuple(candidates)


def _item(
    priority: int,
    title: str,
    fitxa_section: str,
    decision_unlocked: str,
    required_evidence: tuple[str, ...],
    supporting_indicators: tuple[str, ...],
    value_level: str,
    implementation_note: str,
) -> FitxaValueItem:
    return FitxaValueItem(
        priority=priority,
        title=title,
        fitxa_section=fitxa_section,
        decision_unlocked=decision_unlocked,
        required_evidence=required_evidence,
        supporting_indicators=supporting_indicators,
        value_level=value_level,
        implementation_note=implementation_note,
    )


def _missing(core: dict[str, dict[str, str]], code: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    row = core.get(code, {})
    raw = row.get("sources_absent") or row.get("missing_data", "")
    values = tuple(item.strip() for item in raw.split(";") if item.strip())
    return values or fallback


def _write_csv(context: ProjectContext, items: tuple[FitxaValueItem, ...]) -> Path:
    path = context.project_root / "indicators" / "ecoradar_fitxa_value_gate.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(items[0]).keys()))
        writer.writeheader()
        for item in items:
            row = asdict(item)
            row["required_evidence"] = "; ".join(row["required_evidence"])
            row["supporting_indicators"] = "; ".join(row["supporting_indicators"])
            writer.writerow(row)
    return path


def _write_markdown(context: ProjectContext, items: tuple[FitxaValueItem, ...]) -> Path:
    path = context.project_root / "reports" / "ecoradar_fitxa_value_gate.md"
    lines = [
        f"# EcoRadar · Value Gate de l'Informe Integrat · {context.project_name}",
        "",
        "Criteri: qualsevol desenvolupament nou ha de reforçar la Fitxa EcoRadar o desbloquejar una decisió del gestor. L'Informe de Diagnosi Ecològica Integrada es genera després com a justificació tècnica de la Fitxa.",
        "",
        "| Prioritat | Millora | Capítol o síntesi afectada | Decisió que desbloqueja |",
        "| ---: | --- | --- | --- |",
    ]
    for item in items:
        lines.append(f"| {item.priority} | {item.title} | {item.fitxa_section} | {item.decision_unlocked} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
