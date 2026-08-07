# Urban Climate Sources - La Seu d'Urgell

Verification date: 2026-07-09

This file documents the official open sources used or evaluated for the La Seu d'Urgell urban climate poster. It follows the EcoRadar source gate: source inventory and verification come before implementation, and unavailable variables remain explicitly marked.

## Inventory Summary

| Domain | Source | Responsible organization | Status | Use in poster |
| --- | --- | --- | --- | --- |
| LST / surface temperature | Landsat Collection 2 Level-2 UTM Surface Temperature Product | U.S. Geological Survey (USGS) EROS Center | `verified` | Mean land surface temperature for the study bbox, using ST_B10 and QA_PIXEL. |
| LiDAR shade / canopy structure | LiDAR Territorial v3.1 2021-2023 | Institut Cartografic i Geologic de Catalunya | `verified` | Official LiDAR source for canopy/building structure; raw LAZ processing required for true solar shade. |
| Street network / road categorization | Referencial Topografic Territorial v1 | Institut Cartografic i Geologic de Catalunya | `verified` | Official road/cartographic source; vector download is available but the whole GeoPackage archive is very large. |
| Municipal urban trees | La gestio actual del verd urba | Ajuntament de la Seu d'Urgell | `verified` | Municipal count of planted trees in streets and parks and urban green-space area. |
| Open municipal tree inventory | Not found as open geospatial dataset | Ajuntament de la Seu d'Urgell | `blocked` | No tree-by-tree open dataset was found on the municipal website/search; do not invent point inventory. |

## Implemented Poster Metrics v2

Output file: `output/la_seu_urban_metrics_real_v2.json`

Poster file: `output/ecoradar_urba_la_seu_poster_panells_REAL_v6.png`

Study area limitation: the raster/LiDAR metrics below are calculated for the central urban bbox used in the poster update, not for the full municipal boundary.

| Metric | Value | Source and method |
| --- | ---: | --- |
| Mean land surface temperature | 46.7 °C | Landsat 9 Collection 2 Level-2 `ST_B10`, scene `LC09_L2SP_198030_20260708_02_T1`, acquired 2026-07-08 10:35 UTC / 12:35 CEST; QA_PIXEL masked. |
| LST P10-P90 range | 38.7-51.1 °C | Same Landsat ST_B10 extraction; 1,485 valid pixels in the poster bbox. |
| LiDAR shade, summer 15 h | 61.7 % | ICGC LiDAR Territorial v3.1 LAZ tiles, 2 m DSM/DTM grid, direct-sun obstruction model for 2026-06-21 15:00 CEST. |
| LiDAR canopy cover | 31.8 % | ICGC LiDAR point classes 4 and 5 inside the same 130.4 ha central bbox. |
| Municipal urban trees | 5,500 trees, 80 species | Official Ajuntament web page; count applies to streets and parks and is not a georeferenced tree inventory. |
| Street-aligned tree cover | blocked | No official open geospatial municipal tree inventory was found. The ICGC RTT road source is verified, but the small-area vector extract returned an email request form during verification. |

## Landsat Surface Temperature

- Source name: Landsat Collection 2 Level-2 UTM Surface Temperature (ST) Product.
- Responsible organization: U.S. Geological Survey (USGS) Earth Resources Observation and Science (EROS) Center.
- Official URL: `https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-st`
- Service type: STAC API and Cloud Optimized GeoTIFF assets.
- Data format: STAC JSON, GeoTIFF COG.
- Coordinate reference system: per-scene UTM CRS; source collection is global, and the La Seu scene is read in its native projected CRS.
- Available variables: ST_B10 surface temperature, thermal radiance, upwelled/downwelled radiance, atmospheric transmittance, emissivity, emissivity standard deviation, cloud distance, ST_QA, QA_PIXEL, QA_RADSAT.
- Update frequency: Landsat acquisition dependent; new Level-2 products are added after processing.
- Usage license: Landsat data policy as linked by the STAC collection.
- Example connection: `https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-st/items?bbox=1.435,42.335,1.490,42.375&datetime=2026-06-01T00:00:00Z/2026-07-09T23:59:59Z&limit=20`
- Connector status: `verified`.
- Verification notes: The official STAC collection describes ST as Earth's surface temperature in Kelvin and identifies USGS EROS as producer/processor/host. The poster calculation must report the Landsat acquisition date/time, not a generic 15:00 value.

## ICGC LiDAR Territorial

