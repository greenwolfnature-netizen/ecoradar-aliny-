#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "index.html").read_text(encoding="utf-8")
engine = (ROOT / "vendor" / "ecoradar-reading-report.js").read_text(encoding="utf-8")
profiles = (ROOT / "vendor" / "ecoradar-alinya-report-profiles.js").read_text(encoding="utf-8")

assert 'data-generate-reading-report' in html
assert 'data-reading-report-modal' in html
assert 'data-reading-report-pdf' in html
assert 'getSelection:() => ({...activeGuide' in html
assert 'EcoRadarAlinyaReportProfiles.buildFactory' in html
assert 'window.open' in engine and 'print()' in engine
assert 'Context cartogràfic superposable' in html
assert 'id="eu-context-status"' in html
assert html.index('class="eu-map-panel"') < html.index('class="eu-panel eu-context-panel"')
assert "activeGuide = {type:'mode', key:activeMode};" in html
assert "activeGuide = next ? {type:'layer'" not in html

required_sections = (
    'Què estem mesurant?',
    'Què ens aporta aquesta informació?',
    'Què significa aquesta lectura en aquest espai?',
    'Com es relaciona amb la resta de lectures EcoRadar?',
    'Què pot passar si aquest indicador augmenta o disminueix?',
    'Quines conseqüències pot tenir sobre vegetació, fauna, hàbitats i processos ecològics?',
    'Es pot millorar? Com?',
    'Conclusions i implicacions per a la gestió.',
)
for heading in required_sections:
    assert heading in engine, heading

for heading in (
    'Diagnosi tècnica integrada',
    'Relacions ecològiques que cal contrastar',
    'Factors rellevants no verificats amb aquesta lectura',
):
    assert heading in engine, heading

for mode in ('base','habitats','biodiversity','vegetation','vigor','moisture','climateRefuges','temperature','albedo','management','fireDanger','fireCurrent','fires'):
    assert f"{mode}:" in profiles or f"{mode}:" in html, mode
for layer in ('access','publicUse','places','landcover'):
    assert f"{layer}:" in profiles, layer

for useful in ('habitats','biodiversity','vegetation','vigor','moisture','climateRefuges','temperature','albedo','fireDanger','fireCurrent','fires','management'):
    assert f"{useful}:{{contribution:" in profiles, f"missing specific interpretive chain: {useful}"

technical_profiles_start = profiles.index('const technicalProfiles')
for mode in ('base','habitats','biodiversity','vegetation','vigor','moisture','climateRefuges','temperature','albedo','management','fireDanger','fireCurrent','fires'):
    start = profiles.index(f"{mode}:{{", technical_profiles_start)
    end = profiles.find('\n      },', start)
    block = profiles[start:end if end != -1 else None]
    assert 'technicalSynthesis:' in block, f"missing technical synthesis: {mode}"
    assert 'crossRelations:' in block, f"missing ecological relations: {mode}"
    assert 'unverified:' in block, f"missing unverified factors: {mode}"

moisture_start = profiles.index('moisture:{', technical_profiles_start)
moisture_end = profiles.index('\n      temperature:{', moisture_start)
moisture = profiles[moisture_start:moisture_end]
assert "current_fire_danger" in moisture
assert "herbivoria" in moisture.lower()
assert "No es pot deduir la direcció només amb NDMI" in moisture

print('ALINYA_READING_REPORTS=PASS')
