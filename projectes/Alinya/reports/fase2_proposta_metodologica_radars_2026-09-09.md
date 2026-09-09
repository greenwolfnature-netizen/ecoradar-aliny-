# FASE 2 · Proposta metodològica dels 12 RADAR EcoRadar

**Data:** 9 de setembre de 2026  
**Estat:** proposta per revisar; no implementada  
**Abast:** `CORE_01–CORE_12`  
**Canvis aplicats al codi, dades, valors o visor:** cap

## 1. Punt de partida verificat

La proposta parteix de les fórmules executades per `ecoradar/indicators/engine.py`, dels resultats de `projectes/Alinya/indicators/ecoradar_core_indicators.json`, del registre de fonts de la fase 1 i de les incidències H08, H09 i M01–M05 de l'auditoria del 8 de setembre.

La revisió confirma quatre problemes transversals:

1. Els llindars actuals (`18 %`, `25 %`, `35°`, `45/50` hàbitats, `600` espècies, etc.) no tenen un referent ecològic local, una anàlisi de sensibilitat ni validació externa. Per tant, no justifiquen categories universals de 0–100.
2. La mitjana aritmètica permet compensar dimensions que no són commensurables. Per exemple, més accessibilitat pot elevar la suposada resiliència al foc i una puntuació alta de connectivitat pot elevar el suposat potencial de restauració.
3. Diversos CORE mesuren disponibilitat cartogràfica o responsabilitat territorial, però els seus noms suggereixen estat, qualitat o funcionament ecològic.
4. `COMPLET/PARCIAL` i `ALTA/MITJANA/BAIXA` barregen existència de fitxers amb aptitud ecològica de les dades.

La conclusió metodològica és conservar els codis per mantenir compatibilitat, però no forçar que tots siguin puntuacions. La versió revisada ha de distingir quatre tipus de resultat:

- **lectura directa:** valor en la seva escala i unitat pròpies;
- **perfil descriptiu:** diverses mètriques que no s'agreguen perquè tenen significats diferents;
- **classificació ecològica:** només quan existeixen referències, llindars i validació adequats a l'hàbitat, l'època i l'escala;
- **síntesi de decisió:** comparació multicriteri d'alternatives i sectors, amb vetos i incertesa explícits.

## 2. Proposta individual

La columna «signe» usa `+` quan una variable incrementa la dimensió exactament mesurada, `−` quan la redueix, `±` quan l'efecte depèn del context i `0` quan només és context. Cap signe implica automàticament «millor» o «pitjor» estat ecològic.

