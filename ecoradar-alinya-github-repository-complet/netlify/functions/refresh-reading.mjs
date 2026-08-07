import { request as httpsRequest } from "node:https";
import { rootCertificates } from "node:tls";

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store, max-age=0",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "Content-Type",
};

const XEMA_ENDPOINT =
  "https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json";
const CHE_ENDPOINT_PATH = "/api/ficha/procesarTablaValoresActuales";
const CHE_OFFICIAL_HOSTS = Object.freeze([
  "https://www.saihebro.com",
  "https://ap.saihebro.com",
  "https://internet.saihebro.com",
]);
const CHE_ENDPOINT = `${CHE_OFFICIAL_HOSTS[0]}${CHE_ENDPOINT_PATH}`;
const MADRID_TZ = "Europe/Madrid";
const UPSTREAM_TIMEOUT_MS = 15000;
const CHE_ATTEMPT_TIMEOUT_MS = 4500;
const DEFAULT_FETCH = globalThis.fetch;

// Intermedi oficial indicat per l'AIA del certificat *.saihebro.com.
// Subject: FNMT-RCM / AC Componentes Informáticos
// Vigència: 2013-06-24 — 2028-06-24
// SHA-256: F0:38:42:1F:07:F2:0D:63:A2:0D:36:91:E5:A1:78:AB:
//          84:59:EB:E5:70:C1:64:7B:76:90:55:4E:F2:38:76:AB
// La CHE no enviava aquest intermedi el 26/07/2026. S'afegeix a les arrels
// públiques de Node; no es desactiva mai la verificació TLS.
const FNMT_AC_COMPONENTES_INFORMATICOS_PEM = `-----BEGIN CERTIFICATE-----
MIIG1jCCBL6gAwIBAgIQNMarBE42mRJRyCULbJTWwDANBgkqhkiG9w0BAQsFADA7
MQswCQYDVQQGEwJFUzERMA8GA1UECgwIRk5NVC1SQ00xGTAXBgNVBAsMEEFDIFJB
SVogRk5NVC1SQ00wHhcNMTMwNjI0MTA1MjU5WhcNMjgwNjI0MTA1MjU5WjBHMQsw
CQYDVQQGEwJFUzERMA8GA1UECgwIRk5NVC1SQ00xJTAjBgNVBAsMHEFDIENvbXBv
bmVudGVzIEluZm9ybcOhdGljb3MwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQCXVx8rdbF7/xY44CaSqzzGo5BhvzA8knxC/3KJYVzTf+CkOvMxMUDub8b0
h38MDujm/RKZhBNOWbKhxF3U61ZVhcR9xOCciuS/soT80m3BByxAKcZsNka0jCA4
XRkglDaAFxCHEZ06MOnvXsSOZDfPYahbQ3VFCVycJuhlHdAwSpmceQwcRYkR6YgX
wTiyzCNGivMKAmRS3dItqDOmDW/nxiDFq/Jd8VWY7GFkwbbAeqYId8FjN8zfvafu
nsB9SLFkUjPPMeqfmC7Bdh7HMxLpaOXROwH201cmlebiPkn0xSFxXFqwhhr6yN8U
QYZ3O/+xdHLrS6DS9+CJUF6d09ijAgMBAAGjggLIMIICxDASBgNVHRMBAf8ECDAG
AQH/AgEAMA4GA1UdDwEB/wQEAwIBBjAdBgNVHQ4EFgQUGfhYLxTWpsybBJgIDUzX
qwCng2UwgZgGCCsGAQUFBwEBBIGLMIGIMEkGCCsGAQUFBzABhj1odHRwOi8vb2Nz
cGZubXRyY21jYS5jZXJ0LmZubXQuZXMvb2NzcGZubXRyY21jYS9PY3NwUmVzcG9u
ZGVyMDsGCCsGAQUFBzAChi9odHRwOi8vd3d3LmNlcnQuZm5tdC5lcy9jZXJ0cy9B
Q1JBSVpGTk1UUkNNLmNydDAfBgNVHSMEGDAWgBT3fcX9xOiaG3dkp/UdoMy/h2Ca
bTCB6wYDVR0gBIHjMIHgMIHdBgRVHSAAMIHUMCkGCCsGAQUFBwIBFh1odHRwOi8v
d3d3LmNlcnQuZm5tdC5lcy9kcGNzLzCBpgYIKwYBBQUHAgIwgZkMgZZTdWpldG8g
YSBsYXMgY29uZGljaW9uZXMgZGUgdXNvIGV4cHVlc3RhcyBlbiBsYSBEZWNsYXJh
Y2nDs24gZGUgUHLDoWN0aWNhcyBkZSBDZXJ0aWZpY2FjacOzbiBkZSBsYSBGTk1U
LVJDTSAoIEMvIEpvcmdlIEp1YW4sIDEwNi0yODAwOS1NYWRyaWQtRXNwYcOxYSkw
gdQGA1UdHwSBzDCByTCBxqCBw6CBwIaBkGxkYXA6Ly9sZGFwZm5tdC5jZXJ0LmZu
bXQuZXMvQ049Q1JMLE9VPUFDJTIwUkFJWiUyMEZOTVQtUkNNLE89Rk5NVC1SQ00s
Qz1FUz9hdXRob3JpdHlSZXZvY2F0aW9uTGlzdDtiaW5hcnk/YmFzZT9vYmplY3Rj
bGFzcz1jUkxEaXN0cmlidXRpb25Qb2ludIYraHR0cDovL3d3dy5jZXJ0LmZubXQu
ZXMvY3Jscy9BUkxGTk1UUkNNLmNybDANBgkqhkiG9w0BAQsFAAOCAgEAo2bsQ2xL
Dcyodieqjd+uy/lfxDw/MbrAq/ZaNFkIlcypUYamOM4vrm5rz8oLjPCoLkJ48P+n
P08Gkcl5Q6q6VFcZLia+U3gfHXrkyqToQlrtViGCGH3xA4u56XtMHGXSdk9vQ0yD
nW5f7bUEkp+uvcKewrOvNcpbIAgD4eU7gdOS0w7BagcFRBgTKBw2s3z73fRZtouJ
g/atmWYtXbBsfNjph+pCh+h5sbSyZUVzO5AemyjpYYYNMWDQrTXq+7O8zIPuPaNE
SjEexuzn+VjHG90RlUK1LygARi+Ir0opD2w6erb/hK8Eea7MFdKQ2ASqNBGJggNo
5vfPVvjHiL+Antmh7mQSKL+4YwFU64d4KK9k0C1mbJethDQFKcjTK1vMvnXFiups
IuyTqwKauo7u2zMKzY4r3VYOW9TpMyLPFIY8pII5GyNzXlL0F4nscOvduTEPEYqx
eNJfpDDPY/DO8WfxgdRTy2W3D/UoAulb+Y+nuzGGCtFQrsSMQX487R+aY0nWot/h
ajef6BcPuxhDfQrg5IafrISVmcJAplb3tXhh0sz7RbYz6jf1bke4eU5fnrTMtGlV
teUL2vjrfUPHW07kBJuaQ7sxORNV3bpHisOnHj+AriQzCn5vINpSHW6hTm7IfRkb
ltu/aQrsMuUhP7HE/v+uXe5CuboV5ubZhHU=
-----END CERTIFICATE-----`;

