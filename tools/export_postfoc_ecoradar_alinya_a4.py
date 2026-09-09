"""Export a post-fire EcoRadar A4 sheet for Alinya.

This is an editorial/reporting artifact built from already processed EcoRadar
outputs. It does not implement connectors, download data, or run ecological
analysis.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from textwrap import shorten

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes/Alinya"
OUT = PROJECT / "reports/fitxa_postfoc_ecoradar_alinya_a4.pdf"

PAGE_W, PAGE_H = A4
M = 18 * mm

DARK = colors.HexColor("#0b3f2a")
GREEN = colors.HexColor("#3f8a55")
MID_GREEN = colors.HexColor("#7da453")
LIGHT_GREEN = colors.HexColor("#eaf3ec")
ORANGE = colors.HexColor("#f49a23")
RED = colors.HexColor("#cf3f32")
YELLOW = colors.HexColor("#efc84a")
INK = colors.HexColor("#24352f")
MUTED = colors.HexColor("#65736b")
LINE = colors.HexColor("#d7d1c3")
PAPER = colors.HexColor("#f7f5ee")
WHITE = colors.white


STYLE = ParagraphStyle(
    "body",
    fontName="Helvetica",
    fontSize=7.7,
    leading=9.4,
    textColor=INK,
    spaceAfter=0,
)
STYLE_SMALL = ParagraphStyle(
    "small",
    fontName="Helvetica",
    fontSize=6.6,
    leading=8.0,
    textColor=MUTED,
    spaceAfter=0,
)
STYLE_HEAD = ParagraphStyle(
    "head",
    fontName="Helvetica-Bold",
    fontSize=8.2,
    leading=9.6,
    textColor=DARK,
    spaceAfter=0,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def num(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, "", "NO DISPONIBLE"):
            return default
        return float(str(value).replace(",", "."))
    except ValueError:
        return default


def fmt(value: float, decimals: int = 1) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def metric_from(rows: list[dict[str, str]], code_or_name: str, field: str = "value_0_100") -> float:
    for row in rows:
        if row.get("code") == code_or_name or row.get("name") == code_or_name or row.get("indicator") == code_or_name:
            return num(row.get(field) or row.get("value"))
    return 0.0


def card(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str | None = None) -> None:
    c.setFillColor(WHITE)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    if title:
        label_w = min(w - 14, max(74, c.stringWidth(title, "Helvetica-Bold", 9.5) + 22))
        c.setFillColor(DARK)
        c.setStrokeColor(DARK)
        c.roundRect(x, y + h - 22, label_w, 22, 4, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(x + 9, y + h - 15.2, title)


def safe_card(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str) -> tuple[float, float, float, float]:
    """Draw a card whose title stays inside the card.

    Returns the inner content rectangle: x, y, w, h.
    """

    c.setFillColor(WHITE)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    title_h = 20
    c.setFillColor(DARK)
    c.roundRect(x, y + h - title_h, w, title_h, 5, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 8.8)
    c.drawString(x + 10, y + h - 13.5, title)
    pad = 12
    return x + pad, y + pad, w - 2 * pad, h - title_h - pad - 8


def para(c: canvas.Canvas, text: str, x: float, y_top: float, w: float, style=STYLE) -> float:
    p = Paragraph(text, style)
    _, h = p.wrap(w, 500)
    p.drawOn(c, x, y_top - h)
    return y_top - h


def bounded_para(c: canvas.Canvas, text: str, x: float, y_top: float, w: float, max_h: float, style=STYLE) -> float:
    """Draw paragraph only if it fits; shrink once if needed."""

    p = Paragraph(text, style)
    _, h = p.wrap(w, max_h)
    if h > max_h:
        smaller = ParagraphStyle(
            f"{style.name}_small_fit",
            parent=style,
            fontSize=max(5.8, style.fontSize - 0.8),
            leading=max(7.0, style.leading - 1.0),
        )
        p = Paragraph(text, smaller)
        _, h = p.wrap(w, max_h)
    p.drawOn(c, x, y_top - h)
    return y_top - h


def img(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(str(path), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, preserveAspectRatio=True, mask="auto")


def img_crop(c: canvas.Canvas, path: Path, box: tuple[int, int, int, int], x: float, y: float, w: float, h: float) -> None:
    with Image.open(path) as im:
        cropped = im.crop(box)
        iw, ih = cropped.size
        scale = min(w / iw, h / ih)
        dw, dh = iw * scale, ih * scale
        c.drawImage(ImageReader(cropped), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, preserveAspectRatio=True, mask="auto")


def pill(c: canvas.Canvas, x: float, y: float, w: float, text: str, fill) -> None:
    c.setFillColor(fill)
    c.roundRect(x, y, w, 13, 5, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 6.7)
    c.drawCentredString(x + w / 2, y + 4, text)


def bar(c: canvas.Canvas, x: float, y: float, w: float, label: str, value: float, fill=GREEN) -> None:
    label_w = min(58, max(32, w * 0.48))
    value_w = 18
    track_w = max(18, w - label_w - value_w - 6)
    c.setFillColor(INK)
    c.setFont("Helvetica", 6.8)
    c.drawString(x, y + 3, label)
    c.setFillColor(colors.HexColor("#dfe9e2"))
    c.roundRect(x + label_w, y, track_w, 8, 3, stroke=0, fill=1)
    c.setFillColor(fill)
    c.roundRect(x + label_w, y, max(2, track_w * max(0, min(100, value)) / 100), 8, 3, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica", 6.7)
    c.drawRightString(x + w, y + 1.5, f"{value:.0f}")


def mini_radar(c: canvas.Canvas, x: float, y: float, r: float, values: list[tuple[str, float]]) -> None:
    import math

    n = len(values)
    cx, cy = x + r, y + r
    c.setStrokeColor(colors.HexColor("#d8e4dc"))
    c.setLineWidth(0.6)
    for frac in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n):
            a = math.pi / 2 - 2 * math.pi * i / n
            pts.append((cx + r * frac * math.cos(a), cy + r * frac * math.sin(a)))
        c.line(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1])
        for p1, p2 in zip(pts, pts[1:]):
            c.line(p1[0], p1[1], p2[0], p2[1])
    pts = []
    for i, (_, value) in enumerate(values):
        a = math.pi / 2 - 2 * math.pi * i / n
        rr = r * max(0, min(100, value)) / 100
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    c.setFillColor(colors.Color(0.25, 0.55, 0.34, alpha=0.28))
    c.setStrokeColor(DARK)
    c.setLineWidth(1)
    path = c.beginPath()
    path.moveTo(*pts[0])
    for px, py in pts[1:]:
        path.lineTo(px, py)
    path.close()
    c.drawPath(path, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica", 5.7)
    for i, (label, value) in enumerate(values):
        a = math.pi / 2 - 2 * math.pi * i / n
        lx = cx + (r + 16) * math.cos(a)
        ly = cy + (r + 12) * math.sin(a)
        c.drawCentredString(lx, ly, label)
        c.drawCentredString(lx, ly - 6, f"{value:.0f}")


def source_data() -> dict:
    core = read_csv(PROJECT / "indicators/ecoradar_core_indicators.csv")
    core_payload = read_json(PROJECT / "indicators/ecoradar_core_indicators.json")
    cobertes = read_csv(PROJECT / "indicators/cobertes_sol_resum.csv")
    biodiversitat = read_csv(PROJECT / "indicators/biodiversitat_resum.csv")
    hidro = read_csv(PROJECT / "indicators/hidrologia_resum.csv")
    rec = read_csv(PROJECT / "indicators/recreational_pressure_resum.csv")
    con = read_csv(PROJECT / "indicators/connectivitat_resum.csv")
    inc = read_csv(PROJECT / "indicators/incendis_resum.csv")
    sim = read_csv(PROJECT / "indicators/incendis_similarity/similitud_condicions_resum.csv")
    study = read_json(PROJECT / "metadata/study_area_metadata.json")

    biodiv_records = sum(int(num(r["nombre_registres"])) for r in biodiversitat)
    biodiv_species = sum(int(num(r["nombre_especies"])) for r in biodiversitat)
    hic_area = sum(num(r["superficie_ha"]) for r in read_csv(PROJECT / "indicators/habitats_resum.csv") if r.get("es_hic") == "True")
    hic_prior = sum(num(r["superficie_ha"]) for r in read_csv(PROJECT / "indicators/habitats_resum.csv") if r.get("es_prioritari") == "True")
    forest = sum(num(r["superficie_ha"]) for r in cobertes if "Bosc" in r["tipus_coberta"])
    prats = sum(num(r["superficie_ha"]) for r in cobertes if "Prats" in r["tipus_coberta"])
    matollar = sum(num(r["superficie_ha"]) for r in cobertes if "Matollar" in r["tipus_coberta"])
    conreus = sum(num(r["superficie_ha"]) for r in cobertes if "Conreus" in r["tipus_coberta"])

    def core_metric(code: str) -> float:
        return metric_from(core, code)

    core_results = {row["code"]: row.get("primary_result") or "NO AVALUABLE" for row in core}

    inc_dict = {r["metric"]: num(r["value"]) for r in inc}
    sim_dict = {r["metric"]: num(r["value"]) for r in sim}
    rec_dict = {r["indicator"]: num(r["value"]) for r in rec}
    con_main = next((r for r in con if r["layer_id"] == "connectors_terrestres_principals"), None)
    fonts = next((r for r in hidro if r["layer_id"] == "fonts"), None)
    rius = next((r for r in hidro if r["layer_id"] == "rius_aca_che"), None)

    return {
        "phase2": core_payload.get("methodology_version") == "alinya_core_v2_2026-09-09",
        "methodology_version": core_payload.get("methodology_version"),
        "snapshot_id": core_payload.get("snapshot_id"),
        "core_results": core_results,
        "study_ha": num(study["surface_ha"]),
        "forest_ha": forest,
        "forest_pct": forest / num(study["surface_ha"]) * 100,
        "prats_ha": prats,
        "matollar_ha": matollar,
        "conreus_ha": conreus,
        "hic_ha": hic_area,
        "hic_prior_ha": hic_prior,
        "biodiv_records": biodiv_records,
        "biodiv_species": biodiv_species,
        "core": {
            "mosaic": core_metric("CORE_01"),
            "habitats": core_metric("CORE_02"),
            "biodiv": core_metric("CORE_06"),
            "pressio": core_metric("CORE_07"),
            "connect": core_metric("CORE_08"),
            "fire": core_metric("CORE_09"),
            "aigua": core_metric("CORE_10"),
            "restauracio": core_metric("CORE_11"),
            "gestio": core_metric("CORE_12"),
            "refugis": core_metric("CORE_04"),
            "vuln": core_metric("CORE_05"),
        },
        "fire_polygons": int(inc_dict.get("gencat_fire_polygons", 0)),
        "burned_ha": inc_dict.get("gencat_burned_area_ha", 0),
        "burned_pct": inc_dict.get("gencat_burned_area_ha", 0) / num(study["surface_ha"]) * 100,
        "sim": sim_dict,
        "sim_high_ha": sim_dict.get("area_ha_alta", 0) + sim_dict.get("area_ha_mitjana_alta", 0),
        "sim_mid_ha": sim_dict.get("area_ha_mitjana", 0),
        "sim_low_ha": sim_dict.get("area_ha_baixa", 0),
        "paths_km": rec_dict.get("osm_path_track_road_km", 0),
        "public_points": int(rec_dict.get("osm_recreational_point_features", 0)),
        "connectors_ha": num(con_main["area_ha"]) if con_main else 0,
        "fonts": int(num(fonts["feature_count"])) if fonts else 0,
        "rius_km": num(rius["length_km"]) if rius else 0,
    }


def page_header(c: canvas.Canvas, title: str, subtitle: str, page_no: str, message: str) -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(DARK)
    c.roundRect(M, PAGE_H - M - 56, PAGE_W - 2 * M, 56, 6, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#e4efe8"))
    c.circle(M + 31, PAGE_H - M - 28, 23, stroke=0, fill=1)
    c.setFillColor(DARK)
    c.setFont("Helvetica", 22)
    c.drawCentredString(M + 31, PAGE_H - M - 36, page_no)
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 18)
    c.drawString(M + 68, PAGE_H - M - 24, title)
    c.setFont("Helvetica", 10.5)
    c.drawString(M + 68, PAGE_H - M - 43, subtitle)
    c.setFillColor(colors.HexColor("#eef3ee"))
    c.roundRect(PAGE_W - M - 203, PAGE_H - M - 47, 194, 33, 4, stroke=0, fill=1)
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(PAGE_W - M - 194, PAGE_H - M - 26, "MISSATGE CLAU")
    para(c, message, PAGE_W - M - 194, PAGE_H - M - 31, 176, STYLE_SMALL)


def build_pdf(
    output: Path = OUT,
    page_numbers: tuple[str, str, str, str, str] = ("07", "08", "09", "10", "11"),
) -> None:
    d = source_data()
    if not d["phase2"]:
        raise RuntimeError(
            "L'exportador d'Alinyà requereix una instantània Fase 2 vàlida; "
            "s'ha bloquejat l'exportació amb la metodologia CORE 0–100 antiga."
        )
    # The former post-fire layout relied on a common CORE 0–100 radar and
    # prescriptive restoration text. Publish the canonical non-compensatory
    # report contract at this compatibility path.
    from ecoradar.reporting import client_report_a4 as phase2_report

    phase2_report.configure_project(PROJECT)
    phase2_report.build_report(output, phase2_report.prepare_inputs(), include_all_pages=True)
    return
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=A4)
    c.setTitle("EcoRadar - Memoria del foc ampliada - Alinya")

    usable_w = PAGE_W - 2 * M
    gap = 12
    col_w = (usable_w - gap) / 2

    def footer(text: str) -> None:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.2)
        c.drawString(M, 16, shorten(text, width=155, placeholder="..."))

    def metric(x: float, y: float, value: str, label: str, color=DARK, size: float = 17) -> None:
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", size)
        c.drawString(x, y, value)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.4)
        c.drawString(x, y - 10, label)

    def small_row(x: float, y: float, label: str, text: str, color=GREEN) -> None:
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x, y, label)
        c.setFillColor(INK)
        c.setFont("Helvetica", 7)
        c.drawString(x + 82, y, shorten(text, width=76, placeholder="..."))

    def legend_item(x: float, y: float, color, label: str) -> None:
        c.setFillColor(color)
        c.roundRect(x, y - 1, 9, 9, 1.5, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 7.2)
        c.drawString(x + 14, y + 1, label)

    radar_values = [
        ("Hab.", d["core"]["habitats"]),
        ("Biod.", d["core"]["biodiv"]),
        ("Conn.", d["core"]["connect"]),
        ("Mos.", d["core"]["mosaic"]),
        ("Foc", d["core"]["fire"]),
        ("Aigua", d["core"]["aigua"]),
        ("Press.", d["core"]["pressio"]),
        ("Rest.", d["core"]["restauracio"]),
    ]

    # Page 1: diagnosis and official fire perimeters.
    page_header(
        c,
        "MEMÒRIA DEL FOC",
        "Alinyà - diagnosi postfoc",
        page_numbers[0],
        "Focs petits i patró local: validar combustible i mantenir discontinuïtats abans d'actuar.",
    )
    y = PAGE_H - M - 82
    ix, iy, iw, ih = safe_card(c, M, y - 76, usable_w, 76, "DIAGNOSI ECOLÒGICA")
    bounded_para(
        c,
        "Els perímetres oficials postfoc són reduïts, però el senyal rellevant és territorial: massa forestal dominant, contacte bosc-matollar, accessos i discontinuïtats del mosaic. La decisió no és restaurar més, sinó validar combustible i actuar selectivament on el patró es repeteix.",
        ix,
        iy + ih,
        iw,
        ih,
    )

    y = y - 88
    ix, iy, iw, ih = safe_card(c, M, y - 414, usable_w, 414, "PERÍMETRES OFICIALS I CONTEXT TERRITORIAL")
    img_crop(c, PROJECT / "maps/incendis/mapa_incendis_context_alinya.svg.png", (40, 120, 930, 850), ix, iy + 68, iw, ih - 76)
    c.setFillColor(colors.HexColor("#f4f1e8"))
    c.roundRect(ix, iy + 28, iw, 28, 4, stroke=0, fill=1)
    legend_item(ix + 10, iy + 39, colors.HexColor("#4f7f5a"), "Bosc dominant")
    legend_item(ix + 125, iy + 39, ORANGE, "Matollar")
    legend_item(ix + 218, iy + 39, colors.HexColor("#adc85b"), "Prats/herbassars")
    legend_item(ix + 348, iy + 39, RED, "Perímetres d'incendi")
    bounded_para(
        c,
        "Origen d'ignició no informat a la capa consultada. IncendisCat no s'usa com a font de dades.",
        ix,
        iy + 20,
        iw,
        14,
        STYLE_SMALL,
    )

    y = y - 426
    ix, iy, iw, ih = safe_card(c, M, y - 154, usable_w, 154, "INDICADORS, CRITERI I RADAR")
    metric(ix, iy + ih - 22, f"{fmt(d['burned_pct'], 2)} %", "àmbit afectat", ORANGE, 15)
    metric(ix + 86, iy + ih - 22, f"{fmt(d['burned_ha'], 1)} ha", "cremades", DARK, 15)
    metric(ix + 176, iy + ih - 22, f"{d['fire_polygons']}", "perímetres", RED, 15)
    rows = [
        ("Perill", d["core_results"].get("CORE_09", "NO AVALUABLE"), ORANGE),
        ("Probabilitat", "no estadística: concurrència de condicions físiques i accessos", MID_GREEN),
        ("Conseqüència", "si el mosaic es tanca, augmenta la continuïtat de combustible", ORANGE),
        ("Decisió", "camp dirigit a vores, bosc-matollar i discontinuïtats útils", GREEN),
    ]
    yy = iy + ih - 56
    for label, text, color in rows:
        small_row(ix, yy, label, text, color)
        yy -= 15
    if d["phase2"]:
        bounded_para(
            c,
            "La Fase 2 manté separats els 12 RADAR i no els dibuixa sobre una escala comuna 0–100.",
            ix + iw - 158,
            iy + 48,
            148,
            35,
            STYLE_SMALL,
        )
    else:
        mini_radar(c, ix + iw - 150, iy + 10, 50, radar_values)
    footer("Fonts: perímetres oficials d'incendi, ICGC/Generalitat, EcoRadar. Consulta: 2026-07-14.")
    c.showPage()

    # Page 2: territorial similarity and recurrence criteria.
    page_header(
        c,
        "FOC I TERRITORI",
        "Patró, concurrència i condicions",
        page_numbers[1],
        "Les zones probables no són predicció: són coincidències territorials que cal verificar sobre el terreny.",
    )
    y = PAGE_H - M - 82
    ix, iy, iw, ih = safe_card(c, M, y - 432, usable_w, 432, "CONCURRÈNCIA AMBIENTAL I ÀREES SIMILARS")
    img_crop(
        c,
        PROJECT / "maps/incendis_similarity/mapa_similitud_condicions_incendi_alinya.svg.png",
        (50, 125, 930, 865),
        ix,
        iy + 70,
        iw,
        ih - 78,
    )
    c.setFillColor(colors.HexColor("#f4f1e8"))
    c.roundRect(ix, iy + 28, iw, 30, 4, stroke=0, fill=1)
    legend_item(ix + 10, iy + 41, RED, "Alta similitud")
    legend_item(ix + 126, iy + 41, ORANGE, "Mitjana-alta")
    legend_item(ix + 245, iy + 41, YELLOW, "Mitjana")
    legend_item(ix + 338, iy + 41, colors.HexColor("#c7d7a6"), "Baixa")
    bounded_para(
        c,
        "Les àrees similars indiquen prioritat de revisió territorial; no són perímetres futurs ni probabilitat estadística.",
        ix,
        iy + 20,
        iw,
        14,
        STYLE_SMALL,
    )

    y = y - 448
    ix, iy, iw, ih = safe_card(c, M, y - 154, usable_w, 154, "LECTURA DIRECTIVA DEL RISC")
    rows = [
        ("Patró", "vores accessibles, bosc-matollar i condicions físiques semblants", GREEN),
        ("Evidència", "perímetres oficials + similitud ambiental + 124,8 km d'accessos", MID_GREEN),
        ("Perill", "local i condicionat per episodis secs; no és mapa predictiu", ORANGE),
        ("Decisió", "vigilància, discontinuïtat i verificació de combustible en camp", GREEN),
    ]
    yy = iy + ih - 16
    for label, text, color in rows:
        c.setStrokeColor(colors.HexColor("#e6e1d6"))
        c.line(ix, yy - 5, ix + iw, yy - 5)
        small_row(ix, yy, label, text, color)
        yy -= 23
    if d["phase2"]:
        bounded_para(
            c,
            "CORE_01 descriu configuració, CORE_07 accessibilitat cartografiada i CORE_09 un perfil de foc. Cap d'aquests resultats és una puntuació ecològica global.",
            ix,
            iy + 19,
            iw,
            18,
            STYLE_SMALL,
        )
    else:
        bar(c, ix, iy + 5, iw * 0.34, "Foc", d["core"]["fire"], ORANGE)
        bar(c, ix + iw * 0.38, iy + 5, iw * 0.26, "Mosaic", d["core"]["mosaic"], GREEN)
        bar(c, ix + iw * 0.68, iy + 5, iw * 0.28, "Pressió", d["core"]["pressio"], YELLOW)
    footer("Criteri: concurrència espacial i condicions físiques semblants. No s'ha generat cap connector ni anàlisi nova.")
    c.showPage()

    # Page 3: non-urban EcoRadar evidence.
    page_header(
        c,
        "ARGUMENTARI",
        "Lectura per direcció de l'espai natural",
        page_numbers[2],
        "El document diferencia evidència, interpretació i decisió per evitar conclusions no demostrades.",
    )
    y = PAGE_H - M - 82
    ix, iy, iw, ih = safe_card(c, M, y - 194, usable_w, 194, "1. QUÈ DEMOSTREN LES DADES")
    sim_high_pct = d["sim_high_ha"] / d["study_ha"] * 100 if d["study_ha"] else 0
    sim_mid_pct = d["sim_mid_ha"] / d["study_ha"] * 100 if d["study_ha"] else 0
    forest_matollar_ha = d["forest_ha"] + d["matollar_ha"]
    forest_matollar_pct = forest_matollar_ha / d["study_ha"] * 100 if d["study_ha"] else 0
    proven = (
        f"<b>Històric oficial:</b> hi ha {d['fire_polygons']} perímetres dins l'àmbit, amb "
        f"{fmt(d['burned_ha'], 1)} ha cremades ({fmt(d['burned_pct'], 2)} % de l'espai). "
        "La superfície és petita, però el fet rellevant per a direcció és que els focs apareixen en punts concrets "
        "on es poden comparar coberta, relleu, orientació i accessibilitat. Això converteix els incendis històrics "
        "en indicadors de patró territorial, no en una simple estadística de superfície.<br/>"
        f"<b>Continuïtat potencial:</b> bosc i matollar sumen {fmt(forest_matollar_ha, 0)} ha "
        f"({fmt(forest_matollar_pct, 1)} %). Els prats i herbassars ocupen {fmt(d['prats_ha'], 0)} ha "
        f"({fmt(d['prats_ha'] / d['study_ha'] * 100, 1)} %) i els conreus pràcticament no estructuren el mosaic "
        f"({fmt(d['conreus_ha'], 1)} ha). Això vol dir que les discontinuïtats útils depenen sobretot de prats, "
        "vores, gestió pastoral i manteniment selectiu.<br/>"
        f"<b>Concurrència ambiental:</b> {fmt(d['sim_high_ha'], 0)} ha ({fmt(sim_high_pct, 1)} %) queden en classe "
        f"alta o mitjana-alta de similitud amb les condicions dels incendis, {fmt(d['sim_mid_ha'], 0)} ha "
        f"({fmt(sim_mid_pct, 1)} %) en classe mitjana i {fmt(d['sim_low_ha'], 0)} ha en classe baixa. "
        "Això no és probabilitat estadística, però sí una base sòlida per decidir on mirar primer."
    )
    bounded_para(c, proven, ix, iy + ih, iw, ih, STYLE_SMALL)

    y = y - 210
    ix, iy, iw, ih = safe_card(c, M, y - 176, usable_w, 176, "2. INTERPRETACIÓ PER A GESTIÓ")
    interpretation = (
        "<b>No és un problema de superfície cremada:</b> el foc històric ocupa poc, però assenyala punts de contacte "
        "entre combustible potencial, relleu i accés. Per això la gestió ha de prioritzar punts crítics, no grans actuacions homogènies.<br/>"
        "<b>La probabilitat no està calculada:</b> la capa de similitud és un cribratge territorial. No incorpora encara meteorologia, "
        "humitat, vent, continuïtat real de combustible ni comportament esperat del foc.<br/>"
        "<b>El perill operatiu és local:</b> en un espai amb valor d'hàbitats molt alt, una actuació preventiva només és defensable "
        "si coincideixen risc estructural, accessibilitat, baixa afectació sobre HIC i retorn ecològic del mosaic.<br/>"
        "<b>Missatge per direcció:</b> la prioritat no és intervenir més superfície, sinó intervenir millor: menys àrea, més precisió, "
        "més justificació i control explícit dels efectes ecològics."
    )
    bounded_para(c, interpretation, ix, iy + ih, iw, ih, STYLE_SMALL)

    y = y - 192
    ix, iy, iw, ih = safe_card(c, M, y - 128, usable_w, 128, "3. QUÈ FALTA PER PARLAR DE RISC OFICIAL")
    limits = (
        "Per convertir aquesta lectura en risc o probabilitat d'incendi cal incorporar com a mínim: "
        "<b>combustible i estructura forestal</b> validats, <b>humitat/NDMI i estat de vegetació</b> "
        "via Copernicus, <b>temperatura/sequera</b> Meteocat/AEMET/SPEI, i <b>Pla Alfa o perill operatiu</b> "
        "quan s'usi per decisió diària. Sense això, la fitxa ha de parlar de concurrència i prioritat de camp, no de predicció. "
        "Aquest límit és important: protegeix la credibilitat tècnica del parc i evita presentar com a risc oficial allò que encara és diagnosi estructural."
    )
    bounded_para(c, limits, ix, iy + ih, iw, ih, STYLE_SMALL)

    y = y - 144
    ix, iy, iw, ih = safe_card(c, M, y - 108, usable_w, 108, "4. DECISIÓ EXECUTIVA")
    executive = (
        "<b>Decisió recomanada:</b> obrir una validació de camp postfoc focalitzada en combustible continu, "
        "vores accessibles, bosc-matollar i discontinuïtats reals. No es justifica restauració generalitzada per superfície cremada, "
        "però sí una agenda preventiva de mosaic i vigilància als sectors on la concurrència territorial és alta. La decisió ha de quedar vinculada "
        "a una llista curta de punts verificables: combustible, accessos, pendent/orientació, HIC afectables i opcions de manteniment obert."
    )
    bounded_para(c, executive, ix, iy + ih, iw, ih, STYLE)
    footer("Argumentari construït només amb indicadors EcoRadar disponibles i fonts oficials documentades.")
    c.showPage()

    # Page 4: non-urban EcoRadar evidence.
    page_header(
        c,
        "EVIDÈNCIA ECORADAR",
        "Indicadors no urbans incorporats",
        page_numbers[3],
        "S'incorporen hàbitats, biodiversitat, aigua, connectivitat i accessibilitat territorial.",
    )
    y = PAGE_H - M - 82
    cards = [
        (M, y - 190, col_w, 190, "MOSAIC I HÀBITATS", PROJECT / "maps/producte/mapa_habitats_alinya.png"),
        (M + col_w + gap, y - 190, col_w, 190, "BIODIVERSITAT CONEGUDA", PROJECT / "maps/producte/mapa_biodiversitat_alinya.png"),
        (M, y - 396, col_w, 190, "AIGUA I CONNECTIVITAT", PROJECT / "maps/producte/mapa_espai_alinya.png"),
        (M + col_w + gap, y - 396, col_w, 190, "ACCESSIBILITAT I PRESSIÓ", PROJECT / "maps/producte/mapa_pressio_humana_alinya.png"),
    ]
    for x, cy, w, h, title, path in cards:
        ix, iy, iw, ih = safe_card(c, x, cy, w, h, title)
        img(c, path, ix, iy + 52, iw, ih - 58)

    metric(M + 16, y - 164, f"{fmt(d['study_ha'], 0)} ha", "àmbit", DARK, 12)
    metric(M + 96, y - 164, f"{fmt(d['forest_pct'], 1)} %", "forestal", GREEN, 12)
    metric(M + 176, y - 164, f"{fmt(d['hic_ha'], 0)} ha", "HIC", DARK, 12)
    metric(M + col_w + gap + 16, y - 164, f"{d['biodiv_records']}", "cites públiques", DARK, 12)
    metric(M + col_w + gap + 98, y - 164, f"{d['biodiv_species']}", "taxons", GREEN, 12)
    metric(M + 16, y - 370, f"{fmt(d['connectors_ha'], 0)} ha", "connectors", DARK, 12)
    metric(M + 110, y - 370, f"{d['fonts']}", "fonts", GREEN, 12)
    metric(M + col_w + gap + 16, y - 370, f"{fmt(d['paths_km'], 1)} km", "camins i pistes", DARK, 12)
    metric(M + col_w + gap + 120, y - 370, f"{d['public_points']}", "punts ús públic", ORANGE, 12)

    ix, iy, iw, ih = safe_card(c, M, 44, usable_w, 116, "QUÈ ÉS CADA COSA I COM S'INTERPRETA")
    bounded_para(
        c,
        "<b>Mosaic i hàbitats:</b> cobertes, HIC i HIC prioritaris; serveix per saber on una actuació preventiva pot tenir cost ecològic.<br/>"
        "<b>Biodiversitat coneguda:</b> cites públiques disponibles; orienta el mostreig, però no demostra absències ni estat postfoc.<br/>"
        "<b>Aigua i connectivitat:</b> connectors, fonts i drenatge; identifica funcions ecològiques que no s'han de trencar amb actuacions de prevenció.<br/>"
        "<b>Accessibilitat i pressió:</b> camins i punts d'ús; no mesura visitants, però sí facilita ignició, vigilància, extinció i gestió selectiva.",
        ix,
        iy + ih,
        iw,
        ih,
        STYLE_SMALL,
    )
    footer("EcoRadar postfoc ampliat: s'exclouen variables pròpies d'entorns urbans.")
    c.showPage()

    # Page 4: decisions and validation.
    page_header(
        c,
        "DECISIONS",
        "Gestió, límits i validació",
        page_numbers[4],
        "Primer validar; després actuar només on evidència, hàbitat i retorn ecològic coincideixen.",
    )
    y = PAGE_H - M - 82
    ix, iy, iw, ih = safe_card(c, M, y - 214, usable_w, 214, "CONCLUSIONS DE GESTIÓ")
    x0 = ix
    widths = [108, 114, iw - 222]
    yy = iy + ih - 16
    c.setFillColor(colors.HexColor("#f0ede2"))
    c.roundRect(x0, yy - 4, iw, 18, 3, stroke=0, fill=1)
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x0 + 4, yy + 1, "Variable")
    c.drawString(x0 + widths[0] + 4, yy + 1, "Diagnosi")
    c.drawString(x0 + widths[0] + widths[1] + 4, yy + 1, "Decisió")
    yy -= 24
    conclusions = [
        ("Coberta vegetal", "Alta", "No cal restauració generalitzada.", GREEN),
        ("Mosaic agroforestal", "Funcional vulnerable", "Mantenir prats, feixes i ecotons.", MID_GREEN),
        ("Combustible", "A validar", "Comprovar continuïtat bosc-matollar.", ORANGE),
        ("Hàbitats d'interès", "Molt alts", "Evitar impactes sobre HIC.", GREEN),
        ("Aigua", "Parcial", "Verificar fonts, basses i funció hídrica.", YELLOW),
        ("Accessos", "Pressió potencial", "Ordenar camins sensibles.", YELLOW),
    ]
    for variable, diag, decision, color in conclusions:
        c.setFillColor(colors.HexColor("#f8f6ef"))
        c.roundRect(x0, yy - 4, iw, 19, 3, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica", 7)
        c.drawString(x0 + 4, yy + 1, variable)
        pill(c, x0 + widths[0] + 4, yy - 1, 86, diag[:22], color)
        c.setFillColor(INK)
        c.setFont("Helvetica", 7)
        c.drawString(x0 + widths[0] + widths[1] + 4, yy + 1, decision)
        yy -= 22

    y = y - 230
    ix, iy, iw, ih = safe_card(c, M, y - 258, usable_w, 258, "DECISIONS ARGUMENTADES")
    decisions = [
        (
            "Mantenir obert",
            "El mosaic depèn sobretot de prats, vores i gestió pastoral; els conreus són residuals i no generen discontinuïtat agrària suficient.",
            "Prioritzar pastura extensiva, recuperació de feixes i discontinuïtats on el retorn ecològic sigui alt i no comprometi HIC.",
        ),
        (
            "Trencar continuïtat",
            "Bosc i matollar sumen 4.949 ha. El foc històric és local, però el patró pot repetir-se on coincideixen accessos i bosc-matollar.",
            "Fer franges selectives només en punts de concurrència alta o mitjana-alta i amb verificació prèvia de combustible.",
        ),
        (
            "No sobreactuar",
            "La superfície oficial cremada és 17,4 ha, el 0,32 % de l'àmbit. Aquesta dada no justifica una restauració extensiva.",
            "Fer seguiment i evitar restauració generalitzada si no hi ha erosió, sòl nu, fallida de recuperació o risc sobre funcions ecològiques.",
        ),
        (
            "Restaurar clapes",
            "La restauració només és defensable quan el camp confirma sòl nu, erosió, pèrdua de funcionalitat o recuperació lenta.",
            "Actuar localment, controlar erosió i evitar actuacions que degradin hàbitats d'interès o connectors funcionals.",
        ),
    ]
    yy = iy + ih - 18
    for title, evidence, action in decisions:
        c.setFillColor(colors.HexColor("#f8f6ef"))
        c.roundRect(ix, yy - 42, iw, 44, 3, stroke=0, fill=1)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 7.4)
        c.drawString(ix + 8, yy - 10, title)
        bounded_para(c, f"<b>Evidència:</b> {evidence}<br/><b>Decisió:</b> {action}", ix + 108, yy - 1, iw - 120, 38, STYLE_SMALL)
        yy -= 52

    ix, iy, iw, ih = safe_card(c, M, 46, usable_w, 64, "LÍMIT METODOLÒGIC ÚTIL")
    bounded_para(
        c,
        "La fitxa integra dades ja disponibles d'EcoRadar i fonts oficials documentades. No substitueix verificació de camp de combustible, humitat, erosió, HIC i punts d'aigua. No s'infereix biodiversitat postfoc ni estructura forestal sense mostreig validat.",
        ix,
        iy + ih,
        iw,
        ih,
        STYLE_SMALL,
    )
    footer("Document executiu ampliat a 5 pàgines per garantir caixes, textos i figures sense solapaments.")
    c.save()


if __name__ == "__main__":
    build_pdf()
    print(OUT)
