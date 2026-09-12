# Data Availability Report

Projecte: `projectes/Alinya`
Generat: `2026-09-12T17:27:59+00:00`

## Resum

| Estat | Nombre |
| --- | ---: |
| consultada_correctament | 18 |
| legalment_condicionada | 1 |
| manual_pendent | 8 |
| parcial | 2 |
| requereix_credencials | 1 |

## Fonts per bloc

| Bloc | Fonts | Estat |
| --- | ---: | --- |
| Àrea d'estudi | 1 | consultada_correctament: 1 |
| Cartografia base ICGC | 2 | consultada_correctament: 2 |
| Cobertes del sòl ICGC / MCSC | 2 | consultada_correctament: 1, manual_pendent: 1 |
| Hàbitats Generalitat / HIC | 2 | consultada_correctament: 2 |
| SIGPAC i mapa de cultius | 2 | manual_pendent: 2 |
| Copernicus / Sentinel | 5 | consultada_correctament: 3, parcial: 2 |
| DEM / MDT | 1 | consultada_correctament: 1 |
| Hidrologia | 1 | consultada_correctament: 1 |
| Connectivitat ecològica | 1 | consultada_correctament: 1 |
| Biodiversitat | 4 | consultada_correctament: 2, manual_pendent: 2 |
| Pressió humana | 2 | consultada_correctament: 1, legalment_condicionada: 1 |
| Incendis | 3 | consultada_correctament: 2, manual_pendent: 1 |
| Clima | 3 | consultada_correctament: 1, manual_pendent: 1, requereix_credencials: 1 |
| Treball de camp | 1 | manual_pendent: 1 |

## Fonts consultades correctament

- **Àrea d'estudi / Límit de l'àrea d'estudi**: `consultada_correctament`; connector `ecoradar.core.study_area`; indicadors CORE_01, CORE_02, CORE_04, CORE_05, CORE_08, CORE_09, CORE_10, CORE_11, CORE_12.
- **Cartografia base ICGC / Cartografia base i ortofoto ICGC**: `consultada_correctament`; connector `pending_base_cartography_icgc`; indicadors CORE_01, CORE_08, CORE_12.
- **Cartografia base ICGC / Ortofoto ICGC**: `consultada_correctament`; connector `pending_base_cartography_icgc`; indicadors CORE_01, CORE_08, CORE_12.
- **Cobertes del sòl ICGC / MCSC / ICGC - Cobertes del sòl de Catalunya**: `consultada_correctament`; connector `connector_icgc_cobertes_sol`; indicadors CORE_01, CORE_04, CORE_05, CORE_08, CORE_09, CORE_11, CORE_12.
- **Hàbitats Generalitat / HIC / Cartografia dels hàbitats terrestres v3**: `consultada_correctament`; connector `connector_habitats`; indicadors CORE_02, CORE_06, CORE_08, CORE_11, CORE_12.
- **Hàbitats Generalitat / HIC / Hàbitats d'Interès Comunitari v2**: `consultada_correctament`; connector `connector_habitats`; indicadors CORE_02, CORE_12.
- **Copernicus / Sentinel / Copernicus Data Space Sentinel-2 NDVI**: `consultada_correctament`; connector `connector_copernicus_teledeteccio`; indicadors CORE_03, CORE_04, CORE_11, CORE_12.
- **Copernicus / Sentinel / Copernicus Data Space Sentinel-2 NDMI**: `consultada_correctament`; connector `connector_copernicus_teledeteccio`; indicadors CORE_03, CORE_04, CORE_05, CORE_09, CORE_11, CORE_12.
- **Copernicus / Sentinel / Temperatura superficial detallada Landsat/ECOSTRESS**: `consultada_correctament`; connector `connector_detailed_surface_temperature`; indicadors CORE_03, CORE_04, CORE_05, CORE_09, CORE_11, CORE_12.
- **DEM / MDT / ICGC Model d'elevacions del terreny**: `consultada_correctament`; connector `connector_icgc_dem_mdt`; indicadors CORE_04, CORE_05, CORE_08, CORE_09, CORE_10, CORE_11, CORE_12.
- **Hidrologia / ACA / xarxa hidrogràfica, masses d'aigua i punts d'aigua**: `consultada_correctament`; connector `connector_aca_hidrologia`; indicadors CORE_04, CORE_05, CORE_08, CORE_10, CORE_11, CORE_12.
- **Connectivitat ecològica / Infraestructura Verda / Connectivitat ecològica**: `consultada_correctament`; connector `connector_connectivitat_ecologica`; indicadors CORE_01, CORE_08, CORE_10, CORE_11, CORE_12.
- **Biodiversitat / GBIF Occurrence API**: `consultada_correctament`; connector `connector_biodiversitat`; indicadors CORE_06, CORE_11, CORE_12.
- **Biodiversitat / iNaturalist Observations API**: `consultada_correctament`; connector `connector_biodiversitat`; indicadors CORE_06, CORE_11, CORE_12.
- **Pressió humana / OpenStreetMap / Overpass**: `consultada_correctament`; connector `connector_recreational_pressure_osm`; indicadors CORE_07, CORE_08, CORE_09, CORE_11, CORE_12.
- **Incendis / Superfícies afectades per incendis forestals**: `consultada_correctament`; connector `connector_incendis_historial`; indicadors CORE_09, CORE_11, CORE_12.
- **Incendis / EFFIS**: `consultada_correctament`; connector `connector_incendis_historial`; indicadors CORE_09, CORE_12.
- **Clima / Meteocat API**: `consultada_correctament`; connector `connector_meteocat_xema`; indicadors CORE_03, CORE_04, CORE_05, CORE_11, CORE_12.

