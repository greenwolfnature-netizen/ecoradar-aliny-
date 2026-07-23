"""EcoRadar validation engine.

This module validates existing EcoRadar data, indicators, diagnosis and
recommendations before final presentation products are generated. It does not
create connectors, indicators, recommendations, fitxes or final reports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
from typing import Any, Iterable

from ecoradar.sources.mandatory_copernicus import ensure_mandatory_copernicus


TECHNICAL_JSON = "validation/technical_validation.json"
ECOLOGICAL_JSON = "validation/ecological_validation.json"
FIELD_CSV = "validation/field_validation_checklist.csv"
RECOMMENDATIONS_JSON = "validation/recommendations_validation.json"
REPORT_MD = "reports/validation_report.md"

REQUIRED_INPUTS = (
    "processed/study_area.gpkg",
    "metadata/study_area_metadata.json",
    "metadata/data_availability_report.json",
    "metadata/connectors_status_report.json",
    "metadata/indicators_completeness_report.json",
    "indicators/ecoradar_core_indicators.json",
    "diagnosis/ecoradar_diagnosis.json",
    "recommendations/recommendations.json",
)

FINAL_ACTION_TYPES = {
    "conservar",
    "restaurar",
    "ordenar ús públic",
    "millorar connectivitat",
    "gestió forestal",
    "gestió agrària",
    "hidrologia",
    "seguiment",
}


@dataclass(frozen=True)
class ValidationCheck:
    """One validation check result."""

    code: str
    level: str
    title: str
    status: str
    severity: str
    message: str
    evidence: dict[str, Any]


def run_validation_engine(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Run all EcoRadar validation levels for a project."""

    root = Path(project_root)
    _ensure_inputs(root)
    ensure_mandatory_copernicus(root)
    (root / "validation").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)

    context = _load_context(root)
    technical = _technical_validation(context)
    ecological = _ecological_validation(context)
    recommendations = _recommendations_validation(context)
    checklist = _field_checklist(context, technical, ecological, recommendations)

    technical_path = root / TECHNICAL_JSON
    ecological_path = root / ECOLOGICAL_JSON
    field_path = root / FIELD_CSV
    recommendations_path = root / RECOMMENDATIONS_JSON
    report_path = root / REPORT_MD

    technical_payload = _payload(root, "technical", technical)
    ecological_payload = _payload(root, "ecological", ecological)
    recommendations_payload = _payload(root, "recommendations", recommendations)

    technical_path.write_text(json.dumps(technical_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ecological_path.write_text(json.dumps(ecological_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    recommendations_path.write_text(
        json.dumps(recommendations_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_field_csv(field_path, checklist)

    report_payload = {
        "project": root.name,
        "generated_at": _now(),
        "summary": _summary(technical + ecological + recommendations),
        "technical": technical_payload,
        "ecological": ecological_payload,
        "recommendations": recommendations_payload,
        "field_checklist_count": len(checklist),
        "final_outputs_gate": _final_outputs_gate(technical, ecological, recommendations),
    }
    report_path.write_text(_markdown(report_payload, checklist), encoding="utf-8")

    return {
        "technical_validation": str(technical_path),
        "ecological_validation": str(ecological_path),
        "field_validation_checklist": str(field_path),
        "recommendations_validation": str(recommendations_path),
        "validation_report": str(report_path),
        "summary": report_payload["summary"],
        "final_outputs_gate": report_payload["final_outputs_gate"],
    }


def ensure_validation_passed(project_root: str | Path = "projectes/Alinya") -> None:
    """Require validation outputs and block final products on critical errors."""

    root = Path(project_root)
    ensure_mandatory_copernicus(root)
    required = (TECHNICAL_JSON, ECOLOGICAL_JSON, RECOMMENDATIONS_JSON)
    missing = [item for item in required if not (root / item).exists()]
    if missing:
        raise RuntimeError(
            "EcoRadar final outputs require validation before fitxa/report generation. "
            f"Missing: {', '.join(missing)}"
        )
    checks: list[dict[str, Any]] = []
    for relative in required:
        checks.extend(_read_json(root / relative).get("checks", []))
    critical = [item for item in checks if item.get("status") == "FAIL" and item.get("severity") == "critical"]
    if critical:
        titles = "; ".join(item.get("title", item.get("code", "")) for item in critical[:5])
        raise RuntimeError(f"EcoRadar final outputs blocked by critical validation errors: {titles}")


def _ensure_inputs(root: Path) -> None:
    missing = [relative for relative in REQUIRED_INPUTS if not (root / relative).exists()]
    if missing:
        raise RuntimeError(f"EcoRadar validation cannot run before required inputs exist: {', '.join(missing)}")


def _load_context(root: Path) -> dict[str, Any]:
    indicators_payload = _read_json(root / "indicators" / "ecoradar_core_indicators.json")
    indicators = indicators_payload.get("indicators", [])
    diagnosis = _read_json(root / "diagnosis" / "ecoradar_diagnosis.json")
    recommendations_payload = _read_json(root / "recommendations" / "recommendations.json")
    availability = _read_json(root / "metadata" / "data_availability_report.json")
    return {
        "root": root,
        "study_area_metadata": _read_json(root / "metadata" / "study_area_metadata.json"),
        "availability": availability,
        "source_ids": {
            row.get("source_id") or row.get("id")
            for row in availability.get("sources", [])
            if row.get("source_id") or row.get("id")
        },
        "connectors": _read_json(root / "metadata" / "connectors_status_report.json"),
        "completeness": _read_json(root / "metadata" / "indicators_completeness_report.json"),
        "indicators_payload": indicators_payload,
        "indicators": indicators,
        "indicator_by_code": {item.get("code"): item for item in indicators},
        "diagnosis": diagnosis,
        "conclusions": diagnosis.get("conclusions", []),
        "recommendations_payload": recommendations_payload,
        "recommendations": recommendations_payload.get("recommendations", []),
    }


def _technical_validation(context: dict[str, Any]) -> list[ValidationCheck]:
    root = context["root"]
    checks: list[ValidationCheck] = []
    study_meta = context["study_area_metadata"]
    source_ids = context["source_ids"]
    indicators = context["indicators"]

    study_area_path = root / "processed" / "study_area.gpkg"
    study_info = _inspect_vector(study_area_path)
    checks.append(
        _check(
            "TECH_01",
            "technical",
            "CRS de l'àrea d'estudi",
            study_info.get("crs") == "EPSG:25831" and study_meta.get("final_crs") == "EPSG:25831",
            "critical",
            f"CRS detectat: capa={study_info.get('crs')}, metadades={study_meta.get('final_crs')}.",
            {"study_area": study_info, "metadata_final_crs": study_meta.get("final_crs")},
        )
    )
    checks.append(
        _check(
            "TECH_02",
            "technical",
            "Geometria de l'àrea d'estudi",
            bool(study_info.get("valid")) and study_info.get("feature_count", 0) > 0,
            "critical",
            f"Geometries invàlides: {study_info.get('invalid_count', 'n/a')}.",
            study_info,
        )
    )

    meta_area = _float(study_meta.get("surface_ha"))
    geom_area = _float(study_info.get("area_ha"))
    area_delta_pct = abs((geom_area or 0) - (meta_area or 0)) / (meta_area or 1) * 100 if meta_area else None
    checks.append(
        _check(
            "TECH_03",
            "technical",
            "Superfície coherent amb metadades",
            area_delta_pct is not None and area_delta_pct <= 0.5,
            "critical",
            f"Diferència àrea geometria/metadades: {_fmt(area_delta_pct)}%.",
            {"metadata_area_ha": meta_area, "geometry_area_ha": geom_area, "delta_pct": area_delta_pct},
        )
    )

    layer_results = []
    for relative in (
        "processed/cobertes_sol.gpkg",
        "processed/habitats.gpkg",
        "processed/biodiversitat.gpkg",
        "processed/recreational_pressure.gpkg",
        "processed/hidrologia.gpkg",
        "processed/connectivitat.gpkg",
        "processed/incendis.gpkg",
    ):
        layer_results.append(_inspect_layer_clip(root / relative, study_area_path))
    outside_bad = [item for item in layer_results if item.get("status") == "outside_tolerance"]
    checks.append(
        _check(
            "TECH_04",
            "technical",
            "Capes processades retallades dins l'àrea d'estudi",
            not outside_bad,
            "major",
            f"Capes revisades: {len(layer_results)}; fora de tolerància: {len(outside_bad)}.",
            {"layers": layer_results},
        )
    )

    empty_critical = [
        item
        for item in indicators
        if item.get("status") == "COMPLET" and (item.get("value_0_100") is None or not item.get("sources_used"))
    ]
    checks.append(
        _check(
            "TECH_05",
            "technical",
            "Valors sense buits crítics",
            not empty_critical,
            "critical",
            f"Indicadors complets amb valor/font absent: {len(empty_critical)}.",
            {"affected_indicators": [item.get("code") for item in empty_critical]},
        )
    )

    sources = context["availability"].get("sources", [])
    required_fields = ("source_id", "source_name", "url", "access_type", "expected_format", "responsible_connector", "status")
    undocumented = [
        row.get("source_id") or row.get("source_name", "unknown")
        for row in sources
        if any(not row.get(field) for field in required_fields)
    ]
    checks.append(
        _check(
            "TECH_06",
            "technical",
            "Fonts documentades",
            not undocumented and bool(sources),
            "critical",
            f"Fonts al catàleg: {len(sources)}; fonts incompletes: {len(undocumented)}.",
            {"undocumented_sources": undocumented[:20]},
        )
    )

    unknown_sources = sorted(
        {
            source
            for item in indicators
            for source in item.get("sources_used", [])
            if source and source not in source_ids
        }
    )
    checks.append(
        _check(
            "TECH_07",
            "technical",
            "Indicadors vinculats a fonts reals",
            not unknown_sources,
            "critical",
            f"Fonts utilitzades no registrades: {len(unknown_sources)}.",
            {"unknown_sources": unknown_sources},
        )
    )

    invented_like = [
        item.get("code")
        for item in indicators
        if item.get("value_0_100") is not None and not item.get("sources_used") and item.get("status") != "NO DISPONIBLE"
    ]
    checks.append(
        _check(
            "TECH_08",
            "technical",
            "Cap valor inventat",
            not invented_like,
            "critical",
            f"Valors numèrics sense fonts: {len(invented_like)}.",
            {"affected_indicators": invented_like},
        )
    )
    return checks


def _ecological_validation(context: dict[str, Any]) -> list[ValidationCheck]:
    by_code = context["indicator_by_code"]
    conclusions = context["conclusions"]
    text = " ".join(
        " ".join(str(item.get(key, "")) for key in ("title", "interpretation", "management_implication"))
        for item in conclusions
    ).lower()
    limited = [
        item.get("code")
        for item in context["indicators"]
        if item.get("status") in {"PARCIAL", "NO DISPONIBLE"}
    ]
    checks = [
        _check(
            "ECO_01",
            "ecological",
            "Hàbitats alts impliquen prudència de gestió",
            _value(by_code, "CORE_02") >= 80 and ("prud" in text or "prevent" in text or "hic" in text),
            "major",
            "El valor d'hàbitats molt alt ha d'anar lligat a prudència, HIC o validació abans d'actuar.",
            {"CORE_02": by_code.get("CORE_02"), "matched_text": _contains_any(text, ("prud", "prevent", "hic"))},
        ),
        _check(
            "ECO_02",
            "ecological",
            "Prats, ecotons i discontinuïtats no queden invisibles",
            "espais oberts" in text or "prats" in text or "discontinu" in text or "ecotons" in text,
            "major",
            "La diagnosi ha de destacar espais oberts funcionals encara que no siguin dominants.",
            {"matched": _contains_any(text, ("espais oberts", "prats", "discontinu", "ecotons"))},
        ),
        _check(
            "ECO_03",
            "ecological",
            "Pressió humana no es confon amb freqüentació real",
            "no mesura intensitat real" in text or "freqüentació real" in text or "pressió potencial" in text,
            "critical",
            "OSM/camins només poden interpretar-se com accessibilitat o pressió potencial.",
            {"CORE_07": by_code.get("CORE_07")},
        ),
        _check(
            "ECO_04",
            "ecological",
            "Biodiversitat pública no es confon amb inventari complet",
            "no equivalen a inventari complet" in text or "oportunistes" in text,
            "critical",
            "GBIF/iNaturalist han de quedar descrits com a coneixement públic oportunista.",
            {"CORE_06": by_code.get("CORE_06")},
        ),
        _check(
            "ECO_05",
            "ecological",
            "Foc, clima, aigua i restauració no es tanquen si falten dades crítiques",
            all(
                by_code.get(code, {}).get("status") in {"PARCIAL", "NO DISPONIBLE"}
                for code in ("CORE_03", "CORE_04", "CORE_05", "CORE_09", "CORE_10", "CORE_11", "CORE_12")
            )
            and ("provisional" in text or "parcial" in text),
            "critical",
            "Els blocs condicionats per Copernicus, clima, combustible, aigua funcional o camp han de quedar provisionals.",
            {
                code: {
                    "status": by_code.get(code, {}).get("status"),
                    "confidence": by_code.get(code, {}).get("confidence"),
                }
                for code in ("CORE_03", "CORE_04", "CORE_05", "CORE_09", "CORE_10", "CORE_11", "CORE_12")
            },
        ),
        _warn(
            "ECO_06",
            "ecological",
            "Diagnosi validada amb limitacions de dades",
            "Hi ha indicadors parcials o no disponibles; la validació permet fitxa/informe només perquè aquestes limitacions estan explícites.",
            {"limited_indicators": limited},
        )
        if limited
        else _check(
            "ECO_06",
            "ecological",
            "Diagnosi sense limitacions de dades crítiques",
            True,
            "minor",
            "No hi ha indicadors parcials o no disponibles.",
            {},
        ),
    ]
    return checks


def _recommendations_validation(context: dict[str, Any]) -> list[ValidationCheck]:
    indicator_codes = {item.get("code") for item in context["indicators"]}
    indicators = context["indicator_by_code"]
    conclusion_titles = {item.get("title") for item in context["conclusions"]}
    recommendations = context["recommendations"]
    checks: list[ValidationCheck] = []

    malformed = []
    unsupported = []
    missing_sources = []
    missing_localization = []
    overinterpreted = []

    for rec in recommendations:
        rec_id = rec.get("id", "unknown")
        if not all(rec.get(field) for field in ("id", "title", "type", "ecological_justification", "confidence", "location")):
            malformed.append(rec_id)
        rec_indicators = set(rec.get("supporting_indicators", []))
        if not rec_indicators or not rec_indicators <= indicator_codes:
            unsupported.append(rec_id)
        rec_sources = rec.get("sources_used", [])
        if not rec_sources and rec.get("group") != "Dades pendents":
            missing_sources.append(rec_id)
        if not rec.get("location") or rec.get("location") in {"-", "no disponible"}:
            missing_localization.append(rec_id)
        depends_on_partial = any(
            indicators.get(code, {}).get("status") in {"PARCIAL", "NO DISPONIBLE"} for code in rec_indicators
        )
        if depends_on_partial and rec.get("type") in FINAL_ACTION_TYPES and not rec.get("dependencies"):
            overinterpreted.append(rec_id)
        if rec.get("diagnosis_conclusions"):
            missing_conclusions = [title for title in rec.get("diagnosis_conclusions", []) if title not in conclusion_titles]
            if missing_conclusions:
                unsupported.append(rec_id)

    checks.extend(
        [
            _check(
                "REC_01",
                "recommendations",
                "Recomanacions amb camps obligatoris",
                not malformed,
                "critical",
                f"Recomanacions amb camps obligatoris absents: {len(malformed)}.",
                {"recommendations": malformed},
            ),
            _check(
                "REC_02",
                "recommendations",
                "Recomanacions derivades d'indicadors reals",
                not unsupported,
                "critical",
                f"Recomanacions sense indicador/conclusió traçable: {len(unsupported)}.",
                {"recommendations": sorted(set(unsupported))},
            ),
            _check(
                "REC_03",
                "recommendations",
                "Fonts citades quan són actuacions substantives",
                not missing_sources,
                "major",
                f"Recomanacions sense fonts fora de Dades pendents: {len(missing_sources)}.",
                {"recommendations": missing_sources},
            ),
            _check(
                "REC_04",
                "recommendations",
                "Localització indicada",
                not missing_localization,
                "major",
                f"Recomanacions sense localització útil: {len(missing_localization)}.",
                {"recommendations": missing_localization},
            ),
            _check(
                "REC_05",
                "recommendations",
                "No hi ha actuacions finals sense advertir parcialitat",
                not overinterpreted,
                "critical",
                f"Recomanacions finals basades en indicadors parcials sense dependències: {len(overinterpreted)}.",
                {"recommendations": overinterpreted},
            ),
        ]
    )
    return checks


def _field_checklist(
    context: dict[str, Any],
    technical: list[ValidationCheck],
    ecological: list[ValidationCheck],
    recommendations: list[ValidationCheck],
) -> list[dict[str, str]]:
    by_code = context["indicator_by_code"]
    return [
        _field_row(
            "FIELD_01",
            "Hàbitats sensibles",
            "HIC, ecotons i unitats d'hàbitat amb valor alt",
            "Verificar estat real, pressions locals i límits de polígon.",
            "CORE_02",
            "alta",
            "Alta",
            "No hi ha validació de camp d'hàbitats.",
        ),
        _field_row(
            "FIELD_02",
            "HIC i HIC prioritaris",
            "Polígons HIC i HIC prioritaris abans d'actuacions",
            "Confirmar correspondència cartografia-realitat i sensibilitat.",
            "CORE_02; CORE_08",
            "alta",
            "Alta",
            "Recomanació CONS-001 depèn de precisió local.",
        ),
        _field_row(
            "FIELD_03",
            "Prats, ecotons i discontinuïtats",
            "Espais oberts, marges, prats i conreus residuals",
            "Determinar funció ecològica, gestió agrària i paper en mosaic/foc.",
            "CORE_01; CORE_09",
            "mitjana",
            "Alta",
            "SIGPAC/DUN i combustible no disponibles.",
        ),
        _field_row(
            "FIELD_04",
            "Fonts, basses i punts d'aigua",
            "Cursos ACA, fonts oficials i possibles basses no cartografiades",
            "Verificar presència d'aigua, temporalitat, estat ecològic i ús per fauna.",
            "CORE_10; CORE_04",
            by_code.get("CORE_10", {}).get("confidence", "mitjana"),
            "Alta",
            "NDWI i estat funcional de l'aigua no disponibles.",
        ),
        _field_row(
            "FIELD_05",
            "Camins i punts d'ús públic",
            "Accessos, pistes, aparcaments, miradors i punts recreatius",
            "Separar accessibilitat cartogràfica de freqüentació real.",
            "CORE_07",
            by_code.get("CORE_07", {}).get("confidence", "mitjana"),
            "Mitjana",
            "OSM no mesura intensitat real de visitants.",
        ),
        _field_row(
            "FIELD_06",
            "Microhàbitats",
            "Roca, fusta morta, arbres vells, cavitats, surgències i marges",
            "Inventariar elements no visibles a la cartografia oficial.",
            "CORE_02; CORE_06; CORE_11",
            "baixa",
            "Mitjana",
            "No existeix capa de microhàbitats.",
        ),
        _field_row(
            "FIELD_07",
            "Espècies indicadores",
            "Grups i taxons citats per GBIF/iNaturalist amb interès de gestió",
            "Confirmar presència actual, hàbitat i qualitat de la citació.",
            "CORE_06",
            by_code.get("CORE_06", {}).get("confidence", "mitjana"),
            "Alta",
            "Fonts públiques oportunistes no equivalen a inventari complet.",
        ),
        _field_row(
            "FIELD_08",
            "Pressions reals",
            "Ús públic, ramaderia, agricultura, infraestructures i erosió local",
            "Registrar intensitat, temporalitat, conflictes i punts crítics.",
            "CORE_07; CORE_12",
            "mitjana",
            "Mitjana",
            "Falten dades de gestors/comptadors i validació directa.",
        ),
        _field_row(
            "FIELD_09",
            "Zones amb baixa confiança",
            "Vegetació, clima, foc, aigua funcional i restauració",
            "Prioritzar mostreig on falten Copernicus, clima, combustible o validació.",
            "CORE_03; CORE_04; CORE_05; CORE_09; CORE_10; CORE_11",
            "baixa",
            "Alta",
            "Indicadors parcials o no disponibles condicionen decisions finals.",
        ),
    ]


def _inspect_vector(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "valid": False, "error": "missing"}
    try:
        import geopandas as gpd  # type: ignore

        gdf = gpd.read_file(path)
        invalid_count = int((~gdf.geometry.is_valid).sum()) if not gdf.empty else 0
        metric = gdf.to_crs("EPSG:25831") if str(gdf.crs) != "EPSG:25831" and gdf.crs is not None else gdf
        area_ha = float(metric.geometry.union_all().area / 10000) if not metric.empty else 0.0
        return {
            "path": str(path),
            "exists": True,
            "crs": str(gdf.crs),
            "feature_count": int(len(gdf)),
            "invalid_count": invalid_count,
            "valid": invalid_count == 0 and not gdf.empty,
            "area_ha": area_ha,
        }
    except Exception as exc:
        return {"path": str(path), "exists": True, "valid": False, "error": f"{type(exc).__name__}: {exc}"}


def _inspect_layer_clip(layer_path: Path, study_area_path: Path) -> dict[str, Any]:
    if not layer_path.exists():
        return {"path": str(layer_path), "exists": False, "status": "missing"}
    try:
        import geopandas as gpd  # type: ignore

        study = gpd.read_file(study_area_path).to_crs("EPSG:25831")
        layer = gpd.read_file(layer_path).to_crs("EPSG:25831")
        if layer.empty:
            return {"path": str(layer_path), "exists": True, "status": "empty"}
        boundary = study.geometry.union_all()
        geom = layer.geometry.union_all()
        outside = geom.difference(boundary.buffer(2))
        outside_area = float(outside.area) if hasattr(outside, "area") else 0.0
        total_area = float(geom.area) if hasattr(geom, "area") else 0.0
        outside_pct = outside_area / total_area * 100 if total_area else 0.0
        status = "inside" if outside_pct <= 0.5 else "outside_tolerance"
        return {
            "path": str(layer_path),
            "exists": True,
            "status": status,
            "feature_count": int(len(layer)),
            "crs": str(layer.crs),
            "outside_area_m2": outside_area,
            "outside_pct": outside_pct,
        }
    except Exception as exc:
        return {"path": str(layer_path), "exists": True, "status": "not_checked", "error": f"{type(exc).__name__}: {exc}"}


def _payload(root: Path, level: str, checks: list[ValidationCheck]) -> dict[str, Any]:
    return {
        "project": root.name,
        "generated_at": _now(),
        "level": level,
        "summary": _summary(checks),
        "checks": [asdict(check) for check in checks],
    }


def _summary(checks: list[ValidationCheck]) -> dict[str, Any]:
    critical_errors = [item for item in checks if item.status == "FAIL" and item.severity == "critical"]
    major_errors = [item for item in checks if item.status == "FAIL" and item.severity == "major"]
    warnings = [item for item in checks if item.status == "WARN"]
    return {
        "checks": len(checks),
        "passed": sum(1 for item in checks if item.status == "PASS"),
        "warnings": len(warnings),
        "major_errors": len(major_errors),
        "critical_errors": len(critical_errors),
        "status": "BLOCKED" if critical_errors else "VALIDATED_WITH_LIMITATIONS" if major_errors or warnings else "VALIDATED",
    }


def _final_outputs_gate(
    technical: list[ValidationCheck],
    ecological: list[ValidationCheck],
    recommendations: list[ValidationCheck],
) -> dict[str, Any]:
    all_checks = technical + ecological + recommendations
    critical = [item for item in all_checks if item.status == "FAIL" and item.severity == "critical"]
    major = [item for item in all_checks if item.status == "FAIL" and item.severity == "major"]
    return {
        "fitxa_and_final_report_allowed": not critical,
        "critical_errors": [item.code for item in critical],
        "major_errors": [item.code for item in major],
        "conditions": [
            "No hi ha errors tècnics crítics.",
            "Les limitacions estan indicades als indicadors i conclusions.",
            "Les recomanacions tenen indicador, font/localització o dependència quan la dada és parcial.",
            "Les dades pendents apareixen com a limitació o recomanació de validació.",
            "La diagnosi no tanca vegetació, clima, foc, aigua o restauració quan les dades són parcials.",
        ],
    }


def _markdown(payload: dict[str, Any], checklist: list[dict[str, str]]) -> str:
    gate = payload["final_outputs_gate"]
    lines = [
        "# Informe de validació EcoRadar",
        "",
        f"Projecte: `{payload['project']}`",
        f"Generat: `{payload['generated_at']}`",
        f"Estat per generar fitxa/informe final: `{'APTE' if gate['fitxa_and_final_report_allowed'] else 'BLOQUEJAT'}`",
        "",
        "## Resum",
        "",
        "| Nivell | Estat | Checks | Errors crítics | Errors majors | Avisos |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for key, label in (
        ("technical", "Validació tècnica"),
        ("ecological", "Validació ecològica"),
        ("recommendations", "Validació de recomanacions"),
    ):
        summary = payload[key]["summary"]
        lines.append(
            f"| {label} | {summary['status']} | {summary['checks']} | {summary['critical_errors']} | "
            f"{summary['major_errors']} | {summary['warnings']} |"
        )
    lines.extend(["", "## Condicions de publicació", ""])
    for condition in gate["conditions"]:
        lines.append(f"- {condition}")
    if gate["critical_errors"]:
        lines.append(f"- Bloqueig crític: {', '.join(gate['critical_errors'])}")
    if gate["major_errors"]:
        lines.append(f"- Errors majors a revisar: {', '.join(gate['major_errors'])}")
    lines.extend(["", "## Checks tècnics i ecològics", ""])
    for section in ("technical", "ecological", "recommendations"):
        lines.append(f"### {payload[section]['level']}")
        for check in payload[section]["checks"]:
            lines.append(f"- `{check['status']}` `{check['severity']}` {check['code']} - {check['title']}: {check['message']}")
        lines.append("")
    lines.extend(["## Checklist de camp", "", "| ID | Bloc | On mirar | Què comprovar | Prioritat | Motiu |", "|---|---|---|---|---|---|"])
    for row in checklist:
        lines.append(
            f"| {row['id']} | {row['bloc']} | {row['localitzacio_objectiu']} | "
            f"{row['comprovacio']} | {row['prioritat']} | {row['motiu']} |"
        )
    return "\n".join(lines) + "\n"


def _write_field_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = (
        "id",
        "bloc",
        "localitzacio_objectiu",
        "comprovacio",
        "indicadors_relacionats",
        "confiança_actual",
        "prioritat",
        "motiu",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _field_row(
    item_id: str,
    bloc: str,
    location: str,
    check: str,
    indicators: str,
    confidence: str,
    priority: str,
    reason: str,
) -> dict[str, str]:
    return {
        "id": item_id,
        "bloc": bloc,
        "localitzacio_objectiu": location,
        "comprovacio": check,
        "indicadors_relacionats": indicators,
        "confiança_actual": confidence,
        "prioritat": priority,
        "motiu": reason,
    }


def _check(
    code: str,
    level: str,
    title: str,
    passed: bool,
    severity: str,
    message: str,
    evidence: dict[str, Any],
) -> ValidationCheck:
    return ValidationCheck(
        code=code,
        level=level,
        title=title,
        status="PASS" if passed else "FAIL",
        severity=severity,
        message=message,
        evidence=evidence,
    )


def _warn(
    code: str,
    level: str,
    title: str,
    message: str,
    evidence: dict[str, Any],
) -> ValidationCheck:
    return ValidationCheck(
        code=code,
        level=level,
        title=title,
        status="WARN",
        severity="minor",
        message=message,
        evidence=evidence,
    )


def _value(by_code: dict[str, dict[str, Any]], code: str) -> float:
    return _float(by_code.get(code, {}).get("value_0_100")) or 0.0


def _contains_any(text: str, patterns: Iterable[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _fmt(value: Any) -> str:
    number = _float(value)
    if number is None:
        return "n/a"
    return f"{number:.3f}".replace(".", ",")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
