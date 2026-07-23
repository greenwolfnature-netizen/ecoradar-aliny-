# EcoRadar 0.1 · Resum funcional Alinya

Generat: 2026-07-06T20:37:00+00:00

Aquest resum comprova el flux basic amb les capes ja disponibles. No es un informe final ni inclou interpretacions complexes o indexs compostos.

## Indicadors disponibles

| Indicador | Valor | Unitat | Font | Notes |
| --- | ---: | --- | --- | --- |
| superficie_total | 5464.0317 | ha | study_area.gpkg |  |
| perimetre | 93285.61 | m | study_area.gpkg |  |
| percentatge_coberta_forestal | 88.4246 | % | cobertes_sol_resum.csv | Classes amb Bosc/Boscos incloses. |
| percentatge_prats_pastures_herbassars | 9.3344 | % | cobertes_sol_resum.csv |  |
| percentatge_agricola | 0.0047 | % | cobertes_sol_resum.csv |  |
| percentatge_urba_artificial | 0.0801 | % | cobertes_sol_resum.csv | Inclou casc urba i xarxa viaria segons classes disponibles. |
| nombre_tipus_cobertes | 13 | classes | cobertes_sol_resum.csv |  |
| nombre_habitats | 47 | habitats | habitats_resum.csv |  |
| superficie_hic | 3170.9548 | ha | habitats_resum.csv |  |
| nombre_registres_biodiversitat | 731 | registres | biodiversitat.gpkg |  |
| nombre_especies_registrades | 516 | especies | biodiversitat.gpkg |  |
| nombre_registres_recents | 726 | registres | biodiversitat.gpkg | Llindar recent definit pel connector de biodiversitat. |
| densitat_camins_i_pistes | 2.2846 | km/km2 | recreational_pressure_resum.csv | Densitat OSM de camins, pistes i vials menors; no representa intensitat real de visitants. |
| nombre_accessos_punts_us_public | 18 | punts | recreational_pressure_resum.csv | Punts OSM d'aparcament, mirador, informació, refugi, aigua o ús recreatiu; cal validació de camp. |

## Dades no disponibles

| Indicador | Motiu |
| --- | --- |
| ndvi_mitja | Copernicus bloquejat: falten COPERNICUS_CLIENT_ID i COPERNICUS_CLIENT_SECRET. |
| ndmi_mitja | Copernicus bloquejat: falten COPERNICUS_CLIENT_ID i COPERNICUS_CLIENT_SECRET. |
| ndwi_mitja | Copernicus bloquejat: falten COPERNICUS_CLIENT_ID i COPERNICUS_CLIENT_SECRET. |
| lst_mitjana | LST no habilitada: cal configurar col·leccio Sentinel-3/CLMS i credencials. |

## Fitxers utilitzats

- `projectes/Alinya/processed/study_area.gpkg`
- `projectes/Alinya/indicators/cobertes_sol_resum.csv`
- `projectes/Alinya/indicators/habitats_resum.csv`
- `projectes/Alinya/processed/biodiversitat.gpkg`
- `projectes/Alinya/processed/recreational_pressure.gpkg`
- `projectes/Alinya/metadata/teledeteccio_metadata.json`

## Mapes

La carpeta `projectes/Alinya/maps/` queda creada per a sortides cartografiques. En aquesta prova no es generen mapes renderitzats; les capes QGIS/GeoPackage disponibles son les del directori `processed/`.
