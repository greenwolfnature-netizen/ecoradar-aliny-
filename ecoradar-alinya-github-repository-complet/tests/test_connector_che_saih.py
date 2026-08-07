import unittest

from ecoradar.connectors.connector_che_saih import (
    parse_current_signals,
    parse_current_streamflow,
)


class CheSaihStreamflowConnectorTest(unittest.TestCase):
    def test_parses_decimal_comma_and_preserves_real_observation_time(self):
        payload = {
            "VALORES_ACTUALES": """
            <tr>
              <td aria-label='Señal Caudal Valira en seu d Urgell'>
                <a href='/tiempo-real/grafica-senal-A022O65QRIO1-caudal-valira'>Caudal</a>
              </td>
              <td aria-label='Valor 6,41 m³/s'><span>6,41</span></td>
              <td aria-label='Fecha 25/07/2026 17:15'>25/07/2026 17:15</td>
            </tr>
            """
        }
        record = parse_current_streamflow(payload, "A022")
        self.assertEqual(record["station_code"], "A022")
        self.assertEqual(record["river"], "Valira")
        self.assertEqual(record["discharge_m3_s"], 6.41)
        self.assertEqual(record["observed_at_local"], "2026-07-25T17:15:00+02:00")
        self.assertEqual(record["observed_at_utc"], "2026-07-25T15:15:00Z")
        self.assertTrue(record["provisional"])

    def test_rejects_non_discharge_signal(self):
        payload = {
            "VALORES_ACTUALES": """
            <tr>
              <td aria-label='Señal Nivel Segre en seu d Urgell'>
                <a href='/tiempo-real/grafica-senal-A023O17NRIO1-nivel-segre'>Nivel</a>
              </td>
              <td aria-label='Valor 0,37 m'>0,37</td>
              <td aria-label='Fecha 25/07/2026 17:15'>25/07/2026 17:15</td>
            </tr>
            """
        }
        with self.assertRaisesRegex(RuntimeError, "No current discharge"):
            parse_current_streamflow(payload, "A023")

    def test_normalizes_level_flow_and_source_trend_without_analysis(self):
        payload = {
            "VALORES_ACTUALES": """
            <tr>
              <td aria-label='Señal Nivel Valira en seu d Urgell'><a href='/grafica-A022O17NRIO1'>Nivell</a></td>
              <td aria-label='Valor 0,36 m'><a><span>0,36</span></a></td>
              <td aria-label='Fecha 25/07/2026 20:15'>25/07/2026 20:15</td>
              <td aria-label='Tendencia derecha'><div url-ajax='/api/ficha/getDatosMinigraficaSenal?tag=A022O17NRIO1&amp;tipoTag=NRIO'>-</div></td>
            </tr>
            <tr>
              <td aria-label='Señal Caudal Valira en seu d Urgell'><a href='/grafica-A022O65QRIO1'>Cabal</a></td>
              <td aria-label='Valor 6,41 m³/s'><a><span>6,41</span></a></td>
              <td aria-label='Fecha 25/07/2026 20:15'>25/07/2026 20:15</td>
              <td aria-label='Tendencia arriba'><div url-ajax='/api/ficha/getDatosMinigraficaSenal?tag=A022O65QRIO1&amp;tipoTag=QRIO'>-</div></td>
            </tr>
            <tr>
              <td aria-label='Señal Precip. 24h. en seu d Urgell (Bt)'><a href='/grafica-A022O83PA24H'>Pluja</a></td>
              <td aria-label='Valor 2,4 l/m²'><span>2,4</span></td>
              <td aria-label='Fecha 25/07/2026 20:15'>25/07/2026 20:15</td>
              <td aria-label='Tendencia derecha'></td>
            </tr>
            """
        }
        signals = parse_current_signals(payload, "A022")
        self.assertEqual(signals["level"]["value"], 0.36)
        self.assertEqual(signals["discharge"]["value"], 6.41)
        self.assertEqual(signals["precipitation_24h"]["value"], 2.4)
        self.assertEqual(signals["discharge"]["source_trend"], "arriba")
        self.assertIn("A022O65QRIO1", signals["discharge"]["minigraph_path"])


if __name__ == "__main__":
    unittest.main()
