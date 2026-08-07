# connector_incendis_combustible_resiliencia

Status: `source_gated_analysis_deferred`

This request describes a multi-source fire-resilience analysis stack, not a
single connector. Under `AGENTS.md`, connectors may download and normalize one
official source, but they must not calculate risk, resilience, continuity,
mosaic, recurrence, aspect, slope or prioritization.

## Source Gate

| Input | Source id | Status | Decision |
| --- | --- | --- | --- |
| Official burned-area history | `fires_burned_areas_v1r1` | `verified` | A dedicated burned-area connector can be implemented. |
| Active IncendisCat-equivalent source | `fires_active_bombers_actions` | `blocked` | Do not implement until the exact official IncendisCat upstream is proven. |
| EFFIS | `fires_effis` | `pending_verification` | Do not implement until API/download endpoint and license are verified. |
| Forest structure/fuel cartography | `forest_structure_cartography` | `pending_verification` | Do not implement until exact official dataset is selected. |
| Land cover | `land_cover_icgc_cobertes_sol` | `verified` | Existing connector output can feed later analysis. |
| Habitats | `biodiversity_habitats_terrestres_v3` | `verified` | Existing connector output can feed later analysis. |
| Sentinel NDVI/NDMI/NDWI | `copernicus_sentinel2_indices_source` | `requires_credentials` | Connector exists but is blocked until credentials are configured. |
| LST | `copernicus_lst_source` | `requires_credentials` | Not enabled until collection/band mapping is configured and credentials are available. |
| DEM | `terrain_icgc_dem` | `verified` | A DEM connector can be implemented; slope/aspect are analysis products. |
| Tracks/access network | `recreational_osm_overpass` | `verified` | OSM connector can normalize paths/access features. |
| Hydrology | `hydrology_network` | `pending_verification` | Do not implement until exact official layer is documented. |
| Electricity network | `electricity_network_fire_context` | `pending_verification` | Do not implement until official source and constraints are documented. |

## Allowed Connector Work

The following are valid connector-level tasks once requested source by source:

- download official burned-area perimeters and normalize attributes
- download DEM tiles and normalize raster metadata
- download OSM tracks/access features and normalize tags
- reuse existing land-cover and habitats connector outputs
- run Copernicus teledetection only when credentials are available

Each connector must store raw data, normalized data and metadata separately.

## Analysis Engine Work, Not Connector Work

These layers are derived analysis products and must be implemented after source
layers exist:

### Topography

- slope
- aspect
- slope-continuity or uninterrupted slope corridors

### Vegetation and Fuel Structure

- forest continuity
- discontinuities and breaks
- large continuous forest/shrub masses
- agroforestry mosaic
- grassland/pasture presence
- agricultural openings

### Moisture

- NDMI
- NDWI
- LST/thermal stress
- proximity to streams or water points

### Accessibility

- tracks and paths
- access points
- water points
- operational accessibility classes

### Fire History

- burned-area overlap
- time since last fire
- recurrence

## Explicit Non-Goals

This connector must not output:

- final fire risk
- final resilience score
- management priority score
- ecological recommendation
- biodiversity compatibility assessment

Those belong to the EcoRadar Analysis Engine after all required source gates are
open and the uncertainty of each input is documented.

## Future Output Contract

When source gates are open, the fire-resilience data stack should produce:

- `projectes/<name>/raw/incendis_combustible/`
- `projectes/<name>/processed/incendis_combustible_sources.gpkg`
- `projectes/<name>/processed/incendis_combustible_rasters/`
- `projectes/<name>/indicators/incendis_combustible_source_summary.csv`
- `projectes/<name>/metadata/incendis_combustible_metadata.json`

Analysis products should be written separately, for example:

- `slope.tif`
- `aspect.tif`
- `forest_continuity.tif`
- `agroforestry_mosaic.tif`
- `distance_to_access.tif`
- `distance_to_water.tif`
- `fire_recurrence.gpkg`

These future layers must be labelled as derived, with source dependencies and
limitations in metadata.

## Interpretation Rule

EcoRadar should not say "this place has high risk" from connector data alone.
The desired later questions are:

- where is mosaic missing?
- where is forest continuity excessive?
- where are climatic refuges likely?
- where are vulnerable habitats present?
- where could management have ecological return?
- where could intervention harm sensitive species?

Answering those questions requires the Analysis Engine, field validation and
biodiversity constraints, not only raw connector outputs.
