import unittest

from ecoradar.core.study_area import DEFAULT_METRIC_CRS


class PrepareStudyAreaContractTest(unittest.TestCase):
    def test_default_metric_crs_is_catalonia_utm(self):
        self.assertEqual(DEFAULT_METRIC_CRS, "EPSG:25831")


if __name__ == "__main__":
    unittest.main()
