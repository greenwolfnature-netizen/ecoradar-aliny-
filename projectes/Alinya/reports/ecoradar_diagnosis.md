# EcoRadar Diagnosis

Projecte: `Alinya`
Generat: `2026-09-10T05:38:12+00:00`

## Resum

- Estat: `diagnosi contextual amb perfils no compensatoris`
- Confiança: `baixa`
- Conclusions robustes: `0`
- Conclusions provisionals: `6`

## Conclusions

### Diagnosi amb lectures directes, perfils i portes de decisió

- Secció: `situacio_actual`
- Interpretació: Els dotze RADAR ja no comparteixen una escala artificial. Al snapshot actual hi ha quatre resultats complets per a la dimensió exactament declarada, sis perfils parcials i dos resultats NO AVALUABLES. Aquesta distribució descriu aptitud de les dades, no qualitat ecològica del territori.
- Implicació per a la gestió: Llegir cada resultat segons el seu tipus i la seva vigència; cap perfil es pot convertir en una nota global de conservació.
- Indicadors: CORE_01, CORE_02, CORE_03, CORE_04, CORE_05, CORE_06, CORE_07, CORE_08, CORE_09, CORE_10, CORE_11, CORE_12
- Fonts: aca_hydrology, connectivity_infraestructura_verda, copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, fires_burned_areas, gbif_occurrences, habitats_terrestres_v3, hic_v2, icgc_dem_mdt, inaturalist_observations, land_cover_icgc_cobertes_sol, meteocat, osm_public_use, pla_alfa
- Confiança: `baixa`
- Robustesa: `provisional`
- Tipus d'evidència: `observació`
- Limitacions: La confiança varia per RADAR i s’ha de consultar en les vuit dimensions publicades.

### La configuració és forestal i la funció del mosaic depèn de l’objectiu

- Secció: `distribucio_territorial`
- Interpretació: Perfil estructural · bosc 88,4 % · taca màxima 477,4 ha. La cartografia conté 6.994 taques, amb una taca màxima de 477.38 ha i mida efectiva de 102.01 ha. Shannon, vora i nombre de taques es mantenen com a descriptors: no indiquen per si sols fragmentació perjudicial ni mosaic funcional.
- Implicació per a la gestió: Definir per hàbitat o procés quines continuïtats, clarianes i vores s’han de conservar abans d’ordenar actuacions de mosaic.
- Indicadors: CORE_01
- Fonts: land_cover_icgc_cobertes_sol
- Confiança: `mitjana`
- Robustesa: `provisional`
- Tipus d'evidència: `observació + interpretació plausible`
- Limitacions: La mida i la vora de taca depenen de l’escala i de la classificació de la font.; Els ecotons funcionals no es classifiquen sense contrast, objectiu i validació.

### Els HIC impliquen responsabilitat territorial, no estat favorable

- Secció: `valors_ecologics_principals`
- Interpretació: 3.171,0 ha HIC · 58,0 % · 1.229,4 ha prioritaris. Aquestes superfícies i les presències puntuals documenten representació d’hàbitats. No existeixen encara dades locals suficients d’estructura, funcions, pressions i perspectives per classificar-ne l’estat de conservació.
- Implicació per a la gestió: Aplicar no-deteriorament i verificació d’hàbitat abans de qualsevol transformació; no interpretar més hectàrees com a millor estat.
- Indicadors: CORE_02
- Fonts: habitats_terrestres_v3, hic_v2
- Confiança: `mitjana`
- Robustesa: `robusta per responsabilitat; provisional per estat`
- Tipus d'evidència: `observació`
- Limitacions: No avalua estat de conservació.; La presència HIC incrementa responsabilitat i cautela, no qualitat ecològica.

### L’NDVI descriu el 7 de juliol i no l’estat actual de setembre

