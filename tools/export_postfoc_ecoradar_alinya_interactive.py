#!/usr/bin/env python3
"""Build the interactive EcoRadar fire sheet for Alinya.

This exporter does not connect to external services and does not run new
ecological analysis. It packages already generated EcoRadar layers and
indicators into a standalone HTML, following the interactive structure used by
EcoRadar Urba.
"""

from __future__ import annotations

import csv
import html
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
OUT = PROJECT / "maps" / "ecoradar_memoria_foc_alinya_interactiu.html"

W, H = 1040, 760
PAD = 34


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def iter_coords(obj):
    if obj is None:
        return
    if isinstance(obj, (list, tuple)) and obj and isinstance(obj[0], (int, float)):
        yield float(obj[0]), float(obj[1])
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            yield from iter_coords(item)


def geom_bounds(geojson: dict) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for feature in geojson.get("features", []):
        for x, y in iter_coords(feature.get("geometry", {}).get("coordinates")):
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def make_projector(bounds: tuple[float, float, float, float]):
    minx, miny, maxx, maxy = bounds
    bw = maxx - minx
    bh = maxy - miny
    scale = min((W - PAD * 2) / bw, (H - PAD * 2) / bh)
    ox = (W - bw * scale) / 2
    oy = (H - bh * scale) / 2

    def project(x: float, y: float) -> tuple[float, float]:
        return ox + (x - minx) * scale, H - (oy + (y - miny) * scale)

    return project


def decimate(points: list[list[float]], max_points: int) -> list[list[float]]:
    if len(points) <= max_points:
        return points
    step = max(1, math.ceil(len(points) / max_points))
    reduced = points[::step]
    if reduced[-1] != points[-1]:
        reduced.append(points[-1])
    return reduced


def ring_to_path(ring: list[list[float]], project, max_points: int = 180) -> str:
    pts = decimate(ring, max_points)
    if not pts:
        return ""
    projected = [project(float(x), float(y)) for x, y, *_ in pts]
    parts = [f"M{projected[0][0]:.1f},{projected[0][1]:.1f}"]
    parts.extend(f"L{x:.1f},{y:.1f}" for x, y in projected[1:])
    parts.append("Z")
    return " ".join(parts)


def line_to_path(line: list[list[float]], project, max_points: int = 220) -> str:
    pts = decimate(line, max_points)
    if not pts:
        return ""
    projected = [project(float(x), float(y)) for x, y, *_ in pts]
    parts = [f"M{projected[0][0]:.1f},{projected[0][1]:.1f}"]
    parts.extend(f"L{x:.1f},{y:.1f}" for x, y in projected[1:])
    return " ".join(parts)


def geom_to_path(geom: dict, project, max_points: int = 180) -> str:
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Polygon":
        return " ".join(ring_to_path(ring, project, max_points) for ring in coords)
    if gtype == "MultiPolygon":
        return " ".join(
            ring_to_path(ring, project, max_points)
            for poly in coords
            for ring in poly
        )
    if gtype == "LineString":
        return line_to_path(coords, project, max_points)
    if gtype == "MultiLineString":
        return " ".join(line_to_path(line, project, max_points) for line in coords)
    return ""


def centroid(geom: dict, project) -> tuple[float, float]:
    pts = list(iter_coords(geom.get("coordinates")))
    if not pts:
        return 0.0, 0.0
    x = sum(p[0] for p in pts) / len(pts)
    y = sum(p[1] for p in pts) / len(pts)
    return project(x, y)


def fmt_float(value: str | float | int | None, digits: int = 1) -> str:
    if value in (None, ""):
        return "n/d"
    return f"{float(value):.{digits}f}".replace(".", ",")


def pct(value: float) -> str:
    return f"{value:.1f} %".replace(".", ",")


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def path_el(d: str, cls: str, tip: str = "", attrs: str = "") -> str:
    tip_attr = f' data-tip="{esc(tip)}"' if tip else ""
    return f'<path class="{cls}" d="{d}"{tip_attr} {attrs}/>'


def circle_el(x: float, y: float, r: float, cls: str, tip: str = "") -> str:
    tip_attr = f' data-tip="{esc(tip)}"' if tip else ""
    return f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="{r}"{tip_attr}/>'


