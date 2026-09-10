# EcoRadar Recommendations

Projecte: `Alinya`
Generat: `2026-09-10T04:50:18+00:00`

Aquest fitxer conté recomanacions derivades exclusivament de la diagnosi ecològica. No és una fitxa ni un informe final.

## 1 Conservació

### CONS-001 · Conservar preventivament HIC i hàbitats prioritaris abans de qualsevol actuació

- Tipus: `conservar`
- Categoria de decisió: `P1`
- Estat de decisió: `alternativa candidata documentada`
- Urgència: `alta`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: CORE_02 documenta responsabilitat territorial per HIC i HIC prioritaris, sense atribuir-los estat de conservació. La possible irreversibilitat justifica una regla preventiva de no-deteriorament.
- Indicadors: CORE_02, CORE_06, CORE_08
- Fonts: habitats_terrestres_v3, hic_v2
- Localització: Polígons cartografiats com HIC o HIC prioritari dins l'àrea d'Alinyà.
- Superfície afectada: 3.170,95 ha HIC; 1.229,39 ha HIC prioritaris
- Benefici esperat: Evitar impactes sobre hàbitats de responsabilitat de conservació i mantenir els valors que sustenten la diagnosi.
- Dependències: Validació de camp d'hàbitats abans d'actuacions locals.

### CONS-002 · Mantenir la matriu natural connectada i evitar noves barreres

- Tipus: `millorar connectivitat`
- Categoria de decisió: `P2`
- Estat de decisió: `alternativa candidata documentada`
- Urgència: `alta`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: La diagnosi descriu configuració del mosaic, HIC i continuïtat estructural per separat; cap capa aïllada prova funcionalitat ecològica.
- Indicadors: CORE_01, CORE_02, CORE_08, CORE_10
- Fonts: connectivity_infraestructura_verda, land_cover_icgc_cobertes_sol, osm_public_use
- Localització: Connectors oficials i zones de matriu natural identificades per Infraestructura Verda i cobertes del sòl.
- Superfície afectada: 1.198,60 ha en connectors terrestres principals retallats
- Benefici esperat: Mantenir permeabilitat ecològica i reduir fragmentació futura.
- Dependències: Model de barreres fines i validació de passos/corredors locals.

## 2 Restauració

### REST-001 · Validar zones candidates de restauració abans de convertir el potencial en actuacions

- Tipus: `validar al camp`
- Categoria de decisió: `NO AVALUABLE`
- Estat de decisió: `veto per manca d'evidència essencial`
- Urgència: `mitjana`
- Dificultat: `mitjana`
- Confiança: `baixa`
- Justificació: CORE_11 retorna NO AVALUABLE: no hi ha degradació demostrada, referència, objectiu, benefici comparat amb no-intervenció ni viabilitat.
- Indicadors: CORE_11, CORE_12
- Fonts: aca_hydrology, connectivity_infraestructura_verda, copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, fires_burned_areas, gbif_occurrences, habitats_terrestres_v3, hic_v2, icgc_dem_mdt, inaturalist_observations, land_cover_icgc_cobertes_sol, meteocat, osm_public_use, pla_alfa
- Localització: Cap sector de restauració és justificable fins completar la porta de decisió.
- Superfície afectada: 5.464,03 ha d'anàlisi; superfície d'actuació no delimitada
- Benefici esperat: Evitar restauracions mal localitzades i preparar una cartera de zones candidates amb criteri ecològic.
- Dependències: Degradació demostrada, ecosistema de referència, objectiu, benefici, viabilitat, risc i treball de camp.

## 3 Gestió

### GEST-001 · Validar i ordenar l'ús públic on es pot solapar amb hàbitats d'alt valor

- Tipus: `ordenar ús públic`
- Categoria de decisió: `P2`
- Estat de decisió: `alternativa candidata documentada`
- Urgència: `mitjana`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: CORE_07 documenta accessibilitat cartografiada, no pressió. La coincidència espacial amb HIC o connectors indica on mesurar ús i impacte abans de regular.
- Indicadors: CORE_02, CORE_06, CORE_07
- Fonts: connectivity_infraestructura_verda, land_cover_icgc_cobertes_sol, osm_public_use
- Localització: Camins, pistes i punts d'ús públic cartografiats per OSM, especialment propers a HIC i zones connectores.
- Superfície afectada: 124,83 km de camins/pistes OSM; 18 punts d'ús públic
- Benefici esperat: Reduir possibles conflictes entre conservació i ús públic abans que esdevinguin pressions reals.
- Dependències: Comptadors, observació de camp o dades de gestors; Strava només si és legalment compatible.

## 4 Seguiment

### HIDRO-001 · Validar funcionalitat hídrica, fonts i punts d'aigua abans de definir refugis o restauració

- Tipus: `hidrologia`
- Categoria de decisió: `P2`
- Estat de decisió: `alternativa candidata documentada`
- Urgència: `alta`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: La diagnosi indica que l'aigua està cartografiada parcialment però no funcionalment caracteritzada.
- Indicadors: CORE_10, CORE_04
- Fonts: aca_hydrology, copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, icgc_dem_mdt, land_cover_icgc_cobertes_sol
- Localització: Cursos/drenatge ACA i fonts oficials dins l'àrea d'estudi.
- Superfície afectada: 11,77 km de xarxa hidrogràfica/drenatge; 12 fonts oficials
- Benefici esperat: Millorar la lectura de refugis climàtics, fauna associada a aigua i oportunitats de restauració.
- Dependències: NDWI, verificació de camp de fonts/basses i estat ecològic dels punts d'aigua.

