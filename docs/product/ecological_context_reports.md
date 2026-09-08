# Diagnosi contextual global dels informes EcoRadar

Revisió 08/09/2026. Es manté la implementació, el disseny i el càlcul dels indicadors. La revisió afecta el generador d’informes i les metadades analítiques que necessita; no afegeix connectors ni fonts externes.

## Components

- `vendor/ecoradar-alinya-report-profiles.js`: motor compartit, polítiques pròpies de cada indicador, compatibilitat, interpretació de contrastos, escenaris i gestió.
- `vendor/ecoradar-reading-report.js`: set apartats amb el disseny existent. Les limitacions i fonts excloses queden al final. S’elimina la recomanació genèrica afegida a tots els informes. Es conserva la lectura operativa d’incendi i el detall desplegable de biodiversitat.
- `tools/export_ecoradar_alinya_netlify.py`: verifica ràsters i genera metadades i contrastos espacials de la mateixa escena; exporta les còpies habituals. També amplia únicament la tipografia del bloc executiu d’incendi (títol 18 px, etiquetes 14 px, valors 17 px, nota 12 px), sense modificar amplades.

## Interpretació específica

`buildEcologicalContext(D,key,profile,now)` aplica una política de `diagnosticPolicies`: significat del valor disponible, processos, alternatives, trajectòries pròpies i comprovacions de gestió. S’han retirat els escenaris genèrics heretats. Les polítiques cobreixen les 17 lectures actuals i les lectures de connectivitat i aigua. Un augment no es converteix automàticament en millora: tancament de prats, pèrdua de sòl, recuperació hídrica, permeabilitat i esforç de prospecció tenen interpretacions diferents.

Les lectures futures han de registrar una política amb `registerDiagnosticPolicy(key,{peers,diagnose})`. No es permet sobreescriure silenciosament una política existent. Sense política específica, el motor identifica que manca la diagnosi i no omple una plantilla amb el nom de la nova variable. `diagnose` retorna `meaning`, `processes`, `alternatives`, `scenarios` (parelles de títol i text) i `management`.

## Evidència i contrastos reals

`build_ecological_evidence` verifica font, escena, màscara de qualitat, CRS, transformació, dimensions, recompte vàlid, mitjana i mediana (tolerància 0,00051 per arrodoniment). Conserva hashes de fitxer, malla i màscara. Si manca una dependència o comprovació, no inventa compatibilitat.

Per cada ràster espectral vàlid calcula els quartils espacials 25 i 75. Dins els píxels de cada extrem, calcula les medianes de les altres variables de la mateixa escena i màscara. `spatial_contrasts` conserva límits, recomptes, variable contrastada, medianes i mètode `native_same_mask_spatial_quartiles_v1`. No reprojecta ni interpola; una malla o màscara diferent bloqueja el contrast. Un ràster constant no produeix falsos sectors extrems. Els quantils són contrastos dins l’escena, no categories de salut ni anomalies climàtiques.

El motor canvia la interpretació segons el sentit real de la relació: verdor i hidratació concordants o desacoblades, reflectància amb vegetació conservada o amb menor senyal vegetal. Les medianes territorials es distingeixen dels contrastos per píxels. Els inventaris estructurals aporten context separat; la síntesi existent d’interseccions HIC prioritari–connector i buits de coneixement informa activament els informes d’hàbitats, biodiversitat, connectivitat i gestió, amb la data de generació identificada com a tal.

Exemple verificat, exclusivament de l’escena 07/07/2026: albedo ≤0,145, NDVI mediana 0,725 i NDMI 0,224; albedo ≥0,208, NDVI 0,404 i NDMI −0,012. És coherent amb menys verdor i senyal hídric a les superfícies més reflectants; no discrimina roca natural, sòl descobert i vegetació seca. No descriu l’estat actual de setembre.

## Compatibilitat i vigència

`compatibleEvidence` requereix valor, font, qualitat verificada, període vàlid no futur, cobertura, suport, malla, màscara i resolució coincidents. S’accepta resolució mètrica o nativa amb unitats i CRS. Una agregació temporal o harmonització s’ha de calcular i documentar abans; no s’infereix perquè les dades pertanyin al mateix municipi.

El mapa espectral manté el valor i data de la seva escena, sense substituir-los per una lectura diària més nova. Una distribució antiga no es combina amb una observació nova. La composició tèrmica es presenta com a composició, sense assignar-li la data d’una escena individual ni convertir-la en temperatura de l’aire. Les observacions de més de 30 dies s’etiqueten com a context històric; les més recents també queden vinculades a la data, sense vigència universal. Els controls de frescor específics de foc es conserven.

Es diferencien observació, interpretació plausible i escenari condicional. No es calculen probabilitats, velocitats de propagació, severitat, abundància, mortalitat ni funcionalitat biològica a partir d’una associació. Les fonts incompatibles i els controls pendents figuren al final de l’informe.

## Verificació

- `node --test tests/js/ecological-context.test.mjs tests/js/fire-report.test.mjs`: 27 proves; totes les lectures, diagnosi dependent de dades, dades absents, canvi de data/malla/màscara, polítiques futures, coincidències estructurals i regressions d’incendi.
- `python tests/test_ecological_evidence.py`: 7 proves amb ràsters sintètics; resums, qualitat, fitxers absents, parelles reals de píxels, ràsters constants i malles diferents. Les fixtures no entren al visor.
- Contrast calculat sobre els ràsters reals d’Alinyà; generació de l’informe des del visor i revisió de desbordaments i mides CSS.

Referències de base: [USGS NDVI](https://www.usgs.gov/landsat-missions/landsat-normalized-difference-vegetation-index), [USGS NDMI](https://www.usgs.gov/landsat-missions/normalized-difference-moisture-index), [USGS fenologia](https://www.usgs.gov/special-topics/remote-sensing-phenology/science/ndvi-foundation-remote-sensing-phenology). Les conseqüències ecològiques es formulen com a interpretacions condicionals, no com a observacions locals ni llindars calibrats.
