"""Build the EcoRadar source implementation matrix for one project.

This is a data-engine audit artifact only. It does not calculate indicators,
does not run diagnosis and does not create report/fitxa outputs.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "data_sources.yaml"
PROJECT = ROOT / "projectes" / "Alinya"
OUT_JSON = PROJECT / "metadata" / "data_sources_matrix.json"
OUT_CSV = PROJECT / "metadata" / "data_sources_matrix.csv"
OUT_MD = PROJECT / "metadata" / "data_sources_matrix.md"

STATUS_OK = "✅ Funciona"
STATUS_PARTIAL = "⚠️ Parcial"
STATUS_NOT_IMPLEMENTED = "❌ No implementada"
STATUS_CREDENTIALS = "🔒 Requereix credencials"
STATUS_UNAVAILABLE = "🚫 No disponible"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: Any) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def fmt(value: Any, decimals: int = 1) -> str:
    return f"{number(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def status_for_credentials(source: dict[str, Any]) -> str | None:
    missing = [name for name in source.get("requires_credentials", []) if not os.environ.get(name)]
    return STATUS_CREDENTIALS if missing else None


def biodiversity_counts() -> dict[str, int]:
    path = PROJECT / "processed" / "biodiversitat.gpkg"
    if not path.exists():
        return {}
    query = "SELECT source, COUNT(*) FROM biodiversitat GROUP BY source"
    try:
        with sqlite3.connect(path) as connection:
            return {str(source): int(count) for source, count in connection.execute(query)}
    except sqlite3.Error:
        return {}


def habitat_totals() -> dict[str, float]:
    rows = read_csv_rows(PROJECT / "indicators" / "habitats_resum.csv")
    total_hic = 0.0
    total_priority = 0.0
    for row in rows:
        if row.get("es_hic", "").lower() == "true":
            total_hic += number(row.get("superficie_ha"))
        if row.get("es_prioritari", "").lower() == "true":
            total_priority += number(row.get("superficie_ha"))
    return {"hic_ha": total_hic, "priority_ha": total_priority, "habitats": len(rows)}


def evidence_matrix() -> dict[str, dict[str, str]]:
    study = read_json(PROJECT / "metadata" / "study_area_metadata.json")
    cover = read_json(PROJECT / "metadata" / "cobertes_sol_metadata.json")
    habitats = read_json(PROJECT / "metadata" / "habitats_metadata.json")
    habitat_stats = habitat_totals()
    biodiv = read_json(PROJECT / "metadata" / "biodiversitat_metadata.json")
    biodiv_summary = read_csv_rows(PROJECT / "indicators" / "biodiversitat_resum.csv")
    biodiv_by_source = biodiversity_counts()
    osm = read_json(PROJECT / "metadata" / "recreational_pressure_metadata.json")
    tele = read_json(PROJECT / "metadata" / "teledeteccio_metadata.json")
    terrain = read_json(PROJECT / "metadata" / "terrain_metadata.json")
    hydro = read_json(PROJECT / "metadata" / "hidrologia_metadata.json")
    fire = read_json(PROJECT / "metadata" / "incendis_metadata.json")
    connectivity = read_json(PROJECT / "metadata" / "connectivitat_metadata.json")
    fire_sim = read_json(PROJECT / "metadata" / "incendis_similarity" / "similitud_condicions_incendi_alinya_metadata.json")

    records = sum(int(row.get("nombre_registres", 0) or 0) for row in biodiv_summary)
    species = sum(int(row.get("nombre_especies", 0) or 0) for row in biodiv_summary)

    dem = PROJECT / "processed" / "terrain" / "dem.tif"
    slope = PROJECT / "processed" / "terrain" / "slope.tif"
    aspect = PROJECT / "processed" / "terrain" / "aspect.tif"
    northness = PROJECT / "processed" / "terrain" / "northness.tif"
    solana_obaga = PROJECT / "processed" / "terrain" / "solana_obaga.tif"
    fire_poly = PROJECT / "processed" / "incendis.gpkg"
    fuel_proxy = PROJECT / "processed" / "incendis_similarity" / "similitud_condicions_incendi_alinya.gpkg"

    return {
        "study_area_file": {
            "status": STATUS_OK if (PROJECT / "processed" / "study_area.gpkg").exists() else STATUS_UNAVAILABLE,
            "data": f"1 polígon; {fmt(study.get('surface_ha'))} ha; perímetre {fmt(study.get('perimeter_m'), 0)} m; CRS final {study.get('final_crs', '')}",
            "reason": "" if study else "No existeix l'àrea processada.",
            "action": "Cap: font base preparada.",
        },
        "icgc_base_maps": {
            "status": STATUS_PARTIAL if (PROJECT / "maps" / "producte" / "mapa_base_alinya.png").exists() else STATUS_NOT_IMPLEMENTED,
            "data": "Mapes de context locals generats per producte; no hi ha connector ICGC base/ortofoto formalitzat.",
            "reason": "Connector base ICGC pendent encara que existeixen PNG de context.",
            "action": "Crear connector WMTS/WMS per ortofoto/topogràfic ICGC i guardar metadades de capa/escala.",
        },
        "land_cover_icgc_cobertes_sol": {
            "status": STATUS_OK if (PROJECT / "processed" / "cobertes_sol.gpkg").exists() else STATUS_NOT_IMPLEMENTED,
            "data": f"{cover.get('tile_count', 0)} tiles WCS; {cover.get('class_count', 0)} classes; {fmt(cover.get('surface_ha_from_classified_pixels'))} ha classificades; resum CSV i GPKG.",
            "reason": "" if cover else "No hi ha metadades de cobertes.",
            "action": "Cap per Alinyà; mantenir cache per evitar duplicats.",
        },
        "land_cover_mcsc": {
            "status": STATUS_NOT_IMPLEMENTED,
            "data": "No retorna dades dins EcoRadar encara.",
            "reason": "Font CREAF/MCSC documentada com a complement però sense endpoint/connector automàtic verificat.",
            "action": "Verificar via CREAF/servei oficial el format descarregable i crear connector només després de documentar llicència i versió.",
        },
        "habitats_terrestres_v3": {
            "status": STATUS_OK if (PROJECT / "processed" / "habitats.gpkg").exists() else STATUS_NOT_IMPLEMENTED,
            "data": f"{habitats.get('features_downloaded', 0)} polígons descarregats; {habitats.get('features_clipped', 0)} retallats; {habitat_stats['habitats']} hàbitats resumits.",
            "reason": "" if habitats else "No hi ha sortida d'hàbitats.",
            "action": "Cap per Alinyà; falta només incorporar capa puntual si es volen hàbitats <15.000 m2.",
        },
        "hic_v2": {
            "status": STATUS_PARTIAL,
            "data": f"HIC derivats dels camps de la capa d'hàbitats: {fmt(habitat_stats['hic_ha'])} ha HIC; {fmt(habitat_stats['priority_ha'])} ha prioritaris.",
            "reason": "No s'ha descarregat una capa HIC v2 separada; s'han usat camps COD_HIC/HIC_PRIOR presents a hàbitats v3.",
            "action": "Afegir descàrrega/validació HIC v2 IDEC com a capa independent per contrastar v3.",
        },
        "sigpac_catalunya": {
            "status": STATUS_NOT_IMPLEMENTED,
            "data": "No retorna parcel·les SIGPAC ni cultius dins EcoRadar.",
            "reason": "Connector SIGPAC/DUN pendent; les hectàrees agràries actuals provenen només de cobertes/hàbitats.",
            "action": "Localitzar servei oficial descarregable/WMS-WFS i implementar retall per recinte, ús i cultiu.",
        },
        "copernicus_sentinel_indices": {
            "status": STATUS_CREDENTIALS,
            "data": "Cap NDVI/NDMI/NDWI real descarregat.",
            "reason": tele.get("blocker", "Falten credencials Copernicus OAuth."),
            "action": "Configurar COPERNICUS_CLIENT_ID i COPERNICUS_CLIENT_SECRET; executar connector Sentinel-2 L2A.",
        },
        "copernicus_lst": {
            "status": STATUS_CREDENTIALS,
            "data": "Cap LST real descarregada.",
            "reason": tele.get("lst_status", "Falten credencials i mapping de col·lecció LST."),
            "action": "Definir col·lecció operativa LST/Sentinel-3 o CLMS i credencials Copernicus.",
        },
        "icgc_dem_mdt": {
            "status": STATUS_OK if dem.exists() and slope.exists() and aspect.exists() and northness.exists() and solana_obaga.exists() else STATUS_NOT_IMPLEMENTED,
            "data": (
                f"DEM ICGC 5 m retallat; altitud {fmt(terrain.get('variables', {}).get('altitude_m', {}).get('min'))}-"
                f"{fmt(terrain.get('variables', {}).get('altitude_m', {}).get('max'))} m; "
                f"pendent mitjà {fmt(terrain.get('variables', {}).get('slope_degrees', {}).get('mean'))}°; "
                "capes DEM, pendent, orientació, northness i obaga/solana."
            ),
            "reason": "" if terrain else "No hi ha metadades terrain.",
            "action": "Cap per Alinyà; validar només si es canvia la resolució o font ICGC.",
        },
        "aca_hydrology": {
            "status": STATUS_OK if (PROJECT / "processed" / "hidrologia.gpkg").exists() else STATUS_NOT_IMPLEMENTED,
            "data": (
                f"{sum(int(layer.get('feature_count', 0)) for layer in hydro.get('layers', []))} elements oficials; "
                f"{fmt(sum(float(layer.get('length_km', 0.0)) for layer in hydro.get('layers', [])))} km de xarxa hidrogràfica/drenatge; "
                f"{sum(1 for layer in hydro.get('layers', []) if layer.get('theme') == 'springs' for _ in range(int(layer.get('feature_count', 0))))} fonts."
            ),
            "reason": "" if hydro else "No hi ha metadades d'hidrologia.",
            "action": "Cap per Alinyà; les capes amb zero elements es mantenen com a consulta oficial sense presència dins l'àrea.",
        },
        "connectivity_infraestructura_verda": {
            "status": STATUS_OK if (PROJECT / "processed" / "connectivitat.gpkg").exists() else STATUS_NOT_IMPLEMENTED,
            "data": (
                f"{sum(int(layer.get('feature_count', 0)) for layer in connectivity.get('layers', []))} entitats oficials retallades; "
                f"{fmt(sum(float(layer.get('area_ha', 0.0)) for layer in connectivity.get('layers', [])))} ha en capes d'índex/connectors; "
                f"{fmt(sum(float(layer.get('length_km', 0.0)) for layer in connectivity.get('layers', [])))} km en geometries lineals/perímetres."
            ),
            "reason": "" if connectivity else "No hi ha metadades de connectivitat.",
            "action": "Cap per Alinyà; el connector només normalitza dades, no calcula puntuacions de connectivitat.",
        },
        "gbif_occurrences": {
            "status": STATUS_OK if (PROJECT / "raw" / "biodiversitat" / "gbif_raw.json").exists() else STATUS_NOT_IMPLEMENTED,
            "data": f"{biodiv.get('records_downloaded', {}).get('GBIF', 0)} registres bruts; {biodiv_by_source.get('GBIF', 0)} registres normalitzats dins l'àrea.",
            "reason": "Límit GBIF assolit; mostra pública oportunista, no cens complet." if biodiv.get("download_limit_reached", {}).get("GBIF") else "",
            "action": "Afegir paginació/descàrrega completa o filtre taxonòmic si es vol superar el límit actual.",
        },
        "inaturalist_observations": {
            "status": STATUS_OK if (PROJECT / "raw" / "biodiversitat" / "inaturalist_raw.json").exists() else STATUS_NOT_IMPLEMENTED,
            "data": f"{biodiv.get('records_downloaded', {}).get('iNaturalist', 0)} registres bruts; {biodiv_by_source.get('iNaturalist', 0)} registres normalitzats dins l'àrea.",
            "reason": "",
            "action": "Cap per Alinyà; mantenir filtre de qualitat i retall local.",
        },
        "bdbc": {
            "status": STATUS_NOT_IMPLEMENTED,
            "data": "No retorna registres BDBC dins EcoRadar.",
            "reason": "Accés automàtic/API no verificat; font definida com a manual/API pendent.",
            "action": "Verificar amb BDBC/UB si hi ha exportació autoritzada per polígon o quadrícula i documentar llicència.",
        },
        "field_biodiversity": {
            "status": STATUS_UNAVAILABLE,
            "data": "No hi ha fitxers de camp importats.",
            "reason": "No s'ha proporcionat dataset propi de camp per Alinyà.",
            "action": "Crear importador CSV/GPKG/media i plantilla de camp; importar observacions validades.",
        },
        "osm_public_use": {
            "status": STATUS_OK if (PROJECT / "processed" / "recreational_pressure.gpkg").exists() else STATUS_NOT_IMPLEMENTED,
            "data": f"{osm.get('raw_elements', 0)} elements OSM; {osm.get('line_features', 0)} línies; {osm.get('point_features', 0)} punts d'ús públic.",
            "reason": "",
            "action": "Cap per xarxa base; validar intensitat real amb camp/comptadors.",
        },
        "strava_heatmap": {
            "status": STATUS_UNAVAILABLE,
            "data": "No retorna heatmap dins EcoRadar.",
            "reason": "Ús condicionat legalment; EcoRadar no ha de fer scraping ni ús no autoritzat.",
            "action": "Només integrar si Strava ofereix accés compatible/autoritzat i documentat.",
        },
        "fires_burned_areas": {
            "status": STATUS_OK if fire_poly.exists() else STATUS_NOT_IMPLEMENTED,
            "data": f"{fire.get('features_clipped', 0)} perímetres oficials; {fmt(fire.get('burned_area_ha'))} ha cremades dins l'àrea; resum i GeoPackage normalitzats.",
            "reason": "" if fire else "No hi ha metadades d'incendis.",
            "action": "Cap per Alinyà; completar amb altres fonts només quan l'esquema oficial estigui documentat.",
        },
        "effis": {
            "status": STATUS_PARTIAL if (PROJECT / "raw" / "incendis" / "effis_drf_datasets.json").exists() else STATUS_NOT_IMPLEMENTED,
            "data": f"Catàleg EFFIS consultat: {fire.get('effis', {}).get('dataset_count', 0)} datasets; sense geometria local descarregada.",
            "reason": "EFFIS queda integrat només com a catàleg; falta flux product-specific amb geometria, llicència i esquema documentats.",
            "action": "Implementar descàrrega d'un producte EFFIS concret quan es verifiqui l'endpoint oficial, camps i condicions d'ús.",
        },
        "fuel_continuity": {
            "status": STATUS_PARTIAL if fuel_proxy.exists() else STATUS_NOT_IMPLEMENTED,
            "data": f"Proxy local de similitud/condicions: {fire_sim.get('cell_size_m', 0)} m de cel·la; {len(fire_sim.get('similarity_area_by_class_ha', {}))} classes de sortida.",
            "reason": "És una capa derivada/proxy, no un model oficial de combustible validat.",
            "action": "Definir font oficial de combustible/estructura forestal i separar connector de dades de l'anàlisi.",
        },
        "meteocat": {
            "status": STATUS_CREDENTIALS,
            "data": "No retorna temperatura, precipitació, humitat ni vent dins EcoRadar.",
            "reason": "Requereix METEOCAT_API_KEY i selecció d'endpoint/estació o grid.",
            "action": "Obtenir clau Meteocat i implementar connector de consulta climàtica per bbox/estació propera.",
        },
        "aemet": {
            "status": STATUS_CREDENTIALS,
            "data": "No retorna normals, històrics ni prediccions AEMET dins EcoRadar.",
            "reason": "Requereix AEMET_API_KEY.",
            "action": "Obtenir clau AEMET i definir si s'usa com a complement o font principal fora de Catalunya.",
        },
        "spei": {
            "status": STATUS_NOT_IMPLEMENTED,
            "data": "No retorna índex SPEI dins EcoRadar.",
            "reason": "Accés automàtic/API o descàrrega per grid pendent de verificació.",
            "action": "Verificar font CSIC descarregable i crear connector de sequera per coordenada/grid.",
        },
        "field_validation": {
            "status": STATUS_UNAVAILABLE,
            "data": "No hi ha microhàbitats, punts sensibles ni validació de pressions importats.",
            "reason": "No s'ha proporcionat camp validat ni importador formal.",
            "action": "Definir plantilla de camp i connector d'importació per CSV/GPKG/media.",
        },
    }


def build_rows() -> list[dict[str, str]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    evidence = evidence_matrix()
    rows: list[dict[str, str]] = []
    for block in config.get("blocks", []):
        for source in block.get("sources", []):
            source_id = source["id"]
            item = evidence.get(source_id, {})
            status = status_for_credentials(source) or item.get("status", STATUS_NOT_IMPLEMENTED)
            rows.append(
                {
                    "bloc": block.get("name", ""),
                    "id": source_id,
                    "nom_font": source.get("name", ""),
                    "url_servei": source.get("url", ""),
                    "tipus": source.get("access_type", ""),
                    "estat": status,
                    "dades_que_retorna": item.get("data", "No comprovat dins EcoRadar."),
                    "indicadors_ecoradar": ", ".join(source.get("feeds_indicators", [])),
                    "motiu_si_falla": item.get("reason", source.get("error_message", "")),
                    "accio_necessaria": item.get("action", source.get("on_failure", "")),
                }
            )
    return rows


def write_outputs(rows: list[dict[str, str]]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project": "Alinya",
        "scope": "matriu de fonts del motor de recopilació; sense diagnosi ni indicadors nous",
        "status_legend": [STATUS_OK, STATUS_PARTIAL, STATUS_NOT_IMPLEMENTED, STATUS_CREDENTIALS, STATUS_UNAVAILABLE],
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Matriu de fonts EcoRadar - Alinyà",
        "",
        "Aquesta matriu audita només el motor de recopilació de dades. No genera diagnosi, fitxa ni nous indicadors.",
        "",
        "| Bloc | Font | URL / servei | Tipus | Estat | Dades que retorna | Indicadors | Motiu si falla | Acció necessària |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        values = [
            row["bloc"],
            row["nom_font"],
            row["url_servei"],
            row["tipus"],
            row["estat"],
            row["dades_que_retorna"],
            row["indicadors_ecoradar"],
            row["motiu_si_falla"],
            row["accio_necessaria"],
        ]
        escaped = [value.replace("|", "\\|").replace("\n", " ") for value in values]
        lines.append("| " + " | ".join(escaped) + " |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = build_rows()
    write_outputs(rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["estat"]] = counts.get(row["estat"], 0) + 1
    print(json.dumps({"rows": len(rows), "status_counts": counts, "outputs": [str(OUT_MD), str(OUT_CSV), str(OUT_JSON)]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
