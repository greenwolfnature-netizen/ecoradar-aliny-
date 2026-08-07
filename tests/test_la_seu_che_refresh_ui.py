import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "tools" / "render_la_seu_urban_map.py"


class LaSeuCheRefreshUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = RENDERER.read_text(encoding="utf-8")

    def test_che_polling_matches_official_frequency(self):
        self.assertIn("const CHE_REFRESH_INTERVAL_MS=15*60*1000;", self.source)
        self.assertIn("window.setInterval", self.source)
        self.assertIn("document.visibilityState==='visible'", self.source)

    def test_same_official_observation_is_explained_as_current(self):
        self.assertIn("Dada CHE al dia", self.source)
        self.assertIn("última observació oficial", self.source)
        self.assertIn("encara no hi ha un interval posterior", self.source)
        self.assertNotIn(
            "result.textContent='No hi ha cap actualització nova'",
            self.source,
        )

    def test_stale_and_revised_observations_are_distinguished(self):
        self.assertIn("incomingInstant<currentInstant", self.source)
        self.assertIn("Dada revisada per la CHE", self.source)
        self.assertIn("Es conserva la dada més recent mostrada", self.source)


if __name__ == "__main__":
    unittest.main()