export const REFRESHABLE_READINGS = Object.freeze({
  air_temperature: {
    provider: "xema",
    variables: ["32"],
    frequency_code: "30_minutes",
    frequency_label: "font cada 30 minuts",
  },
  relative_humidity: {
    provider: "xema",
    variables: ["33"],
    frequency_code: "30_minutes",
    frequency_label: "font cada 30 minuts",
  },
  wind: {
    provider: "xema",
    variables: ["30", "31", "50"],
    frequency_code: "30_minutes",
    frequency_label: "font cada 30 minuts",
  },
  precipitation: {
    provider: "xema",
    variables: ["35"],
    frequency_code: "30_minutes",
    frequency_label: "font cada 30 minuts",
  },
  river_flow_valira: {
    provider: "che",
    station: "A022",
    river: "Valira",
    signal: "A022O65QRIO1",
    official_url:
      "https://www.saihebro.com/tiempo-real/estacion-aforos-A022-valira-seu",
    frequency_code: "15_minutes",
    frequency_label: "font cada 15 minuts",
  },
  river_flow_segre: {
    provider: "che",
    station: "A023",
    river: "Segre",
    signal: "A023O65QRIO1",
    official_url:
      "https://www.saihebro.com/tiempo-real/estacion-aforos-A023-segre-seu",
    frequency_code: "15_minutes",
    frequency_label: "font cada 15 minuts",
  },
});

