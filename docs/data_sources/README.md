# EcoRadar Data Source Inventory

This directory is the gate for the EcoRadar Data Engine.

No connector should be implemented until the required official sources for the target domain are identified, verified against the responsible body, and documented here with a connector status.

Allowed source statuses:

- `verified`: official source and technical access path have been checked against the responsible body or an official catalogue.
- `requires_credentials`: official source is identified, but access requires credentials or authorization.
- `service_unavailable`: official source is identified, but the service was unavailable during verification.
- `pending_verification`: likely official source is identified, but one or more required metadata fields or the exact endpoint still need confirmation.
- `blocked`: source cannot be identified or legally/technically accessed with current information.

Current files:

- [official_sources.md](official_sources.md): human-readable technical documentation and verification notes.
- [urban_climate_la_seu.md](urban_climate_la_seu.md): official open sources checked for the La Seu d'Urgell urban climate poster.
- [sources_inventory.yml](sources_inventory.yml): structured inventory for future Data Engine work.
- [fire/incendiscat-official-source.md](fire/incendiscat-official-source.md): detailed trace for the IncendisCAT fire-source requirement.
