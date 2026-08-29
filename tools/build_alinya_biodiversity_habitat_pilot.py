#!/usr/bin/env python3
"""Build the qualitative Biodiversity and habitats pilot for EcoRadar Alinyà.

This is an analysis step. It never exposes occurrence coordinates or taxon names,
and it deliberately produces qualitative rules rather than a synthetic score.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import box
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
PROCESSED = PROJECT / "processed"
OUTPUT = PROJECT / "indicators" / "biodiversity_habitat_pilot.geojson"
METADATA = PROJECT / "metadata" / "biodiversity_habitat_pilot_metadata.json"
ECOLOGY_OUTPUT = PROJECT / "indicators" / "biodiversity_ecological_elements.geojson"
SITUATIONS_OUTPUT = PROJECT / "indicators" / "biodiversity_ecological_situations.geojson"
KNOWLEDGE_OUTPUT = PROJECT / "indicators" / "biodiversity_knowledge_coverage.geojson"
ECOLOGY_METADATA = PROJECT / "metadata" / "biodiversity_ecology_metadata.json"


def safe_json_value(value):
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) else round(float(value), 4)
    if pd.isna(value):
        return None
    return value


def write_geojson(frame: gpd.GeoDataFrame, path: Path) -> None:
    """Write public-safe GeoJSON in WGS84 without internal dataframe indexes."""
    public = frame.to_crs(4326).copy()
    path.write_text(public.to_json(drop_id=True), encoding="utf-8")


def build_ecological_products() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, dict]:
    """Build manager-facing products from real ecological geometries.

    Internal BH units are deliberately not used or exported here. Occurrences are
    aggregated to a 1 km knowledge-coverage grid and never expose names or points.
    """
    habitats = read_layer("habitats.gpkg", "habitats").copy()
    biodiversity = read_layer("biodiversitat.gpkg", "biodiversitat").copy()
    connectors = read_layer("connectivitat.gpkg", "connectors_terrestres_principals").copy()
    connector_zones = read_layer("connectivitat.gpkg", "zones_connectors_infraestructura_verda").copy()
    fires = read_layer("incendis.gpkg", "incendis_historics").copy()
    study_units = read_layer("connectivitat.gpkg", "connectivitat_terrestre_index")
    study_geometry = unary_union(list(study_units.geometry))
    current_fire_context = json.loads((PROJECT / "indicators" / "current_fire_danger.json").read_text(encoding="utf-8"))
    fire_variables = current_fire_context.get("variables_today", {})
    ndmi_context = fire_variables.get("ndmi_dryness", {})
    lst_context = fire_variables.get("surface_temperature", {})

    elements_rows = []
    for row in habitats.itertuples():
        elements_rows.append({
            "element_type": "habitat",
            "element_code": str(row.COD_CORINE),
            "name": row.CORINE_CA,
            "hic_code": None if str(row.COD_HIC) in {"-", "None", "nan"} else str(row.COD_HIC),
            "hic_name": row.HIC_CA,
            "is_hic": bool(row.es_hic),
            "is_priority": bool(row.es_prioritari),
            "area_ha": round(float(row.superficie_ha), 4),
            "relevance": (
                "Hàbitat d’interès comunitari prioritari cartografiat."
                if row.es_prioritari else
                "Hàbitat d’interès comunitari cartografiat."
                if row.es_hic else
                "Tipologia d’hàbitat cartografiada; la cartografia no determina per si sola l’estat de conservació."
            ),
            "geometry": row.geometry,
        })
    for row in pd.concat([connectors, connector_zones], ignore_index=True).itertuples():
        connector_name = getattr(row, "espais", None) or "Zona connectora d’infraestructura verda"
        elements_rows.append({
            "element_type": "connector",
            "element_code": getattr(row, "codi_conn", None) or "IV",
            "name": connector_name,
            "hic_code": None,
            "hic_name": None,
            "is_hic": False,
            "is_priority": False,
            "area_ha": round(float(row.geometry.area / 10000), 4),
            "relevance": "Connector cartogràfic oficial o zona d’infraestructura verda; no demostra ús funcional per una espècie concreta.",
            "geometry": row.geometry,
        })
    elements = gpd.GeoDataFrame(elements_rows, geometry="geometry", crs=25831)

    priority = habitats.loc[habitats.es_prioritari.fillna(False), ["geometry"]]
    connector_all = gpd.GeoDataFrame(
        {"geometry": [unary_union(list(connectors.geometry) + list(connector_zones.geometry))]}, crs=25831
    )
    overlap = gpd.overlay(priority, connector_all, how="intersection", keep_geom_type=False)
    overlap = overlap.loc[~overlap.geometry.is_empty & (overlap.geometry.area >= 1000)].copy()
    for idx, geom in enumerate(overlap.geometry, start=1):
        elements.loc[len(elements)] = {
            "element_type": "value_overlap",
            "element_code": f"VAL-{idx:02d}",
            "name": "Coincidència d’HIC prioritari i connector cartografiat",
            "hic_code": None,
            "hic_name": None,
            "is_hic": True,
            "is_priority": True,
            "area_ha": round(float(geom.area / 10000), 4),
            "relevance": "Coincideixen dues evidències espacials de valor: HIC prioritari i connector cartogràfic oficial.",
            "geometry": geom,
        }
    elements = gpd.GeoDataFrame(elements, geometry="geometry", crs=25831)

    # Privacy-preserving 1 km coverage grid. It describes sampling knowledge,
    # never biodiversity level and never exposes occurrence coordinates or names.
    minx, miny, maxx, maxy = study_geometry.bounds
    grid_rows = []
    cell_n = 0
    for x in np.arange(np.floor(minx / 1000) * 1000, maxx, 1000):
        for y in np.arange(np.floor(miny / 1000) * 1000, maxy, 1000):
            clipped = box(x, y, x + 1000, y + 1000).intersection(study_geometry)
            if clipped.is_empty or clipped.area < 10000:
                continue
            cell_n += 1
            grid_rows.append({"knowledge_unit": cell_n, "geometry": clipped})
    knowledge = gpd.GeoDataFrame(grid_rows, geometry="geometry", crs=25831)
    joined = gpd.sjoin(
        biodiversity[["taxonGroup", "eventDate", "geometry"]],
        knowledge[["knowledge_unit", "geometry"]], predicate="within", how="left"
    )
    counts = joined.groupby("knowledge_unit").size()
    flora_counts = joined.loc[joined.taxonGroup.eq("Plantae")].groupby("knowledge_unit").size()
    fauna_counts = joined.loc[~joined.taxonGroup.isin(["Plantae", "Fungi"])].groupby("knowledge_unit").size()
    dated = joined.assign(year=pd.to_datetime(joined.eventDate, errors="coerce").dt.year)
    latest_year = dated.groupby("knowledge_unit").year.max()
    knowledge["records"] = knowledge.knowledge_unit.map(counts).fillna(0).astype(int)
    knowledge["flora_records"] = knowledge.knowledge_unit.map(flora_counts).fillna(0).astype(int)
    knowledge["fauna_records"] = knowledge.knowledge_unit.map(fauna_counts).fillna(0).astype(int)
    knowledge["latest_year"] = knowledge.knowledge_unit.map(latest_year).where(lambda s: s.notna(), None)
    positive = knowledge.loc[knowledge.records > 0, "records"]
    q25 = float(positive.quantile(.25)) if len(positive) else 0
    q60 = float(positive.quantile(.60)) if len(positive) else 0
    knowledge["knowledge_class"] = knowledge.records.map(
        lambda n: "Pràcticament sense dades" if n == 0 else "Poca informació" if n <= q25 else "Informació moderada" if n <= q60 else "Més informació publicada"
    )
    priority_union = unary_union(list(priority.geometry))
    connector_union = connector_all.geometry.iloc[0]
    knowledge["priority_hic_overlap"] = knowledge.geometry.map(lambda g: g.intersection(priority_union).area / 10000 >= .1)
    knowledge["connector_overlap"] = knowledge.geometry.map(lambda g: g.intersection(connector_union).area / 10000 >= .1)
    knowledge["prospecting_interest"] = knowledge.apply(
        lambda r: bool(r.knowledge_class in {"Pràcticament sense dades", "Poca informació"} and (r.priority_hic_overlap or r.connector_overlap)), axis=1
    )
    knowledge["reason"] = knowledge.apply(
        lambda r: "Coneixement públic escàs coincident amb " + " i ".join(
            item for item, ok in [("HIC prioritari", r.priority_hic_overlap), ("connector cartogràfic", r.connector_overlap)] if ok
        ) if r.prospecting_interest else "Cobertura de registres públics agregada; no descriu riquesa ni absència d’espècies.", axis=1
    )
    knowledge = knowledge.drop(columns=["knowledge_unit"])

    # Only exact intersections are situations. Current fire is accepted only
    # for cells classified high or above on the real daily product.
    fire_cells = gpd.read_file(PROJECT / "maps" / "incendis" / "current_fire_danger_cells.geojson", engine="pyogrio").to_crs(25831)
    fire_cells["index_0_100"] = pd.to_numeric(fire_cells["index_0_100"], errors="coerce")
    high_fire = fire_cells.loc[fire_cells.index_0_100 >= 61, ["index_0_100", "category", "geometry"]].copy()
    hic_columns = ["COD_CORINE", "CORINE_CA", "COD_HIC", "HIC_CA", "es_prioritari", "geometry"]
    current_hits = gpd.overlay(habitats.loc[habitats.es_hic.fillna(False), hic_columns], high_fire, how="intersection")
    historic_hits = gpd.overlay(habitats.loc[habitats.es_hic.fillna(False), hic_columns], fires[["fire_date", "geometry"]], how="intersection")
    situation_rows = []
    for kind, hits in (("current_fire", current_hits), ("historic_fire", historic_hits)):
        for code, group in hits.groupby("COD_HIC", dropna=False):
            geom = unary_union(list(group.geometry))
            if geom.is_empty or geom.area < 100:
                continue
            habitat_name = next((v for v in group.HIC_CA if isinstance(v, str) and v.strip()), None) or next(iter(group.CORINE_CA), "Hàbitat HIC")
            current = kind == "current_fire"
            situation_rows.append({
                "situation_type": kind,
                "title": f"{habitat_name} · " + ("comprovació de camp" if current else "mantenir seguiment"),
                "ecological_element": habitat_name,
                "hic_code": None if str(code) in {"-", "None", "nan"} else str(code),
                "is_priority": bool(group.es_prioritari.fillna(False).any()),
                "area_ha": round(float(geom.area / 10000), 4),
                "what_happens": (
                    "Una part concreta de l’HIC coincideix amb cel·les on el producte diari EcoRadar classifica el perill actual com a alt."
                    if current else
                    "Una part concreta de l’HIC coincideix amb un perímetre oficial d’incendi històric."
                ),
                "why_flagged": ["HIC cartografiat", "perill d’incendi actual alt"] if current else ["HIC cartografiat", "perímetre oficial d’incendi històric"],
                "structural": ["hàbitat HIC", "antecedent d’incendi"] if not current else ["hàbitat HIC", "vulnerabilitat territorial incorporada al producte de foc"],
                "current": ["perill EcoRadar actual alt; meteorologia i frescor de dades segons la lectura diària"] if current else ["cap canvi actual inferit a partir del perímetre històric"],
                "meaning": (
                    "La coincidència justifica vigilància i verificació de combustible i estat de l’hàbitat; no demostra impacte ni obliga a intervenir."
                    if current else
                    "L’antecedent justifica revisar la trajectòria de recuperació; no implica un estat de conservació desfavorable."
                ),
                "scenario": "Si les condicions desfavorables es mantenen, l’exposició al foc pot persistir; no és una predicció d’incendi." if current else "Sense una sèrie comparable i camp no es pot afirmar si la recuperació millora o empitjora.",
                "ecological_mechanism": "Un incendi podria alterar estructura, cobertura i recursos de l’hàbitat, amb resposta diferent segons intensitat, recurrència i espècies." if current else "La resposta postincendi depèn de severitat, recurrència, sòl, regeneració i usos posteriors.",
                "unknown": ["estat local de conservació", "humitat del combustible mesurada al camp", "resposta real de flora i fauna"],
                "recommendation": "comprovació de camp" if current else "mantenir seguiment",
                "field_check": ["estructura i continuïtat del combustible", "regeneració i senyals de deteriorament", "evidència d’ús de fauna sense publicar localitzacions sensibles"],
                "monitor": ["perill d’incendi actual", "NDMI i NDVI quan hi hagi una observació nova i vàlida", "temperatura superficial amb data i frescor"],
                "max_fire_index": round(float(group.index_0_100.max()), 1) if current else None,
                "geometry": geom,
            })
    situations = gpd.GeoDataFrame(situation_rows, geometry="geometry", crs=25831)

    meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "definitive_ecological_module",
        "unit": "Geometries reals d’hàbitats, connectors i interseccions; quadrícula d’1 km només per agregar cobertura del coneixement.",
        "privacy": "Cap nom de taxó ni coordenada d’ocurrència s’exporta. La fauna i la flora es representen mitjançant recomptes agregats d’1 km.",
        "knowledge_thresholds": {"positive_q25": q25, "positive_q60": q60},
        "dynamic_data": {
            "ndvi_ndmi": {"date": ndmi_context.get("date_utc"), "status": ndmi_context.get("temporal_status_label", "estat temporal no disponible")},
            "surface_temperature": {"date": lst_context.get("date_utc"), "status": lst_context.get("temporal_status_label", "estat temporal no disponible")},
            "current_fire": {"checked_at_utc": current_fire_context.get("checked_at_utc"), "status": "actualització diària; data exacta preservada"},
        },
        "limitations": [
            "Les coincidències espacials no demostren causalitat ni impacte.",
            "La cartografia d’hàbitats no determina l’estat local de conservació.",
            "Pocs registres signifiquen coneixement insuficient, no baixa biodiversitat.",
            "Els connectors descriuen continuïtat cartogràfica potencial, no ús funcional verificat per fauna.",
        ],
        "counts": {
            "habitat_features": int((elements.element_type == "habitat").sum()),
            "connector_features": int((elements.element_type == "connector").sum()),
            "value_overlap_features": int((elements.element_type == "value_overlap").sum()),
            "situations": len(situations),
            "knowledge_cells": len(knowledge),
            "prospecting_cells": int(knowledge.prospecting_interest.sum()),
        },
    }
    return elements, situations, knowledge, meta


def read_layer(filename: str, layer: str) -> gpd.GeoDataFrame:
    return gpd.read_file(PROCESSED / filename, layer=layer, engine="pyogrio").to_crs(25831)


def union_where(frame: gpd.GeoDataFrame, mask) -> object:
    geometries = frame.loc[mask, "geometry"]
    return unary_union(list(geometries)) if len(geometries) else None


def intersection_area_ha(geometry, overlay) -> float:
    return 0.0 if overlay is None or geometry.is_empty else geometry.intersection(overlay).area / 10000


def zonal_median(path: Path, sectors: gpd.GeoDataFrame) -> list[float | None]:
    values: list[float | None] = []
    with rasterio.open(path) as dataset:
        projected = sectors.to_crs(dataset.crs)
        band = dataset.read(1, masked=True)
        for geometry in projected.geometry:
            mask = geometry_mask([geometry.__geo_interface__], dataset.shape, dataset.transform, invert=True)
            sample = np.asarray(band[mask].compressed(), dtype=float)
            sample = sample[np.isfinite(sample)]
            values.append(round(float(np.median(sample)), 3) if sample.size else None)
    return values


def positive_quantile(series: pd.Series, q: float) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.quantile(q)) if len(values) else None


def relative_signal(value: float | None, threshold: float | None, direction: str) -> bool:
    if value is None or threshold is None:
        return False
    return value <= threshold if direction == "low" else value >= threshold


def build() -> tuple[gpd.GeoDataFrame, dict]:
    sectors = read_layer("connectivitat.gpkg", "connectivitat_terrestre_index").copy()
    sectors["centroid_x"] = sectors.geometry.centroid.x
    sectors["centroid_y"] = sectors.geometry.centroid.y
    sectors = sectors.sort_values(["centroid_y", "centroid_x"], ascending=[False, True]).reset_index(drop=True)
    sectors["sector_id"] = [f"BH-{index:02d}" for index in range(1, len(sectors) + 1)]
    sectors["area_ha"] = sectors.geometry.area / 10000

    habitats = read_layer("habitats.gpkg", "habitats")
    biodiversity = read_layer("biodiversitat.gpkg", "biodiversitat")
    connectors = read_layer("connectivitat.gpkg", "connectors_terrestres_principals")
    connector_zones = read_layer("connectivitat.gpkg", "zones_connectors_infraestructura_verda")
    roads = read_layer("recreational_pressure.gpkg", "osm_paths_tracks_roads")
    public_points = read_layer("recreational_pressure.gpkg", "osm_recreational_points")
    fires = read_layer("incendis.gpkg", "incendis_historics")
    covers = read_layer("cobertes_sol.gpkg", "cobertes_sol")

    hic_union = union_where(habitats, habitats["es_hic"].fillna(False))
    priority_union = union_where(habitats, habitats["es_prioritari"].fillna(False))
    connector_union = unary_union(list(connectors.geometry) + list(connector_zones.geometry))
    natural_union = union_where(
        covers,
        covers["tipus_coberta"].str.contains("Bosc|Boscos|Matollar|Prats|ribera", case=False, regex=True),
    )
    bare_union = union_where(covers, covers["tipus_coberta"].str.contains("Roquissars", case=False, na=False))

    sectors["hic_ha"] = [intersection_area_ha(g, hic_union) for g in sectors.geometry]
    sectors["priority_hic_ha"] = [intersection_area_ha(g, priority_union) for g in sectors.geometry]
    sectors["connector_ha"] = [intersection_area_ha(g, connector_union) for g in sectors.geometry]
    sectors["natural_cover_pct"] = [100 * intersection_area_ha(g, natural_union) / a if a else 0 for g, a in zip(sectors.geometry, sectors.area_ha)]
    sectors["bare_pct"] = [100 * intersection_area_ha(g, bare_union) / a if a else 0 for g, a in zip(sectors.geometry, sectors.area_ha)]

    bio_join = gpd.sjoin(biodiversity[["geometry"]], sectors[["sector_id", "geometry"]], predicate="within", how="left")
    bio_counts = bio_join.groupby("sector_id").size()
    sectors["records"] = sectors.sector_id.map(bio_counts).fillna(0).astype(int)

    sectors["road_km"] = [roads.geometry.intersection(g).length.sum() / 1000 for g in sectors.geometry]
    sectors["access_km_km2"] = sectors.road_km / (sectors.area_ha / 100)
    points_join = gpd.sjoin(public_points[["geometry"]], sectors[["sector_id", "geometry"]], predicate="within", how="left")
    point_counts = points_join.groupby("sector_id").size()
    sectors["public_points"] = sectors.sector_id.map(point_counts).fillna(0).astype(int)
    sectors["historic_fire_ha"] = [sum(intersection_area_ha(g, fire) for fire in fires.geometry) for g in sectors.geometry]
    sectors["historic_fire_events"] = [sum(g.intersects(fire) for fire in fires.geometry) for g in sectors.geometry]

    sectors["ndvi"] = zonal_median(PROCESSED / "teledeteccio" / "ndvi.tif", sectors)
    sectors["ndmi"] = zonal_median(PROCESSED / "teledeteccio" / "ndmi.tif", sectors)
    sectors["lst_c"] = zonal_median(PROCESSED / "landsat" / "landsat_lst.tif", sectors)
    sectors["fire_today"] = zonal_median(
        PROCESSED / "incendis" / "current_fire_danger" / "current_fire_danger_0_100.tif", sectors
    )

    thresholds = {
        "records_q25_positive": positive_quantile(sectors.loc[sectors.records > 0, "records"], 0.25),
        "records_median_positive": positive_quantile(sectors.loc[sectors.records > 0, "records"], 0.5),
        "ndmi_q25": positive_quantile(sectors.ndmi, 0.25),
        "ndvi_q25": positive_quantile(sectors.ndvi, 0.25),
        "lst_q75": positive_quantile(sectors.lst_c, 0.75),
        "bare_q75": positive_quantile(sectors.bare_pct, 0.75),
        "access_q75": positive_quantile(sectors.access_km_km2, 0.75),
        "natural_cover_q75": positive_quantile(sectors.natural_cover_pct, 0.75),
    }

    def classify_knowledge(records: int) -> str:
        if records == 0:
            return "Pràcticament sense dades"
        if records <= (thresholds["records_q25_positive"] or 0):
            return "Poca informació"
        if records <= (thresholds["records_median_positive"] or 0):
            return "Informació moderada"
        return "Ben prospectat en fonts públiques"

    rows = []
    for row in sectors.itertuples():
        value_reasons = []
        if row.priority_hic_ha >= 0.1:
            value_reasons.append(f"{row.priority_hic_ha:.1f} ha d’HIC prioritari cartografiat")
        if row.hic_ha >= 0.1:
            value_reasons.append(f"{row.hic_ha:.1f} ha d’HIC cartografiat")
        if row.connector_ha >= 0.1:
            value_reasons.append(f"{row.connector_ha:.1f} ha dins connectors terrestres oficials")
        if row.records > (thresholds["records_median_positive"] or 0):
            value_reasons.append(f"{row.records} registres públics agregats; indiquen coneixement, no abundància")
        if value_reasons and row.natural_cover_pct >= 75:
            value_reasons.append(f"{row.natural_cover_pct:.0f} % de cobertes naturals o seminaturals com a context de continuïtat")

        pressure_reasons = []
        if relative_signal(row.ndmi, thresholds["ndmi_q25"], "low"):
            pressure_reasons.append(f"NDMI relativament baix ({row.ndmi:.2f}; observació 07/07/2026)")
        if relative_signal(row.ndvi, thresholds["ndvi_q25"], "low"):
            pressure_reasons.append(f"NDVI relativament baix ({row.ndvi:.2f}; observació 07/07/2026)")
        if relative_signal(row.lst_c, thresholds["lst_q75"], "high"):
            pressure_reasons.append(f"temperatura superficial estival relativament elevada ({row.lst_c:.1f} °C)")
        if thresholds["bare_q75"] and row.bare_pct >= thresholds["bare_q75"] and row.bare_pct > 0:
            pressure_reasons.append(f"proporció relativa elevada de roquissars/congestes ({row.bare_pct:.1f} %); no equival automàticament a degradació")
        if row.historic_fire_ha > 0.05:
            label = "coincidència amb dos perímetres històrics" if row.historic_fire_events > 1 else "coincidència amb un perímetre històric"
            pressure_reasons.append(f"{label} ({row.historic_fire_ha:.1f} ha solapades)")
        if row.fire_today is not None and row.fire_today >= 61:
            pressure_reasons.append(f"perill EcoRadar actual alt al sector ({row.fire_today:.0f}/100)")
        if row.access_km_km2 >= (thresholds["access_q75"] or float("inf")):
            pressure_reasons.append(f"accessibilitat potencial relativa elevada ({row.access_km_km2:.1f} km de xarxa/km²); no és freqüentació real")

        knowledge = classify_knowledge(row.records)
        valuable = bool(value_reasons)
        pressured = bool(pressure_reasons)
        connectivity_reasons = []
        if row.connector_ha >= 0.1:
            connectivity_reasons.append(f"{row.connector_ha:.1f} ha dins connectors terrestres oficials")
        if row.natural_cover_pct >= (thresholds["natural_cover_q75"] or float("inf")):
            connectivity_reasons.append(
                f"{row.natural_cover_pct:.0f} % de cobertes naturals o seminaturals com a context de continuïtat"
            )
        reading_coincidences = list(pressure_reasons)
        detected = []
        if value_reasons:
            detected.append("valor ecològic cartografiat amb les fonts disponibles")
        if pressure_reasons:
            detected.append("coincidències espacials amb altres lectures EcoRadar")
        if connectivity_reasons:
            detected.append("continuïtat o connector cartografiat")
        if knowledge in {"Pràcticament sense dades", "Poca informació"}:
            detected.append("coneixement biològic públic insuficient")

        implications = []
        if row.connector_ha >= 0.1:
            implications.append(
                "Una alteració dins un connector cartografiat podria reduir permeabilitat ecològica; la funcionalitat real s’ha de validar per grups de fauna."
            )
        if relative_signal(row.ndmi, thresholds["ndmi_q25"], "low"):
            implications.append(
                "La humitat espectral relativament baixa pot ser compatible amb menys disponibilitat hídrica de la vegetació, però no demostra estrès fisiològic sense camp."
            )
        if relative_signal(row.ndvi, thresholds["ndvi_q25"], "low"):
            implications.append(
                "El vigor espectral relativament baix pot respondre a coberta, fenologia, sòl o estat vegetal; cal contrastar la causa abans d’interpretar degradació."
            )
        if relative_signal(row.lst_c, thresholds["lst_q75"], "high"):
            implications.append(
                "Una superfície relativament càlida pot reduir la funció de refugi tèrmic i reforçar l’assecament, si coincideix amb baixa humitat i la situació es confirma al camp."
            )
        if row.historic_fire_ha > 0.05:
            implications.append(
                "La coincidència amb foc històric justifica revisar trajectòria de recuperació i estructura, però no implica per si sola un estat ecològic desfavorable."
            )
        if row.fire_today is not None and row.fire_today >= 61:
            implications.append(
                "El perill d’incendi actual elevat augmenta la necessitat de vigilància conjuntural; no converteix el sector en candidat automàtic a tractament."
            )
        if row.access_km_km2 >= (thresholds["access_q75"] or float("inf")):
            implications.append(
                "L’accessibilitat potencial pot facilitar coincidències d’ús amb hàbitats o fauna, però la freqüentació i l’impacte real no estan mesurats."
            )
        if valuable and len(pressure_reasons) >= 2:
            followup = "Prioritat de comprovació"
            recommendation = "Comprovar al camp l’estat de l’hàbitat i les coincidències abans de decidir actuacions."
        elif valuable and pressured:
            followup = "Atenció"
            recommendation = "Fer seguiment dirigit i verificar la pressió coincident sobre el terreny."
        elif knowledge in {"Pràcticament sense dades", "Poca informació"}:
            followup = "Coneixement insuficient"
            recommendation = "Prospectar de manera dirigida; la manca de registres no indica baixa biodiversitat."
        elif valuable or pressured:
            followup = "Seguiment recomanat"
            recommendation = "Mantenir observació i repetir les lectures dinàmiques quan hi hagi una nova dada vàlida."
        else:
            followup = "Sense senyals destacables"
            recommendation = "Mantenir observació sense inferir absència de valors o impactes."

        missing = []
        if knowledge != "Ben prospectat en fonts públiques":
            missing.append("prospecció biològica homogènia i de camp")
        missing.extend(["estat local de conservació dels hàbitats", "fragmentació funcional específica per fauna"])
        rows.append(
            {
                "value_reasons": value_reasons,
                "pressure_reasons": pressure_reasons,
                "knowledge_class": knowledge,
                "followup": followup,
                "recommendation": recommendation,
                "missing": missing,
                "valuable": valuable,
                "pressured": pressured,
                "connectivity_reasons": connectivity_reasons,
                "connected": bool(connectivity_reasons),
                "change_detected": False,
                "reading_coincidences": reading_coincidences,
                "detected": detected,
                "possible_implications": implications,
            }
        )

    for key in rows[0]:
        sectors[key] = [row[key] for row in rows]

    keep = [
        "sector_id", "area_ha", "hic_ha", "priority_hic_ha", "connector_ha", "natural_cover_pct",
        "bare_pct", "records", "road_km", "access_km_km2", "public_points", "historic_fire_ha",
        "historic_fire_events", "ndvi", "ndmi", "lst_c", "fire_today", "value_reasons",
        "pressure_reasons", "knowledge_class", "followup", "recommendation", "missing", "valuable",
        "pressured", "connectivity_reasons", "connected", "change_detected", "reading_coincidences",
        "detected", "possible_implications", "geometry",
    ]
    result = sectors[keep].to_crs(4326)
    for column in ["area_ha", "hic_ha", "priority_hic_ha", "connector_ha", "natural_cover_pct", "bare_pct", "road_km", "access_km_km2", "historic_fire_ha"]:
        result[column] = result[column].round(2)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Muntanya d’Alinyà",
        "status": "pilot_qualitative",
        "sector_unit": "49 unitats cartogràfiques oficials de l’índex de connectivitat terrestre de la Generalitat, retallades a l’àmbit; no són una quadrícula EcoRadar ni una delimitació de gestió.",
        "privacy": "Els registres de biodiversitat només s’agreguen per sector. El producte no conté coordenades, noms de taxons ni localitzacions sensibles.",
        "thresholds": thresholds,
        "threshold_method": "Quartils territorials interns per detectar contrastos relatius entre sectors; no són llindars ecològics, legals ni causals.",
        "classification_rules": {
            "Prioritat de comprovació": "valor ecològic cartografiat i dues o més coincidències de pressió",
            "Atenció": "valor ecològic cartografiat i una coincidència de pressió",
            "Coneixement insuficient": "cap registre o recompte dins el primer quartil positiu, sense una coincidència valor-pressions de rang superior",
            "Seguiment recomanat": "valor o pressió sense coincidència suficient per a les categories anteriors",
            "Sense senyals destacables": "cap senyal destacable amb les dades disponibles; no implica absència de valor o impacte",
        },
        "sources": [
            "Generalitat de Catalunya: Hàbitats terrestres v3 i HIC",
            "Generalitat de Catalunya: Infraestructura Verda / connectivitat ecològica",
            "Generalitat de Catalunya: perímetres d’incendis històrics",
            "ICGC: Cobertes del Sol de Catalunya 2024",
            "Copernicus Sentinel-2 L2A: NDVI i NDMI, 07/07/2026",
            "USGS Landsat 8/9 Collection 2 L2: temperatura superficial, composició estival 2025–2026",
            "EcoRadar: perill d’incendi actual, amb data preservada al visor",
            "GBIF i iNaturalist: registres públics agregats",
            "OpenStreetMap: xarxa i punts d’ús públic com a accessibilitat potencial",
        ],
        "limitations": [
            "No avalua estat de conservació ni presència d’espècies protegides perquè aquestes dades no estan verificades en el conjunt disponible.",
            "Pocs registres signifiquen coneixement insuficient, no baixa biodiversitat.",
            "Les coincidències espacials no demostren causalitat ni impacte.",
            "La xarxa OSM indica accessibilitat potencial, no freqüentació ni pressió real.",
            "La fragmentació funcional necessita dades específiques de barreres, espècies i validació de camp.",
            "NDVI, NDMI i temperatura superficial conserven la data real de les observacions i no es presenten com a mesures de camp.",
        ],
        "counts": {
            "sectors": len(result),
            "valuable": int(result.valuable.sum()),
            "pressured": int(result.pressured.sum()),
            "knowledge_insufficient": int(result.knowledge_class.isin(["Pràcticament sense dades", "Poca informació"]).sum()),
            "priority_check": int((result.followup == "Prioritat de comprovació").sum()),
            "connectivity": int(result.connected.sum()),
            "changes_detected": 0,
        },
        "diagnostic_availability": {
            "value": {"available": True},
            "pressure": {"available": True},
            "changes": {
                "available": False,
                "message": "Informació insuficient per generar aquesta diagnosi.",
                "missing": [
                    "sèrie espacial multitemporal comparable de NDVI i NDMI",
                    "dates de coberta del sòl harmonitzades per detectar transicions",
                    "validació de camp dels canvis observats",
                ],
            },
            "connectivity": {
                "available": True,
                "limit": "Mostra connectors oficials i continuïtat de cobertes com a context; no identifica funcionalitat específica per espècie ni barreres no cartografiades.",
            },
            "knowledge": {"available": True},
            "followup": {"available": True},
        },
    }
    return result, metadata


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    result, metadata = build()
    OUTPUT.write_text(result.to_json(drop_id=True), encoding="utf-8")
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elements, situations, knowledge, ecology_metadata = build_ecological_products()
    write_geojson(elements, ECOLOGY_OUTPUT)
    write_geojson(situations, SITUATIONS_OUTPUT)
    write_geojson(knowledge, KNOWLEDGE_OUTPUT)
    ECOLOGY_METADATA.write_text(json.dumps(ecology_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result)} qualitative sectors to {OUTPUT}")
    print(f"Wrote {len(elements)} ecological elements, {len(situations)} exact situations and {len(knowledge)} knowledge cells")


if __name__ == "__main__":
    main()
