# EcoRadar Recommendations

Projecte: `Alinya`
Generat: `2026-07-08T14:37:57+00:00`

Aquest fitxer conté recomanacions derivades exclusivament de la diagnosi ecològica. No és una fitxa ni un informe final.

## 1 Conservació

### CONS-001 · Conservar preventivament HIC i hàbitats prioritaris abans de qualsevol actuació

- Tipus: `conservar`
- Prioritat ecològica: `78.87`
- Urgència: `alta`
- Dificultat: `mitjana`
- Confiança: `alta`
- Justificació: La diagnosi identifica els hàbitats com un dels valors ecològics principals: CORE_02 és molt alt i combina riquesa d'hàbitats, HIC i HIC prioritaris.
- Indicadors: CORE_02, CORE_06, CORE_08
- Fonts: aca_hydrology, connectivity_infraestructura_verda, gbif_occurrences, habitats_terrestres_v3, hic_v2, inaturalist_observations, land_cover_icgc_cobertes_sol, osm_public_use
- Localització: Polígons cartografiats com HIC o HIC prioritari dins l'àrea d'Alinyà.
- Superfície afectada: 3.170,95 ha HIC; 1.229,39 ha HIC prioritaris
- Benefici esperat: Evitar impactes sobre hàbitats de responsabilitat de conservació i mantenir els valors que sustenten la diagnosi.
- Dependències: Validació de camp d'hàbitats abans d'actuacions locals.

### CONS-002 · Mantenir la matriu natural connectada i evitar noves barreres

- Tipus: `millorar connectivitat`
- Prioritat ecològica: `69.01`
- Urgència: `alta`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: La diagnosi relaciona mosaic alt, connectivitat alta i hàbitats de valor; cap capa aïllada explica el funcionament del territori.
- Indicadors: CORE_01, CORE_02, CORE_08, CORE_10
- Fonts: aca_hydrology, connectivity_infraestructura_verda, habitats_terrestres_v3, hic_v2, icgc_dem_mdt, land_cover_icgc_cobertes_sol, osm_public_use
- Localització: Connectors oficials i zones de matriu natural identificades per Infraestructura Verda i cobertes del sòl.
- Superfície afectada: 1.198,60 ha en connectors terrestres principals retallats
- Benefici esperat: Mantenir permeabilitat ecològica i reduir fragmentació futura.
- Dependències: Model de barreres fines i validació de passos/corredors locals.

## 2 Restauració

### REST-001 · Validar zones candidates de restauració abans de convertir el potencial en actuacions

- Tipus: `validar al camp`
- Prioritat ecològica: `56.34`
- Urgència: `mitjana`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: La diagnosi detecta potencial de restauració alt, però encara no priorització espacial ni hàbitats degradats validats.
- Indicadors: CORE_11, CORE_12
- Fonts: aca_hydrology, connectivity_infraestructura_verda, fires_burned_areas, gbif_occurrences, habitats_terrestres_v3, hic_v2, icgc_dem_mdt, inaturalist_observations, land_cover_icgc_cobertes_sol, osm_public_use
- Localització: Àmbit complet; priorització pendent de Sentinel, camp, combustible i SIGPAC/DUN.
- Superfície afectada: 5.464,03 ha d'anàlisi; superfície d'actuació no delimitada
- Benefici esperat: Evitar restauracions mal localitzades i preparar una cartera de zones candidates amb criteri ecològic.
- Dependències: Sentinel, hàbitats degradats, hàbitats font, SIGPAC/DUN i treball de camp.

## 3 Gestió

### GEST-001 · Validar i ordenar l'ús públic on es pot solapar amb hàbitats d'alt valor

- Tipus: `ordenar ús públic`
- Prioritat ecològica: `56.34`
- Urgència: `mitjana`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: La diagnosi detecta valor ecològic molt alt i pressió humana potencial mitjana; això no prova conflicte, però obliga a validar accessos i freqüentació.
- Indicadors: CORE_02, CORE_06, CORE_07
- Fonts: gbif_occurrences, habitats_terrestres_v3, hic_v2, inaturalist_observations, osm_public_use
- Localització: Camins, pistes i punts d'ús públic cartografiats per OSM, especialment propers a HIC i zones connectores.
- Superfície afectada: 124,83 km de camins/pistes OSM; 18 punts d'ús públic
- Benefici esperat: Reduir possibles conflictes entre conservació i ús públic abans que esdevinguin pressions reals.
- Dependències: Comptadors, observació de camp o dades de gestors; Strava només si és legalment compatible.

## 4 Seguiment

### HIDRO-001 · Validar funcionalitat hídrica, fonts i punts d'aigua abans de definir refugis o restauració

