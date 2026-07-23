"""ICGC DEM/MDT connector for EcoRadar.

The connector uses the official ICGC 5 m terrain model already cached for the
project when available. If the cache is missing it can read the official ICGC
Cloud Optimized GeoTIFF URL directly through rasterio.

It creates normalized terrain rasters only. It does not calculate EcoRadar
indicators or make ecological interpretations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask


PROJECT_ROOT = Path("projectes/Alinya")
STUDY_AREA_PATH = PROJECT_ROOT / "processed" / "study_area.gpkg"
RAW_DEM_PATH = PROJECT_ROOT / "raw" / "terrain" / "icgc_dem_5m_alinya_window.tif"
PROCESSED_DIR = PROJECT_ROOT / "processed" / "terrain"
DEM_PATH = PROCESSED_DIR / "dem.tif"
SLOPE_PATH = PROCESSED_DIR / "slope.tif"
ASPECT_PATH = PROCESSED_DIR / "aspect.tif"
NORTHNESS_PATH = PROCESSED_DIR / "northness.tif"
SOLANA_OBAGA_PATH = PROCESSED_DIR / "solana_obaga.tif"
METADATA_PATH = PROJECT_ROOT / "metadata" / "terrain_metadata.json"
VALIDATION_PATH = PROJECT_ROOT / "metadata" / "validations" / "connector_icgc_dem_mdt_validation.json"

TARGET_CRS = "EPSG:25831"
SOURCE_NAME = "ICGC Model d'elevacions del terreny 5 m"
SOURCE_URL = (
    "https://datacloud.icgc.cat/datacloud/model-elevacions-terreny/tif_unzip/"
    "model-elevacions-terreny-topografic-catalunya-5m-2009-2018.tif"
)


def main() -> None:
    result = run_connector()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_connector() -> dict[str, Any]:
    _ensure_dirs()
    study_area = _load_study_area()
    dem_source = RAW_DEM_PATH if RAW_DEM_PATH.exists() else Path(SOURCE_URL)
    dem_data, profile = _read_and_clip_dem(dem_source, study_area)
    slope, aspect, northness, solana_obaga = _derive_terrain(dem_data, profile)

    _write_raster(DEM_PATH, dem_data, profile, nodata=-9999.0)
    _write_raster(SLOPE_PATH, slope, profile, nodata=-9999.0)
    _write_raster(ASPECT_PATH, aspect, profile, nodata=-9999.0)
    _write_raster(NORTHNESS_PATH, northness, profile, nodata=-9999.0)
    _write_raster(SOLANA_OBAGA_PATH, solana_obaga, profile, nodata=0)

    metadata = _write_metadata(study_area, dem_data, slope, aspect, northness)
    validation = _write_validation(metadata)
    return {
        "status": "completed",
        "outputs": {
            "dem": str(DEM_PATH),
            "slope": str(SLOPE_PATH),
            "aspect": str(ASPECT_PATH),
            "northness": str(NORTHNESS_PATH),
            "solana_obaga": str(SOLANA_OBAGA_PATH),
            "metadata": str(METADATA_PATH),
            "validation": str(VALIDATION_PATH),
        },
        "metadata": metadata,
        "validation": validation,
    }


def _ensure_dirs() -> None:
    for directory in (RAW_DEM_PATH.parent, PROCESSED_DIR, METADATA_PATH.parent, VALIDATION_PATH.parent):
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


def _read_and_clip_dem(source: Path, study_area: gpd.GeoDataFrame) -> tuple[np.ndarray, dict[str, Any]]:
    with rasterio.open(str(source)) as dataset:
        mask_area = study_area.to_crs(dataset.crs)
        geometries = [geom for geom in mask_area.geometry if geom is not None and not geom.is_empty]
        clipped, transform = mask(dataset, geometries, crop=True, filled=True)
        data = clipped[0].astype("float32")
        nodata = dataset.nodata if dataset.nodata is not None else -9999.0
        data[data == nodata] = -9999.0
        profile = dataset.profile.copy()
        profile.update(
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=1,
            dtype="float32",
            nodata=-9999.0,
            transform=transform,
            compress="deflate",
            predictor=2,
        )
    return data, profile


def _derive_terrain(dem: np.ndarray, profile: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    z = dem.astype("float32").copy()
    valid = z != -9999.0
    z[~valid] = np.nan
    transform = profile["transform"]
    res_x = abs(float(transform.a))
    res_y = abs(float(transform.e))
    dz_dy, dz_dx = np.gradient(z, res_y, res_x)
    slope = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))).astype("float32")
    aspect = (np.degrees(np.arctan2(dz_dx, -dz_dy)) + 360.0) % 360.0
    aspect = aspect.astype("float32")
    northness = np.cos(np.deg2rad(aspect)).astype("float32")
    # 1 = obaga / north-facing, -1 = solana / south-facing, 0 = neutral or nodata.
    solana_obaga = np.zeros(dem.shape, dtype="int16")
    solana_obaga[(northness >= 0.35) & valid] = 1
    solana_obaga[(northness <= -0.35) & valid] = -1

    for array in (slope, aspect, northness):
        array[~valid] = -9999.0
    solana_obaga[~valid] = 0
    return slope, aspect, northness, solana_obaga.astype("float32")


def _write_raster(path: Path, data: np.ndarray, profile: dict[str, Any], *, nodata: float | int) -> None:
    output_profile = profile.copy()
    output_profile.update(dtype="float32", nodata=nodata, compress="deflate")
    with rasterio.open(path, "w", **output_profile) as destination:
        destination.write(data.astype("float32"), 1)


def _stats(data: np.ndarray, nodata: float = -9999.0) -> dict[str, float | None]:
    valid = data[(data != nodata) & np.isfinite(data)]
    if valid.size == 0:
        return {"min": None, "max": None, "mean": None, "std": None}
    return {
        "min": round(float(np.nanmin(valid)), 4),
        "max": round(float(np.nanmax(valid)), 4),
        "mean": round(float(np.nanmean(valid)), 4),
        "std": round(float(np.nanstd(valid)), 4),
    }


def _write_metadata(
    study_area: gpd.GeoDataFrame,
    dem: np.ndarray,
    slope: np.ndarray,
    aspect: np.ndarray,
    northness: np.ndarray,
) -> dict[str, Any]:
    with rasterio.open(DEM_PATH) as dataset:
        bounds = [round(value, 3) for value in dataset.bounds]
        resolution = list(dataset.res)
        crs = str(dataset.crs)
        width = dataset.width
        height = dataset.height
    metadata = {
        "project": "Alinya",
        "source": SOURCE_NAME,
        "responsible_organization": "Institut Cartogràfic i Geològic de Catalunya",
        "url": SOURCE_URL,
        "service_type": "Cloud Optimized GeoTIFF / raster file",
        "query_date": datetime.now(timezone.utc).isoformat(),
        "crs": crs,
        "resolution_m": resolution,
        "width": width,
        "height": height,
        "bounds": bounds,
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
        "outputs": {
            "dem": str(DEM_PATH),
            "slope": str(SLOPE_PATH),
            "aspect": str(ASPECT_PATH),
            "northness": str(NORTHNESS_PATH),
            "solana_obaga": str(SOLANA_OBAGA_PATH),
        },
        "variables": {
            "altitude_m": _stats(dem),
            "slope_degrees": _stats(slope),
            "aspect_degrees": _stats(aspect),
            "northness": _stats(northness),
        },
        "limitations": [
            "Pendent, orientació i obaga/solana són derivats geomorfològics del DEM, no indicadors ecològics finals.",
            "La classificació obaga/solana és una capa normalitzada simple basada en orientació; la insolació real requeriria model solar amb data, ombres i horizon.",
            "El connector no calcula cap indicador EcoRadar.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata


def _write_validation(metadata: dict[str, Any]) -> dict[str, Any]:
    outputs = metadata["outputs"]
    missing = [path for path in outputs.values() if not Path(path).exists()]
    status = "completed" if not missing else "failed"
    validation = {
        "connector": "connector_icgc_dem_mdt",
        "project": "Alinya",
        "validated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "can_advance_to_next_connector": status == "completed",
        "source": SOURCE_NAME,
        "outputs": outputs,
        "missing_outputs": missing,
        "checks": {
            "crs_is_epsg_25831": metadata.get("crs") == TARGET_CRS,
            "resolution_is_5m": all(abs(float(value) - 5.0) < 0.001 for value in metadata.get("resolution_m", [])),
            "has_altitude_stats": metadata["variables"]["altitude_m"]["mean"] is not None,
            "has_slope_stats": metadata["variables"]["slope_degrees"]["mean"] is not None,
            "has_aspect_stats": metadata["variables"]["aspect_degrees"]["mean"] is not None,
        },
    }
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return validation


if __name__ == "__main__":
    main()
