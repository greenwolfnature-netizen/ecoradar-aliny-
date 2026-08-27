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

for mode in ('base','habitats','biodiversity','vegetation','vigor','moisture','climateRefuges','temperature','albedo','management','fireDanger','fireCurrent','fires'):
    assert f"{mode}:" in profiles or f"{mode}:" in html, mode
for layer in ('access','publicUse','places','landcover'):
    assert f"{layer}:" in profiles, layer

print('ALINYA_READING_REPORTS=PASS')
