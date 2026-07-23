# EcoRadar Urbà — lectures variables i actualització diària

Data de verificació: 2026-07-22

## Regla d'actualització

El procés es comprova cada dia, però una lectura només canvia quan hi ha una observació nova o quan es pot recalcular per a la data i l'hora del dia. L'última dada vàlida es conserva amb la seva data real. Una fallada de servei no converteix una dada antiga en una dada d'avui.

Estats públics obligatoris:

- `actualitzada avui`: la data real de la dada o del càlcul correspon al dia de la comprovació.
- `última dada disponible`: és l'última observació vàlida, però no correspon al dia de la comprovació.
- `dada no disponible`: no hi ha una font o un càlcul local defensable.

## Matriu de fonts i decisions

| Lectura | Font i organisme | Servei / resolució | Actualització | Estat | Decisió |
| --- | --- | --- | --- | --- | --- |
| Temperatura de l'aire | XEMA, Servei Meteorològic de Catalunya; estació CD | Socrata `nzvn-apee`, variable 32, observació puntual | 30 minuts | `verified` | Mostrar la darrera observació vàlida o provisional amb data UTC. |
| Humitat relativa | XEMA, Servei Meteorològic de Catalunya; estació CD | Socrata `nzvn-apee`, variable 33 | 30 minuts | `verified` | Mostrar la darrera observació i la seva validació. |
| Vent | XEMA, Servei Meteorològic de Catalunya; estació CD | variables 30, 31, 50 i 51 | 30 minuts | `verified` | Mostrar velocitat, ratxa i direcció disponibles. |
| Precipitació | XEMA, Servei Meteorològic de Catalunya; estació CD | variable 35, mm per període | 30 minuts | `verified` | Sumar només els períodes del dia civil local disponibles. |
| Temperatura superficial | USGS Landsat Collection 2 Level-2 ST | STAC + COG, 30 m | segons adquisició i QA | `verified` | Substituir només per una escena posterior amb píxels locals vàlids després de QA. |
| NDVI, NDMI i albedo | Copernicus Sentinel-2 MSI L2A | CDSE STAC + Process API, sortida 10 m | segons adquisició sense núvols | `verified` / `requires_credentials` | Actualitzar només amb una escena posterior que superi la màscara SCL; els secrets OAuth només viuen a GitHub Actions. |
| Qualitat de l'aire | CAMS European Air Quality Forecast, ECMWF / Copernicus | WMS públic, PM2,5 a 0,1 graus | horària | `verified` | Mostrar com a context supramunicipal, mai com a mesura de carrer. |
| Confort tèrmic | Derivat de temperatura, humitat i vent XEMA | temperatura aparent de Steadman | amb cada observació XEMA | `verified` com a indicador derivat | No és UTCI, WBGT, risc clínic ni confort espacial de carrer. |
| Ombra | ICGC LiDAR Territorial v3.1 + posició solar | DSM/DTM i vegetació a 2 m | càlcul diari a les 15.00, hora local | `verified` com a indicador derivat | Recalcular amb data, hora, edificis, arbres i relleu; no tornar a processar el LiDAR. |
| Carrers frescos | No hi ha inventari municipal georeferenciat d'arbrat ni observacions tèrmiques de carrer | — | — | `blocked` | Mostrar `dada no disponible`; no convertir OSM o una escena Landsat en frescor observada del carrer. |
| Utilitat climàtica dels refugis | No hi ha xarxa municipal oficial de refugis publicada i georeferenciada | — | — | `blocked` | Mostrar `dada no disponible`; els equipaments OSM no es certifiquen com a refugis. |
| Perill actual d'incendi | Índex EcoRadar documentat a `fire/current-wildfire-danger-urban.md` | graella de 100 m | diària després de XEMA i noves escenes | `verified` com a indicador derivat | Recalcular amb les variables disponibles i reduir confiança si una font no s'ha actualitzat. |
| Situació actual d'escorrentia o inundació | No hi ha model hidrològic operatiu local verificat ni una observació de cabal representativa integrada | — | — | `pending_verification` | Mostrar `dada no disponible`. La pluja XEMA, el proxy estructural d'escorrentia i la làmina SNCZI T=100 no demostren una inundació actual. |

## Fonts oficials verificades

- XEMA observacions: <https://analisi.transparenciacatalunya.cat/d/nzvn-apee>.
- XEMA metadades de variables: <https://analisi.transparenciacatalunya.cat/d/4fb2-n3yi>.
- USGS Landsat C2 L2 ST: <https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-st>.
- Copernicus Data Space Sentinel-2 L2A: <https://dataspace.copernicus.eu/>.
- CAMS European air-quality forecast: <https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts>.
- ICGC LiDAR Territorial v3.1: <https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Elevacions/Elevacions-territorial/LiDAR-Territorial>.
- Temperatura aparent de Steadman, explicació oficial del Bureau of Meteorology: <https://www.bom.gov.au/glossary>.

