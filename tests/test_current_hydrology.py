import unittest

from tools.calculate_la_seu_current_hydrology import _category, _trend


class CurrentHydrologyRulesTest(unittest.TestCase):
    def test_flow_driven_high_score_is_capped_at_vigilance_without_rain(self):
        category, note = _category(82.0, 0.0, 0.0)
        self.assertEqual(category, "vigilància")
        self.assertIn("pluja", note)

    def test_elevated_requires_precipitation_corroboration(self):
        category, note = _category(62.0, 22.0, 0.0)
        self.assertEqual(category, "elevada")
        self.assertIsNone(note)

    def test_undated_sequence_is_only_a_qualitative_trend(self):
        trend = _trend([1, 1, 1, 1, 1, 2, 2, 2, 2, 2])
        self.assertTrue(trend["available"])
        self.assertEqual(trend["direction"], "ascendent")
        self.assertIn("marca temporal individual", trend["timestamp_limitation"])


if __name__ == "__main__":
    unittest.main()
