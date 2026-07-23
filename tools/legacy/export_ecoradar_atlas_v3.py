"""Generate EcoRadar 3.0 A3 decision atlas for Alinya.

EcoRadar 3.0 is not a longer report. It is a decision-oriented ecological
diagnosis: every page must help a manager decide what to conserve, validate,
monitor, restore, or postpone until better evidence exists.

This exporter uses only prepared real data. It never runs connectors and never
creates substitute values for missing sources.
"""

from __future__ import annotations

import json
import shutil
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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
from tools import export_ecoradar_atlas_v2 as v2
from tools import export_ecoradar_product


PROJECT = ROOT / "projectes" / "Alinya"
REPORTS = PROJECT / "reports"
MODULES_DIR = REPORTS / "modules"
OUTPUT = ROOT / "output" / "pdf"
METADATA = PROJECT / "metadata"

ATLAS_V3_PDF = REPORTS / "atlas_diagnosi_ecoradar_alinya_v3_a3.pdf"
MODULES_V3_PDF = MODULES_DIR / "moduls_diagnosi_ecoradar_alinya_v3_a3.pdf"
OUTPUT_V3_PDF = OUTPUT / "atlas_diagnosi_ecoradar_alinya_v3_a3.pdf"
METADATA_V3 = METADATA / "ecoradar_atlas_v3_metadata.json"

PAGE = landscape(A3)
TOTAL_PAGES = 16
NO_DATA = "No disponible"

GREEN_DARK = colors.HexColor("#0A392F")
GREEN = colors.HexColor("#1D604C")
GREEN_2 = colors.HexColor("#5B9066")
GREEN_PALE = colors.HexColor("#DDEBDD")
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


BODY = style("v3_body", 8.5, 10.6)
SMALL = style("v3_small", 7.0, 8.5, MUTED)
TINY = style("v3_tiny", 6.2, 7.5, MUTED)
H2 = style("v3_h2", 10.8, 12.8, GREEN_DARK, True)
WHITE = style("v3_white", 8.2, 9.8, colors.white)
WHITE_H = style("v3_white_h", 11.0, 13.0, colors.white, True)


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


def pressure(context: dict[str, Any], key: str) -> str:
    return a3.pressure_value(context["pressure"], key)


def core(context: dict[str, Any], code: str, key: str = "normalized_value") -> str:
    return a3.core_value(context["core"], code, key)


def draw_footer_v3(c: canvas.Canvas, page_no: int, title: str) -> None:
    w, _ = PAGE
    c.setFillColor(GREEN_DARK)
    c.rect(0, 0, w, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7.1)
    c.drawString(12 * mm, 2.9 * mm, "ECORADAR 3.0 - Quadre de comandament ecològic - Alinyà")
    c.drawCentredString(w / 2, 2.9 * mm, title)
    c.drawRightString(w - 12 * mm, 2.9 * mm, f"{page_no}/{TOTAL_PAGES}")


def traffic_color(value: float | None):
    if value is None:
        return GRAY
    if value >= 70:
        return GREEN_2
    if value >= 45:
        return ORANGE
    return RED


def draw_table(c: canvas.Canvas, rows: list[list[str]], x: float, y_top: float, widths: list[float]) -> float:
    data = []
    for i, row in enumerate(rows):
        st = style("v3_th", 7.0, 8.4, colors.white, True) if i == 0 else style("v3_td", 6.9, 8.3)
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


def draw_map(c: canvas.Canvas, maps: dict[str, Path], key: str, x: float, y: float, w: float, h: float, title: str, subtitle: str = "") -> None:
    card(c, x, y, w, h)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 9.6)
    c.drawString(x + 6 * mm, y + h - 8 * mm, title)
    if subtitle:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.6)
        c.drawString(x + 6 * mm, y + h - 13 * mm, subtitle)
    path = maps.get(key) or maps["base"]
    c.drawImage(str(path), x + 5 * mm, y + 5 * mm, width=w - 10 * mm, height=h - 22 * mm, preserveAspectRatio=True, anchor="c")


def available_core_values(context: dict[str, Any]) -> list[float]:
    values = []
    for row in context["core"]:
        value = as_num(row.get("normalized_value"))
        if value is not None:
            values.append(value)
    return values


def global_index(context: dict[str, Any]) -> float | None:
    values = available_core_values(context)
    return round(statistics.mean(values), 1) if values else None


