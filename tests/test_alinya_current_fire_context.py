from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd

from ecoradar.connectors import connector_pla_alfa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from calculate_alinya_current_fire_danger import _precipitation_context


class PlaAlfaConnectorTests(unittest.TestCase):
    def test_normalizes_exact_official_municipality(self):
        layer = {"editingInfo": {"dataLastEditDate": 1787061433598}}
        query = {
            "features": [{"attributes": {
                "CODIMUNI": "259084", "NOMMUNI": "Fígols i Alinyà",
                "NOMCOMAR": "Alt Urgell", "PERIL_M": 2,
            }}]
        }
        with patch.object(connector_pla_alfa, "_get_json", side_effect=[layer, query]):
            frame, metadata = connector_pla_alfa.fetch_current_level()
        self.assertEqual(frame.iloc[0]["PERIL_M"], 2)
        self.assertEqual(frame.iloc[0]["CODIMUNI"], "259084")
        self.assertEqual(metadata, layer)

    def test_rejects_invalid_level(self):
        layer = {"editingInfo": {"dataLastEditDate": 1787061433598}}
        query = {"features": [{"attributes": {
            "CODIMUNI": "259084", "NOMMUNI": "Fígols i Alinyà",
            "NOMCOMAR": "Alt Urgell", "PERIL_M": 7,
        }}]}
        with patch.object(connector_pla_alfa, "_get_json", side_effect=[layer, query]):
            with self.assertRaisesRegex(RuntimeError, "0-4"):
                connector_pla_alfa.fetch_current_level()


class PrecipitationContextTests(unittest.TestCase):
    def _frame(self, days: int = 30) -> pd.DataFrame:
        end = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
        stamps = [end - timedelta(minutes=30 * offset) for offset in range(days * 48)]
        values = [0.0] * len(stamps)
        values[50] = 2.0
        return pd.DataFrame({
            "codi_estacio": ["Y4"] * len(stamps),
            "codi_variable": ["35"] * len(stamps),
            "data_lectura": stamps,
            "valor_lectura": values,
        })

    def test_accumulates_only_with_sufficient_coverage(self):
        result = _precipitation_context(self._frame(), "35")
        self.assertEqual(result["recent_24h_mm"], 0.0)
        self.assertEqual(result["last_7_days_mm"], 2.0)
        self.assertEqual(result["last_30_days_mm"], 2.0)

    def test_refuses_incomplete_30_day_total(self):
        result = _precipitation_context(self._frame(days=7), "35")
        self.assertIsNone(result["last_30_days_mm"])


if __name__ == "__main__":
    unittest.main()
