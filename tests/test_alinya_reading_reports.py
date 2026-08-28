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
assert 'html2pdf.bundle.min.js' in html
assert 'Desar informe en PDF' in html
assert "global.html2pdf().set(options).from(exportMarkup, 'string').save()" in engine
assert "replaceAll('#ecoradar-alinya ', '')" in engine
assert 'window.open' not in engine
assert 'print()' not in engine
assert (ROOT / 'vendor' / 'html2pdf.bundle.min.js').is_file()
assert (ROOT / 'vendor' / 'html2pdf.bundle.min.js.LICENSE.txt').is_file()
assert 'Context cartogràfic superposable' in html
assert 'id="eu-context-status"' in html
assert html.index('class="eu-map-panel"') < html.index('class="eu-panel eu-context-panel"')
assert 'class="eu-panel eu-reading-guide-horizontal"' in html
assert html.index('class="eu-map-panel"') < html.index('class="eu-panel eu-reading-guide-horizontal"') < html.index('class="eu-panel eu-context-panel"')
assert "activeGuide = {type:'mode', key:activeMode};" in html
assert "activeGuide = next ? {type:'layer'" not in html

required_sections = (
    'Què estem mesurant?',
    'Què ens aporta aquesta informació?',
    'Què ens diu la lectura d’Alinyà?',
    'Possibles causes i factors condicionants',
    'Creuament amb altres lectures EcoRadar',
    'Efectes en cadena',
    'Com pot evolucionar aquesta lectura?',
    'Conseqüències ecològiques',
    'Relació amb els incendis',
    'Sectors prioritaris',
    'Implicacions per a la gestió',
    'Conclusió integrada',
)
for heading in required_sections:
    assert heading in engine, heading

for heading in (
    'Diagnosi tècnica integrada',
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
assert "No equival a humitat fina del combustible" in profiles

extensions_start = profiles.index('const diagnosticExtensions')
extensions_end = profiles.index('const genericDiagnostic', extensions_start)
extensions = profiles[extensions_start:extensions_end]
for mode in ('base','habitats','biodiversity','vegetation','vigor','moisture','climateRefuges','temperature','albedo','management','fireDanger','fireCurrent','fires'):
    start = extensions.index(f"{mode}:{{")
    following = [extensions.find(f"\n      {other}:{{", start + 1) for other in ('base','habitats','biodiversity','vegetation','vigor','moisture','climateRefuges','temperature','albedo','management','fireDanger','fireCurrent','fires')]
    following = [position for position in following if position != -1]
    end = min(following) if following else len(extensions)
    block = extensions[start:end]
    for field in ('causes:','spatialAssessment:','evolution:','chainEffects:','prioritySectors:','managementImplications:','integratedConclusion:'):
        assert field in block, f"missing {field} in diagnostic extension {mode}"

albedo_start = extensions.index('albedo:{')
albedo_end = extensions.index('\n      climateRefuges:{', albedo_start)
albedo = extensions[albedo_start:albedo_end]
for phrase in ('creuament GIS cel·la a cel·la', 'Pla Alfa', 'propagació'):
    assert phrase.lower() in albedo.lower(), phrase
assert 'perill actual' in profiles.lower()

assert 'const genericDiagnostic' in profiles
assert "level:'observat'" in profiles
assert "level:'probable'" in profiles
assert "level:'potencial'" in profiles

print('ALINYA_READING_REPORTS=PASS')
