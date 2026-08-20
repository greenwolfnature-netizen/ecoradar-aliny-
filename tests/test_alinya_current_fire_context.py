from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd

from ecoradar.connectors import connector_pla_alfa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from calculate_alinya_current_fire_danger import (
    _freshness_assessment,
    _precipitation_context,
)
from validate_alinya_daily_timestamps import _validate_fire_freshness


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


class FreshnessAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
        self.dynamic = {
            "kind": "dynamic",
            "full_weight_max_age_hours": 72,
            "exclude_after_hours": 240,
            "rationale": "prova",
        }

    def test_structural_component_does_not_expire_daily(self):
        result = _freshness_assessment(
            "2023-01-01T00:00:00Z",
            {"kind": "structural", "rationale": "prova"},
            self.now,
        )
        self.assertEqual(result["factor"], 1.0)
        self.assertEqual(result["status"], "estructural")

    def test_current_dynamic_component_keeps_full_weight(self):
        result = _freshness_assessment("2026-08-18T12:00:00Z", self.dynamic, self.now)
        self.assertEqual(result["factor"], 1.0)
        self.assertEqual(result["status"], "current")

    def test_recent_dynamic_component_loses_weight_linearly(self):
        result = _freshness_assessment("2026-08-14T00:00:00Z", self.dynamic, self.now)
        expected = 1 - (156 - 72) / (240 - 72)
        self.assertAlmostEqual(result["factor"], expected, places=6)
        self.assertEqual(result["status"], "recent")

    def test_too_old_dynamic_component_is_context_only(self):
        result = _freshness_assessment("2026-08-01T00:00:00Z", self.dynamic, self.now)
        self.assertEqual(result["factor"], 0.0)
        self.assertEqual(result["status"], "too_old")

    def test_missing_dynamic_component_is_excluded(self):
        result = _freshness_assessment(None, self.dynamic, self.now)
        self.assertEqual(result["factor"], 0.0)
        self.assertEqual(result["status"], "too_old")

    def test_validator_rejects_old_dynamic_component_with_weight(self):
        fire = {
            "weights": {"ndmi_dryness": 0.15, "structural": 0.20},
            "effective_weights": {"ndmi_dryness": 0.15, "structural": 0.20},
            "freshness_policy": {
                "ndmi_dryness": self.dynamic,
                "structural": {"kind": "structural"},
            },
            "variables_today": {
                "ndmi_dryness": {"date_utc": "2026-08-01T00:00:00Z"},
                "structural": {"date_utc": "2024-01-01T00:00:00Z"},
            },
            "meteorology_context": {"freshness": {"status": "current"}},
        }
        with self.assertRaisesRegex(RuntimeError, "too old"):
            _validate_fire_freshness(fire, self.now)


if __name__ == "__main__":
    unittest.main()
