"""Phase 2 methodology for the twelve Alinyà EcoRadar CORE results.

The module deliberately avoids a common 0--100 scale.  It reports direct
readings, non-compensatory profiles and decision gates from the evidence that
is actually available in the Alinyà project snapshot.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any


METHODOLOGY_VERSION = "alinya_core_v2_2026-09-09"

NAMES = {
    "CORE_01": "Configuració i mosaic funcional del paisatge",
    "CORE_02": "Responsabilitat territorial per hàbitats d’interès",
    "CORE_03": "Activitat verda observada (NDVI)",
    "CORE_04": "Potencial estructural de refugi climàtic",
    "CORE_05": "Perfil d’exposició i vulnerabilitat climàtica ecològica",
    "CORE_06": "Cobertura del coneixement de biodiversitat",
    "CORE_07": "Accessibilitat cartografiada i ús potencial",
    "CORE_08": "Continuïtat estructural i connectivitat potencial",
    "CORE_09": "Perfil de susceptibilitat i recuperació davant del foc",
    "CORE_10": "Presència hídrica cartografiada",
    "CORE_11": "Cribratge de necessitat i oportunitat de restauració",
    "CORE_12": "Síntesi multicriteri per a la gestió",
}

CONFIDENCE_KEYS = (
    "completesa",
    "vigencia",
    "cobertura",
    "resolucio",
    "qa",
    "representativitat",
    "biaix",
    "validacio",
)


def build_alinya_phase2(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the twelve project-specific Phase 2 CORE records."""

    calculators = (
        _core_01,
        _core_02,
        _core_03,
        _core_04,
        _core_05,
        _core_06,
        _core_07,
        _core_08,
        _core_09,
        _core_10,
        _core_11,
        _core_12,
    )
    results: list[dict[str, Any]] = []
    for calculator in calculators:
        result = calculator(context, results)
        _validate_result(result)
        results.append(result)
    return results


def _result(
    context: dict[str, Any],
    code: str,
    *,
    kind: str,
    primary: str,
    category: str,
    status: str,
    dimensions: dict[str, tuple[str, str]],
    sources: tuple[str, ...],
    absent: tuple[str, ...],
    calculation: str,
    limitations: tuple[str, ...],
    impact: str,
    interpretation_short: str,
    profile: dict[str, Any],
    guide: dict[str, str],
    direct_value: float | None = None,
    direct_unit: str | None = None,
    source_date_utc: str | None = None,
) -> dict[str, Any]:
    confidence, reason = _confidence(dimensions)
    return {
        "code": code,
        "name": NAMES[code],
        "value_0_100": None,
        "category": category,
        "status": status,
        "confidence": confidence,
        "sources_used": sources,
        "sources_absent": absent,
        "calculation_explanation": calculation,
        "limitations": limitations,
        "diagnosis_impact": impact,
        "measurement_kind": kind,
        "direct_value": direct_value,
        "direct_unit": direct_unit,
        "source_date_utc": source_date_utc,
        "primary_result": primary,
        "interpretation_short": interpretation_short,
        "methodology_version": METHODOLOGY_VERSION,
        "profile": profile,
        "guide": guide,
        "confidence_dimensions": {
            key: {"rating": dimensions[key][0], "reason": dimensions[key][1]}
            for key in CONFIDENCE_KEYS
        },
        "confidence_reason": reason,
        "snapshot_input": context.get("reading_registry", {}).get("snapshot_id"),
    }


