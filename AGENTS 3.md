# EcoRadar Project Rules

## Data Engine First

Do not implement any connector until all official sources for EcoRadar have been identified, verified, and documented.

Required order:

1. Identify the official source for every EcoRadar data domain.
2. Verify each source against the responsible official body.
3. Document each source before implementation.
4. Mark each source status as `verified`, `requires_credentials`, `service_unavailable`, `pending_verification`, or `blocked`.
5. Only after all required sources are documented, implement connectors.

## Connector Rules

Each connector must have one responsibility only:

- Connect to the official source.
- Download the data.
- Normalize the data.
- Return a `GeoDataFrame` or `DataFrame`.

Connectors must not perform analysis.

## Required Source Metadata

Every source must be documented with:

- Source name.
- Responsible organization.
- Official URL.
- Service type: API, WMS, WFS, WMTS, GeoJSON, SHP, etc.
- Data format.
- Coordinate reference system.
- Available variables.
- Update frequency.
- Usage license.
- Example connection.
- Connector status.

## EcoRadar Build Order

1. Data source inventory.
2. Data source verification.
3. Technical source documentation.
4. Data Engine connectors.
5. Analysis Engine.
6. EcoRadar modules: fires, biodiversity, connectivity, drought, public use, and others.

## Fire Data Rule

For wildfire data, identify and document the exact official source used by IncendisCat before implementing any connector.

Do not use IncendisCat itself as a data source.

## Daily Interactive Readings

Every interactive EcoRadar must run one automated daily check of every
updateable reading, including current fire danger, meteorology, daily shade,
air-quality context, Landsat surface temperature, and Sentinel-2 NDVI, NDMI,
and albedo.

- Set one `ECORADAR_CHECKED_AT_UTC` value per complete daily run and propagate
  it to `daily_readings`, `daily_history`, and `current_fire_danger`.
- Update `checked_at_utc` and the source-check status on every run, even when a
  source has not published a new observation.
- Preserve each source's real observation or acquisition timestamp. Never
  present the daily check time as the data timestamp.
- Query every configured official source daily, but only recalculate
  source-dependent products when a new valid source observation exists.
- Publish the refreshed records and viewer after the checks, then verify the
  public API and deployed interface.
- Treat packaged JSON as fallback only. The interactive viewer must prefer a
  remote, current snapshot and visibly identify fallback use.
- Apply this contract to Alinyà, la Seu d'Urgell, and every future EcoRadar
  generated from the project template.

## Frozen Product References

The frozen EcoRadar Fitxa v1 reference is documented at:

- `ECORADAR_FITXA_V1.md`
- `docs/product/releases/fitxa_ecoradar_v1/`
- `projectes/_TEMPLATE_ECORADAR_V1/`

Before generating or adapting a Fitxa EcoRadar for a new study area, read `ECORADAR_FITXA_V1.md` and reuse the frozen v1 structure, commands, product criteria, and template. Alinya is the reference case for v1.

For client-facing outputs, the Fitxa EcoRadar is the executive quality reference. Generate and validate the Fitxa first. The Integrated Ecological Diagnosis Report must then justify the Fitxa's main claims with evidence, ecological processes, management implications, future scenarios, and decisions. The report is the technical demonstration of the Fitxa, not the other way around.