| RADAR actual | problema | nom proposat | què mesura | variables proposades | fórmula/lògica | interpretació | confiança | canvi recomanat |
|---|---|---|---|---|---|---|---|---|
| **CORE_01 · Mosaic del paisatge** | La mitjana actual premia entropia, percentatge d'espais oberts i riquesa d'hàbitats sense mesurar configuració. Una barreja fragmentada pot obtenir una puntuació alta. | **Configuració i mosaic funcional del paisatge** | Composició i disposició espacial de les cobertes en relació amb un objectiu ecològic definit: continuïtat, àrea interior, mida de taca i ecotons funcionals. | ICGC cobertes 2024; hàbitats v3; connectors oficials; DEM quan delimiti barreres. `+`: àrea interior, mida efectiva de taca i continuïtat per a l'hàbitat objectiu. `−`: fragmentació o barreres demostrades. `±`: diversitat, vora i proporció d'oberts. Nombre d'hàbitats `0` aquí, perquè correspon a CORE_02. | **Perfil sense mitjana inicial:** proporcions de coberta + mida/àrea interior de taca + densitat de vora per tipus + agregació/continuïtat. Una categoria només és admissible respecte d'una configuració de referència i una escala/grandària de píxel explícites. Shannon queda com a descriptor composicional, sense signe de qualitat. | No usar «baix/alt» de manera universal. Mostrar «continuïtat alta/baixa», «àrea interior suficient/insuficient» i «mosaic compatible/no compatible amb l'objectiu». Un paisatge homogeni i un de molt fragmentat poden ser desfavorables per motius diferents. | **Mitjana** per a estructura general amb ICGC; **baixa** per a funcionalitat si no hi ha objectiu d'hàbitat, escala i validació; **alta** només amb referència local, sensibilitat a gra i contrast de camp. | **MODIFICAR** |
| **CORE_02 · Valor d'hàbitats** | `n` d'hàbitats, % HIC i % HIC prioritari mesuren representació cartografiada, no estat de conservació. La capa HIC independent i la presència puntual d'hàbitats petits no són equivalents a superfície. | **Responsabilitat territorial per hàbitats d'interès** | Quina part de l'àmbit conté HIC i HIC prioritaris, quins tipus hi són representats i quins elements petits consten com a presència. No mesura condició ecològica. | Hàbitats v3 poligonals i puntuals; HIC independent quan es verifiqui. `+`: ha i % d'HIC augmenten responsabilitat territorial, no qualitat. HIC prioritari: bandera de responsabilitat, no «bonus». Estat, estructura/funcions i perspectives futures: absents fins disposar d'evidència específica. | **Valors directes separats:** ha i % sobre superfície cartografiada vàlida; llista/nombre de tipus; ha i % prioritaris; presències puntuals sense convertir-les en ha. Per parlar d'estat cal un mòdul diferent amb àrea/rang, estructura i funcions, pressions i perspectives. | «Més responsabilitat» significa més obligacions i cautela, no millor conservació. Baix/mitjà/alt només si es compara amb un denominador territorial extern i una regla aprovada; altrament, mostrar valors directes. | **Alta/mitjana** per responsabilitat cartografiada segons vigència, cobertura i coherència HIC; **baixa/no avaluable** per estat de conservació sense camp ni variables de condició. | **RENOMENAR + MODIFICAR** |
| **CORE_03 · Estat de la vegetació** | Abans es confonia lectura directa i puntuació. Una sola mediana NDVI no descriu tendència, fenologia ni estat de conservació. | **Activitat verda observada (NDVI)** | Verdor/activitat fotosintètica espectral de l'escena i la seva distribució territorial en la data observada. | Sentinel-2 L2A, bandes vermella i NIR, `dataMask` i QA/SCL. NDMI, albedo, LST i meteorologia només com a contrast si són temporalment compatibles. `+/-`: desviació respecte de la línia base del mateix hàbitat i època; el valor brut no té signe ecològic universal. | **Mantenir lectura directa:** mediana, P10–P90, superfície vàlida i data. Afegir, quan hi hagi sèrie suficient, anomalia respecte de la fenologia esperada per estrat de coberta; no transformar a 0–100. | Baix/intermedi/alt només respecte del mateix tipus de coberta i moment fenològic. NDVI alt indica més verdor, però no necessàriament més biodiversitat, millor conservació o menys combustible. | Confiança per escena: QA, núvols/ombres, cobertura, resolució, edat i representativitat fenològica. **Alta** per observació espectral QA-vàlida; inferior per inferències ecològiques o escena antiga. | **MANTENIR** la lectura directa; **MODIFICAR** el nom i la interpretació |
| **CORE_04 · Refugis climàtics** | El CORE estructural (% forestal + northness + CORE_10) i el producte satel·lital (LST/NDMI/NDVI) comparteixen nom però mesuren coses diferents. Northness i aigua cartografiada no demostren refugi. | **Potencial estructural de refugi climàtic**; lectura separada: **senyal tèrmic i hídric observat** | El CORE descriu capacitat estructural relativa de moderar calor/sequera. La lectura satel·lital mostra on coincideixen frescor superficial i vegetació humida/vigorosa en una finestra compatible. | Estructural: DEM, ombra/topografia, coberta/capçada, continuïtat i aigua permanent validada. Observat: LST, NDMI i NDVI contemporanis. `+`: frescor persistent, humitat vegetal relativa i ombra/capçada quan són estables. `±`: orientació nord, bosc i proximitat a aigua segons hàbitat, altitud i permanència. | **Dos resultats sense barrejar-los:** perfil estructural estable + mapa d'observació actual. El producte observat pot conservar la lògica relativa LST/NDMI/NDVI només amb finestra temporal comuna, denominador visible i validació; l'aigua continua com a context fins que permanència/proximitat entrin formalment. No fer mitjana amb CORE_10. | Estructural alt = més atributs compatibles amb amortiment, no refugi confirmat. Senyal observat alt = píxels relativament més frescos/humits dins la data i màscara, no garantia de refugi per a totes les espècies. | **Mitjana** per potencial estructural; **baixa** amb dades temporalment incompatibles; **alta** només si el senyal és repetit en episodis càlids/secs i contrastat al camp o amb sensors independents. | **SUBSTITUIR** l'índex únic per dos productes diferenciats |
| **CORE_05 · Vulnerabilitat climàtica** | La mitjana actual de menys bosc, pendent, orientació sud, artificialització i menys CORE_10 no representa de manera defensable exposició, sensibilitat i capacitat adaptativa. | **Perfil d'exposició i vulnerabilitat climàtica ecològica** | Manté separats: perill/exposició climàtica, sensibilitat dels receptors i capacitat d'ajust o persistència. | Exposició: anomalies i extrems de temperatura, sequera, dèficit hídric i precipitació. Sensibilitat: dependència hídrica, resposta NDVI/NDMI per hàbitat, trets/estat quan existeixin. Capacitat: refugis persistents, connectivitat funcional, heterogeneïtat i regeneració demostrada. `±`: bosc, pendent, orientació i aigua segons receptor; no tenen signe universal. | **Perfil de tres eixos, sense mitjana:** exposició × receptor present; sensibilitat; capacitat adaptativa. Les dades actuals poden omplir context i observacions, però sense normals climàtiques, llindars per receptor i resposta validada el resultat és «no calculable» com a vulnerabilitat. No usar puntuacions d'altres CORE com a entrades. | Exposició alta no equival a vulnerabilitat alta. Vulnerabilitat alta requereix sensibilitat alta i capacitat limitada; contradiccions entre eixos s'han de mostrar. «Millorar» depèn de reduir exposició/sensibilitat o augmentar capacitat, no simplement de tenir més bosc o aigua cartografiada. | **Baixa/no avaluable** amb l'entrada actual. Mitjana quan els tres eixos tenen dades compatibles; alta només amb relacions receptor-resposta i escenaris validats. | **SUBSTITUIR** |
| **CORE_06 · Biodiversitat coneguda** | Espècies citades, proporció recent i nombre de grups reflecteixen esforç i accessibilitat. El sostre GBIF i les fonts oportunistes no permeten inferir biodiversitat real ni confiança alta. | **Cobertura del coneixement de biodiversitat** | Quantitat, distribució espacial, actualitat, cobertura taxonòmica i qualitat de la informació disponible. La riquesa observada queda com a dada descriptiva. | GBIF i iNaturalist deduplicats; BDBC i camp quan estiguin disponibles. `+`: quadrícules i grups coberts, mostreig recent, protocols coneguts, QA taxonòmic/espacial. `−`: biaix espacial/taxonòmic, duplicats, coordenades incertes, sostre de consulta. Nombre d'espècies `+` per coneixement observat, `0` per qualitat ecològica. | **Perfil de cobertura**, no mitjana de riquesa: completitud de consulta; ocupació de quadrícules; antiguitat per grup; distribució de l'esforç; proporció amb QA; buits. Un 0–100 només seria admissible com a «completesa del mostreig» amb protocol o llista de referència, mai com a biodiversitat. | Baix/mitjà/alt descriu cobertura del coneixement. Una xifra alta no significa biodiversitat alta; una xifra baixa pot significar poc mostreig. Les absències no són absències ecològiques. | **Mitjana/baixa** amb dades oportunistes encara truncades o esbiaixades; **alta** només per grups i zones amb mostreig complet, comparable i validat. | **RENOMENAR + SUBSTITUIR** la puntuació |
| **CORE_07 · Pressió humana i ús públic** | OSM mesura elements cartografiats, no afluència, intensitat, estacionalitat, conflictes o impacte. Més camins no té un signe ecològic únic. | **Accessibilitat cartografiada i ús potencial** | Exposició potencial del territori a l'accés i localització d'equipaments/punts d'ús; també informa capacitat d'accés de gestió. | OSM per tipus de via, senders i punts d'ús; distància a accessos; comptadors/incidències/afluència només quan existeixin. `+`: densitat i proximitat incrementen accessibilitat. `0/±`: relació amb pressió ecològica, perquè depèn d'intensitat, comportament, sensibilitat i gestió. | **Mètriques directes separades:** km/km² per classe de via; % d'àrea per franges de distància; punts/1.000 ha. No combinar en 0–100 sense model d'ús. Crear un producte diferent de pressió real quan hi hagi intensitat i impactes. | Baix/intermedi/alt = menor/mitjana/major accessibilitat cartografiada. No significa poca/molta pressió real ni és una escala de qualitat. Una accessibilitat alta pot augmentar risc d'impacte i facilitar resposta/seguiment. | **Mitjana** per accessibilitat OSM segons completitud local; **baixa/no avaluable** per pressió real sense dades d'ús i impacte. | **RENOMENAR + MODIFICAR** |
| **CORE_08 · Connectivitat ecològica** | La fórmula actual usa coberta natural, superfície de connector i invers de CORE_07; declara hàbitats i hidrologia que no entren numèricament. Confón continuïtat general amb permeabilitat per espècies. | **Continuïtat estructural i connectivitat potencial** | Separadament: continuïtat física d'un tipus d'hàbitat i possibilitat potencial de connexió entre taques per a un receptor o gremi definit. | Cobertes/hàbitats com a nodes; mida i qualitat de taca; distàncies; barreres reals per classe; connectors oficials com a context. `+`: àrea de node, enllaços i disponibilitat d'hàbitat. `−`: barreres/resistència validades. `±`: camins, cursos i matriu segons espècie. | **Nivell 1:** perfil estructural amb àrea, distància, àrea interior, continuïtat i límits de l'àmbit. **Nivell 2 opcional:** graf/PC o cost acumulat per hàbitat o gremi, amb distància de dispersió i resistència documentades. No usar CORE_07 agregat ni declarar fonts que no participen. | Estructural alta = taques grans/pròximes i matriu contínua; no garanteix moviment. Connectivitat funcional alta només és interpretable per al receptor i paràmetres declarats. | **Mitjana** per continuïtat estructural; **baixa** per funcionalitat genèrica; **alta** només amb resistències/dispersió i validació adequades al receptor. | **RENOMENAR + MODIFICAR** |
| **CORE_09 · Resiliència davant del foc** | La fórmula premia camins i aigua cartografiada i penalitza linealment bosc/matollar, pendent i ha cremades. No mesura resistència ni recuperació; confon comportament del foc, resposta operativa i trajectòria ecològica. | **Perfil de susceptibilitat i recuperació davant del foc** | Quatre dimensions separades: propagació potencial actual, sensibilitat ecològica, evidència de recuperació postincendi i capacitat operativa. | Propagació: combustible/continuïtat, NDMI, vent, HR, sequera, pendent/orientació. Sensibilitat: hàbitats, sòl/erosió i trets. Recuperació: severitat, NBR/NDVI temporal, regeneració i recurrència. Operativa: accessos i punts d'aigua. Tots els signes són condicionals excepte dins d'un mecanisme i objectiu explícits. | **Perfil sense puntuació única.** El perill diari i Pla Alfa continuen productes independents. Els perímetres històrics descriuen règim/antecedents; no són linealment bons o dolents. Camins i aigua no entren a la resiliència ecològica, sinó al bloc operatiu. Recuperació només es classifica amb canvi postfoc respecte de referència i temps transcorregut. | Susceptibilitat alta = condicions compatibles amb propagació, no ignició probable. Recuperació alta = retorn/persistència de funcions o trajectòria desitjada demostrats, no simplement menys superfície cremada. No hi ha un únic «baix/alt» que resumeixi els quatre eixos. | **Baixa/no avaluable** per resiliència amb les dades actuals; confiança pròpia per cada eix. Pot ser mitjana per propagació potencial si les entrades actuals són compatibles i QA-vàlides. | **SUBSTITUIR** |
| **CORE_10 · Aigua i funcionalitat hídrica** | Longitud de xarxa i nombre de fonts mesuren presència cartografiada. El DEM es declara com a font, però no entra al valor. No hi ha cabal, permanència, qualitat ni estat ecològic. | **Presència hídrica cartografiada** | Quantitat i distribució d'elements hídrics oficialment cartografiats dins l'àmbit. | ACA: km per tipus de curs/drenatge, fonts i masses/punts presents; superfície vàlida. NDWI datat com a lectura separada. `+`: més elements incrementen presència cartografiada. `0/±`: relació amb disponibilitat actual, qualitat, permanència i funció. DEM només entra si deriva conques o connectivitat hidrològica. | **Valors directes:** km i km/100 ha per tipus; nombre/densitat de fonts; ha d'aigua; distribució/distància. No mitjana 0–100. Crear «condició/funcionalitat hídrica» només amb cabal o permanència, qualitat, estat de ribera, connectivitat i validació. | Baixa/intermèdia/alta = densitat/presència cartografiada, si s'explicita el referent. No significa disponibilitat d'aigua avui, bon estat, cabal ni resiliència. | **Mitjana/alta** per inventari cartogràfic segons cobertura; **baixa/no avaluable** per funcionalitat o disponibilitat actual. | **RENOMENAR + MODIFICAR** |
| **CORE_11 · Potencial de restauració** | La mitjana actual pot donar 73,71 sense degradació demostrada, referència, objectiu, viabilitat o benefici. També recombina CORE derivats i crea doble comptatge. | **Cribratge de necessitat i oportunitat de restauració** | Si hi ha evidència suficient: necessitat d'intervenir, trajectòria desitjada, benefici esperat, viabilitat, riscos i alternativa de no-intervenció per sector. | Evidència directa de degradació/pressió; estat i tendència; ecosistema de referència; objectiu; capacitat de regeneració; restriccions; cost/viabilitat; benefici i risc. `+/-` només respecte de l'objectiu aprovat. Valor d'hàbitat alt pot activar protecció/no-intervenció, no restauració automàtica. | **Porta de decisió:** (1) degradació demostrada? (2) referència i objectiu definits? (3) intervenció aporta més que regeneració/no-intervenció? (4) viable i amb risc acceptable? Si falla 1 o 2: «no avaluable» o «diagnosi necessària». Si passa: matriu ordinal de necessitat, benefici, viabilitat i risc, sense mitjana compensatòria. | Categories útils: «protegir/no intervenir», «monitorar», «diagnosi necessària», «restauració candidata» i «restauració prioritària amb evidència». No usar baix/mitjà/alt genèrics. | **No avaluable** avui com a potencial de restauració. La confiança s'assigna per sector i alternativa, amb validació de camp obligatòria abans d'una prioritat d'intervenció. | **SUBSTITUIR**; retirar la puntuació actual |
| **CORE_12 · Prioritat de gestió** | Mitjana igual dels CORE numèrics; exclou lectures directes i permet que una dimensió compensi una altra. El resultat canvia amb les dades disponibles, no amb una funció de decisió validada. | **Síntesi multicriteri per a la gestió** | Per cada sector, quines accions són justificables segons objectiu, obligacions, urgència, benefici, risc, reversibilitat i solidesa de l'evidència. | Resultats no agregats de CORE_01–11 i lectures actuals, però mai les seves puntuacions com a substituts de variables. Criteris/llindars depenen de la decisió. Vetos: obligació legal, dany irreversible, dada essencial absent, incompatibilitat temporal/espacial o risc d'intervenció. | **Sense score global.** Matriu sector × alternativa; regles de veto; dominància/Pareto i, si el gestor aprova preferències, mètode d'ordenació no compensatori. Pesos i compensacions han de ser explícits i sotmesos a sensibilitat. Sortida: acció, motius, conflictes, confiança i vigència. | Mostrar prioritats `P1/P2/P3`, «monitorar» o «no avaluable» només per una decisió concreta. Cap categoria general «baixa/alta» del territori. Un sector de gran valor pot tenir prioritat de protecció i baixa prioritat d'intervenció. | No hi ha confiança única: es mostra el vector de confiança dels criteris decisius i la robustesa de l'alternativa davant escenaris/pesos. | **ELIMINAR** la mitjana i **SUBSTITUIR** el resultat |

