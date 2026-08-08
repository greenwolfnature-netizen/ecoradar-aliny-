import json
import tempfile
from pathlib import Path
import unittest

from ecoradar.core.context import ProjectContext
from ecoradar.sources.availability import load_data_sources, run_data_availability_check
from ecoradar.sources.source_gate import SourceInventory
from ecoradar.diagnosis.engine import generate_diagnosis_outputs
from ecoradar.product.fitxa_value import generate_fitxa_value_outputs
from ecoradar.recommendations.engine import generate_recommendation_outputs
from ecoradar.sources.mandatory_copernicus import MandatoryCopernicusError


class PlatformIntegrationTest(unittest.TestCase):
    def test_project_context_resolves_name_from_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "Test"
            (root / "metadata").mkdir(parents=True)
            (root / "metadata" / "study_area_metadata.json").write_text(
                json.dumps({"project_name": "Espai Test"}),
                encoding="utf-8",
            )

            context = ProjectContext.from_root(root)

            self.assertEqual(context.project_name, "Espai Test")
            self.assertEqual(context.paths.processed, root.resolve() / "processed")

    def test_source_gate_reads_verified_and_blocked_sources(self):
        inventory = SourceInventory.from_file("docs/data_sources/sources_inventory.yml")

        self.assertTrue(inventory.connector_allowed("land_cover_icgc_cobertes_sol"))
        self.assertFalse(inventory.connector_allowed("climate_meteocat_api"))
        self.assertIn("verified", inventory.status_counts())

    def test_data_sources_config_contains_required_blocks(self):
        config = load_data_sources("config/data_sources.yaml")
        block_ids = {block["id"] for block in config["blocks"]}

        self.assertIn("study_area", block_ids)
        self.assertIn("copernicus_sentinel", block_ids)
        self.assertIn("fieldwork", block_ids)

    def test_data_availability_check_writes_mandatory_reports(self):
        result = run_data_availability_check("projectes/Alinya")

        self.assertTrue(Path(result["data_availability_report"]).exists())
        self.assertTrue(Path(result["data_availability_markdown"]).exists())
        self.assertTrue(Path(result["connectors_status_report"]).exists())
        self.assertTrue(Path(result["indicators_completeness_report"]).exists())

    def test_diagnosis_and_recommendations_block_without_mandatory_copernicus(self):
        with self.assertRaises(MandatoryCopernicusError):
            generate_diagnosis_outputs("projectes/Alinya")
        with self.assertRaises(MandatoryCopernicusError):
            generate_recommendation_outputs("projectes/Alinya")

    def test_fitxa_value_gate_prioritizes_fitxa_impact(self):
        result = generate_fitxa_value_outputs("projectes/Alinya")

        self.assertTrue(Path(result["json"]).exists())
        self.assertTrue(Path(result["csv"]).exists())
        self.assertGreaterEqual(result["item_count"], 1)
        self.assertIsNotNone(result["top_priority"])


if __name__ == "__main__":
    unittest.main()
