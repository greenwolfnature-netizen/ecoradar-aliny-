from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "export_ecoradar_alinya_netlify.py"
GENERATED = ROOT / "index.html"


def _assert_stable_map_layout(text: str) -> None:
    text = text.replace("{{", "{").replace("}}", "}")
    assert "align-items:start; padding:10px; min-height:0" in text
    assert "height:clamp(440px,42vw,520px); min-height:0" in text
    assert ".eu-map-panel { height:420px; }" in text
    assert "const keepMapPosition = mapRectBefore.bottom > 0" in text
    assert "window.scrollBy(0, displacement)" in text


def test_generator_keeps_map_size_and_position_stable() -> None:
    _assert_stable_map_layout(GENERATOR.read_text(encoding="utf-8"))


def test_generated_viewer_contains_the_stability_fix() -> None:
    _assert_stable_map_layout(GENERATED.read_text(encoding="utf-8"))


def test_management_reading_explains_decisions_and_limits() -> None:
    text = GENERATOR.read_text(encoding="utf-8")
    assert "Cribratge de gestió · què cal fer?" in text
    assert "Aquest mapa no delimita actuacions" in text
    assert "Què no permet afirmar" in text
    assert "layers:['fires','access','hic','publicUse']" in text
    assert "layers:['fires','access','hic','biodiversity','publicUse']" not in text


def test_base_map_contains_roads_and_settlements() -> None:
    text = GENERATOR.read_text(encoding="utf-8")
    assert "eu-access.eu-road" in text
    assert "Poblacions OSM" in text
    assert "layers:['access','places']" in text
    assert "poblacions_osm.geojson" in text
