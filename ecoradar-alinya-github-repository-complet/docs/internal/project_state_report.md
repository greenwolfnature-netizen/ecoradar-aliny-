# EcoRadar · Informe Intern D'Estat Del Projecte

Data: 2026-07-07

Aquest document consolida l'estat actual d'EcoRadar com a projecte únic. No implementa cap connector nou, no descarrega dades i no afegeix indicadors. Serveix com a punt de control abans de reorganitzar el codi existent en una plataforma coherent de diagnosi ecològica.

## 1. Principi Rector

EcoRadar s'ha de tractar com una única plataforma:

1. Àrea d'estudi.
2. Obtenció automàtica de dades verificades.
3. Normalització.
4. Anàlisi.
5. Indicadors.
6. Diagnosi.
7. Recomanacions.
8. Informe tècnic.
9. Fitxa executiva.
10. Mapes.

La reorganització ha de respectar `AGENTS.md`:

- No crear connectors nous fins que les fonts oficials estiguin identificades, verificades i documentades.
- Els connectors només han de connectar, descarregar, normalitzar i retornar `GeoDataFrame` o `DataFrame`.
- L'anàlisi, els indicadors, la diagnosi i les recomanacions no han de viure dins dels connectors.
- IncendisCat no és font de dades. Per incendis cal identificar i documentar la font oficial exacta abans d'implementar cap connector nou.

## 2. Estat General

EcoRadar ja disposa d'una base funcional real, però encara no està organitzada com una plataforma única.

### Funciona

- Càrrega, validació i preparació d'àrea d'estudi amb `GeoPackage`, `SHP`, `GeoJSON` i CRS mètric `EPSG:25831`.
- Preparació real del projecte `Alinya` amb `study_area.gpkg` i metadades.
- Connectors funcionals externs per a:
  - cobertes del sòl ICGC,
  - hàbitats terrestres Generalitat,
  - biodiversitat GBIF/iNaturalist,
  - pressió humana OSM/Overpass.
- Connector Copernicus preparat però bloquejat per credencials OAuth.
- EcoRadar Core amb 12 indicadors mestres separats.
- Mapes bàsics derivats en `projectes/Alinya/maps/ecoradar_core/`.
- Producte PDF A3 v3 amb narrativa professional i capa d'interpretació ecològica.
- Pipeline d'execució per Alinyà a `tools/run_ecoradar_diagnosis.py`.
- Tests bàsics de nucli, estudi d'àrea, connectors i biblioteca d'indicadors.

### Parcial

- El motor d'orquestració existeix, però està acoblat a `projectes/Alinya`.
- Els connectors reals són scripts a `/connectors`, no classes registrades dins `ecoradar/connectors`.
- Alguns connectors escriuen resums d'indicadors, cosa que barreja Data Engine i Analysis Engine.
- Les sortides editorials són potents, però hi ha diverses generacions històriques (`export_diagnosi_pdf`, `export_ecoradar_product`, `atlas_a3`, `atlas_v2`, `atlas_v3`) amb solapaments.
- La documentació central encara descriu alguns components com a "no implementats" tot i que ja existeixen prototips funcionals.
- La base de dades normalitzada està dissenyada en SQL però no s'ha consolidat com a GeoPackage únic de projecte.

### No disponible o bloquejat

- NDVI, NDMI, NDWI i LST: Copernicus requereix credencials i LST encara necessita col·lecció operativa verificada.
- Hidrologia fina: cursos d'aigua, fonts, basses, zones humides i funcionalitat hídrica no tenen connector executat.
- DEM, pendent, orientació, insolació i humitat potencial no estan integrats.
- Incendis: hi ha documentació de fonts i criteri, però no hi ha connector implementat per perímetres, recurrència, severitat o estructura del combustible.
- Connectivitat ecològica i fragmentació: només aproximacions parcials amb cobertes/hàbitats; falten barreres, riberes i corredors.
- Espècies protegides, indicadores i invasores: els registres de biodiversitat encara no es creuen amb llistes de referència.
- Ramaderia, microhàbitats i treball de camp: previstos, però sense mòdul d'importació funcional.
- Strava Heatmap: bloquejat fins confirmar condicions d'ús i via compatible; no s'ha d'automatitzar scraping.

