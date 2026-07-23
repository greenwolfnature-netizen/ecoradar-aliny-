"""Generate EcoRadar product-level executive and module PDFs for Alinya.

This exporter consumes already prepared EcoRadar outputs. It does not download
data and does not expose internal processing details in the executive report.
"""

from __future__ import annotations

import csv
import html
import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
REPORTS = PROJECT / "reports"
MODULES_DIR = REPORTS / "modules"
MAPS_DIR = PROJECT / "maps" / "producte"
INDICATORS = PROJECT / "indicators"
CORE_MAPS = PROJECT / "maps" / "ecoradar_core"
METADATA = PROJECT / "metadata"
OUTPUT = ROOT / "output" / "pdf"

EXECUTIVE_MD = REPORTS / "informe_executiu_ecoradar_alinya.md"
EXECUTIVE_PDF = REPORTS / "informe_executiu_ecoradar_alinya.pdf"
MODULES_PDF = MODULES_DIR / "moduls_diagnosi_ecoradar_alinya.pdf"
PRODUCT_PDF = REPORTS / "informe_professional_ecoradar_alinya.pdf"
OUTPUT_PRODUCT_PDF = OUTPUT / "informe_professional_ecoradar_alinya.pdf"
PRODUCT_METADATA = METADATA / "ecoradar_product_metadata.json"

GREEN_DARK = colors.HexColor("#0E3B30")
GREEN = colors.HexColor("#1E644F")
GREEN_MID = colors.HexColor("#568C5F")
GREEN_SOFT = colors.HexColor("#DDEBDD")
SAND = colors.HexColor("#F1EFE3")
CREAM = colors.HexColor("#FBFAF3")
LINE = colors.HexColor("#C6D1C8")
TEXT = colors.HexColor("#152A23")
MUTED = colors.HexColor("#63726B")
ORANGE = colors.HexColor("#D06D32")
RED = colors.HexColor("#B74635")
BLUE = colors.HexColor("#317FA7")
GRAY = colors.HexColor("#9BA59F")

MAP_COLORS = {
    "forest": (75, 119, 68, 230),
    "open": (193, 197, 111, 225),
    "scrub": (137, 143, 77, 215),
    "agri": (211, 174, 83, 230),
    "urban": (151, 151, 151, 230),
    "water": (77, 145, 178, 235),
    "rock": (190, 184, 164, 230),
    "other": (216, 219, 197, 215),
}


@dataclass(frozen=True)
class ModulePage:
    number: int
    title: str
    subtitle: str
    objective: str
    metrics: tuple[tuple[str, str, str], ...]
    map_key: str
    interpretation: str
    implications: tuple[str, ...]
    confidence: str
    gaps: tuple[str, ...]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if not text or text.lower() in {"no disponible", "none", "nan"}:
            return None
        return float(text.replace(",", "."))
    except ValueError:
        return None


def fmt(value: Any, decimals: int = 1, suffix: str = "") -> str:
    number = as_float(value)
    if number is None:
        return ""
    text = f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text}{suffix}"


def metric(rows: list[dict[str, str]], key: str) -> str:
    for row in rows:
        if row.get("indicador") == key:
            return row.get("valor", "")
    return ""


def pressure_metric(rows: list[dict[str, str]], key: str) -> str:
    for row in rows:
        if row.get("indicator") == key:
            return row.get("value", "")
    return ""


def core_row(rows: list[dict[str, str]], code: str) -> dict[str, str]:
    for row in rows:
        if row.get("code") == code:
            return row
    return {}


def clean(text: str) -> str:
    return html.escape(text).replace("·", "-")


def draw_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y_top: float,
    width: float,
    style: ParagraphStyle,
) -> float:
    paragraph = Paragraph(clean(text), style)
    _, height = paragraph.wrap(width, 2000)
    paragraph.drawOn(c, x, y_top - height)
    return height


def draw_card(c: canvas.Canvas, x: float, y: float, w: float, h: float, fill=CREAM) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(colors.white)
    c.roundRect(x, y, w, h, 5, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.roundRect(x, y, w, h, 5, fill=0, stroke=1)


def draw_badge(c: canvas.Canvas, x: float, y: float, label: str, tone: str) -> None:
    tone_l = tone.lower()
    fill = GREEN_MID if tone_l.startswith("alt") else ORANGE if tone_l.startswith("baix") else BLUE
    c.setFillColor(fill)
    c.roundRect(x, y, 28 * mm, 8 * mm, 4, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + 14 * mm, y + 2.8 * mm, label)


def draw_metric(c: canvas.Canvas, x: float, y: float, label: str, value: str, unit: str = "") -> None:
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, value)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.4)
    c.drawString(x, y - 9, unit or label)
    if unit:
        c.drawString(x, y - 19, label)


def draw_footer(c: canvas.Canvas, page_label: str) -> None:
    c.setFillColor(GREEN_DARK)
    c.rect(0, 0, A4[0] if page_label.startswith("Informe") else landscape(A4)[0], 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7.4)
    c.drawRightString((A4[0] if page_label.startswith("Informe") else landscape(A4)[0]) - 12 * mm, 2.8 * mm, page_label)


