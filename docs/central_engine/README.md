# EcoRadar Central Engine

Status: `design_ready_source_gated`

The Central Engine coordinates EcoRadar projects from a single study-area input to normalized data, indicators, reports, and prioritized management recommendations.

This is not connector implementation. The engine remains source-gated by `AGENTS.md`: a connector can only be implemented for sources marked `verified` in `docs/data_sources/sources_inventory.yml`.

## Goal

Given one study area, EcoRadar should:

1. Validate and store the study-area input.
2. Build the project folder structure.
3. Run only allowed source connectors.
4. Preserve raw data and normalized outputs.
5. Import fieldwork data.
6. Populate a project GeoPackage.
7. Calculate indicators only after required source layers exist.
8. Generate maps, tables, reports, and prioritized recommendations.

## Phase 1: Single Input

Required user fields:

- `site_name`
- `municipality`
- `comarca`
- `study_area_boundary`
- `space_type`
- `diagnostic_objective`

Allowed boundary input formats:

- GeoJSON
- SHP
- GeoPackage
- polygon drawn on a map, exported internally to GeoJSON before processing

Allowed space types:

- `natural_protected`
- `forest`
- `agricultural`
- `periurban`
- `urban_green`
- `riparian`
- `dryland`
- `mixed`

Allowed diagnostic objectives:

- `biodiversity`
- `fires`
- `restoration`
- `public_use`
- `annual_monitoring`
- `general_planning`

## Phase 2: Connector Registry

Requested connector families:

- `cartografia`
- `cobertes_sol`
- `habitats`
- `teledeteccio`
- `fauna`
- `clima`
- `aigua`
- `incendis`
- `pressio_humana`
- `dades_camp`

Connector execution rule:

1. Read the source id from the registry.
2. Check the source status in `sources_inventory.yml`.
3. Refuse execution unless status is `verified`.
4. Connect, download, normalize, and return a `DataFrame` or `GeoDataFrame`.
5. Never calculate indicators inside the connector.

## Phase 3: Project Structure

The concrete folder template is available at:

- `ecoradar_projectes/_TEMPLATE`

For a real project, copy the template to:

```text
ecoradar_projectes/<site_slug>
```

The project slug should be lowercase ASCII, with spaces replaced by hyphens.

## Phase 4: Database

Preferred format for EcoRadar 0.1:

- one GeoPackage per project

Future growth path:

- SQLite for non-spatial local workflows
- PostGIS for multi-project or collaborative deployments

Logical schema:

- `docs/central_engine/database_schema.sql`

## Phase 5: Indicators

Indicators must include:

- raw value
- normalized value from 0 to 100
- level
- confidence
- source mode
- linked recommendation

EcoRadar must not collapse the result into one single score. It should produce management profiles:

- biodiversity
- connectivity
- vegetation condition
- human pressure
- fire risk
- restoration potential
- climate vulnerability

## Phase 6: Field Data

Field observations are first-class inputs. They can confirm, correct, or enrich public data, but they must remain traceable as field-derived records.

Minimum fields:

- date
- observer
- coordinates
- observation type
- species or element
- habitat
- certainty
- associated file
- related indicator
- technical comment

## Phase 7: Outputs

The Central Engine should eventually generate:

- GeoPackage maps/layers
- QGIS-ready layers
- CSV tables
- charts
- summary sheet
- technical report
- executive report
- prioritized recommendations

## EcoRadar 0.1 Gate

EcoRadar 0.1 is defined in:

- `docs/central_engine/ecoradar_0_1_scope.md`

At the current source state, only source-gated planning and project initialization are allowed. Connectors for GBIF, iNaturalist, OpenStreetMap, land cover, and Sentinel products still need complete source documentation before implementation.