## 3. Estructura Actual Del Repositori

### Paquet `ecoradar/`

És el nucli que s'ha de conservar com a base de plataforma.

- `ecoradar/core/study_area.py`: càrrega, validació, reparació opcional, reprojecció, superfície i perímetre.
- `ecoradar/core/project.py`: creació d'estructura base de projecte i manifest.
- `ecoradar/connectors/base.py`: contracte `BaseConnector` i `ConnectorResult`.
- `ecoradar/connectors/registry.py`: registre mínim de connectors.
- `ecoradar/connectors/cobertes_sol.py`: connector buit de prova.
- `ecoradar/analysis/core.py`: càlcul dels 12 indicadors EcoRadar Core a partir de sortides ja preparades.
- `ecoradar/indicators/library.py`: catàleg metodològic ampli d'indicadors.
- `ecoradar/cli.py`: CLI base per crear projecte, inspeccionar àrea i preparar àrea d'estudi.

### Carpeta `/connectors`

Conté els connectors reals actuals. Són valuosos i s'han de reutilitzar, però cal integrar-los dins el paquet.

- `connector_icgc_cobertes_sol.py`: descarrega WCS/WMS ICGC, retalla, polygonitza i resumeix cobertes.
- `connector_habitats.py`: consulta WFS Hipermapa, retalla i resumeix hàbitats terrestres/HIC.
- `connector_biodiversitat.py`: consulta GBIF i iNaturalist, normalitza registres i classifica recents/històrics/dubtosos.
- `connector_recreational_pressure_osm.py`: consulta Overpass i normalitza camins, pistes i punts d'ús públic.
- `connector_copernicus_teledeteccio.py`: preparat per NDVI/NDMI/NDWI amb credencials; LST pendent de mapping verificat.

Problema comú: tots tenen `PROJECT_ROOT = Path("projectes/Alinya")`. Això impedeix aplicar-los directament a qualsevol espai natural.

### Carpeta `/tools`

Conté orquestració i producte editorial.

- `run_ecoradar_diagnosis.py`: pipeline real per regenerar dades/productes d'Alinyà.
- `export_ecoradar_product.py`: informe executiu, mòduls i mapes en format producte.
- `export_ecoradar_atlas_a3.py`, `export_ecoradar_atlas_v2.py`, `export_ecoradar_atlas_v3.py`: atles A3, sent `v3` el producte principal.
- Altres exportadors històrics: útils com a referència, però no haurien de ser el camí principal.

### Documentació

- `docs/data_sources/`: inventari i verificació de fonts oficials.
- `docs/central_engine/`: disseny del motor central, esquema de base de dades i perfils d'indicadors.
- `docs/connectors/`: contracte de connectors i especificacions de pressió recreativa/incendis.
- `docs/product/`: estàndard editorial i metodològic del producte EcoRadar.
- `docs/modules/`: especificacions específiques per mòduls, especialment foc.

## 4. Duplicacions I Solapaments

### Connectors

Duplicació principal:

- Contracte i registre a `ecoradar/connectors/`.
- Implementacions reals a `/connectors`.

Decisió recomanada:

- Mantenir el contracte de `ecoradar/connectors/base.py`.
- Migrar progressivament els connectors reals cap a `ecoradar/connectors/` com a classes compatibles amb `BaseConnector`.
- Deixar els scripts de `/connectors` com a wrappers temporals o eliminar-los quan hi hagi equivalència funcional provada.

### Projectes

Hi ha dues estructures:

- `ecoradar_projectes/_TEMPLATE`: plantilla teòrica.
- `projectes/Alinya`: estructura real utilitzada pels connectors i productes.

Decisió recomanada:

- Adoptar `projectes/<nom_projecte>` com a estructura operativa actual, perquè ja conté les dades reals.
- Actualitzar la plantilla perquè coincideixi exactament amb el flux real.
- Mantenir compatibilitat amb `ecoradar_projectes` només si es decideix com a arrel alternativa configurable.

### Informes

Hi ha diverses sortides PDF acumulades.

Decisió recomanada:

- Declarar `atlas_diagnosi_ecoradar_alinya_v3_a3.pdf` com a producte principal actual.
- Declarar `export_ecoradar_atlas_v3.py` com a exporter editorial principal.
- Conservar els exportadors anteriors com a històric fins que el nou `Product Engine` els substitueixi.

