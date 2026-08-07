import unittest

from ecoradar.diagnosis.engine import run_diagnosis_engine
from ecoradar.sources.mandatory_copernicus import MandatoryCopernicusError


class DiagnosisEngineTest(unittest.TestCase):
    def test_diagnosis_engine_blocks_without_mandatory_copernicus(self):
        with self.assertRaises(MandatoryCopernicusError):
            run_diagnosis_engine("projectes/Alinya")


if __name__ == "__main__":
    unittest.main()
