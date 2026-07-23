"""Build an evidence-based fire-condition similarity map for Alinya.

This is not a fire-probability model. It creates derived layers that compare
the study area with the conditions observed in the official historical burned
polygons currently available for Alinya.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union


PROJECT = Path("projectes/Alinya")
OUT_RAW = PROJECT / "raw/terrain"
OUT_PROC = PROJECT / "processed/incendis_similarity"
OUT_MAPS = PROJECT / "maps/incendis_similarity"
OUT_META = PROJECT / "metadata/incendis_similarity"
OUT_IND = PROJECT / "indicators/incendis_similarity"

DEM_URL = (
    "https://datacloud.icgc.cat/datacloud/model-elevacions-terreny/tif_unzip/"
    "model-elevacions-terreny-topografic-catalunya-5m-2009-2018.tif"
)


def ensure_dirs() -> None:
    for path in [OUT_RAW, OUT_PROC, OUT_MAPS, OUT_META, OUT_IND]:
        path.mkdir(parents=True, exist_ok=True)


def cover_group(value: str) -> str:
    s = str(value)
    if "Boscos" in s or "Bosc de ribera" in s:
        return "Bosc"
    if "Matollar" in s:
        return "Matollar"
    if "Prats" in s or "herbassars" in s:
        return "Prats i herbassars"
    if "Conreus" in s:
        return "Conreus"
    if "Cursos d'aigua" in s:
        return "Aigua"
    if "Xarxa" in s or "Casc urb" in s:
        return "Vies i nuclis"
    if "Roquissars" in s:
        return "Roquissars / sol nu"
    return "Altres"


def aspect_class(degrees: float | None) -> str:
    if degrees is None or np.isnan(degrees):
        return "sense_dada"
    # Aspect from np.gradient is converted to 0=N, 90=E, 180=S, 270=W.
    if degrees >= 315 or degrees < 45:
        return "N"
    if degrees < 135:
        return "E"
    if degrees < 225:
        return "S"
    return "W"


def slope_class(degrees: float | None) -> str:
    if degrees is None or np.isnan(degrees):
        return "sense_dada"
    if degrees < 10:
        return "suau"
    if degrees < 25:
        return "mitja"
    if degrees < 35:
        return "forta"
    return "molt_forta"


def distance_score(value: float, samples: list[float]) -> float:
    if not samples or np.isnan(value):
        return 0.0
    med = float(np.median(samples))
    spread = max(float(np.std(samples)), 75.0)
    return float(max(0.0, 1.0 - abs(value - med) / (spread * 3.0)))


def numeric_similarity(value: float, samples: list[float], floor: float) -> float:
    if not samples or np.isnan(value):
        return 0.0
    med = float(np.median(samples))
    spread = max(float(np.std(samples)), floor)
    return float(max(0.0, 1.0 - abs(value - med) / (spread * 2.5)))


def circular_aspect_similarity(value: float, samples: list[float]) -> float:
    if not samples or np.isnan(value):
        return 0.0
    radians = np.deg2rad(samples)
    mean_angle = math.degrees(math.atan2(float(np.sin(radians).mean()), float(np.cos(radians).mean())))
    if mean_angle < 0:
        mean_angle += 360
    diff = abs((value - mean_angle + 180) % 360 - 180)
    return float(max(0.0, 1.0 - diff / 90.0))


def read_or_download_dem(study: gpd.GeoDataFrame) -> Path:
    out_path = OUT_RAW / "icgc_dem_5m_alinya_window.tif"
    if out_path.exists():
        return out_path

    minx, miny, maxx, maxy = study.total_bounds
    margin = 250.0
    with rasterio.open(DEM_URL) as src:
        window = from_bounds(minx - margin, miny - margin, maxx + margin, maxy + margin, src.transform)
        data = src.read(1, window=window, masked=True)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            transform=transform,
            compress="deflate",
            predictor=2,
            tiled=True,
        )
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data.filled(src.nodata if src.nodata is not None else -9999), 1)
    return out_path


def derive_topography(dem_path: Path) -> tuple[Path, Path]:
    slope_path = OUT_PROC / "pendent_icgc_derived_alinya.tif"
    aspect_path = OUT_PROC / "orientacio_icgc_derived_alinya.tif"
    if slope_path.exists() and aspect_path.exists():
        return slope_path, aspect_path

    with rasterio.open(dem_path) as src:
        z = src.read(1).astype("float32")
        nodata = src.nodata
        if nodata is not None:
            z[z == nodata] = np.nan
        res_x, res_y = src.res
        dz_dy, dz_dx = np.gradient(z, res_y, res_x)
        slope = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))).astype("float32")
        aspect = (np.degrees(np.arctan2(dz_dx, -dz_dy)) + 360.0) % 360.0
        aspect = aspect.astype("float32")
        slope[np.isnan(z)] = -9999
        aspect[np.isnan(z)] = -9999
        profile = src.profile.copy()
        profile.update(dtype="float32", nodata=-9999, compress="deflate", predictor=2)
        with rasterio.open(slope_path, "w", **profile) as dst:
            dst.write(slope, 1)
        with rasterio.open(aspect_path, "w", **profile) as dst:
            dst.write(aspect, 1)
    return slope_path, aspect_path


def sample_raster(path: Path, points: list[Point]) -> list[float]:
    with rasterio.open(path) as src:
        values = []
        for (value,) in src.sample([(p.x, p.y) for p in points]):
            val = float(value)
            if src.nodata is not None and val == src.nodata:
                val = float("nan")
            values.append(val)
        return values


def build_grid(study_geom, size: float = 150.0) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = study_geom.bounds
    rows = []
    y = miny
    idx = 0
    while y < maxy:
        x = minx
        while x < maxx:
            geom = box(x, y, min(x + size, maxx), min(y + size, maxy)).intersection(study_geom)
            if not geom.is_empty and geom.area > 1000:
                rows.append({"cell_id": idx, "geometry": geom})
                idx += 1
            x += size
        y += size
    return gpd.GeoDataFrame(rows, crs="EPSG:25831")


def normalize_for_svg(bounds, box_area):
    minx, miny, maxx, maxy = bounds
    left, top, width, height = box_area
    scale = min(width / (maxx - minx), height / (maxy - miny))
    actual_w = (maxx - minx) * scale
    actual_h = (maxy - miny) * scale
    left += (width - actual_w) / 2
    top += (height - actual_h) / 2

    def xy(x, y):
        return left + (x - minx) * scale, top + (maxy - y) * scale

    return xy, left, top, actual_w, actual_h


def ring_path(coords, xy):
    pts = list(coords)
    if not pts:
        return ""
    x0, y0 = xy(*pts[0])
    d = [f"M {x0:.2f} {y0:.2f}"]
    for x, y, *_ in pts[1:]:
        X, Y = xy(x, y)
        d.append(f"L {X:.2f} {Y:.2f}")
    d.append("Z")
    return " ".join(d)


def polygon_paths(geom, xy):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        d = ring_path(geom.exterior.coords, xy)
        for interior in geom.interiors:
            d += " " + ring_path(interior.coords, xy)
        return [d]
    if isinstance(geom, MultiPolygon):
        out = []
        for part in geom.geoms:
            out.extend(polygon_paths(part, xy))
        return out
    if isinstance(geom, GeometryCollection):
        out = []
        for part in geom.geoms:
            out.extend(polygon_paths(part, xy))
        return out
    return []


def line_paths(geom, xy):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        coords = list(geom.coords)
        if len(coords) < 2:
            return []
        x0, y0 = xy(*coords[0])
        d = [f"M {x0:.2f} {y0:.2f}"]
        for x, y, *_ in coords[1:]:
            X, Y = xy(x, y)
            d.append(f"L {X:.2f} {Y:.2f}")
        return [" ".join(d)]
    if isinstance(geom, MultiLineString):
        out = []
        for part in geom.geoms:
            out.extend(line_paths(part, xy))
        return out
    if isinstance(geom, GeometryCollection):
        out = []
        for part in geom.geoms:
            out.extend(line_paths(part, xy))
        return out
    return []


def score_color(score: float) -> str:
    if score >= 0.72:
        return "#c43d32"
    if score >= 0.52:
        return "#e6863a"
    if score >= 0.34:
        return "#e3c85d"
    return "#d7dfbf"


def build_svg(study, grid, fires, cover, access, metadata):
    width, height = 1280, 1280
    minx, miny, maxx, maxy = study.total_bounds
    bounds = (minx - 600, miny - 600, maxx + 600, maxy + 600)
    xy, left, top, aw, ah = normalize_for_svg(bounds, (54, 104, 850, 735))

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    svg.append('<rect width="100%" height="100%" fill="#f6f4ee"/>')
    svg.append('<text x="54" y="44" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#173f35">Muntanya d’Alinyà · similitud ambiental amb incendis històrics</text>')
    svg.append('<text x="54" y="70" font-family="Arial, sans-serif" font-size="14" fill="#5f665c">Capa heurística de similitud, no probabilitat oficial ni predicció operativa.</text>')
    svg.append(f'<rect x="{left-8:.1f}" y="{top-8:.1f}" width="{aw+16:.1f}" height="{ah+16:.1f}" fill="#ffffff" stroke="#d4d0c5"/>')
    svg.append(f'<defs><clipPath id="mainclip"><rect x="{left-8:.1f}" y="{top-8:.1f}" width="{aw+16:.1f}" height="{ah+16:.1f}"/></clipPath></defs>')
    svg.append('<g clip-path="url(#mainclip)">')

    # Base condition polygons
    base_colors = {
        "Bosc": "#52785a",
        "Matollar": "#c58b43",
        "Prats i herbassars": "#9dbb68",
        "Conreus": "#d8c96a",
        "Aigua": "#77a8c8",
        "Vies i nuclis": "#b9b5ac",
        "Roquissars / sol nu": "#d8d1c2",
        "Altres": "#ece7dd",
    }
    for _, row in cover.iterrows():
        for d in polygon_paths(row.geometry.simplify(18, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="{base_colors.get(row.condicio, "#eee")}" stroke="#ffffff" stroke-width="0.25" opacity="0.55"/>')

    # Similarity grid
    for _, row in grid.iterrows():
        color = score_color(float(row.similitud_score))
        for d in polygon_paths(row.geometry.simplify(5, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="{color}" stroke="none" opacity="0.46"/>')

    # Access network
    for geom in access.geometry:
        for d in line_paths(geom.simplify(12, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="none" stroke="#2d2b28" stroke-width="0.8" opacity="0.45" stroke-linecap="round"/>')

    # Official fires
    for _, row in fires.iterrows():
        for d in polygon_paths(row.geometry.simplify(2, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="#d7382f" fill-opacity="0.62" stroke="#7d1712" stroke-width="2.8"/>')

    # Boundary
    for geom in study.geometry:
        for d in polygon_paths(geom.simplify(8, preserve_topology=True), xy):
            svg.append(f'<path d="{d}" fill="none" stroke="#173f35" stroke-width="3"/>')

    svg.append("</g>")

    # Fire labels
    for _, row in fires.iterrows():
        p = row.geometry.representative_point()
        x, y = xy(p.x, p.y)
        label = str(row.etiqueta_foc)
        svg.append(f'<rect x="{x-28:.1f}" y="{y-31:.1f}" width="56" height="24" rx="12" fill="#fff8f0" stroke="#8f1712" stroke-width="1.4"/>')
        svg.append(f'<text x="{x:.1f}" y="{y-15:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" font-weight="700" fill="#7d1712">{label}</text>')

    # Scale bar
    x0, _ = xy(0, 0)
    x1, _ = xy(2000, 0)
    bx, by = left + 22, top + ah - 30
    svg.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx+abs(x1-x0):.1f}" y2="{by:.1f}" stroke="#173f35" stroke-width="4"/>')
    svg.append(f'<text x="{bx+abs(x1-x0)/2:.1f}" y="{by-9:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#173f35">2 km</text>')

    # Side evidence panel
    panel_x = 940
    svg.append(f'<rect x="{panel_x}" y="106" width="290" height="730" rx="7" fill="#ffffff" stroke="#d4d0c5"/>')
    svg.append(f'<text x="{panel_x+20}" y="140" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#173f35">Capes de similitud</text>')
    legend = [
        ("Alta similitud", "#c43d32", "mateixes condicions dominants"),
        ("Mitjana-alta", "#e6863a", "força coincidència"),
        ("Mitjana", "#e3c85d", "coincidència parcial"),
        ("Baixa", "#d7dfbf", "poca semblança"),
    ]
    y = 172
    for title, color, desc in legend:
        svg.append(f'<rect x="{panel_x+22}" y="{y-14}" width="18" height="18" fill="{color}" opacity="0.72"/>')
        svg.append(f'<text x="{panel_x+50}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">{title}</text>')
        svg.append(f'<text x="{panel_x+50}" y="{y+16}" font-family="Arial, sans-serif" font-size="10.5" fill="#6b7068">{desc}</text>')
        y += 43
    y += 8
    svg.append(f'<text x="{panel_x+20}" y="{y}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#173f35">Variables usades</text>')
    y += 24
    variables = [
        "Perímetres oficials 2000 i 2012",
        "Cobertes del sòl ICGC processades",
        "Hàbitats terrestres v3",
        "Pendent, orientació i altitud ICGC",
        "Distància a camins/pistes OSM",
    ]
    for item in variables:
        svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">• {item}</text>')
        y += 21
    y += 10
    svg.append(f'<text x="{panel_x+20}" y="{y}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#173f35">Mostra històrica</text>')
    y += 24
    for row in metadata["fire_sample_summary"]:
        svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">{row["year"]}: {row["area_ha"]:.1f} ha</text>')
        y += 19
        svg.append(f'<text x="{panel_x+34}" y="{y}" font-family="Arial, sans-serif" font-size="10.5" fill="#6b7068">pendent {row["slope_deg"]:.1f}°, orient. {row["aspect_class"]}, {row["cover_group"]}</text>')
        y += 22
    y += 8
    svg.append(f'<text x="{panel_x+20}" y="{y}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#173f35">Límit</text>')
    y += 22
    notes = [
        "No és probabilitat estadística.",
        "Només hi ha 2 incendis locals",
        "amb perímetre oficial.",
        "Cal validar camp, hidrologia,",
        "humitat i meteorologia.",
        "Llinars queda confirmat per",
        "Bombers però sense geometria.",
    ]
    for note in notes:
        svg.append(f'<text x="{panel_x+22}" y="{y}" font-family="Arial, sans-serif" font-size="11.5" fill="#5f665c">{note}</text>')
        y += 18

    # Bottom table
    lx, ly, lw, lh = 54, 890, 1172, 280
    svg.append(f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" rx="7" fill="#ffffff" stroke="#d4d0c5"/>')
    svg.append(f'<text x="{lx+20}" y="{ly+34}" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#173f35">Lectura ecològica prudent</text>')
    lines = [
        ("Evidència", "Dos perímetres oficials dins l’àmbit; el registre de Llinars 24/06/2026 és oficial però no georeferenciable i queda fora d’Alinyà."),
        ("Concurrència", "S’ha calculat semblança de coberta, hàbitat, pendent, orientació, altitud i accessibilitat respecte dels incendis locals."),
        ("Ús correcte", "Serveix per orientar camp i preguntes de gestió; no per afirmar on cremarà."),
        ("Següent pas", "Completar Pla Alfa, meteo, humitat/NDMI, punts d’aigua i validació de camp abans de parlar de probabilitat."),
    ]
    y = ly + 66
    for head, text in lines:
        svg.append(f'<text x="{lx+22}" y="{y}" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#173f35">{head}</text>')
        svg.append(f'<text x="{lx+126}" y="{y}" font-family="Arial, sans-serif" font-size="12" fill="#373d36">{text}</text>')
        y += 44
    svg.append('<text x="54" y="1232" font-family="Arial, sans-serif" font-size="10.5" fill="#5f665c">Fonts: Generalitat/ICGC WFS incendis, ICGC cobertes i DEM, hàbitats terrestres v3, OSM accessos, Bombers g2ay-3vnj per Llinars. IncendisCAT consultat només com a context no oficial.</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def main() -> None:
    ensure_dirs()
    study = gpd.read_file(PROJECT / "processed/study_area.gpkg", layer="study_area").to_crs("EPSG:25831")
    study_geom = study.geometry.union_all()

    fires = gpd.read_file(PROJECT / "processed/incendis/incendis_historics_alinya_clip.gpkg", layer="incendis_historics_clip").to_crs("EPSG:25831")
    fires = fires[fires.geometry.area > 1000].copy()
    fires["centroid"] = fires.representative_point()

    cover = gpd.read_file(PROJECT / "processed/cobertes_sol.gpkg", layer="cobertes_sol").to_crs("EPSG:25831")
    cover["condicio"] = cover["tipus_coberta"].apply(cover_group)
    cover["geometry"] = cover.geometry.intersection(study_geom)
    cover = cover[~cover.geometry.is_empty & cover.geometry.notna()].copy()
    cover_diss = cover.dissolve(by="condicio", as_index=False, aggfunc="first")[["condicio", "geometry"]]

    habitats = gpd.read_file(PROJECT / "processed/habitats.gpkg", layer="habitats").to_crs("EPSG:25831")
    habitats = habitats[["COD_CORINE", "CORINE_CA", "COD_HIC", "geometry"]].copy()

    access = gpd.read_file(PROJECT / "processed/recreational_pressure.gpkg", layer="osm_paths_tracks_roads").to_crs("EPSG:25831")
    access["geometry"] = access.geometry.intersection(study_geom)
    access = access[~access.geometry.is_empty & access.geometry.notna()].copy()
    access_union = access.geometry.union_all()

    dem_path = read_or_download_dem(study)
    slope_path, aspect_path = derive_topography(dem_path)

    fire_points = list(fires["centroid"])
    fires["slope_deg"] = sample_raster(slope_path, fire_points)
    fires["aspect_deg"] = sample_raster(aspect_path, fire_points)
    fires["elevation_m"] = sample_raster(dem_path, fire_points)
    fires["aspect_class"] = fires["aspect_deg"].apply(aspect_class)
    fires["slope_class"] = fires["slope_deg"].apply(slope_class)
    fires["distance_to_access_m"] = fires.geometry.distance(access_union)

    fires_for_join = gpd.GeoDataFrame(fires[["OBJECTID"]].copy(), geometry=fires["centroid"], crs=fires.crs)
    fire_cover = gpd.sjoin(fires_for_join, cover[["condicio", "geometry"]], how="left", predicate="within")
    cover_lookup = fire_cover.drop_duplicates("OBJECTID").set_index("OBJECTID")["condicio"].to_dict()
    fires["cover_group"] = fires["OBJECTID"].map(cover_lookup).fillna("sense_dada")
    fire_hab = gpd.sjoin(fires_for_join, habitats[["COD_CORINE", "CORINE_CA", "geometry"]], how="left", predicate="within")
    hab_lookup = fire_hab.drop_duplicates("OBJECTID").set_index("OBJECTID")["COD_CORINE"].to_dict()
    fires["COD_CORINE"] = fires["OBJECTID"].map(hab_lookup).fillna("sense_dada")

    grid = build_grid(study_geom, 150.0)
    grid["centroid"] = grid.representative_point()
    grid_points = list(grid["centroid"])
    grid["slope_deg"] = sample_raster(slope_path, grid_points)
    grid["aspect_deg"] = sample_raster(aspect_path, grid_points)
    grid["elevation_m"] = sample_raster(dem_path, grid_points)
    grid["aspect_class"] = grid["aspect_deg"].apply(aspect_class)
    grid["slope_class"] = grid["slope_deg"].apply(slope_class)
    grid["distance_to_access_m"] = grid.geometry.distance(access_union)

    grid_for_join = gpd.GeoDataFrame(grid[["cell_id"]].copy(), geometry=grid["centroid"], crs=grid.crs)
    grid_cover = gpd.sjoin(grid_for_join, cover[["condicio", "geometry"]], how="left", predicate="within")
    grid["cover_group"] = grid["cell_id"].map(grid_cover.drop_duplicates("cell_id").set_index("cell_id")["condicio"].to_dict()).fillna("sense_dada")
    grid_hab = gpd.sjoin(grid_for_join, habitats[["COD_CORINE", "CORINE_CA", "geometry"]], how="left", predicate="within")
    grid["COD_CORINE"] = grid["cell_id"].map(grid_hab.drop_duplicates("cell_id").set_index("cell_id")["COD_CORINE"].to_dict()).fillna("sense_dada")

    fire_covers = set(fires["cover_group"])
    fire_habs = set(fires["COD_CORINE"])
    fire_aspects = [float(v) for v in fires["aspect_deg"] if pd.notna(v)]
    fire_slopes = [float(v) for v in fires["slope_deg"] if pd.notna(v)]
    fire_elev = [float(v) for v in fires["elevation_m"] if pd.notna(v)]
    fire_dist = [float(v) for v in fires["distance_to_access_m"] if pd.notna(v)]

    grid["score_coberta"] = grid["cover_group"].apply(lambda x: 1.0 if x in fire_covers else 0.0)
    grid["score_habitat"] = grid["COD_CORINE"].apply(lambda x: 1.0 if x in fire_habs else 0.0)
    grid["score_pendent"] = grid["slope_deg"].apply(lambda v: numeric_similarity(float(v), fire_slopes, 6.0))
    grid["score_orientacio"] = grid["aspect_deg"].apply(lambda v: circular_aspect_similarity(float(v), fire_aspects))
    grid["score_altitud"] = grid["elevation_m"].apply(lambda v: numeric_similarity(float(v), fire_elev, 125.0))
    grid["score_accessibilitat"] = grid["distance_to_access_m"].apply(lambda v: distance_score(float(v), fire_dist))
    grid["similitud_score"] = (
        0.22 * grid["score_coberta"]
        + 0.18 * grid["score_habitat"]
        + 0.18 * grid["score_pendent"]
        + 0.14 * grid["score_orientacio"]
        + 0.12 * grid["score_altitud"]
        + 0.16 * grid["score_accessibilitat"]
    )
    grid["classe_similitud"] = pd.cut(
        grid["similitud_score"],
        bins=[-0.01, 0.34, 0.52, 0.72, 1.01],
        labels=["baixa", "mitjana", "mitjana_alta", "alta"],
    ).astype(str)

    fires_out = OUT_PROC / "incendis_historics_amb_condicions.gpkg"
    grid_out = OUT_PROC / "similitud_condicions_incendi_alinya.gpkg"
    fires.drop(columns=["centroid"]).to_file(fires_out, layer="incendis_condicions", driver="GPKG")
    grid.drop(columns=["centroid"]).to_file(grid_out, layer="similitud_condicions", driver="GPKG")
    grid.drop(columns=["centroid"]).to_file(OUT_MAPS / "similitud_condicions_incendi_alinya.geojson", driver="GeoJSON")

    llinars_path = PROJECT / "raw/incendis/bombers_llinars_incendis_vegetacio_2026.json"
    llinars_records = json.loads(llinars_path.read_text(encoding="utf-8")) if llinars_path.exists() else []

    summary = {
        "created_at": "2026-07-07",
        "status": "environmental_similarity_not_fire_probability",
        "cell_size_m": 150,
        "study_area_ha": float(study_geom.area / 10000),
        "official_fire_polygons_used": int(len(fires)),
        "fire_sample_summary": [
            {
                "year": str(row.etiqueta_foc),
                "area_ha": float(row.area_ha_dins_alinya),
                "cover_group": str(row.cover_group),
                "habitat_corine": str(row.COD_CORINE),
                "slope_deg": float(row.slope_deg),
                "slope_class": str(row.slope_class),
                "aspect_deg": float(row.aspect_deg),
                "aspect_class": str(row.aspect_class),
                "elevation_m": float(row.elevation_m),
                "distance_to_access_m": float(row.distance_to_access_m),
            }
            for _, row in fires.iterrows()
        ],
        "similarity_area_by_class_ha": {
            str(k): float(v)
            for k, v in (grid.assign(area_ha=grid.geometry.area / 10000).groupby("classe_similitud")["area_ha"].sum()).to_dict().items()
        },
        "llinars_bombers_records": llinars_records,
        "method": {
            "description": "Heuristic similarity to official local burned polygons; not a probability model.",
            "weights": {
                "land_cover": 0.22,
                "habitat": 0.18,
                "slope": 0.18,
                "aspect": 0.14,
                "elevation": 0.12,
                "distance_to_access": 0.16,
            },
        },
        "sources": [
            {
                "name": "Superficies afectades per incendis forestals v1.1 / VEGETACIO:VEGETACIO_INCENDIS",
                "organization": "Generalitat de Catalunya",
                "status": "verified",
                "path": str(PROJECT / "processed/incendis/incendis_historics_alinya_clip.gpkg"),
            },
            {
                "name": "Actuacions dels Bombers de la Generalitat",
                "organization": "DGPEIS / Departament d'Interior",
                "status": "official_tabular_context_no_geometry",
                "path": str(llinars_path),
            },
            {
                "name": "Cobertes del sol",
                "organization": "ICGC / EcoRadar processed project data",
                "status": "verified",
                "path": str(PROJECT / "processed/cobertes_sol.gpkg"),
            },
            {
                "name": "Cartografia dels habitats terrestres v3",
                "organization": "Generalitat de Catalunya",
                "status": "verified",
                "path": str(PROJECT / "processed/habitats.gpkg"),
            },
            {
                "name": "Model d'elevacions del terreny 5m",
                "organization": "ICGC",
                "status": "verified",
                "url": DEM_URL,
                "path": str(dem_path),
            },
            {
                "name": "Accessos OSM processats",
                "organization": "OpenStreetMap contributors",
                "status": "verified",
                "path": str(PROJECT / "processed/recreational_pressure.gpkg"),
            },
        ],
        "not_used": [
            "IncendisCAT: consulted only as non-official context; not used as EcoRadar data source.",
            "Pla Alfa: pending verification.",
            "EFFIS: pending connector-grade endpoint and license verification.",
            "Meteocat/AEMET: require credentials before implementation.",
            "Sentinel NDMI/NDVI: requires Copernicus credentials.",
            "Hydrology/water points: pending exact official layer.",
        ],
    }
    (OUT_META / "similitud_condicions_incendi_alinya_metadata.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "metric": "area_ha_" + cls,
                "value": area,
            }
            for cls, area in summary["similarity_area_by_class_ha"].items()
        ]
    ).to_csv(OUT_IND / "similitud_condicions_resum.csv", index=False)

    svg = build_svg(study, grid, fires, cover_diss, access, summary)
    (OUT_MAPS / "mapa_similitud_condicions_incendi_alinya.svg").write_text(svg, encoding="utf-8")

    readme = f"""# Similitud ambiental amb incendis historics - Alinya

