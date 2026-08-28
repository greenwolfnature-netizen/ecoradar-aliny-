#!/usr/bin/env python3
"""Export Alinya EcoRadar as a Netlify-ready interactive package.

The package follows the EcoRadar Urba standalone structure:
index.html + local vendor/d3.min.js + docs + netlify.toml.

No connector is implemented here. The exporter only packages already generated
local EcoRadar layers and indicators.
"""

from __future__ import annotations

import base64
import csv
from collections import Counter, defaultdict
import json
import math
import shutil
import sqlite3
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
OUT_DIR = PROJECT / "maps" / "ecoradar-alinya-netlify-v2"
ZIP_PATH = PROJECT / "maps" / "ecoradar-alinya-netlify-v2.zip"
STANDALONE_HTML = PROJECT / "maps" / "ecoradar_alinya_interactiu-v2.html"
VENDOR_D3 = ROOT / "vendor" / "d3.min.js"
if not VENDOR_D3.is_file():
    VENDOR_D3 = ROOT / "projectes" / "LaSeu_Urba" / "maps" / "ecoradar-la-seu-netlify" / "vendor" / "d3.min.js"
REPORT_ENGINE = ROOT / "vendor" / "ecoradar-reading-report.js"
REPORT_PROFILES = ROOT / "vendor" / "ecoradar-alinya-report-profiles.js"
HTML2PDF = ROOT / "vendor" / "html2pdf.bundle.min.js"
HTML2PDF_LICENSE = ROOT / "vendor" / "html2pdf.bundle.min.js.LICENSE.txt"
BRANDING = PROJECT / "assets" / "branding"
if not BRANDING.is_dir():
    # Transitional fallback for the multi-project workspace. The standalone
    # Alinyà repository always contains its own copy under projectes/Alinya.
    BRANDING = ROOT / "projectes" / "LaSeu_Urba" / "assets" / "branding"
THIRD_PARTY_NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
if not THIRD_PARTY_NOTICES.is_file():
    THIRD_PARTY_NOTICES = (
        ROOT
        / "projectes"
        / "LaSeu_Urba"
        / "releases"
        / "ecoradar-la-seu-github-repository-complet"
        / "THIRD_PARTY_NOTICES.md"
    )
DAILY_FUNCTION = ROOT / "netlify" / "functions" / "daily-readings-alinya.mjs"
if not DAILY_FUNCTION.is_file():
    DAILY_FUNCTION = ROOT / "netlify" / "functions" / "daily-readings.mjs"


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def image_data_uri(path: Path) -> str:
    return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def asset_data_uri(path: Path) -> str:
    mime = {".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp"}.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def biodiversity_breakdown() -> dict:
    """Return record and taxon counts for the groups used in the full report."""
    connection = sqlite3.connect(PROJECT / "processed" / "biodiversitat.gpkg")
    try:
        processed = connection.execute(
            "SELECT source, source_record_id, scientificName, taxonGroup FROM biodiversitat"
        ).fetchall()
    finally:
        connection.close()

    taxonomy = {}
    for source_name, path in (
        ("GBIF", PROJECT / "raw" / "biodiversitat" / "gbif_raw.json"),
        ("iNaturalist", PROJECT / "raw" / "biodiversitat" / "inaturalist_raw.json"),
    ):
        for record in read_json(path).get("records", []):
            if source_name == "GBIF":
                record_id = str(record.get("gbifID") or record.get("key"))
                order = record.get("order")
                canonical = record.get("species") or record.get("acceptedScientificName") or record.get("scientificName")
            else:
                record_id = str(record.get("id"))
                taxon = record.get("taxon") or {}
                canonical = taxon.get("name")
                order = None
                for identification in record.get("identifications", []):
                    identified_taxon = identification.get("taxon") or {}
                    ancestors = identified_taxon.get("ancestors", [])
                    order = next((a.get("name") for a in ancestors if a.get("rank") == "order"), None)
                    if identified_taxon.get("rank") == "order":
                        order = identified_taxon.get("name")
                    if order:
                        break
            taxonomy[(source_name, record_id)] = (order, canonical)

    def category(group: str, order: str | None) -> str:
        if group == "Aves": return "Ocells"
        if order == "Lepidoptera": return "Papallones i arnes"
        if order == "Chiroptera": return "Ratpenats"
        if group == "Mammalia": return "Altres mamífers"
        if order == "Odonata": return "Odonats"
        if order == "Orthoptera": return "Ortòpters"
        if group == "Insecta": return "Altres insectes"
        if group in {"Reptilia", "Squamata"}: return "Rèptils"
        if group == "Amphibia": return "Amfibis"
        if group == "Arachnida": return "Aràcnids"
        if group == "Plantae": return "Flora"
        if group == "Fungi": return "Fongs i líquens"
        if group == "Mollusca": return "Mol·luscs"
        return "Altres grups"

    records = Counter()
    taxa = defaultdict(set)
    names = defaultdict(Counter)
    for source_name, record_id, scientific_name, taxon_group in processed:
        order, canonical = taxonomy.get((source_name, str(record_id)), (None, None))
        group = category(taxon_group or "", order)
        taxon_name = canonical or scientific_name or "Taxó no resolt"
        records[group] += 1
        taxa[group].add(taxon_name)
        names[group][taxon_name] += 1
    records.setdefault("Ratpenats", 0)
    taxa.setdefault("Ratpenats", set())
    return {
        "records": dict(records),
        "taxa": {key: len(value) for key, value in taxa.items()},
        "top": {key: value.most_common(6) for key, value in names.items()},
    }


def decimate(points: list, max_points: int) -> list:
    if len(points) <= max_points:
        return points
    step = max(1, math.ceil(len(points) / max_points))
    out = points[::step]
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def epsg25831_to_lonlat(x: float, y: float) -> list[float]:
    # Inverse UTM zone 31N on WGS84. Accuracy is enough for visualization.
    a = 6378137.0
    e = 0.08181919084262149
    e1sq = 0.006739496742276434
    k0 = 0.9996
    x -= 500000.0
    m = y / k0
    mu = m / (a * (1 - e**2 / 4 - 3 * e**4 / 64 - 5 * e**6 / 256))
    e1 = (1 - math.sqrt(1 - e**2)) / (1 + math.sqrt(1 - e**2))
    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1**2 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    c1 = e1sq * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = a * (1 - e**2) / ((1 - e**2 * math.sin(fp) ** 2) ** 1.5)
    n1 = a / math.sqrt(1 - e**2 * math.sin(fp) ** 2)
    d = x / (n1 * k0)
    q1 = n1 * math.tan(fp) / r1
    q2 = d**2 / 2
    q3 = (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e1sq) * d**4 / 24
    q4 = (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e1sq - 3 * c1**2) * d**6 / 720
    lat = fp - q1 * (q2 - q3 + q4)
    q5 = d
    q6 = (1 + 2 * t1 + c1) * d**3 / 6
    q7 = (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e1sq + 24 * t1**2) * d**5 / 120
    lon0 = math.radians(3.0)
    lon = lon0 + (q5 - q6 + q7) / math.cos(fp)
    return [round(math.degrees(lon), 6), round(math.degrees(lat), 6)]


def convert_coords(obj, max_points: int = 120):
    if obj is None:
        return None
    if isinstance(obj, list) and obj and isinstance(obj[0], (int, float)):
        if -180 <= float(obj[0]) <= 180 and -90 <= float(obj[1]) <= 90:
            return [round(float(obj[0]), 6), round(float(obj[1]), 6)]
        return epsg25831_to_lonlat(float(obj[0]), float(obj[1]))
    if isinstance(obj, list):
        items = decimate(obj, max_points) if obj and isinstance(obj[0], list) and obj[0] and isinstance(obj[0][0], (int, float)) else obj
        return [convert_coords(item, max_points) for item in items]
    return obj


def feature_collection(path: Path, *, max_points: int = 120, filter_fn=None, keep_props=None, limit=None) -> dict:
    data = read_json(path)
    features = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        if filter_fn and not filter_fn(props):
            continue
        if keep_props:
            props = {k: props.get(k) for k in keep_props}
        geom = feat.get("geometry") or {}
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": geom.get("type"),
                "coordinates": convert_coords(geom.get("coordinates"), max_points),
            },
        })
        if limit and len(features) >= limit:
            break
    return {"type": "FeatureCollection", "features": features}


def iter_points(obj):
    if isinstance(obj, list) and obj and isinstance(obj[0], (int, float)):
        yield (float(obj[0]), float(obj[1]))
        return
    if isinstance(obj, list):
        for item in obj:
            yield from iter_points(item)


