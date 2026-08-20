# Official Data Sources

Verification date: 2026-07-25

This document follows `AGENTS.md`: source inventory and verification come before any connector implementation. IncendisCat is explicitly not treated as a source.

## Verification References

- IDEC, the Infraestructura de Dades Espacials de Catalunya, is the official geodata catalogue used to verify geospatial metadata and services. It exposes records for datasets, services, formats, CRS, responsible organizations, and update frequencies.
- The Generalitat open-data Socrata catalogue was queried for Bombers/incident datasets. The official candidate `g2ay-3vnj`, "Actuacions dels Bombers de la Generalitat", was found on 2026-07-05, but it is not proven to be the exact upstream used by IncendisCat.
- IncendisCat was used only as a lead to identify the official source it claims to use. Its FAQ states that its incident data come from open data for Bombers de la Generalitat actions and that IncendisCat is independent and non-official.

## Inventory Summary

| Domain | Source | Responsible organization | Status |
| --- | --- | --- | --- |
| Half-hourly station observations | XEMA open data (Socrata) | Servei Meteorologic de Catalunya | `verified` |
| Climate observations and forecasts | Meteocat API | Servei Meteorologic de Catalunya | `requires_credentials` |
| Climate observations, normals and forecasts | AEMET OpenData | Agencia Estatal de Meteorologia | `requires_credentials` |
| Current river discharge at la Seu d'Urgell | SAIH Ebro stations A022 Valira and A023 Segre | Confederacion Hidrografica del Ebro | `verified` |
| Fires, active incidents | Actuacions dels Bombers de la Generalitat | Departament d'Interior / DGPEIS | `blocked` |
| Fires, active operational viewer | Bombers - Visor d'actuacions incendis PRO | Departament d'Interior / Bombers de la Generalitat | `pending_verification` |
| Fires, burned area perimeters | Superficies afectades per incendis forestals v1.1 | Departament d'Accio Climatica, Alimentacio i Agenda Rural / ICGC / Cos d'Agents Rurals | `verified` |
| Fire danger | Pla Alfa by municipality | Cos d'Agents Rurals / Generalitat de Catalunya | `pending_verification` |
| Fire history and risk, EU scale | EFFIS | Copernicus Emergency Management Service / Joint Research Centre | `pending_verification` |
| Fire public context catalogue, EU scale | EFFIS Data Request Form dataset catalogue | Copernicus Emergency Management Service / Joint Research Centre | `verified` |
| Emergency mapping | Copernicus EMS Mapping | Copernicus Emergency Management Service | `pending_verification` |
| Biodiversity, habitats | Cartografia dels habitats d'interes comunitari a Catalunya 1:50.000, v2 | Generalitat de Catalunya, via IDEC/Hipermapa | `verified` |
| Biodiversity, species records | GBIF Occurrence API | Global Biodiversity Information Facility | `verified` |
| Biodiversity, species observations | iNaturalist Observations API | iNaturalist Network | `verified` |
| Biodiversity, protected areas | Espais Naturals de Proteccio Especial, Natura 2000, PEIN | Direccio General de Politiques Ambientals i Medi Natural | `verified` |
| Connectivity | Index de connectivitat terrestre general | Departament d'Accio Climatica, Alimentacio i Agenda Rural; Minuartia; IDEC | `verified` |
| Connectivity | Connectivitat ecologica, serveis ecosistemics | CREAF / IDEC | `verified` |
| Drought, water management | Unitats d'explotacio, Pla de Sequera | Agencia Catalana de l'Aigua | `verified` |
| Drought, current state | Visor de la sequera | Agencia Catalana de l'Aigua | `pending_verification` |
| Drought, global index | SPEIbase | CSIC / SPEI Global Drought Monitor team | `verified` |
| Vegetation and water indices | Sentinel-2 via Copernicus Data Space | Copernicus Data Space Ecosystem / ESA / European Union | `requires_credentials` |
| Terrain | Model d'elevacions del terreny | Institut Cartografic i Geologic de Catalunya | `verified` |
| Public use | Visitor counts / public-use pressure in protected areas | Generalitat park managers / protected-area bodies | `pending_verification` |
| Public use, recreational infrastructure | OpenStreetMap via Overpass API | OpenStreetMap contributors / Overpass community | `verified` |
| Public use, relative activity heat | Strava Global Heatmap | Strava, Inc. | `blocked` |

## Climate

### XEMA open station observations

