# MEMÒRIA DEL FOC editorial specification

Status: `blocked`

Last checked: 2026-07-07

## Gate

This is a future editorial and analytical specification for the EcoRadar fire module. It is not a final sheet and must not trigger connector implementation, ecological analysis, map generation, chart generation, PDF export, or PNG preview while the fire source trace remains blocked.

Required source gate:

- `docs/data_sources/fire/incendiscat-official-source.md`

## Product

Title: `MEMÒRIA DEL FOC`

Subtitle pattern: `[Nom de l'espai natural] - resposta ecologica postfoc`

Format:

- DIN A4 vertical.
- Professional editorial sheet, with a CREAF / European Environment Agency tone.
- Broad safe margins.
- Technical, sober, credible visual language.
- Main colors: institutional dark green, medium green, orange for alert/risk factors, red only for past fires.
- Avoid a generic infographic look.
- No text, labels, legends, maps, or charts may overlap or overflow their boxes.
- Prefer readability and technical credibility over information density.

## Purpose

The sheet is not a descriptive wildfire fact sheet. It is a post-fire ecological diagnosis. It should explain how the landscape, vegetation, agroforestry mosaic, and repeated-fire risk have responded after fires.

Every visible block must support a management decision.

## Header

Include a small `MISSATGE CLAU` box with one concise management sentence.

Example tone:

`Incendis petits, pero un patro territorial clar: mantenir mosaic funcional per reduir combustible continu.`

The sentence must be generated from validated evidence, not from a generic template.

## Required Sections

### 1. DIAGNOSI ECOLOGICA

Short analytical text that explains:

- what happened after fire,
- which territorial pattern repeats,
- the ecological consequence,
- the resulting management decision.

Avoid generic statements. The section must provide a usable conclusion.

### 2. QUIN PATRO TERRITORIAL ES REPETEIX?

Main real map of the study area.

Required map elements when data support them:

- official basemap or orthophoto, preferably ICGC, with moderate opacity,
- real boundary of the natural area,
- real fire perimeters or points,
- past fires as hollow circles with year in the centre,
- areas with similar characteristics as small precise green square frames,
- clear and discreet legend.

Rules:

- Do not invent perimeters or burned areas.
- Green frames must preserve recurrence locations and be smaller and precise, not broad speculative polygons.
- The block must answer whether fires share a territorial pattern.
- The answer should relate access, aspect, fuel, forest-shrubland edges, agroforestry mosaic, and recurrence only when those variables are available.

### 3. QUINA DIAGNOSI DE GESTIO?

Include short validated indicators, such as:

- percentage of the area affected,
- post-fire sample hectares,
- burned surface inside the study boundary,
- other validated metrics available from official or documented sources.

Include a short interpretive table with four rows:

- `Que passa`
- `Per que`
- `Conseqüencia`
- `Gestio`

The table must interpret, not merely describe.

### 4. RECUPERACIO O NOU COMBUSTIBLE?

Compare orthophotos or NDVI for available post-fire years. If orthophotos are available, show two or three temporal strips, for example 2008, 2013, and 2024.

Explain whether vegetation cover has recovered and whether that recovery increases fuel continuity.

Allowed conclusion only if supported by data:

`La recuperacio de la coberta es alta, pero pot reforcar la continuitat del combustible si no es mante el mosaic obert.`

Do not make biodiversity or forest-structure claims without supporting data.

### 5. CONCLUSIONS DE GESTIO

Use a table with short rows. Each conclusion must end in a decision.

Columns:

- `Variable`
- `Diagnosi`
- `Decisio`

Candidate rows, only when supported by evidence:

- `Coberta vegetal | Alta | No cal restauracio generalitzada.`
- `Mosaic agroforestal | Feble | Prioritzar recuperacio de prats i feixes.`
- `Combustible | Continu | Actuar sobre vores bosc-matollar i pistes.`
- `Habitats oberts | Mantenir | Evitar tancament per successio natural.`
- `Restauracio | Selectiva | Nomes en sol nu, erosio o clapes lentes.`
- `Prioritat | Mosaic | Fer prevencio amb retorn ecologic.`

### 6. ON ES POT REPETIR I PER QUE?

Use a map or territorial scheme with:

- natural area boundary,
- past fires as hollow circles,
- similar-characteristic areas as small green square frames.

The green frames must have a visual proportion similar to the hollow fire circles. Avoid large imprecise polygons.

Include four micro-conclusions:

- `Patro`: accessible edges and forest-shrubland interfaces.
- `Evidencia`: validated evidence, for example Pla Alfa, recent fires, proximity to tracks, land cover, or aspect.
- `Conseqüencia`: active local or regional risk during dry episodes.
- `Gestio`: preventive mosaic and surveillance on high-risk days.

If IncendisCAT is used at all:

- use it only as current operational context,
- do not present it as post-fire ecological recovery evidence,
- include consultation date,
- phrase example: `incendisCAT consultat el [data]`.

If the Bombers ArcGIS operational viewer is used at all:

- use it only as current operational context,
- show it as point evidence, never as burned perimeter or post-fire recovery evidence,
- include consultation date and source status,
- phrase example: `Visor Bombers consultat el [data]; font operativa en verificacio.`

### 7. QUIN MOSAIC REDUEIX EL RISC?

Include a qualitative ring/circle reading of the mosaic, not an exact percentage unless a validated GIS calculation exists.

Categories:

- `Bosc`: dominant
- `Matollar`: continuous
- `Prats/feixes`: discontinuous
- `Conreus`: residual
- `Sol nu`: punctual

The visual proportions must match the text:

- forest and shrubland visually dominant,
- meadows/terraces intermediate,
- crops small,
- bare soil very small.

Centre label:

- `GIS`
- `qualitativa`

Conclusion:

`El mosaic util es el que combina discontinuïtat del combustible i habitat obert.`

### 8. QUATRE DECISIONS DE GESTIO

Final table with three columns:

- `Objectiu`
- `Evidencia`
- `Actuacio`

Recommended rows, only when supported by evidence:

- `Mantenir obert | La recuperacio pot tancar el mosaic. | Pastura extensiva i agricultura de discontinuïtat.`
- `Trencar continuitat | El risc es de vora i combustible, no de superficie cremada. | Franges selectives on coincideixen accessos i bosc-matollar.`
- `No sobreactuar | La coberta s'ha recuperat en bona part. | Seguiment; evitar restauracio generalitzada.`
- `Restaurar clapes | Sol nu, erosio o recuperacio lenta son punts critics. | Restauracio localitzada i control d'erosio.`

## Sources

Always show real sources and consultation date in the final sheet.

Allowed only if actually consulted and quantified:

- official or supplied fire perimeters,
- ICGC WMS orthophoto or basemap,
- Bombers / Generalitat historical data,
- Bombers ArcGIS operational viewer only for current operational context,
- IncendisCAT only for current operational context,
- GBIF, Ornitho, iNaturalist, or other biodiversity databases only if actually consulted and quantified.

## Content Rules

- Do not invent data.
- Do not include charts without real data.
- Do not make unsupported ecological claims.
- If a question cannot be answered with available data, remove it from the final sheet.
- Every block must contribute to a management decision.
- The final sheet should answer, when data allow:
  - has fire accelerated forest closure?
  - has the agroforestry mosaic increased or decreased?
  - has vegetation recovered?
  - has recovery increased fuel continuity?
  - could the same pattern repeat?
  - which interventions have the highest ecological return?

## Future Output

Only after verified and documented official sources are available:

- generate an A4 vertical PDF,
- generate a PNG preview,
- perform visual QA for overlaps, legends, margins, map/chart coherence, and text fit.
