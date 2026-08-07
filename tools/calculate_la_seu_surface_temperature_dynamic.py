"""Update LST and surface heat-island outputs from the selected detailed source."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds

from calculate_la_seu_expanded_indicators import (
    _read,
    _reproject,
    _stats,
    _to_web_grid,
    _write_tif,
)
from calculate_la_seu_extended_urban_indicators import _rgba_continuous, _write_png


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
CLMS = PROJECT / "processed" / "copernicus_hrl_expanded"
INDICATOR = PROJECT / "indicators" / "expanded_scope_indicators.json"
METADATA = PROJECT / "metadata" / "expanded_scope_layers.json"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
SELECTED_METADATA = PROJECT / "metadata" / "current_surface_temperature.json"
DERIVED = PROJECT / "processed" / "expanded_scope_indicators"
MAPS = PROJECT / "maps"


def calculate() -> dict:
    payload = json.loads(INDICATOR.read_text(encoding="utf-8"))
    project = json.loads(PROJECT_MANIFEST.read_text(encoding="utf-8"))
    selection = json.loads(SELECTED_METADATA.read_text(encoding="utf-8"))
    selected = selection["selected"]
    bbox = tuple(
        float(value)
        for value in project["study_area"]["expanded_urban_bbox_epsg4326"]
    )
    source = np.load(ROOT / selected["normalized_npz"])
    lst = source["lst_c"].astype("float32")
    lst_valid = source["valid"].astype(bool) & np.isfinite(lst)
    lst_bounds = [float(value) for value in source["bounds"]]
    lst_crs = str(source["crs"].item())
    lst_transform = from_bounds(*lst_bounds, lst.shape[1], lst.shape[0])
    lst_profile = {"transform": lst_transform, "crs": lst_crs}

    imd, clms_profile = _read(CLMS / "imperviousness_2021.tif")
    tcd23, _ = _read(CLMS / "tree_cover_density_2023.tif")
    herb23, _ = _read(CLMS / "herbaceous_cover_2023.tif")
    clms_valid = (imd <= 100) & (tcd23 <= 100) & (herb23 <= 1)
    vegetation = ((tcd23 > 0) | (herb23 == 1)) & clms_valid
    imd_on_lst = _reproject(
        np.where(clms_valid, imd.astype("float32"), np.nan),
        clms_profile,
        lst.shape,
        lst_transform,
        lst_crs,
        resampling=Resampling.average,
    )
    vegetation_on_lst = _reproject(
        vegetation.astype("float32"),
        clms_profile,
        lst.shape,
        lst_transform,
        lst_crs,
        resampling=Resampling.average,
    )
    urban = lst_valid & np.isfinite(imd_on_lst) & (imd_on_lst >= 50)
    reference = (
        lst_valid
        & np.isfinite(imd_on_lst)
        & np.isfinite(vegetation_on_lst)
        & (imd_on_lst <= 10)
        & (vegetation_on_lst >= 0.5)
    )
    if urban.sum() < 20:
        urban = lst_valid & np.isfinite(imd_on_lst) & (imd_on_lst >= 30)
    if reference.sum() < 20:
        reference = (
            lst_valid
            & np.isfinite(imd_on_lst)
            & np.isfinite(vegetation_on_lst)
            & (imd_on_lst <= 20)
            & (vegetation_on_lst >= 0.25)
        )
    if urban.sum() < 10 or reference.sum() < 10:
        raise RuntimeError(
            "Insufficient valid pixels for the selected-source surface heat-island screening."
        )
    urban_median = float(np.median(lst[urban]))
    reference_median = float(np.median(lst[reference]))
    suhi = np.where(lst_valid, lst - reference_median, np.nan)

    _write_tif(
        DERIVED / "surface_uhi_anomaly_current.tif",
        suhi,
        {
            "height": lst.shape[0],
            "width": lst.shape[1],
            "transform": lst_transform,
            "crs": lst_crs,
        },
    )
    _write_png(
        MAPS / "expanded_surface_temperature.png",
        _rgba_continuous(
            lst,
            [34, 39, 44, 49, 54, 59],
            [
                (42, 127, 96),
                (166, 199, 84),
                (250, 204, 70),
                (244, 141, 40),
                (214, 65, 39),
                (126, 24, 54),
            ],
            valid=lst_valid,
            alpha=220,
        ),
    )
    _write_png(
        MAPS / "expanded_surface_uhi_proxy_current.png",
        _rgba_continuous(
            suhi,
            [-10, -4, 0, 4, 10],
            [
                (44, 107, 150),
                (116, 176, 187),
                (239, 237, 219),
                (229, 142, 72),
                (165, 43, 45),
            ],
            valid=lst_valid,
            alpha=220,
        ),
    )
    target_resolution = int(selected.get("resolution_m") or 70)
    lst_web, lst_web_valid = _to_web_grid(
        lst,
        lst_valid,
        lst_profile,
        bbox,
        target_resolution,
        resampling=Resampling.bilinear,
    )
    suhi_web, suhi_web_valid = _to_web_grid(
        suhi,
        lst_valid,
        lst_profile,
        bbox,
        target_resolution,
        resampling=Resampling.bilinear,
    )
    _write_png(
        MAPS / "expanded_surface_temperature_web.png",
        _rgba_continuous(
            lst_web,
            [34, 39, 44, 49, 54, 59],
            [
                (42, 127, 96),
                (166, 199, 84),
                (250, 204, 70),
                (244, 141, 40),
                (214, 65, 39),
                (126, 24, 54),
            ],
            valid=lst_web_valid,
            alpha=220,
        ),
    )
    _write_png(
        MAPS / "expanded_surface_uhi_proxy_current_web.png",
        _rgba_continuous(
            suhi_web,
            [-10, -4, 0, 4, 10],
            [
                (44, 107, 150),
                (116, 176, 187),
                (239, 237, 219),
                (229, 142, 72),
                (165, 43, 45),
            ],
            valid=suhi_web_valid,
            alpha=220,
        ),
    )

    payload["dynamic_surface_temperature_updated_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()
    payload["metrics"]["land_surface_temperature_c"] = _stats(lst, lst_valid)
    payload["metrics"]["surface_uhi_proxy_c"] = round(
        urban_median - reference_median, 1
    )
    payload["metrics"]["surface_uhi_urban_median_c"] = round(urban_median, 1)
    payload["metrics"]["surface_uhi_reference_median_c"] = round(
        reference_median, 1
    )
    payload["metrics"]["surface_uhi_urban_pixels"] = int(urban.sum())
    payload["metrics"]["surface_uhi_reference_pixels"] = int(reference.sum())
    payload["methods"][
        "surface_uhi_proxy"
    ] = "Latest selected QA-valid detailed LST combined with unchanged CLMS structural masks."
    payload.setdefault("dynamic_source_dates", {})[
        "surface_temperature"
    ] = selected["acquired_at_utc"]
    payload["surface_temperature_source"] = {
        "source_key": selected["source_key"],
        "source": selected["source"],
        "organization": selected["organization"],
        "acquired_at_utc": selected["acquired_at_utc"],
        "resolution_m": selected["resolution_m"],
        "quality": selected["quality"],
    }
    INDICATOR.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    METADATA.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    payload = calculate()
    print(
        json.dumps(
            {
                "source": payload["surface_temperature_source"],
                "lst": payload["metrics"]["land_surface_temperature_c"],
                "surface_uhi_proxy_c": payload["metrics"][
                    "surface_uhi_proxy_c"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
