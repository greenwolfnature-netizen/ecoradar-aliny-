"""EcoRadar Recommendation and Prioritization Engine.

Recommendations are derived exclusively from the ecological diagnosis. The
engine does not generate fitxes, final reports or PDFs, and it does not propose
actions unsupported by indicators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
from typing import Any

from ecoradar.sources.mandatory_copernicus import ensure_mandatory_copernicus


REQUIRED_INPUTS = (
    "diagnosis/ecoradar_diagnosis.json",
    "metadata/diagnosis_engine_report.json",
    "indicators/ecoradar_core_indicators.json",
)
RECOMMENDATIONS_JSON = "recommendations/recommendations.json"
RECOMMENDATIONS_MD = "recommendations/recommendations.md"
PRIORITY_JSON = "recommendations/priority_matrix.json"
PRIORITY_CSV = "recommendations/priority_matrix.csv"

GROUP_ORDER = {
    "Conservació": 1,
    "Restauració": 2,
    "Gestió": 3,
    "Seguiment": 4,
    "Treball de camp": 5,
    "Dades pendents": 6,
}

URGENCY_SCORE = {"molt alta": 4, "alta": 3, "mitjana": 2, "baixa": 1}
DIFFICULTY_SCORE = {"baixa": 3, "mitjana": 2, "alta": 1}
CONFIDENCE_SCORE = {"alta": 3, "mitjana": 2, "baixa": 1}


@dataclass(frozen=True)
class Recommendation:
    """One justified EcoRadar management recommendation."""

    id: str
    title: str
    type: str
    group: str
    ecological_justification: str
    supporting_indicators: tuple[str, ...]
    sources_used: tuple[str, ...]
    location: str
    affected_surface: str
    expected_ecological_benefit: str
    urgency: str
    difficulty: str
    confidence: str
    dependencies: tuple[str, ...]
    diagnosis_conclusions: tuple[str, ...]
    ecological_priority_score: float


def run_recommendation_engine(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Run the recommendation engine after diagnosis exists."""

    root = Path(project_root)
    _ensure_inputs(root)
    ensure_mandatory_copernicus(root)
    out_dir = root / "recommendations"
    out_dir.mkdir(parents=True, exist_ok=True)

    context = _load_context(root)
    recommendations = sorted(
        _build_recommendations(context),
        key=lambda item: (-item.ecological_priority_score, GROUP_ORDER.get(item.group, 99), item.id),
    )

    recommendations_json = root / RECOMMENDATIONS_JSON
    recommendations_md = root / RECOMMENDATIONS_MD
    priority_json = root / PRIORITY_JSON
    priority_csv = root / PRIORITY_CSV

    payload = {
        "project": root.name,
        "generated_at": _now(),
        "scope": "recomanacions derivades exclusivament de la diagnosi ecològica; sense fitxa ni PDF",
        "recommendations": [asdict(item) for item in recommendations],
        "groups": _grouped_ids(recommendations),
    }
    recommendations_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    recommendations_md.write_text(_markdown(payload), encoding="utf-8")
    matrix = _priority_matrix(root, recommendations)
    priority_json.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_priority_csv(priority_csv, recommendations)

    return {
        "recommendations_json": str(recommendations_json),
        "recommendations_markdown": str(recommendations_md),
        "priority_matrix_json": str(priority_json),
        "priority_matrix_csv": str(priority_csv),
        "recommendation_count": len(recommendations),
        "groups": _grouped_ids(recommendations),
    }


