# Similitud ambiental amb incendis historics - Alinya

Status: `environmental_similarity_not_fire_probability`

Aquest producte compara la Muntanya d'Alinya amb les condicions observades als dos perimetres oficials d'incendi disponibles dins l'ambit. No es un model de probabilitat ni una prediccio operativa.

## Sortides

- `mapa_similitud_condicions_incendi_alinya.svg`: mapa visual.
- `similitud_condicions_incendi_alinya.geojson`: grid de similitud.
- `../../processed/incendis_similarity/similitud_condicions_incendi_alinya.gpkg`: capa processada.
- `../../processed/incendis_similarity/incendis_historics_amb_condicions.gpkg`: incendis amb atributs de mostra.
- `../../metadata/incendis_similarity/similitud_condicions_incendi_alinya_metadata.json`: metode, fonts i limitacions.

## Fonts incorporades

- Perimetres oficials d'incendi WFS Generalitat.
- Cobertes del sol processades.
- Habitats terrestres v3 processats.
- DEM ICGC 5 m per altitud, pendent i orientacio.
- Accessos OSM processats.
- Dataset oficial de Bombers `g2ay-3vnj` nomes per documentar Llinars; no aporta geometria.

## Llinars

El dataset oficial de Bombers confirma registres d'incendi de vegetacio a Llinars del Valles el 2026, incloent `2026-06-24` com a incendi de vegetacio urbana. No s'incorpora al mapa d'Alinya perque no te coordenades/perimetre i queda fora de l'ambit.

## Limitacio

No s'han incorporat fonts bloquejades, pendents o amb credencials: IncendisCAT, Pla Alfa, EFFIS, Meteocat/AEMET, Sentinel NDMI/NDVI i hidrologia/punts d'aigua.
