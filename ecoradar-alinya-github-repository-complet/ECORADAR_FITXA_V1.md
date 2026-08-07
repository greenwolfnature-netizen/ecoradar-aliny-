# EcoRadar Fitxa v1

Estat: congelada
Projecte de referencia: Alinya
Data de congelacio: 2026-07-08
Producte principal congelat: Fitxa EcoRadar A4 vertical

## Objectiu de la versio

La Fitxa EcoRadar v1 es una eina executiva de diagnosi ecologica. No es una sortida GIS ni un resum de desenvolupament. La fitxa ha de permetre que un gestor d'un espai natural respongui en menys d'un minut:

1. Quin es l'estat ecologic global de l'espai?
2. Quin proces ecologic es el mes important?
3. Quin es el principal risc?
4. Quina es la principal oportunitat?
5. Quina actuacio faria primer?
6. On hauria d'actuar?

## Regla de producte congelada

Quan es canviï d'espai, no s'han de repetir instruccions de disseny ni de metodologia. S'ha de:

1. Crear o preparar el nou projecte.
2. Carregar l'area d'estudi.
3. Executar el pipeline oficial.
4. Generar la fitxa amb el mateix generador.
5. Canviar nomes els valors, mapes i conclusions derivades de les dades del nou espai.

No s'han de modificar connectors, indicadors, motor de diagnosi ni pipeline per adaptar una fitxa a un nou espai.

## Regla Fitxa Primer

A partir de la versio v1, la Fitxa EcoRadar es el referent de qualitat de tot el producte.

El proces editorial obligatori es:

1. Generar la Fitxa EcoRadar.
2. Considerar la fitxa com el document executiu definitiu.
3. Desenvolupar l'Informe de Diagnosi Ecologica Integrada com a demostracio tecnica de cada afirmacio important de la fitxa.

L'informe no es un document independent ni una ampliacio descriptiva. L'informe ha de justificar la fitxa amb cartografia, dades, indicadors, relacions ecologiques, processos, consequencies, escenaris futurs i implicacions de gestio.

Per cada afirmacio important de la fitxa, l'informe ha de respondre:

- per que passa;
- quines evidencies ho demostren;
- quines consequencies ecologiques te;
- que passara si no s'actua;
- quina decisio de gestio justifica.

Control de qualitat de cada capitol:

`Si elimino aquest capitol, la fitxa continua sent igual de creible?`

Si la resposta es si, el capitol no aporta prou valor i s'ha de reescriure.

## Ordres oficials

Substitueix `NOM_ESPAI` i `/ruta/a/area_estudi.gpkg` pel nou cas.

### 1. Preparar area d'estudi

```bash
/Users/usuario/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m ecoradar.cli prepare-study-area /ruta/a/area_estudi.gpkg --project-name NOM_ESPAI --projects-root projectes --metric-crs EPSG:25831 --repair-geometry --overwrite
```

### 2. Executar pipeline oficial

```bash
/Users/usuario/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tools/run_ecoradar_pipeline.py --project projectes/NOM_ESPAI
```

### 3. Regenerar nomes Fitxa i Informe A4

```bash
/Users/usuario/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ecoradar/reporting/client_report_a4.py --project projectes/NOM_ESPAI
```

### 4. Validar visualment la fitxa

```bash
env XDG_CACHE_HOME=/private/tmp /Users/usuario/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/pdftoppm -q -png -r 170 -f 1 -l 1 projectes/NOM_ESPAI/reports/fitxa_ecoradar_nom_espai_a4.pdf /private/tmp/ecoradar_fitxa_review
```

## Fitxers congelats d'Alinya v1

- `projectes/Alinya/reports/releases/fitxa_ecoradar_alinya_v1.pdf`
- `output/pdf/releases/fitxa_ecoradar_alinya_v1.pdf`
- `docs/product/releases/fitxa_ecoradar_v1/client_report_a4_v1.py`
- `docs/product/releases/fitxa_ecoradar_v1/fitxa_ecoradar_v1.yaml`

## Criteri d'acceptacio de la fitxa

La fitxa nomes es valida si:

- mostra un estat ecologic global clar;
- identifica processos ecologics, no nomes indicadors;
- formula risc, oportunitat i actuacio prioritaria;
- indica on actuar;
- no mostra termes de desenvolupament;
- no mostra fonts pendents com a problema tecnic;
- no conte textos o numeros fora de requadres;
- conserva estructura A4 vertical d'una pagina.

## Elements que no poden aparèixer al cos de la fitxa

- Copernicus
- Sentinel
- APIs
- Connectors
- Data Source Manager
- Desenvolupament
- Fonts pendents
- Desbloquejar dades
- Informacio pensada per desenvolupadors

Si falta informacio, s'expressa en termes ecologics. Exemple:

`No es disposa encara de prou evidencia per prioritzar actuacions forestals de detall.`

## Canvi minim per un nou espai

Per aplicar EcoRadar a un nou espai cal canviar:

- nom del projecte;
- capa de l'area d'estudi;
- dades processades pels connectors;
- mapes generats;
- valors dels indicadors;
- conclusions ecologiques derivades del motor de diagnosi.

No cal tornar a definir:

- disseny de fitxa;
- estructura dels requadres;
- preguntes de gestio;
- criteris d'acceptacio;
- ordre del pipeline;
- llenguatge de producte.