### Indicadors

Hi ha dos nivells:

- `ecoradar/indicators/library.py`: biblioteca metodològica extensa.
- `ecoradar/analysis/core.py`: 12 indicadors mestres calculats.

No és una duplicació problemàtica. És una separació útil:

- La biblioteca defineix què pot existir.
- El Core calcula què es pot calcular amb dades disponibles.

Caldrà afegir un mapping formal entre biblioteca i Core.

## 5. Cobertura Dels Blocs EcoRadar

| Bloc | Estat actual | Comentari |
| --- | --- | --- |
| Cobertes del sòl | Funcional | Connector ICGC real, resum i capa processada. |
| Hàbitats | Funcional | Connector WFS real, HIC i prioritaris. |
| Usos del sòl | Parcial | Derivats de cobertes; falta SIGPAC/cultius si es vol detall agrari. |
| Vegetació | No disponible | Depèn de Copernicus NDVI/NDMI/NDWI. |
| Teledetecció | Bloquejada | Connector preparat, credencials requerides. |
| NDVI | Bloquejat | Sense raster real encara. |
| NDMI | Bloquejat | Sense raster real encara. |
| NDWI | Bloquejat | Sense raster real encara. |
| LST | Pendent | Requereix col·lecció operativa verificada. |
| Refugis climàtics | Parcial | Només proxy forestal; no delimitar refugis. |
| Vulnerabilitat climàtica | Parcial | Proxy incomplet; falta LST, NDMI, DEM i aigua. |
| Hidrologia | No disponible | Falta connector oficial ACA/ICGC seleccionat. |
| Cursos d'aigua | No disponible | Pendent. |
| Punts d'aigua | No disponible | Pendent i camp. |
| Zones humides | No disponible | Font oficial pendent d'integració. |
| Connectivitat ecològica | Parcial | Aproximació amb cobertes/hàbitats; fonts verificades pendents d'implementació. |
| Fragmentació | No disponible | Falta anàlisi espacial de continuïtat i barreres. |
| Corredors ecològics | No disponible | Falta model espacial i riberes/barreres. |
| Biodiversitat | Funcional parcial | GBIF/iNaturalist funcionen; falta creuar protecció/invasores/indicadores. |
| Fauna | Funcional parcial | Depèn dels grups disponibles a GBIF/iNaturalist. |
| Flora | Funcional parcial | Present si hi ha dades públiques; falta validació taxonòmica i legal. |
| Espècies protegides | No disponible | Falta llista oficial i creuament. |
| Espècies indicadores | No disponible | Falta catàleg EcoRadar validat. |
| Espècies invasores | No disponible | Falta llista oficial i creuament. |
| Boscos | Parcial | Percentatge forestal i lectura de mosaic; falta estructura forestal. |
| Prats | Parcial | Percentatge per cobertes; falta estat ecològic i gestió. |
| Matollars | Parcial | Present a cobertes/hàbitats; falta síntesi específica. |
| Agricultura | Parcial | Derivada de cobertes; falta SIGPAC/ramaderia. |
| Ramaderia | No disponible | Sense font ni camp integrat. |
| Pressió humana | Parcial funcional | OSM funciona; no mesura freqüentació real. |
| Ús públic | Parcial | Camins/punts OSM; falta intensitat, comptadors i gestors. |
| Camins | Funcional parcial | OSM/Overpass. |
| Pistes | Funcional parcial | OSM/Overpass. |
| Aparcaments | Funcional parcial | OSM si està cartografiat. |
| Infraestructures | Parcial | OSM bàsic; falta classificació de barreres. |
| Strava Heatmap | Bloquejat | Només si és compatible amb condicions d'ús. |
| Prevenció d'incendis | Parcial | Core proxy amb cobertes; no risc final. |
| Continuïtat forestal | No disponible | Falta anàlisi espacial de masses contínues. |
| Continuïtat del combustible | No disponible | Falta estructura/fuel models/NDMI/topografia. |
| Mosaic agroforestal | Parcial | Derivat de cobertes; falta mètrica espacial. |
| Punts crítics | No disponible | Requereix foc, pendent, accessos, aigua i interfície. |
| Microhàbitats | No disponible | Requereix treball de camp o fonts específiques. |
| Treball de camp | Dissenyat | Esquema previst; importador no implementat. |
| Validació | Parcial | Present com a recomanació, no com a mòdul de dades. |
| Canvi climàtic | Parcial | Sense Meteocat/AEMET/Copernicus complet. |
| Potencial de restauració | No disponible | Bloquejat fins vegetació, aigua, connectivitat i pressió. |
| Prioritat de conservació | Parcial | HIC/hàbitats; falta espacialització robusta. |
| Prioritat de restauració | No disponible | Falta motor de recomanacions espacial. |
| Prioritat de gestió | No disponible | EcoRadar evita top 10 sense dades suficients. |

