# EcoRadar — perill estructural d'incendi forestal 2024

Estat: `verified`

Data de verificació: 2026-07-13

## Decisió d'ús

EcoRadar pot incorporar aquesta font com a capa de **perill estructural d'incendi forestal**. No és una capa d'incendis actius, no és el mapa diari de perill i no substitueix els avisos operatius de la Generalitat.

La integració d'aquesta capa no resol ni evita la porta de dades d'IncendisCat. La font oficial exacta que alimenta IncendisCat continua sense estar demostrada i no s'utilitza en aquest projecte.

## Metadades obligatòries

- **Nom de la font:** Mapa bàsic de perill d'incendi forestal 2024.
- **Organisme responsable:** Generalitat de Catalunya. Departament d'Agricultura, Ramaderia, Pesca i Alimentació.
- **Pàgina oficial:** <https://agricultura.gencat.cat/ca/serveis/cartografia-sig/bases-cartografiques/boscos/mapa-perill-incendi-forestal/mapa-perill-basic-incendi-forestal-2024>
- **Descàrrega oficial:** <https://gencat.cat/agricultura/sig/bases/PERILLBASICINCENDI.zip>
- **Tipus de servei:** descàrrega oficial automatitzable per HTTPS.
- **Format:** ZIP amb GeoTIFF, TFW, piràmides, taula de valors i metadades auxiliars.
- **Sistema de referència:** ETRS89 / UTM zona 31N, EPSG:25831.
- **Resolució espacial:** 100 × 100 m.
- **Variable:** nivell relatiu de perill estructural d'incendi forestal, valors enters d'1 a 10; NoData 15.
- **Àmbit temporal:** versió 2024; darrera actualització oficial indicada: gener de 2024.
- **Freqüència d'actualització:** producte versionat, sense calendari fix declarat.
- **Llicència:** Llicència oberta d'ús d'informació - Catalunya; cal citar la Generalitat, el departament responsable i la darrera actualització, i no desnaturalitzar el sentit de la informació.
- **Exemple de connexió:** `GET https://gencat.cat/agricultura/sig/bases/PERILLBASICINCENDI.zip`.
- **Credencials:** no requerides.
- **Estat del connector/font:** `verified` per a descàrrega directa i tractament local.

## Metodologia oficial declarada

El producte avalua el perill estructural i prioritza la intensitat potencial davant la freqüència històrica. La Generalitat documenta una suma ponderada de:

- vegetació i càrrega forestal, inclosa sequera projectada 2020–2050: 0,6;
- meteorologia desfavorable: 0,2;
- densitat d'ignicions 2000–2021: 0,1;
- continuïtat global, incloent coberta forestal i rugositat: 0,1.

## Limitacions d'interpretació

- L'escala 1–10 és **relativa**, no una probabilitat d'incendi ni una predicció de comportament del foc.
- La capa no incorpora l'estat meteorològic del dia i no serveix per decidir activitats sotmeses al mapa diari o al Pla Alfa.
- No representa vulnerabilitat de persones o edificis, exposició, evacuació ni risc sanitari.
- La font oficial adverteix que incendis recents respecte del mapa de cobertes de 2018 poden aparèixer inicialment amb càrrega cremable zero; cal fer-ne un ús crític.
- Els valors derivats d'un retall EcoRadar han d'indicar el nombre de cel·les forestals vàlides i no s'han d'extrapolar a les zones urbanes sense valor.

## Verificació tècnica del fitxer

- Fitxer principal: `PERILLBASICINCENDI.tif`.
- Dimensions: 2.672 × 2.592 cel·les.
- Extensió EPSG:25831: `260160, 4488800, 527360, 4748000`.
- Tipus: `uint8` temàtic.
- Resolució confirmada: 100 m.
- Valors confirmats: 1–10.
- NoData confirmat: 15.

