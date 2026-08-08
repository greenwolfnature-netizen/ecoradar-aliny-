# Perill d’incendi actual EcoRadar — Muntanya d’Alinyà

## Abast

Lectura analítica derivada a 100 m per a la Muntanya d’Alinyà. No és una
alerta oficial, una probabilitat d’ignició, el Pla Alfa ni el mapa diari
oficial de perill.

## Fonts documentades

| Component | Font i organisme responsable | Servei i format | CRS / resolució | Actualització | Llicència | Estat |
| --- | --- | --- | --- | --- | --- | --- |
| Perill estructural | Mapa bàsic de perill d’incendi forestal 2024, Generalitat de Catalunya | Descàrrega oficial GeoTIFF | EPSG:25831, 100 m | Edició 2024 | Dades obertes Generalitat | `verified` |
| Temperatura superficial | Landsat 8/9 Collection 2 Level-2, USGS | STAC i COG; GeoTIFF normalitzat | 30 m, reprojecció a EPSG:25831 | Segons escena | Domini públic USGS | `verified` |
| NDMI | Sentinel-2 MSI L2A, Copernicus Data Space Ecosystem | OAuth/API de procés; GeoTIFF normalitzat | 10–20 m efectius, reprojecció a 100 m | Segons escena vàlida | Copernicus Data Policy | `verified` |
| Coberta / combustible potencial | Mapa de cobertes del sòl 2024, ICGC | WMS/GeoTIFF i vector normalitzat | EPSG:25831 | Edició 2024 | CC BY 4.0 ICGC | `verified` |
| Concurrència territorial | Derivat EcoRadar de coberta, hàbitat, pendent, orientació, altitud, accessibilitat i incendis històrics oficials | GeoJSON local normalitzat | EPSG:25831, 100 m | Quan canvien les entrades | Mateixes llicències que les fonts | `verified` com a anàlisi |
| Meteorologia | Dades meteorològiques XEMA, estació Y4 Alinyà, Meteocat | API Socrata `nzvn-apee`; CSV normalitzat | Observació puntual | Habitualment cada 30 minuts; comprovació automatitzable | Dades obertes Generalitat | `verified` |

## Fórmula

Tots els components disponibles es normalitzen a 0–100. La temperatura
superficial i l’NDMI utilitzen P10–P90 dins l’àmbit, mantenint la metodologia
estructural ja validada a Alinyà. La meteorologia utilitza P5–P95 dels darrers
35 dies XEMA. L’NDMI i la humitat relativa s’inverteixen perquè els valors
baixos representin més sequedat.

Pesos:

- perill estructural oficial: 24 %;
- temperatura superficial: 16 %;
- sequedat relativa NDMI: 16 %;
- potencial de combustible per coberta: 16 %;
- concurrència territorial: 8 %;
- vent XEMA: 10 %;
- humitat relativa XEMA invertida: 10 %.

La suma dels cinc components territorials és el 80 % i conserva la proporció
interna de l’índex estructural integrat d’Alinyà. La meteorologia representa el
20 % restant, com a la lectura urbana de referència. Si una variable no està
disponible, el seu pes no es converteix en zero: es renormalitzen els pesos
realment disponibles i la cel·la queda marcada com a incompleta.

## Exemple d’execució

```bash
python -m ecoradar.connectors.connector_meteocat_xema --location alinya
python tools/calculate_alinya_current_fire_danger.py
python tools/export_ecoradar_alinya_netlify.py
```

## Limitacions

- L’estació Y4 és una observació puntual; no descriu el vent ni la humitat de
  cada vessant d’un àmbit de 5.464 ha i fort gradient altitudinal.
- L’absència d’una variable XEMA en una comprovació no demostra absència del
  fenomen meteorològic.
- La temperatura Landsat és una composició estival de superfície, no
  temperatura de l’aire ni una observació simultània amb XEMA.
- L’NDMI és un proxy espectral relatiu, no humitat fina del combustible.
- La coberta és un proxy explícit de combustible i requereix validació de
  càrrega, estructura vertical i continuïtat real al camp.
- La quadrícula oficial diària té una resolució massa grossa per interpretar
  diferències internes de la Muntanya d’Alinyà. Es conserva com a context
  oficial, però no s’interpola ni es representa com una superfície detallada.
- Cal consultar sempre Pla Alfa, avisos oficials i instruccions d’emergència.