- Source name: Dades meteorològiques de la XEMA.
- Responsible organization: Servei Meteorològic de Catalunya / Generalitat de Catalunya.
- Official URL: `https://analisi.transparenciacatalunya.cat/d/nzvn-apee`
- Service type: public Socrata open-data API.
- Data format: JSON or CSV.
- Coordinate reference system: station metadata are WGS84 (EPSG:4326); observations are tabular and linked by station code.
- Available variables used by EcoRadar: relative humidity (`33`, %), wind speed at 10 m (`30`, m/s), wind direction at 10 m (`31`, degrees), maximum gust at 10 m (`50`, m/s), gust direction (`51`, degrees), UTC timestamp, validation state and temporal base.
- Update frequency: every 30 minutes, as documented by Meteocat.
- Usage license: METEOCAT intellectual-property terms and Generalitat open-data attribution.
- Example connection: `https://analisi.transparenciacatalunya.cat/resource/nzvn-apee.json?$limit=20&$order=data_lectura%20DESC&$where=codi_estacio='CD'`.
- Connector status: `verified`.
- Verification notes: verified on 2026-07-22 without credentials. Station `CD`, la Seu d'Urgell - Bellestar (849 m), and station `Y4`, Alinyà (1,161 m), are operational. Rechecked on 2026-08-07: Y4 publishes variables 32, 33 and 35 but no wind variables 30, 31, 50 or 51. For Alinyà wind context, the nearest operational XEMA station verified with variable 30 is Organyà `CJ` (568 m), 9.2 km from Y4; its use must be labelled as a nearby point observation and never as wind measured at Alinyà. A blank validation state means the measurement has not started validation; it is retained as a real provisional observation and labelled accordingly, never as a validated value.

### Meteocat API

- Source name: Meteocat API.
- Responsible organization: Servei Meteorologic de Catalunya.
- Official URL: `https://api.meteo.cat/`
- Service type: REST API.
- Data format: JSON.
- Coordinate reference system: station coordinates; exact CRS pending endpoint schema confirmation.
- Available variables: temperature, precipitation, humidity, wind, station observations, forecasts, climate summaries and derived extreme-day indicators depending on endpoint.
- Update frequency: endpoint dependent; real-time/current observations and historical products must be documented per endpoint before implementation.
- Usage license: pending endpoint terms; access requires API credentials.
- Example connection: `https://api.meteo.cat/` currently returns `Forbidden` without credentials.
- Connector status: `requires_credentials`.
- Verification notes: Official portal was reachable but API access is protected. Do not implement until credentials and exact endpoint schemas are documented.

### AEMET OpenData

- Source name: AEMET OpenData.
- Responsible organization: Agencia Estatal de Meteorologia.
- Official URL: `https://opendata.aemet.es/centrodedescargas/inicio`
- Service type: REST API.
- Data format: JSON metadata responses plus downloadable data payloads.
- Coordinate reference system: station coordinates; exact CRS and fields depend on product.
- Available variables: observations, climatological values, station inventory, normal climatological values, forecasts and warnings/extreme episodes depending on product.
- Update frequency: product dependent.
- Usage license: AEMET authorizes use and reproduction citing AEMET as author; API key required.
- Example connection: `https://opendata.aemet.es/opendata/api/valores/climatologicos/inventarioestaciones/todasestaciones/`
- Connector status: `requires_credentials`.
- Verification notes: The official OpenData portal exposes "Obtencion de API Key" and developer access. Do not implement until the API key flow and selected endpoints are documented.

## Hydrology

### SAIH Ebro current hydrological observations at la Seu d'Urgell

- Source name: SAIH Ebro, current values from river-gauging stations.
- Responsible organization: Confederación Hidrográfica del Ebro (CHE), Ministerio para la Transición Ecológica y el Reto Demográfico.
- Official URLs: `https://www.saihebro.com/tiempo-real/estacion-aforos-A022-valira-seu` and `https://www.saihebro.com/tiempo-real/estacion-aforos-A023-segre-seu`.
- Service type: public HTTP current-values endpoint used by the official station pages.
- Data format: JSON response containing the current-signal table; normalized by EcoRadar to CSV.
- Coordinate reference system: official station latitude and longitude retained as EPSG:4326; the station pages also publish projected coordinates in zone 30.
- Available variables used by EcoRadar: instantaneous discharge in m³/s, river level in metres, local observation timestamp, source trend glyph and public recent minigraph samples for station `A022` (Valira) and station `A023` (Segre); A022 also publishes station precipitation over 24 hours.
- Update frequency: every 15 minutes at source; checked daily, queried on
  viewer load and polled every 15 minutes while the page remains visible.
  On-demand updates use direct CORS access, with an EcoRadar Netlify Function
  as fallback.
