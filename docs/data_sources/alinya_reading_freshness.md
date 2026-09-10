# Alinyà: actualització, vigència i sincronització

Implementació local de 10.09.2026, preparada sobre el repositori de publicació
`ecoradar-aliny-`, revisió `77e47f0`. No canvia fórmules, pesos, llindars
ni interpretacions ecològiques de Fase 2.

## Contracte i inventari executable

`config/alinya_reading_policies.json` cobreix 36 lectures. Per cadascuna declara
font, URL, periodicitat de publicació, interval de comprovació, llindar operatiu
de vigència (quan existeix), criteri de nova dada, QA, dependències, impacte i
bloquejos. Es reutilitzen les fonts documentades a `alinya_daily_readings.md`,
`official_sources.md`, `sources_inventory.yml`, `fire/basic-wildfire-danger-2024.md`
i les metadades de cada connector. No s'ha creat cap connector de dades nou.

La consulta diària és una política d'EcoRadar, no la periodicitat de publicació.
Sentinel-2 té revisita nominal de cinc dies; Landsat 8/9, de vuit dies combinats.
Els núvols i el QA condicionen la disponibilitat local. No es dedueix caducitat
d'una cartografia sense calendari oficial documentat. OSM és comunitari;
GBIF/iNaturalist és coneixement públic oportunista, no un inventari oficial complet.

Fonts de periodicitat verificades:
- https://sentiwiki.copernicus.eu/web/s2-mission
- https://landsat.usgs.gov/landsat_acq
- https://www.icgc.cat/es/Geoinformacion-y-mapas/Mapas/Mapa-de-cubiertas-del-suelo-de-Cataluna

## Estats i QA

`ACTUAL`: dada vàlida nova dins del llindar. `ÚLTIMA VALIDADA`: conservació de la
darrera validació, versió d'inventari o composició de període. `DESACTUALITZADA`:
edat superior al llindar declarat. `PENDENT QA`: observació provisional, data
futura no justificada o traçabilitat temporal pendent. `SENSE DADA`: sense dada
validada ni reserva documentada. La UI torna a revisar l'edat en obrir-la.

`freshness.last_validated_data_at_utc` no és la data de comprovació.
La sèrie XEMA serveix per recuperar l'últim codi V; els candidats provisionals
continuen identificats. Els acumulats provisionals no s'etiqueten validats.
Una composició Landsat conserva inici i final de les escenes que aporten píxels.
Les edicions sense data d'observació acreditada conserven la versió i la data de
consulta separadament. No s'inventa una data a partir de l'any del producte.

## Automatització implementada

- Vigilància diària dels catàlegs estructurals i inventaris: estat de servei,
  hash del document de publicació i canvi candidat. Un canvi d'HTML no valida
  una nova cartografia. La promoció queda explícitament pendent del QA específic.
- Es conserva el circuit de dades periòdiques existent: XEMA, Pla Alfa, CAMS,
  ForestDrought, Sentinel-2, Landsat, ECOSTRESS i ombra.
- La consulta Landsat deixa de tenir un final fix el 15.09.2026, conservant la
  selecció estival i el càlcul de mediana existents.
- Els canvis exclusius de comprovació o `snapshot_id` no activen recàlcul de LST.
- Els canvis vàlids de Sentinel-2/LST activen també el perill integrat existent.
- El registre emet un identificador de contingut; comprovacions sense canvi no
  creen una nova identitat. L'històric conserva els registres anteriors i Git
  conserva els fitxers versionats. Correccions de valor a igual data es registren.
- Visor i generador d'informes mostren vigència i snapshot. El visor rebutja una
  actualització remota amb un snapshot diferent del dels seus mapes empaquetats,
  evitant barrejar dades noves amb RADAR o mapes antics. Cal recarregar el visor
  publicat complet quan hi ha una versió nova.

## Límits pendents: no és una activació en producció

La vigilància estructural està implementada, però la promoció automàtica de noves
edicions i la reconstrucció de tota la cartografia encara requereixen un QA
específic. Això queda com a bloqueig per lectura, no com una actualització feta.
Sentinel-2 necessita credencials CDSE per descarregar i validar SCL; el catàleg
local ja identifica candidats recents. ECOSTRESS requereix l'accés Earthdata.

La publicació ha quedat bloquejada per autenticació GitHub (Git sense usuari;
connector GitHub retorna 404). No s'han actualitzat la web pública ni els PDF
publicats. Les modificacions del circuit s'han validat localment i s'han deixat
preparades al repositori local. No s'ha substituït cap font provisional per una
dada inventada ni s'ha executat una actualització completa de totes les fonts.

La taula de resultats es genera a `projectes/Alinya/reports/reading_freshness_audit.md`.
