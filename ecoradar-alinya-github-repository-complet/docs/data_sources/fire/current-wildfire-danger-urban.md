# EcoRadar Urbà — fonts del “Perill d’incendi actual”

Estat de la porta de fonts: `verified`

Data de verificació: 2026-07-24

## Abast

La lectura és un índex EcoRadar derivat de 0 a 100. No és una alerta oficial, no substitueix el Pla Alfa ni el mapa diari oficial i no informa d'incendis actius. IncendisCat no és font de cap variable.

## Matriu de fonts

| Variable | Font oficial | Resolució / representativitat | Actualització | Estat |
| --- | --- | --- | --- | --- |
| Perill estructural | Generalitat, Mapa bàsic de perill d'incendi forestal 2024 | 100 m, EPSG:25831 | producte versionat | `verified` |
| NDMI / sequedat | Sentinel-2 L2A, Copernicus Data Space Ecosystem | B08 10 m i B11/SCL 20 m; sortida reprojectada | segons adquisició vàlida | `verified` per a l'escena local existent; l'actualització API requereix credencials |
| Temperatura superficial | USGS Landsat C2 L2 ST (30 m) o NASA/JPL ECOSTRESS L2T LST V3 (70 m), triant l'última capa local QA-vàlida | 30–70 m segons font seleccionada | segons adquisició, autenticació i QA | Landsat `verified`; ECOSTRESS `requires_credentials` fins a descàrrega QA-vàlida |
| Coberta i continuïtat vegetal | Copernicus CLMS HRL Vegetation 2023 | 10 m, EPSG:3035 | segons versió del producte | `verified` |
| Sequera forestal i potencial de foc | CREAF/EMF, ForestDrought daily modelled forests | graella forestal modelitzada de 500 × 500 m, EPSG:25830 | comprovació diària; la publicació pot tenir retard | `verified` |
| Pendent i orientació | ICGC LiDAR Territorial v3.1 | MDT derivat a 2 m, EPSG:25831 | fixa fins a nova versió LiDAR | `verified` |
| Vent i humitat relativa | Meteocat XEMA, conjunt `nzvn-apee` | observació puntual semihorària; estació CD per a la Seu i Y4 per a Alinyà | 30 minuts | `verified` |

## Criteris d'ús

- La graella comuna de càlcul és la del perill estructural oficial, de 100 m. Les capes de resolució més fina s'agreguen dins de cada cel·la; la LST de 30 m es reprojecta amb interpolació bilineal i les cobertes categòriques amb veí més proper.
- L'NDMI i la LST es normalitzen amb percentils robustos reals de la capa vàlida dins l'àmbit (P5–P95). La sequedat inverteix l'NDMI. Aquest procediment expressa contrast relatiu dins l'àmbit i no una probabilitat física d'ignició.
- La continuïtat vegetal és el percentatge real de cel·les vegetades en una finestra de 3 × 3 cel·les de 100 m, combinat amb la cobertura de la cel·la. No equival a càrrega de combustible mesurada al camp.
- ForestDrought aporta DDS, LFMC, DFMC, SFP, CFP i REW modelitzats. El component EcoRadar utilitza `100 × max(SFP, CFP) / 9`; DDS, LFMC, DFMC i REW es conserven com a diagnòstic i no es tornen a ponderar per evitar duplicar informació del mateix model.
- Cada punt ForestDrought representa una cel·la forestal de 500 × 500 m. EcoRadar només assigna el valor a l'empremta d'aquesta cel·la, sense interpolar-lo a carrers ni a zones no forestals. Quan no hi ha cel·la CREAF, el component queda absent i es renormalitzen els pesos disponibles.
- Pendent i orientació provenen del MDT LiDAR. La solana es calcula com una exposició sud contínua; l'obaga redueix el component d'orientació.
- Vent i humitat són mesures puntuals reals. S'apliquen a l'àmbit i redueixen la confiança espacial perquè no constitueixen un camp meteorològic modelitzat carrer a carrer.
- Les observacions XEMA sense codi de validació es mostren com a provisionals. No s'oculta aquesta limitació.
- Si una font dinàmica falla, es conserva l'últim resultat vàlid amb la seva data real. Les variables absents no es converteixen en zero: els pesos disponibles es renormalitzen i la lectura queda marcada com a incompleta.

## Fórmula executable

Per a cada cel·la EcoRadar de 100 m:

`I = sum(w_i × x_i) / sum(w_i disponibles)`

on tots els components `x_i` s'expressen de 0 a 100 i els pesos són:

| Component | Pes |
| --- | ---: |
| Potencial de foc ForestDrought CREAF, `100 × max(SFP, CFP) / 9` | 20 % |
| Perill estructural Generalitat | 20 % |
| Sequedat relativa NDMI | 15 % |
| Temperatura superficial QA-vàlida més recent entre Landsat i ECOSTRESS | 10 % |
| Continuïtat vegetal | 10 % |
| Vent XEMA | 10 % |
| Humitat relativa inversa XEMA | 10 % |
| Pendent | 3 % |
| Orientació | 2 % |

La fórmula és un índex relatiu EcoRadar, no una probabilitat d'ignició. El pes de ForestDrought no converteix el producte CREAF en alerta oficial i no substitueix el Pla Alfa.

## Traçabilitat

- Perill estructural: `docs/data_sources/fire/basic-wildfire-danger-2024.md`.
- Meteorologia XEMA: `docs/data_sources/official_sources.md` i `docs/data_sources/sources_inventory.yml`.
- Sequera forestal i potencial modelitzat: [CREAF ForestDrought](https://laboratoriforestal.creaf.cat/forestdrought_app/) i [repositori GeoPackage EMF](https://data-emf.creaf.cat/public/gpkg/daily_modelled_forests/).
- Metadades urbanes: `projectes/LaSeu_Urba/metadata/data_sources_matrix.md`.
