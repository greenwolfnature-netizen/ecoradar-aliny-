# connector_recreational_pressure

Status: `source_gated_partial`

This connector is not implemented yet because the requested intensity product
depends on sources with different access status.

## Source Gate

| Source | EcoRadar status | Connector decision |
| --- | --- | --- |
| OpenStreetMap / Overpass API | `verified` | Can support a first connector for recreational infrastructure and access features. |
| Strava Global Heatmap | `blocked` | Do not scrape or ingest until an authorized/licensed API or data delivery path is documented. |
| Wikiloc | `pending_verification` | Future source only. |
| Automatic visitor counters | `pending_verification` | Future source; likely manager-specific. |
| Protected-area manager data | `pending_verification` | Future source; requires owner, license and format verification. |
| Field observations | internal EcoRadar data | Can be imported by the fieldwork module, not by an external-source connector. |

## Allowed First Implementation

An initial OSM-only connector may be implemented as
`connectors/connector_recreational_pressure_osm.py` once requested.

It may download and normalize:

- paths, tracks and footways
- cycleways and minor roads relevant to access
- parking areas
- trailheads/access points where mapped
- viewpoints and recreation facilities
- route relations where mapped
- access and surface tags

It must output normalized vector layers only. It must not call those layers
"visitor intensity" by themselves.

## Blocked Until Authorized Access

The following outputs need Strava, visitor counters, manager data or fieldwork
before they can be considered reliable intensity products:

- relative hiking intensity
- relative BTT intensity
- relative trail running intensity
- relative cycling intensity
- high-use corridors
- low-use/tranquillity maps
- visitor concentration maps
- wildlife/public-use conflict potential maps

Strava heatmap values, if later authorized, must always be stored as relative
activity intensity and never as absolute visitor counts.

Manual visual reference supplied for Alinya:

- `https://www.strava.com/maps/global-heatmap?sport=All&style=dark&terrain=false&labels=true&poi=true&cPhotos=true&3d=false&gColor=blue&gOpacity=100#10.65/42.3576/1.4762`

This URL may help a human compare expected recreational corridors, but it is
not a connector input until Strava provides an authorized data access path for
EcoRadar.

## Future Output Contract

When all required source gates are open, the connector stack should create:

- `projectes/<name>/raw/recreational_pressure/`
- `projectes/<name>/processed/recreational_pressure.gpkg`
- `projectes/<name>/metadata/recreational_pressure_metadata.json`

Analysis Engine outputs should be separate from connector outputs:

- intensity raster/map
- tranquillity map
- potential conflict map
- visitor concentration map

Those maps are derived analysis products, not raw connector responsibilities.
