from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"


def read(relative: str) -> dict:
    return json.loads((PROJECT / relative).read_text(encoding="utf-8"))


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Phase1CoherenceTests(unittest.TestCase):
    def test_one_snapshot_id_is_used_by_every_public_product(self):
        registry = read("metadata/reading_registry.json")
        snapshot_id = registry["snapshot_id"]
        self.assertRegex(snapshot_id, r"^alinya-[0-9a-f]{16}$")
        for relative in (
            "indicators/daily_readings.json",
            "indicators/daily_history.json",
            "indicators/current_fire_danger.json",
            "indicators/ecoradar_core_indicators.json",
            "metadata/indicators_completeness_report.json",
        ):
            self.assertEqual(read(relative).get("snapshot_id"), snapshot_id, relative)

    def test_registry_has_provenance_contract_for_all_current_readings(self):
        registry = read("metadata/reading_registry.json")
        required = set(read("indicators/daily_readings.json")["readings"]) | {
            "climate_refuges", "habitats", "biodiversity", "connectivity",
            "access", "publicUse", "water", "historical_fires",
        }
        self.assertFalse(required - set(registry["readings"]))
        for key in required:
            item = registry["readings"][key]
            for field in ("source", "temporal_kind", "spatial_support", "qa", "validity", "compatibility"):
                self.assertIn(field, item, f"{key}.{field}")

    def test_landsat_composite_is_not_a_single_observation(self):
        selection = read("metadata/current_surface_temperature.json")["selected"]
        self.assertEqual(selection["temporal_kind"], "multitemporal_composite")
        self.assertIsNone(selection["acquired_at_utc"])
        self.assertEqual(selection["component_scene_count"], 26)
        self.assertLess(selection["period_start_utc"], selection["period_end_utc"])
        daily = read("indicators/daily_readings.json")["readings"]["surface_temperature"]
        self.assertEqual(daily["status_code"], "period_context")
        self.assertIsNone(daily["data_at_utc"])

    def test_core03_uses_the_visible_sentinel_reading_without_synthetic_score(self):
        core = {item["code"]: item for item in read("indicators/ecoradar_core_indicators.json")["indicators"]}["CORE_03"]
        sentinel = read("indicators/teledeteccio_sentinel2.json")
        self.assertEqual(core["measurement_kind"], "direct_reading")
        self.assertIsNone(core["value_0_100"])
        self.assertEqual(core["direct_value"], round(sentinel["metrics"]["ndvi"]["median"], 3))
        self.assertEqual(core["source_date_utc"], sentinel["acquired_at_utc"])
        self.assertEqual(core["sources_used"], ["copernicus_sentinel_ndvi"])

    def test_fire_area_denominator_and_product_confidence_are_explicit(self):
        summary = read("indicators/current_fire_danger.json")["summary"]
        self.assertAlmostEqual(summary["valid_area_ha"] + summary["no_data_area_ha"], summary["study_area_ha"], places=1)
        self.assertAlmostEqual(summary["valid_coverage_pct"], 100 * summary["valid_area_ha"] / summary["study_area_ha"], places=1)
        self.assertEqual(summary["coverage_denominator"], "entire study-area polygon")
        history = read("indicators/daily_history.json")
        self.assertNotIn("confidence", history["analytics"]["current_fire_danger"])
        self.assertIn("series_quality", history["analytics"]["current_fire_danger"])

    def test_climate_refuge_denominator_and_context_roles_are_explicit(self):
        refuges = read("indicators/refugis_climatics_potencials.json")
        self.assertEqual([item["weight"] for item in refuges["method"]["formula_inputs"]], [0.50, 0.30, 0.20])
        self.assertIn("ACA drainage and river geometries", refuges["method"]["cartographic_context_only"])
        self.assertEqual(refuges["denominator"]["name"], "vegetated pixels with valid LST, NDMI and NDVI")

    def test_gbif_pagination_continues_until_end_of_records(self):
        module = load_module("test_connector_biodiversitat", "ecoradar/connectors/connector_biodiversitat.py")

        class FakeArea:
            total_bounds = np.array([1.0, 42.0, 1.5, 42.5])
            def to_crs(self, _crs):
                return self

        def response(url: str):
            from urllib.parse import parse_qs, urlsplit
            offset = int(parse_qs(urlsplit(url).query)["offset"][0])
            size = 300 if offset == 0 else 200
            return {"count": 500, "results": [{"key": offset + index} for index in range(size)], "endOfRecords": offset > 0}

        with patch.object(module, "_get_json", side_effect=response):
            records, metadata = module._fetch_gbif(FakeArea(), 1_000)
        self.assertEqual(len(records), 500)
        self.assertEqual(metadata["page_count"], 2)
        self.assertTrue(metadata["end_of_records"])
        self.assertFalse(metadata["download_limit_reached"])

    def test_live_gbif_run_records_pages_total_and_any_safety_ceiling(self):
        metadata = read("metadata/biodiversitat_metadata.json")
        pagination = metadata["gbif_pagination"]
        self.assertGreater(pagination["page_count"], 1)
        self.assertEqual(pagination["downloaded_records"], metadata["records_downloaded"]["GBIF"])
        self.assertEqual(
            pagination["download_limit_reached"],
            pagination["total_matches"] > pagination["downloaded_records"],
        )

    def test_habitat_point_layer_is_traced_but_excluded_from_area_formula(self):
        metadata = read("metadata/habitats_metadata.json")
        self.assertEqual(metadata["point_layer"], "HABITATS:HABITATS_TERRESTPNT")
        self.assertGreater(metadata["point_features_clipped"], 0)
        self.assertIn("habitats_punts", metadata["processed_layers"])
        self.assertTrue(any("do not enter" in text for text in metadata["limitations"]))

    def test_public_sentinel_catalog_does_not_select_without_aoi_scl_qa(self):
        catalog = read("metadata/sentinel2_cdse_catalog_check.json")
        self.assertEqual(catalog["connector_status"], "requires_credentials")
        self.assertEqual(
            set(catalog["missing_requirements"]),
            {"COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"},
        )
        self.assertGreater(catalog["candidate_count"], 0)
        self.assertTrue(all(item["actual_aoi_scl_coverage_pct"] is None for item in catalog["candidates"]))

    def test_phase1_type_floor_is_after_the_original_small_type_rules(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        marker = html.index("Phase 1 legibility floor")
        self.assertGreater(marker, html.rfind("font-size:7px", 0, marker))
        floor = html[marker:marker + 7000]
        for size in ("font-size:11px!important", "font-size:12px!important", "font-size:13px!important"):
            self.assertIn(size, floor)


if __name__ == "__main__":
    unittest.main()
