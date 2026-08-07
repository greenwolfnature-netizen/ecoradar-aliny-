"""Write validation records for Step 2 sources that cannot run automatically.

This is a data-engine artifact only. It does not download data, calculate
indicators, run diagnosis, or create visual reports.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
OUT_DIR = PROJECT / "metadata" / "validations"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_validation(filename: str, payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload.setdefault("project", "Alinya")
    payload.setdefault("validated_at", utc_now())
    payload.setdefault("can_advance_to_next_connector", True)
    path = OUT_DIR / filename
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def missing_env(names: list[str]) -> list[str]:
    return [name for name in names if not os.environ.get(name)]


def main() -> None:
    copernicus_missing = missing_env(["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"])
    meteocat_missing = missing_env(["METEOCAT_API_KEY"])
    aemet_missing = missing_env(["AEMET_API_KEY"])

    validations = {
        "connector_sigpac_validation.json": {
            "connector": "pending_sigpac_connector",
            "source": "SIGPAC Catalunya",
            "status": "blocked_pending_official_service_verification",
            "reason": "No hi ha cap endpoint vectorial oficial verificat i documentat dins el projecte per descarregar recintes SIGPAC per polígon. No es fa scraping del visor.",
            "required_action": "Verificar servei oficial FEGA/Generalitat, esquema de camps, llicència i via de descàrrega abans d'implementar el connector.",
            "outputs": {},
            "missing_outputs": ["processed/sigpac.gpkg", "metadata/sigpac_metadata.json"],
        },
        "connector_meteocat_validation.json": {
            "connector": "pending_meteocat_connector",
            "source": "Meteocat API",
            "status": "blocked_requires_credentials" if meteocat_missing else "ready_for_implementation",
            "reason": "Falta METEOCAT_API_KEY." if meteocat_missing else "Credencial disponible; connector pendent d'implementació.",
            "required_action": "Configurar METEOCAT_API_KEY i seleccionar endpoint/estació o producte de grid oficial.",
            "missing_credentials": meteocat_missing,
            "outputs": {},
            "missing_outputs": ["processed/clima/meteocat.csv", "metadata/clima_metadata.json"],
        },
        "connector_aemet_validation.json": {
            "connector": "pending_aemet_connector",
            "source": "AEMET OpenData",
            "status": "blocked_requires_credentials" if aemet_missing else "ready_for_implementation",
            "reason": "Falta AEMET_API_KEY." if aemet_missing else "Credencial disponible; connector pendent d'implementació.",
            "required_action": "Configurar AEMET_API_KEY i definir la consulta per estació/municipi/comarca o normals climàtiques.",
            "missing_credentials": aemet_missing,
            "outputs": {},
            "missing_outputs": ["processed/clima/aemet.csv"],
        },
        "connector_strava_heatmap_validation.json": {
            "connector": "blocked_strava_heatmap_connector",
            "source": "Strava Global Heatmap",
            "status": "not_implementable_without_authorization",
            "reason": "La font està condicionada legalment; EcoRadar no ha de fer scraping ni descarregar heatmaps sense permís o endpoint autoritzat.",
            "required_action": "Integrar només si existeix accés autoritzat, condicions d'ús compatibles i metadades de llicència.",
            "outputs": {},
            "missing_outputs": [],
        },
        "connector_mcsc_validation.json": {
            "connector": "pending_mcsc_connector",
            "source": "MCSC - Mapa de Cobertes del Sòl de Catalunya",
            "status": "blocked_pending_official_service_verification",
            "reason": "MCSC està documentat com a complement, però no hi ha endpoint/descàrrega oficial verificat al projecte amb llicència i versió.",
            "required_action": "Verificar font CREAF/MCSC oficial, format descarregable i llicència abans d'implementar.",
            "outputs": {},
            "missing_outputs": [],
        },
        "connector_bdbc_validation.json": {
            "connector": "pending_bdbc_connector",
            "source": "Banc de Dades de Biodiversitat de Catalunya",
            "status": "blocked_pending_official_access_verification",
            "reason": "No hi ha API/exportació automàtica verificada per polígon dins el projecte.",
            "required_action": "Confirmar amb BDBC/UB si hi ha exportació autoritzada per quadrícula o àrea i documentar llicència.",
            "outputs": {},
            "missing_outputs": [],
        },
        "connector_spei_validation.json": {
            "connector": "pending_spei_connector",
            "source": "SPEI Global Drought Monitor",
            "status": "blocked_pending_endpoint_schema_verification",
            "reason": "La font està identificada, però falta endpoint o descàrrega automatitzable, esquema de grid i llicència d'ús dins EcoRadar.",
            "required_action": "Documentar descàrrega oficial CSIC per coordenada/grid i implementar només després de verificar camps i resolució.",
            "outputs": {},
            "missing_outputs": [],
        },
        "connector_fieldwork_importer_validation.json": {
            "connector": "pending_fieldwork_importer",
            "source": "Dades pròpies de camp",
            "status": "not_available_no_project_dataset",
            "reason": "No s'ha proporcionat cap dataset de camp per Alinyà.",
            "required_action": "Crear plantilla CSV/GPKG/media i importar observacions validades quan existeixin.",
            "outputs": {},
            "missing_outputs": ["data/fieldwork"],
        },
        "connector_fuel_structure_validation.json": {
            "connector": "pending_fuel_structure_connector",
            "source": "Continuïtat forestal i combustible potencial",
            "status": "partial_proxy_only",
            "reason": "Existeix proxy local de condicions d'incendi, però no una font oficial de combustible/estructura forestal documentada i normalitzada com a connector.",
            "required_action": "Identificar font oficial forestal/combustible, separar descàrrega de l'anàlisi i generar capa normalitzada.",
            "outputs": {
                "proxy": "projectes/Alinya/processed/incendis_similarity/similitud_condicions_incendi_alinya.gpkg"
            },
            "missing_outputs": ["processed/fire/fuel_continuity.gpkg"],
        },
        "connector_icgc_base_cartography_validation.json": {
            "connector": "pending_base_cartography_icgc",
            "source": "Cartografia base i ortofoto ICGC",
            "status": "partial_product_maps_only",
            "reason": "Existeixen mapes PNG de context, però no un connector formal WMTS/WMS que descarregui i documenti ortofoto/topogràfic.",
            "required_action": "Crear connector de context cartogràfic si cal per a productes visuals; no és crític per al motor de dades vector/raster.",
            "outputs": {
                "base_map": "projectes/Alinya/maps/producte/mapa_base_alinya.png",
                "study_area_map": "projectes/Alinya/maps/producte/mapa_espai_alinya.png"
            },
            "missing_outputs": [],
        },
        "connector_copernicus_credentials_gate_validation.json": {
            "connector": "connector_copernicus_teledeteccio",
            "source": "Copernicus Data Space Sentinel-2 / LST",
            "status": "blocked_requires_credentials" if copernicus_missing else "ready_for_execution",
            "reason": "Falten credencials OAuth de Copernicus." if copernicus_missing else "Credencials disponibles; executar connector per descarregar rasters reals.",
            "required_action": "Configurar COPERNICUS_CLIENT_ID i COPERNICUS_CLIENT_SECRET; després executar connector Copernicus.",
            "missing_credentials": copernicus_missing,
            "outputs": {},
            "missing_outputs": [
                "processed/teledeteccio/ndvi.tif",
                "processed/teledeteccio/ndmi.tif",
                "processed/teledeteccio/ndwi.tif",
                "processed/teledeteccio/lst.tif",
            ],
        },
    }

    for filename, payload in validations.items():
        write_validation(filename, payload)

    print(json.dumps({"written": len(validations), "output_dir": str(OUT_DIR)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