def generate_recommendation_outputs(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Compatibility alias for the official recommendation engine."""

    result = run_recommendation_engine(project_root)
    return {
        "json": result["recommendations_json"],
        "csv": result["priority_matrix_csv"],
        "markdown": result["recommendations_markdown"],
        "recommendation_count": result["recommendation_count"],
    }


def _ensure_inputs(root: Path) -> None:
    missing = [relative for relative in REQUIRED_INPUTS if not (root / relative).exists()]
    if missing:
        raise RuntimeError(
            "EcoRadar recommendations cannot run before diagnosis and indicators exist. "
            f"Missing: {', '.join(missing)}"
        )


def _load_context(root: Path) -> dict[str, Any]:
    diagnosis = _read_json(root / "diagnosis" / "ecoradar_diagnosis.json")
    indicators_payload = _read_json(root / "indicators" / "ecoradar_core_indicators.json")
    return {
        "root": root,
        "diagnosis": diagnosis,
        "conclusions": diagnosis.get("conclusions", []),
        "conclusion_by_section": _conclusions_by_section(diagnosis.get("conclusions", [])),
        "indicators": indicators_payload.get("indicators", []),
        "indicator_by_code": {item["code"]: item for item in indicators_payload.get("indicators", [])},
        "study_area": _read_json(root / "metadata" / "study_area_metadata.json"),
        "habitats": _read_csv(root / "indicators" / "habitats_resum.csv"),
        "hydrology": _read_csv(root / "indicators" / "hidrologia_resum.csv"),
        "pressure": _read_csv(root / "indicators" / "recreational_pressure_resum.csv"),
        "connectivity": _read_csv(root / "indicators" / "connectivitat_resum.csv"),
    }


def _build_recommendations(context: dict[str, Any]) -> list[Recommendation]:
    return [
        _conserve_habitats(context),
        _maintain_connectivity(context),
        _validate_public_use(context),
        _field_validation(context),
        _complete_remote_sensing_climate(context),
        _validate_hydrology(context),
        _validate_fire_fuel(context),
        _validate_restoration_candidates(context),
        _verify_agricultural_open_areas(context),
    ]


def _conserve_habitats(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "valors_ecologics_principals")
    hic_ha = _habitat_area(context, "es_hic")
    priority_ha = _habitat_area(context, "es_prioritari")
    return _recommendation(
        "CONS-001",
        "Conservar preventivament HIC i hàbitats prioritaris abans de qualsevol actuació",
        "conservar",
        "Conservació",
        (
            "La diagnosi identifica els hàbitats com un dels valors ecològics principals: CORE_02 és molt alt "
            "i combina riquesa d'hàbitats, HIC i HIC prioritaris."
        ),
        ("CORE_02", "CORE_06", "CORE_08"),
        conclusion.get("sources_used", []),
        "Polígons cartografiats com HIC o HIC prioritari dins l'àrea d'Alinyà.",
        f"{_fmt(hic_ha)} ha HIC; {_fmt(priority_ha)} ha HIC prioritaris",
        "Evitar impactes sobre hàbitats de responsabilitat de conservació i mantenir els valors que sustenten la diagnosi.",
        "alta",
        "mitjana",
        conclusion.get("confidence", "alta"),
        ("Validació de camp d'hàbitats abans d'actuacions locals.",),
        (conclusion.get("title", ""),),
    )


def _maintain_connectivity(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "funcionament_ecologic")
    main_connectors = _sum(
        (row for row in context["connectivity"] if "principals" in str(row.get("layer_id"))),
        "area_ha",
    )
    return _recommendation(
        "CONS-002",
        "Mantenir la matriu natural connectada i evitar noves barreres",
        "millorar connectivitat",
        "Conservació",
        "La diagnosi relaciona mosaic alt, connectivitat alta i hàbitats de valor; cap capa aïllada explica el funcionament del territori.",
        ("CORE_01", "CORE_02", "CORE_08", "CORE_10"),
        conclusion.get("sources_used", []),
        "Connectors oficials i zones de matriu natural identificades per Infraestructura Verda i cobertes del sòl.",
        f"{_fmt(main_connectors)} ha en connectors terrestres principals retallats",
        "Mantenir permeabilitat ecològica i reduir fragmentació futura.",
        "alta",
        "mitjana",
        conclusion.get("confidence", "mitjana"),
        ("Model de barreres fines i validació de passos/corredors locals.",),
        (conclusion.get("title", ""),),
    )


def _validate_public_use(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "pressions")
    values = _metric_dict(context["pressure"])
    km = values.get("osm_path_track_road_km", 0.0)
    points = values.get("osm_recreational_point_features", 0.0)
    return _recommendation(
        "GEST-001",
        "Validar i ordenar l'ús públic on es pot solapar amb hàbitats d'alt valor",
        "ordenar ús públic",
        "Gestió",
        "La diagnosi detecta valor ecològic molt alt i pressió humana potencial mitjana; això no prova conflicte, però obliga a validar accessos i freqüentació.",
        ("CORE_02", "CORE_06", "CORE_07"),
        conclusion.get("sources_used", []),
        "Camins, pistes i punts d'ús públic cartografiats per OSM, especialment propers a HIC i zones connectores.",
        f"{_fmt(km)} km de camins/pistes OSM; {int(points)} punts d'ús públic",
        "Reduir possibles conflictes entre conservació i ús públic abans que esdevinguin pressions reals.",
        "mitjana",
        "mitjana",
        conclusion.get("confidence", "mitjana"),
        ("Comptadors, observació de camp o dades de gestors; Strava només si és legalment compatible.",),
        (conclusion.get("title", ""),),
    )


def _field_validation(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "validacio_camp")
    area = _study_area_ha(context)
    return _recommendation(
        "CAMP-001",
        "Executar una campanya de validació de camp sobre hàbitats, aigua, ús públic i biodiversitat sensible",
        "validar al camp",
        "Treball de camp",
        "La diagnosi marca com a robusta la necessitat de camp perquè falten field_biodiversity i field_validation en diversos indicadors.",
        ("CORE_02", "CORE_06", "CORE_07", "CORE_10"),
        conclusion.get("sources_used", []),
        "HIC i HIC prioritaris, punts d'aigua, accessos principals i grups taxonòmics poc representats.",
        f"{_fmt(area)} ha d'àmbit de mostreig; punts finals a definir en pla de camp",
        "Convertir incerteses en criteris verificats i evitar actuacions incompatibles amb hàbitats o espècies sensibles.",
        "molt alta",
        "mitjana",
        conclusion.get("confidence", "alta"),
        ("Disseny de protocols de camp i importador de dades pròpies EcoRadar.",),
        (conclusion.get("title", ""),),
    )


def _complete_remote_sensing_climate(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "dades_critiques_absents")
    area = _study_area_ha(context)
    return _recommendation(
        "DADES-001",
        "Desbloquejar Copernicus i clima abans de tancar vegetació, refugis climàtics i vulnerabilitat",
        "investigar",
        "Dades pendents",
        "La diagnosi identifica teledetecció i clima com les dades que més condicionen vegetació, clima, foc, restauració i prioritat de gestió.",
        ("CORE_03", "CORE_04", "CORE_05", "CORE_09", "CORE_11", "CORE_12"),
        conclusion.get("sources_used", []),
        "Tot l'àmbit d'Alinyà; lectura raster i climàtica homogènia.",
        f"{_fmt(area)} ha",
        "Augmentar de forma directa la confiança dels indicadors climàtics, de vegetació, foc i restauració.",
        "molt alta",
        "baixa",
        conclusion.get("confidence", "alta"),
        ("Credencials Copernicus, Meteocat/AEMET i definició de producte LST.",),
        (conclusion.get("title", ""),),
    )


def _validate_hydrology(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "debilitats")
    rows = context["hydrology"]
    km = _sum(rows, "length_km")
    springs = sum(int(_float(row.get("feature_count"))) for row in rows if str(row.get("theme")) == "springs")
    return _recommendation(
        "HIDRO-001",
        "Validar funcionalitat hídrica, fonts i punts d'aigua abans de definir refugis o restauració",
        "hidrologia",
        "Seguiment",
        "La diagnosi indica que l'aigua està cartografiada parcialment però no funcionalment caracteritzada.",
        ("CORE_10", "CORE_04"),
        conclusion.get("sources_used", []),
        "Cursos/drenatge ACA i fonts oficials dins l'àrea d'estudi.",
        f"{_fmt(km)} km de xarxa hidrogràfica/drenatge; {springs} fonts oficials",
        "Millorar la lectura de refugis climàtics, fauna associada a aigua i oportunitats de restauració.",
        "alta",
        "mitjana",
        conclusion.get("confidence", "mitjana"),
        ("NDWI, verificació de camp de fonts/basses i estat ecològic dels punts d'aigua.",),
        (conclusion.get("title", ""),),
    )


def _validate_fire_fuel(context: dict[str, Any]) -> Recommendation:
    conclusion = _find_by_title(context, "La resiliència davant del foc queda condicionada")
    area = _study_area_ha(context)
    return _recommendation(
        "FOC-001",
        "Validar combustible, humitat vegetal i discontinuïtats abans de proposar gestió forestal",
        "validar al camp",
        "Treball de camp",
        "La diagnosi no tanca resiliència al foc perquè falten NDMI, LST i estructura oficial de combustible.",
        ("CORE_09", "CORE_01", "CORE_10"),
        conclusion.get("sources_used", []),
        "Masses forestals, matollars, prats i discontinuïtats detectades per cobertes del sòl i DEM.",
        f"{_fmt(area)} ha d'àmbit potencial; actuacions forestals no delimitades encara",
        "Evitar actuacions forestals prematures i separar zones on el mosaic ajuda de zones on pot faltar discontinuïtat.",
        "alta",
        "mitjana",
        conclusion.get("confidence", "mitjana"),
        ("NDMI, LST, font oficial de combustible/estructura forestal i validació de camp.",),
        (conclusion.get("title", ""),),
    )


def _validate_restoration_candidates(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "oportunitats")
    area = _study_area_ha(context)
    return _recommendation(
        "REST-001",
        "Validar zones candidates de restauració abans de convertir el potencial en actuacions",
        "validar al camp",
        "Restauració",
        "La diagnosi detecta potencial de restauració alt, però encara no priorització espacial ni hàbitats degradats validats.",
        ("CORE_11", "CORE_12"),
        conclusion.get("sources_used", []),
        "Àmbit complet; priorització pendent de Sentinel, camp, combustible i SIGPAC/DUN.",
        f"{_fmt(area)} ha d'anàlisi; superfície d'actuació no delimitada",
        "Evitar restauracions mal localitzades i preparar una cartera de zones candidates amb criteri ecològic.",
        "mitjana",
        "mitjana",
        conclusion.get("confidence", "mitjana"),
        ("Sentinel, hàbitats degradats, hàbitats font, SIGPAC/DUN i treball de camp.",),
        (conclusion.get("title", ""),),
    )


def _verify_agricultural_open_areas(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "fortaleses")
    area = _study_area_ha(context)
    return _recommendation(
        "AGR-001",
        "Verificar prats, conreus residuals i espais oberts amb SIGPAC/DUN abans de gestió agrària",
        "gestió agrària",
        "Dades pendents",
        "La diagnosi apunta que els espais oberts poden tenir funció ecològica desproporcionada, però SIGPAC/DUN no està disponible.",
        ("CORE_01", "CORE_09"),
        conclusion.get("sources_used", []),
        "Prats, herbassars, conreus residuals i ecotons detectats per cobertes/hàbitats.",
        f"{_fmt(area)} ha d'àmbit; superfície agrària fina pendent de SIGPAC/DUN",
        "Distingir espais oberts ecològicament estratègics de zones sense funció prioritària abans de gestionar o restaurar.",
        "mitjana",
        "baixa",
        conclusion.get("confidence", "mitjana"),
        ("Accés oficial SIGPAC/DUN i validació de camp dels espais oberts.",),
        (conclusion.get("title", ""),),
    )


def _recommendation(
    rec_id: str,
    title: str,
    rec_type: str,
    group: str,
    justification: str,
    indicators: tuple[str, ...],
    sources: Any,
    location: str,
    surface: str,
    benefit: str,
    urgency: str,
    difficulty: str,
    confidence: str,
    dependencies: tuple[str, ...],
    conclusions: tuple[str, ...],
) -> Recommendation:
    score = _priority_score(urgency, difficulty, confidence)
    return Recommendation(
        id=rec_id,
        title=title,
        type=rec_type,
        group=group,
        ecological_justification=justification,
        supporting_indicators=indicators,
        sources_used=tuple(sorted(str(source) for source in sources)),
        location=location,
        affected_surface=surface,
        expected_ecological_benefit=benefit,
        urgency=urgency,
        difficulty=difficulty,
        confidence=confidence,
        dependencies=dependencies,
        diagnosis_conclusions=conclusions,
        ecological_priority_score=score,
    )


def _priority_score(urgency: str, difficulty: str, confidence: str) -> float:
    raw = (URGENCY_SCORE[urgency] * 0.45) + (DIFFICULTY_SCORE[difficulty] * 0.20) + (CONFIDENCE_SCORE[confidence] * 0.35)
    return round(raw / 3.55 * 100, 2)


def _priority_matrix(root: Path, recommendations: list[Recommendation]) -> dict[str, Any]:
    return {
        "project": root.name,
        "generated_at": _now(),
        "scoring": {
            "urgency_weight": 0.45,
            "difficulty_weight": 0.20,
            "confidence_weight": 0.35,
            "note": "La matriu ordena recomanacions derivades de diagnosi; no crea noves dades.",
        },
        "rows": [asdict(item) for item in recommendations],
    }


def _write_priority_csv(path: Path, recommendations: list[Recommendation]) -> None:
    fieldnames = list(asdict(recommendations[0]).keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in recommendations:
            row = asdict(item)
            for field in ("supporting_indicators", "sources_used", "dependencies", "diagnosis_conclusions"):
                row[field] = "; ".join(row[field])
            writer.writerow(row)


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# EcoRadar Recommendations",
        "",
        f"Projecte: `{payload['project']}`",
        f"Generat: `{payload['generated_at']}`",
        "",
        "Aquest fitxer conté recomanacions derivades exclusivament de la diagnosi ecològica. No és una fitxa ni un informe final.",
        "",
    ]
    for group in GROUP_ORDER:
        items = [item for item in payload["recommendations"] if item["group"] == group]
        if not items:
            continue
        lines.extend([f"## {GROUP_ORDER[group]} {group}", ""])
        for item in items:
            lines.extend(
                [
                    f"### {item['id']} · {item['title']}",
                    "",
                    f"- Tipus: `{item['type']}`",
                    f"- Prioritat ecològica: `{item['ecological_priority_score']}`",
                    f"- Urgència: `{item['urgency']}`",
                    f"- Dificultat: `{item['difficulty']}`",
                    f"- Confiança: `{item['confidence']}`",
                    f"- Justificació: {item['ecological_justification']}",
                    f"- Indicadors: {', '.join(item['supporting_indicators'])}",
                    f"- Fonts: {', '.join(item['sources_used']) or '-'}",
                    f"- Localització: {item['location']}",
                    f"- Superfície afectada: {item['affected_surface']}",
                    f"- Benefici esperat: {item['expected_ecological_benefit']}",
                    f"- Dependències: {'; '.join(item['dependencies']) or '-'}",
                    "",
                ]
            )
    return "\n".join(lines)


def _grouped_ids(recommendations: list[Recommendation]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {group: [] for group in GROUP_ORDER}
    for item in recommendations:
        grouped.setdefault(item.group, []).append(item.id)
    return {group: ids for group, ids in grouped.items() if ids}


def _find(context: dict[str, Any], section: str) -> dict[str, Any]:
    items = context["conclusion_by_section"].get(section, [])
    return items[0] if items else {}


def _find_by_title(context: dict[str, Any], title_start: str) -> dict[str, Any]:
    for item in context["conclusions"]:
        if str(item.get("title", "")).startswith(title_start):
            return item
    return {}


def _conclusions_by_section(conclusions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in conclusions:
        grouped.setdefault(str(item.get("section", "")), []).append(item)
    return grouped


def _study_area_ha(context: dict[str, Any]) -> float:
    metadata = context.get("study_area", {})
    return _float(metadata.get("surface_ha") or metadata.get("area_ha") or metadata.get("study_area_surface_ha"))


def _habitat_area(context: dict[str, Any], field: str) -> float:
    return _sum((row for row in context["habitats"] if _bool(row.get(field))), "superficie_ha")


def _metric_dict(rows: list[dict[str, str]]) -> dict[str, float]:
    return {str(row.get("indicator")): _float(row.get("value")) for row in rows}


def _sum(rows: Any, field: str) -> float:
    return sum(_float(row.get(field)) for row in rows)


def _float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "si", "sí"}


def _fmt(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    print(json.dumps(run_recommendation_engine(), indent=2, ensure_ascii=False))
