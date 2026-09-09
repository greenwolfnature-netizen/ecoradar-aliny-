"""Context-specific diagnosis text for the Alinyà Phase 2 CORE methodology."""

from __future__ import annotations

from typing import Any


def build_alinya_phase2_diagnosis(context: dict[str, Any]) -> list[dict[str, Any]]:
    by = context["by_code"]
    snapshot = context.get("indicators_payload", {}).get("snapshot_id")
    return [
        _conclusion(
            "situacio_actual", "Diagnosi amb lectures directes, perfils i portes de decisió",
            (
                "Els dotze RADAR ja no comparteixen una escala artificial. Al snapshot actual hi ha quatre resultats complets "
                "per a la dimensió exactament declarada, sis perfils parcials i dos resultats NO AVALUABLES. "
                "Aquesta distribució descriu aptitud de les dades, no qualitat ecològica del territori."
            ),
            "Llegir cada resultat segons el seu tipus i la seva vigència; cap perfil es pot convertir en una nota global de conservació.",
            tuple(by), _sources(*by.values()), _confidence(*by.values()),
            ("La confiança varia per RADAR i s’ha de consultar en les vuit dimensions publicades.",),
            "observació", "provisional", snapshot,
        ),
        _conclusion(
            "distribucio_territorial", "La configuració és forestal i la funció del mosaic depèn de l’objectiu",
            (
                f"{_primary(by['CORE_01'])}. La cartografia conté 6.994 taques, amb una taca màxima de "
                f"{_profile(by['CORE_01'], 'configuration', 'largest_patch_ha')} ha i mida efectiva de "
                f"{_profile(by['CORE_01'], 'configuration', 'effective_mesh_area_ha')} ha. Shannon, vora i nombre de taques "
                "es mantenen com a descriptors: no indiquen per si sols fragmentació perjudicial ni mosaic funcional."
            ),
            "Definir per hàbitat o procés quines continuïtats, clarianes i vores s’han de conservar abans d’ordenar actuacions de mosaic.",
            ("CORE_01",), _sources(by["CORE_01"]), by["CORE_01"]["confidence"],
            tuple(by["CORE_01"]["limitations"]), "observació + interpretació plausible", "provisional", snapshot,
        ),
        _conclusion(
            "valors_ecologics_principals", "Els HIC impliquen responsabilitat territorial, no estat favorable",
            (
                f"{_primary(by['CORE_02'])}. Aquestes superfícies i les presències puntuals documenten representació d’hàbitats. "
                "No existeixen encara dades locals suficients d’estructura, funcions, pressions i perspectives per classificar-ne l’estat de conservació."
            ),
            "Aplicar no-deteriorament i verificació d’hàbitat abans de qualsevol transformació; no interpretar més hectàrees com a millor estat.",
            ("CORE_02",), _sources(by["CORE_02"]), by["CORE_02"]["confidence"],
            tuple(by["CORE_02"]["limitations"]), "observació", "robusta per responsabilitat; provisional per estat", snapshot,
        ),
        _conclusion(
            "factors_explicatius", "L’NDVI descriu el 7 de juliol i no l’estat actual de setembre",
            (
                f"{_primary(by['CORE_03'])}. L’escena tenia {_profile(by['CORE_03'], 'valid_coverage_pct')} % de cobertura vàlida, "
                f"amb P10 {_profile(by['CORE_03'], 'p10')} i P90 {_profile(by['CORE_03'], 'p90')}. "
                "El valor és coherent amb una activitat verda desigual dins l’àmbit, però sense línia base per coberta i època "
                "no permet classificar vigor actual, anomalia fenològica o estat de conservació."
            ),
            "Esperar una nova escena QA-vàlida i comparar-la amb la mateixa època i coberta abans d’interpretar canvi o estrès.",
            ("CORE_03",), _sources(by["CORE_03"]), by["CORE_03"]["confidence"],
            tuple(by["CORE_03"]["limitations"]), "observació datada", "robusta per l’escena; no vigent per avui", snapshot,
        ),
        _conclusion(
            "vulnerabilitats", "Refugis i vulnerabilitat climàtica requereixen dues lectures diferents",
            (
                f"{_primary(by['CORE_04'])}. El 42,3 % és la proporció alta o molt alta dins el denominador vegetat amb LST, NDMI i NDVI vàlids; "
                "combina un compost tèrmic 2025–2026 amb una escena del 07/07/2026. CORE_05 retorna NO AVALUABLE perquè només hi ha context parcial "
                "d’exposició i falten sensibilitat i capacitat adaptativa definides per receptor."
            ),
            "Usar el mapa de refugi per seleccionar candidats a sensors o camp, i no per declarar refugis permanents o vulnerabilitat territorial.",
            ("CORE_04", "CORE_05"), _sources(by["CORE_04"], by["CORE_05"]), _confidence(by["CORE_04"], by["CORE_05"]),
            tuple(by["CORE_04"]["limitations"] + by["CORE_05"]["limitations"]), "interpretació plausible", "provisional", snapshot,
        ),
        _conclusion(
            "biodiversitat", "La informació biològica està distribuïda de manera desigual",
            (
                f"{_primary(by['CORE_06'])}. La consulta GBIF es va aturar al sostre de seguretat de 10.000 sobre 31.169 coincidències, "
                "i 18 de 84 cel·les d’1 km no tenen cap registre públic. Això identifica buits de coneixement i biaix d’esforç; "
                "no permet ordenar biodiversitat real ni interpretar absències."
            ),
            "Prioritzar prospecció a les cel·les amb poc coneixement que coincideixen amb HIC o connectors, amb un protocol comparable per grup i estació.",
            ("CORE_06",), _sources(by["CORE_06"]), by["CORE_06"]["confidence"],
            tuple(by["CORE_06"]["limitations"]), "observació", "provisional", snapshot,
        ),
        _conclusion(
            "connectivitat_i_us", "Accessibilitat i continuïtat estructural no demostren pressió ni moviment",
            (
                f"{_primary(by['CORE_07'])}; {_primary(by['CORE_08'])}. La xarxa OSM descriu potencial d’accés i els connectors descriuen continuïtat general. "
                "Sense freqüentació i impacte no hi ha pressió real; sense receptor, resistències i validació no hi ha connectivitat funcional."
            ),
            "Mesurar ús als trams que coincideixen amb valors sensibles i validar passos o barreres per receptors concrets abans de regular o restaurar corredors.",
            ("CORE_07", "CORE_08"), _sources(by["CORE_07"], by["CORE_08"]), _confidence(by["CORE_07"], by["CORE_08"]),
            tuple(by["CORE_07"]["limitations"] + by["CORE_08"]["limitations"]), "observació + hipòtesi", "provisional", snapshot,
        ),
        _conclusion(
            "aigua", "La xarxa hídrica és un inventari, no una lectura de disponibilitat actual",
            (
                f"{_primary(by['CORE_10'])}. Els elements localitzen on comprovar aigua, ribera i possible funció de refugi, però no informen de cabal, "
                "permanència, qualitat o ús per fauna. La seva absència a la capa tampoc prova absència al terreny."
            ),
            "Verificar les dotze fonts i trams seleccionats en període sec, documentant permanència, qualitat, ribera, pressions i sensibilitat.",
            ("CORE_10", "CORE_04"), _sources(by["CORE_10"], by["CORE_04"]), _confidence(by["CORE_10"], by["CORE_04"]),
            tuple(by["CORE_10"]["limitations"]), "observació", "provisional", snapshot,
        ),
        _conclusion(
            "foc", "El foc es presenta com un perfil de propagació, sensibilitat, recuperació i operativa",
            (
                f"{_primary(by['CORE_09'])}. El perill EcoRadar actual conserva la seva escala 0–100 perquè és un producte diari específic, "
                "i el Pla Alfa continua com a context oficial independent. La sensibilitat ecològica i la recuperació postincendi no són avaluables "
                "amb perímetres, camins i aigua cartografiada."
            ),
            "Vigilar vent, humitat, pluja i potencial ForestDrought; abans de tractaments, verificar combustible, hàbitats i sòl als sectors candidats.",
            ("CORE_09",), _sources(by["CORE_09"]), by["CORE_09"]["confidence"],
            tuple(by["CORE_09"]["limitations"]), "escenari potencial", "caduca amb la següent instantània diària", snapshot,
        ),
        _conclusion(
            "implicacions_gestio", "La síntesi manté prioritats per alternativa i rebutja una única nota global",
            (
                f"{_primary(by['CORE_12'])}. La regla preventiva sobre HIC és P1; prospecció, mesura d’ús, verificació hídrica i preparació davant del foc "
                "són P2. La restauració generalitzada queda vetada com a NO AVALUABLE perquè CORE_11 no disposa de degradació, referència, objectiu, benefici i viabilitat."
            ),
            "Aplicar la regla P1, programar les verificacions P2 i aprovar unitats/objectius abans d’ordenar alternatives no dominades.",
            ("CORE_11", "CORE_12"), _sources(by["CORE_11"], by["CORE_12"]), _confidence(by["CORE_11"], by["CORE_12"]),
            tuple(by["CORE_11"]["limitations"] + by["CORE_12"]["limitations"]), "síntesi de decisió", "robusta en els vetos; provisional en l’ordenació", snapshot,
        ),
    ]


def _conclusion(
    section: str, title: str, interpretation: str, management: str,
    indicators: tuple[str, ...], sources: tuple[str, ...], confidence: str,
    limitations: tuple[str, ...], evidence_type: str, robustness: str,
    snapshot_id: str | None,
) -> dict[str, Any]:
    return {
        "section": section,
        "title": title,
        "interpretation": interpretation,
        "management_implication": management,
        "supporting_indicators": indicators,
        "sources_used": sources,
        "confidence": confidence,
        "limitations": limitations,
        "robustness": robustness,
        "evidence_type": evidence_type,
        "snapshot_id": snapshot_id,
    }


def _primary(item: dict[str, Any]) -> str:
    return str(item.get("primary_result") or item.get("status") or "NO AVALUABLE")


def _profile(item: dict[str, Any], *keys: str) -> Any:
    current: Any = item.get("profile", {})
    for key in keys:
        current = current.get(key) if isinstance(current, dict) else None
    return current


def _sources(*items: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({source for item in items for source in item.get("sources_used", [])}))


def _confidence(*items: dict[str, Any]) -> str:
    values = {item.get("confidence") for item in items}
    if "baixa" in values:
        return "baixa"
    if "mitjana" in values:
        return "mitjana"
    return "alta"