### 2.1 Utilitat de gestió i entrades que cal excloure

| CORE | utilitat concreta per al gestor | dades que no han d'entrar en aquest producte |
|---|---|---|
| CORE_01 | Detectar pèrdua d'àrea interior, discontinuïtats, ecotons funcionals i canvis de configuració per tipus de paisatge. | Nombre d'hàbitats com a premi; entropia o densitat de vora amb signe universal; puntuacions CORE_02/08. |
| CORE_02 | Quantificar responsabilitat territorial, cauteles i necessitats de verificació per HIC, inclosos elements puntuals. | Riquesa d'espècies oportunista; superfície HIC tractada com a estat; punts convertits en superfície. |
| CORE_03 | Vigilar anomalies de verdor per data, coberta i sector i decidir on contrastar NDMI, sequera o camp. | Índexs o meteorologia d'altres dates dins el valor NDVI; conversió a percentatge de conservació. |
| CORE_04 | Localitzar estructures capaces d'amortir episodis i comprovar si el senyal tèrmic/hídric actual les confirma. | CORE_10 agregat; aigua no permanent amb signe positiu; LST, NDMI i NDVI temporalment incompatibles en un mateix resultat actual. |
| CORE_05 | Identificar receptors que combinen exposició, sensibilitat i poca capacitat, i quina dimensió cal gestionar o monitorar. | Invers automàtic de bosc/aigua; pendent, orientació o artificialització sense receptor; puntuacions d'altres CORE. |
| CORE_06 | Detectar buits de mostreig per zona, grup i temps abans d'usar registres per decidir. | Nombre brut d'espècies com a qualitat ecològica; absències oportunistes; registres duplicats o fora de QA. |
| CORE_07 | Planificar vigilància, aforaments, regulació i accés operatiu segons la xarxa cartografiada. | Inferència d'afluència o impacte sense intensitat; suma de camins i punts com a «pressió» ecològica. |
| CORE_08 | Identificar taques clau, enllaços i barreres per hàbitat o gremi i contrastar connectors oficials. | Invers de CORE_07; hidrologia/hàbitats declarats només com a context; permeabilitat genèrica per a totes les espècies. |
| CORE_09 | Separar preparació davant propagació, sensibilitat dels valors, recuperació ecològica i capacitat operativa. | Camins i punts d'aigua dins la resiliència ecològica; ha cremades amb signe lineal; perill diari confós amb recuperació. |
| CORE_10 | Inventariar on hi ha xarxa i fonts i on cal mesurar permanència, cabal, qualitat o estat de ribera. | DEM si no deriva cap variable; NDWI d'una data com a permanència; densitat hídrica com a funcionalitat. |
| CORE_11 | Distingir protecció/no-intervenció, diagnosi i restauració candidata a partir de degradació i guany esperat. | Mitjanes de CORE_02/05/07/08/10; valor alt d'hàbitat com a necessitat d'intervenir; restauració sense referència. |
| CORE_12 | Fer explícits els conflictes, vetos i alternatives per sector i documentar per què una acció és prioritària. | Mitjana o suma dels CORE; compensació de restriccions crítiques; prioritat sense objectiu, sector o preferències aprovades. |