- Usage license: the inspected current-values endpoint does not state a specific open-data license. EcoRadar preserves full CHE/SAIH attribution and documents this limitation instead of assuming a license.
- Example connection: `https://www.saihebro.com/api/ficha/procesarTablaValoresActuales?estacion=A022`.
- Connector status: `verified`.
- Verification notes: verified without credentials on 2026-07-26 and
  reverified on 2026-07-27. A022 and
  A023 returned `HTTP 200`, `application/json; charset=utf-8` and the
  `VALORES_ACTUALES` table. GET exposed `Access-Control-Allow-Origin: *`; the
  `OPTIONS` preflight returned `204`, so no browser CORS block was observed.
  The 2026-07-27 check returned 17:45 CEST observations of 6.12 m³/s at A022
  and 1.07 m³/s at A023. On 2026-07-26 and again on 2026-07-27 the deployed
  Netlify route timed out while the official
  endpoint still returned HTTP 200 directly in under one second. The viewer
  therefore tries the official CORS endpoint first. Its server fallback forces
  IPv4 and races the official `www`, `ap` and `internet` SAIH hosts. Because
  the CHE server omitted the FNMT intermediate certificate, Node initially returned
  `UNABLE_TO_VERIFY_LEAF_SIGNATURE`; the function now adds the official FNMT
  AIA intermediate to Node's public roots without disabling TLS validation.
  The A022 24-hour precipitation signal is `A022O83PA24H`. Public minigraph
  values do not include individual timestamps and are therefore used only for
  a qualitative recent direction.
  The dated historical graph API requires a CHE account
  (`requires_credentials`). SAIH explicitly classifies real-time records as
  provisional, unfiltered and subject to later hydrological review. These
  point observations are not flood alerts and are not spatially extrapolated.

### Meteocat municipal precipitation forecast for la Seu d'Urgell

- Source name: Predicció municipal de Meteocat, municipality `252038`.
- Responsible organization: Servei Meteorològic de Catalunya / Generalitat de Catalunya.
- Official URL: `https://www.meteo.cat/prediccio/municipal/252038`.
- Service type: public first-party JSON used by the official municipal forecast widget.
- Data format: JSON normalized by EcoRadar to hourly CSV.
- Coordinate reference system: municipality reference coordinate in the source response; values are municipal and not a street grid.
- Available variables: hourly accumulated precipitation forecast, valid time and model issue time.
- Update frequency: operational forecast; EcoRadar preserves the source issue timestamp.
- Usage license: the inspected widget endpoint does not state a specific reuse licence; Meteocat and Generalitat attribution is retained.
- Example connection: `https://static-m.meteo.cat/ginys/models/postProcessament/variables/prec_acum/intervals/1/prec_acum-1_1h.json`.
- Connector status: `verified`.
- Verification notes: verified without credentials on 2026-07-25. This is a municipal forecast, not an observation, street-scale rainfall field or official warning.

## Fire Data

### Active incidents used by IncendisCat

- Source name: Actuacions dels Bombers de la Generalitat.
- Responsible organization: Departament d'Interior / Direccio General de Prevencio, Extincio d'Incendis i Salvaments.
- Official URL: `https://analisi.transparenciacatalunya.cat/d/g2ay-3vnj`
- Service type: Socrata open data API.
- Data format: JSON, CSV and other Socrata tabular exports.
- Coordinate reference system: no geometry or CRS declared; the dataset uses administrative references (`CODI_INE`, `CODI_COMARCA`, municipality, comarca, emergency region).
- Available variables: action identifier, municipality/comarca/region codes and names, action group and action type codes/descriptions, action date, year, month, urgent/non-urgent flag, validation flag.
- Update frequency: weekly, according to official metadata.
- Usage license: `SEE_TERMS_OF_USE`; Generalitat open data license terms.
- Example connection: `https://analisi.transparenciacatalunya.cat/resource/g2ay-3vnj.json?$limit=10`
- Connector status: `blocked`.
- Verification notes: IncendisCat states that its fire data come from open data for Bombers de la Generalitat actions and its public site reports minute-scale refreshes. IncendisCat's browser code calls its own backend (`backend/api.php`) and exposes latitude, longitude, operational status, deployed units, first-seen and last-update timestamps. Those fields and the minute-scale update behaviour are not documented in the official `g2ay-3vnj` metadata, which is a weekly tabular dataset. Therefore `g2ay-3vnj` is an official candidate, but it is not proven to be the exact IncendisCat upstream. See `docs/data_sources/fire/incendiscat-official-source.md`.

### Bombers ArcGIS operational wildfire viewer

- Source name: Bombers - Visor d'actuacions incendis PRO / `ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW`.
- Responsible organization: Departament d'Interior / Bombers de la Generalitat. The public ArcGIS item owner is `AdminInterior`.
- Official URL: `https://experience.arcgis.com/experience/f6172fd2d6974bc0a8c51e3a6bc2a735`
- Feature layer URL: `https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services/ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW/FeatureServer/0`
- Service type: ArcGIS Experience and ArcGIS FeatureServer query service.
- Data format: ArcGIS JSON query response; point geometry.
- Coordinate reference system: ETRS89 UTM zone 31N, `EPSG:25831`.
- Available variables: action identifier, action dates, IV alarm group/type, situation, start/end/update dates, urgent flag, municipality, vehicle/resource count, fire phase (`COM_FASE`), object identifiers and point geometry.
- Update frequency: the layer metadata reports `cacheMaxAge = 30`; the operational refresh cadence, retention window and archival policy are not formally documented in the inspected metadata.
- Usage license: not declared in the inspected public ArcGIS item/layer metadata.
- Example connection: `https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services/ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW/FeatureServer/0/query?f=json&where=1%3D1&returnGeometry=true&outFields=*&outSR=25831`
- Connector status: `pending_verification`.
- Verification notes: Inspected on 2026-07-07 from the public ArcGIS Experience and FeatureServer metadata. The layer is a view filtered to `TAL_COD_ALARMA1 = 'IV' AND ACT_NUM_VEH >= 0`. A Cadí context query returned one point incident in Gisclareny with phase `Estabilitzat`. This source is suitable only as public operational context at this stage; it is not a burned-area perimeter source, not post-fire ecological evidence, and the exact relationship to IncendisCat remains unproven.

