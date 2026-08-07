"""Calculate two traceable EcoRadar urban potential indicators.

This Analysis Engine module combines normalized layers. It does not download
data and never labels candidate facilities as official climate refuges.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from shapely.geometry import LineString, Point, box, mapping
from shapely.ops import substring, transform

from calculate_la_seu_urban_metrics import _shadow_mask


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
PROCESSED = PROJECT / "processed"
DERIVED = PROCESSED / "urban_potential"
INDICATOR = PROJECT / "indicators" / "urban_potential_services.json"
METADATA = PROJECT / "metadata" / "urban_potential_services.json"
OSM_XML = PROJECT / "raw" / "osm" / "la_seu_bbox.osm"
LIDAR = PROCESSED / "lidar_expanded_arrays.npz"
IMPERvious = PROCESSED / "copernicus_hrl_expanded" / "imperviousness_2021.tif"
SURFACE_SELECTION = PROJECT / "metadata" / "current_surface_temperature.json"
DAILY_SHADE = PROJECT / "indicators" / "daily_shade.json"
ROADS = PROCESSED / "mobility_osm.geojson"
FACILITIES = PROCESSED / "facilities_osm.geojson"
GREEN = PROCESSED / "green_spaces_osm.geojson"

STREET_WEIGHTS = {
    "shade_lidar": 0.25,
    "tree_canopy": 0.18,
    "surface_temperature": 0.20,
    "imperviousness": 0.12,
    "orientation": 0.08,
    "street_width": 0.07,
    "green_proximity": 0.10,
}
EQUIPMENT_WEIGHTS = {
    "shade": 0.20,
    "environment_temperature": 0.20,
    "accessibility": 0.15,
    "opening_hours": 0.10,
    "water": 0.10,
    "vulnerable_population": 0.10,
    "fresh_route_connection": 0.15,
}
WIDTH_DEFAULTS_M = {
    "trunk": 10.0,
    "trunk_link": 8.0,
    "primary": 9.0,
    "primary_link": 7.5,
    "tertiary": 7.0,
    "tertiary_link": 6.5,
    "residential": 6.0,
    "unclassified": 5.5,
    "service": 5.0,
    "living_street": 5.0,
    "pedestrian": 4.0,
    "cycleway": 3.0,
    "footway": 2.5,
    "path": 2.0,
    "steps": 2.0,
}
STREET_CLASSES = set(WIDTH_DEFAULTS_M)
EQUIPMENT_TYPES = {
    "hospital",
    "clinic",
    "school",
    "kindergarten",
    "social_facility",
    "community_centre",
    "library",
    "townhall",
    "bus_station",
}
GREEN_CANDIDATE_TYPES = {"leisure:park", "leisure:garden"}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _category(score: float) -> str:
    if score >= 67:
        return "alt"
    if score >= 34:
        return "mitjà"
    return "baix"


class GridSampler:
    def __init__(self, values: np.ndarray, valid: np.ndarray, transform_) -> None:
        self.values = values
        self.valid = valid & np.isfinite(values)
        self.transform = transform_
        self.height, self.width = values.shape

    def mean(self, geometry) -> float | None:
        if geometry is None or geometry.is_empty:
            return None
        minx, miny, maxx, maxy = geometry.bounds
        raw = rasterio.windows.from_bounds(minx, miny, maxx, maxy, self.transform)
        c0 = max(0, int(math.floor(raw.col_off)))
        r0 = max(0, int(math.floor(raw.row_off)))
        c1 = min(self.width, int(math.ceil(raw.col_off + raw.width)))
        r1 = min(self.height, int(math.ceil(raw.row_off + raw.height)))
        if c1 <= c0 or r1 <= r0:
            return None
        window = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
        local_transform = rasterio.windows.transform(window, self.transform)
        inside = geometry_mask(
            [mapping(geometry)],
            out_shape=(r1 - r0, c1 - c0),
            transform=local_transform,
            invert=True,
            all_touched=True,
        )
        valid = self.valid[r0:r1, c0:c1] & inside
        if not valid.any():
            return None
        return float(np.mean(self.values[r0:r1, c0:c1][valid]))


def _reproject_raster(path: Path, shape, transform_, crs, resampling) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as source:
        src = source.read(1).astype("float32")
        src_valid = source.read_masks(1) > 0
        if source.nodata is not None:
            src_valid &= src != source.nodata
        destination = np.full(shape, np.nan, dtype="float32")
        reproject(
            source=np.where(src_valid, src, np.nan),
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=transform_,
            dst_crs=crs,
            src_nodata=np.nan,
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return destination, np.isfinite(destination)


def _osm_tags_and_water() -> tuple[dict[str, dict[str, str]], list[Point]]:
    tags_by_ref: dict[str, dict[str, str]] = {}
    water: list[Point] = []
    for _, element in ET.iterparse(OSM_XML, events=("end",)):
        if element.tag not in {"node", "way"}:
            continue
        tags = {
            child.attrib.get("k", ""): child.attrib.get("v", "")
            for child in element
            if child.tag == "tag"
        }
        ref = f"{element.tag}/{element.attrib['id']}"
        if tags:
            tags_by_ref[ref] = tags
        if (
            element.tag == "node"
            and tags.get("amenity") in {"drinking_water", "fountain"}
            and element.attrib.get("lon")
            and element.attrib.get("lat")
        ):
            water.append(Point(float(element.attrib["lon"]), float(element.attrib["lat"])))
        element.clear()
    return tags_by_ref, water


def _split_line(line: LineString, max_length: float = 75.0) -> list[LineString]:
    if line.length <= max_length:
        return [line]
    parts = []
    for start in np.arange(0.0, line.length, max_length):
        part = substring(line, float(start), min(float(start + max_length), line.length))
        if isinstance(part, LineString) and part.length >= 5:
            parts.append(part)
    return parts


def _weighted_score(components: dict[str, float | None], weights: dict[str, float]) -> tuple[float, float]:
    available = [(key, value) for key, value in components.items() if value is not None]
    available_weight = sum(weights[key] for key, _ in available)
    if available_weight <= 0:
        return 0.0, 0.0
    score = sum(float(value) * weights[key] for key, value in available) / available_weight
    return round(_clamp(score), 1), round(available_weight * 100, 1)


def _axial_orientation(line: LineString, solar_azimuth_deg: float) -> tuple[float, float]:
    start = line.interpolate(0)
    end = line.interpolate(line.length)
    dx = end.x - start.x
    dy = end.y - start.y
    bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 180.0
    solar_axis = solar_azimuth_deg % 180.0
    delta = abs(bearing - solar_axis)
    delta = min(delta, 180.0 - delta)
    return bearing, abs(math.sin(math.radians(delta))) * 100.0


def _width(tags: dict[str, str], highway: str) -> tuple[float, str]:
    raw = tags.get("width", "").strip().lower().replace(",", ".")
    if raw:
        try:
            width = float(raw.split()[0])
            if 1.0 <= width <= 30.0:
                return width, "etiqueta OSM width"
        except ValueError:
            pass
    return WIDTH_DEFAULTS_M.get(highway, 5.0), "proxy EcoRadar segons classe OSM"


def _prepare_grids():
    lidar = np.load(LIDAR)
    dsm = lidar["dsm"].astype("float32")
    dtm = lidar["dtm"].astype("float32")
    canopy = lidar["canopy"].astype(bool)
    valid = lidar["valid"].astype(bool) & lidar["scope_mask"].astype(bool)
    bounds = [float(value) for value in lidar["bounds"]]
    transform_ = from_bounds(*bounds, dsm.shape[1], dsm.shape[0])
    crs = "EPSG:25831"
    shade_meta = _read_json(DAILY_SHADE)
    solar = shade_meta.get("value", {})
    if solar.get("solar_elevation_deg", 0) > 0:
        shade = _shadow_mask(
            dsm,
            dtm,
            canopy,
            abs(float(lidar["transform"][0])),
            float(solar["solar_elevation_deg"]),
            float(solar["solar_azimuth_deg"]),
        ) & valid
    else:
        shade = lidar["shade"].astype(bool) & valid
    selection = _read_json(SURFACE_SELECTION).get("selected", {})
    lst_path = ROOT / str(selection.get("normalized_tif", ""))
    if not lst_path.exists():
        raise FileNotFoundError("No selected detailed surface-temperature raster")
    lst, lst_valid = _reproject_raster(lst_path, dsm.shape, transform_, crs, Resampling.bilinear)
    impervious, impervious_valid = _reproject_raster(
        IMPERvious, dsm.shape, transform_, crs, Resampling.bilinear
    )
    return {
        "shade": GridSampler(shade.astype("float32"), valid, transform_),
        "canopy": GridSampler(canopy.astype("float32"), valid, transform_),
        "lst": GridSampler(lst, lst_valid & valid, transform_),
        "impervious": GridSampler(impervious, impervious_valid & valid, transform_),
        "slope": GridSampler(lidar["terrain_slope"].astype("float32"), valid, transform_),
        "lst_p10": float(np.nanpercentile(lst[lst_valid & valid], 10)),
        "lst_p90": float(np.nanpercentile(lst[lst_valid & valid], 90)),
        "solar_azimuth": float(solar.get("solar_azimuth_deg", 225.0)),
        "shade_data_at_utc": shade_meta.get("data_at_utc"),
        "surface_temperature": selection,
        "bounds": bounds,
    }


def _street_potential(grids, tags_by_ref, green_union) -> gpd.GeoDataFrame:
    roads = gpd.read_file(ROADS).to_crs(25831)
    roads = roads[roads["highway"].isin(STREET_CLASSES)].explode(index_parts=False)
    scope = box(*grids["bounds"])
    records = []
    for source in roads.itertuples():
        clipped = source.geometry.intersection(scope)
        if clipped.is_empty:
            continue
        lines = [clipped] if isinstance(clipped, LineString) else [
            geom for geom in getattr(clipped, "geoms", []) if isinstance(geom, LineString)
        ]
        part_number = 0
        tags = tags_by_ref.get(source.osm_ref, {})
        width_m, width_source = _width(tags, source.highway)
        for line in lines:
            for segment in _split_line(line):
                part_number += 1
                sample_area = segment.buffer(max(2.0, width_m / 2.0), cap_style=2)
                shade = grids["shade"].mean(sample_area)
                canopy = grids["canopy"].mean(sample_area)
                lst = grids["lst"].mean(sample_area)
                impervious = grids["impervious"].mean(sample_area)
                bearing, orientation_score = _axial_orientation(segment, grids["solar_azimuth"])
                green_distance = float(segment.distance(green_union))
                components = {
                    "shade_lidar": shade * 100 if shade is not None else None,
                    "tree_canopy": canopy * 100 if canopy is not None else None,
                    "surface_temperature": (
                        _clamp(
                            100
                            * (grids["lst_p90"] - lst)
                            / max(0.1, grids["lst_p90"] - grids["lst_p10"])
                        )
                        if lst is not None
                        else None
                    ),
                    "imperviousness": 100 - _clamp(impervious) if impervious is not None else None,
                    "orientation": orientation_score,
                    "street_width": 100 - _clamp((width_m - 2.0) / 8.0 * 100),
                    "green_proximity": 100 * (1 - _clamp(green_distance, 0, 250) / 250),
                }
                score, completeness = _weighted_score(components, STREET_WEIGHTS)
                confidence = round(
                    min(90.0, completeness * (0.78 if width_source.startswith("proxy") else 0.88)),
                    1,
                )
                records.append(
                    {
                        "segment_id": f"{source.osm_ref}-{part_number:03d}",
                        "osm_ref": source.osm_ref,
                        "name": source.name,
                        "highway": source.highway,
                        "length_m": round(segment.length, 1),
                        "width_m": round(width_m, 1),
                        "width_source": width_source,
                        "axis_bearing_deg": round(bearing, 1),
                        "shade_pct": round(shade * 100, 1) if shade is not None else None,
                        "canopy_pct": round(canopy * 100, 1) if canopy is not None else None,
                        "surface_temperature_c": round(lst, 1) if lst is not None else None,
                        "imperviousness_pct": round(impervious, 1) if impervious is not None else None,
                        "green_distance_m": round(green_distance, 1),
                        "freshness_score_0_100": score,
                        "freshness_class": _category(score),
                        "confidence_pct": confidence,
                        "indicator_type": (
                            "Potencial derivat EcoRadar; no és una temperatura "
                            "mesurada al carrer"
                        ),
                        "geometry": segment,
                    }
                )
    if not records:
        raise RuntimeError("No road segments could be evaluated")
    return gpd.GeoDataFrame(records, crs=25831)


def _equipment_potential(grids, tags_by_ref, water_points, streets, roads, green) -> gpd.GeoDataFrame:
    candidates = []
    for row in gpd.read_file(FACILITIES).to_crs(25831).itertuples():
        if row.kind in EQUIPMENT_TYPES:
            tags = tags_by_ref.get(row.osm_ref, {})
            if tags.get("access") not in {"private", "no"}:
                candidates.append(
                    {
                        "candidate_id": row.osm_ref,
                        "name": row.name or f"Equipament {row.osm_ref}",
                        "candidate_type": "equipament públic candidat",
                        "kind": row.kind,
                        "opening_hours": tags.get("opening_hours"),
                        "access_tag": tags.get("access"),
                        "geometry": row.geometry,
                    }
                )
    for row in green[green["kind"].isin(GREEN_CANDIDATE_TYPES)].itertuples():
        tags = tags_by_ref.get(row.osm_ref, {})
        if tags.get("access") not in {"private", "no"}:
            candidates.append(
                {
                    "candidate_id": row.osm_ref,
                    "name": row.name or f"Espai verd candidat {row.osm_ref}",
                    "candidate_type": "espai verd candidat",
                    "kind": row.kind,
                    "opening_hours": tags.get("opening_hours"),
                    "access_tag": tags.get("access"),
                    "geometry": row.geometry.representative_point(),
                }
            )
    water_union = gpd.GeoSeries(water_points, crs=4326).to_crs(25831).union_all() if water_points else None
    walkable = roads[~roads["highway"].isin({"trunk", "trunk_link", "primary", "primary_link", "track"})]
    walkable_union = walkable.geometry.union_all()
    fresh_union = streets[streets["freshness_class"].isin({"alt", "mitjà"})].geometry.union_all()
    records = []
    for candidate in candidates:
        point = candidate["geometry"]
        area = point.buffer(30)
        shade = grids["shade"].mean(area)
        lst = grids["lst"].mean(area)
        slope = grids["slope"].mean(point.buffer(5))
        route_distance = float(point.distance(walkable_union))
        accessibility = 100 * (1 - _clamp(route_distance, 0, 200) / 200)
        if slope is not None:
            accessibility *= 1 - 0.5 * _clamp(slope, 0, 30) / 30
        hours = candidate["opening_hours"]
        hours_score = 100.0 if hours == "24/7" else 70.0 if hours else None
        water_distance = float(point.distance(water_union)) if water_union is not None else None
        water_score = (
            100 * (1 - _clamp(water_distance - 50, 0, 250) / 250)
            if water_distance is not None
            else None
        )
        fresh_distance = float(point.distance(fresh_union)) if fresh_union is not None else None
        fresh_score = (
            100 * (1 - _clamp(fresh_distance, 0, 250) / 250)
            if fresh_distance is not None
            else None
        )
        components = {
            "shade": shade * 100 if shade is not None else None,
            "environment_temperature": (
                _clamp(
                    100
                    * (grids["lst_p90"] - lst)
                    / max(0.1, grids["lst_p90"] - grids["lst_p10"])
                )
                if lst is not None
                else None
            ),
            "accessibility": accessibility,
            "opening_hours": hours_score,
            "water": water_score,
            "vulnerable_population": None,
            "fresh_route_connection": fresh_score,
        }
        score, completeness = _weighted_score(components, EQUIPMENT_WEIGHTS)
        records.append(
            {
                **{key: value for key, value in candidate.items() if key != "geometry"},
                "shade_pct": round(shade * 100, 1) if shade is not None else None,
                "environment_temperature_c": round(lst, 1) if lst is not None else None,
                "accessibility_score_0_100": round(accessibility, 1),
                "water_distance_m": round(water_distance, 1) if water_distance is not None else None,
                "fresh_route_distance_m": round(fresh_distance, 1) if fresh_distance is not None else None,
                "vulnerable_population_component": "no disponible amb detall espacial verificat; exclòs i no inventat",
                "potential_utility_score_0_100": score,
                "potential_utility_class": _category(score),
                "confidence_pct": round(completeness * 0.82, 1),
                "validation_status": "candidat pendent de validació municipal; no és refugi climàtic oficial",
                "geometry": point,
            }
        )
    if not records:
        raise RuntimeError("No equipment or green-space candidates could be evaluated")
    return gpd.GeoDataFrame(records, crs=25831)


def calculate() -> dict:
    grids = _prepare_grids()
    tags_by_ref, water = _osm_tags_and_water()
    green = gpd.read_file(GREEN).to_crs(25831)
    green_union = green.geometry.union_all()
    roads = gpd.read_file(ROADS).to_crs(25831)
    streets = _street_potential(grids, tags_by_ref, green_union)
    equipment = _equipment_potential(grids, tags_by_ref, water, streets, roads, green)
    DERIVED.mkdir(parents=True, exist_ok=True)
    street_path = DERIVED / "cool_street_segments.geojson"
    equipment_path = DERIVED / "climate_utility_candidates.geojson"
    streets.to_crs(4326).to_file(street_path, driver="GeoJSON")
    equipment.to_crs(4326).to_file(equipment_path, driver="GeoJSON")
    selected = grids["surface_temperature"]
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    street_counts = streets.groupby("freshness_class").size().to_dict()
    street_lengths = (streets.groupby("freshness_class")["length_m"].sum() / 1000).round(2).to_dict()
    equipment_counts = equipment.groupby("potential_utility_class").size().to_dict()
    payload = {
        "schema_version": "1.0",
        "generated_at_utc": generated,
        "data_dates": {
            "shade": grids["shade_data_at_utc"],
            "surface_temperature": selected.get("acquired_at_utc"),
            "imperviousness": "2021",
            "osm_extract": "2026-07-10",
            "lidar": "2021-2023",
        },
        "cool_streets": {
            "label": "Potencial de frescor dels carrers",
            "indicator_type": (
                "Potencial derivat EcoRadar; no és una temperatura mesurada al carrer"
            ),
            "segments": int(len(streets)),
            "total_length_km": round(float(streets["length_m"].sum() / 1000), 2),
            "class_counts": {key: int(street_counts.get(key, 0)) for key in ("alt", "mitjà", "baix")},
            "class_lengths_km": {key: float(street_lengths.get(key, 0)) for key in ("alt", "mitjà", "baix")},
            "mean_score_0_100": round(float(streets["freshness_score_0_100"].mean()), 1),
            "mean_confidence_pct": round(float(streets["confidence_pct"].mean()), 1),
            "weights": STREET_WEIGHTS,
            "thresholds": {"alt": ">=67", "mitjà": "34-66.9", "baix": "<34"},
            "methodology_text": (
                "Índex ponderat per trams de fins a 75 m: ombra LiDAR 25 %, "
                "coberta arbòria 18 %, temperatura superficial 20 %, "
                "impermeabilització 12 %, orientació 8 %, amplada 7 % i "
                "proximitat a zones verdes 10 %."
            ),
            "limitations": [
                (
                    "L'amplada utilitza l'etiqueta width d'OSM quan existeix i "
                    "un valor substitutiu documentat segons la classe viària quan falta."
                ),
                (
                    "El potencial de frescor no és una temperatura de l'aire ni "
                    "de la superfície mesurada al carrer."
                ),
                (
                    "La data de l'indicador correspon al component dinàmic més "
                    "recent; les capes estructurals conserven la seva data pròpia."
                ),
            ],
            "output": str(street_path.relative_to(ROOT)),
        },
        "climate_utility_candidates": {
            "label": "Utilitat climàtica potencial dels equipaments",
            "candidate_count": int(len(equipment)),
            "class_counts": {key: int(equipment_counts.get(key, 0)) for key in ("alt", "mitjà", "baix")},
            "mean_score_0_100": round(float(equipment["potential_utility_score_0_100"].mean()), 1),
            "mean_confidence_pct": round(float(equipment["confidence_pct"].mean()), 1),
            "weights": EQUIPMENT_WEIGHTS,
            "thresholds": {"alt": ">=67", "mitjà": "34-66.9", "baix": "<34"},
            "vulnerable_population_component": (
                "no disponible amb detall espacial verificat; component exclòs "
                "i no substituït per cap estimació"
            ),
            "official_refuge_status": (
                "cap element assignat com a refugi oficial; tots són candidats "
                "pendents de validació municipal"
            ),
            "methodology_text": (
                "Índex ponderat de candidats: ombra 20 %, temperatura de l'entorn "
                "20 %, accessibilitat 15 %, horaris 10 %, proximitat a l'aigua "
                "10 %, població vulnerable 10 % i connexió amb itineraris frescos "
                "15 %. Els components no disponibles s'exclouen i els pesos "
                "disponibles es renormalitzen."
            ),
            "limitations": [
                (
                    "Els horaris només s'utilitzen quan consten a OpenStreetMap "
                    "i poden ser incomplets o haver canviat."
                ),
                (
                    "No hi ha una capa verificada de població vulnerable amb "
                    "detall espacial suficient; el component s'exclou i no s'estima."
                ),
                (
                    "Els candidats no són refugis climàtics oficials: requereixen "
                    "validació municipal, inspecció de camp i comprovació de "
                    "capacitat i condicions interiors."
                ),
            ],
            "output": str(equipment_path.relative_to(ROOT)),
        },
        "sources": [
            "ICGC LiDAR Territorial v3.1",
            selected.get("source"),
            "Copernicus HRL Imperviousness 2021",
            (
                "OpenStreetMap: etiquetes de xarxa viària, espais verds, "
                "equipaments, accés, horaris i aigua"
            ),
        ],
        "limitations": [
            (
                "L'amplada utilitza l'etiqueta width d'OSM quan existeix i un "
                "valor substitutiu documentat segons la classe viària quan falta."
            ),
            (
                "El potencial de frescor no és una temperatura de l'aire ni de "
                "la superfície mesurada al carrer."
            ),
            (
                "Els horaris només s'utilitzen quan consten a OpenStreetMap i "
                "poden ser incomplets."
            ),
            (
                "No hi ha una capa verificada de població vulnerable amb detall "
                "espacial suficient; el component s'exclou en lloc d'estimar-lo."
            ),
            (
                "Els candidats no són refugis climàtics oficials i requereixen "
                "validació municipal, inspecció de camp i comprovació de capacitat "
                "i condicions interiors."
            ),
        ],
        "methodology": "docs/data_sources/la_seu_urban_potential_indicators.md",
    }
    INDICATOR.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    payload = calculate()
    print(
        json.dumps(
            {
                "cool_street_segments": payload["cool_streets"]["segments"],
                "equipment_candidates": payload["climate_utility_candidates"]["candidate_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
