# Lectures variables d’EcoRadar Alinyà

## Àmbit i principi de publicació

La comprovació automàtica correspon a la Muntanya d’Alinyà. Cada execució fixa
un únic `checked_at_utc`, encara que les dades d’origen no hagin canviat. La
data de comprovació no substitueix mai la data real de cada observació.

Els JSON empaquetats amb el visor són només una reserva. En producció, la funció
Netlify consulta els tres registres canònics del repositori GitHub:

- `projectes/Alinya/indicators/daily_readings.json`;
- `projectes/Alinya/indicators/daily_history.json`;
- `projectes/Alinya/indicators/current_fire_danger.json`.

## Fonts variables

| Lectura | Font responsable | Servei | Resolució | Actualització | Estat |
| --- | --- | --- | --- | --- | --- |
| Temperatura, humitat, vent i precipitació | Meteocat / Generalitat de Catalunya | XEMA Socrata `nzvn-apee`, estació Y4 | observació puntual | habitualment 30 minuts; comprovació diària | `verified` |
| Temperatura superficial | USGS | Landsat 8/9 Collection 2 Level-2 ST, STAC + COG | 30 m | amb nova escena QA-vàlida | `verified` |
| NDVI, NDMI i albedo | Copernicus / ESA | CDSE Catalog + OAuth2 + Process API | 10–20 m, sortida a 10 m | amb nova escena L2A vàlida | `requires_credentials` per actualitzar |
| PM2,5 contextual | CAMS / ECMWF | WMS públic | 0,1°, aproximadament 10 km | horària | `verified` com a context supramunicipal |
| Perill actual d’incendi | EcoRadar sobre fonts oficials documentades | Analysis Engine | cel·les de 100 m | comprovació diària | indicador derivat |

## Perill actual d’incendi

La fórmula 0–100 és:

`24% perill estructural oficial + 16% temperatura superficial + 16% sequedat
relativa NDMI + 16% potencial de combustible per coberta + 8% concurrència
territorial + 10% vent + 10% humitat relativa baixa`.

Els components disponibles es renormalitzen si manca una variable. Una absència
no es converteix en zero. L’índex no és una alerta oficial, una probabilitat
d’ignició ni el Pla Alfa.

## Limitacions

- L’estació XEMA Y4 és puntual i no representa totes les valls, carenes i
  orientacions de l’àmbit.
- En l’extracte públic comprovat el 23 de juliol de 2026 no constaven registres
  de vent; això es publica com a dada no disponible.
- La temperatura Landsat és superficial i la capa vigent és una composició
  estival, no temperatura de l’aire.
- CAMS només s’incorpora com a context supramunicipal.
- Les escenes Sentinel-2 requereixen credencials gratuïtes CDSE per a
  l’actualització automàtica; cap secret queda dins del repositori.
