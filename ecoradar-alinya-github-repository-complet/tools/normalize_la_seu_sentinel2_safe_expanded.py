"""Normalize an official CDSE Sentinel-2 L2A SAFE product for the expanded scope.

The script accepts either the product ZIP downloaded from Copernicus Browser or
an extracted SAFE directory. It reads the official L2A quantification metadata,
applies band-specific BOA offsets, crops the requested extent and resamples the
20 m bands to the 10 m grid. It performs no indicator analysis.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from xml.etree import ElementTree
import zipfile

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window, from_bounds
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
OUTPUT = PROJECT / "processed" / "sentinel2_cdse_expanded" / "sentinel2_l2a_reflectance_quality.tif"
METADATA = PROJECT / "metadata" / "sentinel2_cdse_expanded_connector.json"
BANDS_10M = ("B02", "B04", "B08")
BANDS_20M = ("B11", "B12")
BAND_IDS = {"B02": 1, "B04": 3, "B08": 7, "B11": 11, "B12": 12}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _members(source: Path) -> list[str]:
    if source.is_dir():
        return [str(path.relative_to(source)) for path in source.rglob("*") if path.is_file()]
    with zipfile.ZipFile(source) as archive:
        return archive.namelist()


def _find_member(members: list[str], pattern: str) -> str:
    matches = [member for member in members if re.search(pattern, member)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one SAFE member for {pattern!r}; found {len(matches)}.")
    return matches[0]


def _read_bytes(source: Path, member: str) -> bytes:
    if source.is_dir():
        return (source / member).read_bytes()
    with zipfile.ZipFile(source) as archive:
        return archive.read(member)


def _dataset(source: Path, member: str) -> str:
    if source.is_dir():
        return str(source / member)
    return f"zip://{source}!{member}"


def _quantification(source: Path, members: list[str]) -> tuple[float, dict[str, float]]:
    metadata_member = _find_member(members, r"(^|/)MTD_MSIL2A\.xml$")
    root = ElementTree.fromstring(_read_bytes(source, metadata_member))
    quantification = None
    offsets_by_id: dict[int, float] = {}
    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1]
        if name == "BOA_QUANTIFICATION_VALUE" and element.text:
            quantification = float(element.text)
        elif name == "BOA_ADD_OFFSET" and element.text:
            band_id = element.attrib.get("band_id")
            if band_id is not None:
                offsets_by_id[int(band_id)] = float(element.text)
    if not quantification or quantification <= 0:
        raise RuntimeError("SAFE metadata does not contain a valid BOA_QUANTIFICATION_VALUE.")
    missing = [band for band, band_id in BAND_IDS.items() if band_id not in offsets_by_id]
    if missing:
        raise RuntimeError(f"SAFE metadata is missing BOA offsets for: {', '.join(missing)}")
    return quantification, {band: offsets_by_id[band_id] for band, band_id in BAND_IDS.items()}


def _aligned_window(dataset, bbox4326) -> Window:
    transformer = Transformer.from_crs(4326, dataset.crs, always_xy=True)
    coordinates = [
        transformer.transform(lon, lat)
        for lon in (bbox4326[0], bbox4326[2])
        for lat in (bbox4326[1], bbox4326[3])
    ]
    bounds = (
        min(point[0] for point in coordinates),
        min(point[1] for point in coordinates),
        max(point[0] for point in coordinates),
        max(point[1] for point in coordinates),
    )
    raw = from_bounds(*bounds, transform=dataset.transform)
    col0 = max(0, math.floor(raw.col_off))
    row0 = max(0, math.floor(raw.row_off))
    col1 = min(dataset.width, math.ceil(raw.col_off + raw.width))
    row1 = min(dataset.height, math.ceil(raw.row_off + raw.height))
    if col1 <= col0 or row1 <= row0:
        raise RuntimeError("Expanded EcoRadar scope does not intersect the Sentinel-2 granule.")
    return Window(col0, row0, col1 - col0, row1 - row0)


def normalize(source: Path) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)
    members = _members(source)
    product_name = next((Path(member).parts[0] for member in members if ".SAFE/" in member), source.stem)
    quantification, offsets = _quantification(source, members)
    band_members = {
        band: _find_member(members, rf"/R10m/[^/]*_{band}_10m\.jp2$")
        for band in BANDS_10M
    }
    band_members.update({
        band: _find_member(members, rf"/R20m/[^/]*_{band}_20m\.jp2$")
        for band in BANDS_20M
    })
    scl_member = _find_member(members, r"/R20m/[^/]*_SCL_20m\.jp2$")
    project = json.loads(PROJECT_MANIFEST.read_text())
    bbox = tuple(float(value) for value in project["study_area"]["expanded_urban_bbox_epsg4326"])

    raw_bands: dict[str, np.ndarray] = {}
    with rasterio.open(_dataset(source, band_members["B02"])) as reference:
        window = _aligned_window(reference, bbox)
        target_transform = reference.window_transform(window)
        target_crs = reference.crs
        width, height = int(window.width), int(window.height)
    for band in BANDS_10M:
        with rasterio.open(_dataset(source, band_members[band])) as dataset:
            raw_bands[band] = dataset.read(1, window=window).astype("float32")
    for band in BANDS_20M:
        with rasterio.open(_dataset(source, band_members[band])) as dataset:
            with WarpedVRT(
                dataset,
                crs=target_crs,
                transform=target_transform,
                width=width,
                height=height,
                resampling=Resampling.bilinear,
            ) as vrt:
                raw_bands[band] = vrt.read(1).astype("float32")
    with rasterio.open(_dataset(source, scl_member)) as dataset:
        with WarpedVRT(
            dataset,
            crs=target_crs,
            transform=target_transform,
            width=width,
            height=height,
            resampling=Resampling.nearest,
        ) as vrt:
            scl = vrt.read(1).astype("float32")

    source_valid = np.ones((height, width), dtype=bool)
    reflectance = []
    for band in ("B02", "B04", "B08", "B11", "B12"):
        raw = raw_bands[band]
        source_valid &= raw > 0
        reflectance.append((raw + offsets[band]) / quantification)
    source_valid &= scl > 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": 7,
        "dtype": "float32",
        "crs": target_crs,
        "transform": target_transform,
        "nodata": -9999.0,
        "compress": "deflate",
        "tiled": True,
    }
    with rasterio.open(OUTPUT, "w", **profile) as target:
        for index, values in enumerate(reflectance, start=1):
            target.write(np.where(source_valid, values, -9999.0).astype("float32"), index)
        target.write(np.where(source_valid, scl, 0).astype("float32"), 6)
        target.write(source_valid.astype("float32"), 7)
        for index, description in enumerate(("B02", "B04", "B08", "B11", "B12", "SCL", "dataMask"), start=1):
            target.set_band_description(index, description)

    sensing_match = re.search(r"(20\d{6}T\d{6})", product_name)
    sensing_time = (
        datetime.strptime(sensing_match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc).isoformat()
        if sensing_match
        else None
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Copernicus Sentinel-2 MSI Level-2A",
        "organization": "European Union Copernicus programme / ESA",
        "scene_id": product_name.removesuffix(".SAFE"),
        "acquired_at_utc": sensing_time,
        "source_file": str(source),
        "source_sha256": _sha256(source) if source.is_file() else None,
        "official_urls": {
            "stac": "https://stac.dataspace.copernicus.eu/v1/collections/sentinel-2-l2a",
            "browser": "https://browser.dataspace.copernicus.eu/",
        },
        "service_type": "official CDSE product download",
        "credentials": "free CDSE user session required for product download",
        "license": "Copernicus Sentinel data policy: free, full and open use with attribution",
        "connector_status": "verified",
        "study_bbox_epsg4326": bbox,
        "crs": str(target_crs),
        "resolution_m": 10,
        "bands": ["B02", "B04", "B08", "B11", "B12", "SCL", "dataMask"],
        "native_resolution_m": {"B02": 10, "B04": 10, "B08": 10, "B11": 20, "B12": 20, "SCL": 20},
        "normalization": {
            "formula": "BOA reflectance = (DN + BOA_ADD_OFFSET) / BOA_QUANTIFICATION_VALUE",
            "quantification_value": quantification,
            "band_offsets": offsets,
            "source": "MTD_MSIL2A.xml from the downloaded SAFE product",
        },
        "output": str(OUTPUT.relative_to(ROOT)),
    }
    METADATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Official CDSE Sentinel-2 L2A ZIP or extracted SAFE directory")
    args = parser.parse_args()
    payload = normalize(args.source.expanduser().resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