## 3. Escala, normalització i precisió

### 3.1 Regla general

No es manté cap escala 0–100 només per coherència visual. Una puntuació sintètica només es pot reintroduir quan hi hagi:

1. constructe ecològic únic i definició operacional;
2. unitat d'anàlisi i escala espacial/temporal fixes;
3. referència, objectiu o llindars justificats per hàbitat o receptor;
4. funció de normalització amb direcció ecològica explícita;
5. política de dades absents sense imputació silenciosa;
6. anàlisi de sensibilitat de llindars, pesos i agregació;
7. validació independent i límits d'ús.

Mentre això no existeixi:

- `CORE_03` conserva NDVI en l'escala `−1…1`, amb tres decimals perquè és una lectura espectral, no un percentatge;
- les superfícies i cobertures es mostren en ha i %, amb denominador i una xifra decimal;
- distàncies i densitats mantenen unitats pròpies;
- els perfils usen classes descriptives vinculades a una pregunta concreta;
- les puntuacions sintètiques eventuals es mostren com a enters, amb interval d'incertesa o classe, no amb dos decimals.

### 3.2 Llindars

Els llindars genèrics actuals `<20/<40/<60/<80` no passen a la metodologia nova. Cada lectura directa manté la seva escala. Cada categoria ecològica ha d'identificar la població de referència, l'època, l'hàbitat, la resolució i l'objectiu de gestió que la fan interpretable.