def build_layers(project) -> tuple[str, dict]:
    study = read_json(PROJECT / "maps" / "ecoradar_core" / "study_area.geojson")
    fires = read_json(PROJECT / "maps" / "incendis" / "incendis_historics_alinya_clip.geojson")
    sim = read_json(PROJECT / "maps" / "incendis_similarity" / "similitud_condicions_incendi_alinya.geojson")
    habitats = read_json(PROJECT / "maps" / "ecoradar_core" / "habitats_hic.geojson")
    biodiv = read_json(PROJECT / "maps" / "ecoradar_core" / "biodiversitat_registres.geojson")
    access = read_json(PROJECT / "maps" / "ecoradar_core" / "pressio_humana_osm_camins.geojson")
    public_points = read_json(PROJECT / "maps" / "ecoradar_core" / "pressio_humana_osm_punts.geojson")

    study_paths = []
    for feat in study["features"]:
        d = geom_to_path(feat["geometry"], project, 700)
        study_paths.append(path_el(d, "layer-boundary", "Límit Muntanya d'Alinyà"))

    sim_paths = []
    sim_counts: dict[str, int] = {}
    for feat in sim["features"]:
        p = feat["properties"]
        cls = str(p.get("classe_similitud", "sense_dada"))
        sim_counts[cls] = sim_counts.get(cls, 0) + 1
        d = geom_to_path(feat["geometry"], project, 16)
        tip = (
            f"Concurrència {cls.replace('_', '-')}; "
            f"pendent {fmt_float(p.get('slope_deg'), 0)}°; "
            f"orientació {p.get('aspect_class', 'n/d')}; "
            f"coberta {p.get('cover_group', 'n/d')}; "
            f"accés {fmt_float(p.get('distance_to_access_m'), 0)} m"
        )
        sim_paths.append(path_el(d, f"sim sim-{cls}", tip))

    hic_paths = []
    hic_features = 0
    prior_features = 0
    for feat in habitats["features"]:
        p = feat["properties"]
        is_hic = p.get("COD_HIC") not in (None, "", "-")
        is_prior = str(p.get("HIC_PRIOR") or "").strip().lower() in {"1", "true", "si", "sí", "yes"}
        if not is_hic and not is_prior:
            continue
        hic_features += 1
        prior_features += int(is_prior)
        d = geom_to_path(feat["geometry"], project, 120)
        name = p.get("CORINE_CA") or "Hàbitat cartografiat"
        tip = f"HIC {p.get('COD_HIC', 'n/d')}; {name[:140]}"
        hic_paths.append(path_el(d, "hic hic-prior" if is_prior else "hic", tip))

    access_paths = []
    for feat in access["features"]:
        p = feat["properties"]
        highway = p.get("highway") or "camí"
        length = fmt_float(p.get("length_km"), 2)
        d = geom_to_path(feat["geometry"], project, 240)
        access_paths.append(path_el(d, f"access access-{esc(highway)}", f"{highway}; {length} km"))

    fire_paths = []
    fire_labels = []
    for feat in fires["features"]:
        p = feat["properties"]
        d = geom_to_path(feat["geometry"], project, 500)
        year = p.get("any_foc") or p.get("etiqueta_foc") or "n/d"
        area = fmt_float(p.get("area_ha_dins_alinya"), 1)
        tip = f"Incendi oficial {year}; {area} ha dins l'àmbit; {p.get('font', '')}"
        fire_paths.append(path_el(d, "fire", tip))
        cx, cy = centroid(feat["geometry"], project)
        fire_labels.append(f'<text class="fire-label" x="{cx:.1f}" y="{cy:.1f}">{esc(year)}</text>')

    biodiv_points = []
    groups: dict[str, int] = {}
    for feat in biodiv["features"]:
        p = feat["properties"]
        coords = feat["geometry"]["coordinates"]
        x, y = project(float(coords[0]), float(coords[1]))
        group = str(p.get("taxonGroup") or "Altres")
        groups[group] = groups.get(group, 0) + 1
        name = p.get("scientificName") or "Registre"
        source = p.get("source") or "font pública"
        biodiv_points.append(circle_el(x, y, 2.6, f"bio bio-{esc(group)}", f"{name}; {group}; {source}"))

    public_point_els = []
    for feat in public_points["features"]:
        p = feat["properties"]
        coords = feat["geometry"]["coordinates"]
        x, y = project(float(coords[0]), float(coords[1]))
        label = p.get("name") or p.get("tourism") or p.get("amenity") or "Punt d'ús públic"
        public_point_els.append(circle_el(x, y, 4.2, "public-point", label))

    layers = f"""
      <g id="layer-similarity" data-layer="similarity">{''.join(sim_paths)}</g>
      <g id="layer-hic" data-layer="hic">{''.join(hic_paths)}</g>
      <g id="layer-access" data-layer="access">{''.join(access_paths)}</g>
      <g id="layer-biodiversity" data-layer="biodiversity">{''.join(biodiv_points)}</g>
      <g id="layer-public" data-layer="public">{''.join(public_point_els)}</g>
      <g id="layer-fires" data-layer="fires">{''.join(fire_paths)}{''.join(fire_labels)}</g>
      <g id="layer-boundary">{''.join(study_paths)}</g>
    """
    counts = {
        "similarity": sim_counts,
        "hic_features": hic_features,
        "hic_prior_features": prior_features,
        "biodiversity_groups": groups,
    }
    return layers, counts