## 6. Arquitectura Integrada Recomanada

La solució tècnica recomanada és reorganitzar sense duplicar:

```text
ecoradar/
  core/
    project.py
    study_area.py
    context.py              # nou: context de projecte i paths
    source_gate.py          # nou: lectura de sources_inventory.yml
  connectors/
    base.py
    registry.py
    land_cover_icgc.py      # migració de connector existent
    habitats_gencat.py      # migració de connector existent
    biodiversity_public.py  # migració de connector existent
    pressure_osm.py         # migració de connector existent
    copernicus.py           # migració source-gated
  analysis/
    core.py
    land_cover.py           # agregacions fora connector
    habitats.py
    biodiversity.py
    pressure.py
    connectivity.py         # futur, quan hi hagi dades
    climate.py              # futur
    fire.py                 # futur
    water.py                # futur
  diagnosis/
    engine.py               # interpreta relacions entre indicadors
    narratives.py           # criteris textuals i confiança
  recommendations/
    engine.py               # recomanacions justificades
  product/
    atlas.py                # producte A3 principal
    executive.py
    maps.py
  pipeline/
    run.py                  # orquestrador genèric
```

No cal crear tota aquesta estructura de cop. Cal fer-ho en fases, migració per migració, mantenint els outputs actuals.

## 7. Flux Operatiu Objectiu

El pipeline únic hauria de ser:

1. `ProjectContext` carrega `project_root`, manifest, CRS, carpetes i àrea d'estudi.
2. `SourceGate` llegeix `docs/data_sources/sources_inventory.yml`.
3. El registre executa només connectors:
   - implementats,
   - amb font `verified`,
   - compatibles amb credencials disponibles,
   - sense duplicar descàrregues.
4. Els connectors retornen dades normalitzades i metadades.
5. El `DataStore` escriu raw, processed i `source_downloads`.
6. L'`Analysis Engine` calcula resums i indicadors.
7. L'`EcoRadar Core` manté els 12 indicadors mestres.
8. El `Diagnosis Engine` interpreta relacions:
   - fortaleses,
   - debilitats,
   - pressions,
   - oportunitats,
   - riscos,
   - incerteses,
   - necessitats de camp.
9. El `Recommendation Engine` genera accions amb:
   - objectiu,
   - justificació,
   - localització,
   - benefici ecològic esperat,
   - indicadors justificatius.
10. El `Product Engine` genera:
   - informe tècnic,
   - informe executiu,
   - fitxa executiva,
   - atles A3,
   - mapes i annex tècnic.

## 8. Decisions Tècniques Recomanades Abans D'Implementar

### Decisió 1: Unificar arrel de projecte

Proposta: usar `projectes/<ProjectName>` com a arrel operativa, perquè ja conté Alinyà i totes les sortides reals.

Impacte: cal actualitzar `create_project_workspace` o afegir configuració perquè no hi hagi dues convencions competint.

### Decisió 2: Convertir connectors reals en classes

Proposta: migrar sense canviar comportament:

- `connector_icgc_cobertes_sol.py` -> `ecoradar/connectors/land_cover_icgc.py`
- `connector_habitats.py` -> `ecoradar/connectors/habitats_gencat.py`
- `connector_biodiversitat.py` -> `ecoradar/connectors/biodiversity_public.py`
- `connector_recreational_pressure_osm.py` -> `ecoradar/connectors/pressure_osm.py`
- `connector_copernicus_teledeteccio.py` -> `ecoradar/connectors/copernicus.py`