### Burned area perimeters

- Source name: Superficies afectades per incendis forestals v1.1.
- Responsible organization: Departament d'Accio Climatica, Alimentacio i Agenda Rural. The lineage states perimeters are derived from satellite image processing under the DACC-ICGC agreement and, where needed, GPS surveys by the Cos d'Agents Rurals.
- Official URL: `http://agricultura.gencat.cat/ca/serveis/cartografia-sig/bases-cartografiques/boscos/incendis-forestals`
- Service type: WFS, WMS, file download.
- Data format: CSV, GML, KML, MMZX, SHP.
- Coordinate reference system: ETRS89 UTM zone 31N, `EPSG:25831`.
- Available variables: burned-area geometry and semantic fire attributes defined by the technical specification.
- Update frequency: annual records by fire year; IDEC also reports some related maintenance as discretionary.
- Usage license: no public access limitations; gencat legal notice.
- Example connection: `https://sig.gencat.cat/ows/VEGETACIO/wfs?service=wfs&version=2.0.0&request=GetCapabilities`
- Connector status: `verified`.

### Pla Alfa

- Source name: Pla Alfa daily fire-danger level by municipality.
- Responsible organization: Cos d'Agents Rurals / Generalitat de Catalunya.
- Official information page: `https://interior.gencat.cat/ca/arees_dactuacio/agents-rurals/pla-alfa/index.html`.
- Official technical endpoint: `https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services/Pla_Alfa_Municipal_Avui_FL_2_view/FeatureServer/0`.
- Service type: public ArcGIS FeatureServer query, read-only view used by the official "Pla Alfa Avui" web map (`a696da9dc39f461dadfc0f22e910b4aa`).
- Data format: Esri JSON / GeoJSON; EcoRadar requests attributes only once per daily run.
- Coordinate reference system: ETRS89 UTM zone 31N, `EPSG:25831` (geometry is not downloaded by the Alinyà connector).
- Available variables: municipal code (`CODIMUNI`), municipality (`NOMMUNI`), county (`NOMCOMAR`) and official operational level 0-4 (`PERIL_M`).
- Update frequency: the official page states 00:00 and 09:30, or exceptionally when required.
- Usage license: no explicit layer-level license is published in the ArcGIS item; use is limited here to factual attribution and the public official value, with a direct link to the source.
- Example connection: `.../FeatureServer/0/query?where=CODIMUNI%3D%27259084%27&outFields=CODIMUNI%2CNOMMUNI%2CNOMCOMAR%2CPERIL_M&returnGeometry=false&f=json`.
- Connector status: `verified`.
- Verification notes: verified on 20 August 2026 against the official Interior page, the public ArcGIS item owned by `AdminInterior`, its municipal-today view, layer schema and a direct query for code `259084` (Fígols i Alinyà). Pla Alfa is kept as an official operational context and is not converted into an EcoRadar score.

### EFFIS

- Source name: European Forest Fire Information System.
- Responsible organization: Copernicus Emergency Management Service / Joint Research Centre.
- Official URL: `https://forest-fire.emergency.copernicus.eu`
- Service type: portal and data request/services; exact machine endpoint pending.
- Data format: pending.
- Coordinate reference system: pending.
- Available variables: active fires, burned areas, severity, recurrence, fire danger/risk, fire weather products depending on service.
- Update frequency: product dependent.
- Usage license: pending.
- Example connection: pending.
- Connector status: `pending_verification`.
- Verification notes: Official EFFIS data request portal is identified, but the connector-grade endpoint and license terms need confirmation.

### EFFIS Data Request Form Dataset Catalogue