## 4. Estat i confiança

### 4.1 Separació obligatòria

- **Estat de disponibilitat:** `COMPLET`, `PARCIAL`, `NO AVALUABLE`. Només respon si hi ha totes les entrades essencials per al producte declarat.
- **Confiança d'ús:** `ALTA`, `MITJANA`, `BAIXA`. Respon si el resultat és prou sòlid per a la inferència concreta que es mostra.

Un inventari pot ser `COMPLET` per descriure presència cartografiada i tenir confiança `BAIXA` per inferir funcionalitat ecològica.

### 4.2 Vector de confiança

Cada producte i cada afirmació rellevant han de registrar vuit dimensions com `adequada`, `limitada`, `insuficient` o `no aplicable`, amb evidència i `snapshot_id`:

1. **completesa** de les entrades essencials;
2. **vigència** respecte del procés mesurat;
3. **cobertura** espacial i temporal;
4. **resolució** adequada a la decisió;
5. **QA** de font i processament;
6. **representativitat** del territori, hàbitat, època i receptor;
7. **biaix** de mostreig, detecció o model;
8. **validació** independent o de camp adequada a l'afirmació.

La confiança global no és una mitjana:

- **ALTA:** totes les dimensions crítiques són adequades, cap és insuficient i hi ha validació adequada a l'ús.
- **MITJANA:** totes les dimensions crítiques són com a mínim limitades i els buits no poden invertir la interpretació principal.
- **BAIXA:** alguna dimensió crítica és insuficient, la dada és massa antiga per parlar d'estat actual, la cobertura és inadequada, hi ha biaix fort o manca la validació requerida.
- **NO AVALUABLE:** falta una dependència essencial o les dades són incompatibles amb la pregunta.

