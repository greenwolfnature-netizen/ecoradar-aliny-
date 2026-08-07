# EcoRadar fire module functional brief

Status: `blocked`

Last checked: 2026-07-07

## Gate

This brief is intentionally not activated for implementation.

The EcoRadar fire module depends on a verified official fire data source. The IncendisCAT-equivalent source is not yet proven, and IncendisCAT itself must not be used as a data source. No connector, ecological analysis, scoring, dashboard, or automated module logic should be implemented until the Data Engine source document is updated from `blocked` to `verified`.

Source gate document:

- `docs/data_sources/fire/incendiscat-official-source.md`

Operational source candidate added on 2026-07-07:

- Bombers ArcGIS viewer `ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW`, status `pending_verification`.
- Use allowed in interim artifacts only as current operational context, not as historical burned area, ecological recovery evidence, or probability input.

Editorial specification, also gated:

- `docs/modules/fire/memoria-del-foc-editorial-spec.md`

## Future objective

Once the official wildfire source is verified, the fire module should help EcoRadar describe recent and historical wildfire pressure on ecological systems in Catalonia, separating operational incident tracking from ecological impact analysis.

## Future ecological questions

- Where have forest fires occurred, and which habitats or protected areas overlap with affected areas?
- How much forest, shrubland, grassland, agricultural, or non-forest surface is affected by each validated event?
- Which municipalities, comarques, watersheds, protected areas, or ecological corridors show repeated fire exposure?
- Which fires are only operational incidents and which have validated burned-area evidence?
- How should provisional incident records be distinguished from validated post-fire cartography?

## Future data needs

- Verified official active-incident source, if EcoRadar includes near-real-time operational fires.
- Verified official burned-area/perimeter source for ecological impact analysis.
- Administrative boundaries for municipalities and comarques.
- Protected areas and habitat layers.
- Land-cover or vegetation layers.
- Optional meteorological context only after the Analysis Engine defines how it will be used.

## Future expected outputs

- Data source inventory entries with source status and metadata.
- Normalized DataFrame or GeoDataFrame from official connectors only.
- Clear separation between:
  - active operational incidents,
  - provisional affected-area tables,
  - validated burned-area/perimeter products.
- Fire event summary tables.
- Spatial overlays for ecological modules only after the Analysis Engine exists.
- A future A4 vertical PDF and PNG preview for the "Memoria del foc" sheet, only after verified data are available and quantified.

## Methodological limits

- Active incident feeds are not equivalent to validated burned-area datasets.
- Satellite hot spots are detections, not official burned-area validation.
- EFFIS and NASA FIRMS can be useful context, but they are not proof of the exact official source used by IncendisCAT.
- Provisional current-year datasets must be labelled as provisional and should not be mixed with validated historical datasets without explicit flags.
- Records without coordinates or perimeters cannot support fine-scale ecological overlay without additional verified geometry.

## Analysis Engine dependencies

The future Analysis Engine must define:

- how provisional and validated fire records are separated,
- how duplicate events across sources are reconciled,
- how spatial uncertainty is represented,
- how burned area is intersected with habitats/protected areas,
- how temporal windows are selected,
- how outputs are labelled when source data is incomplete or provisional.

## Implementation rule

Do not implement this module while the source status is `blocked`.