- Source name: EFFIS / Copernicus Emergency Management Service Data Request Form dataset catalogue.
- Responsible organization: Copernicus Emergency Management Service / Joint Research Centre.
- Official URL: `https://forest-fire.emergency.copernicus.eu/apps/data.request.form/`
- Service type: REST API public catalogue and data-request workflow.
- Data format: JSON catalogue; requestable output formats include ESRI Shapefile, GeoJSON, KML, XLSX and CSV for vector products according to the catalogue response.
- Coordinate reference system: product dependent; the catalogue endpoint itself has no geometry.
- Available variables: requestable dataset codes and names, including `hs_viirs` thermal anomalies from VIIRS, `hs_modis` thermal anomalies from MODIS, and `fire` MODIS/Sentinel-2 burned areas; file-type availability by dataset.
- Update frequency: catalogue/service dependent; product update frequency must be verified per requested EFFIS product before connector implementation.
- Usage license: pending product/request terms; official legal notice and data request conditions apply.
- Example connection: `https://api.effis.emergency.copernicus.eu/rest/drf/datasets/`
- Connector status: `verified`.
- Verification notes: Verified on 2026-07-07 as a public official EFFIS/Copernicus catalogue endpoint. This is approved for source-traceability context only. It is not a local fire-perimeter layer and was not used as an Analysis Engine input in the Cadí map; any connector for EFFIS product downloads still requires per-product schema, CRS, licence and request workflow documentation.

### Copernicus EMS Mapping

- Source name: Copernicus Emergency Management Service Mapping.
- Responsible organization: Copernicus Emergency Management Service.
- Official URL: `https://emergency.copernicus.eu`
- Service type: activation catalogue/download services; exact API endpoint pending.
- Data format: vector/raster map products depending on activation.
- Coordinate reference system: product dependent.
- Available variables: post-fire mapping, flood extent, damage grading and other emergency mapping products.
- Update frequency: activation based.
- Usage license: pending.
- Example connection: pending.
- Connector status: `pending_verification`.

## Biodiversity

### Habitats of Community Interest

- Source name: Cartografia dels habitats d'interes comunitari a Catalunya 1:50.000, versio 2.
- Responsible organization: Generalitat de Catalunya, documented through IDEC; distributed through the agriculture/geodata portal and Hipermapa.
- Official URL: `http://agricultura.gencat.cat/ca/serveis/cartografia-sig/bases-cartografiques/habitats/habitats-catalunya/`
- Service type: WMS, file download, Hipermapa.
- Data format: official catalogue reports vector data; download page and services provide the technical distribution.
- Coordinate reference system: `EPSG:25831`.
- Available variables: CORINE habitats, Habitats of Community Interest, EUNIS correspondences, LPEHT correspondences, habitat interest and threat attributes.
- Update frequency: versioned releases; v2 metadata date 2018-11-30.
- Usage license: no public access limitations in IDEC metadata; gencat legal terms may apply.
- Example connection: `https://sig.gencat.cat/ows/wmts/service/wms?service=wms&version=1.3.0&request=GetCapabilities`
- Connector status: `verified`.

### Terrestrial Habitats

- Source name: Cartografia dels habitats terrestres, versio 3 (2019/2024).
- Responsible organization: Generalitat de Catalunya, Departament de Territori, Habitatge i Transicio Ecologica.
- Official URL: `https://mediambient.gencat.cat/ca/05_ambits_dactuacio/patrimoni_natural/sistemes_dinformacio/habitats/habitats_terrestres/mapa-dels-habitats-terrestres/cartografia-dels-habitats-versio-3-2025/`
- Service type: Hipermapa WMS/WFS.
- Data format: vector; GeoJSON via WFS.
- Coordinate reference system: `EPSG:25831`.
- Available variables: CORINE habitat code/name, Habitat of Community Interest code/name, HIC priority flag, EUNIS and LPEHT correspondences, habitat value/threat attributes, geometry.
- Update frequency: versioned releases; official page update date 2025-06-11.
- Usage license: gencat legal terms apply; public Hipermapa/WFS access verified.
- Example connection: `https://sig.gencat.cat/ows/wfs?service=WFS&version=2.0.0&request=DescribeFeatureType&typeNames=HABITATS_TERRESTPOL`
- Connector status: `verified`.
- Verification notes: the official page describes version 3 as terrestrial habitats catalogued with both the CORINE habitats list and Habitats Directive HIC list. The official Hipermapa layer `HABITATS_TERRESTPOL` exposes `COD_CORINE`, `CORINE_CA`, `COD_HIC`, `HIC_CA`, and `HIC_PRIOR`.

### GBIF Species Occurrences

- Source name: GBIF Occurrence API.
- Responsible organization: Global Biodiversity Information Facility.
- Official URL: `https://api.gbif.org/v1/`
- Service type: REST API.
- Data format: JSON.
- Coordinate reference system: WGS84 coordinates in occurrence records.
- Available variables: scientific name, vernacular name when available, taxonomic classification, event date, coordinates, basis of record, data license, occurrence issues, and record key.
- Update frequency: continuously updated from publishing datasets.
- Usage license: record-level licenses; GBIF citation and dataset attribution requirements apply.
- Example connection: `https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&limit=1`
- Connector status: `verified`.
- Verification notes: official GBIF technical documentation identifies `https://api.gbif.org/` as the stable REST/JSON API base URL. Most API use does not require authentication; GBIF recommends setting a User-Agent and warns that search APIs may be rate limited.

### iNaturalist Species Observations

