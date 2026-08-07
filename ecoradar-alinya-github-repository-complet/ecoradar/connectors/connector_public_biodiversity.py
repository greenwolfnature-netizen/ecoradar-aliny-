"""Download and normalize public GBIF and iNaturalist records for one bbox.

The connector has one responsibility: query each official public endpoint,
normalize the returned records, and return DataFrames. It performs no
ecological analysis and does not scrape third-party portals.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


GBIF_URL = "https://api.gbif.org/v1/occurrence/search"
INATURALIST_URL = "https://api.inaturalist.org/v1/observations"
USER_AGENT = "EcoRadar/1.0 (+https://github.com/greenwolfnature-netizen/ecoradar-seu)"


@dataclass(frozen=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def validate(self) -> None:
        if not (-180 <= self.west < self.east <= 180):
            raise ValueError("Invalid longitude bounds")
        if not (-90 <= self.south < self.north <= 90):
            raise ValueError("Invalid latitude bounds")


def _get_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={"accept": "application/json", "user-agent": USER_AGENT},
    )
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_gbif_bbox(
    bbox: BoundingBox,
    *,
    max_records: int = 10_000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return normalized GBIF records and query metadata for a bbox."""

    bbox.validate()
    rows: list[dict[str, Any]] = []
    total_matches: int | None = None
    offset = 0
    while len(rows) < max_records:
        params = {
            "decimalLongitude": f"{bbox.west},{bbox.east}",
            "decimalLatitude": f"{bbox.south},{bbox.north}",
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",
            "limit": min(300, max_records - len(rows)),
            "offset": offset,
        }
        payload = _get_json(f"{GBIF_URL}?{urlencode(params)}")
        if total_matches is None:
            total_matches = int(payload.get("count", 0))
        page = payload.get("results") or []
        for record in page:
            rows.append(
                {
                    "source": "GBIF",
                    "record_id": str(record.get("key") or ""),
                    "scientific_name": record.get("scientificName") or "",
                    "canonical_name": (
                        record.get("species")
                        or record.get("canonicalName")
                        or record.get("scientificName")
                        or ""
                    ),
                    "taxon_id": str(
                        record.get("acceptedTaxonKey")
                        or record.get("speciesKey")
                        or record.get("taxonKey")
                        or ""
                    ),
                    "taxon_rank": record.get("taxonRank") or "",
                    "kingdom": record.get("kingdom") or "",
                    "taxon_group": (
                        record.get("class")
                        or record.get("order")
                        or record.get("phylum")
                        or ""
                    ),
                    "common_name": record.get("vernacularName") or "",
                    "observed_on": record.get("eventDate") or record.get("year"),
                    "latitude": record.get("decimalLatitude"),
                    "longitude": record.get("decimalLongitude"),
                    "quality": "issues:" + ",".join(record.get("issues") or [])
                    if record.get("issues")
                    else "no_geospatial_issue",
                    "basis": record.get("basisOfRecord") or "",
                    "license": record.get("license") or "",
                    "record_url": (
                        f"https://www.gbif.org/occurrence/{record.get('key')}"
                        if record.get("key") is not None
                        else ""
                    ),
                    "dataset_key": record.get("datasetKey") or "",
                    "dataset_title": record.get("datasetTitle") or "",
                }
            )
        if payload.get("endOfRecords") or not page:
            break
        offset += len(page)
    frame = pd.DataFrame.from_records(rows)
    return frame, {
        "endpoint": GBIF_URL,
        "total_matches": total_matches or 0,
        "downloaded_records": len(frame),
        "download_limit_reached": (total_matches or 0) > len(frame),
    }