def build_metrics() -> dict:
    core_payload = read_json(PROJECT / "indicators" / "ecoradar_core_indicators.json")
    if core_payload.get("methodology_version") != "alinya_core_v2_2026-09-09":
        raise RuntimeError(
            "El visor d'Alinyà requereix la metodologia alinya_core_v2_2026-09-09; "
            "s'ha bloquejat la generació d'un artefacte CORE 0–100 antic."
        )
    core = core_payload.get("indicators", [])
    inc = read_csv_dicts(PROJECT / "indicators" / "incendis_resum.csv")
    sim = read_csv_dicts(PROJECT / "indicators" / "incendis_similarity" / "similitud_condicions_resum.csv")
    covers = read_csv_dicts(PROJECT / "indicators" / "cobertes_sol_resum.csv")
    recs = read_csv_dicts(PROJECT / "recommendations" / "priority_matrix.csv")
    study = read_json(PROJECT / "metadata" / "study_area_metadata.json")

    core_items = [
        {
            "code": r["code"],
            "name": r["name"],
            "display": r.get("primary_result") or "NO AVALUABLE",
            "measurementKind": r.get("measurement_kind"),
            "category": r["category"],
            "status": r["status"],
            "confidence": r["confidence"],
            "interpretation": r.get("interpretation_short", ""),
            "limit": "; ".join(r.get("limitations", [])),
        }
        for r in core
    ]
    inc_metrics = {r["metric"]: r["value"] for r in inc}
    sim_metrics = {r["metric"]: float(r["value"]) for r in sim}
    cover_metrics = {r["tipus_coberta"]: float(r["superficie_ha"]) for r in covers}
    study_ha = float(study["surface_ha"])
    high_plus = sim_metrics.get("area_ha_alta", 0) + sim_metrics.get("area_ha_mitjana_alta", 0)
    forest_like = sum(
        v
        for k, v in cover_metrics.items()
        if any(token in k.lower() for token in ["bosc", "boscos", "matollar"])
    )
    open_like = sum(
        v
        for k, v in cover_metrics.items()
        if any(token in k.lower() for token in ["prats", "conreus"])
    )
    recommendations = [
        {
            "id": r["id"],
            "title": r["title"],
            "group": r["group"],
            "justification": r["ecological_justification"],
            "priorityClass": r["priority_class"],
            "decisionStatus": r["decision_status"],
            "confidence": r["confidence"],
        }
        for r in recs
    ]
    by_code = {item["code"]: item for item in core}
    biodiversity = by_code["CORE_06"]["profile"]
    access = by_code["CORE_07"]["profile"]
    core12 = by_code["CORE_12"]["profile"]
    return {
        "methodologyVersion": core_payload.get("methodology_version"),
        "snapshotId": core_payload.get("snapshot_id"),
        "core": core_items,
        "summary": {
            "studyHa": study_ha,
            "fires": int(float(inc_metrics["gencat_fire_polygons"])),
            "burnedHa": float(inc_metrics["gencat_burned_area_ha"]),
            "burnedPct": float(inc_metrics["gencat_burned_area_ha"]) / study_ha * 100,
            "concurrenceHighHa": high_plus,
            "concurrenceHighPct": high_plus / study_ha * 100,
            "concurrenceMediumHa": sim_metrics.get("area_ha_mitjana", 0),
            "forestLikeHa": forest_like,
            "forestLikePct": forest_like / study_ha * 100,
            "openLikeHa": open_like,
            "openLikePct": open_like / study_ha * 100,
            "records": biodiversity["records_normalized"],
            "knowledgeCells": biodiversity["knowledge_grid_1km"]["cells"],
            "knowledgeCellsWithRecords": biodiversity["knowledge_grid_1km"]["cells_with_records"],
            "pathsKm": access["mapped_network_km"],
            "pathDensity": access["mapped_network_density_km_km2"],
            "publicPoints": access["mapped_use_points"],
            "hicHa": 3170.95,
            "hicPriorHa": 1229.39,
            "managementResult": core12["result"],
        },
        "recommendations": recommendations,
    }