export class UpstreamSourceError extends Error {
  constructor(message, metadata = {}) {
    super(message);
    this.name = "UpstreamSourceError";
    this.metadata = metadata;
  }
}

function fetchCheWithOfficialIntermediate(url, options = {}) {
  return new Promise((resolve, reject) => {
    const timeoutMs = options.timeoutMs || CHE_ATTEMPT_TIMEOUT_MS;
    const request = httpsRequest(
      url,
      {
        method: "GET",
        headers: options.headers,
        signal: options.signal,
        family: 4,
        ca: [...rootCertificates, FNMT_AC_COMPONENTES_INFORMATICOS_PEM],
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          resolve(
            new Response(Buffer.concat(chunks), {
              status: response.statusCode || 502,
              statusText: response.statusMessage || "",
              headers: response.headers,
            }),
          );
        });
      },
    );
    request.setTimeout(timeoutMs, () => {
      request.destroy(
        new Error(`temps d'espera esgotat després de ${timeoutMs / 1000} segons`),
      );
    });
    request.on("error", reject);
    request.end();
  });
}

function cheEndpoint(host, station) {
  return `${host}${CHE_ENDPOINT_PATH}?${new URLSearchParams({ estacion: station })}`;
}

async function fetchCheFromOfficialMirrors(station, options = {}) {
  const controllers = CHE_OFFICIAL_HOSTS.map(() => new AbortController());
  const attempts = CHE_OFFICIAL_HOSTS.map(async (host, index) => {
    const endpoint = cheEndpoint(host, station);
    const response = await fetchCheWithOfficialIntermediate(endpoint, {
      ...options,
      signal: controllers[index].signal,
      timeoutMs: CHE_ATTEMPT_TIMEOUT_MS,
    });
    const contentType = response.headers.get("content-type") || "no declarat";
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} a ${host}`);
    }
    if (!contentType.toLowerCase().includes("application/json")) {
      throw new Error(`format ${contentType} a ${host}`);
    }
    return response;
  });
  try {
    return await Promise.any(attempts);
  } catch (error) {
    const reasons =
      error instanceof AggregateError
        ? error.errors.map((item) => (item instanceof Error ? item.message : String(item)))
        : [error instanceof Error ? error.message : String(error)];
    const timeout = reasons.every((reason) => reason.includes("temps d'espera"));
    throw new UpstreamSourceError(
      timeout
        ? `CHE/SAIH Ebre: temps d'espera als ${CHE_OFFICIAL_HOSTS.length} servidors oficials (${reasons.join(
            " | ",
          )})`
        : `CHE/SAIH Ebre: han fallat tots els servidors oficials (${reasons.join(" | ")})`,
      {
        code: timeout ? "upstream_timeout_all_official_hosts" : "upstream_all_official_hosts_failed",
        provider: "CHE/SAIH Ebre",
        upstream_urls: CHE_OFFICIAL_HOSTS.map((host) => cheEndpoint(host, station)),
        attempts: reasons,
      },
    );
  } finally {
    controllers.forEach((controller) => controller.abort());
  }
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

function isoInstant(value, field) {
  const parsed = new Date(value);
  if (!value || Number.isNaN(parsed.valueOf())) {
    throw new Error(`${field} no és una data vàlida`);
  }
  return parsed.toISOString();
}

function madridDate(value) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: MADRID_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

function publicStatus(dataAt, checkedAt) {
  return madridDate(dataAt) === madridDate(checkedAt)
    ? ["updated_today", "actualitzada avui"]
    : ["last_available", "última dada disponible"];
}

function formatNumber(value, decimals) {
  return new Intl.NumberFormat("ca-ES", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

function readingRecord({
  label,
  valueNumeric,
  decimals,
  unit,
  source,
  dataAt,
  checkedAt,
  quality,
  note,
}) {
  const dataAtUtc = isoInstant(dataAt, "data_at_utc");
  const checkedAtUtc = isoInstant(checkedAt, "checked_at_utc");
  const [statusCode, status] = publicStatus(dataAtUtc, checkedAtUtc);
  return {
    label,
    value: `${formatNumber(valueNumeric, decimals)} ${unit}`,
    value_numeric: valueNumeric,
    unit,
    source,
    data_at_utc: dataAtUtc,
    checked_at_utc: checkedAtUtc,
    status_code: statusCode,
    status,
    quality,
    note,
  };
}

async function fetchJson(url, fetchImpl, provider = "font oficial") {
  const timeoutSignal =
    typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function"
      ? AbortSignal.timeout(UPSTREAM_TIMEOUT_MS)
      : undefined;
  let response;
  try {
    response = await fetchImpl(url, {
      headers: { accept: "application/json", "user-agent": "EcoRadar/1.0" },
      cache: "no-store",
      signal: timeoutSignal,
    });
  } catch (error) {
    if (error instanceof UpstreamSourceError) throw error;
    const timeout =
      error?.name === "AbortError" ||
      error?.name === "TimeoutError" ||
      String(error?.message || "").toLowerCase().includes("timeout") ||
      String(error?.message || "").toLowerCase().includes("temps d'espera");
    throw new UpstreamSourceError(
      timeout
        ? `${provider}: temps d'espera esgotat després de ${UPSTREAM_TIMEOUT_MS / 1000} segons`
        : `${provider}: error de xarxa — ${error instanceof Error ? error.message : String(error)}`,
      {
        code: timeout ? "upstream_timeout" : "upstream_network_error",
        provider,
        upstream_url: String(url),
      },
    );
  }

  const contentType = response.headers.get("content-type") || "no declarat";
  let text;
  try {
    text = await response.text();
  } catch (error) {
    throw new UpstreamSourceError(
      `${provider}: no s'ha pogut llegir el cos de la resposta — ${
        error instanceof Error ? error.message : String(error)
      }`,
      {
        code: "upstream_body_unreadable",
        provider,
        upstream_url: String(url),
        upstream_http_status: response.status,
        upstream_content_type: contentType,
      },
    );
  }

  if (!response.ok) {
    const excerpt = text.replace(/\s+/g, " ").trim().slice(0, 240);
    throw new UpstreamSourceError(
      `${provider}: HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ""}${
        excerpt ? ` — ${excerpt}` : ""
      }`,
      {
        code: "upstream_http_error",
        provider,
        upstream_url: String(url),
        upstream_http_status: response.status,
        upstream_content_type: contentType,
      },
    );
  }
  if (!contentType.toLowerCase().includes("application/json")) {
    throw new UpstreamSourceError(
      `${provider}: format inesperat; s'esperava JSON i s'ha rebut ${contentType}`,
      {
        code: "upstream_content_type_error",
        provider,
        upstream_url: String(url),
        upstream_http_status: response.status,
        upstream_content_type: contentType,
      },
    );
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new UpstreamSourceError(
      `${provider}: JSON invàlid — ${error instanceof Error ? error.message : String(error)}`,
      {
        code: "upstream_invalid_json",
        provider,
        upstream_url: String(url),
        upstream_http_status: response.status,
        upstream_content_type: contentType,
      },
    );
  }
}