La confiança s'ha d'assignar per afirmació. Per exemple, OSM pot tenir confiança mitjana per descriure accessibilitat i confiança baixa per afirmar pressió ecològica real.

## 5. Relacions i control de doble comptatge

| Relació | Regla proposada |
|---|---|
| CORE_01 ↔ CORE_08 | CORE_01 descriu configuració interna del paisatge; CORE_08 avalua enllaços entre nodes i permeabilitat. Poden compartir cartografia base, però no reutilitzar la puntuació de l'altre. |
| CORE_02 ↔ CORE_06 | HIC i hàbitats descriuen responsabilitat territorial; registres d'espècies descriuen coneixement. Riquesa observada no eleva automàticament valor/estat d'hàbitat. |
| CORE_03 ↔ CORE_04/05/09 | NDVI pot aportar evidència datada sobre vegetació, però només entra si la finestra temporal i l'escala són compatibles. No es converteix en qualitat, refugi, vulnerabilitat o resiliència sense mecanisme i referència. |
| CORE_04 ↔ CORE_05 | El refugi és una possible capacitat d'amortiment. CORE_05 no consumeix una puntuació CORE_04: usa els atributs que siguin rellevants per al receptor i evita duplicar-los. |
| CORE_07 ↔ CORE_08/09 | Accessibilitat és context. Una via només és barrera, font de pressió o avantatge operatiu si tipologia i efecte són explícits; no entra amb un signe fix. |
| CORE_10 ↔ CORE_04/05/09/11 | Presència hídrica cartografiada no substitueix permanència, humitat, cabal, qualitat o disponibilitat per extinció. Cada ús ha de citar la variable efectiva, no CORE_10. |
| CORE_11 | Consumeix evidència primària de degradació, referència, benefici i viabilitat; no fa una mitjana de CORE derivats. |
| CORE_12 | Llegeix els resultats i la confiança per comparar alternatives. No retorna com a entrada a cap CORE ni crea un nou valor ecològic. |

