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
    "Biodiversitat i hàbitats",
    "Què hi ha?",
    "On és més rellevant?",
    "Com està?",
    "Què ens falta saber?",
    "Situació coneguda.",
    "Per què EcoRadar ho assenyala?",
):
    assert label in html
assert 'data-bh-filter="inventory"' in html
assert 'data-bh-filter="relevance"' in html
assert 'data-bh-filter="condition"' in html
assert 'data-bh-filter="knowledge"' in html
assert html.count('data-bh-filter=') == 4
assert html.count('class="eu-biodiversity-situation" data-bh-pilot') == 1
assert "Informació insuficient per generar aquesta diagnosi." in html
assert metadata["diagnostic_availability"]["changes"]["available"] is False
assert metadata["counts"]["changes_detected"] == 0
assert metadata["counts"]["connectivity"] > 0
assert "No és una suma de punts" in html
for heading in (
    "Què hi ha aquí?",
    "Per què és important?",
    "Com està?",
    "Hi ha alguna cosa que mereixi atenció?",
    "Què convindria fer?",
    "Veure diagnosi tècnica →",
):
    assert heading in html
assert 'biodiversitySituation.hidden = !isBiodiversitySituation' in html
assert 'mapStack.hidden = isBiodiversitySituation' in html
assert 'Biodiversitat<small>quadre de situació ecològica</small>' in html

profiles = (ROOT / "vendor" / "ecoradar-alinya-report-profiles.js").read_text(encoding="utf-8")
engine = (ROOT / "vendor" / "ecoradar-reading-report.js").read_text(encoding="utf-8")
for chapter in (
    "Patrimoni biològic conegut",
    "Elements i sectors ecològicament valuosos",
    "Connectivitat ecològica",
    "Estat actual dels elements de biodiversitat",
    "Canvis detectats i tendència",
    "Pressions i coincidències que mereixen atenció",
    "Relació amb el foc",
    "Buits de coneixement",
    "Sectors recomanats per al seguiment",
    "Necessitats de validació de camp",
    "Conclusions i implicacions per a la gestió",
    "Fonts, dates, limitacions i confiança",
):
    assert chapter in profiles
assert "biodiversity-habitats" in engine

print("ALINYA_BIODIVERSITY_HABITAT_PILOT=PASS")