def fetch_gbif_count_bbox(
    bbox: BoundingBox,
    *,
    kingdom_key: int | None = None,
) -> dict[str, Any]:
    """Return an official GBIF occurrence count for one bbox and optional kingdom."""

    bbox.validate()
    params: dict[str, Any] = {
        "decimalLongitude": f"{bbox.west},{bbox.east}",
        "decimalLatitude": f"{bbox.south},{bbox.north}",
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
        "limit": 0,
    }
    if kingdom_key is not None:
        params["kingdomKey"] = int(kingdom_key)
    payload = _get_json(f"{GBIF_URL}?{urlencode(params)}")
    return {
        "endpoint": GBIF_URL,
        "total_matches": int(payload.get("count", 0)),
        "filters": {
            "kingdom_key": int(kingdom_key) if kingdom_key is not None else None,
        },
    }


def fetch_inaturalist_bbox(
    bbox: BoundingBox,
    *,
    max_records: int = 10_000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return normalized public iNaturalist observations and query metadata."""

    bbox.validate()
    rows: list[dict[str, Any]] = []
    total_matches: int | None = None
    page_number = 1
    while len(rows) < max_records:
        params = {
            "swlng": bbox.west,
            "swlat": bbox.south,
            "nelng": bbox.east,
            "nelat": bbox.north,
            "geo": "true",
            "per_page": min(200, max_records - len(rows)),
            "page": page_number,
            "order_by": "observed_on",
            "order": "desc",
        }
        payload = _get_json(f"{INATURALIST_URL}?{urlencode(params)}")
        if total_matches is None:
            total_matches = int(payload.get("total_results", 0))
        page = payload.get("results") or []
        for record in page:
            taxon = record.get("taxon") or {}
            ancestor_ids = taxon.get("ancestor_ids") or []
            geojson = record.get("geojson") or {}
            coordinates = geojson.get("coordinates") or [None, None]
            rows.append(
                {
                    "source": "iNaturalist",
                    "record_id": str(record.get("id") or record.get("uuid") or ""),
                    "scientific_name": taxon.get("name") or "",
                    "canonical_name": taxon.get("name") or "",
                    "taxon_id": str(taxon.get("id") or ""),
                    "taxon_rank": taxon.get("rank") or "",
                    "kingdom": (
                        "Animalia"
                        if taxon.get("id") == 1 or 1 in ancestor_ids
                        else ""
                    ),
                    "taxon_group": taxon.get("iconic_taxon_name") or "",
                    "common_name": taxon.get("preferred_common_name") or "",
                    "observed_on": record.get("observed_on")
                    or record.get("time_observed_at"),
                    "latitude": coordinates[1] if len(coordinates) > 1 else None,
                    "longitude": coordinates[0] if coordinates else None,
                    "quality": record.get("quality_grade") or "",
                    "basis": "HUMAN_OBSERVATION",
                    "license": record.get("license_code") or "",
                    "record_url": record.get("uri") or "",
                    "dataset_key": "",
                    "dataset_title": "iNaturalist",
                }
            )
        if not page or len(rows) >= (total_matches or 0):
            break
        page_number += 1
    frame = pd.DataFrame.from_records(rows)
    return frame, {
        "endpoint": INATURALIST_URL,
        "total_matches": total_matches or 0,
        "downloaded_records": len(frame),
        "download_limit_reached": (total_matches or 0) > len(frame),
    }


def fetch_inaturalist_count_bbox(
    bbox: BoundingBox,
    *,
    taxon_id: int | None = None,
) -> dict[str, Any]:
    """Return an official iNaturalist observation count for one bbox and taxon."""

    bbox.validate()
    params: dict[str, Any] = {
        "swlng": bbox.west,
        "swlat": bbox.south,
        "nelng": bbox.east,
        "nelat": bbox.north,
        "geo": "true",
        "per_page": 1,
    }
    if taxon_id is not None:
        params["taxon_id"] = int(taxon_id)
    payload = _get_json(f"{INATURALIST_URL}?{urlencode(params)}")
    return {
        "endpoint": INATURALIST_URL,
        "total_matches": int(payload.get("total_results", 0)),
        "filters": {
            "taxon_id": int(taxon_id) if taxon_id is not None else None,
        },
    }
