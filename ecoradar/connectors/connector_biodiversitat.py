"""GBIF and iNaturalist biodiversity connector for EcoRadar.

This connector reads the Alinya study area, queries public species records from
GBIF and iNaturalist, stores the raw API responses, normalizes common fields,
clips records to the study-area polygon and writes a simple source summary. It
does not make ecological assessments or assume current presence from old data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


PROJECT_ROOT = Path("projectes/Alinya")
STUDY_AREA_PATH = PROJECT_ROOT / "processed" / "study_area.gpkg"
RAW_DIR = PROJECT_ROOT / "raw" / "biodiversitat"
PROCESSED_PATH = PROJECT_ROOT / "processed" / "biodiversitat.gpkg"
SUMMARY_PATH = PROJECT_ROOT / "indicators" / "biodiversitat_resum.csv"
METADATA_PATH = PROJECT_ROOT / "metadata" / "biodiversitat_metadata.json"

TARGET_CRS = "EPSG:25831"
WGS84 = "EPSG:4326"
GBIF_URL = "https://api.gbif.org/v1/occurrence/search"
INAT_URL = "https://api.inaturalist.org/v1/observations"
USER_AGENT = "EcoRadar/0.1 biodiversity connector"
RECENT_YEAR_THRESHOLD = date.today().year - 10


@dataclass(frozen=True)
class QueryConfig:
    buffer_m: float
    max_records_per_source: int
    recent_year_threshold: int


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EcoRadar biodiversity connector")
    parser.add_argument("--buffer-m", type=float, default=0, help="Buffer around study area in metres")
    parser.add_argument("--max-records-per-source", type=int, default=1000, help="Maximum records per source")
    args = parser.parse_args()

    try:
        result = run_connector(
            QueryConfig(
                buffer_m=args.buffer_m,
                max_records_per_source=args.max_records_per_source,
                recent_year_threshold=RECENT_YEAR_THRESHOLD,
            )
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"connector_biodiversitat failed: {exc}", file=sys.stderr)
        raise


def run_connector(config: QueryConfig | None = None) -> dict[str, Any]:
    config = config or QueryConfig(buffer_m=0, max_records_per_source=1000, recent_year_threshold=RECENT_YEAR_THRESHOLD)
    _ensure_dirs()
    study_area = _load_study_area()
    query_area = _query_area(study_area, config.buffer_m)

    gbif_raw = _fetch_gbif(query_area, config.max_records_per_source)
    inat_raw = _fetch_inaturalist(query_area, config.max_records_per_source)
    _write_raw("gbif", gbif_raw)
    _write_raw("inaturalist", inat_raw)

    records = _normalize_gbif(gbif_raw, config.recent_year_threshold) + _normalize_inaturalist(
        inat_raw, config.recent_year_threshold
    )
    normalized = _records_to_geodataframe(records)
    clipped = _clip_records(normalized, query_area)
    clipped = _deduplicate(clipped)

    if PROCESSED_PATH.exists():
        PROCESSED_PATH.unlink()
    clipped.to_file(PROCESSED_PATH, layer="biodiversitat", driver="GPKG")

    summary_rows = _write_summary(clipped, config.recent_year_threshold)
    metadata = _write_metadata(study_area, query_area, config, gbif_raw, inat_raw, clipped)

    return {
        "processed_path": str(PROCESSED_PATH),
        "summary_path": str(SUMMARY_PATH),
        "metadata_path": str(METADATA_PATH),
        "raw_dir": str(RAW_DIR),
        "gbif_downloaded": len(gbif_raw),
        "inaturalist_downloaded": len(inat_raw),
        "normalized_records": int(len(clipped)),
        "summary_groups": len(summary_rows),
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


def _query_area(study_area: gpd.GeoDataFrame, buffer_m: float) -> gpd.GeoDataFrame:
    geometry = study_area.geometry.union_all()
    if buffer_m > 0:
        geometry = geometry.buffer(buffer_m)
    return gpd.GeoDataFrame({"name": ["Alinya"], "buffer_m": [buffer_m]}, geometry=[geometry], crs=TARGET_CRS)


def _fetch_gbif(query_area: gpd.GeoDataFrame, max_records: int) -> list[dict[str, Any]]:
    bounds = query_area.to_crs(WGS84).total_bounds
    records: list[dict[str, Any]] = []
    limit = min(300, max_records)
    offset = 0
    while len(records) < max_records:
        params = {
            "decimalLongitude": f"{bounds[0]},{bounds[2]}",
            "decimalLatitude": f"{bounds[1]},{bounds[3]}",
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",
            "limit": min(limit, max_records - len(records)),
            "offset": offset,
        }
        payload = _get_json(f"{GBIF_URL}?{urlencode(params)}")
        page = payload.get("results", [])
        records.extend(page)
        if payload.get("endOfRecords") or not page:
            break
        offset += len(page)
    return records


def _fetch_inaturalist(query_area: gpd.GeoDataFrame, max_records: int) -> list[dict[str, Any]]:
    bounds = query_area.to_crs(WGS84).total_bounds
    records: list[dict[str, Any]] = []
    per_page = min(200, max_records)
    page_number = 1
    while len(records) < max_records:
        params = {
            "swlng": bounds[0],
            "swlat": bounds[1],
            "nelng": bounds[2],
            "nelat": bounds[3],
            "geo": "true",
            "per_page": min(per_page, max_records - len(records)),
            "page": page_number,
            "order_by": "observed_on",
            "order": "desc",
        }
        payload = _get_json(f"{INAT_URL}?{urlencode(params)}")
        page = payload.get("results", [])
        records.extend(page)
        total = int(payload.get("total_results", 0))
        if not page or len(records) >= total:
            break
        page_number += 1
    return records


def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_raw(source: str, records: list[dict[str, Any]]) -> None:
    payload = {
        "source": source,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }
    (RAW_DIR / f"{source}_raw.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _normalize_gbif(records: list[dict[str, Any]], recent_year_threshold: int) -> list[dict[str, Any]]:
    normalized = []
    for record in records:
        lat = _to_float(record.get("decimalLatitude"))
        lon = _to_float(record.get("decimalLongitude"))
        if lat is None or lon is None:
            continue
        key = record.get("key")
        issues = record.get("issues") or []
        normalized.append(
            {
                "scientificName": _clean(record.get("scientificName")),
                "commonName": _clean(record.get("vernacularName")),
                "taxonGroup": _gbif_taxon_group(record),
                "eventDate": _clean(record.get("eventDate")),
                "latitude": lat,
                "longitude": lon,
                "source": "GBIF",
                "source_record_id": str(key) if key is not None else "",
                "recordUrl": f"https://www.gbif.org/occurrence/{key}" if key is not None else "",
                "identificationConfidence": _gbif_confidence(record, issues),
                "basisOfRecord": _clean(record.get("basisOfRecord")),
                "license": _clean(record.get("license")),
                "recordStatus": _record_status(record.get("eventDate"), recent_year_threshold),
                "isDoubtful": bool(issues),
                "doubtfulReason": ";".join(issues),
            }
        )
    return normalized


def _normalize_inaturalist(records: list[dict[str, Any]], recent_year_threshold: int) -> list[dict[str, Any]]:
    normalized = []
    for record in records:
        lat, lon = _inat_coordinates(record)
        if lat is None or lon is None:
            continue
        taxon = record.get("taxon") or {}
        quality_grade = _clean(record.get("quality_grade"))
        captive = bool(record.get("captive"))
        normalized.append(
            {
                "scientificName": _clean(taxon.get("name")),
                "commonName": _clean(taxon.get("preferred_common_name") or record.get("species_guess")),
                "taxonGroup": _clean(taxon.get("iconic_taxon_name")),
                "eventDate": _clean(record.get("observed_on") or record.get("time_observed_at")),
                "latitude": lat,
                "longitude": lon,
                "source": "iNaturalist",
                "source_record_id": str(record.get("id") or record.get("uuid") or ""),
                "recordUrl": _clean(record.get("uri")),
                "identificationConfidence": quality_grade,
                "basisOfRecord": "HUMAN_OBSERVATION",
                "license": _clean(record.get("license_code")),
                "recordStatus": _record_status(
                    record.get("observed_on") or record.get("time_observed_at"),
                    recent_year_threshold,
                ),
                "isDoubtful": quality_grade == "casual" or captive,
                "doubtfulReason": _inat_doubtful_reason(record),
            }
        )
    return normalized


def _records_to_geodataframe(records: list[dict[str, Any]]) -> gpd.GeoDataFrame:
    if not records:
        return gpd.GeoDataFrame(columns=_normalized_columns() + ["geometry"], geometry="geometry", crs=TARGET_CRS)
    frame = pd.DataFrame(records)
    geometry = [Point(lon, lat) for lon, lat in zip(frame["longitude"], frame["latitude"])]
    gdf = gpd.GeoDataFrame(frame, geometry=geometry, crs=WGS84)
    return gdf.to_crs(TARGET_CRS)


def _clip_records(records: gpd.GeoDataFrame, query_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if records.empty:
        return records
    area = query_area.geometry.union_all()
    return records[records.geometry.within(area)].copy()


def _deduplicate(records: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if records.empty:
        return records
    records = records.drop_duplicates(subset=["source", "source_record_id"]).copy()
    for column in _normalized_columns():
        if column not in records.columns:
            records[column] = ""
    return records[_normalized_columns() + ["geometry"]]


def _write_summary(records: gpd.GeoDataFrame, recent_year_threshold: int) -> list[dict[str, Any]]:
    rows = []
    if records.empty:
        grouped = []
    else:
        grouped = records.groupby("taxonGroup", dropna=False)
    for group, data in grouped:
        species = data["scientificName"].replace("", pd.NA).dropna().nunique()
        source_counts = data["source"].value_counts()
        records_recent = int((data["recordStatus"] == "recent").sum())
        records_historical = int((data["recordStatus"] == "historic").sum())
        rows.append(
            {
                "grup_taxonomic": _clean(group) or "Sense grup",
                "nombre_registres": int(len(data)),
                "nombre_especies": int(species),
                "registres_recents": records_recent,
                "registres_historics": records_historical,
                "font_principal": source_counts.index[0] if not source_counts.empty else "",
                "possibles_buits_informacio": _information_gap_note(data, recent_year_threshold),
            }
        )
    rows = sorted(rows, key=lambda row: (-row["nombre_registres"], row["grup_taxonomic"]))
    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "grup_taxonomic",
                "nombre_registres",
                "nombre_especies",
                "registres_recents",
                "registres_historics",
                "font_principal",
                "possibles_buits_informacio",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _write_metadata(
    study_area: gpd.GeoDataFrame,
    query_area: gpd.GeoDataFrame,
    config: QueryConfig,
    gbif_raw: list[dict[str, Any]],
    inat_raw: list[dict[str, Any]],
    clipped: gpd.GeoDataFrame,
) -> dict[str, Any]:
    metadata = {
        "project": "Alinya",
        "sources_consulted": [
            {"source": "GBIF Occurrence API", "url": GBIF_URL},
            {"source": "iNaturalist Observations API", "url": INAT_URL},
        ],
        "query_date": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "gbif": {"hasCoordinate": True, "hasGeospatialIssue": False, "bbox": "study area bounding box in WGS84"},
            "inaturalist": {"geo": True, "bbox": "study area bounding box in WGS84"},
            "local_clip": "records clipped to study area polygon after download",
            "recent_year_threshold": config.recent_year_threshold,
            "max_records_per_source": config.max_records_per_source,
        },
        "buffer_m": config.buffer_m,
        "study_area_surface_ha": float(study_area.geometry.union_all().area / 10000),
        "query_area_surface_ha": float(query_area.geometry.union_all().area / 10000),
        "records_downloaded": {"GBIF": len(gbif_raw), "iNaturalist": len(inat_raw)},
        "download_limit_reached": {
            "GBIF": len(gbif_raw) >= config.max_records_per_source,
            "iNaturalist": len(inat_raw) >= config.max_records_per_source,
        },
        "records_normalized_after_clip": int(len(clipped)),
        "crs": TARGET_CRS,
        "raw_files": {
            "GBIF": str(RAW_DIR / "gbif_raw.json"),
            "iNaturalist": str(RAW_DIR / "inaturalist_raw.json"),
        },
        "processed_file": str(PROCESSED_PATH),
        "summary_file": str(SUMMARY_PATH),
        "limitations": [
            "GBIF and iNaturalist records are opportunistic/public records and do not prove complete species absence or current presence.",
            "Old records are marked historic and should not be interpreted as current presence without field or recent supporting evidence.",
            "iNaturalist is queried by bounding box and then clipped locally to the study-area polygon.",
            "Coordinate uncertainty, obscured coordinates, taxonomic revisions and observer effort can affect record quality.",
            "No Ornitho or other non-authorized portal scraping is performed.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def _gbif_confidence(record: dict[str, Any], issues: list[str]) -> str:
    if issues:
        return "doubtful"
    if record.get("taxonomicStatus") == "ACCEPTED" or record.get("acceptedTaxonKey"):
        return "accepted"
    return "unclassified"


def _gbif_taxon_group(record: dict[str, Any]) -> str:
    kingdom = _clean(record.get("kingdom"))
    if kingdom in {"Plantae", "Fungi"}:
        return kingdom
    if kingdom and kingdom != "Animalia":
        return kingdom
    return _clean(record.get("class") or record.get("order") or kingdom)


def _record_status(value: object, recent_year_threshold: int) -> str:
    year = _extract_year(value)
    if year is None:
        return "undated"
    if year >= recent_year_threshold:
        return "recent"
    return "historic"


def _information_gap_note(data: pd.DataFrame, recent_year_threshold: int) -> str:
    if data.empty:
        return "sense registres"
    recent = int((data["recordStatus"] == "recent").sum())
    doubtful = int(data["isDoubtful"].sum())
    undated = int((data["recordStatus"] == "undated").sum())
    notes = []
    if recent == 0:
        notes.append(f"sense registres recents des de {recent_year_threshold}")
    if doubtful:
        notes.append(f"{doubtful} registres dubtosos")
    if undated:
        notes.append(f"{undated} registres sense data")
    return "; ".join(notes) if notes else "cap buit evident en les fonts consultades"


def _inat_coordinates(record: dict[str, Any]) -> tuple[float | None, float | None]:
    geojson = record.get("geojson") or {}
    coordinates = geojson.get("coordinates")
    if coordinates and len(coordinates) >= 2:
        return _to_float(coordinates[1]), _to_float(coordinates[0])
    location = _clean(record.get("location"))
    if "," in location:
        lat, lon = location.split(",", 1)
        return _to_float(lat), _to_float(lon)
    return None, None


def _inat_doubtful_reason(record: dict[str, Any]) -> str:
    reasons = []
    if record.get("quality_grade") == "casual":
        reasons.append("quality_grade=casual")
    if record.get("captive"):
        reasons.append("captive_or_cultivated")
    if record.get("obscured"):
        reasons.append("coordinates_obscured")
    return ";".join(reasons)


def _extract_year(value: object) -> int | None:
    text = _clean(value)
    if len(text) < 4:
        return None
    try:
        return int(text[:4])
    except ValueError:
        return None


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return str(value).strip()


def _normalized_columns() -> list[str]:
    return [
        "scientificName",
        "commonName",
        "taxonGroup",
        "eventDate",
        "latitude",
        "longitude",
        "source",
        "source_record_id",
        "recordUrl",
        "identificationConfidence",
        "basisOfRecord",
        "license",
        "recordStatus",
        "isDoubtful",
        "doubtfulReason",
    ]


if __name__ == "__main__":
    main()
