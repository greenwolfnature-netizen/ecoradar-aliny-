# Connector Contract

This is a design contract, not an implementation.

`AGENTS.md` blocks connector implementation until all required official sources for the target domain are identified, verified, and documented. For that reason, requested folders such as `/connectors/clima`, `/connectors/aigua`, `/connectors/incendis`, and `/connectors/copernicus_indices` should not be created yet.

When a source is marked `verified`, each connector must do only four things:

1. Connect to the official source.
2. Download the source data without duplicating previous downloads.
3. Normalize source fields and metadata.
4. Return a `GeoDataFrame` or `DataFrame`.

Connectors must not calculate EcoRadar indicators. Indicators such as climate index, drought index, hydrological index, vegetation stress, fire recurrence, slope, aspect, potential moisture, NDVI, NDMI, NDWI, SPI, and vulnerability belong in the Analysis Engine.

## Required Connector Metadata

Every downloaded dataset must store:

- download date
- source id from `docs/data_sources/sources_inventory.yml`
- official source URL
- source organization
- resolution or scale
- coordinate reference system
- data quality notes
- license
- raw output path
- normalized output path
- checksum or stable source query fingerprint

## Output Policy

Requested file formats are valid as export targets, but they should not force every source into every format. Use the format that preserves the source correctly:

- tabular observations: raw JSON/CSV, normalized CSV/GeoPackage when geometry exists
- vector geodata: GeoPackage preferred, raw source format preserved
- raster geodata: GeoTIFF/COG preferred, raw source format preserved
- metadata: JSON sidecar for every download

## No Duplicate Downloads

Before downloading, a connector should compute a stable fingerprint from:

- source id
- endpoint URL
- query parameters
- area of interest hash
- temporal range
- requested resolution/product

If the fingerprint already exists and the source update frequency has not elapsed, the connector must reuse the cached raw data.

## Proposed Future Modules

These modules are intentionally deferred until source statuses allow implementation:

- `connectors/clima`: Meteocat and AEMET, currently `requires_credentials`.
- `connectors/aigua`: ACA verified boundary layers can start once selected; current drought-state endpoint remains `pending_verification`.
- `connectors/incendis`: burned-area perimeters are `verified`; active IncendisCat upstream remains `blocked`.
- `connectors/copernicus_indices`: Sentinel-2 source requires credentials; NDVI/NDMI/NDWI should be derived outside connectors.

