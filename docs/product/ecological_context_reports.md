# Capa comuna de diagnosi ecològica dels informes

Revisió del 08/09/2026. S’amplia el generador existent d’Alinyà; no s’alteren índexs, capes cartogràfiques, fórmules ni fonts externes. No s’afegeix cap connector.

## Arquitectura

`vendor/ecoradar-alinya-report-profiles.js` exposa `buildEcologicalContext(D, key, profile, now)` i `compatibleEvidence(a, b, now)`. `buildFactory` incorpora `ecologicalContext` a les 17 lectures actuals, inclosos foc i biodiversitat. El catàleg té significat, processos, lectures complementàries, combinacions condicionals, tres trajectòries i gestió. Vigor i humitat tenen regles específiques més detallades. Les altres lectures disposen d’interpretació pròpia de la seva funció ecològica; els escenaris no equivalen automàticament augment de valor a millora.

`vendor/ecoradar-reading-report.js` presenta set apartats amb les classes visuals existents. Manté l’informe operatiu especialitzat de foc, enriquit amb context ecològic; conserva íntegra la diagnosi específica de biodiversitat en un desplegable de l’informe. El desplegable pot obrir-se abans de desar el PDF per incloure’n el contingut. La resta utilitza la capa comuna. Els camps tècnics previs es conserven per compatibilitat, però la nova presentació no reprodueix relacions quantitatives antigues sense comprovació.

`tools/export_ecoradar_alinya_netlify.py::build_ecological_evidence` verifica els ràsters espectrals locals en cada empaquetat. Reutilitza l’escena i la màscara de qualitat documentades a `teledeteccio_sentinel2.json`; comprova CRS, resolució nativa, transformació, dimensions, màscara de píxels vàlids, recompte, mitjana i mediana (tolerància de 0,00051 per l’arrodoniment publicat). Calcula hashes de malla, màscara i fitxer. No reprojecta ni interpola dades. Si falten dependències, fitxers o controls, no emet evidència verificada; la lectura continua disponible com a contrast pendent.

## Contracte de compatibilitat

Les dades a `D.ecologicalEvidence[key]` necessiten valor, font, `quality_verified`, data o període vàlids, `coverage_verified`, `support_id`, `grid_id`, `mask_id` i resolució. S’admet `resolution_m` o `resolution: [x,y]`, `resolution_unit` i `crs` per malles natives. Les unitats angulars no es transformen fictíciament en metres.

Per presentar una associació quantitativa han de coincidir el període, suport, malla, màscara i resolució. Una agregació o harmonització legítima l’ha de produir i documentar el motor de dades; el generador no la infereix d’un nom de municipi, una data semblant o una resolució nominal. Una capa estructural d’un altre any es pot descriure com a condicionant plausible, però no supera automàticament el control d’un creuament actual. L’evidència verificada continua essent associació, mai causalitat.

La regla de presentació de més de 30 dies identifica context històric. No és una caducitat física universal ni altera els controls de frescor del motor d’incendis. Les observacions més recents també es mostren amb data, sense certificar-ne vigència per qualsevol procés. Es rebutgen períodes absents, invertits o futurs. La meteorologia d’estació no s’atribueix a una malla satel·litària. La lectura principal espectral usa l’escena representada al mapa i evita barrejar-la amb una actualització diària posterior.

La comprovació real de NDVI i NDMI mostra la mateixa escena del 07/07/2026, CRS EPSG:4326, malla i màscara amb 377.656 píxels vàlids. Per això se’n permet una associació històrica. Les lectures meteorològiques de setembre no són simultànies i no es presenten com una explicació demostrada d’aquella escena.

## Abast científic

NDVI: verdor, activitat vegetal relativa, protecció potencial del sòl, estructura d’hàbitat, recursos tròfics i regeneració com a processos a contrastar. Biomassa i combustible no es calculen a partir d’NDVI sense calibratge.

NDMI: senyal de contingut hídric vegetal, interpretat amb fenologia, coberta, pluja i calor. No s’equipara a humitat de sòl, combustible fi mort, estrès fisiològic demostrat ni probabilitat d’incendi.

Referències oficials: [USGS NDVI](https://www.usgs.gov/landsat-missions/landsat-normalized-difference-vegetation-index), [USGS NDMI](https://www.usgs.gov/landsat-missions/normalized-difference-moisture-index), [USGS fenologia](https://www.usgs.gov/special-topics/remote-sensing-phenology/science/ndvi-foundation-remote-sensing-phenology). Aquestes fonts fonamenten la interpretació dels índexs; les conseqüències ecològiques es formulen com a hipòtesis condicionals, no com a observacions locals ni resultats calibrats.

## Proves i manteniment

- `node --test tests/js/ecological-context.test.mjs tests/js/fire-report.test.mjs`
- `python tests/test_ecological_evidence.py` amb numpy i rasterio del projecte.

Cobertura: totes les lectures actuals; metadades absents; data, resolució, suport i màscara discordants; qualitat, valors i dates invàlids; evidència històrica; fidelitat a l’escena del mapa; preservació del detall de biodiversitat i de l’informe de foc. Proves de ràsters sintètics per recompte, resums, qualitat i fitxers absents. Cap fixture sintètica entra al visor.

Les còpies de vendor del paquet han de coincidir amb les de l’arrel. L’HTML de l’arrel, paquet i versió autònoma conté les metadades verificades de l’empaquetat. Les execucions futures les regeneren a partir dels ràsters presents. Afegir una lectura requereix un perfil i metadades verificables; la manca de perfil produeix una sortida explícita sense inventar interpretacions.