- Secció: `factors_explicatius`
- Interpretació: NDVI 0,616 · 07/07/2026. L’escena tenia 99.95 % de cobertura vàlida, amb P10 0.341 i P90 0.757. El valor és coherent amb una activitat verda desigual dins l’àmbit, però sense línia base per coberta i època no permet classificar vigor actual, anomalia fenològica o estat de conservació.
- Implicació per a la gestió: Esperar una nova escena QA-vàlida i comparar-la amb la mateixa època i coberta abans d’interpretar canvi o estrès.
- Indicadors: CORE_03
- Fonts: copernicus_sentinel_ndvi
- Confiança: `mitjana`
- Robustesa: `robusta per l’escena; no vigent per avui`
- Tipus d'evidència: `observació datada`
- Limitacions: Descriu verdor espectral el 07/07/2026, no l’estat actual.; No és biodiversitat, biomassa, humitat ni estat de conservació.

### Refugis i vulnerabilitat climàtica requereixen dues lectures diferents

- Secció: `vulnerabilitats`
- Interpretació: Estructural parcial · senyal satel·lital 42,3 %. El 42,3 % és la proporció alta o molt alta dins el denominador vegetat amb LST, NDMI i NDVI vàlids; combina un compost tèrmic 2025–2026 amb una escena del 07/07/2026. CORE_05 retorna NO AVALUABLE perquè només hi ha context parcial d’exposició i falten sensibilitat i capacitat adaptativa definides per receptor.
- Implicació per a la gestió: Usar el mapa de refugi per seleccionar candidats a sensors o camp, i no per declarar refugis permanents o vulnerabilitat territorial.
- Indicadors: CORE_04, CORE_05
- Fonts: copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, icgc_dem_mdt, land_cover_icgc_cobertes_sol, meteocat
- Confiança: `baixa`
- Robustesa: `provisional`
- Tipus d'evidència: `interpretació plausible`
- Limitacions: El senyal no és una observació d’avui ni una normal climàtica.; Aigua i fonts es dibuixen com a context i no entren en la fórmula satel·lital.; Exposició alta no equival a vulnerabilitat alta.; Falten normals, extrems i resposta ecològica per receptor.

### La informació biològica està distribuïda de manera desigual

- Secció: `biodiversitat`
- Interpretació: 3.680 registres · 66/84 cel·les amb dades. La consulta GBIF es va aturar al sostre de seguretat de 10.000 sobre 31.169 coincidències, i 18 de 84 cel·les d’1 km no tenen cap registre públic. Això identifica buits de coneixement i biaix d’esforç; no permet ordenar biodiversitat real ni interpretar absències.
- Implicació per a la gestió: Prioritzar prospecció a les cel·les amb poc coneixement que coincideixen amb HIC o connectors, amb un protocol comparable per grup i estació.
- Indicadors: CORE_06
- Fonts: gbif_occurrences, inaturalist_observations
- Confiança: `baixa`
- Robustesa: `provisional`
- Tipus d'evidència: `observació`
- Limitacions: Pocs registres no signifiquen baixa biodiversitat.; La consulta GBIF arriba al sostre de seguretat de 10.000 registres.

### Accessibilitat i continuïtat estructural no demostren pressió ni moviment

- Secció: `connectivitat_i_us`
- Interpretació: 124,8 km · 2,28 km/km² · 18 punts; 1.198,6 ha en connectors · funcionalitat NO AVALUABLE. La xarxa OSM descriu potencial d’accés i els connectors descriuen continuïtat general. Sense freqüentació i impacte no hi ha pressió real; sense receptor, resistències i validació no hi ha connectivitat funcional.
- Implicació per a la gestió: Mesurar ús als trams que coincideixen amb valors sensibles i validar passos o barreres per receptors concrets abans de regular o restaurar corredors.
- Indicadors: CORE_07, CORE_08
- Fonts: connectivity_infraestructura_verda, land_cover_icgc_cobertes_sol, osm_public_use
- Confiança: `mitjana`
- Robustesa: `provisional`
- Tipus d'evidència: `observació + hipòtesi`
- Limitacions: OSM no mesura freqüentació, comportament ni impacte.; Més accessibilitat també pot facilitar seguiment i resposta de gestió.; Continuïtat estructural no garanteix moviment o flux genètic.; Les vies OSM no reben un signe fix de barrera.

