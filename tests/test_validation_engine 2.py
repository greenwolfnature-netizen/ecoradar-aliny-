import unittest

from ecoradar.validation.engine import ensure_validation_passed, run_validation_engine
from ecoradar.sources.mandatory_copernicus import MandatoryCopernicusError


class EcoRadarValidationEngineTests(unittest.TestCase):
    def test_validation_outputs_and_gate(self):
        with self.assertRaises(MandatoryCopernicusError):
            run_validation_engine("projectes/Alinya")
        with self.assertRaises(MandatoryCopernicusError):
            ensure_validation_passed("projectes/Alinya")


if __name__ == "__main__":
    unittest.main()
