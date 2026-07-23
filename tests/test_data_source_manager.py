from pathlib import Path
import unittest

from ecoradar.sources.data_source_manager import DataSourceManager, run_data_source_manager


class DataSourceManagerTest(unittest.TestCase):
    def test_manager_reads_flattened_catalogue(self):
        manager = DataSourceManager("config/data_sources.yaml")
        source_ids = {source["id"] for source in manager.flattened_sources()}

        self.assertIn("copernicus_sentinel_ndvi", source_ids)
        self.assertIn("copernicus_sentinel_ndmi", source_ids)
        self.assertIn("copernicus_sentinel_ndwi", source_ids)
        self.assertIn("copernicus_sentinel_nbr", source_ids)
        self.assertIn("icgc_orthophoto", source_ids)

    def test_manager_generates_mandatory_reports(self):
        result = run_data_source_manager("projectes/Alinya", config_path="config/data_sources.yaml")

        self.assertTrue(Path(result.data_availability_report).exists())
        self.assertTrue(Path(result.data_availability_markdown).exists())
        self.assertTrue(Path(result.connectors_status_report).exists())
        self.assertTrue(Path(result.indicators_completeness_report).exists())
        self.assertGreaterEqual(result.summary["total_sources"], 25)


if __name__ == "__main__":
    unittest.main()
