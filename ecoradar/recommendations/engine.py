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

PRIORITY_ORDER = {"P1": 1, "P2": 2, "P3": 3, "NO AVALUABLE": 4, "SENSE PRIORITAT ÚNICA": 5}
PRIORITY_BY_ID = {
    "CONS-001": "P1",
    "CONS-002": "P2",
    "GEST-001": "P2",
    "CAMP-001": "P2",
    "DADES-001": "P2",
    "HIDRO-001": "P2",
    "FOC-001": "P2",
    "REST-001": "NO AVALUABLE",
    "AGR-001": "P2",
}


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
    priority_class: str
    decision_status: str


def run_recommendation_engine(
    project_root: str | Path = "projectes/Alinya",
    *,
    allow_partial_copernicus: bool = False,
) -> dict[str, Any]:
    """Run the recommendation engine after diagnosis exists."""

    root = Path(project_root)
    _ensure_inputs(root)
    if not allow_partial_copernicus:
        ensure_mandatory_copernicus(root)
    out_dir = root / "recommendations"
    out_dir.mkdir(parents=True, exist_ok=True)

    context = _load_context(root)
    recommendations = sorted(
        _build_recommendations(context),
        key=lambda item: (PRIORITY_ORDER.get(item.priority_class, 99), GROUP_ORDER.get(item.group, 99), item.id),
    )

    recommendations_json = root / RECOMMENDATIONS_JSON
    recommendations_md = root / RECOMMENDATIONS_MD
    priority_json = root / PRIORITY_JSON
    priority_csv = root / PRIORITY_CSV

    payload = {
        "project": root.name,
        "generated_at": _now(),
        "methodology_version": context["diagnosis"].get("methodology_version"),
        "snapshot_id": context["diagnosis"].get("snapshot_id"),
        "scope": "recomanacions derivades exclusivament de la diagnosi ecològica; sense fitxa ni PDF",
        "recommendations": [asdict(item) for item in recommendations],
        "groups": _grouped_ids(recommendations),
    }
    recommendations_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    recommendations_md.write_text(_markdown(payload), encoding="utf-8")
    matrix = _priority_matrix(root, recommendations)
    matrix["methodology_version"] = payload["methodology_version"]
    matrix["snapshot_id"] = payload["snapshot_id"]
    priority_json.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_priority_csv(priority_csv, recommendations)
    _write_alinya_phase2_compatibility_outputs(root, payload, priority_csv)

    return {
        "recommendations_json": str(recommendations_json),
        "recommendations_markdown": str(recommendations_md),
        "priority_matrix_json": str(priority_json),
        "priority_matrix_csv": str(priority_csv),
        "recommendation_count": len(recommendations),
        "groups": _grouped_ids(recommendations),
    }