## 5 Treball de camp

### CAMP-001 · Executar una campanya de validació de camp sobre hàbitats, aigua, ús públic i biodiversitat sensible

- Tipus: `validar al camp`
- Categoria de decisió: `P2`
- Estat de decisió: `alternativa candidata documentada`
- Urgència: `molt alta`
- Dificultat: `mitjana`
- Confiança: `baixa`
- Justificació: La diagnosi marca com a robusta la necessitat de camp perquè falten field_biodiversity i field_validation en diversos indicadors.
- Indicadors: CORE_02, CORE_06, CORE_07, CORE_10
- Fonts: aca_hydrology, connectivity_infraestructura_verda, copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, fires_burned_areas, gbif_occurrences, habitats_terrestres_v3, hic_v2, icgc_dem_mdt, inaturalist_observations, land_cover_icgc_cobertes_sol, meteocat, osm_public_use, pla_alfa
- Localització: HIC i HIC prioritaris, punts d'aigua, accessos principals i grups taxonòmics poc representats.
- Superfície afectada: 5.464,03 ha d'àmbit de mostreig; punts finals a definir en pla de camp
- Benefici esperat: Convertir incerteses en criteris verificats i evitar actuacions incompatibles amb hàbitats o espècies sensibles.
- Dependències: Disseny de protocols de camp i importador de dades pròpies EcoRadar.

### FOC-001 · Validar combustible, humitat vegetal i discontinuïtats abans de proposar gestió forestal

- Tipus: `validar al camp`
- Categoria de decisió: `P2`
- Estat de decisió: `alternativa candidata documentada`
- Urgència: `alta`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: CORE_09 separa propagació actual, sensibilitat, recuperació i operativa. NDMI i LST disponibles són massa antics o multitemporals per descriure l'estat actual i falta combustible de camp.
- Indicadors: CORE_09, CORE_01, CORE_10
- Fonts: aca_hydrology, fires_burned_areas, icgc_dem_mdt, land_cover_icgc_cobertes_sol, meteocat, osm_public_use, pla_alfa
- Localització: Masses forestals, matollars, prats i discontinuïtats detectades per cobertes del sòl i DEM.
- Superfície afectada: 5.464,03 ha d'àmbit potencial; actuacions forestals no delimitades encara
- Benefici esperat: Evitar actuacions forestals prematures i separar zones on el mosaic ajuda de zones on pot faltar discontinuïtat.
- Dependències: Nova escena NDMI QA-vàlida, combustible/estructura forestal i validació de camp.

## 6 Dades pendents

### AGR-001 · Verificar prats, conreus residuals i espais oberts amb SIGPAC/DUN abans de gestió agrària

- Tipus: `gestió agrària`
- Categoria de decisió: `P2`
- Estat de decisió: `alternativa candidata documentada`
- Urgència: `mitjana`
- Dificultat: `baixa`
- Confiança: `mitjana`
- Justificació: CORE_01 descriu un 9,34 % d'espais oberts i agraris, però no els assigna qualitat ni signe ecològic sense objectiu i contrast.
- Indicadors: CORE_01, CORE_09
- Fonts: land_cover_icgc_cobertes_sol
- Localització: Prats, herbassars, conreus residuals i ecotons detectats per cobertes/hàbitats.
- Superfície afectada: 5.464,03 ha d'àmbit; superfície agrària fina pendent de SIGPAC/DUN
- Benefici esperat: Distingir espais oberts ecològicament estratègics de zones sense funció prioritària abans de gestionar o restaurar.
- Dependències: Accés oficial SIGPAC/DUN i validació de camp dels espais oberts.

### DADES-001 · Desbloquejar Copernicus i clima abans de tancar vegetació, refugis climàtics i vulnerabilitat

- Tipus: `investigar`
- Categoria de decisió: `P2`
- Estat de decisió: `alternativa candidata documentada`
- Urgència: `molt alta`
- Dificultat: `baixa`
- Confiança: `baixa`
- Justificació: L’escena Sentinel-2 disponible és del 07/07/2026 i la LST és un compost multitemporal. Cal una nova escena QA-vàlida i normals compatibles per actualitzar vegetació i clima.
- Indicadors: CORE_03, CORE_04, CORE_05, CORE_09, CORE_11, CORE_12
- Fonts: copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, icgc_dem_mdt, land_cover_icgc_cobertes_sol, meteocat
- Localització: Tot l'àmbit d'Alinyà; lectura raster i climàtica homogènia.
- Superfície afectada: 5.464,03 ha
- Benefici esperat: Augmentar de forma directa la confiança dels indicadors climàtics, de vegetació, foc i restauració.
- Dependències: COPERNICUS_CLIENT_ID i COPERNICUS_CLIENT_SECRET per seleccionar una escena recent amb cobertura real i SCL; normals climàtiques verificades.
