"""OpenStreetMap recreational infrastructure connector for EcoRadar.

This connector is intentionally OSM-only. It downloads and normalizes mapped
paths, tracks, minor access roads, parking/access points and recreational
features from Overpass. It does not estimate visitor counts or Strava-like
intensity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
from shapely.geometry import LineString, Point


PROJECT_ROOT = Path("projectes/Alinya")
STUDY_AREA_PATH = PROJECT_ROOT / "processed" / "study_area.gpkg"
RAW_DIR = PROJECT_ROOT / "raw" / "recreational_pressure"
RAW_PATH = RAW_DIR / "overpass_osm_raw.json"
PROCESSED_PATH = PROJECT_ROOT / "processed" / "recreational_pressure.gpkg"
SUMMARY_PATH = PROJECT_ROOT / "indicators" / "recreational_pressure_resum.csv"
METADATA_PATH = PROJECT_ROOT / "metadata" / "recreational_pressure_metadata.json"

TARGET_CRS = "EPSG:25831"
WGS84 = "EPSG:4326"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SOURCE_URL = "https://wiki.openstreetmap.org/wiki/Overpass_API"
USER_AGENT = "EcoRadar/0.1 recreational-pressure-osm connector"


LINE_HIGHWAYS = (
    "path",
    "track",
    "footway",
    "bridleway",
    "cycleway",
    "service",
    "unclassified",
    "residential",
    "tertiary",
)
POINT_TAGS = {
    "amenity": {"parking", "shelter", "drinking_water"},
    "tourism": {"viewpoint", "information", "picnic_site", "camp_site", "alpine_hut", "wilderness_hut"},
    "leisure": {"picnic_table", "picnic_site"},
    "highway": {"trailhead", "bus_stop"},
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar OSM recreational-pressure connector")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached raw Overpass response")
    args = parser.parse_args()

    try:
        result = run_connector(refresh=args.refresh)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"connector_recreational_pressure_osm failed: {exc}", file=sys.stderr)
        raise


def run_connector(*, refresh: bool = False) -> dict[str, Any]:
    _ensure_dirs()
    study_area = _load_study_area()
    raw = _load_or_fetch(study_area, refresh=refresh)
    lines, points = _normalize(raw, study_area)

    _write_processed(lines, points)
    summary_rows = _write_summary(study_area, lines, points)
    metadata = _write_metadata(study_area, raw, lines, points, refresh)

    return {
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "metadata_path": str(METADATA_PATH),
        "raw_path": str(RAW_PATH),
        "line_features": int(len(lines)),
        "point_features": int(len(points)),
        "summary": summary_rows,
        "metadata": metadata,
    }


def _ensure_dirs() -> None:
    for directory in (RAW_DIR, PROCESSED_PATH.parent, SUMMARY_PATH.parent, METADATA_PATH.parent):
        directory.mkdir(parents=True, exist_ok=True)


def _load_study_area() -> gpd.GeoDataFrame:
    if not STUDY_AREA_PATH.exists():
        raise FileNotFoundError(f"Study area not found: {STUDY_AREA_PATH}")
    study_area = gpd.read_file(STUDY_AREA_PATH).to_crs(TARGET_CRS)
    if study_area.empty:
        raise ValueError("Study area is empty")
    invalid = ~study_area.geometry.is_valid
    if bool(invalid.any()):
        raise ValueError("Study area has invalid geometries")
    return study_area


def _load_or_fetch(study_area: gpd.GeoDataFrame, *, refresh: bool) -> dict[str, Any]:
    if RAW_PATH.exists() and not refresh:
        payload = json.loads(RAW_PATH.read_text(encoding="utf-8"))
        payload["_ecoradar_cache"] = {"used": True}
        return payload

    query = _overpass_query(study_area)
    data = urlencode({"data": query}).encode("utf-8")
    request = Request(
        OVERPASS_URL,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))

    payload["_ecoradar"] = {
        "downloaded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "OpenStreetMap via Overpass API",
        "url": OVERPASS_URL,
    }
    payload["_ecoradar_cache"] = {"used": False}
    RAW_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def _overpass_query(study_area: gpd.GeoDataFrame) -> str:
    west, south, east, north = study_area.to_crs(WGS84).total_bounds
    bbox = f"{south},{west},{north},{east}"
    highway_regex = "|".join(LINE_HIGHWAYS)
    return f"""
