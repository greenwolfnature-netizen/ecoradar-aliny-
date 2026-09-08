# Informe operatiu «Perill d’incendi avui»

Revisió del 8 de setembre de 2026. Abast: narrativa i exportació d’aquesta lectura, sense recalcular índexs ni alterar les altres lectures.

## Implementació existent i fitxers responsables

- `vendor/ecoradar-alinya-report-profiles.js`: `buildFactory` deriva `fireCurrent` a `buildFireReport(D, now)`. Consumeix l’objecte actualitzat `D.currentFire`; no conserva una còpia antiga en inicialitzar el visor.
- `vendor/ecoradar-reading-report.js`: renderització específica de set apartats amb les classes visuals existents; exportació PDF amb tipografia, colors i capes visibles preservats. La taula de fonts té menys espai vertical només al PDF.
- `tools/export_ecoradar_alinya_netlify.py`: mateix empaquetat, amb versió nova dels dos scripts. Les còpies de `vendor` del paquet han de coincidir amb les de l’arrel.
- HTML de l’arrel, paquet i versió autònoma: només actualització de la versió dels dos scripts.

L’error de màxim provenia del camp `max_index_0_100`: el motor actual publica `maximum_index_0_100`. Es manté compatibilitat amb el camp anterior; absències, tipus incorrectes i valors fora de 0–100 es mostren com a «No calculable amb les dades disponibles».

## Vigència i criteris de narrativa

No es canvien els pesos ni l’índex guardat. El Pla Alfa es mostra independentment i mai entra en el càlcul ni determina l’escenari narratiu. Cada font conserva la data d’observació; la comprovació i la generació s’identifiquen separadament.

`temporalState` reutilitza els límits de frescor del producte quan existeixen. En absència de llindars específics, meteorologia actual fins a 3 hores, recent fins a 24 hores, després context; una data absent o futura és no verificable. Els components estructurals es distingeixen de les observacions actuals. Una font exclosa pel motor o amb factor de frescor zero sempre és context. NDMI antic no participa en la interpretació hídrica actual. El Pla Alfa reutilitza la seva política publicada; alternativa de presentació: actual fins a 18 hores, context després de 72 hores.

Les regles següents són convencions descriptives explícites, no llindars calibrats de propagació ni un model nou:

- Humitat relativa ≤40%: possible assecament del combustible fi; ≥70%: possible limitació de l’assecament.
- Vent ≤10 km/h i ratxa ≤20 km/h: senyal observat feble. Vent ≥20 km/h o ratxa ≥40 km/h: possible impuls pel vent. En l’interval intermedi no s’assigna un motor dominant. Calen vent, ratxa i humitat actuals per construir l’escenari d’ignició «ara».
- Set dies o més sense precipitació significativa: dèficit recent d’aportació d’aigua. S’usa el llindar de pluja significativa del producte (1 mm/dia si no és explícit). Pluja de 24 hores ≥1 mm: possible humectació, mai garantia de limitació del foc.
- Sectors: tres cel·les amb índex més alt, només de la mateixa comprovació; tres candidates addicionals amb pendent i continuïtat al quartil superior de la malla, ordenades per índex. Són prioritats de comprovació, no probabilitats ni corredors. No s’atribueixen topònims inventats a les cel·les.
- Exposició: interseccions ecològiques existents només si coincideix la data de comprovació. Sense corredor no es delimiten afectacions.

Fonament físic de la interpretació: [NWCG, vent i humitat del combustible](https://www.nwcg.gov/publications/pms425-1/6-general-winds) i [NWCG, entrades d’un model de comportament superficial](https://www.nwcg.gov/publications/pms437/surface-fire/surface-fire-behavior-worksheet). Aquests documents no validen els llindars descriptius anteriors. Fonts locals i traçabilitat: `docs/data_sources/fire/current-wildfire-danger-alinya.md` i metadades de cada lectura. No s’afegeix cap connector.

## Contracte opcional de punt d’ignició

API: `EcoRadarAlinyaReportProfiles.prepareIgnitionScenario(input, now)`.

`input.ignition`: Feature GeoJSON Point WGS84, amb `properties.source` i `properties.observed_at_utc`. Cap punt es crea automàticament. `input.cells`: FeatureCollection de la malla amb `cell_id`, `raw.slope_deg` i `raw.aspect_deg`. Es comprova inclusió en Polygon/MultiPolygon amb forats; una coincidència múltiple o nul·la bloqueja el resultat.

`input.wind`: `speed_kmh`, `from_degrees` (procedència meteorològica), `timestamp_utc`, `source`, `spatial_scope: 'ignition_local'`. Vent d’una estació llunyana no compleix aquest contracte. `fuel`, `barriers` i `exposedElements`: objectes amb `features`, `source`, `data_at_utc`, `verified: true`, `coverage_verified: true`; han de superar el control temporal. El proveïdor ha de preparar i verificar la cobertura espacial d’aquestes capes, el combustible i la humitat.

Estats: `no_ignition`, `invalid_ignition`, `insufficient_data`, `ready_for_validated_model`. Es retorna el context espacial del punt i les dades pendents. Amb totes les entrades, es poden preparar els eixos de màxim pendent ascendent i sotavent, sempre separats. `potentialDirection` i `potentialCorridor` continuen sent `null`: falta un model validat, creuament espacial del recorregut amb capes locals i anàlisi de sensibilitat. Els eixos no són un corredor. L’informe accepta `D.currentFire.ignition` i `D.currentFire.ignitionContext` per a una integració futura; no s’afegeix un selector visual ni un servei de llamps en aquesta revisió.

## Validació

`node --test tests/js/fire-report.test.mjs`

Deu proves: instantània real del 08/09/2026 17:36 UTC, valors absents/invàlids, meteorologia caducada, NDMI antic, independència del Pla Alfa, cel·les i exposició de dates discordants, punts d’ignició incomplets i complets sintètics. Comparació SHA-256 de vuit perfils no modificats amb la versió publicada anterior (sense data de generació).

La fixture conserva les propietats necessàries de les 5.462 cel·les reals i metadades; omet geometries, ràsters i detall no utilitzat. Els punts dels tests d’ignició són explícitament sintètics i no són observacions. Prova al navegador amb el visor actual i exportació html2pdf: tres pàgines A4, totes revisades visualment, sense text tallat ni pàgina final buida. La longitud pot variar segons les dades i el text generat.
