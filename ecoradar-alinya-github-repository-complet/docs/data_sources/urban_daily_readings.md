# EcoRadar Urbà — lectures variables i actualització diària

Data de verificació: 2026-07-25

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
| Cabal del Valira | CHE / SAIH Ebre; estació A022, riu Valira a la Seu d'Urgell | valors actuals de l'estació d'aforament, observació puntual | 15 minuts | `verified` | Mostrar la darrera observació provisional amb la seva data real; no extrapolar-la a tot el riu ni convertir-la en alerta. |
| Cabal del Segre | CHE / SAIH Ebre; estació A023, riu Segre a la Seu d'Urgell | valors actuals de l'estació d'aforament, observació puntual | 15 minuts | `verified` | Mostrar la darrera observació provisional amb la seva data real; no sumar-la amb la del Valira ni convertir-la en alerta. |
| Temperatura superficial detallada · font principal | USGS Landsat Collection 2 Level-2 ST | STAC + COG, 30 m | segons adquisició i QA | `verified` | Substituir només per una escena posterior amb píxels locals vàlids després de QA. |
| Temperatura superficial detallada · reserva | NASA/JPL ECOSTRESS `ECO_L2T_LSTE.003` | CMR Search + COG, 70 m | adquisició irregular des de l'ISS | `requires_credentials` | Consultar el catàleg cada dia. Si una escena local posterior a Landsat supera les màscares `cloud_mask`, `water_mask` i QC, usar-la com a lectura territorial; la descàrrega requereix el secret `EARTHDATA_TOKEN`. |
| Temperatura superficial contextual | Copernicus CLMS LST Global 3 km Hourly V3 | CDSE Sentinel Hub BYOC, ~3 km, horària | horària | `requires_credentials` | Reserva contextual municipal o supramunicipal. No substituir-ne els píxels per un mapa de carrers ni combinar-la com si tingués 30-70 m. |
| Temperatura terrestre contextual | Copernicus C3S ERA5-Land | CDS API, 0,1° (~9 km natius), horària | diària | `requires_credentials` | Últim recurs contextual i de continuïtat temporal. No és una observació tèrmica urbana ni una capa de detall local. |
| NDVI, NDMI i albedo | Copernicus Sentinel-2 MSI L2A | CDSE STAC + Process API, sortida 10 m | segons adquisició sense núvols | `verified` / `requires_credentials` | Actualitzar només amb una escena posterior que superi la màscara SCL; els secrets OAuth només viuen a GitHub Actions. |
| Qualitat de l'aire | CAMS European Air Quality Forecast, ECMWF / Copernicus | WMS públic, PM2,5 a 0,1 graus | horària | `verified` | Mostrar com a context supramunicipal, mai com a mesura de carrer. |
| Confort tèrmic | Derivat de temperatura, humitat i vent XEMA | temperatura aparent de Steadman | amb cada observació XEMA | `verified` com a indicador derivat | No és UTCI, WBGT, risc clínic ni confort espacial de carrer. |
| Ombra | ICGC LiDAR Territorial v3.1 + posició solar | DSM/DTM i vegetació a 2 m | càlcul diari a les 15.00, hora local | `verified` com a indicador derivat | Recalcular amb data, hora, edificis, arbres i relleu; no tornar a processar el LiDAR. |
| Potencial de frescor dels carrers | Indicador EcoRadar sobre ombra i capçada LiDAR, LST detallada, HRL Imperviousness, orientació, amplada i verd OSM | trams de fins a 75 m | recalculat diàriament; canvia quan canvia una entrada | `verified` com a indicador derivat | Classificar alt, mitjà o baix; no presentar-lo com a temperatura mesurada al carrer. |
| Utilitat climàtica potencial dels equipaments | Indicador EcoRadar sobre equipaments i parcs/jardins OSM, LiDAR, LST, accessibilitat, horaris, aigua i connexió viària fresca | candidats puntuals | recalculat diàriament; canvia quan canvia una entrada | `verified` com a indicador derivat | No etiquetar cap candidat com a refugi climàtic oficial fins a la validació municipal. El component de població vulnerable queda nul si no hi ha detall espacial verificat. |
| Perill actual d'incendi | Índex EcoRadar documentat a `fire/current-wildfire-danger-urban.md`, amb ForestDrought CREAF/EMF | EcoRadar 100 m; component forestal modelitzat natiu de 500 m | comprovació diària després de XEMA, ForestDrought i noves escenes | `verified` com a indicador derivat | Recalcular amb les variables disponibles, conservar la data real del model CREAF i reduir confiança si una font no s'ha actualitzat. |
| Situació hidrològica actual | Indicador EcoRadar sobre cabal i nivell CHE A022/A023, tendència recent, pluja XEMA, previsió municipal Meteocat, SNCZI Q100 i escorrentia potencial | CHE cada 15 minuts; Meteocat operatiu; context territorial estructural | càlcul diari | `verified` com a indicador derivat | Classificar normal, vigilància, elevada o molt elevada amb corroboració de pluja. No afirmar inundació actual ni substituir avisos oficials. |