- Tipus: `hidrologia`
- Prioritat ecològica: `69.01`
- Urgència: `alta`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: La diagnosi indica que l'aigua està cartografiada parcialment però no funcionalment caracteritzada.
- Indicadors: CORE_10, CORE_04
- Fonts: aca_hydrology, icgc_dem_mdt, land_cover_icgc_cobertes_sol
- Localització: Cursos/drenatge ACA i fonts oficials dins l'àrea d'estudi.
- Superfície afectada: 11,77 km de xarxa hidrogràfica/drenatge; 12 fonts oficials
- Benefici esperat: Millorar la lectura de refugis climàtics, fauna associada a aigua i oportunitats de restauració.
- Dependències: NDWI, verificació de camp de fonts/basses i estat ecològic dels punts d'aigua.

## 5 Treball de camp

### CAMP-001 · Executar una campanya de validació de camp sobre hàbitats, aigua, ús públic i biodiversitat sensible

- Tipus: `validar al camp`
- Prioritat ecològica: `91.55`
- Urgència: `molt alta`
- Dificultat: `mitjana`
- Confiança: `alta`
- Justificació: La diagnosi marca com a robusta la necessitat de camp perquè falten field_biodiversity i field_validation en diversos indicadors.
- Indicadors: CORE_02, CORE_06, CORE_07, CORE_10
- Fonts: aca_hydrology, gbif_occurrences, habitats_terrestres_v3, inaturalist_observations, osm_public_use
- Localització: HIC i HIC prioritaris, punts d'aigua, accessos principals i grups taxonòmics poc representats.
- Superfície afectada: 5.464,03 ha d'àmbit de mostreig; punts finals a definir en pla de camp
- Benefici esperat: Convertir incerteses en criteris verificats i evitar actuacions incompatibles amb hàbitats o espècies sensibles.
- Dependències: Disseny de protocols de camp i importador de dades pròpies EcoRadar.

### FOC-001 · Validar combustible, humitat vegetal i discontinuïtats abans de proposar gestió forestal

- Tipus: `validar al camp`
- Prioritat ecològica: `69.01`
- Urgència: `alta`
- Dificultat: `mitjana`
- Confiança: `mitjana`
- Justificació: La diagnosi no tanca resiliència al foc perquè falten NDMI, LST i estructura oficial de combustible.
- Indicadors: CORE_09, CORE_01, CORE_10
- Fonts: aca_hydrology, connectivity_infraestructura_verda, fires_burned_areas, habitats_terrestres_v3, icgc_dem_mdt, land_cover_icgc_cobertes_sol, osm_public_use
- Localització: Masses forestals, matollars, prats i discontinuïtats detectades per cobertes del sòl i DEM.
- Superfície afectada: 5.464,03 ha d'àmbit potencial; actuacions forestals no delimitades encara
- Benefici esperat: Evitar actuacions forestals prematures i separar zones on el mosaic ajuda de zones on pot faltar discontinuïtat.
- Dependències: NDMI, LST, font oficial de combustible/estructura forestal i validació de camp.

## 6 Dades pendents

### DADES-001 · Desbloquejar Copernicus i clima abans de tancar vegetació, refugis climàtics i vulnerabilitat

- Tipus: `investigar`
- Prioritat ecològica: `97.18`
- Urgència: `molt alta`
- Dificultat: `baixa`
- Confiança: `alta`
- Justificació: La diagnosi identifica teledetecció i clima com les dades que més condicionen vegetació, clima, foc, restauració i prioritat de gestió.
- Indicadors: CORE_03, CORE_04, CORE_05, CORE_09, CORE_11, CORE_12
- Fonts: -
- Localització: Tot l'àmbit d'Alinyà; lectura raster i climàtica homogènia.
- Superfície afectada: 5.464,03 ha
- Benefici esperat: Augmentar de forma directa la confiança dels indicadors climàtics, de vegetació, foc i restauració.
- Dependències: Credencials Copernicus, Meteocat/AEMET i definició de producte LST.

### AGR-001 · Verificar prats, conreus residuals i espais oberts amb SIGPAC/DUN abans de gestió agrària

- Tipus: `gestió agrària`
- Prioritat ecològica: `61.97`
- Urgència: `mitjana`
- Dificultat: `baixa`
- Confiança: `mitjana`
- Justificació: La diagnosi apunta que els espais oberts poden tenir funció ecològica desproporcionada, però SIGPAC/DUN no està disponible.
- Indicadors: CORE_01, CORE_09
- Fonts: aca_hydrology, connectivity_infraestructura_verda, fires_burned_areas, habitats_terrestres_v3, icgc_dem_mdt, land_cover_icgc_cobertes_sol, osm_public_use
- Localització: Prats, herbassars, conreus residuals i ecotons detectats per cobertes/hàbitats.
- Superfície afectada: 5.464,03 ha d'àmbit; superfície agrària fina pendent de SIGPAC/DUN
- Benefici esperat: Distingir espais oberts ecològicament estratègics de zones sense funció prioritària abans de gestionar o restaurar.
- Dependències: Accés oficial SIGPAC/DUN i validació de camp dels espais oberts.
