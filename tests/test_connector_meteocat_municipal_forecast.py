import unittest

from ecoradar.connectors.connector_meteocat_municipal_forecast import (
    normalize_forecast_payload,
)


class MeteocatMunicipalForecastConnectorTest(unittest.TestCase):
    def test_selects_only_la_seu_and_preserves_issue_and_valid_times(self):
        payload = {
            "dataSortida": "2026-07-25T00:00Z",
            "codiVariable": "prec_acum",
            "nomVariable": "Precipitació acumulada",
            "unitat": "mm",
            "municipis": [
                {"nom": "Altre", "codi": "000000", "valors": [{"valor": 99, "data": "2026-07-25T01:00Z"}]},
                {
                    "nom": "la Seu d'Urgell",
                    "codi": "252038",
                    "valors": [
                        {"valor": 0.2, "data": "2026-07-25T01:00Z"},
                        {"valor": 1.4, "data": "2026-07-25T02:00Z"},
                    ],
                },
            ],
        }
        frame = normalize_forecast_payload(payload, 1)
        self.assertEqual(len(frame), 2)
        self.assertEqual(set(frame["municipality_code"]), {"252038"})
        self.assertAlmostEqual(frame["precipitation_mm"].sum(), 1.6)
        self.assertEqual(frame["issued_at_utc"].iloc[0], "2026-07-25T00:00:00Z")
        self.assertEqual(frame["valid_at_utc"].iloc[-1], "2026-07-25T02:00:00Z")

    def test_rejects_payload_without_target_municipality(self):
        with self.assertRaisesRegex(RuntimeError, "252038"):
            normalize_forecast_payload({"municipis": [], "dataSortida": "2026-07-25T00:00Z"}, 1)


if __name__ == "__main__":
    unittest.main()
