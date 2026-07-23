"""Build a diagnosis report with a visual EcoRadar summary sheet."""

from __future__ import annotations

import csv
import html
import json
import math
import shutil
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PROJECT = ROOT / "projectes" / "Alinya"
REPORTS = PROJECT / "reports"
INDICATORS = PROJECT / "indicators"
TMP = ROOT / "tmp" / "pdfs"
OUTPUT = ROOT / "output" / "pdf"

FITXA_PDF = REPORTS / "fitxa_diagnosi_ecoradar_alinya.pdf"
BODY_PDF = REPORTS / "diagnosi_ecoradar_alinya.pdf"
REPORT_PDF = REPORTS / "informe_diagnosi_ecoradar_alinya.pdf"
OUTPUT_REPORT_PDF = OUTPUT / "informe_diagnosi_ecoradar_alinya.pdf"
OUTPUT_FITXA_PDF = OUTPUT / "fitxa_ecoradar_alinya_a3.pdf"

GREEN_DARK = colors.HexColor("#113D30")
GREEN = colors.HexColor("#1F604B")
GREEN_MID = colors.HexColor("#4E8A5A")
GREEN_LIGHT = colors.HexColor("#EAF1E7")
SAND = colors.HexColor("#F4F3EA")
CREAM = colors.HexColor("#FBFAF3")
LINE = colors.HexColor("#C8D5CC")
TEXT = colors.HexColor("#162A23")
MUTED = colors.HexColor("#5B6B64")
ORANGE = colors.HexColor("#D26C2C")
RED = colors.HexColor("#B9412B")
GRAY = colors.HexColor("#9EA8A2")

CORE_SHORT_LABELS = {
    "CORE_01": "Mosaic paisatge",
    "CORE_02": "Valor hàbitats",
    "CORE_03": "Estat vegetació",
    "CORE_04": "Refugis climàtics",
    "CORE_05": "Vuln. climàtica",
    "CORE_06": "Biodiversitat",
    "CORE_07": "Pressió humana",
    "CORE_08": "Connectivitat",
    "CORE_09": "Resiliència foc",
    "CORE_10": "Aigua",
    "CORE_11": "Pot. restauració",
    "CORE_12": "Prioritat gestió",
}


def read_csv_dict(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def basic_value(rows: list[dict[str, str]], key: str, fallback: str = "no disponible") -> str:
    for row in rows:
        if row.get("indicador") == key:
            return str(row.get("valor") or fallback)
    return fallback


def as_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str) and value.strip().lower() == "no disponible":
            return None
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def fmt_num(value: str | float | int | None, decimals: int = 1) -> str:
    number = as_float(value)
    if number is None:
        return "no disponible"
    return f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def clean(text: str) -> str:
    return html.escape(text).replace("·", "-")


def draw_para(
    c: canvas.Canvas,
    text: str,
    x: float,
    y_top: float,
    width: float,
    style: ParagraphStyle,
) -> float:
    paragraph = Paragraph(clean(text), style)
    _, height = paragraph.wrap(width, 1000)
    paragraph.drawOn(c, x, y_top - height)
    return height


def draw_card(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str) -> None:
    c.setFillColor(CREAM)
    c.setStrokeColor(colors.white)
    c.roundRect(x, y, w, h, 5, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.45)
    c.roundRect(x, y, w, h, 5, fill=0, stroke=1)
    c.setFillColor(GREEN_DARK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 8, y + h - 15, title)


def draw_metric(c: canvas.Canvas, x: float, y: float, label: str, value: str, unit: str = "") -> None:
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, value)
    if unit:
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUTED)
        c.drawString(x, y - 9, unit)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.3)
    c.drawString(x, y - 20, label)


def draw_bar(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    label: str,
    value: float | None,
    color,
    label_width: float = 76,
) -> None:
    c.setFillColor(TEXT)
    c.setFont("Helvetica", 7.2)
    c.drawString(x, y + 3, label)
    c.setFillColor(colors.HexColor("#E3E9E4"))
    c.roundRect(x + label_width, y, w, 6, 3, fill=1, stroke=0)
    if value is not None:
        c.setFillColor(color)
        c.roundRect(x + label_width, y, max(1, w * min(value, 100) / 100), 6, 3, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 7)
        c.drawRightString(x + label_width + w + 30, y + 1, f"{value:.1f}%".replace(".", ","))
    else:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawRightString(x + label_width + w + 30, y + 1, "ND")


def draw_status_dot(c: canvas.Canvas, x: float, y: float, label: str, color) -> None:
    c.setFillColor(color)
    c.circle(x, y, 3.2 * mm, fill=1, stroke=0)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 6 * mm, y - 2.1 * mm, label)


def indicator_color(value: float | None):
    if value is None:
        return GRAY
    if value < 40:
        return RED
    if value < 60:
        return ORANGE
    if value < 80:
        return GREEN_MID
    return GREEN