- Source name: iNaturalist Observations API.
- Responsible organization: iNaturalist Network.
- Official URL: `https://api.inaturalist.org/v1/observations`
- Service type: REST API.
- Data format: JSON.
- Coordinate reference system: WGS84 coordinates in observation records.
- Available variables: scientific name, preferred common name, iconic taxon group, observed date, coordinates, quality grade, license code, observation URL, and captive/cultivated flag.
- Update frequency: continuously updated from user observations.
- Usage license: record-level licenses and iNaturalist API terms apply.
- Example connection: `https://api.inaturalist.org/v1/observations?per_page=1`
- Connector status: `verified`.
- Verification notes: official iNaturalist API reference points to the supported `https://api.inaturalist.org` API, and the public v1 observations endpoint returns JSON records without scraping. Authenticated OAuth flows exist but are not required for public observations.

### Seguiment d'Amfibis Comuns de Catalunya (SACC)

- Source name: Seguiment d'Amfibis Comuns de Catalunya (SACC).
- Responsible organization: Societat Catalana d'Herpetologia; project included in the Observatori del Patrimoni Natural i la Biodiversitat.
- Official URLs: `https://soccatherp.org/seguiment-damfibis-comuns-de-catalunya-sacc/` and `https://observatorinatura.cat/projectes/info/42/`.
- Service type: monitoring program and public project portal.
- Data format: HTML and monitoring publications; no reusable public local API was documented during verification.
- Coordinate reference system: not declared for a reusable public local export.
- Available variables: amphibian monitoring at water points and watercourses, population trends, and biotic and abiotic breeding-site descriptors.
- Update frequency: monitoring campaigns; the program began as a pilot in 2023 and was implemented from 2024.
- Usage license: no reusable record-level open-data license was identified for an automated local export.
- Example connection: `https://observatorinatura.cat/projectes/info/42/`.
- Connector status: `pending_verification` for La Seu quantitative data.
- Verification notes: the official program and national monitoring period are verified. No public SACC sampling point or quantitative result was verified inside the EcoRadar La Seu scope, so no local SACC count, abundance, species list, or trend is published.

### Protected Natural Areas

- Source name: Espais Naturals de Proteccio Especial, Natura 2000, and PEIN.
- Responsible organization: Direccio General de Politiques Ambientals i Medi Natural, Generalitat de Catalunya.
- Official URL: `http://agricultura.gencat.cat/ca/serveis/cartografia-sig/bases-cartografiques/espais-naturals/`
- Service type: WFS, WMS, OGC API Features/INSPIRE, ATOM for INSPIRE records, file download.
- Data format: CSV, GML, KML, MMZX, SHP for native ENPE; GML for INSPIRE records.
- Coordinate reference system: `EPSG:25831`; INSPIRE records also list `EPSG:4326` and `EPSG:4258`.
- Available variables: ENPE, Natura 2000, PEIN, wetlands, public forests, geoparks, and geological-interest spaces depending on layer.
- Update frequency: discretionary/as needed for native ENPE; INSPIRE records are versioned.
- Usage license: CC BY 4.0 for native ENPE metadata; gencat legal notice; no public access limitations.
- Example connection: `https://sig.gencat.cat/ows/ESPAIS_NATURALS/wfs?service=wfs&version=2.0.0&request=GetCapabilities`
- Connector status: `verified`.

### Natura 2000 — Spain, December 2025 snapshot

- Source name: Espacios protegidos de la Red Natura 2000.
- Responsible organization: Ministerio para la Transicion Ecologica y el Reto Demografico (MITECO), Banco de Datos de la Naturaleza.
- Official URL: `https://www.miteco.gob.es/ca/biodiversidad/servicios/banco-datos-naturaleza/informacion-disponible/red_natura_2000_inf_disp.html`
- Service type: file download, WFS, WMS.
- Data format: GeoJSON, SHP, GML, KMZ.
- Coordinate reference system: `EPSG:25830` for the retained Peninsula/Balearic file and `EPSG:32628` for the retained Canary file.
- Available variables: site code, site name, type code, area in hectares, competent administration, and multipolygon geometry.
- Update frequency: versioned; the retained snapshot is updated to December 2025 from information sent by MITECO to the European Commission in February 2026.
- Usage license: free use with attribution to `© Ministerio para la Transicion Ecologica y el Reto Demografico`.
- Example connection: `https://www.miteco.gob.es/content/dam/miteco/es/biodiversidad/servicios/banco-datos-naturaleza/3-rn2000/rn2000-geojson.zip`
- Connector status: `verified` for the official source; no connector has been implemented.
- Local reference: `data/reference/natura2000/miteco_2025/README.md`.

## Connectivity

### Terrestrial Connectivity Index

- Source name: Index de connectivitat terrestre general.
- Responsible organization: Minuartia as origin, Departament d'Accio Climatica as processor, IDEC as metadata contact.
- Official URL: IDEC record `coneco-indx-connec-terr-gral`.
- Service type: WFS, WMS.
- Data format: digital vector data.
- Coordinate reference system: `EPSG:25831`.
- Available variables: polygonized terrestrial ecological connectivity index values.
- Update frequency: versioned; creation date 2019-03-01 in IDEC metadata.
- Usage license: consult responsible organization; no public access limitations.
- Example connection: `http://sig.gencat.cat/ows/INFRAESTRUCTURA_VERDA/wfs`
- Connector status: `verified`.

