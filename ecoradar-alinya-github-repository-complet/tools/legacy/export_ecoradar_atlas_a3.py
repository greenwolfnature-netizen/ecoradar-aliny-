"""Generate an A3 editorial EcoRadar diagnosis atlas for Alinya.

The atlas is a product-facing diagnostic document. Each module is designed to
stand alone for management use and only uses already prepared real outputs.
Missing inputs are explicitly labelled as not available; no synthetic values are
created.
"""

from __future__ import annotations

import csv
import html
import json
import shutil
import sys
from dataclasses import dataclass
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
PROJECT = ROOT / "projectes" / "Alinya"
REPORTS = PROJECT / "reports"
MODULES_DIR = REPORTS / "modules"
INDICATORS = PROJECT / "indicators"
METADATA = PROJECT / "metadata"
MAPS_DIR = PROJECT / "maps" / "producte"
OUTPUT = ROOT / "output" / "pdf"

ATLAS_PDF = REPORTS / "atlas_diagnosi_ecoradar_alinya_a3.pdf"
MODULES_PDF = MODULES_DIR / "moduls_diagnosi_ecoradar_alinya_a3.pdf"
OUTPUT_ATLAS_PDF = OUTPUT / "atlas_diagnosi_ecoradar_alinya_a3.pdf"
ATLAS_METADATA = METADATA / "ecoradar_atlas_a3_metadata.json"

GREEN_DARK = colors.HexColor("#0E3B30")
GREEN = colors.HexColor("#1D654E")
GREEN_MID = colors.HexColor("#5D9067")
GREEN_SOFT = colors.HexColor("#DCEBDD")
SAND = colors.HexColor("#F2F0E5")
CREAM = colors.HexColor("#FBFAF3")
LINE = colors.HexColor("#C9D2CB")
TEXT = colors.HexColor("#152A23")
MUTED = colors.HexColor("#66756E")
ORANGE = colors.HexColor("#D06D32")
BLUE = colors.HexColor("#2E7FA7")
RED = colors.HexColor("#B84635")
GRAY = colors.HexColor("#929E98")

NO_DATA = "No disponible"


@dataclass(frozen=True)
class Metric:
    label: str
    value: str
    unit: str = ""
    note: str = ""
    max_value: float | None = None


@dataclass(frozen=True)
class Module:
    number: int
    title: str
    objective: str
    executive_summary: str
    map_title: str
    map_key: str
    metrics: tuple[Metric, ...]
    interpretation: str
    management: tuple[str, ...]
    recommendations: tuple[str, ...]
    confidence: str
    status: str
    sources: tuple[str, ...]
    updated_at: str


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def clean(text: str) -> str:
    return html.escape(text).replace("·", "-")


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"no disponible", "none", "nan"}:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def fmt(value: Any, decimals: int = 1, suffix: str = "") -> str:
    number = as_float(value)
    if number is None:
        return NO_DATA
    text = f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text}{suffix}"


def metric_value(rows: list[dict[str, str]], key: str) -> str:
    for row in rows:
        if row.get("indicador") == key:
            return row.get("valor", "")
    return ""


def pressure_value(rows: list[dict[str, str]], key: str) -> str:
    for row in rows:
        if row.get("indicator") == key:
            return row.get("value", "")
    return ""


def core_value(rows: list[dict[str, str]], code: str, key: str = "normalized_value") -> str:
    for row in rows:
        if row.get("code") == code:
            return row.get(key, "")
    return ""


def date_from_metadata(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)[:10]
    return NO_DATA


def draw_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y_top: float,
    width: float,
    style: ParagraphStyle,
) -> float:
    paragraph = Paragraph(clean(text), style)
    _, height = paragraph.wrap(width, 2000)
    paragraph.drawOn(c, x, y_top - height)
    return height


def draw_card(c: canvas.Canvas, x: float, y: float, w: float, h: float, fill=CREAM, stroke=LINE) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.55)
    c.roundRect(x, y, w, h, 3.5, fill=1, stroke=1)


def confidence_color(confidence: str):
    lower = confidence.lower()
    if lower.startswith("alt"):
        return GREEN_MID
    if lower.startswith("mit"):
        return BLUE
    return ORANGE


def draw_badge(c: canvas.Canvas, x: float, y: float, w: float, text: str, fill) -> None:
    c.setFillColor(fill)
    c.roundRect(x, y, w, 8 * mm, 4, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + w / 2, y + 2.7 * mm, text)


