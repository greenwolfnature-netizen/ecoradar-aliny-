# Informe d'execució EcoRadar

Projecte: `Alinya`
Generat: `2026-09-09T11:31:16+00:00`
Estat: `aborted`
Temps total: `0.046` segons

## Mòduls executats

| Pas | Mòdul | Estat | Temps (s) | Sortides | Error |
|---:|---|---|---:|---:|---|
| 1 | Carregar l'àrea d'estudi | ok | 0.008 | 1 |  |
| 2 | Executar el Data Source Manager | ok | 0.004 | 4 |  |
| 3 | Validar totes les fonts | ok | 0.01 | 3 |  |
| 4 | Executar els connectors disponibles | failed | 0.024 | 0 | RuntimeError: Connectors without usable outputs: connector_copernicus_teledeteccio: EcoRadar cannot continue without mandatory Copernicus Sentinel outputs (NDVI, NDMI, NDWI, NBR and LST/equivalent): missing outputs: processed/teledeteccio/ndwi.tif, processed/teledeteccio/nbr.tif, processed/teledeteccio/lst.tif, maps/teledeteccio/ndvi.png, maps/teledeteccio/ndmi.png, maps/teledeteccio/ndwi.png, maps/teledeteccio/nbr.png, maps/teledeteccio/lst.png, indicators/teledeteccio_resum.csv, metadata/teledeteccio_stats.json, metadata/teledeteccio_percentiles.json, metadata/teledeteccio_classification.json, metadata/teledeteccio_ecological_summary.json; missing summary rows: ndvi, ndmi, ndwi, nbr, lst; validation status: blocked_requires_credentials. |

## Fonts

- Fonts utilitzades o disponibles: `18`
- Fonts fallides: `0`

## Indicadors calculats

| Codi | Nom | Estat | Confiança | Valor |
|---|---|---|---|---:|

## Recomanacions generades

| ID | Grup | Prioritat | Títol |
|---|---|---:|---|

## Fitxers creats

- `projectes/Alinya/metadata/connectors_status_report.json`
- `projectes/Alinya/metadata/data_availability_report.json`
- `projectes/Alinya/metadata/indicators_completeness_report.json`
- `projectes/Alinya/reports/data_availability_report.md`

## Errors detectats

- `Executar els connectors disponibles`: RuntimeError: Connectors without usable outputs: connector_copernicus_teledeteccio: EcoRadar cannot continue without mandatory Copernicus Sentinel outputs (NDVI, NDMI, NDWI, NBR and LST/equivalent): missing outputs: processed/teledeteccio/ndwi.tif, processed/teledeteccio/nbr.tif, processed/teledeteccio/lst.tif, maps/teledeteccio/ndvi.png, maps/teledeteccio/ndmi.png, maps/teledeteccio/ndwi.png, maps/teledeteccio/nbr.png, maps/teledeteccio/lst.png, indicators/teledeteccio_resum.csv, metadata/teledeteccio_stats.json, metadata/teledeteccio_percentiles.json, metadata/teledeteccio_classification.json, metadata/teledeteccio_ecological_summary.json; missing summary rows: ndvi, ndmi, ndwi, nbr, lst; validation status: blocked_requires_credentials.
