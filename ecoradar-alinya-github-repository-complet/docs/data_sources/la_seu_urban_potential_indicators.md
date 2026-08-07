# Indicadors EcoRadar de potencial de frescor i utilitat climàtica

Data metodològica: 2026-07-25

## Potencial de frescor dels carrers

La unitat de càlcul és un tram viari OSM d'un màxim de 75 metres. Cada tram
rep una puntuació de 0 a 100 amb aquests components i pesos:

| Component | Pes |
|---|---:|
| Ombra LiDAR a les 15.00 h locals | 25 % |
| Coberta arbòria LiDAR | 18 % |
| Temperatura superficial detallada més recent i QA-vàlida | 20 % |
| Baixa impermeabilització Copernicus HRL | 12 % |
| Oportunitat geomètrica d'ombra segons orientació i azimut solar | 8 % |
| Amplada del carrer | 7 % |
| Proximitat a zones verdes OSM | 10 % |

La classe és **alta** a partir de 67, **mitjana** entre 34 i 66,9 i **baixa**
per sota de 34. L'amplada utilitza `width` d'OSM quan existeix; si falta,
s'aplica un proxy documentat per classe `highway`. La puntuació es normalitza
només amb els components disponibles i la confiança baixa quan l'amplada és un
proxy.

És un indicador derivat EcoRadar de priorització territorial. **No és una
temperatura mesurada al carrer**, no descriu confort individual i no substitueix
una campanya microclimàtica.

## Utilitat climàtica potencial dels equipaments

S'avaluen equipaments d'interès públic i parcs o jardins OSM com a candidats,
amb aquests pesos:

| Component | Pes |
|---|---:|
| Ombra a l'entorn de 30 m | 20 % |
| Temperatura superficial de l'entorn | 20 % |
| Accessibilitat a xarxa caminable i pendent | 15 % |
| Horaris publicats a OSM | 10 % |
| Proximitat a aigua potable o font cartografiada | 10 % |
| Proximitat a població vulnerable | 10 % |
| Connexió amb trams de frescor alta o mitjana | 15 % |

No hi ha una capa pública verificada de població vulnerable amb detall espacial
suficient. Aquest component queda nul, s'exclou de la normalització i redueix la
confiança. Els horaris també queden nuls quan OSM no els publica.

Cap candidat s'etiqueta com a refugi climàtic oficial. La validació municipal
ha de comprovar titularitat, accés real, horari, capacitat, condicions interiors,
aigua, accessibilitat universal i protocol d'activació abans de fer aquesta
declaració.

## Fonts i llicències

- ICGC LiDAR Territorial v3.1, sota les condicions de reutilització de l'ICGC.
- Landsat Collection 2 Level-2 o ECOSTRESS L2T LST V3, segons la font detallada
  QA-vàlida més recent seleccionada i la seva llicència pròpia.
- Copernicus HRL Imperviousness 2021, política de dades Copernicus.
- OpenStreetMap, ODbL 1.0.

Les dates reals de cada entrada, els pesos, la completesa, la confiança i les
limitacions es desen a
`projectes/LaSeu_Urba/metadata/urban_potential_services.json`.