## Fonts fallides, no implementades, amb credencials o manuals pendents

- **Cobertes del sòl ICGC / MCSC / MCSC - Mapa de Cobertes del Sòl de Catalunya**: `manual_pendent`; connector `pending_mcsc_connector`; indicadors CORE_01, CORE_08, CORE_09.
- **SIGPAC i mapa de cultius / SIGPAC Catalunya**: `manual_pendent`; connector `pending_sigpac_connector`; indicadors CORE_01, CORE_08, CORE_09, CORE_11, CORE_12.
- **SIGPAC i mapa de cultius / Mapa de cultius / DUN**: `manual_pendent`; connector `pending_dun_cultius_connector`; indicadors CORE_01, CORE_08, CORE_09, CORE_11, CORE_12.
- **Copernicus / Sentinel / Copernicus Data Space Sentinel-2 NDWI**: `parcial`; connector `connector_copernicus_teledeteccio`; indicadors CORE_03, CORE_10, CORE_11, CORE_12.
- **Copernicus / Sentinel / Copernicus Data Space Sentinel-2 NBR**: `parcial`; connector `connector_copernicus_teledeteccio`; indicadors CORE_03, CORE_09, CORE_11, CORE_12.
- **Biodiversitat / Banc de Dades de Biodiversitat de Catalunya**: `manual_pendent`; connector `pending_bdbc_connector`; indicadors CORE_06, CORE_12.
- **Biodiversitat / Dades pròpies de camp**: `manual_pendent`; connector `pending_fieldwork_importer`; indicadors CORE_02, CORE_06, CORE_07, CORE_10, CORE_11, CORE_12.
- **Pressió humana / Strava Global Heatmap**: `legalment_condicionada`; connector `blocked_strava_heatmap_connector`; indicadors CORE_07, CORE_08, CORE_12.
- **Incendis / Continuïtat forestal i combustible potencial**: `manual_pendent`; connector `pending_fuel_structure_connector`; indicadors CORE_09, CORE_11, CORE_12.
- **Clima / AEMET OpenData**: `requereix_credencials`; connector `pending_aemet_connector`; indicadors CORE_03, CORE_04, CORE_05, CORE_11, CORE_12.
- **Clima / SPEI Global Drought Monitor**: `manual_pendent`; connector `pending_spei_connector`; indicadors CORE_04, CORE_05, CORE_10, CORE_11, CORE_12.
- **Treball de camp / Microhàbitats, validació d'hàbitats, pressions reals i punts sensibles**: `manual_pendent`; connector `pending_fieldwork_importer`; indicadors CORE_02, CORE_06, CORE_07, CORE_10, CORE_11, CORE_12.

## Dades descarregades o disponibles localment