### Ecosystem-Service Connectivity

- Source name: Connectivitat ecologica.
- Responsible organization: CREAF, with IDEC metadata.
- Official URL: IDEC record `servecosis-conectecologica`.
- Service type: WFS, WMS.
- Data format: digital raster/grid data.
- Coordinate reference system: `EPSG:25831`.
- Available variables: ecological connectivity service index based on cost distances, impedances, and habitat affinities.
- Update frequency: versioned; revision date 2020-05-11 in IDEC metadata.
- Usage license: consult responsible organization; no public access limitations.
- Example connection: `http://sig.gencat.cat/ows/INFRAESTRUCTURA_VERDA/wms`
- Connector status: `verified`.

## Drought

### Drought Management Units

- Source name: Unitats d'explotacio, Pla de Sequera.
- Responsible organization: Agencia Catalana de l'Aigua.
- Official URL: `https://aplicacions.aca.gencat.cat/visseq/`
- Service type: WFS, WMS.
- Data format: digital vector data.
- Coordinate reference system: `EPSG:25831`.
- Available variables: exploitation-unit boundaries for drought management.
- Update frequency: monthly review of drought state by unit is described in IDEC metadata; the boundary layer itself has revision date 2019-05-01.
- Usage license: consult ACA; no public access limitations.
- Example connection: `http://sig.gencat.cat/ows/AIGUA/wfs`
- Connector status: `verified`.

### Current Drought State

- Source name: Visor de la sequera.
- Responsible organization: Agencia Catalana de l'Aigua.
- Official URL: `https://aplicacions.aca.gencat.cat/visseq/`
- Service type: web application; technical data endpoint pending.
- Data format: pending.
- Coordinate reference system: pending.
- Available variables: drought state by exploitation unit; exact fields pending.
- Update frequency: monthly review described by ACA metadata.
- Usage license: pending.
- Example connection: pending.
- Connector status: `pending_verification`.

### SPEIbase

- Source name: Global SPEI database, SPEIbase.
- Responsible organization: CSIC / SPEI Global Drought Monitor team.
- Official URL: `https://spei.csic.es/database.html`
- Service type: NetCDF file download.
- Data format: NetCDF.
- Coordinate reference system: geographic longitude/latitude grid.
- Available variables: standardized precipitation-evapotranspiration index (`spei`) at time scales 1 to 48 months.
- Update frequency: updated as new source data become available; latest documented SPEIbase v2.11 spans January 1901 to December 2024.
- Usage license: Open Database License (ODbL) for data.
- Example connection: `https://spei.csic.es/spei_database_2_11`
- Connector status: `verified`.
- Verification notes: Official SPEI documentation provides resolution, temporal coverage, variables, NetCDF format and license.

### SPI

- Source name: Standardized Precipitation Index.
- Responsible organization: not a source; this is a derived indicator.
- Official URL: not applicable.
- Service type: derived calculation from verified precipitation sources.
- Data format: not applicable.
- Coordinate reference system: inherited from precipitation source.
- Available variables: SPI time scale selected by EcoRadar.
- Update frequency: inherited from precipitation source.
- Usage license: inherited from precipitation source.
- Example connection: not applicable.
- Connector status: `blocked`.
- Verification notes: SPI should not be implemented as a connector. It belongs in the Analysis Engine after precipitation sources are verified.

## Copernicus Indices

### Sentinel-derived NDVI, NDMI and NDWI

- Source name: Sentinel-2 via Copernicus Data Space Ecosystem.
- Responsible organization: Copernicus Data Space Ecosystem / ESA / European Union.
- Official URL: `https://dataspace.copernicus.eu/analyse/apis`
- Service type: STAC, OData, openEO, Sentinel Hub APIs, OGC APIs.
- Data format: Sentinel products, API responses, raster outputs from processing APIs.
- Coordinate reference system: product/API dependent; Sentinel-2 native granules are UTM by tile and outputs can be requested/projected per API.
- Available variables: spectral bands required for NDVI, NDMI and NDWI; cloud masks and metadata depending on product.
- Update frequency: Sentinel acquisition cadence/product availability.
- Usage license: Copernicus terms; service account/credentials may be required for processing APIs.
- Example connection: `https://sh.dataspace.copernicus.eu/api/v1/process`
- Connector status: `requires_credentials`.
- Verification notes: Official API catalogue and Sentinel Hub documentation verified. The Processing API can generate rasters for a user-defined area and time range, and Sentinel Hub authentication requires a registered OAuth client with client ID and client secret. NDVI, NDMI and NDWI are derived from Sentinel-2 L2A bands; EcoRadar connector execution requires `COPERNICUS_CLIENT_ID` and `COPERNICUS_CLIENT_SECRET`.

