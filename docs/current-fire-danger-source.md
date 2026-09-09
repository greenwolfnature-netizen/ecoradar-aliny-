# Perill d’incendi actual EcoRadar — Muntanya d’Alinyà

## Abast

Lectura analítica derivada a 100 m per a la Muntanya d’Alinyà. No és una
alerta oficial, una probabilitat d’ignició, el Pla Alfa ni el mapa diari
oficial de perill.

## Fonts documentades

| Component | Font i organisme responsable | Servei i format | CRS / resolució | Actualització | Llicència | Estat |
| --- | --- | --- | --- | --- | --- | --- |
| Perill estructural | Mapa bàsic de perill d’incendi forestal 2024, Generalitat de Catalunya | Descàrrega oficial GeoTIFF | EPSG:25831, 100 m | Edició 2024 | Dades obertes Generalitat | `verified` |
| Potencial de foc i sequera forestal | ForestDrought, CREAF / EMF | repositori HTTPS GeoPackage | cel·les forestals natives de 500 × 500 m | model diari; publicació amb possible retard | reutilització pública; identificador formal pendent | `verified` |
| Temperatura superficial | Landsat 8/9 C2 L2 ST, USGS, o ECOSTRESS L2T V3, NASA/JPL | STAC/CMR i COG; GeoTIFF normalitzat | 30 o 70 m, reprojecció a EPSG:25831 | Segons nova escena QA-vàlida | política USGS / NASA Earthdata | compost Landsat `verified` com a context de període; ECOSTRESS `requires_credentials` |
| NDMI | Sentinel-2 MSI L2A, Copernicus Data Space Ecosystem | OAuth/API de procés; GeoTIFF normalitzat | 10–20 m efectius, reprojecció a 100 m | Segons escena vàlida | Copernicus Data Policy | `verified` |
| Continuïtat vegetal | CLMS HRL Tree Cover Density i Herbaceous Cover 2023 | WMS/GeoTIFF normalitzat | 10 m, reprojecció a 100 m | versió 2023 | Copernicus Data Policy | `verified` |
| Pendent i orientació | Model d'elevacions del terreny 5 m, ICGC | GeoTIFF normalitzat | EPSG:25831, 5 m | edició de la font | CC BY 4.0 ICGC | `verified` |
| Meteorologia | XEMA Y4 Alinyà per temperatura, humitat i precipitació; XEMA CJ Organyà per vent i ratxes, Meteocat | API Socrata `nzvn-apee`; CSV normalitzat | dues observacions puntuals; CJ és a 9,2 km de Y4 | habitualment cada 30 minuts; comprovació diària | Dades obertes Generalitat | `verified` |
| Pla Alfa | Cos d'Agents Rurals / Generalitat de Catalunya | vista pública ArcGIS FeatureServer municipal "Avui" | nivell oficial municipal 0–4 | 00:00 i 09:30, o quan calgui | servei públic oficial; llicència específica no publicada | `verified` |

## Fórmula

Tots els components disponibles es normalitzen a 0–100. La temperatura
superficial, l’NDMI i el pendent utilitzen P5–P95 dins l’àmbit. La meteorologia utilitza P5–P95 dels darrers
35 dies XEMA. L’NDMI i la humitat relativa s’inverteixen perquè els valors
baixos representin més sequedat.

ForestDrought aporta `100 × max(SFP, CFP) / 9` dins de cada empremta forestal
nativa de 500 × 500 m. No s’interpola a zones sense cel·la CREAF. La
continuïtat vegetal combina al 50 % la fracció vegetal de la cel·la i al 50 %
la mitjana del veïnat 3 × 3. L’orientació usa una transformació contínua amb
màxim a solana sud i mínim a nord.

Pesos:

- potencial de foc ForestDrought CREAF: 20 %;
- perill estructural oficial: 20 %;
- sequedat relativa NDMI: 15 %;
- temperatura superficial detallada: 10 %;
- continuïtat vegetal: 10 %;
- vent i ratxa XEMA: 10 %; s'usa el màxim dels dos valors normalitzats disponibles;
- humitat relativa XEMA invertida: 10 %;
- pendent: 3 %;
- orientació de solana: 2 %.

Són els pesos base de la fórmula compartida amb la lectura actual de
l’EcoRadar Urbà. La concurrència territorial no forma part d’aquest índex; es
manté només com a lectura territorial separada. En cada execució, el pes base
d’una variable dinàmica es multiplica pel seu factor de frescor. Després es
renormalitzen els pesos efectius temporalment elegibles i espacialment
disponibles a cada cel·la. Una dada absent o descartada mai es converteix en
zero i, per tant, no pot abaixar artificialment el perill.

## Frescor temporal aplicada al càlcul

| Variable | Tipus | Pes complet | Pes zero / només context | Tractament intermedi |
| --- | --- | --- | --- | --- |
| Vent i ratxa XEMA | dinàmica | fins a 3 h | a partir de 24 h | reducció lineal |
| Humitat relativa XEMA | dinàmica | fins a 3 h | a partir de 24 h | reducció lineal |
| ForestDrought CREAF | dinàmica | fins a 72 h | a partir de 240 h (10 dies) | reducció lineal |
| NDMI Sentinel-2 | dinàmica | fins a 240 h (10 dies) | a partir de 720 h (30 dies) | reducció lineal |
| LST Landsat/ECOSTRESS | dinàmica | fins a 192 h (8 dies) | a partir de 576 h (24 dies) | reducció lineal |
| Perill estructural oficial | estructural | sempre vigent fins a nova edició | no caduca diàriament | pes complet |
| Continuïtat vegetal CLMS | estructural | sempre vigent fins a nova edició | no caduca diàriament | pes complet |
| Pendent i orientació ICGC | estructurals | sempre vigents fins a nova edició | no caduquen diàriament | pes complet |

