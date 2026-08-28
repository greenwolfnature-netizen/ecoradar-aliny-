# EcoRadar Alinyà v2 — paquet Netlify

Aquest directori es pot publicar directament a Netlify. La funció
`/api/daily-readings` consulta el repositori GitHub canònic a cada càrrega; els
JSON empaquetats només s'utilitzen com a reserva si falla la consulta remota.

Si el repositori GitHub és privat, configura
`ECORADAR_DATA_BASE_URL=https://main--NOM_DEL_LLOC.netlify.app/projectes/Alinya`
amb l'àlies de branca del mateix projecte. Si és públic, també es pot
configurar `ECORADAR_GITHUB_REPOSITORY=propietari/repositori` i,
opcionalment, `ECORADAR_GITHUB_BRANCH` (per defecte `main`).

## Contingut

- `index.html`: experiencia EcoRadar reorganitzada per a la Muntanya d'Alinya, amb lectura executiva i tecnica completa.
- `vendor/d3.min.js`: D3 servit localment, com al model EcoRadar Urba.
- `vendor/html2pdf.bundle.min.js`: exportació PDF local mitjançant descàrrega, sense obrir el diàleg d’impressió.
- `vendor/ecoradar-reading-report.js`: motor reutilitzable de previsualització i exportació PDF.
- `vendor/ecoradar-alinya-report-profiles.js`: interpretacions contextuals d’Alinyà basades en les dades reals del visor.
- `docs/data-sources-matrix.md`: matriu de fonts del projecte Alinya.
- `docs/fire-source.md`: nota de traçabilitat de la capa d'incendis.
- `docs/current-fire-danger-source.md`: metodologia i fonts oficials del perill actual.
- `metadata/current_fire_danger.json`: comprovacio, variables, pesos, resultats i limitacions.
- `metadata/biodiversity_habitat_pilot_metadata.json`: regles qualitatives, fonts, llindars relatius i limitacions del pilot.
- `metadata/biodiversity_habitat_pilot.geojson`: sectors agregats sense noms ni coordenades de taxons.
- `metadata/daily_readings.json` i `metadata/daily_history.json`: reserva coherent.
- `netlify/functions/daily-readings.mjs`: lectura remota del repositori canònic.

La capa de concurrencia no es probabilitat oficial d'incendi ni perill diari.
La lectura `Perill d'incendi avui` es un index analitic EcoRadar de 0 a 100
calculat en cel·les de 100 m,
no una alerta oficial ni el Pla Alfa. Utilitza meteorologia XEMA Y4 i
renormalitza els pesos si una variable no esta disponible.
La geometria historica d'incendis va ser consultada el 17.07.2026.
La concurrencia mostrada al visor utilitza nomes els perimetres historics
oficials d'Alinya i les condicions territorials ja processades. No incorpora
EFFIS, FIRMS ni registres operatius recents sense perimetre consolidat.