Status: `environmental_similarity_not_fire_probability`

Aquest producte compara la Muntanya d'Alinya amb les condicions observades als dos perimetres oficials d'incendi disponibles dins l'ambit. No es un model de probabilitat ni una prediccio operativa.

## Sortides

- `mapa_similitud_condicions_incendi_alinya.svg`: mapa visual.
- `similitud_condicions_incendi_alinya.geojson`: grid de similitud.
- `../../processed/incendis_similarity/similitud_condicions_incendi_alinya.gpkg`: capa processada.
- `../../processed/incendis_similarity/incendis_historics_amb_condicions.gpkg`: incendis amb atributs de mostra.
- `../../metadata/incendis_similarity/similitud_condicions_incendi_alinya_metadata.json`: metode, fonts i limitacions.

## Fonts incorporades

- Perimetres oficials d'incendi WFS Generalitat.
- Cobertes del sol processades.
- Habitats terrestres v3 processats.
- DEM ICGC 5 m per altitud, pendent i orientacio.
- Accessos OSM processats.
- Dataset oficial de Bombers `g2ay-3vnj` nomes per documentar Llinars; no aporta geometria.

## Llinars

El dataset oficial de Bombers confirma registres d'incendi de vegetacio a Llinars del Valles el 2026, incloent `2026-06-24` com a incendi de vegetacio urbana. No s'incorpora al mapa d'Alinya perque no te coordenades/perimetre i queda fora de l'ambit.

## Limitacio

No s'han incorporat fonts bloquejades, pendents o amb credencials: IncendisCAT, Pla Alfa, EFFIS, Meteocat/AEMET, Sentinel NDMI/NDVI i hidrologia/punts d'aigua.
"""
    (OUT_MAPS / "README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()