[out:json][timeout:180];
(
  way["highway"~"^({highway_regex})$"]({bbox});
  node["amenity"~"^(parking|shelter|drinking_water)$"]({bbox});
  way["amenity"~"^(parking|shelter|drinking_water)$"]({bbox});
  node["tourism"~"^(viewpoint|information|picnic_site|camp_site|alpine_hut|wilderness_hut)$"]({bbox});
  way["tourism"~"^(viewpoint|information|picnic_site|camp_site|alpine_hut|wilderness_hut)$"]({bbox});
  node["leisure"~"^(picnic_table|picnic_site)$"]({bbox});
  way["leisure"~"^(picnic_table|picnic_site)$"]({bbox});
  node["highway"~"^(trailhead|bus_stop)$"]({bbox});
);
out geom;
"""


def _normalize(raw: dict[str, Any], study_area: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    line_records: list[dict[str, Any]] = []
    point_records: list[dict[str, Any]] = []

    for element in raw.get("elements", []):
        tags = element.get("tags") or {}
        element_type = element.get("type")
        element_id = str(element.get("id", ""))
        if element_type == "way" and tags.get("highway") in LINE_HIGHWAYS:
            geometry = _way_linestring(element)
            if geometry is not None:
                line_records.append(_base_record(element_type, element_id, tags, geometry))
        elif _is_recreational_point(tags):
            geometry = _point_geometry(element)
            if geometry is not None:
                point_records.append(_base_record(element_type, element_id, tags, geometry))

    lines = gpd.GeoDataFrame(line_records, geometry="geometry", crs=WGS84)
    points = gpd.GeoDataFrame(point_records, geometry="geometry", crs=WGS84)
    if lines.empty:
        lines = _empty_gdf("LineString")
    if points.empty:
        points = _empty_gdf("Point")

    study_union = study_area.geometry.union_all()
    lines = gpd.clip(lines.to_crs(TARGET_CRS), study_union)
    points = gpd.clip(points.to_crs(TARGET_CRS), study_union)
    if not lines.empty:
        lines["length_km"] = lines.geometry.length / 1000
    else:
        lines["length_km"] = []
    return lines, points


def _way_linestring(element: dict[str, Any]) -> LineString | None:
    coords = [(node["lon"], node["lat"]) for node in element.get("geometry", []) if "lon" in node and "lat" in node]
    if len(coords) < 2:
        return None
    return LineString(coords)


def _point_geometry(element: dict[str, Any]) -> Point | None:
    if element.get("type") == "node" and "lon" in element and "lat" in element:
        return Point(element["lon"], element["lat"])
    coords = [(node["lon"], node["lat"]) for node in element.get("geometry", []) if "lon" in node and "lat" in node]
    if not coords:
        return None
    line = LineString(coords)
    return line.centroid


def _is_recreational_point(tags: dict[str, Any]) -> bool:
    for key, values in POINT_TAGS.items():
        if tags.get(key) in values:
            return True
    return False


def _base_record(element_type: str, element_id: str, tags: dict[str, Any], geometry: Point | LineString) -> dict[str, Any]:
    return {
        "osm_type": element_type,
        "osm_id": element_id,
        "name": _tag(tags, "name"),
        "highway": _tag(tags, "highway"),
        "amenity": _tag(tags, "amenity"),
        "tourism": _tag(tags, "tourism"),
        "leisure": _tag(tags, "leisure"),
        "surface": _tag(tags, "surface"),
        "access": _tag(tags, "access"),
        "bicycle": _tag(tags, "bicycle"),
        "foot": _tag(tags, "foot"),
        "mtb_scale": _tag(tags, "mtb:scale"),
        "source": "OpenStreetMap",
        "geometry": geometry,
    }


def _tag(tags: dict[str, Any], key: str) -> str:
    value = tags.get(key)
    return "" if value is None else str(value)


def _empty_gdf(geometry_type: str) -> gpd.GeoDataFrame:
    columns = [
        "osm_type",
        "osm_id",
        "name",
        "highway",
        "amenity",
        "tourism",
        "leisure",
        "surface",
        "access",
        "bicycle",
        "foot",
        "mtb_scale",
        "source",
        "geometry",
    ]
    return gpd.GeoDataFrame({column: [] for column in columns}, geometry="geometry", crs=WGS84)


def _write_processed(lines: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> None:
    if PROCESSED_PATH.exists():
        PROCESSED_PATH.unlink()
    lines.to_file(PROCESSED_PATH, layer="osm_paths_tracks_roads", driver="GPKG")
    points.to_file(PROCESSED_PATH, layer="osm_recreational_points", driver="GPKG")


def _write_summary(study_area: gpd.GeoDataFrame, lines: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    area_km2 = float(study_area.geometry.area.sum() / 1_000_000)
    total_km = float(lines["length_km"].sum()) if "length_km" in lines else 0.0
    density = total_km / area_km2 if area_km2 else 0.0
    rows = [
        {"indicator": "osm_line_features", "value": len(lines), "unit": "features"},
        {"indicator": "osm_path_track_road_km", "value": round(total_km, 4), "unit": "km"},
        {"indicator": "osm_path_track_road_density", "value": round(density, 4), "unit": "km/km2"},
        {"indicator": "osm_recreational_point_features", "value": len(points), "unit": "features"},
    ]
    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["indicator", "value", "unit"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _write_metadata(
    study_area: gpd.GeoDataFrame,
    raw: dict[str, Any],
    lines: gpd.GeoDataFrame,
    points: gpd.GeoDataFrame,
    refresh: bool,
) -> dict[str, Any]:
    metadata = {
        "source": "OpenStreetMap via Overpass API",
        "responsible_organization": "OpenStreetMap contributors; Overpass community",
        "url": SOURCE_URL,
        "data_url": OVERPASS_URL,
        "date_consulted": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "crs": TARGET_CRS,
        "service_type": "REST API",
        "data_format": ["JSON", "GeoPackage"],
        "license": "ODbL for OpenStreetMap data; Overpass public instance usage policy applies",
        "raw_cache_used": bool(raw.get("_ecoradar_cache", {}).get("used")),
        "raw_elements": len(raw.get("elements", [])),
        "line_features": int(len(lines)),
        "point_features": int(len(points)),
        "outputs": {
            "raw": str(RAW_PATH),
            "processed": str(PROCESSED_PATH),
            "summary": str(SUMMARY_PATH),
        },
        "limitations": [
            "OpenStreetMap is volunteered geographic information and may be incomplete or unevenly mapped.",
            "The connector normalizes infrastructure and access features only; it does not estimate visitor numbers.",
            "Strava Global Heatmap, Wikiloc, counters and manager datasets remain excluded until authorized connector-grade access is documented.",
            "Later EcoRadar analysis should combine OSM with fieldwork before diagnosing real public-use pressure.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


if __name__ == "__main__":
    main()