def _write_alinya_phase2_compatibility_outputs(
    root: Path,
    payload: dict[str, Any],
    priority_csv: Path,
) -> None:
    """Keep former active aliases synchronized without reviving old results."""

    if payload.get("methodology_version") != "alinya_core_v2_2026-09-09":
        return
    metadata_alias = root / "metadata" / "ecoradar_recommendations.json"
    csv_alias = root / "indicators" / "ecoradar_recommendations.csv"
    metadata_alias.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    csv_alias.write_bytes(priority_csv.read_bytes())


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
            "CORE_02 documenta responsabilitat territorial per HIC i HIC prioritaris, sense atribuir-los estat de conservació. "
            "La possible irreversibilitat justifica una regla preventiva de no-deteriorament."
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
    conclusion = _find(context, "connectivitat_i_us")
    main_connectors = _sum(
        (row for row in context["connectivity"] if "principals" in str(row.get("layer_id"))),
        "area_ha",
    )
    return _recommendation(
        "CONS-002",
        "Mantenir la matriu natural connectada i evitar noves barreres",
        "millorar connectivitat",
        "Conservació",
        "La diagnosi descriu configuració del mosaic, HIC i continuïtat estructural per separat; cap capa aïllada prova funcionalitat ecològica.",
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
    conclusion = _find(context, "connectivitat_i_us")
    values = _metric_dict(context["pressure"])
    km = values.get("osm_path_track_road_km", 0.0)
    points = values.get("osm_recreational_point_features", 0.0)
    return _recommendation(
        "GEST-001",
        "Validar i ordenar l'ús públic on es pot solapar amb hàbitats d'alt valor",
        "ordenar ús públic",
        "Gestió",
        "CORE_07 documenta accessibilitat cartografiada, no pressió. La coincidència espacial amb HIC o connectors indica on mesurar ús i impacte abans de regular.",
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
    conclusion = _find(context, "situacio_actual")
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
    conclusion = _find(context, "vulnerabilitats")
    area = _study_area_ha(context)
    return _recommendation(
        "DADES-001",
        "Desbloquejar Copernicus i clima abans de tancar vegetació, refugis climàtics i vulnerabilitat",
        "investigar",
        "Dades pendents",
        "L’escena Sentinel-2 disponible és del 07/07/2026 i la LST és un compost multitemporal. Cal una nova escena QA-vàlida i normals compatibles per actualitzar vegetació i clima.",
        ("CORE_03", "CORE_04", "CORE_05", "CORE_09", "CORE_11", "CORE_12"),
        conclusion.get("sources_used", []),
        "Tot l'àmbit d'Alinyà; lectura raster i climàtica homogènia.",
        f"{_fmt(area)} ha",
        "Augmentar de forma directa la confiança dels indicadors climàtics, de vegetació, foc i restauració.",
        "molt alta",
        "baixa",
        conclusion.get("confidence", "alta"),
        ("COPERNICUS_CLIENT_ID i COPERNICUS_CLIENT_SECRET per seleccionar una escena recent amb cobertura real i SCL; normals climàtiques verificades.",),
        (conclusion.get("title", ""),),
    )


def _validate_hydrology(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "aigua")
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
    conclusion = _find(context, "foc")
    area = _study_area_ha(context)
    return _recommendation(
        "FOC-001",
        "Validar combustible, humitat vegetal i discontinuïtats abans de proposar gestió forestal",
        "validar al camp",
        "Treball de camp",
        "CORE_09 separa propagació actual, sensibilitat, recuperació i operativa. NDMI i LST disponibles són massa antics o multitemporals per descriure l'estat actual i falta combustible de camp.",
        ("CORE_09", "CORE_01", "CORE_10"),
        conclusion.get("sources_used", []),
        "Masses forestals, matollars, prats i discontinuïtats detectades per cobertes del sòl i DEM.",
        f"{_fmt(area)} ha d'àmbit potencial; actuacions forestals no delimitades encara",
        "Evitar actuacions forestals prematures i separar zones on el mosaic ajuda de zones on pot faltar discontinuïtat.",
        "alta",
        "mitjana",
        conclusion.get("confidence", "mitjana"),
        ("Nova escena NDMI QA-vàlida, combustible/estructura forestal i validació de camp.",),
        (conclusion.get("title", ""),),
    )


def _validate_restoration_candidates(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "implicacions_gestio")
    area = _study_area_ha(context)
    return _recommendation(
        "REST-001",
        "Validar zones candidates de restauració abans de convertir el potencial en actuacions",
        "validar al camp",
        "Restauració",
        "CORE_11 retorna NO AVALUABLE: no hi ha degradació demostrada, referència, objectiu, benefici comparat amb no-intervenció ni viabilitat.",
        ("CORE_11", "CORE_12"),
        conclusion.get("sources_used", []),
        "Cap sector de restauració és justificable fins completar la porta de decisió.",
        f"{_fmt(area)} ha d'anàlisi; superfície d'actuació no delimitada",
        "Evitar restauracions mal localitzades i preparar una cartera de zones candidates amb criteri ecològic.",
        "mitjana",
        "mitjana",
        conclusion.get("confidence", "mitjana"),
        ("Degradació demostrada, ecosistema de referència, objectiu, benefici, viabilitat, risc i treball de camp.",),
        (conclusion.get("title", ""),),
    )


def _verify_agricultural_open_areas(context: dict[str, Any]) -> Recommendation:
    conclusion = _find(context, "distribucio_territorial")
    area = _study_area_ha(context)
    return _recommendation(
        "AGR-001",
        "Verificar prats, conreus residuals i espais oberts amb SIGPAC/DUN abans de gestió agrària",
        "gestió agrària",
        "Dades pendents",
        "CORE_01 descriu un 9,34 % d'espais oberts i agraris, però no els assigna qualitat ni signe ecològic sense objectiu i contrast.",
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
    priority_class = PRIORITY_BY_ID.get(rec_id, "SENSE PRIORITAT ÚNICA")
    decision_status = "veto per manca d'evidència essencial" if priority_class == "NO AVALUABLE" else "alternativa candidata documentada"
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
        priority_class=priority_class,
        decision_status=decision_status,
    )


def _priority_matrix(root: Path, recommendations: list[Recommendation]) -> dict[str, Any]:
    return {
        "project": root.name,
        "generated_at": _now(),
        "decision_method": {
            "type": "non_compensatory_categories",
            "allowed_results": ["P1", "P2", "P3", "NO AVALUABLE", "SENSE PRIORITAT ÚNICA"],
            "note": "La categoria s'aplica a una alternativa documentada; urgència, dificultat i confiança es mostren sense convertir-les en una mitjana.",
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
                    f"- Categoria de decisió: `{item['priority_class']}`",
                    f"- Estat de decisió: `{item['decision_status']}`",
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
