# EcoRadar Urbà — repositori complet de la Seu d’Urgell

Aquest repositori conté el visor interactiu, la funció Netlify, els registres
històrics i de reserva, el codi de càlcul, els connectors oficials, les dades
d’origen i processades necessàries, la documentació metodològica, les proves i
el workflow d’actualització diària de la Seu d’Urgell, Castellciutat i Sant
Antoni.

El projecte Python està declarat a `pyproject.toml` com un únic paquet:
`ecoradar` i els seus subpaquets. Les carpetes operatives `config`, `docs`,
`metadata`, `history`, `netlify`, `projectes`, `tests`, `tools` i `vendor` no
formen part del paquet Python.

## Publicació directa

Els fitxers publicables són a l’arrel:

- `index.html`
- `netlify.toml`
- `metadata/`
- `history/`
- `netlify/`
- `docs/`
- `vendor/`

Per tant, a Netlify la base i el directori de publicació poden quedar a
l’arrel del repositori. La funció és `netlify/functions/daily-readings.mjs`.

## Actualització automàtica

El procés executable és:

```text
.github/workflows/update-current-fire-danger.yml
```

Cada execució:

1. fixa un únic `checked_at_utc` per a tota la comprovació;
2. consulta XEMA, CAMS i ForestDrought CREAF/EMF, i comprova noves escenes Landsat i ECOSTRESS;
3. consulta Sentinel-2 i el context Copernicus quan hi ha credencials;
4. recalcula ombra, perill d’incendi, lectures i historial;
5. regenera el visor i sincronitza tant el paquet intern com l’arrel;
6. valida dates, JavaScript i fitxers;
7. fa `commit` i `push` abans del desplegament a Netlify.

Els JSON de `metadata/` són una reserva estàtica. La lectura principal del
visor prové de l’API Netlify, que consulta els fitxers canònics actualitzats de
`projectes/LaSeu_Urba/indicators/`.

## Secrets de GitHub Actions

Secrets opcionals per actualitzar fonts autenticades:

- `COPERNICUS_CLIENT_ID`
- `COPERNICUS_CLIENT_SECRET`
- `EARTHDATA_TOKEN` (token gratuït de NASA Earthdata Login per descarregar ECOSTRESS)

Secrets opcionals per fer el desplegament directe:

- `NETLIFY_AUTH_TOKEN`
- `NETLIFY_SITE_ID`

No hi ha cap secret real dins del ZIP. `.env.example` només documenta els noms
de les variables.

## Variables de Netlify

Cal configurar una font remota externa al desplegament estàtic:

- `ECORADAR_GITHUB_REPOSITORY=PROPIETARI/REPOSITORI`
- `ECORADAR_GITHUB_BRANCH=main`, si la branca és diferent cal substituir-la
- `ECORADAR_DATA_BEARER_TOKEN`, només si el repositori és privat

Alternativament es pot definir:

```text
ECORADAR_DATA_BASE_URL=https://raw.githubusercontent.com/PROPIETARI/REPOSITORI/main/projectes/LaSeu_Urba
```

## Validació local

Amb Python 3.11 i Node.js:

```bash
pip install -e .
python tools/validate_la_seu_daily_timestamps.py
node --check netlify/functions/daily-readings.mjs
node --test tests/js/test-daily-readings-api.mjs
```

`repository-manifest.json` enumera els fitxers empaquetats, la mida i el
SHA-256 de cadascun. No inclou entorns virtuals, memòria cau, secrets, còpies
Netlify versionades antigues ni paquets ZIP antics.

## Fonts i limitacions

La matriu completa de fonts i estats és a
`projectes/LaSeu_Urba/metadata/data_sources_matrix.md`. Les lectures
contextuals de resolució insuficient no s’interpreten com a mapes de carrer.
La manca d’un registre no s’interpreta automàticament com una absència real.
