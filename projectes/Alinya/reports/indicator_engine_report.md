# Indicator Engine Report

Projecte: `Alinya`
Generat: `2026-09-09T11:20:39+00:00`

## Preflight obligatori

| Fitxer | Existeix |
| --- | --- |
| data_availability_report.json | sí |
| connectors_status_report.json | sí |
| indicators_completeness_report.json | sí |

## Resum

| Estat | Nombre |
| --- | ---: |
| COMPLET | 7 |
| PARCIAL | 5 |

## Indicadors EcoRadar Core

| Codi | Indicador | Valor 0-100 | Categoria | Estat | Confiança | Fonts utilitzades | Fonts absents |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| CORE_01 | Mosaic del paisatge | 70.71 | alt | COMPLET | alta | land_cover_icgc_cobertes_sol, habitats_terrestres_v3, connectivity_infraestructura_verda | land_cover_mcsc, sigpac_catalunya, dun_cultius |
| CORE_02 | Valor d'hàbitats | 98.91 | molt alt | COMPLET | alta | habitats_terrestres_v3, hic_v2 | field_biodiversity, field_validation |
| CORE_03 | Estat de la vegetació | NO DISPONIBLE | lectura directa | PARCIAL | mitjana | copernicus_sentinel_ndvi | copernicus_sentinel_ndwi, copernicus_sentinel_nbr, aemet |
| CORE_04 | Refugis climàtics | 59.2 | mitjà | COMPLET | alta | land_cover_icgc_cobertes_sol, icgc_dem_mdt, aca_hydrology | aemet, spei |
| CORE_05 | Vulnerabilitat climàtica | 37.31 | baix | COMPLET | alta | land_cover_icgc_cobertes_sol, icgc_dem_mdt, aca_hydrology | aemet, spei |
| CORE_06 | Biodiversitat coneguda | 83.06 | molt alt | COMPLET | alta | gbif_occurrences, inaturalist_observations | bdbc, field_biodiversity, field_validation |
| CORE_07 | Pressió humana i ús públic | 49.15 | mitjà | COMPLET | alta | osm_public_use | field_biodiversity, strava_heatmap, field_validation |
| CORE_08 | Connectivitat ecològica | 79.5 | alt | COMPLET | alta | connectivity_infraestructura_verda, land_cover_icgc_cobertes_sol, habitats_terrestres_v3, aca_hydrology, osm_public_use | land_cover_mcsc, sigpac_catalunya, dun_cultius, strava_heatmap |
| CORE_09 | Resiliència davant del foc | 44.17 | mitjà | PARCIAL | mitjana | land_cover_icgc_cobertes_sol, icgc_dem_mdt, fires_burned_areas, osm_public_use, aca_hydrology | land_cover_mcsc, sigpac_catalunya, dun_cultius, copernicus_sentinel_nbr, fuel_continuity |
| CORE_10 | Aigua i funcionalitat hídrica | 47.18 | mitjà | PARCIAL | mitjana | aca_hydrology, icgc_dem_mdt | copernicus_sentinel_ndwi, field_biodiversity, spei, field_validation |
| CORE_11 | Potencial de restauració | 73.71 | alt | PARCIAL | mitjana | habitats_terrestres_v3, land_cover_icgc_cobertes_sol, icgc_dem_mdt, aca_hydrology, connectivity_infraestructura_verda, osm_public_use | sigpac_catalunya, dun_cultius, copernicus_sentinel_ndwi, copernicus_sentinel_nbr, field_biodiversity, fuel_continuity, aemet, spei, field_validation |
| CORE_12 | Prioritat de gestió | 64.29 | alt | PARCIAL | mitjana | aca_hydrology, connectivity_infraestructura_verda, fires_burned_areas, gbif_occurrences, habitats_terrestres_v3, hic_v2, icgc_dem_mdt, inaturalist_observations, land_cover_icgc_cobertes_sol, osm_public_use | aemet, bdbc, copernicus_sentinel_nbr, copernicus_sentinel_ndwi, dun_cultius, field_biodiversity, field_validation, fuel_continuity, land_cover_mcsc, sigpac_catalunya, spei, strava_heatmap |

## Limitacions i impacte sobre la diagnosi

### CORE_01 · Mosaic del paisatge
- Càlcul: Combina diversitat de cobertes, proporció forestal, espais oberts/agroforestals, artificialització, riquesa d'hàbitats i presència de connectors oficials.
- Limitacions: SIGPAC, DUN i MCSC no estan disponibles; l'ús agrari fi no entra al càlcul.; La continuïtat forestal es tracta com a proxy de composició, no com a mètrica espacial completa.
- Impacte: El mosaic es pot comparar i usar com a base de context, però les decisions agràries fines necessiten SIGPAC/DUN.

### CORE_02 · Valor d'hàbitats
- Càlcul: Combina nombre d'hàbitats, superfície d'HIC i superfície d'HIC prioritaris dins l'àrea.
- Limitacions: No hi ha validació de camp d'hàbitats.; No hi ha encara llista EcoRadar d'hàbitats sensibles/degradats aplicada com a capa independent.
- Impacte: La lectura d'hàbitats és sòlida a escala cartogràfica, però les actuacions sobre hàbitats concrets necessiten validació de camp.