def draw_fitxa() -> None:
    from ecoradar.diagnosis.engine import generate_diagnosis_outputs
    from ecoradar.product.fitxa_value import generate_fitxa_value_outputs
    from ecoradar.recommendations.engine import generate_recommendation_outputs

    REPORTS.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    generate_diagnosis_outputs(PROJECT)
    generate_recommendation_outputs(PROJECT)
    generate_fitxa_value_outputs(PROJECT)

    basic = read_csv_dict(INDICATORS / "ecoradar_01_resum.csv")
    core = read_csv_dict(INDICATORS / "ecoradar_core.csv")
    study = read_json_dict(PROJECT / "metadata" / "study_area_metadata.json")
    diagnosis = read_json_dict(PROJECT / "metadata" / "ecoradar_diagnosis.json")
    recommendations = read_json_dict(PROJECT / "metadata" / "ecoradar_recommendations.json").get("recommendations", [])
    fitxa_gate = read_json_dict(PROJECT / "metadata" / "ecoradar_fitxa_value_gate.json").get("items", [])
    map_path = PROJECT / "maps" / "producte" / "mapa_espai_alinya.png"
    if not map_path.exists():
        try:
            sys.path.insert(0, str(TOOLS))
            from export_ecoradar_product import render_maps

            render_maps()
        except Exception:
            pass

    width, height = landscape(A3)
    c = canvas.Canvas(str(FITXA_PDF), pagesize=(width, height))
    c.setTitle("Fitxa EcoRadar - Alinya")
    c.setAuthor("EcoRadar")

    c.setFillColor(SAND)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    margin = 12 * mm
    gutter = 4 * mm
    usable = width - 2 * margin
    header_h = 34 * mm
    left_w = 88 * mm
    map_w = 172 * mm
    right_w = usable - left_w - map_w - 2 * gutter
    top = height - margin
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=TEXT)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=8.5, leading=10.8, textColor=TEXT)

    c.setFillColor(GREEN_DARK)
    c.roundRect(margin, top - header_h, usable, header_h, 7, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.circle(margin + 17 * mm, top - header_h / 2, 10 * mm, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(margin + 17 * mm, top - header_h / 2 - 5, "ER")
    c.setFont("Helvetica-Bold", 24)
    c.drawString(margin + 34 * mm, top - 13 * mm, "FITXA ECORADAR")
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin + 34 * mm, top - 23 * mm, f"{study.get('project_name', 'Alinya')} - diagnosi ecològica de gestió")
    c.setFont("Helvetica", 8.5)
    c.drawRightString(margin + usable - 8 * mm, top - 12 * mm, f"Data diagnosi: {diagnosis.get('generated_at', '')[:10]}")
    c.drawRightString(margin + usable - 8 * mm, top - 23 * mm, "Lectura executiva en menys de cinc minuts")

    y0 = top - header_h - gutter
    col_h = 160 * mm
    draw_card(c, margin, y0 - 76 * mm, left_w, 76 * mm, "1. Espai i estat general")
    draw_metric(c, margin + 8 * mm, y0 - 28 * mm, "superfície", fmt_num(study.get("surface_ha") or basic_value(basic, "superficie_total"), 1), "ha")
    draw_metric(c, margin + 44 * mm, y0 - 28 * mm, "perímetre", fmt_num(study.get("perimeter_m") or basic_value(basic, "perimetre"), 0), "m")
    draw_status_dot(c, margin + 10 * mm, y0 - 48 * mm, diagnosis.get("overall_state", "diagnosi parcial").title(), ORANGE)
    draw_status_dot(c, margin + 10 * mm, y0 - 61 * mm, f"Confiança {diagnosis.get('confidence', 'mitjana-baixa')}", colors.HexColor("#317FA7"))

    draw_card(c, margin, y0 - 122 * mm, left_w, 42 * mm, "2. Valor per a la Fitxa")
    top_fitxa_item = fitxa_gate[0] if fitxa_gate else {}
    draw_para(c, "Figura de protecció: no incorporada encara amb font oficial dins la diagnosi automàtica.", margin + 7 * mm, y0 - 95 * mm, left_w - 14 * mm, small)
    draw_para(c, f"Proper salt de valor: {top_fitxa_item.get('title', 'completar dada que millori decisions')}.", margin + 7 * mm, y0 - 111 * mm, left_w - 14 * mm, small)

    draw_card(c, margin, y0 - col_h, left_w, 34 * mm, "3. Fonts utilitzades")
    draw_para(c, "Àrea d'estudi, ICGC Cobertes del sòl, Hàbitats terrestres Generalitat, GBIF, iNaturalist, OpenStreetMap/Overpass, EcoRadar Core i Fitxa Value Gate.", margin + 7 * mm, y0 - 137 * mm, left_w - 14 * mm, small)

    map_x = margin + left_w + gutter
    draw_card(c, map_x, y0 - col_h, map_w, col_h, "4. Mapa de prioritats preliminars")
    if map_path.exists():
        c.drawImage(ImageReader(str(map_path)), map_x + 8 * mm, y0 - col_h + 15 * mm, width=map_w - 16 * mm, height=col_h - 36 * mm, preserveAspectRatio=True, anchor="c")
    draw_para(
        c,
        "El mapa sintetitza cobertes, hàbitats, biodiversitat pública i accessibilitat. Encara no és una zonificació final de prioritat perquè falten aigua, foc, teledetecció, DEM i validació de camp.",
        map_x + 8 * mm,
        y0 - 13 * mm,
        map_w - 16 * mm,
        small,
    )

    right_x = map_x + map_w + gutter
    draw_card(c, right_x, y0 - 108 * mm, right_w, 108 * mm, "5. EcoRadar Core")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.4)
    c.drawString(right_x + 7 * mm, y0 - 24 * mm, "Indicadors mestres. Els buits no es puntuen.")
    bar_x = right_x + 7 * mm
    bar_y = y0 - 38 * mm
    for idx, row in enumerate(core[:12]):
        value = as_float(row.get("normalized_value"))
        label = CORE_SHORT_LABELS.get(row.get("code", ""), row.get("name", ""))
        draw_bar(c, bar_x, bar_y - idx * 6.3 * mm, right_w - 62 * mm, label, value, indicator_color(value), label_width=43 * mm)

    draw_card(c, right_x, y0 - col_h, right_w, 48 * mm, "6. Resum executiu")
    draw_para(c, diagnosis.get("executive_summary", ""), right_x + 7 * mm, y0 - 124 * mm, right_w - 14 * mm, body)

    bottom_y = margin + 18 * mm
    bottom_h = y0 - col_h - gutter - bottom_y
    card_w = (usable - 3 * gutter) / 4
    groups = [
        ("7. Fortaleses", diagnosis.get("strengths", [])[:2], GREEN_LIGHT),
        ("8. Debilitats", diagnosis.get("weaknesses", [])[:2], CREAM),
        ("9. Pressions", diagnosis.get("pressures", [])[:2], colors.HexColor("#FFF3D7")),
        ("10. Oportunitats", diagnosis.get("opportunities", [])[:2], GREEN_LIGHT),
    ]
    for i, (title, items, fill) in enumerate(groups):
        x = margin + i * (card_w + gutter)
        c.setFillColor(fill)
        c.roundRect(x, bottom_y, card_w, bottom_h, 5, fill=1, stroke=0)
        c.setStrokeColor(LINE)
        c.roundRect(x, bottom_y, card_w, bottom_h, 5, fill=0, stroke=1)
        c.setFillColor(GREEN_DARK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 6 * mm, bottom_y + bottom_h - 10 * mm, title)
        yy = bottom_y + bottom_h - 22 * mm
        for item in items:
            c.setFillColor(GREEN if title.endswith("Fortaleses") or title.endswith("Oportunitats") else ORANGE)
            c.circle(x + 8 * mm, yy - 2 * mm, 2 * mm, fill=1, stroke=0)
            draw_para(c, item.get("title", ""), x + 13 * mm, yy + 2 * mm, card_w - 20 * mm, small)
            yy -= 15 * mm

    strip_y = margin
    c.setFillColor(GREEN_DARK)
    c.roundRect(margin, strip_y, usable, 14 * mm, 5, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8.7)
    c.drawString(margin + 7 * mm, strip_y + 8.2 * mm, "Actuacions prioritàries")
    short_actions = {
        "conservar": "Conservar HIC i hàbitats prioritaris",
        "validar": "Validar mosaic, prats i discontinuïtats",
        "monitoritzar": "Monitoritzar accessos i ús públic",
    }
    action_text = "  |  ".join(
        f"{item.get('priority')}. {short_actions.get(item.get('action_type'), item.get('action_type'))}"
        for item in recommendations[:3]
    )
    strip_style = ParagraphStyle("strip", fontName="Helvetica", fontSize=6.4, leading=7.4, textColor=colors.white)
    draw_para(c, action_text, margin + 48 * mm, strip_y + 12 * mm, usable - 105 * mm, strip_style)
    c.drawRightString(margin + usable - 7 * mm, strip_y + 3.5 * mm, "La fitxa resumeix l'informe tècnic; l'informe amplia la fitxa.")

    c.showPage()
    c.save()
    shutil.copy2(FITXA_PDF, OUTPUT_FITXA_PDF)


def ensure_body_pdf() -> None:
    sys.path.insert(0, str(TOOLS))
    from export_diagnosi_pdf import export_pdf

    export_pdf()


def merge_report() -> None:
    writer = PdfWriter()
    for path in (FITXA_PDF, BODY_PDF):
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
    with REPORT_PDF.open("wb") as handle:
        writer.write(handle)
    shutil.copy2(REPORT_PDF, OUTPUT_REPORT_PDF)


def main() -> None:
    draw_fitxa()
    ensure_body_pdf()
    merge_report()


if __name__ == "__main__":
    main()
