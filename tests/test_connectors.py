import unittest

from ecoradar.connectors.registry import get_connector


class FakeStudyArea:
    name = "Area de prova"
    area_ha = 12.5


class ConnectorRegistryTest(unittest.TestCase):
    def test_empty_cobertes_sol_connector(self):
        connector = get_connector("cobertes_sol_empty")
        result = connector.run(FakeStudyArea())

        self.assertEqual(result.connector_id, "cobertes_sol_empty")
        self.assertEqual(result.status, "not_implemented")
        self.assertFalse(result.metadata["downloads_data"])
        self.assertFalse(result.metadata["calculates_indicators"])
        self.assertEqual(result.metadata["study_area_area_ha"], 12.5)


if __name__ == "__main__":
    unittest.main()