## Capes estructurals excloses del procés diari

No es recalculen diàriament: pendent, orientació, relleu, impermeabilització, zones inundables oficials, escorrentia potencial, edificis, xarxa viària, zones verdes, equipaments i perill estructural d'incendi. Només es reutilitzen com a entrades estàtiques quan un indicador diari ho requereix.

## Freqüència, historial i regla de no duplicació

La configuració executable és `config/urban_daily_readings.json`. La font XEMA publica habitualment cada 30 minuts i CAMS té camps horaris, però el procés automatitzat d’aquesta fitxa els comprova una vegada al dia i en desa únicament el temps de referència més nou. Ombra i perill actual es recalculen diàriament perquè depenen de les condicions del dia; Landsat i Sentinel-2 només canvien quan existeix una nova escena local vàlida; les lectures municipals o oficials bloquejades només canviaran quan es verifiqui una font nova.

El sistema separa dos registres:

- `daily_readings_checks.jsonl`: una entrada per comprovació del procés.
- `daily_readings_observations.jsonl`: una entrada només quan canvien la data real o el valor d'una lectura.

Això evita convertir una comprovació diària en una observació nova i evita duplicar una escena satel·litària antiga. El registre JSONL és append-only i la fitxa publica totes les observacions disponibles per permetre comparar qualsevol data registrada.

## Tendència

La variació percentual es calcula respecte de l'observació anterior real de la mateixa lectura. Una variació absoluta igual o inferior al 0,5 % es considera estable. `↑ millora` i `↓ empitjora` només s'utilitzen quan existeix una direcció metodològicament definida: menys perill, menys PM2,5 o menys càrrega tèrmica en context de calor; i més NDVI, NDMI o ombra. Temperatura de l'aire, humitat, vent, precipitació i albedo no tenen una direcció universalment millor; en aquests casos es mostra `canvi sense valoració` i no s'inventa una millora ecològica.

## Índex de confiança

L'índex és metodològic, no oficial. Combina disponibilitat (40 %), frescor respecte de la freqüència esperada (35 %) i qualitat (25 %). Els factors de qualitat són: dada validada 100 %, QA satel·litària 95 %, indicador derivat documentat 85 %, XEMA provisional 75 %, model supramunicipal 65 % i dada no disponible 0 %. El resultat és `Alta` a partir de 80 %, `Mitjana` entre 55 i 79 %, i `Baixa` per sota de 55 %. La fitxa mostra els tres components perquè el percentatge sigui auditable.

## Alertes

Les alertes no substitueixen avisos oficials:

- Perill actual EcoRadar: `alt` a partir de 60/100 i `molt alt o extrem` a partir de 80/100, segons les categories internes documentades de l'índex.
- Temperatura superficial: 52 °C, llindar cromàtic de cribratge de la capa LST; no és un llindar sanitari.
- PM2,5: 15 µg/m³ com a referència de la guia OMS 2021 de 24 hores. Com que CAMS aporta un camp modelitzat puntual, només activa un avís de cribratge i no una declaració de superació normativa.
- Temperatura aparent: 32 °C com a llindar operatiu EcoRadar de cribratge; no és UTCI, WBGT ni un avís oficial.

Meteocat defineix els avisos de calor amb el percentil 98 local i els avisos de vent o precipitació amb llindars i períodes específics. EcoRadar no substitueix aquests avisos ni aplica el llindar d'un municipi sense integrar-ne el valor oficial corresponent.

## Publicació dinàmica del registre

El visor publicat consulta `/api/daily-readings` en cada càrrega amb memòria cau
desactivada. La funció de Netlify llegeix els registres canònics del repositori
després de l'última execució automàtica i retorna el seu `checked_at_utc`; no
substitueix aquest instant per l'hora en què la funció ha servit la resposta.
`served_at_utc` només descriu el transport.

Els fitxers `metadata/daily_readings.json`, `metadata/daily_history.json` i
`metadata/current_fire_danger.json` inclosos al paquet són exclusivament una
reserva. El navegador els manté mentre consulta l'API i els identifica com a
reserva si la consulta falla. La funció rebutja com a font primària una URL del
mateix origen del desplegament per evitar que un paquet antic es presenti com
una comprovació actual.

Cada execució diària fixa un únic `ECORADAR_CHECKED_AT_UTC` i el propaga als
tres registres. Per tant, la comprovació genera un canvi auditable i un commit
encara que les observacions i els valors calculats siguin idèntics als de
l'execució anterior.
