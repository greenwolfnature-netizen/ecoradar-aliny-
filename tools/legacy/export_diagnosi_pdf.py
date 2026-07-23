"""Export the Alinya EcoRadar diagnosis Markdown to PDF."""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MD = ROOT / "projectes" / "Alinya" / "reports" / "diagnosi_ecoradar_alinya.md"
PROJECT_PDF = ROOT / "projectes" / "Alinya" / "reports" / "diagnosi_ecoradar_alinya.pdf"
OUTPUT_PDF = ROOT / "output" / "pdf" / "diagnosi_ecoradar_alinya.pdf"


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "EcoTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17352B"),
            spaceAfter=16,
        ),
        "subtitle": ParagraphStyle(
            "EcoSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4E5F58"),
            spaceAfter=16,
        ),
        "h2": ParagraphStyle(
            "EcoHeading2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            textColor=colors.HexColor("#17352B"),
            spaceBefore=13,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "EcoBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.6,
            leading=13.4,
            alignment=TA_LEFT,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "EcoSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.6,
            leading=9.4,
        ),
        "cell": ParagraphStyle(
            "EcoCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.2,
            wordWrap="CJK",
        ),
        "cell_header": ParagraphStyle(
            "EcoCellHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=9.2,
            textColor=colors.white,
            wordWrap="CJK",
        ),
    }


def clean_inline(text: str) -> str:
    text = text.replace("·", "-")
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    return escaped


def parse_table(lines: list[str], styles: dict[str, ParagraphStyle]) -> Table:
    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)

    if not rows:
        return Table([])

    col_count = len(rows[0])
    usable_width = A4[0] - 36 * mm
    if col_count == 2:
        widths = [usable_width * 0.55, usable_width * 0.45]
    elif col_count == 3:
        widths = [usable_width * 0.31, usable_width * 0.22, usable_width * 0.47]
    elif col_count == 6:
        widths = [
            usable_width * 0.12,
            usable_width * 0.33,
            usable_width * 0.13,
            usable_width * 0.13,
            usable_width * 0.16,
            usable_width * 0.13,
        ]
    else:
        widths = [usable_width / col_count for _ in range(col_count)]

    data = []
    for row_index, row in enumerate(rows):
        style = styles["cell_header"] if row_index == 0 else styles["cell"]
        data.append([Paragraph(clean_inline(cell), style) for cell in row])

    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245644")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B9C8C0")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAF8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def flush_paragraph(buffer: list[str], story: list, styles: dict[str, ParagraphStyle]) -> None:
    if not buffer:
        return
    paragraph = " ".join(item.strip() for item in buffer).strip()
    if paragraph:
        story.append(Paragraph(clean_inline(paragraph), styles["body"]))
    buffer.clear()


def build_story(markdown: str) -> list:
    styles = build_styles()
    story: list = []
    lines = markdown.splitlines()
    paragraph_buffer: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()

        if not line:
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Spacer(1, 2.5 * mm))
            index += 1
            continue

        if line.startswith("# "):
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(clean_inline(line[2:].strip()), styles["title"]))
            story.append(Paragraph("Diagnosi tècnica preliminar amb dades disponibles", styles["subtitle"]))
            story.append(Spacer(1, 4 * mm))
            index += 1
            continue

        if line.startswith("## "):
            flush_paragraph(paragraph_buffer, story, styles)
            story.append(Paragraph(clean_inline(line[3:].strip()), styles["h2"]))
            index += 1
            continue

        if line.startswith("|"):
            flush_paragraph(paragraph_buffer, story, styles)
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            story.append(parse_table(table_lines, styles))
            story.append(Spacer(1, 4 * mm))
            continue

        if line.startswith("- "):
            flush_paragraph(paragraph_buffer, story, styles)
            while index < len(lines) and lines[index].startswith("- "):
                item_text = lines[index][2:].strip()
                story.append(Paragraph(clean_inline(f"- {item_text}"), styles["body"]))
                index += 1
            story.append(Spacer(1, 2.5 * mm))
            continue

        if re.match(r"^\d+\. ", line):
            flush_paragraph(paragraph_buffer, story, styles)
            while index < len(lines) and re.match(r"^\d+\. ", lines[index]):
                match = re.match(r"^(\d+)\. (.*)", lines[index])
                item_text = f"{match.group(1)}. {match.group(2).strip()}" if match else lines[index].strip()
                story.append(Paragraph(clean_inline(item_text), styles["body"]))
                index += 1
            story.append(Spacer(1, 2.5 * mm))
            continue

        paragraph_buffer.append(line)
        index += 1

    flush_paragraph(paragraph_buffer, story, styles)
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Annex de traçabilitat", styles["h2"]))
    story.append(Paragraph(clean_inline(f"Font Markdown: {SOURCE_MD.relative_to(ROOT)}"), styles["body"]))
    story.append(Paragraph(clean_inline(f"PDF de projecte: {PROJECT_PDF.relative_to(ROOT)}"), styles["body"]))
    return story


def draw_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#63736C"))
    page_text = f"EcoRadar - Alinyà - Diagnosi preliminar - p. {doc.page}"
    canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, page_text)
    canvas.restoreState()


def export_pdf() -> None:
    PROJECT_PDF.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    markdown = SOURCE_MD.read_text(encoding="utf-8")
    doc = SimpleDocTemplate(
        str(PROJECT_PDF),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Primera diagnosi EcoRadar - Alinya",
        author="EcoRadar",
        subject="Diagnosi tècnica preliminar amb dades disponibles",
    )
    doc.build(build_story(markdown), onFirstPage=draw_footer, onLaterPages=draw_footer)
    shutil.copy2(PROJECT_PDF, OUTPUT_PDF)


if __name__ == "__main__":
    export_pdf()
