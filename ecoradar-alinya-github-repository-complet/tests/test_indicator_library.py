import unittest

from ecoradar.indicators import get_indicator, indicators_by_block, list_indicators


class IndicatorLibraryTest(unittest.TestCase):
    def test_library_contains_expected_number_of_indicators(self):
        self.assertEqual(len(list_indicators()), 48)

    def test_indicator_codes_are_unique(self):
        codes = [indicator.code for indicator in list_indicators()]
        self.assertEqual(len(codes), len(set(codes)))

    def test_required_definition_fields_are_populated(self):
        for indicator in list_indicators():
            with self.subTest(indicator=indicator.code):
                self.assertTrue(indicator.code)
                self.assertTrue(indicator.name)
                self.assertTrue(indicator.thematic_block)
                self.assertTrue(indicator.objective)
                self.assertTrue(indicator.required_data)
                self.assertTrue(indicator.data_sources)
                self.assertTrue(indicator.calculation_method)
                self.assertTrue(indicator.valuation_scale)
                self.assertTrue(indicator.confidence_level)
                self.assertTrue(indicator.limitations)
                self.assertTrue(indicator.associated_recommendations)
                self.assertEqual(indicator.calculation_status, "not_implemented")

    def test_lookup_by_code(self):
        indicator = get_indicator("ECO_INC_05")
        self.assertEqual(indicator.name, "Prioritat de gestio forestal compatible amb biodiversitat")

    def test_filter_by_block(self):
        indicators = indicators_by_block("Fauna i biodiversitat")
        self.assertEqual(len(indicators), 5)
        self.assertEqual(indicators[0].code, "ECO_FAU_01")


if __name__ == "__main__":
    unittest.main()