def render_html(svg_layers: str, metrics: dict, counts: dict) -> str:
    data_json = json.dumps({"metrics": metrics, "counts": counts}, ensure_ascii=False)
    green_wolf_logo = "../assets/branding/green_wolf_nature_logo.png"
    ecoradar_logo = "../assets/branding/ecoradar_logo.png"
    return f"""<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EcoRadar · Memòria del foc · Alinyà</title>
<style>
:root {{
  --green-900:#163f35; --green-700:#276a48; --green-500:#6fa06a;
  --ink:#1f2a27; --muted:#65736d; --line:#d7ded6; --paper:#f6f5ef;
  --warn:#c56b2d; --fire:#b83b31; --blue:#2f6f93;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#e9ece5; color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.app {{ min-height:100vh; display:grid; grid-template-rows:auto 1fr auto; }}
header {{ display:grid; grid-template-columns:auto 1fr minmax(280px, 34vw); gap:18px; align-items:center; padding:18px 24px; background:var(--green-900); color:#fff; border-bottom:4px solid #a7bf75; }}
.brand-logos {{ display:flex; gap:10px; align-items:center; background:#fff; border:1px solid rgba(255,255,255,.55); padding:8px 10px; min-height:70px; }}
.brand-logos img {{ display:block; max-height:52px; max-width:128px; object-fit:contain; }}
h1 {{ margin:0; font-size:clamp(28px, 4vw, 48px); line-height:.95; letter-spacing:0; }}
.subtitle {{ margin:8px 0 0; color:#dce9df; font-size:15px; }}
.key {{ align-self:stretch; border:1px solid rgba(255,255,255,.34); padding:12px 14px; background:rgba(255,255,255,.08); }}
.key b {{ display:block; font-size:12px; letter-spacing:.08em; margin-bottom:6px; color:#cfe4c6; }}
.key span {{ font-size:15px; line-height:1.35; }}
.shell {{ display:grid; grid-template-columns:330px minmax(520px,1fr) 380px; gap:14px; padding:14px; min-height:0; }}
aside, .map-wrap {{ background:var(--paper); border:1px solid var(--line); box-shadow:0 8px 28px rgba(28,43,35,.08); }}
aside {{ padding:14px; overflow:auto; }}
.map-wrap {{ position:relative; min-height:760px; display:grid; grid-template-rows:auto auto auto; overflow:hidden; align-self:start; }}
h2 {{ margin:0 0 10px; font-size:17px; color:var(--green-900); }}
h3 {{ margin:14px 0 8px; font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--green-700); }}
p {{ margin:0 0 10px; line-height:1.42; font-size:14px; }}
.muted {{ color:var(--muted); }}
.tabs, .buttons {{ display:grid; gap:8px; }}
.tab, .layer-btn, .zoom-btn {{ border:1px solid #cbd7ce; background:#fff; color:var(--ink); padding:10px 11px; font:inherit; text-align:left; cursor:pointer; }}
.tab.active, .layer-btn.active {{ border-color:var(--green-700); background:#e4efe3; color:var(--green-900); font-weight:700; }}
.layer-btn.off {{ opacity:.5; }}
.layer-btn small {{ display:block; color:var(--muted); font-weight:500; margin-top:2px; }}
.reading-card {{ margin:10px 0 0; border:1px solid #cbd7ce; background:#fff; padding:11px; }}
.reading-card b {{ display:block; color:var(--green-900); margin-bottom:5px; }}
.reading-card ul {{ margin:7px 0 0 17px; padding:0; }}
.reading-card li {{ margin:4px 0; font-size:13px; line-height:1.35; }}
.facts {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
.fact {{ background:#fff; border:1px solid var(--line); padding:10px; min-height:72px; }}
.fact span {{ display:block; font-size:12px; color:var(--muted); line-height:1.2; }}
.fact strong {{ display:block; margin-top:5px; font-size:20px; color:var(--green-900); }}
.map-head {{ display:grid; grid-template-columns:1fr auto; gap:12px; align-items:center; padding:12px 14px; border-bottom:1px solid var(--line); }}
.map-title {{ font-weight:800; color:var(--green-900); }}
.map-subtitle {{ font-size:13px; color:var(--muted); margin-top:2px; }}
.zoom-controls {{ display:flex; gap:6px; }}
.zoom-btn {{ padding:8px 10px; font-weight:700; text-align:center; min-width:38px; }}
svg {{ width:100%; height:100%; display:block; background:#edf0e8; }}
.map-stage {{ position:relative; height:clamp(560px, 68vh, 760px); min-height:0; }}
.tooltip {{ position:absolute; display:none; max-width:300px; pointer-events:none; z-index:5; background:#10251f; color:#fff; border:1px solid rgba(255,255,255,.24); padding:8px 10px; font-size:12px; line-height:1.35; box-shadow:0 12px 26px rgba(0,0,0,.22); }}
.legend {{ display:grid; grid-template-columns:repeat(4, minmax(120px,1fr)); gap:8px 14px; padding:10px 14px 12px; border-top:1px solid var(--line); background:#fbfaf5; font-size:14px; }}
.legend div {{ display:flex; align-items:center; gap:7px; min-width:0; }}
.swatch {{ width:18px; height:12px; border:1px solid rgba(0,0,0,.22); flex:0 0 auto; }}
.layer-boundary {{ fill:none; stroke:#173d33; stroke-width:3.6; vector-effect:non-scaling-stroke; }}
.sim {{ stroke:rgba(60,70,55,.16); stroke-width:.5; cursor:pointer; }}
.sim-alta {{ fill:#b84c35; fill-opacity:.72; }}
.sim-mitjana_alta {{ fill:#d79042; fill-opacity:.62; }}
.sim-mitjana {{ fill:#e2cf7c; fill-opacity:.48; }}
.sim-baixa {{ fill:#dbe5d2; fill-opacity:.38; }}
.hic {{ fill:#2f7b50; fill-opacity:.28; stroke:#1d5e3c; stroke-width:.8; vector-effect:non-scaling-stroke; cursor:pointer; }}
.hic-prior {{ fill:#154e37; fill-opacity:.36; stroke:#102f24; stroke-width:1.2; }}
.access {{ fill:none; stroke:#5d675f; stroke-opacity:.74; stroke-width:1.2; vector-effect:non-scaling-stroke; cursor:pointer; }}
.access-track, .access-path {{ stroke:#746954; stroke-dasharray:4 3; }}
.fire {{ fill:#bf4033; fill-opacity:.25; stroke:#a42220; stroke-width:2.4; vector-effect:non-scaling-stroke; cursor:pointer; }}
.fire-label {{ font-size:18px; font-weight:900; fill:#7d1c19; paint-order:stroke; stroke:#fff; stroke-width:4; text-anchor:middle; dominant-baseline:middle; pointer-events:none; }}
.bio {{ fill:#2d72a0; fill-opacity:.72; stroke:#fff; stroke-width:.8; vector-effect:non-scaling-stroke; cursor:pointer; }}
.public-point {{ fill:#1f2a27; stroke:#fff; stroke-width:1.5; vector-effect:non-scaling-stroke; cursor:pointer; }}
.hidden {{ display:none; }}
.mode-foc .sim-mitjana, .mode-foc .sim-baixa {{ fill-opacity:.16; }}
.mode-foc .sim-alta {{ fill-opacity:.86; stroke:#6f1915; stroke-width:1.2; vector-effect:non-scaling-stroke; }}
.mode-foc .sim-mitjana_alta {{ fill-opacity:.78; stroke:#87512a; stroke-width:.9; vector-effect:non-scaling-stroke; }}
.mode-foc .fire {{ fill-opacity:.36; stroke-width:3.4; }}
.mode-foc .access {{ stroke-opacity:.92; stroke-width:1.6; }}
.mode-gestio .sim {{ fill-opacity:.18; }}
.mode-gestio .hic {{ fill-opacity:.42; stroke-width:1.3; }}
.mode-gestio .hic-prior {{ fill-opacity:.5; stroke-width:1.6; }}
.mode-gestio .bio {{ r:3.2; fill-opacity:.86; }}
.mode-gestio .public-point {{ r:5; }}
.radar-wrap {{ background:#fff; border:1px solid var(--line); padding:10px; }}
.radar-grid {{ fill:none; stroke:#dce3dc; stroke-width:1; }}
.radar-axis {{ stroke:#b9c6bd; stroke-width:1; }}
.radar-poly {{ fill:#2f7b50; fill-opacity:.24; stroke:#1f6b49; stroke-width:2; }}
.indicator {{ display:grid; grid-template-columns:minmax(0,1fr); gap:7px; align-items:start; border-bottom:1px solid #e0e6df; padding:9px 0; }}
.indicator:last-child {{ border-bottom:0; }}
.indicator b {{ font-size:13px; }}
.indicator span {{ color:var(--muted); font-size:12px; }}
.pill {{ display:inline-flex; align-items:center; justify-content:flex-start; max-width:100%; padding:5px 7px; border:1px solid #cdd8d0; background:#fff; font-weight:800; color:var(--green-900); font-size:12px; line-height:1.25; white-space:normal; }}
.decision {{ background:#fff; border-left:4px solid var(--green-700); padding:10px; margin:8px 0; }}
.decision b {{ display:block; font-size:13px; color:var(--green-900); margin-bottom:4px; }}
.limit {{ border:1px solid #d5b08c; background:#fff7ed; padding:12px; }}
.sources {{ font-size:12px; color:var(--muted); line-height:1.45; }}
footer {{ padding:10px 16px; font-size:12px; color:#57645f; background:#f4f3ed; border-top:1px solid var(--line); display:flex; justify-content:space-between; gap:18px; }}
@media (max-width:1180px) {{
  .shell {{ grid-template-columns:1fr; }}
  .map-wrap {{ min-height:680px; }}
  header {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>
<div class="app" id="ecoradar-foc-alinya">
  <header>
    <div class="brand-logos" aria-label="Logos Green Wolf i EcoRadar">
      <img src="{green_wolf_logo}" alt="Green Wolf Nature">
      <img src="{ecoradar_logo}" alt="EcoRadar">
    </div>
    <div>
      <h1>MEMÒRIA DEL FOC</h1>
      <p class="subtitle">Muntanya d'Alinyà · fitxa interactiva postfoc EcoRadar</p>
    </div>
    <div class="key"><b>MISSATGE CLAU</b><span>El senyal principal no és la superfície cremada, sinó la coincidència entre continuïtat bosc-matollar, accessibilitat i condicions topogràfiques semblants als focs històrics.</span></div>
  </header>

  <main class="shell">
    <aside>
      <h2>Lectura</h2>
      <div class="tabs">
        <button class="tab active" data-mode="diagnosi">Diagnosi ecològica</button>
        <button class="tab" data-mode="foc">Foc i concurrència</button>
        <button class="tab" data-mode="gestio">Decisions de gestió</button>
      </div>
      <div class="reading-card" id="mode-reading"></div>
      <h3>Capes</h3>
      <div class="buttons">
        <button class="layer-btn active" data-layer="similarity">Concurrència territorial<small>pendent, orientació, altitud, coberta i accessos</small></button>
        <button class="layer-btn active" data-layer="fires">Incendis oficials<small>perímetres històrics dins l'àmbit</small></button>
        <button class="layer-btn active" data-layer="access">Accessibilitat<small>camins i pistes OSM processats</small></button>
        <button class="layer-btn" data-layer="hic">Hàbitats HIC<small>hàbitats d'interès comunitari cartografiats</small></button>
        <button class="layer-btn" data-layer="biodiversity">Coneixement de biodiversitat<small>registres públics GBIF/iNaturalist; no biodiversitat real</small></button>
        <button class="layer-btn" data-layer="public">Ús públic<small>punts OSM d'informació i ús</small></button>
      </div>
      <h3>Indicadors crítics</h3>
      <div class="facts" id="left-facts"></div>
      <h3>Límit metodològic</h3>
      <div class="limit">
        <p><strong>No és un mapa oficial de probabilitat d'incendi.</strong> És una lectura de concurrència territorial amb dades EcoRadar ja processades.</p>
        <p>CORE_09 manté separats propagació actual, sensibilitat ecològica, recuperació postincendi i context operatiu. La recuperació continua NO AVALUABLE.</p>
      </div>
    </aside>

    <section class="map-wrap">
      <div class="map-head">
        <div>
          <div class="map-title" id="mode-title">Diagnosi ecològica postfoc</div>
          <div class="map-subtitle" id="mode-copy">Mapa de concurrència territorial i capes de decisió.</div>
        </div>
        <div class="zoom-controls">
          <button class="zoom-btn" data-zoom="in">+</button>
          <button class="zoom-btn" data-zoom="out">−</button>
          <button class="zoom-btn" data-zoom="reset">100</button>
        </div>
      </div>
      <div class="map-stage">
        <div class="tooltip" id="tooltip"></div>
        <svg id="map" viewBox="0 0 {W} {H}" role="img" aria-label="Mapa interactiu EcoRadar Memòria del foc Alinyà">
          <rect width="{W}" height="{H}" fill="#eef1e8"/>
          <g id="viewport">
            {svg_layers}
          </g>
        </svg>
      </div>
      <div class="legend" id="legend"></div>
    </section>

    <aside>
      <h2>RADAR EcoRadar · Fase 2</h2>
      <div class="radar-wrap">
        <div id="radar" aria-label="Resultats dels RADAR EcoRadar Fase 2"></div>
      </div>
      <h3>Argumentari</h3>
      <div id="argumentary"></div>
      <h3>Decisions</h3>
      <div id="decisions"></div>
      <h3>Fonts</h3>
      <p class="sources">Fonts consultades en el projecte: Generalitat de Catalunya WFS VEGETACIO:VEGETACIO_INCENDIS per perímetres històrics, ICGC cobertes del sòl i DEM, Hàbitats terrestres i HIC, ACA hidrologia, GBIF/iNaturalist, OpenStreetMap i Infraestructura Verda. Resultats vinculats a <span id="methodology"></span>.</p>
    </aside>
  </main>

  <footer>
    <span>EcoRadar · Memòria del foc · Alinyà</span>
    <span>Dades incrustades localment; sense connectors ni peticions externes</span>
  </footer>
</div>
<script>
const DATA = {data_json};
const MODES = {{
  diagnosi: {{
    title: "Diagnosi ecològica postfoc",
    copy: "La lectura combina incendis històrics, concurrència de condicions, hàbitats, accessibilitat i indicadors EcoRadar.",
    layers: ["similarity", "fires", "access"],
    readingTitle: "Què mostra aquesta lectura",
    reading: [
      "Manté visibles concurrència, incendis i accessos per veure el patró territorial principal.",
      "Els tons vermell i taronja assenyalen coincidència alta o mitjana-alta de condicions, no risc oficial.",
      "La pregunta és si els focs històrics comparteixen una lògica espacial repetible."
    ],
    arguments: [
      "L'àmbit té una matriu clarament forestal: bosc i matollar representen aproximadament el 90,6 % de la superfície processada.",
      "Els dos perímetres oficials sumen 17,4 ha dins l'àmbit; aquesta dada és un antecedent i no avalua per si sola la recuperació o la necessitat d'intervenir.",
      "La concurrència alta o mitjana-alta ocupa 2.437,5 ha, un 44,6 % de l'àmbit, i identifica on coincideixen condicions semblants als focs observats."
    ]
  }},
  foc: {{
    title: "Foc i concurrència territorial",
    copy: "La capa de concurrència no prediu ignicions; mostra on el territori s'assembla als llocs ja cremats segons variables disponibles.",
    layers: ["similarity", "fires", "access", "public"],
    readingTitle: "On mirar primer",
    reading: [
      "En aquesta lectura s'emfatitzen les cel·les alta i mitjana-alta i els perímetres oficials.",
      "Els accessos i punts d'ús públic ajuden a interpretar ignició potencial i vigilància, però no proven causa.",
      "Les zones clares queden en segon pla perquè aporten menys concurrència amb el patró observat."
    ],
    arguments: [
      "La lectura més robusta és estructural: continuïtat de combustible, accessibilitat i topografia poden repetir patrons locals.",
      "Les zones en vermell i taronja han de ser candidates a verificació de combustible, humitat i ús real, no a actuació automàtica.",
      "NDMI i LST disponibles no tenen la vigència necessària per descriure l'estat actual; el Pla Alfa es manté com a context oficial independent."
    ]
  }},
  gestio: {{
    title: "Decisions de gestió",
    copy: "CORE_12 mostra alternatives concretes per sector, amb vetos i sense una prioritat territorial única.",
    layers: ["similarity", "fires", "access", "hic", "biodiversity", "public"],
    readingTitle: "Què condiciona la decisió",
    reading: [
      "S'activen HIC, biodiversitat i ús públic perquè la prevenció del foc no pot contradir valors ecològics.",
      "La concurrència queda com a fons: orienta la prioritat, però la decisió final depèn de camp i combustible.",
      "El resultat útil és distingir la regla preventiva P1, les verificacions P2 i la porta de restauració NO AVALUABLE."
    ],
    arguments: [
      "La proporció d'espais oberts i la densitat de vores són descriptors; el seu signe depèn del receptor, el procés i l'objectiu ecològic.",
      "Les coincidències de foc, coberta, relleu i accés orienten comprovacions de camp, no actuacions territorials automàtiques.",
      "Els HIC activen una regla preventiva de no-deteriorament; els connectors descriuen continuïtat estructural, no moviment demostrat d'espècies."
    ]
  }}
}};
const DECISIONS = DATA.metrics.recommendations;
const LAYERS = {{
  similarity: [["#b84c35","Concurrència alta"],["#d79042","Concurrència mitjana-alta"],["#e2cf7c","Concurrència mitjana"],["#dbe5d2","Concurrència baixa"]],
  fires: [["#bf4033","Perímetres oficials d'incendi"],["#7d1c19","Any al centre del perímetre"]],
  access: [["#5d675f","Camins i pistes"],["#746954","Senders o traces"]],
  hic: [["#2f7b50","HIC"],["#154e37","HIC prioritari"]],
  biodiversity: [["#2d72a0","Registres públics de biodiversitat"]],
  public: [["#1f2a27","Punts d'ús públic OSM"]]
}};
const s = DATA.metrics.summary;
document.getElementById("methodology").textContent = `${{DATA.metrics.methodologyVersion}} · snapshot ${{DATA.metrics.snapshotId}}`;
document.getElementById("left-facts").innerHTML = [
  ["Àmbit", `${{s.studyHa.toLocaleString("ca-ES", {{maximumFractionDigits:0}})}} ha`],
  ["Incendis oficials", `${{s.fires}} perímetres`],
  ["Superfície cremada", `${{s.burnedHa.toLocaleString("ca-ES", {{maximumFractionDigits:1}})}} ha · ${{s.burnedPct.toLocaleString("ca-ES", {{maximumFractionDigits:2}})}} %`],
  ["Concurrència alta/mitjana-alta", `${{s.concurrenceHighHa.toLocaleString("ca-ES", {{maximumFractionDigits:1}})}} ha · ${{s.concurrenceHighPct.toLocaleString("ca-ES", {{maximumFractionDigits:1}})}} %`],
  ["Bosc + matollar", `${{s.forestLikeHa.toLocaleString("ca-ES", {{maximumFractionDigits:0}})}} ha · ${{s.forestLikePct.toLocaleString("ca-ES", {{maximumFractionDigits:1}})}} %`],
  ["Prats + conreus", `${{s.openLikeHa.toLocaleString("ca-ES", {{maximumFractionDigits:0}})}} ha · ${{s.openLikePct.toLocaleString("ca-ES", {{maximumFractionDigits:1}})}} %`],
  ["Coneixement de biodiversitat", `${{s.records.toLocaleString("ca-ES")}} registres · ${{s.knowledgeCellsWithRecords}}/${{s.knowledgeCells}} cel·les`],
  ["Accessibilitat cartografiada", `${{s.pathsKm.toLocaleString("ca-ES", {{maximumFractionDigits:1}})}} km · ${{s.pathDensity.toLocaleString("ca-ES", {{maximumFractionDigits:2}})}} km/km² · ${{s.publicPoints}} punts`]
].map(([k,v]) => `<div class="fact"><span>${{k}}</span><strong>${{v}}</strong></div>`).join("");
const root = document.getElementById("ecoradar-foc-alinya");
const ALL_LAYERS = Object.keys(LAYERS);
function setLayerActive(layer, active) {{
  const btn = document.querySelector(`.layer-btn[data-layer="${{layer}}"]`);
  if (btn) {{
    btn.classList.toggle("active", active);
    btn.classList.toggle("off", !active);
  }}
  document.querySelectorAll(`[data-layer="${{layer}}"]`).forEach(el => el.classList.toggle("hidden", !active));
}}
function applyModeLayers(mode) {{
  const wanted = new Set(MODES[mode].layers);
  ALL_LAYERS.forEach(layer => setLayerActive(layer, wanted.has(layer)));
}}
function setMode(mode) {{
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.mode === mode));
  const m = MODES[mode];
  root.classList.remove("mode-diagnosi", "mode-foc", "mode-gestio");
  root.classList.add(`mode-${{mode}}`);
  document.getElementById("mode-title").textContent = m.title;
  document.getElementById("mode-copy").textContent = m.copy;
  document.getElementById("mode-reading").innerHTML = `<b>${{m.readingTitle}}</b><ul>${{m.reading.map(t => `<li>${{t}}</li>`).join("")}}</ul>`;
  document.getElementById("argumentary").innerHTML = m.arguments.map(t => `<p>${{t}}</p>`).join("");
  applyModeLayers(mode);
  updateLegend();
}}
document.querySelectorAll(".tab").forEach(btn => btn.addEventListener("click", () => setMode(btn.dataset.mode)));
function updateLegend() {{
  const active = [...document.querySelectorAll(".layer-btn.active")].map(b => b.dataset.layer);
  document.getElementById("legend").innerHTML = active.flatMap(layer => LAYERS[layer] || []).map(([c,t]) => `<div><span class="swatch" style="background:${{c}}"></span><span>${{t}}</span></div>`).join("");
}}
document.querySelectorAll(".layer-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    setLayerActive(btn.dataset.layer, !btn.classList.contains("active"));
    updateLegend();
  }});
}});
const tooltip = document.getElementById("tooltip");
document.getElementById("map").addEventListener("mousemove", e => {{
  const target = e.target.closest("[data-tip]");
  if (!target) {{ tooltip.style.display = "none"; return; }}
  tooltip.innerHTML = target.dataset.tip;
  tooltip.style.display = "block";
  const box = e.currentTarget.getBoundingClientRect();
  tooltip.style.left = `${{e.clientX - box.left + 14}}px`;
  tooltip.style.top = `${{e.clientY - box.top + 14}}px`;
}});
document.getElementById("map").addEventListener("mouseleave", () => tooltip.style.display = "none");
let vb = {{x:0,y:0,w:{W},h:{H}}};
const svg = document.getElementById("map");
function applyViewBox() {{ svg.setAttribute("viewBox", `${{vb.x}} ${{vb.y}} ${{vb.w}} ${{vb.h}}`); }}
document.querySelectorAll(".zoom-btn").forEach(btn => btn.addEventListener("click", () => {{
  const z = btn.dataset.zoom;
  if (z === "reset") vb = {{x:0,y:0,w:{W},h:{H}}};
  else {{
    const factor = z === "in" ? .82 : 1.22;
    const nw = vb.w * factor, nh = vb.h * factor;
    vb.x += (vb.w - nw) / 2; vb.y += (vb.h - nh) / 2; vb.w = nw; vb.h = nh;
  }}
  applyViewBox();
}}));
let dragging = false, start = null;
svg.addEventListener("pointerdown", e => {{ dragging = true; start = [e.clientX, e.clientY, vb.x, vb.y]; svg.setPointerCapture(e.pointerId); }});
svg.addEventListener("pointermove", e => {{
  if (!dragging) return;
  const scaleX = vb.w / svg.clientWidth, scaleY = vb.h / svg.clientHeight;
  vb.x = start[2] - (e.clientX - start[0]) * scaleX;
  vb.y = start[3] - (e.clientY - start[1]) * scaleY;
  applyViewBox();
}});
svg.addEventListener("pointerup", () => dragging = false);
function drawRadar() {{
  const radar = document.getElementById("radar");
  const intro = `<p><strong>${{DATA.metrics.summary.managementResult}}</strong></p><p class="muted">Cada RADAR conserva la seva escala. Els valors directes, perfils i portes de decisió no formen una puntuació ecològica global.</p>`;
  const list = DATA.metrics.core.map(d => `<div class="indicator"><div><b>${{d.code}} · ${{d.name}}</b><br><span>${{d.status}} · confiança ${{d.confidence}}</span><br><span>${{d.interpretation}}</span></div><span class="pill">${{d.display}}</span></div>`).join("");
  radar.innerHTML = intro + list;
}}
function drawDecisions() {{
  document.getElementById("decisions").innerHTML = DECISIONS.map(d => `<div class="decision"><b>${{d.priorityClass}} · ${{d.title}}</b><span>${{d.decisionStatus}}. ${{d.justification}}</span></div>`).join("");
}}
setMode("diagnosi");
updateLegend();
drawRadar();
drawDecisions();
</script>
</body>
</html>
"""


def main() -> None:
    study = read_json(PROJECT / "maps" / "ecoradar_core" / "study_area.geojson")
    project = make_projector(geom_bounds(study))
    svg_layers, counts = build_layers(project)
    metrics = build_metrics()
    html_text = render_html(svg_layers, metrics, counts)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html_text, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
