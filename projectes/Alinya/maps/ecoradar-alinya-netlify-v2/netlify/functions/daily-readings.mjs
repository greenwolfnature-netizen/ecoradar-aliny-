const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store, max-age=0",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "Content-Type",
};

const SNAPSHOT_PATHS = {
  daily_readings: "indicators/daily_readings.json",
  daily_history: "indicators/daily_history.json",
  current_fire_danger: "indicators/current_fire_danger.json",
};

export function resolveDataBaseUrl(environment = process.env) {
  const configured = environment.ECORADAR_DATA_BASE_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  const repository = environment.ECORADAR_GITHUB_REPOSITORY?.trim();
  if (!repository) return null;
  const branch = environment.ECORADAR_GITHUB_BRANCH?.trim() || "main";
  return `https://raw.githubusercontent.com/${repository}/${encodeURIComponent(branch)}/projectes/Alinya`;
}

function isoInstant(value, field) {
  const instant = new Date(value);
  if (!value || Number.isNaN(instant.valueOf())) {
    throw new Error(`La resposta remota no conté ${field} vàlid.`);
  }
  return instant.toISOString();
}

async function fetchJson(baseUrl, relativePath, fetchImpl, bearerToken) {
  const url = `${baseUrl}/${relativePath}`;
  const headers = { accept: "application/json" };
  if (bearerToken) headers.authorization = `Bearer ${bearerToken}`;
  const response = await fetchImpl(url, {
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`${relativePath}: HTTP ${response.status}`);
  }
  return response.json();
}

export function validateRemoteSnapshot(daily, history, fire) {
  const checkedAt = isoInstant(daily?.checked_at_utc, "daily_readings.checked_at_utc");
  const historyCheckedAt = isoInstant(history?.checked_at_utc, "daily_history.checked_at_utc");
  const fireCheckedAt = isoInstant(
    fire?.checked_at_utc || fire?.generated_at_utc,
    "current_fire_danger.checked_at_utc",
  );
  if (checkedAt !== historyCheckedAt || checkedAt !== fireCheckedAt) {
    throw new Error(
      "daily_readings, daily_history i current_fire_danger no corresponen a la mateixa comprovació.",
    );
  }
  if (
    !daily?.readings || !daily?.source_checks || !history?.analytics || !fire?.summary ||
    !fire?.meteorology_context || !fire?.pla_alfa
  ) {
    throw new Error("La resposta remota és incompleta.");
  }
  return { checkedAt, fireCheckedAt };
}

export async function loadRemoteSnapshot({
  baseUrl,
  fetchImpl = fetch,
  servedAt = new Date(),
  bearerToken = null,
}) {
  const [daily, history, fire] = await Promise.all(
    Object.values(SNAPSHOT_PATHS).map((path) =>
      fetchJson(baseUrl, path, fetchImpl, bearerToken),
    ),
  );
  const { checkedAt, fireCheckedAt } = validateRemoteSnapshot(daily, history, fire);
  return {
    schema_version: "2.0",
    delivery_mode: "remote_canonical_snapshot",
    served_at_utc: servedAt.toISOString(),
    checked_at_utc: checkedAt,
    source_checks: daily.source_checks,
    daily_readings: daily,
    daily_history: history,
    current_fire_danger: fire,
    assets: {
      current_fire_raster_url: `${baseUrl}/maps/incendis/current_fire_danger.webp`,
      current_fire_cells_url: `${baseUrl}/maps/incendis/current_fire_danger_cells.geojson`,
    },
    fire_checked_at_utc: fireCheckedAt,
  };
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

export default async function handler(request) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: JSON_HEADERS });
  if (request.method !== "GET") {
    return jsonResponse({ error: "method_not_allowed" }, 405);
  }

  const baseUrl = resolveDataBaseUrl();
  if (!baseUrl) {
    return jsonResponse(
      {
        error: "remote_source_not_configured",
        detail:
          "Configura ECORADAR_DATA_BASE_URL o ECORADAR_GITHUB_REPOSITORY. " +
          "La funció no utilitza els JSON del paquet com a font primària.",
      },
      503,
    );
  }

  const requestUrl = new URL(request.url);
  const dataUrl = new URL(baseUrl);
  if (requestUrl.origin === dataUrl.origin) {
    return jsonResponse(
      {
        error: "packaged_source_not_allowed",
        detail: "La font remota ha de ser externa al desplegament estàtic per evitar lectures congelades.",
      },
      503,
    );
  }

  try {
    return jsonResponse(
      await loadRemoteSnapshot({
        baseUrl,
        bearerToken: process.env.ECORADAR_DATA_BEARER_TOKEN || null,
      }),
    );
  } catch (error) {
    return jsonResponse(
      {
        error: "remote_snapshot_unavailable",
        detail: error instanceof Error ? error.message : String(error),
        failed_at_utc: new Date().toISOString(),
      },
      502,
    );
  }
}