def _core_01(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    cover = context["land_cover"]
    forest = _cover_pct(cover, ("bosc", "boscos"))
    open_area = _cover_pct(cover, ("prats", "herbassars", "pastures", "conreus"))
    artificial = _cover_pct(cover, ("casc urbà", "casc urba", "xarxa viària", "xarxa viaria"))
    configuration = _landscape_configuration(context["root"])
    largest = configuration.get("largest_patch_ha")
    primary = f"Perfil estructural · bosc {_ca(forest, 1)} %"
    if largest is not None:
        primary += f" · taca màxima {_ca(largest, 1)} ha"
    profile = {
        "composition": {
            "forest_pct": round(forest, 2),
            "open_and_agricultural_pct": round(open_area, 2),
            "artificial_pct": round(artificial, 3),
            "shannon_composition": round(_shannon(cover), 4),
            "role": "descriptors sense signe universal de qualitat",
        },
        "configuration": configuration,
        "functional_assessment": {
            "status": "NO AVALUABLE",
            "missing": ["objectiu d’hàbitat o procés", "escala funcional", "referència local", "contrast de camp"],
        },
    }
    dimensions = _dimensions(
        completeness=("adequada", "Cobertes ICGC disponibles per a tot l’àmbit."),
        freshness=("adequada", "Capa estructural 2024; no es presenta com una observació diària."),
        coverage=("adequada", "La suma de cobertes coincideix amb l’àmbit validat."),
        resolution=("limitada", "La cartografia permet estructura general, però la sensibilitat a gra no s’ha contrastat."),
        qa=("adequada", "Geometries oficials retallades i àrees calculades en EPSG:25831."),
        representativeness=("limitada", "No s’ha definit l’hàbitat o procés receptor de la configuració."),
        bias=("limitada", "Les vores cartogràfiques poden incloure límits de classificació sense funció d’ecotò."),
        validation=("insuficient", "No hi ha referència local ni validació de camp de la funcionalitat del mosaic."),
    )
    return _result(
        context, "CORE_01", kind="descriptive_profile", primary=primary,
        category="perfil estructural", status="PARCIAL", dimensions=dimensions,
        sources=("land_cover_icgc_cobertes_sol",),
        absent=("mosaic_functional_reference", "field_validation"),
        calculation=(
            "Mostra proporcions de coberta, Shannon només com a descriptor composicional i mètriques espacials "
            "de les taques cartografiades. No agrega els components ni premia fragmentació, diversitat o vora."
        ),
        limitations=(
            "La mida i la vora de taca depenen de l’escala i de la classificació de la font.",
            "Els ecotons funcionals no es classifiquen sense contrast, objectiu i validació.",
        ),
        impact="Aporta estructura territorial i identifica quina configuració cal validar per hàbitat o procés.",
        interpretation_short="Descriu composició i taques; no és una nota de qualitat ni pressuposa que més mosaic sigui millor.",
        profile=profile,
        guide={
            "measure": "La composició i la disposició espacial de les cobertes cartografiades a Alinyà.",
            "basis": "Cobertes del sòl ICGC 2024 retallades a l’àmbit, amb geometries i superfície en EPSG:25831.",
            "calculation": "Proporcions, Shannon descriptiu, nombre i mida de taques, mida efectiva i densitat de vora. Cap mètrica s’agrega ni rep un signe ecològic universal.",
            "interpretation": "Permet descriure continuïtat i fragmentació cartogràfica. No demostra funcionalitat, qualitat, connectivitat per espècies ni que més diversitat o més vora sigui millor.",
            "limits": "Falten objectiu ecològic, escala funcional, contrast de vores i referència local.",
        },
    )


def _core_02(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    rows = context["habitats"]
    area = _study_area_ha(context)
    hic_ha = _sum((row for row in rows if _bool(row.get("es_hic"))), "superficie_ha")
    priority_ha = _sum((row for row in rows if _bool(row.get("es_prioritari"))), "superficie_ha")
    point_count = int(context.get("habitats_metadata", {}).get("point_features_clipped") or 0)
    hic_pct = hic_ha / area * 100 if area else None
    priority_pct = priority_ha / area * 100 if area else None
    profile = {
        "polygon_denominator_ha": round(area, 2),
        "habitat_types": len(rows),
        "hic_area_ha": round(hic_ha, 2),
        "hic_share_pct": _round(hic_pct, 2),
        "priority_hic_area_ha": round(priority_ha, 2),
        "priority_hic_share_pct": _round(priority_pct, 2),
        "small_habitat_point_presences": point_count,
        "point_presences_enter_area_denominator": False,
        "conservation_status": "NO AVALUABLE",
    }
    dimensions = _dimensions(
        completeness=("adequada", "Polígons, camps HIC i presències puntuals estan disponibles."),
        freshness=("adequada", "Versió oficial d’hàbitats documentada com a inventari, no com a lectura d’avui."),
        coverage=("adequada", "La superfície poligonal retallada cobreix l’àmbit documentat."),
        resolution=("limitada", "Els hàbitats menors de 1,5 ha poden constar com a punts i no com a superfície."),
        qa=("adequada", "Àrees recalculades en EPSG:25831 i punts exclosos del denominador superficial."),
        representativeness=("adequada", "Les mètriques representen responsabilitat territorial cartografiada."),
        bias=("limitada", "La representació mínima de la cartografia pot ometre o simplificar peces petites."),
        validation=("insuficient", "No hi ha variables locals d’estructura, funcions, pressions i perspectives."),
    )
    return _result(
        context, "CORE_02", kind="direct_inventory", primary=(
            f"{_ca(hic_ha, 1)} ha HIC · {_ca(hic_pct, 1)} % · {_ca(priority_ha, 1)} ha prioritaris"
        ), category="responsabilitat territorial", status="COMPLET", dimensions=dimensions,
        sources=("habitats_terrestres_v3", "hic_v2"), absent=("habitat_condition_field_data",),
        calculation="Valors directes d’àrea i proporció sobre 5.464,03 ha; les 289 presències puntuals no es converteixen en hectàrees.",
        limitations=("No avalua estat de conservació.", "La presència HIC incrementa responsabilitat i cautela, no qualitat ecològica."),
        impact="Identifica obligacions i sectors de prudència sense fabricar una puntuació de conservació.",
        interpretation_short="Mesura responsabilitat cartografiada per HIC; no mesura estat de conservació.",
        profile=profile,
        guide={
            "measure": "La superfície i la representació cartografiada d’HIC, inclosos els prioritaris.",
            "basis": "Hàbitats terrestres v3 poligonals i puntuals de la Generalitat, retallats a l’àmbit.",
            "calculation": "Hectàrees i percentatges sobre l’àmbit poligonal; les presències puntuals es compten a part i mai es transformen en superfície.",
            "interpretation": "Més HIC significa més responsabilitat territorial i cautela. No significa millor estat, qualitat o tendència favorable.",
            "limits": "Per avaluar conservació calen estructura, funcions, pressions, perspectives i validació de camp.",
        },
    )


def _core_03(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    sentinel = context.get("sentinel2") or {}
    ndvi = _nested(sentinel, "metrics", "ndvi", "median")
    acquired = sentinel.get("acquired_at_utc")
    if ndvi is None or not acquired:
        return _not_evaluable(context, "CORE_03", "No hi ha cap escena NDVI QA-vàlida.", "direct_reading")
    metrics = sentinel.get("metrics", {}).get("ndvi", {})
    profile = {
        "median": ndvi,
        "p10": metrics.get("p10"),
        "p90": metrics.get("p90"),
        "valid_area_ha": sentinel.get("valid_area_ha"),
        "valid_coverage_pct": sentinel.get("valid_coverage_pct"),
        "acquired_at_utc": acquired,
        "phenological_anomaly": "NO AVALUABLE · no hi ha línia base comparable per coberta i època",
    }
    dimensions = _dimensions(
        completeness=("adequada", "NDVI, distribució i màscara SCL consten a l’escena."),
        freshness=("insuficient", "L’escena és del 07/07/2026 i només pot descriure aquella data."),
        coverage=("adequada", f"Cobertura vàlida {sentinel.get('valid_coverage_pct')} % de l’àmbit rasteritzat."),
        resolution=("adequada", "Sentinel-2 L2A a 10 m per a NDVI."),
        qa=("adequada", "dataMask i classes SCL 4, 5 i 6; núvol, ombra, neu i invàlids exclosos."),
        representativeness=("limitada", "Una mediana territorial barreja cobertes i gradients altitudinals."),
        bias=("limitada", "Una sola escena no controla fenologia ni variabilitat estacional."),
        validation=("limitada", "La lectura espectral és verificable, però no s’ha contrastat amb vigor o estat al camp."),
    )
    return _result(
        context, "CORE_03", kind="direct_reading",
        primary=f"NDVI {_ca(ndvi, 3)} · {_date_ca(acquired)}", category="lectura directa datada",
        status="COMPLET", dimensions=dimensions, sources=("copernicus_sentinel_ndvi",),
        absent=("phenological_baseline", "field_validation"),
        calculation="Mediana, P10 i P90 dels píxels NDVI vàlids de l’escena Sentinel-2 L2A; no es transforma a 0–100.",
        limitations=("Descriu verdor espectral el 07/07/2026, no l’estat actual.", "No és biodiversitat, biomassa, humitat ni estat de conservació."),
        impact="Aporta evidència datada sobre activitat verda i conserva separat el context fenològic no disponible.",
        interpretation_short="Lectura espectral d’una escena concreta; sense sèrie fenològica no es classifica com a bona o dolenta.",
        profile=profile, direct_value=round(float(ndvi), 3), direct_unit="NDVI", source_date_utc=str(acquired),
        guide={
            "measure": "La verdor o activitat fotosintètica espectral relativa dels píxels vegetats en la data de l’escena.",
            "basis": "Sentinel-2 L2A, bandes vermella i infraroja propera, amb dataMask i SCL.",
            "calculation": "NDVI=(B08−B04)/(B08+B04); es mostren mediana i distribució dels píxels vàlids, sense escala 0–100.",
            "interpretation": "El valor només és comparable amb el mateix tipus de coberta i moment fenològic. NDVI alt no equival a millor conservació ni més biodiversitat.",
            "limits": "Falta una sèrie recent i una línia base fenològica per coberta; la dada no descriu setembre de 2026.",
        },
    )


def _core_04(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    cover = context["land_cover"]
    terrain = context.get("terrain") or {}
    refuges = context.get("climate_refuges") or {}
    forest = _cover_pct(cover, ("bosc", "boscos"))
    northness = _nested(terrain, "variables", "northness", "mean")
    signal = refuges.get("high_or_very_high_share_of_vegetated_valid_pct")
    denominator = refuges.get("denominator") or {}
    profile = {
        "structural_potential": {
            "forest_cover_pct": round(forest, 2),
            "mean_northness": northness,
            "terrain_role": "context estructural; no prova microclima",
            "mapped_water_role": "context cartogràfic; no entra a la fórmula del senyal observat",
        },
        "observed_satellite_signal": {
            "high_or_very_high_share_pct": signal,
            "denominator": denominator,
            "formula": _nested(refuges, "method", "formula"),
            "temporal_semantics": "compost LST 2025–2026 + escena Sentinel-2 07/07/2026",
        },
        "field_validated_refuge": "NO AVALUABLE",
    }
    dimensions = _dimensions(
        completeness=("limitada", "Hi ha estructura i senyal satel·lital, però no microclima ni permanència hídrica."),
        freshness=("insuficient", "El producte barreja un compost multitemporal LST i una escena Sentinel-2 antiga."),
        coverage=("adequada", f"El denominador vàlid cobreix {denominator.get('share_of_study_raster_pct')} % del raster de l’àmbit."),
        resolution=("limitada", "Les entrades es reprojecten a una malla comuna, però la LST original és de 30 m i l’espectral de 10 m."),
        qa=("adequada", "El denominador exigeix LST, NDMI i NDVI vàlids i NDVI ≥ 0,30."),
        representativeness=("limitada", "Un senyal superficial relatiu no representa el microclima de tots els receptors."),
        bias=("limitada", "La composició estival pot suavitzar extrems i la cobertura forestal no garanteix refugi."),
        validation=("insuficient", "No hi ha sensors microclimàtics ni contrast de camp en episodis càlids i secs."),
    )
    return _result(
        context, "CORE_04", kind="dual_profile",
        primary=f"Estructural parcial · senyal satel·lital {_ca(signal, 1)} %",
        category="dos productes diferenciats", status="PARCIAL", dimensions=dimensions,
        sources=("land_cover_icgc_cobertes_sol", "icgc_dem_mdt", "detailed_surface_temperature", "copernicus_sentinel_ndmi", "copernicus_sentinel_ndvi"),
        absent=("microclimate_field_series", "permanent_water_validation"),
        calculation="Manté separat el perfil estructural del senyal relatiu 0,50·frescor LST + 0,30·NDMI + 0,20·NDVI. El 42,3 % usa només el denominador vegetat amb les tres entrades vàlides.",
        limitations=("El senyal no és una observació d’avui ni una normal climàtica.", "Aigua i fonts es dibuixen com a context i no entren en la fórmula satel·lital."),
        impact="Permet localitzar zones candidates per contrastar, però no declara refugis funcionals.",
        interpretation_short="Separa atributs estructurals i senyal tèrmic/hídric; cap dels dos confirma un refugi ecològic.",
        profile=profile,
        guide={
            "measure": "D’una banda, atributs estructurals compatibles amb amortiment; de l’altra, un senyal satel·lital relatiu de frescor, humitat i verdor.",
            "basis": "Coberta i DEM per a estructura; compost Landsat LST i Sentinel-2 NDMI/NDVI per al senyal observat.",
            "calculation": "Els dos productes no s’agreguen. El senyal satel·lital conserva els pesos 50/30/20 i explicita el denominador vegetat vàlid.",
            "interpretation": "Més atributs o més senyal relatiu indiquen candidats a verificar. No proven microclima estable, aigua permanent o refugi per a totes les espècies.",
            "limits": "Entrades temporalment incompatibles i absència de validació microclimàtica de camp.",
        },
    )


def _core_05(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    registry = context.get("reading_registry", {}).get("readings", {})
    exposure = {
        key: _registry_extract(registry.get(key))
        for key in ("air_temperature", "precipitation_30d", "days_without_significant_rain", "surface_temperature")
    }
    profile = {
        "exposure": {"status": "context actual/parcial", "readings": exposure},
        "sensitivity": {"status": "NO AVALUABLE", "missing": ["receptors definits", "llindars i resposta per hàbitat", "estat o trets"]},
        "adaptive_capacity": {"status": "NO AVALUABLE", "missing": ["refugis persistents validats", "connectivitat funcional", "regeneració demostrada"]},
        "vulnerability": "NO AVALUABLE",
    }
    dimensions = _dimensions(
        completeness=("insuficient", "Només hi ha context d’exposició; falten sensibilitat i capacitat adaptativa."),
        freshness=("limitada", "Meteorologia és actual, però LST i vegetació són context multitemporal o antic."),
        coverage=("limitada", "Meteorologia és puntual i no representa cada vessant; falta exposició territorial homogènia."),
        resolution=("limitada", "Es barregen suport puntual, raster i inventari estructural sense model de receptor."),
        qa=("adequada", "Cada font conserva data, suport i semàntica al registre de lectures."),
        representativeness=("insuficient", "No s’ha definit cap receptor ecològic ni relació dosi-resposta."),
        bias=("insuficient", "Els proxies estructurals no poden substituir sensibilitat ni capacitat adaptativa."),
        validation=("insuficient", "No hi ha model local validat de vulnerabilitat climàtica."),
    )
    return _result(
        context, "CORE_05", kind="three_axis_profile", primary="NO AVALUABLE · només exposició parcial",
        category="perfil incomplet", status="NO AVALUABLE", dimensions=dimensions,
        sources=("meteocat", "detailed_surface_temperature"),
        absent=("climate_normals", "receptor_sensitivity", "adaptive_capacity_validation"),
        calculation="Presenta separadament exposició, sensibilitat i capacitat adaptativa; no calcula mitjana ni usa altres CORE com a substituts.",
        limitations=("Exposició alta no equival a vulnerabilitat alta.", "Falten normals, extrems i resposta ecològica per receptor."),
        impact="Evita atribuir vulnerabilitat a orientació, pendent, bosc o aigua sense mecanisme validat.",
        interpretation_short="Hi ha context d’exposició, però la vulnerabilitat ecològica no es pot calcular sense receptor i resposta.",
        profile=profile,
        guide={
            "measure": "Exposició climàtica, sensibilitat del receptor i capacitat d’ajust o persistència, sempre per separat.",
            "basis": "Registre versionat de meteorologia i teledetecció; les dades de sensibilitat i capacitat encara no existeixen amb prou qualitat.",
            "calculation": "Perfil de tres eixos sense mitjana. La vulnerabilitat només seria avaluable si els tres eixos fossin compatibles i específics del receptor.",
            "interpretation": "Una exposició elevada no implica vulnerabilitat si el receptor és poc sensible o té capacitat adaptativa; ara aquesta combinació no és avaluable.",
            "limits": "Falten normals, receptors, llindars de resposta i validació local.",
        },
    )


def _core_06(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    biodiv = context["biodiversity"]
    metadata = context.get("biodiversity_metadata") or {}
    ecology = context.get("biodiversity_ecology_metadata") or {}
    records = int(metadata.get("records_normalized_after_clip") or _sum(biodiv, "nombre_registres"))
    cells = _knowledge_cells(context.get("biodiversity_knowledge") or {})
    latest_years = [item for item in cells["latest_years"] if item is not None]
    profile = {
        "records_normalized": records,
        "taxonomic_groups_with_records": len([row for row in biodiv if _float(row.get("nombre_registres")) > 0]),
        "knowledge_grid_1km": {
            "cells": cells["count"],
            "cells_with_records": cells["with_records"],
            "cells_without_records": cells["without_records"],
            "prospecting_cells": int(ecology.get("counts", {}).get("prospecting_cells") or cells["prospecting"]),
            "latest_year_range": [min(latest_years), max(latest_years)] if latest_years else None,
        },
        "gbif_pagination": metadata.get("gbif_pagination"),
        "meaning": "cobertura del coneixement; no biodiversitat real",
    }
    gbif = metadata.get("gbif_pagination") or {}
    dimensions = _dimensions(
        completeness=("limitada", f"GBIF va descarregar {gbif.get('downloaded_records')} de {gbif.get('total_matches')} coincidències i iNaturalist sí va completar la consulta."),
        freshness=("limitada", "Hi ha registres recents i històrics; l’antiguitat es conserva i no implica presència actual."),
        coverage=("limitada", f"{cells['with_records']} de {cells['count']} cel·les d’1 km tenen almenys un registre públic."),
        resolution=("adequada", "Les ocurrències es normalitzen com a punts i només s’exposen agregades a 1 km."),
        qa=("limitada", "Filtre espacial i taxonòmic aplicat, però persisteixen coordenades, identificacions i registres dubtosos."),
        representativeness=("insuficient", "Les fonts oportunistes no representen un mostreig comparable d’espècies o abundància."),
        bias=("insuficient", "Esforç, accessibilitat, grup taxonòmic i estació introdueixen biaix no corregit."),
        validation=("insuficient", "No hi ha inventari de camp homogeni ni llista de referència per estimar completesa biològica."),
    )
    return _result(
        context, "CORE_06", kind="knowledge_profile",
        primary=f"{_ca(records, 0)} registres · {cells['with_records']}/{cells['count']} cel·les amb dades",
        category="coneixement públic esbiaixat", status="PARCIAL", dimensions=dimensions,
        sources=("gbif_occurrences", "inaturalist_observations"), absent=("standardized_field_inventory", "BDBC"),
        calculation="Descriu volum, distribució en quadrícula d’1 km, actualitat, cobertura taxonòmica, truncament i buits; no agrega aquests camps.",
        limitations=("Pocs registres no signifiquen baixa biodiversitat.", "La consulta GBIF arriba al sostre de seguretat de 10.000 registres."),
        impact="Orienta prospecció i mostra on la informació és insuficient sense convertir cites en estat biològic.",
        interpretation_short="Mesura on i quant s’ha documentat; no mesura riquesa, abundància o absència reals.",
        profile=profile,
        guide={
            "measure": "La quantitat, distribució espacial, actualitat i biaixos de la informació pública de biodiversitat.",
            "basis": "Registres normalitzats de GBIF i iNaturalist, agregats en cel·les d’1 km per protegir localitzacions.",
            "calculation": "Perfil de registres, grups, cel·les amb/sense dades, antiguitat i completesa de consulta. No hi ha puntuació de biodiversitat.",
            "interpretation": "Una cobertura alta significa més informació disponible. No significa més biodiversitat, millor estat ni absència real en cel·les buides.",
            "limits": "GBIF truncat al sostre de seguretat, esforç oportunista, biaix espacial/taxonòmic i manca d’inventari comparable.",
        },
    )


def _core_07(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    values = {row.get("indicator"): _float(row.get("value")) for row in context["pressure"]}
    km = values.get("osm_path_track_road_km", 0.0)
    density = values.get("osm_path_track_road_density", 0.0)
    points = int(values.get("osm_recreational_point_features", 0.0))
    area = _study_area_ha(context)
    profile = {
        "mapped_network_km": round(km, 2),
        "mapped_network_density_km_km2": round(density, 3),
        "mapped_use_points": points,
        "points_per_1000ha": round(points / area * 1000, 2) if area else None,
        "actual_use_intensity": "NO AVALUABLE",
        "ecological_pressure": "NO AVALUABLE",
    }
    dimensions = _dimensions(
        completeness=("adequada", "Xarxa i punts OSM previstos al perfil estan disponibles."),
        freshness=("limitada", "OSM és una base viva sense data d’observació homogènia per element."),
        coverage=("adequada", "Consulta i retall aplicats a tot l’àmbit."),
        resolution=("adequada", "Geometries lineals i puntuals adequades per descriure accessibilitat cartografiada."),
        qa=("limitada", "La completitud i classificació d’OSM depenen de contribucions comunitàries."),
        representativeness=("adequada", "Representa accessibilitat cartografiada; no intensitat d’ús."),
        bias=("limitada", "Pot haver-hi vies no cartografiades, duplicades o classificades de manera desigual."),
        validation=("insuficient", "No hi ha comptadors, afluència, incidències ni impactes de camp."),
    )
    return _result(
        context, "CORE_07", kind="direct_inventory",
        primary=f"{_ca(km, 1)} km · {_ca(density, 2)} km/km² · {points} punts",
        category="accessibilitat cartografiada", status="COMPLET", dimensions=dimensions,
        sources=("osm_public_use",), absent=("visitor_counts", "field_impact_observations"),
        calculation="Mostra km, km/km² i punts per 1.000 ha per separat; no els combina en una puntuació de pressió.",
        limitations=("OSM no mesura freqüentació, comportament ni impacte.", "Més accessibilitat també pot facilitar seguiment i resposta de gestió."),
        impact="Permet seleccionar trams i punts a contrastar abans d’afirmar pressió humana.",
        interpretation_short="Quantifica accés potencial cartografiat; la pressió real continua sense mesurar.",
        profile=profile,
        guide={
            "measure": "La xarxa d’accés i els punts d’ús potencial cartografiats dins l’àmbit.",
            "basis": "Vies, camins, pistes i punts d’ús públic d’OpenStreetMap, retallats a Alinyà.",
            "calculation": "Longitud total, densitat per km² i punts per 1.000 ha, sense agregació 0–100.",
            "interpretation": "Més xarxa indica més accessibilitat potencial. No demostra afluència, pressió, conflicte, impacte o capacitat de càrrega.",
            "limits": "Falten intensitat, estacionalitat, incidències, comptadors i contrast de camp.",
        },
    )


def _core_08(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    natural = _cover_pct(context["land_cover"], ("bosc", "boscos", "matollar", "prats", "herbassars", "roquissars", "aigua"))
    connector_ha = _sum((row for row in context["connectivity"] if "principals" in str(row.get("layer_id"))), "area_ha")
    area = _study_area_ha(context)
    pilot = context.get("biodiversity_pilot_metadata") or {}
    profile = {
        "structural_level": {
            "natural_or_seminatural_cover_pct": round(natural, 2),
            "main_connector_area_ha": round(connector_ha, 2),
            "main_connector_share_pct": round(connector_ha / area * 100, 2) if area else None,
            "official_connectivity_units": int(pilot.get("counts", {}).get("sectors") or 0),
        },
        "functional_level": {"status": "NO AVALUABLE", "missing": ["receptor o gremi", "distància de dispersió", "resistències", "validació de passos"]},
        "osm_role": "context separat; no s’inverteix CORE_07 ni s’assumeix que tota via sigui barrera",
    }
    dimensions = _dimensions(
        completeness=("limitada", "Hi ha cobertes i connectors oficials; falten nodes, resistències i receptors."),
        freshness=("adequada", "Capes estructurals amb versió documentada; no s’interpreten com a lectura diària."),
        coverage=("adequada", "Cobertes i índex oficial cobreixen l’àmbit."),
        resolution=("limitada", "La unitat oficial general no resol totes les barreres o passos locals."),
        qa=("adequada", "Geometries oficials retallades i mètriques d’àrea traçades."),
        representativeness=("limitada", "Representa continuïtat cartogràfica general, no moviment de cap espècie concreta."),
        bias=("limitada", "La proporció de coberta natural no incorpora qualitat de node ni resistència de matriu."),
        validation=("insuficient", "No hi ha telemetria, genètica, passos verificats ni model receptor-específic."),
    )
    return _result(
        context, "CORE_08", kind="two_level_profile",
        primary=f"{_ca(connector_ha, 1)} ha en connectors · funcionalitat NO AVALUABLE",
        category="continuïtat estructural", status="PARCIAL", dimensions=dimensions,
        sources=("connectivity_infraestructura_verda", "land_cover_icgc_cobertes_sol"),
        absent=("species_specific_resistance", "movement_validation"),
        calculation="Nivell 1: coberta natural i superfície de connectors oficials. Nivell 2 funcional queda buit fins definir receptor, nodes, distància i resistències.",
        limitations=("Continuïtat estructural no garanteix moviment o flux genètic.", "Les vies OSM no reben un signe fix de barrera."),
        impact="Diferencia on hi ha estructura contínua d’allò que encara no es pot afirmar sobre permeabilitat funcional.",
        interpretation_short="Mostra continuïtat general i connectors oficials; la connectivitat per espècie no és avaluable.",
        profile=profile,
        guide={
            "measure": "Continuïtat física general i, només si hi ha dades, connectivitat potencial per receptor.",
            "basis": "Cobertes ICGC i connectors oficials de la Infraestructura Verda; OSM queda com a context.",
            "calculation": "Perfil estructural d’àrea i continuïtat, sense mitjana ni invers de l’accessibilitat. El nivell funcional no es calcula sense paràmetres específics.",
            "interpretation": "Més continuïtat cartogràfica pot afavorir connexió, però no prova moviment, permeabilitat o connectivitat funcional.",
            "limits": "Falten receptors, nodes de qualitat, resistències, dispersió i validació.",
        },
    )


def _core_09(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    fire = context.get("current_fire") or {}
    summary = fire.get("summary") or {}
    pla = fire.get("pla_alfa") or {}
    burned = _metric(context["fires"], "gencat_burned_area_ha")
    access = _metric(context["pressure"], "osm_path_track_road_density")
    hydro_km = _sum(context["hydrology"], "length_km")
    profile = {
        "propagation_current": {
            "ecoradar_index_0_100": summary.get("mean_index_0_100"),
            "category": summary.get("predominant_category"),
            "valid_coverage_pct": summary.get("valid_coverage_pct"),
            "dominant_variables": summary.get("dominant_labels"),
            "data_at_utc": summary.get("latest_update_utc"),
            "pla_alfa_context": {"level": pla.get("level"), "label": pla.get("label"), "data_at_utc": pla.get("data_at_utc")},
        },
        "ecological_sensitivity": {"status": "NO AVALUABLE", "missing": ["trets i estat dels receptors", "sòl i erosió", "severitat esperable"]},
        "postfire_recovery": {"status": "NO AVALUABLE", "historic_burned_area_ha": burned, "missing": ["severitat", "NBR/NDVI temporal", "regeneració", "recurrència comparable"]},
        "operational_context": {"access_density_km_km2": access, "mapped_hydrology_km": round(hydro_km, 2), "role": "context; no és resiliència ecològica"},
    }
    dimensions = _dimensions(
        completeness=("limitada", "La propagació actual té entrades parcials; sensibilitat i recuperació no són avaluables."),
        freshness=("adequada", "Meteorologia, precipitació i Pla Alfa conserven data actual; NDMI/LST antics queden exclosos del perill actual."),
        coverage=("adequada", f"El perill actual declara {summary.get('valid_coverage_pct')} % vàlid i la superfície sense dada."),
        resolution=("limitada", "Malla de 100 m amb meteorologia puntual de Y4/CJ i capes estructurals més fines."),
        qa=("limitada", f"Qualitat/actualització efectiva del producte {summary.get('confidence_pct')} %; no s’anomena confiança ecològica."),
        representativeness=("limitada", "El perfil separa propagació, sensibilitat, recuperació i operativa; només la primera té lectura actual."),
        bias=("limitada", "Falten combustible mesurat, humitat actual i vent territorial per valls i carenes."),
        validation=("insuficient", "No hi ha validació del comportament o recuperació amb incendis observats locals."),
    )
    return _result(
        context, "CORE_09", kind="four_axis_profile",
        primary=f"Propagació actual {summary.get('predominant_category') or 'no disponible'} · recuperació NO AVALUABLE",
        category="perfil foc", status="PARCIAL", dimensions=dimensions,
        sources=("meteocat", "pla_alfa", "land_cover_icgc_cobertes_sol", "icgc_dem_mdt", "fires_burned_areas", "osm_public_use", "aca_hydrology"),
        absent=("fuel_structure_field_data", "postfire_severity_timeseries", "recovery_field_validation"),
        calculation="Quatre eixos no agregats: propagació potencial actual, sensibilitat ecològica, recuperació postincendi i context operatiu. Pla Alfa és context oficial independent.",
        limitations=("El perill actual no és probabilitat d’ignició ni predicció d’incendi.", "Camins, aigua i superfície cremada no sumen ni resten resiliència de manera lineal."),
        impact="Permet vigilar propagació actual sense confondre-la amb sensibilitat, capacitat d’extinció o recuperació ecològica.",
        interpretation_short="La propagació actual és avaluable parcialment; sensibilitat i recuperació necessiten dades pròpies.",
        profile=profile, source_date_utc=summary.get("latest_update_utc"),
        guide={
            "measure": "Separadament, propagació potencial actual, sensibilitat ecològica, recuperació postincendi i context operatiu.",
            "basis": "Perill EcoRadar actual i Pla Alfa; antecedents oficials; OSM i hidrologia només com a context operatiu.",
            "calculation": "Perfil de quatre eixos. No agrega bosc, pendent, camins, aigua ni superfície cremada en una única nota de resiliència.",
            "interpretation": "La categoria de propagació descriu condicions si hi hagués ignició. No és probabilitat, severitat ni capacitat ecològica de recuperar-se.",
            "limits": "Falten combustible de camp, sensibilitat dels receptors, severitat, trajectòria temporal i validació postincendi.",
        },
    )


def _core_10(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    hydro = context["hydrology"]
    courses = _sum((row for row in hydro if row.get("theme") in {"courses", "drainage_axes"}), "length_km")
    springs = int(sum(_float(row.get("feature_count")) for row in hydro if row.get("theme") == "springs"))
    area = _study_area_ha(context)
    density100 = courses / area * 100 if area else None
    profile = {
        "mapped_courses_and_drainage_km": round(courses, 2),
        "mapped_km_per_100ha": _round(density100, 3),
        "mapped_springs": springs,
        "mapped_springs_per_1000ha": round(springs / area * 1000, 2) if area else None,
        "mapped_ponds_lakes_wetlands": 0,
        "current_availability": "NO AVALUABLE",
        "flow_permanence_quality_function": "NO AVALUABLE",
    }
    dimensions = _dimensions(
        completeness=("adequada", "Cursos, drenatges, fonts i capes de basses/estanys/zones humides s’han consultat."),
        freshness=("adequada", "Inventari estructural amb data de consulta; no s’interpreta com a aigua disponible avui."),
        coverage=("adequada", "Geometries oficials retallades a tot l’àmbit."),
        resolution=("limitada", "La cartografia general pot ometre surgències o punts temporals locals."),
        qa=("adequada", "Longitud i recomptes derivats de geometries oficials normalitzades."),
        representativeness=("adequada", "Representa presència cartografiada, que és la dimensió declarada."),
        bias=("limitada", "La no presència a la capa no prova inexistència i no descriu temporalitat."),
        validation=("insuficient", "No hi ha cabal, permanència, qualitat, ribera ni ús faunístic verificats."),
    )
    return _result(
        context, "CORE_10", kind="direct_inventory",
        primary=f"{_ca(courses, 1)} km de xarxa · {springs} fonts cartografiades",
        category="presència cartografiada", status="COMPLET", dimensions=dimensions,
        sources=("aca_hydrology",), absent=("flow_and_permanence", "water_quality", "riparian_condition", "field_validation"),
        calculation="Mostra longitud, densitat i nombre de fonts per separat; no transforma presència en funcionalitat o disponibilitat.",
        limitations=("No informa de cabal, permanència, qualitat o estat de ribera.", "Zero basses o zones humides a la font retallada no prova absència al terreny."),
        impact="Dona una base d’inventari per planificar verificació hídrica sense afirmar funció actual.",
        interpretation_short="Descriu elements hídrics cartografiats; no diu si avui tenen aigua ni si funcionen ecològicament.",
        profile=profile,
        guide={
            "measure": "La presència i distribució d’elements hídrics oficialment cartografiats.",
            "basis": "Cursos ACA/CHE, eixos de drenatge i fonts oficials retallats a l’àmbit.",
            "calculation": "Quilòmetres, densitat per 100 ha i nombre de fonts; cap mitjana o puntuació.",
            "interpretation": "Més elements significa més presència cartografiada. No significa més aigua disponible, millor qualitat, cabal, permanència o funcionalitat.",
            "limits": "Falten cabal, temporalitat, qualitat, estat de ribera, punts locals i validació de camp.",
        },
    )


def _core_11(context: dict[str, Any], _: list[dict[str, Any]]) -> dict[str, Any]:
    gate = {
        "degradation_demonstrated": False,
        "reference_ecosystem_defined": False,
        "management_objective_defined": False,
        "intervention_benefit_vs_non_intervention_demonstrated": False,
        "feasibility_and_risk_assessed": False,
        "decision": "NO AVALUABLE",
    }
    dimensions = _dimensions(
        completeness=("insuficient", "Falten totes les entrades essencials de la porta de decisió."),
        freshness=("insuficient", "No hi ha estat ni tendència de degradació datats per sector."),
        coverage=("insuficient", "No hi ha sectors candidats delimitats amb evidència de degradació."),
        resolution=("insuficient", "No existeix una unitat de restauració vinculada a objectiu i referència."),
        qa=("insuficient", "No hi ha protocol de diagnosi de degradació, benefici, viabilitat i risc."),
        representativeness=("insuficient", "Els altres CORE no substitueixen evidència directa de necessitat de restauració."),
        bias=("insuficient", "Agregar valors, vulnerabilitats o accessibilitat induiria una prioritat sense mecanisme."),
        validation=("insuficient", "No hi ha validació de camp ni acord de l’objectiu de restauració."),
    )
    return _result(
        context, "CORE_11", kind="decision_gate", primary="NO AVALUABLE · falta diagnosi de degradació",
        category="porta de decisió", status="NO AVALUABLE", dimensions=dimensions,
        sources=(), absent=("degradation_evidence", "reference_ecosystem", "restoration_objective", "benefit_feasibility_risk"),
        calculation="Porta no compensatòria: degradació demostrada, referència/objectiu, benefici davant no-intervenció i viabilitat/risc. En fallar les entrades essencials, no calcula resultat.",
        limitations=("Responsabilitat HIC, vulnerabilitat o connectivitat no impliquen necessitat de restaurar.", "No es delimiten superfícies ni actuacions candidates."),
        impact="Impedeix recomanar restauració sense diagnosi i manté obertes protecció, seguiment i no-intervenció.",
        interpretation_short="No hi ha base per valorar potencial de restauració; cal demostrar degradació i definir referència i objectiu.",
        profile={"decision_gate": gate},
        guide={
            "measure": "Si existeix evidència suficient per decidir sobre una oportunitat de restauració en un sector concret.",
            "basis": "Degradació, referència, objectiu, benefici comparat amb no-intervenció, viabilitat i risc.",
            "calculation": "Porta de decisió sense compensació: si falten degradació o referència/objectiu, el resultat és NO AVALUABLE.",
            "interpretation": "NO AVALUABLE no significa que no calgui restaurar; significa que les dades actuals no permeten justificar l’acció.",
            "limits": "Falten evidència de degradació, trajectòria, referència, objectiu, benefici, viabilitat i camp.",
        },
    )


def _core_12(context: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    hic = next((item for item in results if item["code"] == "CORE_02"), {})
    fire = next((item for item in results if item["code"] == "CORE_09"), {})
    matrix = [
        {
            "sector": "Polígons HIC i HIC prioritaris cartografiats",
            "alternative": "Protegir i aplicar no-deteriorament abans d’actuar",
            "result": "P1",
            "decisive_factors": ["responsabilitat HIC cartografiada", "possible irreversibilitat", "estat local no verificat"],
            "vetoes": ["cap actuació transformadora sense comprovació d’hàbitat"],
            "confidence": hic.get("confidence"),
            "robustness": "robusta com a regla preventiva; el disseny local requereix camp",
        },
        {
            "sector": "29 cel·les d’1 km amb interès de prospecció documentat",
            "alternative": "Prospecció biològica dirigida",
            "result": "P2",
            "decisive_factors": ["coneixement públic escàs", "coincidència amb HIC o connector", "biaix d’esforç"],
            "vetoes": [],
            "confidence": "mitjana",
            "robustness": "estable com a prioritat de coneixement, no com a valor biològic",
        },
        {
            "sector": "Xarxa i punts d’accés cartografiats",
            "alternative": "Mesurar ús i impacte abans de regular",
            "result": "P2",
            "decisive_factors": ["124,8 km de xarxa", "18 punts", "freqüentació no disponible"],
            "vetoes": ["no inferir pressió real només des d’OSM"],
            "confidence": "mitjana",
            "robustness": "estable per al seguiment; regulació no ordenable sense intensitat i impacte",
        },
        {
            "sector": "Cursos, drenatges i fonts cartografiats",
            "alternative": "Verificar permanència, qualitat i funció",
            "result": "P2",
            "decisive_factors": ["presència hídrica cartografiada", "permanència desconeguda", "possible funció de refugi"],
            "vetoes": ["no intervenir ni divulgar punts sensibles sense verificació"],
            "confidence": "mitjana",
            "robustness": "estable com a verificació; actuació no ordenable sense camp",
        },
        {
            "sector": "Àrees amb perill EcoRadar actual moderat/alt",
            "alternative": "Vigilar canvis i preparar resposta segons Pla Alfa vigent",
            "result": "P2",
            "decisive_factors": [fire.get("primary_result"), "vent i estructura entre factors dominants", "cobertura vàlida explícita"],
            "vetoes": ["Pla Alfa es manté independent i preval com a context oficial"],
            "confidence": fire.get("confidence"),
            "robustness": "caduca amb la meteorologia i la següent instantània diària",
        },
        {
            "sector": "Àmbit complet",
            "alternative": "Restauració generalitzada",
            "result": "NO AVALUABLE",
            "decisive_factors": ["degradació no demostrada", "referència i objectiu absents", "benefici no comparat amb no-intervenció"],
            "vetoes": ["dada essencial absent", "risc de dany sobre HIC"],
            "confidence": "baixa",
            "robustness": "veto robust mentre faltin les entrades essencials",
        },
    ]
    profile = {
        "global_score": None,
        "decision_rule": "matriu sector × alternativa amb vetos i sense compensació",
        "rows": matrix,
        "dominance": "Cap alternativa d’actuació domina les altres perquè responen a sectors i objectius diferents.",
        "sensitivity": "Sense pesos aprovats pel gestor no es força una ordenació única.",
        "result": "SENSE PRIORITAT ÚNICA",
    }
    dimensions = _dimensions(
        completeness=("limitada", "La matriu pot prioritzar prudència i verificació, però no actuacions de restauració."),
        freshness=("limitada", "El bloc de foc caduca diàriament; els inventaris són estructurals."),
        coverage=("adequada", "Les unitats provenen de capes o quadrícules documentades, no de sectors inventats."),
        resolution=("limitada", "Les unitats de font encara no són unitats de gestió aprovades."),
        qa=("adequada", "Cada fila conserva font, tipus de resultat i veto explícit."),
        representativeness=("limitada", "La síntesi cobreix decisions compatibles amb les dades disponibles, no tot el pla de gestió."),
        bias=("limitada", "No hi ha preferències ni llindars aprovats per ordenar alternatives no dominades."),
        validation=("insuficient", "Falta acord del gestor sobre objectius, unitats i criteris de decisió."),
    )
    return _result(
        context, "CORE_12", kind="multicriteria_decision",
        primary="SENSE PRIORITAT ÚNICA · 1 P1, 4 P2 i 1 NO AVALUABLE",
        category="síntesi no compensatòria", status="PARCIAL", dimensions=dimensions,
        sources=tuple(sorted({source for item in results for source in item.get("sources_used", ())})),
        absent=("approved_management_units", "approved_objectives_and_preferences", "field_validation"),
        calculation="Matriu sector × alternativa amb restriccions i vetos. No calcula mitjana, no transforma els CORE en una sola escala i manté alternatives no dominades.",
        limitations=("P1/P2 són categories de decisió per fila, no puntuacions ecològiques.", "La síntesi s’ha de reexecutar amb cada snapshot i després d’aprovar unitats i objectius."),
        impact="Dona accions justificades i conflictes visibles sense fabricar una falsa prioritat territorial única.",
        interpretation_short="Hi ha una regla preventiva P1 i diverses verificacions P2; no existeix una única acció dominant per a tot Alinyà.",
        profile=profile,
        guide={
            "measure": "Quines alternatives són justificables en cada unitat documentada segons evidència, veto, urgència i incertesa.",
            "basis": "Resultats no agregats de CORE_01–11 i lectures del mateix snapshot; mai les antigues puntuacions com a substituts.",
            "calculation": "Matriu sector × alternativa, vetos i dominància. No hi ha score global, mitjana ni compensació entre dimensions.",
            "interpretation": "P1/P2/P3 s’apliquen a una alternativa i un sector concrets. SENSE PRIORITAT ÚNICA indica opcions no comparables o objectius que ha de decidir el gestor.",
            "limits": "Falten unitats de gestió, objectius, preferències i validació de camp aprovats.",
        },
    )


def _not_evaluable(context: dict[str, Any], code: str, reason: str, kind: str) -> dict[str, Any]:
    dimensions = _dimensions(**{
        key: ("insuficient", reason) for key in CONFIDENCE_KEYS
    })
    return _result(
        context, code, kind=kind, primary="NO AVALUABLE", category="sense dades suficients",
        status="NO AVALUABLE", dimensions=dimensions, sources=(), absent=("essential_data",),
        calculation="No es calcula perquè falta una entrada essencial.", limitations=(reason,),
        impact="No alimenta cap conclusió ecològica fins completar l’entrada.",
        interpretation_short=reason, profile={},
        guide={"measure": NAMES[code], "basis": "Dades no suficients.", "calculation": "No calculat.", "interpretation": "NO AVALUABLE.", "limits": reason},
    )


def _dimensions(**values: tuple[str, str]) -> dict[str, tuple[str, str]]:
    aliases = {"freshness": "vigencia", "coverage": "cobertura", "resolution": "resolucio", "representativeness": "representativitat", "bias": "biaix", "validation": "validacio", "completeness": "completesa"}
    normalized = {aliases.get(key, key): value for key, value in values.items()}
    missing = set(CONFIDENCE_KEYS) - set(normalized)
    if missing:
        raise ValueError(f"Missing confidence dimensions: {sorted(missing)}")
    return normalized


def _confidence(dimensions: dict[str, tuple[str, str]]) -> tuple[str, str]:
    ratings = Counter(value[0] for value in dimensions.values())
    if ratings["insuficient"] >= 3:
        level = "baixa"
    elif ratings["insuficient"] == 0 and ratings["limitada"] <= 1:
        level = "alta"
    else:
        level = "mitjana"
    constrained = [key for key, value in dimensions.items() if value[0] == "insuficient"]
    limited = [key for key, value in dimensions.items() if value[0] == "limitada"]
    if constrained:
        reason = f"Confiança {level}: dimensions insuficients — {', '.join(constrained)}."
    elif limited:
        reason = f"Confiança {level}: dimensions limitades — {', '.join(limited)}."
    else:
        reason = "Confiança alta: les vuit dimensions són adequades per a la dimensió exactament declarada."
    return level, reason


def _validate_result(result: dict[str, Any]) -> None:
    if result.get("value_0_100") is not None:
        raise ValueError(f"{result.get('code')} must not expose a Phase 2 synthetic 0-100 value")
    dimensions = result.get("confidence_dimensions") or {}
    if set(dimensions) != set(CONFIDENCE_KEYS):
        raise ValueError(f"{result.get('code')} has an incomplete confidence vector")


def _landscape_configuration(root: Path) -> dict[str, Any]:
    path = root / "processed" / "cobertes_sol.gpkg"
    if not path.exists():
        return {"status": "NO AVALUABLE", "reason": "No existeix la geometria de cobertes processada."}
    try:
        import geopandas as gpd

        frame = gpd.read_file(path, layer="cobertes_sol")
        if frame.empty or frame.crs is None:
            raise ValueError("empty or unreferenced land-cover layer")
        if frame.crs.to_epsg() != 25831:
            frame = frame.to_crs(25831)
        areas = frame.geometry.area / 10_000
        perimeters = frame.geometry.length / 1_000
        total = float(areas.sum())
        effective = float((areas * areas).sum() / total) if total else None
        largest_index = int(areas.idxmax())
        largest_name = str(frame.loc[largest_index, "tipus_coberta"])
        largest = float(areas.loc[largest_index])
        return {
            "status": "descriptor cartogràfic",
            "patch_count": int(len(frame)),
            "median_patch_ha": round(float(areas.median()), 3),
            "largest_patch_ha": round(largest, 2),
            "largest_patch_cover": largest_name,
            "largest_patch_share_pct": round(largest / total * 100, 2) if total else None,
            "effective_mesh_area_ha": round(effective, 2) if effective is not None else None,
            "edge_density_km_per_km2": round(float(perimeters.sum()) / (total / 100), 2) if total else None,
            "interior_area": "NO AVALUABLE · no s’ha aprovat una distància de vora ni un receptor",
            "ecotone_function": "NO AVALUABLE · la vora cartogràfica no és un ecotò funcional validat",
            "scale_note": "Taques de la classificació ICGC; mètriques sensibles al gra i a la unitat cartogràfica.",
        }
    except (ImportError, OSError, ValueError) as exc:
        return {"status": "NO AVALUABLE", "reason": f"No s’han pogut calcular mètriques espacials: {exc}"}


def _knowledge_cells(payload: dict[str, Any]) -> dict[str, Any]:
    features = payload.get("features", []) if isinstance(payload, dict) else []
    records = [int((feature.get("properties") or {}).get("records") or 0) for feature in features]
    years = [(feature.get("properties") or {}).get("latest_year") for feature in features]
    return {
        "count": len(features),
        "with_records": sum(value > 0 for value in records),
        "without_records": sum(value == 0 for value in records),
        "prospecting": sum(bool((feature.get("properties") or {}).get("prospecting_interest")) for feature in features),
        "latest_years": years,
    }


def _registry_extract(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    return {key: item.get(key) for key in ("value", "data_at_utc", "period_start_utc", "period_end_utc", "temporal_kind", "spatial_support", "validity")}


def _study_area_ha(context: dict[str, Any]) -> float:
    metadata = context.get("study_area") or {}
    return _float(metadata.get("surface_ha") or metadata.get("area_ha") or metadata.get("study_area_surface_ha"))


def _cover_pct(rows: list[dict[str, str]], patterns: tuple[str, ...]) -> float:
    total = _sum(rows, "superficie_ha")
    selected = sum(_float(row.get("superficie_ha")) for row in rows if any(pattern in str(row.get("tipus_coberta", "")).lower() for pattern in patterns))
    return selected / total * 100 if total else 0.0


def _shannon(rows: list[dict[str, str]]) -> float:
    import math

    values = [_float(row.get("superficie_ha")) for row in rows]
    total = sum(values)
    return -sum((value / total) * math.log(value / total) for value in values if value > 0 and total > 0)


def _sum(rows: Any, field: str) -> float:
    return sum(_float(row.get(field)) for row in rows)


def _metric(rows: list[dict[str, str]], key: str) -> float | None:
    for row in rows:
        if row.get("metric") == key or row.get("indicator") == key:
            return _float(row.get("value"))
    return None


def _nested(payload: Any, *keys: str) -> Any:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _float(value: Any) -> float:
    try:
        return float(str(value).replace(",", ".")) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _round(value: Any, digits: int) -> float | None:
    return round(float(value), digits) if value is not None else None


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "si", "sí"}


def _ca(value: Any, digits: int) -> str:
    if value is None:
        return "no disponible"
    text = f"{float(value):,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text


def _date_ca(value: str) -> str:
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.strftime("%d/%m/%Y")
    except ValueError:
        return value
