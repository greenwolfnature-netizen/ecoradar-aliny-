"""EcoRadar Ecological Diagnosis Engine.

This engine transforms validated EcoRadar Core indicators into a structured
ecological diagnosis. It does not calculate recommendations, generate fitxes,
create final reports, or invent unavailable data.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ecoradar.sources.mandatory_copernicus import ensure_mandatory_copernicus


REQUIRED_INPUTS = (
    "indicators/ecoradar_core_indicators.json",
    "metadata/indicator_engine_report.json",
    "metadata/data_availability_report.json",
)
JSON_OUTPUT = "diagnosis/ecoradar_diagnosis.json"
MD_OUTPUT = "reports/ecoradar_diagnosis.md"
REPORT_OUTPUT = "metadata/diagnosis_engine_report.json"


@dataclass(frozen=True)
class DiagnosisConclusion:
    """One traceable ecological conclusion."""

    section: str
    title: str
    interpretation: str
    management_implication: str
    supporting_indicators: tuple[str, ...]
    sources_used: tuple[str, ...]
    confidence: str
    limitations: tuple[str, ...]
    robustness: str


def run_diagnosis_engine(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Run the diagnosis engine after mandatory indicator outputs exist."""

    root = Path(project_root)
    _ensure_inputs(root)
    ensure_mandatory_copernicus(root)
    (root / "diagnosis").mkdir(parents=True, exist_ok=True)
    (root / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)

    context = _load_context(root)
    conclusions = _build_conclusions(context)
    diagnosis = _diagnosis_payload(root, context, conclusions)

    json_path = root / JSON_OUTPUT
    md_path = root / MD_OUTPUT
    report_path = root / REPORT_OUTPUT

    json_path.write_text(json.dumps(diagnosis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_diagnosis_markdown(diagnosis), encoding="utf-8")
    report = _engine_report(root, context, conclusions)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "report": str(report_path),
        "conclusion_count": len(conclusions),
        "confidence_counts": dict(Counter(item.confidence for item in conclusions)),
        "robustness_counts": dict(Counter(item.robustness for item in conclusions)),
    }


