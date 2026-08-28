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
    assert isinstance(properties["missing"], list)
    assert "scientificName" not in properties
    assert "longitude" not in properties
    assert "latitude" not in properties
    assert "score" not in properties

for label in (
    "Valor ecològic destacable",
    "Sectors sota pressió",
    "Buits de coneixement",
    "Sectors recomanats per seguiment",
    "Per què EcoRadar ho assenyala?",
):
    assert label in html
assert 'data-bh-filter="value"' in html
assert 'data-bh-filter="pressure"' in html
assert 'data-bh-filter="knowledge"' in html
assert 'data-bh-filter="followup"' in html
assert "No suma punts ni afirma causalitat" in html

print("ALINYA_BIODIVERSITY_HABITAT_PILOT=PASS")