## Fonts oficials verificades

- XEMA observacions: <https://analisi.transparenciacatalunya.cat/d/nzvn-apee>.
- XEMA metadades de variables: <https://analisi.transparenciacatalunya.cat/d/4fb2-n3yi>.
- CHE / SAIH Ebre, A022 Valira: <https://www.saihebro.com/tiempo-real/estacion-aforos-A022-valira-seu>.
- CHE / SAIH Ebre, A023 Segre: <https://www.saihebro.com/tiempo-real/estacion-aforos-A023-segre-seu>.
- CHE / SAIH Ebre, avís de provisionalitat: <https://www.saihebro.com/info/datos-provisionales-ebro>.
- Meteocat, predicció municipal 252038: <https://www.meteo.cat/prediccio/municipal/252038>.
- OMS, guies globals de qualitat de l'aire 2021: <https://www.who.int/publications/i/item/9789240034228/>.
- CAMS European Air Quality Forecast, fitxa oficial: <https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts>.

## Actualització intradiària a demanda

El visor ofereix el botó **«Actualitza dades»** únicament quan la font directa
publica amb una freqüència inferior a 24 hores i permet una consulta puntual
automatitzable:

| Lectura | Font consultada pel botó | Freqüència declarada |
|---|---|---|
| Temperatura de l'aire | Meteocat XEMA, estació CD, variable 32 | 30 minuts |
| Humitat relativa | Meteocat XEMA, estació CD, variable 33 | 30 minuts |
| Vent | Meteocat XEMA, estació CD, variables 30, 31 i 50 | 30 minuts |
| Precipitació | Meteocat XEMA, estació CD, variable 35 | 30 minuts |
| Cabal del Valira | CHE/SAIH, estació A022 | 15 minuts |
| Cabal del Segre | CHE/SAIH, estació A023 | 15 minuts |

Cada clic consulta només la font i la variable o estació de la lectura
seleccionada. Per a XEMA utilitza `/api/refresh-reading`. Per als cabals A022
i A023 prova primer la consulta directa als dominis oficials del SAIH, que
permeten CORS, i utilitza `/api/refresh-reading` com a reserva. En carregar el
visor també es consulten automàticament les dues estacions i, mentre la pàgina
roman oberta i visible, la consulta es repeteix cada 15 minuts d'acord amb la
freqüència declarada de la font.
Quan la CHE encara no ha publicat un interval posterior, el requadre indica que
la dada ja està al dia i mostra tant l'hora de l'última observació oficial com
l'hora de la nova comprovació. Si la consulta retorna una observació més antiga,
el visor conserva explícitament la més recent; si la CHE revisa el valor sense
canviar-ne l'instant, el visor l'identifica com a dada revisada. Si la consulta falla, mostra
el motiu concret retornat pel servidor: xarxa, temps d'espera, codi HTTP,
format, JSON o senyal absent. La consulta puntual actualitza visualment la dada
i l'hora del requadre sense recarregar la pàgina. La incorporació
permanent a l'històric continua corresponent al procés diari automatitzat, per
evitar que clics d'usuari generin registres històrics incomplets o duplicats.

No es mostra el botó en temperatura superficial satel·litària, ombra diària,
NDVI, NDMI, albedo, potencial de frescor, utilitat potencial dels equipaments,
situació hidrològica derivada, cobertes, impermeabilització, pendent,
inundabilitat ni altres capes diàries, periòdiques o estructurals. Els cabals
directes CHE continuen tenint el seu botó propi.
- USGS Landsat C2 L2 ST: <https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-st>.
- NASA/JPL ECOSTRESS L2T LST V3: <https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.003>.
- NASA CMR Search API: <https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html>.
- Copernicus CLMS LST Global 3 km Hourly V3: <https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/clms/bio-geophysical-parameters/temperature-and-reflectance/land-surface-temperature/lst_global_3km_hourly_v3.html>.
- Copernicus C3S ERA5-Land: <https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview>.
- Copernicus Data Space Sentinel-2 L2A: <https://dataspace.copernicus.eu/>.
- CAMS European air-quality forecast: <https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts>.
- ICGC LiDAR Territorial v3.1: <https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Elevacions/Elevacions-territorial/LiDAR-Territorial>.
- CREAF ForestDrought: <https://laboratoriforestal.creaf.cat/forestdrought_app/>.
- CREAF/EMF, repositori públic de GeoPackage diaris: <https://data-emf.creaf.cat/public/gpkg/daily_modelled_forests/>.
- Temperatura aparent de Steadman, explicació oficial del Bureau of Meteorology: <https://www.bom.gov.au/glossary>.

