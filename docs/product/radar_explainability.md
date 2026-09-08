# Explicabilitat dels RADAR EcoRadar d’Alinyà

Document de traçabilitat de la implementació vigent, verificat el 08.09.2026 contra `ecoradar/indicators/engine.py`, `ecoradar_core_indicators.csv` i el generador de la interfície. Aquest document descriu el càlcul existent; no redefineix algoritmes ni puntuacions.

## Classes de resultat

- **Puntuació sintètica EcoRadar 0–100:** combinació de components normalitzats. El número no és un percentatge d’estat de conservació. La categoria només aplica els llindars `<20` molt baix, `<40` baix, `<60` mitjà, `<80` alt i `≥80` molt alt.
- **Lectura directa:** valor en l’escala de la font. Al visor actual, `RADAR_03` mostra `NDVI 0,616` de l’escena Sentinel-2 del 07.07.2026. No és `61,6/100`, no rep categoria CORE i no entra a `RADAR_12`.
- Les mitjanes de components ignoren valors absents i tots els components normalitzats es limiten a 0–100. `COMPLET/PARCIAL` i la confiança descriuen la completesa del càlcul i de les fonts declarades, dins les limitacions específiques de cada indicador.

## Càlcul implementat per RADAR

| RADAR | Resultat vigent | Càlcul numèric real | Fonts que intervenen |
|---|---:|---|---|
| RADAR_01 · Mosaic del paisatge | 70,71 · alt · COMPLET/alta | Mitjana igual de l’entropia de cobertes, balanç forestal 35–75%, oberts/agrari normalitzat a 18%, invers d’artificialització a 10%, hàbitats normalitzats a 50 i connector principal normalitzat a 25% de l’àmbit. | Cobertes ICGC, hàbitats v3, Infraestructura Verda. |
| RADAR_02 · Valor d’hàbitats | 98,91 · molt alt · COMPLET/alta | Mitjana igual del nombre d’hàbitats normalitzat a 45, superfície HIC normalitzada a 60% i HIC prioritaris normalitzats a 20%. | Hàbitats v3 i camps HIC/HIC_PRIOR. |
| RADAR_03 · Estat de la vegetació | NDVI 0,616 · lectura directa · PARCIAL/mitjana | El motor CORE no produeix puntuació. El visor mostra la mediana dels píxels NDVI vàlids, amb màscara de qualitat, de l’escena Sentinel-2 del 07.07.2026. | Sentinel-2 L2A. |
| RADAR_04 · Refugis climàtics | 59,20 · mitjà · PARCIAL/mitjana | Mitjana igual de percentatge forestal, orientació mitjana transformada a obaga 0–100 i RADAR_10. LST, NDMI i NDVI no hi entren. | Cobertes ICGC, MDT ICGC, RADAR_10. |
| RADAR_05 · Vulnerabilitat climàtica | 37,31 · baix · PARCIAL/mitjana | Mitjana igual de dèficit forestal respecte del 90%, pendent normalitzat a 35°, solana, artificialització normalitzada a 10% i invers de RADAR_10. LST, NDMI, meteorologia i sequera no hi entren. | Cobertes ICGC, MDT ICGC, RADAR_10. |
| RADAR_06 · Biodiversitat coneguda | 95,11 · molt alt · COMPLET/alta | Mitjana igual de taxons normalitzats a 600, proporció de registres recents i grups taxonòmics normalitzats a 10. | GBIF i iNaturalist. |
| RADAR_07 · Pressió humana i ús públic | 49,15 · mitjà · COMPLET/alta | Mitjana igual de densitat de camins normalitzada a 4 km/km² i punts d’ús públic normalitzats a 8 per 1.000 ha. | OpenStreetMap. |
| RADAR_08 · Connectivitat ecològica | 79,50 · alt · COMPLET/alta | Mitjana igual de coberta natural, connector principal normalitzat a 25% de l’àmbit i invers de RADAR_07. Hàbitats i hidrologia no hi entren. | Cobertes ICGC, Infraestructura Verda, RADAR_07. |
| RADAR_09 · Resiliència davant del foc | 44,17 · mitjà · PARCIAL/mitjana | Mitjana igual de l’invers de bosc+matollar respecte del 95%, oberts/agrari a 20%, invers del pendent a 35°, invers de superfície cremada a 100 ha, densitat OSM a 4 km/km² i RADAR_10. Meteorologia, NDMI, LST, Pla Alfa i combustible mesurat no hi entren. | Cobertes i MDT ICGC, incendis històrics Generalitat, OSM, RADAR_10. |
| RADAR_10 · Aigua i funcionalitat hídrica | 47,18 · mitjà · PARCIAL/mitjana | Mitjana igual de xarxa hídrica normalitzada a 1,5 km/100 ha i fonts normalitzades a 15. Relleu, NDWI, cabal, qualitat i permanència no hi entren. | Cursos ACA/CHE i fonts ICGC. |
| RADAR_11 · Potencial de restauració | 73,71 · alt · PARCIAL/mitjana | Mitjana igual de RADAR_02, RADAR_05, invers de RADAR_10, balanç de RADAR_07 amb òptim 20–60 i RADAR_08. | RADAR_02, 05, 10, 07 i 08. |
| RADAR_12 · Prioritat de gestió | 65,49 · alt · PARCIAL/mitjana | Mitjana aritmètica simple, amb el mateix pes, dels RADAR_01–11 que tenen puntuació. RADAR_03 s’omet perquè no té puntuació CORE; l’NDVI directe tampoc hi entra. | Deu puntuacions calculables de RADAR_01–11. |

## Contracte de la interfície

Cada targeta obre un únic desplegable sota la graella amb cinc blocs: què mesura, en què es basa, com es calcula, com interpretar el resultat i confiança. La targeta indica sempre si mostra una puntuació 0–100 o una lectura directa. El desplegable també explicita les variables que el nom conceptual podria suggerir però que no intervenen en el càlcul vigent.

Les targetes funcionen com a botons natius, exposen `aria-expanded` i `aria-controls`, admeten teclat i permeten tancar el desplegable amb el botó de tancament o la tecla Esc.