## 6. Funcionament proposat de CORE_12

`CORE_12` deixa de ser un RADAR quantitatiu i passa a ser una **síntesi multicriteri per a la decisió**.

### 6.1 Unitat i pregunta de decisió

La síntesi s'executa per sector o unitat de gestió i per una pregunta explícita, per exemple: protegir/no intervenir, monitorar, regular accés, preparar resposta al foc, recuperar funcionalitat hídrica o restaurar. Sense sector i objectiu no hi ha prioritat calculable.

### 6.2 Matriu de decisió

Per a cada combinació `sector × alternativa` es mostren:

- obligacions i valors que actuen com a restricció;
- estat o tendència observats;
- pressions o amenaces demostrades;
- benefici ecològic esperat i mecanisme;
- urgència i risc d'irreversibilitat;
- viabilitat, reversibilitat i risc de l'acció;
- alternativa de no-intervenció o regeneració espontània;
- confiança per criteri, font, data i vigència.

### 6.3 Regles no compensatòries

1. **Vetos:** una obligació legal, un risc greu danyós, una entrada essencial absent o una incompatibilitat de dades impedeixen recomanar l'alternativa, encara que altres criteris siguin favorables.
2. **Dominància:** una alternativa domina una altra si és igual o millor en tots els criteris essencials i millor en almenys un, sense activar cap veto.
3. **Ordenació:** si diverses alternatives no són dominades, es mantenen com a opcions o s'aplica un mètode d'ordenació no compensatori només després que el gestor aprovi preferències, pesos i llindars d'indiferència/veto.
4. **Sensibilitat:** la prioritat només es declara robusta si es manté sota variacions raonables de pesos, llindars i escenaris.

