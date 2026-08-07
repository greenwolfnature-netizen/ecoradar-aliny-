import assert from "node:assert/strict";
import {
  REFRESHABLE_READINGS,
  UpstreamSourceError,
  madridLocalToUtc,
  parseCheCurrent,
  refreshReading,
} from "../../netlify/functions/refresh-reading.mjs";

assert.deepEqual(Object.keys(REFRESHABLE_READINGS).sort(), [
  "air_temperature",
  "precipitation",
  "relative_humidity",
  "river_flow_segre",
  "river_flow_valira",
  "wind",
]);
assert.equal(madridLocalToUtc("25/07/2026 17:30"), "2026-07-25T15:30:00.000Z");

const chePayload = {
  VALORES_ACTUALES:
    '<table><tr><td aria-label="Señal Caudal Valira"><a href="/A022O65QRIO1"></a></td>' +
    '<td aria-label="Valor 6,41 m³/s"></td><td aria-label="Fecha 25/07/2026 17:30"></td></tr></table>',
};
const che = parseCheCurrent(
  chePayload,
  REFRESHABLE_READINGS.river_flow_valira,
  new Date("2026-07-25T17:00:00Z"),
);
assert.equal(che.value, "6,41 m³/s");
assert.equal(che.data_at_utc, "2026-07-25T15:30:00.000Z");
assert.equal(che.status_code, "updated_today");

const xemaRows = [
  {
    codi_estacio: "CD",
    codi_variable: "32",
    data_lectura: "2026-07-25T16:30:00.000",
    valor_lectura: "29.7",
    codi_estat: "V",
  },
];
let requestedUrl = "";
const xemaResult = await refreshReading({
  reading: "air_temperature",
  checkedAt: new Date("2026-07-25T17:00:00Z"),
  fetchImpl: async (url) => {
    requestedUrl = String(url);
    return new Response(JSON.stringify(xemaRows), {
      status: 200,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  },
});
assert.match(requestedUrl, /nzvn-apee/);
assert.match(decodeURIComponent(requestedUrl), /codi_variable='32'/);
assert.equal(xemaResult.reading.value, "29,7 °C");
assert.equal(xemaResult.source_frequency_code, "30_minutes");

const precipitationRows = [
  {
    codi_estacio: "CD",
    codi_variable: "35",
    data_lectura: "2026-07-25T15:30:00.000",
    valor_lectura: "0.2",
    codi_estat: "V",
  },
  {
    codi_estacio: "CD",
    codi_variable: "35",
    data_lectura: "2026-07-25T16:00:00.000",
    valor_lectura: "0.4",
    codi_estat: "V",
  },
  {
    codi_estacio: "CD",
    codi_variable: "35",
    data_lectura: "2026-07-24T20:00:00.000",
    valor_lectura: "10",
    codi_estat: "V",
  },
];
const precipitation = await refreshReading({
  reading: "precipitation",
  checkedAt: new Date("2026-07-25T17:00:00Z"),
  fetchImpl: async () =>
    new Response(JSON.stringify(precipitationRows), {
      status: 200,
      headers: { "content-type": "application/json; charset=utf-8" },
    }),
});
assert.equal(precipitation.reading.value, "0,6 mm");

const cheRefresh = await refreshReading({
  reading: "river_flow_segre",
  checkedAt: new Date("2026-07-26T16:30:00Z"),
  fetchImpl: async () =>
    new Response(
      JSON.stringify({
        VALORES_ACTUALES:
          '<tr><td aria-label="Señal Caudal Segre"><a href="/A023O65QRIO1"></a></td>' +
          '<td aria-label="Valor 1,07 m³/s"></td>' +
          '<td aria-label="Fecha 26/07/2026 18:15"></td></tr>',
      }),
      { status: 200, headers: { "content-type": "application/json; charset=utf-8" } },
    ),
});
assert.equal(cheRefresh.reading.value, "1,07 m³/s");
assert.equal(cheRefresh.reading.data_at_utc, "2026-07-26T16:15:00.000Z");
assert.equal(cheRefresh.source_status.provider, "CHE/SAIH Ebre");
assert.match(cheRefresh.source_status.endpoint, /estacion=A023/);
assert.match(cheRefresh.source_status.official_url, /A023-segre-seu/);

await assert.rejects(
  () =>
    refreshReading({
      reading: "river_flow_valira",
      fetchImpl: async () =>
        new Response("Servei temporalment fora de servei", {
          status: 503,
          statusText: "Service Unavailable",
          headers: { "content-type": "text/plain" },
        }),
    }),
  (error) => {
    assert.ok(error instanceof UpstreamSourceError);
    assert.match(error.message, /HTTP 503 Service Unavailable/);
    assert.equal(error.metadata.code, "upstream_http_error");
    assert.equal(error.metadata.upstream_http_status, 503);
    return true;
  },
);

await assert.rejects(
  () =>
    refreshReading({
      reading: "river_flow_valira",
      fetchImpl: async () =>
        new Response("<html>error</html>", {
          status: 200,
          headers: { "content-type": "text/html" },
        }),
    }),
  (error) => {
    assert.ok(error instanceof UpstreamSourceError);
    assert.match(error.message, /format inesperat/);
    assert.equal(error.metadata.code, "upstream_content_type_error");
    return true;
  },
);

await assert.rejects(
  () =>
    refreshReading({
      reading: "river_flow_segre",
      fetchImpl: async () => {
        throw new Error("temps d'espera esgotat després de 4.5 segons");
      },
    }),
  (error) => {
    assert.ok(error instanceof UpstreamSourceError);
    assert.equal(error.metadata.code, "upstream_timeout");
    assert.match(error.message, /temps d'espera esgotat/);
    return true;
  },
);

await assert.rejects(
  () => refreshReading({ reading: "ndvi", fetchImpl: async () => null }),
  /reading_not_refreshable/,
);

console.log("refresh-reading API tests passed");
