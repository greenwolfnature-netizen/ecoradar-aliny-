from pathlib import Path
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


class InteractiveDiagnosisTraceabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.generated = GENERATED.read_text(encoding="utf-8")

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
            self.assertIn(f"CORE_{number:02d}:", self.source)
        self.assertIn('id="eu-core-decision-evidence"', self.generated)

    def test_dynamic_diagnosis_targets_are_unique(self):
        identifiers = re.findall(r'\bid="([^"]+)"', self.generated)
        self.assertEqual(len(identifiers), len(set(identifiers)))


if __name__ == "__main__":
    unittest.main()
