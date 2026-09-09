# EcoRadar Alinyà — Fase 1 de correccions

Data de verificació: 2026-09-09
Instantània comuna: `alinya-1ce1ee286762c656`

## Correccions aplicades

- Sentinel-2: descobriment diari del catàleg públic i selecció preparada per cobertura real de l'àmbit i QA/SCL. La selecció i descàrrega d'una escena nova queda bloquejada sense `COPERNICUS_CLIENT_ID` i `COPERNICUS_CLIENT_SECRET`; l'escena vigent del 07.07.2026 es conserva amb 99,95% de píxels vàlids i historial immutable.
- Landsat LST: identificat com a compost multitemporal de 26 escenes candidates, 23 amb píxels vàlids, del 03.06.2025 al 25.08.2026. No es presenta com una observació individual del 25.08.2026.
- Sincronització: lectures, perill actual, RADAR, completesa, cel·les, visor, API i informes comparteixen un `snapshot_id`; l'API rebutja productes de snapshots diferents.
- CORE_03: mostra `NDVI 0,616` com a lectura directa Sentinel-2 del 07.07.2026, sense conversió a 61,6/100 i sense aportar valor numèric a CORE_12.
- Perill d'incendi: superfície vàlida, superfície sense dada, cobertura de l'àmbit i confiança del producte explícites; el 95% històric queda etiquetat com a qualitat de la sèrie.
- Refugis climàtics: fórmula vigent documentada separant LST, NDMI i NDVI dels contextos cartogràfics; el 42,3% explicita el denominador de píxels vegetats vàlids.
- Traçabilitat: procedència pendent de l'àmbit de treball declarada; hàbitats puntuals incorporats sense entrar a les superfícies ni RADAR; dates dels incendis normalitzades; GBIF paginat; registre únic de metadades per lectura.
- Llegibilitat: els textos abans definits entre 7 i 10 px s'han elevat a 11–13 px sense modificar amplades ni la graella general.

## Verificació superada

- 30 proves Python específiques d'Alinyà.
- 7 proves d'evidència ecològica.
- 33 proves JavaScript de context, informes, instantània i API.
- Compilació Python, coherència temporal i `git diff --check`.
- Revisió funcional en navegador de la vista principal, la capa de perill actual, RADAR_03 i l'informe automàtic.

## Incidències obertes

- Sentinel-2 necessita `COPERNICUS_CLIENT_ID` i `COPERNICUS_CLIENT_SECRET` per validar SCL/dataMask i descarregar una escena nova.
- ECOSTRESS necessita `EARTHDATA_TOKEN` per descarregar el grànul més recent detectat al catàleg.
- L'organisme autor, la URL original i la llicència de l'exportació d'Instamaps usada com a àmbit continuen pendents; el visor l'anomena «Àmbit de treball».
- GBIF declara 31.169 coincidències. L'execució auditada va descarregar 10.000 registres en 34 pàgines i va aturar-se al sostre de seguretat explícit.

## Decisions metodològiques no aplicades

No s'han modificat fórmules, ponderacions, llindars ni significat de CORE_01–CORE_12. H08, H09 i M01–M05 continuen oberts per a decisió ecològica posterior.
