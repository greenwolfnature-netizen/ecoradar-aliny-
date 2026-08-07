# Indicator Profiles

EcoRadar should show profiles, not one simplistic global score.

Each indicator row must store:

- raw value
- normalized value from 0 to 100
- level: `molt_baix`, `baix`, `mitja`, `alt`, `molt_alt`
- confidence: `baixa`, `mitjana`, `alta`
- source mode: `automatica`, `camp`, `mixta`
- linked recommendation

## Profiles

### Biodiversity

Inputs:

- habitats
- species records
- field observations
- protected/invasive/reference species lists when available

Example indicators:

- cited species count
- recent species count
- protected species count
- invasive species count
- information-gap score
- underrepresented taxon groups

### Connectivity

Inputs:

- land cover
- habitats
- protected areas
- water courses
- human pressure

Example indicators:

- mosaic degree
- habitat continuity
- corridor pressure
- river connectivity potential

### Vegetation Condition

Inputs:

- Sentinel-derived indices
- land cover
- drought context
- field observations

Example indicators:

- mean NDVI
- NDVI anomaly
- NDMI moisture stress
- NDWI water signal
- annual vegetation-vigor change

### Human Pressure

Inputs:

- OpenStreetMap/Overpass when verified
- field observations
- access points and recreational features

Example indicators:

- path density
- access-point density
- recreational pressure
- use/conservation conflict

### Fire Risk

Inputs:

- land-cover continuity
- urban-forest interface
- burned-area history
- access network
- terrain derivatives

Example indicators:

- forest continuity
- wildland-urban interface exposure
- fuel accumulation proxy
- protective mosaic score
- priority management zones

### Restoration Potential

Inputs:

- habitats
- degradation signals
- water availability
- land cover
- field observations

Example indicators:

- degraded habitat area
- restoration opportunity area
- water-linked restoration potential
- expected ecological benefit

### Climate Vulnerability

Inputs:

- climate context
- drought indices
- terrain derivatives
- vegetation stress

Example indicators:

- precipitation anomaly
- temperature anomaly
- drought exposure
- potential insolation
- climate refugia potential