def draw_metric_card(c: canvas.Canvas, metric: Metric, x: float, y: float, w: float, h: float) -> None:
    unavailable = metric.value == NO_DATA or not metric.value
    draw_card(c, x, y, w, h, fill=colors.HexColor("#F7F8F2") if unavailable else GREEN_SOFT)
    c.setFillColor(GRAY if unavailable else TEXT)
    c.setFont("Helvetica-Bold", 16 if len(metric.value) < 12 else 12)
    c.drawString(x + 6 * mm, y + h - 11 * mm, metric.value or NO_DATA)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    if metric.unit:
        c.drawString(x + 6 * mm, y + h - 17 * mm, metric.unit)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 7.7)
    c.drawString(x + 6 * mm, y + 8 * mm, metric.label)
    if metric.note:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawString(x + 6 * mm, y + 3.7 * mm, metric.note[:58])


def draw_metric_bars(c: canvas.Canvas, metrics: tuple[Metric, ...], x: float, y_top: float, w: float) -> float:
    y = y_top
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(TEXT)
    c.drawString(x, y, "Lectura ràpida")
    y -= 7 * mm
    for metric in metrics:
        value = as_float(metric.value)
        max_value = metric.max_value
        c.setFont("Helvetica", 7)
        c.setFillColor(TEXT)
        c.drawString(x, y + 1.5 * mm, metric.label[:32])
        c.setFillColor(colors.HexColor("#E3E9E3"))
        c.roundRect(x + 42 * mm, y, w - 64 * mm, 4 * mm, 2, fill=1, stroke=0)
        if value is not None and max_value:
            ratio = max(0, min(1, value / max_value))
            c.setFillColor(GREEN_MID if ratio >= 0.5 else ORANGE)
            c.roundRect(x + 42 * mm, y, (w - 64 * mm) * ratio, 4 * mm, 2, fill=1, stroke=0)
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 7)
        c.drawRightString(x + w, y + 0.5 * mm, metric.value or NO_DATA)
        y -= 7 * mm
    return y


def draw_sources(c: canvas.Canvas, sources: tuple[str, ...], updated_at: str, x: float, y: float, w: float) -> None:
    source_style = ParagraphStyle("source", fontName="Helvetica", fontSize=6.6, leading=8.1, textColor=MUTED)
    draw_card(c, x, y, w, 27 * mm, fill=colors.HexColor("#F7F7EF"))
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawString(x + 5 * mm, y + 21 * mm, "Fonts i actualització")
    source_text = "; ".join(sources) if sources else NO_DATA
    draw_text(c, f"Fonts: {source_text}", x + 5 * mm, y + 18 * mm, w - 10 * mm, source_style)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.6)
    c.drawString(x + 5 * mm, y + 4 * mm, f"Data d'actualització: {updated_at}")


def build_context() -> dict[str, Any]:
    return {
        "basic": read_csv(INDICATORS / "ecoradar_01_resum.csv"),
        "core": read_csv(INDICATORS / "ecoradar_core.csv"),
        "habitats": read_csv(INDICATORS / "habitats_resum.csv"),
        "biodiv": read_csv(INDICATORS / "biodiversitat_resum.csv"),
        "pressure": read_csv(INDICATORS / "recreational_pressure_resum.csv"),
        "metadata": {
            "study": read_json(METADATA / "study_area_metadata.json"),
            "cover": read_json(METADATA / "cobertes_sol_metadata.json"),
            "habitats": read_json(METADATA / "habitats_metadata.json"),
            "biodiv": read_json(METADATA / "biodiversitat_metadata.json"),
            "pressure": read_json(METADATA / "recreational_pressure_metadata.json"),
            "tele": read_json(METADATA / "teledeteccio_metadata.json"),
            "core": read_json(METADATA / "ecoradar_core_metadata.json"),
        },
    }


def no_data_metric(label: str) -> Metric:
    return Metric(label, NO_DATA, "", "Dada no incorporada")


