"""Generate the client-grade EcoRadar A4 portrait report.

The report consumes existing EcoRadar pipeline outputs. It does not download
data, run indicators, run diagnosis/recommendations or invent unavailable
values.
"""

from __future__ import annotations

import csv
import html
import json
import math
import re
import shutil
import sqlite3
import unicodedata
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output" / "pdf"
BRANDING = ROOT / "projectes" / "LaSeu_Urba" / "assets" / "branding"
ECORADAR_LOGO = BRANDING / "ecoradar_logo.png"
GREEN_WOLF_LOGO = BRANDING / "green_wolf_nature_logo.png"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    return slug or "projecte"


def configure_project(project_root: str | Path = ROOT / "projectes" / "Alinya") -> None:
    """Configure report paths for any EcoRadar project."""
    global PROJECT, PROJECT_NAME, PROJECT_SLUG, REPORTS, INDICATORS, METADATA, MAPS
    global REPORT_PATH, FITXA_PATH, OUTPUT_REPORT_PATH, OUTPUT_FITXA_PATH

    PROJECT = Path(project_root)
    if not PROJECT.is_absolute():
        PROJECT = ROOT / PROJECT
    PROJECT_NAME = PROJECT.name
    PROJECT_SLUG = slugify(PROJECT_NAME)
    REPORTS = PROJECT / "reports"
    INDICATORS = PROJECT / "indicators"
    METADATA = PROJECT / "metadata"
    MAPS = PROJECT / "maps" / "producte"

    REPORT_PATH = REPORTS / f"informe_ecoradar_{PROJECT_SLUG}_a4_client.pdf"
    FITXA_PATH = REPORTS / f"fitxa_ecoradar_{PROJECT_SLUG}_a4.pdf"
    OUTPUT_REPORT_PATH = OUTPUT / f"informe_ecoradar_{PROJECT_SLUG}_a4_client.pdf"
    OUTPUT_FITXA_PATH = OUTPUT / f"fitxa_ecoradar_{PROJECT_SLUG}_a4.pdf"


configure_project()

GREEN_DARK = colors.HexColor("#0D3B2E")
GREEN = colors.HexColor("#1F604B")
GREEN_2 = colors.HexColor("#4E8A5A")
GREEN_PALE = colors.HexColor("#E6F0E6")
ACCENT = colors.HexColor("#C9793F")
ACCENT_PALE = colors.HexColor("#F7E7D8")
SAND = colors.HexColor("#F4F2E8")
CREAM = colors.HexColor("#FCFBF4")
LINE = colors.HexColor("#C8D5CC")
TEXT = colors.HexColor("#152A23")
MUTED = colors.HexColor("#64736D")
ORANGE = colors.HexColor("#D26C2C")
RED = colors.HexColor("#B94432")
BLUE = colors.HexColor("#2E7FA6")
GRAY = colors.HexColor("#9AA49E")
YELLOW = colors.HexColor("#E8B84A")

CORE_LABELS = {
    "CORE_01": "Mosaic",
    "CORE_02": "Hàbitats",
    "CORE_03": "Vegetació",
    "CORE_04": "Refugis",
    "CORE_05": "Vulnerab.",
    "CORE_06": "Biodiv.",
    "CORE_07": "Pressió",
    "CORE_08": "Connect.",
    "CORE_09": "Foc",
    "CORE_10": "Aigua",
    "CORE_11": "Restaur.",
    "CORE_12": "Gestió",
}

SOURCE_MATRIX = [
    ("Àrea d'estudi", "GeoPackage del projecte", "Evidència directa", "Superfície, perímetre, retall espacial"),
    ("Cobertes", "ICGC Cobertes 2024", "Evidència directa", "Mosaic, bosc, prats, agricultura, artificial"),
    ("Hàbitats", "Hàbitats terrestres v3 i HIC", "Evidència directa", "Valor d'hàbitats i prudència d'actuació"),
    ("Biodiversitat", "GBIF i iNaturalist", "Evidència directa", "Coneixement públic d'espècies i esforç d'observació"),
    ("Ús públic", "OpenStreetMap/Overpass", "Evidència directa", "Accessibilitat potencial i punts d'ús"),
    ("Connectivitat", "ICGC/Gencat/CREAF", "Font de contrast", "Corredors, barreres i funcionalitat territorial"),
    ("Hidrologia", "ACA i cartografia hidrològica", "Font de contrast", "Cursos, fonts, basses i corredors hídrics"),
    ("Relleu", "ICGC DEM", "Font de contrast", "Pendent, orientació, obagues i solanes"),
    ("Teledetecció", "Observació terrestre oficial", "Font de contrast", "Humitat i vigor vegetal"),
    ("Clima", "Meteocat/AEMET/SPEI", "Font de contrast", "Sequera, anomalies i context climàtic"),
    ("Foc", "Perímetres Gencat/EFFIS/EMS", "Font de contrast", "Històric, recurrència, severitat i recuperació"),
    ("Protecció", "ENPE, PEIN, Natura 2000", "Font de context", "Governança, obligacions i figura de gestió"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def project_display_name() -> str:
    return PROJECT_NAME.replace("_", " ")


def project_map_path(kind: str) -> Path:
    candidates = [
        MAPS / f"mapa_{kind}_{PROJECT_SLUG}.png",
        MAPS / f"mapa_{kind}.png",
    ]
    if PROJECT_SLUG != "alinya":
        candidates.append(MAPS / f"mapa_{kind}_alinya.png")
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def draw_brand_logo(c: canvas.Canvas, path: Path, x: float, y: float, size: float) -> None:
    """Draw an existing square brand asset without deformation."""
    if not path.exists():
        return
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.35)
    c.roundRect(x, y, size, size, 2.2, fill=1, stroke=1)
    inset = 0.7 * mm
    c.drawImage(
        ImageReader(str(path)),
        x + inset,
        y + inset,
        width=size - 2 * inset,
        height=size - 2 * inset,
        preserveAspectRatio=True,
        anchor="c",
    )


def plain(text: Any) -> str:
    """Normalize text from legacy CSV/JSON outputs before PDF rendering."""
    value = str(text or "")
    replacements = {
        "\u2019": "'",
        "\u2018": "'",
        "\u2013": "-",
        "\u2014": "-",
        "\u00b7": "-",
        "â": "'",
        "â€™": "'",
        "â??": "'",
        "â": "-",
        "â€“": "-",
        "â": "-",
        "â€œ": '"',
        "â€": '"',
        "Ã ": "à",
        "Ã¨": "è",
        "Ã©": "é",
        "Ã­": "í",
        "Ã²": "ò",
        "Ã³": "ó",
        "Ãº": "ú",
        "Ã§": "ç",
        "Ã±": "ñ",
    }
    for wrong, right in replacements.items():
        value = value.replace(wrong, right)
    return value


def clean(text: Any) -> str:
    return html.escape(plain(text))


def sentence_start(text: Any) -> str:
    value = plain(text).strip()
    if not value:
        return value
    return value[0].upper() + value[1:]


def draw_centered_text(c: canvas.Canvas, x: float, y: float, text: str, font: str, size: float) -> None:
    """Draw short text optically centered around a point."""
    c.setFont(font, size)
    c.drawCentredString(x, y - size * 0.35, text)


def num(value: Any) -> float | None:
    if value in (None, "", "no disponible"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def fmt(value: Any, decimals: int = 1, suffix: str = "") -> str:
    number = num(value)
    if number is None:
        return "Criteri qualitatiu"
    text = f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text}{suffix}"


def metric(rows: list[dict[str, str]], key: str) -> str:
    for row in rows:
        if row.get("indicador") == key:
            return row.get("valor", "")
    return ""


def core_metric(rows: list[dict[str, str]], code: str) -> str:
    for row in rows:
        if row.get("code") == code:
            return row.get("primary_result") or row.get("value_0_100") or row.get("normalized_value", "")
    return ""


def pressure_metric(rows: list[dict[str, str]], key: str) -> str:
    for row in rows:
        if row.get("indicator") == key:
            return row.get("value", "")
    return ""


def cover_metric_by_text(rows: list[dict[str, str]], pattern: str, value_key: str = "superficie_ha") -> str:
    for row in rows:
        if pattern.lower() in plain(row.get("tipus_coberta", "")).lower():
            return row.get(value_key, "")
    return ""


def priority_habitat_surface(rows: list[dict[str, str]]) -> float | None:
    total = 0.0
    found = False
    for row in rows:
        if str(row.get("es_prioritari", "")).strip().lower() == "true":
            value = num(row.get("superficie_ha"))
            if value is not None:
                total += value
                found = True
    return total if found else None


def rows_sum(rows: list[dict[str, str]], value_key: str, *patterns: str, text_key: str = "nom_habitat") -> float:
    total = 0.0
    for row in rows:
        text = plain(row.get(text_key, "")).lower()
        if any(pattern.lower() in text for pattern in patterns):
            total += num(row.get(value_key)) or 0.0
    return total


def row_value(rows: list[dict[str, str]], match_key: str, match_value: str, value_key: str = "value") -> str:
    for row in rows:
        if row.get(match_key) == match_value:
            return row.get(value_key, "")
    return ""


def top_rows(rows: list[dict[str, str]], key: str, limit: int = 5) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: num(row.get(key)) or 0.0, reverse=True)[:limit]


def top_species(project: Path, limit: int = 8) -> list[dict[str, str]]:
    path = project / "processed" / "biodiversitat.gpkg"
    if not path.exists():
        return []
    query = """
        SELECT scientificName, taxonGroup, source, COUNT(*) AS records
        FROM biodiversitat
        WHERE scientificName IS NOT NULL AND TRIM(scientificName) != ''
        GROUP BY scientificName, taxonGroup, source
        ORDER BY records DESC
        LIMIT ?
    """
    try:
        with sqlite3.connect(path) as connection:
            rows = connection.execute(query, (limit,)).fetchall()
    except sqlite3.Error:
        return []
    return [
        {"scientificName": str(name), "taxonGroup": str(group), "source": str(source), "records": str(records)}
        for name, group, source, records in rows
    ]


def recommendation_rows(project: Path) -> list[dict[str, str]]:
    payload = read_json(project / "recommendations" / "recommendations.json")
    rows: list[dict[str, str]] = []
    for index, item in enumerate(payload.get("recommendations", []), start=1):
        rows.append(
            {
                "priority": str(index),
                "action_type": item.get("type", ""),
                "objective": item.get("title", ""),
                "confidence": item.get("confidence", ""),
                "supporting_indicators": "; ".join(item.get("supporting_indicators", [])),
                "justification": item.get("ecological_justification") or item.get("justification", ""),
                "expected_ecological_benefit": item.get("expected_ecological_benefit", ""),
                "location": item.get("location", ""),
                "group": item.get("group", ""),
            }
        )
    return rows


def availability_summary(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("availability", {}).get("summary", {})


def indicator_completeness(data: dict[str, Any], code: str) -> dict[str, Any]:
    for row in data.get("completeness", {}).get("indicators", []):
        if row.get("indicator") == code:
            return row
    return {}


def block_status(data: dict[str, Any], block_id: str) -> str:
    for block in data.get("availability", {}).get("blocks", []):
        if block.get("block_id") == block_id:
            counts = block.get("status_counts", {})
            return ", ".join(f"{key}: {value}" for key, value in counts.items()) or "sense estat"
    return "bloc no documentat"


def source_status(data: dict[str, Any], source_id: str) -> str:
    for source in data.get("availability", {}).get("sources", []):
        if source.get("source_id") == source_id:
            return source.get("status", "sense estat")
    return "no documentada"


def core_summary_row(data: dict[str, Any], code: str) -> list[str]:
    row = core_row(data["core"], code)
    complete = indicator_completeness(data, code)
    value = client_value(row.get("primary_result") or row.get("value_0_100") or row.get("normalized_value"))
    missing = ", ".join(complete.get("missing_sources", [])[:3])
    if not missing:
        missing = "cap font crítica pendent"
    return [
        row.get("name", code),
        value,
        row.get("status", ""),
        row.get("confidence", ""),
        missing,
    ]


def validation_summary_text(data: dict[str, Any]) -> str:
    technical = data.get("technical_validation", {}).get("summary", {})
    ecological = data.get("ecological_validation", {}).get("summary", {})
    return (
        f"Tècnica: {technical.get('status', 'sense estat')} "
        f"({technical.get('critical_errors', 0)} errors crítics). "
        f"Ecològica: {ecological.get('status', 'sense estat')} "
        f"({ecological.get('warnings', 0)} avisos)."
    )


class Report:
    def __init__(self, path: Path, title: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.c.setTitle(title)
        self.c.setAuthor("EcoRadar")
        self.page_no = 0
        self.width, self.height = A4
        self.margin = 16 * mm
        self.styles = {
            "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.6, leading=11.2, textColor=TEXT),
            "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7.2, leading=9.0, textColor=TEXT),
            "tiny": ParagraphStyle("tiny", fontName="Helvetica", fontSize=6.4, leading=7.6, textColor=MUTED),
            "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=GREEN_DARK),
            "card_title": ParagraphStyle("card_title", fontName="Helvetica-Bold", fontSize=8.7, leading=10.2, textColor=GREEN_DARK),
            "small_bold": ParagraphStyle("small_bold", fontName="Helvetica-Bold", fontSize=7.2, leading=9.0, textColor=TEXT),
            "white": ParagraphStyle("white", fontName="Helvetica", fontSize=8.2, leading=10.5, textColor=colors.white),
            "table": ParagraphStyle("table", fontName="Helvetica", fontSize=6.2, leading=7.6, textColor=TEXT),
            "table_header": ParagraphStyle("table_header", fontName="Helvetica-Bold", fontSize=6.2, leading=7.6, textColor=colors.white),
        }

    def new_page(self, title: str | None = None, section: str | None = None) -> None:
        if self.page_no:
            self.c.showPage()
        self.page_no += 1
        self.c.setFillColor(SAND)
        self.c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        if title:
            self.header(title, section)

    def header(self, title: str, section: str | None = None) -> None:
        c = self.c
        c.setFillColor(GREEN_DARK)
        c.roundRect(self.margin, self.height - self.margin - 22 * mm, self.width - 2 * self.margin, 22 * mm, 5, fill=1, stroke=0)
        c.setFillColor(ACCENT)
        c.roundRect(self.margin, self.height - self.margin - 23.2 * mm, self.width - 2 * self.margin, 2.4 * mm, 1.2, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(self.margin + 8 * mm, self.height - self.margin - 9 * mm, title)
        c.setFont("Helvetica", 7.5)
        c.drawString(self.margin + 8 * mm, self.height - self.margin - 16 * mm, section or "Diagnosi ecològica EcoRadar")

    def footer(self) -> None:
        c = self.c
        c.setFillColor(GREEN_DARK)
        c.rect(0, 0, self.width, 8 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 6.8)
        c.drawString(self.margin, 3 * mm, f"ECORADAR - Diagnosi ecològica de {project_display_name()}")
        c.drawRightString(self.width - self.margin, 3 * mm, str(self.page_no))

    def para(self, text: str, x: float, y_top: float, width: float, style: str = "body") -> float:
        paragraph = Paragraph(clean(text), self.styles[style])
        _, height = paragraph.wrap(width, 1000)
        paragraph.drawOn(self.c, x, y_top - height)
        return height

    def para_fit(
        self,
        text: str,
        x: float,
        y_top: float,
        width: float,
        max_height: float,
        style: str = "body",
        min_font_size: float = 5.4,
    ) -> float:
        base_style = self.styles[style]
        font_size = float(base_style.fontSize)
        while font_size >= min_font_size:
            fitted = base_style.clone(f"{style}_fit_{font_size:.1f}")
            fitted.fontSize = font_size
            fitted.leading = max(font_size + 1.1, font_size * 1.22)
            paragraph = Paragraph(clean(text), fitted)
            _, height = paragraph.wrap(width, 1000)
            if height <= max_height:
                paragraph.drawOn(self.c, x, y_top - height)
                return height
            font_size -= 0.25
        fitted = base_style.clone(f"{style}_fit_min")
        fitted.fontSize = min_font_size
        fitted.leading = max(min_font_size + 1.0, min_font_size * 1.2)
        paragraph = Paragraph(clean(text), fitted)
        _, height = paragraph.wrap(width, 1000)
        paragraph.drawOn(self.c, x, y_top - height)
        return height

    def card(self, x: float, y: float, w: float, h: float, title: str | None = None, fill=CREAM) -> None:
        c = self.c
        c.setFillColor(fill)
        c.setStrokeColor(colors.white)
        c.roundRect(x, y, w, h, 4, fill=1, stroke=0)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.4)
        c.roundRect(x, y, w, h, 4, fill=0, stroke=1)
        if title:
            c.setFillColor(ACCENT)
            c.roundRect(x + 5 * mm, y + h - 11.2 * mm, 14 * mm, 1.1 * mm, 0.5, fill=1, stroke=0)
            c.setFillColor(GREEN_DARK)
            c.setFont("Helvetica-Bold", 8.7)
            c.drawString(x + 5 * mm, y + h - 6.4 * mm, title)

    def metric_card(self, x: float, y: float, w: float, label: str, value: str, unit: str = "") -> None:
        self.card(x, y, w, 22 * mm, fill=GREEN_PALE)
        c = self.c
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 4 * mm, y + 12 * mm, value)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.8)
        c.drawString(x + 4 * mm, y + 7 * mm, unit)
        c.drawString(x + 4 * mm, y + 3.5 * mm, label)

    def finish(self) -> None:
        self.c.save()


def prepare_inputs() -> dict[str, Any]:
    core_payload = read_json(INDICATORS / "ecoradar_core_indicators.json")
    return {
        "basic": read_csv(INDICATORS / "ecoradar_01_resum.csv"),
        "core": core_payload.get("indicators", []),
        "core_payload": core_payload,
        "cover": read_csv(INDICATORS / "cobertes_sol_resum.csv"),
        "habitats": read_csv(INDICATORS / "habitats_resum.csv"),
        "biodiv": read_csv(INDICATORS / "biodiversitat_resum.csv"),
        "pressure": read_csv(INDICATORS / "recreational_pressure_resum.csv"),
        "hydrology": read_csv(INDICATORS / "hidrologia_resum.csv"),
        "connectivity": read_csv(INDICATORS / "connectivitat_resum.csv"),
        "fires": read_csv(INDICATORS / "incendis_resum.csv"),
        "recommendations": recommendation_rows(PROJECT),
        "fitxa_value": read_csv(INDICATORS / "ecoradar_fitxa_value_gate.csv"),
        "study": read_json(METADATA / "study_area_metadata.json"),
        "teledeteccio": read_json(METADATA / "teledeteccio_metadata.json"),
        "diagnosis": read_json(PROJECT / "diagnosis" / "ecoradar_diagnosis.json"),
        "core_meta": read_json(METADATA / "ecoradar_core_metadata.json"),
        "availability": read_json(METADATA / "data_availability_report.json"),
        "connectors": read_json(METADATA / "connectors_status_report.json"),
        "completeness": read_json(METADATA / "indicators_completeness_report.json"),
        "technical_validation": read_json(PROJECT / "validation" / "technical_validation.json"),
        "ecological_validation": read_json(PROJECT / "validation" / "ecological_validation.json"),
        "recommendations_validation": read_json(PROJECT / "validation" / "recommendations_validation.json"),
        "top_species": top_species(PROJECT),
    }


def report_date(payload: dict[str, Any]) -> str:
    generated = payload.get("diagnosis", {}).get("generated_at", "")
    return generated[:10] or datetime.now().strftime("%Y-%m-%d")


def priority_color(category: str):
    normalized = plain(category).casefold().strip()
    return {
        "molt baix": GREEN_2,
        "baix": colors.HexColor("#92B765"),
        "mitjà": YELLOW,
        "mitja": YELLOW,
        "alt": ORANGE,
        "molt alt": RED,
    }.get(normalized, GRAY)


def core_values(core: list[dict[str, str]]) -> list[tuple[str, float | None, str]]:
    management_axes = [
        ("CORE_11", "Restauració"),
        ("CORE_01", "Pèrdua de mosaic"),
        ("CORE_07", "Pressió d'ús"),
        ("CORE_10", "Alteració de l'aigua"),
        ("CORE_09", "Risc d'incendi"),
        ("CORE_05", "Vulnerabilitat"),
    ]
    rows_by_code = {row.get("code", ""): row for row in core}
    values: list[tuple[str, float | None, str]] = []
    for code, label in management_axes:
        row = rows_by_code.get(code)
        if not row:
            continue
        values.append(
            (
                label,
                num(row.get("value_0_100") or row.get("normalized_value")),
                row.get("category", "no disponible"),
            )
        )
    return values


def phase2_methodology(data: dict[str, Any]) -> bool:
    return data.get("core_payload", {}).get("methodology_version") == "alinya_core_v2_2026-09-09"


def core_row(core: list[dict[str, str]], code: str) -> dict[str, str]:
    for row in core:
        if row.get("code") == code:
            return row
    return {}


def client_value(value: Any) -> str:
    if value in (None, ""):
        return "Criteri qualitatiu"
    if str(value).strip().lower() in {"no disponible", "no disponible.", "no_disponible", "no disponible"}:
        return "Criteri qualitatiu"
    return str(value)


def client_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status == "disponible":
        return "evidència directa"
    if status == "parcial":
        return "lectura preliminar"
    if status == "no disponible":
        return "font de contrast"
    return plain(value)


def core_reading(data: dict[str, Any]) -> str:
    forest = fmt(metric(data["basic"], "percentatge_coberta_forestal"), 1, "%")
    grass = fmt(metric(data["basic"], "percentatge_prats_pastures_herbassars"), 1, "%")
    hic = fmt(metric(data["basic"], "superficie_hic"), 0)
    species = metric(data["basic"], "nombre_especies_registrades")
    pressure = fmt(pressure_metric(data["pressure"], "osm_path_track_road_density"), 2)
    return (
        f"{project_display_name()} funciona com una gran matriu forestal ({forest}) amb espais oberts escassos però ecològicament estratègics ({grass}). "
        f"Els {hic} ha d'hàbitats d'interès comunitari i les {species} espècies citades justifiquen una gestió de prudència alta: "
        f"abans d'obrir noves actuacions cal protegir valors coneguts, validar el mosaic fi i entendre millor l'aigua, la humitat vegetal i el foc. "
        f"La xarxa cartografiada ({pressure} km/km2) indica accessibilitat potencial, no freqüentació real."
    )


def draw_badge(report: Report, x: float, y: float, number: str, title: str, subtitle: str) -> None:
    c = report.c
    c.setFillColor(GREEN_DARK)
    c.roundRect(x, y, 178 * mm, 23 * mm, 5, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#DDEBDD"))
    c.circle(x + 12 * mm, y + 11.5 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(GREEN_DARK)
    draw_centered_text(c, x + 12 * mm, y + 11.5 * mm, number, "Helvetica-Bold", 14)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x + 25 * mm, y + 13.2 * mm, title)
    c.setFont("Helvetica", 7.4)
    c.drawString(x + 25 * mm, y + 6.4 * mm, subtitle)


def draw_score_bar(report: Report, x: float, y: float, w: float, label: str, value: float | None, confidence: str) -> None:
    c = report.c
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x, y + 5 * mm, label)
    c.setFillColor(LINE)
    c.roundRect(x, y, w, 3.2 * mm, 1.6, fill=1, stroke=0)
    if value is not None:
        fill = GREEN_2 if value >= 60 else ORANGE if value >= 35 else RED
        c.setFillColor(fill)
        c.roundRect(x, y, max(2 * mm, w * value / 100), 3.2 * mm, 1.6, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawRightString(x + w, y + 4.7 * mm, f"{value:.0f}/100")
    else:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.2)
        c.drawRightString(x + w, y + 4.7 * mm, "criteri insuficient")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.9)
    c.drawString(x, y - 3.6 * mm, f"confiança: {confidence}")


def draw_compact_bar(report: Report, x: float, y: float, w: float, label: str, value: float | None, color=GREEN_2) -> None:
    c = report.c
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 5.8)
    c.drawString(x, y + 3.5 * mm, label)
    c.setFillColor(colors.HexColor("#D9E2DA"))
    c.roundRect(x, y, w, 2.1 * mm, 1, fill=1, stroke=0)
    if value is not None:
        c.setFillColor(color)
        c.roundRect(x, y, max(1.5 * mm, w * max(0, min(100, value)) / 100), 2.1 * mm, 1, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 5.5)
        c.drawRightString(x + w, y + 3.4 * mm, f"{value:.0f}")
    else:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 5.2)
        c.drawRightString(x + w, y + 3.4 * mm, "qual.")


def draw_mini_metric(report: Report, x: float, y: float, label: str, value: str, unit: str = "", color=GREEN_DARK) -> None:
    c = report.c
    c.setFillColor(colors.HexColor("#EEF5EE"))
    c.roundRect(x, y, 33 * mm, 15 * mm, 3, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, 33 * mm, 15 * mm, 3, fill=0, stroke=1)
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 3 * mm, y + 8.2 * mm, value)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.4)
    c.drawString(x + 3 * mm, y + 4.7 * mm, unit)
    c.drawString(x + 3 * mm, y + 2.1 * mm, label)


def draw_source_pill(report: Report, x: float, y: float, title: str, mode: str) -> None:
    c = report.c
    if "directa" in mode:
        fill = GREEN_PALE
        stroke = GREEN_2
    elif "context" in mode:
        fill = colors.HexColor("#E8F0F4")
        stroke = BLUE
    else:
        fill = colors.HexColor("#FFF4D8")
        stroke = YELLOW
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.roundRect(x, y, 42 * mm, 7.2 * mm, 3.5, fill=1, stroke=1)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 5.3)
    c.drawString(x + 2 * mm, y + 4.1 * mm, title[:20])
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 4.6)
    c.drawString(x + 2 * mm, y + 1.4 * mm, mode[:24])


def draw_numbered_actions(report: Report, actions: list[str], x: float, y_top: float, width: float) -> None:
    y = y_top
    c = report.c
    for index, text in enumerate(actions, start=1):
        c.setFillColor(GREEN_PALE)
        c.circle(x + 3 * mm, y - 1.5 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(GREEN_DARK)
        draw_centered_text(c, x + 3 * mm, y - 3 * mm, str(index), "Helvetica-Bold", 5.8)
        used = report.para_fit(sentence_start(text), x + 8 * mm, y, width - 8 * mm, 13 * mm, "small", 5.7)
        y -= max(10 * mm, used + 4 * mm)


def draw_compact_numbered_actions(report: Report, actions: list[str], x: float, y_top: float, width: float) -> None:
    y = y_top
    c = report.c
    for index, text in enumerate(actions, start=1):
        c.setFillColor(GREEN_PALE)
        c.circle(x + 2.6 * mm, y - 2.6 * mm, 2.6 * mm, fill=1, stroke=0)
        c.setFillColor(GREEN_DARK)
        draw_centered_text(c, x + 2.6 * mm, y - 2.6 * mm, str(index), "Helvetica-Bold", 5.2)
        used = report.para_fit(sentence_start(text), x + 7 * mm, y, width - 7 * mm, 10.5 * mm, "tiny", 5.05)
        y -= max(8.3 * mm, used + 2.8 * mm)


def diagnosis_items_text(items: list[dict[str, Any]]) -> str:
    parts = []
    for item in items[:2]:
        title = plain(item.get("title", ""))
        implication = plain(item.get("management_implication", ""))
        if implication:
            parts.append(f"{title}: {implication}")
        else:
            parts.append(title)
    return "; ".join(parts)


def draw_radar(report: Report, values: list[tuple[str, float | None, str]], cx: float, cy: float, radius: float) -> None:
    c = report.c
    available = [(label, value, category) for label, value, category in values if value is not None]
    if len(available) < 3:
        report.para("Radar no disponible: calen almenys tres indicadors numèrics.", cx - radius, cy, 2 * radius, "small")
        return
    n = len(available)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    for step in range(1, 6):
        r = radius * step / 5
        points = []
        for i in range(n):
            angle = -math.pi / 2 + i * 2 * math.pi / n
            points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
        path = c.beginPath()
        path.moveTo(points[0][0], points[0][1])
        for point in points[1:]:
            path.lineTo(point[0], point[1])
        path.close()
        c.drawPath(path, stroke=1, fill=0)
    c.setStrokeColor(GRAY)
    for i in range(n):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        c.line(cx, cy, cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)

    points = []
    for i, (_, value, _) in enumerate(available):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        r = radius * (value or 0) / 100
        points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    path = c.beginPath()
    path.moveTo(points[0][0], points[0][1])
    for point in points[1:]:
        path.lineTo(point[0], point[1])
    path.close()
    c.setFillColor(colors.Color(0.12, 0.38, 0.30, alpha=0.28))
    c.setStrokeColor(GREEN_DARK)
    c.setLineWidth(1.4)
    c.drawPath(path, stroke=1, fill=1)

    # Each indicator uses the same verified category palette as the priority bar.
    c.setLineWidth(0.6)
    for point, (_, _, category) in zip(points, available):
        c.setFillColor(priority_color(category))
        c.setStrokeColor(colors.white)
        c.circle(point[0], point[1], 1.35 * mm, fill=1, stroke=1)

    c.setFont("Helvetica", 6.2)
    for i, (label, value, category) in enumerate(available):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        lx = cx + math.cos(angle) * (radius + 6.5 * mm)
        ly = cy + math.sin(angle) * (radius + 5.2 * mm)
        label_lines = {
            "Pèrdua de mosaic": ["Pèrdua de", "mosaic"],
            "Alteració de l'aigua": ["Alteració de", "l'aigua"],
        }.get(label, [label])
        c.setFillColor(TEXT)
        for line_no, line in enumerate(label_lines):
            c.drawCentredString(lx, ly - line_no * 2.1 * mm, line)
        c.setFillColor(priority_color(category))
        c.setFont("Helvetica-Bold", 6.1)
        value_offset = 4.8 * mm if len(label_lines) > 1 else 2.8 * mm
        c.drawCentredString(lx, ly - value_offset, f"{value:.0f}")
        c.setFont("Helvetica", 6.2)


def draw_image(report: Report, path: Path, x: float, y: float, w: float, h: float) -> None:
    if path.exists():
        report.c.drawImage(ImageReader(str(path)), x, y, width=w, height=h, preserveAspectRatio=True, anchor="c")
    else:
        report.para("Mapa no disponible.", x + 5 * mm, y + h - 10 * mm, w - 10 * mm, "small")


def draw_fitxa_panel(report: Report, x: float, y: float, w: float, h: float, number: str, title: str, subtitle: str = "") -> None:
    c = report.c
    c.setFillColor(CREAM)
    c.setStrokeColor(colors.white)
    c.roundRect(x, y, w, h, 3.8, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#D6E0D8"))
    c.setLineWidth(0.45)
    c.roundRect(x, y, w, h, 3.8, fill=0, stroke=1)
    c.setFillColor(ACCENT)
    c.roundRect(x + 4 * mm, y + h - 9.6 * mm, 10 * mm, 0.9 * mm, 0.4, fill=1, stroke=0)
    c.setFillColor(GREEN_DARK)
    c.setFont("Helvetica-Bold", 8.8)
    c.drawString(x + 4 * mm, y + h - 7 * mm, f"{number}. {title}")
    if subtitle:
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 6.4)
        c.drawString(x + 4 * mm, y + h - 12.2 * mm, subtitle[:72])


def draw_fitxa_metric(
    report: Report,
    x: float,
    y: float,
    value: str,
    label: str,
    accent=GREEN_DARK,
    w: float = 27 * mm,
    h: float = 12.5 * mm,
) -> None:
    c = report.c
    c.setFillColor(colors.HexColor("#EEF5EE"))
    c.roundRect(x, y, w, h, 2.4, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, w, h, 2.4, fill=0, stroke=1)
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 9.6)
    c.drawString(x + 2.4 * mm, y + h - 5.3 * mm, str(value)[:12])
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.7)
    c.drawString(x + 2.4 * mm, y + 3.1 * mm, label[:24])


def draw_fitxa_hbar(
    report: Report,
    x: float,
    y: float,
    w: float,
    label: str,
    value: float,
    max_value: float,
    color=GREEN_2,
    label_width: float = 30 * mm,
) -> None:
    c = report.c
    value_width = 9 * mm
    bar_x = x + label_width
    bar_w = w - label_width - value_width
    c.setFillColor(TEXT)
    c.setFont("Helvetica", 6.2)
    c.drawString(x, y + 0.55 * mm, label[:28])
    c.setFillColor(colors.HexColor("#DCE5DD"))
    c.roundRect(bar_x, y, bar_w, 2.7 * mm, 1.2, fill=1, stroke=0)
    if max_value > 0:
        c.setFillColor(color)
        c.roundRect(bar_x, y, max(1.2 * mm, bar_w * value / max_value), 2.7 * mm, 1.2, fill=1, stroke=0)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 6.2)
    c.drawRightString(x + w, y + 0.55 * mm, fmt(value, 0))


def draw_fitxa_cover_bars(report: Report, rows: list[dict[str, str]], x: float, y_top: float, w: float, limit: int = 5) -> None:
    selected = sorted(
        rows,
        key=lambda row: num(row.get("percentatge_total") or row.get("percentatge")) or 0,
        reverse=True,
    )[:limit]
    values = [num(row.get("percentatge_total") or row.get("percentatge")) or 0 for row in selected]
    max_value = max(values) if values else 1
    y = y_top
    palette = [GREEN_2, colors.HexColor("#6F9F62"), YELLOW, ORANGE, BLUE]
    for idx, row in enumerate(selected):
        name = plain(row.get("tipus_coberta") or row.get("nom_habitat") or "Coberta")
        if "Boscos densos d'aciculifolis" in name:
            name = "Boscos densos de coníferes"
        elif "Boscos clars d'aciculifolis" in name:
            name = "Boscos clars de coníferes"
        value = num(row.get("percentatge_total") or row.get("percentatge")) or 0
        draw_fitxa_hbar(report, x, y, w, name, value, max_value, palette[idx % len(palette)])
        y -= 5.8 * mm


def draw_fitxa_taxon_bars(report: Report, rows: list[dict[str, str]], x: float, y_top: float, w: float, limit: int = 6) -> None:
    selected = sorted(rows, key=lambda row: num(row.get("nombre_registres")) or 0, reverse=True)[:limit]
    max_value = max([num(row.get("nombre_registres")) or 0 for row in selected] or [1])
    y = y_top
    palette = [GREEN_2, BLUE, ORANGE, colors.HexColor("#7E679B"), colors.HexColor("#8B5E34"), YELLOW]
    for idx, row in enumerate(selected):
        label = plain(row.get("grup_taxonomic") or "Grup")
        value = num(row.get("nombre_registres")) or 0
        draw_fitxa_hbar(report, x, y, w, label, value, max_value, palette[idx % len(palette)], 20 * mm)
        y -= 5.6 * mm


def draw_fitxa_scale(report: Report, x: float, y: float, w: float, value: float | None, label: str) -> None:
    c = report.c
    bands = [GREEN_2, colors.HexColor("#92B765"), YELLOW, ORANGE, RED]
    segment = w / len(bands)
    for idx, color in enumerate(bands):
        c.setFillColor(color)
        c.rect(x + idx * segment, y, segment, 4 * mm, fill=1, stroke=0)
    c.setStrokeColor(colors.white)
    for idx in range(1, len(bands)):
        c.line(x + idx * segment, y, x + idx * segment, y + 4 * mm)
    if value is not None:
        px = x + max(0, min(100, value)) * w / 100
        c.setFillColor(GREEN_DARK)
        path = c.beginPath()
        path.moveTo(px, y + 7 * mm)
        path.lineTo(px - 2 * mm, y + 4 * mm)
        path.lineTo(px + 2 * mm, y + 4 * mm)
        path.close()
        c.drawPath(path, stroke=0, fill=1)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 6.4)
    c.drawString(x, y + 6.5 * mm, label)
    c.setFont("Helvetica", 5.8)
    c.drawString(x, y - 3 * mm, "baixa")
    c.drawCentredString(x + w / 2, y - 3 * mm, "mitjana")
    c.drawRightString(x + w, y - 3 * mm, "alta")


