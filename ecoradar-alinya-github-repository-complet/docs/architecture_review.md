# EcoRadar Architecture Review

Data: 2026-07-07

## Objectiu de la consolidació

EcoRadar queda consolidat com una plataforma de diagnosi ecològica amb un flux oficial únic. Aquesta revisió no afegeix connectors, indicadors ni noves sortides finals; reorganitza responsabilitats, arxiva prototips i separa el codi de plataforma dels casos d'ús.

## Arquitectura actual

```text
ecoradar/
  core/              Projecte, àrea d'estudi i orquestració
  sources/           Catàleg de fonts, Data Source Manager i availability gate
  connectors/        Connectors oficials i contracte base
  datastore/         Inventari únic del datastore de projecte
  indicators/        Catàleg i motor oficial d'indicadors
  diagnosis/         Motor oficial de diagnosi ecològica
  recommendations/   Motor oficial de recomanacions i priorització
  validation/        Validation gate oficial
  reporting/         Maquetació visual oficial
```

## Què s'ha mogut

- Els connectors reals han passat de `/connectors` a `ecoradar/connectors/`.
- El Data Source Manager i el source availability gate han passat de `ecoradar/core` a `ecoradar/sources`.
- El renderer A4 oficial ha passat de `tools/export_ecoradar_client_report_a4.py` a `ecoradar/reporting/client_report_a4.py`.
- Els motors oficials de domini han sortit de `ecoradar/core` i han passat als seus paquets: `indicators`, `diagnosis`, `recommendations` i `validation`.
- Els wrappers top-level de `/core` s'han arxivat a `docs/legacy_archive/core_wrappers/`.
- Els exportadors i scripts de prototip s'han mogut a `tools/legacy/`.
- Els PDFs antics que no formen part del pipeline oficial s'han mogut a:
  - `projectes/Alinya/legacy_outputs/reports/`
  - `output/legacy_pdf/`

## Què s'ha eliminat funcionalment

No s'ha esborrat evidència de projecte. S'ha eliminat del flux oficial:

- L'ús d'exportadors A3/v2/v3 com a camí de producció.
- Els motors duplicats antics de diagnosi i recomanacions.
- La dependència de scripts antics per generar la fitxa/informe oficial.
- La carpeta externa `/connectors` com a ubicació de connectors reals.

## Què queda com a legacy

- `tools/legacy/`: prototips visuals, mapes experimentals i scripts previs.
- `docs/legacy_archive/core_wrappers/`: wrappers antics del top-level `core`.
- `projectes/Alinya/legacy_outputs/`: sortides històriques del cas Alinyà.
- `output/legacy_pdf/`: PDFs antics no vinculats al pipeline oficial actual.
- `ecoradar/analysis/core.py`: motor Core antic mantingut només per compatibilitat de tests i referència. El motor oficial és `ecoradar/indicators/engine.py`.
- `ecoradar/product/fitxa_value.py`: value gate històric; pot migrar a `ecoradar/reporting` si es manté com a part del producte.

## Pipeline oficial

```text
Study Area
→ Source Availability
→ Connectors
→ Project Datastore
→ Indicator Engine
→ Diagnosis Engine
→ Recommendation Engine
→ Validation Gate
→ Informe de Diagnosi Ecològica Integrada
→ Fitxa EcoRadar resum executiu
```

Implementació oficial:

- `ecoradar/core/orchestrator.py`
- `ecoradar/pipeline.py`
- `tools/run_ecoradar_pipeline.py` com a launcher curt

## Com executar EcoRadar

Execució completa:

```bash
PYTHONPATH=. .venv/bin/python -m ecoradar.pipeline --project projectes/Alinya
```

Execució sense generar fitxa ni informe:

```bash
PYTHONPATH=. .venv/bin/python -m ecoradar.pipeline --project projectes/Alinya --skip-documents
```

Launcher equivalent:

```bash
PYTHONPATH=. .venv/bin/python tools/run_ecoradar_pipeline.py --project projectes/Alinya --skip-documents
```

## Mòduls obligatoris

Abans de publicar cap fitxa o informe, el pipeline ha d'executar:

1. `ecoradar.core.study_area`
2. `ecoradar.sources.data_source_manager`
3. `ecoradar.connectors.*`
4. `ecoradar.datastore.project_store`
5. `ecoradar.indicators.engine`
6. `ecoradar.diagnosis.engine`
7. `ecoradar.recommendations.engine`
8. `ecoradar.validation.engine`
9. `ecoradar.reporting.client_report_a4`

## Separació de responsabilitats

- Els connectors només obtenen, retallen, normalitzen i escriuen dades.
- El Data Source Manager només audita disponibilitat i completesa de fonts.
- El datastore només inventaria els artefactes oficials del projecte.
- Els indicadors calculen valors i confiança.
- La diagnosi interpreta indicadors, fonts i limitacions.
- Les recomanacions deriven exclusivament de la diagnosi.
- La validació bloqueja la publicació si detecta errors crítics.
- El reporting només llegeix artefactes existents i maqueta.

## Estat del datastore

S'ha creat `ecoradar/datastore/project_store.py`, que genera:

```text
projectes/{project}/datastore/project_datastore.json
projectes/{project}/datastore/ecoradar_project.sqlite
```

Aquest datastore és el primer pas cap a una base única per projecte. Encara no substitueix físicament tots els CSV/JSON/GPKG, però fixa un inventari oficial consultable perquè els mòduls deixin de descobrir fitxers de manera dispersa.

## Cas Alinyà

`projectes/Alinya/` queda com a projecte de prova i demostració. El pipeline oficial accepta qualsevol directori de projecte amb `--project`, i el renderer A4 ja parametriza noms de sortida segons el projecte. Els mapes generats fins ara continuen sent els del cas Alinyà; per multi-projecte complet caldrà que el mòdul cartogràfic generi la mateixa família d'imatges per cada espai.

## Deute tècnic pendent

- Generar automàticament els mapes editorials del renderer A4 per qualsevol projecte, no només per Alinyà.
- Convertir els CSV resum en taules dins un GeoPackage/SQLite únic.
- Convertir les definicions d'indicadors a YAML o una especificació declarativa.
- Modularitzar `validation_engine.py` en validació tècnica, ecològica, camp i recomanacions.
- Eliminar definitivament `ecoradar/analysis/core.py` quan cap test ni sortida antiga el requereixi.
- Decidir si `ecoradar/product/fitxa_value.py` continua com a producte o passa a `reporting`.

## Criteri de qualitat

Cap fitxa ni informe final és vàlid si no existeixen:

- `metadata/data_availability_report.json`
- `metadata/connectors_status_report.json`
- `metadata/indicators_completeness_report.json`
- `indicators/ecoradar_core_indicators.json`
- `diagnosis/ecoradar_diagnosis.json`
- `recommendations/recommendations.json`
- `validation/technical_validation.json`
- `validation/ecological_validation.json`
- `validation/recommendations_validation.json`
- `datastore/project_datastore.json`
