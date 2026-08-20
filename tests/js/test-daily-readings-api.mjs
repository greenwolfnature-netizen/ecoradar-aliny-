import assert from "node:assert/strict";
import test from "node:test";

import {
  loadRemoteSnapshot,
  resolveDataBaseUrl,
  validateRemoteSnapshot,
} from "../../netlify/functions/daily-readings.mjs";

const checkedAt = "2026-07-23T08:15:00Z";
const daily = {
  checked_at_utc: checkedAt,
  readings: { air_temperature: { value: "20,0 °C" } },
  source_checks: { meteocat_xema: { status: "verified", checked_at_utc: checkedAt } },
};
const history = { checked_at_utc: checkedAt, analytics: {} };
const fire = {
  checked_at_utc: checkedAt,
  summary: { mean_index_0_100: 42 },
  meteorology_context: { precipitation_accumulated: { last_7_days_mm: 10 } },
  pla_alfa: { official: true, municipality_code: "259084", level: 0 },
};

test("resolves a GitHub raw base URL when the explicit base is absent", () => {
  assert.equal(
    resolveDataBaseUrl({
      ECORADAR_GITHUB_REPOSITORY: "green-wolf/ecoradar",
      ECORADAR_GITHUB_BRANCH: "production",
    }),
    "https://raw.githubusercontent.com/green-wolf/ecoradar/production/projectes/Alinya",
  );
});

test("rejects snapshots whose daily history belongs to another check", () => {
  assert.throws(
    () =>
      validateRemoteSnapshot(
        daily,
        { ...history, checked_at_utc: "2026-07-22T08:15:00Z" },
        fire,
      ),
    /mateixa comprovació/,
  );
});

test("rejects a current-fire snapshot without official Pla Alfa context", () => {
  assert.throws(
    () => validateRemoteSnapshot(daily, history, { ...fire, pla_alfa: null }),
    /incompleta/,
  );
});

test("returns the remote checked_at_utc and never replaces it with served_at_utc", async () => {
  const payloads = new Map([
    ["indicators/daily_readings.json", daily],
    ["indicators/daily_history.json", history],
    ["indicators/current_fire_danger.json", fire],
  ]);
  const fetchImpl = async (url) => {
    const relative = url.split("/projectes/Alinya/")[1];
    return new Response(JSON.stringify(payloads.get(relative)), {
      status: payloads.has(relative) ? 200 : 404,
      headers: { "content-type": "application/json" },
    });
  };
  const servedAt = new Date("2026-07-23T09:00:00Z");
  const result = await loadRemoteSnapshot({
    baseUrl: "https://example.test/projectes/Alinya",
    fetchImpl,
    servedAt,
  });
  assert.equal(result.checked_at_utc, "2026-07-23T08:15:00.000Z");
  assert.equal(result.served_at_utc, "2026-07-23T09:00:00.000Z");
  assert.equal(result.delivery_mode, "remote_canonical_snapshot");
});