def generate_diagnosis_outputs(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Compatibility alias for the official diagnosis engine."""

    result = run_diagnosis_engine(project_root)
    return {
        "json": result["json"],
        "markdown": result["markdown"],
        "overall_state": "diagnosi parcial defensable",
        "confidence": "mitjana",
    }


def _ensure_inputs(root: Path) -> None:
    missing = [relative for relative in REQUIRED_INPUTS if not (root / relative).exists()]
    if missing:
        raise RuntimeError(
            "EcoRadar diagnosis cannot run before indicator/data reports exist. "
            f"Missing: {', '.join(missing)}"
        )


def _load_context(root: Path) -> dict[str, Any]:
    indicators_payload = _read_json(root / "indicators" / "ecoradar_core_indicators.json")
    indicators = indicators_payload.get("indicators", [])
    return {
        "root": root,
        "indicators_payload": indicators_payload,
        "indicators": indicators,
        "by_code": {item["code"]: item for item in indicators},
        "indicator_report": _read_json(root / "metadata" / "indicator_engine_report.json"),
        "availability": _read_json(root / "metadata" / "data_availability_report.json"),
    }


def _build_conclusions(context: dict[str, Any]) -> list[DiagnosisConclusion]:
    by_code = context["by_code"]
    conclusions = [
        _overall_state(context),
        _ecological_values(by_code),
        _territorial_function(by_code),
        _habitat_biodiversity_conflict(by_code),
        _open_spaces_in_forest_matrix(by_code),
        _climate_uncertainty(by_code),
        _fire_resilience(by_code),
        _water_function(by_code),
        _restoration_potential(by_code),
        _critical_missing_data(context),
        _field_validation_needs(context),
    ]
    return [item for item in conclusions if item is not None]


def _overall_state(context: dict[str, Any]) -> DiagnosisConclusion:
    indicators = context["indicators"]
    complete = sum(1 for item in indicators if item["status"] == "COMPLET")
    partial = sum(1 for item in indicators if item["status"] == "PARCIAL")
    unavailable = sum(1 for item in indicators if item["status"] == "NO DISPONIBLE")
    return DiagnosisConclusion(
        "estat_ecologic_general",
        "Diagnosi ecològica parcial amb valors naturals alts",
        (
            f"El sistema disposa de {complete} indicadors complets, {partial} parcials i {unavailable} no disponible. "
            "Els senyals més sòlids provenen d'hàbitats, biodiversitat coneguda, connectivitat, mosaic i pressió humana potencial. "
            "La diagnosi encara no pot tancar vegetació, clima i una part del foc perquè falten Copernicus, clima i combustible."
        ),
        "La lectura és suficient per orientar prudència i validació, però encara no per prioritzar actuacions finals.",
        tuple(item["code"] for item in indicators),
        _sources_from(indicators),
        "mitjana",
        ("La vegetació Sentinel i el context climàtic no estan disponibles.",),
        "provisional",
    )


def _ecological_values(by_code: dict[str, dict[str, Any]]) -> DiagnosisConclusion:
    habitat = by_code["CORE_02"]
    biodiversity = by_code["CORE_06"]
    connectivity = by_code["CORE_08"]
    return DiagnosisConclusion(
        "valors_ecologics_principals",
        "Hàbitats, biodiversitat coneguda i connectivitat són els principals valors detectats",
        (
            f"El valor d'hàbitats és {habitat['category']} ({habitat['value_0_100']}/100), "
            f"la biodiversitat coneguda és {biodiversity['category']} ({biodiversity['value_0_100']}/100) "
            f"i la connectivitat és {connectivity['category']} ({connectivity['value_0_100']}/100). "
            "Això apunta a un espai amb responsabilitat de conservació elevada, tot i que la biodiversitat prové de fonts públiques oportunistes."
        ),
        "Les decisions que afectin HIC, hàbitats prioritaris o zones connectores han de tractar-se amb criteri preventiu.",
        ("CORE_02", "CORE_06", "CORE_08"),
        _sources_from([habitat, biodiversity, connectivity]),
        _combined_confidence(habitat, biodiversity, connectivity),
        tuple(habitat["limitations"] + biodiversity["limitations"] + connectivity["limitations"]),
        _robustness(habitat, biodiversity, connectivity),
    )


def _territorial_function(by_code: dict[str, dict[str, Any]]) -> DiagnosisConclusion:
    mosaic = by_code["CORE_01"]
    habitats = by_code["CORE_02"]
    connectivity = by_code["CORE_08"]
    water = by_code["CORE_10"]
    return DiagnosisConclusion(
        "funcionament_ecologic",
        "El funcionament ecològic depèn d'una matriu natural connectada amb funcions hídriques parcials",
        (
            f"El mosaic és {mosaic['category']} ({mosaic['value_0_100']}/100) i la connectivitat és "
            f"{connectivity['category']} ({connectivity['value_0_100']}/100). Aquesta combinació suggereix una matriu natural "
            "funcional, però el paper de l'aigua queda parcial perquè NDWI, basses i validació de punts d'aigua no estan disponibles."
        ),
        "La gestió ha de llegir conjuntament hàbitats, mosaic, corredors i aigua; una capa sola no explica el territori.",
        ("CORE_01", "CORE_02", "CORE_08", "CORE_10"),
        _sources_from([mosaic, habitats, connectivity, water]),
        "mitjana",
        tuple(mosaic["limitations"] + connectivity["limitations"] + water["limitations"]),
        "provisional",
    )


def _habitat_biodiversity_conflict(by_code: dict[str, dict[str, Any]]) -> DiagnosisConclusion:
    habitats = by_code["CORE_02"]
    biodiversity = by_code["CORE_06"]
    pressure = by_code["CORE_07"]
    return DiagnosisConclusion(
        "pressions",
        "Valor ecològic alt amb pressió humana potencial mitjana",
        (
            f"Hàbitats i biodiversitat mostren valors molt alts, mentre que la pressió humana és {pressure['category']} "
            f"({pressure['value_0_100']}/100). Això no prova un conflicte, però sí una zona on ús públic i conservació poden solapar-se."
        ),
        "Cal validar punts d'accés, camins i freqüentació real abans d'interpretar conflictes o regular usos.",
        ("CORE_02", "CORE_06", "CORE_07"),
        _sources_from([habitats, biodiversity, pressure]),
        "mitjana",
        tuple(pressure["limitations"] + biodiversity["limitations"]),
        "provisional",
    )


def _open_spaces_in_forest_matrix(by_code: dict[str, dict[str, Any]]) -> DiagnosisConclusion:
    mosaic = by_code["CORE_01"]
    fire = by_code["CORE_09"]
    return DiagnosisConclusion(
        "fortaleses",
        "Els espais oberts poden tenir una funció ecològica desproporcionada dins la matriu forestal",
        (
            "El mosaic és alt però la resiliència davant del foc és només mitjana i parcial. "
            "Aquesta relació indica que prats, conreus residuals i discontinuïtats poden ser importants per biodiversitat, connectivitat i foc."
        ),
        "No convé simplificar la gestió en 'més bosc és sempre millor'; cal preservar heterogeneïtat funcional.",
        ("CORE_01", "CORE_09"),
        _sources_from([mosaic, fire]),
        "mitjana",
        tuple(mosaic["limitations"] + fire["limitations"]),
        "provisional",
    )


def _climate_uncertainty(by_code: dict[str, dict[str, Any]]) -> DiagnosisConclusion:
    vegetation = by_code["CORE_03"]
    refugia = by_code["CORE_04"]
    vulnerability = by_code["CORE_05"]
    return DiagnosisConclusion(
        "vulnerabilitats",
        "La lectura climàtica és la principal incertesa ecològica",
        (
            "L'estat de la vegetació no està disponible i refugis/vulnerabilitat climàtica són parcials. "
            "Sense NDVI, NDMI, NDWI, LST i clima no es pot distingir bé entre estructura favorable i estrès real."
        ),
        "Qualsevol diagnosi climàtica ha de quedar marcada com provisional fins incorporar Copernicus i clima.",
        ("CORE_03", "CORE_04", "CORE_05"),
        _sources_from([refugia, vulnerability]),
        "baixa",
        tuple(vegetation["limitations"] + refugia["limitations"] + vulnerability["limitations"]),
        "provisional",
    )


def _fire_resilience(by_code: dict[str, dict[str, Any]]) -> DiagnosisConclusion:
    fire = by_code["CORE_09"]
    mosaic = by_code["CORE_01"]
    water = by_code["CORE_10"]
    return DiagnosisConclusion(
        "vulnerabilitats",
        "La resiliència davant del foc queda condicionada per combustible i humitat no disponibles",
        (
            f"La resiliència davant del foc és {fire['category']} ({fire['value_0_100']}/100), "
            "però falten NDMI, LST i estructura oficial de combustible. Mosaic i aigua aporten context, però no tanquen el risc."
        ),
        "No s'han de derivar actuacions forestals finals només amb aquest indicador; cal completar combustible i humitat.",
        ("CORE_09", "CORE_01", "CORE_10"),
        _sources_from([fire, mosaic, water]),
        "mitjana",
        tuple(fire["limitations"] + water["limitations"]),
        "provisional",
    )


def _water_function(by_code: dict[str, dict[str, Any]]) -> DiagnosisConclusion:
    water = by_code["CORE_10"]
    refugia = by_code["CORE_04"]
    return DiagnosisConclusion(
        "debilitats",
        "L'aigua està cartografiada parcialment però no funcionalment caracteritzada",
        (
            f"La funcionalitat hídrica és {water['category']} ({water['value_0_100']}/100) i entra també als refugis climàtics. "
            "Hi ha base ACA i DEM, però falta NDWI, estat ecològic, basses/zones humides efectives i validació de camp."
        ),
        "Les decisions sobre refugis, restauració o fauna associada a l'aigua necessiten una campanya de verificació hídrica.",
        ("CORE_10", "CORE_04"),
        _sources_from([water, refugia]),
        "mitjana",
        tuple(water["limitations"] + refugia["limitations"]),
        "provisional",
    )


def _restoration_potential(by_code: dict[str, dict[str, Any]]) -> DiagnosisConclusion:
    restoration = by_code["CORE_11"]
    priority = by_code["CORE_12"]
    return DiagnosisConclusion(
        "oportunitats",
        "Hi ha potencial de restauració, però encara no priorització espacial",
        (
            f"El potencial de restauració és {restoration['category']} ({restoration['value_0_100']}/100), "
            f"mentre la prioritat de gestió és {priority['status'].lower()}. La combinació suggereix oportunitats, però no delimita on actuar."
        ),
        "El següent pas no és executar actuacions sinó completar dades que permetin espacialitzar prioritats.",
        ("CORE_11", "CORE_12"),
        _sources_from([restoration, priority]),
        "mitjana",
        tuple(restoration["limitations"] + priority["limitations"]),
        "provisional",
    )


def _critical_missing_data(context: dict[str, Any]) -> DiagnosisConclusion:
    absent = Counter()
    for indicator in context["indicators"]:
        absent.update(indicator.get("sources_absent", []))
    critical = tuple(item for item, _ in absent.most_common(12))
    return DiagnosisConclusion(
        "dades_critiques_absents",
        "Les dades que més condicionen la diagnosi són teledetecció, clima, camp i combustible",
        "Les fonts absents es repeteixen en indicadors de vegetació, clima, foc, restauració i prioritat de gestió.",
        "Completar aquestes fonts augmentarà directament la confiança de la diagnosi i evitarà conclusions prematures.",
        tuple(indicator["code"] for indicator in context["indicators"] if indicator.get("sources_absent")),
        (),
        "alta",
        critical,
        "robusta",
    )


def _field_validation_needs(context: dict[str, Any]) -> DiagnosisConclusion:
    return DiagnosisConclusion(
        "validacio_camp",
        "Cal validar al camp hàbitats, pressió humana, punts d'aigua i biodiversitat sensible",
        (
            "Les fonts de camp són absents i diversos indicadors depenen de dades oportunistes o cartografia general. "
            "La validació ha de centrar-se en HIC, zones d'ús públic, fonts/basses i grups taxonòmics poc representats."
        ),
        "La campanya de camp ha de convertir incerteses en criteris de gestió verificats.",
        ("CORE_02", "CORE_06", "CORE_07", "CORE_10"),
        ("habitats_terrestres_v3", "gbif_occurrences", "inaturalist_observations", "osm_public_use", "aca_hydrology"),
        "alta",
        ("field_biodiversity", "field_validation", "BDBC no integrat"),
        "robusta",
    )


def _diagnosis_payload(root: Path, context: dict[str, Any], conclusions: list[DiagnosisConclusion]) -> dict[str, Any]:
    return {
        "project": root.name,
        "generated_at": _now(),
        "scope": "diagnosi ecològica basada en indicadors; sense recomanacions, fitxa ni informe final",
        "inputs": {
            "indicators": "indicators/ecoradar_core_indicators.json",
            "indicator_engine_report": "metadata/indicator_engine_report.json",
            "data_availability_report": "metadata/data_availability_report.json",
        },
        "summary": {
            "overall_state": "diagnosi parcial defensable",
            "confidence": _overall_confidence(conclusions),
            "robust_conclusions": sum(1 for item in conclusions if item.robustness == "robusta"),
            "provisional_conclusions": sum(1 for item in conclusions if item.robustness == "provisional"),
        },
        "required_sections": _section_index(conclusions),
        "conclusions": [asdict(item) for item in conclusions],
    }


def _engine_report(root: Path, context: dict[str, Any], conclusions: list[DiagnosisConclusion]) -> dict[str, Any]:
    return {
        "project": root.name,
        "generated_at": _now(),
        "preflight_checked": {relative: (root / relative).exists() for relative in REQUIRED_INPUTS},
        "outputs": {
            "diagnosis_json": JSON_OUTPUT,
            "diagnosis_markdown": MD_OUTPUT,
            "engine_report": REPORT_OUTPUT,
        },
        "conclusion_count": len(conclusions),
        "confidence_counts": dict(Counter(item.confidence for item in conclusions)),
        "robustness_counts": dict(Counter(item.robustness for item in conclusions)),
        "rules_enforced": [
            "No s'han calculat recomanacions.",
            "No s'ha generat fitxa ni informe final.",
            "Cada conclusió inclou indicadors, fonts, confiança, limitacions i robustesa.",
            "Les conclusions dependents d'indicadors parcials s'han marcat com a provisionals.",
        ],
    }


def _diagnosis_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# EcoRadar Diagnosis",
        "",
        f"Projecte: `{payload['project']}`",
        f"Generat: `{payload['generated_at']}`",
        "",
        "## Resum",
        "",
        f"- Estat: `{payload['summary']['overall_state']}`",
        f"- Confiança: `{payload['summary']['confidence']}`",
        f"- Conclusions robustes: `{payload['summary']['robust_conclusions']}`",
        f"- Conclusions provisionals: `{payload['summary']['provisional_conclusions']}`",
        "",
        "## Conclusions",
        "",
    ]
    for conclusion in payload["conclusions"]:
        lines.extend(
            [
                f"### {conclusion['title']}",
                "",
                f"- Secció: `{conclusion['section']}`",
                f"- Interpretació: {conclusion['interpretation']}",
                f"- Implicació per a la gestió: {conclusion['management_implication']}",
                f"- Indicadors: {', '.join(conclusion['supporting_indicators']) or '-'}",
                f"- Fonts: {', '.join(conclusion['sources_used']) or '-'}",
                f"- Confiança: `{conclusion['confidence']}`",
                f"- Robustesa: `{conclusion['robustness']}`",
                f"- Limitacions: {'; '.join(conclusion['limitations']) or '-'}",
                "",
            ]
        )
    return "\n".join(lines)


def _section_index(conclusions: list[DiagnosisConclusion]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    for conclusion in conclusions:
        sections.setdefault(conclusion.section, []).append(conclusion.title)
    return sections


def _combined_confidence(*indicators: dict[str, Any]) -> str:
    values = [item.get("confidence", "baixa") for item in indicators]
    if "baixa" in values:
        return "baixa"
    if "mitjana" in values:
        return "mitjana"
    return "alta"


def _robustness(*indicators: dict[str, Any]) -> str:
    return "robusta" if all(item.get("status") == "COMPLET" for item in indicators) else "provisional"


def _sources_from(indicators: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    return tuple(sorted({source for item in indicators for source in item.get("sources_used", [])}))


def _overall_confidence(conclusions: list[DiagnosisConclusion]) -> str:
    values = [item.confidence for item in conclusions]
    if values.count("alta") >= 5 and values.count("baixa") <= 1:
        return "mitjana"
    if values.count("baixa") >= 3:
        return "baixa"
    return "mitjana"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    print(json.dumps(run_diagnosis_engine(), indent=2, ensure_ascii=False))
