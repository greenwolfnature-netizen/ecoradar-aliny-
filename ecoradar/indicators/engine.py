"""EcoRadar Core Indicator Engine.

The engine calculates the 12 EcoRadar Core indicators only from prepared,
validated project data. It requires the Data Source Manager reports before any
calculation and never creates substitute or fictional values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import csv
import json
import math
from pathlib import Path
from typing import Any, Callable

from ecoradar.sources.data_source_manager import DataSourceManager
from ecoradar.sources.mandatory_copernicus import ensure_mandatory_copernicus


CSV_OUTPUT = "indicators/ecoradar_core_indicators.csv"
JSON_OUTPUT = "indicators/ecoradar_core_indicators.json"
REPORT_JSON = "metadata/indicator_engine_report.json"
REPORT_MD = "reports/indicator_engine_report.md"

CORE_NAMES = {
    "CORE_01": "Mosaic del paisatge",
    "CORE_02": "Valor d'hàbitats",
    "CORE_03": "Estat de la vegetació",
    "CORE_04": "Refugis climàtics",
    "CORE_05": "Vulnerabilitat climàtica",
    "CORE_06": "Biodiversitat coneguda",
    "CORE_07": "Pressió humana i ús públic",
    "CORE_08": "Connectivitat ecològica",
    "CORE_09": "Resiliència davant del foc",
    "CORE_10": "Aigua i funcionalitat hídrica",
    "CORE_11": "Potencial de restauració",
    "CORE_12": "Prioritat de gestió",
}


@dataclass(frozen=True)
class CoreIndicator:
    """One EcoRadar Core indicator result."""

    code: str
    name: str
    value_0_100: float | None
    category: str
    status: str
    confidence: str
    sources_used: tuple[str, ...]
    sources_absent: tuple[str, ...]
    calculation_explanation: str
    limitations: tuple[str, ...]
    diagnosis_impact: str
    measurement_kind: str = "synthetic_score"
    direct_value: float | None = None
    direct_unit: str | None = None
    source_date_utc: str | None = None
    primary_result: str | None = None
    interpretation_short: str = ""
    methodology_version: str = "legacy_core_v1"
    profile: dict[str, Any] = field(default_factory=dict)
    guide: dict[str, str] = field(default_factory=dict)
    confidence_dimensions: dict[str, dict[str, str]] = field(default_factory=dict)
    confidence_reason: str = ""
    snapshot_input: str | None = None


def run_indicator_engine(
    project_root: str | Path = "projectes/Alinya",
    *,
    allow_partial_copernicus: bool = False,
) -> dict[str, Any]:
    """Run the mandatory EcoRadar Core Indicator Engine."""

    root = Path(project_root)
    DataSourceManager().ensure_ready_for_indicators(root)
    if not allow_partial_copernicus:
        ensure_mandatory_copernicus(root)
    (root / "indicators").mkdir(parents=True, exist_ok=True)
    (root / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)

    context = _load_context(root)
    indicators = _calculate_indicators(context)

    csv_path = root / CSV_OUTPUT
    json_path = root / JSON_OUTPUT
    report_json = root / REPORT_JSON
    report_md = root / REPORT_MD

    _write_csv(csv_path, indicators)
    _write_json(json_path, indicators, context)
    if indicators and indicators[0].methodology_version == "alinya_core_v2_2026-09-09":
        _write_alinya_phase2_compatibility_outputs(root, indicators, context)
    report_payload = _report_payload(root, indicators, context)
    report_json.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_md.write_text(_report_markdown(report_payload, indicators), encoding="utf-8")

    return {
        "csv": str(csv_path),
        "json": str(json_path),
        "report_json": str(report_json),
        "report_md": str(report_md),
        "indicator_count": len(indicators),
        "status_counts": _counts(indicator.status for indicator in indicators),
        "confidence_counts": _counts(indicator.confidence for indicator in indicators),
    }


def _load_context(root: Path) -> dict[str, Any]:
    completeness = _read_json(root / "metadata" / "indicators_completeness_report.json")
    by_code = {row["indicator"]: row for row in completeness.get("indicators", [])}
    return {
        "root": root,
        "availability": _read_json(root / "metadata" / "data_availability_report.json"),
        "connectors": _read_json(root / "metadata" / "connectors_status_report.json"),
        "completeness": completeness,
        "completeness_by_code": by_code,
        "study_area": _read_json(root / "metadata" / "study_area_metadata.json"),
        "terrain": _read_json(root / "metadata" / "terrain_metadata.json"),
        "land_cover": _read_csv(root / "indicators" / "cobertes_sol_resum.csv"),
        "habitats": _read_csv(root / "indicators" / "habitats_resum.csv"),
        "biodiversity": _read_csv(root / "indicators" / "biodiversitat_resum.csv"),
        "pressure": _read_csv(root / "indicators" / "recreational_pressure_resum.csv"),
        "hydrology": _read_csv(root / "indicators" / "hidrologia_resum.csv"),
        "connectivity": _read_csv(root / "indicators" / "connectivitat_resum.csv"),
        "fires": _read_csv(root / "indicators" / "incendis_resum.csv"),
        "sentinel2": _read_json(root / "indicators" / "teledeteccio_sentinel2.json"),
        "climate_refuges": _read_json(root / "indicators" / "refugis_climatics_potencials.json"),
        "current_fire": _read_json(root / "indicators" / "current_fire_danger.json"),
        "reading_registry": _read_json(root / "metadata" / "reading_registry.json"),
        "habitats_metadata": _read_json(root / "metadata" / "habitats_metadata.json"),
        "biodiversity_metadata": _read_json(root / "metadata" / "biodiversitat_metadata.json"),
        "biodiversity_ecology_metadata": _read_json(root / "metadata" / "biodiversity_ecology_metadata.json"),
        "biodiversity_pilot_metadata": _read_json(root / "metadata" / "biodiversity_habitat_pilot_metadata.json"),
        "biodiversity_knowledge": _read_json(root / "indicators" / "biodiversity_knowledge_coverage.geojson"),
    }


def _calculate_indicators(context: dict[str, Any]) -> list[CoreIndicator]:
    if context["root"].name.casefold() in {"alinya", "alinyà"}:
        from ecoradar.indicators.alinya_phase2 import build_alinya_phase2

        return [CoreIndicator(**record) for record in build_alinya_phase2(context)]
    calculators: tuple[Callable[[dict[str, Any]], CoreIndicator], ...] = (
        _core_01_mosaic,
        _core_02_habitats,
        _core_03_vegetation,
        _core_04_refugia,
        _core_05_vulnerability,
        _core_06_biodiversity,
        _core_07_human_pressure,
        _core_08_connectivity,
        _core_09_fire_resilience,
        _core_10_water,
        _core_11_restoration,
        _core_12_management_priority,
    )
    return [calculator(context) for calculator in calculators]


def _core_01_mosaic(context: dict[str, Any]) -> CoreIndicator:
    cover = context["land_cover"]
    if not cover:
        return _missing(context, "CORE_01", "No hi ha resum de cobertes del sòl validat.")
    total = _sum(cover, "superficie_ha")
    diversity = _entropy_score([_float(row.get("superficie_ha")) for row in cover], total)
    forest = _cover_pct(cover, ("bosc", "boscos"))
    open_agro = _cover_pct(cover, ("prats", "herbassars", "pastures", "conreus"))
    artificial = _cover_pct(cover, ("casc urbà", "casc urba", "xarxa viària", "xarxa viaria", "urbanitzat"))
    habitat_bonus = _clamp(len(context["habitats"]) / 50 * 100) if context["habitats"] else None
    conn_bonus = _connectivity_surface_score(context)
    value = _mean(
        diversity,
        _balance_score(forest, 35, 75),
        _clamp(open_agro / 18 * 100),
        _inverse_score(artificial, 10),
        habitat_bonus,
        conn_bonus,
    )
    return _indicator(
        context,
        "CORE_01",
        value,
        ("land_cover_icgc_cobertes_sol", "habitats_terrestres_v3", "connectivity_infraestructura_verda"),
        "Combina diversitat de cobertes, proporció forestal, espais oberts/agroforestals, artificialització, riquesa d'hàbitats i presència de connectors oficials.",
        (
            "SIGPAC, DUN i MCSC no estan disponibles; l'ús agrari fi no entra al càlcul.",
            "La continuïtat forestal es tracta com a proxy de composició, no com a mètrica espacial completa.",
        ),
        "El mosaic es pot comparar i usar com a base de context, però les decisions agràries fines necessiten SIGPAC/DUN.",
    )


def _core_02_habitats(context: dict[str, Any]) -> CoreIndicator:
    habitats = context["habitats"]
    if not habitats:
        return _missing(context, "CORE_02", "No hi ha cartografia d'hàbitats validada.")
    area = _study_area_ha(context)
    habitat_count = len(habitats)
    hic_ha = _sum((row for row in habitats if _bool(row.get("es_hic"))), "superficie_ha")
    priority_ha = _sum((row for row in habitats if _bool(row.get("es_prioritari"))), "superficie_ha")
    value = _mean(
        _clamp(habitat_count / 45 * 100),
        _clamp(((hic_ha / area * 100) if area else 0) / 60 * 100),
        _clamp(((priority_ha / area * 100) if area else 0) / 20 * 100),
    )
    return _indicator(
        context,
        "CORE_02",
        value,
        ("habitats_terrestres_v3", "hic_v2"),
        "Combina nombre d'hàbitats, superfície d'HIC i superfície d'HIC prioritaris dins l'àrea.",
        (
            "No hi ha validació de camp d'hàbitats.",
            "No hi ha encara llista EcoRadar d'hàbitats sensibles/degradats aplicada com a capa independent.",
        ),
        "La lectura d'hàbitats és sòlida a escala cartogràfica, però les actuacions sobre hàbitats concrets necessiten validació de camp.",
    )


def _core_03_vegetation(context: dict[str, Any]) -> CoreIndicator:
    sentinel = context.get("sentinel2") or {}
    ndvi = _nested_float(sentinel, ("metrics", "ndvi", "median"))
    acquired = sentinel.get("acquired_at_utc")
    if ndvi is None or not acquired:
        return _missing(
            context,
            "CORE_03",
            "No hi ha una lectura NDVI Sentinel-2 validada disponible.",
        )
    completeness = context["completeness_by_code"].get("CORE_03", {})
    absent = tuple(
        source for source in completeness.get("missing_sources", [])
        if source not in {"copernicus_sentinel_ndvi", "copernicus_sentinel_ndmi"}
    )
    return CoreIndicator(
        code="CORE_03",
        name=CORE_NAMES["CORE_03"],
        value_0_100=None,
        category="lectura directa",
        status="PARCIAL",
        confidence="mitjana",
        sources_used=("copernicus_sentinel_ndvi",),
        sources_absent=absent,
        calculation_explanation=(
            "Lectura directa de la mediana NDVI de l'escena Sentinel-2 L2A amb màscara SCL; "
            "no es transforma en una puntuació sintètica 0–100."
        ),
        limitations=(
            "Una sola escena descriu el vigor espectral de la data, no una tendència ni l'estat de conservació.",
            "NDWI, NBR i context climàtic homogeni continuen absents del RADAR sintètic.",
        ),
        diagnosis_impact="Aporta una observació directa traçable sense alterar la fórmula ni la síntesi CORE_12.",
        measurement_kind="direct_reading",
        direct_value=round(ndvi, 3),
        direct_unit="NDVI",
        source_date_utc=str(acquired),
    )


def _core_04_refugia(context: dict[str, Any]) -> CoreIndicator:
    cover = context["land_cover"]
    terrain = context["terrain"]
    if not cover or not terrain:
        return _missing(context, "CORE_04", "Falten cobertes o DEM per estimar refugis climàtics.")
    forest = _cover_pct(cover, ("bosc", "boscos"))
    northness = _nested_float(terrain, ("variables", "northness", "mean"))
    water = _water_score(context)
    value = _mean(
        _clamp(forest),
        _clamp((northness + 1) / 2 * 100) if northness is not None else None,
        water,
    )
    return _indicator(
        context,
        "CORE_04",
        value,
        ("land_cover_icgc_cobertes_sol", "icgc_dem_mdt", "aca_hydrology"),
        "Combina coberta forestal, orientació/northness del DEM i presència relativa de cursos/fonts oficials.",
        (
            "Falten LST, NDMI i NDVI; no es delimiten refugis tèrmics finals.",
            "El valor és un proxy topogràfic-hídric i de coberta, no un mapa final de refugi climàtic.",
        ),
        "Permet detectar potencial preliminar, però no ha de servir encara per delimitar refugis prioritaris sense teledetecció.",
    )


def _core_05_vulnerability(context: dict[str, Any]) -> CoreIndicator:
    cover = context["land_cover"]
    terrain = context["terrain"]
    if not cover or not terrain:
        return _missing(context, "CORE_05", "Falten cobertes o DEM per estimar vulnerabilitat climàtica.")
    forest = _cover_pct(cover, ("bosc", "boscos"))
    artificial = _cover_pct(cover, ("casc urbà", "casc urba", "xarxa viària", "xarxa viaria", "urbanitzat"))
    slope = _nested_float(terrain, ("variables", "slope_degrees", "mean"))
    northness = _nested_float(terrain, ("variables", "northness", "mean"))
    southness = _clamp((1 - ((northness + 1) / 2)) * 100) if northness is not None else None
    value = _mean(
        _inverse_score(forest, 90),
        _clamp((slope or 0) / 35 * 100),
        southness,
        _clamp(artificial / 10 * 100),
        _inverse_score(_water_score(context), 100),
    )
    return _indicator(
        context,
        "CORE_05",
        value,
        ("land_cover_icgc_cobertes_sol", "icgc_dem_mdt", "aca_hydrology"),
        "Combina menor coberta forestal, pendent, exposició sud proxy, artificialització i menor senyal hídric disponible.",
        (
            "Falten LST, NDMI, sequera SPEI i clima Meteocat/AEMET.",
            "El valor representa vulnerabilitat estructural parcial, no vulnerabilitat climàtica completa.",
        ),
        "Pot orientar quines variables cal completar; no ha de convertir-se encara en mapa final de vulnerabilitat.",
    )


def _core_06_biodiversity(context: dict[str, Any]) -> CoreIndicator:
    biodiv = context["biodiversity"]
    if not biodiv:
        return _missing(context, "CORE_06", "No hi ha registres GBIF/iNaturalist normalitzats.")
    records = _sum(biodiv, "nombre_registres")
    species = _sum(biodiv, "nombre_especies")
    recent = _sum(biodiv, "registres_recents")
    group_count = len([row for row in biodiv if _float(row.get("nombre_registres")) > 0])
    value = _mean(
        _clamp(species / 600 * 100),
        _clamp((recent / records * 100) if records else 0),
        _clamp(group_count / 10 * 100),
    )
    return _indicator(
        context,
        "CORE_06",
        value,
        ("gbif_occurrences", "inaturalist_observations"),
        "Combina riquesa d'espècies citades, proporció de registres recents i cobertura de grups taxonòmics.",
        (
            "Falten BDBC, dades pròpies de camp i llistes creuades d'espècies protegides, amenaçades o invasores.",
            "Les fonts públiques són oportunistes i no equivalen a inventari complet.",
        ),
        "Serveix per valorar coneixement disponible, però les decisions sobre espècies sensibles necessiten camp i llistes normatives.",
    )


def _core_07_human_pressure(context: dict[str, Any]) -> CoreIndicator:
    pressure = context["pressure"]
    if not pressure:
        return _missing(context, "CORE_07", "No hi ha dades OSM/Overpass normalitzades.")
    values = {row.get("indicator"): _float(row.get("value")) for row in pressure}
    density = values.get("osm_path_track_road_density", 0.0)
    points = values.get("osm_recreational_point_features", 0.0)
    points_per_1000ha = points / _study_area_ha(context) * 1000 if _study_area_ha(context) else 0
    value = _mean(_clamp(density / 4 * 100), _clamp(points_per_1000ha / 8 * 100))
    return _indicator(
        context,
        "CORE_07",
        value,
        ("osm_public_use",),
        "Combina densitat de camins/pistes OSM i concentració de punts d'ús públic cartografiats.",
        (
            "OSM no mesura intensitat real de visitants.",
            "Strava queda legalment condicionat i no s'ha usat; falten comptadors, gestors i camp.",
        ),
        "Indica pressió potencial per accessibilitat, però no afluència real.",
    )


def _core_08_connectivity(context: dict[str, Any]) -> CoreIndicator:
    cover = context["land_cover"]
    conn = context["connectivity"]
    if not cover or not conn:
        return _missing(context, "CORE_08", "Falten connectivitat oficial o cobertes.")
    natural = _cover_pct(cover, ("bosc", "boscos", "matollar", "prats", "herbassars", "roquissars", "aigua"))
    value = _mean(natural, _connectivity_surface_score(context), _inverse_score(_human_pressure_value(context), 100))
    return _indicator(
        context,
        "CORE_08",
        value,
        ("connectivity_infraestructura_verda", "land_cover_icgc_cobertes_sol", "habitats_terrestres_v3", "aca_hydrology", "osm_public_use"),
        "Combina cobertes naturals, connectors oficials, context d'hàbitats/hidrologia i pressió per accessibilitat.",
        (
            "No hi ha model de barreres fines ni permeabilitat específica per espècie.",
            "La pressió humana s'integra com a proxy d'infraestructura, no d'intensitat d'ús.",
        ),
        "Útil com a lectura estructural preliminar; els corredors prioritaris requereixen model espacial específic.",
    )


def _core_09_fire_resilience(context: dict[str, Any]) -> CoreIndicator:
    cover = context["land_cover"]
    terrain = context["terrain"]
    if not cover or not terrain:
        return _missing(context, "CORE_09", "Falten cobertes o DEM.")
    forest = _cover_pct(cover, ("bosc", "boscos"))
    shrub = _cover_pct(cover, ("matollar",))
    open_agro = _cover_pct(cover, ("prats", "herbassars", "conreus"))
    slope = _nested_float(terrain, ("variables", "slope_degrees", "mean")) or 0
    burned = _metric(context["fires"], "gencat_burned_area_ha") or 0
    access = _metric(context["pressure"], "osm_path_track_road_density") or 0
    water = _water_score(context)
    value = _mean(
        _inverse_score(forest + shrub, 95),
        _clamp(open_agro / 20 * 100),
        _inverse_score(_clamp(slope / 35 * 100), 100),
        _inverse_score(_clamp(burned / 100 * 100), 100),
        _clamp(access / 4 * 100),
        water,
    )
    return _indicator(
        context,
        "CORE_09",
        value,
        ("land_cover_icgc_cobertes_sol", "icgc_dem_mdt", "fires_burned_areas", "osm_public_use", "aca_hydrology"),
        "Combina continuïtat forestal/matollar proxy, mosaic obert, pendent, incendis històrics, accessibilitat i punts/cursos d'aigua.",
        (
            "Falten NDMI, LST i font oficial de combustible/estructura forestal.",
            "No calcula risc d'incendi; només resiliència estructural parcial.",
        ),
        "Serveix per identificar quines capes falten abans de parlar de risc o de prioritzar gestió forestal.",
    )


def _core_10_water(context: dict[str, Any]) -> CoreIndicator:
    hydro = context["hydrology"]
    if not hydro:
        return _missing(context, "CORE_10", "No hi ha hidrologia ACA normalitzada.")
    length_km = _sum(hydro, "length_km")
    springs = sum(int(_float(row.get("feature_count"))) for row in hydro if str(row.get("theme")) == "springs")
    area = _study_area_ha(context)
    density = length_km / (area / 100) if area else 0
    value = _mean(_clamp(density / 1.5 * 100), _clamp(springs / 15 * 100))
    return _indicator(
        context,
        "CORE_10",
        value,
        ("aca_hydrology", "icgc_dem_mdt"),
        "Combina densitat de cursos/drenatge, fonts oficials i disponibilitat de DEM per contextualitzar funcionalitat hídrica.",
        (
            "Falten NDWI, basses/zones humides amb presència dins l'àrea i punts d'aigua validats al camp.",
            "No incorpora estat ecològic de masses d'aigua.",
        ),
        "Permet saber que hi ha base hidrològica, però no avalua encara qualitat ni funcionalitat ecològica completa.",
    )


def _core_11_restoration(context: dict[str, Any]) -> CoreIndicator:
    components = [
        _core_02_habitats(context).value_0_100,
        _core_05_vulnerability(context).value_0_100,
        _inverse_score(_core_10_water(context).value_0_100, 100),
        _balance_score(_core_07_human_pressure(context).value_0_100, 20, 60),
        _core_08_connectivity(context).value_0_100,
    ]
    if all(value is None for value in components):
        return _missing(context, "CORE_11", "No hi ha components suficients per estimar potencial de restauració.")
    value = _mean(*components)
    return _indicator(
        context,
        "CORE_11",
        value,
        ("habitats_terrestres_v3", "land_cover_icgc_cobertes_sol", "icgc_dem_mdt", "aca_hydrology", "connectivity_infraestructura_verda", "osm_public_use"),
        "Combina valor d'hàbitats, vulnerabilitat climàtica parcial, funcionalitat hídrica, pressió humana gestionable i connectivitat.",
        (
            "Falten Sentinel, hàbitats degradats validats, hàbitats font, SIGPAC/DUN i treball de camp.",
            "No delimita zones de restauració; només calcula potencial agregat provisional.",
        ),
        "Pot orientar on cal completar dades abans de proposar restauració; no és encara una priorització espacial.",
    )


def _core_12_management_priority(context: dict[str, Any]) -> CoreIndicator:
    components = [
        _core_01_mosaic(context),
        _core_02_habitats(context),
        _core_03_vegetation(context),
        _core_04_refugia(context),
        _core_05_vulnerability(context),
        _core_06_biodiversity(context),
        _core_07_human_pressure(context),
        _core_08_connectivity(context),
        _core_09_fire_resilience(context),
        _core_10_water(context),
        _core_11_restoration(context),
    ]
    values = [indicator.value_0_100 for indicator in components if indicator.value_0_100 is not None]
    if not values:
        return _missing(context, "CORE_12", "No hi ha indicadors base calculables.")
    value = sum(values) / len(values)
    used_sources = tuple(sorted({
        source
        for indicator in components
        if indicator.value_0_100 is not None
        for source in indicator.sources_used
    }))
    missing_sources = tuple(sorted({source for indicator in components for source in indicator.sources_absent}))
    return _indicator(
        context,
        "CORE_12",
        value,
        used_sources,
        "Síntesi dels indicadors Core calculables. Manté estat parcial si qualsevol font crítica de síntesi continua absent.",
        (
            "No genera recomanacions ni zones prioritàries.",
            "La síntesi queda limitada per absència de Copernicus, clima, combustible oficial i treball de camp.",
        ),
        "Ofereix només una lectura agregada de motor; no substitueix diagnosi ni priorització de gestió.",
        explicit_absent=missing_sources,
        force_partial=True,
    )


def _indicator(
    context: dict[str, Any],
    code: str,
    value: float | None,
    sources_used: tuple[str, ...],
    calculation: str,
    limitations: tuple[str, ...],
    impact: str,
    *,
    explicit_absent: tuple[str, ...] | None = None,
    force_partial: bool = False,
) -> CoreIndicator:
    completeness = context["completeness_by_code"].get(code, {})
    absent = tuple(explicit_absent if explicit_absent is not None else completeness.get("missing_sources", []))
    normalized = round(value, 2) if value is not None else None
    status = _engine_status(normalized, completeness, force_partial=force_partial)
    confidence = _engine_confidence(normalized, completeness, status)
    return CoreIndicator(
        code=code,
        name=CORE_NAMES[code],
        value_0_100=normalized,
        category=_category(normalized),
        status=status,
        confidence=confidence,
        sources_used=tuple(sources_used),
        sources_absent=absent,
        calculation_explanation=calculation,
        limitations=limitations,
        diagnosis_impact=impact,
    )


def _missing(context: dict[str, Any], code: str, reason: str) -> CoreIndicator:
    completeness = context["completeness_by_code"].get(code, {})
    absent = tuple(completeness.get("missing_sources", []))
    return CoreIndicator(
        code=code,
        name=CORE_NAMES[code],
        value_0_100=None,
        category="no disponible",
        status="NO DISPONIBLE",
        confidence="baixa",
        sources_used=(),
        sources_absent=absent,
        calculation_explanation="No calculat perquè falten fonts crítiques validades.",
        limitations=(reason,),
        diagnosis_impact="Aquest indicador no pot alimentar la diagnosi fins completar les fonts crítiques indicades.",
    )


def _engine_status(value: float | None, completeness: dict[str, Any], *, force_partial: bool = False) -> str:
    if value is None:
        return "NO DISPONIBLE"
    if force_partial:
        return "PARCIAL"
    status = completeness.get("status")
    if status == "DISPONIBLE":
        return "COMPLET"
    if status == "PARCIAL":
        return "PARCIAL"
    return "PARCIAL"


def _engine_confidence(value: float | None, completeness: dict[str, Any], status: str) -> str:
    if value is None or status == "NO DISPONIBLE":
        return "baixa"
    confidence = str(completeness.get("confidence") or "baixa")
    if status == "PARCIAL" and confidence == "alta":
        return "mitjana"
    return confidence


def _write_csv(path: Path, indicators: list[CoreIndicator]) -> None:
    fieldnames = list(asdict(indicators[0]).keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for indicator in indicators:
            row = asdict(indicator)
            for field_name in ("sources_used", "sources_absent", "limitations"):
                row[field_name] = "; ".join(row[field_name])
            for field_name in ("profile", "guide", "confidence_dimensions"):
                row[field_name] = json.dumps(row[field_name], ensure_ascii=False, sort_keys=True)
            writer.writerow(row)


def _write_json(path: Path, indicators: list[CoreIndicator], context: dict[str, Any]) -> None:
    payload = {
        "generated_at": _now(),
        "project": context["root"].name,
        "methodology_version": indicators[0].methodology_version if indicators else None,
        "snapshot_id": context.get("reading_registry", {}).get("snapshot_id"),
        "preflight_reports": {
            "data_availability_report": "metadata/data_availability_report.json",
            "connectors_status_report": "metadata/connectors_status_report.json",
            "indicators_completeness_report": "metadata/indicators_completeness_report.json",
        },
        "indicators": [asdict(indicator) for indicator in indicators],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_alinya_phase2_compatibility_outputs(
    root: Path,
    indicators: list[CoreIndicator],
    context: dict[str, Any],
) -> None:
    """Keep historical Alinyà filenames synchronized with the Phase 2 payload.

    These aliases prevent old report and packaging entry points from exposing
    pre-Phase-2 CORE scores. They contain the same records as the canonical
    indicator output and do not calculate additional values.
    """

    canonical_json = root / JSON_OUTPUT
    canonical_csv = root / CSV_OUTPUT
    json_aliases = (
        root / "indicators" / "ecoradar_core.json",
        root / "indicators" / "ecoradar_indicators.json",
    )
    csv_aliases = (
        root / "indicators" / "ecoradar_core.csv",
        root / "indicators" / "ecoradar_indicators_summary.csv",
    )
    for path in json_aliases:
        path.write_text(canonical_json.read_text(encoding="utf-8"), encoding="utf-8")
    for path in csv_aliases:
        path.write_bytes(canonical_csv.read_bytes())

    snapshot_id = context.get("reading_registry", {}).get("snapshot_id")
    metadata = {
        "project": root.name,
        "generated_at": _now(),
        "methodology_version": "alinya_core_v2_2026-09-09",
        "snapshot_id": snapshot_id,
        "status": "compatibility_alias",
        "canonical_json": JSON_OUTPUT,
        "canonical_csv": CSV_OUTPUT,
        "rule": "Els alias no contenen puntuacions CORE 0–100 ni executen cap càlcul addicional.",
        "aliases": [
            str(path.relative_to(root))
            for path in (*json_aliases, *csv_aliases)
        ],
    }
    for path in (
        root / "metadata" / "ecoradar_core_metadata.json",
        root / "metadata" / "ecoradar_indicators_metadata.json",
    ):
        path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    maps_dir = root / "maps" / "ecoradar_core"
    maps_dir.mkdir(parents=True, exist_ok=True)
    for indicator in indicators:
        result = indicator.primary_result or "NO AVALUABLE"
        text = (
            f"# {indicator.code} · {indicator.name}\n\n"
            "Metodologia: `alinya_core_v2_2026-09-09`\n\n"
            f"Resultat: `{result}`\n\n"
            f"Estat: `{indicator.status}` · Confiança: `{indicator.confidence}`\n\n"
            f"{indicator.interpretation_short}\n\n"
            "Aquest document no expressa una puntuació ecològica global.\n"
        )
        (maps_dir / f"{indicator.code.lower()}.md").write_text(text, encoding="utf-8")

    # The old executive summary recorded a smaller historical download. Keep
    # its record-count field synchronized with the approved CORE_06 universe.
    core06 = next((item for item in indicators if item.code == "CORE_06"), None)
    basic_path = root / "indicators" / "ecoradar_01_resum.csv"
    if core06 and basic_path.exists():
        records = core06.profile.get("records_normalized")
        rows = _read_csv(basic_path)
        for row in rows:
            if row.get("indicador") == "nombre_registres_biodiversitat" and records is not None:
                row["valor"] = str(records)
                row["font"] = "biodiversitat_metadata.json"
                row["notes"] = "Registres normalitzats després del retall espacial; univers de CORE_06 Fase 2."
        if rows:
            with basic_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)


def _report_payload(root: Path, indicators: list[CoreIndicator], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": root.name,
        "generated_at": _now(),
        "scope": "EcoRadar Core Indicator Engine; lectures directes, perfils i síntesi no compensatòria",
        "preflight_checked": {
            "data_availability_report.json": (root / "metadata" / "data_availability_report.json").exists(),
            "connectors_status_report.json": (root / "metadata" / "connectors_status_report.json").exists(),
            "indicators_completeness_report.json": (root / "metadata" / "indicators_completeness_report.json").exists(),
        },
        "outputs": {
            "csv": CSV_OUTPUT,
            "json": JSON_OUTPUT,
            "report_json": REPORT_JSON,
            "report_md": REPORT_MD,
        },
        "status_counts": _counts(indicator.status for indicator in indicators),
        "confidence_counts": _counts(indicator.confidence for indicator in indicators),
        "rules_enforced": [
            "No s'han inventat dades.",
            "No s'ha substituït cap font absent per estimacions arbitràries.",
            "La confiança integra completesa, vigència, cobertura, resolució, QA, representativitat, biaix i validació.",
            "L'estat del resultat és independent de la confiança i de la simple existència de fitxers.",
            "No s'ha aplicat una escala 0-100 comuna a dimensions no commensurables.",
            "No s'ha generat diagnosi, recomanacions, fitxa ni PDF.",
        ],
    }


def _report_markdown(payload: dict[str, Any], indicators: list[CoreIndicator]) -> str:
    lines = [
        "# Indicator Engine Report",
        "",
        f"Projecte: `{payload['project']}`",
        f"Generat: `{payload['generated_at']}`",
        "",
        "## Preflight obligatori",
        "",
        "| Fitxer | Existeix |",
        "| --- | --- |",
    ]
    for name, exists in payload["preflight_checked"].items():
        lines.append(f"| {name} | {'sí' if exists else 'no'} |")
    lines.extend([
        "",
        "## Resum",
        "",
        "| Estat | Nombre |",
        "| --- | ---: |",
    ])
    for status, count in sorted(payload["status_counts"].items()):
        lines.append(f"| {status} | {count} |")
    lines.extend([
        "",
        "## Indicadors EcoRadar Core",
        "",
        "| Codi | Indicador | Resultat | Tipus | Estat | Confiança | Fonts utilitzades | Fonts absents |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for indicator in indicators:
        value = indicator.primary_result or "NO AVALUABLE"
        lines.append(
            "| "
            + " | ".join(
                [
                    indicator.code,
                    indicator.name,
                    value,
                    indicator.measurement_kind,
                    indicator.status,
                    indicator.confidence,
                    ", ".join(indicator.sources_used) or "-",
                    ", ".join(indicator.sources_absent) or "-",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Limitacions i impacte sobre la diagnosi", ""])
    for indicator in indicators:
        lines.append(f"### {indicator.code} · {indicator.name}")
        lines.append(f"- Càlcul: {indicator.calculation_explanation}")
        lines.append(f"- Resultat: {indicator.primary_result or 'NO AVALUABLE'}")
        lines.append(f"- Vector de confiança: {json.dumps(indicator.confidence_dimensions, ensure_ascii=False)}")
        lines.append(f"- Raó de confiança: {indicator.confidence_reason}")
        lines.append(f"- Limitacions: {'; '.join(indicator.limitations) if indicator.limitations else '-'}")
        lines.append(f"- Impacte: {indicator.diagnosis_impact}")
        lines.append("")
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sum(rows: Any, field: str) -> float:
    return sum(_float(row.get(field)) for row in rows)


def _metric(rows: list[dict[str, str]], metric: str) -> float | None:
    for row in rows:
        if row.get("metric") == metric or row.get("indicator") == metric:
            return _float(row.get("value"))
    return None


def _cover_pct(rows: list[dict[str, str]], patterns: tuple[str, ...]) -> float:
    total = _sum(rows, "superficie_ha")
    if not total:
        return 0.0
    selected = 0.0
    for row in rows:
        name = str(row.get("tipus_coberta", "")).lower()
        if any(pattern in name for pattern in patterns):
            selected += _float(row.get("superficie_ha"))
    return selected / total * 100


def _connectivity_surface_score(context: dict[str, Any]) -> float | None:
    rows = context["connectivity"]
    area = _study_area_ha(context)
    if not rows or not area:
        return None
    connector_ha = _sum((row for row in rows if "principals" in str(row.get("layer_id"))), "area_ha")
    return _clamp((connector_ha / area * 100) / 25 * 100)


def _human_pressure_value(context: dict[str, Any]) -> float | None:
    pressure = context["pressure"]
    if not pressure:
        return None
    values = {row.get("indicator"): _float(row.get("value")) for row in pressure}
    density = values.get("osm_path_track_road_density", 0.0)
    points = values.get("osm_recreational_point_features", 0.0)
    area = _study_area_ha(context)
    points_per_1000ha = points / area * 1000 if area else 0
    return _mean(_clamp(density / 4 * 100), _clamp(points_per_1000ha / 8 * 100))


def _water_score(context: dict[str, Any]) -> float:
    hydro = context["hydrology"]
    if not hydro:
        return 0.0
    length_km = _sum(hydro, "length_km")
    springs = sum(int(_float(row.get("feature_count"))) for row in hydro if str(row.get("theme")) == "springs")
    area = _study_area_ha(context)
    density = length_km / (area / 100) if area else 0.0
    return _mean(_clamp(density / 1.5 * 100), _clamp(springs / 15 * 100)) or 0.0


def _study_area_ha(context: dict[str, Any]) -> float:
    metadata = context.get("study_area", {})
    return _float(metadata.get("surface_ha") or metadata.get("area_ha") or metadata.get("study_area_surface_ha"))


def _nested_float(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current is None:
        return None
    return _float(current)


def _float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "si", "sí"}


def _mean(*values: float | None) -> float:
    clean = [value for value in values if value is not None and not math.isnan(value)]
    return sum(clean) / len(clean) if clean else 0.0


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _inverse_score(value: float | None, max_bad: float) -> float:
    if value is None:
        return 0.0
    return _clamp(100 - (value / max_bad * 100))


def _balance_score(value: float | None, optimum_low: float, optimum_high: float) -> float:
    if value is None:
        return 0.0
    if optimum_low <= value <= optimum_high:
        return 100.0
    if value < optimum_low:
        return _clamp(value / optimum_low * 100)
    return _clamp(100 - ((value - optimum_high) / (100 - optimum_high) * 100))


def _entropy_score(values: list[float], total: float) -> float:
    positives = [value for value in values if value > 0]
    if total <= 0 or len(positives) <= 1:
        return 0.0
    entropy = -sum((value / total) * math.log(value / total) for value in positives)
    max_entropy = math.log(len(positives))
    return _clamp(entropy / max_entropy * 100)


def _category(value: float | None) -> str:
    if value is None:
        return "no disponible"
    if value < 20:
        return "molt baix"
    if value < 40:
        return "baix"
    if value < 60:
        return "mitjà"
    if value < 80:
        return "alt"
    return "molt alt"


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    print(json.dumps(run_indicator_engine(), indent=2, ensure_ascii=False))
