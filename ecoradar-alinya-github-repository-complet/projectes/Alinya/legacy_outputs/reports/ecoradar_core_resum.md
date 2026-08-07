# EcoRadar Core · Resum Alinya

Generat: 2026-07-07T15:08:52+00:00

## Resum General

EcoRadar Core ha generat 12 indicadors mestres separats. Aquesta execucio usa nomes les dades ja implementades i no calcula una mitjana global.
Indicadors amb valor numeric: 8. Indicadors no disponibles: 4.

## Taula Dels 12 Indicadors

| Codi | Indicador | Estat | Valor 0-100 | Categoria | Confiança |
| --- | --- | --- | ---: | --- | --- |
| CORE_01 | Mosaic del paisatge | parcial | 60.01 | alt | mitjana |
| CORE_02 | Valor d'habitats | parcial | 98.91 | molt alt | mitjana |
| CORE_03 | Estat de la vegetacio | no disponible | no disponible | no disponible | baixa |
| CORE_04 | Refugis climatics | parcial | 88.42 | molt alt | baixa |
| CORE_05 | Vulnerabilitat climatica | parcial | 22.99 | baix | baixa |
| CORE_06 | Biodiversitat coneguda | parcial | 99.66 | molt alt | mitjana |
| CORE_07 | Pressio humana i us public | parcial | 39.32 | baix | baixa |
| CORE_08 | Connectivitat ecologica | parcial | 60.05 | alt | baixa |
| CORE_09 | Resiliencia al foc | parcial | 32.65 | baix | baixa |
| CORE_10 | Aigua i funcionalitat hidrica | no disponible | no disponible | no disponible | baixa |
| CORE_11 | Potencial de restauracio | no disponible | no disponible | no disponible | baixa |
| CORE_12 | Prioritat de gestio | no disponible | no disponible | no disponible | baixa |

## Indicadors Amb Millor Resultat

- `CORE_06` Biodiversitat coneguda: 99.66 (molt alt). Biodiversitat coneguda basada en cites publiques; grups infrarepresentats o febles: Reptilia, Amphibia, Sense grup, Animalia, Mollusca, Protozoa.
- `CORE_02` Valor d'habitats: 98.91 (molt alt). Valor calculat amb riquesa d'habitats, HIC i HIC prioritaris. Habitats principals: 42.561; 32.641+; 42.425.
- `CORE_04` Refugis climatics: 88.42 (molt alt). Només es pot usar la cobertura forestal com a senyal parcial; el mapa de refugis queda pendent.

## Indicadors Amb Pitjor Resultat

- `CORE_05` Vulnerabilitat climatica: 22.99 (baix).
- `CORE_09` Resiliencia al foc: 32.65 (baix).
- `CORE_07` Pressio humana i us public: 39.32 (baix).

## Dades No Disponibles

- `CORE_03` Estat de la vegetacio: falten NDVI, NDMI, NDWI, anomalia temporal.
- `CORE_10` Aigua i funcionalitat hidrica: falten cursos fluvials, basses, fonts, zones humides, NDWI, punts d'aigua de camp.
- `CORE_11` Potencial de restauracio: falten baixa qualitat de vegetacio, habitats degradats, baixa connectivitat, pressio gestionable, habitats font.
- `CORE_12` Prioritat de gestio: falten refugis climatics, vulnerabilitat, pressio humana, resiliencia al foc, potencial de restauracio.

## Limitacions

- `CORE_01`: No hi ha encara calcul espacial de continuitat forestal.
- `CORE_02`: Habitats sensibles encara no estan classificats en una llista EcoRadar validada.
- `CORE_03`: Copernicus esta bloquejat per manca de credencials i no hi ha rasters NDVI/NDMI/NDWI/LST.
- `CORE_04`: Falten LST, NDMI, orientacio i proximitat a aigua; no es poden delimitar refugis.
- `CORE_05`: Falten LST, NDMI, orientacio, pendent i manca d'aigua; el valor es un proxy incomplet.
- `CORE_06`: No hi ha encara llistes d'especies indicadores, protegides o invasores creuades.
- `CORE_07`: OSM descriu infraestructura cartografiada, no intensitat real de visitants.
- `CORE_07`: Strava, comptadors, dades de gestors i observacions de camp encara no estan incorporats.
- `CORE_08`: Falten barreres, riberes i model espacial de corredors.
- `CORE_09`: Falten pendent, orientacio, NDMI, LST, accessos i punts d'aigua.
- `CORE_10`: No hi ha connector hidrologic executat i NDWI no esta disponible.
- `CORE_11`: Depen d'indicadors encara no disponibles: vegetacio, vulnerabilitat climatica, connectivitat robusta i pressio humana.
- `CORE_12`: Indicador final de sintesi bloquejat fins tenir els Core previs amb prou confiança.

## Primeres Zones Prioritaries

No es generen zones prioritaries espacials en aquesta execucio. Falten pressio humana, teledeteccio, hidrologia/topografia derivada i validacio de camp.

## Recomanacions Preliminars

- `CORE_01`: Validar discontinuïtats reals i conservar espais oberts existents.
- `CORE_02`: Revisar els habitats HIC i prioritaris abans de qualsevol actuacio.
- `CORE_04`: No prioritzar refugis climatics sense teledeteccio, topografia i hidrologia.
- `CORE_05`: Esperar teledeteccio, DEM i hidrologia abans de prioritzar restauracio climatica.
- `CORE_06`: Validar grups infrarepresentats amb treball de camp i llistes de referencia.
- `CORE_07`: Validar sobre el terreny els accessos, aparcaments i camins principals abans d'interpretar pressio real.
- `CORE_08`: No definir corredors fins incorporar barreres i xarxa hidrica.
- `CORE_09`: Analitzar mosaic i discontinuïtats abans de proposar actuacions forestals.
- `CORE_03`: Configurar credencials Copernicus i generar rasters abans de valorar aquest indicador.
- `CORE_10`: Implementar connector hidrologic oficial i executar NDWI quan Copernicus estigui disponible.
- `CORE_11`: Esperar les capes de vegetacio, pressio humana, hidrologia i camp abans de proposar zones.
- `CORE_12`: No generar top 10 zones prioritaries fins disposar de pressio humana, clima, foc, aigua i camp.
