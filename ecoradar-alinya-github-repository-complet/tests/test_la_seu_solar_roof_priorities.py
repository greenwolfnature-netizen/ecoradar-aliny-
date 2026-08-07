import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = (
    ROOT
    / "projectes"
    / "LaSeu_Urba"
    / "indicators"
    / "solar_roof_screening_expanded_summary.json"
)


class LaSeuSolarRoofPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    def test_classes_cover_every_evaluated_building(self):
        self.assertEqual(
            sum(self.summary["classes"].values()),
            self.summary["evaluated_buildings"],
        )

    def test_priority_order_is_complete_and_unique(self):
        self.assertEqual(
            self.summary["priority_order"],
            ["favorable", "condicionada", "baixa"],
        )
        self.assertEqual(
            set(self.summary["class_definitions"]),
            set(self.summary["priority_order"]),
        )

    def test_priority_one_is_geometric_not_guaranteed_yield(self):
        favorable = self.summary["class_definitions"]["favorable"]
        self.assertEqual(favorable["priority"], 1)
        self.assertEqual(favorable["label"], "Millor aptitud geomètrica")
        self.assertIn("pendent", favorable["criteria"].lower())
        self.assertNotIn("producció garantida", favorable["decision"].lower())


if __name__ == "__main__":
    unittest.main()