## Capes estructurals excloses del procés diari

No es recalculen diàriament: pendent, orientació, relleu, impermeabilització, zones inundables oficials, escorrentia potencial, edificis, xarxa viària, zones verdes, equipaments i perill estructural d'incendi. Només es reutilitzen com a entrades estàtiques quan un indicador diari ho requereix.

## Freqüència, historial i regla de no duplicació

La configuració executable és `config/urban_daily_readings.json`. La font XEMA publica habitualment cada 30 minuts, el SAIH Ebro transmet cabals i nivells cada 15 minuts i CAMS té camps horaris, però el procés automatitzat d’aquesta fitxa els comprova una vegada al dia i en desa únicament el temps de referència més nou. També consulta la previsió municipal de precipitació de Meteocat. ForestDrought s'interroga cada dia retrocedint per dates fins a trobar l'últim GeoPackage publicat; la seva data de model es conserva sense confondre-la amb la data de comprovació. Ombra, potencial de frescor, utilitat potencial dels equipaments, situació hidrològica i perill actual es recalculen diàriament; Landsat, ECOSTRESS i Sentinel-2 només canvien quan existeix una nova escena local vàlida.

## Jerarquia tèrmica i regla de substitució

La lectura de temperatura superficial no depèn d'una sola missió:

1. Landsat C2 L2 ST, 30 m, és la font principal de detall.
2. ECOSTRESS L2T LST V3, 70 m, pot substituir-la quan disposa d'una adquisició local més recent i QA-vàlida. L'escena del 21/07/2026 15:32 UTC consta al catàleg CMR per a l'àmbit ampliat de la Seu; la seva incorporació numèrica queda condicionada a la descàrrega autenticada i a la validació dels píxels.
3. CLMS LST 3 km hourly V3 i ERA5-Land (~9 km natius) només poden mantenir un valor contextual agregat. No alimenten el raster urbà, la SUHI de carrer ni una mitjana de l'àmbit detallat.

En cada execució, `checked_at_utc` identifica la comprovació real del dia i
`data_at_utc` conserva l'instant d'adquisició de la font seleccionada. El visor
ha de mostrar tots dos instants tant a la fitxa detallada sota el mapa com al
botó lateral de la lectura temàtica corresponent. No es canvia la data d'una
escena antiga per la data actual, i no es degrada el detall espacial
silenciosament.

El sistema separa dos registres:

- `daily_readings_checks.jsonl`: una entrada per comprovació del procés.
- `daily_readings_observations.jsonl`: una entrada només quan canvien la data real o el valor d'una lectura.

Això evita convertir una comprovació diària en una observació nova i evita duplicar una escena satel·litària antiga. El registre JSONL és append-only i la fitxa publica totes les observacions disponibles per permetre comparar qualsevol data registrada.

## Interpretació pública del valor

Cada cel·la de lectura incorpora **«Què significa»** abans de la metodologia.
El text interpreta el valor actual sense convertir-lo en un diagnòstic clínic,
una alerta oficial ni una classificació universal quan la font no ho permet.
Les lectures remotes actualitzen també aquesta interpretació, i les consultes
intradiàries recalculen el text del valor modificat sense recarregar la pàgina.

- Els valors meteorològics puntuals s'expliquen conjuntament amb les variables
  que en modifiquen l'efecte; temperatura, humitat o vent no són bons o dolents
  per si sols.
- Els cabals CHE es descriuen com a observacions provisionals del punt
  d'aforament. Sense llindars oficials específics no es qualifiquen com a
  normals o alts.
- NDVI, NDMI i albedo publiquen la **mitjana espacial real** de l'última escena
  Sentinel-2 vàlida. NDVI i NDMI es llegeixen amb les classes de la llegenda;
  l'albedo s'explica també com a fracció aproximada de radiació reflectida.
- La temperatura superficial es classifica només dins l'escala cromàtica de la
  capa EcoRadar; no és temperatura de l'aire ni un llindar sanitari.
- Per PM2,5, l'OMS 2021 estableix 15 µg/m³ per a la mitjana de 24 hores i
  5 µg/m³ per a la mitjana anual. CAMS aporta aquí un camp horari modelitzat a
  0,1 graus, aproximadament 10 km. Per tant, el visor només indica si el valor
  puntual queda per sota o al nivell de la referència de 24 hores, però no
  afirma que l'aire sigui bo o dolent ni que la guia es compleixi o se superi.
- Els índexs derivats EcoRadar expliquen la seva classe i reiteren si no són una
  mesura directa, un refugi oficial, una alerta d'incendi o un avís
  d'inundació.

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