### Land Surface Temperature

- Source name: Land Surface Temperature via Copernicus Data Space Ecosystem.
- Responsible organization: Copernicus Data Space Ecosystem / ESA / European Union.
- Official URL: `https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S3SLSTR.html`
- Service type: Sentinel Hub API; CLMS/Sentinel-3 product access depending on selected operational product.
- Data format: raster outputs and API responses.
- Coordinate reference system: product/API dependent; outputs can be requested/projected per API.
- Available variables: land surface temperature and thermal/product metadata depending on collection.
- Update frequency: product dependent.
- Usage license: Copernicus terms; service account/credentials required.
- Example connection: `https://sh.dataspace.copernicus.eu/api/v1/process`
- Connector status: `requires_credentials`.
- Verification notes: LST is available in Copernicus/Sentinel Hub product families such as Sentinel-3 SLSTR and CLMS LST. The exact operational collection and band mapping must be selected and tested with credentials before producing `lst.tif`.

## Terrain

### ICGC Elevation Model

- Source name: Model d'elevacions del terreny.
- Responsible organization: Institut Cartografic i Geologic de Catalunya.
- Official URL: `https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Elevacions-territorial`
- Service type: file download / COG.
- Data format: COG / GeoTIFF depending on product.
- Coordinate reference system: `EPSG:25831`; orthometric heights referenced to EGM08D595 in current IDEC records.
- Available variables: terrain elevation.
- Update frequency: versioned survey/publication products.
- Usage license: CC BY 4.0 for current IDEC elevation records.
- Example connection: `https://datacloud.icgc.cat/datacloud/model-elevacions-terreny/tif_unzip/`
- Connector status: `verified`.
- Verification notes: Derived slope, aspect, potential insolation, water accumulation and hydrological connectivity are not connector outputs; they belong in the Analysis Engine using this DEM as input.

## Public Use

- Source name: Protected-area public-use and visitor-pressure data.
- Responsible organization: pending; likely each protected-area management body or Generalitat protected-area services.
- Official URL: pending.
- Service type: pending.
- Data format: pending.
- Coordinate reference system: pending.
- Available variables: visitor counts, access counters, trail use, facility use, or public-use incidents if available.
- Update frequency: pending.
- Usage license: pending.
- Example connection: pending.
- Connector status: `pending_verification`.
- Verification notes: IDEC confirms official protected-area geometries, but it does not identify a general Catalunya-wide public-use/visitor dataset in the checks performed so far. This domain needs a targeted official-source search before implementation.

### OpenStreetMap Recreational Infrastructure

- Source name: OpenStreetMap via Overpass API.
- Responsible organization: OpenStreetMap contributors; Overpass API maintained by the OSM/Overpass community.
- Official URL: `https://wiki.openstreetmap.org/wiki/Overpass_API`
- Service type: REST API.
- Data format: JSON/XML from Overpass; GeoJSON can be produced by the EcoRadar client.
- Coordinate reference system: WGS84 coordinates in OSM elements.
- Available variables: paths, tracks, cycleways, roads, access tags, parking/access points, viewpoints, recreation facilities, and route relations where mapped.
- Update frequency: continuously updated by OSM contributors.
- Usage license: ODbL for OSM data; public Overpass instance usage policy applies.
- Example connection: `https://overpass-api.de/api/interpreter`
- Connector status: `verified`.
- Verification notes: Overpass is documented as a read-only API for querying selected OSM data by location and tags. Public instances are suitable for small/medium extracts when used respectfully with identifying headers.

### Strava Global Heatmap

- Source name: Strava Global Heatmap.
- Responsible organization: Strava, Inc.
- Official URL: `https://www.strava.com/maps/global-heatmap`
- Service type: web map visualization.
- Data format: not documented for connector use.
- Coordinate reference system: web map tiles; connector-grade CRS/access path not documented.
- Available variables: relative activity heat visualization by activity category through the Strava UI.
- Update frequency: not documented for connector use.
- Usage license: proprietary; automated reuse/download terms not verified.
- Example connection: not available.
- Connector status: `blocked`.
- Verification notes: The heatmap is useful conceptually as a relative activity indicator, but no official public API or download endpoint was verified for automated EcoRadar ingestion. EcoRadar must not scrape tiles or bypass access controls. Strava-derived intensity can only be integrated after an authorized/licensed data access path is documented.

### Future Recreational Data Sources

- Wikiloc, automatic visitor counters, field observations and protected-area manager datasets remain future inputs.
- Connector status: `pending_verification` until each source has an authorized API/file access path, license, CRS/format and update policy.
- Verification notes: these sources can strengthen diagnosis, but they cannot be silently substituted for verified connector data.

## Connector Gate

Connector implementation may start only for sources marked `verified`, and only after deciding which verified source is required for a module. Sources marked `pending_verification` must not be implemented yet.
