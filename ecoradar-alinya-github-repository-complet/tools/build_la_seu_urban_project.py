"""Build the verified spatial layers for EcoRadar Urba La Seu d'Urgell.

The source gate is documented in
projectes/LaSeu_Urba/metadata/data_sources_matrix.md. This script only reads
the raw files that passed that gate, derives map-ready layers, and writes
traceable processed artifacts. It does not invent records for unavailable
domains.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from urllib.request import urlopen

import geopandas as gpd
import laspy
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from shapely.geometry import LineString, Point, Polygon, box, mapping


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
PROCESSED = PROJECT / "processed"
MAPS = PROJECT / "maps"
INDICATORS = PROJECT / "indicators"
METADATA = PROJECT / "metadata"

MAP_BBOX_4326 = (1.435, 42.335, 1.490, 42.375)
LST_BBOX_4326 = (1.452, 42.352, 1.468, 42.361)
LIDAR_BBOX_25831 = (372505.0, 4690020.0, 373841.0, 4690995.0)
LIDAR_RESOLUTION_M = 2.0
LIDAR_FILES = [
    ROOT / "tmp" / "lidar-territorial-v3r1-full1km372690-2021-2023.laz",
    ROOT / "tmp" / "lidar-territorial-v3r1-full1km373690-2021-2023.laz",
]

SOLAR_CLASS_DEFINITIONS = {
    "favorable": {
        "priority": 1,
        "label": "Millor aptitud geomètrica",
        "criteria": (
            "Pendent ≤10° amb qualsevol orientació, o pendent ≤45° i "
            "orientació entre 135° i 225° (sud-est–sud-oest)."
        ),
        "decision": "Primera prioritat per estudiar l’aprofitament fotovoltaic.",
    },
    "condicionada": {
        "priority": 2,
        "label": "Aptitud geomètrica condicionada",
        "criteria": (
            "Pendent ≤45° i orientació entre 90° i 270° (est–oest), "
            "sense complir la classe favorable."
        ),
        "decision": (
            "Segona prioritat; requereix comprovar disposició, ombres i rendiment."
        ),
    },
    "baixa": {
        "priority": 3,
        "label": "Aptitud geomètrica baixa",
        "criteria": "Pendent >45° o orientació fora de l’arc est–sud–oest.",
        "decision": (
            "Prioritat baixa en el cribratge; només s’ha d’estudiar amb "
            "condicions tècniques específiques."
        ),
    },
}

LANDSAT_ITEM_ID = "LC09_L2SP_198030_20260708_02_T1"
PC_ITEM_URL = (
    "https://planetarycomputer.microsoft.com/api/stac/v1/collections/"
    f"landsat-c2-l2/items/{LANDSAT_ITEM_ID}"
)
PC_SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"

GREEN_TAGS = {
    ("leisure", "park"),
    ("leisure", "garden"),
    ("leisure", "nature_reserve"),
    ("leisure", "recreation_ground"),
    ("landuse", "forest"),
    ("landuse", "grass"),
    ("landuse", "meadow"),
    ("landuse", "allotments"),
    ("natural", "wood"),
    ("natural", "scrub"),
    ("natural", "grassland"),
    ("natural", "heath"),
}

FACILITY_AMENITIES = {
    "hospital",
    "clinic",
    "doctors",
    "pharmacy",
    "school",
    "college",
    "kindergarten",
    "library",
    "community_centre",
    "social_facility",
    "nursing_home",
    "townhall",
    "police",
    "fire_station",
    "bus_station",
    "shelter",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reuse-landsat",
        action="store_true",
        help="Reuse existing processed Landsat PNG and metadata instead of redownloading.",
    )
    args = parser.parse_args()

    for directory in (PROCESSED, MAPS, INDICATORS, METADATA):
        directory.mkdir(parents=True, exist_ok=True)

    buildings = process_cadastre_buildings()
    osm_summary = process_osm_extract()
    lidar = process_lidar()
    roofs = derive_solar_roof_screening(buildings, lidar)
    demography = process_demography()
    if args.reuse_landsat and (MAPS / "landsat_lst.png").exists():
        landsat = json.loads((METADATA / "landsat_overlay.json").read_text())
    else:
        landsat = process_landsat()

    layer_manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": "EcoRadar Urba - La Seu d'Urgell",
        "map_bbox_epsg4326": MAP_BBOX_4326,
        "analysis_core_bbox_epsg4326": LST_BBOX_4326,
        "layers_included": [
            "ombra_lidar",
            "cobertura_arboria_lidar",
            "pendent_lidar",
            "edificis_cadastre",
            "temperatura_superficial_landsat",
            "zones_verdes_osm",
            "mobilitat_osm",
            "equipaments_osm",
            "inundabilitat_snczi_q100",
            "preseleccio_cobertes_solars",
            "poblacio_i_edat_idescat",
        ],
        "layers_omitted": [
            "arbrat_municipal_georeferenciat",
            "impermeabilitzacio_copernicus",
            "soroll",
            "qualitat_aire",
            "contaminacio_luminica",
            "incendis",
            "fonts_publiques_municipals",
            "refugis_climatics_municipals",
        ],
        "counts": {
            "cadastre_buildings_in_map": int(len(buildings)),
            "solar_roofs_evaluated": int(len(roofs)),
            **osm_summary,
        },
        "lidar": lidar["metadata"],
        "landsat": landsat,
        "demography": demography,
        "source_matrix": "metadata/data_sources_matrix.md",
    }
    (METADATA / "layer_manifest.json").write_text(
        json.dumps(layer_manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(layer_manifest, ensure_ascii=False, indent=2))


def process_cadastre_buildings() -> gpd.GeoDataFrame:
    source = (
        PROJECT
        / "raw"
        / "cadastre"
        / "A.ES.SDGC.BU.25252.building.gml"
    )
    if not source.exists():
        raise FileNotFoundError(source)
    gdf = gpd.read_file(source, engine="pyogrio")
    if str(gdf.crs).upper() != "EPSG:25831":
        gdf = gdf.to_crs(25831)

    map_bbox_25831 = _bbox_projected(MAP_BBOX_4326, 4326, 25831)
    gdf = gdf[gdf.geometry.intersects(box(*map_bbox_25831))].copy()
    gdf["footprint_m2"] = gdf.geometry.area.round(1)
    keep = [
        "localId",
        "currentUse",
        "numberOfBuildingUnits",
        "numberOfDwellings",
        "numberOfFloorsAboveGround",
        "footprint_m2",
        "geometry",
    ]
    gdf = gdf[keep].rename(columns={"localId": "cadastre_id", "currentUse": "use"})
    gdf = gdf.to_crs(4326)
    gdf = gdf.clip(box(*MAP_BBOX_4326), keep_geom_type=True)
    gdf.to_file(PROCESSED / "buildings_cadastre.geojson", driver="GeoJSON", engine="pyogrio")
    return gdf


def process_osm_extract() -> dict[str, int]:
    source = PROJECT / "raw" / "osm" / "la_seu_bbox.osm"
    root = ET.parse(source).getroot()
    nodes: dict[str, tuple[float, float]] = {}
    node_tags: dict[str, dict[str, str]] = {}
    for node in root.findall("node"):
        node_id = node.attrib["id"]
        nodes[node_id] = (float(node.attrib["lon"]), float(node.attrib["lat"]))
        tags = _xml_tags(node)
        if tags:
            node_tags[node_id] = tags

    green_records: list[dict] = []
    mobility_records: list[dict] = []
    water_records: list[dict] = []
    facility_records: list[dict] = []
    seen_facility_refs: set[str] = set()

    for node_id, tags in node_tags.items():
        amenity = tags.get("amenity")
        if amenity in FACILITY_AMENITIES or tags.get("public_transport") in {
            "station",
            "platform",
            "stop_position",
        } or tags.get("highway") == "bus_stop":
            facility_records.append(
                _facility_record(f"node/{node_id}", Point(nodes[node_id]), tags)
            )
            seen_facility_refs.add(f"node/{node_id}")

    for way in root.findall("way"):
        way_id = way.attrib["id"]
        tags = _xml_tags(way)
        coordinates = [nodes[nd.attrib["ref"]] for nd in way.findall("nd") if nd.attrib["ref"] in nodes]
        if len(coordinates) < 2:
            continue
        is_closed = len(coordinates) >= 4 and coordinates[0] == coordinates[-1]
        polygon = None
        if is_closed:
            try:
                polygon = Polygon(coordinates)
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
            except Exception:
                polygon = None
        line = LineString(coordinates)

        if polygon is not None and any(tags.get(k) == v for k, v in GREEN_TAGS):
            green_records.append(
                {
                    "osm_ref": f"way/{way_id}",
                    "name": _name(tags),
                    "kind": _green_kind(tags),
                    "geometry": polygon,
                }
            )

        if "highway" in tags:
            mobility_records.append(
                {
                    "osm_ref": f"way/{way_id}",
                    "name": _name(tags),
                    "highway": tags.get("highway"),
                    "mode": _mobility_mode(tags),
                    "geometry": line,
                }
            )

        if "waterway" in tags or tags.get("natural") == "water":
            water_records.append(
                {
                    "osm_ref": f"way/{way_id}",
                    "name": _name(tags),
                    "kind": tags.get("waterway") or tags.get("water") or "water",
                    "geometry": polygon if polygon is not None else line,
                }
            )

        amenity = tags.get("amenity")
        if amenity in FACILITY_AMENITIES or tags.get("public_transport") in {"station", "platform"}:
            ref = f"way/{way_id}"
            if ref not in seen_facility_refs:
                point = polygon.representative_point() if polygon is not None else line.interpolate(0.5, normalized=True)
                facility_records.append(_facility_record(ref, point, tags))

    green = _gdf(green_records, 4326)
    mobility = _gdf(mobility_records, 4326)
    water = _gdf(water_records, 4326)
    facilities = _gdf(facility_records, 4326)
    clipper = box(*MAP_BBOX_4326)
    green = green.clip(clipper, keep_geom_type=True)
    mobility = mobility.clip(clipper, keep_geom_type=True)
    water = water.clip(clipper, keep_geom_type=True)
    facilities = facilities[facilities.geometry.intersects(clipper)].copy()

    green.to_file(PROCESSED / "green_spaces_osm.geojson", driver="GeoJSON", engine="pyogrio")
    mobility.to_file(PROCESSED / "mobility_osm.geojson", driver="GeoJSON", engine="pyogrio")
    water.to_file(PROCESSED / "water_osm.geojson", driver="GeoJSON", engine="pyogrio")
    facilities.to_file(PROCESSED / "facilities_osm.geojson", driver="GeoJSON", engine="pyogrio")

    green_area_ha = 0.0
    if len(green):
        green_area_ha = float(green.to_crs(25831).geometry.area.sum() / 10000.0)
    summary = {
        "green_polygons_osm": int(len(green)),
        "green_area_osm_ha": round(green_area_ha, 1),
        "mobility_segments_osm": int(len(mobility)),
        "facility_points_osm": int(len(facilities)),
        "water_features_osm": int(len(water)),
    }
    (INDICATORS / "osm_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    return summary


def process_lidar() -> dict:
    xmin, ymin, xmax, ymax = LIDAR_BBOX_25831
    res = LIDAR_RESOLUTION_M
    ncols = int(math.ceil((xmax - xmin) / res))
    nrows = int(math.ceil((ymax - ymin) / res))
    size = nrows * ncols
    dsm = np.full(size, -np.inf, dtype="float32")
    dtm = np.full(size, np.inf, dtype="float32")
    canopy = np.zeros(size, dtype=bool)

    surface_classes = {2, 3, 4, 5, 6, 8, 9, 17, 75, 77}
    ground_classes = {2, 8, 75}
    canopy_classes = {4, 5}

    for laz_path in LIDAR_FILES:
        if not laz_path.exists():
            raise FileNotFoundError(laz_path)
        with laspy.open(laz_path) as source:
            for points in source.chunk_iterator(2_000_000):
                x = np.asarray(points.x)
                y = np.asarray(points.y)
                z = np.asarray(points.z)
                classification = np.asarray(points.classification)
                inside = (x >= xmin) & (x < xmax) & (y >= ymin) & (y < ymax)
                if not bool(inside.any()):
                    continue
                x, y, z, classification = (
                    x[inside], y[inside], z[inside], classification[inside]
                )
                col = np.floor((x - xmin) / res).astype("int32")
                row = np.floor((ymax - y) / res).astype("int32")
                ok = (row >= 0) & (row < nrows) & (col >= 0) & (col < ncols)
                index = row[ok] * ncols + col[ok]
                z = z[ok].astype("float32")
                classification = classification[ok]

                surface = np.isin(classification, list(surface_classes))
                if bool(surface.any()):
                    np.maximum.at(dsm, index[surface], z[surface])
                ground = np.isin(classification, list(ground_classes))
                if bool(ground.any()):
                    np.minimum.at(dtm, index[ground], z[ground])
                trees = np.isin(classification, list(canopy_classes))
                if bool(trees.any()):
                    canopy[np.unique(index[trees])] = True

    dsm_grid = dsm.reshape((nrows, ncols))
    dtm_grid = dtm.reshape((nrows, ncols))
    valid = np.isfinite(dsm_grid)
    ground = _fill_missing(dtm_grid, np.isfinite(dtm_grid), dsm_grid)
    surface = np.where(valid, dsm_grid, ground)
    dy, dx = np.gradient(ground, res)
    terrain_slope = np.degrees(np.arctan(np.hypot(dx, dy))).astype("float32")
    sdy, sdx = np.gradient(surface, res)
    surface_slope = np.degrees(np.arctan(np.hypot(sdx, sdy))).astype("float32")
    surface_aspect = (np.degrees(np.arctan2(-sdx, sdy)) + 360.0) % 360.0

    solar_elevation, solar_azimuth = _solar_position(
        datetime(2026, 6, 21, 13, 0, tzinfo=timezone.utc), 42.3565, 1.4600
    )
    canopy_grid = canopy.reshape((nrows, ncols))
    shade = _shadow_mask(
        dsm_grid, ground, canopy_grid, res, solar_elevation, solar_azimuth
    )

    np.savez_compressed(
        PROCESSED / "lidar_core_arrays.npz",
        dsm=dsm_grid,
        ground=ground,
        valid=valid,
        canopy=canopy_grid,
        shade=shade,
        terrain_slope=terrain_slope,
        surface_slope=surface_slope,
        surface_aspect=surface_aspect.astype("float32"),
    )

    factor = 4
    shade_ds = _block_mean(shade.astype("float32"), factor)
    canopy_ds = _block_mean(canopy_grid.astype("float32"), factor)
    slope_ds = _block_mean(terrain_slope, factor)
    _write_rgba_png(
        MAPS / "lidar_shade.png",
        _continuous_rgba(
            shade_ds,
            [0.0, 0.15, 0.45, 1.0],
            [(255, 255, 255), (92, 169, 196), (34, 104, 153), (8, 48, 92)],
            valid=shade_ds > 0.03,
            alpha=190,
        ),
    )
    _write_rgba_png(
        MAPS / "lidar_canopy.png",
        _continuous_rgba(
            canopy_ds,
            [0.0, 0.15, 0.45, 1.0],
            [(240, 247, 235), (151, 204, 126), (66, 145, 73), (13, 91, 53)],
            valid=canopy_ds > 0.03,
            alpha=205,
        ),
    )
    _write_rgba_png(
        MAPS / "lidar_slope.png",
        _continuous_rgba(
            slope_ds,
            [0.0, 5.0, 15.0, 30.0, 50.0],
            [(235, 246, 219), (181, 216, 163), (245, 216, 122), (214, 142, 79), (119, 69, 54)],
            valid=np.isfinite(slope_ds),
            alpha=185,
        ),
    )

    lidar_bbox_4326 = _bbox_projected(LIDAR_BBOX_25831, 25831, 4326)
    metadata = {
        "bbox_epsg25831": LIDAR_BBOX_25831,
        "bbox_epsg4326": lidar_bbox_4326,
        "resolution_m": res,
        "web_raster_resolution_m": res * factor,
        "valid_cells_pct": round(float(valid.mean() * 100), 1),
        "canopy_cover_pct": round(float(canopy_grid.mean() * 100), 1),
        "shade_pct": round(float(shade.mean() * 100), 1),
        "shade_datetime_local": "2026-06-21 15:00 CEST",
        "solar_elevation_deg": round(float(solar_elevation), 1),
        "solar_azimuth_deg": round(float(solar_azimuth), 1),
        "terrain_slope_median_deg": round(float(np.nanmedian(terrain_slope)), 1),
        "tiles": [path.name for path in LIDAR_FILES],
    }
    (METADATA / "lidar_overlay.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    return {
        "metadata": metadata,
        "dsm": dsm_grid,
        "ground": ground,
        "valid": valid,
        "shade": shade,
        "canopy": canopy_grid,
        "surface_slope": surface_slope,
        "surface_aspect": surface_aspect,
        "transform": from_origin(xmin, ymax, res, res),
    }


def derive_solar_roof_screening(
    buildings_4326: gpd.GeoDataFrame, lidar: dict
) -> gpd.GeoDataFrame:
    buildings = buildings_4326.to_crs(25831)
    buildings = buildings[
        buildings.geometry.intersects(box(*LIDAR_BBOX_25831))
    ].copy()
    transform = lidar["transform"]
    nrows, ncols = lidar["dsm"].shape
    xmin, _, _, ymax = (
        LIDAR_BBOX_25831[0],
        LIDAR_BBOX_25831[1],
        LIDAR_BBOX_25831[2],
        LIDAR_BBOX_25831[3],
    )
    results: list[dict] = []

    for row in buildings.itertuples():
        geom = row.geometry
        minx, miny, maxx, maxy = geom.bounds
        c0 = max(0, int(math.floor((minx - xmin) / LIDAR_RESOLUTION_M)))
        c1 = min(ncols, int(math.ceil((maxx - xmin) / LIDAR_RESOLUTION_M)) + 1)
        r0 = max(0, int(math.floor((ymax - maxy) / LIDAR_RESOLUTION_M)))
        r1 = min(nrows, int(math.ceil((ymax - miny) / LIDAR_RESOLUTION_M)) + 1)
        if r1 <= r0 or c1 <= c0:
            continue
        window_transform = rasterio.windows.transform(
            rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0), transform
        )
        inside = geometry_mask(
            [mapping(geom)],
            out_shape=(r1 - r0, c1 - c0),
            transform=window_transform,
            invert=True,
        )
        valid = lidar["valid"][r0:r1, c0:c1] & inside
        if int(valid.sum()) < 3:
            continue
        slope_values = lidar["surface_slope"][r0:r1, c0:c1][valid]
        aspect_values = lidar["surface_aspect"][r0:r1, c0:c1][valid]
        slope = float(np.nanmedian(slope_values))
        weights = np.maximum(slope_values, 1.0)
        radians = np.radians(aspect_values)
        aspect = (
            math.degrees(
                math.atan2(
                    float(np.average(np.sin(radians), weights=weights)),
                    float(np.average(np.cos(radians), weights=weights)),
                )
            )
            + 360.0
        ) % 360.0
        if slope <= 10.0 or (slope <= 45.0 and 135.0 <= aspect <= 225.0):
            solar_class = "favorable"
        elif slope <= 45.0 and 90.0 <= aspect <= 270.0:
            solar_class = "condicionada"
        else:
            solar_class = "baixa"
        results.append(
            {
                "cadastre_id": row.cadastre_id,
                "footprint_m2": round(float(geom.area), 1),
                "lidar_cells": int(valid.sum()),
                "median_slope_deg": round(slope, 1),
                "mean_aspect_deg": round(aspect, 1),
                "solar_screen": solar_class,
                "geometry": geom,
            }
        )

    roofs = _gdf(results, 25831).to_crs(4326)
    roofs.to_file(
        PROCESSED / "solar_roof_screening.geojson",
        driver="GeoJSON",
        engine="pyogrio",
    )
    summary = {
        "evaluated_buildings": int(len(roofs)),
        "classes": roofs["solar_screen"].value_counts().to_dict() if len(roofs) else {},
        "priority_order": ["favorable", "condicionada", "baixa"],
        "class_definitions": SOLAR_CLASS_DEFINITIONS,
        "method_note": (
            "Preseleccio geometrica amb petjada cadastral i pendent/orientacio del DSM LiDAR a 2 m. "
            "No es un estudi de viabilitat fotovoltaica."
        ),
    }
    (INDICATORS / "solar_roof_screening_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    return roofs


def process_demography() -> dict:
    source = PROJECT / "raw" / "demografia" / "idescat_emex_252038_2026-07-10.json"
    payload = json.loads(source.read_text())
    tables: dict[str, dict] = {}

    def walk(value) -> None:
        if isinstance(value, dict):
            if str(value.get("id", "")).startswith("t") and "ff" in value:
                tables[value["id"]] = value
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    population_table = tables["t195"]
    age_table = tables["t25"]
    population_rows = _rows(age_table)
    total = int(float(population_rows["Total"][0]))
    age_groups = {
        "0_14": int(float(population_rows["De 0 a 14 anys"][0])),
        "15_64": int(float(population_rows["De 15 a 64 anys"][0])),
        "65_84": int(float(population_rows["De 65 a 84 anys"][0])),
        "85_plus": int(float(population_rows["De 85 anys i més"][0])),
    }
    result = {
        "municipality_code": "252038",
        "reference_year": int(population_table["r"]),
        "population": total,
        "age_groups": age_groups,
        "age_percent": {key: round(value / total * 100, 1) for key, value in age_groups.items()},
        "population_65_plus": age_groups["65_84"] + age_groups["85_plus"],
        "population_65_plus_pct": round(
            (age_groups["65_84"] + age_groups["85_plus"]) / total * 100, 1
        ),
        "source": population_table.get("s"),
        "updated": population_table.get("updated"),
        "official_url": "https://api.idescat.cat/emex/v1/geo/252038.json",
        "spatial_limitation": "Municipal aggregate; not assigned to streets or buildings.",
    }
    (INDICATORS / "demography_idescat.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    return result


def process_landsat() -> dict:
    item = _read_json_url(PC_ITEM_URL)
    st_href = _sign_href(item["assets"]["lwir11"]["href"])
    qa_href = _sign_href(item["assets"]["qa_pixel"]["href"])
    scale = float(item["assets"]["lwir11"]["raster:bands"][0]["scale"])
    offset = float(item["assets"]["lwir11"]["raster:bands"][0]["offset"])
    nodata = int(item["assets"]["lwir11"]["raster:bands"][0]["nodata"])

    with rasterio.open(st_href) as source:
        transformer = Transformer.from_crs(4326, source.crs, always_xy=True)
        x0, y0 = transformer.transform(LST_BBOX_4326[0], LST_BBOX_4326[1])
        x1, y1 = transformer.transform(LST_BBOX_4326[2], LST_BBOX_4326[3])
        window = from_bounds(
            min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), source.transform
        ).round_offsets().round_lengths()
        st_dn = source.read(1, window=window)
        source_bounds = rasterio.windows.bounds(window, source.transform)
        source_crs = source.crs
    with rasterio.open(qa_href) as source:
        qa = source.read(1, window=window)

    invalid_bits = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5)
    valid = (st_dn != nodata) & ((qa & invalid_bits) == 0)
    values = st_dn.astype("float64") * scale + offset - 273.15
    np.savez_compressed(
        PROCESSED / "landsat_lst_core.npz",
        lst_c=values.astype("float32"),
        valid=valid,
        bounds=np.asarray(source_bounds, dtype="float64"),
        crs=np.asarray(str(source_crs)),
    )
    rgba = _continuous_rgba(
        values,
        [36.0, 40.0, 44.0, 48.0, 52.0, 56.0],
        [
            (42, 127, 96),
            (166, 199, 84),
            (250, 204, 70),
            (244, 141, 40),
            (214, 65, 39),
            (126, 24, 54),
        ],
        valid=valid,
        alpha=205,
    )
    _write_rgba_png(MAPS / "landsat_lst.png", rgba)
    transformer = Transformer.from_crs(source_crs, 4326, always_xy=True)
    left, bottom, right, top = source_bounds
    corners = [
        transformer.transform(left, bottom),
        transformer.transform(left, top),
        transformer.transform(right, bottom),
        transformer.transform(right, top),
    ]
    bbox = (
        min(x for x, _ in corners),
        min(y for _, y in corners),
        max(x for x, _ in corners),
        max(y for _, y in corners),
    )
    clean = values[valid]
    metadata = {
        "item_id": item["id"],
        "datetime_utc": item["properties"]["datetime"],
        "datetime_local": "2026-07-08 12:35 CEST",
        "bbox_epsg4326": bbox,
        "valid_pixels": int(clean.size),
        "mean_c": round(float(np.mean(clean)), 1),
        "p10_c": round(float(np.percentile(clean, 10)), 1),
        "p90_c": round(float(np.percentile(clean, 90)), 1),
        "min_c": round(float(np.min(clean)), 1),
        "max_c": round(float(np.max(clean)), 1),
        "cloud_cover_scene_pct": float(item["properties"]["eo:cloud_cover"]),
        "source_collection": "USGS Landsat Collection 2 Level-2 Surface Temperature",
    }
    (METADATA / "landsat_overlay.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    return metadata


def _xml_tags(element: ET.Element) -> dict[str, str]:
    return {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}


def _name(tags: dict[str, str]) -> str | None:
    return tags.get("name:ca") or tags.get("name")


def _green_kind(tags: dict[str, str]) -> str:
    for key in ("leisure", "landuse", "natural"):
        if key in tags:
            return f"{key}:{tags[key]}"
    return "green"


def _mobility_mode(tags: dict[str, str]) -> str:
    highway = tags.get("highway")
    if highway == "cycleway" or tags.get("cycleway") not in {None, "no"}:
        return "ciclable"
    if highway in {"footway", "path", "pedestrian", "steps", "living_street"}:
        return "a_peu"
    return "viaria"


def _facility_record(ref: str, geometry: Point, tags: dict[str, str]) -> dict:
    kind = tags.get("amenity") or tags.get("public_transport") or tags.get("highway")
    return {
        "osm_ref": ref,
        "name": _name(tags) or kind,
        "kind": kind,
        "geometry": geometry,
    }


def _gdf(records: list[dict], crs: int) -> gpd.GeoDataFrame:
    if records:
        return gpd.GeoDataFrame(records, geometry="geometry", crs=crs)
    return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=crs)


def _bbox_projected(bounds, source_crs: int, target_crs: int):
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    xmin, ymin, xmax, ymax = bounds
    points = [
        transformer.transform(xmin, ymin),
        transformer.transform(xmin, ymax),
        transformer.transform(xmax, ymin),
        transformer.transform(xmax, ymax),
    ]
    return (
        min(x for x, _ in points),
        min(y for _, y in points),
        max(x for x, _ in points),
        max(y for _, y in points),
    )


def _fill_missing(values: np.ndarray, valid: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    filled = values.copy()
    filled[~valid] = np.nan
    for _ in range(40):
        missing = np.isnan(filled)
        if not bool(missing.any()):
            break
        total = np.zeros_like(filled, dtype="float32")
        count = np.zeros_like(filled, dtype="uint8")
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                shifted = _shift(filled, dr, dc, np.nan)
                ok = ~np.isnan(shifted)
                total[ok] += shifted[ok]
                count[ok] += 1
        can_fill = missing & (count > 0)
        filled[can_fill] = total[can_fill] / count[can_fill]
    remaining = np.isnan(filled)
    if bool(remaining.any()):
        backup = np.where(np.isfinite(fallback), fallback, np.nanmedian(filled))
        filled[remaining] = backup[remaining]
    return filled


def _shadow_mask(dsm, ground, canopy, resolution, solar_elevation, solar_azimuth):
    valid = np.isfinite(dsm) & np.isfinite(ground)
    shadow = canopy.copy()
    tan_elevation = math.tan(math.radians(solar_elevation))
    azimuth = math.radians(solar_azimuth)
    dx, dy = math.sin(azimuth), math.cos(azimuth)
    seen: set[tuple[int, int]] = set()
    for distance in np.arange(resolution, 160.0 + resolution, resolution):
        col_shift = int(round(dx * distance / resolution))
        row_shift = int(round(-dy * distance / resolution))
        if (row_shift, col_shift) == (0, 0) or (row_shift, col_shift) in seen:
            continue
        seen.add((row_shift, col_shift))
        obstacle = _shift(dsm, row_shift, col_shift, -np.inf)
        shadow |= valid & (obstacle > ground + distance * tan_elevation)
    return shadow & valid


def _shift(values, row_shift: int, col_shift: int, fill):
    output = np.full(values.shape, fill, dtype=values.dtype)
    nrows, ncols = values.shape
    if row_shift >= 0:
        sr0, sr1, dr0, dr1 = row_shift, nrows, 0, nrows - row_shift
    else:
        sr0, sr1, dr0, dr1 = 0, nrows + row_shift, -row_shift, nrows
    if col_shift >= 0:
        sc0, sc1, dc0, dc1 = col_shift, ncols, 0, ncols - col_shift
    else:
        sc0, sc1, dc0, dc1 = 0, ncols + col_shift, -col_shift, ncols
    if sr1 > sr0 and sc1 > sc0:
        output[dr0:dr1, dc0:dc1] = values[sr0:sr1, sc0:sc1]
    return output


def _solar_position(dt_utc: datetime, lat_deg: float, lon_deg: float):
    doy = int(dt_utc.astimezone(timezone.utc).strftime("%j"))
    hour = dt_utc.astimezone(timezone.utc).hour
    gamma = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    solar_minutes = (hour * 60 + eqtime + 4 * lon_deg) % 1440
    hour_angle = math.radians(solar_minutes / 4 - 180)
    latitude = math.radians(lat_deg)
    cos_zenith = math.sin(latitude) * math.sin(declination) + math.cos(latitude) * math.cos(declination) * math.cos(hour_angle)
    zenith = math.acos(min(1.0, max(-1.0, cos_zenith)))
    elevation = 90 - math.degrees(zenith)
    azimuth = (
        math.degrees(
            math.atan2(
                math.sin(hour_angle),
                math.cos(hour_angle) * math.sin(latitude)
                - math.tan(declination) * math.cos(latitude),
            )
        )
        + 180
    ) % 360
    return elevation, azimuth


def _block_mean(values: np.ndarray, factor: int) -> np.ndarray:
    rows = values.shape[0] // factor * factor
    cols = values.shape[1] // factor * factor
    trimmed = values[:rows, :cols]
    return np.nanmean(
        trimmed.reshape(rows // factor, factor, cols // factor, factor), axis=(1, 3)
    )


def _continuous_rgba(values, stops, colors, *, valid, alpha: int):
    rgba = np.zeros((*values.shape, 4), dtype="uint8")
    values = np.asarray(values, dtype="float64")
    for channel in range(3):
        rgba[..., channel] = np.clip(
            np.interp(values, stops, [color[channel] for color in colors]), 0, 255
        ).astype("uint8")
    rgba[..., 3] = np.where(valid & np.isfinite(values), alpha, 0).astype("uint8")
    return rgba


def _write_rgba_png(path: Path, rgba: np.ndarray) -> None:
    with rasterio.open(
        path,
        "w",
        driver="PNG",
        width=rgba.shape[1],
        height=rgba.shape[0],
        count=4,
        dtype="uint8",
    ) as dst:
        for band in range(4):
            dst.write(rgba[..., band], band + 1)


def _rows(table: dict) -> dict[str, list[str]]:
    rows = table["ff"]["f"]
    if isinstance(rows, dict):
        rows = [rows]
    return {row["c"]: str(row["v"]).split(",") for row in rows}


def _read_json_url(url: str) -> dict:
    with urlopen(url, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _sign_href(href: str) -> str:
    return str(_read_json_url(f"{PC_SIGN_URL}?{urlencode({'href': href})}")["href"])


if __name__ == "__main__":
    main()