- Source name: LiDAR Territorial v3.1 2021-2023.
- Responsible organization: Institut Cartografic i Geologic de Catalunya.
- Official URL: `https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Elevacions/Elevacions-territorial/LiDAR-Territorial`
- Metadata URL: `https://catalegs.ide.cat/geonetwork/srv/api/records/lidar-territorial-v3r1-2021-2023`
- Service type: file download / datacloud, viewer download by area.
- Data format: LAZ compressed LAS 1.4 point cloud; associated orthophoto formats.
- Coordinate reference system: `EPSG:25831` ETRS89 / UTM zone 31N; vertical altitudes referenced to EGM08D595 according to IDEC metadata.
- Available variables: X/Y/H point coordinates, GPS time, classification, vegetation classes, buildings, ground, water, and derived elevation/surface models.
- Update frequency: versioned coverage; current documented coverage 2021-2023.
- Usage license: CC BY 4.0.
- Example connection: `https://datacloud.icgc.cat/datacloud/lidar-territorial/laz_unzip/`
- Connector status: `verified`.
- Verification notes: This is the correct official open source for LiDAR-derived shade/canopy metrics. A true "ombra LiDAR estiu 15 h" requires downloading the relevant 1 x 1 km LAZ tiles, constructing DSM/DTM or using point classes, and running a solar-shadow model. Hillshade WMS layers are not equivalent to time-specific shade.

## ICGC Referencial Topografic Territorial

- Source name: Referencial Topografic Territorial (RTT) v1.
- Responsible organization: Institut Cartografic i Geologic de Catalunya.
- Official URL: `https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Geoinformacio-cartografica/Referencial-Topografic-Territorial`
- WMS URL: `https://geoserveis.icgc.cat/servei/catalunya/topografia-territorial/wms`
- Service type: WMS, vector file downloads, image downloads.
- Data format: GeoPackage 2D/3D, Geodatabase, GeoTIFF, DWG, DGN, IFC, WMS rendered layers.
- Coordinate reference system: ICGC territorial products in `EPSG:25831`; exact CRS is declared in product specifications and data files.
- Available variables: relief, hydrography, transports, constructions, land cover, place names; transport layers include road-network categorization attributes.
- Update frequency: versioned; 2024 data source date documented by ICGC.
- Usage license: CC BY 4.0.
- Example connection: `https://datacloud.icgc.cat/datacloud/topografia-territorial/gpkg/`
- Connector status: `verified`.
- Verification notes: The WMS exposes transport layers, but road-length calculations require vector access. The all-Catalonia 2024 GeoPackage archive is approximately 5.3 GB. The tested small-area extract endpoint returned an email request form, so street-aligned tree-cover processing remains blocked for this poster run unless an official vector extract or municipal street-tree inventory is supplied.

## Ajuntament de la Seu d'Urgell Urban Green

- Source name: On som? La gestio actual del verd urba.
- Responsible organization: Ajuntament de la Seu d'Urgell.
- Official URL: `https://www.laseu.cat/viure-a-la-seu/mediambient/ecoturisme-la-seu-naturalment/per-que-es-important-el-verd-urba/on-som-la-gestio-actual-del-verd-urba`
- Service type: official municipal web page.
- Data format: HTML text.
- Coordinate reference system: not spatial/geometric.
- Available variables: 22 ha of green spaces; 5,500 planted trees in streets and parks; 80 tree species.
- Update frequency: not declared.
- Usage license: municipal public web content; no machine-readable open-data licence declared on the inspected page.
- Example connection: `https://www.laseu.cat/@@search?SearchableText=verd%20urb%C3%A0`
- Connector status: `verified`.
- Verification notes: This source supports a municipal tree-count indicator, but it is not a tree inventory and does not include point geometries, crown diameters or street segments.

## Municipal Tree Inventory

- Source name: Open municipal tree inventory for La Seu d'Urgell.
- Responsible organization: Ajuntament de la Seu d'Urgell.
- Official URL: not found.
- Service type: not found.
- Data format: not found.
- Coordinate reference system: not found.
- Available variables: not found.
- Update frequency: not found.
- Usage license: not found.
- Example connection: not available.
- Connector status: `blocked`.
- Verification notes: Searches on the official municipal website found pages about green-space management, singular trees, pruning campaigns and educational material, but no open geospatial tree inventory. Do not represent the 5,500-tree municipal count as a georeferenced inventory.