No es permet que una puntuació alta de coneixement, accessibilitat o connectivitat compensi pèrdua d'hàbitat, una obligació legal o manca d'evidència.

### 6.4 Sortida

La targeta de CORE_12 mostra una de les sortides següents, sense valor 0–100:

- `P1 · actuació o protecció prioritària`, amb criteri de veto/urgència i evidència suficient;
- `P2 · planificar i verificar`, quan la direcció és clara però cal completar validació o disseny;
- `P3 · monitorar`, quan no hi ha senyal d'intervenció urgent;
- `NO AVALUABLE`, quan falta evidència essencial;
- `SENSE PRIORITAT ÚNICA`, quan hi ha alternatives no dominades o conflictes que requereixen decisió del gestor.

La vista territorial ha de mostrar, per sector, l'acció candidata, els tres factors decisius, els conflictes, la confiança i la data de caducitat de la síntesi. El gràfic radial pot conservar els perfils independents, però CORE_12 no ha de ser un dotzè eix numèric.

## 7. Decisió recomanada abans d'implementar

La revisió proposa:

- conservar `CORE_03` com a lectura directa;
- mantenir els codis per compatibilitat, però substituir l'escala 0–100 en `CORE_01`, `CORE_02`, `CORE_04`, `CORE_05`, `CORE_06`, `CORE_07`, `CORE_08`, `CORE_09`, `CORE_10`, `CORE_11` i `CORE_12` fins que cada constructe tingui referència i validació pròpies;
- retirar immediatament de la futura metodologia les puntuacions actuals de `CORE_11` i `CORE_12`;
- conservar els valors publicats actuals sense canvis fins que aquesta proposta s'aprovi i es defineixi una migració versionada.

## 8. Fonament metodològic consultat

- [FRAGSTATS — mètriques de composició, configuració, àrea interior, contrast i connectivitat](https://fragstats.org/index.php/running-via-the-graphical-user-interface/step-6-selecting-and-parameterizing-patch-class-and-landscape-metrics).
- [Comissió Europea/JRC — criteris d'estat de conservació d'hàbitats de l'article 17](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC84824/lb-na-26186-en-n%20.pdf): rang, àrea, estructura i funcions, i perspectives futures.
- [USGS — NDVI i fenologia](https://www.usgs.gov/special-topics/remote-sensing-phenology/science/ndvi-foundation-remote-sensing-phenology): lectura de verdor, saturació i necessitat de comparar sèries per època.
- [IPCC AR6 WGII — vulnerabilitat, exposició i capacitat d'adaptació](https://www.ipcc.ch/report/ar6/wg2/chapter/technical-summary/).
- [Saura i Pascual-Hortal (2007) — índex de probabilitat de connectivitat](https://doi.org/10.1016/j.landurbplan.2007.03.005): hàbitat disponible, nodes, graf i probabilitats de dispersió.
- [Boakes et al. (2010) — biaix espacial i temporal en dades d'ocurrència](https://doi.org/10.1371/journal.pbio.1000385).
- [Gann et al. (2019) — estàndards internacionals de restauració ecològica](https://doi.org/10.1111/rec.13035): degradació, ecosistema de referència, objectius i trajectòria de recuperació.
- [Gan et al. (2013) — robustesa de ponderació i agregació en índexs compostos](https://doi.org/10.1016/j.ecolind.2012.12.025).
- [US EPA — qualitat i aptitud de dades ambientals](https://www.epa.gov/n-steps-online/data-considerations): precisió, representativitat, comparabilitat, QA i documentació.

## 9. Evidència local revisada

- `ecoradar/indicators/engine.py`, funcions `_core_01_mosaic` a `_core_12_management_priority`.
- `projectes/Alinya/indicators/ecoradar_core_indicators.json`, instantània actual del motor.
- `projectes/Alinya/reports/indicator_engine_report.md`, càlculs, fonts i limitacions declarats.
- `docs/data-sources-matrix.md`, disponibilitat i limitacions de les fonts.
- `/Users/usuario/Documents/Ecoradar/auditories/auditoria_tecnica_ecologica_ecoradar_alinya_2026-09-08.md`, incidències H08, H09 i M01–M05.
