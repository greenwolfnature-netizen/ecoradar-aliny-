# Lectures variables d’EcoRadar Alinyà

## Àmbit i principi de publicació

La comprovació automàtica correspon a la Muntanya d’Alinyà. Cada execució fixa
un únic `checked_at_utc`, encara que les dades d’origen no hagin canviat. La
data de comprovació no substitueix mai la data real de cada observació.

Els JSON empaquetats amb el visor són només una reserva. En producció, la funció
Netlify consulta els quatre registres canònics del repositori GitHub:

- `projectes/Alinya/indicators/daily_readings.json`;
- `projectes/Alinya/indicators/daily_history.json`;
- `projectes/Alinya/indicators/current_fire_danger.json`;
- `projectes/Alinya/metadata/reading_registry.json`.

Els quatre fitxers han de compartir el mateix `snapshot_id`; la funció remota
rebutja qualsevol combinació parcial o desincronitzada.

## Fonts variables

| Lectura | Font responsable | Servei | Resolució | Actualització | Estat |
| --- | --- | --- | --- | --- | --- |
| Temperatura, humitat i precipitació | Meteocat / Generalitat de Catalunya | XEMA Socrata `nzvn-apee`, estació Y4 Alinyà | observació puntual | habitualment 30 minuts; comprovació diària | `verified` |
| Vent i ratxa contextuals | Meteocat / Generalitat de Catalunya | XEMA Socrata `nzvn-apee`, estació CJ Organyà, 9,2 km de Y4 | observació puntual propera | habitualment 30 minuts; comprovació diària | `verified` |
| Precipitació acumulada 7/30 dies i dies secs | EcoRadar sobre Meteocat XEMA Y4 | suma de períodes de 30 minuts amb cobertura mínima del 80 % | observació puntual acumulada | amb nova observació XEMA; comprovació diària | derivat de font `verified` |
| Pla Alfa | Cos d'Agents Rurals / Generalitat de Catalunya | ArcGIS FeatureServer públic, vista municipal "Avui" | nivell oficial municipal 0–4 | 00:00 i 09:30, o quan calgui | `verified` |
| Temperatura superficial detallada · principal | USGS | Landsat 8/9 Collection 2 Level-2 ST, STAC + COG | 30 m | amb nova escena QA-vàlida | `verified` |
| Temperatura superficial detallada · alternativa | NASA/JPL ECOSTRESS; NASA LP DAAC | CMR Search + COG protegit, `ECO_L2T_LSTE.003` | 70 m | adquisició irregular; consulta diària | `requires_credentials` per descarregar |
| NDVI, NDMI i albedo | Copernicus / ESA | CDSE Catalog + OAuth2 + Process API | 10–20 m, sortida a 10 m | amb nova escena L2A vàlida | `requires_credentials` per actualitzar |
| PM2,5 contextual | CAMS / ECMWF | WMS públic | 0,1°, aproximadament 10 km | horària | `verified` com a context supramunicipal |
| Ombra topogràfica a les 15 h | ICGC MDT 5 m + posició solar calculada | GeoTIFF estructural + càlcul diari | 5 m | diària perquè canvien data i posició solar | `verified` com a derivat |
| Sequera forestal i potencial de foc | CREAF / EMF | repositori HTTPS GeoPackage `daily_modelled_forests` | punts forestals amb empremta nativa de 500 × 500 m | execució model diària; la publicació pot tenir retard | `verified` |
| Perill actual d’incendi | EcoRadar sobre fonts oficials documentades | Analysis Engine | cel·les de 100 m | comprovació diària | indicador derivat |

La temperatura superficial activa és sempre la capa local detallada QA-vàlida
més recent entre Landsat i ECOSTRESS. Una escena individual conserva la seva
data d’adquisició. El Landsat vigent és un compost estival multitemporal de 26
escenes candidates, 23 de les quals aporten almenys un píxel vàlid a l’àmbit,
entre el 03.06.2025 i el 25.08.2026; per això no s’etiqueta com una observació
del 25.08.2026. Els productes contextuals de 3–9 km no poden substituir una
capa detallada.

ForestDrought es consulta diàriament, però es conserva la data del model
publicat. Cada punt només s'aplica a la seva empremta forestal nativa de
500 × 500 m: no s'interpola sobre zones sense cel·la ni es presenta com una
observació, una ignició o una alerta oficial.

## Perill actual d’incendi

La fórmula 0–100 és la mateixa que a l’EcoRadar Urbà:

`20% potencial de foc ForestDrought + 20% perill estructural + 15% sequedat
NDMI + 10% temperatura superficial detallada + 10% continuïtat vegetal + 10%
vent/ratxa + 10% humitat relativa baixa + 3% pendent + 2% orientació de solana`.

El component de vent conserva el 10 % i usa el màxim normalitzat entre vent
sostingut i ratxa disponibles. Temperatura de l'aire, precipitació recent,
acumulats de 7/30 dies i dies secs es mostren com a factors causals observats
amb la seva data. El Pla Alfa es mostra en paral·lel com a dada oficial
municipal. No s'afegeix a la puntuació 0–100 ni es representa com si tingués
resolució de 100 m.

La concurrència territorial no intervé en aquesta fórmula; continua disponible
com a lectura temàtica separada.

Els components disponibles es renormalitzen si manca una variable. Una absència
no es converteix en zero. L’índex no és una alerta oficial, una probabilitat
d’ignició ni el Pla Alfa.

## Limitacions

- L’estació XEMA Y4 és puntual i no representa totes les valls, carenes i
  orientacions de l’àmbit. Y4 no publica vent; el component de vent usa CJ
  Organyà, a 9,2 km, com a context oficial proper i no com una mesura feta dins
  la Muntanya d’Alinyà.
- La temperatura Landsat és superficial i la capa vigent és una composició
  estival multitemporal, no una observació actual ni temperatura de l’aire.
- CAMS només s’incorpora com a context supramunicipal.
- L’ombra diària d’Alinyà és estrictament topogràfica: considera pendent i orientació del MDT, però no arbres, edificis ni horitzó llunyà.
- Les escenes Sentinel-2 requereixen credencials gratuïtes CDSE per a
  l’actualització automàtica; cap secret queda dins del repositori.
