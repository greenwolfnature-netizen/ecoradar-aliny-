import unittest

from ecoradar.recommendations.engine import run_recommendation_engine
from ecoradar.sources.mandatory_copernicus import MandatoryCopernicusError


class RecommendationEngineTest(unittest.TestCase):
    def test_recommendation_engine_outputs_priority_artifacts(self):
        with self.assertRaises(MandatoryCopernicusError):
            run_recommendation_engine("projectes/Alinya")


if __name__ == "__main__":
    unittest.main()