def draw_fitxa_process_rows(report: Report, x: float, y_top: float, w: float) -> None:
    c = report.c
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 5.7)
    c.drawString(x, y_top, "Nivell")
    c.drawString(x + 8 * mm, y_top, "Opció preferent")
    c.drawRightString(x + w, y_top, "Quan correspon")
    rows = [
        ("A", "Protegir / no intervenir", "el procés funciona"),
        ("B", "Retirar la pressió", "causa reversible"),
        ("C", "Reactivar processos", "procés clau absent"),
        ("D", "Restauració focal", "fallida verificada"),
    ]
    y = y_top - 6 * mm
    for level, option, condition in rows:
        c.setStrokeColor(colors.HexColor("#DDE7DE"))
        c.line(x, y + 4.4 * mm, x + w, y + 4.4 * mm)
        c.setFillColor(GREEN_2 if level in {"A", "B"} else ORANGE)
        c.setFont("Helvetica-Bold", 6.4)
        c.drawString(x, y, level)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 5.8)
        c.drawString(x + 8 * mm, y, option[:25])
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 5.5)
        c.drawRightString(x + w, y, condition[:19])
        y -= 6.5 * mm


def draw_fitxa_action_decisions(report: Report, x: float, y_top: float, width: float) -> None:
    c = report.c
    actions = [
        ("P1", "Delimitar referència", "On: HIC, refugis i obagues", "no-intervenció amb seguiment", "0-6 mesos"),
        ("P2", "Retirar pressions", "On: aigua, accessos i erosió", "abans de transformar l'hàbitat", "0-18 mesos"),
        ("P3", "Reactivar processos", "On: mosaic i corredors hídrics", "mesura reversible i indicador", "0-18 mesos"),
    ]
    y = y_top
    for priority, title, location, benefit_difficulty, horizon in actions:
        c.setFillColor(GREEN_PALE)
        c.circle(x + 3 * mm, y - 3 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(GREEN_DARK)
        draw_centered_text(c, x + 3 * mm, y - 1.5 * mm, priority[-1], "Helvetica-Bold", 6.8)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 6.8)
        c.drawString(x + 8 * mm, y - 0.5 * mm, f"{priority} · {title}"[:36])
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 5.8)
        c.drawString(x + 8 * mm, y - 4.7 * mm, location[:35])
        c.drawString(x + 8 * mm, y - 8.0 * mm, benefit_difficulty[:36])
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 5.8)
        c.drawString(x + 8 * mm, y - 11.0 * mm, horizon)
        y -= 15.2 * mm


def draw_fitxa_footer(report: Report, data: dict[str, Any], x: float, y: float, w: float) -> None:
    c = report.c
    c.setFillColor(GREEN_DARK)
    c.roundRect(x, y, w, 16 * mm, 3, fill=1, stroke=0)
    draw_brand_logo(c, ECORADAR_LOGO, x + 2 * mm, y + 2 * mm, 12 * mm)
    draw_brand_logo(c, GREEN_WOLF_LOGO, x + 15.5 * mm, y + 2 * mm, 12 * mm)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x + 30 * mm, y + 9.8 * mm, "ECORADAR · GREEN WOLF NATURE")
    c.setFont("Helvetica", 6.8)
    c.drawString(x + 30 * mm, y + 4.8 * mm, "Dades - ciència - natura - futur")
    c.setFont("Helvetica", 7.2)
    c.drawString(x + 95 * mm, y + 8.3 * mm, "Diagnosi ecològica integrada per orientar decisions de gestió.")
    c.drawRightString(x + w - 6 * mm, y + 8.3 * mm, report_date(data))


def draw_table(report: Report, rows: list[list[Any]], x: float, y_top: float, widths: list[float], font_size: float = 6.8) -> float:
    header_style = report.styles["table_header"].clone("table_header_custom")
    body_style = report.styles["table"].clone("table_custom")
    header_style.fontSize = font_size
    header_style.leading = font_size + 1.4
    body_style.fontSize = font_size
    body_style.leading = font_size + 1.4
    wrapped_rows = []
    for row_idx, row in enumerate(rows):
        style = header_style if row_idx == 0 else body_style
        wrapped_rows.append([Paragraph(clean(cell), style) for cell in row])
    table = Table(wrapped_rows, colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, LINE),
                ("BACKGROUND", (0, 1), (-1, -1), CREAM),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    _, height = table.wrap(sum(widths), 500)
    table.drawOn(report.c, x, y_top - height)
    return height


