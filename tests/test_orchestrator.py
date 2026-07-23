from pathlib import Path
import unittest

from ecoradar.core.orchestrator import EcoRadarOrchestrator, EcoRadarPipelineError, run_ecoradar_pipeline


class EcoRadarOrchestratorTests(unittest.TestCase):
    def test_orchestrator_blocks_without_mandatory_copernicus(self):
        with self.assertRaises(EcoRadarPipelineError):
            run_ecoradar_pipeline("projectes/Alinya", generate_documents=False)

        self.assertTrue(Path("projectes/Alinya/metadata/ecoradar_execution_report.json").exists())
        self.assertTrue(Path("projectes/Alinya/reports/ecoradar_execution_report.md").exists())

    def test_connector_tasks_are_cache_aware_by_default(self):
        orchestrator = EcoRadarOrchestrator("projectes/Alinya", generate_documents=False)
        with self.assertRaises(RuntimeError):
            orchestrator._run_connectors()


if __name__ == "__main__":
    unittest.main()