- `indicators/biodiversitat_resum.csv`
- `indicators/cobertes_sol_resum.csv`
- `indicators/connectivitat_resum.csv`
- `indicators/habitats_resum.csv`
- `indicators/hidrologia_resum.csv`
- `indicators/incendis_resum.csv`
- `indicators/recreational_pressure_resum.csv`
- `indicators/teledeteccio_satellite_layers.json`
- `indicators/teledeteccio_sentinel2.json`
- `maps/producte/mapa_base_alinya.png`
- `maps/producte/mapa_espai_alinya.png`
- `maps/teledeteccio/landsat_lst.webp`
- `maps/teledeteccio/ndmi.webp`
- `maps/teledeteccio/ndvi.webp`
- `metadata/biodiversitat_metadata.json`
- `metadata/cobertes_sol_metadata.json`
- `metadata/connectivitat_metadata.json`
- `metadata/current_surface_temperature.json`
- `metadata/habitats_metadata.json`
- `metadata/hidrologia_metadata.json`
- `metadata/incendis_metadata.json`
- `metadata/recreational_pressure_metadata.json`
- `metadata/study_area_metadata.json`
- `metadata/teledeteccio_metadata.json`
- `metadata/terrain_metadata.json`
- `processed/biodiversitat.gpkg`
- `processed/cobertes_sol.gpkg`
- `processed/connectivitat.gpkg`
- `processed/habitats.gpkg`
- `processed/hidrologia.gpkg`
- `processed/incendis.gpkg`
- `processed/landsat/landsat_lst.tif`
- `processed/recreational_pressure.gpkg`
- `processed/study_area.gpkg`
- `processed/teledeteccio/ndmi.tif`
- `processed/teledeteccio/ndvi.tif`
- `processed/terrain/aspect.tif`
- `processed/terrain/dem.tif`
- `processed/terrain/northness.tif`
- `processed/terrain/slope.tif`
- `processed/terrain/solana_obaga.tif`
- `raw/biodiversitat/gbif_raw.json`
- `raw/biodiversitat/inaturalist_raw.json`
- `raw/incendis/effis_drf_datasets.json`
- `raw/meteocat_xema/Y4_metadata.json`
- `raw/meteocat_xema/Y4_observations.csv`
- `raw/recreational_pressure/overpass_osm_raw.json`

## Indicadors afectats per dades mancants

| Indicador | Completesa | Estat | Confiança | Fonts mancants |
| --- | ---: | --- | --- | --- |
| CORE_01 | 100.0% | DISPONIBLE | alta | land_cover_mcsc, sigpac_catalunya, dun_cultius |
| CORE_02 | 100.0% | DISPONIBLE | alta | field_biodiversity, field_validation |
| CORE_03 | 83.3% | PARCIAL | alta | aemet |
| CORE_04 | 100.0% | DISPONIBLE | alta | aemet, spei |
| CORE_05 | 100.0% | DISPONIBLE | alta | aemet, spei |
| CORE_06 | 100.0% | DISPONIBLE | alta | bdbc, field_biodiversity, field_validation |
| CORE_07 | 100.0% | DISPONIBLE | alta | field_biodiversity, strava_heatmap, field_validation |
| CORE_08 | 100.0% | DISPONIBLE | alta | land_cover_mcsc, sigpac_catalunya, dun_cultius, strava_heatmap |
| CORE_09 | 83.3% | PARCIAL | alta | land_cover_mcsc, sigpac_catalunya, dun_cultius, fuel_continuity |
| CORE_10 | 90.0% | DISPONIBLE | alta | field_biodiversity, spei, field_validation |
| CORE_11 | 88.2% | PARCIAL | alta | sigpac_catalunya, dun_cultius, field_biodiversity, fuel_continuity, aemet, spei, field_validation |
| CORE_12 | 88.9% | PARCIAL | alta | sigpac_catalunya, dun_cultius, bdbc, field_biodiversity, strava_heatmap, fuel_continuity, aemet, spei, field_validation |

## Estat de connectors

| Connector | Estat | Fonts |
| --- | --- | --- |
| blocked_strava_heatmap_connector | requereix intervenció manual | strava_heatmap |
| connector_aca_hidrologia | implementat | aca_hydrology |
| connector_biodiversitat | implementat | gbif_occurrences, inaturalist_observations |
| connector_connectivitat_ecologica | implementat | connectivity_infraestructura_verda |
| connector_copernicus_teledeteccio | parcial | copernicus_sentinel_ndvi, copernicus_sentinel_ndmi, copernicus_sentinel_ndwi, copernicus_sentinel_nbr |
| connector_detailed_surface_temperature | parcial | detailed_surface_temperature |
| connector_habitats | implementat | habitats_terrestres_v3, hic_v2 |
| connector_icgc_cobertes_sol | implementat | land_cover_icgc_cobertes_sol |
| connector_icgc_dem_mdt | implementat | icgc_dem_mdt |
| connector_incendis_historial | implementat | fires_burned_areas, effis |
| connector_meteocat_xema | parcial | meteocat |
| connector_recreational_pressure_osm | implementat | osm_public_use |
| ecoradar.core.study_area | implementat | study_area_file |
| pending_aemet_connector | requereix intervenció manual | aemet |
| pending_base_cartography_icgc | pendent | icgc_base_maps, icgc_orthophoto |
| pending_bdbc_connector | requereix intervenció manual | bdbc |
| pending_dun_cultius_connector | requereix intervenció manual | dun_cultius |
| pending_fieldwork_importer | requereix intervenció manual | field_biodiversity, field_validation |
| pending_fuel_structure_connector | requereix intervenció manual | fuel_continuity |
| pending_mcsc_connector | requereix intervenció manual | land_cover_mcsc |
| pending_sigpac_connector | requereix intervenció manual | sigpac_catalunya |
| pending_spei_connector | requereix intervenció manual | spei |
