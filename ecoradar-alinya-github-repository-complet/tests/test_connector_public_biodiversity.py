from __future__ import annotations

from urllib.parse import parse_qs, urlparse
import unittest
from unittest.mock import patch

import pandas as pd

from ecoradar.connectors.connector_public_biodiversity import (
    BoundingBox,
    fetch_gbif_bbox,
    fetch_gbif_count_bbox,
    fetch_inaturalist_bbox,
    fetch_inaturalist_count_bbox,
)
from tools.collect_la_seu_public_biodiversity import _species_catalog


class PublicBiodiversityCountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bbox = BoundingBox(
            west=1.44,
            south=42.3445,
            east=1.479,
            north=42.3647,
        )

    @patch(
        "ecoradar.connectors.connector_public_biodiversity._get_json",
        return_value={"count": 5556},
    )
    def test_gbif_animalia_count_uses_kingdom_filter(self, get_json) -> None:
        result = fetch_gbif_count_bbox(self.bbox, kingdom_key=1)
        query = parse_qs(urlparse(get_json.call_args.args[0]).query)
        self.assertEqual(result["total_matches"], 5556)
        self.assertEqual(query["kingdomKey"], ["1"])
        self.assertEqual(query["limit"], ["0"])

    @patch(
        "ecoradar.connectors.connector_public_biodiversity._get_json",
        return_value={"total_results": 265},
    )
    def test_inaturalist_animalia_count_uses_taxon_filter(self, get_json) -> None:
        result = fetch_inaturalist_count_bbox(self.bbox, taxon_id=1)
        query = parse_qs(urlparse(get_json.call_args.args[0]).query)
        self.assertEqual(result["total_matches"], 265)
        self.assertEqual(query["taxon_id"], ["1"])
        self.assertEqual(query["geo"], ["true"])

    @patch(
        "ecoradar.connectors.connector_public_biodiversity._get_json",
        return_value={
            "count": 1,
            "endOfRecords": True,
            "results": [
                {
                    "key": 10,
                    "scientificName": "Pica pica",
                    "species": "Pica pica",
                    "speciesKey": 2482518,
                    "taxonRank": "SPECIES",
                    "kingdom": "Animalia",
                    "class": "Aves",
                    "vernacularName": "Eurasian Magpie",
                    "eventDate": "2026-07-20",
                    "decimalLatitude": 42.35,
                    "decimalLongitude": 1.46,
                }
            ],
        },
    )
    def test_gbif_species_fields_are_normalized(self, _get_json) -> None:
        frame, _query = fetch_gbif_bbox(self.bbox)
        record = frame.iloc[0]
        self.assertEqual(record["canonical_name"], "Pica pica")
        self.assertEqual(record["taxon_rank"], "SPECIES")
        self.assertEqual(record["kingdom"], "Animalia")
        self.assertEqual(record["taxon_group"], "Aves")
        self.assertEqual(record["common_name"], "Eurasian Magpie")

    @patch(
        "ecoradar.connectors.connector_public_biodiversity._get_json",
        return_value={
            "total_results": 1,
            "results": [
                {
                    "id": 20,
                    "observed_on": "2026-07-21",
                    "quality_grade": "research",
                    "geojson": {"coordinates": [1.46, 42.35]},
                    "taxon": {
                        "id": 144087,
                        "name": "Pica pica",
                        "rank": "species",
                        "ancestor_ids": [1, 2, 3],
                        "iconic_taxon_name": "Aves",
                        "preferred_common_name": "Eurasian Magpie",
                    },
                }
            ],
        },
    )
    def test_inaturalist_species_fields_are_normalized(self, _get_json) -> None:
        frame, _query = fetch_inaturalist_bbox(self.bbox)
        record = frame.iloc[0]
        self.assertEqual(record["canonical_name"], "Pica pica")
        self.assertEqual(record["taxon_rank"], "species")
        self.assertEqual(record["kingdom"], "Animalia")
        self.assertEqual(record["taxon_group"], "Aves")
        self.assertEqual(record["common_name"], "Eurasian Magpie")

    def test_catalog_excludes_species_without_mappable_observations(self) -> None:
        gbif = pd.DataFrame(
            [
                {
                    "canonical_name": "Pica pica",
                    "scientific_name": "Pica pica",
                    "taxon_rank": "SPECIES",
                    "kingdom": "Animalia",
                    "taxon_group": "Aves",
                    "common_name": "",
                    "observed_on": "2026-07-20",
                    "longitude": 1.46124,
                    "latitude": 42.35124,
                },
                {
                    "canonical_name": "Species without point",
                    "scientific_name": "Species without point",
                    "taxon_rank": "SPECIES",
                    "kingdom": "Animalia",
                    "taxon_group": "Insecta",
                    "common_name": "",
                    "observed_on": "2026-07-20",
                    "longitude": None,
                    "latitude": None,
                },
            ]
        )
        inaturalist = pd.DataFrame(
            [
                {
                    "canonical_name": "Pica pica",
                    "scientific_name": "Pica pica",
                    "taxon_rank": "species",
                    "kingdom": "Animalia",
                    "taxon_group": "Aves",
                    "common_name": "",
                    "observed_on": "2026-07-21",
                    "longitude": 1.46125,
                    "latitude": 42.35125,
                }
            ]
        )
        catalog = _species_catalog(gbif, inaturalist)
        self.assertEqual(catalog["catalog_count"], 1)
        self.assertEqual(catalog["items"][0]["scientific_name"], "Pica pica")
        self.assertEqual(catalog["items"][0]["map_cell_count"], 1)
        self.assertEqual(
            catalog["items"][0]["observation_cells"][0]["source_counts"],
            {"gbif": 1, "inaturalist": 1},
        )


if __name__ == "__main__":
    unittest.main()
