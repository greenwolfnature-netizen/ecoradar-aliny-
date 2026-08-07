# Mapa d'incendis i condicions territorials - Alinya

Status: `context_map_not_probability_model`

Aquest mapa respon parcialment a la demanda de mapa d'incendis per a la Muntanya d'Alinya sense trencar el gate d'EcoRadar. Mostra històric oficial d'incendis i condicions territorials locals, però no calcula probabilitat d'incendi.

## Sortides

- `mapa_incendis_context_alinya.svg`: mapa visual autoportant.
- `incendis_historics_alinya_clip.geojson`: incendis oficials retallats a l'ambit.
- `../../processed/incendis/incendis_historics_alinya_clip.gpkg`: capa processada d'incendis.
- `../../processed/incendis/condicions_cobertes_alinya.gpkg`: cobertes agrupades per lectura territorial.
- `../../metadata/incendis/mapa_incendis_context_alinya_metadata.json`: metadades i fonts.

## Limitacio

No es calcula recurrencia, probabilitat, risc, orientacio, pendent, combustible continu ni prioritat de gestio. Aquests productes pertanyen a l'Analysis Engine i requereixen un metode validat i totes les fonts obertes.

IncendisCAT s'ha consultat el 2026-07-07 com a context operatiu no oficial, pero no s'ha incorporat com a font EcoRadar perque el projecte prohibeix usar IncendisCAT com a font de dades i la seva font oficial exacta continua bloquejada.

No s'han incorporat fonts amb `pending_verification`, `requires_credentials` o `blocked` com Pla Alfa, EFFIS, Meteocat/AEMET o l'upstream d'IncendisCAT.

## Resum numeric

- Ambit: 5464.0 ha.
- Geometries oficials d'incendi que intersecten l'ambit: 2.
- Superficie acumulada de perimetres oficials dins l'ambit: 17.45 ha (0.319% de l'ambit, suma no deduplicada si hi ha solapaments).