def build_modules(context: dict[str, Any]) -> list[Module]:
    basic = context["basic"]
    core = context["core"]
    habitats = context["habitats"]
    biodiv = context["biodiv"]
    pressure = context["pressure"]
    meta = context["metadata"]

    total_ha = as_float(metric_value(basic, "superficie_total")) or 0
    hic_ha = as_float(metric_value(basic, "superficie_hic")) or 0
    hic_pct = (hic_ha / total_ha * 100) if total_ha else None
    priority_ha = sum(
        as_float(row.get("superficie_ha")) or 0
        for row in habitats
        if str(row.get("es_prioritari", "")).lower() == "true"
    )
    priority_pct = (priority_ha / total_ha * 100) if total_ha else None
    top_groups = ", ".join(row.get("grup_taxonomic", "") for row in biodiv[:3])

    study_date = date_from_metadata(meta["study"], "created_at")
    cover_date = date_from_metadata(meta["cover"], "data_consulta")
    habitat_date = date_from_metadata(meta["habitats"], "query_date")
    biodiv_date = date_from_metadata(meta["biodiv"], "query_date")
    pressure_date = date_from_metadata(meta["pressure"], "date_consulted")
    tele_date = date_from_metadata(meta["tele"], "query_date")
    core_date = date_from_metadata(meta["core"], "generated_at")

    return [
        Module(
            1,
            "Biodiversitat",
            "Identificar la biodiversitat coneguda, els biaixos d'informació i les necessitats de validació de camp.",
            "Les dades públiques mostren una base notable de cites i espècies, però no equivalen a un inventari complet. La lectura és útil per orientar camp i detectar grups poc representats.",
            "Distribució de registres públics dins l'àrea d'estudi",
            "biodiversitat",
            (
                Metric("Espècies citades", fmt(metric_value(basic, "nombre_especies_registrades"), 0), "taxons", max_value=600),
                Metric("Registres totals", fmt(metric_value(basic, "nombre_registres_biodiversitat"), 0), "cites", max_value=900),
                Metric("Registres recents", fmt(metric_value(basic, "nombre_registres_recents"), 0), "cites", max_value=900),
                Metric("Grups principals", top_groups, "", "per nombre de registres"),
            ),
            "Una concentració alta de registres no implica necessàriament més valor ecològic: també pot reflectir accessibilitat i esforç d'observació. Els grups menys observats han de guiar el mostreig.",
            (
                "No deduir absència d'espècies en zones sense cites.",
                "Validar espècies sensibles i cites antigues abans de prendre decisions.",
                "Planificar camp per grups infrarepresentats i zones poc mostrejades.",
            ),
            ("Monitoritzar", "Ampliar dades", "Validar al camp"),
            "Mitjà",
            "Parcial",
            ("GBIF", "iNaturalist"),
            biodiv_date,
        ),
        Module(
            2,
            "Hàbitats",
            "Delimitar el valor de conservació dels hàbitats i les zones que condicionen qualsevol actuació.",
            "Alinyà presenta una superfície important d'hàbitats d'interès i una diversitat elevada d'unitats d'hàbitat. Aquest mòdul és una de les bases més sòlides de la diagnosi actual.",
            "Hàbitats d'interès comunitari i prioritaris",
            "habitats",
            (
                Metric("Hàbitats detectats", fmt(metric_value(basic, "nombre_habitats"), 0), "tipus", max_value=60),
                Metric("Superfície HIC", fmt(hic_ha, 0), "ha", max_value=total_ha),
                Metric("% HIC", fmt(hic_pct, 1, "%"), "sobre l'àrea", max_value=100),
                Metric("HIC prioritaris", fmt(priority_ha, 0), f"{fmt(priority_pct, 1, '%')} de l'àrea", max_value=total_ha),
            ),
            "Els hàbitats d'interès han de funcionar com a capa de prudència. Les actuacions de gestió només haurien de definir-se després de creuar-les amb aquests valors.",
            (
                "Evitar actuacions homogènies en zones amb HIC prioritaris.",
                "Diferenciar conservació estricta, millora i restauració.",
                "Validar localment hàbitats sensibles i estat de conservació.",
            ),
            ("Conservar", "Validar", "Monitoritzar"),
            "Mitjà",
            "Parcial",
            ("Cartografia dels hàbitats terrestres v3", "HIC v2"),
            habitat_date,
        ),
        Module(
            3,
            "Paisatge i connectivitat",
            "Interpretar el mosaic de cobertes i la capacitat del paisatge per mantenir connexions ecològiques.",
            "La matriu forestal domina clarament, amb espais oberts minoritaris però estratègics. Aquesta estructura pot afavorir continuïtat, però exigeix llegir el mosaic amb detall.",
            "Cobertes del sòl i estructura general del mosaic",
            "paisatge",
            (
                Metric("Coberta forestal", fmt(metric_value(basic, "percentatge_coberta_forestal"), 1, "%"), "", max_value=100),
                Metric("Prats i herbassars", fmt(metric_value(basic, "percentatge_prats_pastures_herbassars"), 1, "%"), "", max_value=30),
                Metric("Agrícola", fmt(metric_value(basic, "percentatge_agricola"), 2, "%"), "", max_value=10),
                Metric("Tipus de cobertes", fmt(metric_value(basic, "nombre_tipus_cobertes"), 0), "classes", max_value=20),
            ),
            "El valor de la connectivitat no depèn només de tenir molta coberta natural. També depèn de la mida, posició i funcionalitat dels espais oberts, riberes i discontinuïtats.",
            (
                "Conservar espais oberts que estructuren mosaic.",
                "Incorporar barreres i riberes abans de definir corredors.",
                "Evitar simplificar el paisatge amb actuacions uniformes.",
            ),
            ("Mantenir mosaic", "Ampliar dades", "Monitoritzar"),
            "Mitjà",
            "Parcial",
            ("ICGC Cobertes del sòl", "EcoRadar Core"),
            cover_date,
        ),
        Module(
            4,
            "Pressió humana",
            "Avaluar accessibilitat, punts d'ús públic i possibles zones de concentració d'activitat.",
            "La diagnosi actual mesura infraestructura d'accés cartografiada, no visitants. És una base útil per interpretar pressió potencial, però no intensitat real d'ús.",
            "Xarxa de camins, pistes i punts d'ús públic cartografiats",
            "pressio",
            (
                Metric("Xarxa cartografiada", fmt(pressure_value(pressure, "osm_path_track_road_km"), 1), "km", max_value=180),
                Metric("Densitat de camins", fmt(pressure_value(pressure, "osm_path_track_road_density"), 2), "km/km2", max_value=5),
                Metric("Punts d'ús públic", fmt(pressure_value(pressure, "osm_recreational_point_features"), 0), "punts", max_value=40),
                Metric("Valor EcoRadar", fmt(core_value(core, "CORE_07"), 1), "0-100", max_value=100),
            ),
            "Les zones amb més accessibilitat poden concentrar pertorbacions, però cal contrastar-les amb freqüentació real, estacionalitat i sensibilitat de fauna.",
            (
                "Validar accessos, aparcaments i camins principals.",
                "Creuar ús públic amb hàbitats i espècies sensibles.",
                "Afegir comptadors o dades de gestors abans de regular fluxos.",
            ),
            ("Monitoritzar", "Ampliar dades", "Reduir pressió si es confirma"),
            "Baix",
            "Parcial",
            ("OpenStreetMap", "Overpass API"),
            pressure_date,
        ),
        Module(
            5,
            "Recursos hídrics",
            "Determinar el paper de cursos, fonts, basses i zones humides en la funcionalitat ecològica.",
            "La diagnosi hídrica encara no és calculable amb les capes disponibles. Aquest mòdul es manté com a pàgina de decisió perquè l'aigua és crítica per fauna, refugis i restauració.",
            "Àrea d'estudi i context territorial",
            "base",
            (
                no_data_metric("Cursos fluvials"),
                no_data_metric("Fonts i basses"),
                no_data_metric("Zones humides"),
                no_data_metric("Funcionalitat hídrica"),
            ),
            "Sense hidrografia fina i punts d'aigua verificats no es poden delimitar corredors hídrics, refugis associats a aigua ni prioritats de restauració hidrològica.",
            (
                "Incorporar fonts oficials d'hidrografia i punts d'aigua.",
                "Validar fonts, basses i surgències sobre el terreny.",
                "Creuar l'aigua amb fauna, ombra i refugis climàtics.",
            ),
            ("Ampliar dades", "Validar al camp", "Monitoritzar"),
            "Baix",
            "No disponible",
            ("Font hidrològica oficial pendent d'incorporació",),
            core_date,
        ),
        Module(
            6,
            "Boscos i estructura forestal",
            "Llegir la massa forestal, els espais oberts i la resiliència estructural del territori.",
            "La coberta forestal és molt dominant. Això reforça la necessitat d'analitzar continuïtat, discontinuïtats, humitat i accessibilitat abans de proposar gestió forestal.",
            "Cobertes forestals i espais oberts",
            "paisatge",
            (
                Metric("Coberta forestal", fmt(metric_value(basic, "percentatge_coberta_forestal"), 1, "%"), "", max_value=100),
                Metric("Espais oberts", fmt(metric_value(basic, "percentatge_prats_pastures_herbassars"), 1, "%"), "", max_value=30),
                Metric("Agrícola", fmt(metric_value(basic, "percentatge_agricola"), 2, "%"), "", max_value=10),
                Metric("Resiliència al foc", fmt(core_value(core, "CORE_09"), 1), "0-100", max_value=100),
            ),
            "El repte no és reduir coberta forestal de forma genèrica, sinó detectar on el mosaic pot augmentar resiliència sense perjudicar hàbitats o espècies sensibles.",
            (
                "No planificar actuacions sense creuar hàbitats d'interès.",
                "Identificar espais oberts amb funció ecològica i de discontinuïtat.",
                "Afegir pendent, orientació, humitat i punts d'aigua.",
            ),
            ("Mantenir mosaic", "Ampliar dades", "Conservar"),
            "Baix",
            "Parcial",
            ("ICGC Cobertes del sòl", "EcoRadar Core"),
            cover_date,
        ),
        Module(
            7,
            "Història ecològica",
            "Incorporar memòria de pertorbacions, recuperació de vegetació i recurrència d'incendis.",
            "La història ecològica encara no disposa de sèries i perímetres verificats dins la diagnosi actual. No es fan inferències de recuperació sense dades temporals.",
            "Àrea d'estudi per contextualitzar futures sèries temporals",
            "base",
            (
                no_data_metric("Incendis històrics"),
                no_data_metric("Últim incendi"),
                no_data_metric("Evolució NDVI"),
                no_data_metric("Recurrència"),
            ),
            "Sense dades temporals no es pot distingir recuperació de coberta, recuperació de qualitat ecològica ni recurrència de pertorbacions.",
            (
                "Incorporar perímetres oficials d'incendi quan la font estigui verificada.",
                "Afegir sèries de vegetació per llegir recuperació real.",
                "Creuar recurrència amb hàbitats sensibles.",
            ),
            ("Ampliar dades", "Monitoritzar", "Validar"),
            "Baix",
            "No disponible",
            ("Font oficial d'incendis pendent d'incorporació", "Copernicus/Sentinel pendent"),
            core_date,
        ),
        Module(
            8,
            "Tranquil·litat ecològica",
            "Identificar zones potencialment tranquil·les i possibles conflictes entre ús públic i biodiversitat.",
            "La xarxa d'accessos permet una primera lectura de pressió potencial, però la tranquil·litat real depèn de freqüentació, horaris, estacionalitat i sensibilitat ecològica.",
            "Accessibilitat potencial i punts d'ús públic",
            "pressio",
            (
                Metric("Densitat d'accessos", fmt(pressure_value(pressure, "osm_path_track_road_density"), 2), "km/km2", max_value=5),
                Metric("Punts d'ús públic", fmt(pressure_value(pressure, "osm_recreational_point_features"), 0), "punts", max_value=40),
                Metric("Xarxa cartografiada", fmt(pressure_value(pressure, "osm_path_track_road_km"), 1), "km", max_value=180),
                no_data_metric("Intensitat real d'ús"),
            ),
            "La tranquil·litat no pot derivar-se només de distància a camins. Cal combinar accessibilitat amb intensitat i sensibilitat d'espècies.",
            (
                "Evitar promoure zones sensibles sense dades d'ús real.",
                "Definir àrees de baixa pertorbació quan hi hagi fauna sensible.",
                "Afegir camp i dades temporals d'ús públic.",
            ),
            ("Monitoritzar", "Ampliar dades", "Reduir pressió si es confirma"),
            "Baix",
            "Parcial",
            ("OpenStreetMap", "Dades de biodiversitat públiques"),
            pressure_date,
        ),
        Module(
            9,
            "Vulnerabilitat i canvi climàtic",
            "Detectar estrès climàtic, refugis potencials i zones prioritàries d'adaptació.",
            "La diagnosi climàtica encara és incompleta: hi ha senyals indirectes de coberta, però falten teledetecció, temperatura, humitat i orientació.",
            "Àrea d'estudi per contextualitzar futures capes climàtiques",
            "base",
            (
                Metric("Coberta forestal", fmt(metric_value(basic, "percentatge_coberta_forestal"), 1, "%"), "", max_value=100),
                Metric("Coberta artificial", fmt(metric_value(basic, "percentatge_urba_artificial"), 2, "%"), "", max_value=10),
                no_data_metric("NDMI / humitat"),
                no_data_metric("LST / temperatura"),
            ),
            "La cobertura forestal pot indicar potencial de refugi, però no permet delimitar refugis climàtics sense temperatura, humitat, orientació i aigua.",
            (
                "No zonificar refugis climàtics només amb coberta forestal.",
                "Prioritzar Copernicus/Sentinel i DEM.",
                "Creuar vulnerabilitat amb hàbitats i restauració.",
            ),
            ("Ampliar dades", "Conservar", "Restaurar quan es delimiti"),
            "Baix",
            "Parcial",
            ("ICGC Cobertes del sòl", "Copernicus pendent de credencials"),
            tele_date,
        ),
        Module(
            10,
            "Prioritats de gestió",
            "Transformar la diagnosi en decisions prudents, traçables i compatibles amb conservació.",
            "Encara no és rigorós generar un rànquing final de zones. Sí que es poden establir prioritats de procés: protegir valors coneguts, validar pressions i completar capes crítiques.",
            "Mapa integrat de cobertes i accessibilitat",
            "espai",
            (
                Metric("Hàbitats d'interès", fmt(hic_ha, 0), "ha", max_value=total_ha),
                Metric("Biodiversitat coneguda", fmt(core_value(core, "CORE_06"), 1), "0-100", max_value=100),
                Metric("Pressió potencial", fmt(core_value(core, "CORE_07"), 1), "0-100", max_value=100),
                Metric("Resiliència al foc", fmt(core_value(core, "CORE_09"), 1), "0-100", max_value=100),
            ),
            "Les prioritats actuals han de ser metodològiques i prudents: conservar el valor ja identificat i completar dades abans de proposar actuacions espacials finals.",
            (
                "Revisar HIC i hàbitats prioritaris abans de qualsevol actuació.",
                "Validar espais oberts, accessos i punts d'ús públic.",
                "Completar clima, aigua i foc abans de zonificar actuacions.",
            ),
            ("Conservar", "Ampliar dades", "Validar al camp"),
            "Baix",
            "Parcial",
            ("EcoRadar Core", "Cobertes", "Hàbitats", "Biodiversitat", "OSM"),
            core_date,
        ),
        Module(
            11,
            "Coneixement disponible i buits",
            "Separar el que ja es pot interpretar del que cal completar abans de decidir.",
            "EcoRadar disposa d'una base sòlida per cobertes, hàbitats, biodiversitat pública i accessibilitat OSM. Encara falten capes crítiques per clima, aigua, foc i camp.",
            "Capes actuals sobre l'àrea d'estudi",
            "espai",
            (
                Metric("Cobertes", fmt(metric_value(basic, "nombre_tipus_cobertes"), 0), "classes", max_value=20),
                Metric("Hàbitats", fmt(metric_value(basic, "nombre_habitats"), 0), "tipus", max_value=60),
                Metric("Espècies citades", fmt(metric_value(basic, "nombre_especies_registrades"), 0), "taxons", max_value=600),
                Metric("Xarxa d'accés", fmt(pressure_value(pressure, "osm_path_track_road_km"), 1), "km", max_value=180),
            ),
            "La confiança és desigual: bona per valors generals, baixa per processos que requereixen sèries, camp o capes encara no incorporades.",
            (
                "Mostrar sempre confiança i fonts al costat dels resultats.",
                "Convertir cada buit en una tasca d'obtenció o validació.",
                "Evitar conclusions espacials fortes quan faltin capes base.",
            ),
            ("Ampliar dades", "Validar", "Monitoritzar"),
            "Mitjà",
            "Parcial",
            ("EcoRadar 0.1", "EcoRadar Core"),
            core_date,
        ),
        Module(
            12,
            "Recomanacions de gestió",
            "Sintetitzar accions preliminars sense convertir dades parcials en ordres d'actuació.",
            "Les recomanacions són de fase inicial: conservar els valors coneguts, completar capes crítiques i preparar validació de camp orientada a decisions.",
            "Mapa integrat per orientar la següent fase",
            "espai",
            (
                Metric("Hàbitats d'interès", fmt(hic_ha, 0), "ha", max_value=total_ha),
                Metric("Prats i herbassars", fmt(metric_value(basic, "percentatge_prats_pastures_herbassars"), 1, "%"), "", max_value=30),
                Metric("Xarxa d'accés", fmt(pressure_value(pressure, "osm_path_track_road_km"), 1), "km", max_value=180),
                Metric("Espècies citades", fmt(metric_value(basic, "nombre_especies_registrades"), 0), "taxons", max_value=600),
            ),
            "La millor recomanació ara és no sobreactuar. Cal passar de diagnosi inicial a diagnosi operativa amb camp, clima, aigua i foc abans de definir actuacions finals.",
            (
                "Conservar hàbitats d'interès i espais oberts rellevants.",
                "Monitoritzar accessos i zones d'ús públic.",
                "Completar dades ambientals abans de prioritzar inversions.",
            ),
            ("Conservar", "Monitoritzar", "Ampliar dades"),
            "Mitjà",
            "Parcial",
            ("EcoRadar Core", "Fonts públiques processades"),
            core_date,
        ),
    ]


