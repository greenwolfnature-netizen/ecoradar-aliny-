import unittest

from ecoradar.core.study_area import SUPPORTED_EXTENSIONS


class StudyAreaContractTest(unittest.TestCase):
    def test_supported_extensions(self):
        self.assertIn(".gpkg", SUPPORTED_EXTENSIONS)
        self.assertIn(".shp", SUPPORTED_EXTENSIONS)
        self.assertIn(".geojson", SUPPORTED_EXTENSIONS)


if __name__ == "__main__":
    unittest.main()