def centroid_from_coords(coords) -> tuple[float, float]:
    pts = list(iter_points(coords))
    if not pts:
        return (0.0, 0.0)
    return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6371.0088
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def osm_highway_context_from_raw(map_bbox: list[float]) -> dict:
    """Build the unmasked OSM road/path context from the verified raw extract.

    The analytical access layer remains unchanged for EcoRadar metrics. This
    collection is only the cartographic context visible across the map frame.
    """
    raw = read_json(PROJECT / "raw" / "recreational_pressure" / "overpass_osm_raw.json")
    features = []
    for element in raw.get("elements", []):
        tags = element.get("tags") or {}
        geometry = element.get("geometry") or []
        if element.get("type") != "way" or not tags.get("highway") or len(geometry) < 2:
            continue
        coords = [[float(point["lon"]), float(point["lat"])] for point in geometry]
        xs = [point[0] for point in coords]
        ys = [point[1] for point in coords]
        if max(xs) < map_bbox[0] or min(xs) > map_bbox[2] or max(ys) < map_bbox[1] or min(ys) > map_bbox[3]:
            continue
        length_km = sum(haversine_km(tuple(a), tuple(b)) for a, b in zip(coords, coords[1:]))
        features.append({
            "type": "Feature",
            "properties": {
                "osm_id": element.get("id"),
                "highway": tags.get("highway"),
                "name": tags.get("name:ca") or tags.get("name"),
                "surface": tags.get("surface"),
                "access": tags.get("access"),
                "length_km": round(length_km, 4),
                "scope": "cartographic_context",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": decimate(coords, 120),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def projected_ring_area(coords: list) -> float:
    if len(coords) < 4:
        return 0.0
    area = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i][0], coords[i][1]
        x2, y2 = coords[i + 1][0], coords[i + 1][1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def projected_geom_area_ha(geom: dict) -> float:
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    area = 0.0
    if gtype == "Polygon":
        for idx, ring in enumerate(coords):
            area += projected_ring_area(ring) * (1 if idx == 0 else -1)
    elif gtype == "MultiPolygon":
        for poly in coords:
            for idx, ring in enumerate(poly):
                area += projected_ring_area(ring) * (1 if idx == 0 else -1)
    return max(0.0, area / 10000)


def class_from_score(score: float) -> str:
    if score >= 0.72:
        return "alta"
    if score >= 0.52:
        return "mitjana_alta"
    if score >= 0.34:
        return "mitjana"
    return "baixa"


def recent_fire_context(study_bbox: list[float]) -> dict:
    center = ((study_bbox[0] + study_bbox[2]) / 2, (study_bbox[1] + study_bbox[3]) / 2)
    effis_path = PROJECT / "raw" / "incendis" / "mapasdeincendios_effis_cataluna_2026_20260717.json"
    hotspots_path = PROJECT / "raw" / "incendis" / "mapasdeincendios_hotspots_cataluna_20260717.json"
    perimeters = []
    hotspots = []

    if effis_path.exists():
        payload = read_json(effis_path)
        for feat in payload.get("features", []):
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates")
            centroid = centroid_from_coords(coords)
            dist = haversine_km(center, centroid)
            is_recent_july = str(props.get("start_date", "")).startswith("2026-07")
            if is_recent_july and dist <= 60:
                perimeters.append({
                    "type": "Feature",
                    "properties": {
                        "name": props.get("name"),
                        "source": "Copernicus EFFIS via Mapasdeincendios.es",
                        "area_ha": props.get("area_ha"),
                        "start_date": props.get("start_date"),
                        "location_label": props.get("location_label"),
                        "distance_to_alinya_km": round(dist, 1),
                        "license": props.get("license"),
                    },
                    "geometry": feat.get("geometry"),
                })

    if hotspots_path.exists():
        payload = read_json(hotspots_path)
        for rec in payload.get("data", []):
            try:
                point = (float(rec["longitude"]), float(rec["latitude"]))
            except (KeyError, TypeError, ValueError):
                continue
            dist = haversine_km(center, point)
            if dist <= 60:
                hotspots.append({
                    "type": "Feature",
                    "properties": {
                        "municipality": rec.get("municipality"),
                        "source": rec.get("source_name", "NASA FIRMS"),
                        "observed_at": rec.get("observed_at"),
                        "frp": rec.get("frp"),
                        "confidence": rec.get("confidence"),
                        "location_label": rec.get("location_label"),
                        "distance_to_alinya_km": round(dist, 1),
                    },
                    "geometry": {"type": "Point", "coordinates": [round(point[0], 6), round(point[1], 6)]},
                })

    recent_points = []
    for feat in perimeters:
        recent_points.append(centroid_from_coords(feat["geometry"]["coordinates"]))
    for feat in hotspots:
        recent_points.append(tuple(feat["geometry"]["coordinates"]))

    return {
        "perimeters": {"type": "FeatureCollection", "features": perimeters},
        "hotspots": {"type": "FeatureCollection", "features": hotspots},
        "points": recent_points,
        "meta": {
            "nearby_effis": len(perimeters),
            "nearby_firms": len(hotspots),
            "method": "base_similarity_plus_recent_effis_firms_proximity",
        },
    }


def similarity_collection_with_recent(recent_points: list[tuple[float, float]]) -> tuple[dict, dict[str, float]]:
    path = PROJECT / "maps" / "incendis_similarity" / "similitud_condicions_incendi_alinya.geojson"
    data = read_json(path)
    features = []
    area_by_class = {"baixa": 0.0, "mitjana": 0.0, "mitjana_alta": 0.0, "alta": 0.0}
    keep_props = [
        "cell_id", "slope_deg", "aspect_class", "elevation_m",
        "distance_to_access_m", "cover_group", "similitud_score", "classe_similitud",
    ]
    for feat in data.get("features", []):
        raw_geom = feat.get("geometry") or {}
        geom = {
            "type": raw_geom.get("type"),
            "coordinates": convert_coords(raw_geom.get("coordinates"), 8),
        }
        centroid = centroid_from_coords(geom["coordinates"])
        base_score = float(feat.get("properties", {}).get("similitud_score", 0) or 0)
        nearest = min((haversine_km(centroid, p) for p in recent_points), default=None)
        recent_factor = 0.0 if nearest is None else max(0.0, (18.0 - nearest) / 18.0)
        updated_score = min(1.0, base_score + 0.14 * recent_factor)
        updated_class = class_from_score(updated_score)
        area_ha = projected_geom_area_ha(raw_geom)
        area_by_class[updated_class] += area_ha
        props = {k: feat.get("properties", {}).get(k) for k in keep_props}
        props.update({
            "base_classe_similitud": props.get("classe_similitud"),
            "classe_concurrencia_actualitzada": updated_class,
            "similitud_score_actualitzat": round(updated_score, 4),
            "factor_recent": round(recent_factor, 4),
            "distancia_foc_recent_km": None if nearest is None else round(nearest, 1),
        })
        features.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}, area_by_class


def bbox_from_fc(fc: dict) -> list[float]:
    xs, ys = [], []

    def walk(obj):
        if isinstance(obj, list) and obj and isinstance(obj[0], (int, float)):
            xs.append(obj[0]); ys.append(obj[1]); return
        if isinstance(obj, list):
            for item in obj:
                walk(item)

    for feat in fc["features"]:
        walk(feat["geometry"]["coordinates"])
    return [min(xs), min(ys), max(xs), max(ys)]


def merge_bboxes(*boxes: list[float] | None) -> list[float]:
    valid = [b for b in boxes if b]
    return [min(b[0] for b in valid), min(b[1] for b in valid), max(b[2] for b in valid), max(b[3] for b in valid)]


def source_matrix_md() -> str:
    src = PROJECT / "metadata" / "data_sources_matrix.md"
    if src.exists():
        return src.read_text(encoding="utf-8")
    rows = read_csv(PROJECT / "metadata" / "data_sources_matrix.csv")
    lines = ["# EcoRadar Alinyà — matriu de fonts", "", "| Domini | Font | Estat |", "| --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row.get('domain','')} | {row.get('source_name','')} | {row.get('status','')} |")
    return "\n".join(lines) + "\n"


def build_data() -> dict:
    study = feature_collection(
        PROJECT / "maps" / "ecoradar_core" / "study_area.geojson",
        max_points=650,
        keep_props=["hectares", "descripcio"],
    )
    study_bbox = bbox_from_fc(study)
    recent = {
        "perimeters": {"type": "FeatureCollection", "features": []},
        "hotspots": {"type": "FeatureCollection", "features": []},
        "points": [],
        "meta": {"nearby_effis": 0, "nearby_firms": 0, "method": "historic_fire_similarity_only"},
    }
    similarity, updated_similarity_areas = similarity_collection_with_recent([])
    fires = feature_collection(
        PROJECT / "maps" / "incendis" / "incendis_historics_alinya_clip.geojson",
        max_points=320,
        keep_props=["any_foc", "etiqueta_foc", "area_ha_dins_alinya", "font"],
    )
    hic = feature_collection(
        PROJECT / "maps" / "ecoradar_core" / "habitats_hic.geojson",
        max_points=80,
        filter_fn=lambda p: p.get("COD_HIC") not in (None, "", "-"),
        keep_props=["COD_CORINE", "CORINE_CA", "COD_HIC", "HIC_PRIOR"],
    )
    landcover = feature_collection(
        PROJECT / "maps" / "incendis" / "condicions_cobertes_alinya.geojson",
        max_points=160,
        keep_props=["condicio", "area_ha"],
    )
    biodiversity = feature_collection(
        PROJECT / "maps" / "ecoradar_core" / "biodiversitat_registres.geojson",
        max_points=1,
        keep_props=["scientificName", "taxonGroup", "source", "recordStatus"],
    )
    analytical_access = feature_collection(
        PROJECT / "maps" / "ecoradar_core" / "pressio_humana_osm_camins.geojson",
        max_points=120,
        keep_props=["highway", "surface", "access", "length_km"],
    )
    public_points = feature_collection(
        PROJECT / "maps" / "ecoradar_core" / "pressio_humana_osm_punts.geojson",
        max_points=1,
        keep_props=["name", "amenity", "tourism", "leisure", "highway"],
    )
    settlements = feature_collection(
        PROJECT / "maps" / "ecoradar_core" / "poblacions_osm.geojson",
        max_points=1,
        keep_props=["osm_id", "name", "place", "population", "population_date"],
    )
    road_highways = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "service"}
    roads_km = sum(
        float(feature["properties"].get("length_km") or 0)
        for feature in analytical_access["features"]
        if feature["properties"].get("highway") in road_highways
    )

    core = read_csv(PROJECT / "indicators" / "ecoradar_core_indicators.csv")
    basic = {r["indicador"]: r for r in read_csv(PROJECT / "indicators" / "ecoradar_01_resum.csv")}
    hydrology = read_csv(PROJECT / "indicators" / "hidrologia_resum.csv")
    connectivity = read_csv(PROJECT / "indicators" / "connectivitat_resum.csv")
    biodiversity_detail = biodiversity_breakdown()
    inc = {r["metric"]: r["value"] for r in read_csv(PROJECT / "indicators" / "incendis_resum.csv")}
    sim_rows = {r["metric"]: float(r["value"]) for r in read_csv(PROJECT / "indicators" / "incendis_similarity" / "similitud_condicions_resum.csv")}
    covers = read_csv(PROJECT / "indicators" / "cobertes_sol_resum.csv")
    sentinel = read_json(PROJECT / "indicators" / "teledeteccio_sentinel2.json")
    satellite = read_json(PROJECT / "indicators" / "teledeteccio_satellite_layers.json")
    integrated_fire = read_json(PROJECT / "indicators" / "perill_integrat_ecoradar.json")
    current_fire = read_json(PROJECT / "indicators" / "current_fire_danger.json")
    daily_readings = read_json(PROJECT / "indicators" / "daily_readings.json")
    daily_history = read_json(PROJECT / "indicators" / "daily_history.json")
    current_fire_cells = feature_collection(
        PROJECT / "maps" / "incendis" / "current_fire_danger_cells.geojson",
        max_points=8,
    )
    climate_refuges = read_json(PROJECT / "indicators" / "refugis_climatics_potencials.json")
    relief = read_json(PROJECT / "metadata" / "relleu_base_icgc_osm.json")
    map_bbox = relief.get("bbox_epsg4326", study_bbox)
    access_context = osm_highway_context_from_raw(map_bbox)
    raster_bbox = satellite.get("study_bbox_epsg4326", study_bbox)
    study_ha = 5464.13568486
    forest_like = sum(float(r["superficie_ha"]) for r in covers if any(t in r["tipus_coberta"].lower() for t in ["bosc", "boscos", "matollar"]))
    open_like = sum(float(r["superficie_ha"]) for r in covers if any(t in r["tipus_coberta"].lower() for t in ["prats", "conreus"]))
    high_plus = updated_similarity_areas.get("alta", 0) + updated_similarity_areas.get("mitjana_alta", 0)
    return {
        "bbox": map_bbox,
        "studyBbox": raster_bbox,
        "rasterBboxes": {
            "relief": map_bbox,
            "fireCurrent": current_fire["grid"]["bbox_epsg4326"],
        },
        "study": study,
        "branding": {
            "ecoradar": asset_data_uri(BRANDING / "ecoradar_logo.png"),
            "greenWolf": asset_data_uri(BRANDING / "green_wolf_nature_logo.png"),
        },
        "rasters": {
            "relief": image_data_uri(PROJECT / relief["output"]),
            "temperature": image_data_uri(PROJECT / satellite["outputs"]["temperature"]),
            "vegetation": image_data_uri(PROJECT / satellite["outputs"]["vegetation"]),
            "vigor": image_data_uri(PROJECT / sentinel["outputs"]["ndvi"]),
            "moisture": image_data_uri(PROJECT / sentinel["outputs"]["ndmi"]),
            "albedo": image_data_uri(PROJECT / sentinel["outputs"]["albedo"]),
            "fireDanger": image_data_uri(PROJECT / integrated_fire["outputs"]["webp"]),
            "fireCurrent": image_data_uri(PROJECT / "maps" / "incendis" / "current_fire_danger.webp"),
            "climateRefuges": image_data_uri(PROJECT / climate_refuges["outputs"]["webp"]),
        },
        "vectors": {
            "fires": fires,
            "recentPerimeters": recent["perimeters"],
            "recentHotspots": recent["hotspots"],
            "hic": hic,
            "landcover": landcover,
            "biodiversity": biodiversity,
            "access": access_context,
            "publicUse": public_points,
            "places": settlements,
        },
        "currentFire": {
            "checkedAtUtc": current_fire["checked_at_utc"],
            "status": current_fire["status"],
            "summary": current_fire["summary"],
            "weather": current_fire["weather"],
            "meteorology": current_fire.get("meteorology_context", {}),
            "plaAlfa": current_fire.get("pla_alfa", {}),
            "variables": current_fire["variables_today"],
            "weights": current_fire["weights"],
            "effectiveWeights": current_fire.get("effective_weights", current_fire["weights"]),
            "freshnessPolicy": current_fire.get("freshness_policy", {}),
            "normalization": current_fire["normalization"],
            "cells": current_fire_cells,
        },
        "dailyReadings": daily_readings,
        "dailyHistory": daily_history,
        "metrics": {
            "studyAreaHa": study_ha,
            "fires": int(float(inc["gencat_fire_polygons"])),
            "burnedHa": float(inc["gencat_burned_area_ha"]),
            "burnedPct": float(inc["gencat_burned_area_ha"]) / study_ha * 100,
            "concurrenceHighHa": high_plus,
            "concurrenceHighPct": high_plus / study_ha * 100,
            "fireIntegratedHighHa": integrated_fire["statistics"]["distribution"]["alt"]["area_ha"] + integrated_fire["statistics"]["distribution"]["molt_alt"]["area_ha"],
            "fireIntegratedHighPct": integrated_fire["statistics"]["distribution"]["alt"]["share_pct"] + integrated_fire["statistics"]["distribution"]["molt_alt"]["share_pct"],
            "fireIntegratedMedian": integrated_fire["statistics"]["median"],
            "climateRefugesHighPct": climate_refuges["high_or_very_high_share_of_vegetated_valid_pct"],
            "forestLikeHa": forest_like,
            "forestLikePct": forest_like / study_ha * 100,
            "openLikeHa": open_like,
            "openLikePct": open_like / study_ha * 100,
            "hicHa": 3170.95,
            "hicPriorHa": 1229.39,
            "records": 731,
            "species": 516,
            "habitats": int(float(basic["nombre_habitats"]["valor"])),
            "forestPct": float(basic["percentatge_coberta_forestal"]["valor"]),
            "grasslandPct": float(basic["percentatge_prats_pastures_herbassars"]["valor"]),
            "hydrologyKm": sum(float(r["length_km"]) for r in hydrology if r["layer_id"] in {"rius_aca_che", "eixos_drenatge"}),
            "springs": sum(int(r["feature_count"]) for r in hydrology if r["layer_id"] == "fonts"),
            "connectivityEntities": sum(int(r["feature_count"]) for r in connectivity),
            "connectorHa": sum(float(r["area_ha"]) for r in connectivity if r["layer_id"] in {"connectors_terrestres_principals", "zones_connectors_infraestructura_verda"}),
            "biodiversityGroups": biodiversity_detail,
            "pathsKm": 124.83,
            "roadsKm": roads_km,
            "publicPoints": 18,
            "settlements": len(settlements["features"]),
            "satellite": {
                "temperature": satellite["surface_temperature"]["metrics_c"],
                "temperatureDateRange": satellite["surface_temperature"]["date_range"],
                "temperatureSceneCount": satellite["surface_temperature"]["scene_count"],
                "temperatureCoveragePct": satellite["surface_temperature"]["coverage_pct"],
                "vegetationCoverHa": satellite["vegetation_cover"]["covered_area_ha"],
                "vegetationCoverPct": satellite["vegetation_cover"]["covered_pct"],
                "sentinelDate": sentinel["acquired_at_utc"],
                "ndvi": sentinel["metrics"]["ndvi"],
                "ndmi": sentinel["metrics"]["ndmi"],
                "albedo": sentinel["metrics"]["albedo"],
            },
            "fireOps": {
                "consulted": "17.07.2026",
                "latestRecord": "14.07.2026",
                "julyVegetationFires": 500,
                "julyForestFires": 154,
                "julyAgriculturalFires": 168,
                "julyUrbanVegetationFires": 178,
                "nearbyVegetationFires": 14,
                "nearbyCounties": "Alt Urgell, Cerdanya, Berguedà i Solsonès",
                "altUrgellNotes": "La Seu d'Urgell 04.07; Bassella 07.07 (2 actuacions)",
                "llinarsNote": "Llinars del Vallès 24.06.2026: incendi de vegetació urbana",
                "validation": "La fitxa interactiva mostra només perímetres històrics oficials consolidats dins l'àmbit.",
                "source": "Generalitat WFS VEGETACIO:VEGETACIO_INCENDIS, capa local processada",
                "plaAlfa": "Pla Alfa oficial municipal incorporat des de la vista pública 'Avui' del Cos d'Agents Rurals; conserva separades la data de la dada i la comprovació.",
                "satelliteSource": "Mapasdeincendios.es com a visor informatiu; fonts declarades: NASA FIRMS, Copernicus EFFIS, AEMET i MITECO/EGIF.",
                "satelliteUpdated": "La pàgina consultada el 17.07.2026 indica actualització 18.07.2026 00:00.",
                "activeNow": 13,
                "firms24h": 31,
                "firms7d": 31,
                "firmsLatest": "15.07.2026 04:43",
                "effis2026Perimeters": 53,
                "effis2026Ha": 4550.0,
                "frpMaxMw": 709.8,
                "recentSignals": [
                    "Santa Margarida i els Monjos, 15.07 04:43, detecció tèrmica",
                    "Sant Vicenç dels Horts, 15.07 03:58, detecció tèrmica",
                    "Montcada i Reixac, 15.07 03:58, detecció tèrmica",
                    "Alcanar, 15.07 03:05, possible, 2 deteccions",
                    "Aguilar de Segarra, 14.07 17:03, possible, 5 deteccions",
                    "Lladurs, 13.07 14:17, possible, 2 deteccions",
                ],
                "nearbyEffis": recent["meta"]["nearby_effis"],
                "nearbyFirms": recent["meta"]["nearby_firms"],
                "concurrenceUpdate": "La classe de concurrència es basa només en els perímetres històrics oficials d'Alinyà i les condicions territorials processades.",
            },
            "core": [
                {
                    "code": r["code"],
                    "name": r["name"],
                    "value": None if r["value_0_100"] == "" else float(r["value_0_100"]),
                    "display": f"NDVI {sentinel['metrics']['ndvi']['median']:.3f}" if r["code"] == "CORE_03" else None,
                    "status": "PARCIAL · escena 07.07.2026" if r["code"] == "CORE_03" else r["status"],
                    "confidence": "mitjana" if r["code"] == "CORE_03" else r["confidence"],
                }
                for r in core
            ],
        },
    }


def render_index(data: dict) -> str:
    d_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    ecoradar_logo = data["branding"]["ecoradar"]
    green_wolf_logo = data["branding"]["greenWolf"]
    return f"""<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EcoRadar · Muntanya d'Alinyà</title>
</head>
<body style="margin:0;background:#f4f1e9">

<div id="ecoradar-alinya" class="eu-shell">
  <style>
    #ecoradar-alinya {{
      --ink:#17332d; --blue:#154235; --green:#2f743f; --green-soft:#dfeadb;
      --paper:#f7f4ec; --panel:#fbfaf6; --line:#d7d1c4; --muted:#68747e;
      --orange:#d88932; --red:#b84c35; --purple:#68409a; --cyan:#1688bd;
      color:var(--ink); background:var(--paper); font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
      min-height:760px; border:1px solid #d8d1c4; box-sizing:border-box; overflow:hidden;
    }}
    #ecoradar-alinya * {{ box-sizing:border-box; }}
    #ecoradar-alinya .eu-head {{ position:relative; isolation:isolate; display:grid; grid-template-columns:minmax(280px,.9fr) minmax(430px,1.5fr) auto; gap:20px; align-items:end; overflow:hidden; padding:18px 20px 14px; border-bottom:1px solid #b8c8b9; background:linear-gradient(90deg,rgba(251,250,246,.98) 0%,rgba(239,245,235,.96) 55%,rgba(247,246,239,.98) 100%); }}
    #ecoradar-alinya .eu-head::before {{ content:""; position:absolute; z-index:-2; inset:-45px -20px -55px 43%; background:radial-gradient(circle at 57% 50%,transparent 0 35px,rgba(86,128,67,.16) 36px 37px,transparent 38px 63px,rgba(86,128,67,.13) 64px 65px,transparent 66px 92px,rgba(23,51,45,.10) 93px 95px,transparent 96px),conic-gradient(from 315deg at 57% 50%,transparent 0deg 305deg,rgba(132,164,72,.18) 306deg 338deg,transparent 339deg 360deg); }}
    #ecoradar-alinya .eu-head::after {{ content:""; position:absolute; z-index:-1; top:50%; right:186px; width:16px; height:16px; border:5px solid rgba(64,111,52,.16); border-radius:50%; background:rgba(47,116,63,.18); box-shadow:0 0 0 1px rgba(23,51,45,.08); transform:translateY(-50%); }}
    #ecoradar-alinya .eu-head > * {{ position:relative; z-index:1; }}
    #ecoradar-alinya h1 {{ margin:0; font-size:28px; line-height:.94; letter-spacing:.02em; color:var(--blue); }}
    #ecoradar-alinya h1 span {{ display:block; margin-top:7px; color:var(--green); font-size:31px; }}
    #ecoradar-alinya h1 small {{ display:block; margin-top:7px; color:#49645a; font-size:12px; line-height:1.15; letter-spacing:.08em; }}
    #ecoradar-alinya .eu-title h2 {{ margin:0; font-size:21px; letter-spacing:.055em; color:var(--blue); }}
    #ecoradar-alinya .eu-title p {{ margin:6px 0 0; font-size:11px; color:#384958; }}
    #ecoradar-alinya .eu-brand-stack {{ align-self:start; display:grid; justify-items:end; gap:6px; }}
    #ecoradar-alinya .eu-brand-logos {{ display:flex; align-items:center; gap:6px; }}
    #ecoradar-alinya .eu-brand-logos img {{ width:46px; height:46px; object-fit:contain; border:1px solid #d5dcd5; border-radius:6px; background:#fff; }}
    #ecoradar-alinya .eu-badge {{ border:1px solid #bfc8c1; border-radius:999px; padding:7px 10px; font-size:10px; color:#3e5260; background:#fffefa; white-space:nowrap; }}
    #ecoradar-alinya .eu-grid {{ display:grid; grid-template-columns:272px minmax(0,1fr); gap:10px; align-items:start; padding:10px; min-height:0; }}
    #ecoradar-alinya .eu-column {{ display:flex; flex-direction:column; gap:9px; min-width:0; }}
    #ecoradar-alinya .eu-map-stack {{ display:flex; flex-direction:column; gap:10px; min-width:0; }}
    #ecoradar-alinya .eu-column.eu-right {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; align-items:start; }}
    #ecoradar-alinya .eu-column.eu-right > .eu-panel {{ min-width:0; }}
    #ecoradar-alinya .eu-column.eu-right .eu-panel-wide {{ grid-column:1/-1; }}
    #ecoradar-alinya .eu-column.eu-right .eu-fire-summary-panel {{ grid-column:1; grid-row:2; }}
    #ecoradar-alinya .eu-column.eu-right .eu-fire-variables-panel {{ grid-column:1/-1; grid-row:3; }}
    #ecoradar-alinya .eu-column.eu-right .eu-fire-formula-panel {{ grid-column:2; grid-row:2; }}
    #ecoradar-alinya .eu-panel {{ background:rgba(255,255,255,.76); border:1px solid var(--line); padding:11px; }}
    #ecoradar-alinya .eu-panel h3 {{ margin:0 0 8px; color:var(--blue); font-size:11px; text-transform:uppercase; letter-spacing:.045em; }}
    #ecoradar-alinya .eu-panel p {{ margin:5px 0; font-size:10px; line-height:1.42; color:#425362; }}
    #ecoradar-alinya .eu-modes {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; }}
    #ecoradar-alinya button {{ font:inherit; }}
    #ecoradar-alinya .eu-mode, #ecoradar-alinya .eu-layer {{ border:1px solid #cad0ca; background:#fff; color:#29465d; border-radius:5px; padding:8px 7px; cursor:pointer; text-align:left; font-size:10px; transition:.15s ease; }}
    #ecoradar-alinya .eu-mode:hover, #ecoradar-alinya .eu-layer:hover {{ border-color:#6d8d7a; }}
    #ecoradar-alinya .eu-mode[aria-pressed="true"], #ecoradar-alinya .eu-layer[aria-pressed="true"] {{ color:#fff; background:var(--blue); border-color:var(--blue); }}
    #ecoradar-alinya .eu-mode small {{ display:block; opacity:.72; margin-top:2px; font-size:8px; }}
    #ecoradar-alinya .eu-context-panel {{ display:grid; grid-template-columns:minmax(210px,.9fr) minmax(0,2.1fr); gap:12px; align-items:center; padding:12px 14px; background:#eef1ea; }}
    #ecoradar-alinya .eu-context-intro h3 {{ margin-bottom:5px; }}
    #ecoradar-alinya .eu-context-intro p {{ margin:0; font-size:9px; line-height:1.4; }}
    #ecoradar-alinya .eu-context-status {{ display:block; margin-top:7px; color:var(--green); font-size:8px; font-weight:750; }}
    #ecoradar-alinya .eu-layer-list {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:6px; }}
    #ecoradar-alinya .eu-layer {{ display:grid; grid-template-columns:9px minmax(0,1fr); gap:2px 8px; align-items:center; min-height:45px; padding:7px 8px; }}
    #ecoradar-alinya .eu-layer strong {{ display:block; font-size:9px; line-height:1.15; }}
    #ecoradar-alinya .eu-layer small {{ display:block; grid-column:2; margin-top:1px; color:#6b7881; font-size:7px; line-height:1.2; }}
    #ecoradar-alinya .eu-layer[aria-pressed="true"] small {{ color:rgba(255,255,255,.76); }}
    #ecoradar-alinya .eu-dot {{ width:9px; height:9px; border-radius:2px; background:var(--dot); flex:none; }}
    #ecoradar-alinya .eu-facts {{ display:grid; gap:7px; }}
    #ecoradar-alinya .eu-fact {{ display:grid; grid-template-columns:1fr auto; gap:8px; align-items:baseline; padding-bottom:7px; border-bottom:1px solid #e5e1d8; }}
    #ecoradar-alinya .eu-fact:last-child {{ border-bottom:0; padding-bottom:0; }}
    #ecoradar-alinya .eu-fact span {{ font-size:9px; color:#51616e; }}
    #ecoradar-alinya .eu-fact strong {{ color:var(--green); font-size:14px; }}
    #ecoradar-alinya .eu-map-panel {{ position:relative; align-self:start; width:100%; height:auto; min-height:520px; max-height:680px; aspect-ratio:16/9; border:1px solid #cfc9bb; background:#e9ede5; overflow:hidden; }}
    #ecoradar-alinya .eu-map-head {{ position:absolute; z-index:4; top:10px; left:10px; right:10px; display:flex; justify-content:space-between; pointer-events:none; }}
    #ecoradar-alinya .eu-map-label {{ background:rgba(255,255,255,.9); border:1px solid #d5d0c4; padding:7px 9px; font-size:9px; color:#385064; box-shadow:0 3px 12px rgba(38,51,60,.08); }}
    #ecoradar-alinya .eu-reset {{ pointer-events:auto; border:1px solid #c9c4b8; background:rgba(255,255,255,.94); border-radius:4px; padding:7px 9px; color:var(--blue); cursor:pointer; font-size:9px; }}
    #ecoradar-alinya svg {{ display:block; width:100%; height:100%; min-height:0; cursor:grab; }}
    #ecoradar-alinya svg:active {{ cursor:grabbing; }}
    #ecoradar-alinya .eu-map-bg {{ fill:#edf0e9; }}
    #ecoradar-alinya .eu-study-fill {{ fill:#f3f1e8; stroke:none; }}
    #ecoradar-alinya .eu-boundary {{ fill:none; stroke:#123b31; stroke-width:1.8; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-boundary-outline {{ fill:none; stroke:#123b31; stroke-width:1.8; pointer-events:none; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-sim {{ stroke:rgba(70,70,55,.18); stroke-width:.35; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-sim.alta {{ fill:transparent; stroke:#b84c35; stroke-width:1.4; pointer-events:auto; }}
    #ecoradar-alinya .eu-sim.mitjana_alta {{ fill:transparent; stroke:#d88932; stroke-width:1.05; pointer-events:auto; }}
    #ecoradar-alinya .eu-sim.mitjana {{ fill:transparent; stroke:rgba(70,70,55,.10); stroke-width:.25; pointer-events:none; }}
    #ecoradar-alinya .eu-sim.baixa {{ fill:transparent; stroke:transparent; pointer-events:none; }}
    #ecoradar-alinya .eu-fire {{ fill:#c23c32; fill-opacity:.24; stroke:#a42220; stroke-width:2.2; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-fire-label {{ fill:#7d1c19; stroke:#fff; stroke-width:3px; paint-order:stroke; font-size:12px; font-weight:750; pointer-events:none; }}
    #ecoradar-alinya .eu-access {{ fill:none; stroke:#737b76; stroke-opacity:.72; stroke-width:.9; stroke-linecap:round; stroke-linejoin:round; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-access.eu-road {{ stroke:#a65f28; stroke-opacity:.95; stroke-width:2.3; }}
    #ecoradar-alinya .eu-place-dot {{ fill:#17332d; stroke:#fff; stroke-width:1.4; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-place-label {{ fill:#14395f; stroke:#fff; stroke-width:3px; paint-order:stroke; font-size:11px; font-weight:750; pointer-events:none; }}
    #ecoradar-alinya .eu-hic {{ fill:transparent; stroke:#1d5e3c; stroke-width:1; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-hic.prior {{ fill:transparent; stroke:#102f24; stroke-width:1.35; }}
    #ecoradar-alinya.mode-management .eu-hic {{ fill:#dfeadb; fill-opacity:.55; stroke:#2f743f; stroke-width:.9; cursor:pointer; }}
    #ecoradar-alinya.mode-management .eu-hic.prior {{ fill:#f3d7ad; fill-opacity:.7; stroke:#a85d16; stroke-width:1.55; }}
    #ecoradar-alinya.mode-management .eu-access {{ stroke:#6b716d; stroke-opacity:.72; }}
    #ecoradar-alinya .eu-landcover {{ stroke:rgba(255,255,255,.22); stroke-width:.35; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-landcover.bosc {{ fill:#2f743f; fill-opacity:.72; }}
    #ecoradar-alinya .eu-landcover.matollar {{ fill:#8ca34a; fill-opacity:.72; }}
    #ecoradar-alinya .eu-landcover.prats-i-herbassars {{ fill:#d8c76f; fill-opacity:.8; }}
    #ecoradar-alinya .eu-landcover.conreus {{ fill:#b88955; fill-opacity:.82; }}
    #ecoradar-alinya .eu-landcover.aigua {{ fill:#4d97b5; fill-opacity:.82; }}
    #ecoradar-alinya .eu-landcover.roquissars-sol-nu {{ fill:#b7afa0; fill-opacity:.78; }}
    #ecoradar-alinya .eu-landcover.vies-i-nuclis {{ fill:#785f64; fill-opacity:.82; }}
    #ecoradar-alinya .eu-bio {{ fill:#2d72a0; fill-opacity:.78; stroke:#fff; stroke-width:.8; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-public {{ fill:#1f2a27; stroke:#fff; stroke-width:1.2; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-map-note {{ position:absolute; left:10px; bottom:10px; z-index:4; max-width:360px; padding:7px 9px; background:rgba(255,255,255,.9); border:1px solid #d5d0c4; font-size:8px; line-height:1.35; color:#455662; }}
    #ecoradar-alinya .eu-legend {{ display:grid; gap:5px; font-size:9px; color:#445663; }}
    #ecoradar-alinya .eu-legend-row {{ display:flex; align-items:center; gap:7px; }}
    #ecoradar-alinya .eu-swatch {{ width:18px; height:9px; border:1px solid rgba(0,0,0,.12); }}
    #ecoradar-alinya .eu-guide-title {{ margin:0 0 6px; color:var(--green); font-size:12px; line-height:1.25; font-weight:700; }}
    #ecoradar-alinya .eu-guide-copy {{ margin:0 0 7px!important; color:#334d5d!important; }}
    #ecoradar-alinya .eu-guide-label {{ margin:9px 0 5px; color:var(--blue); font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:.035em; }}
    #ecoradar-alinya .eu-guide-reading {{ margin-top:8px!important; padding-top:7px; border-top:1px solid #e5e1d8; }}
    #ecoradar-alinya .eu-guide-limit {{ margin-top:7px!important; color:#6c5a47!important; }}
    #ecoradar-alinya .eu-reading-guide-horizontal {{ padding:13px 14px; }}
    #ecoradar-alinya .eu-reading-guide-horizontal > h3 {{ margin-bottom:10px; }}
    #ecoradar-alinya .eu-guide-horizontal-grid {{ display:grid; grid-template-columns:minmax(0,1.15fr) minmax(180px,.72fr) minmax(0,1.25fr); gap:16px; align-items:start; }}
    #ecoradar-alinya .eu-guide-horizontal-grid > div {{ min-width:0; }}
    #ecoradar-alinya .eu-guide-horizontal-grid .eu-guide-label {{ margin-top:0; }}
    #ecoradar-alinya .eu-guide-horizontal-grid .eu-guide-reading {{ margin-top:0!important; padding-top:0; border-top:0; }}
    #ecoradar-alinya .eu-generate-report {{ width:100%; min-height:38px; margin-top:12px; padding:8px 12px; border:1px solid var(--green); border-radius:5px; color:#fff; background:var(--green); font:700 10px/1.2 Arial,sans-serif; cursor:pointer; }}
    #ecoradar-alinya .eu-generate-report:hover, #ecoradar-alinya .eu-generate-report:focus-visible {{ background:var(--blue); border-color:var(--blue); outline:2px solid #91a99d; outline-offset:2px; }}
    body.err-modal-open {{ overflow:hidden; }}
    #ecoradar-alinya .err-modal {{ position:fixed; inset:0; z-index:9999; display:grid; place-items:center; padding:18px; background:rgba(18,47,73,.72); }}
    #ecoradar-alinya .err-modal[hidden] {{ display:none; }}
    #ecoradar-alinya .err-dialog {{ display:grid; grid-template-rows:auto minmax(0,1fr) auto; width:min(980px,100%); height:min(92vh,900px); overflow:hidden; border:1px solid #c9c4b8; border-radius:9px; background:#f7f4ec; box-shadow:0 22px 70px rgba(0,0,0,.35); }}
    #ecoradar-alinya .err-toolbar {{ display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 16px; border-bottom:1px solid var(--line); background:#fff; }}
    #ecoradar-alinya .err-toolbar h2 {{ margin:0; color:var(--blue); font-size:15px; }}
    #ecoradar-alinya .err-close, #ecoradar-alinya .err-pdf {{ min-height:34px; padding:7px 11px; border:1px solid var(--blue); border-radius:5px; color:var(--blue); background:#fff; font:700 9px Arial,sans-serif; cursor:pointer; }}
    #ecoradar-alinya .err-pdf {{ color:#fff; background:var(--blue); }}
    #ecoradar-alinya .err-preview {{ overflow:auto; padding:22px; }}
    #ecoradar-alinya .err-document {{ max-width:760px; margin:auto; color:#334d5d; background:#fff; box-shadow:0 5px 24px rgba(0,0,0,.08); }}
    #ecoradar-alinya .err-document > section, #ecoradar-alinya .err-document > footer {{ padding:18px 28px; }}
    #ecoradar-alinya .err-cover {{ display:flex; justify-content:space-between; gap:20px; min-height:160px; padding:28px; border-top:12px solid var(--green); background:#edf4ea; }}
    #ecoradar-alinya .err-cover span {{ color:var(--green); font-size:9px; font-weight:800; letter-spacing:.12em; }}
    #ecoradar-alinya .err-cover h1 {{ margin:24px 0 5px; color:var(--blue); font-size:27px; line-height:1.05; }}
    #ecoradar-alinya .err-cover p, #ecoradar-alinya .err-date {{ margin:0; color:#53636d; font-size:9px; }}
    #ecoradar-alinya .err-metadata, #ecoradar-alinya .err-facts {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }}
    #ecoradar-alinya .err-metadata > div, #ecoradar-alinya .err-fact {{ min-width:0; padding:10px; border:1px solid var(--line); }}
    #ecoradar-alinya .err-metadata b, #ecoradar-alinya .err-metadata span, #ecoradar-alinya .err-fact span, #ecoradar-alinya .err-fact strong, #ecoradar-alinya .err-fact small {{ display:block; overflow-wrap:anywhere; }}
    #ecoradar-alinya .err-metadata b, #ecoradar-alinya .err-fact span {{ color:#64727d; font-size:8px; text-transform:uppercase; }}
    #ecoradar-alinya .err-metadata span {{ margin-top:4px; font-size:11px; }}
    #ecoradar-alinya .err-fact strong {{ margin-top:4px; color:var(--green); font-size:16px; }}
    #ecoradar-alinya .err-synthesis {{ margin:0 28px; padding:18px!important; border-left:4px solid var(--green); background:#edf4ea; }}
    #ecoradar-alinya .err-synthesis h2 {{ border-color:#b8c8b9; }}
    #ecoradar-alinya .err-relations {{ display:grid; gap:8px; }}
    #ecoradar-alinya .err-diagnostic-grid, #ecoradar-alinya .err-sector-grid, #ecoradar-alinya .err-management-grid, #ecoradar-alinya .err-evolution {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px; }}
    #ecoradar-alinya .err-diagnostic-card, #ecoradar-alinya .err-chain-step, #ecoradar-alinya .err-sector, #ecoradar-alinya .err-management, #ecoradar-alinya .err-evolution article {{ padding:11px; border:1px solid var(--line); border-radius:5px; background:#fff; }}
    #ecoradar-alinya .err-chain {{ display:grid; gap:8px; counter-reset:chain; }}
    #ecoradar-alinya .err-chain-step {{ position:relative; padding-left:39px; }}
    #ecoradar-alinya .err-chain-step::before {{ counter-increment:chain; content:counter(chain); position:absolute; left:11px; top:11px; width:20px; height:20px; border-radius:50%; display:grid; place-items:center; color:#fff; background:var(--green); font:700 9px Arial,sans-serif; }}
    #ecoradar-alinya .err-diagnostic-card strong, #ecoradar-alinya .err-sector strong, #ecoradar-alinya .err-management strong, #ecoradar-alinya .err-evolution strong {{ display:block; color:var(--blue); font-size:11px; }}
    #ecoradar-alinya .err-diagnostic-card small, #ecoradar-alinya .err-sector small, #ecoradar-alinya .err-management small {{ display:block; margin-top:5px; color:#687682; font-size:9px; line-height:1.45; }}
    #ecoradar-alinya .err-evidence {{ display:inline-block; width:max-content; margin:0 5px 5px 0; padding:3px 7px; border-radius:99px; color:#315842; background:#e9f2e8; font:700 8px Arial,sans-serif; text-transform:uppercase; letter-spacing:.04em; }}
    #ecoradar-alinya .err-evidence-probable {{ color:#7a4d17; background:#fff0d8; }}
    #ecoradar-alinya .err-evidence-potencial {{ color:#68409a; background:#f1edf6; }}
    #ecoradar-alinya .err-fire-assessment {{ margin:0 28px; padding:18px!important; border-left:5px solid #c66d24; background:#fff3e5; }}
    #ecoradar-alinya .err-conclusion {{ margin:0 28px; padding:18px!important; border-left:5px solid var(--green); background:#edf4ea; }}
    #ecoradar-alinya .err-relation {{ padding:11px 12px; border:1px solid var(--line); background:#fbfaf6; }}
    #ecoradar-alinya .err-relation > div {{ display:flex; justify-content:space-between; gap:12px; align-items:baseline; }}
    #ecoradar-alinya .err-relation strong {{ color:var(--blue); font-size:11px; }}
    #ecoradar-alinya .err-relation span, #ecoradar-alinya .err-relation small {{ color:#6b7881; font-size:9px; }}
    #ecoradar-alinya .err-relation p {{ margin:7px 0 5px; }}
    #ecoradar-alinya .err-unverified {{ margin:0 28px; padding:16px!important; border-left:4px solid #7b858c; background:#f3f1ed; }}
    #ecoradar-alinya .err-document h2 {{ margin:0 0 8px; padding-bottom:5px; border-bottom:1px solid var(--line); color:var(--blue); font-size:14px; text-transform:none; letter-spacing:0; }}
    #ecoradar-alinya .err-document p, #ecoradar-alinya .err-document li {{ color:#3d5261; font-size:11px; line-height:1.55; }}
    #ecoradar-alinya .err-map-frame, #ecoradar-alinya .err-map {{ break-inside:avoid; page-break-inside:avoid; }}
    #ecoradar-alinya .err-map-frame {{ display:block; }}
    #ecoradar-alinya .err-map {{ height:340px; overflow:hidden; border:1px solid var(--line); background:#eef1ea; }}
    #ecoradar-alinya .err-map svg {{ width:100%; height:100%; }}
    #ecoradar-alinya .err-limits {{ margin:0 28px; padding:16px!important; border-left:4px solid var(--orange); background:#fff6e8; }}
    #ecoradar-alinya .err-document footer {{ border-top:1px solid var(--line); color:#687682; font-size:8px; }}
    #ecoradar-alinya .err-actions {{ display:flex; justify-content:flex-end; align-items:center; gap:8px; padding:10px 16px; border-top:1px solid var(--line); background:#fff; }}
    #ecoradar-alinya .err-status {{ margin-right:auto; color:#8a3f20; font-size:8px; }}
    #ecoradar-alinya #eu-reading-guide {{ min-height:0; }}
    #ecoradar-alinya #eu-legend {{ min-height:0; align-content:start; }}
    #ecoradar-alinya .eu-source {{ font-size:8px!important; color:#74808a!important; }}
    #ecoradar-alinya .eu-warning {{ border-left:3px solid var(--orange); padding-left:8px; }}
    #ecoradar-alinya .eu-current {{ border-left:3px solid var(--red); padding-left:8px; }}
    #ecoradar-alinya .eu-tooltip {{ position:absolute; z-index:10; pointer-events:none; opacity:0; background:#122f49; color:#fff; border-radius:4px; padding:7px 8px; max-width:245px; font-size:9px; line-height:1.35; box-shadow:0 8px 24px rgba(0,0,0,.18); }}
    #ecoradar-alinya .eu-fire-cell {{ fill:transparent; stroke:rgba(255,255,255,.08); stroke-width:.2; cursor:pointer; vector-effect:non-scaling-stroke; }}
    #ecoradar-alinya .eu-fire-cell:hover, #ecoradar-alinya .eu-fire-cell:focus {{ fill:rgba(255,255,255,.18); stroke:#fff; stroke-width:1.2; outline:none; }}
    #ecoradar-alinya .eu-fire-popup {{ position:absolute; z-index:12; top:54px; right:12px; width:min(390px,calc(100% - 24px)); max-height:calc(100% - 90px); overflow:auto; padding:13px; border:1px solid #c9c4b8; border-radius:6px; background:rgba(255,255,255,.97); color:#354b5a; box-shadow:0 12px 30px rgba(0,0,0,.2); font-size:10px; line-height:1.4; }}
    #ecoradar-alinya .eu-fire-popup[hidden], #ecoradar-alinya [data-current-fire][hidden], #ecoradar-alinya [data-management][hidden] {{ display:none; }}
    #ecoradar-alinya .eu-fire-popup-close {{ float:right; border:0; border-radius:4px; padding:3px 7px; color:#fff; background:var(--blue); cursor:pointer; }}
    #ecoradar-alinya .eu-fire-popup h3 {{ margin:0 38px 5px 0; color:var(--blue); font-size:13px; text-transform:none; letter-spacing:0; }}
    #ecoradar-alinya .eu-fire-popup-main {{ margin:5px 0 9px; color:var(--red); font-size:18px; font-weight:800; }}
    #ecoradar-alinya .eu-fire-popup.is-management .eu-fire-popup-main {{ color:var(--green); font-size:14px; }}
    #ecoradar-alinya .eu-fire-popup table {{ width:100%; border-collapse:collapse; margin:8px 0; }}
    #ecoradar-alinya .eu-fire-popup th, #ecoradar-alinya .eu-fire-popup td {{ padding:5px 4px; border-bottom:1px solid #e5e1d8; text-align:left; vertical-align:top; }}
    #ecoradar-alinya .eu-fire-popup th {{ color:var(--blue); font-size:8px; text-transform:uppercase; }}
    #ecoradar-alinya .eu-fire-summary {{ display:grid; grid-template-columns:1fr auto; gap:7px 8px; align-items:baseline; }}
    #ecoradar-alinya .eu-fire-summary span {{ color:#51616e; font-size:9px; }}
    #ecoradar-alinya .eu-fire-summary strong {{ color:var(--green); font-size:12px; text-align:right; }}
    #ecoradar-alinya .eu-fire-areas {{ display:grid; gap:4px; margin-top:9px; }}
    #ecoradar-alinya .eu-fire-area {{ display:grid; grid-template-columns:11px 1fr auto; gap:6px; align-items:center; font-size:9px; }}
    #ecoradar-alinya .eu-fire-area i {{ width:11px; height:8px; border-radius:2px; }}
    #ecoradar-alinya .eu-fire-table-wrap {{ overflow-x:auto; }}
    #ecoradar-alinya .eu-fire-table {{ min-width:560px; width:100%; border-collapse:collapse; font-size:8px; }}
    #ecoradar-alinya .eu-fire-table th, #ecoradar-alinya .eu-fire-table td {{ padding:5px; border:1px solid #ded9cf; text-align:left; vertical-align:top; }}
    #ecoradar-alinya .eu-fire-table th {{ color:#fff; background:var(--blue); }}
    #ecoradar-alinya .eu-fire-weights {{ margin:7px 0 0; padding-left:17px; color:#425362; font-size:9px; line-height:1.45; }}
    #ecoradar-alinya .eu-live-status {{ margin:0 0 9px; padding:7px 9px; border-left:3px solid #8a9aa6; background:#f3f5f6; color:#425362; font-size:9px; line-height:1.35; }}
    #ecoradar-alinya .eu-live-status.is-live {{ border-left-color:#2f7b50; background:#edf6ef; color:#285a3c; }}
    #ecoradar-alinya .eu-live-status.is-fallback {{ border-left-color:#c2832d; background:#fff6e8; color:#75501f; }}
    #ecoradar-alinya .eu-foot {{ grid-column:1/-1; display:flex; justify-content:space-between; gap:12px; border-top:1px solid var(--line); padding:7px 11px 1px; font-size:8px; color:#687682; }}
    #ecoradar-alinya .eu-report-nav {{ position:sticky; top:0; z-index:20; display:flex; gap:5px; overflow-x:auto; padding:8px 10px; border-bottom:1px solid var(--line); background:rgba(247,244,236,.96); backdrop-filter:blur(8px); scrollbar-width:thin; }}
    #ecoradar-alinya .eu-report-nav a {{ flex:none; padding:7px 10px; border:1px solid #cbd1c9; border-radius:999px; color:var(--blue); background:#fff; font-size:9px; font-weight:650; text-decoration:none; }}
    #ecoradar-alinya .eu-report-nav a:hover, #ecoradar-alinya .eu-report-nav a:focus-visible {{ color:#fff; background:var(--blue); outline:none; }}
    #ecoradar-alinya .eu-report {{ border-top:1px solid var(--line); background:#f7f4ec; }}
    #ecoradar-alinya .eu-report-section {{ scroll-margin-top:52px; padding:42px max(20px,calc((100% - 1160px)/2)); border-bottom:1px solid var(--line); }}
    #ecoradar-alinya .eu-section-kicker {{ margin:0 0 8px; color:var(--green); font-size:10px; font-weight:800; letter-spacing:.09em; text-transform:uppercase; }}
    #ecoradar-alinya .eu-report-section h2 {{ max-width:850px; margin:0; color:var(--blue); font-size:clamp(24px,3vw,38px); line-height:1.04; }}
    #ecoradar-alinya .eu-lead {{ max-width:880px; margin:13px 0 24px; color:#385064; font-size:14px; line-height:1.6; }}
    #ecoradar-alinya .eu-card-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }}
    #ecoradar-alinya .eu-card-grid.eu-two {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
    #ecoradar-alinya .eu-card-grid.eu-four {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
    #ecoradar-alinya .eu-report-card {{ min-width:0; padding:18px; border:1px solid var(--line); border-radius:8px; background:rgba(255,255,255,.76); }}
    #ecoradar-alinya .eu-report-card.green {{ background:#eef5eb; }}
    #ecoradar-alinya .eu-report-card.blue {{ background:#eaf2f5; }}
    #ecoradar-alinya .eu-report-card.orange {{ background:#fbf0df; }}
    #ecoradar-alinya .eu-report-card h3 {{ margin:0 0 9px; color:var(--blue); font-size:14px; text-transform:none; letter-spacing:0; }}
    #ecoradar-alinya .eu-report-card p, #ecoradar-alinya .eu-report-card li {{ color:#405563; font-size:11px; line-height:1.55; }}
    #ecoradar-alinya .eu-report-card ul {{ margin:8px 0 0; padding-left:18px; }}
    #ecoradar-alinya .eu-big {{ display:block; margin-bottom:5px; color:var(--green); font-size:27px; font-weight:800; line-height:1; }}
    #ecoradar-alinya .eu-subtle {{ color:#73808a!important; font-size:9px!important; }}
    #ecoradar-alinya .eu-data-table {{ width:100%; border-collapse:collapse; margin-top:16px; background:#fff; font-size:10px; }}
    #ecoradar-alinya .eu-data-table th, #ecoradar-alinya .eu-data-table td {{ padding:9px 10px; border:1px solid #ded9cf; text-align:left; vertical-align:top; line-height:1.4; }}
    #ecoradar-alinya .eu-data-table th {{ color:#fff; background:var(--blue); font-size:9px; letter-spacing:.035em; text-transform:uppercase; }}
    #ecoradar-alinya .eu-data-table td.num {{ color:var(--green); font-weight:800; white-space:nowrap; }}
    #ecoradar-alinya .eu-score-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:9px; margin-top:16px; }}
    #ecoradar-alinya .eu-score {{ padding:13px; border:1px solid var(--line); background:#fff; }}
    #ecoradar-alinya .eu-score-head {{ display:flex; justify-content:space-between; gap:8px; color:#415461; font-size:10px; }}
    #ecoradar-alinya .eu-score strong {{ color:var(--green); font-size:16px; }}
    #ecoradar-alinya .eu-score-track {{ height:5px; margin-top:8px; overflow:hidden; border-radius:9px; background:#e4e1d9; }}
    #ecoradar-alinya .eu-score-fill {{ height:100%; background:var(--green); }}
    #ecoradar-alinya .eu-status {{ display:inline-block; margin-top:8px; padding:3px 6px; border-radius:999px; background:#edf1ec; color:#506159; font-size:8px; text-transform:uppercase; }}
    #ecoradar-alinya details.eu-detail {{ margin-top:10px; border:1px solid var(--line); background:#fff; }}
    #ecoradar-alinya details.eu-detail summary {{ cursor:pointer; padding:12px 14px; color:var(--blue); font-size:11px; font-weight:750; }}
    #ecoradar-alinya details.eu-detail > div {{ padding:0 14px 14px; color:#405563; font-size:10px; line-height:1.55; }}
    #ecoradar-alinya .eu-callout {{ margin-top:16px; padding:14px 16px; border-left:4px solid var(--orange); background:#fff8ed; color:#5c5145; font-size:11px; line-height:1.55; }}
    #ecoradar-alinya .eu-executive {{ padding-top:52px; border-top:5px solid var(--green); border-bottom:1px solid #b9c8b8; background:linear-gradient(180deg,#edf4ea 0%,#f7f4ec 100%); text-align:center; }}
    #ecoradar-alinya .eu-executive-intro {{ position:relative; max-width:960px; margin:0 auto 30px; padding:0 36px 30px; }}
    #ecoradar-alinya .eu-executive-intro::after {{ content:""; position:absolute; left:50%; bottom:0; width:min(420px,70%); height:1px; background:#9fb39f; transform:translateX(-50%); }}
    #ecoradar-alinya .eu-executive-head {{ display:flex; flex-direction:column; align-items:center; gap:14px; }}
    #ecoradar-alinya .eu-executive .eu-section-kicker {{ margin-bottom:0; font-size:11px; letter-spacing:.14em; }}
    #ecoradar-alinya .eu-executive .eu-lead {{ max-width:900px; margin:18px auto 22px; color:#294a3c; font-size:clamp(15px,1.5vw,19px); line-height:1.58; }}
    #ecoradar-alinya .eu-reading-path {{ width:min(720px,100%); padding:14px 20px; border:1px solid #bdcdbd; border-radius:10px; background:rgba(255,255,255,.8); }}
    #ecoradar-alinya .eu-reading-path strong {{ display:block; margin-bottom:6px; color:var(--blue); font-size:12px; }}
    #ecoradar-alinya .eu-reading-path p {{ margin:0; color:#405563; font-size:10px; line-height:1.5; }}
    #ecoradar-alinya .eu-actions {{ display:flex; flex-wrap:wrap; justify-content:center; gap:9px; margin:20px 0 0; }}
    #ecoradar-alinya .eu-action {{ display:inline-flex; align-items:center; min-height:40px; padding:9px 14px; border:1px solid var(--blue); border-radius:6px; color:#fff; background:var(--blue); font-size:10px; font-weight:750; text-decoration:none; }}
    #ecoradar-alinya .eu-action.secondary {{ color:var(--blue); background:#fff; }}
    #ecoradar-alinya .eu-exec-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:16px; }}
    #ecoradar-alinya .eu-exec-list {{ margin:0; padding-left:18px; }}
    #ecoradar-alinya .eu-exec-list li {{ margin:7px 0; }}
    #ecoradar-alinya .eu-fire-executive {{ text-align:center; }}
    #ecoradar-alinya .eu-fire-executive .eu-facts {{ max-width:1120px; margin:0 auto; }}
    #ecoradar-alinya .eu-fire-executive .eu-fact {{ grid-template-columns:minmax(0,1fr) minmax(0,1fr); align-items:center; padding:10px 12px; }}
    #ecoradar-alinya .eu-fire-executive .eu-fact span,
    #ecoradar-alinya .eu-fire-executive .eu-fact strong {{ text-align:center; overflow-wrap:anywhere; }}
    #ecoradar-alinya .eu-fire-executive .eu-source {{ max-width:1120px; margin:12px auto 0; text-align:center; }}
    #ecoradar-alinya .eu-evidence-table td:first-child {{ min-width:150px; }}
    #ecoradar-alinya .eu-evidence-table td:nth-child(2) {{ min-width:130px; }}
    #ecoradar-alinya .eu-evidence-table .eu-reading-state {{ white-space:normal; }}
    #ecoradar-alinya .eu-technical-intro {{ padding:18px max(20px,calc((100% - 1160px)/2)); border-top:1px solid var(--line); border-bottom:1px solid var(--line); background:#eef1ea; }}
    #ecoradar-alinya .eu-technical-intro strong {{ color:var(--blue); font-size:12px; }}
    #ecoradar-alinya .eu-technical-intro span {{ margin-left:8px; color:#53636d; font-size:10px; }}
    #ecoradar-alinya .eu-map-access-label {{ margin:0; padding:24px max(20px,calc((100% - 1160px)/2)) 0; color:var(--green); font-size:10px; font-weight:800; letter-spacing:.09em; text-transform:uppercase; background:var(--paper); }}
    #ecoradar-alinya .eu-fire-chapter {{ background:#f5f2eb; }}
    @media (max-width:1050px) {{ #ecoradar-alinya .eu-grid {{ grid-template-columns:230px minmax(0,1fr); }} #ecoradar-alinya .eu-map-panel {{ min-height:480px; }} #ecoradar-alinya .eu-foot {{ grid-column:1/-1; }} }}
    @media (max-width:900px) {{ #ecoradar-alinya .eu-guide-horizontal-grid {{ grid-template-columns:1fr 1fr; }} #ecoradar-alinya .eu-guide-interpretation {{ grid-column:1/-1; }} #ecoradar-alinya .eu-context-panel {{ grid-template-columns:1fr; }} #ecoradar-alinya .eu-layer-list {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} #ecoradar-alinya .eu-card-grid.eu-four, #ecoradar-alinya .eu-score-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
    @media (max-width:760px) {{ #ecoradar-alinya .eu-head {{ grid-template-columns:1fr; }} #ecoradar-alinya .eu-grid {{ grid-template-columns:1fr; }} #ecoradar-alinya .eu-column.eu-right {{ grid-template-columns:1fr; }} #ecoradar-alinya .eu-column.eu-right .eu-fire-summary-panel, #ecoradar-alinya .eu-column.eu-right .eu-fire-variables-panel, #ecoradar-alinya .eu-column.eu-right .eu-fire-formula-panel {{ grid-column:auto; grid-row:auto; }} #ecoradar-alinya .eu-map-panel {{ height:420px; min-height:420px; max-height:none; aspect-ratio:auto; }} #ecoradar-alinya .eu-card-grid, #ecoradar-alinya .eu-card-grid.eu-two, #ecoradar-alinya .eu-card-grid.eu-four, #ecoradar-alinya .eu-score-grid, #ecoradar-alinya .eu-exec-grid {{ grid-template-columns:1fr; }} #ecoradar-alinya .eu-executive-intro {{ padding-right:0; padding-left:0; }} #ecoradar-alinya .eu-report-section {{ padding:32px 14px; }} #ecoradar-alinya .eu-data-table {{ display:block; overflow-x:auto; }} #ecoradar-alinya .eu-technical-intro span {{ display:block; margin:5px 0 0; }} #ecoradar-alinya .eu-fire-executive .eu-fact {{ grid-template-columns:1fr; gap:4px; }} }}
    @media (max-width:760px) {{ #ecoradar-alinya .eu-guide-horizontal-grid {{ grid-template-columns:1fr; gap:10px; }} #ecoradar-alinya .eu-guide-interpretation {{ grid-column:auto; }} #ecoradar-alinya .eu-guide-horizontal-grid .eu-guide-reading {{ padding-top:8px; border-top:1px solid #e5e1d8; }} #ecoradar-alinya .err-modal {{ padding:0; }} #ecoradar-alinya .err-dialog {{ width:100%; height:100vh; border-radius:0; }} #ecoradar-alinya .err-preview {{ padding:8px; }} #ecoradar-alinya .err-cover {{ flex-direction:column; min-height:0; padding:20px; }} #ecoradar-alinya .err-cover h1 {{ margin-top:14px; font-size:22px; }} #ecoradar-alinya .err-metadata, #ecoradar-alinya .err-facts, #ecoradar-alinya .err-diagnostic-grid, #ecoradar-alinya .err-sector-grid, #ecoradar-alinya .err-management-grid, #ecoradar-alinya .err-evolution {{ grid-template-columns:1fr; }} #ecoradar-alinya .err-document > section, #ecoradar-alinya .err-document > footer {{ padding:15px 18px; }} #ecoradar-alinya .err-limits, #ecoradar-alinya .err-fire-assessment, #ecoradar-alinya .err-conclusion {{ margin:0 18px; }} #ecoradar-alinya .err-map {{ height:240px; }} }}
    @media (max-width:760px) {{ #ecoradar-alinya .err-synthesis, #ecoradar-alinya .err-unverified {{ margin:0 18px; }} #ecoradar-alinya .err-relation > div {{ align-items:flex-start; flex-direction:column; gap:2px; }} }}
    @media (max-width:760px) {{ #ecoradar-alinya .eu-layer-list {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
    @media print {{
      @page {{ size:A4 landscape; margin:10mm; }}
      body {{ background:#fff!important; }}
      #ecoradar-alinya {{ border:0; overflow:visible; print-color-adjust:exact; -webkit-print-color-adjust:exact; }}
      #ecoradar-alinya .eu-report-nav {{ display:none; }}
      #ecoradar-alinya .eu-head {{ break-after:avoid; }}
      #ecoradar-alinya .eu-executive {{ padding:7mm 0; break-before:auto!important; }}
      #ecoradar-alinya .eu-map-access-label {{ break-before:page; break-after:avoid; padding:3mm 0 0; }}
      #ecoradar-alinya .eu-grid {{ width:auto; padding:3mm 0 0; min-height:0; display:flex; flex-direction:column; break-inside:auto; }}
      #ecoradar-alinya .eu-map-stack {{ display:contents; }}
      #ecoradar-alinya .eu-map-panel {{ order:1; height:170mm; min-height:170mm; break-inside:avoid; }}
      #ecoradar-alinya svg {{ height:170mm; min-height:170mm; }}
      #ecoradar-alinya .eu-reading-guide-horizontal {{ order:2; break-before:page; }}
      #ecoradar-alinya .eu-column.eu-left {{ order:3; display:block; break-before:page; }}
      #ecoradar-alinya .eu-column.eu-right {{ order:4; display:grid; grid-template-columns:1fr 1fr; align-items:start; break-before:page; }}
      #ecoradar-alinya .eu-foot {{ order:5; }}
      #ecoradar-alinya .eu-report-section {{ padding:10mm 0; break-before:page; }}
      #ecoradar-alinya .eu-report-card, #ecoradar-alinya .eu-callout, #ecoradar-alinya tr {{ break-inside:avoid; }}
      #ecoradar-alinya details.eu-detail > div {{ display:block!important; }}
      #ecoradar-alinya .eu-actions {{ display:none; }}
      #ecoradar-alinya .eu-context-panel {{ display:none; }}
      #ecoradar-alinya .eu-foot {{ padding-top:3mm; }}
    }}
  </style>

  <header class="eu-head">
    <h1>ECORADAR<span>MUNTANYA D'ALINYÀ</span><small>DIAGNOSI ECOLÒGICA INTEGRADA</small></h1>
    <div class="eu-title"><h2>TERRITORI, BIODIVERSITAT I DECISIÓ</h2><p>Lectura executiva i diagnosi tècnica completa · fonts oficials i indicadors traçables</p></div>
    <div class="eu-brand-stack"><div class="eu-brand-logos" aria-label="EcoRadar i Green Wolf Nature"><img src="{ecoradar_logo}" alt="Logotip EcoRadar"><img src="{green_wolf_logo}" alt="Logotip Green Wolf Nature"></div><div class="eu-badge">Dades obertes · versió 20.07.2026</div></div>
  </header>

  <nav class="eu-report-nav" aria-label="Capítols de la fitxa interactiva">
    <a href="#resum">1 · Resum territorial</a><a href="#cartografia">Mapa interactiu</a><a href="#mosaic">2 · Mosaic i hàbitats</a><a href="#biodiversitat">3 · Biodiversitat</a><a href="#aigua">4 · Aigua i connectivitat</a><a href="#pressions">5 · Accessibilitat i ús públic</a><a href="#foc">6 · Foc i resiliència</a><a href="#gestio">7 · Prioritats de gestió</a><a href="#fonts">8 · Fonts i metodologia</a>
  </nav>

  <section class="eu-report-section eu-executive" id="resum">
    <div class="eu-executive-intro">
      <div class="eu-executive-head">
        <div><p class="eu-section-kicker">01 · Resum territorial</p></div>
        <aside class="eu-reading-path"><strong>Dues profunditats, una mateixa diagnosi</strong><p>Aquesta primera pantalla permet una lectura directiva en dos minuts. El mapa i els set capítols següents conserven íntegrament la lectura tècnica, les fitxes, les fonts, les capes i les limitacions.</p></aside>
      </div>
      <p class="eu-lead">La Muntanya d’Alinyà conserva una matriu forestal extensa, una elevada responsabilitat sobre hàbitats d’interès comunitari i una biodiversitat pública ben documentada. El procés territorial central és el tancament progressiu del paisatge: prats, herbassars, vores i ecotons tenen una funció desproporcionada com a hàbitat, espai de campeig i discontinuïtat del combustible.</p>
      <div class="eu-actions"><a class="eu-action" href="#cartografia">Explorar el mapa interactiu</a><a class="eu-action secondary" href="#gestio">Anar a les prioritats de gestió</a><a class="eu-action secondary" href="#mosaic">Començar la lectura tècnica</a></div>
    </div>
    <div class="eu-card-grid eu-four">
      <article class="eu-report-card"><span class="eu-big" id="report-area"></span><h3>Àmbit validat</h3><p>Base espacial comuna per a totes les capes, en ETRS89 / UTM 31N (EPSG:25831).</p></article>
      <article class="eu-report-card green"><span class="eu-big" id="report-forest"></span><h3>Coberta forestal</h3><p>Matriu dominant. La dada de coberta no descriu per si sola estructura, vigor ni combustible.</p></article>
      <article class="eu-report-card orange"><span class="eu-big" id="report-open"></span><h3>Prats i herbassars</h3><p>Peces escasses que poden mantenir ecotons, recursos florals i discontinuïtat funcional.</p></article>
      <article class="eu-report-card blue"><span class="eu-big" id="report-hic"></span><h3>Hàbitats HIC</h3><p>Responsabilitat de conservació que ha de filtrar qualsevol actuació transformadora.</p></article>
    </div>
    <article class="eu-report-card orange eu-fire-executive" style="margin-top:12px" aria-label="Situació actual del perill d'incendi">
      <h3>Situació d’incendi avui</h3>
      <div class="eu-facts">
        <div class="eu-fact"><span>Perill EcoRadar avui</span><strong id="report-fire-today"></strong></div>
        <div class="eu-fact"><span>Pla Alfa</span><strong id="report-pla-alfa"></strong></div>
        <div class="eu-fact"><span>Meteorologia</span><strong id="report-fire-weather"></strong></div>
        <div class="eu-fact"><span>Sequera acumulada</span><strong id="report-fire-drought"></strong></div>
        <div class="eu-fact"><span>Tendència</span><strong id="report-fire-trend"></strong></div>
        <div class="eu-fact"><span>Última actualització</span><strong id="report-fire-update"></strong></div>
      </div>
      <p class="eu-source">Pla Alfa és el nivell operatiu oficial municipal dels Agents Rurals. L’índex 0–100 és una lectura EcoRadar separada; no converteix el Pla Alfa en una puntuació ni n’inventa una resolució de 100 m.</p>
    </article>
    <div class="eu-exec-grid">
      <article class="eu-report-card green"><h3>Conclusions clau</h3><ul class="eu-exec-list"><li>Una base ecològica forta que demana governar el canvi, no transformar de manera general.</li><li>No es justifica una restauració generalitzada. Cal validar, actuar només si el camp confirma un problema funcional i fer seguiment de la resposta.</li><li>Fonts, drenatges, fondals i corredors poden concentrar funcions ecològiques durant la sequera, la calor o la recuperació postpertorbació.</li></ul></article>
      <article class="eu-report-card blue"><h3>Prioritats de gestió</h3><ul class="eu-exec-list"><li>P1 · Delimitar sectors candidats de referència i no-intervenció.</li><li>P2 · Restaurar processos de mosaic i connectivitat, prioritzant la retirada de pressions.</li><li>P3 · Inventariar i protegir processos hídrics, refugis i continuïtat de ribera.</li><li>P4 · Reduir pressions d’accés i ús públic abans d’augmentar infraestructura o capacitat de visita.</li></ul></article>
    </div>
    <div class="eu-callout"><strong>Decisió prioritària.</strong> Aplicar una regla de no-deteriorament; mantenir una xarxa d’espais oberts seleccionada per funció; validar al camp hàbitats, aigua, pressions i estructura forestal; i actuar només quan el benefici ecològic i el seguiment siguin explícits.</div>
  </section>

  <p class="eu-map-access-label">Accés cartogràfic · totes les capes i interaccions originals</p>

  <main class="eu-grid" id="cartografia">
    <aside class="eu-column eu-left">
      <section class="eu-panel">
        <h3>Lectura temàtica</h3>
        <div class="eu-modes" role="group" aria-label="Lectura principal">
          <button class="eu-mode" data-mode="base" aria-pressed="true">Mapa base<small>relleu + carreteres + poblacions</small></button>
          <button class="eu-mode" data-mode="habitats" aria-pressed="false">Hàbitats<small>HIC i prioritaris</small></button>
          <button class="eu-mode" data-mode="biodiversity" aria-pressed="false">Biodiversitat<small>registres públics</small></button>
          <button class="eu-mode" data-mode="vegetation" aria-pressed="false">Cobertura vegetal<small>Copernicus HRL · 2023</small></button>
          <button class="eu-mode" data-mode="vigor" aria-pressed="false">Vigor vegetal<small>NDVI · Sentinel-2</small></button>
          <button class="eu-mode" data-mode="moisture" aria-pressed="false">Humitat vegetal<small>NDMI · Sentinel-2</small></button>
          <button class="eu-mode" data-mode="climateRefuges" aria-pressed="false">Refugis climàtics<small>LST + NDMI + NDVI + aigua</small></button>
          <button class="eu-mode" data-mode="temperature" aria-pressed="false">Temperatura<small>Landsat 8/9 · estius 2025–2026</small></button>
          <button class="eu-mode" data-mode="albedo" aria-pressed="false">Albedo<small>Sentinel-2 · 07.07.2026</small></button>
          <button class="eu-mode" data-mode="management" aria-pressed="false">Cribratge de gestió<small>restriccions i validació</small></button>
          <button class="eu-mode" data-mode="fireDanger" aria-pressed="false">Perill d'incendi<small>Generalitat + LST + NDMI + cobertes</small></button>
          <button class="eu-mode" data-mode="fireCurrent" aria-pressed="false">Perill d'incendi avui<small id="eu-fire-current-date">darrera comprovació · índex EcoRadar 100 m</small></button>
          <button class="eu-mode" data-mode="fires" aria-pressed="false">Històric d'incendis<small>perímetres oficials</small></button>
        </div>
      </section>
    </aside>

    <div class="eu-map-stack">
    <section class="eu-map-panel" aria-label="Mapa interactiu EcoRadar de la Muntanya d'Alinyà">
      <div class="eu-map-head"><div class="eu-map-label" id="eu-active-label">Mapa base verificat</div><button class="eu-reset" type="button">Restablir vista</button></div>
      <svg role="img" aria-label="Mapa d'Alinyà amb relleu, carreteres, poblacions, incendis, hàbitats, biodiversitat i accessibilitat"></svg>
      <div class="eu-map-note">Arrossega per desplaçar i usa la roda per ampliar. Consulta la font, la data i els límits de cada lectura activa.</div>
      <div class="eu-tooltip"></div>
      <div class="eu-fire-popup" hidden aria-live="polite"></div>
    </section>

    <section class="eu-panel eu-reading-guide-horizontal" id="eu-reading-guide" aria-live="polite">
      <h3>Com llegir la capa activa</h3>
      <div class="eu-guide-horizontal-grid">
        <div class="eu-guide-explanation">
          <div class="eu-guide-title" id="eu-guide-title"></div>
          <p class="eu-guide-copy" id="eu-guide-copy"></p>
        </div>
        <div class="eu-guide-key">
          <div class="eu-guide-label">Clau de colors</div>
          <div class="eu-legend" id="eu-legend" role="list"></div>
        </div>
        <div class="eu-guide-interpretation">
          <p class="eu-guide-reading" id="eu-guide-reading"></p>
          <p class="eu-guide-limit" id="eu-guide-limit"></p>
          <button class="eu-generate-report" type="button" data-generate-reading-report>Generar informe</button>
        </div>
      </div>
    </section>

    <section class="eu-panel eu-context-panel" aria-label="Context cartogràfic superposable">
      <div class="eu-context-intro">
        <h3>Context cartogràfic superposable</h3>
        <p>Aquests elements només ajuden a situar i contrastar la lectura principal. Activar-los no crea una diagnosi nova, no modifica els valors de l’indicador i no substitueix «Com llegir la lectura activa».</p>
        <span class="eu-context-status" id="eu-context-status" aria-live="polite"></span>
      </div>
      <div class="eu-layer-list" role="group" aria-label="Superposicions de context">
        <button class="eu-layer" data-layer="hic" aria-pressed="false"><span class="eu-dot" style="--dot:#2f7b50"></span><strong>Hàbitats HIC</strong><small>restricció ecològica</small></button>
        <button class="eu-layer" data-layer="landcover" aria-pressed="false"><span class="eu-dot" style="--dot:#8ca34a"></span><strong>Cobertes ICGC</strong><small>mosaic físic</small></button>
        <button class="eu-layer" data-layer="biodiversity" aria-pressed="false"><span class="eu-dot" style="--dot:#2d72a0"></span><strong>Biodiversitat</strong><small>registres coneguts</small></button>
        <button class="eu-layer" data-layer="access" aria-pressed="true"><span class="eu-dot" style="--dot:#5d675f"></span><strong>Camins i pistes</strong><small>accessibilitat potencial</small></button>
        <button class="eu-layer" data-layer="places" aria-pressed="true"><span class="eu-dot" style="--dot:#17332d"></span><strong>Poblacions OSM</strong><small>orientació territorial</small></button>
        <button class="eu-layer" data-layer="publicUse" aria-pressed="false"><span class="eu-dot" style="--dot:#1f2a27"></span><strong>Ús públic OSM</strong><small>punts per validar</small></button>
        <button class="eu-layer" data-layer="fires" aria-pressed="false"><span class="eu-dot" style="--dot:#c23c32"></span><strong>Incendis oficials</strong><small>antecedent històric</small></button>
      </div>
    </section>

    <aside class="eu-column eu-right">
      <section class="eu-panel">
        <h3>Valors ecològics</h3>
        <div class="eu-facts">
          <div class="eu-fact"><span>HIC cartografiats</span><strong id="eu-hic-value"></strong></div>
          <div class="eu-fact"><span>HIC prioritaris</span><strong id="eu-hic-prior-value"></strong></div>
          <div class="eu-fact"><span>Registres biodiversitat</span><strong id="eu-records-value"></strong></div>
          <div class="eu-fact"><span>Espècies citades</span><strong id="eu-species-value"></strong></div>
          <div class="eu-fact"><span>Camins i pistes OSM</span><strong id="eu-paths-value"></strong></div>
        </div>
        <p class="eu-source">GBIF/iNaturalist són fonts oportunistes i no substitueixen inventari de camp.</p>
      </section>
      <section class="eu-panel">
        <h3>Lectura del mapa</h3>
        <p>Selecciona una lectura temàtica per obtenir la diagnosi. Les superposicions de context situades sota el mapa es poden activar o desactivar sense canviar la lectura, els valors ni l’informe generat.</p>
        <p><a href="#mosaic">Continuar amb el diagnòstic tècnic complet</a></p>
      </section>
      <section class="eu-panel eu-panel-wide" data-management hidden>
        <h3>Cribratge de gestió · què cal fer?</h3>
        <p class="eu-warning"><strong>Aquest mapa no delimita actuacions.</strong> Ordena comprovacions prèvies i assenyala on una decisió necessita més cautela o informació.</p>
        <div class="eu-facts">
          <div class="eu-fact"><span>HIC prioritaris · precaució reforçada</span><strong id="eu-management-hic-prior"></strong></div>
          <div class="eu-fact"><span>Camins i pistes · accés potencial</span><strong id="eu-management-access"></strong></div>
          <div class="eu-fact"><span>Punts d’ús públic · conflictes a validar</span><strong id="eu-management-public"></strong></div>
          <div class="eu-fact"><span>Perímetres històrics · context de pertorbació</span><strong id="eu-management-fires"></strong></div>
        </div>
        <ol class="eu-fire-weights">
          <li><strong>Primer:</strong> comprovar HIC i HIC prioritaris; clica un polígon per saber què representa i què no permet afirmar.</li>
          <li><strong>Després:</strong> contrastar accessos i punts d’ús públic al camp; indiquen accessibilitat potencial, no freqüentació ni pressió real.</li>
          <li><strong>Finalment:</strong> incorporar biodiversitat, estat de conservació, combustible, aigua i objectiu ecològic abans d’assignar qualsevol actuació.</li>
        </ol>
        <p class="eu-source">Resultat admissible: sector pendent de validació, no-intervenció preventiva o candidat a una actuació selectiva justificada. La capa no assigna territorialment cap d’aquestes decisions.</p>
      </section>
      <section class="eu-panel eu-fire-summary-panel" data-current-fire hidden>
        <h3>Perill d’avui · resum</h3>
        <div class="eu-live-status" id="eu-live-status" role="status" aria-live="polite">Consultant l’última comprovació remota…</div>
        <div class="eu-fire-summary" id="eu-fire-current-summary"></div>
        <div class="eu-fire-areas" id="eu-fire-current-areas"></div>
        <p class="eu-source" id="eu-fire-current-check"></p>
      </section>
      <section class="eu-panel eu-fire-variables-panel" data-current-fire hidden>
        <h3>Variables utilitzades avui</h3>
        <div class="eu-fire-table-wrap"><table class="eu-fire-table"><thead><tr><th>Variable</th><th>Valor</th><th>Font</th><th>Data</th><th>Pes</th><th>Estat</th></tr></thead><tbody id="eu-fire-current-variables"></tbody></table></div>
      </section>
      <section class="eu-panel eu-fire-formula-panel" data-current-fire hidden>
        <h3>Fórmula i interpretació</h3>
        <p>L’índex 0–100 combina components estructurals i condicions actuals. Les dades dinàmiques antigues perden pes gradualment o s’exclouen, i els pesos temporalment elegibles i disponibles es renormalitzen; mai no s’assigna un zero fictici.</p>
        <ul class="eu-fire-weights" id="eu-fire-current-weights"></ul>
        <p class="eu-source">Lectura analítica EcoRadar, no alerta oficial, Pla Alfa ni predicció d’ignició. Consulta cada cel·la per veure valors, contribucions i grau de completesa.</p>
      </section>
    </aside>
    </div>

    <footer class="eu-foot"><span>Fonts: Generalitat perill estructural 2024 i incendis · Meteocat XEMA · USGS Landsat 8/9 · Copernicus Sentinel-2/CLMS · ICGC · Hàbitats/HIC · ACA · GBIF/iNaturalist · OSM</span><span>EcoRadar Alinyà · versió 20.07.2026</span></footer>
  </main>

  <article class="eu-report" aria-label="Informe complet interactiu">
    <div class="eu-technical-intro"><strong>Lectura tècnica completa</strong><span>Es conserva tota la profunditat del diagnòstic, sense reduir textos, dades, fitxes, fonts, advertiments, capes ni funcionalitats.</span></div>

    <section class="eu-report-section" id="mosaic">
      <p class="eu-section-kicker">02 · Mosaic i hàbitats</p>
      <h2>Conservar el contrast del paisatge i protegir els valors sensibles</h2>
      <p class="eu-lead">L’extensió del bosc no és el problema per si mateixa. La vulnerabilitat apareix quan es perden espais oberts funcionals, ecotons i punts de baixa pertorbació. La cartografia mostra on hi pot haver responsabilitat ecològica, però l’estat local de conservació s’ha de confirmar sobre el terreny.</p>
      <div class="eu-card-grid eu-two">
        <article class="eu-report-card green"><h3>Mosaic, bosc i espais oberts</h3><p>Els prats i les vores poden sostenir pol·linitzadors, zones de caça per a ocells i ratpenats i espais de pastura que redueixen la continuïtat. Cal distingir espais oberts actius, abandonats, naturals o degradats abans de decidir-ne el tractament.</p><ul><li>Mantenir una xarxa connectada de prats, vores i ecotons.</li><li>Prioritzar funció i retorn ecològic, no una quota superficial.</li><li>Contrastar ús, propietat, manteniment i estat.</li></ul></article>
        <article class="eu-report-card blue"><h3>Hàbitats i zones sensibles</h3><p>La coexistència de 47 hàbitats i una superfície extensa d’HIC obliga a una gestió diferenciada. Una desbrossada pot recuperar un prat o eliminar estructura protectora; un camí pot ordenar l’ús o fragmentar un sector sensible.</p><ul><li>Aplicar HIC i HIC prioritaris com a filtre de prudència.</li><li>Validar els polígons coincidents amb actuacions o accessos.</li><li>Definir objectiu, risc i indicador abans d’intervenir.</li></ul></article>
      </div>
      <div class="eu-callout"><strong>Lectura de les cobertes forestals.</strong> «Boscos densos de coníferes» i «Boscos clars de coníferes» són etiquetes de cobertura; dens o clar indica el grau de cobertura arbòria. Permeten interpretar la continuïtat horitzontal de la coberta cartografiada, però no permeten afirmar estructura vertical, càrrega de combustible, estat sanitari ni qualitat d’hàbitat sense validació específica.</div>
      <div class="eu-score-grid" id="eu-core-scores" aria-label="Indicadors Radar EcoRadar"></div>
    </section>

    <section class="eu-report-section" id="biodiversitat">
      <p class="eu-section-kicker">03 · Biodiversitat detectada</p>
      <h2>Quins grups consten a les bases públiques i què permet afirmar cada recompte</h2>
      <p class="eu-lead">Els 731 registres normalitzats de GBIF i iNaturalist documenten presències i 516 taxons, però no estimen abundància, densitat de població ni riquesa completa. La distribució dels punts també reflecteix l’esforç desigual d’observació.</p>
      <table class="eu-data-table">
        <thead><tr><th>Grup</th><th>Observacions</th><th>Taxons</th><th>Lectura ecològica</th></tr></thead>
        <tbody id="eu-biodiversity-table"></tbody>
      </table>
      <div class="eu-card-grid eu-two" style="margin-top:12px">
        <article class="eu-report-card green"><h3>Taxons amb més registres</h3><p id="eu-top-birds"></p><p id="eu-top-leps"></p><p class="eu-subtle">El nombre entre parèntesis és el recompte de registres normalitzats, no una estimació poblacional.</p></article>
        <article class="eu-report-card orange"><h3>Buit rellevant: ratpenats</h3><p>No hi ha cap registre de Chiroptera entre les observacions normalitzades. Això no demostra absència: les plataformes visuals infrarepresenten aquest grup. Abans d’actuar sobre arbres vells, cavitats, edificacions o punts d’aigua calen detectors d’ultrasons, revisió de refugis i mostreig nocturn.</p></article>
      </div>
    </section>

    <section class="eu-report-section" id="aigua">
      <p class="eu-section-kicker">04 · Aigua, refugis climàtics i connectivitat</p>
      <h2>Refugis potencials i corredors s’han de llegir com un mateix sistema</h2>
      <p class="eu-lead">Fonts, drenatges, fondals i corredors poden concentrar funcions ecològiques durant la sequera, la calor o la recuperació postpertorbació.</p>
      <div class="eu-card-grid">
        <article class="eu-report-card blue"><span class="eu-big" id="report-water-km"></span><h3>Xarxa hídrica</h3><p>Cursos i eixos de drenatge cartografiats.</p></article>
        <article class="eu-report-card green"><span class="eu-big" id="report-springs"></span><h3>Fonts</h3><p>Presència oficial; permanència, qualitat, ombra i ús faunístic pendents de camp.</p></article>
        <article class="eu-report-card"><span class="eu-big" id="report-connectors"></span><h3>Entitats de connectivitat</h3><p>Capes oficials retallades dins l’àmbit.</p></article>
      </div>
      <details class="eu-detail"><summary>Què s’ha de validar abans de gestionar punts d’aigua o refugis?</summary><div>Inventariar permanència i cabal, qualitat, sediments, ombra, vegetació associada, ús per fauna i pressions. LST estival, NDMI i NDVI ja permeten una primera lectura espacial, però delimitar refugis climàtics exigeix sèries temporals, microclima i validació ecològica de camp.</div></details>
      <div class="eu-callout"><strong>Capa incorporada al mapa.</strong> La lectura «Refugis climàtics» mostra els sectors vegetats amb potencial relatiu alt o molt alt, que representen el <strong>{data['metrics']['climateRefugesHighPct']:.1f} %</strong> dels píxels vegetats amb dades vàlides. El blau fosc indica més coincidència de frescor superficial, NDMI i NDVI; la xarxa hídrica i les fonts orienten la validació funcional.</div>
    </section>

    <section class="eu-report-section" id="pressions">
      <p class="eu-section-kicker">05 · Accessibilitat i ús públic</p>
      <h2>L’accessibilitat és una oportunitat de gestió i una pressió potencial que cal mesurar</h2>
      <p class="eu-lead">La xarxa d’accessos pot facilitar gestió i emergència, però també pertorbació, erosió i ignició.</p>
      <div class="eu-card-grid eu-two">
        <article class="eu-report-card orange"><span class="eu-big" id="report-pressure"></span><h3>Accessibilitat potencial</h3><p>OSM no mesura visitants, soroll, gossos, erosió ni estacionalitat.</p></article>
        <article class="eu-report-card"><h3>Pressió coneguda i pressió real</h3><p>Els camins i els punts d’ús públic localitzen on cal observar, però no substitueixen comptatges, estacionalitat, incidències ni resposta ecològica.</p><p>Els 124,8 km representen camins i pistes cartografiats i els 18 punts representen elements d’ús públic registrats a OSM. Mostren accessibilitat potencial, no freqüentació ni pressió real, i serveixen per prioritzar la validació de possibles conflictes amb hàbitats o fauna.</p></article>
      </div>
      <div class="eu-callout"><strong>Llegenda del mapa.</strong> Línies grises: camins i pistes OSM (124,8 km). Punts foscos: elements d’ús públic OSM (18 punts). La seva coincidència amb hàbitats o registres de fauna indica on prioritzar la comprovació de camp; no quantifica l’ús ni l’impacte.</div>
      <details class="eu-detail"><summary>Com s’ha d’interpretar la pressió humana?</summary><div>Els 124,8 km de xarxa i els 18 punts d’ús són localitzadors de pressió potencial. La decisió exigeix comptatges i observació de l’activitat, la temporalitat i la resposta dels hàbitats o la fauna, especialment on coincideixen amb HIC, aigua, rapinyaires o corredors.</div></details>
    </section>

    <section class="eu-report-section eu-fire-chapter" id="foc">
      <p class="eu-section-kicker">06 · Foc i resiliència territorial</p>
      <p class="eu-subtle">Document postincendi · fitxes 10–14</p>
      <h2>Del precedent històric a una decisió professional, selectiva i verificable</h2>
      <p class="eu-subtle">MEMÒRIA DEL FOC · DIAGNOSI ECOLÒGICA POSTFOC · MOSAIC, CONCURRÈNCIA I DECISIÓ</p>
      <p class="eu-lead">Els dos perímetres oficials de 2000 i 2012 sumen 17,4 ha dins l’àmbit i aporten antecedents territorials per examinar coberta, relleu, orientació i accessibilitat. Aquesta memòria històrica es contrasta amb la vulnerabilitat estructural i amb la lectura actualitzada diàriament de meteorologia, sequera i estat de la vegetació. Són tres plans complementaris: cap d’ells, per separat, descriu severitat, probabilitat d’ignició, combustible real o resposta postfoc.</p>
      <div class="eu-card-grid eu-two">
        <article class="eu-report-card"><h3>Indicadors clau</h3><div class="eu-facts"><div class="eu-fact"><span>Àmbit analitzat</span><strong id="eu-area-value"></strong></div><div class="eu-fact"><span>Incendis oficials dins l'àmbit</span><strong id="eu-fires-value"></strong></div><div class="eu-fact"><span>Superfície cremada</span><strong id="eu-burned-value"></strong></div><div class="eu-fact"><span>Índex integrat alt / molt alt</span><strong id="eu-concurrence-value"></strong></div><div class="eu-fact"><span>Bosc + matollar</span><strong id="eu-forest-value"></strong></div><div class="eu-fact"><span>Prats + conreus</span><strong id="eu-open-value"></strong></div></div></article>
        <article class="eu-report-card orange"><h3>Missatge clau</h3><p><strong>El senyal estructural no és la superfície cremada, sinó la coincidència entre continuïtat bosc-matollar, accessibilitat i condicions topogràfiques semblants als focs històrics.</strong></p><p>La situació operativa del dia es llegeix separadament amb l’índex EcoRadar actual, meteorologia XEMA, acumulació de precipitació, ForestDrought, observacions satel·litàries amb control de frescor i Pla Alfa oficial com a context no numèric.</p><h3 style="margin-top:14px">Límit metodològic</h3><p>Ni el mapa estructural ni l’índex actual són una probabilitat oficial d’incendi. La decisió de tractament continua requerint combustible i humitat fina validats al camp, exposició, valors ecològics afectats i viabilitat de manteniment.</p></article>
      </div>
      <div class="eu-card-grid eu-two" style="margin-top:12px">
        <article class="eu-report-card green"><h3>Situació operativa actualitzada</h3><div class="eu-facts"><div class="eu-fact"><span>Perill EcoRadar avui</span><strong id="report-fire-chapter-today"></strong></div><div class="eu-fact"><span>Pla Alfa oficial</span><strong id="report-fire-chapter-pla"></strong></div><div class="eu-fact"><span>Meteorologia</span><strong id="report-fire-chapter-weather"></strong></div><div class="eu-fact"><span>Sequera acumulada</span><strong id="report-fire-chapter-drought"></strong></div><div class="eu-fact"><span>Tendència</span><strong id="report-fire-chapter-trend"></strong></div><div class="eu-fact"><span>Confiança</span><strong id="report-fire-chapter-confidence"></strong></div><div class="eu-fact"><span>Darrera comprovació</span><strong id="report-fire-chapter-update"></strong></div></div></article>
        <article class="eu-report-card blue"><h3>Què determina la lectura d’avui?</h3><p id="report-fire-chapter-dominants"></p><p id="report-fire-chapter-freshness"></p><p><strong>Interpretació de gestió:</strong> el valor diari serveix per graduar la urgència de comprovació, vigilància i preparació operativa. No converteix automàticament una cel·la en zona d’actuació silvícola: aquesta decisió ha de creuar HIC, biodiversitat, aigua, connectivitat, accessibilitat, combustible real i objectiu ecològic.</p></article>
      </div>
      <details class="eu-detail"><summary>Traçabilitat de totes les variables del perill d’incendi avui</summary><div><div class="eu-fire-table-wrap"><table class="eu-fire-table eu-evidence-table"><thead><tr><th>Variable</th><th>Valor</th><th>Data real</th><th>Pes efectiu</th><th>Estat temporal</th><th>Funció en la diagnosi</th></tr></thead><tbody id="report-fire-chapter-variables"></tbody></table></div><p>Temperatura de l’aire, precipitació recent i acumulada i Pla Alfa completen el context operatiu amb data pròpia; el Pla Alfa no entra numèricament a l’índex. Les dades dinàmiques massa antigues es mantenen visibles com a context, però no poden aportar el seu pes complet.</p></div></details>
      <article class="eu-report-card" style="margin-top:12px"><h3>Incendis històrics</h3><p><strong>Històric oficial:</strong> es mostren només els dos perímetres consolidats dins la Muntanya d’Alinyà: 2000 i 2012.</p><p><strong>Lectura territorial:</strong> la concurrència compara les condicions del mosaic, pendent, orientació, altitud i accessibilitat amb aquests perímetres històrics.</p><p><strong>Exclosos del mapa:</strong> registres operatius recents sense perímetre i deteccions satel·litàries puntuals. No s’utilitzen aquí per no barrejar context operatiu amb històric consolidat.</p><p class="eu-source">Font de geometria: Generalitat WFS VEGETACIO:VEGETACIO_INCENDIS, capa local processada al projecte. Consulta 17.07.2026.</p></article>
      <div class="eu-card-grid">
        <article class="eu-report-card green"><span class="eu-big">10</span><h3>Memòria del foc</h3><p>El senyal rellevant no és només la superfície cremada, sinó la coincidència local entre massa forestal, contacte bosc-matollar, relleu, accessos i discontinuïtats.</p></article>
        <article class="eu-report-card blue"><span class="eu-big">11</span><h3>Foc i territori</h3><p>L’índex integrat creua el producte oficial estructural amb LST, NDMI, cobertes i concurrència territorial. Ordena la prioritat de camp, però no és probabilitat d’ignició, perill diari ni comportament futur.</p></article>
        <article class="eu-report-card orange"><span class="eu-big">12</span><h3>Argumentari postincendi</h3><p>Falten estructura vertical, càrrega i continuïtat real del combustible, humitat, vent, sequera operativa, erosió, regeneració, mortalitat i afectació d’espècies.</p></article>
        <article class="eu-report-card"><span class="eu-big">13</span><h3>Evidència integrada</h3><p>HIC, biodiversitat, aigua, connectivitat i accessos condicionen qualsevol actuació. Cap variable decideix sola: la prioritat apareix quan les condicions i el retorn ecològic coincideixen.</p></article>
        <article class="eu-report-card green"><span class="eu-big">14</span><h3>Conclusions postincendi</h3><p>No es justifica una restauració generalitzada. Cal validar, actuar només si el camp confirma un problema funcional i fer seguiment de la resposta.</p></article>
        <article class="eu-report-card orange"><h3>Criteri professional</h3><p>Menys superfície, més precisió, més justificació i seguiment explícit. La decisió correcta pot ser actuar, esperar o no intervenir.</p></article>
      </div>
      <div class="eu-callout"><strong>Límit metodològic.</strong> La diagnosi postincendi no substitueix un projecte executiu, una avaluació de severitat ni el mostreig de combustible, humitat, erosió, HIC i fauna. El visor mostra només perímetres oficials consolidats dins d’Alinyà.</div>
    </section>

    <section class="eu-report-section" id="gestio">
      <p class="eu-section-kicker">07 · Prioritats de gestió</p>
      <h2>Decidir des dels processos ecològics: EUROPARC, gestió adaptativa i rewilding</h2>
      <p class="eu-lead">La finalitat no és conservar una fotografia fixa del paisatge, sinó reforçar integritat ecològica, connectivitat, resiliència i capacitat d’autoregulació. La intervenció és un mitjà temporal: s’escull el nivell mínim necessari i es revisa segons resultats.</p>
      <article class="eu-report-card blue"><h3>Decisions</h3><p><strong>Mantenir obert:</strong> prioritzar prats, feixes i pastura extensiva on redueixen combustible continu sense comprometre HIC.</p><p><strong>Trencar continuïtat:</strong> actuar selectivament on coincideixen accessos, bosc-matollar i concurrència alta o mitjana-alta.</p><p><strong>No sobreactuar:</strong> evitar restauració generalitzada si no hi ha erosió o recuperació lenta validada.</p></article>
      <div class="eu-card-grid" style="margin-top:12px">
        <article class="eu-report-card green"><h3>1 · Objectiu i diagnòstic</h3><p>Identificar l’objecte de conservació o el procés que es vol recuperar, el seu estat inicial, les pressions demostrades i l’escala territorial. No confondre descripció amb diagnòstic.</p></article>
        <article class="eu-report-card blue"><h3>2 · Trajectòria rewilding</h3><p>Definir una trajectòria futura viable, no una còpia rígida del passat: més processos naturals, permeabilitat, heterogeneïtat, interaccions ecològiques i menor dependència de manteniment continu.</p></article>
        <article class="eu-report-card orange"><h3>3 · Mesura i resultat</h3><p>Cap mesura sense objectiu explícit; cap objectiu sense indicador. Cal anticipar resultat, risc, responsable, recursos, calendari i llindar que obligaria a corregir o aturar.</p></article>
      </div>
      <h3 style="margin:22px 0 8px;color:#163f35">Escala d’intervenció ecològica: de menys a més intervenció</h3>
      <div class="eu-callout"><strong>Ús metodològic.</strong> Els nivells A-E serveixen per ordenar el grau mínim d’intervenció, des de protegir i no intervenir fins a la gestió intensiva justificada. És un criteri metodològic i encara no s’ha assignat territorialment a Alinyà; la taula orienta la decisió, però no és una zonificació ni permet assignar nivells sense dades verificades.</div>
      <table class="eu-data-table">
        <thead><tr><th>Opció preferent</th><th>Quan correspon</th><th>Aplicació a Alinyà</th><th>Condició de revisió</th></tr></thead>
        <tbody>
          <tr><td class="num">A · Protegir i no intervenir</td><td>Valors ben conservats, regeneració funcional i absència de pressió activa demostrada.</td><td>Candidats: HIC sensibles, refugis, obagues, sectors tranquils i processos de regeneració. La cartografia orienta; el camp delimita.</td><td>Canvi desfavorable d’hàbitat, aigua, regeneració, espècies indicadores o pressió.</td></tr>
          <tr><td class="num">B · Retirar la pressió</td><td>El sistema pot recuperar-se si s’elimina la causa de degradació.</td><td>Regular accessos, trepig, soroll, drenatges alterats o altres pressions abans de transformar l’hàbitat.</td><td>Si la recuperació espontània no assoleix la trajectòria i el termini definits.</td></tr>
          <tr><td class="num">C · Reactivar processos</td><td>Manca un procés ecològic clau o la connectivitat és insuficient.</td><td>Afavorir continuïtat fluvial, permeabilitat, fusta morta, regeneració natural i herbivoria/pastura extensiva compatible amb HIC i capacitat de càrrega.</td><td>Erosió, sobrepastura, deteriorament d’HIC, conflicte social o absència de resposta funcional.</td></tr>
          <tr><td class="num">D · Restauració activa focalitzada</td><td>Hi ha barrera, erosió, invasora, fallida de regeneració o risc funcional verificat que el sistema no resol sol.</td><td>Intervencions petites, reversibles i experimentals, amb sector de referència i seguiment abans/després.</td><td>Aturar o redissenyar si no millora l’indicador o apareixen efectes col·laterals.</td></tr>
          <tr><td class="num">E · Seguretat i gestió intensiva</td><td>Només quan exposició, combustible, perill i viabilitat de manteniment estan comprovats.</td><td>Tractaments de foc selectius on coincideixin índex integrat, estructura real de combustible, accessos i baixa afectació ecològica.</td><td>Revisió postactuació i postpertorbació; no perpetuar manteniment sense benefici demostrat.</td></tr>
        </tbody>
      </table>
      <div class="eu-callout"><strong>Marc metodològic.</strong> EUROPARC-España (2018, PDF pàg. 29–32) proposa territori com a sistema, successió ecològica, seguiment i gestió adaptativa. EUROPARC-España (2008, PDF pàg. 75–77 i 98) vincula objectiu, diagnòstic, mesura, resultat i avaluació, i admet un gradient entre no-intervenció i maneig actiu. El rewilding reforça processos autoregulats, connectivitat, context social i seguiment adaptatiu segons les <a href="https://portals.iucn.org/library/node/52582">directrius IUCN</a> i els <a href="https://doi.org/10.1111/cobi.13730">principis de Carver et al. (2021)</a>.</div>
      <h3 style="margin:22px 0 8px;color:#163f35">Programa inicial derivat del marc de decisió</h3>
      <table class="eu-data-table">
        <thead><tr><th>Prioritat</th><th>Horitzó</th><th>Actuació</th><th>Indicador de verificació</th></tr></thead>
        <tbody>
          <tr><td class="num">P1</td><td>0–6 mesos</td><td>Delimitar sectors candidats de referència i no-intervenció creuant HIC, refugis, aigua, tranquil·litat i regeneració.</td><td>Línia base, objectiu de procés i llindar de revisió per sector.</td></tr>
          <tr><td class="num">P2</td><td>0–18 mesos</td><td>Restaurar processos de mosaic i connectivitat; prioritzar retirada de pressions i herbivoria compatible abans que desbrossament recurrent.</td><td>Heterogeneïtat, permeabilitat i qualitat d’ecotons sense deteriorament d’HIC.</td></tr>
          <tr><td class="num">P3</td><td>0–12 mesos</td><td>Inventariar i protegir processos hídrics, refugis i continuïtat de ribera per permanència, estat, fauna i pressions.</td><td>Funcionalitat hídrica i resposta d’espècies o microhàbitats indicadors.</td></tr>
          <tr><td class="num">P4</td><td>0–18 mesos</td><td>Reduir pressions d’accés i ús públic abans d’augmentar infraestructura o capacitat de visita.</td><td>Comptatges, incidències i resposta de fauna o hàbitat abans/després.</td></tr>
          <tr><td class="num">P5</td><td>Abans d’actuar</td><td>Validar combustible, humitat fina, exposició i manteniment; intervenir només on el risc funcional i el benefici ecològic coincideixin.</td><td>Cap tractament basat només en índexs; resultat i efectes col·laterals mesurats.</td></tr>
        </tbody>
      </table>
      <div class="eu-card-grid" style="margin-top:12px">
        <article class="eu-report-card green"><h3>Camp ecològic</h3><p>Estat d’HIC i ecotons; estructura forestal i fusta morta; permanència i qualitat de l’aigua; espècies indicadores, microhàbitats i pressions reals.</p></article>
        <article class="eu-report-card blue"><h3>Sèries territorials</h3><p>Cobertes i espais oberts; vigor i humitat estival; perímetres oficials de foc; accessibilitat i actualitzacions cartogràfiques.</p></article>
        <article class="eu-report-card orange"><h3>Governança</h3><p>Responsable per indicador, data i versió de font, llindars acordats, registre d’actuacions i revisió anual o postpertorbació.</p></article>
      </div>
      <h3 style="margin:22px 0 8px;color:#163f35">Traçabilitat de les lectures variables actualitzades</h3>
      <p class="eu-lead">Les lectures variables no redefineixen cada dia els valors estructurals del territori. Serveixen per ajustar la situació operativa, detectar canvis i decidir quan cal validar o accelerar una actuació. La taula mostra la dada real disponible, la seva data i la funció concreta que té en la decisió.</p>
      <div class="eu-fire-table-wrap"><table class="eu-data-table eu-evidence-table"><thead><tr><th>Lectura</th><th>Valor i estat</th><th>Data real</th><th>Com entra en la diagnosi i la gestió</th></tr></thead><tbody id="eu-daily-decision-evidence"></tbody></table></div>
      <h3 style="margin:22px 0 8px;color:#163f35">Traçabilitat dels indicadors Radar</h3>
      <p class="eu-lead">Els dotze indicadors Radar sintetitzen dimensions diferents i no són dotze ordres d’actuació. La prioritat s’estableix quan diversos indicadors coincideixen, la font és adequada i el camp confirma una necessitat funcional.</p>
      <div class="eu-fire-table-wrap"><table class="eu-data-table eu-evidence-table"><thead><tr><th>Indicador</th><th>Valor, estat i confiança</th><th>Ús en la decisió</th></tr></thead><tbody id="eu-core-decision-evidence"></tbody></table></div>
    </section>

    <section class="eu-report-section" id="fonts">
      <p class="eu-section-kicker">08 · Fonts, metodologia i limitacions</p>
      <h2>La força de la diagnosi depèn tant de les dades incorporades com dels límits explícits</h2>
      <div class="eu-card-grid eu-two" style="margin-top:20px">
        <article class="eu-report-card"><h3>Fonts incorporades</h3><ul><li>Copernicus Sentinel-2 L2A: NDVI, NDMI i albedo del 07.07.2026.</li><li>Copernicus CLMS HRL 2023: densitat arbòria i coberta herbàcia.</li><li>USGS Landsat 8/9 C2 L2: composició de 20 escenes de temperatura superficial dels estius 2025–2026.</li><li>Generalitat: Mapa bàsic de perill d’incendi forestal 2024, hàbitats, HIC, infraestructura verda i incendis.</li><li>Meteocat XEMA, estació Y4 Alinyà: temperatura de l’aire, humitat relativa i precipitació; estació CJ Organyà: vent i ratxes com a context puntual a 9,2 km.</li><li>Cos d’Agents Rurals: Pla Alfa oficial municipal de Fígols i Alinyà, vista pública «Avui».</li><li>ICGC: cobertes del sòl i model d’elevacions.</li><li>ACA, GBIF, iNaturalist i OpenStreetMap: aigua, registres biològics i accessibilitat.</li><li>EcoRadar: potencial relatiu de refugi climàtic derivat de LST, NDMI i NDVI, amb pesos i llindars documentats.</li></ul></article>
        <article class="eu-report-card orange"><h3>Limitacions que afecten decisions</h3><ul><li>Hàbitats i punts d’aigua necessiten validació de camp.</li><li>GBIF/iNaturalist no permeten afirmar absències ni equivalen a cens.</li><li>OSM no mesura intensitat real de visitants.</li><li>NDVI i NDMI són instantànies; la LST és una composició estival i no una normal climàtica.</li><li>El perill integrat és una lectura analítica estructural; els pesos i el potencial de combustible per coberta requereixen contrast de camp.</li><li>La lectura de perill actual és un índex EcoRadar, no una alerta oficial ni el Pla Alfa; la humitat és puntual a Y4 i el vent és context puntual de CJ Organyà, a 9,2 km.</li><li>Qualsevol obra o tractament requereix projecte, permisos i validació específica.</li></ul></article>
      </div>
      <details class="eu-detail"><summary>Estat de publicació i validació</summary><div>Producte apte a escala de diagnosi. Els controls tècnics i de recomanacions del projecte estan superats; la validació ecològica manté limitacions explícites. Les entrades de l’informe complet es van validar el 08.07.2026 i la capa històrica d’incendis es va consultar el 17.07.2026.</div></details>
      <details class="eu-detail"><summary>Fórmula del perill d’incendi actual</summary><div><strong>Pesos base: 20% potencial de foc ForestDrought CREAF + 20% perill estructural oficial + 15% sequedat relativa NDMI + 10% temperatura superficial detallada + 10% continuïtat vegetal + 10% vent/ratxa + 10% humitat relativa baixa + 3% pendent + 2% orientació de solana.</strong> El pes efectiu de cada variable dinàmica depèn de la frescor real de la seva observació: és complet dins el termini propi de la font, disminueix linealment en el període recent i és zero quan la dada és massa antiga. Després es renormalitzen només els pesos efectius disponibles a cada cel·la; una absència o exclusió temporal mai no es transforma en risc zero. El component de vent usa el màxim normalitzat entre vent sostingut i ratxa disponibles. ForestDrought aplica 100 × max(SFP, CFP) / 9 només dins l’empremta forestal nativa de 500 × 500 m. Temperatura de l’aire, pluja recent, acumulacions de 7/30 dies i Pla Alfa s’expliquen com a contextos traçables amb escala i data pròpies; el Pla Alfa oficial municipal no es converteix en una puntuació EcoRadar.</div></details>
      <details class="eu-detail"><summary>Bibliografia de planificació, conservació i rewilding</summary><div><p><strong>EUROPARC-España (2018).</strong> <em>Las áreas protegidas en el contexto del cambio global: incorporación de la adaptación al cambio climático en la planificación y gestión</em>, 2a ed. Criteris utilitzats: territori com a sistema, incertesa, successió, connectivitat, seguiment i gestió adaptativa (pàgines PDF 29–32).</p><p><strong>EUROPARC-España (2008).</strong> <em>Planificar para gestionar los espacios naturales protegidos</em>. Cicle objectiu–diagnòstic–mesura–resultat–avaluació i gradient no-intervenció/maneig actiu (pàgines PDF 75–77 i 98).</p><p><strong>IUCN Commission on Ecosystem Management (2025).</strong> <a href="https://portals.iucn.org/library/node/52582"><em>Guidelines for rewilding</em></a>. <strong>Carver et al. (2021).</strong> <a href="https://doi.org/10.1111/cobi.13730"><em>Guiding principles for rewilding</em></a>, Conservation Biology 35:1882–1893.</p></div></details>
    </section>
  </article>
<div class="err-modal" data-reading-report-modal hidden role="dialog" aria-modal="true" aria-labelledby="err-dialog-title">
  <div class="err-dialog">
    <div class="err-toolbar"><div><small>Previsualització de l’informe</small><h2 id="err-dialog-title" data-reading-report-title></h2></div><button class="err-close" type="button" data-reading-report-close aria-label="Tancar l’informe">Tancar</button></div>
    <div class="err-preview" data-reading-report-preview></div>
    <div class="err-actions"><span class="err-status" data-reading-report-status aria-live="polite"></span><button class="err-close" type="button" data-reading-report-close>Tornar al mapa</button><button class="err-pdf" type="button" data-reading-report-pdf>Desar informe en PDF</button></div>
  </div>
</div>
</div>
<script src="./vendor/d3.min.js"></script>
<script src="./vendor/html2pdf.bundle.min.js"></script>
<script src="./vendor/ecoradar-reading-report.js"></script>
<script src="./vendor/ecoradar-alinya-report-profiles.js"></script>
<script>
(() => {{
  const root = document.getElementById('ecoradar-alinya');
  const D = {d_json};
  const printDetails = [...root.querySelectorAll('details.eu-detail')];
  const expandDetailsForPrint = () => printDetails.forEach(detail => {{
    detail.dataset.printWasOpen = String(detail.open);
    detail.open = true;
  }});
  const restoreDetailsAfterPrint = () => printDetails.forEach(detail => {{
    if (detail.dataset.printWasOpen === 'false') detail.open = false;
    delete detail.dataset.printWasOpen;
  }});
  window.addEventListener('beforeprint', expandDetailsForPrint);
  window.addEventListener('afterprint', restoreDetailsAfterPrint);
  if (window.matchMedia('print').matches) expandDetailsForPrint();
  const svg = d3.select(root).select('svg');
  const tooltip = d3.select(root).select('.eu-tooltip');
  const firePopup = root.querySelector('.eu-fire-popup');
  const width = 1000, height = 720;
  svg.attr('viewBox', `0 0 ${{width}} ${{height}}`).attr('preserveAspectRatio','xMidYMid meet');
  svg.append('rect').attr('class','eu-map-bg').attr('width',width).attr('height',height);
  const bboxFeature = {{type:'Feature',geometry:{{type:'Polygon',coordinates:[[[D.bbox[0],D.bbox[1]],[D.bbox[0],D.bbox[3]],[D.bbox[2],D.bbox[3]],[D.bbox[2],D.bbox[1]],[D.bbox[0],D.bbox[1]]]]}}}};
  const projection = d3.geoMercator().fitExtent([[18,18],[width-18,height-18]], bboxFeature);
  const path = d3.geoPath(projection);
  const defs = svg.append('defs');
  const studyClip = defs.append('clipPath').attr('id','eu-study-clip');
  studyClip.selectAll('path').data(D.study.features).join('path').attr('d',path);
  const scene = svg.append('g');
  scene.append('g').selectAll('path').data(D.study.features).join('path').attr('class','eu-study-fill').attr('d',path);
  const contextRasterGroup = scene.append('g').attr('class','eu-rasters eu-context-rasters');
  const analyticalRasterGroup = scene.append('g').attr('class','eu-rasters eu-analytical-rasters').attr('clip-path','url(#eu-study-clip)');
  const rasterGroups = {{}};
  Object.entries(D.rasters).forEach(([key,href]) => {{
    const rasterBbox = D.rasterBboxes?.[key] || D.studyBbox;
    const rasterTopLeft = projection([rasterBbox[0],rasterBbox[3]]);
    const rasterBottomRight = projection([rasterBbox[2],rasterBbox[1]]);
    const targetRasterGroup = key === 'relief' ? contextRasterGroup : analyticalRasterGroup;
    rasterGroups[key] = targetRasterGroup.append('image')
      .attr('href',href).attr('x',rasterTopLeft[0]).attr('y',rasterTopLeft[1])
      .attr('width',rasterBottomRight[0]-rasterTopLeft[0]).attr('height',rasterBottomRight[1]-rasterTopLeft[1])
      .attr('preserveAspectRatio','none').style('display','none').style('opacity',(key === 'fireDanger' || key === 'fireCurrent') ? 1 : .94);
  }});
  const vectorGroup = scene.append('g').attr('class','eu-vectors');
  const groups = {{}};
  groups.boundary = vectorGroup.append('g').selectAll('path').data(D.study.features).join('path').attr('class','eu-boundary').attr('d',path).on('mousemove',(event,d)=>showTip(event,'Límit Muntanya d\\'Alinyà')).on('mouseleave',hideTip);
  groups.fireCurrent = vectorGroup.append('g').attr('clip-path','url(#eu-study-clip)').style('display','none');
  function renderCurrentFireCells(cells) {{
    const features = cells?.features || [];
    groups.fireCurrent.selectAll('path').data(features, d => d.properties?.cell_id).join('path')
      .attr('class','eu-fire-cell').attr('d',path).attr('tabindex',0).attr('role','button')
      .attr('aria-label',d=>`Cel·la ${{d.properties.cell_id}}: índex ${{Number(d.properties.index_0_100).toFixed(1)}} sobre 100, ${{d.properties.category}}`)
      .on('mousemove',(event,d)=>showTip(event,`Cel·la ${{d.properties.cell_id}}<br><strong>${{Number(d.properties.index_0_100).toFixed(1).replace('.',',')}}/100 · ${{d.properties.category}}</strong><br>Clica per veure el detall`))
      .on('mouseleave',hideTip)
      .on('click',(event,d)=>{{ event.stopPropagation(); showFirePopup(d); }})
      .on('keydown',(event,d)=>{{ if (event.key === 'Enter' || event.key === ' ') {{ event.preventDefault(); showFirePopup(d); }} }});
  }}
  renderCurrentFireCells(D.currentFire.cells);
  const landcoverClass = value => ({{'Bosc':'bosc','Matollar':'matollar','Prats i herbassars':'prats-i-herbassars','Conreus':'conreus','Aigua':'aigua','Roquissars / sol nu':'roquissars-sol-nu','Vies i nuclis':'vies-i-nuclis'}}[value] || 'altres');
  groups.landcover = vectorGroup.append('g').attr('clip-path','url(#eu-study-clip)').style('display','none');
  groups.landcover.selectAll('path').data(D.vectors.landcover.features).join('path').attr('class',d=>`eu-landcover ${{landcoverClass(d.properties.condicio)}}`).attr('d',path).on('mousemove',(event,d)=>showTip(event,`${{d.properties.condicio}}<br>${{Number(d.properties.area_ha || 0).toFixed(1).replace('.',',')}} ha`)).on('mouseleave',hideTip);
  groups.fires = vectorGroup.append('g');
  groups.fires.selectAll('path').data(D.vectors.fires.features).join('path').attr('class','eu-fire').attr('d',path).on('mousemove',(event,d)=>showTip(event,`Incendi oficial ${{d.properties.any_foc || d.properties.etiqueta_foc}}<br>${{Number(d.properties.area_ha_dins_alinya).toFixed(1).replace('.',',')}} ha dins l'àmbit<br>${{d.properties.font || ''}}`)).on('mouseleave',hideTip);
  groups.fires.selectAll('text').data(D.vectors.fires.features).join('text').attr('class','eu-fire-label').attr('transform',d=>`translate(${{path.centroid(d)}})`).text(d=>d.properties.any_foc || d.properties.etiqueta_foc);
  const roadHighways = new Set(['motorway','trunk','primary','secondary','tertiary','unclassified','residential','living_street','service']);
  groups.access = vectorGroup.append('g');
  groups.access.selectAll('path').data(D.vectors.access.features).join('path').attr('class',d=>`eu-access ${{roadHighways.has(d.properties.highway) ? 'eu-road' : 'eu-track'}}`).attr('d',path).on('mousemove',(event,d)=>showTip(event,`${{roadHighways.has(d.properties.highway) ? 'Carretera' : 'Camí o pista'}} · ${{d.properties.highway || 'sense classe'}}<br>${{Number(d.properties.length_km || 0).toFixed(2).replace('.',',')}} km`)).on('mouseleave',hideTip);
  groups.hic = vectorGroup.append('g').style('display','none');
  groups.hic.selectAll('path').data(D.vectors.hic.features).join('path').attr('class',d=>`eu-hic ${{d.properties.HIC_PRIOR ? 'prior' : ''}}`).attr('d',path).attr('tabindex',0).on('mousemove',(event,d)=>showTip(event,`HIC ${{d.properties.COD_HIC}}<br>${{(d.properties.CORINE_CA || '').slice(0,120)}}${{root.classList.contains('mode-management') ? '<br><strong>Clica per interpretar la decisió</strong>' : ''}}`)).on('mouseleave',hideTip).on('click',(event,d)=>{{ if (root.classList.contains('mode-management')) {{ event.stopPropagation(); showManagementHicPopup(d); }} }}).on('keydown',(event,d)=>{{ if (root.classList.contains('mode-management') && (event.key === 'Enter' || event.key === ' ')) {{ event.preventDefault(); showManagementHicPopup(d); }} }});
  groups.biodiversity = vectorGroup.append('g').style('display','none');
  groups.biodiversity.selectAll('circle').data(D.vectors.biodiversity.features).join('circle').attr('class','eu-bio').attr('cx',d=>projection(d.geometry.coordinates)[0]).attr('cy',d=>projection(d.geometry.coordinates)[1]).attr('r',2.6).on('mousemove',(event,d)=>showTip(event,`${{d.properties.scientificName || 'Registre'}}<br>${{d.properties.taxonGroup || ''}} · ${{d.properties.source || ''}}`)).on('mouseleave',hideTip);
  groups.publicUse = vectorGroup.append('g').style('display','none');
  groups.publicUse.selectAll('circle').data(D.vectors.publicUse.features).join('circle').attr('class','eu-public').attr('cx',d=>projection(d.geometry.coordinates)[0]).attr('cy',d=>projection(d.geometry.coordinates)[1]).attr('r',4).on('mousemove',(event,d)=>showTip(event,d.properties.name || d.properties.tourism || d.properties.amenity || 'Punt OSM')).on('mouseleave',hideTip);
  const placeLabelLayout = {{
    'Alinyà':{{dx:-8,dy:-9,anchor:'end'}},
    'Llobera':{{dx:8,dy:13,anchor:'start'}},
    "l'Alzina d'Alinyà":{{dx:8,dy:-10,anchor:'start'}},
    'la Vall del Mig':{{dx:-8,dy:-10,anchor:'end'}},
    'les Sorts':{{dx:8,dy:15,anchor:'start'}}
  }};
  const placeLabel = d => placeLabelLayout[d.properties.name] || {{dx:7,dy:-7,anchor:'start'}};
  groups.places = vectorGroup.append('g');
  groups.places.selectAll('circle').data(D.vectors.places.features).join('circle').attr('class','eu-place-dot').attr('cx',d=>projection(d.geometry.coordinates)[0]).attr('cy',d=>projection(d.geometry.coordinates)[1]).attr('r',4).on('mousemove',(event,d)=>showTip(event,`${{d.properties.name}}<br>Nucli OSM · ${{d.properties.place}}${{d.properties.population == null ? '' : `<br>Població OSM: ${{d.properties.population}} · ${{d.properties.population_date || 'data no indicada'}}`}}`)).on('mouseleave',hideTip);
  groups.places.selectAll('text').data(D.vectors.places.features).join('text').attr('class','eu-place-label').attr('x',d=>projection(d.geometry.coordinates)[0]+placeLabel(d).dx).attr('y',d=>projection(d.geometry.coordinates)[1]+placeLabel(d).dy).attr('text-anchor',d=>placeLabel(d).anchor).text(d=>d.properties.name);
  vectorGroup.append('g').selectAll('path').data(D.study.features).join('path').attr('class','eu-boundary-outline').attr('d',path);

  const north = svg.append('g').attr('transform','translate(946 70)');
  north.append('path').attr('d','M0,24 L0,-16 M0,-16 L-6,-5 M0,-16 L6,-5').attr('stroke','#173249').attr('stroke-width',2).attr('fill','none');
  north.append('text').attr('y',-25).attr('text-anchor','middle').attr('font-size',13).attr('font-weight',700).text('N');

  const modeGuides = {{
    base: {{
      label:'Mapa base topogràfic · relleu, carreteres i poblacions',
      title:'Relleu real, xarxa viària i nuclis de referència',
      copy:`Combina l’ombrejat hipsomètric del model d’elevacions ICGC de 5 m amb la xarxa viària i els nuclis OSM de tot el rectangle cartogràfic. Dins l’àmbit analític s’han quantificat ${{Number(D.metrics.pathsKm).toFixed(1).replace('.',',')}} km de xarxa, dels quals ${{Number(D.metrics.roadsKm).toFixed(1).replace('.',',')}} km corresponen a carreteres classificades. L’altitud dins l’àmbit va aproximadament de 607 a 2.379 m.`,
      reading:'Els tons verds i ocres representen cotes relativament més baixes; els grisos i clars, cotes més elevades. El relleu, les carreteres, els camins i les poblacions continuen visibles dins i fora del contorn verd. El contorn identifica el límit de l’àmbit analític, no el límit del mapa base. Les línies taronges més gruixudes són carreteres; les grises fines, camins i pistes. Els punts foscos i les etiquetes identifiquen nuclis `place=hamlet` publicats a OSM.',
      limit:'Límit: el relleu, la xarxa viària i els topònims que es veuen fora del contorn són només context cartogràfic; les lectures i superfícies EcoRadar continuen restringides a l’àmbit validat. Els topònims i la classificació viària provenen d’OSM i no substitueixen cartografia oficial de navegació. Els punts de població situen el topònim, però no delimiten l’extensió urbana; les xifres de població només es mostren al detall quan OSM n’indica també la data.',
      layers:['access','places'],
      raster:'relief',
      legend:[['#b7c897','Cotes baixes i mitjanes'],['#e8e5da','Cotes més elevades'],['#a65f28','Carreteres OSM'],['#737b76','Camins i pistes OSM'],['#17332d','Poblacions i nuclis OSM']]
    }},
    fires: {{
      label:'Històric d’incendis oficial',
      title:'Perímetres històrics dins l’àmbit',
      copy:'Mostra els dos perímetres oficials retallats a la Muntanya d’Alinyà: 2000 i 2012.',
      reading:'La lectura torna als dos perímetres oficials dins l’àmbit. Són la base espacial per interpretar el patró de recurrència: no quantifiquen el risc actual, però sí on el foc ja ha coincidit amb determinades condicions del territori.',
      limit:'Límit: aquesta lectura històrica mostra exclusivament els perímetres consolidats d’Alinyà procedents de Generalitat WFS VEGETACIO:VEGETACIO_INCENDIS; no inclou registres sense perímetre oficial.',
      layers:['fires','access'],
      legend:[['#c23c32','Perímetres oficials Alinyà'],['#5d675f','Accessos']]
    }},
    habitats: {{
      label:'Hàbitats d’interès comunitari',
      title:'HIC com a restricció i valor de gestió',
      copy:'Afegeix HIC i HIC prioritaris per evitar que la prevenció del foc contradigui valors ecològics.',
      reading:'Les actuacions sobre combustible han de filtrar-se amb aquesta capa i validar-se al camp.',
      limit:'Límit: cartografia d’hàbitats no equival a estat de conservació verificat localment.',
      layers:['hic','fires','access'],
      legend:[['transparent','Contorn HIC'],['transparent','Contorn HIC prioritari'],['#c23c32','Incendis'],['#5d675f','Accessos']]
    }},
    biodiversity: {{
      label:'Biodiversitat coneguda',
      title:'Registres públics de biodiversitat',
      copy:'Mostra registres GBIF/iNaturalist disponibles dins l’àmbit.',
      reading:'Serveix per detectar coneixement disponible i buits, no per delimitar biodiversitat real completa.',
      limit:'Límit: fonts oportunistes; no substitueixen inventari de camp ni llistes normatives.',
      layers:['biodiversity','hic','fires'],
      legend:[['#2d72a0','Registres públics'],['transparent','Contorn HIC'],['#c23c32','Incendis']]
    }},
    management: {{
      label:'Cribratge de gestió · comprovacions abans d’actuar',
      title:'On cal validar més abans de decidir',
      copy:'Superposa només quatre evidències verificades: HIC com a filtre de compatibilitat ecològica, camins i punts d’ús públic com a accessibilitat potencial, i perímetres d’incendi com a context històric. No són polígons de proposta ni zones on EcoRadar ordeni intervenir.',
      reading:'Verd clar: HIC que exigeix comprovar compatibilitat i estat al camp. Taronja: HIC prioritari, amb precaució reforçada. Gris: camins i pistes, sense informació de freqüentació. Negre: punts d’ús públic OSM on cal validar possibles conflictes. Vermell: antecedent d’incendi, no risc actual. Clica un HIC per consultar la seva funció en la decisió.',
      limit:'Límit: aquesta lectura no assigna prioritat, actuació, no-intervenció ni escala A–E a cap sector. Abans de decidir cal validar estat de conservació, biodiversitat sensible, ús real, aigua, combustible i objectiu ecològic.',
      layers:['fires','access','hic','publicUse'],
      legend:[['#dfeadb','HIC · compatibilitat a validar'],['#f3d7ad','HIC prioritari · precaució reforçada'],['#6b716d','Camins · accés potencial'],['#1f2a27','Ús públic OSM · conflicte a validar'],['#c23c32','Incendi històric · context']]
    }},
    temperature: {{
      label:`Temperatura superficial · mediana ${{Number(D.metrics.satellite.temperature.median).toFixed(1).replace('.',',')}} °C`,
      title:'Temperatura superficial estival completa',
      copy:`La composició de ${{D.metrics.satellite.temperatureSceneCount}} escenes Landsat 8/9 dels estius 2025–2026 cobreix el ${{Number(D.metrics.satellite.temperatureCoveragePct).toFixed(1).replace('.',',')}} % de l’àmbit. La mediana és ${{Number(D.metrics.satellite.temperature.median).toFixed(1).replace('.',',')}} °C; el 80% central se situa entre ${{Number(D.metrics.satellite.temperature.p10).toFixed(1).replace('.',',')}} i ${{Number(D.metrics.satellite.temperature.p90).toFixed(1).replace('.',',')}} °C.`,
      reading:'Els verds indiquen superfícies relativament més fresques; grocs i taronges, escalfament intermedi; i vermells o granats, superfícies més calentes. La temperatura és la de la pell del sòl o de la vegetació, no la de l’aire.',
      limit:'Límit: és la mediana de les observacions diürnes vàlides de dues temporades càlides. Redueix els buits per núvols, però no és una data única, una normal climàtica, temperatura de l’aire ni confort tèrmic.',
      layers:['access'],
      raster:'temperature',
      legend:[['#2a7f60','≤ 20 °C · més fresca'],['#facc46','28–32 °C · intermèdia'],['#d64127','≥ 36 °C · més calenta']]
    }},
    fireDanger: {{
      label:`Perill integrat EcoRadar · ${{Number(D.metrics.fireIntegratedHighPct).toFixed(1).replace('.',',')}} % alt o molt alt`,
      title:'Perill estructural integrat amb temperatura, humitat i vegetació',
      copy:'Combina el mapa oficial estructural 2024 de la Generalitat (30%), temperatura superficial Landsat (20%), sequedat relativa inversa de l’NDMI (20%), potencial de combustible segons el tipus de coberta (20%) i concurrència de relleu, accessos i focs històrics (10%). Quan la capa oficial no té dada fora del sòl forestal, es renormalitzen només els components disponibles.',
      reading:'Blau: índex integrat baix (<0,25). Groc: moderat (0,25–0,50). Taronja: alt (0,50–0,70). Vermell fosc: molt alt (≥0,70). El mapa cobreix tot l’àmbit i mostra concurrència de factors, no una predicció d’ignició.',
      limit:'No és el perill diari, el Pla Alfa, una probabilitat oficial ni una alerta. Els pesos i el potencial de combustible per coberta són hipòtesis analítiques explícites; cal validar càrrega, estructura vertical, humitat fina i meteorologia al camp.',
      layers:['fires','access'],
      raster:'fireDanger',
      legend:[['#2c7bb6','Baix · <0,25'],['#f0e65b','Moderat · 0,25–0,50'],['#f39a38','Alt · 0,50–0,70'],['#8b1e2d','Molt alt · ≥0,70'],['#c23c32','Perímetres històrics']]
    }},
    fireCurrent: {{
      label:`Perill d’incendi avui · índex EcoRadar 100 m · ${{Number(D.currentFire.summary.mean_index_0_100).toFixed(1).replace('.',',')}}/100 · ${{D.currentFire.summary.predominant_category}}`,
      title:'Perill d’incendi avui · índex EcoRadar a 100 m',
      copy:'Combina per cel·les de 100 m el potencial de foc ForestDrought CREAF, el perill estructural oficial 2024, la sequedat relativa NDMI, la temperatura superficial detallada més recent, la continuïtat vegetal CLMS, el pendent, l’orientació, la humitat XEMA Y4 i el màxim normalitzat entre vent i ratxa de l’estació XEMA CJ Organyà, a 9,2 km. Les variables dinàmiques només conserven el pes complet mentre són actuals; si envelleixen, el pes es redueix o s’exclou i la dada queda com a context amb la seva data. Temperatura de l’aire, pluja recent i acumulacions de 7 i 30 dies expliquen el context meteorològic observat; el Pla Alfa es mostra com a nivell oficial municipal separat. La concurrència territorial no intervé en aquest índex.',
      reading:'Verd: molt baix (0–20). Verd groguenc: baix (21–40). Groc: moderat (41–60). Taronja: alt (61–80). Vermell: molt alt (81–90). Granat: extrem (91–100). Clica qualsevol cel·la per consultar els valors i les contribucions. ForestDrought no s’interpola fora de les cel·les forestals natives.',
      limit:'Límit: és una lectura analítica EcoRadar, no una alerta oficial, el Pla Alfa ni una predicció d’ignició. ForestDrought és un model i només existeix a la seva graella forestal nativa. Y4 no publica vent; CJ Organyà aporta un context puntual proper. Les observacions XEMA i el Pla Alfa són uniformes per a tot l’àmbit: no se’ls atribueix una falsa resolució de 100 m. El popup identifica com a actual, recent o massa antiga cada dada dinàmica.',
      layers:['fireCurrent','fires','access'],
      raster:'fireCurrent',
      legend:[['#2f8f4e','0–20 · molt baix'],['#a8c94a','21–40 · baix'],['#f0d84b','41–60 · moderat'],['#ef8b2c','61–80 · alt'],['#d43d2f','81–90 · molt alt'],['#711d2d','91–100 · extrem'],['#c23c32','Perímetres històrics']]
    }},
    vegetation: {{
      label:`Cobertura vegetal Copernicus · ${{Number(D.metrics.satellite.vegetationCoverPct).toFixed(1).replace('.',',')}} %`,
      title:'Presència de cobertura vegetal',
      copy:`Combina la densitat de coberta arbòria i la presència herbàcia dels productes CLMS HRL 2023. Detecta ${{Number(D.metrics.satellite.vegetationCoverHa).toFixed(1).replace('.',',')}} ha vegetades, el ${{Number(D.metrics.satellite.vegetationCoverPct).toFixed(1).replace('.',',')}} % de la superfície amb dada vàlida.`,
      reading:'Els tons clars indiquen absència de cobertura vegetal detectada; els verds identifiquen presència vegetal, amb un color més intens quan domina clarament dins el píxel de visualització.',
      limit:'Límit: és presència de cobertura, no tipus de comunitat, biodiversitat, qualitat d’hàbitat, vigor, humitat ni càrrega de combustible. El botó vectorial «Tipus de coberta ICGC» permet consultar la classificació territorial complementària.',
      layers:['access'],
      raster:'vegetation',
      legend:[['#ece9de','Sense cobertura HRL'],['#63a25a','Cobertura parcial'],['#286f37','Cobertura vegetal']]
    }},
    vigor: {{
      label:`NDVI · mediana ${{Number(D.metrics.satellite.ndvi.median).toFixed(3).replace('.',',')}}`,
      title:'Vigor fotosintètic de la vegetació (NDVI)',
      copy:`L’NDVI de Sentinel-2 del 07.07.2026 compara la llum roja i l’infraroig proper. La mediana és ${{Number(D.metrics.satellite.ndvi.median).toFixed(3).replace('.',',')}} i el 80% central va de ${{Number(D.metrics.satellite.ndvi.p10).toFixed(3).replace('.',',')}} a ${{Number(D.metrics.satellite.ndvi.p90).toFixed(3).replace('.',',')}}.`,
      reading:'Marró: vigor espectral baix o poca vegetació. Verd clar: activitat intermèdia. Verd fosc: vigor espectral alt en la data de captura.',
      limit:'Límit: l’NDVI no mesura biodiversitat, salut individual ni humitat; és sensible al sòl i pot saturar-se en cobertes vegetals denses.',
      layers:['access'],
      raster:'vigor',
      legend:[['#80583d','≤ 0,10 · baix'],['#bcd37d','0,30–0,55 · intermedi'],['#165e32','≥ 0,85 · alt']]
    }},
    moisture: {{
      label:`NDMI · mediana ${{Number(D.metrics.satellite.ndmi.median).toFixed(3).replace('.',',')}}`,
      title:'Humitat relativa de la vegetació (NDMI)',
      copy:`L’NDMI de Sentinel-2 del 07.07.2026 combina infraroig proper i infraroig d’ona curta. La mediana és ${{Number(D.metrics.satellite.ndmi.median).toFixed(3).replace('.',',')}}; el 80% central va de ${{Number(D.metrics.satellite.ndmi.p10).toFixed(3).replace('.',',')}} a ${{Number(D.metrics.satellite.ndmi.p90).toFixed(3).replace('.',',')}}.`,
      reading:'Marró: vegetació relativament més seca. Tons clars: situació intermèdia. Blau: humitat relativa espectral més alta. És una comparació espacial en una data, no un percentatge d’aigua.',
      limit:'Límit: l’NDMI no equival a humitat mesurada al camp, humitat fina del combustible, humitat del sòl ni risc diari d’incendi.',
      layers:['access'],
      raster:'moisture',
      legend:[['#a6572f','≤ −0,15 · més seca'],['#e1da9d','0,05–0,25 · intermèdia'],['#226691','≥ 0,55 · més humida']]
    }},
    climateRefuges: {{
      label:`Refugis climàtics potencials · ${{Number(D.metrics.climateRefugesHighPct).toFixed(1).replace('.',',')}} % alt o molt alt`,
      title:'Coincidència territorial de frescor, humitat i vigor',
      copy:'La capa combina un 50% de frescor relativa derivada de la temperatura superficial Landsat, un 30% d’humitat relativa NDMI i un 20% de vigor NDVI. Només classifica píxels vegetats amb NDVI igual o superior a 0,30. La xarxa hídrica i les fonts del mapa ajuden a dirigir la validació ecològica.',
      reading:'Verd grisós: territori vegetat sense potencial destacat. Turquesa clar: potencial de suport. Blau: potencial alt. Blau fosc: potencial molt alt. Són sectors on coincideixen superfícies relativament fresques, vegetació més humida i vigor espectral.',
      limit:'Límit: és un cribratge relatiu, no un inventari de refugis certificats. La LST és una composició diürna de dos estius i NDVI/NDMI provenen d’una escena; calen sèries temporals, temperatura i humitat de l’aire, permanència de l’aigua i validació de camp.',
      layers:['hic'],
      raster:'climateRefuges',
      legend:[['#e1e5d3','No destacat'],['#97c7ba','Potencial de suport'],['#328b9f','Potencial alt'],['#1f497d','Potencial molt alt'],['#2f7eab','Xarxa hídrica'],['#0e4f7a','Fonts'],['transparent','Contorn HIC']]
    }},
    albedo: {{
      label:`Albedo · mediana ${{Number(D.metrics.satellite.albedo.median).toFixed(3).replace('.',',')}}`,
      title:'Quanta radiació solar reflecteix la superfície',
      copy:`L’albedo estimat amb Sentinel-2 del 07.07.2026 expressa la fracció de radiació solar reflectida. La mediana és ${{Number(D.metrics.satellite.albedo.median).toFixed(3).replace('.',',')}}; el 80% central va de ${{Number(D.metrics.satellite.albedo.p10).toFixed(3).replace('.',',')}} a ${{Number(D.metrics.satellite.albedo.p90).toFixed(3).replace('.',',')}}.`,
      reading:'Els tons foscos indiquen albedo baix, els grisos valors intermedis i els tons clars albedo alt. Superfícies més clares reflecteixen una proporció més gran de radiació.',
      limit:'Límit: és una estimació espectral de banda ampla, no una mesura radiomètrica de camp. No és temperatura, confort tèrmic ni balanç energètic complet.',
      layers:['access'],
      raster:'albedo',
      legend:[['#2d3b47','≤ 0,05 · baix'],['#9fa397','≈ 0,20 · intermedi'],['#f9efcf','≥ 0,45 · alt']]
    }}
  }};
  const layerGuides = {{
    fires:{{
      label:'Capa · incendis oficials',
      title:'Incendis històrics oficials',
      copy:'Mostra només els perímetres consolidats dins la Muntanya d’Alinyà.',
      reading:'Els polígons vermells són els focs oficials disponibles per al patró històric local. La seva funció és ubicar el precedent territorial, no descriure activitat recent.',
      limit:'No inclou registres sense perímetre, punts operatius ni deteccions satel·litàries. Font: Generalitat WFS VEGETACIO:VEGETACIO_INCENDIS.',
      legend:[['#c23c32','Perímetres 2000 i 2012']]
    }},
    access:{{
      label:'Capa · accessibilitat',
      title:'Camins i pistes',
      copy:'Mostra la xarxa viària OSM de context a tot el rectangle del mapa. Els 124,8 km quantificats per la diagnosi corresponen exclusivament al tram de xarxa dins l’àmbit d’Alinyà.',
      reading:'Les línies taronges indiquen carreteres i les grises, camins i pistes, també fora del contorn verd. Permeten orientar-se i interpretar accessibilitat potencial; només els trams dins l’àmbit entren en la diagnosi. En la lectura d’incendis també ajuden a identificar vores accessibles on la gestió del combustible pot tenir més retorn.',
      limit:'OSM no dona intensitat d’ús, freqüentació, pressió real, estat de manteniment, propietat ni causa d’ignició. Cal contrast de camp.',
      legend:[['#5d675f','Camins i pistes']]
    }},
    hic:{{
      label:'Capa · hàbitats HIC',
      title:'Hàbitats d’interès comunitari',
      copy:'Mostra els hàbitats HIC i prioritaris com a restricció ecològica de les actuacions preventives.',
      reading:'Els contorns verds indiquen zones on qualsevol actuació sobre combustible ha de ser més selectiva i justificada.',
      limit:'La cartografia d’hàbitats no equival a estat de conservació actual ni substitueix validació de camp.',
      legend:[['transparent','Contorn HIC'],['#102f24','HIC prioritari']]
    }},
    landcover:{{
      label:'Capa · cobertura vegetal',
      title:'Cobertes del sòl ICGC 2024',
      copy:'Classifica què cobreix físicament el territori i agrupa les classes originals per facilitar-ne la lectura ecològica.',
      reading:'Verd fosc: bosc. Verd oliva: matollar. Groc: prats i herbassars. Marró: conreus. Blau: aigua. Gris clar: roquissars o sòl nu. Gris fosc: vies i nuclis.',
      limit:'És una classificació de cobertura, no una mesura de vigor, humitat, biodiversitat, qualitat ecològica o combustible.',
      legend:[['#2f743f','Bosc'],['#8ca34a','Matollar'],['#d8c76f','Prats i herbassars'],['#b88955','Conreus'],['#4d97b5','Aigua'],['#b7afa0','Roquissars / sòl nu'],['#785f64','Vies i nuclis']]
    }},
    biodiversity:{{
      label:'Capa · biodiversitat coneguda',
      title:'Registres públics de biodiversitat',
      copy:'Mostra els registres públics disponibles dins l’àmbit.',
      reading:'Els punts blaus identifiquen coneixement disponible i buits d’informació. No delimiten per si sols zones de major biodiversitat.',
      limit:'GBIF/iNaturalist són fonts oportunistes i no substitueixen inventari de camp ni dades normatives.',
      legend:[['#2d72a0','Registres públics']]
    }},
    publicUse:{{
      label:'Capa · ús públic',
      title:'Ús públic OSM',
      copy:'Mostra els 18 punts d’ús públic o elements cartografiats a OpenStreetMap.',
      reading:'Els punts foscos són elements de context. Permeten llegir accessibilitat potencial i prioritzar la validació de possibles conflictes amb hàbitats o fauna, però no mesuren freqüentació ni pressió real.',
      limit:'OSM és cartografia col·laborativa; no quantifica visitants, intensitat d’ús, freqüentació, pressió real ni impacte ecològic.',
      legend:[['#1f2a27','18 punts d’ús públic OSM']]
    }},
    places:{{
      label:'Capa · poblacions OSM',
      title:'Nuclis i poblacions de referència',
      copy:`Mostra ${{D.metrics.settlements}} topònims classificats a OSM com a nucli habitat dins la finestra cartogràfica d’Alinyà.`,
      reading:'Els punts foscos situen el topònim; les etiquetes permeten orientar-se respecte a la xarxa viària i el relleu.',
      limit:'OSM és cartografia col·laborativa. El punt no delimita l’extensió del nucli i no s’utilitza per estimar població, exposició o pressió.',
      legend:[['#17332d','Poblacions i nuclis OSM']]
    }}
  }};

  const ca1 = v => Number(v).toFixed(1).replace('.',',');
  const ca2 = v => Number(v).toFixed(2).replace('.',',');
  const caInt = v => Number(v).toLocaleString('ca-ES');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
  const humanDate = value => {{
    if (!value) return 'dada no disponible';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString('ca-ES', {{timeZone:'Europe/Madrid', day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'}});
  }};
  const metricValue = (item, factor=1, digits=1) => item?.value == null ? null : Number(item.value) * factor;
  const metricText = (item, unit, factor=1, digits=1) => {{
    const value = metricValue(item, factor, digits);
    return value == null ? 'dada no disponible' : `${{Number(value).toFixed(digits).replace('.',',')}} ${{unit}}`;
  }};
  const fireVariableLabels = {{
    creaf_fire_potential:'Potencial de foc ForestDrought',
    structural:'Perill estructural oficial 2024',
    ndmi_dryness:'Sequedat relativa NDMI',
    surface_temperature:'Temperatura superficial',
    vegetation_continuity:'Continuïtat vegetal',
    wind:'Vent',
    relative_humidity_inverse:'Humitat relativa baixa',
    slope:'Pendent',
    aspect:'Exposició de solana'
  }};
  const fireVariableRoles = {{
    creaf_fire_potential:'Estima l’estrès i el potencial de foc del bosc modelitzat; modula la situació acumulada amb la frescor real del model.',
    structural:'Caracteritza el perill territorial de base; orienta on validar combustible i exposició, però no descriu el dia actual.',
    ndmi_dryness:'Aporta el contrast espacial d’humitat espectral quan l’escena és prou recent; si és antiga queda només com a context.',
    surface_temperature:'Aporta el patró espacial de superfície calenta quan l’observació detallada és prou recent; no és temperatura de l’aire.',
    vegetation_continuity:'Representa continuïtat horitzontal de la coberta; no quantifica càrrega ni estructura vertical del combustible.',
    wind:'Representa el component meteorològic actual de propagació amb vent i ratxa XEMA; és context puntual, no una malla local.',
    relative_humidity_inverse:'Representa la sequedat atmosfèrica actual observada a XEMA Y4; no equival a humitat fina del combustible.',
    slope:'Caracteritza la propagació potencial associada al relleu i es manté com a factor estructural.',
    aspect:'Caracteritza l’exposició relativa de solana i es manté com a factor estructural.'
  }};
  const dailyReadingOrder = ['air_temperature','relative_humidity','wind','wind_gust','precipitation','precipitation_7d','precipitation_30d','days_without_significant_rain','surface_temperature','ndmi','ndvi','albedo','terrain_shade','air_quality','thermal_comfort','pla_alfa','current_fire_danger'];
  const dailyReadingRoles = {{
    air_temperature:'Context meteorològic actual per interpretar calor i incendi; és una observació puntual i no una malla territorial.',
    relative_humidity:'Entra en el perill d’incendi actual amb control de frescor i ajuda a graduar vigilància; no mesura humitat del combustible.',
    wind:'Entra en el perill d’incendi actual juntament amb la ratxa; serveix per graduar la urgència operativa, amb la limitació de l’estació de context.',
    wind_gust:'Complementa el vent sostingut en el component meteorològic del perill actual; no permet descriure cada vall o carena.',
    precipitation:'Descriu la pluja recent i contextualitza l’assecament; no entra com un zero de risc ni substitueix la humitat del combustible.',
    precipitation_7d:'Aporta antecedent humit de curt termini per interpretar sequera i disponibilitat de combustible fi.',
    precipitation_30d:'Aporta antecedent acumulat mensual; serveix per contrastar tendència seca, no com a diagnòstic ecològic únic.',
    days_without_significant_rain:'Indica persistència sense pluja significativa i ajuda a prioritzar comprovacions de camp de sequedat i aigua.',
    surface_temperature:'Localitza patrons tèrmics de superfície i participa en perill actual o refugis només segons la frescor i resolució de l’escena.',
    ndmi:'Informa d’humitat espectral relativa; participa en incendi o refugis només si la data és adequada i mai equival a humitat fina.',
    ndvi:'Informa de vigor espectral i ajuda a interpretar vegetació i refugis; no mesura biodiversitat ni estat sanitari per si sol.',
    albedo:'Descriu reflectància superficial i balanç radiatiu contextual; no justifica una actuació ecològica per si sol.',
    terrain_shade:'Actualitza la posició de l’ombra topogràfica segons el dia i l’hora; ajuda a llegir exposició, però no incorpora arbres ni edificis.',
    air_quality:'Aporta context ambiental per a ús públic i episodis atmosfèrics; la resolució modelitzada no permet decisions parcel·làries.',
    thermal_comfort:'Sintetitza condicions meteorològiques per a persones i ús públic; no és un indicador de conservació d’hàbitats.',
    pla_alfa:'Context operatiu oficial municipal que pot condicionar accés, vigilància i activitats; no entra numèricament a l’índex EcoRadar.',
    current_fire_danger:'Síntesi diària per prioritzar comprovació i preparació; no ordena tractaments sense creuar valors ecològics i validació de combustible.'
  }};
  const coreDecisionRoles = {{
    CORE_01:'Sustenta P2: conservar o recuperar mosaic funcional després de validar ús, trajectòria i qualitat dels espais oberts.',
    CORE_02:'Filtre transversal de no-deteriorament per a P1–P5; la cartografia HIC no substitueix l’estat de conservació de camp.',
    CORE_03:'Orienta seguiment de vigor i humitat, però la puntuació parcial i la data de l’escena impedeixen decidir una actuació per si sola.',
    CORE_04:'Sustenta P1 i P3 com a cribratge de sectors potencialment frescos; exigeix permanència hídrica i validació microclimàtica.',
    CORE_05:'Orienta on combinar calor, sequera, relleu i sensibilitat; no equival a impacte observat ni urgència automàtica.',
    CORE_06:'Filtre de biodiversitat per a totes les prioritats; els registres públics documenten presències i buits, no abundància ni absència.',
    CORE_07:'Sustenta P4 com a accessibilitat potencial; cal mesurar freqüentació i conflictes abans de restringir o ampliar l’ús.',
    CORE_08:'Sustenta P2 i P3 per mantenir permeabilitat terrestre i hídrica, amb comprovació de barreres i funcionalitat real.',
    CORE_09:'Sustenta P5 i el capítol 06; combina vulnerabilitat estructural amb la lectura diària, sense convertir-la en ordre de tractament.',
    CORE_10:'Sustenta P3; la xarxa i les fonts orienten inventari, però permanència, qualitat i ús faunístic resten pendents de camp.',
    CORE_11:'Orienta on verificar necessitat de restauració; un valor alt no justifica restauració generalitzada ni substitueix la trajectòria ecològica.',
    CORE_12:'Síntesi de prioritat de gestió; només és interpretable amb els indicadors anteriors, les dates de les fonts i els criteris de camp.'
  }};
  const fireAreaColors = {{
    'molt baix':'#2f8f4e', 'baix':'#a8c94a', 'moderat':'#f0d84b',
    'alt':'#ef8b2c', 'molt alt':'#d43d2f', 'extrem':'#711d2d'
  }};
  function updateCurrentFireSummary(fire) {{
    D.currentFire = fire;
    const meteo = fire.meteorology || {{}};
    const accumulated = meteo.precipitation_accumulated || {{}};
    const pla = fire.plaAlfa || {{}};
    const trend = D.dailyHistory?.analytics?.current_fire_danger?.trend || {{}};
    const trendPct = trend.variation_pct == null ? '' : ` · ${{Math.abs(Number(trend.variation_pct)).toFixed(1).replace('.',',')}} %`;
    const weatherText = `${{metricText(meteo.air_temperature,'°C')}} · HR ${{metricText(meteo.relative_humidity,'%',1,0)}} · vent ${{metricText(meteo.wind,'km/h',3.6)}} · ratxa ${{metricText(meteo.wind_gust,'km/h',3.6)}}`;
    const droughtText = accumulated.last_7_days_mm == null
      ? 'dada no disponible'
      : `${{ca1(accumulated.last_7_days_mm)}} mm / 7 d · ${{accumulated.last_30_days_mm == null ? '—' : ca1(accumulated.last_30_days_mm)}} mm / 30 d · ${{accumulated.days_without_significant_rain == null ? '—' : ca1(accumulated.days_without_significant_rain)}} dies secs`;
    const plaText = pla.level == null ? 'dada no disponible' : `nivell ${{pla.level}} · ${{pla.label}}`;
    const trendText = `${{trend.symbol || '→'}} ${{trend.label || 'sense comparació'}}${{trendPct}}`;
    root.querySelector('#eu-fire-current-date').textContent = `comprovat ${{humanDate(fire.checkedAtUtc)}}`;
    root.querySelector('#eu-fire-current-summary').innerHTML = [
      ['Pla Alfa oficial',plaText],
      ['Meteorologia',weatherText],
      ['Sequera acumulada',droughtText],
      ['Tendència',trendText],
      ['Índex mitjà',`${{ca1(fire.summary.mean_index_0_100)}}/100`],
      ['Categoria predominant',fire.summary.predominant_category],
      ['Màxim territorial',`${{ca1(fire.summary.maximum_index_0_100)}}/100 · ${{fire.summary.maximum_category}}`],
      ['Molt alt o extrem',`${{ca1(fire.summary.very_high_or_extreme_area_pct)}} %`],
      ['Confiança',`${{ca1(fire.summary.confidence_pct)}} % · ${{fire.summary.confidence}}`],
      ['Factors dominants',(fire.summary.dominant_labels || []).join(' · ')]
    ].map(([label,value]) => `<span>${{esc(label)}}</span><strong>${{esc(value)}}</strong>`).join('');
    root.querySelector('#eu-fire-current-areas').innerHTML = Object.entries(fire.summary.area_by_category_ha || {{}})
      .map(([category,area]) => `<div class="eu-fire-area"><i style="background:${{fireAreaColors[category]}}"></i><span>${{esc(category)}}</span><strong>${{ca1(area)}} ha</strong></div>`).join('');
    root.querySelector('#eu-fire-current-check').textContent = `Darrera comprovació del procés: ${{humanDate(fire.checkedAtUtc)}}. Darrera observació meteorològica utilitzada: ${{humanDate(fire.summary.latest_update_utc)}}. Estat: ${{fire.status}}.`;
    root.querySelector('#eu-fire-current-variables').innerHTML = Object.entries(fire.variables || {{}}).map(([key,item]) => `<tr><td>${{esc(fireVariableLabels[key] || key)}}</td><td>${{esc(item.value)}}</td><td>${{esc(item.source)}}</td><td>${{esc(humanDate(item.date_utc))}}</td><td>${{ca1(item.weight_pct)}} %${{item.base_weight_pct == null || item.base_weight_pct === item.weight_pct ? '' : ` <span class="eu-muted">(base ${{ca1(item.base_weight_pct)}} %)</span>`}}</td><td>${{esc(item.quality)}} · ${{esc(item.temporal_status_label || item.update_status)}}</td></tr>`).join('');
    root.querySelector('#eu-fire-current-weights').innerHTML = Object.entries(fire.weights || {{}}).map(([key,weight]) => {{
      const effective = fire.effectiveWeights?.[key] ?? weight;
      return `<li>${{esc(fireVariableLabels[key] || key)}}: <strong>${{ca1(effective * 100)}} %</strong>${{effective === weight ? '' : ` <span class="eu-muted">(base ${{ca1(weight * 100)}} %)</span>`}}</li>`;
    }}).join('');
    root.querySelector('#report-fire-today').textContent = `${{ca1(fire.summary.mean_index_0_100)}}/100 · ${{fire.summary.predominant_category}}`;
    root.querySelector('#report-pla-alfa').textContent = plaText;
    root.querySelector('#report-fire-weather').textContent = weatherText;
    root.querySelector('#report-fire-drought').textContent = droughtText;
    root.querySelector('#report-fire-trend').textContent = trendText;
    root.querySelector('#report-fire-update').textContent = humanDate(fire.checkedAtUtc);
    root.querySelector('#report-fire-chapter-today').textContent = `${{ca1(fire.summary.mean_index_0_100)}}/100 · ${{fire.summary.predominant_category}}`;
    root.querySelector('#report-fire-chapter-pla').textContent = plaText;
    root.querySelector('#report-fire-chapter-weather').textContent = weatherText;
    root.querySelector('#report-fire-chapter-drought').textContent = droughtText;
    root.querySelector('#report-fire-chapter-trend').textContent = trendText;
    root.querySelector('#report-fire-chapter-confidence').textContent = `${{ca1(fire.summary.confidence_pct)}} % · ${{fire.summary.confidence}}`;
    root.querySelector('#report-fire-chapter-update').textContent = humanDate(fire.checkedAtUtc);
    root.querySelector('#report-fire-chapter-dominants').innerHTML = `<strong>Factors dominants:</strong> ${{esc((fire.summary.dominant_labels || []).join(' · ') || 'no determinats')}}.`;
    const excluded = fire.summary.temporally_excluded_variables || [];
    root.querySelector('#report-fire-chapter-freshness').innerHTML = excluded.length
      ? `<strong>Control de frescor:</strong> ${{esc(excluded.map(key => fireVariableLabels[key] || key).join(' · '))}} queda fora del càlcul actual per antiguitat. La resta de variables dinàmiques conserva el pes complet o reduït que indica la seva data.`
      : '<strong>Control de frescor:</strong> cap variable dinàmica ha estat exclosa; els pesos efectius continuen depenent de la data de cada font.';
    root.querySelector('#report-fire-chapter-variables').innerHTML = Object.entries(fire.variables || {{}}).map(([key,item]) => `<tr><td>${{esc(fireVariableLabels[key] || key)}}</td><td>${{esc(item.value)}}</td><td>${{esc(humanDate(item.date_utc))}}</td><td>${{ca1(item.weight_pct)}} %${{item.base_weight_pct == null || item.base_weight_pct === item.weight_pct ? '' : ` <span class="eu-muted">(base ${{ca1(item.base_weight_pct)}} %)</span>`}}</td><td>${{esc(item.temporal_status_label || item.update_status || 'no informat')}}</td><td>${{esc(fireVariableRoles[key] || 'Variable documentada sense interpretació addicional.')}}</td></tr>`).join('');
    renderDecisionEvidence();
  }}
  function renderDecisionEvidence() {{
    const readings = D.dailyReadings?.readings || {{}};
    root.querySelector('#eu-daily-decision-evidence').innerHTML = dailyReadingOrder.map(key => {{
      const item = readings[key] || {{label:key, value:'dada no disponible', status:'dada no disponible', data_at_utc:null}};
      return `<tr><td>${{esc(item.label || key)}}</td><td class="eu-reading-state"><strong>${{esc(item.value || 'dada no disponible')}}</strong><br><span class="eu-subtle">${{esc(item.status || 'estat no informat')}}</span></td><td>${{esc(humanDate(item.data_at_utc))}}</td><td>${{esc(dailyReadingRoles[key])}}</td></tr>`;
    }}).join('');
    root.querySelector('#eu-core-decision-evidence').innerHTML = D.metrics.core.map(metric => {{
      const value = metric.value == null ? null : Math.max(0,Math.min(100,metric.value));
      const valueText = metric.display || (value == null ? 'N/D' : ca1(value));
      const publicCode = String(metric.code || '').replace('CORE_','RADAR_');
      const state = `${{valueText}} · ${{metric.status}} · confiança ${{metric.confidence}}`;
      return `<tr><td><strong>${{esc(publicCode)}} · ${{esc(metric.name)}}</strong></td><td>${{esc(state)}}</td><td>${{esc(coreDecisionRoles[metric.code] || 'Indicador de context que requereix lectura conjunta amb la resta del diagnòstic.')}}</td></tr>`;
    }}).join('');
  }}
  updateCurrentFireSummary(D.currentFire);
  root.querySelector('#eu-area-value').textContent = `${{caInt(D.metrics.studyAreaHa)}} ha`;
  root.querySelector('#eu-fires-value').textContent = `${{D.metrics.fires}} perímetres`;
  root.querySelector('#eu-burned-value').textContent = `${{ca1(D.metrics.burnedHa)}} ha · ${{ca2(D.metrics.burnedPct)}} %`;
  root.querySelector('#eu-concurrence-value').textContent = `${{ca1(D.metrics.fireIntegratedHighHa)}} ha · ${{ca1(D.metrics.fireIntegratedHighPct)}} %`;
  root.querySelector('#eu-forest-value').textContent = `${{caInt(D.metrics.forestLikeHa)}} ha · ${{ca1(D.metrics.forestLikePct)}} %`;
  root.querySelector('#eu-open-value').textContent = `${{caInt(D.metrics.openLikeHa)}} ha · ${{ca1(D.metrics.openLikePct)}} %`;
  root.querySelector('#eu-hic-value').textContent = `${{caInt(D.metrics.hicHa)}} ha`;
  root.querySelector('#eu-hic-prior-value').textContent = `${{caInt(D.metrics.hicPriorHa)}} ha`;
  root.querySelector('#eu-records-value').textContent = caInt(D.metrics.records);
  root.querySelector('#eu-species-value').textContent = caInt(D.metrics.species);
  root.querySelector('#eu-paths-value').textContent = `${{ca1(D.metrics.pathsKm)}} km`;
  root.querySelector('#eu-management-hic-prior').textContent = `${{caInt(D.metrics.hicPriorHa)}} ha`;
  root.querySelector('#eu-management-access').textContent = `${{ca1(D.metrics.pathsKm)}} km`;
  root.querySelector('#eu-management-public').textContent = caInt(D.metrics.publicPoints);
  root.querySelector('#eu-management-fires').textContent = caInt(D.metrics.fires);

  root.querySelector('#report-area').textContent = `${{caInt(D.metrics.studyAreaHa)}} ha`;
  root.querySelector('#report-forest').textContent = `${{ca1(D.metrics.forestPct)}} %`;
  root.querySelector('#report-open').textContent = `${{ca1(D.metrics.grasslandPct)}} %`;
  root.querySelector('#report-hic').textContent = `${{caInt(D.metrics.hicHa)}} ha`;
  root.querySelector('#report-water-km').textContent = `${{ca1(D.metrics.hydrologyKm)}} km`;
  root.querySelector('#report-springs').textContent = caInt(D.metrics.springs);
  root.querySelector('#report-connectors').textContent = caInt(D.metrics.connectivityEntities);
  root.querySelector('#report-pressure').textContent = `${{ca1(D.metrics.pathsKm)}} km · ${{D.metrics.publicPoints}} punts`;

  const groupOrder = ['Flora','Ocells','Papallones i arnes','Altres insectes','Fongs i líquens','Altres mamífers','Ratpenats','Aràcnids','Odonats','Ortòpters','Rèptils','Amfibis'];
  const groupReading = {{
    'Flora':'Base àmplia de cites; no informa de cobertura, estat ni representativitat local.',
    'Ocells':'Bon volum documental, però sense cens, esforç homogeni ni estacionalitat controlada.',
    'Papallones i arnes':'Indicadors útils d’espais oberts i ecotons; mostreig oportunista.',
    'Altres insectes':'Diversitat taxonòmica agregada; cal separar ordres i requeriments en camp.',
    'Fongs i líquens':'Grup sensible al substrat i microclima, probablement infrarepresentat.',
    'Altres mamífers':'Presències documentades; no estima ocupació ni abundància.',
    'Ratpenats':'Buit de mostreig públic: zero registres no significa absència.',
    'Aràcnids':'Coneixement puntual que ajuda a orientar prospecció d’invertebrats.',
    'Odonats':'Poques cites; convé relacionar-les amb la funcionalitat dels punts d’aigua.',
    'Ortòpters':'Grup vinculat sovint a herbassars i espais oberts; cobertura limitada.',
    'Rèptils':'Mostra reduïda; cal prospecció dirigida per hàbitat i estació.',
    'Amfibis':'Cites escasses i dependents de temporalitat i permanència de l’aigua.'
  }};
  const biodiv = D.metrics.biodiversityGroups;
  root.querySelector('#eu-biodiversity-table').innerHTML = groupOrder.map(group => `<tr><td>${{group}}</td><td class="num">${{caInt(biodiv.records[group] || 0)}}</td><td class="num">${{caInt(biodiv.taxa[group] || 0)}}</td><td>${{groupReading[group]}}</td></tr>`).join('');
  const topText = (label, rows) => `<strong>${{label}}:</strong> ${{rows.map(([name,count]) => `<em>${{name}}</em> (${{count}})`).join('; ')}}.`;
  root.querySelector('#eu-top-birds').innerHTML = topText('Ocells', (biodiv.top['Ocells'] || []).slice(0,4));
  root.querySelector('#eu-top-leps').innerHTML = topText('Papallones i arnes', (biodiv.top['Papallones i arnes'] || []).slice(0,4));

  root.querySelector('#eu-core-scores').innerHTML = D.metrics.core.map(metric => {{
    const value = metric.value == null ? null : Math.max(0,Math.min(100,metric.value));
    const valueText = metric.display || (value == null ? 'N/D' : ca1(value));
    const publicCode = String(metric.code || '').replace('CORE_','RADAR_');
    return `<article class="eu-score"><div class="eu-score-head"><span>${{publicCode}} · ${{metric.name}}</span><strong>${{valueText}}</strong></div><div class="eu-score-track"><div class="eu-score-fill" style="width:${{value == null ? 0 : value}}%"></div></div><span class="eu-status">${{metric.status}} · confiança ${{metric.confidence}}</span></article>`;
  }}).join('');

  let activeMode = 'base';
  let activeGuide = {{type:'mode', key:'base'}};
  root.querySelectorAll('.eu-mode').forEach(button => button.addEventListener('click', () => {{
    const mapPanel = root.querySelector('.eu-map-panel');
    const mapRectBefore = mapPanel.getBoundingClientRect();
    const keepMapPosition = mapRectBefore.bottom > 0 && mapRectBefore.top < window.innerHeight;
    activeMode = button.dataset.mode;
    activeGuide = {{type:'mode', key:activeMode}};
    root.querySelectorAll('.eu-mode').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    applyMode(activeMode);
    if (keepMapPosition) {{
      requestAnimationFrame(() => requestAnimationFrame(() => {{
        const displacement = mapPanel.getBoundingClientRect().top - mapRectBefore.top;
        if (Math.abs(displacement) > 1) window.scrollBy(0, displacement);
      }}));
    }}
  }}));
  root.querySelectorAll('.eu-layer').forEach(button => button.addEventListener('click', () => {{
    const key = button.dataset.layer;
    const next = button.getAttribute('aria-pressed') !== 'true';
    setLayer(key, next);
    activeGuide = {{type:'mode', key:activeMode}};
    updateContextStatus();
    updateGuide();
  }}));
  function setLayer(key, visible) {{
    if (groups[key]) groups[key].style('display', visible ? null : 'none');
    const button = root.querySelector(`[data-layer="${{key}}"]`);
    if (button) button.setAttribute('aria-pressed', String(visible));
  }}
  function applyMode(mode) {{
    const guide = modeGuides[mode];
    Object.keys(modeGuides).forEach(key => root.classList.remove(`mode-${{key}}`));
    root.classList.add(`mode-${{mode}}`);
    Object.keys(groups).forEach(k => {{ if (k !== 'boundary') setLayer(k, guide.layers.includes(k)); }});
    Object.entries(rasterGroups).forEach(([key,image]) => image.style('display', key === 'relief' || guide.raster === key ? null : 'none'));
    root.querySelectorAll('[data-current-fire]').forEach(panel => panel.hidden = mode !== 'fireCurrent');
    root.querySelectorAll('[data-management]').forEach(panel => panel.hidden = mode !== 'management');
    if (mode !== 'fireCurrent') firePopup.hidden = true;
    root.querySelector('#eu-active-label').textContent = guide.label;
    activeGuide = {{type:'mode', key:mode}};
    updateContextStatus();
    updateGuide();
  }}
  function updateContextStatus() {{
    const active = [...root.querySelectorAll('.eu-layer[aria-pressed="true"] strong')].map(node => node.textContent.trim());
    const status = root.querySelector('#eu-context-status');
    if (status) status.textContent = active.length ? `Context visible: ${{active.join(' · ')}}` : 'Context visible: cap superposició';
  }}
  function currentGuide() {{
    return modeGuides[activeMode];
  }}
  function updateGuide() {{
    const guide = currentGuide();
    root.querySelector('#eu-active-label').textContent = guide.label;
    root.querySelector('#eu-guide-title').textContent = guide.title;
    root.querySelector('#eu-guide-copy').textContent = guide.copy;
    root.querySelector('#eu-guide-reading').textContent = guide.reading;
    root.querySelector('#eu-guide-limit').textContent = guide.limit;
    updateLegend(guide.legend);
  }}
  function updateLegend(baseRows) {{
    const rows = baseRows.slice();
    root.querySelectorAll('.eu-layer[aria-pressed="true"]').forEach(button => {{
      const key = button.dataset.layer;
      if (key === 'publicUse' && !rows.some(r => r[1].includes('Ús públic'))) rows.push(['#1f2a27','Ús públic OSM']);
      if (key === 'places' && !rows.some(r => r[1].includes('Poblacions'))) rows.push(['#17332d','Poblacions i nuclis OSM']);
      if (key === 'biodiversity' && !rows.some(r => r[1].includes('Biodiversitat') || r[1].includes('Registres'))) rows.push(['#2d72a0','Registres biodiversitat']);
      if (key === 'hic' && !rows.some(r => r[1].includes('HIC'))) rows.push(['#2f7b50','HIC']);
      if (key === 'landcover' && !rows.some(r => r[1] === 'Bosc')) rows.push(['#2f743f','Bosc'],['#8ca34a','Matollar'],['#d8c76f','Prats i herbassars']);
    }});
    root.querySelector('#eu-legend').innerHTML = rows.map(([c,l]) => {{
      const style = c === 'transparent-red' ? 'background:transparent;border-color:#b84c35' : c === 'transparent-orange' ? 'background:transparent;border-color:#d88932' : c === 'transparent' ? 'background:transparent;border-color:#2f743f' : `background:${{c}}`;
      return `<div class="eu-legend-row" role="listitem"><span class="eu-swatch" style="${{style}}"></span>${{l}}</div>`;
    }}).join('');
  }}
  function fireRawValue(key, raw) {{
    const value = raw[key];
    if (value == null && key === 'creaf_fire_potential_0_9') return 'no aplicable · sense cel·la forestal CREAF';
    if (value == null) return 'no disponible a la font';
    if (key === 'official_structural_1_10') return `${{ca1(value)}}/10`;
    if (key === 'surface_temperature_c') return `${{ca1(value)}} °C`;
    if (key === 'ndmi') return Number(value).toFixed(3).replace('.',',');
    if (key === 'creaf_fire_potential_0_9') return `${{ca1(value)}}/9`;
    if (key === 'vegetation_continuity_0_100') return `${{ca1(value)}}/100`;
    if (key === 'slope_deg' || key === 'aspect_deg') return `${{ca1(value)}}°`;
    if (key === 'wind_speed_kmh') return `${{ca1(value)}} km/h`;
    if (key === 'relative_humidity_pct') return `${{ca1(value)}} %`;
    return ca1(value);
  }}
  function showManagementHicPopup(feature) {{
    const p = feature.properties || {{}};
    const priority = Boolean(p.HIC_PRIOR);
    firePopup.classList.add('is-management');
    firePopup.innerHTML = `<button class="eu-fire-popup-close" type="button" aria-label="Tancar detall">×</button>
      <h3>HIC ${{esc(p.COD_HIC || 'sense codi')}} · filtre de gestió</h3>
      <div class="eu-fire-popup-main">${{priority ? 'Precaució reforçada · HIC prioritari' : 'Compatibilitat ecològica a validar'}}</div>
      <p><strong>Què mostra:</strong> ${{esc(p.CORINE_CA || 'hàbitat d’interès comunitari cartografiat')}}.</p>
      <p><strong>Què permet interpretar:</strong> qualsevol proposta que coincideixi amb aquest polígon ha de comprovar al camp el límit, l’estat de conservació i la compatibilitat de l’actuació. ${{priority ? 'El caràcter prioritari reforça el criteri de prudència i no-deteriorament.' : 'La coincidència activa un filtre de prudència, però no determina per si sola la decisió.'}}</p>
      <p><strong>Què cal fer:</strong> descriure l’objectiu ecològic, verificar espècies i processos sensibles, comparar no-intervenció, retirada de pressió i actuació selectiva, i definir seguiment abans d’executar.</p>
      <p class="eu-warning"><strong>Què no permet afirmar:</strong> el polígon no indica estat de conservació actual, degradació, urgència, necessitat d’actuar ni nivell territorial A–E.</p>
      <p class="eu-source">Font cartogràfica HIC incorporada al projecte. Interpretació EcoRadar de cribratge; requereix validació de camp.</p>`;
    firePopup.hidden = false;
    firePopup.querySelector('.eu-fire-popup-close').addEventListener('click', () => {{ firePopup.hidden = true; }});
  }}
  function showFirePopup(feature) {{
    firePopup.classList.remove('is-management');
    const p = feature.properties;
    const rows = [
      ['creaf_fire_potential','creaf_fire_potential_0_9'],
      ['structural','official_structural_1_10'],
      ['ndmi_dryness','ndmi'],
      ['surface_temperature','surface_temperature_c'],
      ['vegetation_continuity','vegetation_continuity_0_100'],
      ['wind','wind_speed_kmh'],
      ['relative_humidity_inverse','relative_humidity_pct'],
      ['slope','slope_deg'],
      ['aspect','aspect_deg']
    ];
    const detailRows = rows.map(([component,rawKey]) => {{
      const normalized = p.normalized[component];
      const contribution = p.contributions[component];
      const freshness = p.source_freshness?.[component] || {{}};
      const creafNotModelled = component === 'creaf_fire_potential' && p.raw.creaf_fire_potential_0_9 == null;
      const normalizedText = creafNotModelled ? 'no aplicable' : normalized == null ? '—' : ca1(normalized);
      const contributionText = creafNotModelled || freshness.factor === 0 ? 'pes exclòs' : contribution == null ? '—' : ca1(contribution);
      const sourceState = `${{humanDate(p.source_dates[component])}} · ${{freshness.status_label || 'estat temporal no informat'}}`;
      return `<tr><td>${{esc(fireVariableLabels[component])}}</td><td>${{esc(fireRawValue(rawKey,p.raw))}}</td><td>${{normalizedText}}</td><td>${{contributionText}}</td><td>${{esc(sourceState)}}</td></tr>`;
    }}).join('');
    const creafNotModelled = p.raw.creaf_fire_potential_0_9 == null;
    const windValue = p.raw.wind_speed_kmh == null ? 'no disponible a la font' : `${{ca1(p.raw.wind_speed_kmh)}} km/h`;
    const windDate = humanDate(p.source_dates.wind);
    const meteo = D.currentFire.meteorology || {{}};
    const accumulated = meteo.precipitation_accumulated || {{}};
    const pla = D.currentFire.plaAlfa || {{}};
    const meteoFreshness = meteo.freshness?.status_label || 'estat temporal no informat';
    const rainFreshness = accumulated.freshness?.status_label || 'estat temporal no informat';
    const plaFreshness = pla.freshness?.status_label || 'estat temporal no informat';
    const excluded = (p.temporally_excluded_variables || []).map(key => fireVariableLabels[key] || key);
    const plaText = pla.level == null ? 'dada no disponible' : `nivell ${{pla.level}} · ${{pla.label}}`;
    const rainText = accumulated.last_7_days_mm == null ? 'dada no disponible' : `${{ca1(accumulated.last_7_days_mm)}} mm en 7 dies · ${{accumulated.last_30_days_mm == null ? '—' : ca1(accumulated.last_30_days_mm)}} mm en 30 dies · ${{accumulated.days_without_significant_rain == null ? '—' : ca1(accumulated.days_without_significant_rain)}} dies sense ≥1 mm/dia`;
    firePopup.innerHTML = `<button class="eu-fire-popup-close" type="button" aria-label="Tancar detall">×</button>
      <h3>${{esc(p.cell_id)}} · perill actual</h3>
      <div class="eu-fire-popup-main">${{ca1(p.index_0_100)}}/100 · ${{esc(p.category)}}</div>
      <p><strong>Confiança:</strong> ${{ca1(p.confidence_pct)}} % · ${{esc(p.confidence)}}. <strong>Cobertura del pes temporalment elegible:</strong> ${{ca1(p.available_weight_pct)}} %; <strong>pes base encara elegible:</strong> ${{ca1(p.eligible_base_weight_pct)}} %.</p>
      <p><strong>Vent contextual XEMA · CJ Organyà:</strong> ${{esc(windValue)}} · observació ${{esc(windDate)}}. <span class="eu-muted">${{esc(p.source_freshness?.wind?.status_label || '')}} · estació oficial de referència situada a 9,2 km de l’estació Y4 d’Alinyà.</span></p>
      <p><strong>Meteorologia actual:</strong> temperatura ${{esc(metricText(meteo.air_temperature,'°C'))}} · humitat ${{esc(metricText(meteo.relative_humidity,'%',1,0))}} · vent ${{esc(metricText(meteo.wind,'km/h',3.6))}} · ratxa ${{esc(metricText(meteo.wind_gust,'km/h',3.6))}} · pluja 24 h ${{accumulated.recent_24h_mm == null ? '—' : ca1(accumulated.recent_24h_mm) + ' mm'}}. <span class="eu-muted">${{esc(meteoFreshness)}}.</span></p>
      <p><strong>Sequera meteorològica acumulada:</strong> ${{esc(rainText)}}. <span class="eu-muted">Acumulacions XEMA fins a ${{esc(humanDate(accumulated.data_at_utc))}} · ${{esc(rainFreshness)}}; si la cobertura és insuficient es mostra “dada no disponible”.</span></p>
      <p><strong>Pla Alfa oficial · Fígols i Alinyà:</strong> ${{esc(plaText)}} · dada ${{esc(humanDate(pla.data_at_utc))}} · comprovació ${{esc(humanDate(pla.checked_at_utc))}} · ${{esc(plaFreshness)}}. <span class="eu-muted">Context operatiu municipal oficial; no entra numèricament a l’índex EcoRadar.</span></p>
      <p><strong>Factors dominants:</strong> ${{esc((p.dominant_labels || []).join(' · ') || 'no determinats')}}.</p>
      ${{excluded.length ? `<p class="eu-warning"><strong>Dades dinàmiques massa antigues:</strong> ${{esc(excluded.join(' · '))}}. Es mostren com a context amb la seva data, però tenen pes zero en el perill d’avui.</p>` : ''}}
      ${{p.complete ? '' : creafNotModelled ? '<p class="eu-warning"><strong>Sense cel·la modelitzada ForestDrought.</strong> CREAF no publica potencial de foc per a aquest punt; el component no és aplicable i els pesos disponibles s’han renormalitzat sense inventar cap valor.</p>' : '<p class="eu-warning"><strong>Càlcul incomplet.</strong> Manquen una o més variables en aquesta cel·la; els pesos disponibles s’han renormalitzat i cap absència s’ha convertit en zero.</p>'}}
      <table><thead><tr><th>Component</th><th>Valor</th><th>0–100</th><th>Aportació</th><th>Data i estat</th></tr></thead><tbody>${{detailRows}}</tbody></table>
      <p class="eu-source">Resolució: 100 m. Lectura analítica EcoRadar; no és una alerta oficial ni el Pla Alfa.</p>`;
    firePopup.hidden = false;
    firePopup.querySelector('.eu-fire-popup-close').addEventListener('click', () => {{ firePopup.hidden = true; }});
  }}
  const zoom = d3.zoom().scaleExtent([1,12]).on('zoom',event => scene.attr('transform',event.transform));
  svg.call(zoom);
  root.querySelector('.eu-reset').addEventListener('click', () => svg.transition().duration(350).call(zoom.transform,d3.zoomIdentity));
  function showTip(event, html) {{
    const box = root.getBoundingClientRect();
    tooltip.html(html).style('opacity',1).style('left',`${{event.clientX-box.left+12}}px`).style('top',`${{event.clientY-box.top+12}}px`);
  }}
  function hideTip() {{ tooltip.style('opacity',0); }}
  async function refreshRemoteSnapshot() {{
    const status = root.querySelector('#eu-live-status');
    try {{
      const response = await fetch('/api/daily-readings', {{cache:'no-store', headers:{{accept:'application/json'}}}});
      if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
      const snapshot = await response.json();
      const remote = snapshot.current_fire_danger;
      if (!remote?.summary || !snapshot.checked_at_utc) throw new Error('resposta remota incompleta');
      const fire = {{
        checkedAtUtc: snapshot.checked_at_utc,
        status: remote.status,
        summary: remote.summary,
        weather: remote.weather,
        meteorology: remote.meteorology_context,
        plaAlfa: remote.pla_alfa,
        variables: remote.variables_today,
        weights: remote.weights,
        effectiveWeights: remote.effective_weights || remote.weights,
        freshnessPolicy: remote.freshness_policy || {{}},
        normalization: remote.normalization,
        cells: D.currentFire.cells
      }};
      D.dailyReadings = snapshot.daily_readings;
      D.dailyHistory = snapshot.daily_history;
      updateCurrentFireSummary(fire);
      const token = encodeURIComponent(snapshot.checked_at_utc);
      if (snapshot.assets?.current_fire_raster_url) {{
        rasterGroups.fireCurrent.attr('href', `${{snapshot.assets.current_fire_raster_url}}?checked=${{token}}`);
      }}
      if (snapshot.assets?.current_fire_cells_url) {{
        const cellsResponse = await fetch(`${{snapshot.assets.current_fire_cells_url}}?checked=${{token}}`, {{cache:'no-store'}});
        if (cellsResponse.ok) {{
          const cells = await cellsResponse.json();
          D.currentFire.cells = cells;
          renderCurrentFireCells(cells);
        }}
      }}
      status.className = 'eu-live-status is-live';
      status.textContent = `Lectura remota actualitzada · comprovació real ${{humanDate(snapshot.checked_at_utc)}}`;
    }} catch (error) {{
      status.className = 'eu-live-status is-fallback';
      status.textContent = `No s’ha pogut consultar la font remota. Es mostra la reserva empaquetada, comprovada ${{humanDate(D.currentFire.checkedAtUtc)}}.`;
    }}
  }}
  const reportBuilder = window.EcoRadarAlinyaReportProfiles.buildFactory(D, modeGuides, layerGuides);
  window.EcoRadarReadingReport.mount({{
    root,
    getSelection:() => ({{...activeGuide, mode:activeMode, guide:currentGuide()}}),
    getMapSvg:() => root.querySelector('.eu-map-panel svg'),
    buildReport:reportBuilder
  }});
  applyMode('base');
  refreshRemoteSnapshot();
}})();
</script>
</body>
</html>
"""


def write_package() -> None:
    data = build_data()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "vendor").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "docs").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metadata").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "history").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "netlify" / "functions").mkdir(parents=True, exist_ok=True)
    shutil.copy2(VENDOR_D3, OUT_DIR / "vendor" / "d3.min.js")
    shutil.copy2(HTML2PDF, OUT_DIR / "vendor" / HTML2PDF.name)
    shutil.copy2(HTML2PDF_LICENSE, OUT_DIR / "vendor" / HTML2PDF_LICENSE.name)
    shutil.copy2(REPORT_ENGINE, OUT_DIR / "vendor" / REPORT_ENGINE.name)
    shutil.copy2(REPORT_PROFILES, OUT_DIR / "vendor" / REPORT_PROFILES.name)
    html_text = render_index(data)
    (OUT_DIR / "index.html").write_text(html_text, encoding="utf-8")
    STANDALONE_HTML.write_text(
        html_text
        .replace('<script src="./vendor/d3.min.js"></script>', '<script src="./ecoradar-alinya-netlify-v2/vendor/d3.min.js"></script>')
        .replace('<script src="./vendor/html2pdf.bundle.min.js"></script>', '<script src="./ecoradar-alinya-netlify-v2/vendor/html2pdf.bundle.min.js"></script>')
        .replace('<script src="./vendor/ecoradar-reading-report.js"></script>', '<script src="./ecoradar-alinya-netlify-v2/vendor/ecoradar-reading-report.js"></script>')
        .replace('<script src="./vendor/ecoradar-alinya-report-profiles.js"></script>', '<script src="./ecoradar-alinya-netlify-v2/vendor/ecoradar-alinya-report-profiles.js"></script>'),
        encoding="utf-8",
    )
    (OUT_DIR / "netlify.toml").write_text(
        """[build]
  publish = "."
  functions = "netlify/functions"

[[redirects]]
  from = "/api/daily-readings"
  to = "/.netlify/functions/daily-readings"
  status = 200

[[headers]]
  for = "/*"
  [headers.values]
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "camera=(), microphone=(), geolocation=()"
    Cache-Control = "no-cache, no-store, must-revalidate"

[[headers]]
  for = "/vendor/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

[[headers]]
  for = "/projectes/Alinya/maps/incendis/*"
  [headers.values]
    Access-Control-Allow-Origin = "*"
""",
        encoding="utf-8",
    )
    (OUT_DIR / "README.md").write_text(
        """# EcoRadar Alinyà v2 — paquet Netlify

Aquest directori es pot publicar directament a Netlify. La funció
`/api/daily-readings` consulta el repositori GitHub canònic a cada càrrega; els
JSON empaquetats només s'utilitzen com a reserva si falla la consulta remota.

Si el repositori GitHub és privat, configura
`ECORADAR_DATA_BASE_URL=https://main--NOM_DEL_LLOC.netlify.app/projectes/Alinya`
amb l'àlies de branca del mateix projecte. Si és públic, també es pot
configurar `ECORADAR_GITHUB_REPOSITORY=propietari/repositori` i,
opcionalment, `ECORADAR_GITHUB_BRANCH` (per defecte `main`).

## Contingut

- `index.html`: experiencia EcoRadar reorganitzada per a la Muntanya d'Alinya, amb lectura executiva i tecnica completa.
- `vendor/d3.min.js`: D3 servit localment, com al model EcoRadar Urba.
- `vendor/html2pdf.bundle.min.js`: exportació PDF local mitjançant descàrrega, sense obrir el diàleg d’impressió.
- `vendor/ecoradar-reading-report.js`: motor reutilitzable de previsualització i exportació PDF.
- `vendor/ecoradar-alinya-report-profiles.js`: interpretacions contextuals d’Alinyà basades en les dades reals del visor.
- `docs/data-sources-matrix.md`: matriu de fonts del projecte Alinya.
- `docs/fire-source.md`: nota de traçabilitat de la capa d'incendis.
- `docs/current-fire-danger-source.md`: metodologia i fonts oficials del perill actual.
- `metadata/current_fire_danger.json`: comprovacio, variables, pesos, resultats i limitacions.
- `metadata/daily_readings.json` i `metadata/daily_history.json`: reserva coherent.
- `netlify/functions/daily-readings.mjs`: lectura remota del repositori canònic.

La capa de concurrencia no es probabilitat oficial d'incendi ni perill diari.
La lectura `Perill d'incendi avui` es un index analitic EcoRadar de 0 a 100
calculat en cel·les de 100 m,
no una alerta oficial ni el Pla Alfa. Utilitza meteorologia XEMA Y4 i
renormalitza els pesos si una variable no esta disponible.
La geometria historica d'incendis va ser consultada el 17.07.2026.
La concurrencia mostrada al visor utilitza nomes els perimetres historics
oficials d'Alinya i les condicions territorials ja processades. No incorpora
EFFIS, FIRMS ni registres operatius recents sense perimetre consolidat.
""",
        encoding="utf-8",
    )
    (OUT_DIR / "docs" / "data-sources-matrix.md").write_text(source_matrix_md(), encoding="utf-8")
    shutil.copy2(
        ROOT / "docs" / "data_sources" / "fire" / "current-wildfire-danger-alinya.md",
        OUT_DIR / "docs" / "current-fire-danger-source.md",
    )
    shutil.copy2(
        PROJECT / "indicators" / "current_fire_danger.json",
        OUT_DIR / "metadata" / "current_fire_danger.json",
    )
    for name in ("daily_readings.json", "daily_history.json"):
        shutil.copy2(PROJECT / "indicators" / name, OUT_DIR / "metadata" / name)
    for name in ("daily_readings_observations.jsonl", "daily_readings_checks.jsonl"):
        shutil.copy2(PROJECT / "history" / name, OUT_DIR / "history" / name)
    shutil.copy2(
        DAILY_FUNCTION,
        OUT_DIR / "netlify" / "functions" / "daily-readings.mjs",
    )
    shutil.copy2(
        ROOT / "docs" / "data_sources" / "alinya_daily_readings.md",
        OUT_DIR / "docs" / "alinya-daily-readings-source.md",
    )
    shutil.copy2(THIRD_PARTY_NOTICES, OUT_DIR / "THIRD_PARTY_NOTICES.md")
    (OUT_DIR / "docs" / "fire-source.md").write_text(
        """# Font d'incendis forestals

El visor no utilitza IncendisCat com a font de dades.

La geometria local incorporada prove de les capes ja processades al projecte:
`projectes/Alinya/maps/incendis/incendis_historics_alinya_clip.geojson`.

La propietat `font` dels elements indica:
`Generalitat de Catalunya WFS VEGETACIO:VEGETACIO_INCENDIS`.

Estat: font oficial documentada localment al projecte. L'index integrat combina
el mapa estructural oficial 2024 amb LST estival Landsat, NDMI, tipus de coberta
i concurrencia territorial. El risc operatiu requereix meteorologia diaria,
Pla Alfa i combustible i humitat fina validats.

## Actualitzacio de concurrencia

La capa `Concurrencia` es calcula dins l'ambit d'Alinya amb els perimetres
historics oficials com a base de comparacio:

1. Manté la similitud ambiental base ja processada per EcoRadar: coberta,
   habitat, pendent, orientacio, altitud i accessibilitat.
2. Utilitza nomes els dos perimetres historics oficials dins l'ambit com a base
   de comparacio.
3. No incorpora registres recents sense perimetre, FIRMS ni geometries externes.
4. No converteix aquest resultat en probabilitat oficial ni en risc diari.
""",
        encoding="utf-8",
    )
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(OUT_DIR.rglob("*")):
            zf.write(path, path.relative_to(OUT_DIR))
    print(OUT_DIR)
    print(ZIP_PATH)
    print(STANDALONE_HTML)


if __name__ == "__main__":
    write_package()
