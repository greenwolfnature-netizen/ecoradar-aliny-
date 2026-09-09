"""Export the complete Muntanya d'Alinya report using the EcoRadar urban layout.

The exporter only reads existing, validated EcoRadar outputs.  It creates a
landscape technical report, appends the frozen Fitxa EcoRadar v1 and then
appends the five-page post-fire document without changing its page order.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ecoradar.reporting import client_report_a4 as source
from tools import export_la_seu_urban_report_v2 as urban
from tools import export_postfoc_ecoradar_alinya_a4 as postfire_export


PROJECT = ROOT / "projectes" / "Alinya"
DEFAULT_BODY = PROJECT / "reports" / "informe_ecoradar_alinya_plantilla_urba_cos.pdf"
DEFAULT_OUTPUT = PROJECT / "reports" / "informe_complet_muntanya_alinya.pdf"
DEFAULT_FITXA = PROJECT / "reports" / "fitxa_ecoradar_alinya_a4.pdf"
OUTPUT_COPY = ROOT / "output" / "pdf" / "informe_complet_muntanya_alinya.pdf"

PAGE_W, PAGE_H = landscape(A4)
MX = 15 * mm
CW = PAGE_W - 2 * MX
TOP = PAGE_H - 34 * mm


def value(data: dict[str, Any], key: str) -> Any:
    return source.metric(data["basic"], key)


def score(data: dict[str, Any], code: str) -> str:
    return source.fmt(source.core_metric(data["core"], code), 1)


def hydrology_km(data: dict[str, Any]) -> float:
    return (source.num(source.row_value(data["hydrology"], "layer_id", "rius_aca_che", "length_km")) or 0) + (
        source.num(source.row_value(data["hydrology"], "layer_id", "eixos_drenatge", "length_km")) or 0
    )


def biodiversity_breakdown() -> dict[str, Any]:
    """Summarize the normalized biodiversity records by ecologically useful groups.

    Orders are read from the retained GBIF/iNaturalist raw responses and joined
    to the 731 records that survived normalization and the study-area clip.
    Counts are records, not abundance estimates or a complete inventory.
    """

    connection = sqlite3.connect(PROJECT / "processed" / "biodiversitat.gpkg")
    try:
        processed = connection.execute(
            "SELECT source, source_record_id, scientificName, taxonGroup FROM biodiversitat"
        ).fetchall()
    finally:
        connection.close()

    taxonomy: dict[tuple[str, str], tuple[str | None, str | None]] = {}
    raw_inputs = (
        ("GBIF", PROJECT / "raw" / "biodiversitat" / "gbif_raw.json"),
        ("iNaturalist", PROJECT / "raw" / "biodiversitat" / "inaturalist_raw.json"),
    )
    for source_name, path in raw_inputs:
        for record in json.loads(path.read_text(encoding="utf-8"))["records"]:
            if source_name == "GBIF":
                record_id = str(record.get("gbifID") or record.get("key"))
                order = record.get("order")
                canonical = record.get("species") or record.get("acceptedScientificName") or record.get("scientificName")
            else:
                record_id = str(record.get("id"))
                taxon = record.get("taxon") or {}
                canonical = taxon.get("name")
                order = None
                for identification in record.get("identifications", []):
                    identified_taxon = identification.get("taxon") or {}
                    for ancestor in identified_taxon.get("ancestors", []):
                        if ancestor.get("rank") == "order":
                            order = ancestor.get("name")
                    if identified_taxon.get("rank") == "order":
                        order = identified_taxon.get("name")
                    if order:
                        break
            taxonomy[(source_name, record_id)] = (order, canonical)

    def category(group: str, order: str | None) -> str:
        if group == "Aves":
            return "Ocells"
        if order == "Lepidoptera":
            return "Papallones i arnes"
        if order == "Chiroptera":
            return "Ratpenats"
        if group == "Mammalia":
            return "Altres mamífers"
        if order == "Odonata":
            return "Odonats"
        if order == "Orthoptera":
            return "Ortòpters"
        if group == "Insecta":
            return "Altres insectes"
        if group in {"Reptilia", "Squamata"}:
            return "Rèptils"
        if group == "Amphibia":
            return "Amfibis"
        if group == "Arachnida":
            return "Aràcnids"
        if group == "Plantae":
            return "Flora"
        if group == "Fungi":
            return "Fongs i líquens"
        if group == "Mollusca":
            return "Mol·luscs"
        return "Altres grups"

    records: Counter[str] = Counter()
    taxa: dict[str, set[str]] = defaultdict(set)
    names: dict[str, Counter[str]] = defaultdict(Counter)
    for source_name, record_id, scientific_name, taxon_group in processed:
        order, canonical = taxonomy.get((source_name, str(record_id)), (None, None))
        group = category(taxon_group or "", order)
        taxon_name = canonical or scientific_name or "Taxó no resolt"
        records[group] += 1
        taxa[group].add(taxon_name)
        names[group][taxon_name] += 1

    # A category with zero records is still reported because it identifies a
    # survey gap requested explicitly by the client.
    records.setdefault("Ratpenats", 0)
    taxa.setdefault("Ratpenats", set())
    names.setdefault("Ratpenats", Counter())
    return {
        "records": records,
        "taxa": {key: len(value) for key, value in taxa.items()},
        "top": {key: value.most_common(6) for key, value in names.items()},
    }


def footer(c: canvas.Canvas, page: int) -> None:
    y = 10 * mm
    c.setStrokeColor(urban.RULE)
    c.setLineWidth(0.65)
    c.line(MX, y + 5 * mm, PAGE_W - MX, y + 5 * mm)
    c.setFillColor(urban.MUTED)
    c.setFont("Arial", 6.5)
    c.drawString(MX, y, "EcoRadar - Informe de Diagnosi Ecologica Integrada - Muntanya d'Alinya")
    c.drawRightString(PAGE_W - MX, y, str(page))


def header(c: canvas.Canvas, number: str, title: str, subtitle: str, page: int) -> None:
    c.setFillColor(urban.NAVY)
    c.setFont("Arial-Bold", 21)
    c.drawString(MX, PAGE_H - 17 * mm, urban.cat(f"{number}. {title}" if number else title))
    c.setFillColor(urban.GREEN)
    c.setFont("Arial-Bold", 11)
    c.drawString(MX, PAGE_H - 27 * mm, urban.cat(subtitle))
    footer(c, page)


def metric_strip(c: canvas.Canvas, metrics: list[tuple[str, str, str, Any]], y: float = 140 * mm) -> None:
    gap = 4 * mm
    w = (CW - 3 * gap) / 4
    for idx, (v, label, note, color) in enumerate(metrics):
        urban.draw_metric_card(c, MX + idx * (w + gap), y, w, 31 * mm, v, label, note, color)


def map_card(c: canvas.Canvas, path: Path, title: str, note: str, x: float, y: float, w: float, h: float) -> None:
    urban.rounded_card(c, x, y, w, h, fill=urban.CARD)
    urban.draw_paragraph(c, f"<b>{title}</b>", x + 6 * mm, y + h - 6 * mm, w - 12 * mm, "card_title")
    if path.exists():
        urban.draw_image_fit(c, path, x + 6 * mm, y + 16 * mm, w - 12 * mm, h - 36 * mm)
    else:
        urban.draw_paragraph(c, "Cartografia no disponible en aquesta versio.", x + 6 * mm, y + h - 28 * mm, w - 12 * mm, "body_small")
    urban.draw_paragraph(c, note, x + 6 * mm, y + 12 * mm, w - 12 * mm, "source")


def evidence_page(
    c: canvas.Canvas,
    page: int,
    number: str,
    title: str,
    subtitle: str,
    metrics: list[tuple[str, str, str, Any]],
    map_kind: str,
    thesis: str,
    interpretation: str,
    decisions: list[str],
    limitation: str,
) -> None:
    header(c, number, title, subtitle, page)
    metric_strip(c, metrics)
    gap = 7 * mm
    left_w = 105 * mm
    right_x = MX + left_w + gap
    right_w = CW - left_w - gap
    map_title = "Potencial relatiu de refugi climatic" if map_kind == "refugis_climatics" else "Expressio territorial"
    map_note = (
        "Blau fosc: potencial alt o molt alt per frescor LST, NDMI i NDVI. Línies blaves: xarxa hidrica; punts blaus: fonts. Capa de cribratge, no refugi validat."
        if map_kind == "refugis_climatics"
        else "Mapa de suport generat amb les capes processades del projecte Alinya."
    )
    map_card(
        c,
        source.project_map_path(map_kind),
        map_title,
        map_note,
        MX,
        36 * mm,
        left_w,
        96 * mm,
    )
    urban.rounded_card(c, right_x, 99 * mm, right_w, 33 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Tesi de la Fitxa</b>", right_x + 6 * mm, 126 * mm, right_w - 12 * mm, "card_title")
    urban.draw_paragraph(c, thesis, right_x + 6 * mm, 115 * mm, right_w - 12 * mm, "body_small")
    urban.rounded_card(c, right_x, 56 * mm, right_w, 39 * mm, fill=urban.CARD)
    urban.draw_paragraph(c, "<b>Lectura ecologica argumentada</b>", right_x + 6 * mm, 89 * mm, right_w - 12 * mm, "card_title")
    urban.draw_paragraph(c, interpretation, right_x + 6 * mm, 78 * mm, right_w - 12 * mm, "body_small")
    urban.rounded_card(c, right_x, 18 * mm, right_w, 34 * mm, fill=urban.PALE_BLUE)
    urban.draw_paragraph(c, "<b>Decisions de gestio</b>", right_x + 6 * mm, 46 * mm, right_w - 12 * mm, "card_title")
    urban.draw_bullets(c, decisions, right_x + 6 * mm, 36 * mm, right_w - 12 * mm, "source", urban.NAVY, 1.5)
    urban.rounded_card(c, MX, 18 * mm, left_w, 13 * mm, fill=urban.PALE_ORANGE)
    urban.draw_paragraph(c, f"<b>Limitacio:</b> {limitation}", MX + 5 * mm, 28 * mm, left_w - 10 * mm, "source")
    c.showPage()


def cover(c: canvas.Canvas, data: dict[str, Any]) -> None:
    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_W * 0.52, PAGE_H, fill=1, stroke=0)
    c.setFillColor(urban.BG)
    c.rect(PAGE_W * 0.52, 0, PAGE_W * 0.48, PAGE_H, fill=1, stroke=0)
    x = MX + 4 * mm
    c.setFillColor(urban.NAVY)
    c.setFont("Arial-Bold", 29)
    c.drawString(x, PAGE_H - 42 * mm, "ECORADAR")
    c.setFillColor(urban.GREEN)
    c.setFont("Arial-Bold", 23)
    c.drawString(x, PAGE_H - 57 * mm, "Muntanya d'Alinya")
    c.setFillColor(urban.INK)
    c.setFont("Arial-Bold", 16)
    c.drawString(x, PAGE_H - 82 * mm, "Informe de diagnosi ecologica integrada")
    c.setFillColor(urban.NAVY)
    c.setFont("Arial-Bold", 9.5)
    c.drawString(x, PAGE_H - 98 * mm, "Mosaic + habitats + biodiversitat + aigua + connectivitat + foc")
    urban.rounded_card(c, x, 43 * mm, PAGE_W * 0.43, 43 * mm, fill=colors.HexColor("#F7F8F5"), stroke=urban.INK)
    urban.draw_paragraph(
        c,
        "Document tecnic per justificar la Fitxa EcoRadar v1 amb dades reals del projecte, processos ecologics, implicacions de gestio, incerteses i un programa de seguiment. Inclou, al final i en el seu ordre original, el document postincendi.",
        x + 7 * mm,
        78 * mm,
        PAGE_W * 0.39,
        "body",
    )
    c.setFillColor(urban.MUTED)
    c.setFont("Arial", 7.5)
    c.drawString(x, 26 * mm, f"Versio 1.0 - {date.today().strftime('%d/%m/%Y')} - ETRS89 / UTM 31N (EPSG:25831)")
    source.draw_brand_logo(c, source.ECORADAR_LOGO, x, 5 * mm, 16 * mm)
    c.setFillColor(urban.NAVY)
    c.setFont("Arial-Bold", 7.2)
    c.drawString(x + 19 * mm, 15 * mm, "ECORADAR")
    c.setFillColor(urban.MUTED)
    c.setFont("Arial", 5.2)
    c.drawString(x + 19 * mm, 10 * mm, "Radiografia territorial")
    source.draw_brand_logo(c, source.GREEN_WOLF_LOGO, x + 60 * mm, 5 * mm, 16 * mm)
    c.setFillColor(urban.NAVY)
    c.setFont("Arial-Bold", 7.2)
    c.drawString(x + 79 * mm, 15 * mm, "GREEN WOLF NATURE")
    c.setFillColor(urban.MUTED)
    c.setFont("Arial", 5.2)
    c.drawString(x + 79 * mm, 10 * mm, "Natura, gestio i conservacio")
    rx = PAGE_W * 0.55
    urban.rounded_card(c, rx, 46 * mm, PAGE_W * 0.40, 130 * mm, fill=urban.CARD)
    urban.draw_paragraph(c, "<b>LECTURA TERRITORIAL</b>", rx + 7 * mm, 168 * mm, PAGE_W * 0.36, "card_title")
    urban.draw_image_fit(c, source.project_map_path("espai"), rx + 7 * mm, 76 * mm, PAGE_W * 0.36, 82 * mm)
    urban.draw_metric_card(c, rx + 6 * mm, 51 * mm, 54 * mm, 28 * mm, source.fmt(data["study"].get("surface_ha"), 0), "Hectarees", "Area d'estudi validada", urban.NAVY)
    urban.draw_metric_card(c, rx + 64 * mm, 51 * mm, 54 * mm, 28 * mm, score(data, "CORE_02"), "Habitats", "Puntuacio Radar /100", urban.GREEN)
    c.setFillColor(urban.MUTED)
    c.setFont("Arial", 6.6)
    c.drawRightString(PAGE_W - MX, 18 * mm, "Entrades validades el 08/07/2026; limitacions explicitades")
    c.showPage()


def executive(c: canvas.Canvas, data: dict[str, Any], page: int) -> None:
    header(c, "1", "Resum executiu", "Que diu la diagnosi i quines decisions permet prendre", page)
    gap = 7 * mm
    col = (CW - gap) / 2
    urban.rounded_card(c, MX, 106 * mm, col, 68 * mm, fill=urban.CARD)
    urban.draw_paragraph(c, "<b>Diagnosi sintetica</b>", MX + 7 * mm, 166 * mm, col - 14 * mm, "card_title")
    urban.draw_paragraph(
        c,
        "Alinya presenta una base ecologica forta i una responsabilitat de conservacio elevada. El proces dominant es el tancament progressiu del paisatge: una matriu forestal molt extensa pot reduir el paper funcional de prats, herbassars i ecotons. La prioritat no es transformar el territori de manera general, sino conservar habitats sensibles, mantenir mosaic, protegir punts d'aigua i ordenar pressions abans que erosionin funcions encara actives.",
        MX + 7 * mm,
        154 * mm,
        col - 14 * mm,
        "body_just",
    )
    rx = MX + col + gap
    urban.rounded_card(c, rx, 106 * mm, col, 68 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Decisio prioritaria</b>", rx + 7 * mm, 166 * mm, col - 14 * mm, "card_title")
    urban.draw_bullets(c, [
        "Aplicar una regla de no-deteriorament abans de qualsevol actuacio transformadora.",
        "Mantenir una xarxa d'espais oberts i ecotons seleccionada per funcio, no per quota superficial.",
        "Validar al camp habitats prioritaris, punts d'aigua, pressions reals i estructura forestal.",
        "Actuar nomes quan el benefici ecologic, el lloc i l'indicador de seguiment siguin explicits.",
    ], rx + 7 * mm, 152 * mm, col - 14 * mm, "body_small")
    metric_strip(c, [
        (source.fmt(value(data, "percentatge_coberta_forestal"), 1, "%"), "Coberta forestal", "Matriu territorial dominant", urban.GREEN),
        (source.fmt(value(data, "percentatge_prats_pastures_herbassars"), 1, "%"), "Prats i herbassars", "Discontinuitat funcional", urban.ORANGE),
        (source.fmt(value(data, "superficie_hic"), 0), "Ha d'HIC", "Responsabilitat de conservacio", urban.NAVY),
        (str(value(data, "nombre_especies_registrades")), "Taxons citats", "Coneixement public oportunista", urban.PURPLE),
    ], 66 * mm)
    urban.rounded_card(c, MX, 23 * mm, CW, 34 * mm, fill=urban.PALE_BLUE)
    urban.draw_paragraph(c, "<b>Missatge clau.</b> Governar el canvi: conservar valors existents, mantenir mosaic, entendre l'aigua, ordenar accessos i intervenir nomes on una actuacio millori un proces ecologic concret.", MX + 8 * mm, 48 * mm, CW - 16 * mm, "body")
    c.showPage()


def framework(c: canvas.Canvas, page: int) -> None:
    header(c, "2", "Marc de diagnosi integrada", "De les dades territorials a processos, consequencies i decisions", page)
    urban.draw_process_band(c, [
        ("EVIDENCIA", "Capes oficials i resultats calculats."),
        ("PROCES", "Mosaic, aigua, connectivitat, clima i foc."),
        ("CONSEQUENCIA", "Que es pot perdre si no s'actua."),
        ("DECISIO", "On conservar, validar o intervenir."),
        ("SEGUIMENT", "Com comprovar el retorn ecologic."),
    ], MX, 133 * mm, CW)
    cards = [
        ("Que es", urban.PALE_GREEN, ["Una diagnosi executiva vinculada a la Fitxa EcoRadar vigent.", "Una lectura de processos ecologics, no una suma de capes.", "Un suport per prioritzar camp, conservacio i gestio adaptativa."]),
        ("Que no es", urban.PALE_ORANGE, ["No es un projecte executiu forestal, hidrologic o postincendi.", "No converteix accessibilitat OSM en frequentacio real.", "No declara absencies d'especies ni estat fisiologic sense dades."]),
        ("Criteri de gestio", urban.PALE_BLUE, ["Conservar abans de transformar.", "Validar quan la incertesa pot canviar la decisio.", "Mesurar el proces que justifica cada actuacio."]),
    ]
    gap = 7 * mm
    w = (CW - 2 * gap) / 3
    for i, (title, fill, bullets) in enumerate(cards):
        x = MX + i * (w + gap)
        urban.rounded_card(c, x, 48 * mm, w, 72 * mm, fill=fill)
        urban.draw_paragraph(c, f"<b>{title}</b>", x + 7 * mm, 112 * mm, w - 14 * mm, "card_title")
        urban.draw_bullets(c, bullets, x + 7 * mm, 98 * mm, w - 14 * mm, "body_small")
    urban.rounded_card(c, MX, 22 * mm, CW, 18 * mm, fill=urban.CARD)
    urban.draw_paragraph(c, "<b>Regla de confiança:</b> alta permet orientar decisio a escala de diagnosi; mitjana exigeix contrast local; baixa obliga a ajornar la zonificacio o prescripcio fina.", MX + 7 * mm, 35 * mm, CW - 14 * mm, "body_small")
    c.showPage()


def method(c: canvas.Canvas, data: dict[str, Any], page: int) -> None:
    header(c, "3", "Dades, escala i metode", "Fonts documentades, normalitzacio i validacio del projecte", page)
    urban.draw_process_band(c, [
        ("INVENTARI", "Organisme responsable i servei oficial."),
        ("VERIFICACIO", "Format, llicencia, escala i estat."),
        ("NORMALITZACIO", "Retall espacial i CRS EPSG:25831."),
        ("DIAGNOSI", "Indicadors i relacions ecologiques."),
        ("VALIDACIO", "Controls tecnics, ecologics i de recomanacions."),
    ], MX, 139 * mm, CW)
    rows = [
        [urban.P("Bloc", "table_bold"), urban.P("Font principal usada", "table_bold"), urban.P("Resultat documentat", "table_bold"), urban.P("Prudencia", "table_bold")],
        [urban.P("Cobertes", "table"), urban.P("ICGC Cobertes del sol", "table"), urban.P("5.464,0 ha classificades", "table"), urban.P("No equival a estructura forestal de detall", "table")],
        [urban.P("Habitats", "table"), urban.P("Generalitat - habitats terrestres v3", "table"), urban.P("47 habitats; HIC derivats dels camps disponibles", "table"), urban.P("Cal validar estat local", "table")],
        [urban.P("Biodiversitat", "table"), urban.P("GBIF + iNaturalist", "table"), urban.P("731 registres normalitzats", "table"), urban.P("Mostra oportunista, no cens", "table")],
        [urban.P("Aigua", "table"), urban.P("ACA i cartografia oficial", "table"), urban.P("15 elements; 11,8 km; 12 fonts", "table"), urban.P("Funcionalitat pendent de camp", "table")],
        [urban.P("Foc", "table"), urban.P("Generalitat - superficies afectades", "table"), urban.P("2 perimetres; 17,4 ha", "table"), urban.P("Capa de similitud es proxy, no prediccio", "table")],
        [urban.P("Pressio", "table"), urban.P("OpenStreetMap / Overpass", "table"), urban.P("124,8 km i 18 punts d'us", "table"), urban.P("Accessibilitat potencial", "table")],
    ]
    table = urban.make_table(rows, [33 * mm, 62 * mm, 72 * mm, CW - 167 * mm], font_size=7)
    urban.table_on_canvas(c, table, MX, 132 * mm)
    urban.rounded_card(c, MX, 23 * mm, CW, 24 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Validacio:</b> estat APTE; 8 controls tecnics superats, validacio ecologica amb una limitacio menor explicita i 5 controls de recomanacions superats. Cap valor numeric sense font segons el control TECH_08.", MX + 7 * mm, 41 * mm, CW - 14 * mm, "body_small")
    c.showPage()


def biodiversity_page(c: canvas.Canvas, data: dict[str, Any], detail: dict[str, Any], page: int) -> None:
    """Render biodiversity as an evidence inventory, not a single score."""

    header(c, "7", "Biodiversitat detectada", "Quins grups consten a GBIF i iNaturalist, i que permet afirmar cada recompte", page)
    records = detail["records"]
    taxa = detail["taxa"]
    connector_taxa = {
        row.get("grup_taxonomic", ""): int(source.num(row.get("nombre_especies")) or 0)
        for row in data["biodiv"]
    }
    displayed_taxa = dict(taxa)
    displayed_taxa.update({
        "Flora": connector_taxa.get("Plantae", taxa["Flora"]),
        "Ocells": connector_taxa.get("Aves", taxa["Ocells"]),
        "Fongs i líquens": connector_taxa.get("Fungi", taxa["Fongs i líquens"]),
        "Altres mamífers": connector_taxa.get("Mammalia", taxa["Altres mamífers"]),
        "Aràcnids": connector_taxa.get("Arachnida", taxa["Aràcnids"]),
        "Rèptils": connector_taxa.get("Reptilia", 0) + connector_taxa.get("Squamata", 0),
        "Amfibis": connector_taxa.get("Amphibia", taxa["Amfibis"]),
    })
    metric_strip(c, [
        (str(value(data, "nombre_registres_biodiversitat")), "Registres normalitzats", "Presencies documentades, no abundancia", urban.GREEN),
        (str(value(data, "nombre_especies_registrades")), "Taxons registrats", "Noms acceptats pel connector", urban.PURPLE),
        (str(records["Ocells"]), "Registres d'ocells", "85 taxons al resum del projecte", urban.BLUE),
        (str(records["Papallones i arnes"]), "Papallones i arnes", f"{taxa['Papallones i arnes']} taxons nominals", urban.ORANGE),
    ])

    gap = 6 * mm
    left_w = 79 * mm
    table_w = 82 * mm
    right_w = CW - left_w - table_w - 2 * gap
    map_card(
        c,
        source.project_map_path("biodiversitat"),
        "Distribucio dels registres",
        "Cada punt es un registre incorporat; la densitat de punts tambe reflecteix esforc d'observacio.",
        MX,
        31 * mm,
        left_w,
        101 * mm,
    )

    table_x = MX + left_w + gap
    group_order = [
        "Flora", "Ocells", "Papallones i arnes", "Altres insectes", "Fongs i líquens",
        "Altres mamífers", "Ratpenats", "Aràcnids", "Odonats", "Ortòpters", "Rèptils", "Amfibis",
    ]
    rows = [[urban.P("Grup", "table_bold"), urban.P("Reg.", "table_bold"), urban.P("Taxons*", "table_bold")]]
    for group in group_order:
        rows.append([
            urban.P(group, "table"),
            urban.P(str(records[group]), "table"),
            urban.P(str(displayed_taxa[group]), "table"),
        ])
    table = urban.make_table(rows, [49 * mm, 14 * mm, 19 * mm], font_size=6.7)
    table_height = urban.table_on_canvas(c, table, table_x, 132 * mm)
    urban.draw_paragraph(
        c,
        "*Per als grans grups s'usa el resum del connector; per als subgrups d'insectes, noms taxonomics agrupats per ordre. No equival a riquesa completa.",
        table_x,
        128 * mm - table_height,
        table_w,
        "source",
    )

    right_x = table_x + table_w + gap
    urban.rounded_card(c, right_x, 77 * mm, right_w, 55 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Com s'ha d'interpretar</b>", right_x + 6 * mm, 126 * mm, right_w - 12 * mm, "card_title")
    urban.draw_paragraph(
        c,
        "Els registres confirmen que les bases publiques contenen una representacio ampla de flora, ocells i invertebrats. No mesuren densitat de poblacio: diverses cites poden correspondre a la mateixa especie, al mateix sector o a periodes amb esforc desigual. La cartografia serveix per localitzar coneixement existent, detectar buits i orientar camp en habitats sensibles, punts d'aigua, roquissars i ecotons.",
        right_x + 6 * mm,
        114 * mm,
        right_w - 12 * mm,
        "body_small",
    )
    urban.rounded_card(c, right_x, 31 * mm, right_w, 41 * mm, fill=urban.PALE_ORANGE)
    urban.draw_paragraph(c, "<b>Buit rellevant: ratpenats</b>", right_x + 6 * mm, 66 * mm, right_w - 12 * mm, "card_title")
    urban.draw_paragraph(
        c,
        "No hi ha cap registre de Chiroptera entre les 731 observacions normalitzades. Aixo no demostra absencia: els ratpenats estan infrarepresentats en plataformes visuals i requereixen detectors d'ultrasons, revisio de refugis i mostreig nocturn. Abans d'actuar sobre arbres vells, cavitats, edificacions o punts d'aigua, cal una prospeccio especifica.",
        right_x + 6 * mm,
        54 * mm,
        right_w - 12 * mm,
        "body_small",
    )

    top_birds = "; ".join(f"<i>{name}</i> ({count})" for name, count in detail["top"]["Ocells"][:4])
    top_leps = "; ".join(f"<i>{name}</i> ({count})" for name, count in detail["top"]["Papallones i arnes"][:4])
    urban.rounded_card(c, MX, 18 * mm, left_w + gap + table_w, 10 * mm, fill=urban.PALE_BLUE)
    urban.draw_paragraph(
        c,
        f"<b>Taxons amb mes registres:</b> ocells: {top_birds}. Lepidopters: {top_leps}.",
        MX + 5 * mm,
        26 * mm,
        left_w + gap + table_w - 10 * mm,
        "source",
    )
    c.showPage()


def postfire_memory_page(c: canvas.Canvas, data: dict[str, Any], fire: dict[str, Any], page: int) -> None:
    header(c, "10", "Memòria del foc", "Què demostren els perímetres oficials i quin problema de gestió plantegen", page)
    metric_strip(c, [
        (str(fire["fire_polygons"]), "Perimetres oficials", "Dins l'area d'estudi", urban.RED),
        (source.fmt(fire["burned_ha"], 1), "Ha cremades", source.fmt(fire["burned_pct"], 2, "%") + " de l'ambit", urban.ORANGE),
        (source.fmt(fire["forest_pct"], 1, "%"), "Coberta forestal", "Context territorial dominant", urban.GREEN),
        (score(data, "CORE_09"), "Resiliencia davant foc", "Indicador Radar /100", urban.NAVY),
    ])
    gap = 7 * mm
    left_w = 113 * mm
    right_x = MX + left_w + gap
    right_w = CW - left_w - gap
    map_card(c, PROJECT / "maps" / "incendis" / "mapa_incendis_context_alinya.svg.png", "Perimetres i cobertes", "Font del foc: superficies afectades per incendis forestals de la Generalitat. IncendisCat no s'utilitza com a font.", MX, 27 * mm, left_w, 105 * mm)
    cards = [
        (99 * mm, 33 * mm, urban.PALE_GREEN, "Evidencia disponible", "Els dos perimetres sumen 17,4 ha, una fraccio petita de l'ambit. La dada descriu on hi ha hagut afectacio oficial cartografiada; no informa per si sola de causa d'ignicio, severitat, combustible actual ni resposta postfoc."),
        (61 * mm, 34 * mm, urban.CARD, "Lectura ecologica", "El senyal rellevant no es la superficie cremada, sino la coincidencia local entre massa forestal, contacte bosc-matollar, relleu, accessos i discontinuïtats. El foc s'ha de llegir com un proces connectat al tancament del paisatge i a la disponibilitat d'humitat."),
        (22 * mm, 35 * mm, urban.PALE_BLUE, "Decisio que justifica", "No es defensa una restauracio extensiva. Es prioritza camp dirigit a vores accessibles, punts de contacte bosc-matollar i discontinuïtats que puguin reduir continuïtat sense perjudicar HIC, sols o refugis."),
    ]
    for y, h, fill, title, text in cards:
        urban.rounded_card(c, right_x, y, right_w, h, fill=fill)
        urban.draw_paragraph(c, f"<b>{title}</b>", right_x + 6 * mm, y + h - 6 * mm, right_w - 12 * mm, "card_title")
        urban.draw_paragraph(c, text, right_x + 6 * mm, y + h - 17 * mm, right_w - 12 * mm, "body_small")
    c.showPage()


def postfire_territory_page(c: canvas.Canvas, data: dict[str, Any], fire: dict[str, Any], page: int) -> None:
    header(c, "11", "Foc i territori", "Concurrència ambiental: una prioritzacio de camp, no un mapa predictiu", page)
    high_pct = fire["sim_high_ha"] / fire["study_ha"] * 100 if fire["study_ha"] else 0
    mid_pct = fire["sim_mid_ha"] / fire["study_ha"] * 100 if fire["study_ha"] else 0
    metric_strip(c, [
        (source.fmt(fire["sim_high_ha"], 0), "Ha alta/mitjana-alta", source.fmt(high_pct, 1, "%") + " de l'ambit", urban.RED),
        (source.fmt(fire["sim_mid_ha"], 0), "Ha mitjanes", source.fmt(mid_pct, 1, "%") + " de l'ambit", urban.ORANGE),
        (source.fmt(fire["paths_km"], 1), "Km d'accessos", "Variable de concurrencia", urban.BLUE),
        (score(data, "CORE_01"), "Mosaic", "Capacitat de discontinuïtat /100", urban.GREEN),
    ])
    gap = 7 * mm
    left_w = 132 * mm
    map_card(c, PROJECT / "maps" / "incendis_similarity" / "mapa_similitud_condicions_incendi_alinya.svg.png", "Concurrencia de condicions", "Les classes comparen condicions territorials amb les dels perimetres historics. No expressen probabilitat d'ignicio ni comportament futur del foc.", MX, 24 * mm, left_w, 108 * mm)
    rx = MX + left_w + gap
    rw = CW - left_w - gap
    rows = [
        [urban.P("Classe", "table_bold"), urban.P("Interpretacio correcta", "table_bold")],
        [urban.P("Alta", "table"), urban.P("Coincidencia territorial elevada; revisar primer al camp.", "table")],
        [urban.P("Mitjana-alta", "table"), urban.P("Diverses condicions coincidents; prioritat condicionada.", "table")],
        [urban.P("Mitjana", "table"), urban.P("Coincidencia parcial; no justifica actuacio per si sola.", "table")],
        [urban.P("Baixa", "table"), urban.P("Menor similitud amb els casos, no absencia de risc.", "table")],
    ]
    table = urban.make_table(rows, [27 * mm, rw - 27 * mm], font_size=6.8)
    urban.table_on_canvas(c, table, rx, 132 * mm)
    urban.rounded_card(c, rx, 57 * mm, rw, 36 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Per que es util</b>", rx + 6 * mm, 87 * mm, rw - 12 * mm, "card_title")
    urban.draw_paragraph(c, "Permet transformar una capa complexa en una agenda verificable: comprovar combustible continu, vores, pendent, acces d'extincio, HIC afectables i oportunitats de manteniment obert. La seva funcio es reduir l'area de prospeccio i ordenar prioritats, no declarar perill oficial.", rx + 6 * mm, 76 * mm, rw - 12 * mm, "body_small")
    urban.rounded_card(c, rx, 24 * mm, rw, 29 * mm, fill=urban.PALE_ORANGE)
    urban.draw_paragraph(c, "<b>Que falta</b>", rx + 6 * mm, 47 * mm, rw - 12 * mm, "card_title")
    urban.draw_paragraph(c, "Combustible i estructura forestal validats, humitat i vigor, meteorologia/sequera i perill operatiu. Sense aquestes peces s'ha de parlar de concurrencia, no de probabilitat.", rx + 6 * mm, 36 * mm, rw - 12 * mm, "body_small")
    c.showPage()


def postfire_argument_page(c: canvas.Canvas, fire: dict[str, Any], page: int) -> None:
    header(c, "12", "Argumentari postincendi", "Com es passa de la dada a una decisio professional i defensable", page)
    gap = 7 * mm
    w = (CW - gap) / 2
    cards = [
        (MX, 103 * mm, urban.PALE_GREEN, "1. Que demostren les dades", f"Hi ha {fire['fire_polygons']} perimetres oficials i {source.fmt(fire['burned_ha'],1)} ha cremades. La superficie es reduida, pero situa casos reals on comparar coberta, relleu, orientacio i accessibilitat. La massa de bosc i matollar domina el context, mentre les discontinuïtats obertes tenen un paper proporcionalment mes gran que la seva superficie."),
        (MX + w + gap, 103 * mm, urban.PALE_BLUE, "2. Que significa ecologicament", "El foc historic assenyala punts de contacte entre combustible potencial, topografia i acces. En un espai amb HIC i biodiversitat elevats, prevenir no equival a obrir franges indiscriminades: una actuacio mal situada pot degradar habitat, afavorir erosio o eliminar ecotons que tambe sostenen resiliencia."),
        (MX, 31 * mm, urban.PALE_ORANGE, "3. Que no sabem encara", "No s'ha calculat probabilitat estadistica ni comportament del foc. Falten estructura vertical, carrega i continuïtat real de combustible, humitat, vent i sequera operativa. Tampoc es disposa d'una avaluacio de camp postincendi sobre erosio, regeneracio, mortalitat o afectacio d'especies."),
        (MX + w + gap, 31 * mm, urban.CARD, "4. Decisio executiva", "Obrir una validacio focalitzada als sectors de concurrencia alta o mitjana-alta i als punts de contacte bosc-matollar accessibles. Qualsevol tractament ha de demostrar retorn ecologic, compatibilitat amb HIC i capacitat de manteniment. Si no hi ha erosio, fallida de regeneracio o risc funcional, la millor decisio pot ser observar i no sobreactuar."),
    ]
    for x, y, fill, title, text in cards:
        urban.rounded_card(c, x, y, w, 63 * mm, fill=fill)
        urban.draw_paragraph(c, f"<b>{title}</b>", x + 7 * mm, y + 56 * mm, w - 14 * mm, "card_title")
        urban.draw_paragraph(c, text, x + 7 * mm, y + 43 * mm, w - 14 * mm, "body_just")
    urban.rounded_card(c, MX, 20 * mm, CW, 7 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Criteri professional:</b> menys superficie, mes precisio, mes justificacio i seguiment explicit dels efectes ecologics.", MX + 6 * mm, 26 * mm, CW - 12 * mm, "source")
    c.showPage()


def postfire_evidence_page(c: canvas.Canvas, data: dict[str, Any], fire: dict[str, Any], biodiversity: dict[str, Any], page: int) -> None:
    header(c, "13", "Evidencia EcoRadar per a la gestio postincendi", "Habitats, biodiversitat, aigua, connectivitat i accessibilitat condicionen qualsevol actuacio", page)
    gap = 7 * mm
    w = (CW - gap) / 2
    h = 68 * mm
    cards = [
        (MX, 102 * mm, urban.PALE_GREEN, "Mosaic i habitats", f"L'ambit te {source.fmt(fire['study_ha'],0)} ha, {source.fmt(fire['forest_pct'],1,'%')} de coberta forestal i {source.fmt(fire['hic_ha'],0)} ha d'HIC. La prevencio ha de mantenir prats, vores i ecotons quan aportin discontinuïtat, pero ha d'evitar tractaments que simplifiquin habitats prioritaris o rodals de valor."),
        (MX + w + gap, 102 * mm, urban.PALE_BLUE, "Biodiversitat coneguda", f"Les bases publiques aporten {fire['biodiv_records']} registres i {fire['biodiv_species']} taxons. Hi consten {biodiversity['records']['Ocells']} registres d'ocells i {biodiversity['records']['Papallones i arnes']} de papallones i arnes, pero cap de ratpenat. Aquests registres orienten prospeccio; no certifiquen absencies ni resposta postfoc."),
        (MX, 27 * mm, colors.HexColor("#E8F3F1"), "Aigua i connectivitat", f"Hi ha {fire['fonts']} fonts registrades i {source.fmt(fire['connectors_ha'],0)} ha associades a capes de connectivitat. Fonts, drenatges, fondals i corredors poden actuar com refugis, eixos de recolonitzacio i punts sensibles a sediments. Les actuacions han de preservar continuïtat, ombra i qualitat hidrica."),
        (MX + w + gap, 27 * mm, urban.PALE_ORANGE, "Accessibilitat i pressio", f"La xarxa cartografiada suma {source.fmt(fire['paths_km'],1)} km i {fire['public_points']} punts d'us potencial. Els accessos faciliten vigilancia i gestio, pero tambe pertorbacio, erosio i ignicio. Cal distingir utilitat operativa de frequentacio real i ordenar els punts que coincideixen amb HIC, fauna o aigua."),
    ]
    for x, y, fill, title, text in cards:
        urban.rounded_card(c, x, y, w, h, fill=fill)
        urban.draw_paragraph(c, f"<b>{title}</b>", x + 7 * mm, y + h - 7 * mm, w - 14 * mm, "card_title")
        urban.draw_paragraph(c, text, x + 7 * mm, y + h - 21 * mm, w - 14 * mm, "body_just")
    urban.rounded_card(c, MX, 18 * mm, CW, 6 * mm, fill=urban.CARD)
    urban.draw_paragraph(c, "Cap variable decideix sola: la prioritat apareix quan risc estructural, acces, baixa afectacio ecologica i retorn del mosaic coincideixen.", MX + 6 * mm, 23 * mm, CW - 12 * mm, "source")
    c.showPage()


def postfire_decisions_page(c: canvas.Canvas, fire: dict[str, Any], page: int) -> None:
    header(c, "14", "Conclusions i decisions postincendi", "Decisions disponibles, validacions pendents i criteris per evitar la sobreactuacio", page)
    rows = [
        [urban.P("Variable", "table_bold"), urban.P("Diagnosi", "table_bold"), urban.P("Decisio justificada", "table_bold"), urban.P("Validacio necessaria", "table_bold")],
        [urban.P("Superficie cremada", "table"), urban.P("17,4 ha; afectacio oficial reduida", "table"), urban.P("No restauracio generalitzada", "table"), urban.P("Erosio, sol nu i regeneracio", "table")],
        [urban.P("Mosaic", "table"), urban.P("Funcional pero vulnerable al tancament", "table"), urban.P("Mantenir prats, vores i ecotons utils", "table"), urban.P("Funcio, gestio i compatibilitat HIC", "table")],
        [urban.P("Combustible", "table"), urban.P("Proxy territorial, no estructura real", "table"), urban.P("Prospeccio abans de tractar", "table"), urban.P("Carrega, continuïtat i humitat", "table")],
        [urban.P("Habitats", "table"), urban.P("Valor molt alt i HIC extensos", "table"), urban.P("Filtre de no-deteriorament", "table"), urban.P("Estat local i sensibilitat", "table")],
        [urban.P("Aigua", "table"), urban.P("Funcio parcialment coneguda", "table"), urban.P("Protegir punts i corredors", "table"), urban.P("Permanencia, qualitat i sediments", "table")],
        [urban.P("Accessos", "table"), urban.P("Pressio potencial i utilitat operativa", "table"), urban.P("Ordenar punts sensibles", "table"), urban.P("Frequentacio, erosio i conflictes", "table")],
    ]
    table = urban.make_table(rows, [39 * mm, 58 * mm, 75 * mm, CW - 172 * mm], font_size=6.9)
    urban.table_on_canvas(c, table, MX, 170 * mm)
    gap = 7 * mm
    w = (CW - 2 * gap) / 3
    actions = [
        ("1. Validar", urban.PALE_GREEN, "Visitar sectors de concurrencia elevada i punts afectats. Mesurar regeneracio, erosio, combustible, aigua, HIC i microhabitats abans de prescriure."),
        ("2. Actuar selectivament", urban.PALE_BLUE, "Intervenir nomes on el camp confirmi problema funcional i on el tractament millori mosaic o seguretat sense degradar habitats ni connectors."),
        ("3. Fer seguiment", urban.PALE_ORANGE, "Comparar fotografies, cobertura, regeneracio, erosio, humitat i resposta d'especies. Revisar la decisio si els indicadors no evolucionen com s'esperava."),
    ]
    for i, (title, fill, text) in enumerate(actions):
        x = MX + i * (w + gap)
        urban.rounded_card(c, x, 47 * mm, w, 55 * mm, fill=fill)
        urban.draw_paragraph(c, f"<b>{title}</b>", x + 7 * mm, 95 * mm, w - 14 * mm, "card_title")
        urban.draw_paragraph(c, text, x + 7 * mm, 82 * mm, w - 14 * mm, "body_small")
    urban.rounded_card(c, MX, 21 * mm, CW, 19 * mm, fill=urban.CARD)
    urban.draw_paragraph(c, "<b>Limit metodologic:</b> la diagnosi postincendi integra fonts oficials i indicadors EcoRadar, pero no substitueix un projecte executiu, una avaluacio de severitat ni mostreig de combustible, humitat, erosio, HIC i fauna. La decisio correcta pot ser actuar, esperar o no intervenir, segons el camp.", MX + 7 * mm, 35 * mm, CW - 14 * mm, "body_small")
    c.showPage()


def diagnosis_table(c: canvas.Canvas, data: dict[str, Any], page: int) -> None:
    header(c, "16", "Diagnosi integrada", "Evidencia, proces, consequencia i decisio de gestio", page)
    rows = [
        [urban.P("Afirmacio", "table_bold"), urban.P("Evidencia", "table_bold"), urban.P("Proces i consequencia", "table_bold"), urban.P("Decisio", "table_bold")],
        [urban.P("La matriu forestal absorbeix mosaic funcional.", "table"), urban.P(f"{source.fmt(value(data, 'percentatge_coberta_forestal'),1,'%')} forestal; {source.fmt(value(data,'percentatge_prats_pastures_herbassars'),1,'%')} obert.", "table"), urban.P("Tancament i perdua d'ecotons, recursos florals i discontinuïtats.", "table"), urban.P("Mantenir espais oberts seleccionats per funcio.", "table")],
        [urban.P("El valor es concentra en habitats sensibles.", "table"), urban.P(f"{source.fmt(value(data,'superficie_hic'),0)} ha HIC; {source.fmt(source.priority_habitat_surface(data['habitats']),0)} ha prioritaris.", "table"), urban.P("Una actuacio util en un sector pot ser perjudicial en un altre.", "table"), urban.P("Capa de prudencia i camp previ.", "table")],
        [urban.P("La vulnerabilitat es dinamica.", "table"), urban.P("NDVI, NDMI i LST disponibles; manca contrast temporal i de camp.", "table"), urban.P("Cobertura no equival a bon estat ni resiliencia.", "table"), urban.P("Usar les capes com a cribratge i validar la decisio al camp.", "table")],
        [urban.P("El foc depen del mateix sistema.", "table"), urban.P("2 perimetres oficials, 17,4 ha; matriu forestal dominant.", "table"), urban.P("Continuïtat, humitat, relleu i accessos condicionen comportament.", "table"), urban.P("Validar combustible i conservar discontinuïtats.", "table")],
        [urban.P("L'accessibilitat pot convertir valor en pressio.", "table"), urban.P("124,8 km de xarxa i 18 punts potencials.", "table"), urban.P("Concentracio local de pertorbacio sense mesura de frequentacio.", "table"), urban.P("Ordenar, comptar i adaptar la gestio.", "table")],
    ]
    table = urban.make_table(rows, [47 * mm, 52 * mm, 72 * mm, CW - 171 * mm], font_size=7)
    urban.table_on_canvas(c, table, MX, 172 * mm)
    urban.rounded_card(c, MX, 23 * mm, CW, 30 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Lectura conjunta.</b> Alinya no requereix una restauracio generalitzada. Requereix protegir els valors ja presents, governar el tancament del paisatge, entendre els punts d'aigua, ordenar l'accessibilitat i actuar nomes on el retorn ecologic sigui demostrable.", MX + 7 * mm, 46 * mm, CW - 14 * mm, "body")
    c.showPage()


def rewilding_decision_page(c: canvas.Canvas, page: int) -> None:
    header(c, "17", "Marc de decisio EUROPARC + rewilding", "Processos naturals, intervencio minima i gestio adaptativa", page)
    urban.rounded_card(c, MX, 149 * mm, CW, 27 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(
        c,
        "<b>Finalitat:</b> reforcar integritat ecologica, connectivitat, resiliencia i capacitat d'autoregulacio. La intervencio es un mitja temporal, no un objectiu: s'escull el nivell minim necessari i es revisa segons la resposta del sistema.",
        MX + 7 * mm, 168 * mm, CW - 14 * mm, "body",
    )
    steps = [
        ("1. Objectiu", urban.PALE_GREEN, "Definir l'objecte de conservacio o el proces i la trajectoria futura viable."),
        ("2. Diagnosi", urban.PALE_BLUE, "Separar estat, pressio demostrada, incertesa i escala territorial."),
        ("3. Opcio minima", urban.CARD, "Prioritzar proteccio, retirada de pressio i recuperacio espontania."),
        ("4. Resultat", urban.PALE_ORANGE, "Anticipar benefici, risc, responsable, recursos i termini."),
        ("5. Adaptacio", urban.CARD, "Mesurar, comparar amb referencia i corregir o aturar."),
    ]
    gap = 4 * mm
    w = (CW - 4 * gap) / 5
    for i, (title, fill, body) in enumerate(steps):
        x = MX + i * (w + gap)
        urban.rounded_card(c, x, 111 * mm, w, 31 * mm, fill=fill)
        urban.draw_paragraph(c, f"<b>{title}</b>", x + 5 * mm, 135 * mm, w - 10 * mm, "card_title")
        urban.draw_paragraph(c, body, x + 5 * mm, 124 * mm, w - 10 * mm, "body_small")

    rows = [
        [urban.P("Opcio", "table_bold"), urban.P("Condicio", "table_bold"), urban.P("Aplicacio a Alinya", "table_bold"), urban.P("Indicador o llindar", "table_bold")],
        [urban.P("A. Protegir / no intervenir", "table"), urban.P("Valors funcionals i sense pressio activa.", "table"), urban.P("HIC, refugis, obagues, tranquilitat i regeneracio; delimitacio final al camp.", "table"), urban.P("Estat d'habitat, aigua, regeneracio i especies indicadores.", "table")],
        [urban.P("B. Retirar pressio", "table"), urban.P("Recuperacio probable si desapareix la causa.", "table"), urban.P("Regular acces, trepig, soroll o alteracions hidriques abans de transformar.", "table"), urban.P("Trajectoria i termini de recuperacio definits.", "table")],
        [urban.P("C. Reactivar processos", "table"), urban.P("Manca connectivitat, herbivoria o dinamica natural.", "table"), urban.P("Permeabilitat, fusta morta, regeneracio i pastura extensiva compatible.", "table"), urban.P("Heterogeneitat sense erosio, sobrepastura ni deteriorament d'HIC.", "table")],
        [urban.P("D. Restauracio activa", "table"), urban.P("Barrera, invasora, erosio o fallida comprovada.", "table"), urban.P("Accio focal, reversible i experimental amb sector de referencia.", "table"), urban.P("Aturar si no millora el proces o apareixen efectes col·laterals.", "table")],
        [urban.P("E. Seguretat intensiva", "table"), urban.P("Exposicio, combustible i viabilitat verificats.", "table"), urban.P("Tractament de foc nomes on coincideixen risc funcional i baixa afectacio.", "table"), urban.P("Resultat postactuacio i capacitat real de manteniment.", "table")],
    ]
    table = urban.make_table(rows, [42 * mm, 50 * mm, 92 * mm, CW - 184 * mm], font_size=6.4)
    urban.table_on_canvas(c, table, MX, 103 * mm)
    urban.rounded_card(c, MX, 17 * mm, CW, 15 * mm, fill=urban.CARD)
    urban.draw_paragraph(
        c,
        "<b>Base:</b> EUROPARC-Espana 2018, PDF 29-32 (territori, successio, incertesa i gestio adaptativa); EUROPARC-Espana 2008, PDF 75-77 i 98 (cicle de planificacio i gradient no-intervencio/maneig); IUCN CEM 2025 i Carver et al. 2021 (processos autoregulats, connectivitat, context social i seguiment).",
        MX + 7 * mm, 28 * mm, CW - 14 * mm, "source",
    )
    c.showPage()


def actions_page(c: canvas.Canvas, data: dict[str, Any], page: int) -> None:
    header(c, "18", "Programa d'actuacio", "Prioritats derivades del marc de decisio", page)
    actions = [
        ("P1", urban.GREEN, "Referencia i no-intervencio", "0-6 mesos", "Delimitar candidats creuant HIC, refugis, aigua, tranquilitat i regeneracio; validar-los al camp.", "Linia base, objectiu de proces i llindar de revisio per sector."),
        ("P2", urban.ORANGE, "Restaurar mosaic i connectivitat", "0-18 mesos", "Retirar pressions i afavorir herbivoria compatible abans que desbrossament recurrent.", "Heterogeneitat, permeabilitat i qualitat sense deteriorament d'HIC."),
        ("P3", urban.BLUE, "Protegir processos hidrics", "0-12 mesos", "Classificar fonts, basses i trams ombrivols per permanencia, estat, fauna i pressions.", "Funcionalitat hidrica i resposta d'especies o microhabitats."),
        ("P4", urban.PURPLE, "Reduir pressio d'acces", "0-18 mesos", "Mesurar us real i regular abans d'augmentar infraestructura o capacitat de visita.", "Comptatges, incidencies i resposta abans/despres."),
        ("P5", urban.RED, "Foc: intervencio condicionada", "abans d'actuar", "Validar combustible, humitat fina, exposicio i manteniment; actuar nomes amb benefici net.", "Cap tractament basat nomes en indexs; efectes col·laterals mesurats."),
    ]
    y, h, gap = 150 * mm, 25 * mm, 4 * mm
    for code, color, title, horizon, action, indicator in actions:
        urban.rounded_card(c, MX, y, CW, h, fill=urban.CARD)
        c.setFillColor(color)
        c.circle(MX + 11 * mm, y + h / 2, 6.5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Arial-Bold", 8.5)
        c.drawCentredString(MX + 11 * mm, y + h / 2 - 2.8, code)
        c.setFillColor(urban.NAVY)
        c.setFont("Arial-Bold", 9.2)
        c.drawString(MX + 23 * mm, y + h - 8 * mm, urban.cat(title))
        c.setFillColor(color)
        c.setFont("Arial-Bold", 7.3)
        c.drawRightString(PAGE_W - MX - 6 * mm, y + h - 8 * mm, urban.cat(horizon))
        urban.draw_paragraph(c, action, MX + 23 * mm, y + h - 12 * mm, 112 * mm, "body_small")
        urban.draw_paragraph(c, f"<b>Indicador:</b> {indicator}", MX + 140 * mm, y + h - 12 * mm, CW - 146 * mm, "body_small")
        y -= h + gap
    urban.rounded_card(c, MX, 18 * mm, CW, 13 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Principi:</b> primer protegir o retirar pressions; despres reactivar processos; restauracio activa nomes si la recuperacio espontania no es viable o hi ha un risc funcional verificat.", MX + 7 * mm, 28 * mm, CW - 14 * mm, "body_small")
    c.showPage()


def monitoring_page(c: canvas.Canvas, page: int) -> None:
    header(c, "19", "Validacio i seguiment", "Protocol minim per convertir la diagnosi en gestio adaptativa", page)
    blocks = [
        ("A. Camp ecologic", urban.PALE_GREEN, ["Estat d'HIC i ecotons.", "Estructura forestal i fusta morta.", "Permanencia i qualitat de l'aigua.", "Especies indicadores i microhabitats.", "Pressions i conflictes reals."]),
        ("B. Series territorials", urban.PALE_BLUE, ["Cobertes i espais oberts.", "Vigor i humitat estival.", "Perimetres oficials de foc.", "Canvis d'accessibilitat.", "Actualitzacio de cartografia oficial."]),
        ("C. Governanca", urban.PALE_ORANGE, ["Responsable per indicador.", "Data i versio de cada font.", "Llindars acordats, no inventats.", "Registre d'actuacions.", "Revisio anual i postpertorbacio."]),
    ]
    gap = 7 * mm
    w = (CW - 2 * gap) / 3
    for i, (title, fill, bullets) in enumerate(blocks):
        x = MX + i * (w + gap)
        urban.rounded_card(c, x, 99 * mm, w, 74 * mm, fill=fill)
        urban.draw_paragraph(c, f"<b>{title}</b>", x + 7 * mm, 165 * mm, w - 14 * mm, "card_title")
        urban.draw_bullets(c, bullets, x + 7 * mm, 151 * mm, w - 14 * mm, "body_small")
    rows = [
        [urban.P("Indicador", "table_bold"), urban.P("Unitat", "table_bold"), urban.P("Periodicitat", "table_bold"), urban.P("Decisio que revisa", "table_bold")],
        [urban.P("Espais oberts funcionals", "table"), urban.P("ha + qualitat", "table"), urban.P("2-3 anys", "table"), urban.P("Manteniment de mosaic", "table")],
        [urban.P("Estat d'habitats sensibles", "table"), urban.P("classes / incidencies", "table"), urban.P("preactuacio", "table"), urban.P("No-deteriorament", "table")],
        [urban.P("Punts d'aigua funcionals", "table"), urban.P("nombre + estat", "table"), urban.P("estacional", "table"), urban.P("Conservacio i restauracio", "table")],
        [urban.P("Pressio real", "table"), urban.P("comptatges / incidencies", "table"), urban.P("temporada", "table"), urban.P("Ordenacio d'us public", "table")],
    ]
    table = urban.make_table(rows, [62 * mm, 40 * mm, 38 * mm, CW - 140 * mm], font_size=7)
    urban.table_on_canvas(c, table, MX, 90 * mm)
    c.showPage()


def sources_page(c: canvas.Canvas, page: int) -> None:
    header(c, "20", "Fonts, limitacions i criteris d'us", "Traçabilitat del producte i prudencia de les conclusions", page)
    gap = 8 * mm
    w = (CW - gap) / 2
    urban.rounded_card(c, MX, 42 * mm, w, 132 * mm, fill=urban.CARD)
    urban.draw_paragraph(c, "<b>Fonts incorporades</b>", MX + 7 * mm, 166 * mm, w - 14 * mm, "card_title")
    refs = [
        "<b>D1.</b> Area d'estudi validada: GeoPackage del projecte, EPSG:25831.",
        "<b>D2.</b> ICGC: Cobertes del sol de Catalunya i model d'elevacions.",
        "<b>D3.</b> Generalitat de Catalunya: habitats terrestres v3 i camps HIC disponibles.",
        "<b>D4.</b> ACA: xarxa hidrografica, drenatge i fonts.",
        "<b>D5.</b> Generalitat: Infraestructura Verda i connectivitat ecologica.",
        "<b>D6.</b> GBIF i iNaturalist: registres publics normalitzats dins l'ambit.",
        "<b>D7.</b> OpenStreetMap/Overpass: xarxa i punts d'us public potencial.",
        "<b>D8.</b> Generalitat: superficies afectades per incendis forestals.",
        "<b>D9.</b> Metadades, informes de validacio i indicadors del projecte Alinya.",
        "<b>D10.</b> EcoRadar: potencial relatiu de refugi climatic derivat de LST, NDMI i NDVI; xarxa hidrica oficial com a context.",
        "<b>M1.</b> EUROPARC-Espana 2018: adaptacio, processos i gestio adaptativa; PDF 29-32.",
        "<b>M2.</b> EUROPARC-Espana 2008: cicle de planificacio i zonificacio; PDF 75-77 i 98.",
        "<b>M3.</b> IUCN CEM 2025 i Carver et al. 2021: directrius i principis de rewilding.",
    ]
    y = 151 * mm
    for ref in refs:
        y -= urban.draw_paragraph(c, ref, MX + 7 * mm, y, w - 14 * mm, "ref") + 3 * mm
    rx = MX + w + gap
    urban.rounded_card(c, rx, 42 * mm, w, 132 * mm, fill=urban.CARD)
    urban.draw_paragraph(c, "<b>Limitacions que afecten decisions</b>", rx + 7 * mm, 166 * mm, w - 14 * mm, "card_title")
    urban.draw_bullets(c, [
        "La cartografia d'habitats no substitueix l'estat de conservacio observat al camp.",
        "GBIF i iNaturalist no permeten afirmar absencies ni equivalen a un cens complet.",
        "OSM descriu accessibilitat potencial, no intensitat real de visitants.",
        "NDVI, NDMI i LST aporten context territorial; la humitat fina, l'estructura vertical i la carrega real de combustible encara requereixen camp.",
        "La capa de similitud postfoc es una concurrencia territorial relativa, no una prediccio.",
        "Les recomanacions son de diagnosi; qualsevol obra o tractament requereix projecte, permisos i validacio especifica.",
    ], rx + 7 * mm, 151 * mm, w - 14 * mm, "body_small", urban.ORANGE)
    urban.rounded_card(c, rx, 53 * mm, w, 34 * mm, fill=urban.PALE_GREEN)
    urban.draw_paragraph(c, "<b>Estat de publicacio:</b> APTE. Validacio tecnica i de recomanacions superada; validacio ecologica superada amb limitacions explicites.", rx + 7 * mm, 79 * mm, w - 14 * mm, "body_small")
    c.showPage()


def build_body(path: Path, data: dict[str, Any]) -> None:
    if not source.phase2_methodology(data):
        raise RuntimeError(
            "L'informe d'Alinyà requereix una instantània Fase 2 vàlida; "
            "s'ha bloquejat l'exportació amb la metodologia CORE 0–100 antiga."
        )
    # The Phase 2 CORE contract has no common 0–100 scale. Reuse the compact
    # project report so the legacy score-based body cannot be rendered.
    source.build_report(path, data, include_all_pages=True)
    return
    urban.register_fonts()
    urban.build_styles()
    biodiversity = biodiversity_breakdown()
    fire = postfire_export.source_data()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=landscape(A4), pageCompression=1)
    c.setTitle("EcoRadar - Informe complet de la Muntanya d'Alinya")
    c.setAuthor("EcoRadar")
    c.setSubject("Diagnosi ecologica integrada amb document postincendi")
    c.setKeywords("EcoRadar, Alinya, habitats, biodiversitat, connectivitat, foc, gestio")
    cover(c, data)
    executive(c, data, 2)
    framework(c, 3)
    method(c, data, 4)
    evidence_page(c, 5, "4", "Cartografia integrada", "Una base territorial comuna per llegir totes les decisions", [
        (source.fmt(data["study"].get("surface_ha"), 0), "Ha d'ambit", "Limit validat", urban.NAVY),
        ("47", "Habitats", "Unitats cartografiades", urban.GREEN),
        ("15", "Elements d'aigua", "Fonts oficials", urban.BLUE),
        ("55", "Entitats de connectivitat", "Capes oficials retallades", urban.PURPLE),
    ], "espai", "La mateixa base espacial ha de governar conservacio, restauracio, acces, aigua i foc; les decisions sectorials s'han de llegir sobre un territori compartit.", "Separar capes per departaments pot ocultar conflictes i sinergies. Un mateix sector pot sostenir un HIC, funcionar com a corredor, contenir un punt d'aigua i ser accessible des d'una pista. La superposicio no dona una resposta automatica, pero obliga a explicitar que es protegeix, quin proces es vol millorar i quins efectes col·laterals s'han d'evitar.", ["Usar un unic limit i CRS en tots els projectes.", "Creuar cada actuacio amb habitats, aigua, corredors i accessos.", "Documentar escala, data i versio abans de comparar resultats."], "Els mapes orienten prioritats; la delimitacio fina i l'estat real exigeixen comprovacio local.")
    evidence_page(c, 6, "5", "Mosaic, bosc i espais oberts", "Tancament del paisatge i perdua potencial de funcio", [
        (source.fmt(value(data,"percentatge_coberta_forestal"),1,"%"), "Forestal", "Matriu dominant", urban.GREEN),
        (source.fmt(value(data,"percentatge_prats_pastures_herbassars"),1,"%"), "Prats/herbassars", "Peces escasses", urban.ORANGE),
        (score(data,"CORE_01"), "Mosaic", "Puntuacio Radar /100", urban.NAVY),
        (score(data,"CORE_08"), "Connectivitat", "Puntuacio Radar /100", urban.PURPLE),
    ], "paisatge", "Els espais oberts han passat de ser superficie marginal a infraestructura ecologica: sostenen ecotons, aliment, campeig i discontinuïtat del combustible.", "El problema no es l'extensio del bosc per si mateixa, sino la perdua de contrast quan prats, herbassars i vores deixen de funcionar. Aquests ambients aporten recursos florals per a pol·linitzadors, zones de cacera per a ocells i ratpenats, i espais de pastura o gestio que poden mantenir discontinuïtats. Cal distingir espais oberts actius, abandonats, naturals o degradats abans d'assignar tractament.", ["Mantenir una xarxa connectada de prats, vores i ecotons.", "Evitar obertures generals: prioritzar funcio i retorn ecologic.", "Contrastar us, propietat, manteniment i estat abans d'actuar."], "SIGPAC/DUN i la gestio agraria real no estan incorporats; la causa i velocitat del tancament s'han de validar.")
    evidence_page(c, 7, "6", "Habitats i zones sensibles", "Responsabilitat de conservacio i filtre de no-deteriorament", [
        (str(value(data,"nombre_habitats")), "Habitats", "Diversitat cartografiada", urban.GREEN),
        (source.fmt(value(data,"superficie_hic"),0), "Ha d'HIC", "Interes comunitari", urban.NAVY),
        (source.fmt(source.priority_habitat_surface(data["habitats"]),0), "Ha prioritaries", "Prudencia maxima", urban.RED),
        (score(data,"CORE_02"), "Valor d'habitats", "Puntuacio Radar /100", urban.PURPLE),
    ], "habitats", "El valor ecologic es concentra en habitats sensibles, ecotons i punts de baixa pertorbacio; aquests elements han de condicionar el disseny abans que l'obra.", "La coexistencia de 47 habitats i una superficie extensa d'HIC obliga a gestio diferenciada. Una desbrossada pot recuperar un prat o eliminar estructura protectora; un cami pot ordenar l'us o fragmentar una zona sensible. La cartografia identifica responsabilitat potencial, pero el camp ha de comprovar composicio, estructura, pressions, representativitat i correspondencia entre el poligon i la realitat.", ["Aplicar HIC i HIC prioritaris com a filtre de prudencia.", "Validar els poligons que coincideixen amb actuacions o accessos.", "Definir objectiu ecologic, risc i indicador abans d'intervenir."], "La presencia cartografica no informa per si sola de qualitat, tendencia ni estat local de conservacio.")
    biodiversity_page(c, data, biodiversity, 8)
    evidence_page(c, 9, "8", "Aigua, vegetacio i refugis climatics", "Funcions dinamiques encara condicionades per dades i camp", [
        (source.fmt(hydrology_km(data),1), "Km hidrografics", "Cursos i drenatges", urban.BLUE),
        (str(source.row_value(data["hydrology"],"layer_id","fonts","feature_count") or "12"), "Fonts", "Registre oficial", urban.GREEN),
        (score(data,"CORE_04"), "Refugis", "Puntuacio Radar /100", urban.PURPLE),
        (score(data,"CORE_10"), "Aigua", "Puntuacio Radar /100", urban.NAVY),
    ], "refugis_climatics", "Punts d'aigua, obagues i trams ombrivols poden sostenir refugis desproporcionadament importants durant sequera, calor o recuperacio postpertorbacio.", "El mapa identifica potencial relatiu allà on coincideixen superfícies més fresques, vegetació relativament més humida i vigor espectral. La xarxa hídrica i les fonts s'hi mostren com a context funcional. En un espai mediterrani de muntanya, aquestes coincidències poden concentrar amfibis, invertebrats, abeurada de mamífers, vegetació higròfila i corredors de moviment; la cartografia orienta la prospecció, però no certifica el refugi.", ["Inventariar permanencia, qualitat, pressions i us faunistic.", "Protegir candidats coincidents amb HIC, corredors i baixa pertorbacio.", "Contrastar el potencial amb series temporals i microclima de camp."], "L'índex combina 50% frescor LST, 30% NDMI i 20% NDVI sobre vegetació amb NDVI >= 0,30. La LST és una composició de dos estius i Sentinel-2 una escena; no equivalen a temperatura de l'aire, normal climàtica ni refugi validat.")
    evidence_page(c, 10, "9", "Foc i resiliencia territorial", "Continuïtat, mosaic, humitat i accessos", [
        ("2", "Perimetres oficials", "Dins l'ambit", urban.RED),
        ("17,4", "Ha cremades", "Superficie oficial", urban.ORANGE),
        (score(data,"CORE_09"), "Resiliencia foc", "Puntuacio Radar /100", urban.NAVY),
        (source.fmt(value(data,"percentatge_coberta_forestal"),1,"%"), "Forestal", "Continuïtat potencial", urban.GREEN),
    ], "paisatge", "El foc es una expressio del mateix sistema de continuïtat, humitat, relleu, accessibilitat i mosaic; no es pot interpretar com un modul aillat.", "Els perimetres historics dins l'ambit son reduits, pero permeten examinar configuracions territorials reals. La prevencio ecologica no consisteix a reduir vegetacio de forma uniforme: ha de conservar discontinuïtats que tambe aporten habitat, evitar impactes sobre HIC i verificar carrega, estructura, humitat i possibilitat de manteniment. Una franja sense manteniment o mal situada pot perdre eficacia i generar cost ecologic.", ["Mantenir discontinuïtats que tinguin funcio ecologica demostrable.", "Usar la similitud per dirigir camp, mai com a prediccio.", "Validar combustible, acces, erosio i habitats abans de tractar."], "L'index integrat es una lectura territorial estructural; la carrega i humitat fina del combustible i la meteorologia operativa requereixen dades de camp i serveis oficials en temps real.")
    postfire_memory_page(c, data, fire, 11)
    postfire_territory_page(c, data, fire, 12)
    postfire_argument_page(c, fire, 13)
    postfire_evidence_page(c, data, fire, biodiversity, 14)
    postfire_decisions_page(c, fire, 15)
    evidence_page(c, 16, "15", "Pressió humana i connectivitat", "Accessibilitat potencial, tranquil·litat i governança", [
        (source.fmt(source.pressure_metric(data["pressure"],"osm_path_track_road_km"),1), "Km de xarxa", "Camins, pistes i vials", urban.ORANGE),
        (source.fmt(source.pressure_metric(data["pressure"],"osm_path_track_road_density"),2), "Km/km2", "Densitat cartografica", urban.RED),
        (str(value(data,"nombre_accessos_punts_us_public")), "Punts d'us", "Potencials", urban.BLUE),
        (score(data,"CORE_08"), "Connectivitat", "Puntuacio Radar /100", urban.GREEN),
    ], "pressio_humana", "L'accessibilitat pot convertir valor ecologic en pressio si no s'ordena, pero tambe es una infraestructura necessaria per a gestio, vigilancia i emergencia.", "Una xarxa extensa no implica automaticament impacte: el resultat depen de frequentacio, temporada, tipus d'us, soroll, gossos, erosio i proximitat a punts sensibles. Els 18 punts detectats son localitzadors de pressio potencial. Cal contrastar-los amb HIC, aigua, rapinyaires, refugis i corredors per decidir on informar, limitar, desviar o mantenir tranquil·litat.", ["Mesurar intensitat, activitat i temporalitat als punts sensibles.", "Ordenar i senyalitzar accessos abans d'ampliar capacitat.", "Mantenir corredors, refugis i zones de baixa pertorbacio."], "OSM no mesura visitants, soroll, gossos, erosio, estacionalitat ni resposta de fauna.")
    diagnosis_table(c, data, 17)
    rewilding_decision_page(c, 18)
    actions_page(c, data, 19)
    monitoring_page(c, 20)
    sources_page(c, 21)
    c.save()


def merge_documents(body: Path, fitxa: Path, output: Path) -> None:
    writer = PdfWriter()
    body_reader = PdfReader(str(body))
    fitxa_reader = PdfReader(str(fitxa))
    for page in body_reader.pages:
        writer.add_page(page)
    for page in fitxa_reader.pages:
        writer.add_page(page)
    writer.add_metadata({
        "/Title": "EcoRadar - Informe complet de la Muntanya d'Alinya",
        "/Author": "EcoRadar",
        "/Subject": "Diagnosi ecologica integrada amb la Fitxa EcoRadar Fase 2",
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", type=Path, default=DEFAULT_BODY)
    parser.add_argument("--fitxa", type=Path, default=DEFAULT_FITXA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source.configure_project(PROJECT)
    data = source.prepare_inputs()
    build_body(args.body, data)
    merge_documents(args.body, args.fitxa, args.output)
    OUTPUT_COPY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_COPY.write_bytes(args.output.read_bytes())
    print(args.output)


if __name__ == "__main__":
    main()