function xemaUrl(config) {
  const variableClause = config.variables
    .map((code) => `codi_variable='${code}'`)
    .join(" OR ");
  const params = new URLSearchParams({
    $limit: config.variables[0] === "35" ? "200" : "20",
    $order: "data_lectura DESC",
    $where: `codi_estacio='CD' AND (${variableClause})`,
  });
  return `${XEMA_ENDPOINT}?${params.toString()}`;
}

function latestByVariable(records) {
  const latest = new Map();
  for (const row of records) {
    const code = String(row.codi_variable || "");
    if (!code || latest.has(code)) continue;
    const number = Number(row.valor_lectura);
    if (!Number.isFinite(number) || !row.data_lectura) continue;
    latest.set(code, {
      value: number,
      dataAt: isoInstant(row.data_lectura, "XEMA data_lectura"),
      state: String(row.codi_estat || ""),
    });
  }
  return latest;
}

function xemaQuality(...items) {
  return items.every((item) => item?.state === "V")
    ? "validada"
    : "provisional XEMA";
}

function buildXemaReading(reading, records, checkedAt) {
  const latest = latestByVariable(records);
  const source = "Meteocat XEMA · estació CD (la Seu d'Urgell - Bellestar)";
  if (reading === "air_temperature") {
    const item = latest.get("32");
    if (!item) throw new Error("XEMA no ha retornat la variable 32");
    return readingRecord({
      label: "Temperatura de l'aire",
      valueNumeric: item.value,
      decimals: 1,
      unit: "°C",
      source,
      dataAt: item.dataAt,
      checkedAt,
      quality: xemaQuality(item),
      note: "Observació puntual en garita meteorològica; no és temperatura de cada carrer.",
    });
  }
  if (reading === "relative_humidity") {
    const item = latest.get("33");
    if (!item) throw new Error("XEMA no ha retornat la variable 33");
    return readingRecord({
      label: "Humitat relativa",
      valueNumeric: item.value,
      decimals: 0,
      unit: "%",
      source,
      dataAt: item.dataAt,
      checkedAt,
      quality: xemaQuality(item),
      note: "Observació puntual; no és una malla urbana d'humitat.",
    });
  }
  if (reading === "wind") {
    const wind = latest.get("30");
    if (!wind) throw new Error("XEMA no ha retornat la variable 30");
    const gust = latest.get("31");
    const direction = latest.get("50");
    const details = [];
    if (gust) details.push(`ratxa ${formatNumber(gust.value * 3.6, 1)} km/h`);
    if (direction) details.push(`direcció ${formatNumber(direction.value, 0)}°`);
    return readingRecord({
      label: "Vent",
      valueNumeric: Math.round(wind.value * 36) / 10,
      decimals: 1,
      unit: "km/h",
      source,
      dataAt: wind.dataAt,
      checkedAt,
      quality: xemaQuality(wind),
      note:
        `${details.length ? `${details.join(" · ")}. ` : ""}` +
        "Mesura puntual a 10 m; no és un camp de vent urbà.",
    });
  }
  if (reading === "precipitation") {
    const validRows = records
      .filter((row) => String(row.codi_variable) === "35")
      .map((row) => ({
        value: Number(row.valor_lectura),
        dataAt: isoInstant(row.data_lectura, "XEMA data_lectura"),
        state: String(row.codi_estat || ""),
      }))
      .filter((row) => Number.isFinite(row.value))
      .sort((a, b) => new Date(a.dataAt) - new Date(b.dataAt));
    if (!validRows.length) throw new Error("XEMA no ha retornat la variable 35");
    const latestDate = madridDate(validRows.at(-1).dataAt);
    const dayRows = validRows.filter((row) => madridDate(row.dataAt) === latestDate);
    const total = dayRows.reduce((sum, row) => sum + row.value, 0);
    const latestRow = dayRows.at(-1);
    return readingRecord({
      label: "Precipitació",
      valueNumeric: Math.round(total * 10) / 10,
      decimals: 1,
      unit: "mm",
      source,
      dataAt: latestRow.dataAt,
      checkedAt,
      quality: xemaQuality(latestRow),
      note:
        `Acumulació dels períodes XEMA disponibles del ${latestDate}; ` +
        "pot ser parcial si el dia encara no ha acabat.",
    });
  }
  throw new Error(`Lectura XEMA no admesa: ${reading}`);
}

