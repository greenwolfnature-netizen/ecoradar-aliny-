"""EcoRadar Core indicator synthesis.

The Core layer consumes already prepared connector outputs and produces a first
separated diagnostic table. It never downloads data and never fills missing
values with invented estimates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

from ecoradar.sources.availability import ensure_mandatory_preflight


CORE_OUTPUTS = {
    "csv": "indicators/ecoradar_core.csv",
    "json": "indicators/ecoradar_core.json",
    "report": "reports/ecoradar_core_resum.md",
    "maps_dir": "maps/ecoradar_core",
    "metadata": "metadata/ecoradar_core_metadata.json",
}


@dataclass(frozen=True)
class CoreIndicatorResult:
    """One EcoRadar Core result row."""

    code: str
    name: str
    status: str
    raw_value: str
    normalized_value: float | None
    category: str
    confidence: str
    sources_used: tuple[str, ...]
    limitations: tuple[str, ...]
    preliminary_recommendation: str
    brief_interpretation: str
    missing_data: tuple[str, ...]
    map_output: str


def generate_core_outputs(project_root: str | Path = "projectes/Alinya") -> dict[str, Any]:
    """Generate EcoRadar Core outputs for a prepared project."""

    root = Path(project_root)
    ensure_mandatory_preflight(root)
    indicators_dir = root / "indicators"
    reports_dir = root / "reports"
    maps_dir = root / "maps" / "ecoradar_core"
    metadata_dir = root / "metadata"
    for directory in (indicators_dir, reports_dir, maps_dir, metadata_dir):
        directory.mkdir(parents=True, exist_ok=True)

    context = _load_context(root)
    results = _build_core_results(context, maps_dir)

    csv_path = root / CORE_OUTPUTS["csv"]
    json_path = root / CORE_OUTPUTS["json"]
    report_path = root / CORE_OUTPUTS["report"]
    metadata_path = root / CORE_OUTPUTS["metadata"]

    _write_csv(csv_path, results)
    _write_json(json_path, results)
    basic_maps = _write_basic_maps(root, maps_dir)
    _write_maps_manifest(maps_dir, results, basic_maps)
    _write_report(report_path, results)
    metadata = _write_metadata(metadata_path, root, context, results, basic_maps)

    return {
        "csv": str(csv_path),
        "json": str(json_path),
        "report": str(report_path),
        "maps_dir": str(maps_dir),
        "basic_maps": [str(path) for path in basic_maps],
        "metadata": str(metadata_path),
        "indicator_count": len(results),
        "status_counts": _status_counts(results),
        "metadata_payload": metadata,
    }


def _load_context(root: Path) -> dict[str, Any]:
    indicators_dir = root / "indicators"
    metadata_dir = root / "metadata"
    processed_dir = root / "processed"

    context: dict[str, Any] = {
        "root": root,
        "study_area": _read_json(metadata_dir / "study_area_metadata.json"),
        "tele": _read_json(metadata_dir / "teledeteccio_metadata.json"),
        "ecoradar_01": _read_csv_optional(indicators_dir / "ecoradar_01_resum.csv"),
        "land_cover": _read_csv_optional(indicators_dir / "cobertes_sol_resum.csv"),
        "habitats": _read_csv_optional(indicators_dir / "habitats_resum.csv"),
        "biodiv_summary": _read_csv_optional(indicators_dir / "biodiversitat_resum.csv"),
        "recreational_pressure": _read_csv_optional(indicators_dir / "recreational_pressure_resum.csv"),
        "biodiv_path": processed_dir / "biodiversitat.gpkg",
        "human_pressure_path": processed_dir / "recreational_pressure.gpkg",
    }
    return context


def _build_core_results(context: dict[str, Any], maps_dir: Path) -> list[CoreIndicatorResult]:
    basic = _basic_values(context.get("ecoradar_01"))
    land_cover = context.get("land_cover")
    habitats = context.get("habitats")
    biodiv = context.get("biodiv_summary")

    results = [
        _mosaic_result(basic, land_cover, maps_dir),
        _habitat_value_result(basic, habitats, maps_dir),
        _vegetation_state_result(context, maps_dir),
        _climate_refugia_result(basic, context, maps_dir),
        _climate_vulnerability_result(basic, context, maps_dir),
        _known_biodiversity_result(basic, biodiv, maps_dir),
        _human_pressure_result(context, maps_dir),
        _connectivity_result(basic, context, maps_dir),
        _fire_resilience_result(basic, context, maps_dir),
        _water_functionality_result(context, maps_dir),
        _restoration_potential_result(context, maps_dir),
        _management_priority_result(context, maps_dir),
    ]
    return results


def _mosaic_result(basic: dict[str, Any], land_cover: pd.DataFrame | None, maps_dir: Path) -> CoreIndicatorResult:
    if land_cover is None or land_cover.empty:
        return _unavailable("CORE_01", "Mosaic del paisatge", ("cobertes del sol",), maps_dir)

    cover_types = _num(basic.get("nombre_tipus_cobertes"))
    forest = _num(basic.get("percentatge_coberta_forestal"))
    grass = _num(basic.get("percentatge_prats_pastures_herbassars"))
    agricultural = _num(basic.get("percentatge_agricola"))
    artificial = _num(basic.get("percentatge_urba_artificial"))
    components = [
        _clamp((cover_types or 0) / 12 * 100),
        _balance_score(forest, optimum_low=35, optimum_high=70),
        _clamp((grass or 0) / 15 * 100),
        _clamp((agricultural or 0) / 15 * 100),
        _inverse_pressure(artificial, max_bad=10),
    ]
    value = round(mean(components), 2)
    return _result(
        "CORE_01",
        "Mosaic del paisatge",
        "parcial",
        f"cobertes={int(cover_types or 0)}; forestal={forest}%; prats={grass}%; agricola={agricultural}%; artificial={artificial}%",
        value,
        "mitjana",
        ("cobertes_sol_resum.csv",),
        ("No hi ha encara calcul espacial de continuitat forestal.",),
        "Validar discontinuïtats reals i conservar espais oberts existents.",
        "Mosaic estimat amb classes de coberta i percentatges basics; la continuitat espacial queda pendent.",
        ("continuïtat forestal espacial",),
        maps_dir,
    )


def _habitat_value_result(basic: dict[str, Any], habitats: pd.DataFrame | None, maps_dir: Path) -> CoreIndicatorResult:
    if habitats is None or habitats.empty:
        return _unavailable("CORE_02", "Valor d'habitats", ("habitats",), maps_dir)

    area_ha = _num(basic.get("superficie_total")) or 0
    habitat_count = _num(basic.get("nombre_habitats")) or 0
    hic_ha = _num(basic.get("superficie_hic")) or 0
    hic_pct = (hic_ha / area_ha * 100) if area_ha else 0
    priority_ha = float(habitats.loc[habitats["es_prioritari"].astype(str).str.lower().eq("true"), "superficie_ha"].sum())
    components = [
        _clamp(habitat_count / 40 * 100),
        _clamp(hic_pct / 60 * 100),
        _clamp((priority_ha / area_ha * 100) / 15 * 100) if area_ha else 0,
    ]
    value = round(mean(components), 2)
    top = habitats.sort_values("superficie_ha", ascending=False).head(3)
    top_names = "; ".join(str(name) for name in top["codi_habitat"].tolist())
    return _result(
        "CORE_02",
        "Valor d'habitats",
        "parcial",
        f"habitats={int(habitat_count)}; HIC={round(hic_ha, 2)} ha; prioritaris={round(priority_ha, 2)} ha",
        value,
        "mitjana",
        ("habitats_resum.csv",),
        ("Habitats sensibles encara no estan classificats en una llista EcoRadar validada.",),
        "Revisar els habitats HIC i prioritaris abans de qualsevol actuacio.",
        f"Valor calculat amb riquesa d'habitats, HIC i HIC prioritaris. Habitats principals: {top_names}.",
        ("classificacio d'habitats sensibles", "zones de mes valor espacialitzades"),
        maps_dir,
    )


def _vegetation_state_result(context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    return _blocked_copernicus(
        "CORE_03",
        "Estat de la vegetacio",
        ("NDVI", "NDMI", "NDWI", "anomalia temporal"),
        maps_dir,
    )


def _climate_refugia_result(basic: dict[str, Any], context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    forest = _num(basic.get("percentatge_coberta_forestal"))
    if forest is None:
        return _unavailable("CORE_04", "Refugis climatics", ("cobertura forestal", "LST", "NDMI", "aigua", "orientacio"), maps_dir)
    value = round(_clamp(forest), 2)
    return _result(
        "CORE_04",
        "Refugis climatics",
        "parcial",
        f"cobertura forestal={forest}%",
        value,
        "baixa",
        ("cobertes_sol_resum.csv",),
        ("Falten LST, NDMI, orientacio i proximitat a aigua; no es poden delimitar refugis.",),
        "No prioritzar refugis climatics sense teledeteccio, topografia i hidrologia.",
        "Només es pot usar la cobertura forestal com a senyal parcial; el mapa de refugis queda pendent.",
        ("LST", "NDMI", "orientacio nord/obaga", "proximitat a cursos o punts d'aigua"),
        maps_dir,
    )


def _climate_vulnerability_result(basic: dict[str, Any], context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    artificial = _num(basic.get("percentatge_urba_artificial"))
    forest = _num(basic.get("percentatge_coberta_forestal"))
    if artificial is None or forest is None:
        return _unavailable("CORE_05", "Vulnerabilitat climatica", ("LST", "NDMI", "pendent", "aigua", "coberta vegetal"), maps_dir)
    raw_proxy = round(100 - _balance_score(forest, 35, 85) + min(20, artificial * 2), 2)
    value = _clamp(raw_proxy)
    return _result(
        "CORE_05",
        "Vulnerabilitat climatica",
        "parcial",
        f"proxy disponible: forestal={forest}%; artificial={artificial}%",
        value,
        "baixa",
        ("cobertes_sol_resum.csv",),
        ("Falten LST, NDMI, orientacio, pendent i manca d'aigua; el valor es un proxy incomplet.",),
        "Esperar teledeteccio, DEM i hidrologia abans de prioritzar restauracio climatica.",
        "Vulnerabilitat només aproximada amb cobertura; no hi ha mapa de zones vulnerables.",
        ("LST alta", "NDMI baix", "orientacio sud", "pendent", "manca d'aigua"),
        maps_dir,
    )


def _known_biodiversity_result(basic: dict[str, Any], biodiv: pd.DataFrame | None, maps_dir: Path) -> CoreIndicatorResult:
    records = _num(basic.get("nombre_registres_biodiversitat"))
    species = _num(basic.get("nombre_especies_registrades"))
    recent = _num(basic.get("nombre_registres_recents"))
    if records is None or species is None:
        return _unavailable("CORE_06", "Biodiversitat coneguda", ("registres biodiversitat",), maps_dir)
    recent_share = (recent / records * 100) if records else 0
    value = round(mean([_clamp(species / 500 * 100), _clamp(recent_share)]), 2)
    underrepresented = _underrepresented_groups(biodiv)
    return _result(
        "CORE_06",
        "Biodiversitat coneguda",
        "parcial",
        f"registres={int(records)}; especies={int(species)}; recents={int(recent or 0)}",
        value,
        "mitjana",
        ("biodiversitat.gpkg", "biodiversitat_resum.csv"),
        ("No hi ha encara llistes d'especies indicadores, protegides o invasores creuades.",),
        "Validar grups infrarepresentats amb treball de camp i llistes de referencia.",
        f"Biodiversitat coneguda basada en cites publiques; grups infrarepresentats o febles: {underrepresented}.",
        ("especies indicadores", "especies protegides/interes", "buit espacial d'informacio"),
        maps_dir,
    )


def _human_pressure_result(context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    pressure = context.get("recreational_pressure")
    pressure_path = context.get("human_pressure_path")
    if pressure is not None and not pressure.empty and pressure_path is not None and Path(pressure_path).exists():
        values = _indicator_values(pressure)
        density = _num(values.get("osm_path_track_road_density"))
        points = _num(values.get("osm_recreational_point_features"))
        area_ha = _num(_basic_values(context.get("ecoradar_01")).get("superficie_total")) or 0
        points_per_1000ha = (points / area_ha * 1000) if points is not None and area_ha else 0
        components = [
            _clamp((density or 0) / 5 * 100),
            _clamp(points_per_1000ha / 10 * 100),
        ]
        value = round(mean(components), 2)
        return _result(
            "CORE_07",
            "Pressio humana i us public",
            "parcial",
            f"densitat camins/pistes={density} km/km2; punts us public={int(points or 0)}",
            value,
            "baixa",
            ("recreational_pressure.gpkg", "recreational_pressure_resum.csv"),
            (
                "OSM descriu infraestructura cartografiada, no intensitat real de visitants.",
                "Strava, comptadors, dades de gestors i observacions de camp encara no estan incorporats.",
            ),
            "Validar sobre el terreny els accessos, aparcaments i camins principals abans d'interpretar pressio real.",
            "Pressio humana estimada parcialment amb xarxa OSM i punts d'us public; no representa nombre de visitants.",
            ("heatmap autoritzat", "comptadors", "dades de gestors", "observacions de camp"),
            maps_dir,
        )
    return _result(
        "CORE_07",
        "Pressio humana i us public",
        "no disponible",
        "no disponible",
        None,
        "baixa",
        (),
        ("Connector OSM de pressio humana encara no implementat/executat.", "Strava segueix bloquejat per ingesta automatica."),
        "Implementar primer el connector OSM-only de camins, accessos i aparcaments.",
        "No es pot valorar pressio humana amb les dades actuals.",
        ("densitat de camins", "aparcaments", "refugis/miradors", "zones recreatives", "heatmap autoritzat"),
        maps_dir,
    )


def _connectivity_result(basic: dict[str, Any], context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    forest = _num(basic.get("percentatge_coberta_forestal"))
    grass = _num(basic.get("percentatge_prats_pastures_herbassars"))
    if forest is None or grass is None:
        return _unavailable("CORE_08", "Connectivitat ecologica", ("cobertes", "habitats", "barreres"), maps_dir)
    value = round(mean([_balance_score(forest, 35, 80), _clamp(grass / 15 * 100)]), 2)
    return _result(
        "CORE_08",
        "Connectivitat ecologica",
        "parcial",
        f"forestal={forest}%; prats={grass}%",
        value,
        "baixa",
        ("cobertes_sol_resum.csv", "habitats_resum.csv"),
        ("Falten barreres, riberes i model espacial de corredors.",),
        "No definir corredors fins incorporar barreres i xarxa hidrica.",
        "Connectivitat aproximada només amb cobertes; corredors i barreres principals pendents.",
        ("barreres", "xarxa de riberes", "infraestructures", "corredors potencials"),
        maps_dir,
    )


def _fire_resilience_result(basic: dict[str, Any], context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    forest = _num(basic.get("percentatge_coberta_forestal"))
    grass = _num(basic.get("percentatge_prats_pastures_herbassars"))
    agricultural = _num(basic.get("percentatge_agricola"))
    if forest is None:
        return _unavailable("CORE_09", "Resiliencia al foc", ("cobertes", "pendent", "NDMI", "LST", "accessos", "aigua"), maps_dir)
    protective = _clamp(((grass or 0) + (agricultural or 0)) / 20 * 100)
    continuity_penalty = _clamp(forest)
    value = round(_clamp((protective * 0.6) + ((100 - continuity_penalty) * 0.4)), 2)
    return _result(
        "CORE_09",
        "Resiliencia al foc",
        "parcial",
        f"forestal={forest}%; prats={grass}%; agricola={agricultural}%",
        value,
        "baixa",
        ("cobertes_sol_resum.csv",),
        ("Falten pendent, orientacio, NDMI, LST, accessos i punts d'aigua.",),
        "Analitzar mosaic i discontinuïtats abans de proposar actuacions forestals.",
        "Estimacio parcial basada en continuitat forestal aparent i mosaic obert; no es risc final.",
        ("pendent", "orientacio", "NDMI", "LST", "accessos", "punts d'aigua"),
        maps_dir,
    )


def _water_functionality_result(context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    return _result(
        "CORE_10",
        "Aigua i funcionalitat hidrica",
        "no disponible",
        "no disponible",
        None,
        "baixa",
        (),
        ("No hi ha connector hidrologic executat i NDWI no esta disponible.",),
        "Implementar connector hidrologic oficial i executar NDWI quan Copernicus estigui disponible.",
        "No es pot valorar funcionalitat hidrica amb les dades actuals.",
        ("cursos fluvials", "basses", "fonts", "zones humides", "NDWI", "punts d'aigua de camp"),
        maps_dir,
    )


def _restoration_potential_result(context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    return _result(
        "CORE_11",
        "Potencial de restauracio",
        "no disponible",
        "no disponible",
        None,
        "baixa",
        (),
        ("Depen d'indicadors encara no disponibles: vegetacio, vulnerabilitat climatica, connectivitat robusta i pressio humana.",),
        "Esperar les capes de vegetacio, pressio humana, hidrologia i camp abans de proposar zones.",
        "No es pot calcular potencial de restauracio sense els indicadors base complets.",
        ("baixa qualitat de vegetacio", "habitats degradats", "baixa connectivitat", "pressio gestionable", "habitats font"),
        maps_dir,
    )


def _management_priority_result(context: dict[str, Any], maps_dir: Path) -> CoreIndicatorResult:
    return _result(
        "CORE_12",
        "Prioritat de gestio",
        "no disponible",
        "no disponible",
        None,
        "baixa",
        (),
        ("Indicador final de sintesi bloquejat fins tenir els Core previs amb prou confiança.",),
        "No generar top 10 zones prioritaries fins disposar de pressio humana, clima, foc, aigua i camp.",
        "No es calcula cap prioritat global per evitar una mitjana simplista.",
        ("refugis climatics", "vulnerabilitat", "pressio humana", "resiliencia al foc", "potencial de restauracio"),
        maps_dir,
    )


def _blocked_copernicus(code: str, name: str, missing: tuple[str, ...], maps_dir: Path) -> CoreIndicatorResult:
    return _result(
        code,
        name,
        "no disponible",
        "no disponible",
        None,
        "baixa",
        ("teledeteccio_metadata.json",),
        ("Copernicus esta bloquejat per manca de credencials i no hi ha rasters NDVI/NDMI/NDWI/LST.",),
        "Configurar credencials Copernicus i generar rasters abans de valorar aquest indicador.",
        "No es pot calcular sense teledeteccio real.",
        missing,
        maps_dir,
    )


def _unavailable(code: str, name: str, missing: tuple[str, ...], maps_dir: Path) -> CoreIndicatorResult:
    return _result(
        code,
        name,
        "no disponible",
        "no disponible",
        None,
        "baixa",
        (),
        ("Falten les dades requerides per calcular l'indicador.",),
        "Generar o verificar les fonts requerides abans de calcular.",
        "No disponible amb les dades actuals.",
        missing,
        maps_dir,
    )


def _result(
    code: str,
    name: str,
    status: str,
    raw_value: str,
    normalized_value: float | None,
    confidence: str,
    sources_used: tuple[str, ...],
    limitations: tuple[str, ...],
    recommendation: str,
    interpretation: str,
    missing_data: tuple[str, ...],
    maps_dir: Path,
) -> CoreIndicatorResult:
    return CoreIndicatorResult(
        code=code,
        name=name,
        status=status,
        raw_value=raw_value,
        normalized_value=normalized_value,
        category=_category(normalized_value) if normalized_value is not None else "no disponible",
        confidence=confidence,
        sources_used=sources_used,
        limitations=limitations,
        preliminary_recommendation=recommendation,
        brief_interpretation=interpretation,
        missing_data=missing_data,
        map_output=str(maps_dir / f"{code.lower()}.md"),
    )


def _write_csv(path: Path, results: list[CoreIndicatorResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for result in results:
            row = asdict(result)
            for key in ("sources_used", "limitations", "missing_data"):
                row[key] = "; ".join(row[key])
            writer.writerow(row)


def _write_json(path: Path, results: list[CoreIndicatorResult]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "indicators": [asdict(result) for result in results],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_basic_maps(root: Path, maps_dir: Path) -> list[Path]:
    """Generate simple map layers from already processed data."""

    try:
        import geopandas as gpd
    except ImportError:
        return []

    study_area_path = root / "processed" / "study_area.gpkg"
    land_cover_path = root / "processed" / "cobertes_sol.gpkg"
    habitats_path = root / "processed" / "habitats.gpkg"
    biodiversity_path = root / "processed" / "biodiversitat.gpkg"
    recreational_path = root / "processed" / "recreational_pressure.gpkg"

    written: list[Path] = []
    study_area = gpd.read_file(study_area_path) if study_area_path.exists() else None

    if study_area is not None and not study_area.empty:
        path = maps_dir / "study_area.geojson"
        study_area.to_file(path, driver="GeoJSON")
        written.append(path)

    if land_cover_path.exists():
        land_cover = gpd.read_file(land_cover_path)
        if not land_cover.empty:
            path = maps_dir / "cobertes_sol.geojson"
            land_cover[["tipus_coberta", "geometry"]].to_file(path, driver="GeoJSON")
            written.append(path)

    if habitats_path.exists():
        habitats = gpd.read_file(habitats_path)
        if not habitats.empty:
            columns = [column for column in ("COD_CORINE", "CORINE_CA", "COD_HIC", "HIC_PRIOR", "geometry") if column in habitats.columns]
            path = maps_dir / "habitats_hic.geojson"
            habitats[columns].to_file(path, driver="GeoJSON")
            written.append(path)

    if biodiversity_path.exists():
        biodiversity = gpd.read_file(biodiversity_path)
        if not biodiversity.empty:
            columns = [column for column in ("scientificName", "commonName", "taxonGroup", "eventDate", "source", "recordStatus", "geometry") if column in biodiversity.columns]
            path = maps_dir / "biodiversitat_registres.geojson"
            biodiversity[columns].to_file(path, driver="GeoJSON")
            written.append(path)

    if recreational_path.exists():
        try:
            recreational_lines = gpd.read_file(recreational_path, layer="osm_paths_tracks_roads")
            if not recreational_lines.empty:
                columns = [column for column in ("highway", "surface", "access", "bicycle", "foot", "length_km", "geometry") if column in recreational_lines.columns]
                path = maps_dir / "pressio_humana_osm_camins.geojson"
                recreational_lines[columns].to_file(path, driver="GeoJSON")
                written.append(path)
        except Exception:
            pass
        try:
            recreational_points = gpd.read_file(recreational_path, layer="osm_recreational_points")
            if not recreational_points.empty:
                columns = [column for column in ("name", "amenity", "tourism", "leisure", "highway", "geometry") if column in recreational_points.columns]
                path = maps_dir / "pressio_humana_osm_punts.geojson"
                recreational_points[columns].to_file(path, driver="GeoJSON")
                written.append(path)
        except Exception:
            pass

    return written


def _write_maps_manifest(maps_dir: Path, results: list[CoreIndicatorResult], basic_maps: list[Path]) -> None:
    lines = [
        "# EcoRadar Core Maps",
        "",
        "Aquesta carpeta conte mapes basics de comprovacio i reserva les sortides cartografiques dels 12 indicadors Core.",
        "Els mapes d'indicador derivats es generaran quan les dades espacials requerides estiguin disponibles.",
        "",
        "## Mapes Basics Generats",
        "",
    ]
    if basic_maps:
        for path in basic_maps:
            lines.append(f"- `{path.name}`")
    else:
        lines.append("- No s'ha generat cap mapa basic.")
    lines.extend([
        "",
        "## Mapes D'Indicador",
        "",
        "| Indicador | Estat | Fitxer previst |",
        "| --- | --- | --- |",
    ])
    for result in results:
        map_path = Path(result.map_output)
        lines.append(f"| {result.code} · {result.name} | {result.status} | `{map_path.name}` |")
        map_path.write_text(
            f"# {result.code} · {result.name}\n\n"
            f"Estat: `{result.status}`\n\n"
            f"Valor normalitzat: `{result.normalized_value if result.normalized_value is not None else 'no disponible'}`\n\n"
            f"Aquest fitxer es un placeholder documental. El mapa derivat es generara quan les dades espacials requerides estiguin disponibles.\n",
            encoding="utf-8",
        )
    (maps_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(path: Path, results: list[CoreIndicatorResult]) -> None:
    available = [result for result in results if result.normalized_value is not None]
    unavailable = [result for result in results if result.normalized_value is None]
    best = sorted(available, key=lambda item: item.normalized_value or -1, reverse=True)[:3]
    worst = sorted(available, key=lambda item: item.normalized_value or 101)[:3]
    partial = [result for result in results if result.status == "parcial"]

    lines = [
        "# EcoRadar Core · Resum Alinya",
        "",
        f"Generat: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        "",
        "## Resum General",
        "",
        "EcoRadar Core ha generat 12 indicadors mestres separats. Aquesta execucio usa nomes les dades ja implementades i no calcula una mitjana global.",
        f"Indicadors amb valor numeric: {len(available)}. Indicadors no disponibles: {len(unavailable)}.",
        "",
        "## Taula Dels 12 Indicadors",
        "",
        "| Codi | Indicador | Estat | Valor 0-100 | Categoria | Confiança |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for result in results:
        value = result.normalized_value if result.normalized_value is not None else "no disponible"
        lines.append(f"| {result.code} | {result.name} | {result.status} | {value} | {result.category} | {result.confidence} |")

    lines.extend(["", "## Indicadors Amb Millor Resultat", ""])
    if best:
        for result in best:
            lines.append(f"- `{result.code}` {result.name}: {result.normalized_value} ({result.category}). {result.brief_interpretation}")
    else:
        lines.append("- No hi ha indicadors calculables.")

    lines.extend(["", "## Indicadors Amb Pitjor Resultat", ""])
    if worst:
        for result in worst:
            lines.append(f"- `{result.code}` {result.name}: {result.normalized_value} ({result.category}).")
    else:
        lines.append("- No hi ha indicadors calculables.")

    lines.extend(["", "## Dades No Disponibles", ""])
    for result in unavailable:
        lines.append(f"- `{result.code}` {result.name}: falten {', '.join(result.missing_data)}.")

    lines.extend(["", "## Limitacions", ""])
    for result in results:
        for limitation in result.limitations:
            lines.append(f"- `{result.code}`: {limitation}")

    lines.extend(["", "## Primeres Zones Prioritaries", ""])
    lines.append("No es generen zones prioritaries espacials en aquesta execucio. Falten pressio humana, teledeteccio, hidrologia/topografia derivada i validacio de camp.")

    lines.extend(["", "## Recomanacions Preliminars", ""])
    for result in partial + unavailable:
        lines.append(f"- `{result.code}`: {result.preliminary_recommendation}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_metadata(
    path: Path,
    root: Path,
    context: dict[str, Any],
    results: list[CoreIndicatorResult],
    basic_maps: list[Path],
) -> dict[str, Any]:
    metadata = {
        "project": root.name,
        "run_name": "EcoRadar Core",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "input_files": {
            "study_area": str(root / "processed" / "study_area.gpkg"),
            "land_cover_summary": str(root / "indicators" / "cobertes_sol_resum.csv"),
            "habitats_summary": str(root / "indicators" / "habitats_resum.csv"),
            "biodiversity_summary": str(root / "indicators" / "biodiversitat_resum.csv"),
            "teledetection_metadata": str(root / "metadata" / "teledeteccio_metadata.json"),
        },
        "outputs": {key: str(root / value) for key, value in CORE_OUTPUTS.items() if key != "maps_dir"},
        "maps_dir": str(root / CORE_OUTPUTS["maps_dir"]),
        "basic_maps": [str(path) for path in basic_maps],
        "status_counts": _status_counts(results),
        "indicators": [
            {
                "code": result.code,
                "status": result.status,
                "confidence": result.confidence,
                "missing_data": result.missing_data,
            }
            for result in results
        ],
        "limitations": [
            "No es genera cap puntuacio global.",
            "Els indicadors parcials no substitueixen validacio de camp.",
            "Els mapes derivats Core son placeholders documentals fins que les dades espacials requerides estiguin disponibles.",
            "Teledeteccio, pressio humana, hidrologia i topografia derivada limiten diversos indicadors.",
        ],
    }
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


def _basic_values(frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {}
    return {str(row["indicador"]): row["valor"] for _, row in frame.iterrows()}


def _indicator_values(frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {}
    return {str(row["indicator"]): row["value"] for _, row in frame.iterrows()}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_optional(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def _status_counts(results: list[CoreIndicatorResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _balance_score(value: float | None, optimum_low: float, optimum_high: float) -> float:
    if value is None:
        return 0
    if optimum_low <= value <= optimum_high:
        return 100
    if value < optimum_low:
        return _clamp(value / optimum_low * 100)
    return _clamp(100 - ((value - optimum_high) / (100 - optimum_high) * 100))


def _inverse_pressure(value: float | None, max_bad: float) -> float:
    if value is None:
        return 0
    return _clamp(100 - (value / max_bad * 100))


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


def _underrepresented_groups(frame: pd.DataFrame | None) -> str:
    if frame is None or frame.empty:
        return "no disponible"
    low = frame.loc[frame["nombre_registres"] < 10, "grup_taxonomic"].tolist()
    return ", ".join(str(item) for item in low[:6]) if low else "cap grup evident amb menys de 10 registres"


if __name__ == "__main__":
    payload = generate_core_outputs()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
