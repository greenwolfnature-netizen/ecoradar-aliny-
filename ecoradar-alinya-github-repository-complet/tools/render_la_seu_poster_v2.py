"""Render La Seu d'Urgell urban climate poster v3 panels.

The render reads calculated metrics from output/la_seu_urban_metrics_real_v2.json
and patches the existing v1 poster. It avoids embedding untraceable numbers in
the image generation step.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IN_PATH = ROOT / "output/ecoradar_urba_la_seu_poster_panells_REAL_v1.png"
METRICS_PATH = ROOT / "output/la_seu_urban_metrics_real_v2.json"
OUT_PATH = ROOT / "output/ecoradar_urba_la_seu_poster_panells_REAL_v6.png"

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
FONT_REGULAR = FONT_DIR / "Arial.ttf"
FONT_BOLD = FONT_DIR / "Arial Bold.ttf"

BG = (242, 239, 230, 255)
CARD = (251, 250, 246, 255)
BORDER = (199, 193, 179, 255)
RULE = (205, 199, 187, 255)
NAVY = (26, 59, 103, 255)
TEXT = (45, 45, 43, 255)
MUTED = (112, 110, 104, 255)
GREEN = (8, 117, 55, 255)
SOFT_GREEN = (104, 132, 92, 255)
BLUE = (20, 134, 199, 255)
RED = (206, 43, 46, 255)
BAR_BG = (226, 220, 209, 255)


def main() -> None:
    metrics = json.loads(METRICS_PATH.read_text())
    img = Image.open(IN_PATH).convert("RGBA")
    img = remove_map_texts(img)
    draw = ImageDraw.Draw(img)

    draw_right_panel(draw, metrics)
    draw_left_status(draw, metrics)
    draw_lidar_factor(draw, metrics)

    img.save(OUT_PATH)
    print(OUT_PATH)


def draw_right_panel(draw: ImageDraw.ImageDraw, metrics: dict) -> None:
    # Clean the whole right column to remove old nested borders.
    draw.rectangle((3180, 245, 4284, 2140), fill=BG)

    x0, x1 = 3235, 4276
    routes = (x0, 265, x1, 932)
    refuges = (x0, 962, x1, 1232)
    indicator = (x0, 1266, x1, 1864)
    use = (x0, 1895, x1, 2126)

    draw_routes_card(draw, routes)
    draw_refuges_card(draw, refuges)
    draw_indicator_card(draw, indicator, metrics)
    draw_use_card(draw, use)


def draw_routes_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw_card(draw, box)
    x0, y0, x1, _ = box
    draw.text((x0 + 58, y0 + 42), "RUTES CLIMÀTIQUES RECOMANADES", font=font(30, bold=True), fill=NAVY)

    routes = [
        (
            "1",
            GREEN,
            "RUTA RIBERA DEL SEGRE",
            "4,2 km  •  50-70 min a peu",
            "Itinerari fresc seguint el riu, amb ventilació i proximitat a l'aigua. Connecta Valira, centre històric i Parc del Segre.",
        ),
        (
            "2",
            BLUE,
            "RUTA ESCOLAR FRESCA",
            "2,6 km  •  30-40 min a peu",
            "Connecta centres educatius amb zones verdes i trams de confort alt. Evita carrers més exposats a la radiació solar de tarda.",
        ),
        (
            "3",
            (104, 59, 171, 255),
            "RUTA GENT GRAN I SALUT",
            "3,1 km  •  40-55 min a peu",
            "Itinerari suau per a mobilitat quotidiana, amb places, bancs, fonts i accessos a serveis de salut i descans.",
        ),
    ]

    y = y0 + 145
    for number, color, title, meta, desc in routes:
        draw_number_badge(draw, x0 + 122, y + 18, 31, number, color)
        draw.text((x0 + 190, y - 12), title, font=font(26, bold=True), fill=color)
        draw.text((x0 + 190, y + 28), meta, font=font(21, bold=True), fill=TEXT)
        draw_wrapped(draw, desc, x0 + 190, y + 70, x1 - 58, font(18), TEXT, line_gap=2)
        y += 190


def draw_refuges_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw_card(draw, box)
    x0, y0, _, _ = box
    draw.text((x0 + 58, y0 + 38), "REFUGIS CLIMÀTICS URBANS POTENCIALS", font=font(29, bold=True), fill=NAVY)
    items = [
        ("A", "Parc del Segre"),
        ("B", "Plaça dels Oms"),
        ("C", "Jardins de la Catedral"),
        ("D", "Parc Olímpic del Segre"),
        ("E", "Biblioteca Sant Agustí"),
    ]
    y = y0 + 78
    for letter, label in items:
        draw_number_badge(draw, x0 + 112, y + 17, 17, letter, GREEN, text_size=20)
        draw.text((x0 + 160, y + 2), label, font=font(23, bold=True), fill=TEXT)
        y += 36


def draw_indicator_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], metrics: dict) -> None:
    draw_card(draw, box)

    header = font(29, bold=True)
    label_font = font(22, bold=True)
    sub_font = font(17)
    value_font = font(23, bold=True)
    value_small = font(20, bold=True)

    x0, y0, x1, _ = box
    draw.text((x0 + 58, y0 + 38), "INDICADORS CLAU (Àrea d'estudi)", font=header, fill=NAVY)
    draw.line((x0 + 58, y0 + 92, x1 - 58, y0 + 92), fill=RULE, width=4)

    landsat = metrics["landsat_lst"]
    lidar = metrics["lidar_central_core"]
    municipal = metrics["municipal_green"]
    blocked = metrics["linear_tree_cover_official"]

    rows = [
        {
            "kind": "tree",
            "color": GREEN,
            "label": "Superfície amb ombra LiDAR",
            "sub": f"{lidar['solar_datetime_local']}; nucli central {format_decimal(lidar['area_ha'])} ha",
            "value": f"{format_decimal(lidar['shade_pct'])} %",
            "fill": GREEN,
        },
        {
            "kind": "thermo",
            "color": BLUE,
            "label": "Temperatura superficial mitjana",
            "sub": "Landsat 9 ST_B10; 08/07/2026 12:35 CEST",
            "value": f"{format_decimal(landsat['lst_mean_c'])} °C",
            "fill": TEXT,
        },
        {
            "kind": "heat",
            "color": TEXT,
            "label": "Rang LST real",
            "sub": f"P10-P90; {landsat['valid_pixels']:,}".replace(",", ".") + " píxels vàlids",
            "value": f"{format_decimal(landsat['lst_p10_c'])}-{format_decimal(landsat['lst_p90_c'])} °C",
            "fill": TEXT,
        },
        {
            "kind": "tree",
            "color": SOFT_GREEN,
            "label": "Coberta de capçada LiDAR",
            "sub": "classes vegetació ICGC 4-5; graella 2 m",
            "value": f"{format_decimal(lidar['canopy_cover_pct'])} %",
            "fill": SOFT_GREEN,
        },
        {
            "kind": "dots",
            "color": GREEN,
            "label": "Arbrat municipal",
            "sub": f"{municipal['green_spaces_ha']} ha de verd urbà; {municipal['tree_species']} espècies",
            "value": f"{municipal['planted_trees_streets_and_parks']:,}".replace(",", "."),
            "fill": GREEN,
        },
        {
            "kind": "line_blocked",
            "color": RED,
            "label": "Cobertura d'arbrat lineal",
            "sub": "sense inventari georeferenciat obert",
            "value": "bloquejat" if blocked["status"] == "blocked" else blocked["status"],
            "fill": RED,
            "small": True,
        },
    ]

    row_top = y0 + 116
    row_h = 71
    for idx, row in enumerate(rows):
        y = row_top + idx * row_h
        if idx:
            draw.line((x0 + 58, y - 8, x1 - 58, y - 8), fill=RULE, width=2)
        draw_icon(draw, row["kind"], x0 + 113, y + 26, row["color"])
        draw.text((x0 + 175, y + 2), row["label"], font=label_font, fill=TEXT)
        draw.text((x0 + 175, y + 34), row["sub"], font=sub_font, fill=TEXT)
        vf = value_small if row.get("small") else value_font
        draw_right_text(draw, (x1 - 58, y + 16), row["value"], vf, row["fill"])


def draw_use_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw_card(draw, box)
    x0, y0, x1, _ = box
    draw.text((x0 + 58, y0 + 38), "COM UTILITZAR AQUEST MAPA", font=font(29, bold=True), fill=NAVY)
    body = (
        "Planifica els desplaçaments a peu en dies calorosos prioritzant les rutes "
        "amb més ombra, verd i aigua. Consulta refugis climàtics en episodis de calor."
    )
    draw_wrapped(draw, body, x0 + 58, y0 + 85, x1 - 58, font(19, bold=True), TEXT, line_gap=3)
    foot = (
        "Fonts v6: USGS Landsat C2 L2 ST, ICGC LiDAR Territorial v3.1 i Ajuntament. "
        "Àmbit mètric: 130,4 ha. Arbrat lineal: sense font geoespacial oberta."
    )
    draw_wrapped(draw, foot, x0 + 58, y0 + 160, x1 - 58, font(15), MUTED, line_gap=2)
    draw_right_text(draw, (x1 - 58, y0 + 202), "Panell v6 · valors oficials/derivats documentats · 2026", font(15), MUTED)


def draw_left_status(draw: ImageDraw.ImageDraw, metrics: dict) -> None:
    x0, y0, x1, y1 = 20, 1888, 770, 2096
    draw.rectangle((x0, y0, x1, y1), fill=CARD)
    draw.line((x0, y0, x1, y0), fill=BORDER, width=2)

    landsat = metrics["landsat_lst"]
    lidar = metrics["lidar_central_core"]
    municipal = metrics["municipal_green"]

    draw.text((42, 1920), "DADES OFICIALS V6", font=font(27, bold=True), fill=NAVY)
    entries = [
        (f"LST Landsat 9: {format_decimal(landsat['lst_mean_c'])} °C (08/07/2026)", TEXT),
        (f"Ombra LiDAR 15 h: {format_decimal(lidar['shade_pct'])} %", TEXT),
        (f"Arbrat municipal: {municipal['planted_trees_streets_and_parks']:,}".replace(",", ".") + " arbres · 80 espècies", TEXT),
        ("Arbrat lineal: bloquejat; sense inventari obert", RED),
    ]
    y = 1973
    for line, fill in entries:
        draw.text((64, y), line, font=font(18), fill=fill)
        y += 27


def draw_lidar_factor(draw: ImageDraw.ImageDraw, metrics: dict) -> None:
    value = int(round(float(metrics["lidar_central_core"]["shade_pct"])))
    label_area = (56, 1282, 245, 1334)
    bar_area = (374, 1294, 735, 1333)
    draw.rectangle(label_area, fill=CARD)
    draw.rectangle(bar_area, fill=CARD)
    draw.text((63, 1292), "Ombra LiDAR", font=font(27), fill=(0, 0, 0, 255))
    draw.rectangle((374, 1294, 673, 1329), fill=BAR_BG)
    draw.rectangle((374, 1294, 374 + int(299 * value / 100), 1329), fill=SOFT_GREEN)
    draw.text((677, 1296), str(value), font=font(25), fill=(0, 0, 0, 255))


def remove_map_texts(img: Image.Image) -> Image.Image:
    draw = ImageDraw.Draw(img)
    # Rectangles cover the visible OSM/place labels in the central map.
    # They are deliberately limited to map labels; panel text remains untouched.
    label_boxes = [
        (1868, 800, 2210, 875),   # Club Sedis Aeromodelisme
        (1800, 1105, 2415, 1258), # Llar de Sant Josep / Seminari Conciliar
        (1248, 1265, 1940, 1365), # Castell de Ciutat / Parc de la Valira
        (2200, 1218, 2680, 1330), # Camp de futbol
        (1248, 1358, 2010, 1472), # Parc del Toll del Bressol / Parc de la Boixadera
        (1780, 1390, 2530, 1558), # Passeig / Plaça / Parc del Segre
        (1840, 1535, 2290, 1650), # Institut Joan Brudieu
    ]
    for box in label_boxes:
        draw.rectangle(box, fill=CARD)
    return img


def draw_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=3, fill=CARD, outline=BORDER, width=2)


def draw_number_badge(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int,
    text: str,
    fill: tuple[int, int, int, int],
    text_size: int = 30,
) -> None:
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)
    fnt = font(text_size, bold=True)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    draw.text((cx - (bbox[2] - bbox[0]) / 2, cy - (bbox[3] - bbox[1]) / 2 - 2), text, font=fnt, fill=CARD)


def draw_right_text(draw: ImageDraw.ImageDraw, anchor: tuple[int, int], text: str, fnt: ImageFont.FreeTypeFont, fill: tuple[int, int, int, int]) -> None:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    draw.text((anchor[0] - (bbox[2] - bbox[0]), anchor[1]), text, font=fnt, fill=fill)


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    right: int,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    line_gap: int = 4,
) -> int:
    line_h = draw.textbbox((0, 0), "Ag", font=fnt)[3] + line_gap
    for line in wrap_text(draw, text, fnt, right - x):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_h
    return y


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> Iterable[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = word if not current else f"{current} {word}"
        width = draw.textbbox((0, 0), test, font=fnt)[2]
        if width <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_icon(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, color: tuple[int, int, int, int]) -> None:
    if kind == "tree":
        draw.rectangle((cx - 4, cy + 10, cx + 4, cy + 25), fill=color)
        draw.rectangle((cx - 23, cy + 24, cx + 23, cy + 30), fill=color)
        draw.ellipse((cx - 17, cy - 10, cx + 7, cy + 14), fill=color)
        draw.ellipse((cx - 2, cy - 17, cx + 20, cy + 6), fill=color)
        draw.ellipse((cx - 26, cy - 2, cx - 2, cy + 22), fill=color)
    elif kind == "thermo":
        draw.rounded_rectangle((cx - 5, cy - 21, cx + 5, cy + 15), radius=5, outline=SOFT_GREEN, width=3)
        draw.ellipse((cx - 13, cy + 5, cx + 13, cy + 31), outline=BLUE, width=4)
        draw.line((cx, cy - 12, cx, cy + 15), fill=BLUE, width=4)
        draw.ellipse((cx - 6, cy + 13, cx + 6, cy + 25), fill=BLUE)
    elif kind == "heat":
        for offset in (-14, 0, 14):
            pts = [
                (cx + offset, cy - 20),
                (cx + offset + 7, cy - 9),
                (cx + offset - 7, cy + 4),
                (cx + offset, cy + 18),
            ]
            draw.line(pts, fill=color, width=4, joint="curve")
    elif kind == "dots":
        draw.ellipse((cx - 20, cy - 17, cx - 4, cy - 1), fill=color)
        draw.ellipse((cx + 4, cy - 17, cx + 20, cy - 1), fill=color)
        draw.ellipse((cx - 9, cy + 3, cx + 9, cy + 21), fill=color)
        draw.rectangle((cx - 4, cy + 21, cx + 4, cy + 32), fill=color)
    elif kind == "line_blocked":
        draw.line((cx - 24, cy - 5, cx + 24, cy - 5), fill=color, width=5)
        draw.line((cx - 24, cy + 11, cx + 24, cy + 11), fill=color, width=5)
        draw.line((cx - 16, cy - 20, cx + 18, cy + 26), fill=color, width=4)


def format_decimal(value: float) -> str:
    return f"{float(value):.1f}".replace(".", ",")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size=size)


if __name__ == "__main__":
    main()