Cada classe hauria de rebre `ProjectContext`, no una constant `PROJECT_ROOT`.

### Decisió 3: Treure anàlisi dels connectors

Els connectors actuals creen CSV resum. Això és útil, però metodològicament hauria de moure's a `ecoradar/analysis/*`.

Transició recomanada:

- Fase 1: mantenir CSV per compatibilitat.
- Fase 2: fer que el connector retorni dades normalitzades.
- Fase 3: moure `_write_summary` a mòduls d'anàlisi i adaptar tests.

### Decisió 4: Declarar un Product Engine únic

Proposta:

- Producte principal: `export_ecoradar_atlas_v3.py`.
- Producte històric: resta d'exportadors.
- Objectiu final: moure producte a `ecoradar/product/` i deixar `tools/` només com a CLI/wrappers.

### Decisió 5: No completar blocs amb proxies febles

Els blocs obligatoris no s'han d'omplir artificialment. Cal representar-los així:

- `calculat`: dades suficients.
- `parcial`: una part ajuda a orientar, però no tanca decisió.
- `bloquejat`: font o credencial pendent.
- `pendent`: font verificada però connector/anàlisi encara no migrat.

## 9. Riscos Principals

1. Risc de falsa precisió: generar prioritats o top 10 sense hidrologia, foc, clima i camp.
2. Risc d'arquitectura doble: mantenir `/connectors` i `ecoradar/connectors` en paral·lel massa temps.
3. Risc de producte acoblat a Alinyà: exports i connectors no són genèrics encara.
4. Risc de barrejar fonts amb anàlisi: resums dins connectors.
5. Risc documental: alguns documents descriuen una fase anterior i poden contradir el codi actual.
6. Risc legal o d'ús: Strava/Wikiloc no s'han d'automatitzar sense condicions clares.
7. Risc d'incendis: no implementar connector fins complir la Fire Data Rule.

## 10. Pla De Reorganització Recomanat

### Fase 1: Consolidació Sense Canvi Funcional

Objectiu: fer que EcoRadar tingui una única arquitectura sense alterar resultats.

- Crear `ProjectContext` genèric.
- Crear `SourceGate` que llegeixi `sources_inventory.yml`.
- Afegir registre real de connectors implementats.
- Adaptar `run_ecoradar_diagnosis.py` perquè accepti qualsevol projecte preparat.
- Escriure tests per assegurar que Alinyà produeix els mateixos outputs.

### Fase 2: Migració De Connectors

Objectiu: integrar els connectors reals dins `ecoradar/connectors`.

- Migrar un connector cada vegada.
- Mantenir wrappers antics temporalment.
- Substituir constants `PROJECT_ROOT` per `ProjectContext`.
- Afegir fingerprint de descàrrega i política de no duplicació.
- Separar retorn normalitzat de resum analític.

### Fase 3: Analysis Engine Modular

Objectiu: moure agregacions i resums fora dels connectors.

- `analysis/land_cover.py`
- `analysis/habitats.py`
- `analysis/biodiversity.py`
- `analysis/pressure.py`
- preparar esquelets source-gated per `water.py`, `fire.py`, `climate.py`, `connectivity.py`.

### Fase 4: Diagnosis Engine

Objectiu: passar d'indicadors separats a interpretació integrada.

- Crear diagnosi de fortaleses/debilitats/pressions/oportunitats/riscos/incerteses.
- Fer que cada conclusió apunti a dades i indicadors justificatius.
- Marcar explícitament decisions habilitades i decisions bloquejades.

### Fase 5: Recommendation Engine

Objectiu: generar recomanacions tècniques justificades.

- Cada recomanació ha d'incloure objectiu, justificació, localització, benefici esperat i indicadors.
- No generar recomanacions espacials fortes sense dades suficients.
- En baixa confiança, recomanar validació o monitoratge, no actuació irreversible.

### Fase 6: Product Engine Únic

Objectiu: convertir els exportadors actuals en producte coherent.

- Atles A3 v3 com a base.
- Fitxa executiva d'una pàgina.
- Informe tècnic amb annex.
- Informe executiu sense detalls interns.
- Mapes amb llegendes i context quan les dades existeixin.

## 11. Criteri Per Als Blocs Encara No Coberts

