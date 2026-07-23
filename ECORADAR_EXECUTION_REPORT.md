# Informe d'execució EcoRadar

Projecte: `Alinya`
Generat: `2026-07-08T12:14:29+00:00`
Estat: `completed`
Temps total: `10.712` segons

## Mòduls executats

| Pas | Mòdul | Estat | Temps (s) | Sortides | Error |
|---:|---|---|---:|---:|---|
| 1 | Carregar l'àrea d'estudi | ok | 0.63 | 1 |  |
| 2 | Executar el Data Source Manager | ok | 0.004 | 4 |  |
| 3 | Validar totes les fonts | ok | 0.012 | 3 |  |
| 4 | Executar els connectors disponibles | ok | 0.0 | 26 |  |
| 5 | Processar i normalitzar les dades | ok | 0.0 | 5 |  |
| 6 | Crear el Project Datastore | ok | 0.005 | 2 |  |
| 7 | Calcular els indicadors EcoRadar Core | ok | 0.01 | 4 |  |
| 8 | Executar el Motor de Diagnosi | ok | 0.012 | 3 |  |
| 9 | Executar el Motor de Recomanacions | ok | 0.01 | 4 |  |
| 10 | Executar el Mòdul de Validació | ok | 8.836 | 5 |  |
| 11 | Generar l'Informe de Diagnosi Ecològica Integrada | ok | 0.852 | 2 |  |
| 12 | Generar la Fitxa EcoRadar resum executiu | ok | 0.341 | 2 |  |

## Fonts

- Fonts utilitzades o disponibles: `14`
- Fonts fallides: `0`

## Indicadors calculats

| Codi | Nom | Estat | Confiança | Valor |
|---|---|---|---|---:|
| CORE_01 | Mosaic del paisatge | COMPLET | alta | 70.71 |
| CORE_02 | Valor d'hàbitats | COMPLET | alta | 98.91 |
| CORE_03 | Estat de la vegetació | NO DISPONIBLE | baixa | None |
| CORE_04 | Refugis climàtics | PARCIAL | mitjana | 59.2 |
| CORE_05 | Vulnerabilitat climàtica | PARCIAL | mitjana | 37.31 |
| CORE_06 | Biodiversitat coneguda | COMPLET | alta | 95.11 |
| CORE_07 | Pressió humana i ús públic | COMPLET | alta | 49.15 |
| CORE_08 | Connectivitat ecològica | COMPLET | alta | 79.5 |
| CORE_09 | Resiliència davant del foc | PARCIAL | mitjana | 44.17 |
| CORE_10 | Aigua i funcionalitat hídrica | PARCIAL | mitjana | 47.18 |
| CORE_11 | Potencial de restauració | PARCIAL | mitjana | 73.71 |
| CORE_12 | Prioritat de gestió | PARCIAL | mitjana | 65.49 |

## Recomanacions generades

| ID | Grup | Prioritat | Títol |
|---|---|---:|---|
| DADES-001 | Dades pendents | 97.18 | Desbloquejar Copernicus i clima abans de tancar vegetació, refugis climàtics i vulnerabilitat |
| CAMP-001 | Treball de camp | 91.55 | Executar una campanya de validació de camp sobre hàbitats, aigua, ús públic i biodiversitat sensible |
| CONS-001 | Conservació | 78.87 | Conservar preventivament HIC i hàbitats prioritaris abans de qualsevol actuació |
| CONS-002 | Conservació | 69.01 | Mantenir la matriu natural connectada i evitar noves barreres |
| HIDRO-001 | Seguiment | 69.01 | Validar funcionalitat hídrica, fonts i punts d'aigua abans de definir refugis o restauració |
| FOC-001 | Treball de camp | 69.01 | Validar combustible, humitat vegetal i discontinuïtats abans de proposar gestió forestal |
| AGR-001 | Dades pendents | 61.97 | Verificar prats, conreus residuals i espais oberts amb SIGPAC/DUN abans de gestió agrària |
| REST-001 | Restauració | 56.34 | Validar zones candidates de restauració abans de convertir el potencial en actuacions |
| GEST-001 | Gestió | 56.34 | Validar i ordenar l'ús públic on es pot solapar amb hàbitats d'alt valor |

## Fitxers creats

- `output/pdf/fitxa_ecoradar_alinya_a4.pdf`
- `output/pdf/informe_ecoradar_alinya_a4_client.pdf`
- `projectes/Alinya/datastore/ecoradar_project.sqlite`
- `projectes/Alinya/datastore/project_datastore.json`
- `projectes/Alinya/diagnosis/ecoradar_diagnosis.json`
- `projectes/Alinya/indicators/ecoradar_core_indicators.csv`
- `projectes/Alinya/indicators/ecoradar_core_indicators.json`
- `projectes/Alinya/metadata/connectors_status_report.json`
- `projectes/Alinya/metadata/data_availability_report.json`
- `projectes/Alinya/metadata/diagnosis_engine_report.json`
- `projectes/Alinya/metadata/indicator_engine_report.json`
- `projectes/Alinya/metadata/indicators_completeness_report.json`
- `projectes/Alinya/recommendations/priority_matrix.csv`
- `projectes/Alinya/recommendations/priority_matrix.json`
- `projectes/Alinya/recommendations/recommendations.json`
- `projectes/Alinya/recommendations/recommendations.md`
- `projectes/Alinya/reports/data_availability_report.md`
- `projectes/Alinya/reports/ecoradar_diagnosis.md`
- `projectes/Alinya/reports/fitxa_ecoradar_alinya_a4.pdf`
- `projectes/Alinya/reports/indicator_engine_report.md`
- `projectes/Alinya/reports/informe_ecoradar_alinya_a4_client.pdf`
- `projectes/Alinya/reports/validation_report.md`
- `projectes/Alinya/validation/ecological_validation.json`
- `projectes/Alinya/validation/field_validation_checklist.csv`
- `projectes/Alinya/validation/recommendations_validation.json`
- `projectes/Alinya/validation/technical_validation.json`

## Errors detectats

No s'han detectat errors crítics en aquesta execució.
