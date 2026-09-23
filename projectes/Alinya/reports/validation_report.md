# Informe de validació EcoRadar

Projecte: `Alinya`
Generat: `2026-09-23T18:37:57+00:00`
Estat per generar fitxa/informe final: `APTE`

## Resum

| Nivell | Estat | Checks | Errors crítics | Errors majors | Avisos |
|---|---|---:|---:|---:|---:|
| Validació tècnica | VALIDATED | 8 | 0 | 0 | 0 |
| Validació ecològica | VALIDATED_WITH_LIMITATIONS | 8 | 0 | 0 | 1 |
| Validació de recomanacions | VALIDATED | 5 | 0 | 0 | 0 |

## Condicions de publicació

- No hi ha errors tècnics crítics.
- Les limitacions estan indicades als indicadors i conclusions.
- Les recomanacions tenen indicador, font/localització o dependència quan la dada és parcial.
- Les dades pendents apareixen com a limitació o recomanació de validació.
- La diagnosi no tanca vegetació, clima, foc, aigua o restauració quan les dades són parcials.

## Checks tècnics i ecològics

### technical
- `PASS` `critical` TECH_01 - CRS de l'àrea d'estudi: CRS detectat: capa=EPSG:25831, metadades=EPSG:25831.
- `PASS` `critical` TECH_02 - Geometria de l'àrea d'estudi: Geometries invàlides: 0.
- `PASS` `critical` TECH_03 - Superfície coherent amb metadades: Diferència àrea geometria/metadades: 0,000%.
- `PASS` `major` TECH_04 - Capes processades retallades dins l'àrea d'estudi: Capes revisades: 7; fora de tolerància: 0.
- `PASS` `critical` TECH_05 - Valors sense buits crítics: Indicadors complets amb valor/font absent: 0.
- `PASS` `critical` TECH_06 - Fonts documentades: Fonts al catàleg: 30; fonts incompletes: 0.
- `PASS` `critical` TECH_07 - Indicadors vinculats a fonts reals: Fonts utilitzades no registrades: 0.
- `PASS` `critical` TECH_08 - Cap valor inventat: Valors numèrics sense fonts: 0.

### ecological
- `PASS` `critical` ECO_V2_01 - Cap CORE força una escala comuna 0–100: Els dotze CORE han de ser lectures, perfils o decisions amb l'escala pròpia.
- `PASS` `critical` ECO_V2_02 - Vector de confiança complet i independent: Cada RADAR ha d'explicar les vuit dimensions de confiança.
- `PASS` `critical` ECO_V2_03 - HIC no es presenta com a estat de conservació: CORE_02 només pot informar responsabilitat territorial amb les dades actuals.
- `PASS` `critical` ECO_V2_04 - Vegetació directa, datada i sense puntuació: CORE_03 ha de conservar NDVI en l'escala i data pròpies.
- `PASS` `critical` ECO_V2_05 - Vulnerabilitat i restauració no sobreinterpretades: Sense receptor, degradació i referència no es pot fabricar vulnerabilitat o potencial de restauració.
- `PASS` `critical` ECO_V2_06 - CORE_12 és no compensatori: CORE_12 ha de comparar sector i alternativa amb vetos, sense mitjana global.
- `PASS` `major` ECO_V2_07 - La diagnosi respecta vigència i significat: La diagnosi ha d'identificar dades antigues i evitar causalitat o estat actual no suportats.
- `WARN` `minor` ECO_V2_08 - Perfils pendents de dades de camp i decisions metodològiques: La validació permet publicar els resultats perquè els buits generen NO AVALUABLE o PARCIAL i no valors inventats.

### recommendations
- `PASS` `critical` REC_01 - Recomanacions amb camps obligatoris: Recomanacions amb camps obligatoris absents: 0.
- `PASS` `critical` REC_02 - Recomanacions derivades d'indicadors reals: Recomanacions sense indicador/conclusió traçable: 0.
- `PASS` `major` REC_03 - Fonts citades quan són actuacions substantives: Recomanacions sense fonts fora de Dades pendents: 0.
- `PASS` `major` REC_04 - Localització indicada: Recomanacions sense localització útil: 0.
- `PASS` `critical` REC_05 - No hi ha actuacions finals sense advertir parcialitat: Recomanacions finals basades en indicadors parcials sense dependències: 0.

## Checklist de camp

| ID | Bloc | On mirar | Què comprovar | Prioritat | Motiu |
|---|---|---|---|---|---|
| FIELD_01 | Hàbitats sensibles | HIC, ecotons i unitats d'hàbitat amb valor alt | Verificar estat real, pressions locals i límits de polígon. | Alta | No hi ha validació de camp d'hàbitats. |
| FIELD_02 | HIC i HIC prioritaris | Polígons HIC i HIC prioritaris abans d'actuacions | Confirmar correspondència cartografia-realitat i sensibilitat. | Alta | Recomanació CONS-001 depèn de precisió local. |
| FIELD_03 | Prats, ecotons i discontinuïtats | Espais oberts, marges, prats i conreus residuals | Determinar funció ecològica, gestió agrària i paper en mosaic/foc. | Alta | SIGPAC/DUN i combustible no disponibles. |
| FIELD_04 | Fonts, basses i punts d'aigua | Cursos ACA, fonts oficials i possibles basses no cartografiades | Verificar presència d'aigua, temporalitat, estat ecològic i ús per fauna. | Alta | NDWI i estat funcional de l'aigua no disponibles. |
| FIELD_05 | Camins i punts d'ús públic | Accessos, pistes, aparcaments, miradors i punts recreatius | Separar accessibilitat cartogràfica de freqüentació real. | Mitjana | OSM no mesura intensitat real de visitants. |
| FIELD_06 | Microhàbitats | Roca, fusta morta, arbres vells, cavitats, surgències i marges | Inventariar elements no visibles a la cartografia oficial. | Mitjana | No existeix capa de microhàbitats. |
| FIELD_07 | Espècies indicadores | Grups i taxons citats per GBIF/iNaturalist amb interès de gestió | Confirmar presència actual, hàbitat i qualitat de la citació. | Alta | Fonts públiques oportunistes no equivalen a inventari complet. |
| FIELD_08 | Pressions reals | Ús públic, ramaderia, agricultura, infraestructures i erosió local | Registrar intensitat, temporalitat, conflictes i punts crítics. | Mitjana | Falten dades de gestors/comptadors i validació directa. |
| FIELD_09 | Zones amb baixa confiança | Vegetació, clima, foc, aigua funcional i restauració | Prioritzar mostreig on falten Copernicus, clima, combustible o validació. | Alta | Indicadors parcials o no disponibles condicionen decisions finals. |