Els terminis responen a la naturalesa i cadència de cada font: XEMA és
subdiària; ForestDrought és un model diari amb possible retard; Sentinel-2 té
revisita freqüent però pot quedar impedit pels núvols; Landsat té una revisita
combinada aproximada de vuit dies i també depèn de la qualitat de l’escena. El
factor és 1 dins el termini de pes complet, disminueix linealment fins a 0 i
queda exclòs en superar el termini màxim. El valor antic continua visible al
popup, amb data i estat «massa antiga», exclusivament com a context.

La frescor només s’aplica a observacions individuals amb data d’adquisició. El
compost Landsat actual agrega 26 escenes candidates (23 amb píxels vàlids) del
03.06.2025 al 25.08.2026: es mostra com a context multitemporal i no rep el pes
dinàmic corresponent a una observació del 25.08.2026.

La meteorologia que sosté una lectura «d’avui» és obligatòria: si tant el vent
com la humitat superen el límit màxim o no estan disponibles, el procés no
publica un índex nou i conserva l’últim producte vàlid amb la seva data. La
temperatura de l’aire i la precipitació es classifiquen com a context actual
fins a 3 h, recent entre 3 i 24 h, i massa antic després de 24 h. El Pla Alfa,
que no puntua, es marca actual fins a 18 h, recent fins a 72 h i massa antic a
partir d’aquest moment.

La lectura operativa que acompanya el mapa incorpora també, sense alterar els
pesos, la temperatura de l'aire, la pluja de les darreres 24 hores, els
acumulats observats de 7 i 30 dies i els dies consecutius sense almenys 1,0 mm
diari. Els acumulats només es publiquen amb un mínim del 80 % dels períodes
XEMA de 30 minuts; un buit no es tracta com pluja zero. No es mostra una
anomalia climàtica perquè encara no hi ha una normal oficial homogènia de Y4
verificada i integrada.

El Pla Alfa es mostra com a context operatiu oficial municipal, amb la seva
data de dada i de comprovació. No s'incorpora numèricament a l'índex EcoRadar:
fer-ho duplicaria part del senyal meteorològic i atribuiria falsa precisió de
100 m a una decisió oficial municipal.

## Exemple d’execució

```bash
python -m ecoradar.connectors.connector_meteocat_xema --location alinya
python -m ecoradar.connectors.connector_pla_alfa
python tools/fetch_alinya_creaf_forestdrought.py
python tools/fetch_alinya_ecostress.py
python tools/select_alinya_surface_temperature.py
python tools/calculate_alinya_current_fire_danger.py
python tools/export_ecoradar_alinya_netlify.py
```

## Limitacions

- Y4 aporta humitat però no publica vent. El vent prové de CJ Organyà, a 9,2 km
  de Y4; cap de les dues observacions descriu cada vessant d’un àmbit de 5.464
  ha i fort gradient altitudinal.
- L’absència d’una variable XEMA en una comprovació no demostra absència del
  fenomen meteorològic.
- La temperatura superficial detallada no és temperatura de l’aire ni una
  observació necessàriament simultània amb XEMA.
- L’NDMI és un proxy espectral relatiu, no humitat fina del combustible.
- ForestDrought és un model, no una observació, ignició o alerta oficial.
- La continuïtat HRL no mesura càrrega, espècie ni estructura vertical del combustible.
- La quadrícula oficial diària té una resolució massa grossa per interpretar
  diferències internes de la Muntanya d’Alinyà. Es conserva com a context
  oficial, però no s’interpola ni es representa com una superfície detallada.
- Cal consultar sempre Pla Alfa, avisos oficials i instruccions d’emergència.

## Correcció de la font del Pla Alfa — 2026-09-08

Estat: `verified`. La pàgina oficial d’Interior enllaça l’experiència
`2cf7ebbe492f401db826cb21eae9bfae`, que utilitza el webmap «Pla Alfa Avui»
`a696da9dc39f461dadfc0f22e910b4aa`. Les capes municipals vigents del webmap
apunten a `Pla_Alfa_Municipal_Avui_FL_alternatiu_VW/FeatureServer/0`
(item `02c89a3c7f9a4b269aa3ddd117d48691`). La capa anterior
`Pla_Alfa_Municipal_Avui_FL_2_view` encara responia nivell 0, amb dades
del 18 d’agost; la vigent retorna `PERIL_M=2` per `CODIMUNI=259084`
(Fígols i Alinyà) el 8 de setembre.

URL oficial del servei:
https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services/Pla_Alfa_Municipal_Avui_FL_alternatiu_VW/FeatureServer/0

Es mantenen organisme, format JSON/ArcGIS FeatureServer, CRS EPSG:25831,
variables CODIMUNI/NOMMUNI/NOMCOMAR/PERIL_M, cadència i condicions d’ús
documentats. Exemple: `/query?where=CODIMUNI%3D%27259084%27&outFields=*&returnGeometry=false&f=json`.
Correcció exclusiva del Pla Alfa; sense recalcular l’índex EcoRadar ni
canviar la data de comprovació global de les altres lectures.
