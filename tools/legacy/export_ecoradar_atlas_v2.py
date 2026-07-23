"""Generate EcoRadar 2.0 A3 editorial diagnosis atlas for Alinya.

Version 2.0 is intentionally less template-like than the first atlas. Every
page answers a different management question and keeps missing data explicit.
It uses only the already prepared EcoRadar outputs; no connector is run here.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import export_ecoradar_atlas_a3 as a3
from tools import export_ecoradar_product

PROJECT = ROOT / "projectes" / "Alinya"
REPORTS = PROJECT / "reports"
MODULES_DIR = REPORTS / "modules"
OUTPUT = ROOT / "output" / "pdf"
METADATA = PROJECT / "metadata"

ATLAS_V2_PDF = REPORTS / "atlas_diagnosi_ecoradar_alinya_v2_a3.pdf"
MODULES_V2_PDF = MODULES_DIR / "moduls_diagnosi_ecoradar_alinya_v2_a3.pdf"
OUTPUT_V2_PDF = OUTPUT / "atlas_diagnosi_ecoradar_alinya_v2_a3.pdf"
METADATA_V2 = METADATA / "ecoradar_atlas_v2_metadata.json"

PAGE = landscape(A3)
NO_DATA = "No disponible"

GREEN_DARK = colors.HexColor("#0B3B30")
GREEN = colors.HexColor("#1E604D")
GREEN_2 = colors.HexColor("#5D9067")
GREEN_PALE = colors.HexColor("#DDEBDE")
SAND = colors.HexColor("#F2F0E5")
CREAM = colors.HexColor("#FBFAF3")
LINE = colors.HexColor("#CBD5CC")
TEXT = colors.HexColor("#152A23")
MUTED = colors.HexColor("#61746B")
ORANGE = colors.HexColor("#D06D32")
RED = colors.HexColor("#B84635")
BLUE = colors.HexColor("#2E7FA7")
GRAY = colors.HexColor("#A0AAA5")


def style(name: str, size: float, leading: float, color=TEXT, bold: bool = False) -> ParagraphStyle:
    return ParagraphStyle(
        name,
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        leading=leading,
        textColor=color,
    )


BODY = style("body", 8.6, 10.7)
SMALL = style("small", 7.0, 8.6, MUTED)
TINY = style("tiny", 6.2, 7.5, MUTED)
H2 = style("h2", 11.0, 13.0, GREEN_DARK, True)
WHITE = style("white", 8.0, 9.5, colors.white)
WHITE_H = style("white_h", 11.0, 13.0, colors.white, True)


def p(c: canvas.Canvas, text: str, x: float, y_top: float, w: float, st: ParagraphStyle = BODY) -> float:
    return a3.draw_text(c, text, x, y_top, w, st)


def card(c: canvas.Canvas, x: float, y: float, w: float, h: float, fill=CREAM, stroke=LINE) -> None:
    a3.draw_card(c, x, y, w, h, fill=fill, stroke=stroke)


def as_num(value: Any) -> float | None:
    return a3.as_float(value)


def fmt(value: Any, decimals: int = 1, suffix: str = "") -> str:
    return a3.fmt(value, decimals, suffix)


def metric(context: dict[str, Any], key: str) -> str:
    return a3.metric_value(context["basic"], key)


def core(context: dict[str, Any], code: str, key: str = "normalized_value") -> str:
    return a3.core_value(context["core"], code, key)


def pressure(context: dict[str, Any], key: str) -> str:
    return a3.pressure_value(context["pressure"], key)


def draw_footer(c: canvas.Canvas, page_no: int, title: str) -> None:
    w, _ = PAGE
    c.setFillColor(GREEN_DARK)
    c.rect(0, 0, w, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7.1)
    c.drawString(12 * mm, 2.9 * mm, "ECORADAR 2.0 - Diagnosi ecològica visual - Alinyà")
    c.drawCentredString(w / 2, 2.9 * mm, title)
    c.drawRightString(w - 12 * mm, 2.9 * mm, f"{page_no}/14")


def draw_header(c: canvas.Canvas, page_no: int, title: str, question: str, confidence: str, status: str) -> None:
    w, h = PAGE
    margin = 12 * mm
    c.setFillColor(GREEN_DARK)
    c.roundRect(margin, h - margin - 26 * mm, 205 * mm, 26 * mm, 4, fill=1, stroke=0)
    c.setStrokeColor(colors.white)
    c.setLineWidth(0.8)
    c.circle(margin + 13 * mm, h - margin - 13 * mm, 8.8 * mm, fill=0, stroke=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(margin + 13 * mm, h - margin - 17 * mm, str(page_no))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin + 29 * mm, h - margin - 10.5 * mm, title)
    c.setFont("Helvetica", 8.7)
    c.drawString(margin + 29 * mm, h - margin - 19 * mm, "Pregunta de gestió")

    qx = margin + 210 * mm
    q_w = w - qx - margin
    card(c, qx, h - margin - 26 * mm, q_w, 26 * mm)
    p(c, question, qx + 6 * mm, h - margin - 6 * mm, q_w - 56 * mm, style("q", 8.0, 9.5))
    badge_w = 25 * mm
    c.setFillColor(GRAY if status == "No disponible" else GREEN_2)
    c.roundRect(qx + q_w - 54 * mm, h - margin - 20 * mm, badge_w, 7 * mm, 3.5, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(qx + q_w - 54 * mm + badge_w / 2, h - margin - 17.5 * mm, status)
    c.setFillColor(ORANGE if confidence == "Baix" else BLUE if confidence == "Mitjà" else GREEN_2)
    c.roundRect(qx + q_w - 27 * mm, h - margin - 20 * mm, badge_w, 7 * mm, 3.5, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.drawCentredString(qx + q_w - 27 * mm + badge_w / 2, h - margin - 17.5 * mm, confidence)


def draw_map(c: canvas.Canvas, maps: dict[str, Path], key: str, x: float, y: float, w: float, h: float, title: str) -> None:
    card(c, x, y, w, h)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 9.6)
    c.drawString(x + 6 * mm, y + h - 8 * mm, title)
    path = maps.get(key) or maps["base"]
    c.drawImage(str(path), x + 5 * mm, y + 5 * mm, width=w - 10 * mm, height=h - 18 * mm, preserveAspectRatio=True, anchor="c")


def draw_metric(c: canvas.Canvas, x: float, y: float, w: float, label: str, value: str, unit: str = "", fill=GREEN_PALE) -> None:
    unavailable = value == NO_DATA or not value
    card(c, x, y, w, 20 * mm, fill=colors.HexColor("#F7F8F2") if unavailable else fill)
    c.setFillColor(GRAY if unavailable else TEXT)
    c.setFont("Helvetica-Bold", 13 if len(value) < 12 else 10)
    c.drawString(x + 5 * mm, y + 11 * mm, value or NO_DATA)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawString(x + 5 * mm, y + 5 * mm, label[:38])
    if unit:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.4)
        c.drawString(x + 5 * mm, y + 2.2 * mm, unit)


def draw_bar(c: canvas.Canvas, x: float, y: float, w: float, label: str, value: str, max_value: float, color=GREEN_2) -> None:
    c.setFillColor(TEXT)
    c.setFont("Helvetica", 7)
    c.drawString(x, y + 1.3 * mm, label)
    c.setFillColor(colors.HexColor("#E2E8E2"))
    c.roundRect(x + 42 * mm, y, w - 62 * mm, 4 * mm, 2, fill=1, stroke=0)
    number = as_num(value)
    if number is not None:
        c.setFillColor(color)
        c.roundRect(x + 42 * mm, y, (w - 62 * mm) * max(0, min(1, number / max_value)), 4 * mm, 2, fill=1, stroke=0)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(x + w, y + 0.6 * mm, value)


def draw_table(c: canvas.Canvas, rows: list[list[str]], x: float, y_top: float, widths: list[float]) -> float:
    data = []
    for i, row in enumerate(rows):
        st = style("th", 7.0, 8.4, colors.white, True) if i == 0 else style("td", 6.9, 8.2)
        data.append([Paragraph(a3.clean(cell), st) for cell in row])
    table = Table(data, colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F8F1")),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    _, h = table.wrap(sum(widths), 1000)
    table.drawOn(c, x, y_top - h)
    return h


def draw_sources(c: canvas.Canvas, x: float, y: float, w: float, sources: str, date: str) -> None:
    card(c, x, y, w, 18 * mm, fill=colors.HexColor("#F8F8F0"))
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawString(x + 4 * mm, y + 12 * mm, "Fonts i actualització")
    p(c, f"{sources}. Actualització: {date}.", x + 4 * mm, y + 9 * mm, w - 8 * mm, TINY)


def available_core_values(context: dict[str, Any]) -> list[float]:
    values: list[float] = []
    for row in context["core"]:
        value = as_num(row.get("normalized_value"))
        if value is not None:
            values.append(value)
    return values


def traffic_color(value: float | None) -> Any:
    if value is None:
        return GRAY
    if value >= 70:
        return GREEN_2
    if value >= 45:
        return ORANGE
    return RED


def page_radiografia(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    w, h = PAGE
    draw_header(c, 1, "Radiografia ecològica", "Quin és l'estat general de l'espai i què cal mirar primer?", "Baix", "Parcial")
    margin = 12 * mm
    top = h - 45 * mm
    values = available_core_values(context)
    global_index = round(statistics.mean(values), 1) if values else None

    card(c, margin, top - 72 * mm, 72 * mm, 72 * mm, fill=GREEN_DARK)
    p(c, "Lectura global EcoRadar", margin + 7 * mm, top - 7 * mm, 58 * mm, WHITE_H)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(margin + 36 * mm, top - 34 * mm, fmt(global_index, 1) if global_index is not None else NO_DATA)
    c.setFont("Helvetica", 10)
    c.drawCentredString(margin + 36 * mm, top - 44 * mm, "0-100 preliminar")
    p(c, "Valor calculat només amb indicadors disponibles o parcials. No és una puntuació final de conservació.", margin + 7 * mm, top - 53 * mm, 58 * mm, WHITE)

    draw_map(c, maps, "espai", margin + 78 * mm, top - 122 * mm, 178 * mm, 122 * mm, "Mapa resum de l'espai")

    x = margin + 262 * mm
    card(c, x, top - 122 * mm, w - x - margin, 122 * mm)
    p(c, "Semàfors de decisió", x + 6 * mm, top - 7 * mm, 70 * mm, H2)
    sem = [
        ("Hàbitats", core(context, "CORE_02"), "Valor alt, validar sensibilitat"),
        ("Biodiversitat", core(context, "CORE_06"), "Base pública forta, biaix d'esforç"),
        ("Mosaic", core(context, "CORE_01"), "Cal continuïtat espacial"),
        ("Pressió humana", core(context, "CORE_07"), "Accessibilitat, no afluència"),
        ("Aigua", core(context, "CORE_10"), "Sense dada incorporada"),
        ("Vegetació", core(context, "CORE_03"), "Sense teledetecció"),
    ]
    yy = top - 20 * mm
    for label, value, note in sem:
        num = as_num(value)
        c.setFillColor(traffic_color(num))
        c.circle(x + 8 * mm, yy + 1 * mm, 2.8 * mm, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 7.8)
        c.drawString(x + 14 * mm, yy, label)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.7)
        c.drawString(x + 42 * mm, yy, value if value else NO_DATA)
        c.drawString(x + 60 * mm, yy, note[:44])
        yy -= 12 * mm

    y2 = 28 * mm
    widths = [82 * mm, 82 * mm, 82 * mm, 82 * mm]
    labels = [
        ("Fortaleses", "Hàbitats d'interès extensos, alta biodiversitat citada, matriu natural dominant."),
        ("Amenaces", "Continuïtat forestal i pressió potencial encara poc caracteritzades; ús públic real no mesurat."),
        ("Oportunitats", "Orientar camp amb buits detectats i conservar espais oberts clau abans de perdre mosaic."),
        ("Comparació", "No disponible fins incorporar altres espais EcoRadar o valors regionals de referència."),
    ]
    for i, (title, text) in enumerate(labels):
        xx = margin + i * (widths[i] + 5 * mm)
        card(c, xx, y2, widths[i], 47 * mm)
        p(c, title, xx + 5 * mm, y2 + 39 * mm, widths[i] - 10 * mm, H2)
        p(c, text, xx + 5 * mm, y2 + 26 * mm, widths[i] - 10 * mm, BODY)
    draw_footer(c, 1, "Radiografia ecològica")


def page_biodiversitat(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    w, h = PAGE
    draw_header(c, 2, "Biodiversitat", "Què sabem de les espècies i on pot estar esbiaixada la informació?", "Mitjà", "Parcial")
    margin = 12 * mm
    top = h - 45 * mm
    draw_map(c, maps, "biodiversitat", margin, top - 168 * mm, 188 * mm, 168 * mm, "Registres públics normalitzats")
    x = margin + 194 * mm
    draw_metric(c, x, top - 20 * mm, 52 * mm, "Espècies citades", fmt(metric(context, "nombre_especies_registrades"), 0), "taxons")
    draw_metric(c, x + 58 * mm, top - 20 * mm, 52 * mm, "Registres recents", fmt(metric(context, "nombre_registres_recents"), 0), "cites")
    draw_metric(c, x + 116 * mm, top - 20 * mm, 52 * mm, "Registres totals", fmt(metric(context, "nombre_registres_biodiversitat"), 0), "cites")

    card(c, x, top - 85 * mm, 168 * mm, 56 * mm)
    p(c, "Com es reparteix el coneixement?", x + 6 * mm, top - 36 * mm, 80 * mm, H2)
    yy = top - 48 * mm
    for row in context["biodiv"][:6]:
        draw_bar(c, x + 6 * mm, yy, 154 * mm, row["grup_taxonomic"], row["nombre_registres"], 300, BLUE)
        yy -= 8 * mm

    card(c, x, top - 134 * mm, 82 * mm, 42 * mm)
    p(c, "Risc d'interpretació", x + 5 * mm, top - 99 * mm, 70 * mm, H2)
    p(c, "Les cites indiquen on hi ha coneixement, no necessàriament on hi ha més biodiversitat. Els buits poden ser manca d'esforç de mostreig.", x + 5 * mm, top - 113 * mm, 72 * mm, BODY)
    card(c, x + 88 * mm, top - 134 * mm, 80 * mm, 42 * mm, fill=colors.HexColor("#FFF5E8"))
    p(c, "Dades encara no creuades", x + 93 * mm, top - 99 * mm, 68 * mm, H2)
    p(c, "Espècies protegides, amenaçades, indicadores i invasores: No disponible. Sense aquest creuament, la pàgina orienta camp i prudència, no prioritza espècies sensibles.", x + 93 * mm, top - 113 * mm, 68 * mm, BODY)

    rows = [["Decisió", "Criteri"], ["Monitoritzar", "Grups infrarepresentats i zones sense mostreig"], ["Validar", "Cites sensibles o antigues"], ["Conservar", "Zones amb concentració de valors quan es validin"]]
    draw_table(c, rows, x, top - 146 * mm, [43 * mm, 125 * mm])
    draw_sources(c, x, 21 * mm, 168 * mm, "GBIF; iNaturalist", context["metadata"]["biodiv"].get("query_date", "")[:10])
    draw_footer(c, 2, "Biodiversitat")


def page_habitats(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    w, h = PAGE
    draw_header(c, 3, "Hàbitats", "Quins hàbitats condicionen qualsevol actuació de gestió?", "Mitjà", "Parcial")
    margin = 12 * mm
    top = h - 45 * mm
    draw_map(c, maps, "habitats", margin, top - 126 * mm, 220 * mm, 126 * mm, "Hàbitats d'interès i prioritaris")
    x = margin + 226 * mm
    hic = as_num(metric(context, "superficie_hic")) or 0
    total = as_num(metric(context, "superficie_total")) or 0
    hic_pct = hic / total * 100 if total else None
    priority = sum((as_num(row.get("superficie_ha")) or 0) for row in context["habitats"] if str(row.get("es_prioritari", "")).lower() == "true")
    draw_metric(c, x, top - 22 * mm, 48 * mm, "Hàbitats", fmt(metric(context, "nombre_habitats"), 0), "tipus")
    draw_metric(c, x + 54 * mm, top - 22 * mm, 48 * mm, "HIC", fmt(hic, 0), "ha")
    draw_metric(c, x + 108 * mm, top - 22 * mm, 48 * mm, "HIC prioritaris", fmt(priority, 0), "ha")
    card(c, x, top - 91 * mm, 156 * mm, 60 * mm)
    p(c, "Els hàbitats com a capa de prudència", x + 6 * mm, top - 39 * mm, 125 * mm, H2)
    p(c, f"Els HIC representen aproximadament {fmt(hic_pct, 1, '%')} de l'àrea analitzada. No són un diagnòstic d'estat de conservació, sinó una alerta de responsabilitat: abans d'actuar cal saber quin hàbitat es pot afectar i amb quin grau de reversibilitat.", x + 6 * mm, top - 53 * mm, 138 * mm, BODY)

    top_habs = [["Codi", "Hàbitat principal", "ha"]]
    for row in context["habitats"][:5]:
        top_habs.append([row["codi_habitat"], row["nom_habitat"][:70], fmt(row["superficie_ha"], 0)])
    draw_table(c, top_habs, margin, 82 * mm, [22 * mm, 210 * mm, 24 * mm])
    card(c, margin + 264 * mm, 21 * mm, 72 * mm, 60 * mm, fill=GREEN_DARK)
    p(c, "Decisions", margin + 270 * mm, 72 * mm, 60 * mm, WHITE_H)
    p(c, "Conservar HIC prioritaris. Validar estat local. Evitar actuacions uniformes en hàbitats sensibles.", margin + 270 * mm, 58 * mm, 58 * mm, WHITE)
    draw_sources(c, margin + 264 * mm, 21 * mm, 72 * mm, "Cartografia hàbitats terrestres v3; HIC", context["metadata"]["habitats"].get("query_date", "")[:10])
    draw_footer(c, 3, "Hàbitats")


def page_paisatge(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    w, h = PAGE
    draw_header(c, 4, "Paisatge i connectivitat", "El mosaic actual ajuda o limita la gestió ecològica?", "Mitjà", "Parcial")
    margin = 12 * mm
    top = h - 45 * mm
    draw_map(c, maps, "paisatge", margin + 108 * mm, top - 154 * mm, 150 * mm, 154 * mm, "Mosaic de cobertes")
    left = margin
    draw_metric(c, left, top - 22 * mm, 46 * mm, "Forestal", fmt(metric(context, "percentatge_coberta_forestal"), 1, "%"))
    draw_metric(c, left + 52 * mm, top - 22 * mm, 46 * mm, "Prats", fmt(metric(context, "percentatge_prats_pastures_herbassars"), 1, "%"))
    card(c, left, top - 91 * mm, 98 * mm, 62 * mm)
    p(c, "Història que explica el paisatge", left + 5 * mm, top - 38 * mm, 82 * mm, H2)
    p(c, "La matriu forestal dominant no és bona o dolenta per si sola. La decisió clau és si deixa prou heterogeneïtat per mantenir prats, ecotons, fauna de medis oberts i discontinuïtats útils.", left + 5 * mm, top - 52 * mm, 86 * mm, BODY)
    card(c, margin + 264 * mm, top - 154 * mm, 72 * mm, 154 * mm)
    p(c, "Connectivitat: què falta?", margin + 270 * mm, top - 8 * mm, 58 * mm, H2)
    for i, item in enumerate(["Barreres", "Xarxa de riberes", "Continuïtat forestal", "Infraestructures", "Corredors potencials"]):
        draw_metric(c, margin + 270 * mm, top - (28 + i * 22) * mm, 58 * mm, item, NO_DATA)
    rows = [["Gestió", "Lectura"], ["Mantenir", "Espais oberts i prats amb funció de mosaic"], ["Ampliar dades", "Continuïtat espacial i barreres"], ["Evitar", "Actuacions homogènies sobre tot el bosc"]]
    draw_table(c, rows, margin, 58 * mm, [48 * mm, 202 * mm])
    draw_sources(c, margin + 258 * mm, 21 * mm, 78 * mm, "ICGC Cobertes del sòl; EcoRadar Core", context["metadata"]["cover"].get("data_consulta", "")[:10])
    draw_footer(c, 4, "Paisatge i connectivitat")


def page_pressio(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    w, h = PAGE
    draw_header(c, 5, "Pressió humana", "On pot concentrar-se l'ús públic i quin risc de conflicte pot generar?", "Baix", "Parcial")
    margin = 12 * mm
    top = h - 45 * mm
    draw_map(c, maps, "pressio", margin, top - 145 * mm, 188 * mm, 145 * mm, "Accessibilitat i punts d'ús públic")
    x = margin + 194 * mm
    draw_metric(c, x, top - 22 * mm, 52 * mm, "Xarxa", fmt(pressure(context, "osm_path_track_road_km"), 1), "km")
    draw_metric(c, x + 58 * mm, top - 22 * mm, 52 * mm, "Densitat", fmt(pressure(context, "osm_path_track_road_density"), 2), "km/km2")
    draw_metric(c, x + 116 * mm, top - 22 * mm, 52 * mm, "Punts", fmt(pressure(context, "osm_recreational_point_features"), 0), "ús públic")
    card(c, x, top - 86 * mm, 168 * mm, 56 * mm)
    p(c, "Mapa de conflicte potencial", x + 6 * mm, top - 38 * mm, 110 * mm, H2)
    p(c, "El mapa mostra estructura d'accés, no pressió real. El conflicte ecològic apareix quan accessibilitat, freqüentació i sensibilitat biològica coincideixen. Ara només es pot detectar on cal validar.", x + 6 * mm, top - 52 * mm, 150 * mm, BODY)
    rows = [["Risc", "Lectura de gestió"], ["Alt potencial", "Camins o punts d'ús sobre hàbitats sensibles: cal validar"], ["Baix coneixement", "Zones amb accessos però sense dades de fauna: mostreig"], ["No estimat", "Nombre real de visitants"]]
    draw_table(c, rows, x, top - 98 * mm, [38 * mm, 130 * mm])
    action_y = 63 * mm
    actions = [
        ("Regular?", "Només si la intensitat real confirma pressió sobre zones sensibles."),
        ("Validar?", "Aparcaments, accessos principals i camins sobre hàbitats d'interès."),
        ("No concloure", "No estimar visitants només amb camins OSM."),
    ]
    for i, (title, text) in enumerate(actions):
        xx = x + i * 56 * mm
        card(c, xx, action_y, 52 * mm, 31 * mm, fill=colors.HexColor("#FFF5E8") if i != 1 else GREEN_PALE)
        p(c, title, xx + 4 * mm, action_y + 23 * mm, 42 * mm, H2)
        p(c, text, xx + 4 * mm, action_y + 12 * mm, 42 * mm, TINY)
    draw_sources(c, x, 21 * mm, 168 * mm, "OpenStreetMap; Overpass API", context["metadata"]["pressure"].get("date_consulted", "")[:10])
    draw_footer(c, 5, "Pressió humana")


def page_aigua(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 6, "Recursos hídrics", "Què no podem decidir encara sense conèixer l'aigua?", "Baix", "No disponible")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    draw_map(c, maps, "base", margin + 92 * mm, top - 150 * mm, 170 * mm, 150 * mm, "Context territorial per incorporar hidrologia")
    left = margin
    for i, label in enumerate(["Cursos fluvials", "Fonts i basses", "Zones humides", "Funcionalitat hídrica"]):
        draw_metric(c, left, top - (22 + i * 27) * mm, 72 * mm, label, NO_DATA, fill=colors.HexColor("#F7F8F2"))
    x = margin + 270 * mm
    card(c, x, top - 150 * mm, 66 * mm, 150 * mm, fill=colors.HexColor("#FFF5E8"))
    p(c, "Decisió bloquejada", x + 6 * mm, top - 8 * mm, 54 * mm, H2)
    p(c, "L'aigua estructura refugis, reproducció, connectivitat i resiliència. Sense hidrografia fina i punts verificats no és rigorós delimitar corredors de ribera, basses clau ni restauració associada a l'aigua.", x + 6 * mm, top - 23 * mm, 54 * mm, BODY)
    p(c, "Acció EcoRadar", x + 6 * mm, top - 83 * mm, 54 * mm, H2)
    p(c, "Incorporar font oficial, validar punts d'aigua al camp i creuar-los amb fauna, ombra, hàbitats i sequera. Aquesta dada convertirà un buit crític en criteri de priorització.", x + 6 * mm, top - 98 * mm, 54 * mm, BODY)
    draw_sources(c, x, 21 * mm, 66 * mm, "Font hidrològica oficial pendent d'incorporació", context["metadata"]["core"].get("generated_at", "")[:10])
    draw_footer(c, 6, "Recursos hídrics")


def page_boscos(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 7, "Boscos i estructura forestal", "On el bosc és valor, on és continuïtat i on caldria llegir mosaic?", "Baix", "Parcial")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    draw_map(c, maps, "paisatge", margin, top - 152 * mm, 176 * mm, 152 * mm, "Estructura forestal i espais oberts")
    x = margin + 184 * mm
    draw_metric(c, x, top - 22 * mm, 50 * mm, "Forestal", fmt(metric(context, "percentatge_coberta_forestal"), 1, "%"))
    draw_metric(c, x + 56 * mm, top - 22 * mm, 50 * mm, "Espais oberts", fmt(metric(context, "percentatge_prats_pastures_herbassars"), 1, "%"))
    draw_metric(c, x + 112 * mm, top - 22 * mm, 50 * mm, "Resiliència", fmt(core(context, "CORE_09"), 1), "0-100")
    card(c, x, top - 94 * mm, 162 * mm, 60 * mm)
    p(c, "La pregunta no és 'tallar o no tallar'", x + 6 * mm, top - 52 * mm, 130 * mm, H2)
    p(c, "La gestió forestal no hauria de començar reduint biomassa de manera homogènia. La decisió correcta és detectar on el mosaic pot augmentar resiliència sense degradar hàbitats d'interès ni eliminar refugis.", x + 6 * mm, top - 67 * mm, 146 * mm, BODY)
    rows = [["Criteri", "Estat"], ["Mosaic obert", "Disponible parcial"], ["Continuïtat crítica", NO_DATA], ["Pendent i orientació", NO_DATA], ["Humitat vegetal", NO_DATA]]
    draw_table(c, rows, x, top - 108 * mm, [45 * mm, 65 * mm])
    draw_sources(c, x + 116 * mm, 21 * mm, 46 * mm, "ICGC Cobertes; EcoRadar Core", context["metadata"]["cover"].get("data_consulta", "")[:10])
    draw_footer(c, 7, "Boscos i estructura forestal")


def page_historia(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 8, "Història ecològica", "Què ha passat al territori i com s'ha recuperat?", "Baix", "No disponible")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    card(c, margin, top - 152 * mm, 336 * mm, 152 * mm)
    p(c, "Aquest mòdul ha de convertir-se en una peça central d'EcoRadar", margin + 8 * mm, top - 9 * mm, 200 * mm, H2)
    p(c, "La història ecològica diferencia estat i trajectòria. Ara no hi ha prou dades per reconstruir memòria del territori i no es dibuixa cap evolució fictícia. Quan s'incorporin incendis, NDVI, canvis d'ús i biodiversitat temporal, aquesta pàgina explicarà recuperació, recurrència i canvis de rumb.", margin + 8 * mm, top - 24 * mm, 200 * mm, BODY)
    timeline_y = top - 72 * mm
    c.setStrokeColor(GREEN_DARK)
    c.setLineWidth(1.4)
    c.line(margin + 20 * mm, timeline_y, margin + 315 * mm, timeline_y)
    milestones = [("Incendis", NO_DATA), ("Canvis d'ús", NO_DATA), ("NDVI", NO_DATA), ("Recurrència", NO_DATA), ("Biodiversitat", NO_DATA)]
    for i, (label, value) in enumerate(milestones):
        xx = margin + 28 * mm + i * 65 * mm
        c.setFillColor(ORANGE)
        c.circle(xx, timeline_y, 4 * mm, fill=1, stroke=0)
        p(c, label, xx - 18 * mm, timeline_y - 10 * mm, 36 * mm, style("tl", 7.3, 8.5, TEXT, True))
        p(c, value, xx - 18 * mm, timeline_y - 20 * mm, 36 * mm, SMALL)
    card(c, margin + 8 * mm, 30 * mm, 150 * mm, 44 * mm, fill=colors.HexColor("#FFF5E8"))
    p(c, "Per què importa?", margin + 14 * mm, 66 * mm, 120 * mm, H2)
    p(c, "Sense història no sabem si l'estat actual és degradació, recuperació, estabilitat o canvi recent. La mateixa coberta pot exigir gestions oposades segons la trajectòria.", margin + 14 * mm, 52 * mm, 120 * mm, BODY)
    future_x = margin + 166 * mm
    card(c, future_x, 30 * mm, 92 * mm, 44 * mm, fill=colors.HexColor("#F7F8F2"))
    p(c, "Què desbloquejarà decisions?", future_x + 5 * mm, 66 * mm, 74 * mm, H2)
    p(c, "Incendis: recurrència. NDVI: recuperació de vigor. Usos del sòl: canvi de mosaic. Biodiversitat: retorn d'espècies indicadores.", future_x + 5 * mm, 52 * mm, 78 * mm, SMALL)
    draw_sources(c, margin + 264 * mm, 30 * mm, 62 * mm, "Perímetres d'incendi i sèries temporals pendents d'incorporació", context["metadata"]["core"].get("generated_at", "")[:10])
    draw_footer(c, 8, "Història ecològica")


def page_tranquillitat(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 9, "Tranquil·litat ecològica", "On podria existir baixa pertorbació útil per a la fauna?", "Baix", "Parcial")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    draw_map(c, maps, "pressio", margin + 92 * mm, top - 150 * mm, 170 * mm, 150 * mm, "Accessibilitat com a pressió potencial")
    left = margin
    draw_metric(c, left, top - 22 * mm, 72 * mm, "Densitat d'accessos", fmt(pressure(context, "osm_path_track_road_density"), 2), "km/km2")
    draw_metric(c, left, top - 49 * mm, 72 * mm, "Punts d'ús públic", fmt(pressure(context, "osm_recreational_point_features"), 0), "punts")
    draw_metric(c, left, top - 76 * mm, 72 * mm, "Intensitat real", NO_DATA)
    card(c, left, top - 150 * mm, 72 * mm, 64 * mm)
    p(c, "Indicador propi EcoRadar", left + 5 * mm, top - 94 * mm, 60 * mm, H2)
    p(c, "La tranquil·litat ecològica és probabilitat funcional de baixa pertorbació per a la fauna. No és el contrari simple de camins: depèn d'ús real, sensibilitat, relleu, cobertes i refugis.", left + 5 * mm, top - 108 * mm, 60 * mm, BODY)
    x = margin + 270 * mm
    rows = [["Factor", "Estat"], ["Accessibilitat", "Parcial"], ["Ús públic real", NO_DATA], ["Fauna sensible", NO_DATA], ["Hàbitats", "Parcial"], ["Relleu", NO_DATA]]
    card(c, x, top - 150 * mm, 66 * mm, 150 * mm)
    draw_table(c, rows, x + 5 * mm, top - 10 * mm, [30 * mm, 26 * mm])
    draw_sources(c, x, 21 * mm, 66 * mm, "OSM; biodiversitat pública; hàbitats", context["metadata"]["pressure"].get("date_consulted", "")[:10])
    draw_footer(c, 9, "Tranquil·litat ecològica")


def page_clima(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 10, "Vulnerabilitat i canvi climàtic", "On hi pot haver estrès i on hi pot haver refugi climàtic?", "Baix", "Parcial")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    draw_map(c, maps, "base", margin, top - 150 * mm, 172 * mm, 150 * mm, "Base territorial per futures capes climàtiques")
    x = margin + 180 * mm
    draw_metric(c, x, top - 22 * mm, 50 * mm, "Forestal", fmt(metric(context, "percentatge_coberta_forestal"), 1, "%"))
    draw_metric(c, x + 56 * mm, top - 22 * mm, 50 * mm, "Artificial", fmt(metric(context, "percentatge_urba_artificial"), 2, "%"))
    draw_metric(c, x + 112 * mm, top - 22 * mm, 50 * mm, "NDMI", NO_DATA)
    card(c, x, top - 104 * mm, 162 * mm, 70 * mm, fill=colors.HexColor("#F7F8F2"))
    p(c, "Encara no és un mapa climàtic", x + 6 * mm, top - 43 * mm, 120 * mm, H2)
    p(c, "La cobertura forestal pot suggerir ombra i microclima, però no delimita refugis reals. Un refugi climàtic exigeix evidència convergent: temperatura superficial baixa, humitat, orientació, relleu i aigua.", x + 6 * mm, top - 58 * mm, 140 * mm, BODY)
    rows = [["Capa", "Estat"], ["NDVI", NO_DATA], ["NDMI", NO_DATA], ["NDWI", NO_DATA], ["LST", NO_DATA], ["DEM/orientació", NO_DATA]]
    draw_table(c, rows, x, top - 118 * mm, [35 * mm, 45 * mm])
    draw_sources(c, x + 86 * mm, 21 * mm, 76 * mm, "ICGC Cobertes; Copernicus pendent de credencials", context["metadata"]["tele"].get("query_date", "")[:10])
    draw_footer(c, 10, "Vulnerabilitat i canvi climàtic")


def page_coneixement(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 11, "Coneixement disponible i buits", "Quines decisions són robustes i quines encara depenen de dades?", "Mitjà", "Parcial")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    rows = [["Àmbit", "Dades actuals", "Confiança", "Decisió possible"]]
    entries = [
        ("Cobertes", "Classes i superfícies", "Mitjana", "Llegir mosaic general"),
        ("Hàbitats", "HIC i prioritaris", "Mitjana", "Capa de prudència"),
        ("Biodiversitat", "Registres públics", "Mitjana", "Orientar camp"),
        ("Pressió humana", "OSM accessos", "Baixa", "Accessibilitat potencial"),
        ("Aigua", NO_DATA, "Baixa", "No zonificar"),
        ("Foc/història", NO_DATA, "Baixa", "No prioritzar actuacions finals"),
        ("Clima", "Coberta com a proxy", "Baixa", "No delimitar refugis"),
    ]
    for row in entries:
        rows.append(list(row))
    draw_table(c, rows, margin, top, [42 * mm, 70 * mm, 32 * mm, 130 * mm])
    draw_map(c, maps, "espai", margin, 24 * mm, 142 * mm, 92 * mm, "Capes disponibles sobre l'espai")
    card(c, margin + 150 * mm, 24 * mm, 186 * mm, 92 * mm, fill=GREEN_DARK)
    p(c, "Regla de decisió", margin + 158 * mm, 104 * mm, 150 * mm, WHITE_H)
    p(c, "La confiança és una variable de gestió. EcoRadar no busca omplir pàgines amb aparença de certesa: separa què ja permet decidir, què només orienta i què exigeix dades o camp abans d'actuar.", margin + 158 * mm, 88 * mm, 154 * mm, WHITE)
    draw_footer(c, 11, "Coneixement disponible i buits")


def page_recomanacions(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 12, "Recomanacions de gestió", "Quines accions tenen sentit amb el coneixement actual?", "Mitjà", "Parcial")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    draw_map(c, maps, "espai", margin + 154 * mm, top - 150 * mm, 182 * mm, 150 * mm, "Mapa integrat per orientar accions")
    actions = [
        ("Conservar", "HIC i hàbitats prioritaris abans de qualsevol actuació."),
        ("Monitoritzar", "Accessos i punts d'ús públic amb possible concentració."),
        ("Validar", "Espais oberts, grups de biodiversitat i punts sensibles."),
        ("Ampliar dades", "Aigua, clima, foc, relleu i ús públic real."),
    ]
    for i, (title, text) in enumerate(actions):
        y = top - (35 + i * 30) * mm
        card(c, margin, y, 132 * mm, 24 * mm, fill=GREEN_PALE if i == 0 else CREAM)
        p(c, title, margin + 6 * mm, y + 17 * mm, 40 * mm, H2)
        p(c, text, margin + 50 * mm, y + 17 * mm, 72 * mm, BODY)
    draw_sources(c, margin, 21 * mm, 132 * mm, "EcoRadar Core; fonts públiques processades", context["metadata"]["core"].get("generated_at", "")[:10])
    draw_footer(c, 12, "Recomanacions de gestió")


def page_prioritats_core(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 13, "Prioritats de gestió", "Què es pot prioritzar ara sense sobreactuar?", "Baix", "Parcial")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    draw_map(c, maps, "habitats", margin, top - 150 * mm, 172 * mm, 150 * mm, "Valor ecològic com a primera capa de prioritat")
    x = margin + 180 * mm
    rows = [["Prioritat", "Criteri", "Confiança"], ["1. Conservació", "HIC i hàbitats prioritaris", "Mitjana"], ["2. Validació", "Espais oberts i accessos", "Mitjana/baixa"], ["3. Monitoratge", "Pressió potencial d'ús públic", "Baixa"], ["4. Ampliació", "Aigua, foc, clima i camp", "Baixa"]]
    draw_table(c, rows, x, top, [48 * mm, 100 * mm, 42 * mm])
    card(c, x, 35 * mm, 190 * mm, 70 * mm, fill=colors.HexColor("#FFF5E8"))
    p(c, "Encara no hi ha top 10 de zones", x + 6 * mm, 94 * mm, 140 * mm, H2)
    p(c, "Un top 10 seria una falsa precisió sense hidrologia, foc, clima, relleu i validació de camp. La decisió experta ara és prioritzar conservació prudent, camp dirigit i incorporació de dades que canviaran decisions.", x + 6 * mm, 78 * mm, 160 * mm, BODY)
    draw_footer(c, 13, "Prioritats de gestió")


def page_pla_prioritats(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    draw_header(c, 14, "Pla de prioritats", "Quin pla d'acció curt pot seguir el gestor després de llegir EcoRadar?", "Baix", "Parcial")
    margin = 12 * mm
    _, h = PAGE
    top = h - 45 * mm
    draw_map(c, maps, "espai", margin, top - 150 * mm, 184 * mm, 150 * mm, "Mapa preliminar d'orientació de prioritats")
    x = margin + 192 * mm
    plan = [
        ("Conservació", "Protegir i revisar HIC, HIC prioritaris i zones amb valor d'hàbitat."),
        ("Restauració", "No zonificada encara; dependrà d'aigua, vegetació, relleu i camp."),
        ("Seguiment", "Biodiversitat pública, grups infrarepresentats i accessos principals."),
        ("Conflictes", "Creuament potencial entre ús públic i valors ecològics; cal intensitat real."),
        ("Refugis", "Potencial només indirecte; cal NDMI, LST, orientació i punts d'aigua."),
    ]
    for i, (title, text) in enumerate(plan):
        y = top - (24 + i * 26) * mm
        color = GREEN_PALE if i == 0 else colors.HexColor("#FFF5E8") if i in (1, 3) else CREAM
        card(c, x, y, 144 * mm, 20 * mm, fill=color)
        p(c, title, x + 5 * mm, y + 14 * mm, 35 * mm, style("pt", 8.0, 9.3, TEXT, True))
        p(c, text, x + 42 * mm, y + 14 * mm, 92 * mm, SMALL)
    card(c, margin, 21 * mm, 336 * mm, 42 * mm, fill=GREEN_DARK)
    p(c, "Pla d'acció curt", margin + 8 * mm, 54 * mm, 100 * mm, WHITE_H)
    action_style = style("action_white", 8.6, 11.2, colors.white)
    p(c, "1. Confirmar hàbitats sensibles. 2. Fer camp dirigit als buits. 3. Incorporar aigua, clima i foc. 4. Mesurar ús públic real. 5. Regenerar EcoRadar i només llavors zonificar actuacions finals.", margin + 8 * mm, 39 * mm, 300 * mm, action_style)
    draw_footer(c, 14, "Pla de prioritats")


PAGES = [
    page_radiografia,
    page_biodiversitat,
    page_habitats,
    page_paisatge,
    page_pressio,
    page_aigua,
    page_boscos,
    page_historia,
    page_tranquillitat,
    page_clima,
    page_coneixement,
    page_recomanacions,
    page_prioritats_core,
    page_pla_prioritats,
]


def build_pdf(context: dict[str, Any], maps: dict[str, Path]) -> None:
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(MODULES_V2_PDF), pagesize=PAGE)
    c.setTitle("EcoRadar 2.0 - Atles de diagnosi ecològica Alinyà")
    c.setAuthor("EcoRadar")
    for fn in PAGES:
        c.setFillColor(SAND)
        c.rect(0, 0, PAGE[0], PAGE[1], fill=1, stroke=0)
        fn(c, context, maps)
        c.showPage()
    c.save()

    writer = PdfWriter()
    reader = PdfReader(str(MODULES_V2_PDF))
    for page in reader.pages:
        writer.add_page(page)
    with ATLAS_V2_PDF.open("wb") as handle:
        writer.write(handle)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy2(ATLAS_V2_PDF, OUTPUT_V2_PDF)


def write_metadata(context: dict[str, Any], maps: dict[str, Path]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project": "Alinyà",
        "version": "2.0",
        "format": "A3 landscape",
        "outputs": {
            "atlas_pdf": str(ATLAS_V2_PDF.relative_to(ROOT)),
            "modules_pdf": str(MODULES_V2_PDF.relative_to(ROOT)),
            "output_copy": str(OUTPUT_V2_PDF.relative_to(ROOT)),
        },
        "page_count": len(PAGES),
        "new_pages": ["Radiografia ecològica", "Pla de prioritats"],
        "design_principles": [
            "Each page answers one management question.",
            "Pages use different narrative structures where data allow it.",
            "No synthetic data are generated.",
            "Unavailable inputs are labelled and translated into management implications.",
        ],
        "maps": {key: str(path.relative_to(ROOT)) for key, path in maps.items()},
    }
    METADATA_V2.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    context = a3.build_context()
    maps = export_ecoradar_product.render_maps()
    build_pdf(context, maps)
    write_metadata(context, maps)


if __name__ == "__main__":
    main()
