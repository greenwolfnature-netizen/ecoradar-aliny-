# EcoRadar fire source trace: IncendisCAT

Status: `blocked`

Last checked: 2026-07-07

## Decision

EcoRadar must not implement a wildfire connector from IncendisCAT at this stage.

IncendisCAT states that its incident data comes from open data for "actuacions dels Bombers de la Generalitat de Catalunya", but its public browser code uses its own backend endpoints (`backend/api.php`, `backend/plaalfa.php`, `backend/firms.php`). The exact upstream official endpoint used by that backend is not exposed or proven.

The closest official open-data candidate is `g2ay-3vnj`, "Actuacions dels Bombers de la Generalitat", but it cannot be validated as the exact IncendisCAT source because key IncendisCAT fields and update behaviour are not present in the official dataset metadata:

- IncendisCAT exposes latitude, longitude, operational status, deployed units, first seen, last update, and minute-scale refresh.
- `g2ay-3vnj` is documented as a weekly tabular dataset by municipality/comarca/region, with no point coordinates and no operational status fields.

Until the official upstream used by IncendisCAT is demonstrated by an official source or by IncendisCAT maintainers with verifiable endpoint documentation, the source remains blocked.

## IncendisCAT trace evidence

- Site: https://incendiscat.cat/
- Public statement: IncendisCAT says the data comes from open data for the actions of Bombers de la Generalitat de Catalunya.
- Public statement: IncendisCAT says the map refreshes every minute with the latest Bombers information.
- Public code trace:
  - `https://incendiscat.cat/mapa.html`
  - `https://incendiscat.cat/js/app.min.js`
  - Browser data endpoint: `https://incendiscat.cat/backend/api.php?timespan=21600000`
- Important constraint: these IncendisCAT backend endpoints are not official Generalitat sources and must not be used as EcoRadar data sources.

## Official candidate source metadata

### Source name

Actuacions dels Bombers de la Generalitat

### Responsible organization

Departament d'Interior / Interior i Seguretat Publica. Direccio General de Prevencio, Extincio d'Incendis i Salvaments (DGPEIS).

Official dataset attribution: "Departament d'Interior. Direcció General de Prevenció, Extinció d'Incendis i Salvaments".

### Official URL

- Dataset page: https://analisi.transparenciacatalunya.cat/d/g2ay-3vnj
- Metadata API: https://analisi.transparenciacatalunya.cat/api/views/g2ay-3vnj
- Example JSON API: https://analisi.transparenciacatalunya.cat/resource/g2ay-3vnj.json?$limit=10

### Service type

Socrata open data API.

### Data format

Tabular dataset available through Socrata API formats, including JSON and CSV.

### Coordinate reference system

No CRS is declared for geometries because the dataset is tabular and does not expose coordinates.

Geographic reference is by administrative codes and names:

- `CODI_INE`
- `CODI_COMARCA`
- `MUNICIPI`
- `NOM_POBLACIO`
- `NOM_COMARCA`
- `CODI_REGIO`
- `NOM_REGIO`

### Available variables

Documented fields:

- `ACT_NUM_ACTUACIO`: action identifier
- `CODI_INE`: municipality code according to INE
- `NOM_REGIO`: emergency region name
- `TAL_COD_ALARMA1`: action group code
- `TGA_NOM_GRUPO`: action group description
- `TAL_COD_ALARMA2`: action type code
- `TAL_NOM_ALARMA`: action type description
- `MUNICIPI`: municipality
- `NOM_POBLACIO`: population/place name
- `CODI_COMARCA`: comarca code
- `NOM_COMARCA`: comarca
- `ANY`: year
- `MES`: month
- `ACT_DAT_ACTUACIO`: action date
- `CODI_REGIO`: emergency region identifier
- `URGENTS`: urgent/non-urgent classification
- `VALIDAT`: whether the action information is validated/final in the information systems

### Update frequency

Weekly, according to the official metadata.

### Usage license

License ID in dataset metadata: `SEE_TERMS_OF_USE`.

General Generalitat open data license page: https://web.gencat.cat/ca/generalitat/dades-indicadors/dades-obertes/llicencies

Relevant conditions include citation of the source and last update date, and not altering or denaturalizing the meaning of the information.

### Example connection

Metadata:

```text
GET https://analisi.transparenciacatalunya.cat/api/views/g2ay-3vnj
```

Sample records:

```text
GET https://analisi.transparenciacatalunya.cat/resource/g2ay-3vnj.json?$limit=10
```

Example filter for vegetation/fire-related actions should only be designed after validating the field values and the source status:

```text
GET https://analisi.transparenciacatalunya.cat/resource/g2ay-3vnj.json?$limit=10&$where=upper(tal_nom_alarma)%20like%20%27%25INCENDI%25%27
```

### Connector status

`blocked`

Reason: official candidate source exists, but it has not been proven to be the exact official source used by IncendisCAT. No EcoRadar connector may be implemented from this source for the IncendisCAT-equivalent fire module until this trace is resolved.

