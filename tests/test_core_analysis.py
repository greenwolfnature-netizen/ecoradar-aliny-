import unittest

from ecoradar.analysis.core import _category, _status_counts, CoreIndicatorResult


class CoreAnalysisContractTest(unittest.TestCase):
    def test_category_scale(self):
        self.assertEqual(_category(None), "no disponible")
        self.assertEqual(_category(10), "molt baix")
        self.assertEqual(_category(35), "baix")
        self.assertEqual(_category(55), "mitjà")
        self.assertEqual(_category(75), "alt")
        self.assertEqual(_category(95), "molt alt")

    def test_status_counts_keep_indicators_separate(self):
        results = [
            CoreIndicatorResult("CORE_01", "A", "parcial", "x", 50, "mitjà", "baixa", (), (), "", "", (), ""),
            CoreIndicatorResult("CORE_02", "B", "no disponible", "x", None, "no disponible", "baixa", (), (), "", "", (), ""),
        ]
        self.assertEqual(_status_counts(results), {"parcial": 1, "no disponible": 1})


if __name__ == "__main__":
    unittest.main()
