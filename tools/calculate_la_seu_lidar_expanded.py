"""Calculate LiDAR terrain, canopy and summer direct-shade layers for the expanded scope.

Input LAZ tiles are the official ICGC LiDAR Territorial v3.1 files documented
in the project source matrix. This analysis is deliberately separate from the
download step and writes a reusable numeric archive plus traceability metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import laspy
import numpy as np
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping

from calculate_la_seu_urban_metrics import _fill_missing_dtm, _shadow_mask, _solar_position


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
OUTPUT = PROJECT / "processed" / "lidar_expanded_arrays.npz"
METADATA = PROJECT / "metadata" / "lidar_expanded_analysis.json"
RESOLUTION_M = 2.0

TILE_CODES = [
    "371690", "371691",
    "372689", "372690", "372691",
    "373689", "373690", "373691",
    "374689", "374690", "374691",
]


def _tile_path(code: str) -> Path:
    return ROOT / "tmp" / f"lidar-territorial-v3r1-full1km{code}-2021-2023.laz"


def _tile_url(code: str) -> str:
    group = f"{int(code[:3]) // 10}{int(code[3:]) // 10}"
    return (
        "https://datacloud.icgc.cat/datacloud/lidar-territorial/laz_unzip/"
        f"full10km{group}/lidar-territorial-v3r1-full1km{code}-2021-2023.laz"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def calculate() -> dict:
    manifest = json.loads(PROJECT_MANIFEST.read_text())
    bbox4326 = tuple(float(v) for v in manifest["study_area"]["expanded_urban_bbox_epsg4326"])
    transformer = Transformer.from_crs(4326, 25831, always_xy=True)
    ring = [
        transformer.transform(bbox4326[0], bbox4326[1]),
        transformer.transform(bbox4326[0], bbox4326[3]),
        transformer.transform(bbox4326[2], bbox4326[3]),
        transformer.transform(bbox4326[2], bbox4326[1]),
    ]
    polygon = Polygon(ring)
    minx, miny, maxx, maxy = polygon.bounds
    xmin = math.floor(minx / RESOLUTION_M) * RESOLUTION_M
    ymin = math.floor(miny / RESOLUTION_M) * RESOLUTION_M
    xmax = math.ceil(maxx / RESOLUTION_M) * RESOLUTION_M
    ymax = math.ceil(maxy / RESOLUTION_M) * RESOLUTION_M
    ncols = int(round((xmax - xmin) / RESOLUTION_M))
    nrows = int(round((ymax - ymin) / RESOLUTION_M))
    size = nrows * ncols
    dsm = np.full(size, -np.inf, dtype="float32")
    dtm = np.full(size, np.inf, dtype="float32")
    canopy = np.zeros(size, dtype=bool)

    transform = from_origin(xmin, ymax, RESOLUTION_M, RESOLUTION_M)
    scope_mask = geometry_mask(
        [mapping(polygon)],
        out_shape=(nrows, ncols),
        transform=transform,
        invert=True,
        all_touched=False,
    )
    surface_classes = np.asarray([2, 3, 4, 5, 6, 8, 9, 17, 75, 77], dtype="uint8")
    ground_classes = np.asarray([2, 8, 75], dtype="uint8")
    canopy_classes = np.asarray([4, 5], dtype="uint8")

    tile_records = []
    for code in TILE_CODES:
        path = _tile_path(code)
        if not path.exists():
            raise FileNotFoundError(path)
        with laspy.open(path) as source:
            point_count = int(source.header.point_count)
            for points in source.chunk_iterator(2_000_000):
                x = np.asarray(points.x)
                y = np.asarray(points.y)
                z = np.asarray(points.z)
                classification = np.asarray(points.classification)
                inside = (x >= xmin) & (x < xmax) & (y >= ymin) & (y < ymax)
                if not bool(inside.any()):
                    continue
                x, y, z, classification = x[inside], y[inside], z[inside], classification[inside]
                col = np.floor((x - xmin) / RESOLUTION_M).astype("int32")
                row = np.floor((ymax - y) / RESOLUTION_M).astype("int32")
                ok = (row >= 0) & (row < nrows) & (col >= 0) & (col < ncols)
                index = row[ok] * ncols + col[ok]
                within_scope = scope_mask.ravel()[index]
                if not bool(within_scope.any()):
                    continue
                index = index[within_scope]
                z = z[ok][within_scope].astype("float32")
                classification = classification[ok][within_scope]
                surface = np.isin(classification, surface_classes)
                if bool(surface.any()):
                    np.maximum.at(dsm, index[surface], z[surface])
                ground = np.isin(classification, ground_classes)
                if bool(ground.any()):
                    np.minimum.at(dtm, index[ground], z[ground])
                trees = np.isin(classification, canopy_classes)
                if bool(trees.any()):
                    canopy[np.unique(index[trees])] = True
        tile_records.append(
            {
                "code": code,
                "path": str(path.relative_to(ROOT)),
                "official_url": _tile_url(code),
                "point_count": point_count,
                "sha256": _sha256(path),
            }
        )

    dsm_grid = dsm.reshape((nrows, ncols))
    dtm_grid = dtm.reshape((nrows, ncols))
    canopy_grid = canopy.reshape((nrows, ncols)) & scope_mask
    valid = np.isfinite(dsm_grid) & scope_mask
    dtm_valid = np.isfinite(dtm_grid) & scope_mask
    ground = _fill_missing_dtm(dtm_grid, dtm_valid, dsm_grid)
    surface = np.where(valid, dsm_grid, ground)
    dy, dx = np.gradient(ground, RESOLUTION_M)
    terrain_slope = np.degrees(np.arctan(np.hypot(dx, dy))).astype("float32")
    sdy, sdx = np.gradient(surface, RESOLUTION_M)
    surface_slope = np.degrees(np.arctan(np.hypot(sdx, sdy))).astype("float32")
    surface_aspect = ((np.degrees(np.arctan2(-sdx, sdy)) + 360.0) % 360.0).astype("float32")

    lon = (bbox4326[0] + bbox4326[2]) / 2
    lat = (bbox4326[1] + bbox4326[3]) / 2
    solar_utc = datetime(2026, 6, 21, 13, 0, tzinfo=timezone.utc)
    solar_elevation, solar_azimuth = _solar_position(solar_utc, lat, lon)
    shade = _shadow_mask(
        dsm_grid,
        ground,
        canopy_grid,
        RESOLUTION_M,
        solar_elevation,
        solar_azimuth,
    ) & scope_mask
    valid_count = int(valid.sum())
    if valid_count == 0:
        raise RuntimeError("No valid LiDAR cells were found in the expanded scope.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUTPUT,
        dsm=dsm_grid,
        dtm=ground.astype("float32"),
        canopy=canopy_grid,
        shade=shade,
        valid=valid,
        scope_mask=scope_mask,
        terrain_slope=terrain_slope,
        surface_slope=surface_slope,
        surface_aspect=surface_aspect,
        bounds=np.asarray([xmin, ymin, xmax, ymax], dtype="float64"),
        crs=np.asarray("EPSG:25831"),
        transform=np.asarray(tuple(transform)[:6], dtype="float64"),
    )
    scope_cells = int(scope_mask.sum())
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "analysis": "expanded_lidar_terrain_canopy_and_direct_summer_shade",
        "scope": "La Seu d'Urgell, Castellciutat and Sant Antoni",
        "study_bbox_epsg4326": bbox4326,
        "analysis_polygon_area_ha": round(float(polygon.area / 10000), 1),
        "grid_bounds_epsg25831": [xmin, ymin, xmax, ymax],
        "crs": "EPSG:25831",
        "resolution_m": RESOLUTION_M,
        "scope_cells": scope_cells,
        "valid_cells": valid_count,
        "valid_cells_pct": round(valid_count / scope_cells * 100, 1),
        "canopy_cover_pct": round(float(canopy_grid[valid].mean() * 100), 1),
        "shade_pct": round(float(shade[valid].mean() * 100), 1),
        "terrain_slope_median_deg": round(float(np.median(terrain_slope[valid])), 1),
        "shade_datetime_local": "2026-06-21 15:00 CEST",
        "solar_elevation_deg": round(float(solar_elevation), 1),
        "solar_azimuth_deg": round(float(solar_azimuth), 1),
        "source": "ICGC LiDAR Territorial v3.1, 2021-2023",
        "organization": "Institut Cartografic i Geologic de Catalunya",
        "license": "CC BY 4.0",
        "classification": {
            "ground": [2, 8, 75],
            "canopy": [4, 5],
            "surface": [2, 3, 4, 5, 6, 8, 9, 17, 75, 77],
        },
        "method": "2 m DSM/DTM from classified points; canopy presence from classes 4-5; direct-sun obstruction at the documented solar position.",
        "limitations": "Modelled direct shade for one summer instant; not measured pedestrian thermal comfort, air temperature or a seasonal shade average.",
        "output": str(OUTPUT.relative_to(ROOT)),
        "tiles": tile_records,
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    payload = calculate()
    print(json.dumps({key: payload[key] for key in ("analysis_polygon_area_ha", "valid_cells_pct", "canopy_cover_pct", "shade_pct", "terrain_slope_median_deg")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
