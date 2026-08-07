"""Process the official 2024 structural wildfire-danger raster for La Seu.

The script does not download data. It reads the already verified Generalitat
GeoTIFF, clips it to the expanded EcoRadar viewing rectangle, preserves the
official 1-10 values, renders a transparent web overlay, and registers the
result in the project manifests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.mask import mask
from rasterio.transform import array_bounds
from rasterio.warp import transform_bounds
from shapely.geometry import box, mapping
from shapely.ops import transform


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
RAW_DIR = PROJECT / "raw" / "incendis" / "perill_basic_2024"
RAW_TIF = RAW_DIR / "PERILLBASICINCENDI.tif"
PROCESSED_TIF = PROJECT / "processed" / "fire_danger_structural_2024.tif"
MAP_PNG = PROJECT / "maps" / "fire_danger_structural_2024.png"
INDICATOR_JSON = PROJECT / "indicators" / "fire_danger_structural_2024.json"
METADATA_JSON = PROJECT / "metadata" / "fire_danger_structural_2024.json"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
LAYER_MANIFEST = PROJECT / "metadata" / "layer_manifest.json"

# Operational rectangle, not an administrative neighbourhood boundary.
# It contains the original raster core, Castellciutat, both parts of Sant
# Antoni, and the verified Segre-Valira confluence with a 100 m display margin.
EXPANDED_BBOX_4326 = (1.4400, 42.3445, 1.4790, 42.3647)
PLACE_REFERENCES = [
    {
        "name": "Castellciutat",
        "coordinates_epsg4326": [1.4438139, 42.3552954],
        "source": "OpenStreetMap node/937152420; ref:idescat 2520380002201",
    },
    {
        "name": "Sant Antoni · la Seu d'Urgell",
        "coordinates_epsg4326": [1.4739694, 42.3614067],
        "source": "OpenStreetMap node/12526232576; ref:idescat 2520380004301",
    },
    {
        "name": "Sant Antoni · les Valls de Valira",
        "coordinates_epsg4326": [1.4751061, 42.3619862],
        "source": "OpenStreetMap node/12526232571; ref:idescat 2523980013601",
    },
]

# EcoRadar display symbology only. It does not change the official cell values.
COLORS = {
    1: (44, 123, 182),
    2: (99, 169, 196),
    3: (154, 203, 156),
    4: (201, 221, 120),
    5: (240, 230, 91),
    6: (247, 200, 75),
    7: (243, 154, 56),
    8: (231, 111, 46),
    9: (204, 61, 47),
    10: (139, 30, 45),
}

SOURCE = {
    "name": "Mapa bàsic de perill d'incendi forestal 2024",
    "organization": (
        "Generalitat de Catalunya. Departament d'Agricultura, "
        "Ramaderia, Pesca i Alimentació"
    ),
    "official_page": (
        "https://agricultura.gencat.cat/ca/serveis/cartografia-sig/"
        "bases-cartografiques/boscos/mapa-perill-incendi-forestal/"
        "mapa-perill-basic-incendi-forestal-2024"
    ),
    "download_url": (
        "https://gencat.cat/agricultura/sig/bases/PERILLBASICINCENDI.zip"
    ),
    "license": "Llicència oberta d'ús d'informació - Catalunya",
    "reference_date": "2024-01",
    "credentials": "none",
    "status": "verified",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not RAW_TIF.exists():
        raise FileNotFoundError(
            f"Missing verified source raster: {RAW_TIF}. "
            "Download and extract the official ZIP first."
        )

    processed_at = datetime.now(timezone.utc).isoformat()
    expanded_polygon_4326 = box(*EXPANDED_BBOX_4326)
    to_25831 = Transformer.from_crs(4326, 25831, always_xy=True).transform
    expanded_area_ha = transform(to_25831, expanded_polygon_4326).area / 10_000

    with rasterio.open(RAW_TIF) as src:
        to_source = Transformer.from_crs(4326, src.crs, always_xy=True).transform
        source_geometry = transform(to_source, expanded_polygon_4326)
        clipped, clipped_transform = mask(
            src,
            [mapping(source_geometry)],
            crop=True,
            all_touched=False,
            filled=False,
        )
        band = clipped[0]
        valid_mask = (~np.ma.getmaskarray(band)) & (band.data != src.nodata)
        values = band.data[valid_mask].astype(np.uint8)
        if not values.size:
            raise RuntimeError("The official raster has no valid forest cells in the bbox")

        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            height=band.shape[0],
            width=band.shape[1],
            transform=clipped_transform,
            count=1,
            dtype="uint8",
            nodata=15,
            compress="deflate",
        )
        PROCESSED_TIF.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(PROCESSED_TIF, "w", **profile) as dst:
            dst.write(np.where(valid_mask, band.data, 15).astype(np.uint8), 1)
            dst.update_tags(
                source=SOURCE["name"],
                source_url=SOURCE["official_page"],
                values="Official relative structural wildfire-danger scale 1-10",
                ecoradar_scope="Expanded operational rectangle; not neighbourhood boundary",
            )

        source_bounds = array_bounds(band.shape[0], band.shape[1], clipped_transform)
        web_bounds = transform_bounds(src.crs, 4326, *source_bounds, densify_pts=21)
        source_metadata = {
            "crs": src.crs.to_epsg(),
            "resolution_m": list(src.res),
            "nodata": src.nodata,
            "dtype": src.dtypes[0],
            "source_dimensions": [src.width, src.height],
            "source_bounds": list(src.bounds),
        }

    rgba = np.zeros((4, band.shape[0], band.shape[1]), dtype=np.uint8)
    for value, color in COLORS.items():
        selected = valid_mask & (band.data == value)
        rgba[0][selected], rgba[1][selected], rgba[2][selected] = color
        rgba[3][selected] = 220
    # Upscale with nearest-neighbour replication so browsers preserve the
    # categorical 100 m cells instead of blurring the very small source crop.
    web_scale = 20
    rgba_web = np.repeat(np.repeat(rgba, web_scale, axis=1), web_scale, axis=2)
    MAP_PNG.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        MAP_PNG,
        "w",
        driver="PNG",
        width=rgba_web.shape[2],
        height=rgba_web.shape[1],
        count=4,
        dtype="uint8",
    ) as dst:
        dst.write(rgba_web)

    unique, counts = np.unique(values, return_counts=True)
    distribution = {
        str(int(value)): {
            "cells": int(count),
            "forest_area_ha": int(count),
            "share_valid_forest_cells_pct": round(float(count / values.size * 100), 1),
        }
        for value, count in zip(unique, counts)
    }
    mode_value = int(unique[np.argmax(counts)])
    stats = {
        "valid_forest_cells": int(values.size),
        "valid_forest_area_ha": int(values.size),
        "minimum": int(values.min()),
        "maximum": int(values.max()),
        "median": float(np.median(values)),
        "mode": mode_value,
        "cells_8_to_10_pct": round(float((values >= 8).mean() * 100), 1),
        "distribution": distribution,
    }
    interpretation = (
        "Official relative structural-danger scale. Values are not ignition "
        "probabilities, daily danger, vulnerability, exposure, or emergency warnings."
    )

    metadata = {
        "generated_at_utc": processed_at,
        "source": SOURCE,
        "source_file": str(RAW_TIF.relative_to(ROOT)),
        "source_sha256": sha256(RAW_TIF),
        "source_raster": source_metadata,
        "expanded_operational_scope": {
            "bbox_epsg4326": list(EXPANDED_BBOX_4326),
            "area_ha": round(expanded_area_ha, 1),
            "definition": (
                "Original urban raster core, Castellciutat and Sant Antoni, "
                "extended south to include the Segre-Valira confluence."
            ),
            "limitation": "Operational rectangle; not an administrative boundary.",
            "place_references": PLACE_REFERENCES,
        },
        "processed_layer": {
            "tif": str(PROCESSED_TIF.relative_to(ROOT)),
            "png": str(MAP_PNG.relative_to(ROOT)),
            "bbox_epsg4326": list(web_bounds),
            "resolution_m": 100,
            "values": "1-10, unchanged from source",
            "web_png_dimensions": [rgba_web.shape[2], rgba_web.shape[1]],
            "web_png_resampling": "nearest-neighbour display enlargement only",
            "display_symbology": {
                str(key): "#%02x%02x%02x" % value for key, value in COLORS.items()
            },
        },
        "statistics": stats,
        "interpretation": interpretation,
        "limitations": [
            "Static structural-danger product, version 2024; not the daily danger map.",
            "No value in an urban pixel does not mean zero wildfire risk.",
            "The source warns about omissions related to recent fires and 2018 land cover.",
            "The 1-10 scale is relative and must not be converted to probabilities.",
            "IncendisCat and active-incident feeds are not used.",
        ],
    }
    METADATA_JSON.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    INDICATOR_JSON.write_text(
        json.dumps(
            {
                "indicator": "structural_wildfire_danger_2024",
                "status": "verified",
                "source": SOURCE,
                "study_area": metadata["expanded_operational_scope"],
                "statistics": stats,
                "interpretation": interpretation,
                "limitations": metadata["limitations"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    update_manifests(metadata, processed_at)

    print(PROCESSED_TIF)
    print(MAP_PNG)
    print(METADATA_JSON)
    print(json.dumps(stats, ensure_ascii=False))


def update_manifests(metadata: dict, generated_at: str) -> None:
    project_manifest = json.loads(PROJECT_MANIFEST.read_text())
    study_area = project_manifest.setdefault("study_area", {})
    study_area["expanded_urban_bbox_epsg4326"] = list(EXPANDED_BBOX_4326)
    study_area["expanded_urban_area_ha"] = metadata["expanded_operational_scope"]["area_ha"]
    study_area["expanded_urban_scope_note"] = metadata["expanded_operational_scope"]["limitation"]
    project_manifest.setdefault("product_outputs", {})["fire_danger_metadata"] = (
        "metadata/fire_danger_structural_2024.json"
    )
    PROJECT_MANIFEST.write_text(
        json.dumps(project_manifest, ensure_ascii=False, indent=2) + "\n"
    )

    layer_manifest = json.loads(LAYER_MANIFEST.read_text())
    layer_manifest["generated_at_utc"] = generated_at
    layer_manifest["expanded_study_bbox_epsg4326"] = list(EXPANDED_BBOX_4326)
    included = layer_manifest.setdefault("layers_included", [])
    if "perill_estructural_incendi_2024" not in included:
        included.append("perill_estructural_incendi_2024")
    omitted = layer_manifest.setdefault("layers_omitted", [])
    omitted[:] = [item for item in omitted if item != "incendis"]
    if "incendis_operatius_incendiscat" not in omitted:
        omitted.append("incendis_operatius_incendiscat")
    layer_manifest["fire_danger"] = {
        "source": SOURCE["name"],
        "organization": SOURCE["organization"],
        "reference_date": SOURCE["reference_date"],
        "resolution_m": 100,
        "bbox_epsg4326": metadata["processed_layer"]["bbox_epsg4326"],
        "expanded_scope_bbox_epsg4326": list(EXPANDED_BBOX_4326),
        "expanded_scope_area_ha": metadata["expanded_operational_scope"]["area_ha"],
        "statistics": metadata["statistics"],
        "license": SOURCE["license"],
        "status": "verified",
        "interpretation": metadata["interpretation"],
        "metadata": "metadata/fire_danger_structural_2024.json",
    }
    LAYER_MANIFEST.write_text(
        json.dumps(layer_manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
