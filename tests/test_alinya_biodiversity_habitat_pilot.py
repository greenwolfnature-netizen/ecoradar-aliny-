#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEOJSON = ROOT / "projectes" / "Alinya" / "indicators" / "biodiversity_habitat_pilot.geojson"
METADATA = ROOT / "projectes" / "Alinya" / "metadata" / "biodiversity_habitat_pilot_metadata.json"
HTML = ROOT / "projectes" / "Alinya" / "maps" / "ecoradar-alinya-netlify-v2" / "index.html"


features = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
metadata = json.loads(METADATA.read_text(encoding="utf-8"))
html = HTML.read_text(encoding="utf-8")

assert len(features) == 49
assert metadata["status"] == "pilot_qualitative"
assert "no són una quadrícula EcoRadar" in metadata["sector_unit"]
assert "coordenades" in metadata["privacy"]
assert "noms de taxons" in metadata["privacy"]

allowed = {
    "Sense senyals destacables",
    "Seguiment recomanat",
    "Atenció",
    "Prioritat de comprovació",
    "Coneixement insuficient",
}
for feature in features:
    properties = feature["properties"]
    assert properties["followup"] in allowed
    assert isinstance(properties["value_reasons"], list)
    assert isinstance(properties["pressure_reasons"], list)
    assert isinstance(properties["connectivity_reasons"], list)
    assert isinstance(properties["reading_coincidences"], list)
    assert isinstance(properties["possible_implications"], list)
    assert isinstance(properties["missing"], list)
    assert "scientificName" not in properties
    assert "longitude" not in properties
    assert "latitude" not in properties
    assert "score" not in properties

for label in (
    "Quadre de situació ecològica d’Alinyà",
    "Valor ecològic",
    "Sectors sota pressió",
    "Canvis detectats",
    "Connectivitat",
    "Buits de coneixement",
    "Seguiment prioritari",
    "Per què EcoRadar ho assenyala?",
):
    assert label in html
assert 'data-bh-filter="value"' in html
assert 'data-bh-filter="pressure"' in html
assert 'data-bh-filter="changes"' in html
assert 'data-bh-filter="connectivity"' in html
assert 'data-bh-filter="knowledge"' in html
assert 'data-bh-filter="followup"' in html
assert html.count('class="eu-biodiversity-situation" data-bh-pilot') == 1
assert "Informació insuficient per generar aquesta diagnosi." in html
assert metadata["diagnostic_availability"]["changes"]["available"] is False
assert metadata["counts"]["changes_detected"] == 0
assert metadata["counts"]["connectivity"] > 0
assert "No és una suma de punts" in html
for heading in (
    "Què hi ha",
    "Per què és rellevant",
    "Què està detectant EcoRadar",
    "Amb quines altres lectures coincideix",
    "Quina és la possible implicació ecològica",
    "Què no sabem",
    "Què convindria comprovar o seguir",
):
    assert heading in html
assert 'biodiversitySituation.hidden = !isBiodiversitySituation' in html
assert 'mapStack.hidden = isBiodiversitySituation' in html
assert 'Biodiversitat<small>quadre de situació ecològica</small>' in html

print("ALINYA_BIODIVERSITY_HABITAT_PILOT=PASS")
