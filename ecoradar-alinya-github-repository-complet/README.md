# EcoRadar Muntanya d’Alinyà — repositori complet

Repositori autònom preparat per GitHub Desktop, GitHub Actions i desplegament
continu a Netlify. Manté la mateixa arquitectura operativa del repositori
canònic EcoRadar La Seu i substitueix únicament l’àmbit, les fonts, les capes,
els indicadors, els mapes i els informes per les dades verificades d’Alinyà.

## Publicació

1. Descomprimeix el ZIP i crea un repositori nou amb GitHub Desktop a partir
   d’aquesta carpeta.
2. Publica’l a GitHub.
3. A GitHub, configura:
   `COPERNICUS_CLIENT_ID`, `COPERNICUS_CLIENT_SECRET`,
   i, opcionalment, `NETLIFY_AUTH_TOKEN` i `NETLIFY_SITE_ID`.
4. A Netlify, si el repositori és privat, configura
   `ECORADAR_DATA_BASE_URL=https://main--NOM_DEL_LLOC.netlify.app/projectes/Alinya`
   amb l'àlies de branca del projecte. Si el repositori és públic, també pots
   usar `ECORADAR_GITHUB_REPOSITORY=propietari/repositori` i, si la branca no
   és `main`, `ECORADAR_GITHUB_BRANCH`.
5. Cada `push` a `main` executa `Update EcoRadar Alinyà daily readings`,
   recalcula les lectures, desplega la versió nova i comprova el visor públic i
   `/api/daily-readings`. També es pot executar manualment i s’executa cada dia
   a les 14:35 UTC.

Si Netlify està connectat al repositori GitHub, el `push` del workflow ja
activa el desplegament continu i no calen `NETLIFY_AUTH_TOKEN` ni
`NETLIFY_SITE_ID`. Si tots dos secrets existeixen, el workflow també fa un
desplegament explícit amb Netlify CLI. En tots dos casos, no finalitza fins que
el visor públic i `/api/daily-readings` exposen exactament el
`checked_at_utc` de l’execució en curs.

## Lectura remota

La funció Netlify `/api/daily-readings` consulta els JSON canònics del
repositori GitHub. Els JSON empaquetats al desplegament només són una reserva
si falla aquesta consulta. La data pública sempre prové de
`checked_at_utc`, que es renova en cada execució, encara que els valors de les
fonts no canviïn.

## Fonts i límits

Les fonts i metodologies són a `docs/data_sources/` i
`projectes/Alinya/metadata/data_sources_matrix.*`. El perill d’incendi actual
és un índex analític EcoRadar 0–100, no una alerta oficial, el Pla Alfa ni una
predicció d’ignició. No s’utilitza IncendisCat com a font.

## Informes inclosos

- `projectes/Alinya/reports/fitxa_ecoradar_alinya_v1.pdf`
- `projectes/Alinya/reports/informe_complet_muntanya_alinya.pdf`

## Validació local

```bash
pip install -e .
python tools/validate_alinya_daily_timestamps.py --max-age-minutes 30
node --check netlify/functions/daily-readings.mjs
node --test tests/js/test-daily-readings-api.mjs
```