### CORE_03 · Estat de la vegetació
- Càlcul: Lectura directa de la mediana NDVI de l'escena Sentinel-2 L2A amb màscara SCL; no es transforma en una puntuació sintètica 0–100.
- Limitacions: Una sola escena descriu el vigor espectral de la data, no una tendència ni l'estat de conservació.; NDWI, NBR i context climàtic homogeni continuen absents del RADAR sintètic.
- Impacte: Aporta una observació directa traçable sense alterar la fórmula ni la síntesi CORE_12.

### CORE_04 · Refugis climàtics
- Càlcul: Combina coberta forestal, orientació/northness del DEM i presència relativa de cursos/fonts oficials.
- Limitacions: Falten LST, NDMI i NDVI; no es delimiten refugis tèrmics finals.; El valor és un proxy topogràfic-hídric i de coberta, no un mapa final de refugi climàtic.
- Impacte: Permet detectar potencial preliminar, però no ha de servir encara per delimitar refugis prioritaris sense teledetecció.

### CORE_05 · Vulnerabilitat climàtica
- Càlcul: Combina menor coberta forestal, pendent, exposició sud proxy, artificialització i menor senyal hídric disponible.
- Limitacions: Falten LST, NDMI, sequera SPEI i clima Meteocat/AEMET.; El valor representa vulnerabilitat estructural parcial, no vulnerabilitat climàtica completa.
- Impacte: Pot orientar quines variables cal completar; no ha de convertir-se encara en mapa final de vulnerabilitat.

### CORE_06 · Biodiversitat coneguda
- Càlcul: Combina riquesa d'espècies citades, proporció de registres recents i cobertura de grups taxonòmics.
- Limitacions: Falten BDBC, dades pròpies de camp i llistes creuades d'espècies protegides, amenaçades o invasores.; Les fonts públiques són oportunistes i no equivalen a inventari complet.
- Impacte: Serveix per valorar coneixement disponible, però les decisions sobre espècies sensibles necessiten camp i llistes normatives.

### CORE_07 · Pressió humana i ús públic
- Càlcul: Combina densitat de camins/pistes OSM i concentració de punts d'ús públic cartografiats.
- Limitacions: OSM no mesura intensitat real de visitants.; Strava queda legalment condicionat i no s'ha usat; falten comptadors, gestors i camp.
- Impacte: Indica pressió potencial per accessibilitat, però no afluència real.

### CORE_08 · Connectivitat ecològica
- Càlcul: Combina cobertes naturals, connectors oficials, context d'hàbitats/hidrologia i pressió per accessibilitat.
- Limitacions: No hi ha model de barreres fines ni permeabilitat específica per espècie.; La pressió humana s'integra com a proxy d'infraestructura, no d'intensitat d'ús.
- Impacte: Útil com a lectura estructural preliminar; els corredors prioritaris requereixen model espacial específic.

### CORE_09 · Resiliència davant del foc
- Càlcul: Combina continuïtat forestal/matollar proxy, mosaic obert, pendent, incendis històrics, accessibilitat i punts/cursos d'aigua.
- Limitacions: Falten NDMI, LST i font oficial de combustible/estructura forestal.; No calcula risc d'incendi; només resiliència estructural parcial.
- Impacte: Serveix per identificar quines capes falten abans de parlar de risc o de prioritzar gestió forestal.

### CORE_10 · Aigua i funcionalitat hídrica
- Càlcul: Combina densitat de cursos/drenatge, fonts oficials i disponibilitat de DEM per contextualitzar funcionalitat hídrica.
- Limitacions: Falten NDWI, basses/zones humides amb presència dins l'àrea i punts d'aigua validats al camp.; No incorpora estat ecològic de masses d'aigua.
- Impacte: Permet saber que hi ha base hidrològica, però no avalua encara qualitat ni funcionalitat ecològica completa.

### CORE_11 · Potencial de restauració
- Càlcul: Combina valor d'hàbitats, vulnerabilitat climàtica parcial, funcionalitat hídrica, pressió humana gestionable i connectivitat.
- Limitacions: Falten Sentinel, hàbitats degradats validats, hàbitats font, SIGPAC/DUN i treball de camp.; No delimita zones de restauració; només calcula potencial agregat provisional.
- Impacte: Pot orientar on cal completar dades abans de proposar restauració; no és encara una priorització espacial.

### CORE_12 · Prioritat de gestió
- Càlcul: Síntesi dels indicadors Core calculables. Manté estat parcial si qualsevol font crítica de síntesi continua absent.
- Limitacions: No genera recomanacions ni zones prioritàries.; La síntesi queda limitada per absència de Copernicus, clima, combustible oficial i treball de camp.
- Impacte: Ofereix només una lectura agregada de motor; no substitueix diagnosi ni priorització de gestió.