def page_cover(report: Report, data: dict[str, Any]) -> None:
    report.new_page()
    c = report.c
    w, h = report.width, report.height
    c.setFillColor(colors.HexColor("#F3F0E4"))
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Editorial cover: the territory is the product, so the map dominates.
    c.setFillColor(GREEN_DARK)
    c.roundRect(10 * mm, h - 42 * mm, 190 * mm, 28 * mm, 5, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#DDEBDD"))
    c.circle(24 * mm, h - 28 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(GREEN_DARK)
    draw_centered_text(c, 24 * mm, h - 28 * mm, "ER", "Helvetica-Bold", 10.5)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(38 * mm, h - 24 * mm, "INFORME DE DIAGNOSI ECOLÒGICA INTEGRADA")
    c.setFont("Helvetica", 8.5)
    c.drawString(38 * mm, h - 32 * mm, "EcoRadar - suport tècnic per orientar decisions de gestió")

    c.setFillColor(CREAM)
    c.setStrokeColor(colors.white)
    c.roundRect(10 * mm, 76 * mm, 190 * mm, 181 * mm, 6, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.roundRect(14 * mm, 101 * mm, 182 * mm, 150 * mm, 4, fill=1, stroke=0)
    draw_image(report, project_map_path("espai"), 15 * mm, 102 * mm, 180 * mm, 148 * mm)

    c.setFillColor(colors.Color(0.05, 0.23, 0.18, alpha=0.90))
    c.roundRect(18 * mm, 218 * mm, 95 * mm, 25 * mm, 4, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(24 * mm, 232 * mm, project_display_name())
    c.setFont("Helvetica", 8)
    c.drawString(24 * mm, 224 * mm, f"Diagnosi generada el {report_date(data)}")
    c.setFillColor(ACCENT)
    c.roundRect(24 * mm, 220.5 * mm, 36 * mm, 1.4 * mm, 0.7, fill=1, stroke=0)

    c.setFillColor(colors.Color(0.95, 0.98, 0.93, alpha=0.94))
    c.roundRect(18 * mm, 107 * mm, 72 * mm, 24 * mm, 4, fill=1, stroke=0)
    c.setFillColor(GREEN_DARK)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(24 * mm, 123 * mm, "LECTURA TERRITORIAL")
    report.para_fit(
        "El mapa situa la matriu ecològica que estructura les decisions: hàbitats, accessibilitat, mosaic i zones que cal validar al camp.",
        24 * mm,
        119 * mm,
        58 * mm,
        11 * mm,
        "tiny",
        5.2,
    )

    c.setFillColor(GREEN_DARK)
    c.roundRect(10 * mm, 48 * mm, 190 * mm, 20 * mm, 4, fill=1, stroke=0)
    for i, (label, value, unit) in enumerate([
        ("superfície", fmt(data["study"].get("surface_ha"), 1), "ha"),
        ("hàbitats", metric(data["basic"], "nombre_habitats"), "tipus"),
        ("HIC", fmt(metric(data["basic"], "superficie_hic"), 0), "ha"),
        ("espècies", metric(data["basic"], "nombre_especies_registrades"), "taxons"),
    ]):
        x = 19 * mm + i * 45 * mm
        c.setFillColor(colors.HexColor("#ECF4EA"))
        c.roundRect(x, 53 * mm, 34 * mm, 10 * mm, 3, fill=1, stroke=0)
        c.setFillColor(GREEN_DARK)
        c.setFont("Helvetica-Bold", 8.8)
        c.drawString(x + 3 * mm, 58.4 * mm, str(value))
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 4.8)
        c.drawString(x + 3 * mm, 55.2 * mm, f"{unit} {label}".strip())

    c.setFillColor(CREAM)
    c.roundRect(10 * mm, 21 * mm, 190 * mm, 18 * mm, 4, fill=1, stroke=0)
    c.setFillColor(ACCENT)
    c.roundRect(16 * mm, 34.5 * mm, 28 * mm, 1.2 * mm, 0.6, fill=1, stroke=0)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(16 * mm, 31.2 * mm, "OBJECTIU DEL DOCUMENT")
    report.para_fit(
        "Convertir l'evidència territorial disponible en una lectura ecològica integrada i en criteris de decisió per a la gestió de l'espai.",
        16 * mm,
        28 * mm,
        142 * mm,
        8 * mm,
        "small",
        6.0,
    )
    c.setFillColor(GREEN_DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(194 * mm, 29.2 * mm, "ECORADAR")
    c.setFont("Helvetica", 5.3)
    c.drawRightString(194 * mm, 25.2 * mm, "Dades - ciència - natura - futur")


def page_fitxa(report: Report, data: dict[str, Any]) -> None:
    report.new_page()
    # The fitxa is a dense executive sheet. Increase its general typography by
    # one point and compensate with wider/taller internal content areas below.
    for style_name in ("body", "small", "tiny"):
        report.styles[style_name].fontSize += 1
        report.styles[style_name].leading += 1.2
    basic = data["basic"]
    core = data["core"]
    fitxa_value = data["fitxa_value"]
    m = 5 * mm
    c = report.c

    # Header: visual sheet, not a technical report page.
    c.setFillColor(GREEN_DARK)
    c.roundRect(m, 266.5 * mm, 130 * mm, 25.5 * mm, 4.5, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#DDEBDD"))
    c.circle(m + 12 * mm, 280 * mm, 8.5 * mm, fill=1, stroke=0)
    c.setFillColor(GREEN_DARK)
    draw_centered_text(c, m + 12 * mm, 280 * mm, "01", "Helvetica-Bold", 14)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15.5)
    c.drawString(m + 25 * mm, 282.2 * mm, f"FITXA ECORADAR: {project_display_name().upper()}")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(m + 25 * mm, 275.2 * mm, "Radiografia ecològica per orientar decisions de gestió")
    report.card(139 * mm, 266.5 * mm, 66 * mm, 25.5 * mm)
    c.setFillColor(ACCENT)
    c.roundRect(144 * mm, 286.3 * mm, 16 * mm, 1.1 * mm, 0.5, fill=1, stroke=0)
    c.setFillColor(GREEN_DARK)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawString(144 * mm, 283.7 * mm, "ESTAT ECOLÒGIC")
    c.setFillColor(GREEN_2)
    c.setFont("Helvetica-Bold", 9.4)
    c.drawString(144 * mm, 279 * mm, "Favorable però vulnerable")
    report.para_fit(
        "Bon estat general, però el tancament del paisatge exigeix gestió activa dels espais oberts.",
        144 * mm,
        274.5 * mm,
        56 * mm,
        7.5 * mm,
        "tiny",
        6.2,
    )

    # 1. Territorial matrix and values.
    draw_fitxa_panel(report, m, 179 * mm, 75 * mm, 84 * mm, "1", "Mosaic territorial", "Quina estructura sosté el funcionament ecològic?")
    metric_y = 234 * mm
    for value, unit, label in [
        (fmt(data["study"].get("surface_ha"), 1), "ha", "superfície"),
        (fmt(metric(basic, "percentatge_coberta_forestal"), 1, "%"), "", "coberta forestal"),
        (fmt(metric(basic, "superficie_hic"), 0), "ha", "HIC"),
        (metric(basic, "nombre_especies_registrades"), "taxons", "biodiversitat"),
    ]:
        c.setFillColor(GREEN_DARK)
        c.circle(m + 7 * mm, metric_y + 3 * mm, 2.7 * mm, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 8.4)
        c.drawString(m + 12 * mm, metric_y + 4.5 * mm, value)
        c.setFont("Helvetica", 6.3)
        c.drawString(m + 12 * mm, metric_y + 1 * mm, f"{unit} {label}".strip())
        metric_y -= 12.4 * mm
    draw_image(report, project_map_path("paisatge"), 36 * mm, 194 * mm, 39 * mm, 46 * mm)
    c.setFillColor(TEXT)
    c.setFont("Helvetica", 5.7)
    c.drawString(38 * mm, 188 * mm, "Bosc, prats, matollars i usos artificials")

    # 2. Radar decision profile.
    draw_fitxa_panel(report, 82 * mm, 179 * mm, 61 * mm, 84 * mm, "2", "Prioritat de gestió", "Àmbits amb necessitat o potencial d'actuació")
    draw_radar(report, core_values(core), 112.5 * mm, 225 * mm, 15.6 * mm)
    draw_fitxa_scale(report, 91 * mm, 188 * mm, 43 * mm, None, "prioritat de gestió")

    # 3. Habitats and cover composition.
    draw_fitxa_panel(report, 146 * mm, 179 * mm, 59 * mm, 84 * mm, "3", "Hàbitats i refugis", "On coincideixen valor i protecció climàtica?")
    draw_image(report, project_map_path("refugis_climatics"), 151 * mm, 226 * mm, 49 * mm, 20 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.2)
    c.drawString(151 * mm, 222.5 * mm, "blau fosc: potencial alt · blau: aigua i fonts")
    draw_fitxa_cover_bars(report, data["cover"], 151 * mm, 216.5 * mm, 48 * mm, 3)
    report.para_fit(
        "Dens o clar indica el grau de cobertura arbòria. Orienta la continuïtat horitzontal; no descriu estructura vertical, combustible ni estat sanitari.",
        151 * mm,
        202 * mm,
        48 * mm,
        7.5 * mm,
        "tiny",
        5.5,
    )
    draw_fitxa_metric(report, 151 * mm, 180.5 * mm, fmt(priority_habitat_surface(data["habitats"]), 0), "ha HIC priorit.", w=25 * mm, h=11.5 * mm)
    draw_fitxa_metric(report, 178 * mm, 180.5 * mm, metric(basic, "nombre_habitats"), "hàbitats", w=25 * mm, h=11.5 * mm)

    # 4. Biodiversity knowledge, large central band.
    draw_fitxa_panel(report, m, 100 * mm, 149 * mm, 75 * mm, "4", "Biodiversitat coneguda", "Quins grups estan ben representats i què cal validar?")
    draw_image(report, project_map_path("biodiversitat"), 10 * mm, 108 * mm, 49 * mm, 37 * mm)
    draw_fitxa_metric(report, 10 * mm, 149 * mm, metric(basic, "nombre_registres_biodiversitat"), "cites públiques", w=25 * mm)
    draw_fitxa_metric(report, 37 * mm, 149 * mm, metric(basic, "nombre_especies_registrades"), "taxons", w=22 * mm)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(64 * mm, 154 * mm, "Grups taxonòmics principals")
    draw_fitxa_taxon_bars(report, data["biodiv"], 64 * mm, 147 * mm, 47 * mm, 5)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(116 * mm, 154 * mm, "Taxons més citats")
    y_species = 147 * mm
    for row in data.get("top_species", [])[:4]:
        name = plain(row.get("scientificName", "")).split("(")[0].strip()
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 6.1)
        c.drawString(116 * mm, y_species, name[:29])
        c.setFont("Helvetica-Bold", 6.1)
        c.drawRightString(150 * mm, y_species, str(row.get("records", "")))
        y_species -= 5.2 * mm
    report.para(
        "La base pública és útil per orientar mostreig i detectar buits, però no certifica absències. La prioritat és convertir cites disperses en coneixement validat sobre hàbitats sensibles.",
        61 * mm,
        115 * mm,
        91 * mm,
        "tiny",
    )

    # Interpretation side box.
    draw_fitxa_panel(report, 157 * mm, 100 * mm, 48 * mm, 75 * mm, "5", "Lectura experta", "Què implica per a la gestió?")
    side_items = [
        "QUÈ PASSA? El paisatge es tanca i els espais oberts guanyen valor funcional.",
        "CAUSA PRINCIPAL? Menor gestió agroforestal i expansió progressiva de la massa forestal.",
        "RISC PRINCIPAL? Perdre mosaic, ecotons i recursos d'espècies d'ambients oberts.",
        "OPORTUNITAT? Protegir HIC i refugis, retirar pressions i recuperar processos.",
    ]
    y_side = 156 * mm
    for idx, text in enumerate(side_items, start=1):
        c.setFillColor(GREEN_PALE if idx < 4 else colors.HexColor("#FFF1DD"))
        c.circle(162 * mm, y_side - 2 * mm, 3.1 * mm, fill=1, stroke=0)
        c.setFillColor(GREEN_DARK if idx < 4 else ORANGE)
        draw_centered_text(c, 162 * mm, y_side - 2 * mm, str(idx), "Helvetica-Bold", 6.3)
        report.para_fit(text, 167 * mm, y_side + 1 * mm, 33 * mm, 10.5 * mm, "tiny", 6.0)
        y_side -= 13.5 * mm

    # 6. Access and public use.
    draw_fitxa_panel(report, m, 35 * mm, 70 * mm, 61 * mm, "6", "Accessibilitat i ús públic", "On cal validar possibles conflictes?")
    draw_image(report, project_map_path("pressio_humana"), 8 * mm, 55 * mm, 41 * mm, 25 * mm)
    draw_fitxa_metric(report, 51 * mm, 69 * mm, fmt(pressure_metric(data["pressure"], "osm_path_track_road_km"), 1), "km xarxa", w=20 * mm, h=11 * mm)
    draw_fitxa_metric(report, 51 * mm, 55.5 * mm, pressure_metric(data["pressure"], "osm_recreational_point_features"), "punts ús públic", w=20 * mm, h=11 * mm)
    c.setStrokeColor(MUTED)
    c.setLineWidth(0.7)
    c.line(10 * mm, 50.5 * mm, 15 * mm, 50.5 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.1)
    c.drawString(16 * mm, 49.3 * mm, "camins i pistes OSM")
    c.setFillColor(GREEN_2)
    c.circle(42 * mm, 50.5 * mm, 1.1 * mm, fill=1, stroke=0)
    c.setFillColor(MUTED)
    c.drawString(44 * mm, 49.3 * mm, "punts d'ús públic OSM")
    report.para_fit(
        "Els 124,8 km són camins i pistes cartografiats; els 18 punts són elements d'ús públic registrats a OSM. Mostren accessibilitat potencial, no freqüentació ni pressió real, i serveixen per prioritzar la validació de possibles conflictes amb hàbitats o fauna.",
        8 * mm,
        47.5 * mm,
        64 * mm,
        12 * mm,
        "tiny",
        6.0,
    )

    # 7. Ecological processes.
    draw_fitxa_panel(report, 78 * mm, 35 * mm, 64 * mm, 61 * mm, "7", "Escala d'intervenció ecològica", "Per a què serveixen els nivells A-E?")
    draw_fitxa_process_rows(report, 84 * mm, 78.5 * mm, 49 * mm)
    report.para_fit(
        "E: gestió intensiva només per seguretat o risc funcional verificat. Els nivells A-E ordenen el grau mínim d'intervenció. És un criteri metodològic encara no assignat territorialment; no és una zonificació.",
        82.5 * mm,
        48 * mm,
        56.5 * mm,
        12.5 * mm,
        "tiny",
        6.0,
    )

    draw_fitxa_panel(report, 146 * mm, 35 * mm, 59 * mm, 61 * mm, "8", "Actuacions prioritàries", "Primeres decisions justificades")
    draw_fitxa_action_decisions(report, 149 * mm, 80 * mm, 51 * mm)

    # Bottom explanatory band.
    report.card(m, 18.5 * mm, 200 * mm, 14.5 * mm)
    c.setFillColor(GREEN_DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(105 * mm, 29.5 * mm, "PER QUÈ ÉS IMPORTANT AQUESTA FITXA?")
    band_texts = [
        "Resumeix valors, pressions i dades crítiques en una sola lectura.",
        "Escull el nivell mínim d'intervenció que recupera el procés ecològic.",
        "Evita conclusions fortes quan la informació ecològica és insuficient.",
        "Vincula cada mesura a un indicador, un llindar i una revisió.",
    ]
    x_text = 9 * mm
    for text in band_texts:
        c.setStrokeColor(LINE)
        c.line(x_text - 2 * mm, 20.5 * mm, x_text - 2 * mm, 27.8 * mm)
        report.para_fit(text, x_text, 27.2 * mm, 43 * mm, 8 * mm, "tiny", 6.0)
        x_text += 49 * mm

    draw_fitxa_footer(report, data, m, 1 * mm, 200 * mm)


def page_executive(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Resum executiu", "Lectura integrada per a gestió")
    diagnosis = data["diagnosis"]
    m = report.margin
    y = report.height - 50 * mm
    report.card(m, y - 48 * mm, 178 * mm, 42 * mm, "Diagnosi general")
    report.para(diagnosis.get("executive_summary", ""), m + 6 * mm, y - 17 * mm, 166 * mm, "body")
    y -= 60 * mm
    for title, key, fill in [
        ("Fortaleses", "strengths", GREEN_PALE),
        ("Debilitats", "weaknesses", CREAM),
        ("Pressions", "pressures", colors.HexColor("#FFF3D7")),
        ("Oportunitats", "opportunities", GREEN_PALE),
    ]:
        report.card(m, y - 38 * mm, 85 * mm, 34 * mm, title, fill=fill)
        items = diagnosis.get(key, [])[:2]
        text = diagnosis_items_text(items)
        report.para(text, m + 6 * mm, y - 18 * mm, 73 * mm, "small")
        m = report.margin + 93 * mm if m == report.margin else report.margin
        if m == report.margin:
            y -= 44 * mm
    report.footer()


def page_core(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Indicadors EcoRadar Radar", "Lectura de decisió, confiança i evidència")
    rows = [["Indicador", "Lectura", "Valor", "Categoria", "Confiança"]]
    for row in data["core"]:
        rows.append([
            row["name"],
            client_status(row["status"]),
            client_value(row.get("value_0_100") or row.get("normalized_value")),
            client_value(row["category"]),
            row["confidence"],
        ])
    draw_table(report, rows, report.margin, report.height - 50 * mm, [62 * mm, 25 * mm, 26 * mm, 34 * mm, 25 * mm], 6.4)
    m = report.margin
    report.card(m, 58 * mm, 178 * mm, 32 * mm, "Com s'ha de llegir aquesta taula")
    report.para(
        "Els valors numèrics provenen de dades ja processades. Els criteris qualitatius no substitueixen cap dada: indiquen quins blocs ja formen part de la metodologia i quines fonts oficials de contrast han d'afinar la decisió espacial.",
        m + 6 * mm,
        80 * mm,
        166 * mm,
        "small",
    )
    report.footer()


def page_chapter_overview(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Capítols de diagnosi temàtica", "Estructura de l'Informe de Diagnosi Ecològica Integrada")
    m = report.margin
    top = report.height - 50 * mm
    rows = [["Capítol", "Pregunta de gestió", "Indicadors principals", "Confiança"]]
    chapters = [
        ("Territorial", "Com s'organitza la matriu ecològica?", "CORE_01, CORE_02, CORE_08", "alta/mitjana"),
        ("Vegetació", "Quina estructura forestal i vegetal suggereixen les dades?", "CORE_01, CORE_03, CORE_09", "parcial"),
        ("Clima", "Què es pot dir de refugis i vulnerabilitat climàtica?", "CORE_03, CORE_04, CORE_05", "baixa/mitjana"),
        ("Hidrologia", "Quin paper té l'aigua en la funcionalitat ecològica?", "CORE_04, CORE_10, CORE_11", "mitjana"),
        ("Biodiversitat", "Quin coneixement biològic existeix i què cal validar?", "CORE_02, CORE_06", "alta amb cautela"),
        ("Connectivitat", "La matriu permet fluxos ecològics?", "CORE_01, CORE_08, CORE_10", "alta"),
        ("Pressió humana", "On hi pot haver solapament entre ús i conservació?", "CORE_07, CORE_12", "alta com a accessibilitat"),
        ("Foc", "Què condiciona la resiliència davant del foc?", "CORE_01, CORE_09, CORE_10", "parcial"),
        ("Restauració", "On hi ha oportunitat i quines dades falten?", "CORE_05, CORE_10, CORE_11", "mitjana"),
        ("Gestió", "Quines decisions es poden prioritzar?", "CORE_12 + recomanacions", "mitjana"),
    ]
    rows.extend([list(row) for row in chapters])
    report.card(m, top - 130 * mm, 178 * mm, 124 * mm, "Índex interpretatiu")
    draw_table(report, rows, m + 5 * mm, top - 16 * mm, [28 * mm, 64 * mm, 45 * mm, 31 * mm], 5.6)
    report.card(m, 38 * mm, 178 * mm, 46 * mm, "Criteri de lectura")
    report.para(
        "La Fitxa EcoRadar és la síntesi executiva definitiva. Cada capítol de l'informe respon una pregunta de gestió i justifica tècnicament les afirmacions de la Fitxa, separant les conclusions robustes de les provisionals.",
        m + 6 * mm,
        72 * mm,
        166 * mm,
        "small",
    )
    report.footer()


def page_module(report: Report, title: str, subtitle: str, map_name: str, metrics: list[tuple[str, str, str]], interpretation: str, implications: list[str]) -> None:
    report.new_page(title, subtitle)
    m = report.margin
    top = report.height - 50 * mm
    report.card(m, top - 94 * mm, 178 * mm, 88 * mm, "Mapa interpretatiu")
    map_path = MAPS / map_name
    if not map_path.exists() and map_name.startswith("mapa_"):
        kind = map_name.removeprefix("mapa_").removesuffix(".png")
        for suffix in (f"_{PROJECT_SLUG}", "_alinya"):
            if kind.endswith(suffix):
                kind = kind[: -len(suffix)]
                break
        map_path = project_map_path(kind)
    draw_image(report, map_path, m + 5 * mm, top - 88 * mm, 168 * mm, 70 * mm)
    y = top - 122 * mm
    for i, (label, value, unit) in enumerate(metrics):
        report.metric_card(m + i * 44 * mm, y, 40 * mm, label, value, unit)
    report.card(m, 38 * mm, 84 * mm, 62 * mm, "Què significa ecològicament?")
    report.para(interpretation, m + 6 * mm, 88 * mm, 72 * mm, "body")
    report.card(m + 92 * mm, 38 * mm, 86 * mm, 62 * mm, "Criteris de decisió")
    draw_numbered_actions(report, implications, m + 98 * mm, 88 * mm, 74 * mm)
    report.footer()


def page_soil_land_use(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Estat i usos del sòl", "Com s'organitza la matriu territorial?")
    m = report.margin
    top = report.height - 50 * mm
    report.card(m, top - 88 * mm, 108 * mm, 82 * mm, "Mapa de cobertes i mosaic")
    draw_image(report, project_map_path("paisatge"), m + 4 * mm, top - 82 * mm, 100 * mm, 65 * mm)
    report.card(m + 114 * mm, top - 88 * mm, 64 * mm, 82 * mm, "Cobertes dominants")
    rows = [["Coberta", "ha", "%"]]
    for row in top_rows(data["cover"], "superficie_ha", 6):
        rows.append([row["tipus_coberta"][:42], fmt(row["superficie_ha"], 1), fmt(row["percentatge_total"], 1, "%")])
    draw_table(report, rows, m + 119 * mm, top - 16 * mm, [32 * mm, 14 * mm, 12 * mm], 4.9)

    conreus_hab = rows_sum(data["habitats"], "superficie_ha", "conreus", "frui")
    pastures_hab = rows_sum(data["habitats"], "superficie_ha", "pastura")
    report.metric_card(m, 104 * mm, 40 * mm, "forestal", fmt(metric(data["basic"], "percentatge_coberta_forestal"), 1, "%"), "cobertes")
    report.metric_card(m + 45 * mm, 104 * mm, 40 * mm, "prats/herbassars", fmt(metric(data["basic"], "percentatge_prats_pastures_herbassars"), 1, "%"), "cobertes")
    report.metric_card(m + 90 * mm, 104 * mm, 40 * mm, "conreus", fmt(conreus_hab, 1), "ha habitats")
    report.metric_card(m + 135 * mm, 104 * mm, 40 * mm, "pastura", fmt(pastures_hab, 1), "ha habitats")

    report.card(m, 38 * mm, 84 * mm, 54 * mm, "Interpretació")
    report.para(
        "La lectura del sòl mostra una muntanya clarament forestal, amb espais oberts escassos però funcionals. Els conreus detectats per hàbitats són més amplis que la classe agrícola de cobertes, cosa que indica que per decisions agràries cal incorporar SIGPAC/DUN abans de quantificar ús ramader o subvencions.",
        m + 6 * mm,
        82 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 38 * mm, 86 * mm, 54 * mm, "Criteris de gestió")
    draw_numbered_actions(
        report,
        [
            "Conservar discontinuïtats i espais oberts com a part de la funcionalitat ecològica.",
            "No deduir ramaderia real sense dades SIGPAC/DUN o validació de camp.",
            "Creuar usos agraris amb hàbitats abans de proposar actuacions.",
        ],
        m + 98 * mm,
        82 * mm,
        74 * mm,
    )
    report.footer()


def page_forest_vegetation(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Vegetació i massa forestal", "Quina estructura forestal suggereixen les dades actuals?")
    m = report.margin
    top = report.height - 50 * mm
    forest_cover = [
        row for row in data["cover"]
        if "Bosc" in row.get("tipus_coberta", "") or "Boscos" in row.get("tipus_coberta", "")
    ]
    rows = [["Tipus de massa/coberta", "ha", "%"]]
    for row in top_rows(forest_cover, "superficie_ha", 7):
        rows.append([row["tipus_coberta"][:60], fmt(row["superficie_ha"], 1), fmt(row["percentatge_total"], 1, "%")])
    report.card(m, top - 88 * mm, 178 * mm, 82 * mm, "Masses forestals segons cobertes ICGC")
    draw_table(report, rows, m + 6 * mm, top - 17 * mm, [102 * mm, 30 * mm, 28 * mm], 6.0)

    boscos_hab = rows_sum(data["habitats"], "superficie_ha", "boscos", "pinedes", "carrascars")
    matollars_hab = rows_sum(data["habitats"], "superficie_ha", "matollars", "boixedes", "brolles", "garrigues")
    prats_hab = rows_sum(data["habitats"], "superficie_ha", "prats")
    report.metric_card(m, 104 * mm, 40 * mm, "boscos", fmt(boscos_hab, 0), "ha habitats")
    report.metric_card(m + 45 * mm, 104 * mm, 40 * mm, "matollars", fmt(matollars_hab, 0), "ha habitats")
    report.metric_card(m + 90 * mm, 104 * mm, 40 * mm, "prats", fmt(prats_hab, 0), "ha habitats")
    report.metric_card(m + 135 * mm, 104 * mm, 40 * mm, "foc Radar", fmt(core_metric(data["core"], "CORE_09"), 1), "0-100")

    report.card(m, 38 * mm, 84 * mm, 54 * mm, "Lectura ecològica")
    report.para(
        "La massa forestal és extensa i dominada per aciculifolis densos i clars. Això pot sostenir hàbitats forestals rellevants, però també obliga a entendre discontinuïtats, humitat i pendent abans de parlar de resiliència al foc.",
        m + 6 * mm,
        82 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 38 * mm, 86 * mm, 54 * mm, "Decisions que desbloqueja")
    draw_numbered_actions(
        report,
        [
            "Incorporar inventari forestal/estructura abans de prescriure aclarides.",
            "Localitzar prats i matollars funcionals per mantenir mosaic.",
            "Creuar massa forestal amb pendent, orientació i NDMI abans de prioritzar foc.",
        ],
        m + 98 * mm,
        82 * mm,
        74 * mm,
    )
    report.footer()


def page_biodiversity_detail(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Fauna, flora i biodiversitat coneguda", "Què sabem i què cal validar?")
    m = report.margin
    top = report.height - 50 * mm
    report.card(m, top - 82 * mm, 72 * mm, 76 * mm, "Mapa de registres")
    draw_image(report, project_map_path("biodiversitat"), m + 4 * mm, top - 76 * mm, 64 * mm, 58 * mm)
    report.card(m + 78 * mm, top - 82 * mm, 100 * mm, 76 * mm, "Grups principals")
    rows = [["Grup", "Reg.", "Taxons", "Recent", "Font"]]
    for row in data["biodiv"][:8]:
        rows.append([row["grup_taxonomic"], row["nombre_registres"], row["nombre_especies"], row["registres_recents"], row["font_principal"]])
    draw_table(report, rows, m + 83 * mm, top - 17 * mm, [25 * mm, 14 * mm, 15 * mm, 16 * mm, 22 * mm], 5.5)

    report.card(m, 101 * mm, 178 * mm, 38 * mm, "Espècies/taxons més citats a les dades disponibles")
    species_rows = [["Taxó", "Grup", "Font", "Reg."]]
    for row in data["top_species"][:6]:
        species_rows.append([row["scientificName"][:62], row["taxonGroup"], row["source"], row["records"]])
    draw_table(report, species_rows, m + 6 * mm, 131 * mm, [93 * mm, 24 * mm, 24 * mm, 16 * mm], 5.6)

    report.card(m, 38 * mm, 84 * mm, 50 * mm, "Interpretació")
    report.para(
        "GBIF i iNaturalist aporten una base pública consistent: plantes, ocells i insectes concentren bona part del coneixement. Aquest patró reflecteix presència observada i també esforç d'observació; no permet afirmar absències.",
        m + 6 * mm,
        78 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 38 * mm, 86 * mm, 50 * mm, "Fonts faunístiques")
    report.para(
        "GBIF i iNaturalist estan integrats. Ornitho/BDBC i dades pròpies s'han de tractar com a font complementària amb autorització o import manual; EcoRadar no fa scraping ni substitueix aquestes dades.",
        m + 98 * mm,
        78 * mm,
        74 * mm,
        "small",
    )
    report.footer()


def page_water_access_pressure(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Aigua, accessibilitat i pressió humana", "On poden aparèixer tensions de gestió?")
    m = report.margin
    top = report.height - 50 * mm
    report.card(m, top - 90 * mm, 100 * mm, 84 * mm, "Mapa d'accessibilitat potencial")
    draw_image(report, project_map_path("pressio_humana"), m + 4 * mm, top - 84 * mm, 92 * mm, 66 * mm)
    report.card(m + 106 * mm, top - 90 * mm, 72 * mm, 84 * mm, "Indicadors disponibles")
    report.metric_card(m + 112 * mm, top - 46 * mm, 30 * mm, "xarxa", fmt(pressure_metric(data["pressure"], "osm_path_track_road_km"), 1), "km")
    report.metric_card(m + 146 * mm, top - 46 * mm, 26 * mm, "punts", pressure_metric(data["pressure"], "osm_recreational_point_features"), "ús públic")
    report.metric_card(m + 112 * mm, top - 72 * mm, 30 * mm, "densitat", fmt(pressure_metric(data["pressure"], "osm_path_track_road_density"), 2), "km/km2")
    report.metric_card(m + 146 * mm, top - 72 * mm, 26 * mm, "aigua", fmt(cover_metric_by_text(data["cover"], "Cursos d'aigua"), 1), "ha cursos")
    report.para(
        "Els cursos d'aigua detectats per cobertes són una senyal mínima; punts d'aigua, fonts, basses i ACA no estan encara integrats com a capa funcional.",
        m + 112 * mm,
        top - 78 * mm,
        58 * mm,
        "tiny",
    )

    report.card(m, 38 * mm, 84 * mm, 58 * mm, "Interpretació")
    report.para(
        "La pressió humana actual és una lectura d'accessibilitat, no de freqüentació real. Tot i així, 124,8 km de camins/pistes i 18 punts d'ús públic ja permeten identificar àrees on cal verificar concentració de visitants i compatibilitat amb hàbitats sensibles.",
        m + 6 * mm,
        84 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 38 * mm, 86 * mm, 58 * mm, "Decisions")
    draw_numbered_actions(
        report,
        [
            "Validar punts d'aigua i accessos principals al camp.",
            "No estimar visitants sense comptadors, gestors o fonts autoritzades.",
            "Creuar accessos amb HIC i biodiversitat abans de regular ús públic.",
        ],
        m + 98 * mm,
        84 * mm,
        74 * mm,
    )
    report.footer()


def page_climate_diagnosis(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Clima, refugis i vulnerabilitat", "Què es pot concloure sense sobreinterpretar les dades?")
    m = report.margin
    top = report.height - 50 * mm
    rows = [["Indicador", "Valor", "Estat", "Fonts pendents"]]
    for code, label in [
        ("CORE_03", "Estat de la vegetació"),
        ("CORE_04", "Refugis climàtics"),
        ("CORE_05", "Vulnerabilitat climàtica"),
    ]:
        core = core_row(data["core"], code)
        complete = indicator_completeness(data, code)
        rows.append([
            label,
            client_value(core.get("value_0_100") or core.get("normalized_value")),
            core.get("status", ""),
            ", ".join(complete.get("missing_sources", [])[:5]),
        ])
    report.card(m, top - 76 * mm, 178 * mm, 70 * mm, "Estat de la lectura climàtica")
    draw_table(report, rows, m + 6 * mm, top - 17 * mm, [42 * mm, 24 * mm, 28 * mm, 76 * mm], 5.7)
    report.card(m, 98 * mm, 84 * mm, 52 * mm, "Interpretació")
    report.para(
        "El relleu, l'orientació, les cobertes i la hidrologia permeten una lectura preliminar de refugis i vulnerabilitat, però l'estat climàtic i fisiològic de la vegetació no es pot tancar sense NDVI, NDMI, NDWI, LST i clima validat.",
        m + 6 * mm,
        140 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 98 * mm, 86 * mm, 52 * mm, "Decisió de gestió")
    draw_numbered_actions(
        report,
        [
            "Tractar refugis i vulnerabilitat com a hipòtesi de treball, no com a zonificació final.",
            "Prioritzar credencials Copernicus i clima abans de decisions climàtiques fortes.",
            "Validar zones obagues, punts d'aigua i vegetació aparentment resilient al camp.",
        ],
        m + 98 * mm,
        140 * mm,
        74 * mm,
    )
    report.card(m, 38 * mm, 178 * mm, 38 * mm, "Conclusió del capítol")
    report.para(
        "La diagnosi climàtica és útil per orientar el treball pendent, però encara no per delimitar actuacions finals d'adaptació climàtica o restauració climàtica.",
        m + 6 * mm,
        64 * mm,
        166 * mm,
        "small",
    )
    report.footer()


def page_hydrology_diagnosis(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Hidrologia i funcionalitat hídrica", "Cursos, fonts i punts d'aigua com a estructura ecològica")
    m = report.margin
    top = report.height - 50 * mm
    rows = [["Element", "Entitats", "Longitud", "Comentari"]]
    for layer in ["rius_aca_che", "eixos_drenatge", "fonts", "preses_basses", "zones_humides_estanys"]:
        for row in data["hydrology"]:
            if row.get("layer_id") == layer:
                rows.append([
                    row.get("description", row.get("layer_id", ""))[:34],
                    row.get("feature_count", "0"),
                    fmt(row.get("length_km"), 2),
                    row.get("theme", ""),
                ])
                break
    report.card(m, top - 82 * mm, 178 * mm, 76 * mm, "Base hidrològica disponible")
    draw_table(report, rows, m + 6 * mm, top - 17 * mm, [54 * mm, 22 * mm, 28 * mm, 58 * mm], 5.8)
    report.metric_card(m, 103 * mm, 40 * mm, "rius/drenatge", fmt((num(row_value(data["hydrology"], "layer_id", "rius_aca_che", "length_km")) or 0) + (num(row_value(data["hydrology"], "layer_id", "eixos_drenatge", "length_km")) or 0), 2), "km")
    report.metric_card(m + 45 * mm, 103 * mm, 40 * mm, "fonts", row_value(data["hydrology"], "layer_id", "fonts", "feature_count") or "0", "punts")
    report.metric_card(m + 90 * mm, 103 * mm, 40 * mm, "Radar aigua", fmt(core_metric(data["core"], "CORE_10"), 1), "0-100")
    report.metric_card(m + 135 * mm, 103 * mm, 40 * mm, "refugis", fmt(core_metric(data["core"], "CORE_04"), 1), "0-100")
    report.card(m, 38 * mm, 84 * mm, 50 * mm, "Interpretació")
    report.para(
        "La cartografia mostra cursos i fonts, però no descriu per si sola temporalitat, qualitat ecològica ni ús per fauna. La funcionalitat hídrica queda parcial fins incorporar NDWI, basses i verificació de camp.",
        m + 6 * mm,
        78 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 38 * mm, 86 * mm, 50 * mm, "Decisions")
    draw_numbered_actions(
        report,
        [
            "Verificar fonts i punts d'aigua com a refugis i punts sensibles.",
            "No inferir estat ecològic només amb geometria de cursos.",
            "Creuar aigua amb biodiversitat i ús públic abans d'actuar.",
        ],
        m + 98 * mm,
        78 * mm,
        74 * mm,
    )
    report.footer()


def page_connectivity_diagnosis(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Connectivitat ecològica", "Matriu, corredors i barreres potencials")
    m = report.margin
    top = report.height - 50 * mm
    rows = [["Capa", "Entitats", "ha", "km"]]
    for row in data["connectivity"]:
        rows.append([
            row.get("theme", row.get("layer_id", ""))[:42],
            row.get("feature_count", "0"),
            fmt(row.get("area_ha"), 1),
            fmt(row.get("length_km"), 1),
        ])
    report.card(m, top - 88 * mm, 178 * mm, 82 * mm, "Capes de connectivitat disponibles")
    draw_table(report, rows[:7], m + 6 * mm, top - 17 * mm, [74 * mm, 22 * mm, 30 * mm, 30 * mm], 5.8)
    report.metric_card(m, 103 * mm, 40 * mm, "Radar connect.", fmt(core_metric(data["core"], "CORE_08"), 1), "0-100")
    report.metric_card(m + 45 * mm, 103 * mm, 40 * mm, "connectors", fmt(row_value(data["connectivity"], "layer_id", "connectors_terrestres_principals", "area_ha"), 1), "ha")
    report.metric_card(m + 90 * mm, 103 * mm, 40 * mm, "mosaic", fmt(core_metric(data["core"], "CORE_01"), 1), "0-100")
    report.metric_card(m + 135 * mm, 103 * mm, 40 * mm, "pressió", fmt(core_metric(data["core"], "CORE_07"), 1), "0-100")
    report.card(m, 38 * mm, 84 * mm, 50 * mm, "Interpretació")
    report.para(
        "La connectivitat és alta perquè la matriu natural, els hàbitats i els connectors oficials mantenen continuïtat territorial. Tot i així, la permeabilitat real pot variar segons espècie, barreres locals i intensitat d'ús.",
        m + 6 * mm,
        78 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 38 * mm, 86 * mm, 50 * mm, "Decisions")
    draw_numbered_actions(
        report,
        [
            "Evitar noves barreres en connectors i matriu natural.",
            "Validar punts de pas i friccions locals abans de projectes.",
            "Relacionar corredors amb aigua, hàbitats i pressió humana.",
        ],
        m + 98 * mm,
        78 * mm,
        74 * mm,
    )
    report.footer()


def page_human_pressure_diagnosis(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Pressió humana i ús públic", "Accessibilitat potencial, no freqüentació real")
    m = report.margin
    top = report.height - 50 * mm
    report.card(m, top - 90 * mm, 100 * mm, 84 * mm, "Mapa d'accessibilitat potencial")
    draw_image(report, project_map_path("pressio_humana"), m + 4 * mm, top - 84 * mm, 92 * mm, 66 * mm)
    report.card(m + 106 * mm, top - 90 * mm, 72 * mm, 84 * mm, "Lectura d'ús públic")
    report.metric_card(m + 112 * mm, top - 46 * mm, 30 * mm, "xarxa", fmt(pressure_metric(data["pressure"], "osm_path_track_road_km"), 1), "km")
    report.metric_card(m + 146 * mm, top - 46 * mm, 26 * mm, "punts", pressure_metric(data["pressure"], "osm_recreational_point_features"), "ús públic")
    report.metric_card(m + 112 * mm, top - 72 * mm, 30 * mm, "densitat", fmt(pressure_metric(data["pressure"], "osm_path_track_road_density"), 2), "km/km2")
    report.metric_card(m + 146 * mm, top - 72 * mm, 26 * mm, "Radar", fmt(core_metric(data["core"], "CORE_07"), 1), "0-100")
    report.card(m, 38 * mm, 84 * mm, 58 * mm, "Interpretació")
    report.para(
        "OpenStreetMap permet estimar accessibilitat i punts potencials d'ús públic. No mesura freqüentació, estacionalitat ni conflictes reals. Per tant, aquest capítol identifica on mirar, no on regular automàticament.",
        m + 6 * mm,
        84 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 38 * mm, 86 * mm, 58 * mm, "Decisions")
    draw_numbered_actions(
        report,
        [
            "Validar accessos i punts de concentració amb gestors o camp.",
            "Creuar camins amb HIC i biodiversitat abans de limitar usos.",
            "Usar Strava només si la compatibilitat legal està resolta.",
        ],
        m + 98 * mm,
        84 * mm,
        74 * mm,
    )
    report.footer()


def page_fire_climate_gaps(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Foc, clima i dades crítiques", "Quines capes falten per decidir amb seguretat?")
    m = report.margin
    top = report.height - 50 * mm
    rows = [["Bloc", "Completesa", "Estat", "Fonts clau pendents"]]
    labels = {
        "CORE_03": "Vegetació",
        "CORE_04": "Refugis climàtics",
        "CORE_05": "Vulnerabilitat climàtica",
        "CORE_09": "Resiliència al foc",
        "CORE_10": "Aigua",
        "CORE_12": "Prioritat de gestió",
    }
    for code, label in labels.items():
        row = indicator_completeness(data, code)
        rows.append([label, f"{row.get('data_available_percent', 0)}%", row.get("status", "-"), ", ".join(row.get("missing_sources", [])[:4])])
    report.card(m, top - 78 * mm, 178 * mm, 72 * mm, "Completesa de blocs crítics")
    draw_table(report, rows, m + 6 * mm, top - 17 * mm, [34 * mm, 26 * mm, 28 * mm, 92 * mm], 5.7)

    report.card(m, 92 * mm, 84 * mm, 48 * mm, "Lectura de risc")
    report.para(
        "La diagnosi pot orientar prudència i treball de camp, però no ha de tancar prioritats finals de foc, clima, aigua o restauració fins incorporar Copernicus, DEM/MDT, hidrologia i històric d'incendis.",
        m + 6 * mm,
        130 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 92 * mm, 86 * mm, 48 * mm, "Camí per completar")
    draw_numbered_actions(
        report,
        [
            "Activar Copernicus per NDVI, NDMI, NDWI i LST.",
            "Integrar DEM/MDT per pendent, orientació i obagues.",
            "Afegir ACA i perímetres d'incendis abans de mapa final de prioritats.",
        ],
        m + 98 * mm,
        130 * mm,
        74 * mm,
    )
    report.card(m, 38 * mm, 178 * mm, 38 * mm, "Garantia metodològica")
    report.para(
        "Aquest informe no substitueix dades inexistents per estimacions. Les conclusions fortes es limiten als blocs amb evidència directa; la resta queda com a diagnosi parcial i full de ruta de dades.",
        m + 6 * mm,
        64 * mm,
        166 * mm,
        "small",
    )
    report.footer()


def page_recommendations(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Propostes d'actuació", "Recomanacions justificades per dades")
    m = report.margin
    y = report.height - 52 * mm
    for row in data["recommendations"][:5]:
        report.card(m, y - 30 * mm, 178 * mm, 26 * mm)
        c = report.c
        c.setFillColor(GREEN_DARK)
        c.circle(m + 8 * mm, y - 16 * mm, 5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(m + 8 * mm, y - 18.2 * mm, row["priority"])
        c.setFillColor(GREEN_DARK)
        c.setFont("Helvetica-Bold", 8.2)
        report.para(f"{plain(row['action_type']).upper()} - {plain(row['objective'])}", m + 17 * mm, y - 7 * mm, 112 * mm, "small")
        report.para(
            f"Justificació: {row['justification']} Benefici esperat: {row['expected_ecological_benefit']}",
            m + 17 * mm,
            y - 15 * mm,
            112 * mm,
            "small",
        )
        report.para(
            f"On actuar: {row['location']} Indicadors: {row['supporting_indicators']}. Confiança: {row['confidence']}.",
            m + 133 * mm,
            y - 11 * mm,
            39 * mm,
            "tiny",
        )
        y -= 33 * mm
    report.footer()


def page_restoration_management(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Restauració i prioritat de gestió", "De la diagnosi a la decisió")
    m = report.margin
    top = report.height - 50 * mm
    rows = [["Bloc", "Valor", "Estat", "Lectura"]]
    for code, label, reading in [
        ("CORE_11", "Potencial de restauració", "Oportunitats, no actuacions finals"),
        ("CORE_12", "Prioritat de gestió", "Síntesi parcial de decisions"),
        ("CORE_02", "Valor d'hàbitats", "Condiciona prudència"),
        ("CORE_07", "Pressió humana", "Accessibilitat potencial"),
    ]:
        core = core_row(data["core"], code)
        rows.append([
            label,
            client_value(core.get("value_0_100") or core.get("normalized_value")),
            core.get("status", ""),
            reading,
        ])
    report.card(m, top - 72 * mm, 178 * mm, 66 * mm, "Indicadors que condicionen la gestió")
    draw_table(report, rows, m + 6 * mm, top - 17 * mm, [48 * mm, 24 * mm, 30 * mm, 70 * mm], 5.8)
    report.card(m, 98 * mm, 84 * mm, 52 * mm, "Interpretació")
    report.para(
        "El potencial de restauració és una lectura de prioritat relativa, no una ordre d'intervenció. EcoRadar diferencia conservar valors coneguts, validar incerteses i actuar només quan la localització i el benefici ecològic estan justificats.",
        m + 6 * mm,
        140 * mm,
        72 * mm,
        "small",
    )
    report.card(m + 92 * mm, 98 * mm, 86 * mm, 52 * mm, "Criteri de gestió")
    draw_numbered_actions(
        report,
        [
            "Conservar primer on el valor d'hàbitats és alt.",
            "Restaurar només quan camp, vegetació, aigua i connectivitat ho confirmin.",
            "Convertir dades pendents en recomanacions de validació, no en actuacions finals.",
        ],
        m + 98 * mm,
        140 * mm,
        74 * mm,
    )
    report.card(m, 38 * mm, 178 * mm, 38 * mm, "Relació amb les recomanacions")
    report.para(
        "Les recomanacions del capítol següent deriven de la diagnosi i mantenen dependències explícites. Quan una dada crítica falta, EcoRadar prioritza completar informació o validar al camp abans d'executar actuacions.",
        m + 6 * mm,
        64 * mm,
        166 * mm,
        "small",
    )
    report.footer()


def page_roadmap(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Full de ruta i dades que canvien decisions", "Priorització segons valor per a la Fitxa i la seva justificació tècnica")
    rows = [["Prioritat", "Millora", "Capítol o síntesi afectada", "Decisió que desbloqueja"]]
    for row in data["fitxa_value"]:
        rows.append([row["priority"], row["title"], row["fitxa_section"], row["decision_unlocked"]])
    draw_table(report, rows, report.margin, report.height - 50 * mm, [16 * mm, 48 * mm, 48 * mm, 66 * mm], 6.1)
    report.footer()


def page_annex(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Traçabilitat de fonts", "Fonts oficials, evidència usada i capes de contrast")
    m = report.margin
    y = report.height - 50 * mm
    report.card(m, y - 42 * mm, 178 * mm, 36 * mm, "Principi de lectura")
    report.para(
        f"EcoRadar integra les fonts en tres nivells: evidència directa quan la dada ja s'ha processat per {project_display_name()}; font de contrast quan és oficial i definida metodològicament; font de context quan ajuda a interpretar gestió, protecció o governança. Cap valor numèric es substitueix per una simulació.",
        m + 6 * mm,
        y - 18 * mm,
        166 * mm,
        "body",
    )
    y -= 54 * mm
    rows = [["Bloc", "Font", "Paper en la diagnosi", "Decisió que aporta"]]
    for row in SOURCE_MATRIX:
        rows.append(list(row))
    draw_table(report, rows, m, y - 2 * mm, [31 * mm, 50 * mm, 38 * mm, 59 * mm], 5.6)
    report.footer()


def page_integrated_chapter(report: Report, chapter: dict[str, Any]) -> None:
    """Render one mandatory chapter of the Integrated Ecological Diagnosis Report."""

    report.new_page(f"{chapter['number']}. {chapter['title']}", chapter["subtitle"])
    m = report.margin
    top = report.height - 50 * mm

    report.card(m, top - 43 * mm, 84 * mm, 37 * mm, chapter.get("evidence_title", "Evidències per a la decisió"))
    evidence_text = " · ".join(chapter["data_used"])
    if chapter.get("result_note"):
        evidence_text = f"{evidence_text}. {chapter['result_note']}"
    report.para_fit(evidence_text, m + 5 * mm, top - 16 * mm, 74 * mm, 22 * mm, "tiny", 5.2)

    report.card(m + 92 * mm, top - 43 * mm, 86 * mm, 37 * mm, chapter.get("map_title", "Mapa per orientar la decisió"))
    draw_image(report, project_map_path(chapter["map_kind"]), m + 97 * mm, top - 34 * mm, 76 * mm, 18 * mm)
    report.para_fit(chapter["map_note"], m + 97 * mm, top - 37 * mm, 76 * mm, 7 * mm, "tiny", 5.1)

    report.card(m, 153 * mm, 178 * mm, 44 * mm, chapter.get("table_title", "Lectura per a la decisió"))
    rows = chapter.get("rows") or [["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"]]
    table_height = draw_table(
        report,
        rows,
        m + 5 * mm,
        188 * mm,
        chapter.get("widths", [48 * mm, 22 * mm, 27 * mm, 25 * mm, 48 * mm]),
        4.9,
    )
    if chapter.get("indicator_note"):
        report.para_fit(chapter["indicator_note"], m + 5 * mm, 187 * mm - table_height - 2 * mm, 166 * mm, 8 * mm, "tiny", 5.2)

    report.card(m, 92 * mm, 178 * mm, 55 * mm, chapter.get("interpretation_title", "Lectura ecològica"))
    report.para_fit(chapter["interpretation"], m + 5 * mm, 136 * mm, 168 * mm, 36 * mm, "small", 5.8)

    report.card(m, 31 * mm, 86 * mm, 55 * mm, chapter.get("limitations_title", "Fiabilitat de la decisió"))
    report.para_fit(
        f"Confiança: {chapter['confidence']}. {chapter['limitations']}",
        m + 5 * mm,
        75 * mm,
        76 * mm,
        34 * mm,
        "tiny",
        5.2,
    )

    report.card(m + 92 * mm, 31 * mm, 86 * mm, 55 * mm, chapter.get("decision_title", "DECISIÓ DE GESTIÓ"))
    decision_items = chapter["decision"] if "decision" in chapter else chapter["implications"]
    draw_numbered_actions(report, decision_items, m + 98 * mm, 74 * mm, 74 * mm)
    report.footer()


def management_report_blocks(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Group client-facing chapters by dominant ecological processes."""

    chapters = process_report_chapters(data)
    by_number = {chapter["number"]: chapter for chapter in chapters}

    def pick(*numbers: int) -> list[dict[str, Any]]:
        return [by_number[number] for number in numbers if number in by_number]

    return [
        {
            "number": 1,
            "prefix": "PROCÉS",
            "title": "TANCAMENT DEL PAISATGE I PÈRDUA DE MOSAIC FUNCIONAL",
            "question": "Procés dominant: la matriu forestal guanya pes i els espais oberts passen de ser superfície a ser funció ecològica crítica.",
            "map_kind": "paisatge",
            "synthesis": (
                "El procés estructurant d'Alinyà és el tancament progressiu del paisatge. No és un problema perquè hi hagi bosc, sinó perquè la pèrdua de contrast pot reduir ecotons, espais oberts, discontinuïtats de combustible, recursos tròfics i opcions de gestió. "
                "Aquest procés integra cobertes, hàbitats, biodiversitat, connectivitat, foc, restauració i decisions de gestió en una mateixa lectura."
            ),
            "progression": [
                "Detectar el domini forestal i la funció desproporcionada dels espais oberts.",
                "Relacionar mosaic, hàbitats, biodiversitat, foc i restauració en una sola cadena causal.",
                "Separar obertura útil, no-intervenció i gestió forestal selectiva.",
            ],
            "prepared_decisions": [
                "Mantenir espais oberts funcionals abans que desapareguin com a procés.",
                "No aplicar gestió forestal homogènia sobre una matriu ecològicament heterogènia.",
                "Fer que cada actuació sobre mosaic justifiqui biodiversitat, foc i hàbitats alhora.",
            ],
            "chapters": pick(1, 2),
            "labels": {
                "evidence": "Evidències del procés",
                "interpretation": "Com funciona ecològicament",
                "table": "Relació entre evidències i procés",
                "confidence": "Solidesa de la lectura",
                "action": "Decisions que exigeix",
            },
        },
        {
            "number": 2,
            "prefix": "PROCÉS",
            "title": "VALOR ECOLÒGIC CONCENTRAT EN HÀBITATS, ECOTONS I PUNTS SENSIBLES",
            "question": "Procés dominant: el valor no es reparteix de manera uniforme; es concentra en hàbitats d'interès, ecotons, punts d'aigua i zones de baixa pertorbació.",
            "map_kind": "habitats",
            "synthesis": (
                "El segon procés és la concentració de responsabilitat ecològica. Alinyà té valors extensos, però les decisions més sensibles es decideixen en punts concrets: HIC, hàbitats prioritaris, ecotons, aigua, zones tranquil·les i registres de biodiversitat. "
                "La gestió no pot tractar l'espai com una sola unitat; ha de treballar amb zones de prudència i filtres de no-perjudici."
            ),
            "progression": [
                "Identificar on el valor ecològic condiciona qualsevol actuació.",
                "Llegir biodiversitat pública com a senyal de valor i de biaix d'observació.",
                "Convertir hàbitats, aigua i ecotons en criteris de prudència.",
            ],
            "prepared_decisions": [
                "Conservar abans de transformar.",
                "Delimitar zones on no intervenir és també una decisió activa.",
                "Validar al camp només allò que pot canviar una decisió de gestió.",
            ],
            "chapters": pick(3, 4),
            "labels": {
                "evidence": "Valor concentrat",
                "interpretation": "Per què condiciona la gestió",
                "table": "Evidències integrades",
                "confidence": "Solidesa i prudència",
                "action": "Filtre de gestió",
            },
        },
        {
            "number": 3,
            "prefix": "PROCÉS",
            "title": "VULNERABILITAT DINÀMICA: VEGETACIÓ, AIGUA, CLIMA I FOC",
            "question": "Procés dominant: el funcionament futur dependrà de la resposta de la vegetació, la humitat, els refugis climàtics i la continuïtat del combustible.",
            "map_kind": "base",
            "synthesis": (
                "El tercer procés no es veu completament en una capa estàtica. Depèn de variables dinàmiques: vigor vegetal, humitat, temperatura superficial, aigua funcional, orientació, pendent i combustible. "
                "Copernicus ja ha localitzat una escena d'estiu adequada; el pas crític és convertir aquesta evidència en índexs que permetin separar refugis, estrès, risc de foc i restauració realment necessària."
            ),
            "progression": [
                "Separar estructura vegetal de funcionament fisiològic.",
                "Relacionar refugis, aigua, humitat i foc en una mateixa vulnerabilitat.",
                "Evitar actuacions forestals o de restauració abans de conèixer la resposta dinàmica.",
            ],
            "prepared_decisions": [
                "No zonificar estrès ni refugis només amb cobertes.",
                "Tractar obagues, fonts i masses humides com a infraestructura climàtica provisional.",
                "Fer que la prevenció del foc reforci mosaic i biodiversitat, no només combustible.",
            ],
            "chapters": pick(5, 6),
            "labels": {
                "evidence": "Senyals dinàmics",
                "interpretation": "Com canvia el funcionament",
                "table": "Variables que governen el procés",
                "confidence": "Què permet decidir ara",
                "action": "Decisions condicionades",
            },
        },
        {
            "number": 4,
            "prefix": "PROCÉS",
            "title": "PRESSIÓ HUMANA, CONNECTIVITAT I GOVERNANÇA ADAPTATIVA",
            "question": "Procés dominant: l'accessibilitat, la connectivitat i la capacitat de decisió determinaran si els valors actuals es mantenen o es degraden.",
            "map_kind": "pressio_humana",
            "synthesis": (
                "El quart procés és de governança ecològica: els camins, punts d'accés, corredors, zones sensibles i mancances de camp han de convertir-se en una manera de decidir. "
                "La pressió humana no es pot reduir a quilòmetres de camí, però l'accessibilitat ja indica on cal mirar primer per evitar conflictes entre ús públic, fauna, aigua, hàbitats i restauració."
            ),
            "progression": [
                "Relacionar accessibilitat, connectivitat i punts sensibles.",
                "Convertir restauració i priorització en decisions condicionades per processos.",
                "Organitzar el treball de camp i el full de ruta al voltant de decisions, no de dades disperses.",
            ],
            "prepared_decisions": [
                "Ordenar ús públic allà on pugui afectar hàbitats, aigua o tranquil·litat.",
                "Restaurar només funcions debilitades, no superfícies sense diagnosi.",
                "Executar una gestió adaptativa: protegir, validar, actuar i revisar.",
            ],
            "chapters": pick(7, 8),
            "labels": {
                "evidence": "Pressió i governança",
                "interpretation": "Com condiciona decisions",
                "table": "Evidències i resposta",
                "confidence": "Condicions de decisió",
                "action": "Seqüència de gestió",
            },
        },
    ]


def process_report_chapters(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the client-facing report organized by ecological processes.

    Indicators are only evidence. The diagnosis is the process that links them.
    """

    forest_pct = fmt(metric(data["basic"], "percentatge_coberta_forestal"), 1, "%")
    grass_pct = fmt(metric(data["basic"], "percentatge_prats_pastures_herbassars"), 1, "%")
    agricultural_pct = fmt(metric(data["basic"], "percentatge_agricola"), 2, "%")
    artificial_pct = fmt(metric(data["basic"], "percentatge_urba_artificial"), 2, "%")
    habitats_count = metric(data["basic"], "nombre_habitats")
    hic_ha = fmt(metric(data["basic"], "superficie_hic"), 0)
    priority_hic = fmt(priority_habitat_surface(data["habitats"]), 0)
    species_count = metric(data["basic"], "nombre_especies_registrades")
    recent_records = metric(data["basic"], "nombre_registres_recents")
    road_km = fmt(pressure_metric(data["pressure"], "osm_path_track_road_km"), 1)
    public_points = metric(data["basic"], "nombre_accessos_punts_us_public") or pressure_metric(data["pressure"], "osm_recreational_point_features") or "0"
    hydrology_km = fmt((num(row_value(data["hydrology"], "layer_id", "rius_aca_che", "length_km")) or 0) + (num(row_value(data["hydrology"], "layer_id", "eixos_drenatge", "length_km")) or 0), 2)
    fonts_count = row_value(data["hydrology"], "layer_id", "fonts", "feature_count") or "0"
    mosaic_score = fmt(core_metric(data["core"], "CORE_01"), 1)
    habitat_score = fmt(core_metric(data["core"], "CORE_02"), 1)
    refuges_score = fmt(core_metric(data["core"], "CORE_04"), 1)
    vulnerability_score = fmt(core_metric(data["core"], "CORE_05"), 1)
    biodiversity_score = fmt(core_metric(data["core"], "CORE_06"), 1)
    pressure_score = fmt(core_metric(data["core"], "CORE_07"), 1)
    connectivity_score = fmt(core_metric(data["core"], "CORE_08"), 1)
    fire_score = fmt(core_metric(data["core"], "CORE_09"), 1)
    water_score = fmt(core_metric(data["core"], "CORE_10"), 1)
    restoration_score = fmt(core_metric(data["core"], "CORE_11"), 1)
    management_score = fmt(core_metric(data["core"], "CORE_12"), 1)
    forest_ha = fmt(rows_sum(data["cover"], "superficie_ha", "Bosc", "Boscos", text_key="tipus_coberta"), 0)
    scrub_ha = fmt(rows_sum(data["cover"], "superficie_ha", "Matollar", text_key="tipus_coberta"), 0)
    grass_ha = fmt(rows_sum(data["cover"], "superficie_ha", "Prats", "herbassars", text_key="tipus_coberta"), 0)
    copernicus_meta = data.get("teledeteccio", {})
    copernicus_capture = copernicus_meta.get("capture_date") or "data no identificada"
    copernicus_cloud = copernicus_meta.get("cloud_cover_percent")
    copernicus_cloud_text = fmt(copernicus_cloud, 1, "%") if copernicus_cloud is not None else "núvol no documentat"
    copernicus_scene_note = f"{copernicus_capture}, {copernicus_cloud_text} de núvols"
    top_groups = "; ".join(
        f"{plain(row.get('grup_taxonomic', ''))}: {row.get('nombre_especies', '')} taxons"
        for row in data["biodiv"][:3]
    )
    top_species_names = "; ".join(
        plain(row.get("scientificName", "")).split("(")[0].strip()
        for row in data.get("top_species", [])[:3]
    )

    def common_labels(chapter: dict[str, Any]) -> dict[str, Any]:
        chapter.setdefault("evidence_title", "Evidències integrades")
        chapter.setdefault("map_title", "Expressió territorial")
        chapter.setdefault("table_title", "Com les evidències construeixen el procés")
        chapter.setdefault("interpretation_title", "Lectura ecològica del procés")
        chapter.setdefault("limitations_title", "Confiança i prudència")
        chapter.setdefault("decision_title", "DECISIÓ DE GESTIÓ")
        return chapter

    return [
        common_labels({
            "number": 1,
            "title": "La matriu forestal està absorbint el mosaic funcional",
            "subtitle": "Procés de tancament, pèrdua de contrast i paper crític dels espais oberts",
            "data_used": [
                f"{forest_pct} de coberta forestal",
                f"{grass_pct} de prats i herbassars",
                f"mosaic {mosaic_score}/100",
                f"connectivitat {connectivity_score}/100",
                f"resiliència al foc {fire_score}/100",
            ],
            "result_note": (
                "El procés principal no és la presència de bosc, sinó la possible pèrdua de contrast funcional dins una matriu molt forestal."
            ),
            "map_kind": "paisatge",
            "map_note": "El mapa mostra la matriu forestal i les discontinuïtats que encara estructuren el mosaic.",
            "rows": [
                ["Evidència", "Resultat", "Funció ecològica", "Decisió"],
                ["Bosc", forest_pct, "matriu, refugi i continuïtat", "gestionar estructura"],
                ["Prats/herbassars", grass_pct, "llum, aliment, ecotons i discontinuïtat", "mantenir peces clau"],
                ["Mosaic", f"{mosaic_score}/100", "diversitat funcional", "evitar homogeneïtzació"],
                ["Foc/restauració", f"{fire_score}/100 / {restoration_score}/100", "risc i oportunitat lligats", "actuar selectivament"],
            ],
            "widths": [32 * mm, 30 * mm, 68 * mm, 40 * mm],
            "interpretation": (
                "Alinyà funciona com un sistema de muntanya on el bosc dona continuïtat, ombra, sòl i refugi, però on els espais oberts sostenen funcions que no es poden substituir fàcilment: floració, recursos per pol·linitzadors, zones de caça, discontinuïtats de combustible, ecotons i punts de transició entre hàbitats. "
                "El tancament del paisatge pot semblar una evolució natural positiva si només es mira l'augment de coberta vegetal. Ecològicament, però, el risc és que la matriu guanyi uniformitat i perdi heterogeneïtat. Aquesta homogeneïtzació reduiria opcions per a espècies d'espais oberts, faria menys llegible el mosaic agroforestal i concentraria la gestió del foc en un territori més continu. "
                "Per això el procés integra cobertes, hàbitats, biodiversitat, connectivitat, foc i restauració: mantenir mosaic no és una actuació estètica, és conservar el mecanisme que reparteix funcions."
            ),
            "limitations": (
                "La lectura és robusta per estructura i cobertes, però la causa precisa del tancament - abandonament ramader, successió, gestió forestal o condicions locals - requereix camp i informació d'ús agrari."
            ),
            "confidence": "alta per estructura; mitjana per causa",
            "confidence_note": "La confiança és alta perquè diverses fonts coincideixen en el patró; baixa lleugerament quan la decisió depèn de la causa del canvi.",
            "decision": [
                "Mantenir una xarxa d'espais oberts funcionals abans que el tancament elimini ecotons i discontinuïtats útils.",
                "Evitar actuacions forestals homogènies: cada intervenció ha de demostrar benefici per mosaic, hàbitats i foc.",
                "Validar quins prats, clarianes i marges són actius, recuperables o millor deixats a evolució natural.",
            ],
        }),
        common_labels({
            "number": 2,
            "title": "Els espais oberts han passat de superfície marginal a infraestructura ecològica",
            "subtitle": "Ecotons, prats, herbassars, gestió tradicional i restauració funcional",
            "data_used": [
                f"{grass_ha} ha de prats/herbassars",
                f"{agricultural_pct} agrícola cartogràfic",
                f"{habitats_count} hàbitats",
                f"potencial de restauració {restoration_score}/100",
            ],
            "result_note": "Els espais oberts són escassos en proporció, però tenen un pes funcional superior a la seva superfície.",
            "map_kind": "paisatge",
            "map_note": "La lectura útil no és quanta superfície oberta hi ha, sinó on sosté ecotons, hàbitats i discontinuïtats.",
            "rows": [
                ["Peça del procés", "Resultat", "Conseqüència", "Gestió"],
                ["Prats/herbassars", f"{grass_ha} ha", "funció desproporcionada", "mantenir qualitat"],
                ["Agrícola", agricultural_pct, "ús real encara incert", "contrastar gestió"],
                ["Hàbitats", habitats_count, "resposta diferent per unitat", "evitar recepta única"],
                ["Restauració", f"{restoration_score}/100", "oportunitat condicionada", "recuperar funcions"],
            ],
            "widths": [34 * mm, 30 * mm, 60 * mm, 46 * mm],
            "interpretation": (
                "La gestió dels espais oberts no s'ha de plantejar com una oposició entre bosc i prat. El procés real és més fi: alguns espais oberts són peces clau perquè connecten hàbitats, mantenen floració, faciliten moviments de fauna, trenquen continuïtats forestals i conserven memòria de gestió tradicional. Altres poden ser espais degradats, abandonats o de baixa prioritat. "
                "Aquesta diferència és la que ha d'orientar la restauració. Obrir superfície sense criteri pot empobrir hàbitats sensibles; no actuar pot deixar perdre ecotons que mantenen biodiversitat. La restauració bona és selectiva: identifica funcions debilitades i actua només on la intervenció les recupera sense perjudicar valors existents."
            ),
            "limitations": (
                "Sense SIGPAC/DUN, dades de gestió ramadera i verificació de camp, no es pot distingir amb prou detall quins espais oberts són mantinguts activament i quins estan en regressió."
            ),
            "confidence": "mitjana-alta",
            "confidence_note": "L'evidència espacial és clara, però la decisió concreta depèn de saber quin procés manté cada espai obert.",
            "decision": [
                "Prioritzar espais oberts que connectin HIC, punts d'aigua, ecotons i discontinuïtats forestals.",
                "No recuperar superfície oberta de manera indiscriminada: cada actuació ha de justificar quina funció ecològica recupera.",
                "Fer del manteniment del mosaic una actuació recurrent, no una intervenció puntual.",
            ],
        }),
        common_labels({
            "number": 3,
            "title": "El valor ecològic es concentra en hàbitats sensibles i ecotons",
            "subtitle": "HIC, hàbitats prioritaris, biodiversitat i zones de no-perjudici",
            "data_used": [
                f"{hic_ha} ha d'hàbitats d'interès comunitari",
                f"{priority_hic} ha d'hàbitats prioritaris",
                f"valor d'hàbitats {habitat_score}/100",
                f"{species_count} taxons citats",
            ],
            "result_note": "El valor d'hàbitats és molt alt i converteix la prudència en una decisió de gestió, no en una limitació.",
            "map_kind": "habitats",
            "map_note": "El mapa situa els hàbitats que han de funcionar com a filtre previ d'actuació.",
            "rows": [
                ["Evidència", "Resultat", "Lectura ecològica", "Criteri"],
                ["HIC", f"{hic_ha} ha", "responsabilitat de conservació", "filtre previ"],
                ["Prioritaris", f"{priority_hic} ha", "risc de pèrdua singular", "camp obligatori"],
                ["Biodiversitat", f"{species_count} taxons", "valor conegut i biaix d'observació", "validar sensibles"],
                ["Ecotons", "associats al mosaic", "transició funcional", "gestió fina"],
            ],
            "widths": [30 * mm, 34 * mm, 68 * mm, 38 * mm],
            "interpretation": (
                "La diagnosi mostra que Alinyà no pot gestionar-se com una superfície homogènia. El valor ecològic es concentra en hàbitats d'interès, hàbitats prioritaris, ecotons i punts on la biodiversitat coneguda assenyala una responsabilitat de conservació. Aquest procés obliga a canviar el criteri de gestió: abans de preguntar què es pot fer, cal preguntar què no es pot deteriorar. "
                "Això és especialment important perquè els processos del primer bloc - tancament, restauració i gestió forestal - poden tenir efectes oposats segons l'hàbitat afectat. Una actuació que manté mosaic en un lloc pot degradar un hàbitat sensible en un altre. La gestió professional ha de començar amb una capa de no-perjudici."
            ),
            "limitations": (
                "La cartografia dona distribució i responsabilitat, però no estat local de conservació. La qualitat real de cada polígon necessita camp."
            ),
            "confidence": "alta a escala cartogràfica; mitjana per estat local",
            "confidence_note": "Alta vol dir que la presència i extensió són defensables; mitjana recorda que l'estat del polígon pot canviar la decisió.",
            "decision": [
                "Aplicar HIC, hàbitats prioritaris, ecotons i punts d'aigua com a filtre de no-perjudici.",
                "No executar restauració, ús públic o gestió forestal en zones sensibles sense validació local.",
                "Crear una jerarquia de prudència: conservar, actuar amb condicions o intervenir només si el benefici és clar.",
            ],
        }),
        common_labels({
            "number": 4,
            "title": "El coneixement de biodiversitat indica valor, però també biaix d'observació",
            "subtitle": "Registres públics, grups taxonòmics, espècies potencialment sensibles i necessitat de camp",
            "data_used": [
                f"{species_count} taxons registrats",
                f"{recent_records} registres recents",
                top_groups or "grups taxonòmics principals no resumits",
                top_species_names or "espècies principals no resumides",
            ],
            "result_note": "La biodiversitat coneguda reforça el valor de l'espai, però no equival a inventari complet.",
            "map_kind": "biodiversitat",
            "map_note": "El mapa mostra concentració d'observacions i també possibles buits d'esforç de mostreig.",
            "rows": [
                ["Evidència", "Resultat", "Què significa", "Ús correcte"],
                ["Taxons", species_count, "coneixement públic elevat", "senyal de valor"],
                ["Recents", recent_records, "activitat biològica actual probable", "validar sensibles"],
                ["Grups", top_groups[:48] or "no resumit", "esforç desigual", "no confondre amb absència"],
                ["Camp", "pendent", "qualitat i presència actual", "prioritzar buits"],
            ],
            "widths": [28 * mm, 36 * mm, 62 * mm, 44 * mm],
            "interpretation": (
                "Les dades públiques de biodiversitat fan dues coses alhora. Primer, confirmen que Alinyà és un espai amb interès biològic alt i amb activitat natural registrada. Segon, mostren que el coneixement no és neutre: depèn d'on observa la gent, de quins grups es miren més i de quines zones són accessibles. "
                "Això condiciona la diagnosi perquè una zona amb poques cites no és necessàriament una zona pobra, i una zona amb moltes cites pot reflectir més esforç d'observació que més biodiversitat real. El valor gestor és identificar buits crítics: espais oberts, punts d'aigua, HIC prioritaris, zones tranquil·les i sectors on una actuació podria afectar espècies no detectades."
            ),
            "limitations": (
                "Les fonts públiques són oportunistes i no substitueixen inventaris específics d'espècies protegides, amenaçades, invasores o indicadores."
            ),
            "confidence": "alta per coneixement disponible; mitjana per estat real de comunitats",
            "confidence_note": "La dada és útil per orientar prudència, però no per descartar presències ni absències.",
            "decision": [
                "Tractar les cites com a senyal de valor i els buits com a prioritat de mostreig.",
                "Validar espècies sensibles abans d'actuar en HIC, punts d'aigua, prats i ecotons.",
                "No usar manca de cites com a justificació per intervenir sense camp.",
            ],
        }),
        common_labels({
            "number": 5,
            "title": "La resposta futura dependrà de vigor, humitat i refugis climàtics",
            "subtitle": "Vegetació, Copernicus, relleu, aigua i vulnerabilitat climàtica",
            "data_used": [
                f"escena d'estiu localitzada: {copernicus_scene_note}",
                f"refugis climàtics {refuges_score}/100",
                f"vulnerabilitat climàtica {vulnerability_score}/100",
                f"funcionalitat hídrica {water_score}/100",
            ],
            "result_note": "La diagnosi dinàmica ja té una escena recent adequada, però encara no té índexs processats de vigor i humitat.",
            "map_kind": "base",
            "map_note": "El context topogràfic orienta obagues i fondals; la imatge recent ha de confirmar funcionament.",
            "rows": [
                ["Variable", "Resultat", "Què governa", "Decisió"],
                ["Imatge estival", copernicus_scene_note, "vigor i humitat", "processar índexs"],
                ["Refugis", f"{refuges_score}/100", "amortiment climàtic", "prudència"],
                ["Vulnerabilitat", f"{vulnerability_score}/100", "exposició local", "no zonificar encara"],
                ["Aigua", f"{hydrology_km} km / {fonts_count} fonts", "nodes de resistència", "inventariar"],
            ],
            "widths": [32 * mm, 38 * mm, 58 * mm, 42 * mm],
            "interpretation": (
                "El funcionament futur d'Alinyà no dependrà només de quins hàbitats hi ha, sinó de com responen en anys secs i calorosos. La matriu forestal pot actuar com a refugi o com a massa vulnerable segons orientació, humitat, densitat, sòl i proximitat a l'aigua. Per això Copernicus entra aquí com una evidència clau: hi ha una imatge d'estiu adequada per contrastar la cartografia amb vigor i humitat. "
                "Aquesta dada no permet encara afirmar on hi ha estrès, però sí canvia la diagnosi: el pas següent ja no és buscar una font, sinó processar una evidència concreta i comparar-la amb obagues, solanes, fonts, prats i masses forestals. Això ha de separar refugis reals de refugis aparents i zones vulnerables invisibles en la cartografia estàtica."
            ),
            "limitations": (
                "Sense índexs calculats de vegetació, humitat i temperatura superficial, els refugis i la vulnerabilitat són lectures potencials."
            ),
            "confidence": "mitjana",
            "confidence_note": "Mitjana indica que el patró estructural és coherent, però falta la prova dinàmica que confirma funcionament.",
            "decision": [
                "Processar la imatge d'estiu abans de tancar zones d'estrès, refugis o restauració climàtica.",
                "Tractar obagues, fondals i punts d'aigua com a zones de prudència fins validar-ne la funció.",
                "Fer que el camp contrasti els extrems: masses denses i clares, obagues i solanes, prats i entorns hídrics.",
            ],
        }),
        common_labels({
            "number": 6,
            "title": "El foc és una expressió del mateix procés de continuïtat, humitat i mosaic",
            "subtitle": "Combustible potencial, discontinuïtats, aigua, accessos i hàbitats",
            "data_used": [
                f"resiliència davant del foc {fire_score}/100",
                f"{forest_pct} forestal",
                f"{grass_pct} espais oberts herbacis",
                f"humitat estival pendent de processar: {copernicus_scene_note}",
            ],
            "result_note": "La lectura del foc queda lligada al mosaic i a la humitat vegetal, no a una capa de risc aïllada.",
            "map_kind": "paisatge",
            "map_note": "El mapa mostra continuïtats i discontinuïtats, no un risc final d'incendi.",
            "rows": [
                ["Factor", "Resultat", "Efecte sobre el procés", "Resposta"],
                ["Continuïtat forestal", forest_pct, "propagació potencial", "crear estructura"],
                ["Espais oberts", grass_pct, "discontinuïtat i biodiversitat", "mantenir selectivament"],
                ["Humitat", copernicus_scene_note, "separarà continuïtat seca i humida", "processar"],
                ["Accessos/aigua", f"{road_km} km / {fonts_count} fonts", "resposta i punts sensibles", "validar"],
            ],
            "widths": [34 * mm, 36 * mm, 58 * mm, 42 * mm],
            "interpretation": (
                "El foc no és un capítol separat del mosaic: és una conseqüència possible de continuïtat, pendent, orientació, estructura i humitat. En un paisatge que es tanca, la prevenció no pot consistir només a reduir combustible. Ha de conservar discontinuïtats útils, evitar empobrir hàbitats i mantenir espais oberts que també tenen valor per biodiversitat. "
                "La humitat vegetal és la peça que falta per afinar la decisió. Una massa contínua i humida pot ser refugi i no prioritat d'actuació; una massa contínua, exposada i seca pot requerir gestió. Per això la futura lectura de Copernicus és important per evitar una resposta forestal massa uniforme."
            ),
            "limitations": (
                "No hi ha encara model complet de combustible, humitat processada, severitat històrica ni estructura forestal de detall."
            ),
            "confidence": "mitjana",
            "confidence_note": "La forma del paisatge és clara; la resposta del combustible viu encara necessita evidència dinàmica i camp.",
            "decision": [
                "No executar tractaments generalitzats de combustible en zones d'alt valor d'hàbitat.",
                "Prioritzar discontinuïtats existents, prats i ecotons on el benefici sigui ecològic i preventiu.",
                "Validar humitat, estructura i accessos abans de redactar actuacions forestals executives.",
            ],
        }),
        common_labels({
            "number": 7,
            "title": "L'accessibilitat pot transformar valor ecològic en pressió si no s'ordena",
            "subtitle": "Camins, punts d'ús públic, connectivitat, fauna i tranquil·litat ecològica",
            "data_used": [
                f"{road_km} km de xarxa viària i camins",
                f"{public_points} punts d'ús públic detectats",
                f"pressió humana {pressure_score}/100",
                f"connectivitat ecològica {connectivity_score}/100",
            ],
            "result_note": "La pressió actual és una lectura d'accessibilitat potencial, no una estimació de visitants.",
            "map_kind": "pressio_humana",
            "map_note": "El mapa localitza on l'accés pot interactuar amb hàbitats, aigua i zones tranquil·les.",
            "rows": [
                ["Evidència", "Resultat", "Procés afectat", "Gestió"],
                ["Camins", f"{road_km} km", "accessibilitat i fragmentació fina", "ordenar"],
                ["Punts d'ús", public_points, "concentració de pertorbació", "validar intensitat"],
                ["Connectivitat", f"{connectivity_score}/100", "permeabilitat", "evitar barreres"],
                ["Hàbitats/aigua", "zones sensibles", "conflicte potencial", "filtre de prudència"],
            ],
            "widths": [32 * mm, 32 * mm, 64 * mm, 42 * mm],
            "interpretation": (
                "La pressió humana no és només quanta gent entra, sinó on l'accés toca processos sensibles. Un camí pot ser compatible en una zona robusta i problemàtic si travessa un HIC sensible, un punt d'aigua, un refugi potencial o una zona de baixa pertorbació per fauna. "
                "La connectivitat ecològica alta és una fortalesa, però també pot ser vulnerable a petites friccions acumulades: aparcaments, camins secundaris, ús dispers, miradors o passos que no trenquen el mapa general però sí el comportament d'espècies sensibles. Per això la gestió de l'ús públic ha de començar per identificar interseccions entre accessibilitat i valor, no per comptar camins de manera aïllada."
            ),
            "limitations": (
                "No es disposa encara d'intensitat real de freqüentació, estacionalitat, tipologia d'usuaris ni validació de conflictes sobre el terreny."
            ),
            "confidence": "alta per accessibilitat; baixa per freqüentació real",
            "confidence_note": "Es pot decidir on mirar primer, però no quantificar encara quanta pressió real suporta cada sector.",
            "decision": [
                "Validar in situ els punts on camins i ús públic coincideixen amb HIC, punts d'aigua o zones tranquil·les.",
                "Ordenar accessos abans que la pressió dispersa degradi processos sensibles.",
                "No confondre baixa superfície artificial amb baixa pertorbació ecològica.",
            ],
        }),
        common_labels({
            "number": 8,
            "title": "La gestió ha de ser adaptativa perquè els processos encara estan oberts",
            "subtitle": "Prioritats, restauració, validació de camp, seguiment i actualització",
            "data_used": [
                f"prioritat de gestió {management_score}/100",
                f"potencial de restauració {restoration_score}/100",
                "checklist de camp generada",
                "dades dinàmiques pendents de processar",
            ],
            "result_note": "La diagnosi permet decisions estratègiques, però no totes les actuacions executives estan tancades.",
            "map_kind": "espai",
            "map_note": "La localització final de les actuacions ha de creuar processos, propietat, camp i governança.",
            "rows": [
                ["Fase", "Objectiu", "Procés que resol", "Condició"],
                ["Ara", "conservar i no deteriorar", "valor i mosaic", "aplicable"],
                ["Camp", "validar punts crítics", "aigua, hàbitats, ús", "prioritari"],
                ["Després", "restaurar funcions", "mosaic i refugis", "localització validada"],
                ["Seguiment", "revisar decisions", "clima, foc, vegetació", "dades noves"],
            ],
            "widths": [24 * mm, 44 * mm, 58 * mm, 44 * mm],
            "interpretation": (
                "Els processos detectats no demanen una gran actuació única, sinó una seqüència de gestió adaptativa. Primer cal protegir allò que ja és robust: hàbitats, ecotons, punts sensibles i mosaic funcional. Després cal reduir incerteses que poden canviar decisions: estat fisiològic de la vegetació, punts d'aigua, freqüentació real i estructura forestal. Només llavors té sentit executar restauració o tractaments més fins. "
                "Aquest enfocament evita dues errades habituals: actuar massa aviat amb dades parcials o esperar massa i deixar que el procés de tancament, la pressió o la vulnerabilitat climàtica avancin sense control."
            ),
            "limitations": (
                "La conversió en pla executiu requereix pressupost, propietat, permisos, calendaris, responsables i verificació de camp."
            ),
            "confidence": "mitjana-alta com a estratègia",
            "confidence_note": "La seqüència és sòlida perquè deriva de processos coincidents; la ubicació fina queda condicionada per camp i dades dinàmiques.",
            "decision": [
                "Aprovar una seqüència: protegir ara, validar punts crítics, actuar selectivament i revisar amb seguiment.",
                "No finançar actuacions que no indiquin quin procés ecològic milloren.",
                "Reexecutar EcoRadar quan s'incorporin índexs de vegetació, freqüentació real o resultats de camp.",
            ],
        }),
        common_labels({
            "number": 18,
            "title": "Annex tècnic: traçabilitat de les dades",
            "subtitle": "Informació interna per auditoria, no per decisió directa de gestió",
            "data_used": [
                "registre central de fonts",
                "estat de dades disponibles",
                "serveis oficials i fonts manuals",
                "metadades i validació",
            ],
            "result_note": "Aquests elements s'inclouen només per transparència tècnica.",
            "map_kind": "base",
            "map_note": "Mapa base de suport a la traçabilitat tècnica.",
            "rows": [["Bloc", "Font", "Paper", "Decisió"]] + [list(row) for row in SOURCE_MATRIX[:6]],
            "widths": [30 * mm, 48 * mm, 44 * mm, 48 * mm],
            "interpretation": (
                "La traçabilitat permet revisar quines dades alimenten cada conclusió, quines fonts han estat processades i quines continuen condicionades per permisos, accés manual o camp. Aquesta informació és necessària per auditar el producte, però no forma part del relat principal de gestió."
            ),
            "limitations": (
                "Els detalls tècnics no incrementen per si sols la qualitat ecològica; només permeten verificar-la i actualitzar-la."
            ),
            "confidence": "alta com a annex tècnic",
            "decision": [
                "Mantenir la traçabilitat fora del cos principal de l'informe destinat a gestors.",
                "Actualitzar aquest annex quan canviïn fonts, permisos, sistemes de referència o metadades.",
                "No convertir una font absent en una dada estimada dins cap conclusió.",
            ],
        }),
        common_labels({
            "number": 19,
            "title": "Annex tècnic: dades insuficients i efecte sobre decisions",
            "subtitle": "Quines incerteses afecten cada procés",
            "data_used": [
                "informes de disponibilitat",
                "completesa d'indicadors",
                "validació tècnica i ecològica",
                "checklist de camp",
            ],
            "result_note": "Les dades insuficients s'expressen com a impacte sobre decisions, no com a excusa metodològica.",
            "map_kind": "base",
            "map_note": "Les incerteses s'han de convertir en tasques de camp o actualització de fonts.",
            "rows": [
                ["Nivell", "En què es basa", "Què indica", "Com s'ha d'usar"],
                ["Alta", "fonts oficials, completes i coherents", "decisió defensable a escala de diagnosi", "actuar amb prudència normal"],
                ["Mitjana", "bones fonts però falta detall local o dinàmic", "criteri orientador", "validar abans d'executar"],
                ["Baixa", "falta una peça crítica o només hi ha proxy", "hipòtesi de treball", "no zonificar ni actuar"],
                ["Variable", "canvia segons procés i escala", "separar decisió general i detall", "documentar condicions"],
            ],
            "widths": [30 * mm, 48 * mm, 50 * mm, 42 * mm],
            "interpretation": (
                "La confiança no mesura si una conclusió sona convincent, sinó si les dades permeten convertir-la en decisió. EcoRadar la basa en cinc criteris: qualitat oficial de la font, actualitat, escala adequada, coherència amb altres capes i validació o comprovació local. "
                "En una diagnosi per processos, la confiança també indica quin tram de la cadena causal és robust i quin continua obert. Així es pot conservar allò que ja és clar, però ajornar la zonificació fina quan falta vegetació dinàmica, freqüentació real o camp."
            ),
            "limitations": (
                "Aquest annex resumeix el sentit operatiu de la confiança. El detall tècnic complet queda a les metadades."
            ),
            "confidence": "alta sobre l'impacte de les mancances",
            "confidence_note": "Aquí la confiança és alta perquè no afirma resultats ecològics nous: explica com s'ha ponderat la solidesa de cada conclusió.",
            "decision": [
                "No eliminar incerteses del document principal: convertir-les en prudència ecològica i decisions condicionades.",
                "Assignar responsable i calendari a cada dada que pot canviar una decisió.",
                "Reexecutar la diagnosi quan les dades dinàmiques o de camp estiguin incorporades.",
            ],
        }),
    ]


def technical_annex_chapters(data: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = process_report_chapters(data)
    return [chapter for chapter in chapters if int(chapter.get("number", 0)) >= 18]


def page_management_block_intro(report: Report, block: dict[str, Any]) -> None:
    report.new_page(f"{block.get('prefix', 'BLOC')} {block['number']}. {block['title']}", block["question"])
    m = report.margin

    report.card(m, 202 * mm, 178 * mm, 50 * mm, block.get("synthesis_title", "Síntesi del procés"))
    report.para_fit(block["synthesis"], m + 6 * mm, 236 * mm, 166 * mm, 28 * mm, "body", 7.5)

    report.card(m, 133 * mm, 82 * mm, 58 * mm, block.get("progression_title", "Com es manifesta"))
    draw_numbered_actions(report, block["progression"], m + 6 * mm, 174 * mm, 70 * mm)

    report.card(m + 88 * mm, 133 * mm, 90 * mm, 58 * mm, "Mapa de lectura")
    draw_image(report, project_map_path(block["map_kind"]), m + 97 * mm, 150 * mm, 74 * mm, 30 * mm)
    report.para_fit("Aquest mapa no tanca la decisió; situa el bloc dins el mateix territori per mantenir una lectura integrada.", m + 94 * mm, 144 * mm, 78 * mm, 9 * mm, "tiny", 5.2)

    report.card(m, 58 * mm, 82 * mm, 64 * mm, block.get("chapters_title", "Lectures integrades"))
    chapter_lines = [
        f"{block['number']}.{index} {chapter['title']}"
        for index, chapter in enumerate(block["chapters"], start=1)
    ]
    draw_compact_numbered_actions(report, chapter_lines, m + 6 * mm, 105 * mm, 70 * mm)

    report.card(m + 88 * mm, 58 * mm, 90 * mm, 64 * mm, block.get("decisions_title", "Decisions que exigeix"))
    draw_numbered_actions(report, block["prepared_decisions"], m + 94 * mm, 105 * mm, 78 * mm)
    report.footer()


def page_progressive_chapter(report: Report, chapter: dict[str, Any], block: dict[str, Any], index: int) -> None:
    labels = block["labels"]
    report.new_page(f"{block['number']}.{index} {chapter['title']}", chapter["subtitle"])
    m = report.margin
    top = report.height - 50 * mm

    report.card(m, top - 48 * mm, 96 * mm, 42 * mm, labels["evidence"])
    evidence_text = " · ".join(chapter["data_used"])
    if chapter.get("result_note"):
        evidence_text = f"{evidence_text}. {chapter['result_note']}"
    report.para_fit(sentence_start(evidence_text), m + 5 * mm, top - 21 * mm, 86 * mm, 22 * mm, "tiny", 5.2)

    report.card(m + 102 * mm, top - 48 * mm, 76 * mm, 42 * mm, "Situació espacial")
    draw_image(report, project_map_path(chapter["map_kind"]), m + 105 * mm, top - 40 * mm, 70 * mm, 21 * mm)
    report.para_fit(sentence_start(chapter["map_note"]), m + 106 * mm, top - 42 * mm, 68 * mm, 5.5 * mm, "tiny", 4.8)

    report.card(m, 119 * mm, 178 * mm, 73 * mm, labels["interpretation"])
    report.para_fit(chapter["interpretation"], m + 6 * mm, 175 * mm, 166 * mm, 43 * mm, "small", 6.1)

    report.card(m, 73 * mm, 178 * mm, 39 * mm, labels["table"])
    rows = chapter.get("rows") or [["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"]]
    draw_table(
        report,
        rows,
        m + 5 * mm,
        101 * mm,
        chapter.get("widths", [48 * mm, 22 * mm, 27 * mm, 25 * mm, 48 * mm]),
        4.75,
    )

    report.card(m, 18 * mm, 86 * mm, 48 * mm, labels["confidence"])
    confidence_note = chapter.get("confidence_note")
    confidence_text = f"Confiança: {chapter['confidence']}."
    if confidence_note:
        confidence_text += f" {confidence_note}"
    confidence_text += f" {chapter['limitations']}"
    report.para_fit(
        confidence_text,
        m + 5 * mm,
        50 * mm,
        76 * mm,
        30 * mm,
        "tiny",
        5.1,
    )

    report.card(m + 92 * mm, 18 * mm, 86 * mm, 48 * mm, labels["action"])
    decision_items = chapter["decision"] if "decision" in chapter else chapter["implications"]
    draw_compact_numbered_actions(report, decision_items[:3], m + 98 * mm, 50 * mm, 74 * mm)
    report.footer()


def page_technical_annex(report: Report, chapter: dict[str, Any], index: int) -> None:
    annex_title = sentence_start(chapter["title"].replace("Annex tècnic: ", ""))
    report.new_page(f"ANNEX {index}. {annex_title}", chapter["subtitle"])
    m = report.margin

    report.card(m, 204 * mm, 178 * mm, 48 * mm, "Per què aquest annex no forma part del relat principal")
    evidence_text = " · ".join(chapter["data_used"])
    if chapter.get("result_note"):
        evidence_text = f"{evidence_text}. {chapter['result_note']}"
    report.para_fit(sentence_start(evidence_text), m + 6 * mm, 235 * mm, 166 * mm, 22 * mm, "small", 6.5)

    report.card(m, 133 * mm, 178 * mm, 60 * mm, "Traçabilitat i control")
    draw_table(
        report,
        chapter.get("rows") or [],
        m + 5 * mm,
        177 * mm,
        chapter.get("widths", [48 * mm, 40 * mm, 42 * mm, 48 * mm]),
        4.8,
    )

    report.card(m, 73 * mm, 86 * mm, 50 * mm, "Lectura tècnica")
    report.para_fit(chapter["interpretation"], m + 5 * mm, 107 * mm, 76 * mm, 25 * mm, "tiny", 5.4)

    report.card(m + 92 * mm, 73 * mm, 86 * mm, 50 * mm, "Com condiciona futures versions")
    decision_items = chapter["decision"] if "decision" in chapter else chapter["implications"]
    draw_compact_numbered_actions(report, decision_items[:3], m + 98 * mm, 107 * mm, 74 * mm)

    report.card(m, 31 * mm, 178 * mm, 34 * mm, "Confiança")
    report.para_fit(
        f"Confiança: {chapter['confidence']}. {chapter['limitations']}",
        m + 6 * mm,
        50 * mm,
        166 * mm,
        17 * mm,
        "tiny",
        5.2,
    )
    report.footer()


def integrated_report_chapters(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the fixed 22-chapter structure required for every EcoRadar report."""

    availability = availability_summary(data)
    forest_pct = fmt(metric(data["basic"], "percentatge_coberta_forestal"), 1, "%")
    grass_pct = fmt(metric(data["basic"], "percentatge_prats_pastures_herbassars"), 1, "%")
    hic_ha = fmt(metric(data["basic"], "superficie_hic"), 0)
    species_count = metric(data["basic"], "nombre_especies_registrades")
    road_km = fmt(pressure_metric(data["pressure"], "osm_path_track_road_km"), 1)
    hydrology_km = fmt((num(row_value(data["hydrology"], "layer_id", "rius_aca_che", "length_km")) or 0) + (num(row_value(data["hydrology"], "layer_id", "eixos_drenatge", "length_km")) or 0), 2)
    validation_text = validation_summary_text(data)
    recommendations = data["recommendations"][:4]
    recommendation_rows_table = [["Recomanació", "Grup", "Conf.", "Indicadors"]]
    for row in recommendations:
        recommendation_rows_table.append([
            row.get("objective", "")[:58],
            row.get("group", ""),
            row.get("confidence", ""),
            row.get("supporting_indicators", "")[:42],
        ])

    source_rows = [["Bloc", "Estat", "Impacte"]]
    for block in data.get("availability", {}).get("blocks", [])[:9]:
        source_rows.append([
            block.get("block_name", ""),
            ", ".join(f"{k}: {v}" for k, v in block.get("status_counts", {}).items()),
            "condiciona confiança" if "requereix_credencials" in block.get("status_counts", {}) or "manual_pendent" in block.get("status_counts", {}) else "evidència disponible",
        ])

    chapters: list[dict[str, Any]] = [
        {
            "number": 1,
            "title": "Resum executiu",
            "subtitle": "Lectura integrada per orientar decisions",
            "data_used": ["Indicadors Radar", "Diagnosi", "Recomanacions", "Validació"],
            "map_kind": "espai",
            "map_note": "Mapa general de l'espai com a referència de lectura.",
            "rows": [
                ["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"],
                core_summary_row(data, "CORE_02"),
                core_summary_row(data, "CORE_06"),
                core_summary_row(data, "CORE_08"),
                core_summary_row(data, "CORE_12"),
            ],
            "interpretation": core_reading(data),
            "limitations": "La síntesi és robusta per hàbitats, mosaic, biodiversitat pública i connectivitat; és provisional per vegetació, clima, foc, aigua i restauració quan falten fonts crítiques.",
            "confidence": "mitjana-alta amb blocs parcials explícits",
            "implications": [
                "Conservar valors d'hàbitat abans d'obrir actuacions transformadores.",
                "Usar les conclusions parcials per dirigir treball de camp, no per tancar zonificacions finals.",
                "Prioritzar dades que canvien decisions: Copernicus, clima, SIGPAC/DUN i validació de camp.",
            ],
        },
        {
            "number": 2,
            "title": "Àrea d'estudi",
            "subtitle": "Delimitació, escala i base espacial de la diagnosi",
            "data_used": ["study_area.gpkg", "CRS EPSG:25831", "superfície", "perímetre"],
            "map_kind": "espai",
            "map_note": "Límit validat de l'àrea d'estudi.",
            "rows": [
                ["Variable", "Valor", "Estat", "Confiança", "Observació"],
                ["Superfície", fmt(data["study"].get("surface_ha"), 1), "validada", "alta", "base per a tots els percentatges"],
                ["Perímetre", fmt(data["study"].get("perimeter_m"), 0), "validat", "alta", "base per a connectivitat i límits"],
                ["CRS final", data["study"].get("final_crs", "EPSG:25831"), "validat", "alta", "coherent amb cartografia catalana"],
            ],
            "interpretation": "Una àrea d'estudi geomètricament consistent és la condició prèvia per comparar cobertes, hàbitats, accessos i fonts. En aquest cas la validació tècnica no detecta errors de geometria ni discrepàncies de superfície.",
            "limitations": "La delimitació no incorpora per si sola règim de propietat, límits administratius fins ni figura de protecció; aquests elements condicionen la gestió però no alteren el càlcul espacial bàsic.",
            "confidence": "alta",
            "implications": [
                "Totes les capes processades s'han de retallar estrictament a aquest límit.",
                "Qualsevol canvi de límit obliga a regenerar indicadors i diagnosi.",
                "La governança i propietat s'han d'afegir abans de programar actuacions executives.",
            ],
        },
        {
            "number": 3,
            "title": "Metodologia EcoRadar aplicada",
            "subtitle": "De fonts verificades a diagnosi i decisió",
            "data_used": ["data_sources.yaml", "Data Source Manager", "Indicadors Radar", "Motors de diagnosi i recomanació"],
            "map_kind": "base",
            "map_note": "Mapa base usat com a context territorial, no com a indicador.",
            "rows": [
                ["Fase", "Sortida", "Estat", "Confiança", "Criteri"],
                ["Fonts", "auditoria", "executada", "alta", "no es calcula sense inventari"],
                ["Indicadors", "12 Radar", "executada", "mixta", "valors reals o parcial/no disponible"],
                ["Diagnosi", "conclusions", "executada", "mixta", "robust/provisional segons fonts"],
                ["Validació", "gate", "superada", "alta", "atura productes finals si hi ha errors crítics"],
            ],
            "interpretation": "EcoRadar no parteix d'una puntuació única. Ordena evidències, calcula indicadors traçables i interpreta relacions ecològiques: valor, pressió, vulnerabilitat, oportunitat i incertesa.",
            "limitations": "El mètode integra informació existent i automatitzable; no substitueix estudis específics d'espècies, hidrologia, enginyeria forestal o impacte ambiental.",
            "confidence": "alta com a procés; variable segons cada bloc de dades",
            "implications": [
                "Les decisions finals han de distingir conclusions robustes i provisionals.",
                "Les dades absents es converteixen en tasques de validació, no en valors ficticis.",
                "El mateix flux és reutilitzable per qualsevol espai amb àrea d'estudi validada.",
            ],
        },
        {
            "number": 4,
            "title": "Auditoria de dades",
            "subtitle": "Què s'ha pogut consultar i què condiciona la diagnosi",
            "data_used": ["data_availability_report", "connectors_status_report", "indicators_completeness_report"],
            "map_kind": "base",
            "map_note": "La cartografia base contextualitza fonts i retalls espacials.",
            "rows": source_rows,
            "widths": [50 * mm, 58 * mm, 62 * mm],
            "interpretation": f"S'han revisat {availability.get('total_sources', 0)} fonts. Les fonts disponibles permeten una radiografia territorial robusta, però Copernicus, clima, SIGPAC/DUN, BDBC i camp condicionen la diagnosi fina de vegetació, gestió agrària i vulnerabilitat.",
            "limitations": "Una font pendent no s'ha substituït per cap estimació. Quan afecta un indicador, aquest queda parcial o no disponible i baixa la confiança.",
            "confidence": "alta sobre l'estat de disponibilitat; variable sobre cada domini ecològic",
            "implications": [
                "Abans d'una versió contractual final cal prioritzar les fonts que canvien decisions.",
                "Les fonts manuals s'han d'importar amb metadades i traçabilitat.",
                "Les fonts legalment condicionades, com Strava, no s'han d'usar sense compatibilitat clara.",
            ],
        },
        {
            "number": 5,
            "title": "Diagnosi territorial",
            "subtitle": "Estructura, mosaic, fragmentació, ecotons i connectivitat del paisatge",
            "data_used": ["Cobertes ICGC", "Hàbitats", "OSM", "connectivitat", "àrea d'estudi"],
            "map_kind": "paisatge",
            "map_note": "Mapa de cobertes i mosaic territorial.",
            "rows": [
                ["Element", "Valor", "Estat", "Confiança", "Lectura"],
                ["Coberta forestal", forest_pct, "disponible", "alta", "matriu dominant"],
                ["Prats/herbassars", grass_pct, "disponible", "alta", "espais oberts funcionals"],
                core_summary_row(data, "CORE_01"),
                core_summary_row(data, "CORE_08"),
            ],
            "interpretation": "La muntanya funciona com una matriu forestal extensa amb discontinuïtats obertes que poden ser petites en superfície però importants per biodiversitat, mosaic i foc. Els ecotons entre bosc, matollar, prats i conreus són una peça de gestió clau.",
            "limitations": "La fragmentació funcional per espècie encara necessita dades de barreres, freqüentació real i validació local d'ecotons.",
            "confidence": "alta per estructura general; mitjana per fragmentació funcional",
            "implications": [
                "Gestionar el mosaic fi, no només les classes dominants.",
                "Evitar homogeneïtzar espais oberts escassos.",
                "Creuar qualsevol actuació amb connectivitat i hàbitats abans d'executar-la.",
            ],
        },
        {
            "number": 6,
            "title": "Diagnosi dels hàbitats",
            "subtitle": "Hàbitats, HIC, qualitat, representativitat i singularitat",
            "data_used": ["Hàbitats terrestres v3", "HIC", "àrea d'estudi"],
            "map_kind": "habitats",
            "map_note": "Mapa d'hàbitats i HIC processats dins l'àrea.",
            "rows": [
                ["Element", "Valor", "Estat", "Confiança", "Lectura"],
                ["Nombre d'hàbitats", metric(data["basic"], "nombre_habitats"), "disponible", "alta", "heterogeneïtat ecològica"],
                ["Superfície HIC", hic_ha, "disponible", "alta", "responsabilitat de conservació"],
                ["HIC prioritaris", fmt(priority_habitat_surface(data["habitats"]), 0), "disponible", "alta", "prudència d'actuació"],
                core_summary_row(data, "CORE_02"),
            ],
            "interpretation": "El valor d'hàbitats és el senyal ecològic més fort. La presència extensa d'HIC i HIC prioritaris obliga a gestionar amb criteri preventiu i a evitar actuacions homogènies sobre unitats ecològiques diferents.",
            "limitations": "La cartografia indica presència i distribució, però no certifica qualitat local ni estat de conservació sense camp.",
            "confidence": "alta a escala cartogràfica; mitjana per qualitat local",
            "implications": [
                "Validar HIC i prioritaris abans d'obres, aclarides o canvis d'ús.",
                "Identificar hàbitats sensibles i degradats amb treball de camp dirigit.",
                "Fer que el valor d'hàbitat condicioni qualsevol prioritat de restauració o ús públic.",
            ],
        },
        {
            "number": 7,
            "title": "Diagnosi de la vegetació",
            "subtitle": "Vigor, estat, NDVI, NDMI, NDWI i limitacions",
            "data_used": ["Cobertes vegetals", "hàbitats", "Copernicus pendent"],
            "map_kind": "paisatge",
            "map_note": "S'utilitza mapa de cobertes perquè els índexs Sentinel no estan disponibles.",
            "rows": [
                ["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"],
                core_summary_row(data, "CORE_03"),
                ["NDVI", "no calculat", source_status(data, "copernicus_sentinel_ndvi"), "baixa", "credencials Copernicus"],
                ["NDMI", "no calculat", source_status(data, "copernicus_sentinel_ndmi"), "baixa", "credencials Copernicus"],
                ["NDWI", "no calculat", source_status(data, "copernicus_sentinel_ndwi"), "baixa", "credencials Copernicus"],
            ],
            "interpretation": "La cartografia mostra cobertura i tipus de vegetació, però no permet avaluar vigor fisiològic ni estrès hídric actual. Qualsevol conclusió sobre vigor vegetal queda oberta fins disposar d'índexs Sentinel reals.",
            "limitations": "No hi ha NDVI, NDMI ni NDWI validats. No s'ha substituït aquesta absència per cap índex simulat.",
            "confidence": "baixa per estat de vegetació; alta per cobertura estructural",
            "implications": [
                "No definir zones d'estrès vegetal sense teledetecció.",
                "Prioritzar credencials Copernicus i sèrie temporal d'estiu.",
                "Usar cobertes i hàbitats només com a lectura estructural provisional.",
            ],
        },
        {
            "number": 8,
            "title": "Diagnosi climàtica",
            "subtitle": "LST, refugis climàtics, vulnerabilitat, orientacions, obagues i solanes",
            "data_used": ["DEM/MDT", "orientació", "pendent", "cobertes", "clima pendent", "LST pendent"],
            "map_kind": "base",
            "map_note": "Mapa base; la cartografia climàtica específica resta condicionada per fonts pendents.",
            "rows": [
                ["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"],
                core_summary_row(data, "CORE_04"),
                core_summary_row(data, "CORE_05"),
                ["LST", "no calculada", source_status(data, "copernicus_lst"), "baixa", "credencials Copernicus"],
                ["Meteocat/AEMET", "no integrat", block_status(data, "climate"), "baixa", "credencials/API"],
            ],
            "interpretation": "El relleu i l'orientació permeten intuir obagues, solanes i refugis potencials, però la diagnosi climàtica no pot tancar-se sense LST, humitat de vegetació i dades climàtiques.",
            "limitations": "Refugis i vulnerabilitat són lectures parcials. Sense LST i clima no s'han de convertir en zonificació final.",
            "confidence": "mitjana per refugis potencials; baixa per clima actual",
            "implications": [
                "Validar obagues i punts d'aigua com a refugis al camp.",
                "No prioritzar restauració climàtica sense LST/NDMI.",
                "Afegir Meteocat/AEMET/SPEI per contextualitzar sequera i anomalies.",
            ],
        },
        {
            "number": 9,
            "title": "Diagnosi hidrològica",
            "subtitle": "Cursos d'aigua, fonts, basses, zones humides i funcionalitat",
            "data_used": ["ACA/hidrografia", "fonts", "DEM", "NDWI pendent", "camp pendent"],
            "map_kind": "base",
            "map_note": "Mapa base; la capa hidrològica existeix al datastore però no té mapa temàtic publicat.",
            "rows": [
                ["Element", "Valor", "Estat", "Confiança", "Lectura"],
                ["Cursos/drenatge", hydrology_km, "disponible", "mitjana", "xarxa cartografiada"],
                ["Fonts", row_value(data["hydrology"], "layer_id", "fonts", "feature_count") or "0", "disponible", "mitjana", "punts a validar"],
                core_summary_row(data, "CORE_10"),
                core_summary_row(data, "CORE_04"),
            ],
            "interpretation": "La hidrologia cartografiada identifica estructura espacial d'aigua, però la funcionalitat ecològica depèn de temporalitat, qualitat, accessibilitat per fauna i pressions locals.",
            "limitations": "Falten NDWI, basses funcionals, zones humides verificades i treball de camp. La lectura hídrica és parcial.",
            "confidence": "mitjana",
            "implications": [
                "Fer camp específic a fonts, basses i cursos temporals.",
                "No assumir qualitat ecològica només per presència cartogràfica.",
                "Creuar punts d'aigua amb fauna, refugis climàtics i ús públic.",
            ],
        },
        {
            "number": 10,
            "title": "Diagnosi de biodiversitat",
            "subtitle": "Flora, fauna, grups taxonòmics, indicadores, protegides, invasores i limitacions del coneixement",
            "data_used": ["GBIF", "iNaturalist", "BDBC pendent", "camp pendent"],
            "map_kind": "biodiversitat",
            "map_note": "Registres públics normalitzats dins l'àrea d'estudi.",
            "rows": [
                ["Element", "Valor", "Estat", "Confiança", "Limitació"],
                ["Registres", metric(data["basic"], "nombre_registres_biodiversitat"), "disponible", "alta", "fonts oportunistes"],
                ["Taxons", species_count, "disponible", "alta", "no equival a inventari complet"],
                ["BDBC", "pendent", source_status(data, "bdbc"), "baixa", "import manual/autorització"],
                core_summary_row(data, "CORE_06"),
            ],
            "interpretation": "La biodiversitat coneguda és alta i útil per orientar mostreig, però prové de fonts públiques amb biaix d'observació. Les absències no són absències ecològiques.",
            "limitations": "Falten llistes normatives creuades d'espècies protegides, amenaçades, invasores i indicadores, així com validació de camp.",
            "confidence": "alta per coneixement públic; mitjana-baixa per estat real de comunitats",
            "implications": [
                "Usar les cites per prioritzar mostreig i detectar buits.",
                "No fer gestió d'espècies sensibles sense validació i marc normatiu.",
                "Incorporar BDBC, dades pròpies i protocols de camp.",
            ],
        },
        {
            "number": 11,
            "title": "Diagnosi de connectivitat ecològica",
            "subtitle": "Corredors, matriu natural i barreres potencials",
            "data_used": ["connectivitat oficial", "cobertes", "hàbitats", "hidrologia", "OSM"],
            "map_kind": "paisatge",
            "map_note": "El mapa de paisatge ajuda a llegir la matriu i les discontinuïtats.",
            "rows": [
                ["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"],
                core_summary_row(data, "CORE_08"),
                core_summary_row(data, "CORE_01"),
                core_summary_row(data, "CORE_10"),
                core_summary_row(data, "CORE_07"),
            ],
            "interpretation": "La connectivitat territorial és un actiu: la matriu forestal i els connectors mantenen continuïtat. La connectivitat funcional, però, depèn de grups d'espècies, barreres locals i pressió humana.",
            "limitations": "No hi ha model funcional per espècie ni freqüentació real. La connectivitat és alta com a estructura, no necessàriament com a ús biològic efectiu.",
            "confidence": "alta per estructura; mitjana per funcionalitat",
            "implications": [
                "Evitar noves barreres en connectors principals.",
                "Prioritzar corredors hídrics i ecotons com a zones sensibles.",
                "Validar friccions locals amb camp i gestors.",
            ],
        },
        {
            "number": 12,
            "title": "Diagnosi de pressió humana",
            "subtitle": "Accessibilitat, ús públic potencial i limitacions de freqüentació",
            "data_used": ["OpenStreetMap", "camins", "pistes", "punts d'ús públic", "Strava condicionat"],
            "map_kind": "pressio_humana",
            "map_note": "Mapa d'accessibilitat potencial i punts d'ús públic.",
            "rows": [
                ["Element", "Valor", "Estat", "Confiança", "Lectura"],
                ["Xarxa camins/pistes", road_km, "disponible", "alta", "accessibilitat potencial"],
                ["Punts ús públic", pressure_metric(data["pressure"], "osm_recreational_point_features"), "disponible", "alta", "concentració potencial"],
                ["Strava", "no usat", source_status(data, "strava_heatmap"), "baixa", "condicionament legal"],
                core_summary_row(data, "CORE_07"),
            ],
            "interpretation": "La pressió humana observada és una pressió potencial per accessibilitat. No mesura nombre de visitants, temporalitat ni conflicte real, però permet localitzar on cal mirar primer.",
            "limitations": "Sense comptadors, gestors, Strava compatible o camp, no es pot estimar freqüentació real.",
            "confidence": "alta per accessibilitat; baixa per ús real",
            "implications": [
                "Validar punts de concentració amb observació i gestors.",
                "Creuar camins amb HIC i fauna sensible abans de regular.",
                "No presentar OSM com a intensitat real de visitants.",
            ],
        },
        {
            "number": 13,
            "title": "Diagnosi forestal",
            "subtitle": "Massa forestal, estructura potencial i gestió compatible amb biodiversitat",
            "data_used": ["Cobertes forestals", "hàbitats forestals", "DEM", "inventari forestal pendent"],
            "map_kind": "paisatge",
            "map_note": "Mapa de cobertes forestals i discontinuïtats.",
            "rows": [
                ["Element", "Valor", "Estat", "Confiança", "Lectura"],
                ["Coberta forestal", forest_pct, "disponible", "alta", "matriu dominant"],
                ["Boscos hàbitats", fmt(rows_sum(data["habitats"], "superficie_ha", "boscos", "pinedes", "carrascars"), 0), "disponible", "alta", "estructura cartogràfica"],
                ["Matollars", fmt(rows_sum(data["habitats"], "superficie_ha", "matollars", "brolles", "garrigues"), 0), "disponible", "alta", "combustible/heterogeneïtat"],
                core_summary_row(data, "CORE_09"),
            ],
            "interpretation": "La dominància forestal és un valor ecològic i alhora una responsabilitat de gestió. Sense inventari estructural no es poden prescriure actuacions silvícoles fines.",
            "limitations": "Falten dades d'estructura forestal, combustible, edat, densitat, regeneració i fusta morta.",
            "confidence": "alta per cobertura; mitjana-baixa per estructura forestal funcional",
            "implications": [
                "No proposar aclarides generalitzades sense inventari forestal.",
                "Prioritzar gestió que mantingui hàbitats, ecotons i fusta morta quan sigui compatible.",
                "Creuar estructura forestal amb foc, pendent, humitat i biodiversitat.",
            ],
        },
        {
            "number": 14,
            "title": "Diagnosi de resiliència davant del foc",
            "subtitle": "Continuïtat forestal, combustible, mosaic, pendent, humitat i accessos",
            "data_used": ["cobertes", "incendis històrics", "DEM", "OSM", "NDMI/LST pendents", "combustible pendent"],
            "map_kind": "paisatge",
            "map_note": "El mapa de paisatge mostra continuïtats i discontinuïtats; no és un mapa final de risc.",
            "rows": [
                ["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"],
                core_summary_row(data, "CORE_09"),
                core_summary_row(data, "CORE_01"),
                ["Incendis", str(len(data["fires"])) if data["fires"] else "0", "disponible/parcial", "mitjana", "severitat i recurrència fina"],
                ["NDMI/LST", "no calculat", block_status(data, "copernicus_sentinel"), "baixa", "credencials Copernicus"],
            ],
            "interpretation": "La resiliència davant del foc no és només risc oficial: depèn de mosaic, humitat, pendent, continuïtat i accessos. EcoRadar només pot orientar hipòtesis de gestió mentre falten NDMI, LST i combustible.",
            "limitations": "No hi ha model complet de combustible ni humitat vegetal. Les conclusions de foc són parcials.",
            "confidence": "mitjana",
            "implications": [
                "Validar discontinuïtats i acumulacions de combustible al camp.",
                "No actuar sobre HIC sensibles només per criteris de combustible.",
                "Prioritzar actuacions on mosaic i benefici ecològic coincideixin.",
            ],
        },
        {
            "number": 15,
            "title": "Diagnosi de restauració ecològica",
            "subtitle": "Potencial, degradació, connectivitat, aigua i vulnerabilitat",
            "data_used": ["Radar restauració", "hàbitats", "connectivitat", "aigua", "vegetació pendent", "camp pendent"],
            "map_kind": "habitats",
            "map_note": "Mapa d'hàbitats per identificar valors font i zones sensibles.",
            "rows": [
                ["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"],
                core_summary_row(data, "CORE_11"),
                core_summary_row(data, "CORE_05"),
                core_summary_row(data, "CORE_10"),
                core_summary_row(data, "CORE_08"),
            ],
            "interpretation": "El potencial de restauració és una orientació de prioritat, no una ordre d'obra. Les millors oportunitats són les que milloren funcionalitat sense perdre valors d'hàbitat existents.",
            "limitations": "Falten vegetació Sentinel, degradació local, pressions reals i validació de camp. No es delimiten actuacions finals.",
            "confidence": "mitjana",
            "implications": [
                "Convertir potencial en actuació només després de camp.",
                "Prioritzar restauració connectada a hàbitats font i aigua.",
                "Evitar restauracions que simplifiquin mosaic o perjudiquin HIC.",
            ],
        },
        {
            "number": 16,
            "title": "Diagnosi de gestió",
            "subtitle": "De la lectura ecològica a criteris de decisió",
            "data_used": ["Radar gestió", "recomanacions", "validació", "prioritat de gestió"],
            "map_kind": "espai",
            "map_note": "Mapa de l'espai com a suport per situar decisions.",
            "rows": [
                ["Indicador", "Valor", "Estat", "Confiança", "Fonts pendents"],
                core_summary_row(data, "CORE_12"),
                core_summary_row(data, "CORE_02"),
                core_summary_row(data, "CORE_07"),
                core_summary_row(data, "CORE_11"),
            ],
            "interpretation": "La gestió ha de separar decisions immediates de conservació, decisions condicionades per dades i treballs de validació. EcoRadar prioritza prudència on el valor és alt i coneixement on la incertesa condiciona acció.",
            "limitations": "Sense figura de protecció completa, propietat, pressupost i governança, la priorització és ecològica i tècnica, no encara executiva.",
            "confidence": "mitjana",
            "implications": [
                "Aplicar primer mesures de no deteriorament en valors coneguts.",
                "Planificar camp per reduir incerteses que bloquegen decisions.",
                "Convertir recomanacions en projecte només amb localització i responsables.",
            ],
        },
        {
            "number": 17,
            "title": "Síntesi integrada",
            "subtitle": "Relació entre valors, pressions, vulnerabilitats i oportunitats",
            "data_used": ["12 indicadors Radar", "diagnosi", "validació", "recomanacions"],
            "map_kind": "espai",
            "map_note": "Mapa general per llegir la síntesi territorial.",
            "rows": [
                ["Bloc", "Valor", "Estat", "Confiança", "Lectura"],
                ["Valor hàbitats", fmt(core_metric(data["core"], "CORE_02"), 1), "fort", "alta", "prudència"],
                ["Biodiversitat", fmt(core_metric(data["core"], "CORE_06"), 1), "fort", "alta", "coneixement públic"],
                ["Pressió humana", fmt(core_metric(data["core"], "CORE_07"), 1), "mitjà", "alta", "accessibilitat"],
                ["Clima/foc/aigua", "parcial", "pendent", "mitjana-baixa", "validació"],
            ],
            "interpretation": "La lectura integrada mostra un espai amb valors d'hàbitat i biodiversitat alts, una matriu natural connectada i pressions que cal entendre com a accessibilitat potencial. Els blocs climàtic, de foc, vegetació fisiològica i aigua funcional determinen les decisions que encara no s'han de tancar.",
            "limitations": "La síntesi manté separats els indicadors; no es redueix a una nota global única.",
            "confidence": "mitjana-alta",
            "implications": [
                "Conservar i validar abans d'intervenir.",
                "Fer servir incerteses com a full de ruta de dades.",
                "Prioritzar actuacions reversibles i justificades per múltiples indicadors.",
            ],
        },
        {
            "number": 18,
            "title": "Recomanacions prioritzades",
            "subtitle": "Actuacions derivades exclusivament de la diagnosi",
            "data_used": ["recommendations.json", "priority_matrix", "indicadors sustentadors"],
            "map_kind": "espai",
            "map_note": "La localització precisa requereix convertir recomanacions en actuacions espacials validades.",
            "rows": recommendation_rows_table,
            "widths": [70 * mm, 28 * mm, 20 * mm, 52 * mm],
            "interpretation": "Les recomanacions no són genèriques: deriven de valor d'hàbitats, biodiversitat, connectivitat, pressió potencial i mancances crítiques. Quan falta dada, la recomanació és validar o completar, no actuar definitivament.",
            "limitations": "Algunes recomanacions encara són de preparació perquè la diagnosi climàtica, vegetal, hídrica i de foc és parcial.",
            "confidence": "mitjana",
            "implications": [
                "Ordenar actuacions per benefici ecològic i confiança.",
                "Separar conservació immediata, restauració condicionada i dades pendents.",
                "No executar actuacions finals sense localització i validació quan la recomanació ho indiqui.",
            ],
        },
        {
            "number": 19,
            "title": "Validació",
            "subtitle": "Controls tècnics, ecològics, de camp i de recomanacions",
            "data_used": ["technical_validation", "ecological_validation", "field checklist", "recommendations_validation"],
            "map_kind": "base",
            "map_note": "Mapa base per vincular validació tècnica i retalls espacials.",
            "rows": [
                ["Nivell", "Estat", "Errors crítics", "Avisos", "Impacte"],
                ["Tècnica", data.get("technical_validation", {}).get("summary", {}).get("status", ""), str(data.get("technical_validation", {}).get("summary", {}).get("critical_errors", 0)), str(data.get("technical_validation", {}).get("summary", {}).get("warnings", 0)), "habilita informe"],
                ["Ecològica", data.get("ecological_validation", {}).get("summary", {}).get("status", ""), str(data.get("ecological_validation", {}).get("summary", {}).get("critical_errors", 0)), str(data.get("ecological_validation", {}).get("summary", {}).get("warnings", 0)), "amb limitacions"],
                ["Recomanacions", data.get("recommendations_validation", {}).get("summary", {}).get("status", "validat"), "0", "0", "traçabilitat"],
            ],
            "interpretation": validation_text,
            "limitations": "La validació no converteix dades parcials en completes; només certifica que les limitacions estan declarades i que no hi ha errors crítics.",
            "confidence": "alta com a control de qualitat",
            "implications": [
                "Publicar amb advertiments quan la validació és amb limitacions.",
                "Usar la checklist de camp com a pròxim pas obligatori.",
                "No generar productes finals si apareixen errors crítics futurs.",
            ],
        },
        {
            "number": 20,
            "title": "Limitacions",
            "subtitle": "Dades absents, incerteses i impacte sobre la diagnosi",
            "data_used": ["indicadors de completesa", "auditoria de fonts", "diagnosi"],
            "map_kind": "base",
            "map_note": "No hi ha mapa específic de limitacions; es relacionen amb blocs de dades.",
            "rows": [
                ["Bloc", "Limitació", "Impacte", "Resposta EcoRadar"],
                ["Vegetació", "NDVI/NDMI/NDWI absents", "CORE_03 no disponible", "no inventar valors"],
                ["Clima", "LST/Meteocat/AEMET pendents", "refugis/vulnerabilitat parcials", "baixar confiança"],
                ["Biodiversitat", "BDBC/camp pendents", "absències no interpretables", "validar"],
                ["Ús públic", "freqüentació real absent", "pressió és potencial", "camp/gestors"],
            ],
            "widths": [28 * mm, 54 * mm, 42 * mm, 46 * mm],
            "interpretation": "Les limitacions són part del resultat. Indiquen què impedeix decidir amb seguretat i quina dada cal incorporar per convertir hipòtesis en actuacions.",
            "limitations": "Aquest capítol resumeix mancances principals; la traçabilitat completa és a l'annex i als informes de metadades.",
            "confidence": "alta sobre les mancances declarades",
            "implications": [
                "No amagar dades absents en presentacions executives.",
                "Prioritzar fonts que afecten més d'un indicador.",
                "Convertir cada limitació crítica en tasca de camp o font a desbloquejar.",
            ],
        },
        {
            "number": 21,
            "title": "Conclusions finals",
            "subtitle": "Criteri expert i lectura defensable del territori",
            "data_used": ["síntesi integrada", "recomanacions", "validació", "limitacions"],
            "map_kind": "espai",
            "map_note": "Mapa general de tancament per situar la lectura global.",
            "rows": [
                ["Conclusió", "Evidència", "Confiança", "Decisió"],
                ["Alt valor ecològic", "HIC, hàbitats, biodiversitat", "alta", "conservar amb prudència"],
                ["Mosaic funcional", "cobertes i hàbitats", "alta", "mantenir discontinuïtats"],
                ["Blocs parcials", "vegetació, clima, foc, aigua", "mitjana/baixa", "validar abans d'actuar"],
                ["Pressió potencial", "OSM", "alta per accessos", "verificar ús real"],
            ],
            "interpretation": "Alinyà pot llegir-se com un espai de gran responsabilitat ecològica, on la gestió ha de protegir valors coneguts i completar dades crítiques abans de decisions irreversibles.",
            "limitations": "Les conclusions finals són una diagnosi integrada, no un pla executiu tancat ni un estudi sectorial complet.",
            "confidence": "mitjana-alta",
            "implications": [
                "Fer de la conservació preventiva el punt de partida.",
                "Transformar buits en una campanya de validació focalitzada.",
                "Construir el pla de gestió a partir de recomanacions justificades i dades completes.",
            ],
        },
        {
            "number": 22,
            "title": "Annexos",
            "subtitle": "Fonts, traçabilitat i lectura tècnica de suport",
            "data_used": ["data_sources.yaml", "metadades", "informes de disponibilitat", "sortides GIS"],
            "map_kind": "base",
            "map_note": "La cartografia base acompanya la traçabilitat de fonts.",
            "rows": [["Bloc", "Font", "Paper", "Decisió"]] + [list(row) for row in SOURCE_MATRIX[:8]],
            "widths": [30 * mm, 48 * mm, 44 * mm, 48 * mm],
            "interpretation": "Els annexos garanteixen que qualsevol lectura ecològica pugui ser auditada: fonts, estat, limitacions, connector responsable i impacte sobre indicadors.",
            "limitations": "L'annex documental no substitueix metadades completes ni fitxers GIS; els complementa per lectura de gestor.",
            "confidence": "alta com a traçabilitat",
            "implications": [
                "Facilitar revisió tècnica i actualitzacions futures.",
                "Permetre comparar diagnòstics entre espais mantenint el mateix mètode.",
                "Documentar fonts absents amb el mateix rigor que fonts disponibles.",
            ],
        },
    ]
    return apply_expert_diagnosis_prose(data, chapters)


def apply_expert_diagnosis_prose(data: dict[str, Any], chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace descriptive placeholders with ecological diagnosis prose.

    The report must teach something that is not obvious from the maps alone:
    process, cause, evidence, consequence, scenario, opportunity and uncertainty.
    """

    forest_pct = fmt(metric(data["basic"], "percentatge_coberta_forestal"), 1, "%")
    grass_pct = fmt(metric(data["basic"], "percentatge_prats_pastures_herbassars"), 1, "%")
    hic_ha = fmt(metric(data["basic"], "superficie_hic"), 0)
    species_count = metric(data["basic"], "nombre_especies_registrades")
    records_count = metric(data["basic"], "nombre_registres_biodiversitat")
    recent_records = metric(data["basic"], "nombre_registres_recents")
    habitats_count = metric(data["basic"], "nombre_habitats")
    agricultural_pct = fmt(metric(data["basic"], "percentatge_agricola"), 2, "%")
    artificial_pct = fmt(metric(data["basic"], "percentatge_urba_artificial"), 2, "%")
    road_density = fmt(pressure_metric(data["pressure"], "osm_path_track_road_density"), 2)
    road_km = fmt(pressure_metric(data["pressure"], "osm_path_track_road_km"), 1)
    public_points = metric(data["basic"], "nombre_accessos_punts_us_public") or "0"
    water_km = fmt((num(row_value(data["hydrology"], "layer_id", "rius_aca_che", "length_km")) or 0) + (num(row_value(data["hydrology"], "layer_id", "eixos_drenatge", "length_km")) or 0), 2)
    mosaic_score = fmt(core_metric(data["core"], "CORE_01"), 1)
    habitat_score = fmt(core_metric(data["core"], "CORE_02"), 1)
    refuges_score = fmt(core_metric(data["core"], "CORE_04"), 1)
    vulnerability_score = fmt(core_metric(data["core"], "CORE_05"), 1)
    biodiversity_score = fmt(core_metric(data["core"], "CORE_06"), 1)
    pressure_score = fmt(core_metric(data["core"], "CORE_07"), 1)
    connectivity_score = fmt(core_metric(data["core"], "CORE_08"), 1)
    fire_score = fmt(core_metric(data["core"], "CORE_09"), 1)
    water_score = fmt(core_metric(data["core"], "CORE_10"), 1)
    restoration_score = fmt(core_metric(data["core"], "CORE_11"), 1)
    management_score = fmt(core_metric(data["core"], "CORE_12"), 1)
    copernicus_meta = data.get("teledeteccio", {})
    copernicus_scene = copernicus_meta.get("scene_id") or "escena no identificada"
    copernicus_capture = copernicus_meta.get("capture_date") or "data no identificada"
    copernicus_cloud = copernicus_meta.get("cloud_cover_percent")
    copernicus_cloud_text = fmt(copernicus_cloud, 1, "%") if copernicus_cloud is not None else "núvol no documentat"
    copernicus_catalog_status = copernicus_meta.get("status", "no consultat")
    top_groups = ", ".join(
        f"{row.get('grup_taxonomic', '')} ({row.get('nombre_especies', '')} taxons)"
        for row in data["biodiv"][:3]
    )
    top_species_names = ", ".join(row.get("scientificName", "") for row in data.get("top_species", [])[:3])

    expert: dict[int, dict[str, Any]] = {
        1: {
            "interpretation": (
                f"Alinya mostra un sistema ecològic amb alta responsabilitat de conservació: {hic_ha} ha d'HIC, "
                f"{species_count} taxons citats, connectivitat alta i una matriu forestal del {forest_pct}. El patró suggereix "
                "un paisatge on el tancament forestal i la persistència d'hàbitats valuosos conviuen amb espais oberts que actuen com a peces funcionals escasses."
            ),
            "limitations": (
                "La diagnosi és robusta per valors cartogràfics i coneixement públic, però encara és prudent en vegetació fisiològica, clima, aigua funcional i foc. Aquestes incerteses no anul·len la diagnosi: indiquen on una decisió podria canviar quan entri nova evidència."
            ),
            "implications": [
                "Si no s'actua, el tancament del paisatge pot reduir espais oberts funcionals.",
                "La primera oportunitat és conservar HIC i ecotons abans de restaurar.",
                "El treball de camp ha de validar humitat, punts d'aigua, prats i pressió real.",
            ],
        },
        2: {
            "interpretation": (
                "L'àrea delimitada és prou gran i contínua per analitzar processos de paisatge, no només parcel·les. La forma del límit incorpora vessants, carenes i fons de vall, de manera que la diagnosi pot relacionar topografia, cobertes, accessibilitat i hàbitats sense perdre el context funcional."
            ),
            "limitations": (
                "La geometria és sòlida, però el límit ecològic no sempre coincideix amb el límit administratiu o de projecte. Algunes dinàmiques - fauna mòbil, foc, aigua i connectivitat - poden originar-se fora de l'àrea."
            ),
            "implications": [
                "Interpretar pressions i corredors també a la vora del límit.",
                "No tancar actuacions sense comprovar propietat, governança i figures de protecció.",
                "Usar el perímetre com a frontera de càlcul, no com a frontera ecològica absoluta.",
            ],
        },
        3: {
            "interpretation": (
                "El mètode força una lectura escalonada: primer evidència, després indicador, després diagnosi i finalment decisió. Això evita que una dada cridanera governi tota la interpretació i permet relacionar hàbitats, pressió, connectivitat i incertesa en una mateixa lògica de gestió adaptativa."
            ),
            "limitations": (
                "La metodologia no pretén substituir estudis sectorials; els ordena. La incertesa no es resol amb narrativa, sinó amb noves fonts, camp i actualització iterativa dels indicadors."
            ),
            "implications": [
                "Les decisions robustes neixen de coincidència entre diverses evidències.",
                "Les decisions provisionals es converteixen en hipòtesis de treball de camp.",
                "Cada nova font ha de canviar una decisió, no només afegir una capa.",
            ],
        },
        4: {
            "interpretation": (
                "L'auditoria revela una asimetria típica en diagnosi ecològica automàtica: el territori i els hàbitats estan ben descrits, mentre que processos dinàmics - humitat vegetal, clima, freqüentació i ús agrari real - encara depenen de fonts pendents. Això orienta on invertir abans de prendre decisions fines."
            ),
            "limitations": (
                "Les absències no són un defecte menor: afecten sobretot l'estat actual de la vegetació, la vulnerabilitat climàtica, la resiliència al foc i la gestió agro-ramadera. Per això la confiança baixa només en els capítols afectats."
            ),
            "implications": [
                "Desbloquejar Copernicus i clima abans de zonificar estrès o refugis.",
                "Afegir SIGPAC/DUN abans d'interpretar gestió agrària.",
                "Usar la matriu de fonts com a pla de millora del producte.",
            ],
        },
        5: {
            "interpretation": (
                f"El paisatge funciona com una matriu forestal molt dominant ({forest_pct}) amb prats i herbassars limitats ({grass_pct}). "
                "Aquesta combinació és coherent amb un procés de tancament del paisatge, probablement vinculat a menor pressió agro-ramadera. El resultat és més continuïtat ecològica forestal, però menys diversitat estructural i menys hàbitats oberts."
            ),
            "limitations": (
                "La cartografia no explica per si sola si els espais oberts es mantenen per gestió activa, sòls pobres, pendent o història d'ús. Aquesta causa és clau per decidir si conservar, restaurar o deixar evolucionar."
            ),
            "implications": [
                "Sense gestió, els espais oberts poden continuar retrocedint.",
                "Els ecotons són oportunitats prioritàries per biodiversitat i mosaic.",
                "Cal evitar actuacions forestals homogènies que esborrin discontinuïtats útils.",
            ],
        },
        6: {
            "interpretation": (
                f"La gran superfície d'HIC ({hic_ha} ha) i la diversitat d'hàbitats indiquen que Alinya no és només una massa forestal extensa, sinó un mosaic amb responsabilitat de conservació europea. La singularitat no rau en una sola peça, sinó en la coexistència d'unitats forestals, obertes i rupícoles que poden respondre de manera diferent a una mateixa actuació."
            ),
            "limitations": (
                "La qualitat local dels polígons no es pot inferir només de la cartografia. L'estat de conservació real depèn de composició, estructura, pressions puntuals, invasores, regeneració i ús històric."
            ),
            "implications": [
                "Si s'intervé sense camp, el risc és degradar valors que el mapa no jerarquitza.",
                "La millor oportunitat és prioritzar unitats d'hàbitat, no sectors administratius.",
                "HIC i ecotons han de funcionar com a filtre previ de qualsevol actuació.",
            ],
        },
        7: {
            "interpretation": (
                "Les cobertes indiquen una estructura vegetal extensa, però no diuen si la vegetació està funcionant bé aquest any. En un sistema mediterrani de muntanya, vigor i humitat poden canviar ràpidament segons sequera, orientació i sòl; per això una massa aparentment estable pot contenir zones vulnerables invisibles en cartografia estàtica."
            ),
            "limitations": (
                "Sense NDVI, NDMI i NDWI no es pot distingir vigor, humitat foliar ni estrès hídric. La incertesa afecta especialment refugis climàtics, foc i restauració."
            ),
            "implications": [
                "Si no s'incorpora teledetecció, es pot confondre cobertura amb bon estat.",
                "L'oportunitat és detectar zones de decaïment abans que siguin visibles al camp.",
                "Les actuacions forestals han d'esperar la lectura d'humitat i vigor.",
            ],
        },
        8: {
            "interpretation": (
                "La topografia d'Alinya probablement crea un mosaic microclimàtic: obagues més estables, solanes més exposades i fons de vall amb possible efecte refugi si conserven aigua. Aquest procés pot explicar diferències de recuperació, humitat i vulnerabilitat que no es veuen en una mitjana climàtica."
            ),
            "limitations": (
                "La lectura encara és potencial perquè falten LST, clima i sèrie d'humitat vegetal. Sense aquestes dades no es pot afirmar quines zones funcionen realment com a refugi durant episodis extrems."
            ),
            "implications": [
                "Sense gestió, solanes i vessants secs poden acumular vulnerabilitat.",
                "Les obagues i punts d'aigua són candidats a conservació preventiva.",
                "Cal prioritzar camp en gradients solana-obaga i fonts permanents.",
            ],
        },
        9: {
            "interpretation": (
                f"La xarxa hídrica cartografiada ({water_km} km) i les fonts detectades suggereixen una estructura d'aigua fragmentada però ecològicament decisiva. En muntanya mediterrània, petits punts d'aigua poden concentrar biodiversitat, connectivitat local i refugi climàtic molt més enllà de la seva superfície."
            ),
            "limitations": (
                "La cartografia no indica permanència, cabal, qualitat ni ús per fauna. Una font cartografiada pot ser ecològicament clau o funcionalment seca segons estació i gestió."
            ),
            "implications": [
                "Si no es protegeixen punts d'aigua, es debiliten refugis i corredors locals.",
                "L'oportunitat és convertir fonts i cursos en eixos de seguiment climàtic.",
                "Cal validar temporalitat i pressions abans de restaurar o obrir accessos.",
            ],
        },
        10: {
            "interpretation": (
                f"Els {species_count} taxons citats indiquen un territori ben reconegut per observadors, però també reflecteixen biaixos d'esforç: plantes, ocells i insectes solen aparèixer més que grups nocturns, discrets o difícils d'identificar. El valor real és detectar on el coneixement és fort i on encara és cec."
            ),
            "limitations": (
                "GBIF i iNaturalist confirmen cites, no absències ni estat poblacional. Sense BDBC, camp i llistes normatives, les espècies protegides, indicadores o invasores no queden completament jerarquitzades."
            ),
            "implications": [
                "Sense mostreig dirigit es pot sobreprotegir el que és visible i ignorar el que és sensible.",
                "L'oportunitat és orientar inventaris cap a buits taxonòmics i hàbitats clau.",
                "Les cites recents han de guiar camp, no substituir-lo.",
            ],
        },
        11: {
            "interpretation": (
                "La connectivitat alta no significa absència de problemes; significa que encara existeix una matriu capaç de sostenir fluxos ecològics. El repte és evitar que petites barreres, accessos o canvis d'ús fragmentin gradualment una funcionalitat que avui sembla favorable."
            ),
            "limitations": (
                "La connectivitat funcional varia segons espècie, mobilitat, sensibilitat a pertorbació i dependència d'aigua. Les dades actuals descriuen estructura territorial, no moviment real."
            ),
            "implications": [
                "Si no es protegeixen corredors, la pèrdua serà acumulativa i poc visible.",
                "L'oportunitat és conservar connectivitat abans que calgui restaurar-la.",
                "Camins, hàbitats i aigua s'han de llegir conjuntament.",
            ],
        },
        12: {
            "interpretation": (
                f"La xarxa de {road_km} km i una densitat de {road_density} km/km2 indiquen accessibilitat suficient per generar tensions locals, encara que no mesurin visitants. La pressió ecològica probable no és homogènia: es concentra on accessos, punts d'ús públic, HIC i fauna sensible coincideixen."
            ),
            "limitations": (
                "OSM descriu infraestructura, no intensitat. Sense comptadors, gestors, observació de camp o font compatible legalment, no es pot atribuir freqüentació real."
            ),
            "implications": [
                "Sense ordenació, els punts accessibles poden erosionar tranquil·litat ecològica.",
                "L'oportunitat és actuar preventivament on pressió potencial i valor coincideixen.",
                "La gestió d'ús públic ha de basar-se en conflictes verificats.",
            ],
        },
        13: {
            "interpretation": (
                "La dominància forestal pot respondre a recuperació natural, abandonament d'usos oberts o maduració de masses. Aquest procés pot augmentar hàbitats forestals, ombra i connectivitat, però també reduir heterogeneïtat i concentrar combustible si no hi ha discontinuïtats funcionals."
            ),
            "limitations": (
                "Sense estructura forestal - edat, densitat, regeneració, fusta morta i combustible - no es pot saber si el bosc és madur, simplificat, resilient o vulnerable."
            ),
            "implications": [
                "Si no es gestiona el mosaic, pot augmentar la continuïtat del combustible.",
                "L'oportunitat és compatibilitzar maduresa forestal i espais oberts clau.",
                "Les actuacions silvícoles han de ser selectives i justificades per hàbitat.",
            ],
        },
        14: {
            "interpretation": (
                "La resiliència al foc depèn de la relació entre tancament forestal, discontinuïtats, pendent, accessos i humitat. A Alinya, el senyal forestal dominant fa plausible una continuïtat de combustible, però el mosaic, els prats i la xarxa de camins poden funcionar com a oportunitats de gestió si es validen sobre el terreny."
            ),
            "limitations": (
                "Sense NDMI, LST i model de combustible no es pot transformar aquesta lectura en risc final. La incertesa és crítica perquè una actuació mal situada pot reduir biodiversitat sense millorar resiliència."
            ),
            "implications": [
                "Sense actuació fina, la continuïtat forestal pot augmentar vulnerabilitat futura.",
                "L'oportunitat és reforçar mosaic protector sense simplificar HIC.",
                "Cal prioritzar zones on combustible, pendent i baix valor sensible coincideixin.",
            ],
        },
        15: {
            "interpretation": (
                "El potencial de restauració no s'ha d'entendre com una crida a intervenir més, sinó a intervenir millor. En un espai amb valors alts, restaurar pot significar mantenir processos: aigua funcional, ecotons, espais oberts, connectivitat i baixa pertorbació."
            ),
            "limitations": (
                "Sense camp, teledetecció i degradació local, no es pot distingir una zona realment degradada d'una zona naturalment oberta, seca o de baixa cobertura."
            ),
            "implications": [
                "Si es restaura sense diagnosi fina, es poden perdre hàbitats valuosos.",
                "L'oportunitat és restaurar funcions, no només cobertes.",
                "Les accions han de començar per zones amb benefici múltiple i baix risc.",
            ],
        },
        16: {
            "interpretation": (
                "La gestió òptima no és la que maximitza un indicador, sinó la que resol tensions entre valors: hàbitats alts, pressió potencial, connectivitat i incertesa climàtica. EcoRadar apunta una estratègia conservadora: protegir el que ja funciona i validar abans d'intervenir on falta evidència."
            ),
            "limitations": (
                "La priorització és ecològica; encara necessita encaix amb propietat, pressupost, normativa, acceptació social i capacitat operativa."
            ),
            "implications": [
                "Sense governança, bones recomanacions poden quedar sense execució.",
                "L'oportunitat és convertir la diagnosi en cartera d'actuacions escalonada.",
                "Cada actuació ha de tenir indicador de seguiment i criteri d'èxit.",
            ],
        },
        17: {
            "interpretation": (
                "La síntesi mostra un sistema en equilibri delicat: alt valor i bona connectivitat, però amb risc de simplificació si el tancament forestal continua i si la pressió humana es concentra en punts sensibles. La clau no és triar entre conservar o actuar, sinó decidir on la inacció també és una forma de pèrdua."
            ),
            "limitations": (
                "La lectura integrada encara és més robusta per valors i estructura que per processos dinàmics. Vegetació actual, clima, foc i aigua poden modificar prioritats quan entrin noves dades."
            ),
            "implications": [
                "Sense seguiment, els canvis graduals poden passar desapercebuts.",
                "L'oportunitat és anticipar-se abans que la restauració sigui més costosa.",
                "Les prioritats han de revisar-se quan s'actualitzin les fonts crítiques.",
            ],
        },
        18: {
            "interpretation": (
                "Les recomanacions s'ordenen per dependència ecològica: primer protegir valors que ja són evidents, després validar processos que poden canviar decisions i finalment transformar oportunitats en actuacions. Això evita que la restauració s'avanci a la comprensió del sistema."
            ),
            "limitations": (
                "Algunes recomanacions són encara pre-actuacions: completar dades, validar camp i reduir incertesa. No són febles; són necessàries perquè una actuació posterior sigui defensable."
            ),
            "implications": [
                "Sense aquesta seqüència, es pot gastar esforç en actuacions poc determinants.",
                "L'oportunitat és crear un pla de treball per fases i evidències.",
                "Cada recomanació s'ha de vincular a localització, benefici i indicador.",
            ],
        },
        19: {
            "interpretation": (
                "La validació confirma que el sistema és tècnicament coherent i ecològicament prudent: no tanca com a definitius els blocs que depenen de fonts incompletes. Això és important perquè la credibilitat d'una diagnosi no depèn de dir-ho tot, sinó de saber fins on pot afirmar."
            ),
            "limitations": (
                "La validació és un control de coherència, no una auditoria de camp. Les conclusions provisionals continuen exigint verificació territorial."
            ),
            "implications": [
                "Sense validació, la diagnosi podria sobreinterpretar dades parcials.",
                "L'oportunitat és usar la checklist com a pont entre informe i camp.",
                "La propera versió ha de reduir avisos, no amagar-los.",
            ],
        },
        20: {
            "interpretation": (
                "Les limitacions principals no són burocràtiques: indiquen processos ecològics que encara no es poden llegir bé. Sense humitat vegetal no es veu estrès; sense freqüentació no es veu pertorbació real; sense camp no es confirma qualitat d'hàbitats ni funcionalitat d'aigua."
            ),
            "limitations": (
                "El risc més gran seria convertir aquestes mancances en conclusions fortes. EcoRadar les manté visibles perquè condicionen directament gestió, restauració i seguiment."
            ),
            "implications": [
                "Sense completar dades, algunes decisions seguiran sent reversibles o preliminars.",
                "L'oportunitat és prioritzar fonts segons impacte real en decisions.",
                "Cada incertesa crítica ha de tenir una acció de resolució assignada.",
            ],
        },
        21: {
            "interpretation": (
                "La conclusió ecològica central és que Alinya no necessita una gestió intensiva generalitzada, sinó una gestió fina del contrast: conservar grans valors, mantenir discontinuïtats, evitar pressions en punts sensibles i completar informació allà on una decisió podria ser irreversible."
            ),
            "limitations": (
                "Aquesta conclusió és una diagnosi integrada, no un projecte executiu. El pas següent és convertir-la en zonificació validada, calendari, pressupost i responsables."
            ),
            "implications": [
                "Sense acció selectiva, el territori pot perdre mosaic abans de perdre superfície natural.",
                "L'oportunitat és gestionar abans que el problema sigui evident.",
                "El criteri rector ha de ser conservar processos, no només cobertes.",
            ],
        },
        22: {
            "interpretation": (
                "Els annexos no són un apèndix administratiu: són la garantia que cada lectura ecològica pot ser revisada, repetida i millorada. En una metodologia aplicable a molts espais, aquesta traçabilitat és el que permet comparar diagnòstics sense perdre rigor local."
            ),
            "limitations": (
                "La traçabilitat documental no substitueix la qualitat de les fonts originals. Quan una font és parcial, manual o condicionada, el seu paper queda limitat en la diagnosi."
            ),
            "implications": [
                "Sense traçabilitat, la diagnosi perd defensabilitat tècnica.",
                "L'oportunitat és actualitzar l'informe sense canviar el mètode.",
                "Les fonts absents han de quedar tan documentades com les fonts usades.",
            ],
        },
    }

    deep_reading: dict[int, dict[str, Any]] = {
        1: {
            "result_note": (
                f"Resultats clau: {forest_pct} de coberta forestal, {grass_pct} de prats/herbassars, "
                f"{hic_ha} ha d'HIC, {species_count} taxons i pressió potencial {pressure_score}/100."
            ),
            "indicator_note": (
                f"Hàbitats {habitat_score}/100 i biodiversitat {biodiversity_score}/100 indiquen valor alt; "
                f"mosaic {mosaic_score}/100 i connectivitat {connectivity_score}/100 mostren una estructura funcional; "
                "vegetació, clima, foc i aigua queden condicionats per fonts dinàmiques parcials."
            ),
            "interpretation": (
                f"Alinya no presenta només molta natura: presenta una estructura de muntanya on el bosc domina ({forest_pct}) "
                f"i els espais oberts són proporcionalment escassos ({grass_pct}), però molt rellevants perquè introdueixen llum, "
                "ecotons, recursos tròfics i discontinuïtat del combustible. La combinació d'HIC extensos, alta biodiversitat coneguda "
                "i bona connectivitat suggereix un espai amb una base ecològica forta, però també amb risc de simplificació si el mosaic "
                "es tanca i la gestió deixa de mantenir contrastos estructurals."
            ),
            "limitations": (
                "La conclusió sobre valor ecològic és consistent perquè coincideixen hàbitats, cobertes, biodiversitat pública i connectivitat. "
                "La conclusió sobre estat fisiològic, vulnerabilitat climàtica i resiliència al foc és provisional perquè falten NDVI, NDMI, LST, "
                "clima i combustible. Això obliga a distingir conservació preventiva - ja defensable - de zonificació fina - encara pendent."
            ),
            "implications": [
                "Si el tancament continua, no només es perden prats: es redueixen zones d'alimentació, floració, caça, termoregulació i transició entre hàbitats, i el sistema tendeix a una matriu més homogènia.",
                "La gestió ha de mantenir peces obertes i ecotons allà on reforcin HIC, biodiversitat i discontinuïtat, evitant obrir zones sensibles sense evidència.",
                "La pròxima decisió útil és separar tres àmbits: zones de conservació estricta, zones de mosaic a mantenir i zones on cal validar humitat, aigua i pressió real abans d'actuar.",
            ],
        },
        2: {
            "result_note": (
                f"L'àrea validada té {fmt(data['study'].get('surface_ha'), 1)} ha i un perímetre de "
                f"{fmt(data['study'].get('perimeter_m'), 0)} m en {data['study'].get('final_crs', 'EPSG:25831')}."
            ),
            "rows": [
                ["Lectura espacial", "Resultat", "Què implica", "Decisió de gestió"],
                ["Superfície", fmt(data["study"].get("surface_ha"), 1), "escala suficient per processos de paisatge", "planificar per unitats funcionals"],
                ["Perímetre", fmt(data["study"].get("perimeter_m"), 0), "molta relació amb vores i entrades", "mirar pressions també al límit"],
                ["Context", "vessants, carenes i fondalades", "aigua, foc i fauna travessen el polígon", "definir zona d'influència"],
                ["CRS", data["study"].get("final_crs", "EPSG:25831"), "càlcul coherent amb cartografia catalana", "comparar capes oficials"],
            ],
            "widths": [38 * mm, 34 * mm, 50 * mm, 48 * mm],
            "indicator_note": (
                "La delimitació no és només un polígon: determina quines pressions entren, quins processos travessen el límit i quines actuacions necessiten coordinació externa."
            ),
            "interpretation": (
                "La delimitació d'Alinya és prou extensa per llegir processos de paisatge, però no s'ha d'entendre com una frontera ecològica tancada. El perímetre llarg indica molta superfície de contacte amb accessos, drenatges, vessants i continuïtats externes. Això vol dir que una decisió dins l'àrea pot dependre d'allò que passa fora: un camí que entra, una carena que propaga foc, un curs que drena des de fora o una espècie que utilitza l'espai només parcialment."
            ),
            "limitations": (
                "La geometria és fiable, però encara no incorpora propietat, convenis, figures de protecció, drets d'ús ni zones amb restriccions operatives. Sense aquesta capa de governança, la diagnosi pot orientar prioritats però no ordenar execució administrativa."
            ),
            "implications": [
                "Si es gestiona només dins el polígon, es poden tractar símptomes però no causes: accessos, foc, aigua i fauna poden estar governats per continuïtats externes.",
                "Cal definir una zona d'influència per revisar camins d'entrada, drenatges, carenes, punts d'aigua i corredors que condicionen el funcionament intern.",
                "Abans de convertir recomanacions en obra, el límit ecològic s'ha de creuar amb propietat, servituds, permisos i responsabilitats de manteniment.",
            ],
        },
        3: {
            "result_note": (
                "El flux ha generat auditoria de fonts, indicadors Radar, diagnosi, recomanacions i validació. "
                f"Copernicus ja aporta catàleg STAC real: {copernicus_capture}, {copernicus_cloud_text} de núvols."
            ),
            "rows": [
                ["Decisió de gestió", "Evidència disponible", "Què permet decidir", "Què no tanca encara"],
                ["Conservar valors coneguts", "HIC, hàbitats, cobertes, biodiversitat", "prudència i no deteriorament", "qualitat local sense camp"],
                ["Mantenir mosaic", f"{forest_pct} forestal i {grass_pct} oberts", "prioritzar ecotons i prats funcionals", "causa i gestió agrària fina"],
                ["Llegir vegetació actual", f"STAC: {copernicus_capture}", "escena candidata localitzada", "cal token per NDVI/NDMI/NDWI"],
                ["Ordenar actuacions", "Radar, diagnosi i validació", "què és robust o provisional", "cost, propietat i calendari"],
            ],
            "widths": [42 * mm, 48 * mm, 40 * mm, 40 * mm],
            "indicator_note": (
                "Aquesta pàgina no és una explicació del mètode: és el tauler de què es pot decidir avui. "
                "Quan una evidència és parcial, només habilita validació o actuacions reversibles."
            ),
            "interpretation": (
                "La lectura aplicada ja permet decisions de primer nivell: conservar els valors cartogràfics robustos, evitar actuacions homogènies en HIC, mantenir el mosaic que sosté discontinuïtats i preparar camp allà on els indicadors són parcials. La dada nova de Copernicus és important: el problema no és trobar una escena, perquè el catàleg oficial ja n'ha identificat una; el coll d'ampolla és convertir les bandes oficials en índexs validats. Això transforma una incertesa genèrica en una tasca concreta."
            ),
            "limitations": (
                "La metodologia és sòlida per separar decisions immediates i decisions condicionades. Sense token Copernicus no es poden calcular NDVI, NDMI ni NDWI; sense camp no es pot confirmar qualitat local; sense governança no es pot convertir prioritat ecològica en execució."
            ),
            "implications": [
                "Decisió immediata: conservar i no deteriorar HIC, ecotons i espais oberts funcionals perquè diverses fonts ja coincideixen en el seu valor.",
                "Decisió condicionada: no zonificar estrès, refugis, foc o restauració fina fins processar l'escena Sentinel i validar punts crítics al camp.",
                "Pas operatiu: obtenir credencial Copernicus/Sentinel Hub o token CDSE, executar bandes B03, B04, B08 i B11, i actualitzar Radar abans de tancar actuacions de vegetació, clima i foc.",
            ],
        },
        4: {
            "result_note": (
                f"L'auditoria ja no diu només 'pendent': Copernicus STAC està {copernicus_catalog_status} i identifica {copernicus_scene} ({copernicus_capture}, {copernicus_cloud_text})."
            ),
            "rows": [
                ["Bloc crític", "Resultat obtingut", "Decisió que habilita", "Desbloqueig pendent"],
                ["Copernicus", f"escena {copernicus_capture}, {copernicus_cloud_text}", "seleccionar imatge d'estiu", "token per bandes i Process API"],
                ["Clima", "fonts API definides", "saber què cal demanar", "claus Meteocat/AEMET/SPEI"],
                ["Agrari", f"{agricultural_pct} agrícola per cobertes", "no sobredimensionar agricultura", "SIGPAC/DUN per ús real"],
                ["Camp", "checklist generada", "validar punts sensibles", "sortida de camp i metadades"],
            ],
            "widths": [34 * mm, 48 * mm, 42 * mm, 46 * mm],
            "indicator_note": (
                "La matriu de fonts ha de llegir-se com una llista de decisions desbloquejades o bloquejades, no com una taula tècnica."
            ),
            "interpretation": (
                "L'auditoria ara diferencia tres situacions. Primera: fonts que ja permeten decisió, com cobertes, hàbitats, biodiversitat pública, hidrologia base, relleu i accessibilitat. Segona: fonts que ja s'han localitzat però encara no es poden processar, com Copernicus, on l'escena existeix però cal autorització per descarregar o processar bandes. Tercera: fonts que requereixen conveni, clau o camp, com Meteocat/AEMET, SIGPAC/DUN, BDBC i freqüentació real. Aquesta distinció és útil perquè diu on cal insistir i què canviarà quan entri cada font."
            ),
            "limitations": (
                "La diagnosi territorial i d'hàbitats és defensable; la diagnosi de processos dinàmics encara és incompleta. No es pot convertir una escena STAC en NDVI sense bandes processades, ni una API definida en clima sense clau i consulta real."
            ),
            "implications": [
                "Copernicus és la prioritat tècnica: ja hi ha escena candidata; amb credencials es poden generar NDVI, NDMI i NDWI i revisar vegetació, refugis, foc i restauració.",
                "Clima i SPEI són la prioritat interpretativa: sense sequera i anomalies, els refugis climàtics continuen sent potencials i no zonificació definitiva.",
                "SIGPAC/DUN i camp són la prioritat de gestió: expliquen si els espais oberts són residuals, actius o recuperables, i quina eina de gestió els pot mantenir.",
            ],
        },
        5: {
            "result_note": (
                f"Cobertes principals: {forest_pct} forestal, {grass_pct} prats/herbassars, {agricultural_pct} agrícola i {artificial_pct} artificial; mosaic Radar {mosaic_score}/100."
            ),
            "indicator_note": (
                f"Un mosaic {mosaic_score}/100 és alt, però el {forest_pct} forestal mostra que la diversitat depèn de peces obertes petites i de la seva posició, no de grans superfícies agrícoles."
            ),
            "interpretation": (
                "La lectura territorial apunta a un paisatge en procés de tancament: els boscos densos i clars formen el cos principal del sistema, mentre que prats i herbassars conserven una funció desproporcionada respecte de la seva superfície. Aquests espais oberts poden sostenir pol·linitzadors, flora heliòfila, zones de caça per rapinyaires, punts de pas i discontinuïtats contra grans continuïtats forestals. El problema ecològic no és que hi hagi bosc, sinó que el sistema perdi contrast."
            ),
            "limitations": (
                "No es pot atribuir la causa del tancament només amb cobertes: pot respondre a abandonament ramader, successió natural, gestió forestal limitada o condicions edàfiques. Aquesta causa importa perquè una resposta de pastura, sega, aclarida o no intervenció no té el mateix efecte."
            ),
            "implications": [
                "Si no s'actua, el risc no és només perdre hectàrees de prat, sinó perdre funcions: aliment, llum, floració, zones de termoregulació i transicions que fan el paisatge més resilient.",
                "L'oportunitat és identificar prats, clarianes i marges que connectin valors: HIC, aigua, fauna coneguda i discontinuïtat forestal.",
                "La gestió hauria de mantenir mosaic amb intervencions fines i recurrents, no amb grans transformacions que substitueixin complexitat per simplificació.",
            ],
        },
        6: {
            "result_note": (
                f"S'han identificat {habitats_count} hàbitats i {hic_ha} ha d'HIC; el valor d'hàbitats és {habitat_score}/100."
            ),
            "indicator_note": (
                f"Un valor {habitat_score}/100 és molt alt: indica responsabilitat de conservació, però no autoritza a assumir que tots els polígons tenen el mateix estat ni la mateixa sensibilitat."
            ),
            "interpretation": (
                "El bloc d'hàbitats és el nucli de responsabilitat ecològica d'Alinya. La combinació d'una gran superfície d'HIC i molts tipus d'hàbitat indica que les decisions de gestió han de ser diferenciades: allò que beneficia un hàbitat obert pot perjudicar un hàbitat forestal madur, i una actuació positiva per reduir combustible pot ser negativa si afecta una comunitat prioritària o un ecotò sensible. La gestió ha de llegir el territori per unitats ecològiques, no per grans taques administratives."
            ),
            "limitations": (
                "La cartografia dona distribució i responsabilitat, però no estat de conservació local: estructura, composició florística, presència d'invasores, compactació, regeneració o impacte d'herbivoria requereixen camp."
            ),
            "implications": [
                "Si es gestionen els HIC com una capa uniforme, es pot protegir superfície però perdre qualitat ecològica.",
                "L'oportunitat és crear una jerarquia de prudència: HIC prioritaris i hàbitats sensibles primer, ecotons després, i zones degradades només quan estiguin validades.",
                "Qualsevol actuació de restauració, ús públic o prevenció d'incendis ha de passar per un filtre d'hàbitats abans de definir maquinària, calendari i intensitat.",
            ],
        },
        7: {
            "result_note": (
                "NDVI, NDMI, NDWI i LST no estan disponibles; l'informe només pot llegir estructura vegetal a partir de cobertes i hàbitats."
            ),
            "indicator_note": (
                "CORE_03 és no disponible: això no vol dir que no hi hagi estrès vegetal, sinó que encara no hi ha evidència remota validada per mesurar-lo."
            ),
            "interpretation": (
                "La vegetació d'Alinya es veu extensa i estructuralment dominant, però la pregunta de gestió important és si aquesta vegetació manté vigor i humitat en períodes crítics. En sistemes mediterranis de muntanya, dues masses amb la mateixa coberta poden funcionar de manera molt diferent segons orientació, sòl, densitat i sequera acumulada. Per això, sense teledetecció, la diagnosi pot dir on hi ha vegetació, però no on comença a fallar funcionalment."
            ),
            "limitations": (
                "L'absència de NDVI, NDMI, NDWI i LST impedeix detectar decaïment, estrès hídric, anomalies d'estiu i zones amb recuperació lenta. Aquesta limitació afecta també refugis, vulnerabilitat, foc i restauració."
            ),
            "implications": [
                "Si es prenen decisions només amb cobertes, es pot prioritzar una massa aparentment estable mentre una altra, menys visible, acumula estrès i risc de pèrdua de vigor.",
                "L'oportunitat és usar Sentinel per detectar gradients de vigor i humitat i dirigir el camp cap a zones on el problema encara no és evident.",
                "Fins que no hi hagi índexs, les actuacions forestals o de restauració han de ser prudents i justificades per hàbitat, mosaic i observació local.",
            ],
        },
        8: {
            "result_note": (
                f"Refugis climàtics {refuges_score}/100 i vulnerabilitat climàtica {vulnerability_score}/100, tots dos parcials per manca de LST, NDMI, clima i SPEI."
            ),
            "indicator_note": (
                "Els valors actuals són proxies estructurals: orientació, coberta, relleu i aigua indiquen potencial, però no confirmen temperatura ni estrès real."
            ),
            "interpretation": (
                "La diagnosi climàtica suggereix que Alinya pot tenir una forta heterogeneïtat microclimàtica: obagues i fons de vall poden conservar humitat i temperatures més moderades, mentre que solanes, pendents exposats i zones amb baixa cobertura poden acumular estrès. Aquesta diferència és crítica perquè el canvi climàtic no afecta el territori de manera uniforme; reorganitza quines zones funcionen com a refugi i quines esdevenen punts de vulnerabilitat."
            ),
            "limitations": (
                "Sense LST, NDMI, SPEI i sèries Meteocat/AEMET, el sistema no pot confirmar quines zones amortitzen episodis extrems ni quines pateixen escalfament superficial o sequera recurrent."
            ),
            "implications": [
                "Si no s'identifiquen refugis, la gestió pot perdre les zones que mantindran biodiversitat durant onades de calor i sequeres llargues.",
                "L'oportunitat és conservar obagues, fons frescals i punts d'aigua com a infraestructura ecològica d'adaptació climàtica.",
                "Les actuacions a solanes i vessants secs han de valorar si restauren funció o si poden augmentar exposició, erosió i estrès.",
            ],
        },
        9: {
            "result_note": (
                f"La base hidrològica detecta {water_km} km de cursos/drenatge i fonts cartografiades; funcionalitat hídrica {water_score}/100 parcial."
            ),
            "indicator_note": (
                f"Un valor {water_score}/100 indica presència d'estructura hídrica, però no qualitat, permanència ni valor real per fauna."
            ),
            "interpretation": (
                "La hidrologia d'Alinya s'ha de llegir com una xarxa de punts i línies petites amb funció ecològica gran. En ambients mediterranis, una font permanent, una bassa funcional o un tram ombrívol poden actuar com a refugi climàtic, connector de fauna, punt de reproducció i concentrador de pressió alhora. Per això l'aigua no és només un recurs físic; és un organitzador del comportament de la fauna i de les prioritats de conservació."
            ),
            "limitations": (
                "Les dades actuals no informen permanència, cabal, qualitat, abeurament, trepig, espècies associades ni pressions locals. Sense NDWI i camp, no es pot convertir presència cartogràfica en funcionalitat ecològica completa."
            ),
            "implications": [
                "Si fonts i basses es degraden o s'assequen, l'efecte pot ser desproporcionat: es perden refugis, reproducció d'amfibis, punts d'abeurada i nodes de connectivitat.",
                "L'oportunitat és fer una auditoria de punts d'aigua amb permanència, qualitat, accessibilitat per fauna i conflictes d'ús.",
                "Les actuacions d'ús públic o ramaderia han d'evitar concentrar pressió sobre els pocs punts hídrics funcionals.",
            ],
        },
        10: {
            "result_note": (
                f"Biodiversitat pública: {records_count} registres, {species_count} taxons, {recent_records} registres recents; grups principals: {top_groups}. Taxons destacats per cites: {top_species_names or 'pendent de lectura detallada'}."
            ),
            "indicator_note": (
                f"Biodiversitat coneguda {biodiversity_score}/100 és molt alta com a coneixement disponible, però no equival a inventari complet ni a estat poblacional."
            ),
            "interpretation": (
                "Les dades de biodiversitat indiquen que Alinya és un territori amb alta densitat d'observacions útils, especialment en plantes, ocells i insectes. Això és valuós perquè permet orientar ràpidament mostreigs i detectar hàbitats d'interès, però també pot enganyar: els grups més visibles i observats tendeixen a dominar el relat, mentre que quiròpters, invertebrats especialistes, flora discreta, amfibis estacionals o espècies nocturnes poden quedar infrarepresentats."
            ),
            "limitations": (
                "GBIF i iNaturalist documenten cites i esforç d'observació, no absències. Sense BDBC, protocols de camp i creuament normatiu, no es pot tancar una lectura de protegides, amenaçades, invasores o indicadores."
            ),
            "implications": [
                "Si es gestiona només segons cites disponibles, es pot protegir el que és fàcil d'observar i deixar sense atenció espècies més sensibles o menys detectables.",
                "L'oportunitat és transformar les dades públiques en un pla de mostreig: confirmar grups forts, omplir buits i revisar hàbitats amb alta probabilitat d'espècies indicadores.",
                "Les decisions sobre calendari d'obres, ús públic o restauració han d'incorporar una verificació de camp en hàbitats i èpoques sensibles.",
            ],
        },
        11: {
            "result_note": (
                f"Connectivitat ecològica {connectivity_score}/100, alimentada per cobertes, hàbitats, hidrologia, infraestructura verda i accessibilitat."
            ),
            "indicator_note": (
                f"Un valor {connectivity_score}/100 alt indica una matriu permeable, però no garanteix connectivitat per totes les espècies ni absència de barreres locals."
            ),
            "interpretation": (
                "La connectivitat d'Alinya és una fortalesa perquè la matriu natural encara pot facilitar fluxos ecològics entre hàbitats, vessants i corredors hídrics. Però aquesta connectivitat és vulnerable a degradacions petites i acumulatives: un camí molt freqüentat, una tanca, una pista ampliada o un punt d'ús públic mal situat poden no canviar el mapa general, però sí alterar moviments de fauna sensible, tranquil·litat i ús de punts d'aigua."
            ),
            "limitations": (
                "La diagnosi és estructural, no específica per espècie. No incorpora telemetria, atropellaments, barreres fines, soroll, llum nocturna ni freqüentació real."
            ),
            "implications": [
                "Si no es preserven els corredors abans de perdre'ls, la restauració posterior serà més cara i menys efectiva.",
                "L'oportunitat és identificar corredors que combinin hàbitats, aigua i baixa pressió, i blindar-los en la planificació d'ús públic.",
                "Qualsevol nova infraestructura o intensificació d'ús ha d'avaluar efecte barrera, no només ocupació superficial.",
            ],
        },
        12: {
            "result_note": (
                f"Ús públic potencial: {road_km} km de camins/pistes, {road_density} km/km2 i {public_points} punts d'accés o ús públic; pressió Radar {pressure_score}/100."
            ),
            "indicator_note": (
                f"Un valor {pressure_score}/100 mitjà indica accessibilitat significativa, no freqüentació real. El risc apareix quan accessos coincideixen amb HIC, punts d'aigua o fauna sensible."
            ),
            "interpretation": (
                "La pressió humana d'Alinya s'ha d'interpretar com a capacitat d'entrada al sistema, no com a nombre de visitants. La xarxa existent pot ser compatible amb la conservació si canalitza usos cap a zones robustes, però pot generar conflicte si facilita entrada a punts ecològicament delicats. El patró de gestió important és la concentració: pocs punts mal ordenats poden tenir més impacte que molts camins poc utilitzats."
            ),
            "limitations": (
                "Sense comptadors, observació de camp, dades dels gestors o fonts de heatmap legalment compatibles, no es pot estimar intensitat real, estacionalitat ni tipus d'usuari."
            ),
            "implications": [
                "Si no s'ordena l'accés, la pressió pot desplaçar fauna, erosionar punts sensibles i degradar fonts o miradors sense que el mapa de camins canviï.",
                "L'oportunitat és dissenyar zones de recepció, itineraris recomanats i zones de tranquil·litat abans que aparegui conflicte consolidat.",
                "Cal validar sobre el terreny quins punts tenen aparcament informal, ús recurrent, residus, trepig, gossos o activitats incompatibles.",
            ],
        },
        13: {
            "result_note": (
                f"La massa forestal domina el paisatge ({forest_pct}); el sistema diferencia boscos densos, boscos clars, matollars, bosc de ribera i prats."
            ),
            "indicator_note": (
                "La dominància forestal és una oportunitat per maduresa i connectivitat, però pot reduir heterogeneïtat i augmentar continuïtat de combustible si no hi ha discontinuïtats funcionals."
            ),
            "interpretation": (
                "La diagnosi forestal apunta a un territori on el bosc és el component estructurant. Això pot representar recuperació natural i major coberta protectora del sòl, però també un procés de simplificació si totes les masses tendeixen a densificar-se sense clarianes, ecotons ni gradients d'edat. El valor forestal no es mesura només per superfície: depèn de maduresa, estrats, fusta morta, regeneració, espècies dominants i relació amb espais oberts."
            ),
            "limitations": (
                "Falten dades d'estructura forestal, inventari de masses, combustible, edat, densitat, decaïment i biodiversitat forestal específica. Per això no es pot prescriure silvicultura detallada."
            ),
            "implications": [
                "Si el bosc es densifica sense mosaic, pot augmentar competència hídrica, continuïtat del combustible i pèrdua d'espais oberts funcionals.",
                "L'oportunitat és combinar zones de no intervenció o maduració amb zones de gestió selectiva del mosaic, sempre filtrades per hàbitats.",
                "Les accions forestals han d'evitar una lectura productivista simple: l'objectiu és estructura ecològica, no només reducció de biomassa.",
            ],
        },
        14: {
            "result_note": (
                f"Resiliència davant del foc {fire_score}/100 parcial; combina cobertes forestals, pendent/DEM, incendis històrics, accessos i aigua, però falten NDMI, LST i combustible oficial."
            ),
            "indicator_note": (
                f"Un valor {fire_score}/100 mitjà no és risc d'incendi: és una lectura parcial de capacitat del territori per resistir i recuperar-se."
            ),
            "interpretation": (
                "El foc s'ha de llegir com a procés ecològic i de gestió, no només com a perill. La dominància forestal pot generar continuïtat, mentre que prats, roquissars, conreus residuals, camins i punts d'aigua poden introduir discontinuïtats. La pregunta clau no és on hi ha risc en abstracte, sinó on una actuació podria reduir continuïtat sense destruir hàbitats valuosos, i on la no intervenció podria deixar créixer una vulnerabilitat estructural."
            ),
            "limitations": (
                "Sense model de combustible, NDMI, LST i dades climàtiques, no es pot delimitar risc final ni severitat probable. Una actuació de prevenció mal situada pot empobrir biodiversitat i no millorar resiliència."
            ),
            "implications": [
                "Si no es manté mosaic, un incendi futur podria trobar menys discontinuïtats i afectar hàbitats d'alt valor amb més severitat.",
                "L'oportunitat és prioritzar actuacions de baix impacte en zones on discontinuïtat, accessibilitat i menor sensibilitat d'hàbitat coincideixin.",
                "La prevenció ha d'estar subordinada a una doble pregunta: redueix propagació i manté o millora valor ecològic?",
            ],
        },
        15: {
            "result_note": (
                f"Potencial de restauració {restoration_score}/100 parcial; alt com a oportunitat agregada, però sense zones finals perquè falten camp, Sentinel, degradació local i hàbitats font."
            ),
            "indicator_note": (
                f"Un valor {restoration_score}/100 alt no vol dir actuar a tot arreu; vol dir que hi ha marge de millora si es localitzen funcions degradades."
            ),
            "interpretation": (
                "La restauració a Alinya ha de ser funcional, no cosmètica. En un espai amb alt valor d'hàbitats, restaurar no significa transformar grans superfícies, sinó recuperar processos: mantenir espais oberts on sostenen biodiversitat, millorar punts d'aigua, reforçar ecotons, reduir pressions puntuals i augmentar resiliència climàtica o davant del foc sense simplificar el sistema."
            ),
            "limitations": (
                "Sense diagnosi de degradació local, no es pot saber si una zona necessita restauració, manteniment, no intervenció o simplement seguiment. Aquesta distinció és crítica per no actuar on el valor ja és alt."
            ),
            "implications": [
                "Si es restaura sense criteri, es poden invertir recursos en canvis visibles però ecològicament pobres, o fins i tot degradar hàbitats oberts naturals.",
                "L'oportunitat és prioritzar actuacions amb benefici múltiple: aigua, mosaic, connectivitat, baixa pressió i compatibilitat amb HIC.",
                "Cada actuació ha de tenir una hipòtesi verificable: quin procés millora, quin indicador ho mesurarà i quin risc evita.",
            ],
        },
        16: {
            "result_note": (
                f"Prioritat de gestió {management_score}/100 parcial, amb valors forts en hàbitats, biodiversitat i connectivitat, i incerteses en clima, vegetació, foc i aigua."
            ),
            "indicator_note": (
                "La prioritat agregada és una brúixola, no una ordre d'execució: indica on cal gestionar amb més cura i quines dades falten per actuar."
            ),
            "interpretation": (
                "La gestió d'Alinya ha de resoldre tensions, no maximitzar una sola dimensió. Conservar valors alts pot requerir no intervenir en alguns llocs i actuar en altres per mantenir mosaic. Reduir risc de foc pot ser coherent amb biodiversitat si reforça discontinuïtats existents, però pot ser perjudicial si simplifica HIC. Ordenar ús públic pot protegir tranquil·litat sense tancar l'espai si canalitza pressions cap a zones robustes."
            ),
            "limitations": (
                "La priorització encara no incorpora pressupost, propietat, calendari, acceptació social ni capacitat operativa. Per tant, és una priorització ecològica, no un pla executiu tancat."
            ),
            "implications": [
                "Si no es jerarquitzen decisions, la gestió pot reaccionar a pressions visibles i ignorar processos lents però més importants.",
                "L'oportunitat és convertir la diagnosi en cartera d'actuacions: conservació immediata, validació, restauració selectiva i seguiment.",
                "Cada decisió ha de tenir un criteri de sortida: quan es considera resolta, quin indicador ho prova i qui n'assumeix manteniment.",
            ],
        },
        17: {
            "result_note": (
                f"Sintesi: hàbitats {habitat_score}/100, biodiversitat {biodiversity_score}/100, connectivitat {connectivity_score}/100, pressió {pressure_score}/100, gestió {management_score}/100."
            ),
            "indicator_note": (
                "Els valors alts no porten a actuar més, sinó a actuar millor; els valors parcials indiquen on la diagnosi ha de continuar oberta."
            ),
            "interpretation": (
                "La síntesi integrada descriu un territori amb capital ecològic alt i vulnerabilitats de procés encara poc resoltes. La matriu natural i els HIC aporten valor, però el tancament del paisatge, la pressió potencial, la manca de dades climàtiques i la incertesa sobre aigua/foc poden convertir fortaleses en fragilitats. Un bosc continu pot ser corredor i refugi, però també pot perdre mosaic i augmentar combustible; una xarxa de camins pot facilitar gestió, però també pertorbació."
            ),
            "limitations": (
                "La síntesi encara no pot ordenar microzones amb precisió perquè falten capes dinàmiques i camp. La seva força actual és definir línies de decisió i no sobreinterpretar-les."
            ),
            "implications": [
                "Si no s'actua, el canvi probablement serà lent i silenciós: menys contrast, menys espais oberts funcionals i més dependència d'uns pocs refugis.",
                "L'oportunitat és anticipar gestió abans que la pèrdua de funció sigui visible o costosa de revertir.",
                "La gestió ha de protegir simultàniament tres actius: hàbitats d'alt valor, mosaic funcional i processos de resiliència.",
            ],
        },
        18: {
            "result_note": (
                "Les recomanacions existents s'ordenen per evidència: conservar valors robustos, validar incerteses i preparar actuacions selectives."
            ),
            "indicator_note": (
                "Una recomanació amb indicador parcial ha de ser validació o preparació; només les recomanacions sostingudes per diverses fonts poden orientar actuació directa."
            ),
            "interpretation": (
                "La priorització no ha de premiar el que és més fàcil d'executar, sinó el que evita pèrdues ecològiques més rellevants o desbloqueja decisions futures. En Alinya, això implica protegir valors d'hàbitat i connectivitat, completar dades de processos dinàmics i només després definir restauració o gestió forestal amb localització precisa."
            ),
            "limitations": (
                "Les recomanacions encara no incorporen cost, permisos, agents responsables ni calendari detallat. Sense aquests elements, són orientacions tècniques prioritzades, no projectes executius."
            ),
            "implications": [
                "Si es passa directament a obra, es pot actuar sobre símptomes i no sobre processos.",
                "L'oportunitat és transformar cada recomanació en fitxa d'actuació amb objectiu, evidència, localització, risc i indicador de seguiment.",
                "Les accions de validació no són tràmits: són el mecanisme que evita invertir en actuacions ecològicament febles.",
            ],
        },
        19: {
            "result_note": (
                "La validació tècnica no detecta errors crítics i la validació ecològica manté avisos on les dades són parcials."
            ),
            "indicator_note": (
                "Una validació superada amb avisos significa que l'informe és utilitzable, però que determinades conclusions han de quedar etiquetades com a provisionals."
            ),
            "interpretation": (
                "La validació és el mecanisme que diferencia una diagnosi professional d'un resum automàtic. No serveix per fer desaparèixer incerteses, sinó per comprovar que cada conclusió diu exactament fins on pot arribar. Això és essencial en espais amb alt valor: una conclusió massa segura pot justificar una actuació inadequada; una conclusió massa tímida pot bloquejar decisions necessàries."
            ),
            "limitations": (
                "La validació documental no substitueix camp. Confirma coherència interna, traçabilitat i prudència interpretativa, però no verifica sobre el terreny hàbitats, pressions, punts d'aigua o espècies sensibles."
            ),
            "implications": [
                "Si no es valida, el sistema pot confondre disponibilitat de dades amb qualitat de decisió.",
                "L'oportunitat és usar la checklist de camp com a traducció operativa de les incerteses de l'informe.",
                "La propera versió ha de reduir avisos incorporant evidència, no suavitzant el llenguatge.",
            ],
        },
        20: {
            "result_note": (
                "Les limitacions crítiques afecten Copernicus, clima, combustible, SIGPAC/DUN, BDBC, freqüentació real i validació de camp."
            ),
            "indicator_note": (
                "Cada limitació afecta una decisió concreta: clima i Sentinel afecten refugis/foc/restauració; ús real afecta pressió; camp afecta qualitat i localització."
            ),
            "interpretation": (
                "Les limitacions no són notes al peu: són els punts on la diagnosi pot canviar. Sense humitat vegetal es pot subestimar estrès; sense freqüentació es pot sobredimensionar o infravalorar pressió; sense camp es pot confondre presència cartogràfica amb qualitat ecològica; sense SIGPAC/DUN es perd part de la lectura agrària i ramadera que explica el mosaic."
            ),
            "limitations": (
                "El risc metodològic principal seria compensar buits amb intuïcions. L'informe els manté visibles perquè condicionen decisions, pressupost i prioritat de treball de camp."
            ),
            "implications": [
                "Si aquestes dades no s'incorporen, les decisions més delicades hauran de continuar sent reversibles, prudents i subjectes a validació.",
                "L'oportunitat és convertir cada buit en una tasca amb responsable: credencial, connector, camp, consulta administrativa o acord amb gestors.",
                "Les limitacions s'han de comunicar al gestor com a full de ruta, no com a excusa tècnica.",
            ],
        },
        21: {
            "result_note": (
                "Conclusió integrada: alt valor ecològic, mosaic funcional però vulnerable al tancament, pressió potencial moderada i blocs dinàmics parcialment resolts."
            ),
            "indicator_note": (
                "La lectura conjunta no recomana una intervenció massiva; recomana gestió selectiva, conservació preventiva i millora de dades on canvien decisions."
            ),
            "interpretation": (
                "Alinya és un espai on la qualitat de la gestió dependrà de mantenir contrastos. La superfície natural i els HIC aporten una base molt valuosa, però el repte és evitar que aquesta naturalitat es converteixi en homogeneïtat. Un paisatge massa tancat pot perdre recursos per espècies d'espais oberts, reduir ecotons, concentrar combustible i fer més difícil la resposta davant sequera o foc. Alhora, una gestió massa activa podria empobrir hàbitats sensibles. La resposta adequada és fina, gradual i mesurable."
            ),
            "limitations": (
                "Aquesta conclusió és defensable com a diagnosi estratègica. Encara no és una zonificació executiva perquè falten capes dinàmiques, camp i governança."
            ),
            "implications": [
                "Si no es gestiona, el canvi més probable és una pèrdua de funcions abans que una pèrdua visible de superfície natural.",
                "L'oportunitat és intervenir abans que els símptomes siguin evidents: mantenir mosaic, protegir aigua, ordenar accessos i validar hàbitats sensibles.",
                "El criteri rector hauria de ser: conservar el que funciona, actuar només on una funció ecològica està en risc i mesurar si l'actuació millora el procés.",
            ],
        },
        22: {
            "result_note": (
                "Els annexos mantenen traçabilitat de fonts, estats, metadades, indicadors, validació i sortides GIS perquè la diagnosi sigui revisable."
            ),
            "indicator_note": (
                "La traçabilitat no és un complement administratiu: permet saber quin resultat es pot defensar, quin és provisional i què cal actualitzar."
            ),
            "interpretation": (
                "En un producte de diagnosi ecològica, els annexos són part de la credibilitat. Permeten que un tècnic revisi fonts, que un gestor entengui per què una conclusió és robusta o provisional, i que una futura actualització millori el resultat sense reescriure la metodologia. Això converteix EcoRadar en un sistema acumulatiu, no en un document tancat."
            ),
            "limitations": (
                "La traçabilitat no millora una font feble; només en fa explícit l'ús i l'impacte. La qualitat final continuarà depenent de fonts oficials, camp i revisió experta."
            ),
            "implications": [
                "Sense annexos auditables, una diagnosi visualment bona pot perdre defensabilitat davant revisió tècnica.",
                "L'oportunitat és establir una història de versions per comparar anys, espais i decisions.",
                "Cada actualització futura ha de deixar clar què ha canviat en dades, indicadors, diagnosi i recomanacions.",
            ],
        },
    }

    for number, update in deep_reading.items():
        expert.setdefault(number, {}).update(update)

    for chapter in chapters:
        update = expert.get(chapter["number"])
        if update:
            chapter.update(update)
    return chapters


def management_report_chapters(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the client-facing report as management questions.

    The main report hides implementation language. Technical traceability stays
    in annexes so the document reads as ecological advice for managers.
    """

    forest_pct = fmt(metric(data["basic"], "percentatge_coberta_forestal"), 1, "%")
    grass_pct = fmt(metric(data["basic"], "percentatge_prats_pastures_herbassars"), 1, "%")
    agricultural_pct = fmt(metric(data["basic"], "percentatge_agricola"), 2, "%")
    artificial_pct = fmt(metric(data["basic"], "percentatge_urba_artificial"), 2, "%")
    habitats_count = metric(data["basic"], "nombre_habitats")
    hic_ha = fmt(metric(data["basic"], "superficie_hic"), 0)
    priority_hic = fmt(priority_habitat_surface(data["habitats"]), 0)
    records_count = metric(data["basic"], "nombre_registres_biodiversitat")
    species_count = metric(data["basic"], "nombre_especies_registrades")
    recent_records = metric(data["basic"], "nombre_registres_recents")
    road_km = fmt(pressure_metric(data["pressure"], "osm_path_track_road_km"), 1)
    road_density = fmt(pressure_metric(data["pressure"], "osm_path_track_road_density"), 2)
    public_points = metric(data["basic"], "nombre_accessos_punts_us_public") or pressure_metric(data["pressure"], "osm_recreational_point_features") or "0"
    hydrology_km = fmt((num(row_value(data["hydrology"], "layer_id", "rius_aca_che", "length_km")) or 0) + (num(row_value(data["hydrology"], "layer_id", "eixos_drenatge", "length_km")) or 0), 2)
    fonts_count = row_value(data["hydrology"], "layer_id", "fonts", "feature_count") or "0"
    mosaic_score = fmt(core_metric(data["core"], "CORE_01"), 1)
    habitat_score = fmt(core_metric(data["core"], "CORE_02"), 1)
    vegetation_state = client_value(core_row(data["core"], "CORE_03").get("status", ""))
    refuges_score = fmt(core_metric(data["core"], "CORE_04"), 1)
    vulnerability_score = fmt(core_metric(data["core"], "CORE_05"), 1)
    biodiversity_score = fmt(core_metric(data["core"], "CORE_06"), 1)
    pressure_score = fmt(core_metric(data["core"], "CORE_07"), 1)
    connectivity_score = fmt(core_metric(data["core"], "CORE_08"), 1)
    fire_score = fmt(core_metric(data["core"], "CORE_09"), 1)
    water_score = fmt(core_metric(data["core"], "CORE_10"), 1)
    restoration_score = fmt(core_metric(data["core"], "CORE_11"), 1)
    management_score = fmt(core_metric(data["core"], "CORE_12"), 1)
    copernicus_meta = data.get("teledeteccio", {})
    copernicus_capture = copernicus_meta.get("capture_date") or "data no identificada"
    copernicus_cloud = copernicus_meta.get("cloud_cover_percent")
    copernicus_cloud_text = fmt(copernicus_cloud, 1, "%") if copernicus_cloud is not None else "núvol no documentat"
    copernicus_scene_note = f"{copernicus_capture}, {copernicus_cloud_text} de núvols"
    top_groups = "; ".join(
        f"{plain(row.get('grup_taxonomic', ''))}: {row.get('nombre_especies', '')} taxons"
        for row in data["biodiv"][:3]
    )
    top_species_names = "; ".join(
        plain(row.get("scientificName", "")).split("(")[0].strip()
        for row in data.get("top_species", [])[:3]
    )
    forest_ha = fmt(rows_sum(data["cover"], "superficie_ha", "Bosc", "Boscos", text_key="tipus_coberta"), 0)
    scrub_ha = fmt(rows_sum(data["cover"], "superficie_ha", "Matollar", text_key="tipus_coberta"), 0)
    grass_ha = fmt(rows_sum(data["cover"], "superficie_ha", "Prats", "herbassars", text_key="tipus_coberta"), 0)

    def common_labels(chapter: dict[str, Any]) -> dict[str, Any]:
        chapter.setdefault("evidence_title", "TESI DE LA FITXA")
        chapter.setdefault("map_title", "On es veu al territori")
        chapter.setdefault("table_title", "Per què aquesta tesi és defensable")
        chapter.setdefault("interpretation_title", "Criteri expert")
        chapter.setdefault("limitations_title", "Prudència abans d'actuar")
        chapter.setdefault("decision_title", "DECISIÓ DE GESTIÓ")
        return chapter

    chapters = [
        common_labels({
            "number": 1,
            "title": "Què hauria de fer primer el gestor?",
            "subtitle": "Síntesi executiva orientada a decisions dels propers anys",
            "data_used": [
                "Alta responsabilitat de conservació",
                f"{hic_ha} ha d'hàbitats d'interès",
                f"{species_count} taxons citats",
                "pressió potencial concentrada en accessos",
            ],
            "result_note": "La lectura global és prou sòlida per ordenar prioritats, però no per executar actuacions fines sense camp.",
            "map_kind": "espai",
            "map_note": "El mapa situa l'espai i ajuda a llegir les decisions sobre una mateixa base territorial.",
            "rows": [
                ["Pregunta", "Resultat bàsic", "Lectura de gestió", "Confiança"],
                ["Què té més valor?", f"{hic_ha} ha HIC i {habitats_count} hàbitats", "conservació preventiva", "alta"],
                ["On hi ha pressió?", f"{road_km} km de xarxa i {public_points} punts", "ordenar ús i validar freqüentació", "mitjana-alta"],
                ["Què cal no tocar?", "HIC, ecotons i punts d'aigua sensibles", "filtre previ d'actuació", "mitjana"],
                ["Què falta per decidir millor?", "estat fisiològic, ús real i camp", "prioritzar verificació", "mitjana"],
            ],
            "widths": [42 * mm, 46 * mm, 56 * mm, 26 * mm],
            "interpretation": (
                f"Alinyà no demana una resposta única, sinó una gestió per capes. El valor d'hàbitats és molt elevat ({habitat_score}/100), la biodiversitat coneguda és alta ({biodiversity_score}/100) i la connectivitat estructural és forta ({connectivity_score}/100). "
                "Això no descriu només un espai valuós: obliga a una manera de governar-lo. La primera responsabilitat és evitar pèrdues de funcionalitat abans de buscar grans transformacions. Si cada àmbit decideix per separat - bosc, ús públic, restauració o aigua - el risc és simplificar un mosaic que actualment reparteix refugis, discontinuïtats, hàbitats prioritaris i zones de transició. La decisió correcta és treballar amb una cartera d'actuacions petites, condicionades i verificables, no amb una intervenció única de gran abast."
            ),
            "limitations": (
                "La lectura és robusta per hàbitats, cobertes, biodiversitat pública, connectivitat i accessibilitat potencial. És més prudent per l'estat fisiològic actual de la vegetació, la freqüentació real, la disponibilitat hídrica funcional i el comportament del foc."
            ),
            "confidence": "mitjana-alta",
            "decision": [
                "Aprovar una regla inicial de no deteriorament: cap actuació transformadora sense revisar hàbitats sensibles, punts d'aigua i ecotons afectats.",
                "Ordenar el treball dels propers anys en tres paquets: protecció immediata de valors coneguts, validació de punts crítics i actuacions només on el benefici ecològic sigui mesurable.",
                "Convertir cada nova proposta forestal, recreativa o de restauració en una pregunta: quin procés millora, on, amb quin risc i amb quin indicador de seguiment?",
            ],
        }),
        common_labels({
            "number": 2,
            "title": "Cal recuperar espais oberts?",
            "subtitle": "Mosaic territorial, prats, conreus residuals i ecotons",
            "data_used": [
                f"{forest_pct} de coberta forestal",
                f"{grass_pct} de prats i herbassars",
                f"{agricultural_pct} agrícola cartogràfic",
                f"{artificial_pct} artificial",
            ],
            "result_note": f"El mosaic obté {mosaic_score}/100: funcional, però condicionat per una matriu forestal molt dominant.",
            "map_kind": "paisatge",
            "map_note": "El mapa mostra que els espais oberts no són dominants, però estructuren discontinuïtats i ecotons.",
            "rows": [
                ["Component", "Resultat", "Què vol dir", "Decisió associada"],
                ["Bosc", forest_pct, "matriu principal; afavoreix continuïtat forestal", "gestionar sense homogeneïtzar"],
                ["Prats/herbassars", grass_pct, "recurs escàs per espècies d'espais oberts", "mantenir i validar qualitat"],
                ["Agrícola", agricultural_pct, "presència residual segons cobertes", "contrastar ús real"],
                ["Artificial", artificial_pct, "pressió superficial baixa", "vigilar accessos, no superfície"],
            ],
            "widths": [30 * mm, 28 * mm, 70 * mm, 42 * mm],
            "interpretation": (
                "El patró territorial és compatible amb un procés de tancament del paisatge: la massa forestal domina i els espais oberts queden com a peces escasses. El problema no és que hi hagi molt bosc; el problema apareix si el bosc avança fins a esborrar les discontinuïtats que alimenten flors, insectes, preses, zones de campeig, ecotons i oportunitats de gestió del combustible. Si no s'actua, els espais oberts que ara funcionen com a petites frontisses ecològiques poden perdre qualitat abans de desaparèixer cartogràficament. "
                "La solució no és obrir superfície per obrir-ne, sinó mantenir una xarxa d'espais oberts ben triats: prats connectats, ecotons propers a hàbitats d'interès i punts on la gestió tradicional encara pugui sostenir biodiversitat i discontinuïtat."
            ),
            "limitations": (
                "La dada d'ús agrari real encara no permet distingir amb prou seguretat quins espais oberts es mantenen per ramaderia, per condicions naturals o per abandonament recent. Aquesta diferència és decisiva per decidir si cal mantenir, recuperar o deixar evolucionar."
            ),
            "confidence": "alta per estructura; mitjana per causa i gestió agrària",
            "decision": [
                "Mantenir una xarxa mínima d'espais oberts funcionals, prioritzant prats, herbassars i ecotons connectats amb hàbitats d'interès.",
                "No convertir la recuperació d'espais oberts en una actuació generalitzada: seleccionar zones on es demostri benefici per biodiversitat, mosaic o prevenció d'homogeneïtzació.",
                "Verificar sobre el terreny quins espais oberts són actius, degradats, abandonats o d'origen natural abans de programar desbrossades o pastura dirigida.",
            ],
        }),
        common_labels({
            "number": 3,
            "title": "El bosc evoluciona favorablement?",
            "subtitle": "Massa forestal, matollars, estructura potencial i prudència silvícola",
            "data_used": [
                f"{forest_ha} ha de cobertes boscoses",
                f"{scrub_ha} ha de matollar",
                f"{grass_ha} ha de prats/herbassars",
                f"resiliència davant del foc {fire_score}/100",
            ],
            "result_note": "El bosc és un valor ecològic i alhora el principal condicionant de gestió del paisatge.",
            "map_kind": "paisatge",
            "map_note": "La cartografia de cobertes situa grans masses, clarianes, matollars i discontinuïtats.",
            "rows": [
                ["Element", "Resultat", "Lectura ecològica", "Gestió"],
                ["Boscos", f"{forest_ha} ha", "domini estructural del territori", "conservar estructura i diversitat"],
                ["Matollar", f"{scrub_ha} ha", "transició, refugi i combustible potencial", "gestió selectiva"],
                ["Prats/herbassars", f"{grass_ha} ha", "discontinuïtat funcional", "mantenir allà on aporta valor"],
                ["Foc", f"{fire_score}/100", "lectura parcial de resiliència", "no decidir només amb cobertes"],
            ],
            "widths": [28 * mm, 28 * mm, 74 * mm, 40 * mm],
            "interpretation": (
                "El bosc d'Alinyà no pot llegir-se només com a superfície arbrada. És una infraestructura ecològica: regula ombra, sòl, connectivitat, refugi i microclima. La seva evolució serà favorable si manté heterogeneïtat d'edats, clarianes, ecotons, fusta morta, sotabosc divers i relació amb prats i cursos d'aigua. Si la massa es tanca de manera homogènia, el territori pot perdre dues coses alhora: biodiversitat associada a espais oberts i capacitat de resposta davant sequera o foc. "
                "Per això la gestió forestal no s'ha d'entendre com aclarir més o menys, sinó com crear estructura: conservar rodals madurs, mantenir discontinuïtats funcionals, evitar tractaments en hàbitats sensibles i intervenir només on l'actuació augmenti resiliència sense empobrir el mosaic."
            ),
            "limitations": (
                "No es disposa encara d'informació suficient sobre estructura vertical, densitat, edat, regeneració, fusta morta ni humitat de capçada per prescriure tractaments forestals de detall."
            ),
            "confidence": "alta per cobertura; mitjana-baixa per estructura forestal funcional",
            "decision": [
                "No plantejar aclarides o actuacions forestals homogènies sobre tota la matriu: seleccionar només sectors on coincideixin continuïtat excessiva, baixa heterogeneïtat i benefici ecològic clar.",
                "Mantenir discontinuïtats naturals i semiobertes com a infraestructura ecològica, no com a espais marginals.",
                "Programar inventari forestal de detall en sectors prioritaris abans de decidir tractaments silvícoles.",
            ],
        }),
        common_labels({
            "number": 4,
            "title": "Quins hàbitats requereixen més protecció?",
            "subtitle": "Hàbitats d'interès, representativitat i zones que condicionen qualsevol actuació",
            "data_used": [
                f"{habitats_count} hàbitats cartografiats",
                f"{hic_ha} ha d'hàbitats d'interès",
                f"{priority_hic} ha d'hàbitats prioritaris",
                f"valor d'hàbitats {habitat_score}/100",
            ],
            "result_note": "El valor d'hàbitats és el senyal més fort de responsabilitat de conservació.",
            "map_kind": "habitats",
            "map_note": "El mapa permet situar unitats d'hàbitat i zones on la prudència ha de ser màxima.",
            "rows": [
                ["Component", "Resultat", "Interpretació", "Criteri"],
                ["Diversitat d'hàbitats", habitats_count, "heterogeneïtat ecològica elevada", "gestió diferenciada"],
                ["HIC", f"{hic_ha} ha", "responsabilitat de conservació", "filtre previ"],
                ["HIC prioritaris", f"{priority_hic} ha", "màxima prudència", "camp obligatori"],
                ["Valor hàbitats", f"{habitat_score}/100", "molt alt", "evitar actuacions irreversibles"],
            ],
            "widths": [36 * mm, 30 * mm, 62 * mm, 42 * mm],
            "interpretation": (
                "La cartografia d'hàbitats indica que Alinyà no és una unitat homogènia de gestió, sinó un conjunt de responsabilitats ecològiques superposades. La coexistència de molts hàbitats, HIC i hàbitats prioritaris fa que una actuació útil en un sector pugui ser negativa en un altre: una desbrossada pot recuperar mosaic o degradar un hàbitat prioritari; un camí pot ordenar l'ús o travessar una zona sensible; una actuació forestal pot reduir continuïtat o simplificar estructura. "
                "La decisió professional és establir una jerarquia de prudència: primer zones de no perjudici, després zones on només es pot actuar amb condicions, i finalment zones on la restauració o la gestió poden aportar benefici net."
            ),
            "limitations": (
                "La cartografia identifica presència i distribució, però no substitueix l'avaluació local d'estat de conservació. Un polígon d'hàbitat pot estar ben conservat, degradat o en transició, i aquesta diferència canvia la decisió."
            ),
            "confidence": "alta a escala cartogràfica; mitjana per qualitat local",
            "decision": [
                "Establir els HIC i HIC prioritaris com a capa de veto o prudència reforçada abans de qualsevol actuació.",
                "Validar al camp els polígons que coincideixin amb camins, punts d'ús públic, possibles actuacions forestals o restauració.",
                "No executar restauracions o gestió forestal en hàbitats sensibles sense objectiu ecològic explícit i indicador de seguiment.",
            ],
        }),
        common_labels({
            "number": 5,
            "title": "La vegetació mostra estrès?",
            "subtitle": "Estructura disponible i necessitat d'informació fisiològica abans de decidir detalls",
            "data_used": [
                "estructura vegetal ben descrita",
                f"{forest_pct} forestal",
                f"{grass_pct} prats/herbassars",
                f"escena d'estiu localitzada: {copernicus_scene_note}",
                f"estat fisiològic: {vegetation_state}",
            ],
            "result_note": "Ja hi ha una escena d'estiu apta per completar la lectura fisiològica, però encara no s'han processat els índexs de vigor i humitat.",
            "map_kind": "paisatge",
            "map_note": "El mapa situa l'estructura vegetal; la imatge d'estiu localitzada permetrà contrastar-ne vigor i humitat.",
            "rows": [
                ["Pregunta", "Resposta actual", "Què permet decidir", "Què queda condicionat"],
                ["Què hi ha?", "cobertes i hàbitats", "estructura general", "vigor actual"],
                ["Imatge recent", copernicus_scene_note, "finestra bona d'anàlisi", "processar índexs"],
                ["On pot fallar?", "matriu forestal dominant", "mostreig dirigit", "estrès hídric"],
                ["Evolució temporal", "encara no concloent", "seguiment", "tendència fisiològica"],
            ],
            "widths": [34 * mm, 42 * mm, 46 * mm, 48 * mm],
            "interpretation": (
                "La vegetació d'Alinyà ja es pot llegir bé des del punt de vista estructural, però el salt important és saber com està funcionant en ple període vegetatiu. La imatge d'estiu localitzada per Copernicus és especialment valuosa perquè permetrà contrastar la cartografia amb vigor, humitat i presència d'aigua superficial o humitat de vegetació. Això canvia la diagnosi: el problema ja no és saber si hi ha una base remota adequada, sinó convertir-la en criteri ecològic útil. "
                "Fins que aquests índexs no estiguin processats, la lectura més honesta és aquesta: el bosc domina i estructura el paisatge, però encara no sabem quins rodals treballen com a refugis, quins acumulen estrès i quins espais oberts mantenen millor resposta hídrica. Aquesta diferència és clau per no confondre cobertura amb bon estat. Un gestor podria veure dues masses forestals iguals al mapa i, en canvi, una estar amortint la sequera i l'altra estar perdent vigor per orientació, sòl prim, densitat o exposició. La decisió correcta és fer servir la cartografia per orientar el camp i la imatge d'estiu per discriminar on cal actuar, on cal conservar i on convé no tocar."
            ),
            "limitations": (
                "No es disposa encara dels valors calculats de vigor, humitat i aigua superficial. Per això no es poden declarar zones d'estrès, però sí preparar una lectura molt concreta: comparar obagues i solanes, masses denses i clares, ecotons, prats en regressió i entorns d'aigua."
            ),
            "confidence": "alta per estructura i escena disponible; baixa per estat fisiològic calculat",
            "confidence_note": "La confiança combina qualitat de font, actualitat, escala i si la dada permet actuar. Aquí és alta per saber on és la vegetació i quina imatge recent servirà, però baixa per afirmar com està funcionant.",
            "decision": [
                "Processar la imatge d'estiu localitzada abans de prescriure actuacions forestals fines, restauració de vegetació o zones d'estrès.",
                "Dirigir el camp cap a contrastos que la teledetecció haurà de confirmar: obagues i solanes, masses denses i clares, prats en regressió i punts propers a l'aigua.",
                "Mantenir de moment una gestió prudent: actuar sobre valors robustos i ajornar decisions de vigor, sequera o decaïment fins tenir índexs calculats.",
            ],
        }),
        common_labels({
            "number": 6,
            "title": "On convé conservar refugis climàtics?",
            "subtitle": "Obagues, humitat potencial, bosc, aigua i vulnerabilitat futura",
            "data_used": [
                f"refugis climàtics {refuges_score}/100",
                f"vulnerabilitat climàtica {vulnerability_score}/100",
                "relleu i orientació com a lectura potencial",
                f"imatge d'estiu disponible per contrastar humitat: {copernicus_scene_note}",
                "aigua funcional pendent de camp",
            ],
            "result_note": "Hi ha refugis potencials i una imatge recent per contrastar humitat, però la delimitació fina encara no és operativa.",
            "map_kind": "base",
            "map_note": "El context topogràfic orienta possibles obagues, fondals i corredors frescos.",
            "rows": [
                ["Element", "Resultat", "Què suggereix", "Prudència"],
                ["Refugis", f"{refuges_score}/100", "potencial mitjà", "validar microclima"],
                ["Vulnerabilitat", f"{vulnerability_score}/100", "no extrema a escala global", "detall local"],
                ["Humitat recent", copernicus_scene_note, "anàlisi viable", "cal índex calculat"],
                ["Bosc", forest_pct, "ombra i amortiment potencial", "estructura importa"],
            ],
            "widths": [30 * mm, 30 * mm, 68 * mm, 42 * mm],
            "interpretation": (
                "Els refugis climàtics no són simplement zones fresques: són espais on ombra, humitat, orientació, sòl, aigua i baixa pertorbació coincideixen prou per amortir episodis de calor o sequera. A Alinyà, la matriu forestal i el relleu poden generar refugis potencials, especialment en obagues, fondals i entorns hídrics. La dada de Copernicus és útil perquè dona una finestra recent per comprovar si aquests refugis potencials també mantenen humitat i vigor durant l'estiu. "
                "Aquesta distinció és decisiva per a la gestió. Un refugi no es protegeix perquè surt verd al mapa, sinó perquè manté funció quan el territori s'estressa: ofereix ombra, continuïtat de sòl viu, disponibilitat d'aigua o microclima més estable. Quan es processin els índexs, EcoRadar podrà separar zones que només semblen favorables de zones que realment amortitzen condicions extremes."
            ),
            "limitations": (
                "La diagnosi climàtica encara és potencial. L'escena recent reforça la viabilitat de l'anàlisi, però sense índexs calculats i validació local no es poden delimitar refugis finals ni solanes vulnerables amb precisió operativa."
            ),
            "confidence": "mitjana",
            "confidence_note": "Mitjana vol dir que diverses capes apunten en la mateixa direcció, però encara falta la prova dinàmica que confirmi el funcionament climàtic.",
            "decision": [
                "Tractar obagues, fondals, entorns de fonts i corredors hídrics com a zones de prudència climàtica fins validar-les.",
                "Evitar actuacions que redueixin ombra, humitat o tranquil·litat en possibles refugis fins que la imatge recent i el camp confirmin el seu paper.",
                "Prioritzar una lectura conjunta de relleu, aigua, coberta i humitat estival abans de planificar restauració climàtica.",
            ],
        }),
        common_labels({
            "number": 7,
            "title": "Com s'ha de gestionar l'aigua?",
            "subtitle": "Cursos, fonts, basses potencials i funcionalitat ecològica",
            "data_used": [
                f"{hydrology_km} km de cursos o drenatges cartografiats",
                f"{fonts_count} fonts registrades",
                f"funcionalitat hídrica {water_score}/100",
                "basses i zones humides a validar",
            ],
            "result_note": "L'aigua és probablement més important ecològicament que no pas extensa en superfície.",
            "map_kind": "base",
            "map_note": "El mapa general situa el context; la lectura hídrica requereix treball de camp sobre punts concrets.",
            "rows": [
                ["Element", "Resultat", "Funció probable", "Decisió"],
                ["Cursos/drenatges", f"{hydrology_km} km", "corredors i eixos d'humitat", "mantenir continuïtat"],
                ["Fonts", fonts_count, "nodes de fauna i refugi", "verificar estat"],
                ["Basses/zones humides", "informació parcial", "reproducció i abeurada", "inventariar"],
                ["Funcionalitat", f"{water_score}/100", "lectura mitjana", "camp prioritari"],
            ],
            "widths": [34 * mm, 30 * mm, 64 * mm, 42 * mm],
            "interpretation": (
                "En un espai mediterrani de muntanya, l'aigua pesa molt més ecològicament que la seva superfície. Una font permanent, una bassa funcional o un tram ombrívol poden concentrar activitat de fauna, connectar hàbitats, actuar com a refugi climàtic i sostenir processos en anys secs. Però també poden convertir-se en punts de conflicte si concentren bestiar, persones o degradació de ribera. "
                "La solució no és restaurar tots els punts d'aigua ni fer-los més visibles, sinó classificar-los: punts de conservació estricta, punts de millora funcional, punts d'abeurada compatibles i punts que cal mantenir tranquils perquè la fauna els utilitzi."
            ),
            "limitations": (
                "La informació actual no permet diferenciar permanència, qualitat, cabal, ús faunístic ni pressions locals. Aquesta mancança limita la priorització hidrològica fina."
            ),
            "confidence": "mitjana",
            "decision": [
                "Fer un inventari de camp de fonts, basses, punts d'abeurada i trams ombrívols abans de proposar obres o restauració hídrica.",
                "Prioritzar la protecció de punts d'aigua que coincideixin amb hàbitats d'interès, corredors i baixa pertorbació.",
                "No fer més accessibles els punts d'aigua sensibles sense valorar impacte sobre fauna i tranquil·litat.",
            ],
        }),
        common_labels({
            "number": 8,
            "title": "Què sabem realment de la biodiversitat?",
            "subtitle": "Coneixement públic, grups taxonòmics i buits que condicionen decisions",
            "data_used": [
                f"{records_count} registres públics",
                f"{species_count} taxons",
                f"{recent_records} registres recents",
                f"grups principals: {top_groups}",
            ],
            "result_note": f"Els taxons més citats inclouen: {top_species_names or 'sense rànquing disponible'}.",
            "map_kind": "biodiversitat",
            "map_note": "El mapa mostra on s'ha observat biodiversitat, però també on hi pot haver més esforç d'observació.",
            "rows": [
                ["Grup", "Registres", "Taxons", "Lectura"],
                *[
                    [
                        plain(row.get("grup_taxonomic", "")),
                        row.get("nombre_registres", ""),
                        row.get("nombre_especies", ""),
                        "ben representat a les dades públiques" if idx < 3 else "complementari",
                    ]
                    for idx, row in enumerate(data["biodiv"][:5])
                ],
            ],
            "widths": [38 * mm, 28 * mm, 28 * mm, 76 * mm],
            "interpretation": (
                "La biodiversitat coneguda és elevada, però el gestor ha de llegir-la com a coneixement acumulat, no com a inventari complet. Les cites indiquen on hi ha valor documentat i també on hi ha hagut ulls mirant. Això és útil perquè evita dues males decisions: actuar sense prudència en zones amb cites sensibles i considerar pobres les zones poc observades. "
                "La decisió no és protegir només els punts amb registres, sinó usar-los per dissenyar una campanya intel·ligent: revisar hàbitats amb alta responsabilitat, punts d'aigua, ecotons i sectors amb pressió potencial, i incorporar criteri expert abans de tocar zones que puguin sostenir espècies vulnerables o indicadores."
            ),
            "limitations": (
                "Les dades públiques tenen biaix espacial, temporal i taxonòmic. No permeten afirmar absències ni substituir protocols específics per espècies protegides, amenaçades, invasores o indicadores."
            ),
            "confidence": "alta per coneixement registrat; mitjana per estat real de comunitats",
            "decision": [
                "Usar els registres existents per dissenyar mostreig focalitzat, no per tancar conclusions d'absència.",
                "Prioritzar validació d'espècies sensibles en hàbitats d'interès, punts d'aigua i zones amb pressió potencial.",
                "Incorporar dades expertes i de gestors abans de prendre decisions que puguin afectar fauna o flora vulnerable.",
            ],
        }),
        common_labels({
            "number": 9,
            "title": "On cal preservar la connectivitat?",
            "subtitle": "Matriu natural, corredors, ecotons i barreres potencials",
            "data_used": [
                f"connectivitat ecològica {connectivity_score}/100",
                f"mosaic {mosaic_score}/100",
                f"{forest_pct} forestal",
                f"{road_density} km/km2 de xarxa viària o camins",
            ],
            "result_note": "La connectivitat estructural és un actiu, però la funcionalitat depèn d'espècies i pertorbacions.",
            "map_kind": "paisatge",
            "map_note": "La matriu de cobertes ajuda a veure continuïtats, ecotons i possibles friccions.",
            "rows": [
                ["Factor", "Resultat", "Efecte ecològic", "Gestió"],
                ["Matriu natural", forest_pct, "continuïtat elevada", "evitar fragmentació"],
                ["Mosaic", f"{mosaic_score}/100", "heterogeneïtat útil", "mantenir ecotons"],
                ["Xarxa d'accés", f"{road_density} km/km2", "barrera o pertorbació potencial", "ordenar ús"],
                ["Aigua", f"{hydrology_km} km", "corredor humit potencial", "protegir continuïtat"],
            ],
            "widths": [34 * mm, 30 * mm, 66 * mm, 40 * mm],
            "interpretation": (
                "La connectivitat d'Alinyà sembla forta perquè la matriu natural és extensa i poc artificialitzada. Ara bé, connectivitat no vol dir només continuïtat de bosc: espècies diferents utilitzen corredors diferents, i algunes necessiten mosaics d'obert-tancat, punts d'aigua o baixa pertorbació. Les barreres més importants poden ser físiques, però també comportamentals: camins freqüentats, zones recreatives o soroll poden reduir permeabilitat per fauna sensible."
            ),
            "limitations": (
                "No hi ha encara models funcionals per espècie ni dades de freqüentació real. La lectura és sòlida per estructura territorial, però provisional per permeabilitat biològica efectiva."
            ),
            "confidence": "alta per estructura; mitjana per funcionalitat",
            "decision": [
                "No crear noves barreres en corredors, ecotons i fons de vall sense justificació ecològica.",
                "Prioritzar la preservació de continuïtats entre hàbitats d'interès, punts d'aigua i zones tranquil·les.",
                "Avaluar qualsevol nou ús públic segons el seu efecte sobre permeabilitat, no només segons superfície ocupada.",
            ],
        }),
        common_labels({
            "number": 10,
            "title": "On cal limitar o ordenar la freqüentació?",
            "subtitle": "Accessibilitat potencial, punts d'ús públic i conflicte conservació-ús",
            "data_used": [
                f"{road_km} km de camins i pistes",
                f"{public_points} punts d'accés o ús públic",
                f"pressió humana {pressure_score}/100",
                "freqüentació real pendent de validació",
            ],
            "result_note": "La dada actual mesura accessibilitat potencial, no nombre de visitants.",
            "map_kind": "pressio_humana",
            "map_note": "El mapa localitza xarxa d'accés i punts on pot concentrar-se l'ús públic.",
            "rows": [
                ["Element", "Resultat", "Què implica", "Decisió"],
                ["Camins/pistes", f"{road_km} km", "penetració territorial", "jerarquitzar xarxa"],
                ["Densitat", f"{road_density} km/km2", "accessibilitat mitjana-alta", "vigilar sectors sensibles"],
                ["Punts d'ús", public_points, "concentració potencial", "validar sobre el terreny"],
                ["Pressió", f"{pressure_score}/100", "nivell mitjà", "ordenar, no prohibir a cegues"],
            ],
            "widths": [32 * mm, 30 * mm, 66 * mm, 42 * mm],
            "interpretation": (
                "La pressió humana d'Alinyà s'ha de llegir com a probabilitat de contacte entre persones i valors ecològics, no com a recompte de visitants. Una xarxa d'accés extensa pot ser compatible amb conservació si concentra els usos en eixos robustos, previsibles i allunyats de punts sensibles. Però pot generar impacte si dispersa persones cap a HIC, fonts, zones de cria, ecotons o refugis climàtics. "
                "La decisió no és prohibir de manera general, sinó dissenyar l'espai públic com una eina de conservació: itineraris prioritaris, punts d'entrada assumibles, sectors tranquils i criteris clars per no promocionar zones ecològicament fràgils."
            ),
            "limitations": (
                "Sense comptadors, observació de camp o dades agregades legalment compatibles, no es pot estimar intensitat real ni temporalitat de l'ús públic."
            ),
            "confidence": "alta per accessibilitat; baixa per freqüentació real",
            "decision": [
                "Concentrar l'ús públic en eixos ja consolidats i allunyar-lo dels punts d'aigua, HIC sensibles i zones de baixa pertorbació.",
                "Fer verificació de camp en els punts d'ús públic detectats abans de decidir regulacions.",
                "No presentar cap dada d'accessibilitat com a nombre de visitants.",
            ],
        }),
        common_labels({
            "number": 11,
            "title": "Com reduir la vulnerabilitat davant del foc?",
            "subtitle": "Continuïtat forestal, mosaic, humitat potencial i accessos",
            "data_used": [
                f"resiliència davant del foc {fire_score}/100",
                f"mosaic {mosaic_score}/100",
                f"{forest_pct} forestal",
                f"humitat estival pendent de processar: {copernicus_scene_note}",
                f"{grass_pct} espais oberts herbacis",
            ],
            "result_note": "La lectura és suficient per orientar prudència; la imatge d'estiu ajudarà a separar continuïtat seca de continuïtat amb més humitat funcional.",
            "map_kind": "paisatge",
            "map_note": "El mapa mostra continuïtats i discontinuïtats, no un mapa final de risc d'incendi.",
            "rows": [
                ["Factor", "Resultat", "Lectura", "Gestió"],
                ["Continuïtat forestal", forest_pct, "alta", "crear o mantenir discontinuïtats útils"],
                ["Mosaic", f"{mosaic_score}/100", "bo però millorable", "conservar espais oberts"],
                ["Prats/herbassars", grass_pct, "recurs preventiu i ecològic", "mantenir selectivament"],
                ["Resiliència", f"{fire_score}/100", "mitjana i parcial", "validar combustible"],
            ],
            "widths": [36 * mm, 30 * mm, 54 * mm, 50 * mm],
            "interpretation": (
                "La vulnerabilitat al foc no depèn només de si hi ha molt bosc. Depèn de continuïtat, pendent, orientació, humitat, accessos, estructura del combustible i capacitat del mosaic per frenar propagacions. En un paisatge forestal dominant, els espais oberts i els ecotons tenen una doble funció estratègica: poden reduir continuïtat del combustible i alhora sostenir biodiversitat. "
                "El risc de mala gestió és actuar només amb lògica de combustible i perdre hàbitats o processos valuosos. La bona gestió busca coincidències: punts on una intervenció selectiva millora resiliència al foc, manté espais oberts funcionals, reforça accessos útils i no perjudica hàbitats prioritaris. La lectura d'humitat vegetal serà especialment important perquè no totes les continuïtats forestals tenen el mateix comportament: una obaga humida pot ser refugi i no problema, mentre que una massa contínua exposada i seca pot concentrar vulnerabilitat."
            ),
            "limitations": (
                "No es disposa encara d'un model complet de combustible, humitat de vegetació, severitat històrica i microtopografia aplicada. La decisió ha de ser preventiva i selectiva."
            ),
            "confidence": "mitjana",
            "confidence_note": "La confiança és mitjana perquè la forma del paisatge és clara, però la resposta del combustible viu depèn d'humitat i estructura que encara s'han de quantificar.",
            "decision": [
                "No executar tractaments de combustible generalitzats en zones d'alt valor d'hàbitat sense avaluació local.",
                "Prioritzar discontinuïtats existents, prats, ecotons i accessos estratègics on la intervenció aporti també benefici ecològic.",
                "Fer una validació de combustible i humitat en sectors forestals continus abans de redactar actuacions executables.",
            ],
        }),
        common_labels({
            "number": 12,
            "title": "On s'hauria de concentrar la restauració?",
            "subtitle": "Restaurar funcions, no només superfícies",
            "data_used": [
                f"potencial de restauració {restoration_score}/100",
                f"vulnerabilitat climàtica {vulnerability_score}/100",
                f"funcionalitat hídrica {water_score}/100",
                f"imatge d'estiu per contrastar vigor: {copernicus_scene_note}",
                f"connectivitat {connectivity_score}/100",
            ],
            "result_note": "El potencial és alt com a orientació, però les actuacions finals requereixen localització i camp.",
            "map_kind": "habitats",
            "map_note": "El mapa d'hàbitats ajuda a evitar restauracions que malmetin valors existents.",
            "rows": [
                ["Criteri", "Resultat", "Què significa", "Ús en decisió"],
                ["Restauració", f"{restoration_score}/100", "oportunitat agregada alta", "prioritzar, no executar encara"],
                ["Aigua", f"{water_score}/100", "funcionalitat parcial", "camp en punts crítics"],
                ["Connectivitat", f"{connectivity_score}/100", "bon suport territorial", "connectar actuacions"],
                ["Vulnerabilitat", f"{vulnerability_score}/100", "baixa-mitjana global", "buscar punts locals"],
            ],
            "widths": [34 * mm, 30 * mm, 64 * mm, 42 * mm],
            "interpretation": (
                "La restauració més valuosa a Alinyà no hauria de consistir a transformar grans superfícies, sinó a recuperar funcions puntuals: mantenir espais oberts clau, millorar punts d'aigua, reforçar ecotons, reduir pertorbacions en zones sensibles i connectar hàbitats font. En un espai amb molt valor preexistent, restaurar massa pot ser tan problemàtic com no actuar: una actuació ben intencionada pot simplificar un hàbitat, obrir una zona tranquil·la o alterar una successió valuosa. "
                "La restauració s'ha de formular com un contracte de resultat: quin procés està debilitat, quina actuació el millora, quin risc comporta i quin indicador demostrarà que ha funcionat. La imatge estival de Copernicus pot aportar aquest indicador quan es processi: ajudarà a saber si una zona oberta conserva vigor, si una massa forestal manté humitat o si un sector aparentment degradat és, en realitat, un hàbitat sec funcional que no convé transformar."
            ),
            "limitations": (
                "La localització final de restauració necessita evidència de degradació local, pressió real, disponibilitat d'aigua, estat de vegetació i viabilitat de gestió."
            ),
            "confidence": "mitjana",
            "confidence_note": "Mitjana indica que el potencial és coherent amb diverses fonts, però la localització final necessita comprovar estat real de vegetació, aigua i pressions.",
            "decision": [
                "Concentrar restauració en funcions verificables: espais oberts estratègics, punts d'aigua, ecotons i sectors de connectivitat.",
                "No restaurar HIC ben conservats ni zones sensibles només perquè apareixen com a prioritàries en una síntesi agregada.",
                "Exigir per cada actuació un objectiu ecològic, una localització, un indicador de seguiment i una comprovació de no perjudici.",
            ],
        }),
        common_labels({
            "number": 13,
            "title": "Quines zones no s'han de tocar?",
            "subtitle": "Àrees de prudència ecològica i filtre previ d'actuació",
            "data_used": [
                f"{hic_ha} ha HIC",
                f"{priority_hic} ha HIC prioritaris",
                "punts d'aigua i refugis potencials",
                "zones amb biodiversitat citada",
            ],
            "result_note": "La no-intervenció també és una decisió de gestió quan protegeix processos actius.",
            "map_kind": "habitats",
            "map_note": "Els hàbitats d'interès, els ecotons i les zones sensibles han de condicionar qualsevol projecte.",
            "rows": [
                ["Zona de prudència", "Evidència", "Risc si s'actua", "Criteri"],
                ["HIC prioritaris", f"{priority_hic} ha", "pèrdua de valor singular", "veto o camp obligatori"],
                ["Punts d'aigua", f"{fonts_count} fonts", "pertorbació de fauna", "protecció i validació"],
                ["Ecotons/prats", grass_pct, "simplificació del mosaic", "gestió selectiva"],
                ["Refugis potencials", f"{refuges_score}/100", "pèrdua d'amortiment climàtic", "prudència"],
            ],
            "widths": [38 * mm, 30 * mm, 58 * mm, 44 * mm],
            "interpretation": (
                "Un bon pla de gestió no només decideix on actuar; també delimita on no convé intervenir o on cal fer-ho amb condicions estrictes. A Alinyà, les zones de més prudència són aquelles on se solapen hàbitats d'interès, possibles refugis climàtics, punts d'aigua, ecotons i cites de biodiversitat. En aquests espais, la pèrdua de qualitat pot no ser visible immediatament en hectàrees, però sí en funcions: reproducció, refugi, connectivitat, humitat o tranquil·litat."
            ),
            "limitations": (
                "La delimitació precisa de zones de no-intervenció requereix verificar estat local, propietat, pressions i objectius de conservació."
            ),
            "confidence": "mitjana-alta",
            "decision": [
                "Aplicar un filtre de no-perjudici abans de qualsevol actuació en HIC, punts d'aigua, ecotons i refugis potencials.",
                "Considerar la no-intervenció activa com una mesura de conservació quan el sistema ja manté funcions valuoses.",
                "Documentar per què una zona es deixa sense actuar i quin indicador es farà servir per comprovar-ne l'evolució.",
            ],
        }),
        common_labels({
            "number": 14,
            "title": "Quines actuacions són prioritàries?",
            "subtitle": "De la diagnosi a decisions executables",
            "data_used": [
                f"prioritat de gestió {management_score}/100",
                "valor d'hàbitats molt alt",
                "pressió potencial mitjana",
                "restauració condicionada per camp",
            ],
            "result_note": "La prioritat no és una llista d'obres, sinó una seqüència de decisions.",
            "map_kind": "espai",
            "map_note": "La localització final de cada actuació s'ha de tancar amb camp i governança.",
            "rows": [
                ["Prioritat", "Objectiu", "Evidència", "Condició"],
                ["1", "conservar valors", "HIC, hàbitats, biodiversitat", "immediata"],
                ["2", "validar punts crítics", "aigua, prats, refugis, ús públic", "camp"],
                ["3", "ordenar accessos", "camins i punts d'ús", "freqüentació real"],
                ["4", "restaurar funcions", "mosaic, aigua, connectivitat", "localització validada"],
            ],
            "widths": [18 * mm, 42 * mm, 64 * mm, 46 * mm],
            "interpretation": (
                "La seqüència de gestió més defensable és començar pel que ja és robust: conservar valors d'hàbitat, evitar deteriorament i ordenar riscos evidents. Després cal reduir incerteses que bloquegen decisions: qualitat local d'hàbitats, punts d'aigua, freqüentació real i estructura forestal. Només quan aquestes incerteses estiguin resoltes té sentit passar a restauració o tractaments forestals amb projecte executiu. "
                "Aquesta seqüència evita gastar pressupost en actuacions visibles però poc transformadores, i concentra l'esforç en allò que canvia el funcionament del territori."
            ),
            "limitations": (
                "Sense pressupost, propietat, calendari, consens amb gestors i comprovació de camp, les prioritats són ecològiques i tècniques, no encara administratives."
            ),
            "confidence": "mitjana-alta",
            "decision": [
                "Adoptar una prioritat en tres temps: protegir ara, validar durant la primera campanya de camp i executar actuacions només amb localització confirmada.",
                "No finançar actuacions de restauració o gestió forestal que no indiquin quin procés ecològic milloraran.",
                "Fer que cada actuació tingui indicador de seguiment abans d'entrar en pressupost.",
            ],
        }),
        common_labels({
            "number": 15,
            "title": "Què cal validar al camp?",
            "subtitle": "La informació que pot canviar decisions",
            "data_used": [
                "hàbitats sensibles i prioritaris",
                "prats, ecotons i discontinuïtats",
                "fonts, basses i punts d'aigua",
                "pressió real i microhàbitats",
            ],
            "result_note": "El camp no és un tràmit: és el pas que converteix diagnosi en projecte executiu.",
            "map_kind": "espai",
            "map_note": "El mapa general serveix per preparar recorreguts, sectors i punts de comprovació.",
            "rows": [
                ["Element a validar", "Per què importa", "Decisió que pot canviar", "Prioritat"],
                ["HIC i prioritaris", "qualitat local", "permetre o limitar actuacions", "molt alta"],
                ["Prats/ecotons", "mosaic i biodiversitat", "mantenir o recuperar", "alta"],
                ["Aigua", "refugi i fauna", "protegir/restaurar", "alta"],
                ["Ús públic", "conflicte real", "ordenar o no ordenar", "alta"],
            ],
            "widths": [40 * mm, 48 * mm, 54 * mm, 28 * mm],
            "interpretation": (
                "La validació de camp ha d'estar dissenyada per resoldre decisions, no per acumular observacions. Els punts prioritaris són aquells on una mala decisió tindria cost ecològic: hàbitats sensibles, zones d'ús públic potencial, punts d'aigua, espais oberts escassos i sectors forestals continus. La campanya ha de registrar estat, pressions, evidències d'ús, microhàbitats i viabilitat d'actuació."
            ),
            "limitations": (
                "Sense camp, algunes conclusions seguiran sent estratègiques. Això no impedeix decidir mesures de prudència, però sí executar actuacions fines."
            ),
            "confidence": "alta sobre què cal validar; pendent sobre resultats locals",
            "decision": [
                "Planificar una campanya de camp curta però focalitzada en punts que desbloquegen decisions.",
                "Registrar evidència amb coordenades, fotografia, pressió observada, estat de l'hàbitat i decisió associada.",
                "Actualitzar la diagnosi només quan el camp confirmi o corregeixi les hipòtesis actuals.",
            ],
        }),
        common_labels({
            "number": 16,
            "title": "Què convé fer durant els propers anys?",
            "subtitle": "Full de ruta de gestió adaptativa",
            "data_used": [
                "curt termini: conservació i camp",
                "mitjà termini: ordenació i restauració selectiva",
                "llarg termini: seguiment i adaptació",
            ],
            "result_note": "La gestió ha de ser seqüencial: no tot s'ha de fer alhora.",
            "map_kind": "espai",
            "map_note": "El full de ruta s'ha d'aterrar posteriorment en sectors i responsables.",
            "rows": [
                ["Horitzó", "Decisió principal", "Què resol", "Indicador de seguiment"],
                ["0-12 mesos", "protegir valors i fer camp", "evita dany i redueix incertesa", "checklist validada"],
                ["1-3 anys", "ordenar accessos i restaurar funcions", "redueix pressions", "mosaic/aigua/ús"],
                ["3-6 anys", "seguiment adaptatiu", "avalua efectes", "tendència i qualitat"],
                ["continu", "actualitzar diagnosi", "manté vigència", "dades noves"],
            ],
            "widths": [26 * mm, 48 * mm, 54 * mm, 42 * mm],
            "interpretation": (
                "El valor d'EcoRadar per a un gestor és convertir una radiografia en seqüència de treball. El primer any ha de reduir risc i incertesa: conservar, validar i no deteriorar. El segon bloc ha de executar actuacions selectives allà on hi hagi benefici ecològic i viabilitat. El seguiment posterior ha de comprovar si les decisions mantenen mosaic, protegeixen hàbitats, redueixen pertorbacions i milloren funcionalitat hídrica o connectivitat."
            ),
            "limitations": (
                "El calendari dependrà de pressupost, propietat, autoritzacions, compatibilitat amb usos existents i resultats de camp."
            ),
            "confidence": "mitjana-alta com a estratègia",
            "decision": [
                "Aprovar un full de ruta adaptatiu: primer prudència i camp, després actuacions selectives, finalment seguiment i revisió.",
                "No transformar prioritats ecològiques en obres sense fase prèvia de validació.",
                "Revisar la diagnosi anualment o després de noves dades crítiques, incendis, sequeres o canvis d'ús.",
            ],
        }),
        common_labels({
            "number": 17,
            "title": "Conclusió per a la direcció de l'espai",
            "subtitle": "Criteri final de gestió ecològica integrada",
            "data_used": [
                "alt valor d'hàbitats",
                "biodiversitat coneguda elevada",
                "mosaic amb espais oberts escassos",
                "pressions potencials a validar",
            ],
            "result_note": "La diagnosi permet decidir criteris estratègics, no encara cada actuació executiva.",
            "map_kind": "espai",
            "map_note": "La lectura final situa el conjunt de decisions en l'àrea d'estudi.",
            "rows": [
                ["Missatge clau", "Evidència", "Conseqüència", "Decisió"],
                ["Conservar primer", "HIC i hàbitats alts", "evitar pèrdua de valor", "prudència"],
                ["Mantenir mosaic", "bosc dominant i prats escassos", "evitar homogeneïtzació", "gestió selectiva"],
                ["Ordenar ús", "xarxa i punts d'accés", "reduir conflictes", "validar i concentrar"],
                ["Actuar amb dades", "blocs parcials", "evitar errors", "camp i seguiment"],
            ],
            "widths": [36 * mm, 44 * mm, 48 * mm, 42 * mm],
            "interpretation": (
                "Alinyà presenta una base ecològica forta i una responsabilitat de conservació elevada. La qüestió central no és recuperar un espai degradat de manera general, sinó evitar que el tancament del paisatge, la gestió forestal poc fina, l'ús públic no ordenat o la manca d'informació sobre aigua i estrès vegetal erosionin funcions que ara encara semblen actives. "
                "La millor decisió és governar el canvi, no intentar congelar el territori: mantenir mosaic, protegir hàbitats, entendre l'aigua, ordenar accessos i intervenir només on l'actuació millori un procés ecològic concret."
            ),
            "limitations": (
                "Aquesta conclusió és estratègica. La seva conversió en pla executiu requereix camp, governança, pressupost, permisos i actualització de dades dinàmiques."
            ),
            "confidence": "mitjana-alta",
            "decision": [
                "Adoptar EcoRadar com a diagnosi inicial per prioritzar gestió, no com a substitut d'un projecte executiu sectorial.",
                "Declarar com a línia de gestió: conservar valors existents, mantenir mosaic, ordenar pressions i validar abans d'actuar.",
                "Fer que cada futura actuació respongui a una pregunta: quin procés ecològic millora i com es comprovarà?",
            ],
        }),
        common_labels({
            "number": 18,
            "title": "Annex tècnic: traçabilitat de les dades",
            "subtitle": "Informació interna per auditoria, no per decisió directa de gestió",
            "data_used": [
                "registre central de fonts",
                "estat de dades disponibles",
                "serveis oficials i fonts manuals",
                "metadades i validació",
            ],
            "result_note": "Aquests elements s'inclouen només per transparència tècnica.",
            "map_kind": "base",
            "map_note": "Mapa base de suport a la traçabilitat tècnica.",
            "rows": [["Bloc", "Font", "Paper", "Decisió"]] + [list(row) for row in SOURCE_MATRIX[:6]],
            "widths": [30 * mm, 48 * mm, 44 * mm, 48 * mm],
            "interpretation": (
                "La traçabilitat permet revisar quines dades alimenten cada conclusió, quines fonts han estat processades i quines continuen condicionades per permisos, accés manual o camp. Aquesta informació és necessària per auditar el producte, però no forma part del relat principal de gestió."
            ),
            "limitations": (
                "Els detalls tècnics no incrementen per si sols la qualitat ecològica; només permeten verificar-la i actualitzar-la."
            ),
            "confidence": "alta com a annex tècnic",
            "decision": [
                "Mantenir la traçabilitat fora del cos principal de l'informe destinat a gestors.",
                "Actualitzar aquest annex quan canviïn fonts, permisos, sistemes de referència o metadades.",
                "No convertir una font absent en una dada estimada dins cap conclusió.",
            ],
        }),
        common_labels({
            "number": 19,
            "title": "Annex tècnic: dades insuficients i efecte sobre decisions",
            "subtitle": "Quines incerteses afecten cada capítol",
            "data_used": [
                "informes de disponibilitat",
                "completesa d'indicadors",
                "validació tècnica i ecològica",
                "checklist de camp",
            ],
            "result_note": "Les dades insuficients s'expressen com a impacte sobre decisions, no com a excusa metodològica.",
            "map_kind": "base",
            "map_note": "Les incerteses s'han de convertir en tasques de camp o actualització de fonts.",
            "rows": [
                ["Nivell", "En què es basa", "Què indica", "Com s'ha d'usar"],
                ["Alta", "fonts oficials, completes i coherents", "decisió defensable a escala de diagnosi", "actuar amb prudència normal"],
                ["Mitjana", "bones fonts però falta detall local o dinàmic", "criteri orientador", "validar abans d'executar"],
                ["Baixa", "falta una peça crítica o només hi ha proxy", "hipòtesi de treball", "no zonificar ni actuar"],
                ["Variable", "canvia segons procés i escala", "separar decisió general i detall", "documentar condicions"],
            ],
            "widths": [30 * mm, 48 * mm, 50 * mm, 42 * mm],
            "interpretation": (
                "La confiança no mesura si una conclusió sona convincent, sinó si les dades permeten convertir-la en decisió. EcoRadar la basa en cinc criteris: qualitat oficial de la font, actualitat, escala adequada, coherència amb altres capes i validació o comprovació local. Per això una mateixa pàgina pot tenir confiança alta per estructura territorial i baixa per estat fisiològic: saber on hi ha bosc és sòlid; saber quin bosc pateix estrès exigeix una dada dinàmica. La incertesa és útil quan es tradueix en una decisió ajornada o en una tasca concreta. En aquesta versió, les mancances principals afecten decisions fines sobre vegetació, foc, aigua i ús públic real; no impedeixen decisions preventives sobre conservació d'hàbitats, prudència en zones sensibles i planificació de camp."
            ),
            "limitations": (
                "Aquest annex resumeix el sentit operatiu de la confiança. El detall tècnic complet queda a les metadades, però el criteri de gestió és simple: confiança alta permet decidir, mitjana orienta i baixa obliga a validar."
            ),
            "confidence": "alta sobre l'impacte de les mancances",
            "confidence_note": "Aquí la confiança és alta perquè no afirma resultats ecològics nous: explica com s'ha ponderat la solidesa de cada conclusió.",
            "decision": [
                "No eliminar incerteses del document principal: convertir-les en prudència ecològica i decisions condicionades.",
                "Assignar responsable i calendari a cada dada que pot canviar una decisió.",
                "Reexecutar la diagnosi quan les dades dinàmiques o de camp estiguin incorporades.",
            ],
        }),
    ]
    return chapters


def page_phase2_overview(report: Report, data: dict[str, Any]) -> None:
    report.new_page("12 RADAR · metodologia revisada", "Lectures directes, perfils i decisions sense escala comuna 0–100")
    m = report.margin
    top = report.height - 48 * mm
    snapshot = data.get("core_payload", {}).get("snapshot_id") or "pendent de segellat"
    report.card(m, top - 28 * mm, 178 * mm, 23 * mm, "Contracte metodològic", fill=GREEN_PALE)
    report.para_fit(
        f"Metodologia alinya_core_v2_2026-09-09 · snapshot {snapshot}. Cada RADAR conserva la seva escala, unitat i límits; COMPLET/PARCIAL/NO AVALUABLE no descriuen qualitat ecològica.",
        m + 6 * mm, top - 19 * mm, 166 * mm, 8 * mm, "small", 6.8,
    )
    rows = [["RADAR", "Resultat", "Tipus", "Estat", "Confiança"]]
    for item in data["core"]:
        rows.append([
            item.get("code", "").replace("CORE_", "RADAR_"),
            item.get("primary_result") or "NO AVALUABLE",
            str(item.get("measurement_kind", "")).replace("_", " "),
            item.get("status", ""),
            item.get("confidence", ""),
        ])
    draw_table(report, rows, m, top - 35 * mm, [22 * mm, 69 * mm, 36 * mm, 29 * mm, 22 * mm], 6.0)
    report.card(m, 28 * mm, 178 * mm, 26 * mm, "Regla de lectura")
    report.para_fit(
        "Només el perill d'incendi diari manté una escala sintètica pròpia fora dels CORE. NDVI, superfícies, longituds i recomptes són valors directes; els perfils no s'aplanen i CORE_12 compara alternatives amb vetos.",
        m + 6 * mm, 40 * mm, 166 * mm, 10 * mm, "small", 6.8,
    )
    report.footer()


def page_phase2_details(report: Report, data: dict[str, Any], items: list[dict[str, Any]], title: str) -> None:
    report.new_page(title, "Què mesura, resultat, interpretació i confiança")
    m = report.margin
    top = report.height - 48 * mm
    gap = 6 * mm
    card_w = 86 * mm
    card_h = 59 * mm
    for index, item in enumerate(items):
        col = index % 2
        row = index // 2
        x = m + col * (card_w + gap)
        y = top - (row + 1) * card_h - row * gap
        report.card(x, y, card_w, card_h, fill=GREEN_PALE if item.get("status") == "COMPLET" else CREAM)
        report.c.setFillColor(ACCENT)
        report.c.roundRect(x + 5 * mm, y + card_h - 17 * mm, 14 * mm, 1.1 * mm, 0.5, fill=1, stroke=0)
        report.para_fit(
            f"{item.get('code', '').replace('CORE_', 'RADAR_')} · {item.get('name', '')}",
            x + 5 * mm, y + card_h - 5 * mm, card_w - 10 * mm, 10 * mm, "card_title", 7.2,
        )
        report.para_fit(
            item.get('primary_result') or 'NO AVALUABLE',
            x + 5 * mm, y + card_h - 20 * mm, card_w - 10 * mm, 8 * mm, "small_bold", 6.6,
        )
        report.para_fit(
            item.get("interpretation_short", ""),
            x + 5 * mm, y + card_h - 31 * mm, card_w - 10 * mm, 14 * mm, "small", 6.4,
        )
        report.para_fit(
            f"{item.get('status')} · confiança {item.get('confidence')}. {item.get('confidence_reason', '')}",
            x + 5 * mm, y + 15 * mm, card_w - 10 * mm, 11 * mm, "tiny", 5.9,
        )
    report.footer()


def page_phase2_diagnosis(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Diagnosi contextual", "Observació → significat → incertesa → implicació de gestió")
    m = report.margin
    top = report.height - 49 * mm
    rows = [["Tipus", "Conclusió específica", "Implicació per al gestor", "Conf."]]
    for item in data.get("diagnosis", {}).get("conclusions", []):
        rows.append([
            item.get("evidence_type", "interpretació"),
            item.get("title", ""),
            item.get("management_implication", ""),
            item.get("confidence", ""),
        ])
    draw_table(report, rows, m, top, [28 * mm, 53 * mm, 76 * mm, 21 * mm], 5.9)
    report.card(m, 25 * mm, 178 * mm, 30 * mm, "Vigència")
    report.para_fit(
        "Meteorologia, Pla Alfa i perill d'incendi caduquen amb l'actualització diària. L'NDVI descriu el 07/07/2026 i el producte de refugis combina aquesta escena amb un compost LST 2025–2026; tots dos són context, no estat actual.",
        m + 6 * mm, 41 * mm, 166 * mm, 12 * mm, "small", 6.8,
    )
    report.footer()


def page_phase2_decision(report: Report, data: dict[str, Any]) -> None:
    report.new_page("Síntesi multicriteri", "CORE_12 · sector × alternativa, vetos i opcions no dominades")
    m = report.margin
    top = report.height - 49 * mm
    core12 = core_row(data["core"], "CORE_12")
    rows = [["Sector o unitat documentada", "Alternativa", "Resultat", "Veto o límit"]]
    for item in core12.get("profile", {}).get("rows", []):
        rows.append([
            item.get("sector", ""),
            item.get("alternative", ""),
            item.get("result", ""),
            "; ".join(item.get("vetoes", [])) or item.get("robustness", ""),
        ])
    draw_table(report, rows, m, top, [48 * mm, 55 * mm, 21 * mm, 54 * mm], 6.2)
    report.card(m, 57 * mm, 178 * mm, 36 * mm, "Resultat global", fill=GREEN_PALE)
    report.para_fit(
        f"{core12.get('primary_result')}. {core12.get('interpretation_short')} No s'aplica cap mitjana, compensació o puntuació territorial única.",
        m + 6 * mm, 79 * mm, 166 * mm, 16 * mm, "small", 6.8,
    )
    core11 = core_row(data["core"], "CORE_11")
    report.card(m, 25 * mm, 178 * mm, 26 * mm, "Porta de restauració")
    report.para_fit(
        f"{core11.get('primary_result')}. {core11.get('interpretation_short')}",
        m + 6 * mm, 38 * mm, 166 * mm, 9 * mm, "small", 6.8,
    )
    report.footer()


def build_phase2_report(report: Report, data: dict[str, Any], include_all_pages: bool) -> None:
    page_phase2_overview(report, data)
    if include_all_pages:
        page_phase2_details(report, data, data["core"][:6], "RADAR 01–06")
        page_phase2_details(report, data, data["core"][6:], "RADAR 07–12")
        page_phase2_diagnosis(report, data)
        page_phase2_decision(report, data)


def build_report(path: Path, data: dict[str, Any], include_all_pages: bool = True) -> None:
    report = Report(path, f"Informe EcoRadar A4 - {project_display_name()}")
    if phase2_methodology(data):
        build_phase2_report(report, data, include_all_pages)
    elif include_all_pages:
        page_cover(report, data)
        for block in management_report_blocks(data):
            page_management_block_intro(report, block)
            for index, chapter in enumerate(block["chapters"], start=1):
                page_progressive_chapter(report, chapter, block, index)
        annexes = technical_annex_chapters(data)
        for index, chapter in enumerate(annexes, start=1):
            page_technical_annex(report, chapter, index)
    else:
        page_fitxa(report, data)
    report.finish()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate EcoRadar A4 client report from existing pipeline outputs.")
    parser.add_argument("--project", default=str(PROJECT), help="Project directory, for example projectes/Alinya")
    args = parser.parse_args()
    configure_project(args.project)
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    data = prepare_inputs()
    build_report(FITXA_PATH, data, include_all_pages=False)
    build_report(REPORT_PATH, data, include_all_pages=True)
    shutil.copy2(FITXA_PATH, OUTPUT_FITXA_PATH)
    shutil.copy2(REPORT_PATH, OUTPUT_REPORT_PATH)
    print(json.dumps({"report": str(REPORT_PATH), "fitxa": str(FITXA_PATH)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
