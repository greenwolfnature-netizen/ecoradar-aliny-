"""Calculate traceable urban climate metrics for La Seu d'Urgell.

The script deliberately separates official source access and derived metrics
from poster rendering. It uses:

- USGS Landsat Collection 2 Level-2 ST_B10, accessed through the Planetary
  Computer mirror of the same USGS item because direct USGS COG access requires
  EROS login or requester-pays AWS credentials in this environment.
- ICGC LiDAR Territorial v3.1 LAZ tiles already downloaded to tmp/.

The LiDAR calculation is limited to a central urban bbox covered by two 1 km
tiles. Do not generalize those values to the whole municipality.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import urlopen

import laspy
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.windows import from_bounds


OUT_PATH = Path("output/la_seu_urban_metrics_real_v2.json")

PC_ITEM_URL = (
    "https://planetarycomputer.microsoft.com/api/stac/v1/collections/"
    "landsat-c2-l2/items/LC09_L2SP_198030_20260708_02_T1"
)
PC_SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"

LANDSAT_BBOX_4326 = (1.452, 42.352, 1.468, 42.361)
LIDAR_BBOX_25831 = (372505.0, 4690020.0, 373841.0, 4690995.0)
LIDAR_FILES = [
    Path("tmp/lidar-territorial-v3r1-full1km372690-2021-2023.laz"),
    Path("tmp/lidar-territorial-v3r1-full1km373690-2021-2023.laz"),
]


@dataclass(frozen=True)
class LandsatMetrics:
    item_id: str
    datetime_utc: str
    datetime_local_note: str
    cloud_cover_pct: float
    bbox_epsg4326: tuple[float, float, float, float]
    valid_pixels: int
    lst_mean_c: float
    lst_min_c: float
    lst_max_c: float
    lst_p10_c: float
    lst_p90_c: float
    access_note: str


@dataclass(frozen=True)
class LidarMetrics:
    bbox_epsg25831: tuple[float, float, float, float]
    area_ha: float
    grid_resolution_m: float
    dsm_valid_cells_pct: float
    canopy_cover_pct: float
    shade_pct: float
    solar_datetime_local: str
    solar_elevation_deg: float
    solar_azimuth_deg: float
    lidar_tiles: list[str]
    limitation: str


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    landsat = calculate_landsat_metrics()
    lidar = calculate_lidar_metrics()
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "study_area_note": (
            "Metrics are calculated for a central urban bbox, not for the full "
            "municipal boundary. Municipal tree count comes from the official "
            "Ajuntament web page documented in docs/data_sources/urban_climate_la_seu.md."
        ),
        "municipal_green": {
            "source": "Ajuntament de la Seu d'Urgell",
            "green_spaces_ha": 22,
            "planted_trees_streets_and_parks": 5500,
            "tree_species": 80,
            "official_url": (
                "https://www.laseu.cat/viure-a-la-seu/mediambient/"
                "ecoturisme-la-seu-naturalment/per-que-es-important-el-verd-urba/"
                "on-som-la-gestio-actual-del-verd-urba"
            ),
        },
        "landsat_lst": asdict(landsat),
        "lidar_central_core": asdict(lidar),
        "linear_tree_cover_official": {
            "status": "blocked",
            "reason": (
                "No open geospatial municipal tree inventory was found. The ICGC "
                "RTT vector extract endpoint for the road network returns an email "
                "request form, not a direct dataset in this environment."
            ),
        },
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def calculate_landsat_metrics() -> LandsatMetrics:
    item = _read_json_url(PC_ITEM_URL)
    signed_st = _sign_pc_href(item["assets"]["lwir11"]["href"])
    signed_qa = _sign_pc_href(item["assets"]["qa_pixel"]["href"])
    scale = float(item["assets"]["lwir11"]["raster:bands"][0]["scale"])
    offset = float(item["assets"]["lwir11"]["raster:bands"][0]["offset"])
    nodata = int(item["assets"]["lwir11"]["raster:bands"][0]["nodata"])

    with rasterio.open(signed_st) as st_src:
        transformer = Transformer.from_crs("EPSG:4326", st_src.crs, always_xy=True)
        xmin, ymin = transformer.transform(LANDSAT_BBOX_4326[0], LANDSAT_BBOX_4326[1])
        xmax, ymax = transformer.transform(LANDSAT_BBOX_4326[2], LANDSAT_BBOX_4326[3])
        left, right = sorted((xmin, xmax))
        bottom, top = sorted((ymin, ymax))
        window = from_bounds(left, bottom, right, top, st_src.transform).round_offsets().round_lengths()
        st_dn = st_src.read(1, window=window)

    with rasterio.open(signed_qa) as qa_src:
        qa = qa_src.read(1, window=window)

    invalid_bits = (
        (1 << 0)  # fill
        | (1 << 1)  # dilated cloud
        | (1 << 2)  # cirrus
        | (1 << 3)  # cloud
        | (1 << 4)  # cloud shadow
        | (1 << 5)  # snow
    )
    valid = (st_dn != nodata) & ((qa & invalid_bits) == 0)
    values_c = st_dn.astype("float64") * scale + offset - 273.15
    clean = values_c[valid]
    if clean.size == 0:
        raise RuntimeError("No valid Landsat ST_B10 pixels after QA mask")

    return LandsatMetrics(
        item_id=str(item["id"]),
        datetime_utc=str(item["properties"]["datetime"]),
        datetime_local_note="2026-07-08 12:35 CEST, derived from 10:35 UTC acquisition",
        cloud_cover_pct=float(item["properties"]["eo:cloud_cover"]),
        bbox_epsg4326=LANDSAT_BBOX_4326,
        valid_pixels=int(clean.size),
        lst_mean_c=round(float(np.mean(clean)), 1),
        lst_min_c=round(float(np.min(clean)), 1),
        lst_max_c=round(float(np.max(clean)), 1),
        lst_p10_c=round(float(np.percentile(clean, 10)), 1),
        lst_p90_c=round(float(np.percentile(clean, 90)), 1),
        access_note=(
            "USGS STAC item verified; COG read through Planetary Computer signed "
            "mirror because direct USGS asset access required EROS/AWS credentials."
        ),
    )


def calculate_lidar_metrics() -> LidarMetrics:
    for path in LIDAR_FILES:
        if not path.exists():
            raise FileNotFoundError(path)

    xmin, ymin, xmax, ymax = LIDAR_BBOX_25831
    res = 2.0
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
        with laspy.open(laz_path) as src:
            for points in src.chunk_iterator(2_000_000):
                x = np.asarray(points.x)
                y = np.asarray(points.y)
                z = np.asarray(points.z)
                cls = np.asarray(points.classification)
                in_bbox = (x >= xmin) & (x < xmax) & (y >= ymin) & (y < ymax)
                if not bool(in_bbox.any()):
                    continue
                x = x[in_bbox]
                y = y[in_bbox]
                z = z[in_bbox]
                cls = cls[in_bbox]
                col = np.floor((x - xmin) / res).astype("int32")
                row = np.floor((ymax - y) / res).astype("int32")
                ok = (row >= 0) & (row < nrows) & (col >= 0) & (col < ncols)
                if not bool(ok.any()):
                    continue
                idx = row[ok] * ncols + col[ok]
                z = z[ok].astype("float32")
                cls = cls[ok]

                surface = np.isin(cls, list(surface_classes))
                if bool(surface.any()):
                    np.maximum.at(dsm, idx[surface], z[surface])

                ground = np.isin(cls, list(ground_classes))
                if bool(ground.any()):
                    np.minimum.at(dtm, idx[ground], z[ground])

                trees = np.isin(cls, list(canopy_classes))
                if bool(trees.any()):
                    canopy[np.unique(idx[trees])] = True

    dsm_grid = dsm.reshape((nrows, ncols))
    dtm_grid = dtm.reshape((nrows, ncols))
    dsm_valid = np.isfinite(dsm_grid)
    dtm_valid = np.isfinite(dtm_grid)
    dtm_filled = _fill_missing_dtm(dtm_grid, dtm_valid, dsm_grid)

    lon, lat = Transformer.from_crs("EPSG:25831", "EPSG:4326", always_xy=True).transform(
        (xmin + xmax) / 2.0,
        (ymin + ymax) / 2.0,
    )
    solar_utc = datetime(2026, 6, 21, 13, 0, tzinfo=timezone.utc)
    solar_elev, solar_az = _solar_position(solar_utc, lat, lon)
    shade = _shadow_mask(dsm_grid, dtm_filled, canopy.reshape((nrows, ncols)), res, solar_elev, solar_az)

    total_cells = nrows * ncols
    area_ha = (ncols * res) * (nrows * res) / 10000.0
    return LidarMetrics(
        bbox_epsg25831=LIDAR_BBOX_25831,
        area_ha=round(area_ha, 1),
        grid_resolution_m=res,
        dsm_valid_cells_pct=round(float(dsm_valid.mean() * 100.0), 1),
        canopy_cover_pct=round(float(canopy.mean() * 100.0), 1),
        shade_pct=round(float(shade.mean() * 100.0), 1),
        solar_datetime_local="2026-06-21 15:00 CEST",
        solar_elevation_deg=round(float(solar_elev), 1),
        solar_azimuth_deg=round(float(solar_az), 1),
        lidar_tiles=[str(path) for path in LIDAR_FILES],
        limitation=(
            "LiDAR shade is modelled for the central urban bbox only. It uses a 2 m "
            "DSM/DTM grid from ICGC point classes and a simple direct-sun obstruction "
            "model; it is not a field-measured pedestrian thermal-comfort index."
        ),
    )


def _fill_missing_dtm(dtm: np.ndarray, valid: np.ndarray, dsm: np.ndarray) -> np.ndarray:
    filled = dtm.copy()
    filled[~valid] = np.nan
    for _ in range(40):
        missing = np.isnan(filled)
        if not bool(missing.any()):
            break
        total = np.zeros_like(filled, dtype="float32")
        count = np.zeros_like(filled, dtype="uint8")
        for shifted in _neighbor_arrays(filled):
            ok = ~np.isnan(shifted)
            total[ok] += shifted[ok]
            count[ok] += 1
        can_fill = missing & (count > 0)
        filled[can_fill] = total[can_fill] / count[can_fill]
    still_missing = np.isnan(filled)
    if bool(still_missing.any()):
        fallback = np.where(np.isfinite(dsm), dsm, np.nanmedian(filled))
        filled[still_missing] = fallback[still_missing]
    return filled


def _neighbor_arrays(arr: np.ndarray) -> Iterable[np.ndarray]:
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            yield _shift(arr, dr, dc, fill=np.nan)


def _shadow_mask(
    dsm: np.ndarray,
    ground: np.ndarray,
    canopy: np.ndarray,
    resolution: float,
    solar_elevation_deg: float,
    solar_azimuth_deg: float,
) -> np.ndarray:
    valid = np.isfinite(dsm) & np.isfinite(ground)
    shadow = canopy.copy()
    tan_elev = math.tan(math.radians(solar_elevation_deg))
    az = math.radians(solar_azimuth_deg)
    dx = math.sin(az)
    dy = math.cos(az)
    seen_shifts: set[tuple[int, int]] = set()
    for distance in np.arange(resolution, 160.0 + resolution, resolution):
        col_shift = int(round((dx * distance) / resolution))
        row_shift = int(round((-dy * distance) / resolution))
        if (row_shift, col_shift) == (0, 0) or (row_shift, col_shift) in seen_shifts:
            continue
        seen_shifts.add((row_shift, col_shift))
        obstacle = _shift(dsm, row_shift, col_shift, fill=-np.inf)
        blocks_sun = obstacle > (ground + distance * tan_elev)
        shadow |= valid & blocks_sun
    return shadow & valid


def _shift(arr: np.ndarray, row_shift: int, col_shift: int, fill: float) -> np.ndarray:
    out = np.full(arr.shape, fill, dtype=arr.dtype)
    nrows, ncols = arr.shape

    if row_shift >= 0:
        src_r0, src_r1 = row_shift, nrows
        dst_r0, dst_r1 = 0, nrows - row_shift
    else:
        src_r0, src_r1 = 0, nrows + row_shift
        dst_r0, dst_r1 = -row_shift, nrows

    if col_shift >= 0:
        src_c0, src_c1 = col_shift, ncols
        dst_c0, dst_c1 = 0, ncols - col_shift
    else:
        src_c0, src_c1 = 0, ncols + col_shift
        dst_c0, dst_c1 = -col_shift, ncols

    if src_r1 > src_r0 and src_c1 > src_c0:
        out[dst_r0:dst_r1, dst_c0:dst_c1] = arr[src_r0:src_r1, src_c0:src_c1]
    return out


def _solar_position(dt_utc: datetime, lat_deg: float, lon_deg: float) -> tuple[float, float]:
    if dt_utc.tzinfo is None:
        raise ValueError("dt_utc must be timezone aware")
    dt_utc = dt_utc.astimezone(timezone.utc)
    doy = int(dt_utc.strftime("%j"))
    hour = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    gamma = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    true_solar_minutes = (hour * 60 + eqtime + 4 * lon_deg) % 1440
    hour_angle = math.radians(true_solar_minutes / 4 - 180)
    lat = math.radians(lat_deg)
    cos_zenith = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(hour_angle)
    cos_zenith = min(1.0, max(-1.0, cos_zenith))
    zenith = math.acos(cos_zenith)
    elevation = 90 - math.degrees(zenith)
    azimuth = (math.degrees(math.atan2(math.sin(hour_angle), math.cos(hour_angle) * math.sin(lat) - math.tan(decl) * math.cos(lat))) + 180) % 360
    return elevation, azimuth


def _read_json_url(url: str) -> dict:
    with urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _sign_pc_href(href: str) -> str:
    url = f"{PC_SIGN_URL}?{urlencode({'href': href})}"
    signed = _read_json_url(url)
    return str(signed["href"])


if __name__ == "__main__":
    main()