def load_geojson(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def iter_coords(geometry: dict[str, Any]) -> Iterable[tuple[float, float]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if gtype == "Point":
        yield float(coords[0]), float(coords[1])
    elif gtype in {"LineString", "MultiPoint"}:
        for point in coords:
            yield float(point[0]), float(point[1])
    elif gtype in {"Polygon", "MultiLineString"}:
        for line in coords:
            for point in line:
                yield float(point[0]), float(point[1])
    elif gtype == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                for point in ring:
                    yield float(point[0]), float(point[1])
    elif gtype == "GeometryCollection":
        for child in geometry.get("geometries", []):
            yield from iter_coords(child)


def iter_rings(geometry: dict[str, Any]) -> Iterable[list[tuple[float, float]]]:
    gtype = geometry.get("type")
    if gtype == "Polygon":
        for ring in geometry.get("coordinates", [])[:1]:
            yield [(float(x), float(y)) for x, y in ring]
    elif gtype == "MultiPolygon":
        for polygon in geometry.get("coordinates", []):
            if polygon:
                yield [(float(x), float(y)) for x, y in polygon[0]]


def iter_lines(geometry: dict[str, Any]) -> Iterable[list[tuple[float, float]]]:
    gtype = geometry.get("type")
    if gtype == "LineString":
        yield [(float(x), float(y)) for x, y in geometry.get("coordinates", [])]
    elif gtype == "MultiLineString":
        for line in geometry.get("coordinates", []):
            yield [(float(x), float(y)) for x, y in line]
    elif gtype in {"Polygon", "MultiPolygon"}:
        yield from iter_rings(geometry)


def bounds_from_features(features: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for feature in features:
        for x, y in iter_coords(feature.get("geometry") or {}):
            xs.append(x)
            ys.append(y)
    if not xs or not ys:
        return (0, 0, 1, 1)
    return (min(xs), min(ys), max(xs), max(ys))


def transform_factory(bounds: tuple[float, float, float, float], width: int, height: int, padding: int = 80):
    minx, miny, maxx, maxy = bounds
    span_x = max(maxx - minx, 1)
    span_y = max(maxy - miny, 1)
    scale = min((width - 2 * padding) / span_x, (height - 2 * padding) / span_y)
    x_offset = (width - span_x * scale) / 2
    y_offset = (height - span_y * scale) / 2

    def project(point: tuple[float, float]) -> tuple[int, int]:
        x, y = point
        px = x_offset + (x - minx) * scale
        py = height - (y_offset + (y - miny) * scale)
        return int(px), int(py)

    return project, scale


def cover_class(name: str) -> str:
    lower = name.lower()
    if "aigua" in lower or "ribera" in lower:
        return "water"
    if "urb" in lower or "viària" in lower or "viaria" in lower:
        return "urban"
    if "conreu" in lower or "agr" in lower:
        return "agri"
    if "prats" in lower or "herbass" in lower or "pastur" in lower:
        return "open"
    if "matollar" in lower or "broll" in lower:
        return "scrub"
    if "bosc" in lower:
        return "forest"
    if "roquiss" in lower or "congest" in lower:
        return "rock"
    return "other"


def draw_geojson_polygons(
    draw: ImageDraw.ImageDraw,
    features: list[dict[str, Any]],
    project,
    fill_for_feature,
    outline: tuple[int, int, int, int] | None = None,
) -> None:
    for feature in features:
        fill = fill_for_feature(feature)
        for ring in iter_rings(feature.get("geometry") or {}):
            if len(ring) >= 3:
                draw.polygon([project(point) for point in ring], fill=fill, outline=outline)


def draw_geojson_lines(
    draw: ImageDraw.ImageDraw,
    features: list[dict[str, Any]],
    project,
    fill: tuple[int, int, int, int],
    width: int = 3,
) -> None:
    for feature in features:
        for line in iter_lines(feature.get("geometry") or {}):
            if len(line) >= 2:
                draw.line([project(point) for point in line], fill=fill, width=width, joint="curve")


def draw_geojson_points(
    draw: ImageDraw.ImageDraw,
    features: list[dict[str, Any]],
    project,
    fill: tuple[int, int, int, int],
    radius: int = 5,
) -> None:
    for feature in features:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        x, y = project(tuple(geometry.get("coordinates", [0, 0])[:2]))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=(255, 255, 255, 220))


def draw_scale_and_north(draw: ImageDraw.ImageDraw, scale: float, width: int, height: int) -> None:
    font = ImageFont.load_default()
    bar_m = 2000
    bar_px = max(30, int(bar_m * scale))
    x = 95
    y = height - 90
    draw.line((x, y, x + bar_px, y), fill=(20, 45, 38, 255), width=6)
    draw.line((x, y - 8, x, y + 8), fill=(20, 45, 38, 255), width=3)
    draw.line((x + bar_px, y - 8, x + bar_px, y + 8), fill=(20, 45, 38, 255), width=3)
    draw.text((x, y + 12), "2 km", fill=(20, 45, 38, 255), font=font)
    nx = width - 105
    ny = 95
    draw.polygon([(nx, ny - 42), (nx - 15, ny + 18), (nx, ny + 8), (nx + 15, ny + 18)], fill=(20, 45, 38, 255))
    draw.text((nx - 4, ny + 24), "N", fill=(20, 45, 38, 255), font=font)


def render_maps() -> dict[str, Path]:
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    study = load_geojson(CORE_MAPS / "study_area.geojson")
    cover = load_geojson(CORE_MAPS / "cobertes_sol.geojson")
    habitats = load_geojson(CORE_MAPS / "habitats_hic.geojson")
    pressure_lines = load_geojson(CORE_MAPS / "pressio_humana_osm_camins.geojson")
    pressure_points = load_geojson(CORE_MAPS / "pressio_humana_osm_punts.geojson")
    biodiversity = load_geojson(CORE_MAPS / "biodiversitat_registres.geojson")

    study_features = study.get("features", [])
    bounds = bounds_from_features(study_features)
    width, height = 1800, 1260
    project, scale = transform_factory(bounds, width, height)

    def base_image() -> tuple[Image.Image, ImageDraw.ImageDraw]:
        image = Image.new("RGBA", (width, height), (242, 240, 228, 255))
        draw = ImageDraw.Draw(image, "RGBA")
        for gx in range(120, width, 160):
            draw.line((gx, 0, gx, height), fill=(220, 222, 207, 85), width=1)
        for gy in range(120, height, 160):
            draw.line((0, gy, width, gy), fill=(220, 222, 207, 85), width=1)
        return image, draw

    def boundary(draw: ImageDraw.ImageDraw, w: int = 6) -> None:
        draw_geojson_lines(draw, study_features, project, (12, 61, 48, 255), width=w)

    def save(image: Image.Image, name: str) -> Path:
        path = MAPS_DIR / name
        image.convert("RGB").save(path, quality=95)
        return path

    paths: dict[str, Path] = {}

    image, draw = base_image()
    draw_geojson_polygons(
        draw,
        cover.get("features", []),
        project,
        lambda feature: MAP_COLORS[cover_class(str(feature.get("properties", {}).get("tipus_coberta", "")))],
    )
    draw_geojson_lines(draw, pressure_lines.get("features", []), project, (83, 74, 54, 220), width=3)
    draw_geojson_points(draw, pressure_points.get("features", []), project, (208, 109, 50, 240), radius=8)
    boundary(draw)
    draw_scale_and_north(draw, scale, width, height)
    paths["espai"] = save(image, "mapa_espai_alinya.png")

    image, draw = base_image()
    draw_geojson_polygons(
        draw,
        cover.get("features", []),
        project,
        lambda feature: MAP_COLORS[cover_class(str(feature.get("properties", {}).get("tipus_coberta", "")))],
    )
    boundary(draw)
    draw_scale_and_north(draw, scale, width, height)
    paths["paisatge"] = save(image, "mapa_paisatge_alinya.png")

    image, draw = base_image()
    draw_geojson_polygons(
        draw,
        habitats.get("features", []),
        project,
        lambda feature: (206, 108, 50, 225)
        if str(feature.get("properties", {}).get("HIC_PRIOR", "")).lower() in {"true", "1", "si", "sí"}
        else (72, 136, 84, 215)
        if str(feature.get("properties", {}).get("COD_HIC", "")).strip()
        else (214, 218, 202, 80),
        outline=(255, 255, 255, 40),
    )
    boundary(draw)
    draw_scale_and_north(draw, scale, width, height)
    paths["habitats"] = save(image, "mapa_habitats_alinya.png")

    image, draw = base_image()
    draw_geojson_polygons(draw, study_features, project, lambda _feature: (221, 235, 221, 255))
    draw_geojson_points(draw, biodiversity.get("features", []), project, (48, 116, 146, 150), radius=5)
    boundary(draw)
    draw_scale_and_north(draw, scale, width, height)
    paths["biodiversitat"] = save(image, "mapa_biodiversitat_alinya.png")

    image, draw = base_image()
    draw_geojson_polygons(draw, study_features, project, lambda _feature: (224, 231, 217, 255))
    draw_geojson_lines(draw, pressure_lines.get("features", []), project, (72, 65, 47, 240), width=5)
    draw_geojson_points(draw, pressure_points.get("features", []), project, (208, 109, 50, 255), radius=10)
    boundary(draw, 7)
    draw_scale_and_north(draw, scale, width, height)
    paths["pressio"] = save(image, "mapa_pressio_humana_alinya.png")

    image, draw = base_image()
    draw_geojson_polygons(draw, study_features, project, lambda _feature: (221, 235, 221, 255))
    boundary(draw, 7)
    draw_scale_and_north(draw, scale, width, height)
    paths["base"] = save(image, "mapa_base_alinya.png")
    return paths


def build_modules(context: dict[str, Any]) -> list[ModulePage]:
    basic = context["basic"]
    core = context["core"]
    pressure = context["pressure"]
    habitats = context["habitats"]
    biodiv = context["biodiv"]

    total_ha = as_float(metric(basic, "superficie_total")) or 0
    hic_ha = as_float(metric(basic, "superficie_hic")) or 0
    hic_pct = (hic_ha / total_ha * 100) if total_ha else None
    priority_ha = sum(
        as_float(row.get("superficie_ha")) or 0
        for row in habitats
        if str(row.get("es_prioritari", "")).lower() == "true"
    )
    priority_pct = (priority_ha / total_ha * 100) if total_ha else None
    top_groups = ", ".join(row.get("grup_taxonomic", "") for row in biodiv[:3])
    c = lambda code: core_row(core, code)

    return [
        ModulePage(
            1,
            "Biodiversitat",
            "Coneixement d'espècies i qualitat de la informació biològica",
            "Identificar què se sap de la biodiversitat i on cal reforçar inventari.",
            (
                ("Espècies citades", fmt(metric(basic, "nombre_especies_registrades"), 0), "taxons"),
                ("Registres recents", fmt(metric(basic, "nombre_registres_recents"), 0), "cites"),
                ("Registres totals", fmt(metric(basic, "nombre_registres_biodiversitat"), 0), "cites"),
                ("Grups principals", top_groups, ""),
            ),
            "biodiversitat",
            "La informació pública apunta a una biodiversitat coneguda elevada, però la lectura depèn molt de l'esforç d'observació. El valor real s'ha de contrastar amb camp i amb grups menys visibles.",
            (
                "Planificar camp per als grups menys representats abans de concloure absències.",
                "Protegir la informació d'espècies sensibles quan s'espacialitzin resultats.",
                "Separar cites recents, històriques i dubtoses en qualsevol decisió.",
            ),
            "Mitjà",
            ("Inventari dirigit", "espècies protegides", "espècies indicadores"),
        ),
        ModulePage(
            2,
            "Hàbitats",
            "Valor de conservació i sensibilitat dels hàbitats presents",
            "Localitzar els hàbitats que condicionen qualsevol actuació de gestió.",
            (
                ("Hàbitats detectats", fmt(metric(basic, "nombre_habitats"), 0), "tipus"),
                ("Superfície d'interès", fmt(hic_ha, 0), "ha"),
                ("% d'interès", fmt(hic_pct, 1, "%"), "sobre l'àrea"),
                ("Hàbitats prioritaris", fmt(priority_ha, 0), f"{fmt(priority_pct, 1, '%')} de l'àrea"),
            ),
            "habitats",
            "El senyal d'hàbitats és molt fort. Les zones amb hàbitats d'interès i prioritaris han d'actuar com a capa de prudència abans de definir treballs forestals, restauració o ús públic.",
            (
                "Creuar qualsevol actuació amb hàbitats prioritaris i sensibles.",
                "Diferenciar conservació estricta, millora ecològica i zones amb marge de gestió.",
                "Validar sobre el terreny els hàbitats de més valor o més fràgils.",
            ),
            "Mitjà",
            ("hàbitats sensibles", "estat de conservació local", "pressions puntuals"),
        ),
        ModulePage(
            3,
            "Paisatge i connectivitat",
            "Mosaic, cobertes i continuïtat ecològica",
            "Entendre si el paisatge ofereix diversitat estructural i connexió funcional.",
            (
                ("Coberta forestal", fmt(metric(basic, "percentatge_coberta_forestal"), 1, "%"), ""),
                ("Prats i herbassars", fmt(metric(basic, "percentatge_prats_pastures_herbassars"), 1, "%"), ""),
                ("Classes de coberta", fmt(metric(basic, "nombre_tipus_cobertes"), 0), ""),
                ("Mosaic Core", fmt(c("CORE_01").get("normalized_value"), 1), "0-100"),
            ),
            "paisatge",
            "Alinyà mostra una matriu natural molt forestal. Això pot afavorir continuïtat ecològica, però també fa especialment importants els espais oberts i les discontinuïtats que mantenen mosaic.",
            (
                "Conservar prats, pastures i clarianes que aportin heterogeneïtat.",
                "Evitar simplificar el paisatge amb actuacions uniformes.",
                "Calcular continuïtat espacial abans de delimitar corredors o barreres.",
            ),
            "Mitjà",
            ("continuïtat forestal espacial", "barreres", "riberes"),
        ),
        ModulePage(
            4,
            "Pressió humana",
            "Accessibilitat, ús públic i possibles concentracions d'activitat",
            "Avaluar on la presència humana pot condicionar conservació, tranquil·litat o gestió.",
            (
                ("Xarxa cartografiada", fmt(pressure_metric(pressure, "osm_path_track_road_km"), 1), "km"),
                ("Densitat de camins", fmt(pressure_metric(pressure, "osm_path_track_road_density"), 2), "km/km2"),
                ("Punts d'ús públic", fmt(pressure_metric(pressure, "osm_recreational_point_features"), 0), "punts"),
                ("Pressió Core", fmt(c("CORE_07").get("normalized_value"), 1), "0-100"),
            ),
            "pressio",
            "La xarxa d'accés és una bona primera aproximació a la pressió potencial, però no mesura visitants. La lectura correcta és d'accessibilitat i concentració probable, no d'afluència real.",
            (
                "Validar aparcaments, accessos i camins principals al camp.",
                "Creuar ús públic amb zones sensibles abans de senyalitzar o promocionar itineraris.",
                "Incorporar comptatges o dades de gestors per passar de potencial a intensitat real.",
            ),
            "Baix",
            ("intensitat real", "estacionalitat", "conflicte ús públic-fauna"),
        ),
        ModulePage(
            5,
            "Boscos i estructura forestal",
            "Continuïtat, espais oberts i resiliència estructural",
            "Llegir la massa forestal no només com a cobertura, sinó com a estructura de gestió.",
            (
                ("Coberta forestal", fmt(metric(basic, "percentatge_coberta_forestal"), 1, "%"), ""),
                ("Matriu oberta", fmt(metric(basic, "percentatge_prats_pastures_herbassars"), 1, "%"), ""),
                ("Agrícola", fmt(metric(basic, "percentatge_agricola"), 2, "%"), ""),
                ("Resiliència foc", fmt(c("CORE_09").get("normalized_value"), 1), "0-100"),
            ),
            "paisatge",
            "La forta dominància forestal obliga a mirar la continuïtat i el mosaic amb detall. El valor no és reduir bosc, sinó detectar on el mosaic pot millorar resiliència sense perdre biodiversitat.",
            (
                "Evitar actuacions genèriques sense creuar hàbitats d'interès.",
                "Identificar espais oberts que funcionen com a discontinuïtats ecològiques.",
                "Completar relleu, orientació, humitat i accessos abans de prioritzar treballs.",
            ),
            "Baix",
            ("relleu", "orientació", "humitat de vegetació", "històric de foc"),
        ),
        ModulePage(
            6,
            "Tranquil·litat ecològica",
            "Àrees de baixa pertorbació i potencial refugi de fauna",
            "Distingir zones accessibles de zones potencialment tranquil·les.",
            (
                ("Densitat d'accessos", fmt(pressure_metric(pressure, "osm_path_track_road_density"), 2), "km/km2"),
                ("Punts d'ús públic", fmt(pressure_metric(pressure, "osm_recreational_point_features"), 0), "punts"),
                ("Xarxa cartografiada", fmt(pressure_metric(pressure, "osm_path_track_road_km"), 1), "km"),
                ("Pressió Core", fmt(c("CORE_07").get("normalized_value"), 1), "0-100"),
            ),
            "pressio",
            "La tranquil·litat no es pot derivar només de la xarxa de camins. Caldrà combinar distància a accessos, intensitat d'ús, estacionalitat i sensibilitat de fauna.",
            (
                "No promocionar zones sensibles fins entendre l'ús real.",
                "Detectar àrees amb baixa accessibilitat com a candidates a tranquil·litat.",
                "Afegir observacions de camp i dades temporals d'ús públic.",
            ),
            "Baix",
            ("intensitat d'ús", "fauna sensible", "estacionalitat"),
        ),
        ModulePage(
            7,
            "Vulnerabilitat i canvi climàtic",
            "Estrès tèrmic, humitat i capacitat de refugi",
            "Detectar zones vulnerables i zones que poden actuar com a refugi climàtic.",
            (
                ("Coberta forestal", fmt(metric(basic, "percentatge_coberta_forestal"), 1, "%"), ""),
                ("Coberta artificial", fmt(metric(basic, "percentatge_urba_artificial"), 2, "%"), ""),
                ("Senyal de refugi", fmt(c("CORE_04").get("normalized_value"), 1), "0-100"),
                ("Senyal de vulnerabilitat", fmt(c("CORE_05").get("normalized_value"), 1), "0-100"),
            ),
            "base",
            "La cobertura forestal suggereix potencial de refugi, però no n'hi ha prou. Cal temperatura, humitat, orientació i aigua per convertir la intuïció en zones prioritàries.",
            (
                "No delimitar refugis climàtics només amb cobertura forestal.",
                "Prioritzar teledetecció i topografia derivada.",
                "Creuar futures zones vulnerables amb hàbitats i restauració.",
            ),
            "Baix",
            ("temperatura superficial", "humitat", "orientació", "aigua"),
        ),
        ModulePage(
            8,
            "Prioritats de gestió",
            "On actuar primer i amb quin criteri",
            "Transformar la diagnosi en una agenda d'actuació prudent i verificable.",
            (
                ("Hàbitats d'interès", fmt(hic_ha, 0), "ha"),
                ("Biodiversitat coneguda", fmt(c("CORE_06").get("normalized_value"), 1), "0-100"),
                ("Pressió potencial", fmt(c("CORE_07").get("normalized_value"), 1), "0-100"),
                ("Resiliència al foc", fmt(c("CORE_09").get("normalized_value"), 1), "0-100"),
            ),
            "espai",
            "Encara no és correcte generar un rànquing espacial tancat. Sí que es poden establir línies de prioritat: protegir valor, completar dades crítiques i validar pressions.",
            (
                "Primer: revisar HIC i hàbitats prioritaris abans d'actuar.",
                "Segon: validar espais oberts i accessos clau.",
                "Tercer: completar clima, aigua i foc abans de zonificar prioritats.",
            ),
            "Baix",
            ("zones d'actuació", "cost i complexitat", "benefici esperat"),
        ),
        ModulePage(
            9,
            "Coneixement i buits",
            "Què sabem, què falta i què cal comprovar",
            "Fer explícita la qualitat de la diagnosi i evitar conclusions falsament precises.",
            (
                ("Cobertes processades", fmt(metric(basic, "nombre_tipus_cobertes"), 0), "classes"),
                ("Hàbitats processats", fmt(metric(basic, "nombre_habitats"), 0), "tipus"),
                ("Espècies citades", fmt(metric(basic, "nombre_especies_registrades"), 0), "taxons"),
                ("Xarxa d'accés", fmt(pressure_metric(pressure, "osm_path_track_road_km"), 1), "km"),
            ),
            "espai",
            "La diagnosi és prou sòlida per entendre valors generals, però encara insuficient per definir actuacions espacials fines en clima, aigua, foc i tranquil·litat.",
            (
                "Usar les dades fortes per orientar preguntes, no per tancar decisions.",
                "Convertir cada buit en una tasca de camp o una font a incorporar.",
                "Mantenir separat el resultat ecològic del nivell de confiança.",
            ),
            "Mitjà",
            ("teledetecció", "hidrologia", "foc", "camp"),
        ),
        ModulePage(
            10,
            "Recomanacions de gestió",
            "Primeres línies d'acció orientades a decisions",
            "Proposar actuacions prudents, verificables i compatibles amb biodiversitat.",
            (
                ("Hàbitats d'interès", fmt(hic_ha, 0), "ha"),
                ("Prats i herbassars", fmt(metric(basic, "percentatge_prats_pastures_herbassars"), 1, "%"), ""),
                ("Xarxa d'accés", fmt(pressure_metric(pressure, "osm_path_track_road_km"), 1), "km"),
                ("Espècies citades", fmt(metric(basic, "nombre_especies_registrades"), 0), "taxons"),
            ),
            "espai",
            "La recomanació principal no és actuar encara amb receptes generals, sinó preparar la diagnosi operativa: camp dirigit, capes crítiques i creuaments amb hàbitats.",
            (
                "Validar hàbitats sensibles i espais oberts.",
                "Completar clima, aigua, foc i intensitat d'ús públic.",
                "Definir unitats de gestió només quan hi hagi prou confiança.",
            ),
            "Mitjà",
            ("priorització espacial", "seguiment", "cost-benefici ecològic"),
        ),
    ]


def build_context() -> dict[str, Any]:
    return {
        "basic": read_csv(INDICATORS / "ecoradar_01_resum.csv"),
        "core": read_csv(INDICATORS / "ecoradar_core.csv"),
        "habitats": read_csv(INDICATORS / "habitats_resum.csv"),
        "biodiv": read_csv(INDICATORS / "biodiversitat_resum.csv"),
        "pressure": read_csv(INDICATORS / "recreational_pressure_resum.csv"),
    }


def write_executive_markdown(context: dict[str, Any]) -> None:
    basic = context["basic"]
    core = context["core"]
    c = lambda code: core_row(core, code)
    lines = [
        "# EcoRadar Alinyà - Informe executiu",
        "",
        "## Lectura general",
        "",
        "Alinyà apareix com un espai natural de gran valor, amb una matriu forestal dominant, una presència rellevant d'espais oberts i una diversitat d'hàbitats molt notable. La diagnosi inicial permet orientar decisions, però encara no justifica una zonificació final d'actuacions.",
        "",
        "## Valors principals",
        "",
        f"- Superfície analitzada: {fmt(metric(basic, 'superficie_total'), 0)} ha.",
        f"- Coberta forestal: {fmt(metric(basic, 'percentatge_coberta_forestal'), 1, '%')}.",
        f"- Prats, pastures i herbassars: {fmt(metric(basic, 'percentatge_prats_pastures_herbassars'), 1, '%')}.",
        f"- Hàbitats detectats: {fmt(metric(basic, 'nombre_habitats'), 0)}.",
        f"- Superfície amb hàbitats d'interès: {fmt(metric(basic, 'superficie_hic'), 0)} ha.",
        f"- Espècies citades en dades públiques: {fmt(metric(basic, 'nombre_especies_registrades'), 0)}.",
        "",
        "## Pressions i vulnerabilitats",
        "",
        "La xarxa d'accessos cartografiada permet començar a entendre l'accessibilitat potencial, però encara no mesura la intensitat real d'ús públic. La continuïtat forestal és elevada i pot tenir lectures positives per a connectivitat, però també exigeix estudiar millor mosaic, discontinuïtats, humitat i resiliència al foc.",
        "",
        "## Prioritats prudents",
        "",
        "1. Creuar qualsevol actuació amb hàbitats d'interès i hàbitats prioritaris.",
        "2. Validar al camp els espais oberts, prats i pastures, perquè poden ser claus per a biodiversitat, mosaic i resiliència.",
        "3. Completar la lectura de vegetació, humitat, aigua, topografia i foc abans de delimitar zones d'intervenció.",
        "4. Validar accessos, aparcaments i punts d'ús públic abans d'interpretar pressió real.",
        "5. Dissenyar una campanya de camp dirigida als buits d'informació.",
        "",
        "## Nivell de confiança",
        "",
        f"- Hàbitats: {c('CORE_02').get('confidence', 'mitjana')}.",
        f"- Biodiversitat coneguda: {c('CORE_06').get('confidence', 'mitjana')}.",
        f"- Paisatge i cobertes: {c('CORE_01').get('confidence', 'mitjana')}.",
        "- Clima, aigua, foc i tranquil·litat ecològica: baix fins completar dades.",
        "",
        "## Conclusió",
        "",
        "EcoRadar ja ofereix una primera lectura ecològica útil d'Alinyà. El valor principal del territori és clar, però la gestió fina encara requereix més evidència espacial i validació de camp.",
    ]
    REPORTS.mkdir(parents=True, exist_ok=True)
    EXECUTIVE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def draw_map(c: canvas.Canvas, image_path: Path, x: float, y: float, w: float, h: float, title: str) -> None:
    draw_card(c, x, y, w, h)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 7, y + h - 14, title)
    c.drawImage(str(image_path), x + 7, y + 9, width=w - 14, height=h - 28, preserveAspectRatio=True, anchor="c")


def draw_table(c: canvas.Canvas, data: list[list[str]], x: float, y_top: float, widths: list[float]) -> float:
    style_body = ParagraphStyle("table_body", fontName="Helvetica", fontSize=8.0, leading=10, textColor=TEXT)
    style_head = ParagraphStyle("table_head", fontName="Helvetica-Bold", fontSize=8.0, leading=10, textColor=colors.white)
    table_data = []
    for row_index, row in enumerate(data):
        style = style_head if row_index == 0 else style_body
        table_data.append([Paragraph(clean(cell), style) for cell in row])
    table = Table(table_data, colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAF4")),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    _, height = table.wrap(sum(widths), 1000)
    table.drawOn(c, x, y_top - height)
    return height


def executive_pdf(context: dict[str, Any], maps: dict[str, Path]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    basic = context["basic"]
    core = context["core"]
    c = lambda code: core_row(core, code)

    width, height = A4
    pdf = canvas.Canvas(str(EXECUTIVE_PDF), pagesize=A4)
    pdf.setTitle("EcoRadar Alinya - Informe executiu")
    pdf.setAuthor("EcoRadar")

    margin = 15 * mm
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.2, leading=12.8, textColor=TEXT)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=7.8, leading=10.2, textColor=MUTED)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=GREEN_DARK)

    # Cover
    pdf.setFillColor(SAND)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(GREEN_DARK)
    pdf.roundRect(margin, height - margin - 38 * mm, width - 2 * margin, 38 * mm, 6, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(margin + 10, height - margin - 15 * mm, "EcoRadar Alinyà")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(margin + 10, height - margin - 25 * mm, "Informe executiu de diagnosi ecològica")
    draw_badge(pdf, width - margin - 40 * mm, height - margin - 17 * mm, "Preliminar", "Mitjà")
    draw_map(pdf, maps["espai"], margin, height - margin - 150 * mm, width - 2 * margin, 102 * mm, "Mapa de l'espai de treball")

    card_y = margin + 26 * mm
    card_w = (width - 2 * margin - 2 * 5 * mm) / 3
    for idx, (label, value, unit) in enumerate(
        [
            ("Superfície", fmt(metric(basic, "superficie_total"), 0), "ha"),
            ("Hàbitats", fmt(metric(basic, "nombre_habitats"), 0), "tipus"),
            ("Espècies citades", fmt(metric(basic, "nombre_especies_registrades"), 0), "taxons"),
        ]
    ):
        x = margin + idx * (card_w + 5 * mm)
        draw_card(pdf, x, card_y, card_w, 24 * mm)
        draw_metric(pdf, x + 8, card_y + 15 * mm, label, value, unit)
    draw_footer(pdf, "Informe executiu EcoRadar - Alinyà")
    pdf.showPage()

    # Synthesis
    pdf.setFillColor(SAND)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(GREEN_DARK)
    pdf.rect(0, height - 22 * mm, width, 22 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(margin, height - 14 * mm, "Lectura executiva")
    y = height - 34 * mm
    draw_card(pdf, margin, y - 46 * mm, width - 2 * margin, 46 * mm)
    draw_text(
        pdf,
        "Alinyà apareix com un espai natural amb un valor ecològic alt, dominat per una matriu forestal extensa i amb una presència rellevant d'espais oberts. La combinació d'hàbitats d'interès, diversitat de cobertes i biodiversitat coneguda ofereix una base sòlida per orientar la gestió, però encara no justifica una priorització espacial definitiva.",
        margin + 9,
        y - 9,
        width - 2 * margin - 18,
        body,
    )
    y -= 58 * mm
    data = [
        ["Tema", "Lectura de gestió", "Confiança"],
        ["Hàbitats", "Valor de conservació molt rellevant; cal creuar actuacions amb hàbitats d'interès.", "Mitjana"],
        ["Paisatge", "Matriu forestal dominant; els espais oberts són peces clau del mosaic.", "Mitjana"],
        ["Biodiversitat", "Moltes cites i espècies, però amb biaix d'observació i grups poc representats.", "Mitjana"],
        ["Ús públic", "Accessibilitat potencial identificada; falta intensitat real.", "Baixa"],
        ["Clima, aigua i foc", "Encara insuficient per zonificar vulnerabilitat o resiliència.", "Baixa"],
    ]
    draw_table(pdf, data, margin, y, [37 * mm, 104 * mm, 25 * mm])
    draw_footer(pdf, "Informe executiu EcoRadar - Alinyà")
    pdf.showPage()

    # Decisions
    pdf.setFillColor(SAND)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(GREEN_DARK)
    pdf.rect(0, height - 22 * mm, width, 22 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(margin, height - 14 * mm, "Què hauria de tenir en compte un gestor?")
    left_w = (width - 2 * margin - 6 * mm) * 0.54
    right_w = width - 2 * margin - 6 * mm - left_w
    y = height - 34 * mm
    draw_card(pdf, margin, y - 145 * mm, left_w, 145 * mm)
    draw_text(pdf, "Implicacions principals", margin + 8, y - 8, left_w - 16, h2)
    implications = [
        "1. Els hàbitats d'interès han de ser la primera capa de prudència.",
        "2. Els prats i espais oberts no són marginals: poden sostenir biodiversitat, mosaic i resiliència.",
        "3. La pressió humana s'ha d'interpretar com accessibilitat potencial fins disposar d'intensitat real.",
        "4. Les actuacions forestals no s'han de plantejar sense relleu, orientació, humitat i foc.",
        "5. La priorització final ha d'esperar clima, aigua, foc i validació de camp.",
    ]
    ty = y - 27
    for item in implications:
        used = draw_text(pdf, item, margin + 10, ty, left_w - 20, body)
        ty -= used + 9

    draw_card(pdf, margin + left_w + 6 * mm, y - 145 * mm, right_w, 145 * mm)
    draw_text(pdf, "Indicadors clau", margin + left_w + 6 * mm + 8, y - 8, right_w - 16, h2)
    metrics = [
        ("Mosaic", fmt(c("CORE_01").get("normalized_value"), 1), "0-100"),
        ("Hàbitats", fmt(c("CORE_02").get("normalized_value"), 1), "0-100"),
        ("Biodiversitat", fmt(c("CORE_06").get("normalized_value"), 1), "0-100"),
        ("Pressió humana", fmt(c("CORE_07").get("normalized_value"), 1), "0-100"),
        ("Resiliència al foc", fmt(c("CORE_09").get("normalized_value"), 1), "0-100"),
    ]
    my = y - 34
    for label, value, unit in metrics:
        draw_metric(pdf, margin + left_w + 6 * mm + 10, my, label, value, unit)
        my -= 22 * mm
    draw_footer(pdf, "Informe executiu EcoRadar - Alinyà")
    pdf.showPage()

    # Missing data and next steps
    pdf.setFillColor(SAND)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(GREEN_DARK)
    pdf.rect(0, height - 22 * mm, width, 22 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(margin, height - 14 * mm, "Dades que falten i següent pas")
    y = height - 34 * mm
    data = [
        ["Àmbit", "Per què és important", "Acció recomanada"],
        ["Vegetació i humitat", "Permet detectar vigor, estrès i refugis climàtics.", "Afegir sèries recents i estivals."],
        ["Aigua", "Condiciona fauna, refugis, connectivitat i restauració.", "Integrar cursos, fonts, basses i estat."],
        ["Foc i estructura", "Permet llegir continuïtat, mosaic i capacitat de resposta.", "Afegir històric, relleu i punts d'aigua."],
        ["Ús públic real", "Diferencia accessibilitat de pressió efectiva.", "Validar accessos i incorporar comptatges."],
        ["Camp", "Redueix biaixos i confirma hàbitats o espècies sensibles.", "Camp dirigit als buits detectats."],
    ]
    draw_table(pdf, data, margin, y, [34 * mm, 76 * mm, 56 * mm])
    draw_text(
        pdf,
        "La conclusió executiva és deliberadament prudent: EcoRadar ja identifica valors i preguntes de gestió, però evita convertir dades parcials en ordres d'actuació. La següent versió ha de transformar aquests buits en capes espacials verificades.",
        margin,
        58 * mm,
        width - 2 * margin,
        body,
    )
    draw_footer(pdf, "Informe executiu EcoRadar - Alinyà")
    pdf.showPage()
    pdf.save()


def module_pdf(context: dict[str, Any], maps: dict[str, Path]) -> None:
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    modules = build_modules(context)
    width, height = landscape(A4)
    pdf = canvas.Canvas(str(MODULES_PDF), pagesize=landscape(A4))
    pdf.setTitle("EcoRadar Alinya - Moduls de diagnosi")
    pdf.setAuthor("EcoRadar")
    body = ParagraphStyle("module_body", fontName="Helvetica", fontSize=8.1, leading=10.4, textColor=TEXT)
    small = ParagraphStyle("module_small", fontName="Helvetica", fontSize=7.1, leading=9.0, textColor=MUTED)
    gap_text = ParagraphStyle("module_gap", fontName="Helvetica", fontSize=6.8, leading=8.0, textColor=colors.white)
    h = ParagraphStyle("module_h", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=GREEN_DARK)

    for module in modules:
        pdf.setFillColor(SAND)
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        margin = 10 * mm
        header_h = 27 * mm
        pdf.setFillColor(GREEN_DARK)
        pdf.roundRect(margin, height - margin - header_h, width * 0.62, header_h, 6, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.circle(margin + 13 * mm, height - margin - header_h / 2, 9 * mm, fill=0, stroke=1)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(margin + 13 * mm, height - margin - header_h / 2 - 5, str(module.number))
        pdf.setFont("Helvetica-Bold", 17)
        pdf.drawString(margin + 28 * mm, height - margin - 11 * mm, module.title)
        pdf.setFont("Helvetica", 9.2)
        pdf.drawString(margin + 28 * mm, height - margin - 20 * mm, module.subtitle)

        objective_x = margin + width * 0.62 + 5 * mm
        objective_w = width - objective_x - margin
        draw_card(pdf, objective_x, height - margin - header_h, objective_w, header_h)
        draw_text(pdf, module.objective, objective_x + 8, height - margin - 8, objective_w - 16, body)

        top = height - margin - header_h - 5 * mm
        left_w = 56 * mm
        map_w = 135 * mm
        right_w = width - 2 * margin - left_w - map_w - 2 * 5 * mm
        panel_h = top - 18 * mm

        # Indicators
        x = margin
        draw_card(pdf, x, 18 * mm, left_w, panel_h)
        draw_text(pdf, "Indicadors principals", x + 7, top - 8, left_w - 14, h)
        y = top - 28
        for label, value, unit in module.metrics:
            pdf.setFillColor(GREEN_SOFT)
            pdf.roundRect(x + 7, y - 11, left_w - 14, 16 * mm, 4, fill=1, stroke=0)
            pdf.setFillColor(TEXT)
            pdf.setFont("Helvetica-Bold", 11.5)
            pdf.drawString(x + 12, y + 2, value)
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 7)
            pdf.drawString(x + 12, y - 7, unit or label)
            pdf.drawString(x + 12, y - 16, label)
            y -= 22 * mm

        # Map
        map_x = margin + left_w + 5 * mm
        map_y = 18 * mm
        draw_map(pdf, maps.get(module.map_key, maps["base"]), map_x, map_y, map_w, panel_h, "Cartografia interpretativa")
        legend_y = map_y + 8
        pdf.setFillColor(colors.white)
        pdf.roundRect(map_x + 7, legend_y, 52 * mm, 18 * mm, 4, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6.8)
        pdf.drawString(map_x + 11, legend_y + 11, "Mapa sintètic per a decisió")
        pdf.drawString(map_x + 11, legend_y + 4, "No substitueix verificació de camp")

        # Interpretation
        right_x = map_x + map_w + 5 * mm
        draw_card(pdf, right_x, 18 * mm, right_w, panel_h)
        draw_text(pdf, "Interpretació ecològica", right_x + 8, top - 8, right_w - 16, h)
        used = draw_text(pdf, module.interpretation, right_x + 8, top - 25, right_w - 16, body)
        y2 = top - 32 - used
        draw_text(pdf, "Implicacions per a la gestió", right_x + 8, y2, right_w - 16, h)
        y2 -= 16
        for item in module.implications:
            pdf.setFillColor(GREEN_MID)
            pdf.circle(right_x + 11, y2 - 3, 2.2, fill=1, stroke=0)
            used = draw_text(pdf, item, right_x + 17, y2 + 2, right_w - 25, small)
            y2 -= used + 7
        draw_text(pdf, "Nivell de confiança", right_x + 8, 59 * mm, right_w - 16, h)
        draw_badge(pdf, right_x + 8, 47 * mm, module.confidence, module.confidence)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(right_x + 40 * mm, 49.5 * mm, "Segons qualitat i completitud de dades.")
        pdf.setFillColor(ORANGE)
        pdf.roundRect(right_x + 8, 22 * mm, right_w - 16, 18 * mm, 4, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 7.3)
        pdf.drawString(right_x + 13, 35 * mm, "Cal completar")
        draw_text(pdf, ", ".join(module.gaps[:3]), right_x + 13, 31 * mm, right_w - 26, gap_text)

        pdf.setFillColor(GREEN_DARK)
        pdf.rect(0, 0, width, 8 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica", 7.2)
        pdf.drawString(margin, 2.8 * mm, "ECORADAR - Dades, ciència, natura i futur")
        pdf.drawRightString(width - margin, 2.8 * mm, f"Mòdul {module.number} de {len(modules)} - Diagnosi Alinyà")
        pdf.showPage()
    pdf.save()


def merge_product_pdf() -> None:
    writer_path = PRODUCT_PDF
    from pypdf import PdfWriter

    writer = PdfWriter()
    for source in (EXECUTIVE_PDF, MODULES_PDF):
        reader = PdfReader(str(source))
        for page in reader.pages:
            writer.add_page(page)
    with writer_path.open("wb") as handle:
        writer.write(handle)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(writer_path, OUTPUT_PRODUCT_PDF)


def write_metadata(context: dict[str, Any], maps: dict[str, Path]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project": "Alinyà",
        "product_outputs": {
            "executive_markdown": str(EXECUTIVE_MD.relative_to(ROOT)),
            "executive_pdf": str(EXECUTIVE_PDF.relative_to(ROOT)),
            "modules_pdf": str(MODULES_PDF.relative_to(ROOT)),
            "combined_product_pdf": str(PRODUCT_PDF.relative_to(ROOT)),
        },
        "map_outputs": {key: str(value.relative_to(ROOT)) for key, value in maps.items()},
        "principles": [
            "Executive output hides internal technical implementation details.",
            "Modules keep indicators separated and do not invent unavailable data.",
            "Maps are interpretative products generated from already prepared local outputs.",
        ],
        "input_counts": {
            "basic_rows": len(context["basic"]),
            "core_rows": len(context["core"]),
            "habitat_rows": len(context["habitats"]),
            "biodiversity_rows": len(context["biodiv"]),
            "pressure_rows": len(context["pressure"]),
        },
    }
    METADATA.mkdir(parents=True, exist_ok=True)
    PRODUCT_METADATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify_no_executive_terms() -> None:
    banned = ["connector", "fitxer", "crs", "oauth", "gpkg", "geopackage", "codis interns"]
    text = EXECUTIVE_MD.read_text(encoding="utf-8").lower()
    found = [term for term in banned if term in text]
    if found:
        raise RuntimeError(f"Executive report contains internal terms: {', '.join(found)}")


def main() -> None:
    context = build_context()
    maps = render_maps()
    write_executive_markdown(context)
    verify_no_executive_terms()
    executive_pdf(context, maps)
    module_pdf(context, maps)
    merge_product_pdf()
    write_metadata(context, maps)


if __name__ == "__main__":
    main()
