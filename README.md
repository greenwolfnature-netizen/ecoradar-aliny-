# EcoRadar Muntanya d’Alinyà — repositori complet

Repositori autònom preparat per GitHub Desktop, GitHub Actions i desplegament
continu a Netlify. Manté la mateixa arquitectura operativa del repositori
canònic EcoRadar La Seu i substitueix únicament l’àmbit, les fonts, les capes,
els indicadors, els mapes i els informes per les dades verificades d’Alinyà.

## Publicació

1. Descomprimeix el ZIP i crea un repositori nou amb GitHub Desktop a partir
   d’aquesta carpeta.
2. Publica’l a GitHub.
3. A GitHub, configura si escau:
   `COPERNICUS_CLIENT_ID`, `COPERNICUS_CLIENT_SECRET`,
   `NETLIFY_AUTH_TOKEN` i `NETLIFY_SITE_ID`.
4. A Netlify, configura `ECORADAR_GITHUB_REPOSITORY=propietari/repositori` i,
   si la branca no és `main`, `ECORADAR_GITHUB_BRANCH`.
5. Executa manualment `Update EcoRadar Alinyà daily readings` una primera
   vegada. Després s’executa cada dia a les 14:35 UTC.

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