def draw_header(c: canvas.Canvas, module: Module, page_w: float, page_h: float, margin: float) -> None:
    header_h = 30 * mm
    c.setFillColor(GREEN_DARK)
    c.roundRect(margin, page_h - margin - header_h, page_w * 0.58, header_h, 4, fill=1, stroke=0)
    c.setStrokeColor(colors.white)
    c.setLineWidth(0.8)
    c.circle(margin + 14 * mm, page_h - margin - header_h / 2, 9.5 * mm, fill=0, stroke=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(margin + 14 * mm, page_h - margin - header_h / 2 - 5, str(module.number))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin + 31 * mm, page_h - margin - 12 * mm, module.title)
    c.setFont("Helvetica", 9.7)
    c.drawString(margin + 31 * mm, page_h - margin - 22 * mm, "Mòdul de diagnosi ecològica - lectura autònoma per a gestió")

    meta_x = margin + page_w * 0.58 + 5 * mm
    meta_w = page_w - meta_x - margin
    draw_card(c, meta_x, page_h - margin - header_h, meta_w, header_h)
    style = ParagraphStyle("header_meta", fontName="Helvetica", fontSize=7.8, leading=9.8, textColor=TEXT)
    draw_text(c, module.objective, meta_x + 6 * mm, page_h - margin - 6 * mm, meta_w - 12 * mm, style)
    draw_badge(c, meta_x + meta_w - 63 * mm, page_h - margin - header_h + 5 * mm, 29 * mm, module.status, GRAY if module.status == "No disponible" else GREEN_MID)
    draw_badge(c, meta_x + meta_w - 31 * mm, page_h - margin - header_h + 5 * mm, 26 * mm, module.confidence, confidence_color(module.confidence))


