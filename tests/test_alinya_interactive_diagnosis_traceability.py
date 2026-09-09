from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "export_ecoradar_alinya_netlify.py"
GENERATED = (
    ROOT
    / "projectes"
    / "Alinya"
    / "maps"
    / "ecoradar-alinya-netlify-v2"
    / "index.html"
)
METHODOLOGY = ROOT / "docs" / "metodologia_oficial_ecoradar.md"
CORE = ROOT / "projectes" / "Alinya" / "indicators" / "ecoradar_core_indicators.json"


class InteractiveDiagnosisTraceabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.generated = GENERATED.read_text(encoding="utf-8")
        cls.methodology = METHODOLOGY.read_text(encoding="utf-8")
        cls.core = {
            item["code"]: item
            for item in json.loads(CORE.read_text(encoding="utf-8"))["indicators"]
        }

    def test_fire_executive_text_is_centered_and_mobile_safe(self):
        self.assertIn(".eu-fire-executive .eu-fact span", self.generated)
        self.assertIn("text-align:center; overflow-wrap:anywhere", self.generated)
        self.assertIn(".eu-fire-executive .eu-fact { grid-template-columns:1fr", self.generated)

    def test_chapter_six_uses_current_operational_evidence(self):
        self.assertIn("Situació operativa actualitzada", self.generated)
        self.assertIn("report-fire-chapter-variables", self.generated)
        self.assertIn("meteorologia XEMA", self.generated)
        self.assertNotIn(
            "Per convertir-lo en risc operatiu encara calen meteorologia diària",
            self.generated,
        )

    def test_all_daily_readings_have_a_decision_role(self):
        expected = {
            "air_temperature", "relative_humidity", "wind", "wind_gust",
            "precipitation", "precipitation_7d", "precipitation_30d",
            "days_without_significant_rain", "surface_temperature", "ndmi",
            "ndvi", "albedo", "terrain_shade", "air_quality",
            "thermal_comfort", "pla_alfa", "current_fire_danger",
        }
        order_match = re.search(r"const dailyReadingOrder = \[(.*?)\];", self.generated)
        self.assertIsNotNone(order_match)
        found = set(re.findall(r"'([^']+)'", order_match.group(1)))
        self.assertEqual(found, expected)
        for key in expected:
            self.assertRegex(self.source, rf"\n\s+{re.escape(key)}:")

    def test_all_radar_indicators_have_a_management_role(self):
        for number in range(1, 13):
            self.assertIn(f"CORE_{number:02d}", self.core)
        self.assertIn('id="eu-core-decision-evidence"', self.generated)

    def test_all_radar_cards_expose_the_five_explanation_blocks(self):
        for number in range(1, 13):
            item = self.core[f"CORE_{number:02d}"]
            self.assertTrue(item["guide"]["measure"])
            self.assertTrue(item["guide"]["basis"])
            self.assertTrue(item["guide"]["calculation"])
            self.assertTrue(item["guide"]["interpretation"])
            self.assertTrue(item["confidence_reason"])
        self.assertIn('id="eu-core-explainer"', self.generated)
        self.assertIn('aria-controls="eu-core-explainer"', self.generated)
        self.assertIn('data-core-code=', self.generated)
        for heading in (
            "1 · Què mesura",
            "2 · En què es basa",
            "3 · Com es calcula",
            "4 · Com interpretar el resultat",
            "5 · Confiança",
        ):
            self.assertIn(heading, self.generated)

    def test_direct_ndvi_is_not_presented_as_a_synthetic_score(self):
        vegetation = self.core["CORE_03"]
        self.assertEqual(vegetation["measurement_kind"], "direct_reading")
        self.assertIsNone(vegetation["value_0_100"])
        self.assertIn("NDVI 0,616", vegetation["primary_result"])
        self.assertIn("no equival a `61,6/100`", self.methodology)

    def test_radar_12_documents_the_non_compensatory_decision_matrix(self):
        management = self.core["CORE_12"]
        self.assertEqual(management["measurement_kind"], "multicriteria_decision")
        self.assertIsNone(management["profile"]["global_score"])
        self.assertIn("Matriu sector × alternativa", management["calculation_explanation"])
        self.assertIn("No calcula una mitjana global", self.methodology)

    def test_explanations_name_inputs_that_do_not_enter_current_formulas(self):
        connectivity = self.core["CORE_08"]
        fire = self.core["CORE_09"]
        water = self.core["CORE_10"]
        self.assertNotIn("osm_public_use", connectivity["sources_used"])
        self.assertIn("pla_alfa", fire["sources_used"])
        self.assertIn("Pla Alfa", fire["guide"]["basis"])
        self.assertEqual(water["profile"]["flow_permanence_quality_function"], "NO AVALUABLE")

    def test_dynamic_diagnosis_targets_are_unique(self):
        identifiers = re.findall(r'\bid="([^"]+)"', self.generated)
        self.assertEqual(len(identifiers), len(set(identifiers)))


if __name__ == "__main__":
    unittest.main()
