#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "projectes" / "Alinya"
HTML = BASE / "maps" / "ecoradar-alinya-netlify-v2" / "index.html"
ELEMENTS = BASE / "indicators" / "biodiversity_ecological_elements.geojson"
SITUATIONS = BASE / "indicators" / "biodiversity_ecological_situations.geojson"
KNOWLEDGE = BASE / "indicators" / "biodiversity_knowledge_coverage.geojson"
META = BASE / "metadata" / "biodiversity_ecology_metadata.json"

html = HTML.read_text(encoding="utf-8")
elements = json.loads(ELEMENTS.read_text(encoding="utf-8"))["features"]
situations = json.loads(SITUATIONS.read_text(encoding="utf-8"))["features"]
knowledge = json.loads(KNOWLEDGE.read_text(encoding="utf-8"))["features"]
metadata = json.loads(META.read_text(encoding="utf-8"))

assert metadata["status"] == "definitive_ecological_module"
assert len(elements) > 450 and len(situations) > 0 and len(knowledge) > 0
assert {f["properties"]["element_type"] for f in elements} == {"habitat", "connector", "value_overlap"}
assert {f["properties"]["situation_type"] for f in situations} == {"current_fire", "historic_fire"}
for feature in elements + situations + knowledge:
    assert feature["geometry"] and feature["geometry"]["coordinates"]
    for forbidden in ("scientificName", "commonName", "longitude", "latitude", "sector_id"):
        assert forbidden not in feature["properties"]
for feature in situations:
    props = feature["properties"]
    assert props["recommendation"] in {"comprovació de camp", "mantenir seguiment"}
    assert props["area_ha"] > 0 and props["why_flagged"] and props["structural"] and props["current"]
for feature in knowledge:
    props = feature["properties"]
    assert props["records"] >= 0 and props["fauna_records"] >= 0 and props["flora_records"] >= 0
    assert props["knowledge_class"] in {"Pràcticament sense dades", "Poca informació", "Informació moderada", "Més informació publicada"}

module = html.split('<section class="eu-biodiversity-situation" data-bh-pilot', 1)[1].split('</section>', 1)[0]
for label in ("Què hi ha?", "On és més rellevant?", "Com està?", "Què ens falta saber?"):
    assert label in module
assert module.count('data-bh-filter=') == 4
for forbidden in ("BH-01", "44 sectors", "26 coincidències", "39 sectors", "Els 49 sectors"):
    assert forbidden not in module
for required in ("Explorar hàbitats", "Fauna", "Flora", "Connectivitat", "HIC prioritaris", "Coincidència de valors", "Situació actual", "On tenim menys informació?", "Quins grups coneixem pitjor?", "On seria útil prospectar?", "Per què EcoRadar ho assenyala?"):
    assert required in html
assert "const ecology = D.biodiversityEcology" in html
assert "const features = D.biodiversityPilot.sectors.features" not in html
assert "eu-bh-sector" not in html
assert "Només generen diagnosi actual si la política de frescor les manté vigents" in html
assert "Informació insuficient per afirmar canvis ecològics temporals" in html

profiles = (ROOT / "vendor" / "ecoradar-alinya-report-profiles.js").read_text(encoding="utf-8")
chapters = ("Síntesi executiva", "Patrimoni biològic conegut", "Hàbitats", "Fauna i flora conegudes", "Elements de major interès", "Connectivitat", "Estat actual", "Canvis detectats", "Pressions", "Relació amb incendis", "Buits de coneixement", "Necessitats de seguiment i camp", "Conclusions de gestió", "Fonts, dates, limitacions i confiança")
for chapter in chapters:
    assert f"title:'{chapter}'" in profiles
assert "biodiversity-habitats" in (ROOT / "vendor" / "ecoradar-reading-report.js").read_text(encoding="utf-8")

print("ALINYA_BIODIVERSITY_HABITAT_DEFINITIVE=PASS")