function decodeHtml(value) {
  return value
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&amp;", "&")
    .replaceAll("&nbsp;", " ");
}

function numericFromLabel(value) {
  const match = value.match(/[-+]?\d+(?:[.,]\d+)?/);
  if (!match) throw new Error(`Valor CHE sense número: ${value}`);
  return Number(match[0].replace(",", "."));
}

export function madridLocalToUtc(label) {
  const match = String(label).match(
    /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})$/,
  );
  if (!match) throw new Error(`Data CHE no reconeguda: ${label}`);
  const [, day, month, year, hour, minute] = match;
  const wallClock = Date.UTC(+year, +month - 1, +day, +hour, +minute);
  const guess = new Date(wallClock);
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: MADRID_TZ,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(guess)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, Number(part.value)]),
  );
  const representedAsUtc = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
  );
  return new Date(wallClock - (representedAsUtc - wallClock)).toISOString();
}

export function parseCheCurrent(payload, config, checkedAt) {
  const table = payload?.VALORES_ACTUALES;
  if (typeof table !== "string" || !table.trim()) {
    throw new Error("La resposta CHE no conté VALORES_ACTUALES");
  }
  const rows = table.match(/<tr\b[\s\S]*?<\/tr>/gi) || [];
  const row = rows.find(
    (candidate) =>
      candidate.includes(config.signal) &&
      /aria-label=["']Señal Caudal\s/i.test(candidate),
  );
  if (!row) throw new Error(`No s'ha trobat el senyal ${config.signal}`);
  const labels = [...row.matchAll(/aria-label=["']([^"']+)["']/gi)].map((match) =>
    decodeHtml(match[1]),
  );
  const valueLabel = labels.find((label) => label.startsWith("Valor "));
  const dateLabel = labels.find((label) => label.startsWith("Fecha "));
  if (!valueLabel || !dateLabel) throw new Error("Fila CHE incompleta");
  const value = numericFromLabel(valueLabel.slice(6));
  const dataAt = madridLocalToUtc(dateLabel.slice(6));
  return readingRecord({
    label: `Cabal del ${config.river}`,
    valueNumeric: value,
    decimals: 2,
    unit: "m³/s",
    source: `CHE · SAIH Ebre · estació ${config.station} (${config.river})`,
    dataAt,
    checkedAt,
    quality: "dada provisional SAIH",
    note:
      "Observació puntual a l'estació d'aforament. Dada de temps real provisional " +
      "i subjecta a revisió de la CHE; no és una alerta d'inundació ni representa tot el tram fluvial.",
  });
}

export async function refreshReading({
  reading,
  fetchImpl = DEFAULT_FETCH,
  checkedAt = new Date(),
}) {
  const config = REFRESHABLE_READINGS[reading];
  if (!config) throw new Error("reading_not_refreshable");
  let data;
  if (config.provider === "xema") {
    const records = await fetchJson(xemaUrl(config), fetchImpl, "Meteocat XEMA");
    if (!Array.isArray(records)) throw new Error("Resposta XEMA no tabular");
    data = buildXemaReading(reading, records, checkedAt);
  } else {
    const url = `${CHE_ENDPOINT}?${new URLSearchParams({ estacion: config.station })}`;
    const cheFetch =
      fetchImpl === DEFAULT_FETCH
        ? (_url, options) => fetchCheFromOfficialMirrors(config.station, options)
        : fetchImpl;
    data = parseCheCurrent(
      await fetchJson(url, cheFetch, "CHE/SAIH Ebre"),
      config,
      checkedAt,
    );
  }
  return {
    schema_version: "1.0",
    reading_key: reading,
    checked_at_utc: isoInstant(checkedAt, "checked_at_utc"),
    source_frequency_code: config.frequency_code,
    source_frequency_label: config.frequency_label,
    source_status: {
      provider: config.provider === "che" ? "CHE/SAIH Ebre" : "Meteocat XEMA",
      endpoint:
        config.provider === "che"
          ? `${CHE_ENDPOINT}?${new URLSearchParams({ estacion: config.station })}`
          : xemaUrl(config),
      official_url: config.official_url || null,
      access_mode: "Funció Netlify intermediària d'EcoRadar",
    },
    reading: data,
  };
}

export default async function handler(request) {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: JSON_HEADERS });
  }
  if (request.method !== "GET") {
    return jsonResponse({ error: "method_not_allowed" }, 405);
  }
  const reading = new URL(request.url).searchParams.get("reading") || "";
  if (!REFRESHABLE_READINGS[reading]) {
    return jsonResponse(
      {
        error: "reading_not_refreshable",
        detail:
          "El botó només està habilitat per a fonts oficials amb actualització inferior a 24 hores.",
      },
      400,
    );
  }
  try {
    return jsonResponse(await refreshReading({ reading }));
  } catch (error) {
    return jsonResponse(
      {
        error: "source_refresh_failed",
        reading_key: reading,
        checked_at_utc: new Date().toISOString(),
        detail: error instanceof Error ? error.message : String(error),
        source_error:
          error instanceof UpstreamSourceError ? error.metadata : null,
      },
      502,
    );
  }
}
