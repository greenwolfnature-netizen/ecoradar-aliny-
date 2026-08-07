"""Fetch and normalize NASA ECOSTRESS L2T V3 LST for the expanded La Seu scope.

Discovery uses the public NASA CMR Search API. Data downloads use the protected
LP DAAC Cloud Optimized GeoTIFF links and therefore require an Earthdata Login
user token in ``EARTHDATA_TOKEN``. This connector only discovers, downloads,
quality-masks and normalizes the official source; it does not calculate an
EcoRadar indicator.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.transform import from_bounds
from rasterio.windows import from_bounds as window_from_bounds


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
PROJECT_MANIFEST = PROJECT / "metadata" / "project_manifest.json"
OUTPUT_DIR = PROJECT / "processed" / "ecostress_expanded"
OUTPUT_TIF = OUTPUT_DIR / "ecostress_lst_expanded.tif"
OUTPUT_NPZ = OUTPUT_DIR / "ecostress_lst_expanded.npz"
METADATA = PROJECT / "metadata" / "ecostress_expanded_connector.json"

CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"
COLLECTION_SHORT_NAME = "ECO_L2T_LSTE"
COLLECTION_VERSION = "003"
COLLECTION_DOI = "https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.003"
CLIENT_ID = "EcoRadar"


def _utc_now() -> datetime:
    configured = os.environ.get("ECORADAR_CHECKED_AT_UTC")
    if configured:
        parsed = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _json_request(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/json", "Client-Id": CLIENT_ID},
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def _query_granules(
    bbox: tuple[float, ...],
    *,
    lookback_days: int = 120,
    limit: int = 100,
) -> tuple[list[dict], str]:
    end = _utc_now()
    start = end - timedelta(days=lookback_days)
    parameters = {
        "short_name": COLLECTION_SHORT_NAME,
        "version": COLLECTION_VERSION,
        "bounding_box": ",".join(str(value) for value in bbox),
        "temporal": f"{_iso(start)},{_iso(end)}",
        "page_size": limit,
        "sort_key": "-start_date",
    }
    url = f"{CMR_GRANULES}?{urlencode(parameters)}"
    entries = _json_request(url).get("feed", {}).get("entry", [])
    entries.sort(key=lambda item: item.get("time_start", ""), reverse=True)
    return entries, url


def _download_link(entry: dict, suffix: str) -> str:
    expected = f"_{suffix}.tif"
    for link in entry.get("links", []):
        href = str(link.get("href", ""))
        if (
            href.startswith("https://")
            and "/lp-prod-protected/" in href
            and href.endswith(expected)
        ):
            return href
    raise RuntimeError(
        f"CMR granule {entry.get('producer_granule_id')} has no protected {suffix} GeoTIFF link."
    )


def _download(url: str, destination: Path, token: str) -> None:
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "EcoRadar/1.0",
        },
    )
    with urlopen(request, timeout=300) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)


def _catalog_candidate(entry: dict) -> dict:
    return {
        "granule_id": entry.get("producer_granule_id"),
        "concept_id": entry.get("id"),
        "acquired_at_utc": entry.get("time_start"),
        "day_night_flag": entry.get("day_night_flag"),
        "updated_at_utc": entry.get("updated"),
        "bounds_epsg4326": entry.get("boxes", []),
    }


def _write_metadata(payload: dict) -> dict:
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    METADATA.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def _record_check(
    existing: dict,
    *,
    search_url: str,
    candidate: dict | None,
    status: str,
    note: str,
) -> dict:
    return _write_metadata(
        {
            **existing,
            "latest_catalog_check_utc": _iso(_utc_now()),
            "official_catalog_search_url": search_url,
            "latest_catalog_candidate": candidate,
            "connector_status": status,
            "status_note": note,
            "updated": False,
        }
    )


def _normalize_granule(
    entry: dict,
    bbox: tuple[float, ...],
    token: str,
) -> tuple[np.ndarray, np.ndarray, tuple[float, float, float, float], str]:
    with tempfile.TemporaryDirectory(prefix="ecoradar-ecostress-") as temporary:
        directory = Path(temporary)
        local: dict[str, Path] = {}
        for suffix in ("LST", "QC", "cloud", "water"):
            path = directory / f"{suffix}.tif"
            _download(_download_link(entry, suffix), path, token)
            local[suffix] = path

        with rasterio.open(local["LST"]) as source:
            transformer = Transformer.from_crs(4326, source.crs, always_xy=True)
            projected = [
                transformer.transform(x, y)
                for x in (bbox[0], bbox[2])
                for y in (bbox[1], bbox[3])
            ]
            bounds = (
                min(x for x, _ in projected),
                min(y for _, y in projected),
                max(x for x, _ in projected),
                max(y for _, y in projected),
            )
            window = (
                window_from_bounds(*bounds, source.transform)
                .round_offsets()
                .round_lengths()
            )
            lst_dn = source.read(1, window=window)
            source_bounds = rasterio.windows.bounds(window, source.transform)
            source_crs = str(source.crs)

        arrays = {}
        for suffix in ("QC", "cloud", "water"):
            with rasterio.open(local[suffix]) as source:
                arrays[suffix] = source.read(1, window=window)

    qc = arrays["QC"].astype("uint16")
    cloud = arrays["cloud"]
    water = arrays["water"]
    valid = (
        (lst_dn >= 7500)
        & ((qc & 0b11) == 0)
        & (cloud == 0)
        & (water == 0)
    )
    if int(valid.sum()) < 50:
        raise RuntimeError(
            f"Only {int(valid.sum())} ECOSTRESS pixels passed LST, mandatory-QA, cloud and water masks."
        )
    values_c = lst_dn.astype("float64") * 0.02 - 273.15
    return values_c, valid, source_bounds, source_crs


def fetch(*, bbox_override: tuple[float, ...] | None = None) -> dict:
    if bbox_override is None:
        manifest = json.loads(PROJECT_MANIFEST.read_text(encoding="utf-8"))
        bbox = tuple(
            float(value)
            for value in manifest["study_area"]["expanded_urban_bbox_epsg4326"]
        )
    else:
        bbox = tuple(float(value) for value in bbox_override)
    entries, search_url = _query_granules(bbox)
    existing = (
        json.loads(METADATA.read_text(encoding="utf-8"))
        if METADATA.exists()
        else {}
    )
    if not entries:
        return _record_check(
            existing,
            search_url=search_url,
            candidate=None,
            status="service_unavailable",
            note="NASA CMR did not return an ECOSTRESS L2T V3 granule for the study area and lookback period.",
        )

    latest_candidate = _catalog_candidate(entries[0])
    existing_time = str(existing.get("acquired_at_utc") or "")
    if (
        existing_time
        and str(entries[0].get("time_start") or "") <= existing_time
        and OUTPUT_TIF.exists()
        and OUTPUT_NPZ.exists()
    ):
        return _record_check(
            existing,
            search_url=search_url,
            candidate=latest_candidate,
            status="verified",
            note="The public NASA catalog was checked; the latest QA-valid local granule was already normalized.",
        )

    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not token:
        return _record_check(
            existing,
            search_url=search_url,
            candidate=latest_candidate,
            status="requires_credentials",
            note="A newer official catalog granule exists, but protected LP DAAC COG download requires EARTHDATA_TOKEN.",
        )

    failures: list[str] = []
    selected: tuple[dict, np.ndarray, np.ndarray, tuple[float, float, float, float], str] | None = None
    for entry in entries:
        acquired_at = str(entry.get("time_start") or "")
        if (
            existing_time
            and acquired_at <= existing_time
            and OUTPUT_TIF.exists()
            and OUTPUT_NPZ.exists()
        ):
            break
        try:
            values_c, valid, source_bounds, source_crs = _normalize_granule(
                entry, bbox, token
            )
        except (HTTPError, URLError) as error:
            if isinstance(error, HTTPError) and error.code in {401, 403}:
                return _record_check(
                    existing,
                    search_url=search_url,
                    candidate=latest_candidate,
                    status="requires_credentials",
                    note="EARTHDATA_TOKEN was rejected or lacks LP DAAC data-download authorization.",
                )
            failures.append(f"{entry.get('producer_granule_id')}: {error}")
            continue
        except Exception as error:
            failures.append(f"{entry.get('producer_granule_id')}: {error}")
            continue
        selected = (entry, values_c, valid, source_bounds, source_crs)
        break

    if selected is None:
        if existing and OUTPUT_TIF.exists() and OUTPUT_NPZ.exists():
            return _record_check(
                existing,
                search_url=search_url,
                candidate=latest_candidate,
                status="verified",
                note="No newer ECOSTRESS granule passed the local QA masks; the previous normalized granule is retained."
                + (f" Checked failures: {' | '.join(failures[:3])}" if failures else ""),
            )
        return _record_check(
            existing,
            search_url=search_url,
            candidate=latest_candidate,
            status="service_unavailable",
            note="No ECOSTRESS granule could be normalized with at least 50 valid local pixels."
            + (f" Checked failures: {' | '.join(failures[:3])}" if failures else ""),
        )

    entry, values_c, valid, source_bounds, source_crs = selected
    normalized = np.where(valid, values_c, -9999.0).astype("float32")
    transform = from_bounds(
        *source_bounds,
        normalized.shape[1],
        normalized.shape[0],
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        OUTPUT_TIF,
        "w",
        driver="GTiff",
        height=normalized.shape[0],
        width=normalized.shape[1],
        count=1,
        dtype="float32",
        crs=source_crs,
        transform=transform,
        nodata=-9999.0,
        compress="deflate",
    ) as target:
        target.write(normalized, 1)
    np.savez_compressed(
        OUTPUT_NPZ,
        lst_c=values_c.astype("float32"),
        valid=valid,
        bounds=np.asarray(source_bounds, dtype="float64"),
        crs=np.asarray(source_crs),
    )

    payload = {
        "generated_at_utc": _iso(_utc_now()),
        "latest_catalog_check_utc": _iso(_utc_now()),
        "connector": "nasa_ecostress_l2t_v3_expanded",
        "responsibility": "discover_download_quality_mask_and_normalize_only",
        "scope": "La Seu d'Urgell, Castellciutat and Sant Antoni",
        "study_bbox_epsg4326": bbox,
        "source": "NASA/JPL ECOSTRESS L2T Land Surface Temperature V3",
        "organization": "NASA/JPL ECOSTRESS; NASA LP DAAC",
        "collection": "ECO_L2T_LSTE.003",
        "collection_doi": COLLECTION_DOI,
        "granule_id": entry.get("producer_granule_id"),
        "concept_id": entry.get("id"),
        "acquired_at_utc": entry.get("time_start"),
        "day_night_flag": entry.get("day_night_flag"),
        "official_catalog_search_url": search_url,
        "latest_catalog_candidate": latest_candidate,
        "service_type": "NASA CMR Search plus Earthdata Login protected Cloud Optimized GeoTIFF",
        "license": "NASA Earthdata Data Use Policy; FreeAndOpenData true",
        "crs": source_crs,
        "resolution_m": 70,
        "variables": ["LST", "QC", "cloud_mask", "water_mask"],
        "normalization": "LST_C = LST_DN * 0.02 - 273.15; DN 7500-65535; QC bits 1-0 = 00; cloud=0; water=0",
        "valid_pixels": int(valid.sum()),
        "normalized_tif": str(OUTPUT_TIF.relative_to(ROOT)),
        "normalized_npz": str(OUTPUT_NPZ.relative_to(ROOT)),
        "sha256": hashlib.sha256(OUTPUT_TIF.read_bytes()).hexdigest(),
        "connector_status": "verified",
        "status_note": "Official ECOSTRESS granule downloaded and locally QA-masked.",
        "updated": True,
    }
    return _write_metadata(payload)


def main() -> None:
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
