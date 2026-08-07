import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
RENDERER = ROOT / "tools" / "render_la_seu_urban_map.py"
CALCULATOR = ROOT / "tools" / "calculate_la_seu_daily_readings.py"
HTML = PROJECT / "maps" / "ecoradar_urba_la_seu_interactiu.html"


class LaSeuDailyReadingPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = RENDERER.read_text(encoding="utf-8")
        cls.calculator = CALCULATOR.read_text(encoding="utf-8")
        cls.daily = json.loads(
            (PROJECT / "indicators" / "daily_readings.json").read_text(
                encoding="utf-8"
            )
        )
        cls.html = HTML.read_text(encoding="utf-8")

    def test_recent_sidebar_readings_are_remote_sync_targets(self):
        expected = {
            "surface_temperature",
            "shade",
            "ndvi",
            "ndmi",
            "albedo",
            "cool_streets",
            "climate_refuge_utility",
            "current_fire_danger",
            "current_runoff_or_flood",
        }
        for key in expected:
            with self.subTest(key=key):
                self.assertIn(f'data-reading-meta="{key}"', self.html)
        self.assertIn("updateAllLateralReadingMeta();", self.renderer)
        self.assertIn("Object.entries(D.dailyReadings?.readings", self.renderer)

    def test_sentinel_cards_publish_real_means(self):
        self.assertIn('.get("mean")', self.calculator)
        readings = self.daily["readings"]
        self.assertEqual(readings["ndvi"]["value_numeric"], 0.520)
        self.assertEqual(readings["ndmi"]["value_numeric"], 0.087)
        self.assertEqual(readings["albedo"]["value_numeric"], 0.196)
        self.assertIn("NDVI mitjana", self.html)
        self.assertIn("NDMI mitjana", self.html)
        self.assertIn("Albedo estimat · mitjana", self.html)
        self.assertNotIn("NDVI mediana", self.html)

    def test_every_daily_card_has_an_interpretation_before_methodology(self):
        for key, item in self.daily["readings"].items():
            with self.subTest(key=key):
                self.assertTrue(item.get("interpretation"))
        self.assertIn("<dt>Què significa</dt>", self.html)
        self.assertLess(
            self.html.index("<dt>Què significa</dt>"),
            self.html.index("<dt>Metodologia</dt>"),
        )

    def test_pm25_interpretation_preserves_who_and_cams_limitations(self):
        interpretation = self.daily["readings"]["air_quality"]["interpretation"]
        self.assertIn("OMS 2021", interpretation)
        self.assertIn("15 µg/m³", interpretation)
        self.assertIn("mitjana de 24 hores", interpretation)
        self.assertIn("camp CAMS horari modelitzat", interpretation)
        self.assertIn("no permet afirmar que l'aire sigui bo o dolent", interpretation)


if __name__ == "__main__":
    unittest.main()
