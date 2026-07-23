# Primera diagnosi EcoRadar · Alinyà

Data: 2026-07-06

Tipus de document: diagnosi tècnica preliminar amb dades disponibles.

Aquest document sintetitza el primer funcionament real d'EcoRadar sobre l'àrea d'estudi d'Alinyà. No és un informe final ni una valoració ecològica completa. Els resultats es basen només en les capes que ja han estat preparades pel motor: àrea d'estudi, cobertes del sòl, hàbitats, biodiversitat pública i EcoRadar Core.

## 1. Estat de la base de dades

L'àrea d'estudi s'ha carregat i normalitzat correctament:

| Variable | Valor |
| --- | ---: |
| Superfície | 5.464,03 ha |
| Perímetre | 93.285,61 m |
| CRS final | EPSG:25831 |
| Errors geomètrics detectats | cap |

La prova confirma que EcoRadar pot treballar amb un espai real, generar una carpeta de projecte, conservar metadades i creuar les primeres fonts processades.

## 2. Connectors disponibles

| Connector | Estat | Sortida utilitzada |
| --- | --- | --- |
| Àrea d'estudi | correcte | `processed/study_area.gpkg` |
| Cobertes del sòl | correcte | `processed/cobertes_sol.gpkg` |
| Hàbitats | correcte | `processed/habitats.gpkg` |
| Biodiversitat | correcte | `processed/biodiversitat.gpkg` |
| Teledetecció Copernicus | bloquejat | falten credencials OAuth |
| Pressió humana | parcial OSM | `processed/recreational_pressure.gpkg` |
| Aigua i hidrologia | no disponible | connector no executat |
| Incendis i estructura del combustible | no disponible | connector no executat |

## 3. Lectura tècnica inicial

Alinyà mostra una base territorial clarament natural i forestal. La coberta forestal representa el 88,42% de l'àrea, mentre que prats, pastures i herbassars representen el 9,33%. Les cobertes agrícoles i artificials apareixen amb valors molt baixos en les dades actuals. El connector OSM ha identificat 124,83 km de camins, pistes i vials menors cartografiats, amb una densitat de 2,28 km/km² i 18 punts d'ús públic o recreatiu.

Aquesta estructura apunta a un espai amb molta continuïtat de cobertes naturals. Això pot ser positiu per a hàbitats i connectivitat, però també obliga a estudiar amb més detall el mosaic, les discontinuïtats, els espais oberts i la resiliència davant grans incendis. Amb les dades actuals encara no es pot afirmar on hi ha continuïtat crítica, perquè falta el càlcul espacial de continuïtat forestal, pendent, orientació, punts d'aigua i humitat de vegetació. La informació OSM ajuda a localitzar infraestructura d'accés, però no mesura intensitat real de visitants.

## 4. Cobertes del sòl

| Indicador | Valor |
| --- | ---: |
| Coberta forestal | 88,42% |
| Prats, pastures i herbassars | 9,33% |
| Agrícola | 0,0047% |
| Urbà o artificial | 0,0801% |
| Tipus de cobertes detectades | 13 |

La primera lectura indica un paisatge molt dominat per cobertes forestals, amb una presència rellevant però minoritària d'espais oberts. EcoRadar marca el mosaic del paisatge com a parcial perquè encara no calcula la continuïtat forestal espacial ni el patró real de discontinuïtats.

Diagnosi preliminar:

- Cal conservar la informació sobre espais oberts, prats i pastures perquè poden tenir un paper important en biodiversitat, mosaic i gestió del combustible.
- No es pot valorar encara si el mosaic és funcional sense cartografia espacial més detallada de continuïtats i vores.

## 5. Hàbitats

| Indicador | Valor |
| --- | ---: |
| Nombre d'hàbitats detectats | 47 |
| Superfície HIC | 3.170,95 ha |
| Superfície HIC prioritària | 1.229,39 ha |

El valor d'hàbitats és el senyal més fort de la diagnosi inicial. La combinació de nombre d'hàbitats, superfície d'hàbitats d'interès comunitari i presència d'HIC prioritaris dona un resultat alt dins del Core.

Diagnosi preliminar:

- Alinyà té una estructura d'hàbitats amb valor de conservació elevat segons les dades disponibles.
- Abans de proposar actuacions cal espacialitzar millor les zones de més valor i incorporar una llista validada d'hàbitats sensibles.
- Qualsevol actuació forestal o de restauració hauria de creuar-se amb HIC i HIC prioritaris.

## 6. Biodiversitat coneguda

| Indicador | Valor |
| --- | ---: |
| Registres públics normalitzats | 731 |
| Espècies registrades | 516 |
| Registres recents | 726 |

Les dades públiques de biodiversitat donen una primera base útil, però no equivalen a un inventari complet. Són registres oportunistes i poden estar condicionats per esforç d'observació, accessibilitat, grups més populars i qualitat de coordenades.

Diagnosi preliminar:

