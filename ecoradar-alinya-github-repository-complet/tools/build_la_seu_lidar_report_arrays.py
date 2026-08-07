"""Build LiDAR raster arrays used by the La Seu urban diagnosis report.

This helper is intentionally limited to numeric LAZ processing so it can run
inside the project's geospatial virtual environment. The PDF exporter converts
the saved arrays to styled PNG figures with the bundled artifact runtime.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import laspy
import numpy as np

from calculate_la_seu_urban_metrics import (
    LIDAR_BBOX_25831,
    LIDAR_FILES,
    _fill_missing_dtm,
    _shadow_mask,
    _solar_position,
)


ROOT = Path(__file__).resolve().parents[1]


def build_arrays(output: Path) -> None:
    xmin, ymin, xmax, ymax = LIDAR_BBOX_25831
    resolution = 2.0
    ncols = int(np.ceil((xmax - xmin) / resolution))
    nrows = int(np.ceil((ymax - ymin) / resolution))
    size = nrows * ncols
    dsm = np.full(size, -np.inf, dtype="float32")
    dtm = np.full(size, np.inf, dtype="float32")
    canopy = np.zeros(size, dtype=bool)

    surface_classes = {2, 3, 4, 5, 6, 8, 9, 17, 75, 77}
    ground_classes = {2, 8, 75}
    canopy_classes = {4, 5}

    for relative_path in LIDAR_FILES:
        laz_path = ROOT / relative_path
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
                x = x[inside]
                y = y[inside]
                z = z[inside]
                classification = classification[inside]
                col = np.floor((x - xmin) / resolution).astype("int32")
                row = np.floor((ymax - y) / resolution).astype("int32")
                valid_index = (row >= 0) & (row < nrows) & (col >= 0) & (col < ncols)
                index = row[valid_index] * ncols + col[valid_index]
                z = z[valid_index].astype("float32")
                classification = classification[valid_index]

                surface = np.isin(classification, list(surface_classes))
                if bool(surface.any()):
                    np.maximum.at(dsm, index[surface], z[surface])
                ground_points = np.isin(classification, list(ground_classes))
                if bool(ground_points.any()):
                    np.minimum.at(dtm, index[ground_points], z[ground_points])
                tree_points = np.isin(classification, list(canopy_classes))
                if bool(tree_points.any()):
                    canopy[np.unique(index[tree_points])] = True

    dsm_grid = dsm.reshape((nrows, ncols))
    dtm_grid = dtm.reshape((nrows, ncols))
    ground = _fill_missing_dtm(dtm_grid, np.isfinite(dtm_grid), dsm_grid)
    solar_utc = datetime(2026, 6, 21, 13, 0, tzinfo=timezone.utc)
    solar_elevation, solar_azimuth = _solar_position(solar_utc, 42.3565, 1.4600)
    canopy_grid = canopy.reshape((nrows, ncols))
    shade_grid = _shadow_mask(
        dsm_grid,
        ground,
        canopy_grid,
        resolution,
        solar_elevation,
        solar_azimuth,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        canopy=canopy_grid,
        shade=shade_grid,
        valid=np.isfinite(dsm_grid),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_arrays(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
