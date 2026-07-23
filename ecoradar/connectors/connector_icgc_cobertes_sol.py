"""ICGC land-cover connector for EcoRadar.

This connector uses the official ICGC Cobertes del Sol service. It downloads
the 2024 WCS classified raster for the study-area bounding box, masks it with
the Alinya study area, polygonizes the clipped classes, and writes a summary
table. It does not calculate EcoRadar indices or ecological interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import re
import sys
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import urlopen

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.mask import mask
from shapely.geometry import shape


PROJECT_ROOT = Path("projectes/Alinya")
STUDY_AREA_PATH = PROJECT_ROOT / "processed" / "study_area.gpkg"
RAW_DIR = PROJECT_ROOT / "raw" / "cobertes_sol"
PROCESSED_PATH = PROJECT_ROOT / "processed" / "cobertes_sol.gpkg"
SUMMARY_PATH = PROJECT_ROOT / "indicators" / "cobertes_sol_resum.csv"
METADATA_PATH = PROJECT_ROOT / "metadata" / "cobertes_sol_metadata.json"

SERVICE_URL = "https://geoserveis.icgc.cat/servei/catalunya/cobertes-sol/wms"
SOURCE_NAME = "ICGC - Cobertes del Sol de Catalunya"
COVERAGE_ID = "cobertes_2024"
TARGET_CRS = "EPSG:25831"
TILE_SIZE_M = 4000
NO_LABEL = "Sense dades / no classificat"


@dataclass(frozen=True)
class Tile:
    xmin: int
    ymin: int
    xmax: int
    ymax: int

    @property
    def path_name(self) -> str:
        return f"{COVERAGE_ID}_{self.xmin}_{self.ymin}_{self.xmax}_{self.ymax}.tif"


def main() -> None:
    result = run_connector()
    print(json.dumps(result, indent=2))


def run_connector() -> dict[str, object]:
    _ensure_dirs()
    study_area = _load_study_area()
    bounds = study_area.total_bounds
    tiles = list(_build_tiles(bounds))

    records: list[dict[str, object]] = []
    pixel_counts: dict[int, int] = {}
    sample_points: dict[int, tuple[float, float]] = {}
    downloaded_tiles: list[str] = []

    geometries = [geom for geom in study_area.geometry if geom is not None and not geom.is_empty]
    for tile in tiles:
        tile_path = RAW_DIR / tile.path_name
        if not tile_path.exists():
            _download_tile(tile, tile_path)
        downloaded_tiles.append(str(tile_path))

        tile_records, tile_counts, tile_samples = _process_tile(tile_path, geometries)
        records.extend(tile_records)
        for code, count in tile_counts.items():
            pixel_counts[code] = pixel_counts.get(code, 0) + count
        for code, point in tile_samples.items():
            sample_points.setdefault(code, point)

    if not records:
        raise RuntimeError("No land-cover pixels were found inside the study area")

    class_labels = _resolve_class_labels(sample_points)
    output = gpd.GeoDataFrame(records, geometry="geometry", crs=TARGET_CRS)
    output["color_rgb"] = output["rgb_code"].map(_rgb_code_to_string)
    output["tipus_coberta"] = output["rgb_code"].map(class_labels).fillna(NO_LABEL)
    output = output[["rgb_code", "color_rgb", "tipus_coberta", "geometry"]]
    if PROCESSED_PATH.exists():
        PROCESSED_PATH.unlink()
    output.to_file(PROCESSED_PATH, layer="cobertes_sol", driver="GPKG")

    study_area_ha = float(study_area.geometry.union_all().area / 10000)
    total_area_ha = _write_summary(pixel_counts, class_labels, study_area_ha)
    metadata = _write_metadata(
        study_area=study_area,
        tiles=tiles,
        downloaded_tiles=downloaded_tiles,
        class_count=len(pixel_counts),
        total_area_ha=total_area_ha,
    )

    return {
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "metadata_path": str(METADATA_PATH),
        "classes": len(pixel_counts),
        "surface_ha": total_area_ha,
        "tiles": len(tiles),
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
        raise ValueError("Study area has invalid geometries; repair it before running connector")
    return study_area


def _build_tiles(bounds: Iterable[float]) -> Iterable[Tile]:
    xmin, ymin, xmax, ymax = [float(value) for value in bounds]
    x0 = int(np.floor(xmin))
    y0 = int(np.floor(ymin))
    x1 = int(np.ceil(xmax))
    y1 = int(np.ceil(ymax))

    x = x0
    while x < x1:
        next_x = min(x + TILE_SIZE_M, x1)
        y = y0
        while y < y1:
            next_y = min(y + TILE_SIZE_M, y1)
            yield Tile(xmin=x, ymin=y, xmax=next_x, ymax=next_y)
            y = next_y
        x = next_x


def _download_tile(tile: Tile, output_path: Path) -> None:
    params = [
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", COVERAGE_ID),
        ("FORMAT", "image/tiff"),
        ("SUBSET", f"x({tile.xmin},{tile.xmax})"),
        ("SUBSET", f"y({tile.ymin},{tile.ymax})"),
    ]
    url = f"{SERVICE_URL}?{urlencode(params)}"
    with urlopen(url, timeout=120) as response:
        payload = response.read()
    if payload.lstrip().startswith(b"<"):
        raise RuntimeError(f"WCS tile download failed for {tile}: {payload[:500].decode('utf-8', 'ignore')}")
    output_path.write_bytes(payload)


def _process_tile(
    tile_path: Path,
    geometries: list[object],
) -> tuple[list[dict[str, object]], dict[int, int], dict[int, tuple[float, float]]]:
    with rasterio.open(tile_path) as dataset:
        clipped, transform = mask(dataset, geometries, crop=True, filled=False)
        if clipped.shape[0] < 3:
            raise RuntimeError(f"Expected RGB GeoTIFF from WCS, got {clipped.shape[0]} bands in {tile_path}")
        red = clipped[0]
        green = clipped[1]
        blue = clipped[2]
        valid_mask = ~(red.mask | green.mask | blue.mask)
        red_values = np.asarray(red.filled(255), dtype=np.uint32)
        green_values = np.asarray(green.filled(255), dtype=np.uint32)
        blue_values = np.asarray(blue.filled(255), dtype=np.uint32)
        values = ((red_values << 16) | (green_values << 8) | blue_values).astype(np.int32)

        if not bool(valid_mask.any()):
            return [], {}, {}

        unique, counts = np.unique(values[valid_mask], return_counts=True)
        pixel_counts = {int(code): int(count) for code, count in zip(unique, counts)}
        sample_points = _sample_points(values, valid_mask, transform, pixel_counts.keys())

        tile_records = []
        for geometry_mapping, raster_value in shapes(values, mask=valid_mask, transform=transform):
            code = int(raster_value)
            tile_records.append(
                {
                    "rgb_code": code,
                    "geometry": shape(geometry_mapping),
                }
            )
        return tile_records, pixel_counts, sample_points


def _sample_points(
    values: np.ndarray,
    valid_mask: np.ndarray,
    transform: object,
    codes: Iterable[int],
) -> dict[int, tuple[float, float]]:
    points: dict[int, tuple[float, float]] = {}
    for code in codes:
        rows, cols = np.where((values == code) & valid_mask)
        if len(rows) == 0:
            continue
        x, y = rasterio.transform.xy(transform, int(rows[0]), int(cols[0]), offset="center")
        points[int(code)] = (float(x), float(y))
    return points


def _resolve_class_labels(sample_points: dict[int, tuple[float, float]]) -> dict[int, str]:
    labels: dict[int, str] = {}
    for code, (x, y) in sorted(sample_points.items()):
        label = _get_feature_info_label(x, y)
        labels[code] = label or f"Coberta {code}"
    return labels


def _get_feature_info_label(x: float, y: float) -> str | None:
    half_size = 5
    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetFeatureInfo",
        "layers": COVERAGE_ID,
        "query_layers": COVERAGE_ID,
        "styles": "",
        "crs": TARGET_CRS,
        "bbox": f"{x - half_size},{y - half_size},{x + half_size},{y + half_size}",
        "width": "10",
        "height": "10",
        "i": "5",
        "j": "5",
        "info_format": "text/plain",
    }
    url = f"{SERVICE_URL}?{urlencode(params)}"
    with urlopen(url, timeout=60) as response:
        text = response.read().decode("utf-8", "replace")
    for line in text.splitlines():
        if line.strip().startswith("class"):
            label = line.split("=", 1)[1].strip()
            if label.startswith("'") and label.endswith("'"):
                label = label[1:-1]
            return label
    return None


def _write_summary(pixel_counts: dict[int, int], labels: dict[int, str], study_area_ha: float) -> float:
    grouped: dict[str, int] = {}
    color_by_label: dict[str, list[str]] = {}
    for code, count in pixel_counts.items():
        label = labels.get(code, NO_LABEL)
        grouped[label] = grouped.get(label, 0) + count
        color_by_label.setdefault(label, []).append(_rgb_code_to_string(code))

    rows = []
    classified_ha = sum(grouped.values()) / 10000
    for label, count in sorted(grouped.items(), key=lambda item: item[0]):
        area_ha = count / 10000
        rows.append(
            {
                "tipus_coberta": label,
                "superficie_ha": round(area_ha, 4),
                "percentatge_total": round((area_ha / study_area_ha) * 100, 4) if study_area_ha else 0,
                "colors_rgb": ";".join(sorted(set(color_by_label[label]))),
            }
        )

    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["tipus_coberta", "superficie_ha", "percentatge_total", "colors_rgb"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return classified_ha


def _rgb_code_to_string(code: int) -> str:
    red = (int(code) >> 16) & 255
    green = (int(code) >> 8) & 255
    blue = int(code) & 255
    return f"{red},{green},{blue}"


def _write_metadata(
    study_area: gpd.GeoDataFrame,
    tiles: list[Tile],
    downloaded_tiles: list[str],
    class_count: int,
    total_area_ha: float,
) -> dict[str, object]:
    metadata = {
        "font": SOURCE_NAME,
        "url": SERVICE_URL,
        "service_type": "WCS/WMS",
        "coverage_id": COVERAGE_ID,
        "data_consulta": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "crs": TARGET_CRS,
        "escala_resolucio": "1 m raster classified coverage, according to WCS DescribeCoverage offset vectors",
        "limitacions": [
            "Connector uses ICGC WCS classified raster values and WMS GetFeatureInfo labels.",
            "The WCS GeoTIFF is RGB-rendered; classes are resolved from sampled RGB pixels through official WMS GetFeatureInfo responses.",
            "Areas are calculated from 1 m pixels after masking with the study area.",
            "Pixel-based clipping may differ slightly from vector-source areas along boundaries.",
            "No EcoRadar ecological interpretation or index is calculated.",
        ],
        "study_area_path": str(STUDY_AREA_PATH),
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "raw_tiles": downloaded_tiles,
        "tile_count": len(tiles),
        "class_count": class_count,
        "surface_ha_from_classified_pixels": total_area_ha,
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"connector_icgc_cobertes_sol failed: {exc}", file=sys.stderr)
        raise
