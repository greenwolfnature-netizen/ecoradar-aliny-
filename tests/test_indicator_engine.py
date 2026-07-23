import unittest

from ecoradar.indicators.engine import run_indicator_engine
from ecoradar.sources.mandatory_copernicus import MandatoryCopernicusError


class IndicatorEngineTest(unittest.TestCase):
    def test_indicator_engine_blocks_without_mandatory_copernicus(self):
        with self.assertRaises(MandatoryCopernicusError):
            run_indicator_engine("projectes/Alinya")


if __name__ == "__main__":
    unittest.main()
