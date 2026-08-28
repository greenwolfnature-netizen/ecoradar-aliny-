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
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
PROCESSED = PROJECT / "processed"
OUTPUT = PROJECT / "indicators" / "biodiversity_habitat_pilot.geojson"
METADATA = PROJECT / "metadata" / "biodiversity_habitat_pilot_metadata.json"


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
            }
        )

    for key in rows[0]:
        sectors[key] = [row[key] for row in rows]

    keep = [
        "sector_id", "area_ha", "hic_ha", "priority_hic_ha", "connector_ha", "natural_cover_pct",
        "bare_pct", "records", "road_km", "access_km_km2", "public_points", "historic_fire_ha",
        "historic_fire_events", "ndvi", "ndmi", "lst_c", "fire_today", "value_reasons",
        "pressure_reasons", "knowledge_class", "followup", "recommendation", "missing", "valuable",
        "pressured", "geometry",
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
        },
    }
    return result, metadata


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    result, metadata = build()
    OUTPUT.write_text(result.to_json(drop_id=True), encoding="utf-8")
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result)} qualitative sectors to {OUTPUT}")


if __name__ == "__main__":
    main()