Els blocs obligatoris s'han de mantenir dins la metodologia encara que no siguin calculables avui.

La manera correcta de tractar-los és:

- inventariar font oficial,
- verificar status,
- documentar metadades,
- implementar connector només si status és `verified`,
- normalitzar dades,
- afegir anàlisi,
- afegir interpretació,
- incorporar recomanacions només si la confiança ho permet.

Cap bloc s'ha d'omplir amb dades simulades.

## 12. Conclusió Interna

EcoRadar ja no és només un prototip d'informes. Té:

- un nucli d'àrea d'estudi,
- connectors reals,
- dades processades d'Alinyà,
- EcoRadar Core,
- mapes bàsics,
- producte editorial A3,
- una metodologia de prudència i confiança.

El problema actual no és absència de components, sinó falta d'integració formal.

La següent passa no hauria de ser crear més indicadors ni més connectors. Hauria de ser consolidar el motor com a plataforma:

- una sola entrada de projecte,
- un sol registre de fonts,
- un sol registre de connectors,
- un sol pipeline,
- un sol motor d'anàlisi,
- un sol motor de diagnosi,
- un sol producte editorial principal.

Només després d'aquesta consolidació té sentit ampliar hidrologia, incendis, DEM, clima i camp.

## 13. Primera Reorganització Executada

Data: 2026-07-07

S'ha iniciat la reorganització sense implementar connectors nous ni descarregar dades externes.

Components incorporats:

- `ecoradar/core/context.py`: context comú de projecte i convencions de carpetes.
- `ecoradar/core/source_gate.py`: lectura del registre de fonts i control d'execució segons `connector_status`.
- `ecoradar/diagnosis/engine.py`: motor de diagnosi ecològica a partir d'indicadors existents.
- `ecoradar/recommendations/engine.py`: motor de recomanacions justificades tècnicament.
- `tools/run_ecoradar_diagnosis.py`: pipeline actualitzat perquè generi Core, diagnosi, recomanacions, fitxa executiva i atles.
- `tools/export_informe_diagnosi_fitxa_pdf.py`: Fitxa EcoRadar A3 actualitzada com a quadre de comandament visual.
- `ecoradar/product/fitxa_value.py`: filtre de priorització que avalua quines mancances o funcionalitats aportarien més valor a la Fitxa EcoRadar.

Sortides noves o actualitzades:

- `projectes/Alinya/metadata/ecoradar_diagnosis.json`
- `projectes/Alinya/reports/ecoradar_diagnosis.md`
- `projectes/Alinya/metadata/ecoradar_recommendations.json`
- `projectes/Alinya/indicators/ecoradar_recommendations.csv`
- `projectes/Alinya/reports/ecoradar_recommendations.md`
- `projectes/Alinya/reports/fitxa_diagnosi_ecoradar_alinya.pdf`
- `output/pdf/fitxa_ecoradar_alinya_a3.pdf`
- `projectes/Alinya/metadata/ecoradar_fitxa_value_gate.json`
- `projectes/Alinya/indicators/ecoradar_fitxa_value_gate.csv`
- `projectes/Alinya/reports/ecoradar_fitxa_value_gate.md`

Validació:

- Tests automatitzats: 15 correctes.
- Pipeline principal executat sense refrescar dades externes.
- Fitxa EcoRadar renderitzada a PNG i revisada visualment.

Limitació mantinguda:

- La Fitxa EcoRadar mostra mapa de prioritats preliminars, no zonificació final. No es genera prioritat espacial definitiva fins incorporar teledetecció, hidrologia, topografia, foc i validació de camp.

## 14. Criteri De Priorització Per La Fitxa

S'ha incorporat com a regla de producte que cap nova funcionalitat hauria de ser prioritària si no millora una part concreta de la Fitxa EcoRadar.

Per Alinyà, el filtre actual prioritza:

1. Figura de protecció i context administratiu.
2. Teledetecció de vegetació i humitat.
3. Hidrologia funcional.
4. Relleu, pendent i orientació.
5. Històric d'incendis i continuïtat del combustible.
6. Validació de camp dirigida.

Aquesta llista no afegeix dades noves; ordena el desenvolupament segons el valor que cada peça aportaria a la decisió del gestor.