- La biodiversitat coneguda és alta en termes de registres i espècies citades.
- Cal validar grups infrarepresentats i espècies sensibles amb treball de camp.
- No s'ha de deduir absència d'espècies a partir de buits de registres.
- No s'ha de considerar presència actual una cita antiga sense suport recent o validació.

## 7. Pressió humana i ús públic

| Indicador | Valor |
| --- | ---: |
| Elements lineals OSM | 200 |
| Longitud de camins, pistes i vials menors | 124,83 km |
| Densitat de camins i pistes | 2,28 km/km² |
| Punts d'ús públic o recreatiu | 18 |

Aquest bloc ja no està buit, però continua sent parcial. OpenStreetMap permet identificar infraestructura cartografiada: camins, pistes, vials menors, aparcaments, miradors, refugis, punts d'informació o altres elements d'ús públic quan estan mapejats.

Diagnosi preliminar:

- La xarxa OSM proporciona una primera base per estudiar accessibilitat i possibles corredors d'ús públic.
- Aquesta dada no equival a intensitat real de visitants.
- Caldrà validar sobre el terreny els punts d'accés, aparcaments i camins principals.
- Strava, comptadors, dades de gestors i observacions de camp continuen pendents.

## 8. EcoRadar Core

| Codi | Indicador | Estat | Valor 0-100 | Categoria | Confiança |
| --- | --- | --- | ---: | --- | --- |
| CORE_01 | Mosaic del paisatge | parcial | 60,01 | alt | mitjana |
| CORE_02 | Valor d'hàbitats | parcial | 98,91 | molt alt | mitjana |
| CORE_03 | Estat de la vegetació | no disponible | no disponible | no disponible | baixa |
| CORE_04 | Refugis climàtics | parcial | 88,42 | molt alt | baixa |
| CORE_05 | Vulnerabilitat climàtica | parcial | 22,99 | baix | baixa |
| CORE_06 | Biodiversitat coneguda | parcial | 99,66 | molt alt | mitjana |
| CORE_07 | Pressió humana i ús públic | parcial | 39,32 | baix | baixa |
| CORE_08 | Connectivitat ecològica | parcial | 60,05 | alt | baixa |
| CORE_09 | Resiliència al foc | parcial | 32,65 | baix | baixa |
| CORE_10 | Aigua i funcionalitat hídrica | no disponible | no disponible | no disponible | baixa |
| CORE_11 | Potencial de restauració | no disponible | no disponible | no disponible | baixa |
| CORE_12 | Prioritat de gestió | no disponible | no disponible | no disponible | baixa |

EcoRadar Core funciona com a estructura de síntesi, però la diagnosi encara és parcial. Els indicadors més robustos ara mateix són hàbitats, biodiversitat coneguda i cobertes. La pressió humana ja disposa d'una primera base OSM, però continua amb confiança baixa perquè no incorpora intensitat real d'ús. Els indicadors climàtics, hídrics, restauració i prioritat final encara depenen de connectors pendents.

## 9. Dades que falten

Les principals mancances són:

- NDVI, NDMI, NDWI i LST per valorar estat de vegetació, estrès i refugis climàtics.
- DEM, pendent i orientació per vulnerabilitat climàtica i foc.
- Intensitat real d'ús públic, comptadors, dades de gestors, Strava autoritzat o observacions de camp.
- Cursos fluvials, fonts, basses, zones humides i punts d'aigua.
- Històric d'incendis, discontinuïtats, accessos i punts d'aigua per resiliència al foc.
- Dades de camp per validar hàbitats sensibles, espècies, pressions i prioritats.

## 10. Primera priorització tècnica

Encara no es pot generar un top 10 de zones prioritàries. Amb les dades actuals només es poden proposar línies de treball:

1. Revisar zones amb HIC i HIC prioritaris abans de qualsevol proposta de gestió.
2. Identificar i validar al camp els espais oberts, prats i pastures, perquè poden ser clau per mosaic, biodiversitat i foc.
3. Completar teledetecció per detectar vigor vegetal, humitat i possibles zones d'estrès.
4. Validar la xarxa OSM de camins, accessos i punts d'ús públic i complementar-la amb observació de camp.
5. Incorporar hidrologia i punts d'aigua per valorar refugis, funcionalitat hídrica i resiliència.
6. Fer una campanya de camp dirigida als buits d'informació i als grups infrarepresentats.

## 11. Conclusió tècnica

La prova amb Alinyà valida l'estructura bàsica d'EcoRadar. El motor ja pot preparar una àrea real, integrar cobertes, hàbitats, biodiversitat i infraestructura OSM d'ús públic, generar indicadors Core i documentar les mancances.

La primera diagnosi indica un espai amb alt valor d'hàbitats, molta coberta forestal, una base important de biodiversitat coneguda i una xarxa d'accés cartografiada que ja es pot començar a analitzar amb prudència. Però encara no és prudent fer recomanacions espacials finals de gestió, restauració, aigua o incendis. Per passar de diagnosi preliminar a diagnosi operativa cal completar teledetecció, hidrologia, topografia derivada, foc i validació de camp.
