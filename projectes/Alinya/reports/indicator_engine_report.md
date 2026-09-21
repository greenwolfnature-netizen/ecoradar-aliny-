# Indicator Engine Report

Projecte: `Alinya`
Generat: `2026-09-21T19:44:41+00:00`

## Preflight obligatori

| Fitxer | Existeix |
| --- | --- |
| data_availability_report.json | sí |
| connectors_status_report.json | sí |
| indicators_completeness_report.json | sí |

## Resum

| Estat | Nombre |
| --- | ---: |
| COMPLET | 4 |
| NO AVALUABLE | 2 |
| PARCIAL | 6 |

## Indicadors EcoRadar Core

| Codi | Indicador | Resultat | Tipus | Estat | Confiança | Fonts utilitzades | Fonts absents |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CORE_01 | Configuració i mosaic funcional del paisatge | Perfil estructural · bosc 88,4 % · taca màxima 477,4 ha | descriptive_profile | PARCIAL | mitjana | land_cover_icgc_cobertes_sol | mosaic_functional_reference, field_validation |
| CORE_02 | Responsabilitat territorial per hàbitats d’interès | 3.171,0 ha HIC · 58,0 % · 1.229,4 ha prioritaris | direct_inventory | COMPLET | mitjana | habitats_terrestres_v3, hic_v2 | habitat_condition_field_data |
| CORE_03 | Activitat verda observada (NDVI) | NDVI 0,676 · 15/09/2026 | direct_reading | COMPLET | mitjana | copernicus_sentinel_ndvi | phenological_baseline, field_validation |
| CORE_04 | Potencial estructural de refugi climàtic | Estructural parcial · senyal satel·lital 42,4 % | dual_profile | PARCIAL | mitjana | land_cover_icgc_cobertes_sol, icgc_dem_mdt, detailed_surface_temperature, copernicus_sentinel_ndmi, copernicus_sentinel_ndvi | microclimate_field_series, permanent_water_validation |
| CORE_05 | Perfil d’exposició i vulnerabilitat climàtica ecològica | NO AVALUABLE · només exposició parcial | three_axis_profile | NO AVALUABLE | baixa | meteocat, detailed_surface_temperature | climate_normals, receptor_sensitivity, adaptive_capacity_validation |
| CORE_06 | Cobertura del coneixement de biodiversitat | 3.680 registres · 66/84 cel·les amb dades | knowledge_profile | PARCIAL | baixa | gbif_occurrences, inaturalist_observations | standardized_field_inventory, BDBC |
| CORE_07 | Accessibilitat cartografiada i ús potencial | 124,8 km · 2,28 km/km² · 18 punts | direct_inventory | COMPLET | mitjana | osm_public_use | visitor_counts, field_impact_observations |
| CORE_08 | Continuïtat estructural i connectivitat potencial | 1.198,6 ha en connectors · funcionalitat NO AVALUABLE | two_level_profile | PARCIAL | mitjana | connectivity_infraestructura_verda, land_cover_icgc_cobertes_sol | species_specific_resistance, movement_validation |
| CORE_09 | Perfil de susceptibilitat i recuperació davant del foc | Propagació actual moderat · recuperació NO AVALUABLE | four_axis_profile | PARCIAL | mitjana | meteocat, pla_alfa, land_cover_icgc_cobertes_sol, icgc_dem_mdt, fires_burned_areas, osm_public_use, aca_hydrology | fuel_structure_field_data, postfire_severity_timeseries, recovery_field_validation |
| CORE_10 | Presència hídrica cartografiada | 11,8 km de xarxa · 12 fonts cartografiades | direct_inventory | COMPLET | mitjana | aca_hydrology | flow_and_permanence, water_quality, riparian_condition, field_validation |
| CORE_11 | Cribratge de necessitat i oportunitat de restauració | NO AVALUABLE · falta diagnosi de degradació | decision_gate | NO AVALUABLE | baixa | - | degradation_evidence, reference_ecosystem, restoration_objective, benefit_feasibility_risk |
| CORE_12 | Síntesi multicriteri per a la gestió | SENSE PRIORITAT ÚNICA · 1 P1, 4 P2 i 1 NO AVALUABLE | multicriteria_decision | PARCIAL | mitjana | aca_hydrology, connectivity_infraestructura_verda, copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, fires_burned_areas, gbif_occurrences, habitats_terrestres_v3, hic_v2, icgc_dem_mdt, inaturalist_observations, land_cover_icgc_cobertes_sol, meteocat, osm_public_use, pla_alfa | approved_management_units, approved_objectives_and_preferences, field_validation |

