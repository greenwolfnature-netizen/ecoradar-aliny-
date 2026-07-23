"""Create the multidisciplinary EcoRadar Urba diagnosis for La Seu d'Urgell.

This exporter creates a new report and does not modify the interactive map,
the verified datasets, or the previous v2 report. It combines the documented
environmental evidence with a cautious population-health interpretation.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
from typing import Iterable

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from pypdf import PdfReader, PdfWriter

import export_la_seu_urban_report_v2 as base


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "diagnosi_ecoradar_urba_la_seu_integrada_v3.pdf"
DEFAULT_PROJECT_COPY = PROJECT / "reports" / "diagnosi_ecoradar_urba_la_seu_integrada_v3.pdf"
DEFAULT_FITXA_OUTPUT = ROOT / "output" / "pdf" / "fitxa_ecoradar_urba_la_seu_iqt_v1.pdf"
DEFAULT_FITXA_PROJECT_COPY = PROJECT / "reports" / "fitxa_ecoradar_urba_la_seu_iqt_v1.pdf"
DEFAULT_IQT_METADATA = PROJECT / "indicators" / "territorial_quality_index.json"
DEFAULT_ASSETS = ROOT / "tmp" / "pdfs" / "la_seu_urban_v3_assets"
BRANDING_DIR = PROJECT / "assets" / "branding"
ECORADAR_LOGO = BRANDING_DIR / "ecoradar_logo.png"
GREEN_WOLF_LOGO = BRANDING_DIR / "green_wolf_nature_logo.png"

PAGE_W, PAGE_H = landscape(A4)
MARGIN_X = base.MARGIN_X
CONTENT_W = base.CONTENT_W
CONTENT_TOP = base.CONTENT_TOP

NAVY = base.NAVY
GREEN = base.GREEN
DARK_GREEN = base.DARK_GREEN
BLUE = base.BLUE
PURPLE = base.PURPLE
ORANGE = base.ORANGE
RED = base.RED
INK = base.INK
MUTED = base.MUTED
BG = base.BG
CARD = base.CARD
BORDER = base.BORDER
RULE = base.RULE
PALE_GREEN = base.PALE_GREEN
PALE_BLUE = base.PALE_BLUE
PALE_ORANGE = base.PALE_ORANGE
PALE_RED = base.PALE_RED
WHITE = colors.white

MAP_BBOX = (1.435, 42.335, 1.490, 42.375)
CORE_BBOX = (1.45165, 42.35186, 1.46826, 42.36100)


def load_inputs() -> dict:
    return {
        "manifest": json.loads((PROJECT / "metadata" / "layer_manifest.json").read_text()),
        "demography": json.loads((PROJECT / "indicators" / "demography_idescat.json").read_text()),
        "solar": json.loads((PROJECT / "indicators" / "solar_roof_screening_summary.json").read_text()),
        "sentinel": json.loads((PROJECT / "indicators" / "sentinel2_urban_indicators.json").read_text()),
        "context": json.loads((PROJECT / "indicators" / "contextual_environment.json").read_text()),
        "extended": json.loads((PROJECT / "indicators" / "extended_urban_indicators.json").read_text()),
        "buildings": _read_geojson("buildings_cadastre.geojson"),
        "green": _read_geojson("green_spaces_osm.geojson"),
        "mobility": _read_geojson("mobility_osm.geojson"),
        "facilities": _read_geojson("facilities_osm.geojson"),
        "water": _read_geojson("water_osm.geojson"),
        "roofs": _read_geojson("solar_roof_screening.geojson"),
    }


def _read_geojson(name: str) -> dict:
    return json.loads((PROJECT / "processed" / name).read_text())


def footer(c: canvas.Canvas, page: int) -> None:
    y = 10 * mm
    c.setStrokeColor(RULE)
    c.setLineWidth(0.65)
    c.line(MARGIN_X, y + 5 * mm, PAGE_W - MARGIN_X, y + 5 * mm)
    c.setFillColor(MUTED)
    c.setFont("Arial", 6.5)
    c.drawString(
        MARGIN_X,
        y,
        base.cat("EcoRadar Urba - Diagnosi integrada de gestio ambiental i salut publica - La Seu d'Urgell"),
    )
    c.drawRightString(PAGE_W - MARGIN_X, y, str(page))


def section_header(c: canvas.Canvas, number: str, title: str, subtitle: str, page: int) -> None:
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 22)
    c.drawString(MARGIN_X, PAGE_H - 17 * mm, base.cat(f"{number}. {title}" if number else title))
    c.setFillColor(GREEN)
    c.setFont("Arial-Bold", 11.5)
    c.drawString(MARGIN_X, PAGE_H - 27 * mm, base.cat(subtitle))
    footer(c, page)


def card_title(c: canvas.Canvas, title: str, x: float, top: float, width: float) -> float:
    return base.draw_paragraph(c, f"<b>{title}</b>", x, top, width, "card_title")


def draw_metric(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    value: str,
    label: str,
    note: str,
    accent=GREEN,
) -> None:
    base.draw_metric_card(c, x, y, w, h, value, label, note, accent)


def draw_brand_logo(
    c: canvas.Canvas,
    path: Path,
    x: float,
    y: float,
    size: float,
    *,
    white_backplate: bool = True,
) -> None:
    """Draw a square brand asset without deformation or clipping."""
    if not path.exists():
        return
    if white_backplate:
        c.setFillColor(colors.white)
        c.setStrokeColor(HexColor("#D9DED8"))
        c.setLineWidth(0.35)
        c.roundRect(x, y, size, size, 2.2, fill=1, stroke=1)
    inset = 0.8 * mm
    c.drawImage(
        ImageReader(str(path)),
        x + inset,
        y + inset,
        width=size - 2 * inset,
        height=size - 2 * inset,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def _projection(bbox: tuple[float, float, float, float], x: float, y: float, w: float, h: float):
    xmin, ymin, xmax, ymax = bbox
    cos_lat = math.cos(math.radians((ymin + ymax) / 2))
    span_x = (xmax - xmin) * cos_lat
    span_y = ymax - ymin
    scale = min(w / span_x, h / span_y)
    draw_w = span_x * scale
    draw_h = span_y * scale
    ox = x + (w - draw_w) / 2
    oy = y + (h - draw_h) / 2

    def project(lon: float, lat: float) -> tuple[float, float]:
        return (
            ox + (lon - xmin) * cos_lat * scale,
            oy + (lat - ymin) * scale,
        )

    return project


def _iter_geometries(geometry: dict):
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not coordinates:
        return
    if kind == "Polygon":
        yield "Polygon", coordinates
    elif kind == "MultiPolygon":
        for polygon in coordinates:
            yield "Polygon", polygon
    elif kind == "LineString":
        yield "LineString", coordinates
    elif kind == "MultiLineString":
        for line in coordinates:
            yield "LineString", line
    elif kind == "Point":
        yield "Point", coordinates
    elif kind == "MultiPoint":
        for point in coordinates:
            yield "Point", point


def draw_features(
    c: canvas.Canvas,
    feature_collection: dict,
    bbox: tuple[float, float, float, float],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill=None,
    stroke=INK,
    line_width: float = 0.35,
    point_radius: float = 1.8,
    property_fill: dict[str, object] | None = None,
    property_name: str | None = None,
    filter_property: tuple[str, set[str]] | None = None,
) -> None:
    project = _projection(bbox, x, y, w, h)
    c.saveState()
    clip = c.beginPath()
    clip.rect(x, y, w, h)
    c.clipPath(clip, stroke=0, fill=0)
    c.setLineWidth(line_width)
    c.setStrokeColor(stroke)
    for feature in feature_collection.get("features", []):
        properties = feature.get("properties") or {}
        if filter_property:
            key, allowed = filter_property
            if properties.get(key) not in allowed:
                continue
        feature_fill = fill
        if property_fill and property_name:
            feature_fill = property_fill.get(properties.get(property_name), fill)
        if feature_fill is not None:
            c.setFillColor(feature_fill)
        for kind, coordinates in _iter_geometries(feature.get("geometry") or {}):
            if kind == "Point":
                px, py = project(float(coordinates[0]), float(coordinates[1]))
                c.circle(px, py, point_radius, fill=1 if feature_fill is not None else 0, stroke=1)
                continue
            if kind == "LineString":
                if len(coordinates) < 2:
                    continue
                path = c.beginPath()
                px, py = project(float(coordinates[0][0]), float(coordinates[0][1]))
                path.moveTo(px, py)
                for coordinate in coordinates[1:]:
                    px, py = project(float(coordinate[0]), float(coordinate[1]))
                    path.lineTo(px, py)
                c.drawPath(path, fill=0, stroke=1)
                continue
            if kind == "Polygon":
                if not coordinates or not coordinates[0]:
                    continue
                path = c.beginPath()
                for ring in coordinates:
                    if len(ring) < 3:
                        continue
                    px, py = project(float(ring[0][0]), float(ring[0][1]))
                    path.moveTo(px, py)
                    for coordinate in ring[1:]:
                        px, py = project(float(coordinate[0]), float(coordinate[1]))
                        path.lineTo(px, py)
                    path.close()
                c.drawPath(path, fill=1 if feature_fill is not None else 0, stroke=1)
    c.restoreState()


def draw_map_frame(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str) -> tuple[float, float, float, float]:
    base.rounded_card(c, x, y, w, h, fill=CARD)
    card_title(c, title, x + 5 * mm, y + h - 5 * mm, w - 10 * mm)
    map_x = x + 5 * mm
    map_y = y + 14 * mm
    map_w = w - 10 * mm
    map_h = h - 31 * mm
    c.setFillColor(HexColor("#EEF1EA"))
    c.setStrokeColor(BORDER)
    c.rect(map_x, map_y, map_w, map_h, fill=1, stroke=1)
    return map_x, map_y, map_w, map_h


def draw_north_scale(c: canvas.Canvas, bbox, x, y, w, h, metres: int = 500) -> None:
    c.setStrokeColor(NAVY)
    c.setFillColor(NAVY)
    c.setLineWidth(1.2)
    nx, ny = x + w - 9 * mm, y + h - 11 * mm
    c.line(nx, ny - 8 * mm, nx, ny)
    c.line(nx, ny, nx - 2 * mm, ny - 3 * mm)
    c.line(nx, ny, nx + 2 * mm, ny - 3 * mm)
    c.setFont("Arial-Bold", 7)
    c.drawCentredString(nx, ny + 2 * mm, "N")
    mean_lat = (bbox[1] + bbox[3]) / 2
    lon_metres = 111320 * math.cos(math.radians(mean_lat))
    fraction = (metres / lon_metres) / (bbox[2] - bbox[0])
    length = max(18 * mm, min(w * 0.28, w * fraction))
    sx, sy = x + 7 * mm, y + 7 * mm
    c.line(sx, sy, sx + length, sy)
    c.line(sx, sy - 1.5 * mm, sx, sy + 1.5 * mm)
    c.line(sx + length, sy - 1.5 * mm, sx + length, sy + 1.5 * mm)
    c.setFont("Arial", 6.2)
    c.drawCentredString(sx + length / 2, sy + 2 * mm, f"{metres} m")


def draw_integrated_map(
    c: canvas.Canvas,
    data: dict,
    x: float,
    y: float,
    w: float,
    h: float,
    bbox=MAP_BBOX,
    *,
    show_core_boundary: bool = True,
) -> None:
    draw_features(c, data["green"], bbox, x, y, w, h, fill=HexColor("#B8D1A0"), stroke=HexColor("#6D9B61"), line_width=0.45)
    draw_features(c, data["mobility"], bbox, x, y, w, h, fill=None, stroke=HexColor("#C5B9A6"), line_width=0.35)
    draw_features(c, data["buildings"], bbox, x, y, w, h, fill=HexColor("#EEE9DF"), stroke=HexColor("#AAA399"), line_width=0.18)
    draw_features(c, data["water"], bbox, x, y, w, h, fill=None, stroke=HexColor("#3F9EC0"), line_width=0.8)
    draw_features(c, data["facilities"], bbox, x, y, w, h, fill=NAVY, stroke=WHITE, line_width=0.5, point_radius=1.6)
    if show_core_boundary:
        project = _projection(bbox, x, y, w, h)
        p0 = project(CORE_BBOX[0], CORE_BBOX[1])
        p1 = project(CORE_BBOX[2], CORE_BBOX[3])
        c.saveState()
        c.setStrokeColor(NAVY)
        c.setLineWidth(0.8)
        c.setDash(3, 2)
        c.rect(p0[0], p0[1], p1[0] - p0[0], p1[1] - p0[1], fill=0, stroke=1)
        c.restoreState()
    draw_north_scale(c, bbox, x, y, w, h)


def draw_raster_map(
    c: canvas.Canvas,
    path: Path,
    data: dict,
    bbox,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    overlay_buildings: bool = True,
) -> None:
    c.setFillColor(HexColor("#F4F3EE"))
    c.rect(x, y, w, h, fill=1, stroke=0)
    c.drawImage(ImageReader(str(path)), x, y, w, h, preserveAspectRatio=False, mask="auto")
    if overlay_buildings:
        draw_features(c, data["buildings"], bbox, x, y, w, h, fill=None, stroke=HexColor("#FFFFFF"), line_width=0.24)


def page_cover(c: canvas.Canvas, data: dict) -> None:
    c.setFillColor(WHITE)
    c.rect(0, 0, PAGE_W * 0.52, PAGE_H, fill=1, stroke=0)
    c.setFillColor(BG)
    c.rect(PAGE_W * 0.52, 0, PAGE_W * 0.48, PAGE_H, fill=1, stroke=0)
    x = MARGIN_X + 4 * mm
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 31)
    c.drawString(x, PAGE_H - 42 * mm, base.cat("ECORADAR URBA"))
    c.setFillColor(GREEN)
    c.setFont("Arial-Bold", 23)
    c.drawString(x, PAGE_H - 56 * mm, "La Seu d'Urgell")
    c.setFillColor(INK)
    c.setFont("Arial-Bold", 16)
    c.drawString(x, PAGE_H - 81 * mm, base.cat("Informe de diagnosi integrada"))
    c.drawString(x, PAGE_H - 92 * mm, base.cat("gestio ambiental i salut publica"))
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 9.5)
    c.drawString(x, PAGE_H - 109 * mm, base.cat("Clima urba + LiDAR + Sentinel-2 + demografia + inundabilitat + xarxa urbana"))
    base.rounded_card(c, x, 42 * mm, PAGE_W * 0.43, 37 * mm, fill=HexColor("#F7F8F5"), stroke=INK)
    base.draw_paragraph(
        c,
        "Document tecnic que interpreta els resultats obtinguts des de dues mirades complementaries: la gestio ambiental del territori i la salut publica de base medica. Orienta decisions municipals; no es una avaluacio clinica individual.",
        x + 7 * mm,
        71 * mm,
        PAGE_W * 0.39,
        "body",
    )
    c.setFillColor(MUTED)
    c.setFont("Arial", 7.5)
    c.drawString(x, 26 * mm, base.cat("Versio 3.1 - 12 de juliol de 2026 - indicadors Copernicus integrats"))
    draw_brand_logo(c, ECORADAR_LOGO, x, 4 * mm, 18 * mm)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 7.2)
    c.drawString(x + 21 * mm, 14.5 * mm, "ECORADAR")
    c.setFillColor(MUTED)
    c.setFont("Arial", 5.2)
    c.drawString(x + 21 * mm, 9.5 * mm, base.cat("Radiografia territorial"))
    draw_brand_logo(c, GREEN_WOLF_LOGO, x + 63 * mm, 4 * mm, 18 * mm)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 7.2)
    c.drawString(x + 84 * mm, 14.5 * mm, "GREEN WOLF NATURE")
    c.setFillColor(MUTED)
    c.setFont("Arial", 5.2)
    c.drawString(x + 84 * mm, 9.5 * mm, base.cat("Natura, gestio i benestar"))

    rx = PAGE_W * 0.55
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 11.5)
    c.drawString(rx, PAGE_H - 23 * mm, base.cat("XARXA CLIMATICA DE BENESTAR"))
    base.rounded_card(c, rx, 77 * mm, PAGE_W * 0.40, 101 * mm, fill=CARD)
    map_x, map_y, map_w, map_h = rx + 2 * mm, 79 * mm, PAGE_W * 0.40 - 4 * mm, 97 * mm
    c.setFillColor(HexColor("#EEF1EA"))
    c.rect(map_x, map_y, map_w, map_h, fill=1, stroke=0)
    draw_integrated_map(c, data, map_x, map_y, map_w, map_h, bbox=CORE_BBOX, show_core_boundary=False)
    draw_metric(c, rx, 40 * mm, 55 * mm, 32 * mm, "61,7%", "Ombra LiDAR", "Nucli central, 15 h d'estiu.", DARK_GREEN)
    draw_metric(c, rx + 59 * mm, 40 * mm, 55 * mm, 32 * mm, "20,1%", "Poblacio 65+", "2.617 persones; dada municipal.", PURPLE)
    c.setFillColor(MUTED)
    c.setFont("Arial", 6.6)
    c.drawRightString(PAGE_W - MARGIN_X, 18 * mm, base.cat("Dades verificades - ambit raster central: 130,4 ha"))
    c.showPage()


def page_executive(c: canvas.Canvas, data: dict) -> None:
    section_header(c, "1", "Resum executiu", "Diagnosi compartida i decisions prioritaries", 2)
    gap = 7 * mm
    col_w = (CONTENT_W - gap) / 2
    top = 174 * mm
    h = 55 * mm
    base.rounded_card(c, MARGIN_X, top - h, col_w, h, fill=PALE_GREEN)
    card_title(c, "Lectura de gestio ambiental", MARGIN_X + 6 * mm, top - 6 * mm, col_w - 12 * mm)
    base.draw_bullets(
        c,
        [
            "La infraestructura verda i blava es rellevant, pero la proteccio climatica no es uniforme ni continua.",
            "El nucli central presenta 61,7% d'ombra modelada i 31,8% de capcada, amb contrastos termics marcats a la LST.",
            "La decisio no es augmentar una mitjana municipal, sino protegir recorreguts essencials i punts d'espera.",
        ],
        MARGIN_X + 7 * mm,
        top - 18 * mm,
        col_w - 14 * mm,
        "body_small",
    )
    right_x = MARGIN_X + col_w + gap
    base.rounded_card(c, right_x, top - h, col_w, h, fill=PALE_BLUE)
    card_title(c, "Lectura medica i de salut publica", right_x + 6 * mm, top - 6 * mm, col_w - 12 * mm)
    base.draw_bullets(
        c,
        [
            "La calor es un risc ambiental que pot causar efectes aguts i agreujar malalties croniques; l'edat es nomes una part de la vulnerabilitat. [H1, H4, H5]",
            "El municipi registra 2.617 persones de 65 anys o mes (20,1%), pero les dades no permeten localitzar-les ni identificar vulnerabilitat clinica individual.",
            "Ombra, descans, aigua, accessibilitat i continuitat de ruta son mesures de prevencio ambiental, no tractaments medics.",
        ],
        right_x + 7 * mm,
        top - 18 * mm,
        col_w - 14 * mm,
        "body_small",
    )

    manifest = data["manifest"]
    gap_m = 4 * mm
    mw = (CONTENT_W - 2 * gap_m) / 3
    mh = 31 * mm
    y1, y2 = 82 * mm, 47 * mm
    draw_metric(c, MARGIN_X, y1, mw, mh, "61,7%", "Ombra directa", "LiDAR, 21/06/2026 a les 15 h CEST. [D1]", DARK_GREEN)
    draw_metric(c, MARGIN_X + mw + gap_m, y1, mw, mh, "31,8%", "Coberta de capcada", "Classes de vegetacio LiDAR 4 i 5. [D1]", GREEN)
    draw_metric(c, MARGIN_X + 2 * (mw + gap_m), y1, mw, mh, "46,7 C", "LST mitjana", "Landsat 9; no es temperatura de l'aire. [D2]", ORANGE)
    draw_metric(c, MARGIN_X, y2, mw, mh, "2.304", "Edificis", "Petjades oficials dins el mapa. [D3]", NAVY)
    draw_metric(c, MARGIN_X + mw + gap_m, y2, mw, mh, "1.504", "Cobertes analitzades", "392 amb geometria preliminar favorable.", PURPLE)
    draw_metric(c, MARGIN_X + 2 * (mw + gap_m), y2, mw, mh, "13.003", "Poblacio 2025", "Idescat a partir del Cens anual INE. [D4]", BLUE)
    base.rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 19 * mm, fill=PALE_ORANGE)
    base.draw_paragraph(
        c,
        "<b>Decisio principal.</b> Crear una xarxa climatica validada que connecti habitatge, equipaments, espais verds i blaus, serveis sanitaris i mobilitat quotidiana; prioritzar-la per exposicio, vulnerabilitat i capacitat real d'us. EcoRadar identifica on inspeccionar i actuar, no certifica confort ni resultats de salut.",
        MARGIN_X + 7 * mm,
        36 * mm,
        CONTENT_W - 14 * mm,
        "body",
    )
    c.showPage()


def page_framework(c: canvas.Canvas) -> None:
    section_header(c, "2", "Marc de diagnosi compartida", "De la dada territorial al risc, la proteccio i l'autonomia", 3)
    base.draw_process_band(
        c,
        [
            ("PERILL", "Calor, radiacio, inundacio i superficies exposades."),
            ("EXPOSICIO", "On, quan i durant quant temps hi ha persones."),
            ("VULNERABILITAT", "Edat, salut, habitatge, renda, mobilitat i xarxa social."),
            ("PROTECCIO", "Ombra, verd, aigua, refugis, serveis i informacio."),
            ("DECISIO", "Actuacio prioritzada, mesurable i revisable."),
        ],
        MARGIN_X,
        139 * mm,
        CONTENT_W,
    )
    gap = 6 * mm
    col_w = (CONTENT_W - 2 * gap) / 3
    y, h = 53 * mm, 70 * mm
    cards = [
        ("Gestor ambiental", PALE_GREEN, ["Interpreta processos espacials i funcionament de la infraestructura verda, blava i construida.", "Relaciona exposicio amb manteniment, mobilitat, aigua, biodiversitat, risc i cost de cicle de vida.", "Demana geometria, data, escala, llicencia i incertesa abans de decidir."]),
        ("Metge / salut publica", PALE_BLUE, ["Interpreta la plausibilitat sanitaria a escala poblacional, no diagnostica persones amb el mapa.", "Diferencia risc agut, agreujament de malaltia cronica i determinants socials de l'exposicio.", "Exigeix prudencia causal, proteccio de dades i avaluacio abans d'afirmar impactes locals."]),
        ("Decisio conjunta", PALE_ORANGE, ["Prioritza recorreguts essencials, poblacio vulnerable i punts on l'actuacio es utilitzable.", "Combina solucions basades en natura, ombra construida, serveis, comunicacio i seguiment.", "Mesura exposicio i us; els resultats de salut requereixen un disseny epidemiologic especific."]),
    ]
    for idx, (title, fill, bullets) in enumerate(cards):
        x = MARGIN_X + idx * (col_w + gap)
        base.rounded_card(c, x, y, col_w, h, fill=fill)
        card_title(c, title, x + 6 * mm, y + h - 6 * mm, col_w - 12 * mm)
        base.draw_bullets(c, bullets, x + 6 * mm, y + h - 19 * mm, col_w - 12 * mm, "body_small")
    base.rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 22 * mm, fill=CARD)
    base.draw_paragraph(
        c,
        "<b>Formula de treball:</b> risc per a la salut = perill x exposicio x vulnerabilitat, moderat per la proteccio disponible. EcoRadar aporta sobretot evidencia espacial sobre perill i proteccio; l'exposicio humana real i la vulnerabilitat clinica requereixen dades addicionals i governanca intersectorial. [H1, H7]",
        MARGIN_X + 7 * mm,
        39 * mm,
        CONTENT_W - 14 * mm,
        "body",
    )
    c.showPage()


def page_sources_method(c: canvas.Canvas) -> None:
    section_header(c, "3", "Dades, escala i metode", "Només fonts verificades i resultats obtinguts", 4)
    base.draw_process_band(
        c,
        [
            ("INVENTARI", "Identificacio de l'organisme responsable."),
            ("VERIFICACIO", "Servei, llicencia, CRS i cobertura local."),
            ("NORMALITZACIO", "EPSG:25831 per al calcul i 4326 per al visor."),
            ("DERIVACIO", "LiDAR, LST i cribratge de cobertes."),
            ("INTERPRETACIO", "Gestio ambiental + salut publica prudent."),
        ],
        MARGIN_X,
        145 * mm,
        CONTENT_W,
    )
    rows = [
        [base.P("Font", "table_bold"), base.P("Organisme / servei", "table_bold"), base.P("Dada local obtinguda", "table_bold"), base.P("Us en la diagnosi", "table_bold")],
        [base.P("LiDAR Territorial v3.1 [D1]", "table"), base.P("ICGC - LAZ - EPSG:25831 - CC BY 4.0", "table"), base.P("2 fulls 1 x 1 km; nucli de 130,4 ha", "table"), base.P("DSM/DTM, ombra, capcada, pendent i orientacio de superfície.", "table")],
        [base.P("Landsat 9 C2 L2 ST [D2]", "table"), base.P("USGS EROS - STAC/COG", "table"), base.P("Escena 08/07/2026; 1.485 pixels valids", "table"), base.P("Temperatura superficial, P10-P90 i contrast espacial.", "table")],
        [base.P("INSPIRE Buildings [D3]", "table"), base.P("Direccio General del Cadastre - ATOM/GML", "table"), base.P("2.304 edificis dins l'extensio", "table"), base.P("Teixit construit i base del cribratge solar.", "table")],
        [base.P("Idescat / Cens anual INE [D4]", "table"), base.P("API El municipi en xifres", "table"), base.P("Poblacio i grups d'edat 2025", "table"), base.P("Vulnerabilitat demografica agregada, no localitzada.", "table")],
        [base.P("SNCZI T=100 [D5]", "table"), base.P("MITECO - WMS INSPIRE", "table"), base.P("Retall local WMS verificat", "table"), base.P("Extensio oficial visualitzada; no s'ha calculat area vectorial.", "table")],
        [base.P("OpenStreetMap [D6]", "table"), base.P("OSMF - ODbL", "table"), base.P("Verd, aigua, mobilitat i 37 equipaments", "table"), base.P("Estructura funcional; requereix contrast municipal i de camp.", "table")],
        [base.P("Sentinel-2 L2A [D9]", "table"), base.P("CDSE - STAC/OAuth2/Process API", "table"), base.P("Escena 07/07/2026; 13.177 pixels valids", "table"), base.P("NDVI, NDMI i albedo amb mascara SCL; 10/20 m.", "table")],
        [base.P("CLMS / S5P / CAMS [D10]", "table"), base.P("CDSE i ECMWF - API/WMS", "table"), base.P("LST nocturna, NO2 i PM2,5", "table"), base.P("Context agregat a 3-10 km; mai mapa de carrer.", "table")],
    ]
    table = base.make_table(rows, [41 * mm, 50 * mm, 47 * mm, CONTENT_W - 138 * mm], font_size=7.0)
    base.table_on_canvas(c, table, MARGIN_X, 127 * mm)
    base.rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 24 * mm, fill=PALE_ORANGE)
    base.draw_paragraph(
        c,
        "<b>Regla de validesa.</b> Les mitjanes LiDAR i Landsat pertanyen al nucli central; la demografia es municipal; la inundabilitat es una imatge WMS oficial; OSM es una base comunitaria. No es barregen aquestes escales per atribuir risc a un carrer, edifici o persona sense dades que ho sostinguin.",
        MARGIN_X + 7 * mm,
        41 * mm,
        CONTENT_W - 14 * mm,
        "body",
    )
    c.showPage()


def page_integrated_map(c: canvas.Canvas, data: dict) -> None:
    section_header(c, "4", "Cartografia integrada", "Teixit urba, verd, aigua, equipaments i ambit raster", 5)
    base.rounded_card(c, MARGIN_X, 28 * mm, CONTENT_W, 148 * mm, fill=BG)
    panel_x = MARGIN_X + 207 * mm
    map_x, map_y = MARGIN_X + 2 * mm, 30 * mm
    map_w, map_h = panel_x - map_x - 2 * mm, 144 * mm
    c.setFillColor(HexColor("#EEF1EA"))
    c.rect(map_x, map_y, map_w, map_h, fill=1, stroke=0)
    draw_integrated_map(c, data, map_x, map_y, map_w, map_h, bbox=CORE_BBOX, show_core_boundary=False)
    panel_w = PAGE_W - MARGIN_X - panel_x - 5 * mm
    base.rounded_card(c, panel_x, 36 * mm, panel_w, 132 * mm, fill=CARD)
    card_title(c, "Lectura del mapa", panel_x + 6 * mm, 160 * mm, panel_w - 12 * mm)
    base.draw_bullets(
        c,
        [
            "El nucli edificat concentra la major part dels equipaments OSM i la xarxa quotidiana.",
            "Els espais verds i els cursos d'aigua formen una matriu territorial potent, pero no equivalen automaticament a recorreguts accessibles o segurs.",
            "El rectangle discontinu delimita el nucli de 130,4 ha on s'han calculat LiDAR i LST.",
            "37 equipaments OSM son punts de context; no s'han classificat com a refugis climatics sense verificacio municipal.",
        ],
        panel_x + 7 * mm,
        148 * mm,
        panel_w - 14 * mm,
        "body_small",
    )
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 8)
    c.drawCentredString(panel_x + panel_w / 2, 75 * mm, base.cat("LLEGENDA"))
    legend = [
        (HexColor("#B8D1A0"), "Zones verdes OSM"),
        (HexColor("#EEE9DF"), "Edificis Cadastre"),
        (HexColor("#3F9EC0"), "Aigua OSM"),
        (NAVY, "Equipaments OSM"),
    ]
    legend_x = panel_x + (panel_w - 44 * mm) / 2
    yy = 66 * mm
    for color, label in legend:
        c.setFillColor(color)
        c.setStrokeColor(color)
        c.rect(legend_x, yy, 7 * mm, 3.5 * mm, fill=1, stroke=1)
        c.setFillColor(INK)
        c.setFont("Arial", 7.2)
        c.drawString(legend_x + 10 * mm, yy, base.cat(label))
        yy -= 8.5 * mm
    base.draw_paragraph(
        c,
        "Figura 1. Mapa vectorial generat amb les capes realment incorporades al projecte. Fonts: Cadastre [D3] i OpenStreetMap [D6].",
        MARGIN_X + 4 * mm,
        26 * mm,
        CONTENT_W - 8 * mm,
        "source",
    )
    c.showPage()


def page_heat(c: canvas.Canvas, data: dict) -> None:
    section_header(c, "5", "Calor, ombra i capcada", "Tres lectures complementaries del nucli central", 6)
    gap = 5 * mm
    frame_w = (CONTENT_W - 2 * gap) / 3
    frame_y, frame_h = 72 * mm, 102 * mm
    maps = [
        ("Temperatura superficial", PROJECT / "maps" / "landsat_lst.png", [(HexColor("#2A7F60"), "menys calenta"), (ORANGE, "alta"), (RED, "mes alta")]),
        ("Ombra LiDAR - 15 h", PROJECT / "maps" / "lidar_shade.png", [(HexColor("#88BFD3"), "ombra parcial"), (NAVY, "ombra alta")]),
        ("Coberta de capcada", PROJECT / "maps" / "lidar_canopy.png", [(HexColor("#9DCA83"), "baixa"), (DARK_GREEN, "alta")]),
    ]
    for idx, (title, image_path, legend) in enumerate(maps):
        x = MARGIN_X + idx * (frame_w + gap)
        map_x, map_y, map_w, map_h = draw_map_frame(c, x, frame_y, frame_w, frame_h, title)
        draw_raster_map(c, image_path, data, CORE_BBOX, map_x, map_y, map_w, map_h)
        lx = x + 6 * mm
        ly = frame_y + 6 * mm
        for color, label in legend:
            c.setFillColor(color)
            c.rect(lx, ly, 5 * mm, 3 * mm, fill=1, stroke=0)
            c.setFillColor(INK)
            c.setFont("Arial", 6.2)
            c.drawString(lx + 7 * mm, ly, base.cat(label))
            lx += 29 * mm

    gap_m = 4 * mm
    mw = (CONTENT_W - 3 * gap_m) / 4
    mh = 29 * mm
    y = 38 * mm
    draw_metric(c, MARGIN_X, y, mw, mh, "46,7 C", "LST mitjana", "P10-P90: 38,7-51,1 C. [D2]", ORANGE)
    draw_metric(c, MARGIN_X + mw + gap_m, y, mw, mh, "61,7%", "Ombra directa", "Model solar a 2 m. [D1]", DARK_GREEN)
    draw_metric(c, MARGIN_X + 2 * (mw + gap_m), y, mw, mh, "31,8%", "Capcada", "Vegetacio mitjana i alta. [D1]", GREEN)
    draw_metric(c, MARGIN_X + 3 * (mw + gap_m), y, mw, mh, "98,6%", "DSM valid", "Cobertura de superficie LiDAR.", NAVY)
    base.rounded_card(c, MARGIN_X, 20 * mm, CONTENT_W, 14 * mm, fill=PALE_ORANGE)
    base.draw_paragraph(c, "<b>Lectura conjunta:</b> la LST assenyala superficies que acumulen calor; l'ombra i la capcada expliquen part de la proteccio potencial. Cap d'aquestes capes, per si sola, mesura temperatura de l'aire, UTCI, PET o risc clinic individual.", MARGIN_X + 7 * mm, 31 * mm, CONTENT_W - 14 * mm, "body_small")
    c.showPage()


def page_built_solar(c: canvas.Canvas, data: dict) -> None:
    section_header(c, "7", "Teixit construit, pendent i cobertes", "Cribratge ambiental previ, no projecte fotovoltaic", 8)
    gap = 7 * mm
    left_w = CONTENT_W * 0.58
    right_w = CONTENT_W - left_w - gap
    map_x, map_y, map_w, map_h = draw_map_frame(c, MARGIN_X, 61 * mm, left_w, 113 * mm, "Preseleccio geometrica de cobertes")
    draw_features(c, data["buildings"], CORE_BBOX, map_x, map_y, map_w, map_h, fill=HexColor("#E7E3DA"), stroke=HexColor("#A9A39A"), line_width=0.18)
    draw_features(
        c,
        data["roofs"],
        CORE_BBOX,
        map_x,
        map_y,
        map_w,
        map_h,
        fill=RED,
        stroke=WHITE,
        line_width=0.18,
        property_fill={"favorable": DARK_GREEN, "condicionada": ORANGE, "baixa": RED},
        property_name="solar_screen",
    )
    draw_north_scale(c, CORE_BBOX, map_x, map_y, map_w, map_h, 250)
    right_x = MARGIN_X + left_w + gap
    base.rounded_card(c, right_x, 61 * mm, right_w, 113 * mm, fill=CARD)
    card_title(c, "Resultats obtinguts", right_x + 6 * mm, 166 * mm, right_w - 12 * mm)
    base.draw_bullets(
        c,
        [
            "2.304 edificis cadastrals dins l'extensio general. [D3]",
            "1.504 edificis amb prou cel.les LiDAR per al cribratge.",
            "392 favorables, 351 condicionats i 761 de classe baixa segons pendent i orientacio de superficie.",
            "Pendent median del terreny del nucli: 2,1 graus; no descriu cada vorera ni cada acces.",
        ],
        right_x + 7 * mm,
        153 * mm,
        right_w - 14 * mm,
        "body_small",
    )
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 8)
    c.drawString(right_x + 6 * mm, 100 * mm, base.cat("LECTURA PROFESSIONAL"))
    base.draw_paragraph(
        c,
        "<b>Gestio ambiental:</b> el cribratge ajuda a ordenar inspeccions d'energia solar, cobertes fresques o verdes i ombra construida. <b>Salut publica:</b> l'energia local i la rehabilitacio poden aportar resiliencia, pero el mapa no quantifica pobresa energetica, temperatura interior ni benefici sanitari.",
        right_x + 6 * mm,
        94 * mm,
        right_w - 12 * mm,
        "body_small",
    )
    base.rounded_card(c, MARGIN_X, 25 * mm, CONTENT_W, 28 * mm, fill=PALE_ORANGE)
    base.draw_paragraph(c, "<b>Limitacio critica:</b> orientacio i pendent LiDAR no informen de capacitat estructural, propietat, instal.lacions, ombres anuals, potencia, connexio, proteccio patrimonial ni cost. Les 392 cobertes favorables son candidates a revisio tecnica, no instal.lacions recomanades.", MARGIN_X + 7 * mm, 47 * mm, CONTENT_W - 14 * mm, "body")
    c.showPage()


def page_copernicus_indicators(c: canvas.Canvas, data: dict) -> None:
    section_header(c, "6", "Indicadors Copernicus integrats", "Vegetacio, estat hidric, albedo i context atmosferic", 7)
    sentinel = data["sentinel"]
    context = data["context"]
    gap = 5 * mm
    frame_w = (CONTENT_W - 2 * gap) / 3
    frame_y, frame_h = 82 * mm, 92 * mm
    maps = [
        ("NDVI - vigor vegetal", PROJECT / "maps" / "sentinel2_ndvi.webp", [(HexColor("#80583D"), "baix"), (HexColor("#B8D27D"), "mitja"), (HexColor("#165E32"), "alt")]),
        ("NDMI - humitat relativa", PROJECT / "maps" / "sentinel2_ndmi.webp", [(HexColor("#A6572F"), "estres"), (HexColor("#E1DA9D"), "intermedi"), (HexColor("#226691"), "alt")]),
        ("Albedo espectral estimat", PROJECT / "maps" / "sentinel2_albedo.webp", [(HexColor("#2D3B47"), "baix"), (HexColor("#9FA397"), "mitja"), (HexColor("#F9EFCF"), "alt")]),
    ]
    for idx, (title, image_path, legend) in enumerate(maps):
        x = MARGIN_X + idx * (frame_w + gap)
        map_x, map_y, map_w, map_h = draw_map_frame(c, x, frame_y, frame_w, frame_h, title)
        draw_raster_map(c, image_path, data, CORE_BBOX, map_x, map_y, map_w, map_h)
        lx = x + 5 * mm
        ly = frame_y + 5 * mm
        for color, label in legend:
            c.setFillColor(color)
            c.rect(lx, ly, 4 * mm, 2.8 * mm, fill=1, stroke=0)
            c.setFillColor(INK)
            c.setFont("Arial", 5.8)
            c.drawString(lx + 5.5 * mm, ly, base.cat(label))
            lx += 23 * mm

    metrics = sentinel["metrics"]
    mw = (CONTENT_W - 2 * gap) / 3
    draw_metric(c, MARGIN_X, 48 * mm, mw, 27 * mm, str(metrics["ndvi"]["median"]).replace(".", ","), "NDVI median", "Escena 07/07/2026; 10 m. [D9]", GREEN)
    draw_metric(c, MARGIN_X + mw + gap, 48 * mm, mw, 27 * mm, str(metrics["ndmi"]["median"]).replace(".", ","), "NDMI median", "B11 nativa 20 m; no es humitat del sol. [D9]", BLUE)
    draw_metric(c, MARGIN_X + 2 * (mw + gap), 48 * mm, mw, 27 * mm, str(metrics["albedo"]["median"]).replace(".", ","), "Albedo median", "Conversio narrow-to-broadband publicada. [D9]", ORANGE)

    night = context.get("night_lst", {})
    soil = context.get("soil_moisture", {})
    no2 = context.get("no2", {})
    pm25 = context.get("pm25", {})
    base.rounded_card(c, MARGIN_X, 20 * mm, CONTENT_W, 22 * mm, fill=PALE_BLUE)
    context_text = (
        f"<b>Context supramunicipal, no mapa de carrer:</b> LST nocturna CLMS 3 km: {str(night.get('value_c', 'n/d')).replace('.', ',')} C; "
        f"NO2 troposferic Sentinel-5P: {no2.get('value_mol_m2', 'n/d')} mol/m2; "
        f"PM2,5 CAMS 10 km: {str(pm25.get('value_ug_m3', 'n/d')).replace('.', ',')} microg/m3. "
        f"Humitat superficial del sol CLMS 1 km: {str(soil.get('value_pct_saturation', 'n/d')).replace('.', ',')}% de saturacio. [D10]"
    )
    base.draw_paragraph(c, context_text, MARGIN_X + 7 * mm, 37 * mm, CONTENT_W - 14 * mm, "body_small")
    c.showPage()


def page_green_blue_flood(c: canvas.Canvas, data: dict) -> None:
    section_header(c, "8", "Infraestructura verda, blava i inundabilitat", "Beneficis potencials i compatibilitat amb el risc", 9)
    gap = 7 * mm
    frame_w = (CONTENT_W - gap) / 2
    left_x = MARGIN_X
    mx, my, mw, mh = draw_map_frame(c, left_x, 64 * mm, frame_w, 110 * mm, "Verd, aigua i equipaments")
    draw_features(c, data["green"], MAP_BBOX, mx, my, mw, mh, fill=HexColor("#B8D1A0"), stroke=HexColor("#6D9B61"), line_width=0.45)
    draw_features(c, data["water"], MAP_BBOX, mx, my, mw, mh, fill=None, stroke=BLUE, line_width=0.85)
    draw_features(c, data["facilities"], MAP_BBOX, mx, my, mw, mh, fill=NAVY, stroke=WHITE, line_width=0.5, point_radius=1.5)
    draw_north_scale(c, MAP_BBOX, mx, my, mw, mh)
    right_x = MARGIN_X + frame_w + gap
    fx, fy, fw, fh = draw_map_frame(c, right_x, 64 * mm, frame_w, 110 * mm, "SNCZI - zona inundable T=100 anys")
    draw_integrated_map(c, data, fx, fy, fw, fh)
    flood_path = PROJECT / "raw" / "inundabilitat" / "snczi_q100_la_seu_bbox.png"
    c.drawImage(ImageReader(str(flood_path)), fx, fy, fw, fh, preserveAspectRatio=False, mask="auto")
    draw_north_scale(c, MAP_BBOX, fx, fy, fw, fh)
    base.rounded_card(c, MARGIN_X, 26 * mm, frame_w, 31 * mm, fill=PALE_GREEN)
    base.draw_paragraph(c, "<b>Gestio ambiental.</b> Els 92 poligons verds i 98 elements d'aigua OSM descriuen una matriu potencial de refrigeracio, biodiversitat i drenatge. Cal auditar continuïtat, accessibilitat, estat, cabal, seguretat i manteniment abans de definir rutes.", MARGIN_X + 7 * mm, 51 * mm, frame_w - 14 * mm, "body_small")
    base.rounded_card(c, right_x, 26 * mm, frame_w, 31 * mm, fill=PALE_BLUE)
    base.draw_paragraph(c, "<b>Salut i proteccio civil.</b> Un espai fresc no es adequat com a ruta o refugi si queda afectat per inundacio o no es operatiu durant una emergencia. El WMS T=100 s'ha visualitzat, pero no s'ha calculat area ni poblacio exposada. [D5, H9]", right_x + 7 * mm, 51 * mm, frame_w - 14 * mm, "body_small")
    c.showPage()


def page_population_health(c: canvas.Canvas, data: dict) -> None:
    section_header(c, "9", "Poblacio, vulnerabilitat i salut", "Que sabem, que no sabem i com prioritzar amb equitat", 10)
    demo = data["demography"]
    left_w = CONTENT_W * 0.43
    right_x = MARGIN_X + left_w + 8 * mm
    right_w = CONTENT_W - left_w - 8 * mm
    base.rounded_card(c, MARGIN_X, 81 * mm, left_w, 94 * mm, fill=CARD)
    card_title(c, "Estructura d'edats 2025", MARGIN_X + 7 * mm, 167 * mm, left_w - 14 * mm)
    bar_x, bar_y, bar_w, bar_h = MARGIN_X + 8 * mm, 139 * mm, left_w - 16 * mm, 10 * mm
    age_parts = [
        (12.3, BLUE, "0-14", "1.597"),
        (67.6, GREEN, "15-64", "8.789"),
        (16.6, ORANGE, "65-84", "2.164"),
        (3.5, PURPLE, "85+", "453"),
    ]
    cursor = bar_x
    for pct, color, label, count in age_parts:
        width = bar_w * pct / 100
        c.setFillColor(color)
        c.rect(cursor, bar_y, width, bar_h, fill=1, stroke=0)
        cursor += width
    yy = 125 * mm
    for idx, (pct, color, label, count) in enumerate(age_parts):
        col = idx % 2
        row = idx // 2
        xx = MARGIN_X + 8 * mm + col * (left_w / 2 - 4 * mm)
        y = yy - row * 13 * mm
        c.setFillColor(color)
        c.circle(xx + 2 * mm, y + 1 * mm, 2.2 * mm, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Arial", 7.5)
        c.drawString(xx + 7 * mm, y - 1 * mm, f"{label}: {count} ({str(pct).replace('.', ',')}%)")
    draw_metric(c, MARGIN_X + 8 * mm, 83 * mm, left_w - 16 * mm, 25 * mm, "20,1%", "Poblacio de 65 anys o mes", "2.617 persones; agregat municipal. [D4]", PURPLE)
    base.rounded_card(c, right_x, 81 * mm, right_w, 94 * mm, fill=PALE_BLUE)
    card_title(c, "Lectura medica prudent", right_x + 7 * mm, 167 * mm, right_w - 14 * mm)
    base.draw_bullets(
        c,
        [
            "La calor pot causar deshidratacio, esgotament, cop de calor i lesio renal aguda, i agreujar patologia cardiovascular, respiratoria, diabetis i salut mental. [H1]",
            "Canal Salut identifica risc especial en majors de 75 anys, infants menors de 4, malalties croniques, discapacitat, medicacio rellevant, solitud i treball en calor. [H5]",
            "Els grups d'Idescat no permeten quantificar majors de 75 ni combinar edat amb diagnostic, habitatge, renda, solitud o mobilitat.",
            "Per tant, 20,1% de poblacio 65+ es un indicador de planificacio, no una estimacio de persones clinicament vulnerables.",
        ],
        right_x + 8 * mm,
        153 * mm,
        right_w - 16 * mm,
        "body_small",
    )
    base.rounded_card(c, MARGIN_X, 27 * mm, CONTENT_W, 45 * mm, fill=PALE_ORANGE)
    card_title(c, "Implicacio de gestio", MARGIN_X + 7 * mm, 65 * mm, CONTENT_W - 14 * mm)
    base.draw_bullets(
        c,
        [
            "Prioritzar itineraris cap a CAP, serveis socials, compres, escoles, parades i espais d'estada; els 37 equipaments OSM son una base d'auditoria, no una xarxa de refugis.",
            "Coordinar Salut, urbanisme, serveis socials, proteccio civil i manteniment; afegir coneixement local sense publicar dades personals de salut.",
            "Mesurar accessibilitat, ombra, descans, aigua, horaris i us real abans d'afirmar que una intervencio redueix risc sanitari.",
        ],
        MARGIN_X + 8 * mm,
        53 * mm,
        CONTENT_W - 16 * mm,
        "body_small",
    )
    c.showPage()


def page_diagnosis_matrix(c: canvas.Canvas) -> None:
    section_header(c, "10", "Diagnosi integrada", "Evidencia, lectura ambiental, lectura medica i decisio", 11)
    rows = [
        [base.P("Tema", "table_bold"), base.P("Evidencia obtinguda", "table_bold"), base.P("Gestio ambiental", "table_bold"), base.P("Salut publica", "table_bold"), base.P("Decisio", "table_bold")],
        [base.P("Calor", "table"), base.P("LST 46,7 C; P10-P90 38,7-51,1 C.", "table"), base.P("Superficies amb acumulacio termica; contrastar a carrer.", "table"), base.P("Indicador de perill superficial, no dosi humana.", "table"), base.P("Campanya microclimatica en trams calents i molt utilitzats.", "table")],
        [base.P("Ombra i capcada", "table"), base.P("61,7% d'ombra; 31,8% de capcada.", "table"), base.P("Proteccio rellevant a escala d'ambit, possible discontinuïtat de xarxa.", "table"), base.P("Reduccio plausible de carrega radiant i suport a mobilitat durant calor.", "table"), base.P("Tancar buits d'ombra sobre recorreguts essencials.", "table")],
        [base.P("Verd i aigua", "table"), base.P("92 poligons verds; 98 elements d'aigua OSM.", "table"), base.P("Matriu de serveis ecosistemics potencials.", "table"), base.P("Beneficis depenen de qualitat, acces, seguretat i us. [H2, H3]", "table"), base.P("Auditar connexions i evitar atribuir benefici per mera proximitat.", "table")],
        [base.P("Inundabilitat", "table"), base.P("Lamina oficial T=100 visible al WMS.", "table"), base.P("Condiciona rutes, refugis i actuacions a la ribera.", "table"), base.P("El risc de desastre pot afectar lesions, salut i serveis essencials. [H9]", "table"), base.P("Creuar la xarxa climatica amb protocols i rutes segures d'emergencia.", "table")],
        [base.P("Poblacio", "table"), base.P("13.003 habitants; 20,1% amb 65+.", "table"), base.P("Cal planificacio equitativa i de proximitat.", "table"), base.P("Edat sola no defineix vulnerabilitat; manquen factors clinics i socials.", "table"), base.P("Prioritzar sense geolocalitzar salut individual; treball intersectorial.", "table")],
        [base.P("Cobertes", "table"), base.P("1.504 analitzades; 392 favorables geomètricament.", "table"), base.P("Cartera d'inspeccions per energia i rehabilitacio.", "table"), base.P("No quantifica confort interior ni pobresa energetica.", "table"), base.P("Estudi tecnic i social abans de seleccionar inversions.", "table")],
    ]
    table = base.make_table(rows, [25 * mm, 47 * mm, 51 * mm, 51 * mm, CONTENT_W - 174 * mm], font_size=6.7)
    base.table_on_canvas(c, table, MARGIN_X, 174 * mm)
    base.rounded_card(c, MARGIN_X, 24 * mm, CONTENT_W, 24 * mm, fill=PALE_GREEN)
    base.draw_paragraph(c, "<b>Conclusio tecnica:</b> la Seu disposa d'actius ambientals i d'una base cartografica suficient per prioritzar una xarxa climatica. La prioritat es convertir cobertura potencial en proteccio utilitzable, continua, segura davant inundacions i orientada a persones amb menys capacitat d'evitar l'exposicio.", MARGIN_X + 7 * mm, 43 * mm, CONTENT_W - 14 * mm, "body")
    c.showPage()


def page_actions(c: canvas.Canvas) -> None:
    section_header(c, "11", "Programa d'actuacio", "Prioritats compartides, terminis i criteris de verificacio", 12)
    actions = [
        ("P1", DARK_GREEN, "Auditar la xarxa climatica", "0-6 mesos", "Recorreguts, voreres, ombra, bancs, aigua, lavabos, pendents, creuaments, horaris i capacitat dels equipaments.", "Trams auditats; incidencies critiques resoltes o senyalitzades."),
        ("P2", ORANGE, "Tancar discontinuïtats de proteccio", "0-24 mesos", "Arbrat viable, pergoles, ombra temporal, materials i descans en punts calents i d'espera; integrar reg i drenatge.", "Metres de xarxa amb ombra a hores acordades; supervivencia i manteniment."),
        ("P3", PURPLE, "Protocol calor-salut i equitat", "abans de cada estiu", "Coordinar Salut, CAP, serveis socials i proteccio civil; comunicacio accessible i seguiment de persones vulnerables segons protocols oficials.", "Protocol actiu; equipaments verificats; cobertura de comunicacio."),
        ("P4", BLUE, "Compatibilitzar frescor i inundabilitat", "0-12 mesos", "Revisar rutes, estades i equipaments davant la lamina T=100 i els plans d'emergencia; no concentrar funcions critiques en punts vulnerables.", "Rutes alternatives definides; punts conflictius documentats."),
        ("P5", NAVY, "Verificar cobertes candidates", "6-24 mesos", "Estudi estructural, energetic, patrimonial i social de les 392 cobertes favorables; prioritzar equipaments i comunitats amb criteris publics.", "Cobertes inspeccionades; projectes viables; energia i co-beneficis mesurats."),
        ("P6", RED, "Mesurar i revisar", "cada estiu", "Campanyes microclimatiques, comptatge d'us, enquesta breu, actualitzacio LiDAR/LST i registre de manteniment.", "Canvi d'exposicio i us amb metode estable; incertesa publicada."),
    ]
    y = 157 * mm
    h = 21.5 * mm
    gap = 3.2 * mm
    for code, color, title, horizon, action, indicator in actions:
        base.rounded_card(c, MARGIN_X, y, CONTENT_W, h, fill=CARD)
        c.setFillColor(color)
        c.circle(MARGIN_X + 10 * mm, y + h / 2, 5.7 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Arial-Bold", 8)
        c.drawCentredString(MARGIN_X + 10 * mm, y + h / 2 - 2.7, code)
        c.setFillColor(NAVY)
        c.setFont("Arial-Bold", 8.8)
        c.drawString(MARGIN_X + 21 * mm, y + h - 7 * mm, base.cat(title))
        c.setFillColor(color)
        c.setFont("Arial-Bold", 7)
        c.drawRightString(PAGE_W - MARGIN_X - 6 * mm, y + h - 7 * mm, horizon)
        base.draw_paragraph(c, action, MARGIN_X + 21 * mm, y + h - 10.5 * mm, 120 * mm, "body_small")
        base.draw_paragraph(c, f"<b>Indicador:</b> {indicator}", MARGIN_X + 146 * mm, y + h - 10.5 * mm, CONTENT_W - 152 * mm, "body_small")
        y -= h + gap
    base.rounded_card(c, MARGIN_X, 19 * mm, CONTENT_W, 11 * mm, fill=PALE_GREEN)
    base.draw_paragraph(c, "<b>Ordre de decisio:</b> primer seguretat i poblacio amb menys capacitat d'evitar l'exposicio; despres continuïtat i manteniment de la xarxa; finalment ampliacio de cobertura i projectes demostratius.", MARGIN_X + 7 * mm, 27 * mm, CONTENT_W - 14 * mm, "body_small")
    c.showPage()


def page_monitoring(c: canvas.Canvas) -> None:
    section_header(c, "12", "Seguiment ambiental i sanitari", "Indicadors, governanca i disseny d'avaluacio", 13)
    gap = 6 * mm
    col_w = (CONTENT_W - 2 * gap) / 3
    y, h = 101 * mm, 73 * mm
    blocks = [
        ("A. Exposicio ambiental", PALE_GREEN, ["Temperatura i humitat de l'aire.", "Radiacio / globus i vent.", "Ombra per tram i franja horaria.", "Capcada sobre xarxa peatonal.", "Punts calents Landsat repetibles.", "Inundabilitat i operativitat de rutes."]),
        ("B. Us, autonomia i equitat", PALE_BLUE, ["Comptatges a rutes i espais.", "Temps i barreres fins a equipaments.", "Obertura, aigua, seients i lavabos.", "Enquesta breu de confort i seguretat.", "Participacio de gent gran i mobilitat reduida.", "Resultats agregats, sense dades personals." ]),
        ("C. Salut publica", PALE_ORANGE, ["Vigilancia segons sistemes oficials existents.", "Protocol d'alerta i coordinacio intersectorial.", "No atribuir canvis de salut al mapa sense disseny.", "Definir abans indicadors i comparadors.", "Avaluacio etica i proteccio de dades.", "Publicar limitacions i possibles confusions." ]),
    ]
    for idx, (title, fill, bullets) in enumerate(blocks):
        x = MARGIN_X + idx * (col_w + gap)
        base.rounded_card(c, x, y, col_w, h, fill=fill)
        card_title(c, title, x + 6 * mm, y + h - 6 * mm, col_w - 12 * mm)
        base.draw_bullets(c, bullets, x + 6 * mm, y + h - 19 * mm, col_w - 12 * mm, "body_small")
    rows = [
        [base.P("Pregunta", "table_bold"), base.P("Indicador minim", "table_bold"), base.P("Disseny recomanat", "table_bold"), base.P("Precaucio", "table_bold")],
        [base.P("Ha baixat l'exposicio?", "table"), base.P("Ombra, radiacio i microclima per tram", "table"), base.P("Abans-despres amb dies comparables", "table"), base.P("Controlar meteorologia i hora", "table")],
        [base.P("S'utilitza la xarxa?", "table"), base.P("Comptatge, recorreguts i enquesta", "table"), base.P("Mostreig repetit en calor i dies normals", "table"), base.P("No confondre presencia amb benefici", "table")],
        [base.P("Es equitativa?", "table"), base.P("Accessibilitat per grups i barreres", "table"), base.P("Participacio i analisi agregada", "table"), base.P("No publicar dades sensibles", "table")],
        [base.P("Ha millorat la salut?", "table"), base.P("Indicadors sanitaris predefinits", "table"), base.P("Avaluacio epidemiologica especifica", "table"), base.P("Evitar atribucio causal simple", "table")],
    ]
    table = base.make_table(rows, [52 * mm, 60 * mm, 62 * mm, CONTENT_W - 174 * mm], font_size=7.0)
    base.table_on_canvas(c, table, MARGIN_X, 91 * mm)
    base.rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 16 * mm, fill=CARD)
    base.draw_paragraph(c, "<b>Criteri de qualitat:</b> una millora cartografica o un augment d'arbres no demostra per si sol menys risc. Cal verificar que l'actuacio funciona, es accessible, s'utilitza i redueix exposicio en condicions comparables.", MARGIN_X + 7 * mm, 34 * mm, CONTENT_W - 14 * mm, "body_small")
    c.showPage()


def page_data_references(c: canvas.Canvas) -> None:
    section_header(c, "13", "Fonts de dades", "Referencies oficials i artefactes del projecte", 14)
    gap = 7 * mm
    col_w = (CONTENT_W - gap) / 2
    left_x = MARGIN_X
    right_x = MARGIN_X + col_w + gap
    base.rounded_card(c, left_x, 39 * mm, col_w, 136 * mm, fill=CARD)
    base.rounded_card(c, right_x, 39 * mm, col_w, 136 * mm, fill=CARD)
    card_title(c, "Dades territorials i teledeteccio", left_x + 6 * mm, 168 * mm, col_w - 12 * mm)
    left_refs = [
        "<b>D1.</b> ICGC. <i>LiDAR Territorial v3.1 (2021-2023)</i>, LAZ/LAS 1.4, EPSG:25831, CC BY 4.0. <link href='https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Elevacions/Elevacions-territorial/LiDAR-Territorial' color='#173D6D'>icgc.cat</link>.",
        "<b>D2.</b> U.S. Geological Survey, EROS. <i>Landsat Collection 2 Level-2 Surface Temperature</i>. Escena LC09_L2SP_198030_20260708_02_T1. <link href='https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-st' color='#173D6D'>USGS STAC</link>; DOI 10.5066/P9OGBGM6.",
        "<b>D3.</b> Direccio General del Cadastre. <i>INSPIRE Buildings - La Seu d'Urgell, 25252</i>, ATOM/GML, actualitzacio de l'index 20/02/2026. <link href='https://www.catastro.hacienda.gob.es/webinspire/index.html' color='#173D6D'>catastro.hacienda.gob.es</link>.",
        "<b>D4.</b> Idescat. API <i>El municipi en xifres</i>, codi 252038; dades 2025 del Cens de poblacio anual de l'INE, actualitzades 25/02/2026. <link href='https://api.idescat.cat/emex/v1/geo/252038.json' color='#173D6D'>api.idescat.cat</link>.",
    ]
    y = 155 * mm
    for ref in left_refs:
        used = base.draw_paragraph(c, ref, left_x + 6 * mm, y, col_w - 12 * mm, "ref")
        y -= used + 4 * mm
    card_title(c, "Risc, xarxa urbana i context", right_x + 6 * mm, 168 * mm, col_w - 12 * mm)
    right_refs = [
        "<b>D5.</b> MITECO. Sistema Nacional de Cartografia de Zones Inundables. WMS <i>ZI_LaminasQ100</i>, capa NZ.RiskZone. <link href='https://www.miteco.gob.es/es/agua/temas/gestion-de-los-riesgos-de-inundacion/snczi/acceso-servicio-wms.html' color='#173D6D'>miteco.gob.es</link>.",
        "<b>D6.</b> OpenStreetMap contributors. Extracte OSM XML de l'extensio, ODbL 1.0. <link href='https://www.openstreetmap.org/copyright' color='#173D6D'>openstreetmap.org/copyright</link>.",
        "<b>D7.</b> Ajuntament de la Seu d'Urgell. <i>La gestio actual del verd urba</i>: 22 ha, 5.500 arbres i 80 especies; recompte agregat, no inventari georeferenciat. <link href='https://www.laseu.cat/viure-a-la-seu/mediambient/ecoturisme-la-seu-naturalment/per-que-es-important-el-verd-urba/on-som-la-gestio-actual-del-verd-urba' color='#173D6D'>laseu.cat</link>.",
        "<b>D8.</b> EcoRadar. <i>data_sources_matrix.md</i>, <i>layer_manifest.json</i>, capes processades i informe de validacio del projecte LaSeu_Urba, 10-12/07/2026.",
        "<b>D9.</b> Copernicus Data Space Ecosystem / ESA. <i>Sentinel-2 MSI L2A</i>, escena S2A 07/07/2026, STAC + OAuth2 + Process API. NDVI, NDMI i albedo derivats amb mascara SCL.",
        "<b>D10.</b> Copernicus CLMS, Sentinel-5P i CAMS/ECMWF. LST nocturna 3 km, columna troposferica NO2 i PM2,5 europeu 10 km; context agregat, no carrer.",
    ]
    y = 155 * mm
    for ref in right_refs:
        used = base.draw_paragraph(c, ref, right_x + 6 * mm, y, col_w - 12 * mm, "ref")
        y -= used + 4 * mm
    base.rounded_card(c, MARGIN_X, 20 * mm, CONTENT_W, 13 * mm, fill=PALE_GREEN)
    base.draw_paragraph(c, "Totes les xifres del cos de l'informe provenen d'aquestes fonts o de derivacions documentades al projecte. Fonts web verificades el 10-12/07/2026.", MARGIN_X + 7 * mm, 30 * mm, CONTENT_W - 14 * mm, "source")
    c.showPage()


def page_health_references(c: canvas.Canvas) -> None:
    section_header(c, "14", "Fonts de salut i criteris d'us", "Evidencia poblacional, limitacions i prudencia clinica", 15)
    gap = 7 * mm
    col_w = (CONTENT_W - gap) / 2
    left_x, right_x = MARGIN_X, MARGIN_X + col_w + gap
    base.rounded_card(c, left_x, 49 * mm, col_w, 126 * mm, fill=CARD)
    base.rounded_card(c, right_x, 49 * mm, col_w, 126 * mm, fill=CARD)
    card_title(c, "Calor, ciutat i vulnerabilitat", left_x + 6 * mm, 168 * mm, col_w - 12 * mm)
    refs_left = [
        "<b>H1.</b> World Health Organization (28/04/2026). <i>Heat and health</i>. <link href='https://www.who.int/news-room/fact-sheets/detail/climate-change-heat-and-health' color='#173D6D'>who.int</link>.",
        "<b>H4.</b> European Climate and Health Observatory / EEA. <i>Heat and health</i>. <link href='https://climate-adapt.eea.europa.eu/en/observatory/topics/health-impacts/heat-and-health' color='#173D6D'>climate-adapt.eea.europa.eu</link>.",
        "<b>H5.</b> Canal Salut (actualitzat 26/05/2026). <i>Especial precaucio amb les persones mes vulnerables a la calor</i>. <link href='https://canalsalut.gencat.cat/ca/vida-saludable/consells-estacionals/estiu/calor/especial-precaucio-persones-mes-vulnerables/' color='#173D6D'>canalsalut.gencat.cat</link>.",
        "<b>H7.</b> WHO Regional Office for Europe (2023). <i>Urban and built environments</i>. <link href='https://www.who.int/europe/news-room/fact-sheets/item/urban-and-built-environments' color='#173D6D'>who.int/europe</link>.",
        "<b>H9.</b> WHO Regional Office for Europe (2022). <i>Protecting environments and health by building urban resilience</i>. <link href='https://www.who.int/europe/news/item/13-06-2022-who-europe-reports-on-the-contribution-of-urban-planning-and-management-to-resilience-and-health-protection' color='#173D6D'>who.int/europe</link>.",
    ]
    y = 155 * mm
    for ref in refs_left:
        used = base.draw_paragraph(c, ref, left_x + 6 * mm, y, col_w - 12 * mm, "ref")
        y -= used + 3.1 * mm
    card_title(c, "Verd, blau, mobilitat i benestar", right_x + 6 * mm, 168 * mm, col_w - 12 * mm)
    refs_right = [
        "<b>H2.</b> WHO Regional Office for Europe (2016). <i>Urban green spaces and health</i>. WHO/EURO:2016-3352-43111-60341. <link href='https://www.who.int/europe/publications/i/item/WHO-EURO-2016-3352-43111-60341' color='#173D6D'>who.int/europe</link>.",
        "<b>H3.</b> WHO Regional Office for Europe (2021). <i>Green and blue spaces and mental health</i>. ISBN 9789289055666. <link href='https://www.who.int/europe/publications/i/item/9789289055666' color='#173D6D'>who.int/europe</link>.",
        "<b>H6.</b> WHO Regional Office for Europe (2022). <i>Urban design for health</i>. WHO/EURO:2022-5961-45726-65769. <link href='https://www.who.int/europe/publications/i/item/WHO-EURO-2022-5961-45726-65769' color='#173D6D'>who.int/europe</link>.",
        "<b>H8.</b> WHO (2025). <i>Green spaces: sectoral solutions for air pollution and health</i>. <link href='https://www.who.int/publications/i/item/B09366' color='#173D6D'>who.int</link>.",
    ]
    y = 155 * mm
    for ref in refs_right:
        used = base.draw_paragraph(c, ref, right_x + 6 * mm, y, col_w - 12 * mm, "ref")
        y -= used + 3.5 * mm
    base.rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 20 * mm, fill=PALE_ORANGE)
    base.draw_paragraph(c, "<b>Criteri d'us:</b> l'informe aplica evidencia de salut poblacional per orientar l'entorn urba. No ha mesurat morbiditat, mortalitat, ingressos, medicacio, temperatura interior ni exposicio individual a la Seu. No s'han calculat casos evitats ni estalvis sanitaris.", MARGIN_X + 7 * mm, 37 * mm, CONTENT_W - 14 * mm, "body_small")
    c.showPage()


def territorial_quality_profile(data: dict) -> dict:
    """Build the transparent, non-normative IQT profile from report indicators."""
    lidar = data["manifest"]["lidar"]
    extended = data["extended"]["metrics"]
    sentinel = data["sentinel"]["metrics"]
    soil = data["context"]["soil_moisture"]

    shade = float(lidar["shade_pct"])
    urban_green = (float(lidar["canopy_cover_pct"]) + float(extended["vegetation_cover_area_pct"])) / 2
    vegetation_vigour = 50 * (float(sentinel["ndvi"]["median"]) + 1)
    vegetation_moisture = 50 * (float(sentinel["ndmi"]["median"]) + 1)
    water_state = (vegetation_moisture + float(soil["value_pct_saturation"])) / 2
    permeability = 100 - float(extended["imperviousness_mean_pct"])
    low_runoff = 100 - float(extended["runoff_proxy_mean_0_100"])

    dimensions = [
        {"label": "Ombra", "value": round(shade, 1), "formula": "ombra LiDAR (%)"},
        {
            "label": "Verd urbà",
            "value": round(urban_green, 1),
            "formula": "mitjana de capçada LiDAR (%) i cobertura vegetal HRL (%)",
        },
        {
            "label": "Vigor vegetal",
            "value": round(vegetation_vigour, 1),
            "formula": "50 × (NDVI medià + 1)",
        },
        {
            "label": "Estat hídric",
            "value": round(water_state, 1),
            "formula": "mitjana de 50 × (NDMI medià + 1) i humitat superficial del sòl (%)",
        },
        {
            "label": "Permeabilitat",
            "value": round(permeability, 1),
            "formula": "100 − impermeabilització mitjana (%)",
        },
        {
            "label": "Baixa escorrentia",
            "value": round(low_runoff, 1),
            "formula": "100 − índex relatiu d'escorrentia (0–100)",
        },
    ]
    iqt = round(sum(item["value"] for item in dimensions) / len(dimensions))
    return {
        "index_name": "Índex de Qualitat Territorial EcoRadar",
        "acronym": "IQT",
        "value_0_100": iqt,
        "aggregation": "mitjana aritmètica amb el mateix pes per a les sis dimensions",
        "dimensions": dimensions,
        "status": "indicador compost intern de cribratge; no és un índex oficial ni normatiu",
        "interpretation_limit": (
            "Resumeix condicions territorials de l'àmbit raster central. No mesura qualitat de vida, "
            "salut individual, biodiversitat ni causalitat, i no s'ha d'usar per comparar ciutats sense "
            "un protocol comú de dates, resolucions i mostreig."
        ),
    }


def fitxa_panel(c: canvas.Canvas, x: float, y: float, w: float, h: float, number: str, title: str, subtitle: str) -> None:
    c.setFillColor(CARD)
    c.setStrokeColor(HexColor("#D6E0D8"))
    c.setLineWidth(0.45)
    c.roundRect(x, y, w, h, 3.8, fill=1, stroke=1)
    c.setFillColor(ORANGE)
    c.roundRect(x + 4 * mm, y + h - 9.6 * mm, 10 * mm, 0.9 * mm, 0.4, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 7.8)
    c.drawString(x + 4 * mm, y + h - 7 * mm, base.cat(f"{number}. {title}"))
    c.setFillColor(INK)
    c.setFont("Arial", 5.2)
    c.drawString(x + 4 * mm, y + h - 12 * mm, base.cat(subtitle[:72]))


def fitxa_metric(c: canvas.Canvas, x: float, y: float, w: float, h: float, value: str, label: str, accent=GREEN) -> None:
    c.setFillColor(HexColor("#EEF5EE"))
    c.setStrokeColor(RULE)
    c.roundRect(x, y, w, h, 2.2, fill=1, stroke=1)
    c.setFillColor(accent)
    c.setFont("Arial-Bold", 8.0)
    c.drawString(x + 2.2 * mm, y + h - 5.0 * mm, base.cat(value)[:14])
    c.setFillColor(MUTED)
    c.setFont("Arial", 4.6)
    c.drawString(x + 2.2 * mm, y + 2.8 * mm, base.cat(label)[:28])


def fitxa_para_fit(
    c: canvas.Canvas,
    text: str,
    x: float,
    y_top: float,
    width: float,
    max_height: float,
    *,
    font_size: float = 5.5,
    min_font_size: float = 4.5,
    color=INK,
    bold: bool = False,
) -> float:
    size = font_size
    while size >= min_font_size:
        style = base.STYLES["body_small"].clone(f"fitxa_{size:.2f}_{x}_{y_top}")
        style.fontName = "Arial-Bold" if bold else "Arial"
        style.fontSize = size
        style.leading = size * 1.22
        style.textColor = color
        paragraph = Paragraph(base.cat(text), style)
        _, height = paragraph.wrap(width, 1000)
        if height <= max_height:
            paragraph.drawOn(c, x, y_top - height)
            return height
        size -= 0.2
    paragraph.drawOn(c, x, y_top - height)
    return height


def draw_iqt_radar(c: canvas.Canvas, profile: dict, cx: float, cy: float, radius: float) -> None:
    dimensions = profile["dimensions"]
    count = len(dimensions)
    c.setLineWidth(0.45)
    for step in range(1, 6):
        r = radius * step / 5
        points = []
        for idx in range(count):
            angle = math.pi / 2 - idx * 2 * math.pi / count
            points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
        path = c.beginPath()
        path.moveTo(*points[0])
        for point in points[1:]:
            path.lineTo(*point)
        path.close()
        c.setStrokeColor(HexColor("#D5DDD4"))
        c.drawPath(path, fill=0, stroke=1)

    for idx in range(count):
        angle = math.pi / 2 - idx * 2 * math.pi / count
        c.setStrokeColor(HexColor("#AAB8AD"))
        c.line(cx, cy, cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)

    points = []
    for idx, item in enumerate(dimensions):
        angle = math.pi / 2 - idx * 2 * math.pi / count
        r = radius * max(0, min(100, item["value"])) / 100
        points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    path = c.beginPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    path.close()
    c.setFillColor(HexColor("#7BA96B"))
    c.setStrokeColor(DARK_GREEN)
    c.setLineWidth(1.25)
    c.drawPath(path, fill=1, stroke=1)
    for px, py in points:
        c.setFillColor(DARK_GREEN)
        c.circle(px, py, 0.9 * mm, fill=1, stroke=0)

    label_radius = radius + 6.4 * mm
    for idx, item in enumerate(dimensions):
        angle = math.pi / 2 - idx * 2 * math.pi / count
        lx = cx + math.cos(angle) * label_radius
        ly = cy + math.sin(angle) * label_radius
        c.setFillColor(INK)
        c.setFont("Arial", 4.5)
        label = base.cat(item["label"])
        if math.cos(angle) > 0.25:
            # Keep right-hand labels inside the radar panel.
            c.drawRightString(lx, ly, label)
            c.setFont("Arial-Bold", 4.5)
            c.drawRightString(lx, ly - 2.8 * mm, f"{item['value']:.0f}")
        elif math.cos(angle) < -0.25:
            # Keep left-hand labels inside the radar panel.
            c.drawString(lx, ly, label)
            c.setFont("Arial-Bold", 4.5)
            c.drawString(lx, ly - 2.8 * mm, f"{item['value']:.0f}")
        else:
            c.drawCentredString(lx, ly, label)
            c.setFont("Arial-Bold", 4.5)
            c.drawCentredString(lx, ly - 2.8 * mm, f"{item['value']:.0f}")

    c.setFillColor(colors.white)
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.1)
    c.circle(cx, cy, 7.0 * mm, fill=1, stroke=1)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 10.5)
    c.drawCentredString(cx, cy + 1.5 * mm, str(profile["value_0_100"]))
    c.setFont("Arial-Bold", 3.25)
    c.drawCentredString(cx, cy - 1.8 * mm, "ÍNDEX DE QUALITAT")
    c.drawCentredString(cx, cy - 4.0 * mm, "TERRITORIAL / 100")


def build_urban_fitxa(path: Path, data: dict, profile: dict) -> None:
    """Render the frozen-v1-inspired A4 portrait urban decision sheet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = A4
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    c.setTitle("Fitxa EcoRadar Urbà La Seu d'Urgell - Índex de Qualitat Territorial")
    c.setAuthor("EcoRadar")
    c.setSubject("Síntesi executiva de la diagnosi integrada ambiental i de salut pública")
    c.setFillColor(BG)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    m = 5 * mm

    # Capçalera i estat global.
    c.setFillColor(NAVY)
    c.roundRect(m, 268 * mm, 132 * mm, 24 * mm, 4.5, fill=1, stroke=0)
    c.setFillColor(HexColor("#DDEBDD"))
    c.circle(m + 12 * mm, 280 * mm, 8.5 * mm, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 13)
    c.drawCentredString(m + 12 * mm, 278.5 * mm, "01")
    c.setFillColor(colors.white)
    c.setFont("Arial-Bold", 13.2)
    c.drawString(m + 25 * mm, 282.2 * mm, "FITXA ECORADAR URBÀ")
    c.setFont("Arial-Bold", 8.1)
    c.drawString(m + 25 * mm, 275.2 * mm, "LA SEU D'URGELL · QUALITAT TERRITORIAL I BENESTAR")
    c.setFillColor(CARD)
    c.setStrokeColor(RULE)
    c.roundRect(141 * mm, 268 * mm, 64 * mm, 24 * mm, 4, fill=1, stroke=1)
    c.setFillColor(ORANGE)
    c.roundRect(146 * mm, 286.3 * mm, 16 * mm, 1.1 * mm, 0.5, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 6.1)
    c.drawString(146 * mm, 283.7 * mm, "ESTAT TERRITORIAL")
    c.setFillColor(GREEN)
    c.setFont("Arial-Bold", 8.0)
    c.drawString(146 * mm, 278.8 * mm, "Favorable però vulnerable")
    fitxa_para_fit(
        c,
        "Actius territorials rellevants, però encara cal reforçar autonomia, equitat i continuïtat dels entorns i serveis.",
        146 * mm,
        274.7 * mm,
        54 * mm,
        8 * mm,
        font_size=5.2,
        min_font_size=4.7,
        color=MUTED,
    )

    # 1. Mosaic urbà.
    fitxa_panel(c, m, 181 * mm, 75 * mm, 82 * mm, "1", "Mosaic urbà", "Quina estructura sosté el confort territorial?")
    c.setFillColor(HexColor("#EEF1EA"))
    c.rect(9 * mm, 205 * mm, 67 * mm, 42 * mm, fill=1, stroke=0)
    draw_integrated_map(c, data, 9 * mm, 205 * mm, 67 * mm, 42 * mm, bbox=CORE_BBOX, show_core_boundary=False)
    fitxa_metric(c, 9 * mm, 190.8 * mm, 31.5 * mm, 11 * mm, "130,4 ha", "àmbit raster central", NAVY)
    fitxa_metric(c, 43.5 * mm, 190.8 * mm, 32.5 * mm, 11 * mm, "2.304", "edificis oficials", NAVY)
    fitxa_para_fit(c, "92 polígons verds · 98 elements d'aigua · 37 equipaments de context.", 10 * mm, 188 * mm, 64 * mm, 6 * mm, font_size=4.8)

    # 2. Radar amb el cercle IQT requerit.
    fitxa_panel(c, 82 * mm, 181 * mm, 61 * mm, 82 * mm, "2", "Radar territorial", "Sis dimensions calculades amb les dades de l'informe")
    draw_iqt_radar(c, profile, 112.5 * mm, 219.8 * mm, 15.8 * mm)
    fitxa_para_fit(
        c,
        "IQT EcoRadar: mitjana amb pes igual. Índex intern de cribratge, no normatiu ni comparable sense protocol comú.",
        87 * mm,
        189.5 * mm,
        51 * mm,
        7 * mm,
        font_size=4.7,
        min_font_size=4.3,
        color=MUTED,
    )

    # 3. Clima i cobertes.
    fitxa_panel(c, 146 * mm, 181 * mm, 59 * mm, 82 * mm, "3", "Clima i cobertes", "Quins factors concentren risc i protecció?")
    fitxa_metric(c, 151 * mm, 228 * mm, 23 * mm, 12 * mm, "61,7%", "ombra LiDAR", DARK_GREEN)
    fitxa_metric(c, 177 * mm, 228 * mm, 23 * mm, 12 * mm, "31,8%", "capçada LiDAR", GREEN)
    fitxa_metric(c, 151 * mm, 212.5 * mm, 23 * mm, 12 * mm, "41,7%", "impermeabilització", ORANGE)
    fitxa_metric(c, 177 * mm, 212.5 * mm, 23 * mm, 12 * mm, "+9,1 °C", "illa de calor sup.", RED)
    fitxa_metric(c, 151 * mm, 197 * mm, 23 * mm, 12 * mm, "46,7 °C", "LST diürna mitjana", RED)
    fitxa_metric(c, 177 * mm, 197 * mm, 23 * mm, 12 * mm, "0,177", "albedo medià", ORANGE)
    fitxa_para_fit(c, "La LST és temperatura superficial d'una escena, no temperatura de l'aire ni exposició personal.", 151 * mm, 193 * mm, 49 * mm, 10 * mm, font_size=4.7, color=MUTED)

    # 4. Salut i vulnerabilitat, amb conclusió alineada amb el marc OMS/OPS.
    fitxa_panel(c, m, 103 * mm, 155 * mm, 72 * mm, "4", "Salut i vulnerabilitat", "Com es converteix l'entorn en una decisió preventiva?")
    c.setFillColor(HexColor("#F0F3ED"))
    c.rect(10 * mm, 116 * mm, 50 * mm, 29 * mm, fill=1, stroke=0)
    draw_raster_map(c, PROJECT / "maps" / "landsat_lst.png", data, CORE_BBOX, 10 * mm, 116 * mm, 50 * mm, 29 * mm)
    fitxa_metric(c, 10 * mm, 147.5 * mm, 23 * mm, 10.5 * mm, "13.003", "població 2025", NAVY)
    fitxa_metric(c, 36 * mm, 147.5 * mm, 23 * mm, 10.5 * mm, "20,1%", "població 65+", PURPLE)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 6)
    c.drawString(65 * mm, 155 * mm, "CONCLUSIÓ · MARC OMS/OPS")
    health_items = [
        "Millorar de manera contínua els entorns físics i socials i els recursos de la comunitat.",
        "Dissenyar espais, mobilitat, informació i serveis perquè sostinguin autonomia i capacitat funcional.",
        "Decidir amb participació significativa de les persones grans, equitat i coordinació intersectorial.",
        "Aplicar, monitorar i avaluar si les actuacions redueixen barreres i permeten fer allò que les persones valoren.",
    ]
    y_item = 148 * mm
    for idx, text in enumerate(health_items, start=1):
        c.setFillColor(PALE_BLUE if idx < 4 else PALE_ORANGE)
        c.circle(68 * mm, y_item - 2 * mm, 2.5 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY if idx < 4 else ORANGE)
        c.setFont("Arial-Bold", 4.8)
        c.drawCentredString(68 * mm, y_item - 2.9 * mm, str(idx))
        fitxa_para_fit(c, text, 73 * mm, y_item + 1 * mm, 78 * mm, 9.2 * mm, font_size=4.9, min_font_size=4.4)
        y_item -= 11.1 * mm
    fitxa_para_fit(
        c,
        "Context ambiental: LST diürna 46,7 °C; la dada nocturna de 18,0 °C és agregada a 3 km. No són temperatura de l'aire ni exposició individual.",
        10 * mm,
        112.5 * mm,
        50 * mm,
        8 * mm,
        font_size=4.5,
        min_font_size=4.1,
        color=MUTED,
    )

    # 5. Lectura experta.
    fitxa_panel(c, 163 * mm, 103 * mm, 42 * mm, 72 * mm, "5", "Lectura experta", "Què implica per a la gestió?")
    expert_items = [
        "QUÈ PASSA? La protecció climàtica existeix, però no és uniforme ni contínua.",
        "CAUSA? Contrast entre verd, ombra i superfícies impermeables.",
        "RISC? Trams calents i punts d'espera amb poca capacitat d'evitar l'exposició.",
        "OPORTUNITAT? Connectar actius verds i blaus amb equipaments i rutes quotidianes.",
    ]
    y_exp = 156 * mm
    for idx, text in enumerate(expert_items, start=1):
        c.setFillColor(PALE_GREEN if idx < 4 else PALE_ORANGE)
        c.circle(168 * mm, y_exp - 2 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(DARK_GREEN if idx < 4 else ORANGE)
        c.setFont("Arial-Bold", 5.1)
        c.drawCentredString(168 * mm, y_exp - 3 * mm, str(idx))
        fitxa_para_fit(c, text, 173 * mm, y_exp + 1 * mm, 27 * mm, 10.5 * mm, font_size=5.0, min_font_size=4.5)
        y_exp -= 13.5 * mm

    # 6. Accessibilitat i pressió.
    fitxa_panel(c, m, 43 * mm, 70 * mm, 55 * mm, "6", "Accessibilitat i pressió", "On cal mirar primer?")
    c.setFillColor(HexColor("#EEF1EA"))
    c.rect(9 * mm, 58 * mm, 37 * mm, 27 * mm, fill=1, stroke=0)
    draw_integrated_map(c, data, 9 * mm, 58 * mm, 37 * mm, 27 * mm, bbox=CORE_BBOX, show_core_boundary=False)
    fitxa_metric(c, 48 * mm, 72 * mm, 22 * mm, 12 * mm, "1.141", "trams OSM", NAVY)
    fitxa_metric(c, 48 * mm, 57 * mm, 22 * mm, 12 * mm, "37", "equipaments", BLUE)
    fitxa_para_fit(c, "Auditar recorreguts essencials, punts d'espera i accessos. Els equipaments no són refugis climàtics certificats.", 10 * mm, 53 * mm, 58 * mm, 8 * mm, font_size=4.8)

    # 7. Processos territorials.
    fitxa_panel(c, 78 * mm, 43 * mm, 64 * mm, 55 * mm, "7", "PROCESSOS TERRITORIALS", "Quines dinàmiques condicionen la decisió?")
    c.setFillColor(MUTED)
    c.setFont("Arial-Bold", 4.6)
    c.drawString(83 * mm, 83 * mm, "Procés")
    c.drawRightString(136 * mm, 83 * mm, "Evidència · confiança")
    process_rows = [
        ("Cobertura arbòria", "+0,6 pp (2018–23) · mitjana"),
        ("Illa de calor superficial", "+9,1 °C · mitjana"),
        ("Impermeabilització", "41,7% · alta"),
        ("Escorrentia potencial", "34,4/100 · mitjana"),
    ]
    y_proc = 76 * mm
    for idx, (label, value) in enumerate(process_rows):
        c.setStrokeColor(RULE)
        c.line(83 * mm, y_proc + 3.5 * mm, 137 * mm, y_proc + 3.5 * mm)
        c.setFillColor(INK)
        c.setFont("Arial", 4.9)
        c.drawString(83 * mm, y_proc, base.cat(label))
        c.setFont("Arial-Bold", 4.8)
        c.drawRightString(137 * mm, y_proc, base.cat(value))
        y_proc -= 7.1 * mm
    fitxa_para_fit(c, "Només el canvi arbori és temporal; la resta són estats o proxies d'escenes concretes.", 84 * mm, 51 * mm, 52 * mm, 7 * mm, font_size=4.6, color=MUTED)

    # 8. Actuacions prioritàries.
    fitxa_panel(c, 146 * mm, 43 * mm, 59 * mm, 55 * mm, "8", "Actuacions prioritàries", "Primeres decisions justificades")
    actions = [
        ("P1", "Auditar la xarxa climàtica", "rutes, voreres i equipaments", "0–6 mesos"),
        ("P2", "Tancar buits de protecció", "trams calents i punts d'espera", "0–24 mesos"),
        ("P3", "Protocol calor-salut", "coordinació municipal i sanitària", "abans de l'estiu"),
    ]
    y_act = 84 * mm
    for idx, (priority, title, location, horizon) in enumerate(actions, start=1):
        c.setFillColor(PALE_GREEN)
        c.circle(152 * mm, y_act - 3 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(DARK_GREEN)
        c.setFont("Arial-Bold", 5.4)
        c.drawCentredString(152 * mm, y_act - 4 * mm, str(idx))
        c.setFillColor(INK)
        c.setFont("Arial-Bold", 5.3)
        c.drawString(157 * mm, y_act - 0.5 * mm, base.cat(f"{priority} · {title}")[:35])
        c.setFillColor(MUTED)
        c.setFont("Arial", 4.6)
        c.drawString(157 * mm, y_act - 4.8 * mm, base.cat(f"On: {location}")[:38])
        c.setFillColor(ORANGE)
        c.setFont("Arial-Bold", 4.6)
        c.drawString(157 * mm, y_act - 8.7 * mm, base.cat(horizon))
        y_act -= 13.5 * mm

    # Banda final, traçabilitat i peu.
    c.setFillColor(CARD)
    c.setStrokeColor(RULE)
    c.roundRect(m, 22 * mm, 200 * mm, 16 * mm, 3, fill=1, stroke=1)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 6.8)
    c.drawCentredString(105 * mm, 33 * mm, "CONCLUSIÓ OMS: CIUTAT SALUDABLE I AMIGABLE AMB LES PERSONES GRANS")
    band_texts = [
        "Millora contínua dels entorns físics, socials i dels recursos comunitaris.",
        "Autonomia, inclusió, participació i capacitat funcional com a resultats.",
        "Acció intersectorial i equitativa, amb participació de les persones grans.",
        "Seguiment i avaluació per mantenir i ampliar les mesures eficaces.",
    ]
    x_band = 9 * mm
    for text in band_texts:
        c.setStrokeColor(RULE)
        c.line(x_band - 2 * mm, 24.5 * mm, x_band - 2 * mm, 31 * mm)
        fitxa_para_fit(c, text, x_band, 30 * mm, 43 * mm, 7 * mm, font_size=4.8, min_font_size=4.3)
        x_band += 49 * mm

    c.setFillColor(NAVY)
    c.roundRect(m, 4 * mm, 200 * mm, 15 * mm, 3, fill=1, stroke=0)
    draw_brand_logo(c, ECORADAR_LOGO, m + 3 * mm, 5 * mm, 13 * mm)
    draw_brand_logo(c, GREEN_WOLF_LOGO, m + 18 * mm, 5 * mm, 13 * mm)
    c.setFillColor(colors.white)
    c.setFont("Arial-Bold", 7.2)
    c.drawString(m + 34 * mm, 13 * mm, "ECORADAR · GREEN WOLF NATURE")
    c.setFont("Arial", 4.9)
    c.drawString(m + 34 * mm, 8.8 * mm, "Dades · ciència · salut · territori · natura · futur")
    c.setFont("Arial", 4.7)
    c.drawString(m + 96 * mm, 13 * mm, "Fonts i mètodes: informe integrat [D1, D2, D4, D9, D10].")
    c.drawString(m + 96 * mm, 8.8 * mm, "[OMS1] OMS/OPS 2023 · doi.org/10.37774/9789275327975 · IQT documentat")
    c.save()


def write_iqt_metadata(path: Path, data: dict, profile: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **profile,
        "project": "EcoRadar Urbà - La Seu d'Urgell",
        "study_area": "àmbit raster central de 130,4 ha",
        "generated_on": "2026-07-12",
        "healthy_city_framework": {
            "reference_id": "OMS1",
            "title": "Programas nacionales de ciudades y comunidades amigables con las personas mayores. Una guía",
            "organization": "Organización Mundial de la Salud / Organización Panamericana de la Salud",
            "year": 2023,
            "doi": "https://doi.org/10.37774/9789275327975",
            "license": "CC BY-NC-SA 3.0 IGO",
            "principles_applied": [
                "millora contínua dels entorns físics i socials i dels recursos comunitaris",
                "autonomia, inclusió, participació i capacitat funcional",
                "participació significativa de les persones grans",
                "equitat i coordinació intersectorial",
                "aplicació, seguiment, avaluació i millora de les actuacions",
            ],
        },
        "input_references": {
            "shade_and_canopy": "metadata/layer_manifest.json · LiDAR territorial ICGC v3r1, 2 m",
            "vegetation_cover_imperviousness_runoff_tree_change": "indicators/extended_urban_indicators.json",
            "ndvi_ndmi": "indicators/sentinel2_urban_indicators.json · escena 2026-07-07",
            "soil_moisture": "indicators/contextual_environment.json · CLMS 1 km, 2026-07-07",
        },
        "quality_rules": [
            "No s'inclou la temperatura superficial perquè no existeix una normalització urbana universal que permeti convertir-la en qualitat 0–100 sense llindars arbitraris.",
            "No s'inclouen NO2 ni PM2,5 perquè són contextos agregats de resolució massa grossa per caracteritzar el teixit urbà.",
            "NDVI i NDMI es reexpressen matemàticament del domini teòric [-1, 1] a [0, 100]; això no crea un llindar ecològic ni sanitari.",
            "La humitat del sòl d'1 km només aporta context municipal a la dimensió hídrica i no es representa com a mapa de carrer.",
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_fitxa(base_report: Path, fitxa_pdf: Path) -> None:
    reader = PdfReader(str(base_report))
    fitxa = PdfReader(str(fitxa_pdf))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for page in fitxa.pages:
        writer.add_page(page)
    if reader.metadata:
        metadata = {str(key): str(value) for key, value in reader.metadata.items() if value is not None}
        metadata["/Subject"] = "Diagnosi integrada ambiental i de salut pública amb Fitxa EcoRadar IQT"
        writer.add_metadata(metadata)
    temporary = base_report.with_name(f"{base_report.stem}.with_fitxa.tmp.pdf")
    with temporary.open("wb") as handle:
        writer.write(handle)
    temporary.replace(base_report)


def export_report(output: Path, project_copy: Path) -> None:
    base.register_fonts()
    base.build_styles()
    data = load_inputs()
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=landscape(A4), pageCompression=1)
    c.setTitle("EcoRadar Urbà La Seu d'Urgell - Diagnosi integrada ambiental i de salut pública")
    c.setAuthor("EcoRadar")
    c.setSubject("Diagnosi urbana amb lectura de gestió ambiental i salut pública")
    c.setKeywords("EcoRadar, La Seu d'Urgell, LiDAR, Landsat, salut pública, inundabilitat, demografia, cobertes solars")
    page_cover(c, data)
    page_executive(c, data)
    page_framework(c)
    page_sources_method(c)
    page_integrated_map(c, data)
    page_heat(c, data)
    page_copernicus_indicators(c, data)
    page_built_solar(c, data)
    page_green_blue_flood(c, data)
    page_population_health(c, data)
    page_diagnosis_matrix(c)
    page_actions(c)
    page_monitoring(c)
    page_data_references(c)
    page_health_references(c)
    c.save()
    profile = territorial_quality_profile(data)
    build_urban_fitxa(DEFAULT_FITXA_OUTPUT, data, profile)
    write_iqt_metadata(DEFAULT_IQT_METADATA, data, profile)
    append_fitxa(output, DEFAULT_FITXA_OUTPUT)
    DEFAULT_FITXA_PROJECT_COPY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DEFAULT_FITXA_OUTPUT, DEFAULT_FITXA_PROJECT_COPY)
    project_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output, project_copy)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--project-copy", type=Path, default=DEFAULT_PROJECT_COPY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_report(args.output, args.project_copy)
    print(args.output)
    print(args.project_copy)


if __name__ == "__main__":
    main()
