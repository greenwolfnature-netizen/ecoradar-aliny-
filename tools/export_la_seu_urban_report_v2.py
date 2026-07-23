"""Export the professional EcoRadar Urba diagnosis report for La Seu d'Urgell.

The report is a client-facing technical document. It reads the documented
metrics from ``output/la_seu_urban_metrics_real_v2.json``, embeds the frozen
urban poster supplied for the project, and derives two diagnostic LiDAR maps
from the same ICGC LAZ tiles and solar-shadow method used by the metrics tool.

No connector or analytical result is modified by this exporter.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
from typing import Iterable

import json
import numpy as np
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = ROOT / "output/la_seu_urban_metrics_real_v2.json"
DEFAULT_POSTER = Path("/Users/usuario/Downloads/ChatGPT Image 10 jul. 2026, 07_36_07.png")
DEFAULT_OUTPUT = ROOT / "output/pdf/diagnosi_ecoradar_urba_la_seu_lidar_v2.pdf"
DEFAULT_ASSETS = ROOT / "tmp/pdfs/la_seu_urban_v2_assets"


PAGE_W, PAGE_H = landscape(A4)
MARGIN_X = 15 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X
CONTENT_TOP = PAGE_H - 24 * mm
CONTENT_BOTTOM = 16 * mm

NAVY = HexColor("#173D6D")
GREEN = HexColor("#4F7E45")
DARK_GREEN = HexColor("#176B3A")
BLUE = HexColor("#1686C7")
PURPLE = HexColor("#6E3BB0")
ORANGE = HexColor("#EF9E2C")
RED = HexColor("#B43C2F")
INK = HexColor("#2D2D2B")
MUTED = HexColor("#6F706C")
BG = HexColor("#F3F0E8")
CARD = HexColor("#FBFAF6")
BORDER = HexColor("#C9C1B3")
RULE = HexColor("#D8D1C5")
PALE_GREEN = HexColor("#E8F0E3")
PALE_BLUE = HexColor("#E5EEF7")
PALE_ORANGE = HexColor("#FFF1DC")
PALE_RED = HexColor("#F8E8E5")
WHITE = colors.white

FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_ITALIC = "/System/Library/Fonts/Supplemental/Arial Italic.ttf"


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Arial", FONT_REGULAR))
    pdfmetrics.registerFont(TTFont("Arial-Bold", FONT_BOLD))
    pdfmetrics.registerFont(TTFont("Arial-Italic", FONT_ITALIC))


STYLES: dict[str, ParagraphStyle] = {}


CATALAN_WORDS = {
    "acces": "accés",
    "actuacio": "actuació",
    "actuacions": "actuacions",
    "adaptacio": "adaptació",
    "afirmacio": "afirmació",
    "aillades": "aïllades",
    "ambit": "àmbit",
    "ampliacio": "ampliació",
    "antropogenica": "antropogènica",
    "arbrat": "arbrat",
    "avaluacio": "avaluació",
    "calcul": "càlcul",
    "calculs": "càlculs",
    "capcada": "capçada",
    "carrega": "càrrega",
    "classificacio": "classificació",
    "cientifica": "científica",
    "climatica": "climàtica",
    "climatic": "climàtic",
    "climatics": "climàtics",
    "clinica": "clínica",
    "complecio": "compleció",
    "conclusio": "conclusió",
    "consequencia": "conseqüència",
    "construida": "construïda",
    "conversio": "conversió",
    "continua": "contínua",
    "croniques": "cròniques",
    "critics": "crítics",
    "critiques": "crítiques",
    "decisio": "decisió",
    "dependencia": "dependència",
    "depen": "depèn",
    "derivacio": "derivació",
    "derivacions": "derivacions",
    "despres": "després",
    "deshidratacio": "deshidratació",
    "diaria": "diària",
    "direccio": "direcció",
    "distancia": "distància",
    "distribucio": "distribució",
    "edificacio": "edificació",
    "educacio": "educació",
    "elevacio": "elevació",
    "epidemiologica": "epidemiològica",
    "especifica": "específica",
    "especies": "espècies",
    "especie": "espècie",
    "estrategic": "estratègic",
    "estres": "estrès",
    "estimacio": "estimació",
    "evidencia": "evidència",
    "evaporacio": "evaporació",
    "evolucio": "evolució",
    "exposicio": "exposició",
    "fisic": "físic",
    "fisica": "física",
    "fisiologica": "fisiològica",
    "funcio": "funció",
    "geometria": "geometria",
    "gestio": "gestió",
    "governanca": "governança",
    "cohesio": "cohesió",
    "horaries": "horàries",
    "hipotesis": "hipòtesis",
    "huma": "humà",
    "human": "humà",
    "informacio": "informació",
    "indexs": "índexs",
    "integracio": "integració",
    "interpretacio": "interpretació",
    "linia": "línia",
    "llicencia": "llicència",
    "mascara": "màscara",
    "maxim": "màxim",
    "maximitzar": "maximitzar",
    "mes": "més",
    "metode": "mètode",
    "metodologicament": "metodològicament",
    "meteorologiques": "meteorològiques",
    "microclimatica": "microclimàtica",
    "microclimatiques": "microclimàtiques",
    "minim": "mínim",
    "mitjancant": "mitjançant",
    "nomes": "només",
    "normalitzacio": "normalització",
    "nuvoll": "núvol",
    "ocupacio": "ocupació",
    "orientacio": "orientació",
    "optim": "òptim",
    "pagina": "pàgina",
    "pagines": "pàgines",
    "participacio": "participació",
    "percepcio": "percepció",
    "pergoles": "pèrgoles",
    "planificacio": "planificació",
    "poblacio": "població",
    "posicio": "posició",
    "prioritaria": "prioritària",
    "prioritzacio": "priorització",
    "precaucio": "precaució",
    "prediccio": "predicció",
    "proces": "procés",
    "proteccio": "protecció",
    "psicologica": "psicològica",
    "publica": "pública",
    "publicacio": "publicació",
    "radiacio": "radiació",
    "referencia": "referència",
    "reduccio": "reducció",
    "reduida": "reduïda",
    "relacio": "relació",
    "resolucio": "resolució",
    "respiratories": "respiratòries",
    "restauracio": "restauració",
    "revisio": "revisió",
    "sanitaria": "sanitària",
    "separacio": "separació",
    "senyalitzacio": "senyalització",
    "seguents": "següents",
    "series": "sèries",
    "sino": "sinó",
    "simulacio": "simulació",
    "satisfaccio": "satisfacció",
    "sintetica": "sintètica",
    "son": "són",
    "superficie": "superfície",
    "supervisio": "supervisió",
    "tecnic": "tècnic",
    "tecnica": "tècnica",
    "tecnics": "tècnics",
    "tecniques": "tècniques",
    "termic": "tèrmic",
    "termica": "tèrmica",
    "termics": "tèrmics",
    "unic": "únic",
    "urba": "urbà",
    "validacio": "validació",
    "valids": "vàlids",
    "vegetacio": "vegetació",
    "versio": "versió",
    "pixels": "píxels",
}

CATALAN_PHRASES = (
    ("Que diu", "Què diu"),
    ("Que permet", "Què permet"),
    ("Que podem", "Què podem"),
    ("Que no podem", "Què no podem"),
    ("Que es", "Què és"),
    ("Que no es", "Què no és"),
    ("Per que", "Per què"),
    ("L'ombra es", "L'ombra és"),
    ("No es una", "No és una"),
    ("No es un", "No és un"),
    ("No es la", "No és la"),
    ("No es el", "No és el"),
    ("Es una", "És una"),
    ("Es un", "És un"),
    ("Es la", "És la"),
    ("Es el", "És el"),
    ("es que", "és que"),
    ("no es uniforme", "no és uniforme"),
    ("no es maximitzar", "no és maximitzar"),
    ("no es prova", "no és prova"),
    ("prioritaria es", "prioritària és"),
    ("no es una", "no és una"),
    ("no es un", "no és un"),
    ("no es la", "no és la"),
    ("no es el", "no és el"),
    ("es una", "és una"),
    ("es un", "és un"),
    ("es la", "és la"),
    ("es el", "és el"),
    ("d'us", "d'ús"),
    ("us de", "ús de"),
    ("us real", "ús real"),
    ("Us i", "Ús i"),
    ("Cel.les", "Cel·les"),
    ("cel.les", "cel·les"),
)


def cat(text: str) -> str:
    """Apply conservative Catalan orthography to visible text, not markup."""
    parts = re.split(r"(<[^>]+>)", text)
    for index in range(0, len(parts), 2):
        part = parts[index]
        for source, target in CATALAN_PHRASES:
            part = part.replace(source, target)
        for source, target in CATALAN_WORDS.items():
            pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)

            def replace(match: re.Match[str], replacement: str = target) -> str:
                value = match.group(0)
                if value.isupper():
                    return replacement.upper()
                if value[:1].isupper():
                    return replacement[:1].upper() + replacement[1:]
                return replacement

            part = pattern.sub(replace, part)
        parts[index] = part
    return "".join(parts)


def build_styles() -> None:
    STYLES.update(
        {
            "body": ParagraphStyle(
                "body",
                fontName="Arial",
                fontSize=9.2,
                leading=12.4,
                textColor=INK,
                alignment=TA_LEFT,
                spaceAfter=4,
            ),
            "body_just": ParagraphStyle(
                "body_just",
                parent=None,
                fontName="Arial",
                fontSize=9.2,
                leading=12.6,
                textColor=INK,
                alignment=TA_JUSTIFY,
            ),
            "body_small": ParagraphStyle(
                "body_small",
                fontName="Arial",
                fontSize=7.8,
                leading=10.2,
                textColor=INK,
            ),
            "source": ParagraphStyle(
                "source",
                fontName="Arial",
                fontSize=6.8,
                leading=8.6,
                textColor=MUTED,
            ),
            "card_title": ParagraphStyle(
                "card_title",
                fontName="Arial-Bold",
                fontSize=10.8,
                leading=13.2,
                textColor=NAVY,
            ),
            "subhead": ParagraphStyle(
                "subhead",
                fontName="Arial-Bold",
                fontSize=10.5,
                leading=13,
                textColor=NAVY,
            ),
            "table": ParagraphStyle(
                "table",
                fontName="Arial",
                fontSize=7.2,
                leading=9.2,
                textColor=INK,
            ),
            "table_bold": ParagraphStyle(
                "table_bold",
                fontName="Arial-Bold",
                fontSize=7.2,
                leading=9.2,
                textColor=NAVY,
            ),
            "ref": ParagraphStyle(
                "ref",
                fontName="Arial",
                fontSize=6.9,
                leading=8.8,
                textColor=INK,
            ),
            "center_small": ParagraphStyle(
                "center_small",
                fontName="Arial",
                fontSize=7.4,
                leading=9.2,
                textColor=MUTED,
                alignment=TA_CENTER,
            ),
        }
    )


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(cat(text), STYLES[style])


def draw_paragraph(
    c: canvas.Canvas,
    text: str,
    x: float,
    top: float,
    width: float,
    style: str = "body",
    max_height: float = 300 * mm,
) -> float:
    p = P(text, style)
    _, height = p.wrap(width, max_height)
    p.drawOn(c, x, top - height)
    return height


def rounded_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    fill=CARD,
    stroke=BORDER,
    radius: float = 4 * mm,
) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def section_header(c: canvas.Canvas, number: str, title: str, subtitle: str, page: int) -> None:
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 22)
    c.drawString(MARGIN_X, PAGE_H - 17 * mm, cat(f"{number}. {title}" if number else title))
    c.setFillColor(GREEN)
    c.setFont("Arial-Bold", 11.5)
    c.drawString(MARGIN_X, PAGE_H - 27 * mm, cat(subtitle))
    footer(c, page)


def footer(c: canvas.Canvas, page: int) -> None:
    y = 10 * mm
    c.setStrokeColor(RULE)
    c.setLineWidth(0.65)
    c.line(MARGIN_X, y + 5 * mm, PAGE_W - MARGIN_X, y + 5 * mm)
    c.setFillColor(MUTED)
    c.setFont("Arial", 6.5)
    c.drawString(MARGIN_X, y, cat("EcoRadar Urba - Diagnosi climatica, salut ambiental i benestar - La Seu d'Urgell"))
    c.drawRightString(PAGE_W - MARGIN_X, y, str(page))


def draw_bullets(
    c: canvas.Canvas,
    items: Iterable[str],
    x: float,
    top: float,
    width: float,
    style: str = "body",
    color=GREEN,
    gap: float = 3.2,
) -> float:
    y = top
    for item in items:
        c.setFillColor(color)
        c.circle(x + 2.2, y - 5.2, 2.1, fill=1, stroke=0)
        h = draw_paragraph(c, item, x + 11, y, width - 11, style)
        y -= h + gap
    return top - y


def draw_metric_card(
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
    rounded_card(c, x, y, w, h)
    c.setFillColor(accent)
    c.circle(x + 12 * mm, y + h / 2, 6.5 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Arial-Bold", 7.2 if len(value) > 8 else 9.4)
    c.drawCentredString(x + 12 * mm, y + h / 2 - 2.6, value)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 8.5)
    c.drawString(x + 23 * mm, y + h - 10 * mm, cat(label))
    draw_paragraph(c, note, x + 23 * mm, y + h - 15 * mm, w - 27 * mm, "body_small")


def draw_process_band(c: canvas.Canvas, steps: list[tuple[str, str]], x: float, y: float, w: float) -> None:
    step_w = w / len(steps)
    for idx, (title, detail) in enumerate(steps):
        cx = x + idx * step_w + 9 * mm
        c.setFillColor(GREEN if idx < len(steps) - 1 else NAVY)
        c.circle(cx, y + 21 * mm, 6.8 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Arial-Bold", 8)
        c.drawCentredString(cx, y + 21 * mm - 2.5, str(idx + 1))
        if idx < len(steps) - 1:
            c.setStrokeColor(BORDER)
            c.setLineWidth(1.2)
            c.line(cx + 8 * mm, y + 21 * mm, x + (idx + 1) * step_w + 1 * mm, y + 21 * mm)
        c.setFillColor(NAVY)
        c.setFont("Arial-Bold", 8.2)
        c.drawString(x + idx * step_w + 2 * mm, y + 9 * mm, cat(title))
        draw_paragraph(c, detail, x + idx * step_w + 2 * mm, y + 6 * mm, step_w - 6 * mm, "source")


def draw_image_fit(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    with Image.open(path) as img:
        iw, ih = img.size
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(ImageReader(str(path)), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, preserveAspectRatio=True, mask="auto")


def table_on_canvas(c: canvas.Canvas, table: Table, x: float, top: float, max_h: float = 400 * mm) -> float:
    _, h = table.wrapOn(c, CONTENT_W, max_h)
    table.drawOn(c, x, top - h)
    return h


def make_table(
    rows: list[list[object]],
    widths: list[float],
    header: bool = True,
    font_size: float = 7.2,
) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE if header else CARD),
        ("FONTNAME", (0, 0), (-1, 0), "Arial-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CARD, HexColor("#F7F5EF")]),
    ]
    table.setStyle(TableStyle(style))
    return table


def build_lidar_assets(assets_dir: Path, poster_path: Path) -> dict[str, Path]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    canopy_path = assets_dir / "lidar_canopy.png"
    shade_path = assets_dir / "lidar_shade.png"
    cover_crop = assets_dir / "poster_cover_crop.png"

    with Image.open(poster_path) as poster:
        poster = poster.convert("RGB")
        pw, ph = poster.size
        crop_box = (int(pw * 0.22), int(ph * 0.07), int(pw * 0.68), int(ph * 0.86))
        poster.crop(crop_box).save(cover_crop)

    arrays_path = assets_dir / "lidar_report_arrays.npz"
    helper = ROOT / "tools/build_la_seu_lidar_report_arrays.py"
    geospatial_python = ROOT / ".venv/bin/python"
    subprocess.run(
        [str(geospatial_python), str(helper), "--output", str(arrays_path)],
        cwd=ROOT,
        check=True,
    )
    with np.load(arrays_path) as arrays:
        canopy_grid = arrays["canopy"]
        shade_grid = arrays["shade"]
        valid = arrays["valid"]
    nrows, ncols = valid.shape

    canopy_rgb = np.empty((nrows, ncols, 3), dtype="uint8")
    canopy_rgb[:] = (242, 239, 230)
    canopy_rgb[valid] = (229, 231, 220)
    canopy_rgb[canopy_grid] = (29, 111, 61)
    canopy_rgb[~valid] = (210, 209, 204)
    Image.fromarray(canopy_rgb, mode="RGB").save(canopy_path)

    shade_rgb = np.empty((nrows, ncols, 3), dtype="uint8")
    shade_rgb[:] = (242, 239, 230)
    shade_rgb[valid] = (247, 226, 184)
    shade_rgb[shade_grid] = (75, 121, 111)
    shade_rgb[canopy_grid] = (22, 91, 54)
    shade_rgb[~valid] = (210, 209, 204)
    Image.fromarray(shade_rgb, mode="RGB").save(shade_path)
    return {"canopy": canopy_path, "shade": shade_path, "cover": cover_crop}


def page_cover(c: canvas.Canvas, poster_path: Path, assets: dict[str, Path]) -> None:
    c.setFillColor(WHITE)
    c.rect(0, 0, PAGE_W * 0.52, PAGE_H, fill=1, stroke=0)
    c.setFillColor(BG)
    c.rect(PAGE_W * 0.52, 0, PAGE_W * 0.48, PAGE_H, fill=1, stroke=0)

    x = MARGIN_X + 4 * mm
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 31)
    c.drawString(x, PAGE_H - 43 * mm, cat("ECORADAR URBA"))
    c.setFillColor(GREEN)
    c.setFont("Arial-Bold", 23)
    c.drawString(x, PAGE_H - 57 * mm, "La Seu d'Urgell")
    c.setFillColor(INK)
    c.setFont("Arial-Bold", 16)
    c.drawString(x, PAGE_H - 83 * mm, cat("Informe de diagnosi integrada"))
    c.drawString(x, PAGE_H - 94 * mm, cat("clima, salut i benestar urba"))
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 9.5)
    c.drawString(x, PAGE_H - 111 * mm, cat("LiDAR territorial + temperatura superficial + xarxa urbana"))

    rounded_card(c, x, 40 * mm, PAGE_W * 0.43, 36 * mm, fill=HexColor("#F7F8F5"), stroke=INK)
    draw_paragraph(
        c,
        "Document tecnic per argumentar el sentit de l'EcoRadar Urba, justificar les prioritats del mapa i orientar decisions municipals de salut publica, mobilitat quotidiana i infraestructura verda.",
        x + 7 * mm,
        69 * mm,
        PAGE_W * 0.39,
        "body",
    )
    c.setFillColor(MUTED)
    c.setFont("Arial", 7.5)
    c.drawString(x, 25 * mm, cat("Versio 2.0 - 10 de juliol de 2026 - ETRS89 / UTM 31N (EPSG:25831)"))

    rx = PAGE_W * 0.55
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 11.5)
    c.drawString(rx, PAGE_H - 24 * mm, cat("XARXA CLIMATICA DE BENESTAR"))
    rounded_card(c, rx, 80 * mm, PAGE_W * 0.40, 96 * mm, fill=CARD)
    draw_image_fit(c, assets["cover"], rx + 4 * mm, 84 * mm, PAGE_W * 0.40 - 8 * mm, 88 * mm)
    draw_metric_card(c, rx, 42 * mm, 55 * mm, 34 * mm, "61,7%", "Ombra LiDAR", "21/06/2026, 15 h CEST", DARK_GREEN)
    draw_metric_card(c, rx + 59 * mm, 42 * mm, 55 * mm, 34 * mm, "46,7 C", "LST mitjana", "08/07/2026, 12:35 CEST", ORANGE)
    c.setFillColor(MUTED)
    c.setFont("Arial", 6.6)
    c.drawRightString(PAGE_W - MARGIN_X, 18 * mm, cat("Dades obertes documentades - ambit metric central: 130,4 ha"))
    c.showPage()


def page_executive(c: canvas.Canvas, m: dict) -> None:
    section_header(c, "1", "Resum executiu", "Que diu la diagnosi i quines decisions permet prendre", 2)
    left_x = MARGIN_X
    col_gap = 7 * mm
    col_w = (CONTENT_W - col_gap) / 2
    top_y = CONTENT_TOP - 8 * mm
    card_h = 52 * mm
    rounded_card(c, left_x, top_y - card_h, col_w, card_h)
    draw_paragraph(c, "<b>Diagnosi sintetica</b>", left_x + 6 * mm, top_y - 6 * mm, col_w - 12 * mm, "card_title")
    draw_paragraph(
        c,
        "EcoRadar Urba transforma capes territorials, temperatura superficial i estructura tridimensional de la vegetacio i l'edificacio en una lectura operativa de l'exposicio a la calor. La conclusio principal es que la Seu disposa d'una base verda i blava rellevant, pero la proteccio climatica no es uniforme ni necessàriament continua al llarg dels recorreguts quotidians. La decisio prioritaria es consolidar una xarxa climatica que connecti ribera, centre, escoles, serveis de salut, places i refugis.",
        left_x + 6 * mm,
        top_y - 18 * mm,
        col_w - 12 * mm,
        "body_just",
    )
    right_x = left_x + col_w + col_gap
    rounded_card(c, right_x, top_y - card_h, col_w, card_h)
    draw_paragraph(c, "<b>Que permet decidir?</b>", right_x + 6 * mm, top_y - 6 * mm, col_w - 12 * mm, "card_title")
    draw_bullets(
        c,
        [
            "Quins itineraris convé validar i senyalitzar durant episodis de calor.",
            "On prioritzar arbrat, pergoles, bancs, fonts o naturalitzacio.",
            "Quins refugis potencials necessiten comprovacio d'horaris, capacitat i accessibilitat.",
            "Com incorporar criteris d'equitat per protegir gent gran, infants, persones amb malalties croniques, discapacitat o treball exterior.",
        ],
        right_x + 7 * mm,
        top_y - 18 * mm,
        col_w - 14 * mm,
    )

    lidar = m["lidar_central_core"]
    landsat = m["landsat_lst"]
    municipal = m["municipal_green"]
    metrics_y = 54 * mm
    gap = 4 * mm
    mw = (CONTENT_W - 2 * gap) / 3
    mh = 33 * mm
    draw_metric_card(c, MARGIN_X, metrics_y + mh + gap, mw, mh, f"{str(lidar['shade_pct']).replace('.', ',')}%", "Ombra directa estimada", "Solstici d'estiu, 15 h CEST; model LiDAR a 2 m.", DARK_GREEN)
    draw_metric_card(c, MARGIN_X + mw + gap, metrics_y + mh + gap, mw, mh, f"{str(lidar['canopy_cover_pct']).replace('.', ',')}%", "Coberta de capcada", "Classes ICGC 4 i 5 dins l'ambit central.", GREEN)
    draw_metric_card(c, MARGIN_X + 2 * (mw + gap), metrics_y + mh + gap, mw, mh, f"{str(landsat['lst_mean_c']).replace('.', ',')} C", "Temperatura superficial", "Landsat 9; no equival a temperatura de l'aire.", ORANGE)
    draw_metric_card(c, MARGIN_X, metrics_y, mw, mh, "38,7-51,1", "Rang LST P10-P90", f"{landsat['valid_pixels']:,} pixels valids".replace(",", "."), RED)
    draw_metric_card(c, MARGIN_X + mw + gap, metrics_y, mw, mh, f"{municipal['planted_trees_streets_and_parks']:,}".replace(",", "."), "Arbrat municipal", "22 ha de verd i 80 especies; recompte no georeferenciat.", GREEN)
    draw_metric_card(c, MARGIN_X + 2 * (mw + gap), metrics_y, mw, mh, f"{str(lidar['area_ha']).replace('.', ',')} ha", "Ambit metric central", "Els resultats raster no representen tot el municipi.", NAVY)

    rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 27 * mm, fill=PALE_GREEN)
    draw_paragraph(
        c,
        "<b>Missatge clau.</b> L'ombra es una infraestructura de salut: redueix la carrega radiant, facilita la mobilitat activa i ajuda a mantenir l'autonomia durant la calor. EcoRadar prioritza on verificar i actuar; no substitueix sensors, treball de camp ni una avaluacio clinica. [H1-H6]",
        MARGIN_X + 7 * mm,
        43 * mm,
        CONTENT_W - 14 * mm,
        "body",
    )
    c.showPage()


def page_purpose(c: canvas.Canvas) -> None:
    section_header(c, "2", "El sentit d'EcoRadar Urba", "De la cartografia a una infraestructura urbana de salut i benestar", 3)
    draw_process_band(
        c,
        [
            ("EXPOSICIO", "Radiacio, superficies calentes i discontinuïtat d'ombra."),
            ("PROTECCIO", "Arbrat, ombra construida, verd, aigua i refugis."),
            ("MOBILITAT", "Recorreguts caminables, accessibles i amb descans."),
            ("AUTONOMIA", "Acces segur a escola, CAP, compres i relacions socials."),
            ("SALUT", "Menys risc termic i millor benestar fisic, mental i social."),
        ],
        MARGIN_X,
        131 * mm,
        CONTENT_W,
    )

    gap = 7 * mm
    col_w = (CONTENT_W - 2 * gap) / 3
    y = 49 * mm
    h = 69 * mm
    cards = [
        (
            "Que es",
            PALE_GREEN,
            [
                "Un sistema de prioritzacio territorial per reduir exposicio a la calor.",
                "Una lectura integrada de verd, aigua, ombra LiDAR, LST i xarxa urbana.",
                "Un suport per coordinar salut publica, urbanisme, mobilitat i manteniment del verd.",
            ],
        ),
        (
            "Que no es",
            PALE_ORANGE,
            [
                "No es una prediccio de temperatura de l'aire a escala de carrer.",
                "No es un certificat de confort termic ni de seguretat d'una ruta.",
                "No demostra impactes sanitaris locals sense dades epidemiologiques i de camp.",
            ],
        ),
        (
            "Valor public",
            PALE_BLUE,
            [
                "Permet comparar alternatives i justificar inversions amb dades traçables.",
                "Fa visible la desigual distribucio de l'ombra i ajuda a prioritzar poblacio vulnerable.",
                "Crea una linia base per mesurar si les actuacions milloren l'exposicio real.",
            ],
        ),
    ]
    for idx, (title, fill, bullets) in enumerate(cards):
        x = MARGIN_X + idx * (col_w + gap)
        rounded_card(c, x, y, col_w, h, fill=fill)
        draw_paragraph(c, f"<b>{title}</b>", x + 6 * mm, y + h - 6 * mm, col_w - 12 * mm, "card_title")
        draw_bullets(c, bullets, x + 6 * mm, y + h - 18 * mm, col_w - 12 * mm, "body_small")

    rounded_card(c, MARGIN_X, 21 * mm, CONTENT_W, 21 * mm, fill=CARD)
    draw_paragraph(
        c,
        "<b>Criteri de governanca:</b> la prioritat no es maximitzar un unic indicador, sino reduir exposicio als recorreguts essencials sense empitjorar accessibilitat, seguretat, disponibilitat d'aigua, biodiversitat o manteniment. La xarxa ha de ser continua, utilitzable i socialment justa.",
        MARGIN_X + 7 * mm,
        37 * mm,
        CONTENT_W - 14 * mm,
        "body",
    )
    c.showPage()


def page_data_method(c: canvas.Canvas) -> None:
    section_header(c, "3", "Dades, escala i metode", "Traçabilitat: font, derivacio, interpretacio i validacio", 4)
    draw_process_band(
        c,
        [
            ("FONTS", "USGS, ICGC, Ajuntament i OSM/BBBike."),
            ("NORMALITZACIO", "CRS comu, retalls i control de qualitat."),
            ("DERIVACIONS", "LST, capcada, DSM/DTM i ombra solar."),
            ("MODEL", "Index relatiu i prioritzacio de trams."),
            ("VALIDACIO", "Camp, sensors, accessibilitat i revisio municipal."),
        ],
        MARGIN_X,
        142 * mm,
        CONTENT_W,
    )

    rows: list[list[object]] = [
        [P("Font", "table_bold"), P("Organisme / llicencia", "table_bold"), P("Estat", "table_bold"), P("Funcio en la diagnosi", "table_bold")],
        [P("LiDAR Territorial v3.1 (2021-2023) [D2]", "table"), P("ICGC - CC BY 4.0", "table"), P("verificada", "table"), P("Nuvoll LAZ classificat; DSM/DTM a 2 m, coberta de capcada i simulacio d'ombra directa.", "table")],
        [P("Landsat 9 C2 L2 ST_B10 [D1]", "table"), P("USGS EROS - dades obertes", "table"), P("verificada", "table"), P("Temperatura de la superficie terrestre d'una escena, amb mascara QA_PIXEL i conversio oficial a kelvin/Celsius.", "table")],
        [P("Adreces municipals [D4]", "table"), P("ICGC + administracions locals - CC BY 4.0", "table"), P("verificada", "table"), P("Estructura urbana i densitat de punts d'acces; 2.721 punts al mapa de referencia.", "table")],
        [P("Gestio actual del verd urba [D3]", "table"), P("Ajuntament de la Seu d'Urgell", "table"), P("verificada", "table"), P("22 ha de verd, 5.500 arbres i 80 especies. Es un recompte municipal, no un inventari espacial.", "table")],
        [P("OpenStreetMap / BBBike [D5-D6]", "table"), P("Comunitat OSM - ODbL", "table"), P("documentada", "table"), P("Geometria de carrers, edificis, verd, aigua i equipaments. La complecio varia i requereix contrast municipal.", "table")],
        [P("Inventari municipal d'arbrat lineal", "table"), P("Ajuntament", "table"), P("bloquejada", "table"), P("No s'ha localitzat una capa oberta arbre a arbre. No s'infereix una cobertura lineal oficial.", "table")],
    ]
    table = make_table(rows, [42 * mm, 44 * mm, 24 * mm, CONTENT_W - 110 * mm])
    table_on_canvas(c, table, MARGIN_X, 126 * mm)

    rounded_card(c, MARGIN_X, 23 * mm, CONTENT_W, 30 * mm, fill=PALE_ORANGE)
    draw_paragraph(c, "<b>Regla d'interpretacio.</b>", MARGIN_X + 7 * mm, 47 * mm, 45 * mm, "card_title")
    draw_paragraph(
        c,
        "Les dades observades (Landsat, punts LiDAR, cartografia i recompte municipal) es distingeixen dels resultats derivats (LST agregada, capcada, ombra i indexs) i de les propostes de gestio (rutes, refugis i prioritats). Aquesta separacio evita presentar una simulacio com si fos una mesura de confort humà.",
        MARGIN_X + 47 * mm,
        48 * mm,
        CONTENT_W - 54 * mm,
        "body",
    )
    c.showPage()


def page_poster(c: canvas.Canvas, poster_path: Path) -> None:
    section_header(c, "4", "El mapa EcoRadar Urba", "Fitxa executiva de la xarxa climatica de benestar", 5)
    rounded_card(c, MARGIN_X, 26 * mm, CONTENT_W, 153 * mm, fill=BG)
    draw_image_fit(c, poster_path, MARGIN_X + 3 * mm, 29 * mm, CONTENT_W - 6 * mm, 147 * mm)
    draw_paragraph(
        c,
        "Figura 1. Poster EcoRadar Urba aportat com a referencia executiva. Els valors LiDAR i Landsat s'expliquen i es limiten metodologicament a les pagines seguents. Les rutes i refugis son propostes de planificacio pendents de validacio de camp.",
        MARGIN_X + 4 * mm,
        24 * mm,
        CONTENT_W - 8 * mm,
        "source",
    )
    c.showPage()


def draw_map_frame(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float, title: str, legend: list[tuple[object, str]]) -> None:
    rounded_card(c, x, y, w, h, fill=CARD)
    draw_paragraph(c, f"<b>{title}</b>", x + 5 * mm, y + h - 5 * mm, w - 10 * mm, "card_title")
    image_y = y + 17 * mm
    image_h = h - 35 * mm
    draw_image_fit(c, path, x + 5 * mm, image_y, w - 10 * mm, image_h)
    c.setFillColor(NAVY)
    c.setFont("Arial-Bold", 7)
    c.drawString(x + w - 13 * mm, y + h - 16 * mm, "N")
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.2)
    c.line(x + w - 10 * mm, y + h - 25 * mm, x + w - 10 * mm, y + h - 18 * mm)
    c.line(x + w - 10 * mm, y + h - 18 * mm, x + w - 12 * mm, y + h - 21 * mm)
    c.line(x + w - 10 * mm, y + h - 18 * mm, x + w - 8 * mm, y + h - 21 * mm)
    lx = x + 6 * mm
    for color, label in legend:
        c.setFillColor(color)
        c.rect(lx, y + 6 * mm, 5 * mm, 3.2 * mm, fill=1, stroke=0)
        c.setFillColor(MUTED)
        c.setFont("Arial", 6.5)
        c.drawString(lx + 6 * mm, y + 6 * mm, cat(label))
        lx += 35 * mm
    c.setStrokeColor(INK)
    c.setLineWidth(1.5)
    c.line(x + w - 39 * mm, y + 8 * mm, x + w - 19 * mm, y + 8 * mm)
    c.setFillColor(MUTED)
    c.setFont("Arial", 6.2)
    c.drawCentredString(x + w - 29 * mm, y + 10 * mm, "200 m")


def page_lidar(c: canvas.Canvas, m: dict, assets: dict[str, Path]) -> None:
    section_header(c, "5", "Integracio LiDAR", "Ombra solar i estructura de la capcada a l'ambit central", 6)
    lidar = m["lidar_central_core"]
    gap = 4 * mm
    mw = (CONTENT_W - 3 * gap) / 4
    y_metrics = 151 * mm
    mh = 28 * mm
    draw_metric_card(c, MARGIN_X, y_metrics, mw, mh, "61,7%", "Ombra estimada", "21/06/2026, 15:00 CEST", DARK_GREEN)
    draw_metric_card(c, MARGIN_X + mw + gap, y_metrics, mw, mh, "31,8%", "Capcada", "Vegetacio mitjana i alta", GREEN)
    draw_metric_card(c, MARGIN_X + 2 * (mw + gap), y_metrics, mw, mh, "98,6%", "Cobertura DSM", "Cel.les amb superficie valida", NAVY)
    draw_metric_card(c, MARGIN_X + 3 * (mw + gap), y_metrics, mw, mh, "2 m", "Resolucio", "Graella DSM/DTM", BLUE)

    map_gap = 7 * mm
    map_w = (CONTENT_W - map_gap) / 2
    map_y = 51 * mm
    map_h = 91 * mm
    draw_map_frame(c, assets["canopy"], MARGIN_X, map_y, map_w, map_h, "Coberta de capcada LiDAR", [(DARK_GREEN, "classes 4-5"), (HexColor("#E5E7DC"), "altres superficies")])
    draw_map_frame(c, assets["shade"], MARGIN_X + map_w + map_gap, map_y, map_w, map_h, "Ombra directa estimada", [(HexColor("#4B796F"), "ombra"), (HexColor("#F7E2B8"), "sol directe"), (DARK_GREEN, "capcada")])

    rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 22 * mm, fill=PALE_ORANGE)
    draw_paragraph(
        c,
        "<b>Metode i limit.</b> Nuvoll LiDAR ICGC v3.1, classes de superficie i terreny; DSM/DTM a 2 m; posicio solar aproximada: elevacio 66,8 graus i azimut 220,4 graus. El 61,7% representa obstruccio del sol directe al solstici d'estiu a les 15 h dins 130,4 ha. No incorpora nuvolositat, vent, humitat, albedo, calor antropogenica ni resposta fisiologica, i no equival a UTCI, PET o temperatura de l'aire. [D2]",
        MARGIN_X + 7 * mm,
        39 * mm,
        CONTENT_W - 14 * mm,
        "body_small",
    )
    c.showPage()


def page_lst(c: canvas.Canvas, m: dict) -> None:
    section_header(c, "6", "Temperatura superficial", "Lectura Landsat: una fotografia termica del 8 de juliol de 2026", 7)
    landsat = m["landsat_lst"]
    gap = 4 * mm
    mw = (CONTENT_W - 3 * gap) / 4
    y = 150 * mm
    mh = 30 * mm
    draw_metric_card(c, MARGIN_X, y, mw, mh, "46,7 C", "LST mitjana", "Escena a les 12:35 CEST", ORANGE)
    draw_metric_card(c, MARGIN_X + mw + gap, y, mw, mh, "38,7 C", "Percentil 10", "Extrem inferior central", BLUE)
    draw_metric_card(c, MARGIN_X + 2 * (mw + gap), y, mw, mh, "51,1 C", "Percentil 90", "Extrem superior central", RED)
    draw_metric_card(c, MARGIN_X + 3 * (mw + gap), y, mw, mh, "1.485", "Pixels valids", "Mascara QA_PIXEL aplicada", NAVY)

    rounded_card(c, MARGIN_X, 95 * mm, CONTENT_W, 43 * mm, fill=CARD)
    draw_paragraph(c, "<b>Distribucio resumida de la LST</b>", MARGIN_X + 7 * mm, 132 * mm, 80 * mm, "card_title")
    x0 = MARGIN_X + 25 * mm
    x1 = PAGE_W - MARGIN_X - 25 * mm
    bar_y = 111 * mm
    vmin, vmax = landsat["lst_min_c"], landsat["lst_max_c"]
    c.setLineWidth(8)
    c.setStrokeColor(HexColor("#E8D9B6"))
    c.line(x0, bar_y, x1, bar_y)
    p10 = x0 + (landsat["lst_p10_c"] - vmin) / (vmax - vmin) * (x1 - x0)
    p90 = x0 + (landsat["lst_p90_c"] - vmin) / (vmax - vmin) * (x1 - x0)
    mean = x0 + (landsat["lst_mean_c"] - vmin) / (vmax - vmin) * (x1 - x0)
    c.setStrokeColor(ORANGE)
    c.setLineWidth(11)
    c.line(p10, bar_y, p90, bar_y)
    for xpos, label, color in [(x0, "35,5 min", MUTED), (p10, "38,7 P10", BLUE), (mean, "46,7 mitjana", NAVY), (p90, "51,1 P90", RED), (x1, "53,0 max", MUTED)]:
        c.setStrokeColor(color)
        c.setLineWidth(1.2)
        c.line(xpos, bar_y - 5 * mm, xpos, bar_y + 5 * mm)
        c.setFillColor(color)
        c.setFont("Arial-Bold", 6.7)
        c.drawCentredString(xpos, bar_y - 9 * mm, label)

    col_gap = 7 * mm
    col_w = (CONTENT_W - col_gap) / 2
    box_y = 49 * mm
    box_h = 37 * mm
    rounded_card(c, MARGIN_X, box_y, col_w, box_h, fill=PALE_GREEN)
    draw_paragraph(c, "<b>Que podem afirmar</b>", MARGIN_X + 6 * mm, box_y + box_h - 5 * mm, col_w - 12 * mm, "card_title")
    draw_bullets(c, ["L'escena mostra contrastos termics intensos dins l'ambit.", "La LST permet detectar superficies que acumulen calor i comparar-les amb ombra i capcada.", "La combinacio amb LiDAR millora la prioritzacio d'inspeccions de carrer."], MARGIN_X + 6 * mm, box_y + box_h - 16 * mm, col_w - 12 * mm, "body_small")
    right_x = MARGIN_X + col_w + col_gap
    rounded_card(c, right_x, box_y, col_w, box_h, fill=PALE_RED)
    draw_paragraph(c, "<b>Que no podem afirmar</b>", right_x + 6 * mm, box_y + box_h - 5 * mm, col_w - 12 * mm, "card_title")
    draw_bullets(c, ["46,7 C no es la temperatura de l'aire ni la que percep directament una persona.", "Una sola escena no descriu variabilitat diaria, nocturna o estacional.", "No es pot assignar risc sanitari individual sense exposicio, vulnerabilitat i mesures microclimatiques."], right_x + 6 * mm, box_y + box_h - 16 * mm, col_w - 12 * mm, "body_small", RED)

    draw_paragraph(c, "Font: Landsat 9 Collection 2 Level-2 ST, escena LC09_L2SP_198030_20260708_02_T1. Conversio oficial: ST = DN x 0,00341802 + 149 K; control QA_PIXEL. [D1]", MARGIN_X, 42 * mm, CONTENT_W, "source")
    c.showPage()


def page_integrated(c: canvas.Canvas) -> None:
    section_header(c, "7", "Diagnosi urbana integrada", "Evidencia, proces, consequencia i decisio de gestio", 8)
    rows: list[list[object]] = [
        [P("Afirmacio", "table_bold"), P("Evidencia disponible", "table_bold"), P("Proces i consequencia", "table_bold"), P("Decisio justificada", "table_bold")],
        [P("La proteccio climatica es rellevant pero discontinua.", "table"), P("61,7% d'ombra modelada i 31,8% de capcada a escala d'ambit; model viari amb trams de confort desigual.", "table"), P("Una mitjana d'ambit pot ocultar recorreguts essencials sense continuïtat d'ombra.", "table"), P("Mesurar l'ombra per tram i tancar discontinuïtats entre refugis i equipaments.", "table")],
        [P("La ribera del Segre es un eix climatic estrategic.", "table"), P("Continuïtat d'aigua i espais verds al mapa; ruta ribera prioritzada.", "table"), P("La infraestructura verda i blava pot aportar ombra, evaporacio, descans i orientacio territorial.", "table"), P("Connectar la ribera amb centre, CAP, escoles i places sense crear punts febles.", "table")],
        [P("Les superficies calentes requereixen contrast local.", "table"), P("LST mitjana 46,7 C; P10-P90 38,7-51,1 C en una escena estival.", "table"), P("La temperatura superficial elevada indica acumulacio de calor, pero no quantifica l'estres termic huma.", "table"), P("Prioritzar campanyes microclimatiques als trams calents i d'alta demanda peatonal.", "table")],
        [P("L'arbrat es un actiu, pero falta saber on protegeix.", "table"), P("5.500 arbres municipals i 80 especies; sense inventari georeferenciat obert.", "table"), P("El recompte global no informa de la capcada sobre vorera, estat, vulnerabilitat o equitat espacial.", "table"), P("Crear inventari arbre a arbre i indicador de capcada sobre xarxa peatonal.", "table")],
        [P("Les rutes i refugis encara son hipotesis de planificacio.", "table"), P("Cartografia i model relatiu; no hi ha auditoria completa de voreres, fonts, bancs, horaris i capacitat.", "table"), P("Una ruta aparentment fresca pot ser inutilitzable per barreres, pendents o manca de serveis.", "table"), P("Validacio de camp amb participacio de salut, mobilitat, serveis socials i usuaris vulnerables.", "table")],
    ]
    table = make_table(rows, [42 * mm, 50 * mm, 56 * mm, CONTENT_W - 148 * mm], font_size=7.0)
    table_on_canvas(c, table, MARGIN_X, 170 * mm)

    rounded_card(c, MARGIN_X, 25 * mm, CONTENT_W, 29 * mm, fill=PALE_GREEN)
    draw_paragraph(
        c,
        "<b>Lectura conjunta.</b> La diagnosi no proposa omplir la ciutat d'actuacions aïllades. Proposa una xarxa: protegir primer els recorreguts que sostenen vida quotidiana, salut, educacio i autonomia; combinar arbrat amb ombra construida on l'espai o l'aigua ho exigeixin; i verificar els beneficis amb mesures repetibles.",
        MARGIN_X + 7 * mm,
        48 * mm,
        CONTENT_W - 14 * mm,
        "body",
    )
    c.showPage()


def page_health(c: canvas.Canvas) -> None:
    section_header(c, "8", "Salut i benestar en entorns urbans", "Per que l'ombra, el verd i la mobilitat quotidiana son infraestructura sanitaria", 9)
    gap = 6 * mm
    col_w = (CONTENT_W - gap) / 2
    top = 174 * mm
    card_h = 62 * mm
    cards = [
        ("1. Reduccio de la carrega termica", PALE_ORANGE, ["La calor pot causar deshidratacio, esgotament i cop de calor, i agreujar malalties cardiovasculars, respiratories, renals, diabetis i salut mental.", "L'ombra redueix radiacio solar i temperatura radiant mitjana, un determinant clau del confort exterior en condicions assolellades.", "La planificacio urbana i els plans calor-salut poden prevenir una part important dels impactes. [H1, H4, H6]"]),
        ("2. Activitat fisica i autonomia", PALE_BLUE, ["Carrers caminables, amb ombra, bancs, fonts i destinacions properes faciliten activitat fisica quotidiana.", "Durant la calor, una xarxa protegida pot ajudar a mantenir l'acces a serveis, compres, escola i relacions socials.", "La qualitat del recorregut importa tant com la distancia, especialment per a gent gran i mobilitat reduida. [H2, H7]"]),
        ("3. Salut mental i cohesio social", PALE_GREEN, ["Les revisions de l'OMS descriuen una relacio generalment favorable entre espais verds i blaus i salut mental.", "Els mecanismes inclouen restauracio psicologica, reduccio de l'estres, activitat fisica i contacte social.", "No existeix un tipus d'espai universalment optim: qualitat, acces, seguretat i context determinen el benefici. [H2, H3, H8]"]),
        ("4. Equitat ambiental", HexColor("#F0EAF7"), ["La vulnerabilitat depen de l'edat i la salut, pero tambe de l'habitatge, la renda, l'ocupacio, l'aïllament social i la capacitat d'evitar l'exposicio.", "Persones majors de 75 anys, infants petits, malalties croniques, discapacitat, treball exterior i vida en solitud requereixen proteccio especifica.", "Prioritzar per vulnerabilitat evita que la millora es concentri nomes on ja hi ha mes verd. [H1, H4, H5]"]),
    ]
    for idx, (title, fill, bullets) in enumerate(cards):
        row = idx // 2
        col = idx % 2
        x = MARGIN_X + col * (col_w + gap)
        y = top - (row + 1) * card_h - row * gap
        rounded_card(c, x, y, col_w, card_h, fill=fill)
        draw_paragraph(c, f"<b>{title}</b>", x + 6 * mm, y + card_h - 5 * mm, col_w - 12 * mm, "card_title")
        draw_bullets(c, bullets, x + 6 * mm, y + card_h - 17 * mm, col_w - 12 * mm, "body_small")

    rounded_card(c, MARGIN_X, 20 * mm, CONTENT_W, 19 * mm, fill=CARD)
    draw_paragraph(
        c,
        "<b>Abast de l'evidencia.</b> EcoRadar utilitza aquesta base cientifica per orientar el disseny urba, pero no ha mesurat resultats de salut de la poblacio de la Seu. Qualsevol estimacio d'ingressos evitats, mortalitat, salut mental o estalvi sanitari requeriria dades locals, un disseny d'avaluacio i supervisio epidemiologica.",
        MARGIN_X + 7 * mm,
        35 * mm,
        CONTENT_W - 14 * mm,
        "body_small",
    )
    c.showPage()


def page_actions(c: canvas.Canvas) -> None:
    section_header(c, "9", "Programa d'actuacio", "De la diagnosi a un pla municipal verificable", 10)
    actions = [
        ("P1", GREEN, "Validar i publicar la xarxa climatica", "0-6 mesos", "Auditar rutes, refugis, voreres, pendents, fonts, bancs i horaris; acordar protocol d'activacio per calor.", "100% dels trams prioritaris auditats; incidencies critiques resoltes o senyalitzades."),
        ("P2", NAVY, "Tancar discontinuïtats d'ombra", "0-24 mesos", "Prioritzar punts d'espera i trams essencials amb arbrat viable, pergoles o ombra temporal; integrar drenatge i manteniment.", "Metres de xarxa prioritaria amb ombra directa a les 15 h; supervivencia de plantacions."),
        ("P3", PURPLE, "Consolidar refugis climatics", "0-12 mesos", "Verificar confort, aigua, seients, accessibilitat, capacitat, horaris i comunicacio dels espais interiors i exteriors.", "Poblacio vulnerable a menys d'un temps de recorregut acordat d'un refugi operatiu."),
        ("P4", ORANGE, "Crear l'inventari municipal d'arbrat", "0-18 mesos", "Geometria arbre a arbre, especie, capcada, estat, risc, reg i relacio amb vorera; publicar una capa oberta compatible.", "Cobertura d'inventari; percentatge de capcada sobre xarxa peatonal; buits prioritaris."),
        ("P5", RED, "Mesurar, avaluar i revisar", "cada estiu", "Campanyes repetides de temperatura, humitat, vent i globus negre; contrast amb LST/LiDAR i enquestes d'us.", "Canvi d'exposicio per tram; us de rutes/refugis; evolucio anual amb metode estable."),
    ]
    y = 154 * mm
    h = 25 * mm
    gap = 4 * mm
    for code, color, title, horizon, action, indicator in actions:
        rounded_card(c, MARGIN_X, y, CONTENT_W, h, fill=CARD)
        c.setFillColor(color)
        c.circle(MARGIN_X + 11 * mm, y + h / 2, 6.5 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Arial-Bold", 8.5)
        c.drawCentredString(MARGIN_X + 11 * mm, y + h / 2 - 2.8, code)
        c.setFillColor(NAVY)
        c.setFont("Arial-Bold", 9.3)
        c.drawString(MARGIN_X + 23 * mm, y + h - 8 * mm, cat(title))
        c.setFillColor(color)
        c.setFont("Arial-Bold", 7.4)
        c.drawRightString(PAGE_W - MARGIN_X - 6 * mm, y + h - 8 * mm, horizon)
        draw_paragraph(c, action, MARGIN_X + 23 * mm, y + h - 12 * mm, 112 * mm, "body_small")
        draw_paragraph(c, f"<b>Indicador:</b> {indicator}", MARGIN_X + 140 * mm, y + h - 12 * mm, CONTENT_W - 146 * mm, "body_small")
        y -= h + gap

    rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 16 * mm, fill=PALE_GREEN)
    draw_paragraph(c, "<b>Principi de prioritzacio:</b> primer recorreguts essencials i poblacio vulnerable; despres continuïtat de xarxa; finalment ampliacio de cobertura. Els llindars quantitatius s'han d'acordar amb l'Ajuntament i validar al camp, no inventar-los.", MARGIN_X + 7 * mm, 34 * mm, CONTENT_W - 14 * mm, "body_small")
    c.showPage()


def page_monitoring(c: canvas.Canvas) -> None:
    section_header(c, "10", "Validacio i seguiment", "Protocol minim per convertir el mapa en una eina operativa", 11)
    gap = 6 * mm
    col_w = (CONTENT_W - 2 * gap) / 3
    y = 104 * mm
    h = 70 * mm
    blocks = [
        ("A. Auditoria de camp", PALE_GREEN, ["Continuïtat i amplada de vorera.", "Pendents, creuaments i barreres.", "Ombra real per franges horaries.", "Bancs, fonts, lavabos i descans.", "Horaris, capacitat i senyalitzacio de refugis.", "Percepcio de seguretat i us real."]),
        ("B. Campanya microclimatica", PALE_BLUE, ["Temperatura i humitat de l'aire.", "Temperatura de globus / radiacio.", "Velocitat i direccio del vent.", "Punts fixos i recorreguts mobils.", "Dies normals i episodis de calor.", "Calcul UTCI/PET nomes amb variables suficients."]),
        ("C. Governanca de dades", PALE_ORANGE, ["Metadades, data i versio de cada font.", "Mateix ambit i CRS per comparar anys.", "Control de qualitat i incertesa.", "Inventari d'arbrat georeferenciat.", "Historial d'actuacions i manteniment.", "Publicacio de resultats agregats i prudents."]),
    ]
    for idx, (title, fill, bullets) in enumerate(blocks):
        x = MARGIN_X + idx * (col_w + gap)
        rounded_card(c, x, y, col_w, h, fill=fill)
        draw_paragraph(c, f"<b>{title}</b>", x + 6 * mm, y + h - 6 * mm, col_w - 12 * mm, "card_title")
        draw_bullets(c, bullets, x + 6 * mm, y + h - 19 * mm, col_w - 12 * mm, "body_small")

    rows: list[list[object]] = [
        [P("Indicador de seguiment", "table_bold"), P("Unitat", "table_bold"), P("Periodicitat", "table_bold"), P("Lectura", "table_bold")],
        [P("Ombra sobre xarxa prioritaria a hores acordades", "table"), P("% / metres", "table"), P("anual + postactuacio", "table"), P("Resultat espacial; separar arbre, edifici i ombra construida.", "table")],
        [P("Coberta de capcada sobre vorera", "table"), P("%", "table"), P("2-3 anys", "table"), P("No substituir per nombre d'arbres.", "table")],
        [P("Exposicio microclimatica", "table"), P("UTCI/PET o variables", "table"), P("campanyes estivals", "table"), P("Comparar condicions meteorologiques equivalents.", "table")],
        [P("Accessibilitat de refugis", "table"), P("temps / poblacio", "table"), P("abans de l'estiu", "table"), P("Incloure horaris, barreres i capacitat real.", "table")],
        [P("Us i satisfaccio", "table"), P("comptatge / enquesta", "table"), P("episodis de calor", "table"), P("Desagregar grups vulnerables sense exposar dades personals.", "table")],
    ]
    table = make_table(rows, [58 * mm, 30 * mm, 38 * mm, CONTENT_W - 126 * mm], font_size=7.0)
    table_on_canvas(c, table, MARGIN_X, 94 * mm)

    rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 15 * mm, fill=CARD)
    draw_paragraph(c, "<b>Criteri de revisio:</b> actualitzar el mapa quan canviin les fonts, la capcada, l'obra urbana o el protocol; conservar series comparables i publicar incerteses. Una millora visual del mapa no es prova d'una millora termica.", MARGIN_X + 7 * mm, 33 * mm, CONTENT_W - 14 * mm, "body_small")
    c.showPage()


def page_sources(c: canvas.Canvas) -> None:
    section_header(c, "11", "Fonts, limitacions i criteris d'us", "Referencies verificables i lectura prudent dels resultats", 12)
    left_x = MARGIN_X
    gap = 8 * mm
    col_w = (CONTENT_W - gap) / 2
    rounded_card(c, left_x, 48 * mm, col_w, 127 * mm, fill=CARD)
    draw_paragraph(c, "<b>Fonts de dades</b>", left_x + 6 * mm, 169 * mm, col_w - 12 * mm, "card_title")
    data_refs = [
        "<b>D1.</b> USGS EROS (2020). <i>Landsat 8-9 OLI/TIRS Level-2, Collection 2</i>. DOI 10.5066/P9OGBGM6. <link href='https://doi.org/10.5066/P9OGBGM6' color='#173D6D'>doi.org</link>; guia ST: <link href='https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature' color='#173D6D'>usgs.gov</link>.",
        "<b>D2.</b> ICGC. <i>LiDAR Territorial v3.1 (2021-2023)</i>, LAZ/LAS 1.4, classes ASPRS, CC BY 4.0. <link href='https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Elevacions/Elevacions-territorial/LiDAR-Territorial' color='#173D6D'>icgc.cat</link>; <link href='https://catalegs.ide.cat/geonetwork/srv/api/records/lidar-territorial-v3r1-2021-2023' color='#173D6D'>metadades</link>.",
        "<b>D3.</b> Ajuntament de la Seu d'Urgell. <i>La gestio actual del verd urba</i>: 22 ha, 5.500 arbres, 80 especies. <link href='https://www.laseu.cat/viure-a-la-seu/mediambient/ecoturisme-la-seu-naturalment/per-que-es-important-el-verd-urba/on-som-la-gestio-actual-del-verd-urba' color='#173D6D'>laseu.cat</link>.",
        "<b>D4.</b> ICGC i administracions locals. <i>Adreces municipals v2.2</i>, publicacio abril 2026, ETRS89/UTM 31N, CC BY 4.0. <link href='https://www.icgc.cat/ca/Geoinformacio-i-mapes/Dades-i-productes/Geoinformacio-cartografica/Adreces-municipals' color='#173D6D'>icgc.cat</link>.",
        "<b>D5.</b> OpenStreetMap contributors. Dades ODbL. <link href='https://www.openstreetmap.org/copyright' color='#173D6D'>openstreetmap.org/copyright</link>.",
        "<b>D6.</b> BBBike Extract Service. Extracte OSM de la Seu, GeoPackage, 09/07/2026. <link href='https://extract.bbbike.org/' color='#173D6D'>extract.bbbike.org</link>.",
        "<b>D7.</b> EcoRadar. <i>la_seu_urban_metrics_real_v2.json</i> i poster tecnic v0/v6; calculs derivats documentats, 09/07/2026.",
    ]
    y = 157 * mm
    for ref in data_refs:
        h = draw_paragraph(c, ref, left_x + 6 * mm, y, col_w - 12 * mm, "ref")
        y -= h + 2.6 * mm

    right_x = left_x + col_w + gap
    rounded_card(c, right_x, 48 * mm, col_w, 127 * mm, fill=CARD)
    draw_paragraph(c, "<b>Salut, benestar i adaptacio</b>", right_x + 6 * mm, 169 * mm, col_w - 12 * mm, "card_title")
    health_refs = [
        "<b>H1.</b> WHO (2026). <i>Heat and health</i>. <link href='https://www.who.int/news-room/fact-sheets/detail/climate-change-heat-and-health' color='#173D6D'>who.int</link>.",
        "<b>H2.</b> WHO Regional Office for Europe (2016). <i>Urban green spaces and health</i>. WHO/EURO:2016-3352-43111-60341. <link href='https://www.who.int/europe/publications/i/item/WHO-EURO-2016-3352-43111-60341' color='#173D6D'>who.int/europe</link>.",
        "<b>H3.</b> WHO Regional Office for Europe (2021). <i>Green and blue spaces and mental health</i>. ISBN 9789289055666. <link href='https://www.who.int/europe/publications/i/item/9789289055666' color='#173D6D'>who.int/europe</link>.",
        "<b>H4.</b> European Climate and Health Observatory / EEA. <i>Heat and health</i>. <link href='https://climate-adapt.eea.europa.eu/en/observatory/topics/health-impacts/heat-and-health' color='#173D6D'>climate-adapt.eea.europa.eu</link>.",
        "<b>H5.</b> Canal Salut (actualitzat 26/05/2026). <i>Especial precaucio amb les persones mes vulnerables a la calor</i>. <link href='https://canalsalut.gencat.cat/ca/vida-saludable/consells-estacionals/estiu/calor/especial-precaucio-persones-mes-vulnerables/' color='#173D6D'>canalsalut.gencat.cat</link>.",
        "<b>H6.</b> IPCC (2022). AR6 WGII, capitol 6, <i>Cities, settlements and key infrastructure</i>. <link href='https://www.ipcc.ch/report/ar6/wg2/chapter/chapter-6/' color='#173D6D'>ipcc.ch</link>.",
        "<b>H7.</b> WHO Europe (2023). <i>Urban and built environments</i>. <link href='https://www.who.int/europe/news-room/fact-sheets/item/urban-and-built-environments' color='#173D6D'>who.int/europe</link>.",
        "<b>H8.</b> Twohig-Bennett, C.; Jones, A. (2018). Systematic review and meta-analysis of greenspace exposure and health outcomes. <i>Environmental Research</i> 166:628-637. DOI 10.1016/j.envres.2018.06.030.",
    ]
    y = 157 * mm
    for ref in health_refs:
        h = draw_paragraph(c, ref, right_x + 6 * mm, y, col_w - 12 * mm, "ref")
        y -= h + 2.0 * mm

    rounded_card(c, MARGIN_X, 22 * mm, CONTENT_W, 19 * mm, fill=PALE_ORANGE)
    draw_paragraph(
        c,
        "<b>Limitacions principals:</b> ambit LiDAR/LST central de 130,4 ha; ombra modelada per una data i hora; LST d'una sola escena i no temperatura de l'aire; inventari municipal d'arbrat no georeferenciat; dependencia de la complecio OSM; rutes i refugis pendents de validacio de camp. Fonts web consultades el 10/07/2026.",
        MARGIN_X + 7 * mm,
        36 * mm,
        CONTENT_W - 14 * mm,
        "body_small",
    )
    c.showPage()


def export_report(metrics_path: Path, poster_path: Path, output_path: Path, assets_dir: Path) -> None:
    register_fonts()
    build_styles()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assets = build_lidar_assets(assets_dir, poster_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=landscape(A4), pageCompression=1)
    c.setTitle("EcoRadar Urbà La Seu d'Urgell - Diagnosi integrada LiDAR")
    c.setAuthor("EcoRadar")
    c.setSubject("Diagnosi de confort climàtic, salut ambiental i benestar urbà")
    c.setKeywords("EcoRadar, La Seu d'Urgell, LiDAR, Landsat, salut urbana, ombra, verd urbà")
    page_cover(c, poster_path, assets)
    page_executive(c, metrics)
    page_purpose(c)
    page_data_method(c)
    page_poster(c, poster_path)
    page_lidar(c, metrics, assets)
    page_lst(c, metrics)
    page_integrated(c)
    page_health(c)
    page_actions(c)
    page_monitoring(c)
    page_sources(c)
    c.save()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--poster", type=Path, default=DEFAULT_POSTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_report(args.metrics, args.poster, args.output, args.assets_dir)
    print(args.output)


if __name__ == "__main__":
    main()