def page_decision_dashboard(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    w, h = PAGE
    v2.draw_header(c, 1, "Radiografia ecològica global", "Si només tens cinc minuts, què has de saber d'Alinyà?", "Baix", "Parcial")
    margin = 12 * mm
    top = h - 45 * mm
    gi = global_index(context)

    card(c, margin, top - 78 * mm, 74 * mm, 78 * mm, fill=GREEN_DARK)
    p(c, "Índex de lectura", margin + 7 * mm, top - 8 * mm, 58 * mm, WHITE_H)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(margin + 37 * mm, top - 36 * mm, fmt(gi, 1) if gi is not None else NO_DATA)
    c.setFont("Helvetica", 9.5)
    c.drawCentredString(margin + 37 * mm, top - 46 * mm, "preliminar - no és nota global")
    p(c, "Lectura integrada dels senyals disponibles. Serveix per orientar decisions prudents, no per certificar estat de conservació.", margin + 7 * mm, top - 58 * mm, 58 * mm, WHITE)

    draw_map(
        c,
        maps,
        "espai",
        margin + 82 * mm,
        top - 128 * mm,
        178 * mm,
        128 * mm,
        "Mapa de comandament ecològic",
        "Cobertes, accessibilitat i punts d'ús públic disponibles",
    )

    x = margin + 266 * mm
    card(c, x, top - 128 * mm, 70 * mm, 128 * mm)
    p(c, "Decisions immediates", x + 5 * mm, top - 7 * mm, 54 * mm, H2)
    decisions = [
        ("Conservar", "HIC i hàbitats prioritaris com a primera capa de prudència."),
        ("Validar", "Espais oberts, accessos i buits de biodiversitat abans de regular."),
        ("No concloure", "Refugis, aigua, història ecològica i ús real sense evidència."),
        ("Monitoritzar", "Pressió potencial i grups taxonòmics poc representats."),
    ]
    yy = top - 23 * mm
    for label, text in decisions:
        c.setFillColor(GREEN_2 if label == "Conservar" else ORANGE if label == "Validar" else GRAY if label == "No concloure" else BLUE)
        c.roundRect(x + 5 * mm, yy - 2 * mm, 24 * mm, 7 * mm, 3.5, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 6.7)
        c.drawCentredString(x + 17 * mm, yy + 0.5 * mm, label)
        p(c, text, x + 33 * mm, yy + 4 * mm, 30 * mm, TINY)
        yy -= 25 * mm

    y2 = 25 * mm
    rows = [
        ["Senyals interpretables", "Incerteses que limiten decisions", "Resposta de gestió"],
        ["Hàbitats d'interès extensos i biodiversitat pública elevada.", "Sense aigua, foc, clima, relleu ni intensitat real d'ús públic.", "Conservar amb prudència i convertir els buits en camp dirigit."],
        ["Matriu natural dominant i espais oberts rellevants.", "Continuïtat forestal i pressió potencial encara parcialment caracteritzades.", "No sobreactuar: prioritzar decisions reversibles i verificables."],
    ]
    draw_table(c, rows, margin, y2 + 48 * mm, [90 * mm, 115 * mm, 120 * mm])
    draw_footer_v3(c, 1, "Radiografia ecològica global")


def page_comparison(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    _, h = PAGE
    v2.draw_header(c, 15, "Comparació i valors de referència", "Alinyà és alt, baix o singular respecte altres espais?", "Baix", "No disponible")
    margin = 12 * mm
    top = h - 45 * mm

    rows = [
        ["Indicador", "Valor Alinyà", "Referència EcoRadar", "Mitjana regional", "Lectura"],
        ["Coberta forestal", fmt(metric(context, "percentatge_coberta_forestal"), 1, "%"), NO_DATA, NO_DATA, "Context necessari per saber si el mosaic és excepcional o habitual."],
        ["Hàbitats detectats", fmt(metric(context, "nombre_habitats"), 0), NO_DATA, NO_DATA, "El valor absolut és informatiu, però necessita comparació territorial."],
        ["HIC", fmt(metric(context, "superficie_hic"), 0) + " ha", NO_DATA, NO_DATA, "Cal normalitzar per superfície i regió biogeogràfica."],
        ["Espècies citades", fmt(metric(context, "nombre_especies_registrades"), 0), NO_DATA, NO_DATA, "Depèn molt de l'esforç d'observació."],
        ["Densitat de camins", fmt(pressure(context, "osm_path_track_road_density"), 2), NO_DATA, NO_DATA, "Cal comparar amb espais similars i intensitat real."],
    ]
    draw_table(c, rows, margin, top, [44 * mm, 35 * mm, 45 * mm, 42 * mm, 150 * mm])

    mid_y = 94 * mm
    cards = [
        ("Banc EcoRadar", "Comparar amb altres espais processats amb la mateixa metodologia."),
        ("Context regional", "Normalitzar per regió biogeogràfica, superfície i tipologia d'espai."),
        ("Percentils", "Mostrar si Alinyà està per sobre o per sota d'espais similars."),
        ("Decisió", "Saber si una pressió o valor és excepcional i requereix prioritat."),
    ]
    for i, (title, text) in enumerate(cards):
        xx = margin + i * 82 * mm
        fill = GREEN_PALE if i in (0, 3) else CREAM
        card(c, xx, mid_y, 76 * mm, 42 * mm, fill=fill)
        p(c, title, xx + 5 * mm, mid_y + 31 * mm, 62 * mm, H2)
        p(c, text, xx + 5 * mm, mid_y + 18 * mm, 62 * mm, SMALL)

    card(c, margin, 30 * mm, 100 * mm, 50 * mm, fill=colors.HexColor("#FFF5E8"))
    p(c, "Per què encara no comparem?", margin + 6 * mm, 79 * mm, 80 * mm, H2)
    p(c, "No hi ha encara una base multi-espai EcoRadar ni valors regionals normalitzats incorporats. Mostrar comparació ara seria menys rigorós que indicar la manca.", margin + 6 * mm, 63 * mm, 82 * mm, BODY)

    card(c, margin + 108 * mm, 30 * mm, 110 * mm, 50 * mm, fill=GREEN_PALE)
    p(c, "Com s'ha d'implementar", margin + 114 * mm, 79 * mm, 90 * mm, H2)
    p(c, "Crear un banc de referència per regió, superfície i tipologia d'espai. Comparar percentils, no només valors bruts.", margin + 114 * mm, 63 * mm, 90 * mm, BODY)

    card(c, margin + 226 * mm, 30 * mm, 110 * mm, 50 * mm, fill=GREEN_DARK)
    p(c, "Valor per al gestor", margin + 232 * mm, 79 * mm, 90 * mm, WHITE_H)
    p(c, "La comparació permet saber si una pressió és excepcional, si un valor és singular i si una actuació és prioritària dins una xarxa d'espais.", margin + 232 * mm, 63 * mm, 88 * mm, WHITE)
    draw_footer_v3(c, 15, "Comparació i referències")


def page_roadmap(c: canvas.Canvas, context: dict[str, Any], maps: dict[str, Path]) -> None:
    _, h = PAGE
    v2.draw_header(c, 16, "Full de ruta", "Quina seqüència d'actuacions converteix la diagnosi en gestió?", "Mitjà", "Parcial")
    margin = 12 * mm
    top = h - 45 * mm

    phases = [
        (
            "Curt termini",
            "0-6 mesos",
            [
                "Validar hàbitats sensibles i espais oberts.",
                "Revisar accessos, aparcaments i punts d'ús públic.",
                "Definir camp dirigit als buits de biodiversitat.",
            ],
            "Decidir què conservar i què no tocar.",
        ),
        (
            "Mitjà termini",
            "6-18 mesos",
            [
                "Incorporar hidrologia, DEM, pendent i orientació.",
                "Activar teledetecció NDVI, NDMI, NDWI i LST.",
                "Mesurar ús públic real amb fonts autoritzades.",
            ],
            "Passar de diagnosi preliminar a zonificació operativa.",
        ),
        (
            "Llarg termini",
            "18-36 mesos",
            [
                "Construir banc comparatiu EcoRadar.",
                "Afegir història ecològica i recurrència d'incendis.",
                "Monitoritzar efectes de les actuacions.",
            ],
            "Prioritzar inversions i avaluar resultats.",
        ),
    ]

    col_w = 104 * mm
    for i, (title, period, actions, unlock) in enumerate(phases):
        x = margin + i * (col_w + 8 * mm)
        card(c, x, top - 138 * mm, col_w, 138 * mm, fill=CREAM if i != 1 else GREEN_PALE)
        c.setFillColor(GREEN_DARK)
        c.roundRect(x + 5 * mm, top - 20 * mm, 36 * mm, 8 * mm, 4, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(x + 23 * mm, top - 17.3 * mm, period)
        p(c, title, x + 5 * mm, top - 32 * mm, col_w - 10 * mm, H2)
        yy = top - 50 * mm
        for action in actions:
            c.setFillColor(GREEN_2)
            c.circle(x + 8 * mm, yy - 2 * mm, 1.8 * mm, fill=1, stroke=0)
            used = p(c, action, x + 12 * mm, yy + 1.5 * mm, col_w - 20 * mm, BODY)
            yy -= used + 7 * mm
        card(c, x + 5 * mm, top - 128 * mm, col_w - 10 * mm, 25 * mm, fill=GREEN_DARK)
        p(c, "Decisió que desbloqueja", x + 10 * mm, top - 111 * mm, col_w - 20 * mm, WHITE_H)
        p(c, unlock, x + 10 * mm, top - 121 * mm, col_w - 20 * mm, WHITE)

    card(c, margin, 24 * mm, 328 * mm, 34 * mm, fill=colors.HexColor("#FFF5E8"))
    p(c, "Principi de qualitat", margin + 7 * mm, 50 * mm, 70 * mm, H2)
    p(c, "EcoRadar 3.0 ha de millorar per incorporació de dades reals, no per embellir buits. Cada nova font només entra quan està verificada i documentada.", margin + 82 * mm, 49 * mm, 230 * mm, BODY)
    draw_footer_v3(c, 16, "Full de ruta")


V2_PAGES: list[Callable[[canvas.Canvas, dict[str, Any], dict[str, Path]], None]] = [
    v2.page_biodiversitat,
    v2.page_habitats,
    v2.page_paisatge,
    v2.page_pressio,
    v2.page_aigua,
    v2.page_boscos,
    v2.page_historia,
    v2.page_tranquillitat,
    v2.page_clima,
    v2.page_coneixement,
    v2.page_recomanacions,
    v2.page_prioritats_core,
    v2.page_pla_prioritats,
]


def build_pdf(context: dict[str, Any], maps: dict[str, Path]) -> None:
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    original_footer = v2.draw_footer
    v2.draw_footer = draw_footer_v3
    try:
        c = canvas.Canvas(str(MODULES_V3_PDF), pagesize=PAGE)
        c.setTitle("EcoRadar 3.0 - Diagnosi ecològica visual Alinyà")
        c.setAuthor("EcoRadar")
        for fn in [page_decision_dashboard, *V2_PAGES, page_comparison, page_roadmap]:
            c.setFillColor(SAND)
            c.rect(0, 0, PAGE[0], PAGE[1], fill=1, stroke=0)
            fn(c, context, maps)
            c.showPage()
        c.save()
    finally:
        v2.draw_footer = original_footer

    writer = PdfWriter()
    reader = PdfReader(str(MODULES_V3_PDF))
    for page in reader.pages:
        writer.add_page(page)
    with ATLAS_V3_PDF.open("wb") as handle:
        writer.write(handle)
    shutil.copy2(ATLAS_V3_PDF, OUTPUT_V3_PDF)


def write_metadata(context: dict[str, Any], maps: dict[str, Path]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project": "Alinyà",
        "version": "3.0",
        "format": "A3 landscape",
        "outputs": {
            "atlas_pdf": str(ATLAS_V3_PDF.relative_to(ROOT)),
            "modules_pdf": str(MODULES_V3_PDF.relative_to(ROOT)),
            "output_copy": str(OUTPUT_V3_PDF.relative_to(ROOT)),
        },
        "page_count": TOTAL_PAGES,
        "required_sections": [
            "Radiografia ecològica global",
            "Mòduls de diagnosi",
            "Comparació i valors de referència",
            "Prioritats de gestió",
            "Pla d'acció",
            "Full de ruta",
        ],
        "quality_gate": [
            "Every page answers one management question.",
            "No synthetic values are generated.",
            "Unavailable inputs state why decisions are blocked.",
            "Recommendations are tied to available evidence or explicit data gaps.",
        ],
        "maps": {key: str(path.relative_to(ROOT)) for key, path in maps.items()},
    }
    METADATA_V3.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    context = a3.build_context()
    maps = export_ecoradar_product.render_maps()
    build_pdf(context, maps)
    write_metadata(context, maps)


if __name__ == "__main__":
    main()