## Limitacions i impacte sobre la diagnosi

### CORE_01 · Configuració i mosaic funcional del paisatge
- Càlcul: Mostra proporcions de coberta, Shannon només com a descriptor composicional i mètriques espacials de les taques cartografiades. No agrega els components ni premia fragmentació, diversitat o vora.
- Resultat: Perfil estructural · bosc 88,4 % · taca màxima 477,4 ha
- Vector de confiança: {"completesa": {"rating": "adequada", "reason": "Cobertes ICGC disponibles per a tot l’àmbit."}, "vigencia": {"rating": "adequada", "reason": "Capa estructural 2024; no es presenta com una observació diària."}, "cobertura": {"rating": "adequada", "reason": "La suma de cobertes coincideix amb l’àmbit validat."}, "resolucio": {"rating": "limitada", "reason": "La cartografia permet estructura general, però la sensibilitat a gra no s’ha contrastat."}, "qa": {"rating": "adequada", "reason": "Geometries oficials retallades i àrees calculades en EPSG:25831."}, "representativitat": {"rating": "limitada", "reason": "No s’ha definit l’hàbitat o procés receptor de la configuració."}, "biaix": {"rating": "limitada", "reason": "Les vores cartogràfiques poden incloure límits de classificació sense funció d’ecotò."}, "validacio": {"rating": "insuficient", "reason": "No hi ha referència local ni validació de camp de la funcionalitat del mosaic."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — validacio.
- Limitacions: La mida i la vora de taca depenen de l’escala i de la classificació de la font.; Els ecotons funcionals no es classifiquen sense contrast, objectiu i validació.
- Impacte: Aporta estructura territorial i identifica quina configuració cal validar per hàbitat o procés.

### CORE_02 · Responsabilitat territorial per hàbitats d’interès
- Càlcul: Valors directes d’àrea i proporció sobre 5.464,03 ha; les 289 presències puntuals no es converteixen en hectàrees.
- Resultat: 3.171,0 ha HIC · 58,0 % · 1.229,4 ha prioritaris
- Vector de confiança: {"completesa": {"rating": "adequada", "reason": "Polígons, camps HIC i presències puntuals estan disponibles."}, "vigencia": {"rating": "adequada", "reason": "Versió oficial d’hàbitats documentada com a inventari, no com a lectura d’avui."}, "cobertura": {"rating": "adequada", "reason": "La superfície poligonal retallada cobreix l’àmbit documentat."}, "resolucio": {"rating": "limitada", "reason": "Els hàbitats menors de 1,5 ha poden constar com a punts i no com a superfície."}, "qa": {"rating": "adequada", "reason": "Àrees recalculades en EPSG:25831 i punts exclosos del denominador superficial."}, "representativitat": {"rating": "adequada", "reason": "Les mètriques representen responsabilitat territorial cartografiada."}, "biaix": {"rating": "limitada", "reason": "La representació mínima de la cartografia pot ometre o simplificar peces petites."}, "validacio": {"rating": "insuficient", "reason": "No hi ha variables locals d’estructura, funcions, pressions i perspectives."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — validacio.
- Limitacions: No avalua estat de conservació.; La presència HIC incrementa responsabilitat i cautela, no qualitat ecològica.
- Impacte: Identifica obligacions i sectors de prudència sense fabricar una puntuació de conservació.

### CORE_03 · Activitat verda observada (NDVI)
- Càlcul: Mediana, P10 i P90 dels píxels NDVI vàlids de l’escena Sentinel-2 L2A; no es transforma a 0–100.
- Resultat: NDVI 0,676 · 15/09/2026
- Vector de confiança: {"completesa": {"rating": "adequada", "reason": "NDVI, distribució i màscara SCL consten a l’escena."}, "vigencia": {"rating": "insuficient", "reason": "L’escena és del 07/07/2026 i només pot descriure aquella data."}, "cobertura": {"rating": "adequada", "reason": "Cobertura vàlida 96.18 % de l’àmbit rasteritzat."}, "resolucio": {"rating": "adequada", "reason": "Sentinel-2 L2A a 10 m per a NDVI."}, "qa": {"rating": "adequada", "reason": "dataMask i classes SCL 4, 5 i 6; núvol, ombra, neu i invàlids exclosos."}, "representativitat": {"rating": "limitada", "reason": "Una mediana territorial barreja cobertes i gradients altitudinals."}, "biaix": {"rating": "limitada", "reason": "Una sola escena no controla fenologia ni variabilitat estacional."}, "validacio": {"rating": "limitada", "reason": "La lectura espectral és verificable, però no s’ha contrastat amb vigor o estat al camp."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — vigencia.
- Limitacions: Descriu verdor espectral el 07/07/2026, no l’estat actual.; No és biodiversitat, biomassa, humitat ni estat de conservació.
- Impacte: Aporta evidència datada sobre activitat verda i conserva separat el context fenològic no disponible.

### CORE_04 · Potencial estructural de refugi climàtic
- Càlcul: Manté separat el perfil estructural del senyal relatiu 0,50·frescor LST + 0,30·NDMI + 0,20·NDVI. El 42,3 % usa només el denominador vegetat amb les tres entrades vàlides.
- Resultat: Estructural parcial · senyal satel·lital 42,4 %
- Vector de confiança: {"completesa": {"rating": "limitada", "reason": "Hi ha estructura i senyal satel·lital, però no microclima ni permanència hídrica."}, "vigencia": {"rating": "insuficient", "reason": "El producte barreja un compost multitemporal LST i una escena Sentinel-2 antiga."}, "cobertura": {"rating": "adequada", "reason": "El denominador vàlid cobreix 89.7 % del raster de l’àmbit."}, "resolucio": {"rating": "limitada", "reason": "Les entrades es reprojecten a una malla comuna, però la LST original és de 30 m i l’espectral de 10 m."}, "qa": {"rating": "adequada", "reason": "El denominador exigeix LST, NDMI i NDVI vàlids i NDVI ≥ 0,30."}, "representativitat": {"rating": "limitada", "reason": "Un senyal superficial relatiu no representa el microclima de tots els receptors."}, "biaix": {"rating": "limitada", "reason": "La composició estival pot suavitzar extrems i la cobertura forestal no garanteix refugi."}, "validacio": {"rating": "insuficient", "reason": "No hi ha sensors microclimàtics ni contrast de camp en episodis càlids i secs."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — vigencia, validacio.
- Limitacions: El senyal no és una observació d’avui ni una normal climàtica.; Aigua i fonts es dibuixen com a context i no entren en la fórmula satel·lital.
- Impacte: Permet localitzar zones candidates per contrastar, però no declara refugis funcionals.

### CORE_05 · Perfil d’exposició i vulnerabilitat climàtica ecològica
- Càlcul: Presenta separadament exposició, sensibilitat i capacitat adaptativa; no calcula mitjana ni usa altres CORE com a substituts.
- Resultat: NO AVALUABLE · només exposició parcial
- Vector de confiança: {"completesa": {"rating": "insuficient", "reason": "Només hi ha context d’exposició; falten sensibilitat i capacitat adaptativa."}, "vigencia": {"rating": "limitada", "reason": "Meteorologia és actual, però LST i vegetació són context multitemporal o antic."}, "cobertura": {"rating": "limitada", "reason": "Meteorologia és puntual i no representa cada vessant; falta exposició territorial homogènia."}, "resolucio": {"rating": "limitada", "reason": "Es barregen suport puntual, raster i inventari estructural sense model de receptor."}, "qa": {"rating": "adequada", "reason": "Cada font conserva data, suport i semàntica al registre de lectures."}, "representativitat": {"rating": "insuficient", "reason": "No s’ha definit cap receptor ecològic ni relació dosi-resposta."}, "biaix": {"rating": "insuficient", "reason": "Els proxies estructurals no poden substituir sensibilitat ni capacitat adaptativa."}, "validacio": {"rating": "insuficient", "reason": "No hi ha model local validat de vulnerabilitat climàtica."}}
- Raó de confiança: Confiança baixa: dimensions insuficients — completesa, representativitat, biaix, validacio.
- Limitacions: Exposició alta no equival a vulnerabilitat alta.; Falten normals, extrems i resposta ecològica per receptor.
- Impacte: Evita atribuir vulnerabilitat a orientació, pendent, bosc o aigua sense mecanisme validat.

### CORE_06 · Cobertura del coneixement de biodiversitat
- Càlcul: Descriu volum, distribució en quadrícula d’1 km, actualitat, cobertura taxonòmica, truncament i buits; no agrega aquests camps.
- Resultat: 3.680 registres · 66/84 cel·les amb dades
- Vector de confiança: {"completesa": {"rating": "limitada", "reason": "GBIF va descarregar 10000 de 31169 coincidències i iNaturalist sí va completar la consulta."}, "vigencia": {"rating": "limitada", "reason": "Hi ha registres recents i històrics; l’antiguitat es conserva i no implica presència actual."}, "cobertura": {"rating": "limitada", "reason": "66 de 84 cel·les d’1 km tenen almenys un registre públic."}, "resolucio": {"rating": "adequada", "reason": "Les ocurrències es normalitzen com a punts i només s’exposen agregades a 1 km."}, "qa": {"rating": "limitada", "reason": "Filtre espacial i taxonòmic aplicat, però persisteixen coordenades, identificacions i registres dubtosos."}, "representativitat": {"rating": "insuficient", "reason": "Les fonts oportunistes no representen un mostreig comparable d’espècies o abundància."}, "biaix": {"rating": "insuficient", "reason": "Esforç, accessibilitat, grup taxonòmic i estació introdueixen biaix no corregit."}, "validacio": {"rating": "insuficient", "reason": "No hi ha inventari de camp homogeni ni llista de referència per estimar completesa biològica."}}
- Raó de confiança: Confiança baixa: dimensions insuficients — representativitat, biaix, validacio.
- Limitacions: Pocs registres no signifiquen baixa biodiversitat.; La consulta GBIF arriba al sostre de seguretat de 10.000 registres.
- Impacte: Orienta prospecció i mostra on la informació és insuficient sense convertir cites en estat biològic.

### CORE_07 · Accessibilitat cartografiada i ús potencial
- Càlcul: Mostra km, km/km² i punts per 1.000 ha per separat; no els combina en una puntuació de pressió.
- Resultat: 124,8 km · 2,28 km/km² · 18 punts
- Vector de confiança: {"completesa": {"rating": "adequada", "reason": "Xarxa i punts OSM previstos al perfil estan disponibles."}, "vigencia": {"rating": "limitada", "reason": "OSM és una base viva sense data d’observació homogènia per element."}, "cobertura": {"rating": "adequada", "reason": "Consulta i retall aplicats a tot l’àmbit."}, "resolucio": {"rating": "adequada", "reason": "Geometries lineals i puntuals adequades per descriure accessibilitat cartografiada."}, "qa": {"rating": "limitada", "reason": "La completitud i classificació d’OSM depenen de contribucions comunitàries."}, "representativitat": {"rating": "adequada", "reason": "Representa accessibilitat cartografiada; no intensitat d’ús."}, "biaix": {"rating": "limitada", "reason": "Pot haver-hi vies no cartografiades, duplicades o classificades de manera desigual."}, "validacio": {"rating": "insuficient", "reason": "No hi ha comptadors, afluència, incidències ni impactes de camp."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — validacio.
- Limitacions: OSM no mesura freqüentació, comportament ni impacte.; Més accessibilitat també pot facilitar seguiment i resposta de gestió.
- Impacte: Permet seleccionar trams i punts a contrastar abans d’afirmar pressió humana.

### CORE_08 · Continuïtat estructural i connectivitat potencial
- Càlcul: Nivell 1: coberta natural i superfície de connectors oficials. Nivell 2 funcional queda buit fins definir receptor, nodes, distància i resistències.
- Resultat: 1.198,6 ha en connectors · funcionalitat NO AVALUABLE
- Vector de confiança: {"completesa": {"rating": "limitada", "reason": "Hi ha cobertes i connectors oficials; falten nodes, resistències i receptors."}, "vigencia": {"rating": "adequada", "reason": "Capes estructurals amb versió documentada; no s’interpreten com a lectura diària."}, "cobertura": {"rating": "adequada", "reason": "Cobertes i índex oficial cobreixen l’àmbit."}, "resolucio": {"rating": "limitada", "reason": "La unitat oficial general no resol totes les barreres o passos locals."}, "qa": {"rating": "adequada", "reason": "Geometries oficials retallades i mètriques d’àrea traçades."}, "representativitat": {"rating": "limitada", "reason": "Representa continuïtat cartogràfica general, no moviment de cap espècie concreta."}, "biaix": {"rating": "limitada", "reason": "La proporció de coberta natural no incorpora qualitat de node ni resistència de matriu."}, "validacio": {"rating": "insuficient", "reason": "No hi ha telemetria, genètica, passos verificats ni model receptor-específic."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — validacio.
- Limitacions: Continuïtat estructural no garanteix moviment o flux genètic.; Les vies OSM no reben un signe fix de barrera.
- Impacte: Diferencia on hi ha estructura contínua d’allò que encara no es pot afirmar sobre permeabilitat funcional.

### CORE_09 · Perfil de susceptibilitat i recuperació davant del foc
- Càlcul: Quatre eixos no agregats: propagació potencial actual, sensibilitat ecològica, recuperació postincendi i context operatiu. Pla Alfa és context oficial independent.
- Resultat: Propagació actual moderat · recuperació NO AVALUABLE
- Vector de confiança: {"completesa": {"rating": "limitada", "reason": "La propagació actual té entrades parcials; sensibilitat i recuperació no són avaluables."}, "vigencia": {"rating": "adequada", "reason": "Meteorologia, precipitació i Pla Alfa conserven data actual; NDMI/LST antics queden exclosos del perill actual."}, "cobertura": {"rating": "adequada", "reason": "El perill actual declara 98.0 % vàlid i la superfície sense dada."}, "resolucio": {"rating": "limitada", "reason": "Malla de 100 m amb meteorologia puntual de Y4/CJ i capes estructurals més fines."}, "qa": {"rating": "limitada", "reason": "Qualitat/actualització efectiva del producte 61.2 %; no s’anomena confiança ecològica."}, "representativitat": {"rating": "limitada", "reason": "El perfil separa propagació, sensibilitat, recuperació i operativa; només la primera té lectura actual."}, "biaix": {"rating": "limitada", "reason": "Falten combustible mesurat, humitat actual i vent territorial per valls i carenes."}, "validacio": {"rating": "insuficient", "reason": "No hi ha validació del comportament o recuperació amb incendis observats locals."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — validacio.
- Limitacions: El perill actual no és probabilitat d’ignició ni predicció d’incendi.; Camins, aigua i superfície cremada no sumen ni resten resiliència de manera lineal.
- Impacte: Permet vigilar propagació actual sense confondre-la amb sensibilitat, capacitat d’extinció o recuperació ecològica.

### CORE_10 · Presència hídrica cartografiada
- Càlcul: Mostra longitud, densitat i nombre de fonts per separat; no transforma presència en funcionalitat o disponibilitat.
- Resultat: 11,8 km de xarxa · 12 fonts cartografiades
- Vector de confiança: {"completesa": {"rating": "adequada", "reason": "Cursos, drenatges, fonts i capes de basses/estanys/zones humides s’han consultat."}, "vigencia": {"rating": "adequada", "reason": "Inventari estructural amb data de consulta; no s’interpreta com a aigua disponible avui."}, "cobertura": {"rating": "adequada", "reason": "Geometries oficials retallades a tot l’àmbit."}, "resolucio": {"rating": "limitada", "reason": "La cartografia general pot ometre surgències o punts temporals locals."}, "qa": {"rating": "adequada", "reason": "Longitud i recomptes derivats de geometries oficials normalitzades."}, "representativitat": {"rating": "adequada", "reason": "Representa presència cartografiada, que és la dimensió declarada."}, "biaix": {"rating": "limitada", "reason": "La no presència a la capa no prova inexistència i no descriu temporalitat."}, "validacio": {"rating": "insuficient", "reason": "No hi ha cabal, permanència, qualitat, ribera ni ús faunístic verificats."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — validacio.
- Limitacions: No informa de cabal, permanència, qualitat o estat de ribera.; Zero basses o zones humides a la font retallada no prova absència al terreny.
- Impacte: Dona una base d’inventari per planificar verificació hídrica sense afirmar funció actual.

### CORE_11 · Cribratge de necessitat i oportunitat de restauració
- Càlcul: Porta no compensatòria: degradació demostrada, referència/objectiu, benefici davant no-intervenció i viabilitat/risc. En fallar les entrades essencials, no calcula resultat.
- Resultat: NO AVALUABLE · falta diagnosi de degradació
- Vector de confiança: {"completesa": {"rating": "insuficient", "reason": "Falten totes les entrades essencials de la porta de decisió."}, "vigencia": {"rating": "insuficient", "reason": "No hi ha estat ni tendència de degradació datats per sector."}, "cobertura": {"rating": "insuficient", "reason": "No hi ha sectors candidats delimitats amb evidència de degradació."}, "resolucio": {"rating": "insuficient", "reason": "No existeix una unitat de restauració vinculada a objectiu i referència."}, "qa": {"rating": "insuficient", "reason": "No hi ha protocol de diagnosi de degradació, benefici, viabilitat i risc."}, "representativitat": {"rating": "insuficient", "reason": "Els altres CORE no substitueixen evidència directa de necessitat de restauració."}, "biaix": {"rating": "insuficient", "reason": "Agregar valors, vulnerabilitats o accessibilitat induiria una prioritat sense mecanisme."}, "validacio": {"rating": "insuficient", "reason": "No hi ha validació de camp ni acord de l’objectiu de restauració."}}
- Raó de confiança: Confiança baixa: dimensions insuficients — completesa, vigencia, cobertura, resolucio, qa, representativitat, biaix, validacio.
- Limitacions: Responsabilitat HIC, vulnerabilitat o connectivitat no impliquen necessitat de restaurar.; No es delimiten superfícies ni actuacions candidates.
- Impacte: Impedeix recomanar restauració sense diagnosi i manté obertes protecció, seguiment i no-intervenció.

### CORE_12 · Síntesi multicriteri per a la gestió
- Càlcul: Matriu sector × alternativa amb restriccions i vetos. No calcula mitjana, no transforma els CORE en una sola escala i manté alternatives no dominades.
- Resultat: SENSE PRIORITAT ÚNICA · 1 P1, 4 P2 i 1 NO AVALUABLE
- Vector de confiança: {"completesa": {"rating": "limitada", "reason": "La matriu pot prioritzar prudència i verificació, però no actuacions de restauració."}, "vigencia": {"rating": "limitada", "reason": "El bloc de foc caduca diàriament; els inventaris són estructurals."}, "cobertura": {"rating": "adequada", "reason": "Les unitats provenen de capes o quadrícules documentades, no de sectors inventats."}, "resolucio": {"rating": "limitada", "reason": "Les unitats de font encara no són unitats de gestió aprovades."}, "qa": {"rating": "adequada", "reason": "Cada fila conserva font, tipus de resultat i veto explícit."}, "representativitat": {"rating": "limitada", "reason": "La síntesi cobreix decisions compatibles amb les dades disponibles, no tot el pla de gestió."}, "biaix": {"rating": "limitada", "reason": "No hi ha preferències ni llindars aprovats per ordenar alternatives no dominades."}, "validacio": {"rating": "insuficient", "reason": "Falta acord del gestor sobre objectius, unitats i criteris de decisió."}}
- Raó de confiança: Confiança mitjana: dimensions insuficients — validacio.
- Limitacions: P1/P2 són categories de decisió per fila, no puntuacions ecològiques.; La síntesi s’ha de reexecutar amb cada snapshot i després d’aprovar unitats i objectius.
- Impacte: Dona accions justificades i conflictes visibles sense fabricar una falsa prioritat territorial única.