## Additional operational official candidate found on 2026-07-07

### Source name

Bombers - Visor d'actuacions incendis PRO / `ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW`

### Responsible organization

Departament d'Interior / Bombers de la Generalitat. The public ArcGIS item owner is `AdminInterior`.

### Official URL

- ArcGIS Experience: https://experience.arcgis.com/experience/f6172fd2d6974bc0a8c51e3a6bc2a735
- Feature layer: https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services/ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW/FeatureServer/0

### Service type

ArcGIS Experience and ArcGIS FeatureServer query service.

### Data format

ArcGIS JSON query response with point geometry.

### Coordinate reference system

`EPSG:25831`.

### Available variables

- `ACT_NUM_ACTUACIO`
- `ACT_DAT_ACTUACIO`
- `TAL_COD_ALARMA1`
- `TAL_DESC_ALARMA1`
- `TAL_COD_ALARMA2`
- `TAL_DESC_ALARMA2`
- `ACT_SITUACIO`
- `ACT_DAT_ACTUAL`
- `ACT_DAT_INICI`
- `ACT_DAT_FI`
- `ACT_URGENT`
- `MUNICIPI_DPX`
- `MUNICIPI_SIG`
- `DATA_ACT`
- `ACT_NUM_VEH`
- `COM_FASE`
- point geometry

### Update frequency

The layer metadata reports `cacheMaxAge = 30`. The inspected metadata does not formally document the operational refresh cadence, retention window, archive scope, or licence.

### Usage license

Not declared in the inspected public ArcGIS item/layer metadata.

### Example connection

```text
GET https://services7.arcgis.com/ZCqVt1fRXwwK6GF4/arcgis/rest/services/ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW/FeatureServer/0/query?f=json&where=1%3D1&returnGeometry=true&outFields=*&outSR=25831
```

### Connector status

`pending_verification`

### Verification notes

The public Experience configuration identifies a Bombers real-time vegetation-fire viewer, and the FeatureServer layer is filtered to `TAL_COD_ALARMA1 = 'IV' AND ACT_NUM_VEH >= 0`. On 2026-07-07 a Cadí context query returned one point incident in Gisclareny, phase `Estabilitzat`.

This source is closer to the operational fields exposed by IncendisCAT than `g2ay-3vnj`, because it includes point geometry and phase/status-like attributes. It still does not prove the exact IncendisCAT upstream: IncendisCAT's own backend has not been formally mapped to this FeatureServer, and licence/retention terms remain undocumented. Therefore the IncendisCAT source gate remains `blocked` and no connector should be implemented from this layer yet.

## Related official fire datasets, not IncendisCAT source

These are useful future candidates for the EcoRadar fire domain, but they do not prove the IncendisCAT upstream:

### Incendis forestals per comarques a Catalunya. Any en curs

- Dataset ID: `9r29-e8ha`
- URL: https://analisi.transparenciacatalunya.cat/d/9r29-e8ha
- Description: provisional current-year forest fires with date, starting municipality, and affected forest/non-forest areas.
- Status for IncendisCAT trace: `pending_verification`

### Incendis forestals per comarques a Catalunya. Any anterior

- Dataset ID: `crs7-idxi`
- URL: https://analisi.transparenciacatalunya.cat/d/crs7-idxi
- Description: previous-year forest fires with date, starting municipality, and affected forest/non-forest areas.
- Update frequency: annual.
- Status for IncendisCAT trace: `pending_verification`

### Incendis forestals a Catalunya. Anys 2011-2024

- Dataset ID: `bks7-dkfd`
- URL: https://analisi.transparenciacatalunya.cat/d/bks7-dkfd
- Description: forest fires in Catalonia from 2011 to 2024 with date, starting municipality, and affected forest/non-forest area.
- Status for IncendisCAT trace: `pending_verification`

### Base cartografica d'incendis forestals

- Dataset ID: `dw2p-tke8`
- URL: https://analisi.transparenciacatalunya.cat/d/dw2p-tke8
- Description: cartographic wildfire perimeters for 1986-2021, with historical perimeters incorporated from satellite imagery work commissioned by the Agriculture department to the Institut Cartografic i Geologic de Catalunya.
- Status for IncendisCAT trace: `pending_verification`

## Open verification tasks

1. Obtain official documentation or confirmation for the exact real-time Bombers open-data endpoint used for active incidents.
2. Verify whether IncendisCAT maps `backend/api.php` from `g2ay-3vnj`, the Bombers ArcGIS FeatureServer, a non-catalog Generalitat endpoint, a Bombers feed, or a manually derived/proxied source.
3. Confirm whether the official source exposes point coordinates, operational status, active units, and minute-scale updates with documented licence and retention terms.
4. Only after the exact official source is verified, update this document status to `verified` or `requires_credentials`.
5. Do not implement a connector while this document remains `blocked`.
