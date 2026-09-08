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
METHODOLOGY = ROOT / "docs" / "metodologia_oficial_ecoradar.md"


class InteractiveDiagnosisTraceabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.generated = GENERATED.read_text(encoding="utf-8")
        cls.methodology = METHODOLOGY.read_text(encoding="utf-8")

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

    def test_all_radar_cards_expose_the_five_explanation_blocks(self):
        for number in range(1, 13):
            self.assertRegex(
                self.source,
                rf'"CORE_{number:02d}": \{{\n\s+"kind":',
            )
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
        self.assertIn("Lectura directa · NDVI", self.generated)
        self.assertIn("NDVI 0,616 no es transforma en 61,6/100", self.generated)
        self.assertIn("la lectura directa `NDVI 0,616` tampoc", self.methodology)

    def test_radar_12_documents_the_actual_equal_weight_mean(self):
        self.assertIn("Mitjana aritmètica simple, amb el mateix pes", self.generated)
        self.assertIn("mitjana aritmètica simple, amb el mateix pes", self.methodology)
        self.assertNotIn("No és una mitjana simple", self.methodology)

    def test_explanations_name_inputs_that_do_not_enter_current_formulas(self):
        self.assertIn("Hàbitats i hidrologia no intervenen numèricament", self.generated)
        self.assertIn("meteorologia actual, NDMI, LST, Pla Alfa ni combustible mesurat", self.generated)
        self.assertIn("El relleu, l’NDWI, el cabal, la qualitat i la permanència", self.generated)

    def test_dynamic_diagnosis_targets_are_unique(self):
        identifiers = re.findall(r'\bid="([^"]+)"', self.generated)
        self.assertEqual(len(identifiers), len(set(identifiers)))


if __name__ == "__main__":
    unittest.main()
