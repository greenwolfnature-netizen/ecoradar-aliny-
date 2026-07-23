# EcoRadar 0.1 Scope

EcoRadar 0.1 should be the smallest useful version of the Central Engine.

It should not try to implement the full platform at once.

## Included Workflows

1. Study-area intake.
2. Project folder creation.
3. Project GeoPackage schema creation.
4. Source registry checks.
5. Fieldwork import contract.
6. Indicator table contract.
7. Report summary contract.

## Requested 0.1 Data Families

| Family | Requested source | Current gate |
| --- | --- | --- |
| Study area | User-provided boundary | Allowed |
| Land cover | ICGC / MCSC | Needs source inventory entry before connector |
| Habitats | HIC / habitats | Partly `verified` |
| Sentinel NDVI/NDMI/NDWI | Copernicus Data Space | `requires_credentials`; indices are analysis products |
| Fauna | GBIF / iNaturalist | Needs source inventory entry before connector |
| Human pressure | OpenStreetMap / Overpass | Needs source inventory entry before connector |
| Field form | EcoRadar own data | Allowed as local import contract |
| Indicators | Derived from available normalized tables | Analysis Engine, not connector |
| Summary report | Derived from indicators and recommendations | Report Engine |

## What 0.1 Can Build First

These parts do not require external connector implementation:

- project manifest
- folder structure
- study-area table contract
- field-observation import schema
- indicator schema
- recommendation schema
- source-gate registry
- report skeleton

## What 0.1 Must Not Build Yet

Do not implement:

- real connectors for sources not marked `verified`
- Sentinel-derived NDVI/NDMI/NDWI calculations before credentialed source access is documented
- climate scoring while Meteocat/AEMET are `requires_credentials`
- active-fire connector while the IncendisCAT upstream remains `blocked`
- one single global EcoRadar score

## First Functional Milestone

The first functional milestone should be:

1. Create a project from a study-area boundary.
2. Store the area in the project GeoPackage.
3. Import a fieldwork CSV or GeoPackage.
4. Store field observations in the normalized schema.
5. Create empty indicator and recommendation tables with metadata.
6. Produce a basic project manifest that lists missing source gates.

This milestone is useful because it lets EcoRadar organize field and project data immediately, while public-source connectors remain properly gated.