def draw_module_page(c: canvas.Canvas, module: Module, maps: dict[str, Path], total_modules: int) -> None:
    page_w, page_h = landscape(A3)
    margin = 12 * mm
    c.setFillColor(SAND)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    draw_header(c, module, page_w, page_h, margin)

    body = ParagraphStyle("body", fontName="Helvetica", fontSize=8.4, leading=10.6, textColor=TEXT)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=7.0, leading=8.5, textColor=MUTED)
    title = ParagraphStyle("panel_title", fontName="Helvetica-Bold", fontSize=10.2, leading=12, textColor=GREEN_DARK)
    white = ParagraphStyle("white", fontName="Helvetica", fontSize=7.4, leading=9.0, textColor=colors.white)

    top = page_h - margin - 35 * mm
    bottom = margin + 9 * mm
    left_x = margin
    map_x = margin + 78 * mm
    right_x = page_w - margin - 88 * mm
    left_w = 72 * mm
    map_w = right_x - map_x - 5 * mm
    right_w = 88 * mm

    # Left column: executive summary and indicators.
    draw_card(c, left_x, top - 78 * mm, left_w, 78 * mm)
    draw_text(c, "Resum executiu", left_x + 6 * mm, top - 6 * mm, left_w - 12 * mm, title)
    draw_text(c, module.executive_summary, left_x + 6 * mm, top - 19 * mm, left_w - 12 * mm, body)

    metrics_y = top - 83 * mm
    metric_h = 22 * mm
    draw_text(c, "Indicadors", left_x, metrics_y - 1 * mm, left_w, title)
    y = metrics_y - 27 * mm
    for metric in module.metrics:
        draw_metric_card(c, metric, left_x, y, left_w, metric_h)
        y -= metric_h + 4 * mm

    # Center: large map and compact chart.
    map_h = 173 * mm
    draw_card(c, map_x, top - map_h, map_w, map_h)
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(map_x + 6 * mm, top - 9 * mm, module.map_title)
    image_path = maps.get(module.map_key, maps["base"])
    c.drawImage(str(image_path), map_x + 6 * mm, top - map_h + 9 * mm, width=map_w - 12 * mm, height=map_h - 23 * mm, preserveAspectRatio=True, anchor="c")

    chart_y = top - map_h - 7 * mm
    draw_card(c, map_x, bottom, map_w, chart_y - bottom)
    draw_metric_bars(c, module.metrics, map_x + 7 * mm, chart_y - 8 * mm, map_w - 14 * mm)

    # Right column: interpretation, management, recommendations.
    draw_card(c, right_x, top - 62 * mm, right_w, 62 * mm)
    draw_text(c, "Interpretació ecològica", right_x + 6 * mm, top - 6 * mm, right_w - 12 * mm, title)
    draw_text(c, module.interpretation, right_x + 6 * mm, top - 20 * mm, right_w - 12 * mm, body)

    manage_h = 62 * mm
    manage_y = top - 68 * mm - manage_h
    draw_card(c, right_x, manage_y, right_w, manage_h)
    draw_text(c, "Implicacions per a la gestió", right_x + 6 * mm, manage_y + manage_h - 6 * mm, right_w - 12 * mm, title)
    y2 = manage_y + manage_h - 22 * mm
    for item in module.management:
        c.setFillColor(GREEN_MID)
        c.circle(right_x + 8 * mm, y2 - 2.2 * mm, 1.7 * mm, fill=1, stroke=0)
        used = draw_text(c, item, right_x + 12 * mm, y2 + 1.5 * mm, right_w - 18 * mm, small)
        y2 -= used + 4.5 * mm

    rec_h = 42 * mm
    rec_y = manage_y - 5 * mm - rec_h
    c.setFillColor(GREEN_DARK)
    c.roundRect(right_x, rec_y, right_w, rec_h, 3.5, fill=1, stroke=0)
    draw_text(c, "Recomanacions", right_x + 6 * mm, rec_y + rec_h - 6 * mm, right_w - 12 * mm, ParagraphStyle("rec_title", fontName="Helvetica-Bold", fontSize=10.2, leading=12, textColor=colors.white))
    chip_x = right_x + 6 * mm
    chip_y = rec_y + 17 * mm
    for rec in module.recommendations:
        chip_w = max(24 * mm, min(44 * mm, (len(rec) * 2.3 + 12) * mm / 3))
        c.setFillColor(colors.HexColor("#E7F0E8"))
        c.roundRect(chip_x, chip_y, chip_w, 8 * mm, 4, fill=1, stroke=0)
        c.setFillColor(GREEN_DARK)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(chip_x + chip_w / 2, chip_y + 2.7 * mm, rec)
        chip_x += chip_w + 3 * mm
        if chip_x > right_x + right_w - 34 * mm:
            chip_x = right_x + 6 * mm
            chip_y -= 10 * mm

    draw_sources(c, module.sources, module.updated_at, right_x, bottom, right_w)

    c.setFillColor(GREEN_DARK)
    c.rect(0, 0, page_w, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7.3)
    c.drawString(margin, 2.9 * mm, "ECORADAR - Diagnosi ecològica professional - Alinyà")
    c.drawRightString(page_w - margin, 2.9 * mm, f"Mòdul {module.number} de {total_modules} - A3 horitzontal")


