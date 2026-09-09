from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
CONFIDENCE_KEYS = {
    "completesa", "vigencia", "cobertura", "resolucio", "qa", "representativitat", "biaix", "validacio"
}


def read(relative: str) -> dict:
    return json.loads((PROJECT / relative).read_text(encoding="utf-8"))


class AlinyaPhase2MethodologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = read("indicators/ecoradar_core_indicators.json")
        cls.by_code = {item["code"]: item for item in cls.payload["indicators"]}

    def test_phase2_replaces_the_common_core_scale(self):
        self.assertEqual(self.payload["methodology_version"], "alinya_core_v2_2026-09-09")
        self.assertEqual(set(self.by_code), {f"CORE_{index:02d}" for index in range(1, 13)})
        self.assertTrue(all(item["value_0_100"] is None for item in self.by_code.values()))
        self.assertTrue(all(item.get("primary_result") for item in self.by_code.values()))

    def test_every_radar_has_the_eight_dimension_confidence_vector(self):
        for code, item in self.by_code.items():
            self.assertEqual(set(item["confidence_dimensions"]), CONFIDENCE_KEYS, code)
            self.assertIn(item["confidence"], {"alta", "mitjana", "baixa"}, code)
            self.assertTrue(item["confidence_reason"], code)

    def test_core01_describes_configuration_without_rewarding_fragmentation(self):
        item = self.by_code["CORE_01"]
        configuration = item["profile"]["configuration"]
        self.assertGreater(configuration["patch_count"], 1)
        self.assertGreater(configuration["largest_patch_ha"], 0)
        self.assertEqual(item["measurement_kind"], "descriptive_profile")
        self.assertNotIn("mitjana aritmètica", item["calculation_explanation"].casefold())

    def test_core02_is_responsibility_and_never_conservation_status(self):
        item = self.by_code["CORE_02"]
        self.assertIn("Responsabilitat", item["name"])
        self.assertEqual(item["profile"]["conservation_status"], "NO AVALUABLE")
        self.assertFalse(item["profile"]["point_presences_enter_area_denominator"])
        self.assertGreater(item["profile"]["small_habitat_point_presences"], 0)

    def test_core03_preserves_direct_ndvi_and_date(self):
        item = self.by_code["CORE_03"]
        sentinel = read("indicators/teledeteccio_sentinel2.json")
        self.assertEqual(item["measurement_kind"], "direct_reading")
        self.assertEqual(item["direct_value"], round(sentinel["metrics"]["ndvi"]["median"], 3))
        self.assertEqual(item["source_date_utc"], sentinel["acquired_at_utc"])
        self.assertIn("NO AVALUABLE", item["profile"]["phenological_anomaly"])

    def test_core04_and_core05_do_not_mix_structure_with_vulnerability(self):
        refuge = self.by_code["CORE_04"]
        vulnerability = self.by_code["CORE_05"]
        self.assertEqual(refuge["measurement_kind"], "dual_profile")
        self.assertIn("structural_potential", refuge["profile"])
        self.assertIn("observed_satellite_signal", refuge["profile"])
        self.assertEqual(vulnerability["status"], "NO AVALUABLE")
        self.assertEqual(vulnerability["profile"]["sensitivity"]["status"], "NO AVALUABLE")
        self.assertEqual(vulnerability["profile"]["adaptive_capacity"]["status"], "NO AVALUABLE")

    def test_core06_is_knowledge_coverage_with_bias_and_pagination(self):
        item = self.by_code["CORE_06"]
        pagination = item["profile"]["gbif_pagination"]
        self.assertEqual(item["measurement_kind"], "knowledge_profile")
        self.assertTrue(pagination["download_limit_reached"])
        self.assertGreater(item["profile"]["knowledge_grid_1km"]["cells_without_records"], 0)
        self.assertEqual(item["confidence_dimensions"]["biaix"]["rating"], "insuficient")

    def test_core07_and_core10_are_direct_inventories(self):
        access = self.by_code["CORE_07"]
        water = self.by_code["CORE_10"]
        self.assertEqual(access["profile"]["ecological_pressure"], "NO AVALUABLE")
        self.assertEqual(water["profile"]["flow_permanence_quality_function"], "NO AVALUABLE")
        self.assertEqual(access["measurement_kind"], "direct_inventory")
        self.assertEqual(water["measurement_kind"], "direct_inventory")

    def test_core08_and_core09_separate_structural_and_functional_dimensions(self):
        connectivity = self.by_code["CORE_08"]
        fire = self.by_code["CORE_09"]
        self.assertEqual(connectivity["profile"]["functional_level"]["status"], "NO AVALUABLE")
        self.assertNotIn("osm_public_use", connectivity["sources_used"])
        self.assertEqual(set(fire["profile"]), {"propagation_current", "ecological_sensitivity", "postfire_recovery", "operational_context"})
        self.assertEqual(fire["profile"]["postfire_recovery"]["status"], "NO AVALUABLE")

    def test_core11_is_a_gate_and_core12_is_non_compensatory(self):
        restoration = self.by_code["CORE_11"]
        management = self.by_code["CORE_12"]
        self.assertEqual(restoration["status"], "NO AVALUABLE")
        self.assertFalse(restoration["profile"]["decision_gate"]["degradation_demonstrated"])
        self.assertEqual(management["measurement_kind"], "multicriteria_decision")
        self.assertIsNone(management["profile"]["global_score"])
        self.assertGreater(len(management["profile"]["rows"]), 0)
        self.assertEqual(management["profile"]["result"], "SENSE PRIORITAT ÚNICA")
        self.assertNotIn("mitjana aritmètica", management["calculation_explanation"].casefold())

    def test_diagnosis_and_recommendations_consume_the_phase2_contract(self):
        diagnosis = read("diagnosis/ecoradar_diagnosis.json")
        recommendations = read("recommendations/recommendations.json")
        priority = read("recommendations/priority_matrix.json")
        self.assertEqual(diagnosis["methodology_version"], "alinya_core_v2_2026-09-09")
        self.assertTrue(all(item.get("evidence_type") for item in diagnosis["conclusions"]))
        self.assertTrue(all(item.get("priority_class") for item in recommendations["recommendations"]))
        self.assertTrue(all("ecological_priority_score" not in item for item in recommendations["recommendations"]))
        self.assertEqual(priority["decision_method"]["type"], "non_compensatory_categories")

    def test_public_viewer_contains_phase2_results_and_no_core_score_bar(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("alinya_core_v2_2026-09-09", html)
        self.assertIn("SENSE PRIORITAT ÚNICA", html)
        self.assertNotIn("Puntuació sintètica EcoRadar · 0–100", html)
        self.assertNotIn("Mitjana aritmètica, amb el mateix pes", html)


if __name__ == "__main__":
    unittest.main()
