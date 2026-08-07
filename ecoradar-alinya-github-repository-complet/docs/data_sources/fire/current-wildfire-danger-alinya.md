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
| Temperatura superficial | Landsat 8/9 C2 L2 ST, USGS, o ECOSTRESS L2T V3, NASA/JPL | STAC/CMR i COG; GeoTIFF normalitzat | 30 o 70 m, reprojecció a EPSG:25831 | Segons nova escena QA-vàlida | política USGS / NASA Earthdata | Landsat `verified`; ECOSTRESS `requires_credentials` |
| NDMI | Sentinel-2 MSI L2A, Copernicus Data Space Ecosystem | OAuth/API de procés; GeoTIFF normalitzat | 10–20 m efectius, reprojecció a 100 m | Segons escena vàlida | Copernicus Data Policy | `verified` |
| Continuïtat vegetal | CLMS HRL Tree Cover Density i Herbaceous Cover 2023 | WMS/GeoTIFF normalitzat | 10 m, reprojecció a 100 m | versió 2023 | Copernicus Data Policy | `verified` |
| Pendent i orientació | Model d'elevacions del terreny 5 m, ICGC | GeoTIFF normalitzat | EPSG:25831, 5 m | edició de la font | CC BY 4.0 ICGC | `verified` |
| Meteorologia | XEMA Y4 Alinyà per humitat i XEMA CJ Organyà per vent, Meteocat | API Socrata `nzvn-apee`; CSV normalitzat | dues observacions puntuals; CJ és a 9,2 km de Y4 | habitualment cada 30 minuts; comprovació automatitzable | Dades obertes Generalitat | `verified` |

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
- vent XEMA: 10 %;
- humitat relativa XEMA invertida: 10 %;
- pendent: 3 %;
- orientació de solana: 2 %.

És exactament la mateixa fórmula i els mateixos pesos que la lectura actual de
l’EcoRadar Urbà. La concurrència territorial no forma part d’aquest índex; es
manté només com a lectura territorial separada. Si una variable no està
disponible, el seu pes no es converteix en zero: es renormalitzen els pesos
realment disponibles i la cel·la queda marcada com a incompleta.

## Exemple d’execució

```bash
python -m ecoradar.connectors.connector_meteocat_xema --location alinya
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
