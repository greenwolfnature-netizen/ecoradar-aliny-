"""Collect source-specific public biodiversity summaries for La Seu EcoRadar."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pandas as pd

from ecoradar.connectors.connector_public_biodiversity import (
    BoundingBox,
    fetch_gbif_bbox,
    fetch_gbif_count_bbox,
    fetch_inaturalist_bbox,
    fetch_inaturalist_count_bbox,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
SCOPE = PROJECT / "indicators" / "expanded_scope_indicators.json"
OUTPUT = PROJECT / "metadata" / "biodiversity_public_observations.json"

URBAN_FUNCTIONS = {
    "Aves": (
        "Pot contribuir al control d’invertebrats, a la dispersió de llavors "
        "i, segons la dieta, a retirar matèria orgànica. La funció concreta "
        "depèn de l’espècie i de l’ús real que faci de la ciutat."
    ),
    "Mammalia": (
        "Pot contribuir al control d’invertebrats, a la dispersió de llavors "
        "o al reciclatge de nutrients, segons la dieta i l’espècie."
    ),
    "Insecta": (
        "Pot contribuir a la pol·linització, la descomposició, el control "
        "biològic i l’alimentació d’altres animals, segons l’espècie."
    ),
    "Arachnida": (
        "Pot contribuir a regular altres artròpodes i forma part de la xarxa "
        "tròfica dels espais verds i edificats."
    ),
    "Reptilia": (
        "Pot contribuir a regular invertebrats i petits animals i forma part "
        "de la xarxa tròfica urbana."
    ),
    "Amphibia": (
        "Pot contribuir al consum d’invertebrats i connecta ecològicament els "
        "medis aquàtics i terrestres."
    ),
    "Actinopterygii": (
        "Forma part de les xarxes tròfiques i del funcionament ecològic dels "
        "cursos d’aigua urbans i periurbans."
    ),
    "Mollusca": (
        "Pot contribuir a la descomposició, al reciclatge de nutrients i a "
        "l’alimentació d’altres espècies."
    ),
    "Gastropoda": (
        "Pot contribuir a la descomposició, al reciclatge de nutrients i a "
        "l’alimentació d’altres espècies."
    ),
}
DEFAULT_URBAN_FUNCTION = (
    "La presència documentada forma part de la biodiversitat i de la xarxa "
    "tròfica urbana, però el grup taxonòmic disponible no permet atribuir-li "
    "un servei ecològic més concret sense una validació específica."
)
FUNCTION_LIMIT = (
    "És una funció ecològica urbana potencial atribuïda al grup taxonòmic. "
    "No és un benefici mesurat, una abundància ni una avaluació funcional "
    "específica d’aquesta espècie a la Seu d’Urgell."
)


def _iso_date_range(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    if frame.empty or "observed_on" not in frame:
        return None, None
    values = pd.to_datetime(frame["observed_on"], errors="coerce", utc=True).dropna()
    if values.empty:
        return None, None
    return values.min().date().isoformat(), values.max().date().isoformat()


def _summary(frame: pd.DataFrame, query: dict, *, record_label: str) -> dict:
    first_date, latest_date = _iso_date_range(frame)
    taxon_ids = frame["taxon_id"].fillna("").astype(str) if not frame.empty else pd.Series(dtype=str)
    taxon_names = (
        frame["scientific_name"].fillna("").astype(str)
        if not frame.empty
        else pd.Series(dtype=str)
    )
    unique_taxa = {
        value
        for value in taxon_ids
        if value and value.lower() not in {"nan", "none"}
    }
    if not unique_taxa:
        unique_taxa = {
            value.strip()
            for value in taxon_names
            if value and value.strip()
        }
    basis_counts = (
        Counter(frame["basis"].fillna("").astype(str))
        if not frame.empty and "basis" in frame
        else Counter()
    )
    return {
        "status": "verified",
        "information_type": record_label,
        "records_collected": int(len(frame)),
        "source_total_matches": int(query["total_matches"]),
        "unique_taxa_in_source": len(unique_taxa),
        "first_observation_date": first_date,
        "latest_observation_date": latest_date,
        "download_limit_reached": bool(query["download_limit_reached"]),
        "basis_counts": {
            key or "not_reported": int(value)
            for key, value in sorted(basis_counts.items())
        },
        "endpoint": query["endpoint"],
    }


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _species_catalog(gbif: pd.DataFrame, inaturalist: pd.DataFrame) -> dict:
    """Build a source-separated catalogue of observed Animalia species."""

    catalog: dict[str, dict] = {}
    for source_key, frame in (("gbif", gbif), ("inaturalist", inaturalist)):
        if frame.empty:
            continue
        for record in frame.to_dict("records"):
            if _clean_text(record.get("taxon_rank")).casefold() != "species":
                continue
            if _clean_text(record.get("kingdom")).casefold() != "animalia":
                continue
            name = (
                _clean_text(record.get("canonical_name"))
                or _clean_text(record.get("scientific_name"))
            )
            if not name:
                continue
            key = name.casefold()
            item = catalog.setdefault(
                key,
                {
                    "scientific_name": name,
                    "source_counts": {"gbif": 0, "inaturalist": 0},
                    "_groups": Counter(),
                    "_common_names": Counter(),
                    "_dates": [],
                    "_cells": {},
                },
            )
            item["source_counts"][source_key] += 1
            group = _clean_text(record.get("taxon_group"))
            if group:
                item["_groups"][group] += 1
            common_name = _clean_text(record.get("common_name"))
            if (
                common_name
                and common_name.casefold() != name.casefold()
                and "|" not in common_name
                and len(common_name) <= 80
            ):
                item["_common_names"][common_name] += 1
            observed_on = pd.to_datetime(
                record.get("observed_on"), errors="coerce", utc=True
            )
            if not pd.isna(observed_on):
                item["_dates"].append(observed_on)
            try:
                longitude = float(record.get("longitude"))
                latitude = float(record.get("latitude"))
            except (TypeError, ValueError):
                continue
            if not (
                math.isfinite(longitude)
                and math.isfinite(latitude)
                and -180 <= longitude <= 180
                and -90 <= latitude <= 90
            ):
                continue
            cell_key = (round(longitude, 3), round(latitude, 3))
            cell = item["_cells"].setdefault(
                cell_key,
                {
                    "longitude": cell_key[0],
                    "latitude": cell_key[1],
                    "source_counts": {"gbif": 0, "inaturalist": 0},
                    "_dates": [],
                },
            )
            cell["source_counts"][source_key] += 1
            if not pd.isna(observed_on):
                cell["_dates"].append(observed_on)

    items = []
    for item in catalog.values():
        if not item["_cells"]:
            continue
        group = item["_groups"].most_common(1)[0][0] if item["_groups"] else ""
        common_name = (
            item["_common_names"].most_common(1)[0][0]
            if item["_common_names"]
            else ""
        )
        latest_date = (
            max(item["_dates"]).date().isoformat() if item["_dates"] else None
        )
        source_counts = item["source_counts"]
        observation_cells = []
        for cell in item["_cells"].values():
            observation_cells.append(
                {
                    "longitude": cell["longitude"],
                    "latitude": cell["latitude"],
                    "source_counts": cell["source_counts"],
                    "latest_observation_date": (
                        max(cell["_dates"]).date().isoformat()
                        if cell["_dates"]
                        else None
                    ),
                }
            )
        observation_cells.sort(
            key=lambda cell: (cell["latitude"], cell["longitude"])
        )
        items.append(
            {
                "scientific_name": item["scientific_name"],
                "common_name": common_name,
                "common_name_note": (
                    "Nom comú aportat per la font; no s’ha traduït ni validat "
                    "com a nom oficial en català."
                    if common_name
                    else None
                ),
                "taxon_group": group or "grup no informat",
                "sources": [
                    source
                    for source in ("gbif", "inaturalist")
                    if source_counts[source] > 0
                ],
                "source_counts": source_counts,
                "latest_observation_date": latest_date,
                "map_cell_count": len(observation_cells),
                "observation_cells": observation_cells,
                "urban_function": URBAN_FUNCTIONS.get(
                    group, DEFAULT_URBAN_FUNCTION
                ),
                "interpretation_limit": FUNCTION_LIMIT,
            }
        )
    items.sort(key=lambda item: item["scientific_name"].casefold())
    return {
        "catalog_count": len(items),
        "selection_scope": (
            "Registres del regne Animalia identificats amb rang d’espècie i "
            "amb almenys una observació georeferenciada dins el rectangle "
            "operatiu. La coincidència entre fonts es fa pel nom científic "
            "canònic i els recomptes es mantenen separats."
        ),
        "cross_source_join": "exact canonical scientific name",
        "coordinates_published": False,
        "map_representation": (
            "Observation coordinates are aggregated to 0.001-degree cell "
            "centres (approximately 80 x 111 m at La Seu latitude)."
        ),
        "species_without_georeferenced_observations_included": False,
        "functional_interpretation": (
            "Context ecològic potencial assignat pel grup taxonòmic; no és una "
            "mesura del benefici aportat per cada espècie."
        ),
        "items": items,
    }


def collect() -> dict:
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    west, south, east, north = scope["study_bbox_epsg4326"]
    bbox = BoundingBox(west=west, south=south, east=east, north=north)
    gbif, gbif_query = fetch_gbif_bbox(bbox)
    inaturalist, inat_query = fetch_inaturalist_bbox(bbox)
    gbif_animalia = fetch_gbif_count_bbox(bbox, kingdom_key=1)
    inaturalist_animalia = fetch_inaturalist_count_bbox(bbox, taxon_id=1)
    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "schema_version": "1.0",
        "checked_at_utc": checked_at,
        "scope": "Operational rectangle of La Seu d'Urgell, Castellciutat and Sant Antoni",
        "study_bbox_epsg4326": [west, south, east, north],
        "scope_note": "The bbox is an operational study rectangle, not an administrative boundary.",
        "sources": {
            "gbif": {
                **_summary(gbif, gbif_query, record_label="public occurrence records"),
                "name": "GBIF Occurrence API",
                "organization": "Global Biodiversity Information Facility",
                "license": "Record-level licenses; GBIF and publishing-dataset attribution apply.",
            },
            "inaturalist": {
                **_summary(
                    inaturalist,
                    inat_query,
                    record_label="public observations",
                ),
                "name": "iNaturalist Observations API",
                "organization": "iNaturalist Network",
                "license": "Record-level licenses and iNaturalist API terms apply.",
            },
            "sacc": {
                "name": "Seguiment d'Amfibis Comuns de Catalunya (SACC)",
                "organization": "Societat Catalana d'Herpetologia",
                "status": "pending_verification",
                "information_type": "official monitoring program; local quantitative results not incorporated",
                "records_collected": None,
                "unique_taxa_in_source": None,
                "latest_observation_date": None,
                "official_url": "https://soccatherp.org/seguiment-damfibis-comuns-de-catalunya-sacc/",
                "data_portal_url": "https://observatorinatura.cat/projectes/info/42/",
                "monitoring_period": "2023-present",
                "useful_data_available_since": 2023,
                "update_frequency": "monitoring campaigns",
                "access_note": (
                    "No public SACC sampling point or quantitative result was verified "
                    "inside the EcoRadar La Seu scope. EcoRadar does not interpret the "
                    "missing local export as zero amphibian observations."
                ),
            },
        },
        "taxonomic_groups": {
            "animalia": {
                "scientific_name": "Animalia",
                "taxonomic_rank": "kingdom",
                "catalan_definition": (
                    "Regne taxonòmic que agrupa els animals. El recompte mostra "
                    "registres o observacions atribuïts a aquest regne dins l'àmbit, "
                    "no individus, abundància ni riquesa completa."
                ),
                "source_counts": {
                    "gbif": {
                        "records": int(gbif_animalia["total_matches"]),
                        "filter": "kingdomKey=1",
                        "endpoint": gbif_animalia["endpoint"],
                    },
                    "inaturalist": {
                        "records": int(inaturalist_animalia["total_matches"]),
                        "filter": "taxon_id=1",
                        "endpoint": inaturalist_animalia["endpoint"],
                    },
                },
                "cross_source_total": None,
                "interpretation": (
                    "Els dos totals es mantenen separats perquè una mateixa observació "
                    "pot aparèixer als dos portals."
                ),
            }
        },
        "species_catalog": _species_catalog(gbif, inaturalist),
        "interpretation": {
            "cross_source_deduplication": False,
            "totals_must_not_be_summed": (
                "The same biological event may be represented in more than one portal. "
                "Source totals are displayed separately and are not a unique inventory."
            ),
            "presence_limit": (
                "Public opportunistic records document submitted records, not abundance, "
                "complete richness, current occupancy, or demonstrated absence."
            ),
            "coordinate_publication": (
                "EcoRadar publishes derived 0.001-degree observation-cell centres, "
                "not exact record coordinates."
            ),
        },
        "provenance": {
            "inventory": "docs/data_sources/sources_inventory.yml",
            "technical_documentation": "docs/data_sources/la_seu_public_biodiversity.md",
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2, ensure_ascii=False))