### La xarxa hídrica és un inventari, no una lectura de disponibilitat actual

- Secció: `aigua`
- Interpretació: 11,8 km de xarxa · 12 fonts cartografiades. Els elements localitzen on comprovar aigua, ribera i possible funció de refugi, però no informen de cabal, permanència, qualitat o ús per fauna. La seva absència a la capa tampoc prova absència al terreny.
- Implicació per a la gestió: Verificar les dotze fonts i trams seleccionats en període sec, documentant permanència, qualitat, ribera, pressions i sensibilitat.
- Indicadors: CORE_10, CORE_04
- Fonts: aca_hydrology, copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, icgc_dem_mdt, land_cover_icgc_cobertes_sol
- Confiança: `mitjana`
- Robustesa: `provisional`
- Tipus d'evidència: `observació`
- Limitacions: No informa de cabal, permanència, qualitat o estat de ribera.; Zero basses o zones humides a la font retallada no prova absència al terreny.

### El foc es presenta com un perfil de propagació, sensibilitat, recuperació i operativa

- Secció: `foc`
- Interpretació: Propagació actual alt · recuperació NO AVALUABLE. El perill EcoRadar actual conserva la seva escala 0–100 perquè és un producte diari específic, i el Pla Alfa continua com a context oficial independent. La sensibilitat ecològica i la recuperació postincendi no són avaluables amb perímetres, camins i aigua cartografiada.
- Implicació per a la gestió: Vigilar vent, humitat, pluja i potencial ForestDrought; abans de tractaments, verificar combustible, hàbitats i sòl als sectors candidats.
- Indicadors: CORE_09
- Fonts: aca_hydrology, fires_burned_areas, icgc_dem_mdt, land_cover_icgc_cobertes_sol, meteocat, osm_public_use, pla_alfa
- Confiança: `mitjana`
- Robustesa: `caduca amb la següent instantània diària`
- Tipus d'evidència: `escenari potencial`
- Limitacions: El perill actual no és probabilitat d’ignició ni predicció d’incendi.; Camins, aigua i superfície cremada no sumen ni resten resiliència de manera lineal.

### La síntesi manté prioritats per alternativa i rebutja una única nota global

- Secció: `implicacions_gestio`
- Interpretació: SENSE PRIORITAT ÚNICA · 1 P1, 4 P2 i 1 NO AVALUABLE. La regla preventiva sobre HIC és P1; prospecció, mesura d’ús, verificació hídrica i preparació davant del foc són P2. La restauració generalitzada queda vetada com a NO AVALUABLE perquè CORE_11 no disposa de degradació, referència, objectiu, benefici i viabilitat.
- Implicació per a la gestió: Aplicar la regla P1, programar les verificacions P2 i aprovar unitats/objectius abans d’ordenar alternatives no dominades.
- Indicadors: CORE_11, CORE_12
- Fonts: aca_hydrology, connectivity_infraestructura_verda, copernicus_sentinel_ndmi, copernicus_sentinel_ndvi, detailed_surface_temperature, fires_burned_areas, gbif_occurrences, habitats_terrestres_v3, hic_v2, icgc_dem_mdt, inaturalist_observations, land_cover_icgc_cobertes_sol, meteocat, osm_public_use, pla_alfa
- Confiança: `baixa`
- Robustesa: `robusta en els vetos; provisional en l’ordenació`
- Tipus d'evidència: `síntesi de decisió`
- Limitacions: Responsabilitat HIC, vulnerabilitat o connectivitat no impliquen necessitat de restaurar.; No es delimiten superfícies ni actuacions candidates.; P1/P2 són categories de decisió per fila, no puntuacions ecològiques.; La síntesi s’ha de reexecutar amb cada snapshot i després d’aprovar unitats i objectius.
