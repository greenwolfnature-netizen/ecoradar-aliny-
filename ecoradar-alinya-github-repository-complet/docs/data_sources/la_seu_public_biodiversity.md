# Registres públics de biodiversitat · la Seu d'Urgell

## Àmbit i criteri

La consulta utilitza exactament el rectangle operatiu ampliat de l'EcoRadar
urbà (`1.44, 42.3445, 1.479, 42.3647`, EPSG:4326). No és un límit
administratiu. Els resultats es mostren separats per font i no se sumen perquè
un mateix esdeveniment biològic pot estar representat en més d'un portal.

## Fonts verificades

| Font | Organització | Servei | Actualització | Llicència | Estat |
|---|---|---|---|---|---|
| GBIF Occurrence API | Global Biodiversity Information Facility | REST JSON | contínua segons publicadors | llicència per registre i atribució GBIF/dataset | `verified` |
| iNaturalist Observations API | iNaturalist Network | REST JSON | contínua | llicència per registre i termes de l'API | `verified` |
| SACC | Societat Catalana d'Herpetologia / Observatori del Patrimoni Natural | programa de seguiment i portal públic | campanyes de seguiment; des de 2023 | sense llicència oberta identificada per a registres locals | `pending_verification` per a dades locals de la Seu |

## Procés

`ecoradar/connectors/connector_public_biodiversity.py` descarrega i normalitza
els registres públics de GBIF i iNaturalist dins el rectangle. El connector no
fa cap interpretació ecològica. `tools/collect_la_seu_public_biodiversity.py`
calcula únicament resums de traçabilitat per font: registres recollits, taxons
identificables dins cada font, interval de dates, tipus de registre i si s'ha
assolit el límit de descàrrega. També consulta els recomptes oficials filtrats
per `Animalia`: `kingdomKey=1` a GBIF i `taxon_id=1` a iNaturalist.

L'EcoRadar no publica les coordenades exactes dels registres. Per representar
les observacions al mapa, les agrupa en cel·les de `0,001°`, aproximadament
`80 × 111 m` a la latitud de la Seu. Els totals de GBIF i iNaturalist es
mantenen separats i no es dedupliquen entre portals.

## Selector d'espècies i funció ecològica urbana

El visor crea un catàleg seleccionable només amb registres d'`Animalia`
identificats per la font amb rang taxonòmic d'espècie i amb almenys una
observació georeferenciada cartografiable. La unió entre GBIF i iNaturalist es
fa pel nom científic canònic exacte, però els recomptes continuen separats per
portal perquè no s'ha fet una deduplicació d'esdeveniments. Les espècies sense
cap cel·la d'observació queden excloses del desplegable.

El rectangle informatiu mostra:

- nom científic i, quan la font el proporciona de manera inequívoca, nom comú
  sense traduir;
- grup taxonòmic;
- registres de GBIF i observacions d'iNaturalist per separat;
- data de l'observació pública més recent;
- cel·les d'observació agregades representades al mapa, diferenciades per
  GBIF, iNaturalist o presència de registres als dos portals;
- una funció ecològica urbana potencial atribuïda al grup taxonòmic.

La funció descrita és context interpretatiu general —pol·linització,
descomposició, control biològic, dispersió, xarxa tròfica o funcionament dels
cursos d'aigua, segons el grup— i no una mesura del servei prestat per
l'espècie seleccionada. El visor ho adverteix expressament: no és un benefici
mesurat, una abundància ni una avaluació funcional específica a la Seu
d'Urgell. Quan el grup disponible no permet una atribució prudent, no
s'assigna cap servei concret.

## Animalia

`Animalia` és el regne taxonòmic que agrupa els animals. En la comprovació del
26/07/2026 consten, dins el rectangle operatiu:

- `5.556` registres atribuïts a Animalia a GBIF.
- `265` observacions atribuïdes a Animalia a iNaturalist.

Són recomptes de registres publicats, no nombres d'individus, abundàncies ni
una estimació de tota la diversitat animal. Els dos totals no se sumen perquè
una mateixa observació pot haver estat compartida als dos portals. El visor
explica aquesta definició en passar el cursor o donar focus al terme
`Animalia`.

## SACC

S'han verificat el programa oficial de Seguiment d'Amfibis Comuns de Catalunya,
la coordinació de la Societat Catalana d'Herpetologia i la seva incorporació a
l'Observatori del Patrimoni Natural. El projecte s'inicia el 2023 i
s'implementa des de 2024. No s'ha pogut verificar cap punt SACC públic ni cap
resultat quantitatiu dins l'àmbit EcoRadar de la Seu. Per això no es mostra cap
total, abundància, llista d'espècies o tendència local inventada. La manca
d'aquesta exportació no significa zero observacions d'amfibis.

## Limitacions

- Són registres oportunistes o de ciència ciutadana, no un cens complet.
- El nombre de registres no equival a abundància, ocupació ni riquesa total.
- La cobertura depèn de l'esforç d'observació, la visibilitat de les dades, les
  revisions taxonòmiques i la precisió espacial.
- Els punts del mapa són centres de cel·les agregades d'aproximadament 100 m,
  no localitzacions exactes.
- Els registres antics no confirmen presència actual.
- Les tres fonts no es poden sumar com si fossin observacions úniques.
- La funció ecològica potencial del grup no demostra que cada espècie
  seleccionada presti aquell benefici dins la ciutat.