def atlas_pdf(context: dict[str, Any], maps: dict[str, Path]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    modules = build_modules(context)
    page_size = landscape(A3)
    c = canvas.Canvas(str(MODULES_PDF), pagesize=page_size)
    c.setTitle("EcoRadar Alinya - Atles A3 de moduls de diagnosi")
    c.setAuthor("EcoRadar")
    for module in modules:
        draw_module_page(c, module, maps, len(modules))
        c.showPage()
    c.save()

    # The atlas currently equals the module pack; keeping both paths supports a
    # future executive front matter without changing downstream references.
    writer = PdfWriter()
    reader = PdfReader(str(MODULES_PDF))
    for page in reader.pages:
        writer.add_page(page)
    with ATLAS_PDF.open("wb") as handle:
        writer.write(handle)
    shutil.copy2(ATLAS_PDF, OUTPUT_ATLAS_PDF)


def write_metadata(context: dict[str, Any], maps: dict[str, Path]) -> None:
    modules = build_modules(context)
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "project": "Alinyà",
        "format": "A3 landscape",
        "outputs": {
            "atlas_pdf": str(ATLAS_PDF.relative_to(ROOT)),
            "modules_pdf": str(MODULES_PDF.relative_to(ROOT)),
            "output_copy": str(OUTPUT_ATLAS_PDF.relative_to(ROOT)),
        },
        "module_count": len(modules),
        "modules": [
            {
                "number": module.number,
                "title": module.title,
                "status": module.status,
                "confidence": module.confidence,
                "updated_at": module.updated_at,
                "sources": module.sources,
            }
            for module in modules
        ],
        "map_outputs": {key: str(path.relative_to(ROOT)) for key, path in maps.items()},
        "data_policy": "No synthetic values. Missing source data are displayed as 'No disponible'.",
    }
    ATLAS_METADATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    from export_ecoradar_product import render_maps

    context = build_context()
    maps = render_maps()
    atlas_pdf(context, maps)
    write_metadata(context, maps)


if __name__ == "__main__":
    main()
