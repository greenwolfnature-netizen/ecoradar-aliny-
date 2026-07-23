"""Render the standalone and inline EcoRadar Urba map from processed data."""

from __future__ import annotations

import base64
import html
import json
import os
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon, box, mapping
from shapely.geometry.polygon import orient


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
PROCESSED = PROJECT / "processed"
MAPS = PROJECT / "maps"
METADATA = PROJECT / "metadata"
INDICATORS = PROJECT / "indicators"
VIS_DIR = Path(os.getenv("ECORADAR_VIS_DIR", str(MAPS / "preview")))
VIS_FILE = VIS_DIR / "ecoradar-la-seu-urba.html"


def main() -> None:
    manifest = json.loads((METADATA / "layer_manifest.json").read_text())
    demography = json.loads((INDICATORS / "demography_idescat.json").read_text())
    expanded_path = INDICATORS / "expanded_scope_indicators.json"
    expanded = json.loads(expanded_path.read_text()) if expanded_path.exists() else None
    expanded_scope = expanded is not None
    study_bbox = (
        expanded["study_bbox_epsg4326"]
        if expanded_scope
        else manifest["analysis_core_bbox_epsg4326"]
    )
    solar_summary = json.loads(
        (
            INDICATORS
            / (
                "solar_roof_screening_expanded_summary.json"
                if expanded_scope
                else "solar_roof_screening_summary.json"
            )
        ).read_text()
    )
    extended = json.loads(
        (INDICATORS / "extended_urban_indicators.json").read_text()
    )
    extended_metrics = extended["metrics"]
    sentinel_path = INDICATORS / (
        "sentinel2_expanded_indicators.json"
        if expanded_scope
        else "sentinel2_urban_indicators.json"
    )
    sentinel = json.loads(sentinel_path.read_text()) if sentinel_path.exists() else None
    sentinel_expanded = sentinel_path.name == "sentinel2_expanded_indicators.json"
    context_path = INDICATORS / "contextual_environment.json"
    context = json.loads(context_path.read_text()) if context_path.exists() else None
    fire_path = METADATA / "fire_danger_structural_2024.json"
    fire = json.loads(fire_path.read_text()) if fire_path.exists() else None
    current_fire_path = INDICATORS / "current_fire_danger.json"
    current_fire_cells_path = MAPS / "current_fire_danger_cells.geojson"
    current_fire = json.loads(current_fire_path.read_text()) if current_fire_path.exists() else None
    current_fire_cells = json.loads(current_fire_cells_path.read_text()) if current_fire_cells_path.exists() else None
    daily_path = INDICATORS / "daily_readings.json"
    daily = json.loads(daily_path.read_text()) if daily_path.exists() else None
    daily_history_path = INDICATORS / "daily_history.json"
    daily_history = json.loads(daily_history_path.read_text()) if daily_history_path.exists() else None
    biodiversity_path = METADATA / "biodiversity_urban_potential.json"
    biodiversity = json.loads(biodiversity_path.read_text())

    raster_data = {
        "shade": _data_url(
            MAPS / ("expanded_lidar_shade_web.png" if expanded_scope else "lidar_shade.png")
        ),
        "canopy": _data_url(
            MAPS / ("expanded_lidar_canopy_web.png" if expanded_scope else "lidar_canopy.png")
        ),
        "slope": _data_url(
            MAPS
            / (
                "expanded_lidar_slope_web.png"
                if expanded_scope
                else "lidar_slope.png"
            )
        ),
        "lst": _data_url(
            MAPS / ("expanded_landsat_lst_web.png" if expanded_scope else "landsat_lst.png")
        ),
        "flood": _data_url(
            MAPS / "snczi_q100_expanded.png"
            if expanded_scope
            else PROJECT / "raw" / "inundabilitat" / "snczi_q100_la_seu_bbox.png"
        ),
        "uhi": _data_url(MAPS / ("expanded_surface_uhi_proxy_web.png" if expanded_scope else "surface_uhi_proxy.png")),
        "impervious": _data_url(MAPS / ("expanded_copernicus_imperviousness_2021_web.png" if expanded_scope else "copernicus_imperviousness_2021.png")),
        "vegetation": _data_url(MAPS / ("expanded_copernicus_vegetation_cover_2023_web.png" if expanded_scope else "copernicus_vegetation_cover_2023.png")),
        "treeChange": _data_url(MAPS / ("expanded_copernicus_tree_change_2018_2023_web.png" if expanded_scope else "copernicus_tree_change_2018_2023.png")),
        "runoff": _data_url(MAPS / ("expanded_runoff_potential_proxy_web.png" if expanded_scope else "runoff_potential_proxy.png")),
        "biodiversity": _data_url(MAPS / "biodiversity_urban_potential.webp"),
        "biodiversityGreen": _data_url(MAPS / "biodiversity_green_corridor.png"),
        "biodiversityFluvial": _data_url(MAPS / "biodiversity_fluvial_corridor.png"),
        "biodiversityIsolated": _data_url(MAPS / "biodiversity_isolated_green.png"),
        "biodiversityBarrier": _data_url(MAPS / "biodiversity_structural_barrier.png"),
        "biodiversityPriority": _data_url(MAPS / "biodiversity_field_priority.png"),
    }
    biodiversity_metrics = biodiversity["metrics"]
    biodiversity_mode = (
        '<button class="eu-mode" data-mode="biodiversity" aria-pressed="false">'
        'Biodiversitat urbana<small>potencial · seguiments locals</small></button>'
    )
    biodiversity_details = (
        '<details class="eu-biodiversity" id="eu-biodiversity-details" hidden>'
        '<summary>Consultar detalls de biodiversitat urbana</summary><div class="eu-biodiversity-body">'
        '<div><h4>Resum del bloc</h4><div class="eu-bio-summary">'
        '<div><span><strong>Papallones</strong><small>Seguiment local CBMS</small></span><b class="eu-bio-badge observed">Dada observada</b></div>'
        '<div><span><strong>Ratpenats</strong><small>Caixes refugi</small></span><b class="eu-bio-badge infrastructure">Infraestructura de seguiment</b></div>'
        '<div><span><strong>Ocells</strong><small>Observacions locals</small></span><b class="eu-bio-badge pending">Pendent d’integració</b></div>'
        '<div><span><strong>Potencial ecològic</strong><small>Model territorial</small></span><b class="eu-bio-badge potential">Potencial calculat</b></div>'
        '</div></div>'
        '<div><h4>Papallones <b class="eu-bio-badge observed">Dada observada</b></h4>'
        '<div class="eu-bio-data"><div class="wide"><span>Itinerari</span><strong>CBMS 168 – Pla de les Forques</strong></div>'
        '<div class="wide"><span>Municipi</span><strong>la Seu d’Urgell</strong></div><div><span>Període</span><strong>2011–2025</strong></div>'
        '<div><span>Anys amb dades</span><strong>15</strong></div><div><span>Longitud</span><strong>1.400 m</strong></div><div><span>Seccions</span><strong>12</strong></div>'
        '<div><span>Espècies registrades</span><strong>81</strong></div><div><span>Mitjana anual d’espècies</span><strong>35</strong></div>'
        '<div><span>Exemplars comptats</span><strong>5.873</strong></div><div><span>Mitjana anual d’exemplars</span><strong>392</strong></div>'
        '<div><span>Mostrejos efectuats</span><strong>188</strong></div></div>'
        '<p>Sèrie local de seguiment continuada des de 2011. Són dades observades, no potencial calculat.</p>'
        '<p><strong>Nota:</strong> Aquestes dades corresponen a l’itinerari del Pla de les Forques i no representen automàticament tot el nucli urbà.</p></div>'
        '<div><h4>Ratpenats <b class="eu-bio-badge infrastructure">Infraestructura de seguiment</b></h4>'
        '<p><strong>5 caixes refugi actives</strong>, instal·lades sobre arbres i de cinc models Schwegler diferents. Cada caixa disposa de dues revisions registrades.</p>'
        '<p class="eu-bio-names">la Seu A-seu1 · la Seu A-seu2 · la Seu A-seu3 · la Seu A-seu4 · la Seu A-seu5</p>'
        '<p>En les dades públiques consultades consten <strong>0 espècies registrades</strong>. Això no demostra absència de ratpenats.</p>'
        '<p><strong>Interpretació:</strong> Hi ha infraestructura local de seguiment, però les dades públiques disponibles no confirmen ocupació ni permeten valorar la diversitat de ratpenats.</p>'
        '<p>Representació pública agregada, sense coordenades detallades i sense tractar les caixes com a observacions de fauna.</p></div>'
        '<div><h4>Ocells <b class="eu-bio-badge pending">Pendent d’integració</b></h4>'
        '<p><strong>Observacions disponibles — pendent d’integració quantitativa.</strong> Existeixen observacions ornitològiques locals disponibles, especialment associades al nucli urbà i al corredor fluvial del Segre.</p>'
        '<p>El riu Segre i els espais verds connectats constitueixen àmbits prioritaris per analitzar la biodiversitat d’ocells urbans i fluvials.</p>'
        '<p>No es mostren totals, tendències, abundàncies ni llistes completes d’espècies.</p></div>'
        '<div><h4>Potencial general de biodiversitat</h4><p>'
        f'Índex relatiu mitjà: <strong>{_ca(biodiversity_metrics["potential_mean_0_100"], 1)}/100</strong>. '
        'Combina vegetació, arbrat, continuïtat verda, proximitat a l’aigua i permeabilitat, amb un 20 % de pes cadascun. <b class="eu-bio-badge potential">Potencial calculat</b></p></div>'
        '<div><h4>Connectivitat ecològica</h4><p>Es diferencien corredors verds i fluvials potencials, espais vegetats potencialment aïllats i barreres urbanes estructurals. La barrera lumínica no es cartografia perquè no hi ha cap capa local incorporada.</p></div>'
        '<div><h4>Zones prioritàries de validació de camp</h4><p>'
        f'El tramat violeta assenyala les <strong>{_ca(biodiversity_metrics["high_potential_area_ha"], 1)} ha</strong> del quartil superior del potencial calculat. No hi ha observacions biològiques superposades: tota prioritat és una hipòtesi per comprovar al camp.</p></div>'
        '<div><h4>Divulgació i participació</h4><p>Nit dels Ratpenats · passejada amb detector d’ultrasons · itinerari de papallones · cens de pol·linitzadors · ciència ciutadana.</p></div>'
        '<div><h4>Fonts</h4><p>Catalan Butterfly Monitoring Scheme — itinerari 168, Pla de les Forques.<br>Programa de Seguiment de Ratpenats — caixes refugi de la Seu d’Urgell.<br>Ornitho / Institut Català d’Ornitologia — observacions locals d’ocells.</p></div>'
        '</div></details>'
    )
    fire_mode = ""
    fire_facts = ""
    if fire:
        raster_data["fireDanger"] = _data_url(
            MAPS / (
                "expanded_fire_danger_structural_2024_web.png"
                if expanded_scope
                else "fire_danger_structural_2024.png"
            )
        )
        fire_stats = fire["statistics"]
        fire_mode = (
            '<button class="eu-mode" data-mode="fireDanger" aria-pressed="false">'
            'Perill d’incendi<small>estructural · Generalitat 2024</small></button>'
        )
        fire_facts = (
            '<section class="eu-panel eu-warning"><h3>Perill estructural d’incendi · 2024</h3>'
            '<div class="eu-facts">'
            f'<div class="eu-fact"><span>Nivell modal forestal</span><strong>{fire_stats["mode"]}/10</strong></div>'
            f'<div class="eu-fact"><span>Màxim dins l’àmbit</span><strong>{fire_stats["maximum"]}/10</strong></div>'
            f'<div class="eu-fact"><span>Superfície forestal avaluada</span><strong>{fire_stats["valid_forest_area_ha"]} ha</strong></div>'
            f'<div class="eu-fact"><span>Cel·les en nivells 8–10</span><strong>{_ca(fire_stats["cells_8_to_10_pct"], 1)} %</strong></div>'
            '</div><p class="eu-source">Mapa bàsic oficial a 100 m i escala relativa 1–10. '
            'No és el perill diari, una probabilitat d’ignició ni una alerta d’emergència.</p></section>'
        )
    current_fire_mode = ""
    current_fire_facts = ""
    if current_fire and current_fire_cells:
        raster_data["fireCurrent"] = _data_url(MAPS / "current_fire_danger.png")
        summary = current_fire["summary"]
        variable_names = {
            "structural": "Perill estructural",
            "ndmi_dryness": "NDMI / sequedat",
            "surface_temperature": "Temperatura superficial",
            "vegetation_continuity": "Coberta i continuïtat",
            "wind": "Vent",
            "relative_humidity_inverse": "Humitat relativa",
            "slope": "Pendent",
            "aspect": "Orientació",
        }
        rows = []
        for key, item in current_fire["variables_today"].items():
            date = _human_utc(item["date_utc"])
            rows.append(
                '<tr>'
                f'<th>{variable_names[key]}</th><td>{item["value"].replace(".", ",")}</td>'
                f'<td>{item["source"]}<small>{date}</small></td>'
                f'<td>{item["quality"]}<small>{item["weight_pct"]} % · {item["update_status"]}</small></td>'
                '</tr>'
            )
        weather = current_fire["weather"]
        gust = weather.get("daily_max_wind_gust_ms")
        humidity_min = weather.get("daily_min_relative_humidity_pct")
        wind_direction = weather.get("wind_direction_deg", {}).get("value")
        weather_details = []
        if gust is not None:
            weather_details.append(f'ratxa màxima del dia {_ca(float(gust) * 3.6, 1)} km/h')
        if wind_direction is not None:
            weather_details.append(f'direcció més recent {_ca(float(wind_direction), 0)}°')
        if humidity_min is not None:
            weather_details.append(f'humitat mínima del dia {_ca(float(humidity_min), 0)} %')
        weight_lines = ''.join(
            f'<li><span>{variable_names[key]}</span><strong>{int(round(value * 100))} %</strong></li>'
            for key, value in current_fire["weights"].items()
        )
        area_lines = ''.join(
            f'<span>{name}: <strong>{_ca(value, 1)} ha</strong></span>'
            for name, value in summary["area_by_category_ha"].items()
        )
        current_fire_mode = (
            '<button class="eu-mode" data-mode="fireCurrent" aria-pressed="false">'
            f'Perill d’incendi actual<small data-live-check-meta>reserva · {_human_utc(current_fire.get("checked_at_utc") or summary["latest_update_utc"])}</small></button>'
        )
        current_fire_facts = (
            '<section class="eu-panel eu-fire-current" data-current-fire hidden><h3>1. Perill d’incendi actual</h3>'
            '<div class="eu-fire-summary">'
            f'<div><span>Índex mitjà</span><strong data-fire-summary="mean">{_ca(summary["mean_index_0_100"], 1)}/100</strong></div>'
            f'<div><span>Nivell predominant</span><strong data-fire-summary="category">{summary["predominant_category"]}</strong></div>'
            f'<div><span>Màxim</span><strong data-fire-summary="maximum">{_ca(summary["maximum_index_0_100"], 1)} · {summary["maximum_category"]}</strong></div>'
            f'<div><span>Molt alt o extrem</span><strong data-fire-summary="very-high">{_ca(summary["very_high_or_extreme_area_pct"], 1)} %</strong></div>'
            f'<div><span>Confiança</span><strong data-fire-summary="confidence">{summary["confidence"]} · {_ca(summary["confidence_pct"], 1)} %</strong></div>'
            '</div><div class="eu-fire-area">' + area_lines + '</div>'
            f'<p><strong>Factors dominants:</strong> {", ".join(summary["dominant_labels"])}.</p>'
            f'<p class="eu-source">Darrera observació dinàmica: {_human_utc(summary["latest_update_utc"])}. '
            + ' · '.join(weather_details)
            + '.</p><p class="eu-source"><strong>No és una alerta oficial</strong> i no substitueix el Pla Alfa ni els mapes diaris oficials.</p></section>'
            '<section class="eu-panel eu-fire-current" data-current-fire hidden><h3>2. Variables utilitzades avui</h3>'
            '<div class="eu-fire-table-wrap"><table class="eu-fire-table"><thead><tr><th>Variable</th><th>Valor</th><th>Font i data</th><th>Qualitat i pes</th></tr></thead><tbody>'
            + ''.join(rows)
            + '</tbody></table></div><p class="eu-source">Els valors espacials són resums de l’àmbit; fes clic en una cel·la per consultar-ne els valors reals i les contribucions.</p></section>'
            '<section class="eu-panel eu-fire-current" data-current-fire hidden><h3>3. Com es calcula l’índex</h3>'
            '<p>Totes les variables es normalitzen a 0–100. NDMI baix i humitat relativa baixa s’inverteixen. LST i NDMI usen P5–P95 reals de la capa; vent i humitat, P5–P95 dels darrers 35 dies XEMA.</p>'
            '<ul class="eu-fire-weights">' + weight_lines + '</ul>'
            '<p class="eu-source">Si falta una variable no es converteix en zero: es renormalitzen els pesos disponibles i la cel·la queda marcada com a incompleta. Graella de 100 m; la meteorologia és una observació puntual de Bellestar, no una malla urbana.</p></section>'
        )
    sentinel_modes = ""
    sentinel_facts = ""
    if sentinel:
        sentinel_suffix = "_expanded" if sentinel_expanded else ""
        raster_data.update(
            ndvi=_data_url(MAPS / f"sentinel2_ndvi{sentinel_suffix}.webp"),
            ndmi=_data_url(MAPS / f"sentinel2_ndmi{sentinel_suffix}.webp"),
            albedo=_data_url(MAPS / f"sentinel2_albedo{sentinel_suffix}.webp"),
        )
        acquisition_date = sentinel["acquired_at_utc"][:10].split("-")
        acquisition_label = ".".join(reversed(acquisition_date))
        sentinel_modes = (
            f'<button class="eu-mode" data-mode="ndvi" aria-pressed="false">NDVI<small>Sentinel-2 · {acquisition_label}</small></button>'
            f'<button class="eu-mode" data-mode="ndmi" aria-pressed="false">NDMI<small>Sentinel-2 · {acquisition_label}</small></button>'
            f'<button class="eu-mode" data-mode="albedo" aria-pressed="false">Albedo<small>Sentinel-2 · estimació</small></button>'
        )
        sentinel_facts = (
            '<section class="eu-panel"><h3>Indicadors Sentinel-2 L2A</h3><div class="eu-facts">'
            f'<div class="eu-fact"><span>NDVI mediana</span><strong>{_ca(sentinel["metrics"]["ndvi"]["median"], 3)}</strong></div>'
            f'<div class="eu-fact"><span>NDMI mediana</span><strong>{_ca(sentinel["metrics"]["ndmi"]["median"], 3)}</strong></div>'
            f'<div class="eu-fact"><span>Albedo estimat · mediana</span><strong>{_ca(sentinel["metrics"]["albedo"]["median"], 3)}</strong></div>'
            '</div><p class="eu-source">Escena única amb màscara SCL. NDMI no és humitat volumètrica del sòl i l’albedo és una conversió espectral publicada.</p></section>'
        )
    contextual_facts = ""
    if context:
        context_rows = []
        context_notes = []
        if context.get("pm25"):
            pm25 = context["pm25"]
            context_rows.append(f'<div class="eu-fact"><span>PM2,5 CAMS · model 10 km</span><strong>{_ca(pm25["value_ug_m3"], 2)} µg/m³</strong></div>')
            context_notes.append(f'PM2,5 {pm25["reference_time_utc"][:10]}')
        if context.get("night_lst"):
            night = context["night_lst"]
            context_rows.append(f'<div class="eu-fact"><span>LST nocturna CLMS · 3 km</span><strong>{_ca(night["value_c"], 1)} °C</strong></div>')
            context_notes.append(f'LST {night["reference_date"]}')
        if context.get("soil_moisture"):
            soil = context["soil_moisture"]
            context_rows.append(f'<div class="eu-fact"><span>Humitat sòl CLMS · 1 km</span><strong>{_ca(soil["value_pct_saturation"], 1)} %</strong></div>')
            context_notes.append(f'SSM {soil["reference_date"]}')
        if context.get("no2"):
            no2 = context["no2"]
            no2_label = f'{no2["value_mol_m2"]:.2e}'.replace(".", ",")
            context_rows.append(f'<div class="eu-fact"><span>NO₂ troposfèric S5P · context</span><strong>{no2_label} mol/m²</strong></div>')
            context_notes.append(f'NO₂ {no2["reference_date"]}')
        if context_rows:
            contextual_facts = (
                '<section class="eu-panel"><h3>Context supramunicipal</h3><div class="eu-facts">'
                + ''.join(context_rows)
                + '</div><p class="eu-source">'
                + ' · '.join(context_notes)
                + '. Valors agregats a la resolució nativa; no són mesures ni mapes de carrer.</p></section>'
            )

    daily_readings_html = ""
    if daily:
        daily_rows = []
        for key, item in daily["readings"].items():
            data_date = _human_utc(item["data_at_utc"]) if item.get("data_at_utc") else "—"
            check_date = _human_utc(item["checked_at_utc"])
            analytics = daily_history.get("analytics", {}).get(key, {}) if daily_history else {}
            trend = analytics.get("trend", {"symbol": "→", "label": "sense comparació", "variation_pct": None})
            variation = trend.get("variation_pct")
            variation_label = "—" if variation is None else f'{variation:+.1f} %'.replace(".", ",")
            confidence = analytics.get("confidence", {"score_pct": 0, "label": "Baixa"})
            frequency = analytics.get("frequency", {"frequency_label": "no definida", "trigger": "—"})
            reading_alerts = analytics.get("alerts", [])
            alert_html = ''.join(
                f'<div class="eu-reading-alert {alert["level"]}"><strong>Alerta · {html.escape(alert["label"])}</strong><span>{html.escape(alert["basis"])}</span></div>'
                for alert in reading_alerts
            )
            daily_rows.append(
                f'<article class="eu-daily-row{" has-alert" if reading_alerts else ""}" data-reading-key="{html.escape(key)}">'
                '<div class="eu-daily-heading">'
                f'<strong data-reading-field="label">{html.escape(item["label"])}</strong>'
                f'<b class="eu-daily-status {item["status_code"]}" data-reading-field="status">{html.escape(item["status"])}</b>'
                '</div>'
                f'<div class="eu-daily-value" data-reading-field="value">{html.escape(item["value"])}</div>'
                '<div class="eu-reading-metrics">'
                f'<span class="eu-trend"><b data-reading-field="trend">{trend["symbol"]} {html.escape(trend["label"])}</b><small data-reading-field="variation">{variation_label}</small></span>'
                f'<span class="eu-confidence {confidence["label"].lower()}"><b data-reading-field="confidence-score">Confiança {confidence["score_pct"]} %</b><small data-reading-field="confidence-label">{html.escape(confidence["label"])}</small></span>'
                '</div>'
                f'<dl><dt>Font</dt><dd data-reading-field="source">{html.escape(item["source"])}</dd>'
                f'<dt>Data real</dt><dd data-reading-field="data-at">{data_date}</dd>'
                f'<dt>Última comprovació</dt><dd data-reading-field="checked-at">{check_date}</dd>'
                f'<dt>Freqüència</dt><dd data-reading-field="frequency">{html.escape(frequency["frequency_label"])}</dd>'
                f'<dt>S’actualitza quan</dt><dd data-reading-field="trigger">{html.escape(frequency["trigger"])}</dd></dl>'
                + alert_html +
                f'<p data-reading-field="note">{html.escape(item["note"])}</p>'
                '</article>'
            )
        counts = daily["status_counts"]
        active_alerts = daily_history.get("active_alerts", []) if daily_history else []
        alerts_summary = (
            '<div class="eu-alert-summary" id="eu-alert-summary"><strong>Alertes actives</strong>'
            + ''.join(f'<span class="{alert["level"]}">{html.escape(daily["readings"][alert["reading"]]["label"])} · {html.escape(alert["label"])}</span>' for alert in active_alerts)
            + '</div>'
        ) if active_alerts else '<div class="eu-alert-summary clear" id="eu-alert-summary"><strong>Sense alertes actives amb els llindars definits</strong></div>'
        history_options = ''.join(
            f'<option value="{key}">{html.escape(item["label"])}</option>'
            for key, item in daily["readings"].items()
            if daily_history and len(daily_history.get("series", {}).get(key, [])) >= 2
        )
        history_panel = (
            '<section class="eu-panel eu-history-panel"><h3>Històric i comparació temporal</h3>'
            '<label for="eu-history-reading">Lectura</label><select id="eu-history-reading">' + history_options + '</select>'
            '<div class="eu-history-chart-wrap"><svg id="eu-history-chart" role="img" aria-label="Gràfica d’evolució de la lectura seleccionada"></svg></div>'
            '<div class="eu-history-controls"><label>Data A<select id="eu-history-a"></select></label><label>Data B<select id="eu-history-b"></select></label></div>'
            '<div class="eu-history-comparison" id="eu-history-comparison"></div>'
            '<p class="eu-source">Només es mostren lectures amb dues observacions reals o més. Cada punt conserva la data de font i les comprovacions sense dada nova no dupliquen la sèrie.</p></section>'
        ) if history_options else ""
        daily_readings_html = (
            '<section class="eu-panel eu-daily-panel"><h3>Actualització diària</h3>'
            '<div class="eu-live-status is-loading" id="eu-live-status" role="status">Consultant la darrera comprovació del servidor…</div>'
            f'<p class="eu-daily-summary">Avui: <strong data-count="updated_today">{counts["updated_today"]}</strong> · '
            f'última disponible: <strong data-count="last_available">{counts["last_available"]}</strong> · '
            f'no disponible: <strong data-count="unavailable">{counts["unavailable"]}</strong></p>'
            '<details class="eu-source-checks"><summary>Estat de les fonts consultades</summary><div id="eu-source-check-list"></div></details>'
            + alerts_summary +
            '<div class="eu-daily-list">' + ''.join(daily_rows) + '</div>'
            '<p class="eu-source">La resposta de la funció de servidor és la font principal. Els valors empaquetats només es mostren com a reserva quan la consulta remota falla.</p></section>'
            + history_panel
        )

    vectors = {
        "buildings": _compact_geojson(
            PROCESSED / "buildings_cadastre.geojson",
            ["cadastre_id", "footprint_m2", "use"],
            simplify_m=0.35,
            clip_bbox=study_bbox,
        ),
        "green": _compact_geojson(
            PROCESSED / "green_spaces_osm.geojson",
            ["name", "kind"],
            simplify_m=2.0,
            clip_bbox=study_bbox,
        ),
        "mobility": _compact_geojson(
            PROCESSED / "mobility_osm.geojson",
            ["name", "highway", "mode"],
            simplify_m=1.5,
            clip_bbox=study_bbox,
        ),
        "facilities": _compact_geojson(
            PROCESSED / "facilities_osm.geojson",
            ["name", "kind"],
            clip_bbox=study_bbox,
        ),
        "water": _compact_geojson(
            PROCESSED / "water_osm.geojson",
            ["name", "kind"],
            simplify_m=1.5,
            clip_bbox=study_bbox,
        ),
    }
    _add_roof_attributes(
        vectors["buildings"],
        PROCESSED
        / (
            "solar_roof_screening_expanded.geojson"
            if expanded_scope
            else "solar_roof_screening.geojson"
        ),
        study_bbox,
    )
    if expanded_scope:
        scope_metrics = expanded["metrics"]
        lst_metrics = scope_metrics["land_surface_temperature_c"]
    else:
        scope_metrics = extended_metrics
        lst_metrics = {
            "mean": manifest["landsat"]["mean_c"],
            "p10": manifest["landsat"]["p10_c"],
            "p90": manifest["landsat"]["p90_c"],
        }

    data = {
        "bbox": _pad_bbox(study_bbox, 0.035) if expanded_scope else manifest["map_bbox_epsg4326"],
        "mapBbox": manifest["map_bbox_epsg4326"],
        "floodBbox": study_bbox if expanded_scope else manifest["map_bbox_epsg4326"],
        "lidarBbox": study_bbox if expanded_scope else manifest["lidar"]["bbox_epsg4326"],
        "lstBbox": study_bbox if expanded_scope else manifest["landsat"]["bbox_epsg4326"],
        "indicatorBbox": study_bbox,
        "expandedBbox": manifest.get(
            "expanded_study_bbox_epsg4326",
            manifest["analysis_core_bbox_epsg4326"],
        ),
        "fireBbox": study_bbox if (fire and expanded_scope) else (fire["processed_layer"]["bbox_epsg4326"] if fire else None),
        "places": [
            place
            for place in fire["expanded_operational_scope"]["place_references"]
            if "les Valls de Valira" not in place["name"]
        ] if fire else [],
        "metrics": {
            "studyAreaHa": expanded["study_area_ha"] if expanded_scope else 130.4,
            "buildings": len(vectors["buildings"]["features"]),
            "shade": (
                daily.get("readings", {}).get("shade", {}).get("value_numeric")
                if daily else None
            ) or scope_metrics.get("shade_pct", manifest["lidar"]["shade_pct"]),
            "canopy": scope_metrics.get("canopy_cover_pct", manifest["lidar"]["canopy_cover_pct"]),
            "slopeMedian": scope_metrics.get("terrain_slope_median_deg", manifest["lidar"]["terrain_slope_median_deg"]),
            "lstMean": lst_metrics["mean"],
            "lstP10": lst_metrics["p10"],
            "lstP90": lst_metrics["p90"],
            "lstDate": (
                daily.get("readings", {}).get("surface_temperature", {}).get("data_at_utc")
                if daily else manifest["landsat"]["datetime_local"]
            ),
            "population": demography["population"],
            "older": demography["population_65_plus"],
            "olderPct": demography["population_65_plus_pct"],
            "roofEvaluated": solar_summary["evaluated_buildings"],
            "roofFavorable": solar_summary["classes"].get("favorable", 0),
            "roofConditioned": solar_summary["classes"].get("condicionada", 0),
            "greenFeatures": len(vectors["green"]["features"]),
            "facilities": len(vectors["facilities"]["features"]),
            "mobilitySegments": len(vectors["mobility"]["features"]),
            "waterFeatures": len(vectors["water"]["features"]),
            "surfaceUhi": scope_metrics["surface_uhi_proxy_c"],
            "imperviousMean": scope_metrics["imperviousness_mean_pct"],
            "imperviousHighArea": scope_metrics["imperviousness_area_ge_50_pct"],
            "vegetationCover": scope_metrics["vegetation_cover_area_pct"],
            "treeChange": scope_metrics["tree_density_change_2018_2023_pp"],
            "runoffProxy": scope_metrics["runoff_proxy_mean_0_100"],
        },
        "rasters": raster_data,
        "vectors": vectors,
        "currentFire": {
            "summary": current_fire["summary"],
            "weather": current_fire["weather"],
            "cells": current_fire_cells,
        } if current_fire and current_fire_cells else None,
        "dailyReadings": daily,
        "dailyHistory": daily_history,
    }

    fragment = (
        FRAGMENT.replace("__ECORADAR_DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        .replace("__SENTINEL_MODES__", sentinel_modes)
        .replace("__FIRE_MODE__", fire_mode)
        .replace("__CURRENT_FIRE_MODE__", current_fire_mode)
        .replace("__BIODIVERSITY_MODE__", biodiversity_mode)
        .replace("__BIODIVERSITY_DETAILS__", biodiversity_details)
        .replace("__SENTINEL_FACTS__", sentinel_facts)
        .replace("__FIRE_FACTS__", fire_facts)
        .replace("__CURRENT_FIRE_FACTS__", current_fire_facts)
        .replace("__CONTEXTUAL_FACTS__", contextual_facts)
        .replace("__DAILY_READINGS__", daily_readings_html)
        .replace(
            "__LST_BUTTON_META__",
            _human_utc(daily["readings"]["surface_temperature"]["data_at_utc"])[:10]
            if daily and daily["readings"]["surface_temperature"].get("data_at_utc") else "dada no disponible",
        )
        .replace(
            "__SHADE_BUTTON_META__",
            _human_utc(daily["readings"]["shade"]["data_at_utc"])[:10] + " · 15.00 h"
            if daily and daily["readings"]["shade"].get("data_at_utc") else "dada no disponible",
        )
    )
    VIS_DIR.mkdir(parents=True, exist_ok=True)
    VIS_FILE.write_text(fragment)

    standalone = STANDALONE_PREFIX + fragment + STANDALONE_SUFFIX
    output = MAPS / "ecoradar_urba_la_seu_interactiu.html"
    output.write_text(standalone)
    print(output)
    print(VIS_FILE)
    print(f"fragment_bytes={VIS_FILE.stat().st_size}")


def _data_url(path: Path) -> str:
    media_type = "image/webp" if path.suffix.lower() == ".webp" else "image/png"
    return f"data:{media_type};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _ca(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def _human_utc(value: str) -> str:
    date, time = value[:10].split("-"), value[11:16]
    return f"{date[2]}/{date[1]}/{date[0]} {time} UTC"


def _pad_bbox(bbox: list[float] | tuple[float, ...], fraction: float) -> list[float]:
    width = float(bbox[2]) - float(bbox[0])
    height = float(bbox[3]) - float(bbox[1])
    return [
        float(bbox[0]) - width * fraction,
        float(bbox[1]) - height * fraction,
        float(bbox[2]) + width * fraction,
        float(bbox[3]) + height * fraction,
    ]


def _compact_geojson(
    path: Path,
    properties: list[str],
    simplify_m: float = 0.0,
    clip_bbox: list[float] | tuple[float, ...] | None = None,
) -> dict:
    gdf = gpd.read_file(path, engine="pyogrio")
    if clip_bbox is not None and len(gdf):
        scope = box(*clip_bbox)
        gdf = gdf[gdf.geometry.intersects(scope)].copy()
    if simplify_m and len(gdf):
        projected = gdf.to_crs(25831)
        projected.geometry = projected.geometry.simplify(simplify_m, preserve_topology=True)
        gdf = projected.to_crs(4326)
    features = []
    for row in gdf.itertuples(index=False):
        props = {}
        for prop in properties:
            if hasattr(row, prop):
                value = getattr(row, prop)
                if value is not None:
                    props[prop] = value.item() if hasattr(value, "item") else value
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": _round_geometry(mapping(_orient_for_d3(row.geometry))),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _add_roof_attributes(
    buildings: dict,
    roof_path: Path,
    clip_bbox: list[float] | tuple[float, ...],
) -> None:
    roofs = gpd.read_file(roof_path, engine="pyogrio")
    roofs = roofs[roofs.geometry.intersects(box(*clip_bbox))]
    attributes = {
        str(row.cadastre_id): {
            "median_slope_deg": row.median_slope_deg,
            "mean_aspect_deg": row.mean_aspect_deg,
            "solar_screen": row.solar_screen,
        }
        for row in roofs.itertuples()
        if getattr(row, "cadastre_id", None) is not None
    }
    for feature in buildings["features"]:
        cadastre_id = feature["properties"].get("cadastre_id")
        if cadastre_id is not None and str(cadastre_id) in attributes:
            feature["properties"].update(attributes[str(cadastre_id)])


def _round_geometry(geometry: dict) -> dict:
    def rounded(value):
        if isinstance(value, (list, tuple)):
            return [rounded(item) for item in value]
        if isinstance(value, float):
            return round(value, 5)
        return value

    return {"type": geometry["type"], "coordinates": rounded(geometry["coordinates"])}


def _orient_for_d3(geometry):
    """Use d3-geo's spherical winding convention for polygon interiors."""
    if isinstance(geometry, Polygon):
        return orient(geometry, sign=-1.0)
    if isinstance(geometry, MultiPolygon):
        return MultiPolygon([orient(part, sign=-1.0) for part in geometry.geoms])
    return geometry


STANDALONE_PREFIX = """<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EcoRadar Urbà · La Seu d'Urgell</title>
</head>
<body style="margin:0;background:#f4f1e9">
"""

STANDALONE_SUFFIX = """
</body>
</html>
"""


FRAGMENT = r"""
<div id="ecoradar-urba-la-seu" class="eu-shell">
  <style>
    #ecoradar-urba-la-seu {
      --ink:#15314f; --blue:#0a3a71; --green:#2f743f; --green-soft:#dfeadb;
      --paper:#f7f4ec; --panel:#fbfaf6; --line:#d7d1c4; --muted:#68747e;
      --orange:#e57a24; --red:#c7252c; --purple:#68409a; --cyan:#1688bd;
      color:var(--ink); background:var(--paper); font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
      min-height:760px; border:1px solid #d8d1c4; box-sizing:border-box; overflow:hidden;
    }
    #ecoradar-urba-la-seu * { box-sizing:border-box; }
    #ecoradar-urba-la-seu .eu-head { display:grid; grid-template-columns:minmax(280px,.9fr) minmax(430px,1.5fr) auto; gap:20px; align-items:end; padding:18px 20px 14px; border-bottom:1px solid var(--line); background:linear-gradient(90deg,#fbfaf6 0%,#f6f2e8 70%,#f9f7f1 100%); }
    #ecoradar-urba-la-seu h1 { margin:0; font-size:28px; line-height:.94; letter-spacing:.02em; color:var(--blue); }
    #ecoradar-urba-la-seu h1 span { display:block; margin-top:7px; color:var(--green); font-size:31px; }
    #ecoradar-urba-la-seu h1 small { display:block; margin-top:7px; color:#49645a; font-size:12px; line-height:1.15; letter-spacing:.08em; }
    #ecoradar-urba-la-seu .eu-title h2 { margin:0; font-size:21px; letter-spacing:.055em; color:var(--blue); }
    #ecoradar-urba-la-seu .eu-title p { margin:6px 0 0; font-size:11px; color:#384958; }
    #ecoradar-urba-la-seu .eu-badge { align-self:start; border:1px solid #bfc8c1; border-radius:999px; padding:7px 10px; font-size:10px; color:#3e5260; background:#fffefa; white-space:nowrap; }
    #ecoradar-urba-la-seu .eu-grid { display:grid; grid-template-columns:272px minmax(0,1fr); gap:10px; align-items:start; padding:10px; min-height:655px; }
    #ecoradar-urba-la-seu .eu-column { display:flex; flex-direction:column; gap:9px; min-width:0; }
    #ecoradar-urba-la-seu .eu-map-panel { grid-column:2; }
    #ecoradar-urba-la-seu .eu-column.eu-right { grid-column:1/-1; display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:9px; align-items:start; }
    #ecoradar-urba-la-seu .eu-right .eu-daily-panel, #ecoradar-urba-la-seu .eu-right .eu-history-panel { grid-column:1/-1; }
    #ecoradar-urba-la-seu .eu-right #eu-reading-guide { grid-column:span 2; }
    #ecoradar-urba-la-seu .eu-summary-grid { grid-column:1/-1; display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); grid-auto-rows:auto; gap:9px; align-items:stretch; }
    #ecoradar-urba-la-seu .eu-summary-grid>.eu-panel { height:100%; min-height:220px; }
    #ecoradar-urba-la-seu .eu-panel { background:rgba(255,255,255,.76); border:1px solid var(--line); padding:11px; }
    #ecoradar-urba-la-seu .eu-panel h3 { margin:0 0 8px; color:var(--blue); font-size:11px; text-transform:uppercase; letter-spacing:.045em; }
    #ecoradar-urba-la-seu .eu-panel p { margin:5px 0; font-size:10px; line-height:1.42; color:#425362; }
    #ecoradar-urba-la-seu .eu-modes { display:grid; grid-template-columns:1fr 1fr; gap:6px; }
    #ecoradar-urba-la-seu button { font:inherit; }
    #ecoradar-urba-la-seu .eu-mode, #ecoradar-urba-la-seu .eu-layer { border:1px solid #cad0ca; background:#fff; color:#29465d; border-radius:5px; padding:8px 7px; cursor:pointer; text-align:left; font-size:10px; transition:.15s ease; }
    #ecoradar-urba-la-seu .eu-mode:hover, #ecoradar-urba-la-seu .eu-layer:hover { border-color:#6d8d7a; transform:translateY(-1px); }
    #ecoradar-urba-la-seu .eu-mode[aria-pressed="true"], #ecoradar-urba-la-seu .eu-layer[aria-pressed="true"] { color:#fff; background:var(--blue); border-color:var(--blue); }
    #ecoradar-urba-la-seu .eu-mode small { display:block; opacity:.72; margin-top:2px; font-size:8px; }
    #ecoradar-urba-la-seu .eu-layer-list { display:grid; gap:5px; }
    #ecoradar-urba-la-seu .eu-layer { display:flex; align-items:center; gap:8px; padding:7px 8px; }
    #ecoradar-urba-la-seu .eu-dot { width:9px; height:9px; border-radius:2px; background:var(--dot); flex:none; }
    #ecoradar-urba-la-seu .eu-facts { display:grid; gap:7px; }
    #ecoradar-urba-la-seu .eu-fact { display:grid; grid-template-columns:1fr auto; gap:8px; align-items:baseline; padding-bottom:7px; border-bottom:1px solid #e5e1d8; }
    #ecoradar-urba-la-seu .eu-fact:last-child { border-bottom:0; padding-bottom:0; }
    #ecoradar-urba-la-seu .eu-fact span { font-size:9px; color:#51616e; }
    #ecoradar-urba-la-seu .eu-fact strong { color:var(--green); font-size:14px; }
    #ecoradar-urba-la-seu .eu-map-panel { position:relative; height:720px; min-height:635px; border:1px solid #cfc9bb; background:#e9ede5; overflow:hidden; }
    #ecoradar-urba-la-seu .eu-map-head { position:absolute; z-index:4; top:10px; left:10px; right:10px; display:flex; justify-content:space-between; pointer-events:none; }
    #ecoradar-urba-la-seu .eu-map-label { background:rgba(255,255,255,.9); border:1px solid #d5d0c4; padding:7px 9px; font-size:9px; color:#385064; box-shadow:0 3px 12px rgba(38,51,60,.08); }
    #ecoradar-urba-la-seu .eu-reset { pointer-events:auto; border:1px solid #c9c4b8; background:rgba(255,255,255,.94); border-radius:4px; padding:7px 9px; color:var(--blue); cursor:pointer; font-size:9px; }
    #ecoradar-urba-la-seu svg { display:block; width:100%; height:100%; min-height:635px; cursor:grab; }
    #ecoradar-urba-la-seu svg:active { cursor:grabbing; }
    #ecoradar-urba-la-seu .eu-map-bg { fill:#edf0e9; }
    #ecoradar-urba-la-seu .eu-building { fill:#eee9df; stroke:#9f9b91; stroke-width:.45; vector-effect:non-scaling-stroke; }
    #ecoradar-urba-la-seu .eu-green { fill:#a8c88f; fill-opacity:.72; stroke:#5f965a; stroke-width:.8; vector-effect:non-scaling-stroke; }
    #ecoradar-urba-la-seu .eu-water { stroke:#3f9ec0; stroke-width:1.2; vector-effect:non-scaling-stroke; }
    #ecoradar-urba-la-seu .eu-water.area { fill:#96c9db; fill-opacity:.8; }
    #ecoradar-urba-la-seu .eu-water.line { fill:none; stroke-width:1.7; }
    #ecoradar-urba-la-seu .eu-road { fill:none; stroke:#fbfbf7; stroke-width:2.4; stroke-linecap:round; stroke-linejoin:round; vector-effect:non-scaling-stroke; }
    #ecoradar-urba-la-seu .eu-road.viaria { stroke:#c9bda7; stroke-width:1.35; }
    #ecoradar-urba-la-seu .eu-road.a_peu { stroke:#8768a8; stroke-width:1.25; stroke-dasharray:4 3; }
    #ecoradar-urba-la-seu .eu-road.ciclable { stroke:#1591bd; stroke-width:1.8; }
    #ecoradar-urba-la-seu .eu-facility { fill:#0b477d; stroke:#fff; stroke-width:1.3; vector-effect:non-scaling-stroke; }
    #ecoradar-urba-la-seu .eu-roof { stroke:#fff; stroke-width:.35; vector-effect:non-scaling-stroke; }
    #ecoradar-urba-la-seu .eu-roof.favorable { fill:#1b8b55; }
    #ecoradar-urba-la-seu .eu-roof.condicionada { fill:#e2a72f; }
    #ecoradar-urba-la-seu .eu-roof.baixa { fill:#c95a47; }
    #ecoradar-urba-la-seu .eu-boundary { fill:none; stroke:#0b3d72; stroke-width:1.2; stroke-dasharray:6 4; vector-effect:non-scaling-stroke; }
    #ecoradar-urba-la-seu .eu-place { fill:#fff; stroke:#0b3d72; stroke-width:2; vector-effect:non-scaling-stroke; }
    #ecoradar-urba-la-seu .eu-place-label { fill:#14395f; stroke:#fff; stroke-width:3px; paint-order:stroke; font-size:11px; font-weight:750; pointer-events:none; }
    #ecoradar-urba-la-seu .eu-map-note { position:absolute; left:10px; bottom:10px; z-index:4; max-width:330px; padding:7px 9px; background:rgba(255,255,255,.9); border:1px solid #d5d0c4; font-size:8px; line-height:1.35; color:#455662; }
    #ecoradar-urba-la-seu .eu-legend { display:grid; gap:5px; font-size:9px; color:#445663; }
    #ecoradar-urba-la-seu .eu-legend-row { display:flex; align-items:center; gap:7px; }
    #ecoradar-urba-la-seu .eu-swatch { width:18px; height:9px; border:1px solid rgba(0,0,0,.12); }
    #ecoradar-urba-la-seu .eu-guide-title { margin:0 0 6px; color:var(--green); font-size:12px; line-height:1.25; font-weight:700; }
    #ecoradar-urba-la-seu .eu-guide-copy { margin:0 0 7px!important; color:#334d5d!important; }
    #ecoradar-urba-la-seu .eu-guide-label { margin:9px 0 5px; color:var(--blue); font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:.035em; }
    #ecoradar-urba-la-seu .eu-guide-reading { margin-top:8px!important; padding-top:7px; border-top:1px solid #e5e1d8; }
    #ecoradar-urba-la-seu .eu-guide-limit { margin-top:7px!important; color:#6c5a47!important; }
    #ecoradar-urba-la-seu .eu-biodiversity { margin-top:9px; padding-top:7px; border-top:1px solid #e5e1d8; }
    #ecoradar-urba-la-seu .eu-biodiversity[hidden] { display:none; }
    #ecoradar-urba-la-seu .eu-biodiversity summary { color:var(--blue); cursor:pointer; font-size:11px; font-weight:700; line-height:1.4; }
    #ecoradar-urba-la-seu .eu-biodiversity-body { display:grid; gap:8px; padding-top:8px; }
    #ecoradar-urba-la-seu .eu-biodiversity h4 { margin:0 0 3px; color:var(--green); font-size:11px; }
    #ecoradar-urba-la-seu .eu-biodiversity p { margin:0!important; font-size:11px!important; line-height:1.45!important; }
    #ecoradar-urba-la-seu .eu-bio-summary { display:grid; gap:4px; }
    #ecoradar-urba-la-seu .eu-bio-summary>div { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:5px; align-items:center; padding:5px 0; border-bottom:1px solid #e5e1d8; }
    #ecoradar-urba-la-seu .eu-bio-summary small { display:block; color:#64717b; font-size:9px; font-weight:400; }
    #ecoradar-urba-la-seu .eu-bio-badge { display:inline-block; border:1px solid; border-radius:3px; padding:2px 4px; font-size:9px; line-height:1.2; font-weight:700; }
    #ecoradar-urba-la-seu .eu-bio-badge.observed { color:#22613a; background:#e5f1e7; border-color:#8eb69a; }
    #ecoradar-urba-la-seu .eu-bio-badge.infrastructure { color:#27567b; background:#e7eff6; border-color:#97b3ca; }
    #ecoradar-urba-la-seu .eu-bio-badge.potential { color:#5e4080; background:#eee9f4; border-color:#b3a2c5; }
    #ecoradar-urba-la-seu .eu-bio-badge.pending { color:#7a5922; background:#f7eedb; border-color:#cbb37d; }
    #ecoradar-urba-la-seu .eu-bio-data { display:grid; grid-template-columns:1fr 1fr; gap:4px; margin:5px 0; }
    #ecoradar-urba-la-seu .eu-bio-data>div { min-width:0; padding:5px; background:#f7f5ef; border:1px solid #e2ddd2; }
    #ecoradar-urba-la-seu .eu-bio-data .wide { grid-column:1/-1; }
    #ecoradar-urba-la-seu .eu-bio-data span { display:block; color:#64717b; font-size:9px; line-height:1.25; }
    #ecoradar-urba-la-seu .eu-bio-data strong { display:block; margin-top:1px; color:#24465b; font-size:10px; line-height:1.3; }
    #ecoradar-urba-la-seu .eu-bio-names { padding:5px; background:#f7f5ef; border-left:2px solid #97b3ca; }
    #ecoradar-urba-la-seu .eu-age { display:flex; height:11px; border-radius:7px; overflow:hidden; margin:8px 0 5px; }
    #ecoradar-urba-la-seu .eu-age span:nth-child(1){background:#65a2c4;width:12.3%} #ecoradar-urba-la-seu .eu-age span:nth-child(2){background:#67a767;width:67.6%} #ecoradar-urba-la-seu .eu-age span:nth-child(3){background:#d29d46;width:16.6%} #ecoradar-urba-la-seu .eu-age span:nth-child(4){background:#934e73;width:3.5%}
    #ecoradar-urba-la-seu .eu-age-labels { display:grid; grid-template-columns:1fr 1fr; gap:3px 8px; font-size:8px; color:#50616e; }
    #ecoradar-urba-la-seu .eu-source { font-size:8px!important; color:#74808a!important; }
    #ecoradar-urba-la-seu .eu-live-status { margin:0 0 8px; padding:7px 8px; border-left:3px solid var(--green); background:#e8f2ea; color:#315a3f; font-size:9px; line-height:1.35; }
    #ecoradar-urba-la-seu .eu-live-status.is-loading { border-color:var(--cyan); background:#e8f2f7; color:#31576c; }
    #ecoradar-urba-la-seu .eu-live-status.is-fallback { border-color:var(--orange); background:#fff2db; color:#76521e; }
    #ecoradar-urba-la-seu .eu-daily-summary { margin-bottom:9px; padding:6px 7px; background:#eef3ec; border-left:3px solid var(--green); }
    #ecoradar-urba-la-seu .eu-source-checks { margin:0 0 9px; border:1px solid #ded9ce; background:#fffefa; }
    #ecoradar-urba-la-seu .eu-source-checks summary { padding:6px 7px; color:var(--blue); cursor:pointer; font-size:9px; font-weight:700; }
    #ecoradar-urba-la-seu #eu-source-check-list { display:grid; gap:4px; padding:0 7px 7px; }
    #ecoradar-urba-la-seu .eu-source-check { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:4px 8px; padding-top:4px; border-top:1px solid #ebe7de; font-size:8px; line-height:1.35; }
    #ecoradar-urba-la-seu .eu-source-check small { grid-column:1/-1; color:#69757e; }
    #ecoradar-urba-la-seu .eu-source-check b { color:#24633a; }
    #ecoradar-urba-la-seu .eu-source-check b.blocked, #ecoradar-urba-la-seu .eu-source-check b.service_unavailable { color:#8a3842; }
    #ecoradar-urba-la-seu .eu-source-check b.requires_credentials, #ecoradar-urba-la-seu .eu-source-check b.pending_verification { color:#8a651c; }
    #ecoradar-urba-la-seu .eu-daily-list { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:7px; }
    #ecoradar-urba-la-seu .eu-daily-row { min-width:0; padding:8px; border:1px solid #e1ddd3; background:#fffefa; }
    #ecoradar-urba-la-seu .eu-daily-row.has-alert { border-left:4px solid var(--orange); background:#fff9ef; }
    #ecoradar-urba-la-seu .eu-daily-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:6px; }
    #ecoradar-urba-la-seu .eu-daily-heading>strong { min-width:0; color:var(--blue); font-size:10px; line-height:1.3; }
    #ecoradar-urba-la-seu .eu-daily-status { flex:none; max-width:118px; border:1px solid; border-radius:999px; padding:2px 5px; text-align:center; font-size:7px; line-height:1.25; }
    #ecoradar-urba-la-seu .eu-daily-status.updated_today { color:#24633a; background:#e4f1e7; border-color:#8db79a; }
    #ecoradar-urba-la-seu .eu-daily-status.last_available { color:#785819; background:#f6eed9; border-color:#cbb276; }
    #ecoradar-urba-la-seu .eu-daily-status.unavailable { color:#6c4650; background:#f3e8ea; border-color:#c8a5ad; }
    #ecoradar-urba-la-seu .eu-daily-value { margin:5px 0; color:var(--green); font-size:14px; font-weight:750; overflow-wrap:anywhere; }
    #ecoradar-urba-la-seu .eu-reading-metrics { display:grid; grid-template-columns:1fr 1fr; gap:5px; margin:5px 0 7px; }
    #ecoradar-urba-la-seu .eu-reading-metrics>span { min-width:0; padding:5px; border:1px solid #ded9ce; background:#f7f5ef; }
    #ecoradar-urba-la-seu .eu-reading-metrics b, #ecoradar-urba-la-seu .eu-reading-metrics small { display:block; font-size:8px; line-height:1.3; }
    #ecoradar-urba-la-seu .eu-reading-metrics small { color:#6d7880; }
    #ecoradar-urba-la-seu .eu-confidence.alta b { color:#23663c; } #ecoradar-urba-la-seu .eu-confidence.mitjana b { color:#8a651c; } #ecoradar-urba-la-seu .eu-confidence.baixa b { color:#8a3842; }
    #ecoradar-urba-la-seu .eu-daily-row dl { display:grid; grid-template-columns:70px minmax(0,1fr); gap:2px 5px; margin:0; font-size:8px; line-height:1.35; }
    #ecoradar-urba-la-seu .eu-daily-row dt { color:#74808a; }
    #ecoradar-urba-la-seu .eu-daily-row dd { min-width:0; margin:0; color:#415461; overflow-wrap:anywhere; }
    #ecoradar-urba-la-seu .eu-daily-row p { margin-top:6px; padding-top:5px; border-top:1px solid #ebe7de; font-size:8px; }
    #ecoradar-urba-la-seu .eu-alert-summary { display:grid; gap:4px; margin:0 0 9px; padding:7px; border:1px solid #dfb171; background:#fff2db; font-size:8px; }
    #ecoradar-urba-la-seu .eu-alert-summary>span { padding:4px 5px; border-left:3px solid var(--orange); background:#fffaf1; }
    #ecoradar-urba-la-seu .eu-alert-summary>span.critical { border-color:var(--red); color:#8a2630; }
    #ecoradar-urba-la-seu .eu-alert-summary.clear { border-color:#a9c6ae; background:#edf5ee; }
    #ecoradar-urba-la-seu .eu-reading-alert { display:grid; gap:2px; margin:6px 0; padding:6px; border-left:3px solid var(--orange); background:#fff0d6; font-size:8px; line-height:1.35; }
    #ecoradar-urba-la-seu .eu-reading-alert.critical { border-color:var(--red); background:#f9e5e7; }
    #ecoradar-urba-la-seu .eu-reading-alert span { color:#64594d; }
    #ecoradar-urba-la-seu .eu-history-panel>label, #ecoradar-urba-la-seu .eu-history-controls label { display:grid; gap:3px; color:#5b6973; font-size:8px; }
    #ecoradar-urba-la-seu .eu-history-panel select { width:100%; min-width:0; padding:6px; border:1px solid #cfc9bd; background:#fff; color:var(--blue); font-size:9px; }
    #ecoradar-urba-la-seu .eu-history-chart-wrap { margin:8px 0; border:1px solid #ded9ce; background:#fff; }
    #ecoradar-urba-la-seu #eu-history-chart { width:100%; height:250px; min-height:250px; cursor:default; }
    #ecoradar-urba-la-seu .eu-history-controls { display:grid; grid-template-columns:1fr 1fr; gap:6px; }
    #ecoradar-urba-la-seu .eu-history-comparison { margin-top:7px; padding:7px; background:#eef3ec; border-left:3px solid var(--green); font-size:9px; line-height:1.4; }
    #ecoradar-urba-la-seu .eu-warning { border-left:3px solid var(--orange); padding-left:8px; }
    #ecoradar-urba-la-seu .eu-tooltip { position:absolute; z-index:10; pointer-events:none; opacity:0; background:#122f49; color:#fff; border-radius:4px; padding:7px 8px; max-width:230px; font-size:9px; line-height:1.35; box-shadow:0 8px 24px rgba(0,0,0,.18); }
    #ecoradar-urba-la-seu .eu-fire-cell { fill:transparent; stroke:transparent; stroke-width:.45; vector-effect:non-scaling-stroke; cursor:pointer; }
    #ecoradar-urba-la-seu .eu-fire-cell:hover, #ecoradar-urba-la-seu .eu-fire-cell:focus { fill:transparent; stroke:transparent; outline:none; }
    #ecoradar-urba-la-seu .eu-fire-popup { position:absolute; z-index:12; top:52px; right:10px; width:min(390px,calc(100% - 20px)); max-height:calc(100% - 72px); overflow:auto; padding:12px; background:rgba(255,255,255,.97); border:1px solid #b8b2a6; box-shadow:0 12px 32px rgba(20,39,54,.22); font-size:9px; line-height:1.38; }
    #ecoradar-urba-la-seu .eu-fire-popup[hidden] { display:none; }
    #ecoradar-urba-la-seu .eu-fire-popup-close { float:right; border:1px solid #c9c4b8; background:#fff; color:var(--blue); cursor:pointer; border-radius:3px; }
    #ecoradar-urba-la-seu .eu-fire-popup h3 { margin:0 0 2px; color:var(--blue); font-size:13px; }
    #ecoradar-urba-la-seu .eu-fire-popup h4 { margin:10px 0 4px; color:var(--green); font-size:10px; }
    #ecoradar-urba-la-seu .eu-fire-popup-main { display:flex; gap:8px; align-items:baseline; margin:4px 0 8px; }
    #ecoradar-urba-la-seu .eu-fire-popup-main strong { font-size:22px; color:#9f312d; }
    #ecoradar-urba-la-seu .eu-fire-popup table { width:100%; border-collapse:collapse; }
    #ecoradar-urba-la-seu .eu-fire-popup th, #ecoradar-urba-la-seu .eu-fire-popup td { padding:3px 2px; border-bottom:1px solid #e7e2d8; text-align:left; vertical-align:top; }
    #ecoradar-urba-la-seu .eu-fire-popup td:last-child { text-align:right; white-space:nowrap; }
    #ecoradar-urba-la-seu .eu-fire-summary { display:grid; grid-template-columns:1fr 1fr; gap:5px; }
    #ecoradar-urba-la-seu .eu-fire-summary>div { padding:6px; background:#f7f4ec; border:1px solid #e2ddd2; }
    #ecoradar-urba-la-seu .eu-fire-summary span { display:block; color:#69757e; font-size:8px; }
    #ecoradar-urba-la-seu .eu-fire-summary strong { display:block; color:#9f312d; font-size:12px; }
    #ecoradar-urba-la-seu .eu-fire-area { display:flex; flex-wrap:wrap; gap:4px 8px; margin-top:7px; font-size:8px; color:#52616c; }
    #ecoradar-urba-la-seu .eu-fire-table-wrap { overflow-x:auto; }
    #ecoradar-urba-la-seu .eu-fire-table { width:100%; min-width:520px; border-collapse:collapse; font-size:8px; }
    #ecoradar-urba-la-seu .eu-fire-table th, #ecoradar-urba-la-seu .eu-fire-table td { padding:4px; border-bottom:1px solid #e5e1d8; text-align:left; vertical-align:top; }
    #ecoradar-urba-la-seu .eu-fire-table th { color:var(--blue); }
    #ecoradar-urba-la-seu .eu-fire-table small { display:block; margin-top:2px; color:#77818a; }
    #ecoradar-urba-la-seu .eu-fire-weights { display:grid; gap:3px; padding:0; margin:7px 0; list-style:none; }
    #ecoradar-urba-la-seu .eu-fire-weights li { display:flex; justify-content:space-between; gap:8px; border-bottom:1px solid #e5e1d8; padding-bottom:3px; font-size:9px; }
    #ecoradar-urba-la-seu .eu-foot { grid-column:1/-1; display:flex; justify-content:space-between; gap:12px; border-top:1px solid var(--line); padding:7px 11px 1px; font-size:8px; color:#687682; }
    @media (max-width:1050px) { #ecoradar-urba-la-seu .eu-grid { grid-template-columns:230px minmax(0,1fr); } #ecoradar-urba-la-seu .eu-column.eu-right, #ecoradar-urba-la-seu .eu-summary-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } #ecoradar-urba-la-seu .eu-daily-list { grid-template-columns:repeat(4,minmax(0,1fr)); } #ecoradar-urba-la-seu .eu-right #eu-reading-guide { grid-column:span 2; } #ecoradar-urba-la-seu .eu-foot { grid-column:1/-1; } }
    @media (max-width:760px) { #ecoradar-urba-la-seu .eu-head { grid-template-columns:1fr; } #ecoradar-urba-la-seu .eu-grid { grid-template-columns:1fr; } #ecoradar-urba-la-seu .eu-map-panel { grid-column:1; } #ecoradar-urba-la-seu .eu-column.eu-right, #ecoradar-urba-la-seu .eu-summary-grid { display:grid; grid-template-columns:1fr; } #ecoradar-urba-la-seu .eu-right #eu-reading-guide { grid-column:1; } #ecoradar-urba-la-seu .eu-daily-list { grid-template-columns:1fr; } #ecoradar-urba-la-seu .eu-summary-grid>.eu-panel { min-height:0; } #ecoradar-urba-la-seu .eu-map-panel, #ecoradar-urba-la-seu svg { height:520px; min-height:520px; } #ecoradar-urba-la-seu #eu-history-chart { height:220px; min-height:220px; } }
  </style>

  <header class="eu-head">
    <h1>ECORADAR URBÀ<span>LA SEU D'URGELL</span><small>CASTELLCIUTAT · SANT ANTONI</small></h1>
    <div class="eu-title"><h2>XARXA CLIMÀTICA DE BENESTAR</h2><p>Mapa tècnic interactiu · només dades obtingudes i verificades · EPSG:25831 / EPSG:4326</p></div>
    <div class="eu-badge">Dades obertes · actualització traçable</div>
  </header>

  <main class="eu-grid">
    <aside class="eu-column eu-left">
      <section class="eu-panel">
        <h3>Lectura temàtica</h3>
        <div class="eu-modes" role="group" aria-label="Capa raster principal">
          <button class="eu-mode" data-mode="none" aria-pressed="true">Mapa base<small>edificis, verd i aigua</small></button>
          <button class="eu-mode" data-mode="lst" aria-pressed="false">Temperatura<small data-reading-meta="surface_temperature">Landsat · __LST_BUTTON_META__</small></button>
          <button class="eu-mode" data-mode="uhi" aria-pressed="false">Illa de calor<small>SUHI superficial · proxy</small></button>
          <button class="eu-mode" data-mode="shade" aria-pressed="false">Ombra LiDAR<small data-reading-meta="shade">__SHADE_BUTTON_META__</small></button>
          <button class="eu-mode" data-mode="canopy" aria-pressed="false">Capçada<small>classes LiDAR 4–5</small></button>
          <button class="eu-mode" data-mode="vegetation" aria-pressed="false">Coberta vegetal<small>CLMS HRL · 2023</small></button>
          <button class="eu-mode" data-mode="treeChange" aria-pressed="false">Canvi arbrat<small>TCD · 2018–2023</small></button>
          <button class="eu-mode" data-mode="impervious" aria-pressed="false">Impermeabilització<small>CLMS HRL · 2021</small></button>
          <button class="eu-mode" data-mode="runoff" aria-pressed="false">Escorrentia<small>índex relatiu · proxy</small></button>
          <button class="eu-mode" data-mode="slope" aria-pressed="false">Pendent<small>MDT LiDAR · 2 m</small></button>
          <button class="eu-mode" data-mode="flood" aria-pressed="false">Inundabilitat<small>SNCZI · T=100 anys</small></button>
          __FIRE_MODE__
          __CURRENT_FIRE_MODE__
          __SENTINEL_MODES__
          __BIODIVERSITY_MODE__
        </div>
      </section>
      <section class="eu-panel">
        <h3>Capes vectorials</h3>
        <div class="eu-layer-list">
          <button class="eu-layer" data-layer="buildings" aria-pressed="true"><span class="eu-dot" style="--dot:#d2cdc2"></span>Edificis Cadastre</button>
          <button class="eu-layer" data-layer="green" aria-pressed="true"><span class="eu-dot" style="--dot:#73a764"></span>Zones verdes OSM</button>
          <button class="eu-layer" data-layer="mobility" aria-pressed="false"><span class="eu-dot" style="--dot:#6d58a0"></span>Mobilitat OSM</button>
          <button class="eu-layer" data-layer="facilities" aria-pressed="true"><span class="eu-dot" style="--dot:#0b477d"></span>Equipaments OSM</button>
          <button class="eu-layer" data-layer="water" aria-pressed="true"><span class="eu-dot" style="--dot:#3f9ec0"></span>Aigua OSM</button>
          <button class="eu-layer" data-layer="roofs" aria-pressed="false"><span class="eu-dot" style="--dot:#e2a72f"></span>Cobertes solars</button>
        </div>
      </section>
    </aside>

    <section class="eu-map-panel" aria-label="Mapa interactiu EcoRadar Urbà de la Seu d'Urgell">
      <div class="eu-map-head"><div class="eu-map-label" id="eu-active-label">Mapa base verificat</div><button class="eu-reset" type="button">Restablir vista</button></div>
      <svg role="img" aria-label="Mapa de la Seu d'Urgell amb capes climàtiques, urbanes i de benestar"></svg>
      <div class="eu-map-note">El requadre blau inclou Castellciutat i Sant Antoni. El perill estructural oficial i el perill actual EcoRadar són lectures separades. Cap de les dues substitueix el Pla Alfa.</div>
      <div class="eu-tooltip"></div>
      <div class="eu-fire-popup" hidden aria-live="polite"></div>
    </section>

    <aside class="eu-column eu-right">
      <section class="eu-panel" id="eu-reading-guide" aria-live="polite">
        <h3>Com llegir la capa activa</h3>
        <div class="eu-guide-title" id="eu-guide-title"></div>
        <p class="eu-guide-copy" id="eu-guide-copy"></p>
        <div class="eu-guide-label">Clau de colors</div>
        <div class="eu-legend" id="eu-legend" role="list"></div>
        <p class="eu-guide-reading" id="eu-guide-reading"></p>
        <p class="eu-guide-limit" id="eu-guide-limit"></p>
        __BIODIVERSITY_DETAILS__
      </section>
      <section class="eu-panel eu-territory-panel">
        <h3>Àmbit territorial ampliat</h3>
        <div class="eu-facts">
          <div class="eu-fact"><span>Superfície del requadre</span><strong id="eu-area-value"></strong></div>
          <div class="eu-fact"><span>Nucli occidental inclòs</span><strong>Castellciutat</strong></div>
          <div class="eu-fact"><span>Barri septentrional inclòs</span><strong>Sant Antoni</strong></div>
        </div>
        <p class="eu-source">El requadre discontinu blau és operatiu, no un límit administratiu. Les capes LiDAR, Landsat, CLMS, incendi i els vectors s’han recalculat per a tot aquest àmbit.</p>
        <p class="eu-source">Els corredors de ventilació no es cartografien: relleu i edificis no substitueixen un camp de vent o una modelització CFD.</p>
      </section>
      __DAILY_READINGS__
      <div class="eu-summary-grid">
      <section class="eu-panel">
        <h3>Indicadors clau</h3>
        <div class="eu-facts">
          <div class="eu-fact"><span>Ombra LiDAR · càlcul diari 15 h</span><strong id="eu-shade-value"></strong></div>
          <div class="eu-fact"><span>Coberta de capçada LiDAR</span><strong id="eu-canopy-value"></strong></div>
          <div class="eu-fact"><span>Temperatura superficial mitjana</span><strong id="eu-lst-value"></strong></div>
          <div class="eu-fact"><span>Rang P10–P90 LST</span><strong id="eu-lst-range"></strong></div>
          <div class="eu-fact"><span>Edificis dins l’àmbit</span><strong id="eu-buildings-value"></strong></div>
        </div>
      </section>
      <section class="eu-panel">
        <h3>Indicadors Copernicus derivats</h3>
        <div class="eu-facts">
          <div class="eu-fact"><span>Illa de calor superficial</span><strong id="eu-uhi-value"></strong></div>
          <div class="eu-fact"><span>Impermeabilització mitjana</span><strong id="eu-imd-value"></strong></div>
          <div class="eu-fact"><span>Cobertura vegetal HRL</span><strong id="eu-veg-value"></strong></div>
          <div class="eu-fact"><span>Canvi TCD 2018–2023</span><strong id="eu-tree-value"></strong></div>
          <div class="eu-fact"><span>Escorrentia relativa</span><strong id="eu-runoff-value"></strong></div>
        </div>
        <p class="eu-source">SUHI diürna, cobertura i escorrentia són indicadors de cribratge. No equivalen a temperatura de l'aire, cabal ni impacte sanitari.</p>
      </section>
      <section class="eu-panel">
        <h3>Població i edat · municipi</h3>
        <div class="eu-fact"><span>Població 2025</span><strong>13.003</strong></div>
        <div class="eu-age" aria-label="Distribució de la població per edat"><span></span><span></span><span></span><span></span></div>
        <div class="eu-age-labels"><span>0–14 · 12,3 %</span><span>15–64 · 67,6 %</span><span>65–84 · 16,6 %</span><span>85+ · 3,5 %</span></div>
        <p><strong>2.617 persones (20,1 %)</strong> tenen 65 anys o més.</p>
        <p class="eu-source">Idescat, a partir del Cens de població anual de l'INE. Dada agregada municipal, no assignada a carrers.</p>
      </section>
      __SENTINEL_FACTS__
      __FIRE_FACTS__
      __CURRENT_FIRE_FACTS__
      __CONTEXTUAL_FACTS__
      <section class="eu-panel eu-warning">
        <h3>Cobertes solars · preselecció</h3>
        <div class="eu-facts">
          <div class="eu-fact"><span>Edificis analitzats</span><strong id="eu-roofs-value"></strong></div>
          <div class="eu-fact"><span>Geometria favorable</span><strong id="eu-roofs-favorable"></strong></div>
          <div class="eu-fact"><span>Geometria condicionada</span><strong id="eu-roofs-conditioned"></strong></div>
        </div>
        <p class="eu-source">Cribratge de pendent i orientació amb Cadastre + LiDAR. Requereix verificació estructural, normativa i energètica.</p>
      </section>
      </div>
    </aside>

    <footer class="eu-foot"><span>Fonts: ICGC · Cadastre · USGS Landsat · Copernicus CLMS/CAMS · Meteocat XEMA · Idescat/INE · MITECO-SNCZI · Generalitat (perill d’incendi 2024) · OpenStreetMap</span><span>EcoRadar Urbà · projecte verificable</span></footer>
  </main>
</div>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
(() => {
  const root = document.getElementById('ecoradar-urba-la-seu');
  const D = __ECORADAR_DATA__;
  const dataDate = key => {
    const raw=D.dailyReadings?.readings?.[key]?.data_at_utc;
    if(!raw) return 'dada no disponible';
    const [y,m,d]=raw.slice(0,10).split('-');
    return `${d}/${m}/${y}`;
  };
  const svg = d3.select(root).select('svg');
  const tooltip = d3.select(root).select('.eu-tooltip');
  const firePopup = root.querySelector('.eu-fire-popup');
  const width = 1000, height = 720;
  svg.attr('viewBox', `0 0 ${width} ${height}`).attr('preserveAspectRatio','xMidYMid meet');
  svg.append('rect').attr('class','eu-map-bg').attr('width',width).attr('height',height);
  const bboxFeature = {type:'Feature',geometry:{type:'Polygon',coordinates:[[[D.bbox[0],D.bbox[1]],[D.bbox[0],D.bbox[3]],[D.bbox[2],D.bbox[3]],[D.bbox[2],D.bbox[1]],[D.bbox[0],D.bbox[1]]]]}};
  const projection = d3.geoMercator().fitExtent([[12,12],[width-12,height-12]],bboxFeature);
  const path = d3.geoPath(projection);
  const scene = svg.append('g');
  const rasterGroup = scene.append('g').attr('class','eu-rasters');
  const vectorGroup = scene.append('g').attr('class','eu-vectors');

  const rasterBboxes = {shade:D.lidarBbox,canopy:D.lidarBbox,slope:D.lidarBbox,lst:D.lstBbox,uhi:D.lstBbox,flood:D.floodBbox,fireDanger:D.fireBbox,fireCurrent:D.indicatorBbox,impervious:D.indicatorBbox,vegetation:D.indicatorBbox,treeChange:D.indicatorBbox,runoff:D.indicatorBbox,ndvi:D.indicatorBbox,ndmi:D.indicatorBbox,albedo:D.indicatorBbox,biodiversity:D.indicatorBbox,biodiversityGreen:D.indicatorBbox,biodiversityFluvial:D.indicatorBbox,biodiversityIsolated:D.indicatorBbox,biodiversityBarrier:D.indicatorBbox,biodiversityPriority:D.indicatorBbox};
  const rasterLabels = {none:'Mapa base verificat',lst:`Temperatura superficial · Landsat · ${dataDate('surface_temperature')}`,uhi:'Illa de calor superficial · proxy diürn',shade:`Ombra directa · LiDAR · ${dataDate('shade')} 15.00 h`,canopy:'Coberta de capçada · LiDAR',vegetation:'Cobertura vegetal · CLMS HRL 2023',treeChange:'Canvi de densitat arbòria · CLMS 2018–2023',impervious:'Impermeabilització · CLMS HRL 2021',runoff:'Escorrentia potencial · índex relatiu',slope:'Pendent del terreny · LiDAR',flood:'Inundabilitat fluvial · SNCZI · T=100 anys',fireDanger:'Perill estructural d’incendi · Generalitat 2024',fireCurrent:'Perill d’incendi actual · índex EcoRadar derivat',ndvi:'NDVI · Sentinel-2 L2A',ndmi:'NDMI · Sentinel-2 L2A',albedo:'Albedo urbà estimat · Sentinel-2 L2A',biodiversity:'Biodiversitat urbana · potencial i seguiments locals'};
  const legends={none:[['#d2cdc2','Gris · edificis Cadastre'],['#73a764','Verd · zones verdes OSM'],['#68b5d1','Blau · aigua OSM']],lst:[['#2a7f60','Verd fosc · ≤ 40 °C'],['#facc46','Groc · 44–48 °C'],['#d64127','Vermell · ≥ 52 °C']],uhi:[['#2c6b96','Blau · més fresca que la referència'],['#efeddb','Clar · temperatura semblant'],['#a52b2d','Vermell fosc · més calenta']],shade:[['#88bfd3','Blau clar · ombra parcial'],['#0a3d70','Blau fosc · ombra alta']],canopy:[['#9dca83','Verd clar · capçada baixa'],['#17683d','Verd fosc · capçada alta']],vegetation:[['#ece9de','Clar · sense cobertura HRL'],['#3f8442','Verd · cobertura vegetal']],treeChange:[['#972a2a','Vermell · pèrdua ≥10 pp'],['#e7e5da','Clar · situació estable'],['#18693f','Verd · guany ≥10 pp']],impervious:[['#eeefe2','Clar · 0–10 %'],['#eeb85c','Taronja · 30–60 %'],['#89212e','Vermell fosc · 60–100 %']],runoff:[['#367fa3','Blau · potencial baix'],['#cbcd7e','Groc verdós · potencial mitjà'],['#d55a32','Taronja fosc · potencial alt']],slope:[['#b8d5a3','Verd clar · ≤ 5°'],['#f0d36f','Groc · 15–30°'],['#8e5541','Marró fosc · ≥ 50°']],flood:[['#e8beff','Lila · làmina modelada T=100']],fireDanger:[['#2c7bb6','Blau · nivells relatius 1–3'],['#f0e65b','Groc · nivells 4–6'],['#f39a38','Taronja · nivells 7–8'],['#8b1e2d','Vermell fosc · nivells 9–10']],ndvi:[['#80583d','Marró · ≤ 0,1'],['#bcd37d','Verd clar · 0,3–0,55'],['#165e32','Verd fosc · ≥ 0,85']],ndmi:[['#a6572f','Marró · estrès hídric relatiu'],['#e1da9d','Clar · estat intermedi'],['#226691','Blau fosc · humitat relativa alta']],albedo:[['#2d3b47','Fosc · ≤ 0,05'],['#9fa397','Gris · entorn de 0,20'],['#f9efcf','Clar · ≥ 0,45']],biodiversity:[['#e8dfc6','Clar · potencial relatiu baix'],['#1c6241','Verd fosc · potencial alt / corredor verd'],['#3080a1','Blau · corredor fluvial potencial'],['#cf8f37','Taronja · espai verd potencialment aïllat'],['#4c4e4e','Gris · barrera urbana estructural'],['#69409a','Violeta · prioritat de validació de camp']]};
  legends.biodiversity=[['linear-gradient(90deg,#e8dfc6,#1c6241)','Gradient · potencial ecològic 0–100'],['#1c6241','Diagonal verda · corredor verd'],['#3080a1','Diagonal blava · corredor fluvial'],['#cf8f37','Punts taronja · espai aïllat'],['#4c4e4e','Barres grises · barrera urbana'],['#69409a','Creus violetes · validació de camp']];
  legends.fireCurrent=[['#2f8f4e','0–20 · molt baix'],['#a8c94a','21–40 · baix'],['#f0d84b','41–60 · moderat'],['#ef8b2c','61–80 · alt'],['#d43d2f','81–90 · molt alt'],['#711d2d','91–100 · extrem']];
  const modeGuides={
    none:{title:'Mapa base i capes de context',copy:'Mostra l’estructura física sobre la qual es projecten les lectures ambientals: edificis, zones verdes, aigua i equipaments.',reading:'Els colors identifiquen tipus d’element, no una escala de millor o pitjor qualitat.',limit:'Límit: OSM i Cadastre són bases de context; una zona verda cartografiada no implica necessàriament accés públic, ombra o qualitat ecològica.'},
    lst:{title:'Temperatura superficial diürna',copy:`Representa la temperatura de la superfície estimada per Landsat durant el pas del satèl·lit del ${dataDate('surface_temperature')}.`,reading:'Els tons verds indiquen superfícies relativament més fresques; els grocs i taronges, més calentes; els vermells foscos, els valors més elevats de l’escena.',limit:'Límit: no és temperatura de l’aire, sensació tèrmica, exposició personal ni una mitjana estacional.'},
    uhi:{title:'Illa de calor superficial',copy:'Compara les superfícies urbanes impermeables amb una referència vegetada de baixa impermeabilització dins el mateix àmbit.',reading:'El blau assenyala valors inferiors a la referència; els tons clars, valors semblants; el vermell fosc, una temperatura superficial clarament superior.',limit:'Límit: és un proxy diürn d’una sola escena, no una illa de calor atmosfèrica o nocturna.'},
    shade:{title:'Ombra directa modelada amb LiDAR',copy:`Estima quines superfícies queden protegides de la radiació solar directa el ${dataDate('shade')} a les 15.00 h, considerant data, hora, posició solar, relleu, edificis i arbres LiDAR.`,reading:'El blau clar indica ombra parcial i el blau fosc una obstrucció solar més alta en aquell instant.',limit:'Límit: no representa l’ombra de tot el dia ni el confort tèrmic fisiològic; la geometria LiDAR es manté fins que se’n publica una actualització estructural.'},
    canopy:{title:'Coberta de capçada',copy:'Localitza la presència i densitat relativa de capçades a partir de les classes de vegetació del LiDAR de l’ICGC.',reading:'El verd clar correspon a presència baixa o dispersa; el verd fosc, a una cobertura de capçada més alta.',limit:'Límit: no identifica espècies, estat sanitari, propietat, accessibilitat ni ombra real a nivell de vianant.'},
    vegetation:{title:'Cobertura vegetal Copernicus',copy:'Combina presència arbòria i coberta herbàcia del producte CLMS HRL 2023 per mostrar superfícies vegetades.',reading:'Els tons clars indiquen absència de cobertura detectada; el verd identifica presència vegetal.',limit:'Límit: és una classificació de cobertura, no mesura biodiversitat, qualitat ecològica, ús públic ni reg.'},
    treeChange:{title:'Canvi de densitat arbòria 2018–2023',copy:'Compara la densitat de coberta arbòria de Copernicus entre 2018 i 2023. No s’etiqueta com a canvi fins a 2025 perquè aquesta dada no estava disponible.',reading:'El vermell mostra pèrdues d’almenys 10 punts percentuals; el clar, estabilitat; el verd, guanys d’almenys 10 punts.',limit:'Límit: part del canvi aparent pot provenir de diferències de classificació entre productes.'},
    impervious:{title:'Impermeabilització del sòl',copy:'Expressa el percentatge de superfície segellada o impermeable estimat per Copernicus HRL 2021.',reading:'Els tons clars indiquen poca impermeabilització; el taronja, valors intermedis; el vermell fosc, superfícies molt segellades.',limit:'Límit: un valor alt suggereix més acumulació de calor i menys infiltració, però no determina per si sol risc sanitari o hidrològic.'},
    runoff:{title:'Escorrentia potencial relativa',copy:'Índex de cribratge que combina impermeabilització Copernicus i pendent LiDAR per identificar on l’aigua podria generar més escorrentia superficial.',reading:'El blau indica potencial relatiu baix; el groc verdós, intermedi; el taronja fosc, més alt.',limit:'Límit: no és un model hidrològic; no incorpora pluja de disseny, sòls, clavegueram, cabals ni calibratge.'},
    slope:{title:'Pendent del terreny',copy:'Mostra la inclinació del model digital del terreny derivat del LiDAR de l’ICGC, expressada en graus.',reading:'El verd clar correspon a superfícies planes o suaus; el groc, a pendents moderats; el marró fosc, a pendents molt forts.',limit:'Límit: el pendent no descriu per si sol accessibilitat, estat del paviment, escales, amplada o risc de caiguda.'},
    flood:{title:'Inundabilitat fluvial T=100 anys',copy:'Representa la làmina oficial del SNCZI per a l’escenari de període de retorn de 100 anys.',reading:'El color lila delimita l’extensió que el model oficial identifica com a inundable en aquest escenari.',limit:'Límit: no és una alerta en temps real ni garanteix absència de risc fora de la làmina cartografiada.'},
    fireDanger:{title:'Perill estructural d’incendi forestal',copy:'Mostra el Mapa bàsic de perill d’incendi forestal 2024 de la Generalitat, en cel·les oficials de 100 m i escala relativa d’1 a 10.',reading:'El blau indica nivells estructurals baixos; el groc, intermedis; el taronja i el vermell fosc, nivells alts o molt alts.',limit:'Límit: no és el perill diari, una probabilitat d’ignició, un incendi actiu ni una alerta d’emergència.'},
    fireCurrent:{title:'Perill d’incendi actual · índex EcoRadar',copy:'Combina el perill estructural, la sequedat NDMI, la temperatura superficial, la continuïtat vegetal, el pendent, l’orientació i les darreres observacions reals de vent i humitat XEMA.',reading:'Es representa com una superfície raster contínua amb la mateixa configuració visual del mapa de perill estructural. El verd indica perill baix; el groc, moderat; el taronja, alt; i el vermell o granat, molt alt o extrem.',limit:'Límit: el gradient és una representació espacial interpolada d’un índex EcoRadar derivat. No és una alerta oficial i no substitueix el Pla Alfa o el mapa diari oficial.'},
    ndvi:{title:'NDVI · vigor espectral de la vegetació',copy:'Índex Sentinel-2 calculat amb B08 i B04. Valors alts solen correspondre a vegetació fotosintèticament activa; valors baixos, a sòl nu, superfícies construïdes o aigua.',reading:'El marró indica NDVI baix; el verd clar, vigor intermedi; el verd fosc, valors molt alts.',limit:'Límit: no mesura directament biodiversitat, salut de cada arbre ni qualitat ecològica i pot saturar-se en vegetació densa.'},
    ndmi:{title:'NDMI · humitat relativa de la vegetació',copy:'Índex Sentinel-2 calculat amb B08 i B11 que respon al contingut d’aigua de la vegetació i a l’estrès hídric relatiu.',reading:'El marró suggereix més estrès relatiu; els tons clars, una situació intermèdia; el blau fosc, valors d’humitat relativa més alts.',limit:'Límit: no és humitat volumètrica del sòl, demanda de reg ni una mesura de camp.'},
    albedo:{title:'Albedo espectral estimat',copy:'Estima la fracció de radiació solar reflectida combinant bandes Sentinel-2 amb una fórmula narrow-to-broadband publicada.',reading:'Els tons foscos indiquen menor reflectància i major absorció relativa; els tons clars, més reflectància.',limit:'Límit: és una estimació espectral, no una mesura radiomètrica de camp; un albedo alt no implica per si sol més confort.'},
    biodiversity:{title:'Biodiversitat urbana · potencial ecològic',copy:'Integra cinc components verificats amb el mateix pes: vegetació, arbrat, continuïtat verda en una finestra aproximada de 210 m, proximitat a l’aigua i permeabilitat del sòl.',reading:'El gradient clar–verd és el potencial general. Les trames transparents s’hi superposen: diagonal verda i blava per als corredors, punts taronja per als espais aïllats, barres grises per a les barreres i creus violetes per a la validació de camp.',limit:'Límit: el CBMS correspon només a l’itinerari 168; les caixes no confirmen ocupació i els ocells resten pendents d’integració quantitativa. El mapa continua sent potencial calculat.'}
  };
  const rasters = {};
  Object.entries(D.rasters).forEach(([key,href]) => {
    const b = rasterBboxes[key]; const p0 = projection([b[0],b[3]]), p1 = projection([b[2],b[1]]);
    rasters[key] = rasterGroup.append('image').attr('href',href).attr('x',p0[0]).attr('y',p0[1]).attr('width',p1[0]-p0[0]).attr('height',p1[1]-p0[1]).attr('preserveAspectRatio','none').style('display','none').style('pointer-events','none');
  });

  const groups = {};
  groups.green = vectorGroup.append('g').selectAll('path').data(D.vectors.green.features).join('path').attr('class','eu-green').attr('d',path).on('mousemove',event => showTip(event,'Zona verda OSM')).on('mouseleave',hideTip);
  groups.water = vectorGroup.append('g');
  groups.water.selectAll('path').data(D.vectors.water.features).join('path').attr('class',d=>`eu-water ${d.geometry.type.includes('Polygon')?'area':'line'}`).attr('d',path);
  groups.buildings = vectorGroup.append('g').selectAll('path').data(D.vectors.buildings.features).join('path').attr('class','eu-building').attr('d',path).on('mousemove',(event,d)=>showTip(event,`${d.properties.cadastre_id || 'Edifici cadastral'}<br>${d.properties.footprint_m2 || '—'} m² de petjada`)).on('mouseleave',hideTip);
  groups.mobility = vectorGroup.append('g').style('display','none');
  groups.mobility.selectAll('path').data(D.vectors.mobility.features).join('path').attr('class',d=>`eu-road ${d.properties.mode || 'viaria'}`).attr('d',path).on('mousemove',(event,d)=>showTip(event,`${d.properties.name || 'Tram OSM'}<br>${d.properties.mode || 'mobilitat'}`)).on('mouseleave',hideTip);
  groups.roofs = vectorGroup.append('g').style('display','none');
  groups.roofs.selectAll('path').data(D.vectors.buildings.features.filter(d=>d.properties.solar_screen)).join('path').attr('class',d=>`eu-roof ${d.properties.solar_screen}`).attr('d',path).on('mousemove',(event,d)=>showTip(event,`Coberta ${d.properties.solar_screen}<br>Pendent ${d.properties.median_slope_deg}° · orientació ${d.properties.mean_aspect_deg}°`)).on('mouseleave',hideTip);
  groups.facilities = vectorGroup.append('g').selectAll('circle').data(D.vectors.facilities.features).join('circle').attr('class','eu-facility').attr('cx',d=>projection(d.geometry.coordinates)[0]).attr('cy',d=>projection(d.geometry.coordinates)[1]).attr('r',3.4).on('mousemove',(event,d)=>showTip(event,`${d.properties.name || 'Equipament'}<br>${d.properties.kind || ''}`)).on('mouseleave',hideTip);

  const lb = D.expandedBbox;
  const core = {type:'Feature',geometry:{type:'Polygon',coordinates:[[[lb[0],lb[1]],[lb[0],lb[3]],[lb[2],lb[3]],[lb[2],lb[1]],[lb[0],lb[1]]]]}};
  vectorGroup.append('path').datum(core).attr('class','eu-boundary').attr('d',path).style('pointer-events','none');
  const placeGroup = vectorGroup.append('g');
  const placePoints = placeGroup.selectAll('g').data(D.places).join('g').attr('transform',d=>`translate(${projection(d.coordinates_epsg4326).join(',')})`);
  placePoints.append('circle').attr('class','eu-place').attr('r',4.2);
  placePoints.append('text').attr('class','eu-place-label').attr('x',7).attr('y',-7).text(d=>d.name.replace(' · la Seu d\'Urgell','').replace(' · les Valls de Valira',''));
  groups.fireCurrent=vectorGroup.append('g').style('display','none');
  function renderCurrentFireCells(cells){
    groups.fireCurrent.selectAll('*').remove();
    if(!cells?.features) return;
    groups.fireCurrent.append('g').selectAll('path').data(cells.features).join('path')
      .attr('class','eu-fire-cell').attr('d',path).attr('tabindex',0)
      .attr('aria-label',d=>`Cel·la ${d.properties.cell_id}: ${d.properties.index_0_100} sobre 100, ${d.properties.category}`)
      .on('mousemove',(event,d)=>showTip(event,`${d.properties.index_0_100}/100 · ${d.properties.category}<br>Confiança ${d.properties.confidence_pct}%`))
      .on('mouseleave',hideTip)
      .on('click',(event,d)=>{event.stopPropagation();showFirePopup(d.properties);})
      .on('keydown',(event,d)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();showFirePopup(d.properties);}});
  }
  if(D.currentFire) renderCurrentFireCells(D.currentFire.cells);

  const north = svg.append('g').attr('transform','translate(946 70)'); north.append('path').attr('d','M0,24 L0,-16 M0,-16 L-6,-5 M0,-16 L6,-5').attr('stroke','#173249').attr('stroke-width',2).attr('fill','none'); north.append('text').attr('y',-25).attr('text-anchor','middle').attr('font-size',13).attr('font-weight',700).text('N');
  let activeMode='none';
  const ca1=value=>Number(value).toFixed(1).replace('.',',');
  const caInt=value=>Number(value).toLocaleString('ca-ES');
  root.querySelector('#eu-area-value').textContent=`${ca1(D.metrics.studyAreaHa)} ha`;
  root.querySelector('#eu-shade-value').textContent=`${ca1(D.metrics.shade)} %`;
  root.querySelector('#eu-canopy-value').textContent=`${ca1(D.metrics.canopy)} %`;
  root.querySelector('#eu-lst-value').textContent=`${ca1(D.metrics.lstMean)} °C`;
  root.querySelector('#eu-lst-range').textContent=`${ca1(D.metrics.lstP10)}–${ca1(D.metrics.lstP90)} °C`;
  root.querySelector('#eu-buildings-value').textContent=caInt(D.metrics.buildings);
  root.querySelector('#eu-roofs-value').textContent=caInt(D.metrics.roofEvaluated);
  root.querySelector('#eu-roofs-favorable').textContent=caInt(D.metrics.roofFavorable);
  root.querySelector('#eu-roofs-conditioned').textContent=caInt(D.metrics.roofConditioned);
  root.querySelector('#eu-uhi-value').textContent=`+${D.metrics.surfaceUhi.toFixed(1).replace('.',',')} °C`;
  root.querySelector('#eu-imd-value').textContent=`${D.metrics.imperviousMean.toFixed(1).replace('.',',')} %`;
  root.querySelector('#eu-veg-value').textContent=`${D.metrics.vegetationCover.toFixed(1).replace('.',',')} %`;
  root.querySelector('#eu-tree-value').textContent=`${D.metrics.treeChange>=0?'+':''}${D.metrics.treeChange.toFixed(1).replace('.',',')} pp`;
  root.querySelector('#eu-runoff-value').textContent=`${D.metrics.runoffProxy.toFixed(1).replace('.',',')} / 100`;

  const historyReading=root.querySelector('#eu-history-reading');
  const historyDateA=root.querySelector('#eu-history-a');
  const historyDateB=root.querySelector('#eu-history-b');
  const historyComparison=root.querySelector('#eu-history-comparison');
  const historyChart=d3.select(root).select('#eu-history-chart');
  const readingLabel=key=>D.dailyReadings?.readings?.[key]?.label || key;
  const historyNumber=value=>Number(value).toLocaleString('ca-ES',{maximumFractionDigits:3});
  function historyStamp(value){
    return new Intl.DateTimeFormat('ca-ES',{dateStyle:'short',timeStyle:'short',timeZone:'UTC'}).format(new Date(value))+' UTC';
  }
  function drawHistory(key){
    if(!historyReading || historyChart.empty()) return;
    const raw=(D.dailyHistory?.series?.[key] || []).filter(d=>d.value_numeric!=null && d.data_at_utc);
    const series=raw.map(d=>({...d,date:new Date(d.data_at_utc),number:Number(d.value_numeric)})).filter(d=>Number.isFinite(d.number) && !Number.isNaN(d.date.valueOf()));
    historyChart.selectAll('*').remove();
    const W=Math.max(320,Math.round(historyChart.node()?.getBoundingClientRect().width || 320));
    const H=Math.max(200,Math.round(historyChart.node()?.getBoundingClientRect().height || 250)),M={top:18,right:20,bottom:38,left:52};
    historyChart.attr('viewBox',`0 0 ${W} ${H}`).attr('preserveAspectRatio','xMidYMid meet').attr('aria-label',`Evolució de ${readingLabel(key)} amb ${series.length===1?'1 observació':series.length+' observacions'}`);
    if(!series.length){
      historyChart.append('text').attr('x',W/2).attr('y',H/2).attr('text-anchor','middle').attr('fill','#5b6973').attr('font-size',10).text('No hi ha observacions històriques');
      historyDateA.innerHTML=''; historyDateB.innerHTML=''; historyComparison.textContent='No hi ha dues dates disponibles per comparar.';
      return;
    }
    let xDomain=d3.extent(series,d=>d.date);
    if(+xDomain[0]===+xDomain[1]) xDomain=[new Date(+xDomain[0]-43200000),new Date(+xDomain[1]+43200000)];
    let yDomain=d3.extent(series,d=>d.number);
    const yPad=yDomain[0]===yDomain[1]?Math.max(Math.abs(yDomain[0])*.05,.5):(yDomain[1]-yDomain[0])*.08;
    yDomain=[yDomain[0]-yPad,yDomain[1]+yPad];
    const x=d3.scaleUtc().domain(xDomain).range([M.left,W-M.right]);
    const y=d3.scaleLinear().domain(yDomain).nice().range([H-M.bottom,M.top]);
    const xTicks=Math.max(4,Math.min(10,Math.floor(W/125)));
    historyChart.append('g').attr('transform',`translate(0,${H-M.bottom})`).call(d3.axisBottom(x).ticks(xTicks).tickFormat(d3.utcFormat('%d/%m'))).call(g=>g.selectAll('text').attr('font-size',8));
    historyChart.append('g').attr('transform',`translate(${M.left},0)`).call(d3.axisLeft(y).ticks(6).tickFormat(v=>historyNumber(v))).call(g=>g.selectAll('text').attr('font-size',8));
    historyChart.append('path').datum(series).attr('fill','none').attr('stroke','#216b4b').attr('stroke-width',1.8).attr('d',d3.line().x(d=>x(d.date)).y(d=>y(d.number)));
    const pointStep=Math.max(1,Math.ceil(series.length/100));
    const visiblePoints=series.filter((d,index)=>index%pointStep===0 || index===series.length-1);
    historyChart.selectAll('.eu-history-point').data(visiblePoints).join('circle').attr('class','eu-history-point').attr('cx',d=>x(d.date)).attr('cy',d=>y(d.number)).attr('r',series.length===1?3.5:1.7).attr('fill','#164f78').append('title').text(d=>`${historyStamp(d.data_at_utc)} · ${d.value}`);
    const options=series.map((d,index)=>`<option value="${index}">${historyStamp(d.data_at_utc)} · ${d.value}</option>`).join('');
    historyDateA.innerHTML=options; historyDateB.innerHTML=options;
    historyDateA.value=String(Math.max(0,series.length-2)); historyDateB.value=String(series.length-1);
    function compare(){
      if(series.length<2){historyComparison.innerHTML=`<strong>${readingLabel(key)}</strong><br>Només hi ha una observació registrada; encara no es pot comparar amb una data anterior.`;return;}
      const a=series[Number(historyDateA.value)], b=series[Number(historyDateB.value)];
      if(!a || !b){historyComparison.textContent='Selecciona dues observacions.';return;}
      const delta=b.number-a.number;
      const pct=a.number===0?null:delta/Math.abs(a.number)*100;
      const sign=delta>0?'+':'';
      historyComparison.innerHTML=`<strong>${readingLabel(key)}</strong><br>Data A: ${historyStamp(a.data_at_utc)} · ${a.value}<br>Data B: ${historyStamp(b.data_at_utc)} · ${b.value}<br>Variació: ${sign}${historyNumber(delta)}${a.unit?' '+a.unit:''}${pct==null?'':` · ${pct>=0?'+':''}${historyNumber(pct)} %`}`;
    }
    historyDateA.onchange=compare; historyDateB.onchange=compare; compare();
  }
  if(historyReading){ historyReading.addEventListener('change',()=>drawHistory(historyReading.value)); drawHistory(historyReading.value); }

  root.querySelectorAll('.eu-mode').forEach(button => button.addEventListener('click',() => {
    activeMode=button.dataset.mode; root.querySelectorAll('.eu-mode').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    Object.entries(rasters).forEach(([key,image])=>image.style('display',(activeMode==='biodiversity'?key.startsWith('biodiversity'):key===activeMode)?null:'none'));
    groups.fireCurrent.style('display',activeMode==='fireCurrent'?null:'none');
    if(activeMode!=='fireCurrent') firePopup.hidden=true;
    root.querySelector('#eu-active-label').textContent=rasterLabels[activeMode]; updateGuide();
  }));
  root.querySelectorAll('.eu-layer').forEach(button => button.addEventListener('click',() => {
    const key=button.dataset.layer, next=button.getAttribute('aria-pressed')!=='true'; button.setAttribute('aria-pressed',String(next)); groups[key].style('display',next?null:'none'); updateLegend();
  }));
  const zoom=d3.zoom().scaleExtent([1,12]).on('zoom',event=>scene.attr('transform',event.transform)); svg.call(zoom);
  root.querySelector('.eu-reset').addEventListener('click',()=>svg.transition().duration(350).call(zoom.transform,d3.zoomIdentity));

  function showTip(event,html){ const box=root.getBoundingClientRect(); tooltip.html(html).style('opacity',1).style('left',`${event.clientX-box.left+12}px`).style('top',`${event.clientY-box.top+12}px`); }
  function hideTip(){ tooltip.style('opacity',0); }
  const fmt=(value,decimals=1)=>value==null?'dada no disponible':Number(value).toFixed(decimals).replace('.',',');
  const humanDate=value=>value?new Intl.DateTimeFormat('ca-ES',{dateStyle:'short',timeStyle:'short',timeZone:'UTC'}).format(new Date(value))+' UTC':'dada no disponible';
  function showFirePopup(p){
    const r=p.raw,n=p.normalized,c=p.contributions,w=D.currentFire.weather;
    const dryness=n.ndmi_dryness==null?'dada no disponible':n.ndmi_dryness>=67?'seca':n.ndmi_dryness>=33?'intermèdia':'humida relativa';
    const rows=[
      ['Perill estructural',r.structural_1_10==null?'dada no disponible':`${fmt(r.structural_1_10)}/10`,n.structural,c.structural],
      ['NDMI',r.ndmi==null?'dada no disponible':`${fmt(r.ndmi,3)} · ${dryness}`,n.ndmi_dryness,c.ndmi_dryness],
      ['Temperatura superficial',r.surface_temperature_c==null?'dada no disponible':`${fmt(r.surface_temperature_c)} °C`,n.surface_temperature,c.surface_temperature],
      ['Coberta / continuïtat',r.vegetation_cover_pct==null?'dada no disponible':`${fmt(r.vegetation_cover_pct)} % / ${fmt(r.vegetation_continuity_pct)} %`,n.vegetation_continuity,c.vegetation_continuity],
      ['Pendent',r.slope_pct==null?'dada no disponible':`${fmt(r.slope_pct)} % (${fmt(r.slope_deg)}°)`,n.slope,c.slope],
      ['Orientació',`${r.aspect_cardinal} · ${r.aspect_exposure} · ${fmt(r.aspect_deg)}°`,n.aspect,c.aspect],
      ['Vent',r.wind_speed_kmh==null?'dada no disponible':`${fmt(r.wind_speed_kmh)} km/h`,n.wind,c.wind],
      ['Humitat relativa',r.relative_humidity_pct==null?'dada no disponible':`${fmt(r.relative_humidity_pct,0)} %`,n.relative_humidity_inverse,c.relative_humidity_inverse]
    ];
    const meteo=[];
    if(w.daily_max_wind_gust_ms!=null) meteo.push(`Ratxa màxima del dia: ${fmt(w.daily_max_wind_gust_ms*3.6)} km/h`);
    if(w.wind_direction_deg?.value!=null) meteo.push(`Direcció del vent: ${fmt(w.wind_direction_deg.value,0)}°`);
    if(w.daily_min_relative_humidity_pct!=null) meteo.push(`Humitat mínima del dia: ${fmt(w.daily_min_relative_humidity_pct,0)} %`);
    const explanation=`El valor ${p.category} s’explica principalment per ${p.dominant_labels.map(v=>v.toLowerCase()).join(', ')}. ${p.complete?'Les vuit variables disposen de valor en aquesta cel·la.':`La lectura és incompleta i s’ha recalculat amb el ${fmt(p.available_weight_pct)} % del pes disponible.`}`;
    const sourceNames={structural:'Perill estructural',ndmi_dryness:'NDMI',surface_temperature:'Temperatura superficial',vegetation_continuity:'Coberta vegetal',wind:'Vent',relative_humidity_inverse:'Humitat relativa',slope:'Pendent',aspect:'Orientació'};
    firePopup.innerHTML=`<button class="eu-fire-popup-close" type="button" aria-label="Tancar">×</button><h3>ÍNDEX ECORADAR</h3><div class="eu-fire-popup-main"><strong>${fmt(p.index_0_100)}/100</strong><span>${p.category}</span></div><div>Actualització: ${humanDate(p.updated_at_utc)} · confiança ${p.confidence} (${fmt(p.confidence_pct)} %)</div><h4>Variables de la cel·la</h4><table><thead><tr><th>Variable</th><th>Valor real</th><th>0–100</th><th>Aportació</th></tr></thead><tbody>${rows.map(row=>`<tr><th>${row[0]}</th><td>${row[1]}</td><td>${fmt(row[2])}</td><td>${row[3]==null?'dada no disponible':`${fmt(row[3])} punts`}</td></tr>`).join('')}</tbody></table><p>${meteo.join(' · ')}</p><h4>Variables dominants</h4><p>${p.dominant_labels.map(label=>`✓ ${label}`).join('<br>')}</p><h4>Explicació</h4><p>${explanation}</p><h4>Data de cada font</h4><p>${Object.entries(p.source_dates).map(([key,value])=>`${sourceNames[key]}: ${humanDate(value)}`).join('<br>')}</p><p><strong>No és una alerta oficial ni substitueix el Pla Alfa.</strong></p>`;
    firePopup.hidden=false;
    firePopup.querySelector('.eu-fire-popup-close').addEventListener('click',()=>{firePopup.hidden=true;});
  }
  function updateGuide(){
    const guide=modeGuides[activeMode];
    root.querySelector('#eu-guide-title').textContent=guide.title;
    root.querySelector('#eu-guide-copy').textContent=guide.copy;
    root.querySelector('#eu-guide-reading').textContent=guide.reading;
    root.querySelector('#eu-guide-limit').textContent=guide.limit;
    root.querySelector('#eu-biodiversity-details').hidden=activeMode!=='biodiversity';
    root.querySelectorAll('[data-current-fire]').forEach(panel=>panel.hidden=activeMode!=='fireCurrent');
    updateLegend();
  }
  function updateLegend(){
    let rows=legends[activeMode].slice(); if(root.querySelector('[data-layer="roofs"]').getAttribute('aria-pressed')==='true') rows.push(['#1b8b55','Coberta favorable'],['#e2a72f','Condicionada'],['#c95a47','Baixa']);
    root.querySelector('#eu-legend').innerHTML=rows.map(([c,l])=>`<div class="eu-legend-row" role="listitem"><span class="eu-swatch" style="background:${c}"></span>${l}</div>`).join('');
  }

  function updateDailyRow(key,item,analytics){
    const row=root.querySelector(`[data-reading-key="${key}"]`);
    if(!row) return;
    const field=(name)=>row.querySelector(`[data-reading-field="${name}"]`);
    field('label').textContent=item.label;
    field('value').textContent=item.value;
    const status=field('status');
    status.textContent=item.status;
    status.className=`eu-daily-status ${item.status_code}`;
    field('source').textContent=item.source;
    field('data-at').textContent=humanDate(item.data_at_utc);
    field('checked-at').textContent=humanDate(item.checked_at_utc);
    field('note').textContent=item.note;
    const trend=analytics?.trend || {symbol:'→',label:'sense comparació',variation_pct:null};
    field('trend').textContent=`${trend.symbol} ${trend.label}`;
    field('variation').textContent=trend.variation_pct==null?'—':`${trend.variation_pct>=0?'+':''}${fmt(trend.variation_pct)} %`;
    const confidence=analytics?.confidence || {score_pct:0,label:'Baixa'};
    field('confidence-score').textContent=`Confiança ${confidence.score_pct} %`;
    field('confidence-label').textContent=confidence.label;
    const confidenceBox=field('confidence-score').parentElement;
    confidenceBox.className=`eu-confidence ${String(confidence.label).toLowerCase()}`;
    field('frequency').textContent=analytics?.frequency?.frequency_label || 'no definida';
    field('trigger').textContent=analytics?.frequency?.trigger || '—';
    row.querySelectorAll('.eu-reading-alert').forEach(node=>node.remove());
    const alerts=analytics?.alerts || [];
    row.classList.toggle('has-alert',alerts.length>0);
    const note=field('note');
    alerts.forEach(alert=>{
      const box=document.createElement('div');
      box.className=`eu-reading-alert ${alert.level}`;
      const title=document.createElement('strong');
      title.textContent=`Alerta · ${alert.label}`;
      const basis=document.createElement('span');
      basis.textContent=alert.basis;
      box.append(title,basis);
      note.before(box);
    });
  }

  function updateSourceChecks(sourceChecks){
    const list=root.querySelector('#eu-source-check-list');
    if(!list) return;
    list.replaceChildren();
    Object.values(sourceChecks || {}).forEach(item=>{
      const row=document.createElement('div');
      row.className='eu-source-check';
      const label=document.createElement('span');
      label.textContent=item.label;
      const status=document.createElement('b');
      status.className=item.status;
      status.textContent=item.status;
      const detail=document.createElement('small');
      detail.textContent=`Comprovació: ${humanDate(item.checked_at_utc)} · dada: ${humanDate(item.data_at_utc)} · ${item.note}`;
      row.append(label,status,detail);
      list.append(row);
    });
  }

  function updateFireSummary(fire){
    if(!fire?.summary) return;
    const summary=fire.summary;
    const set=(name,value)=>{const node=root.querySelector(`[data-fire-summary="${name}"]`);if(node)node.textContent=value;};
    set('mean',`${fmt(summary.mean_index_0_100)}/100`);
    set('category',summary.predominant_category);
    set('maximum',`${fmt(summary.maximum_index_0_100)} · ${summary.maximum_category}`);
    set('very-high',`${fmt(summary.very_high_or_extreme_area_pct)} %`);
    set('confidence',`${summary.confidence} · ${fmt(summary.confidence_pct)} %`);
  }

  async function applyRemoteDailySnapshot(payload){
    const daily=payload.daily_readings;
    const history=payload.daily_history;
    if(!daily?.checked_at_utc || !daily?.readings || !history?.analytics) throw new Error('Resposta dinàmica incompleta');
    D.dailyReadings=daily;
    D.dailyHistory=history;
    Object.entries(daily.readings).forEach(([key,item])=>updateDailyRow(key,item,history.analytics[key]));
    Object.entries(daily.status_counts || {}).forEach(([key,value])=>{
      const node=root.querySelector(`[data-count="${key}"]`);
      if(node) node.textContent=value;
    });
    const alertSummary=root.querySelector('#eu-alert-summary');
    if(alertSummary){
      alertSummary.replaceChildren();
      const title=document.createElement('strong');
      const alerts=history.active_alerts || [];
      title.textContent=alerts.length?'Alertes actives':'Sense alertes actives amb els llindars definits';
      alertSummary.append(title);
      alertSummary.className=`eu-alert-summary${alerts.length?'':' clear'}`;
      alerts.forEach(alert=>{
        const item=document.createElement('span');
        item.className=alert.level;
        item.textContent=`${daily.readings[alert.reading]?.label || alert.reading} · ${alert.label}`;
        alertSummary.append(item);
      });
    }
    updateSourceChecks(payload.source_checks);
    const liveStatus=root.querySelector('#eu-live-status');
    liveStatus.className='eu-live-status';
    liveStatus.textContent=`Dades remotes verificades · última comprovació automàtica ${humanDate(payload.checked_at_utc)}`;
    const checkMeta=root.querySelector('[data-live-check-meta]');
    if(checkMeta) checkMeta.textContent=`comprovació ${humanDate(payload.checked_at_utc)}`;

    const surface=daily.readings.surface_temperature;
    const surfaceMeta=root.querySelector('[data-reading-meta="surface_temperature"]');
    if(surfaceMeta) surfaceMeta.textContent=`Landsat · ${surface?.data_at_utc?dataDate('surface_temperature'):'dada no disponible'}`;
    const shade=daily.readings.shade;
    const shadeMeta=root.querySelector('[data-reading-meta="shade"]');
    if(shadeMeta) shadeMeta.textContent=shade?.data_at_utc?`${dataDate('shade')} · 15.00 h`:'dada no disponible';
    if(shade?.value_numeric!=null){
      D.metrics.shade=Number(shade.value_numeric);
      root.querySelector('#eu-shade-value').textContent=`${ca1(D.metrics.shade)} %`;
    }
    if(surface?.value_numeric!=null){
      D.metrics.lstMean=Number(surface.value_numeric);
      root.querySelector('#eu-lst-value').textContent=`${ca1(D.metrics.lstMean)} °C`;
    }
    rasterLabels.lst=`Temperatura superficial · Landsat · ${dataDate('surface_temperature')}`;
    rasterLabels.shade=`Ombra directa · LiDAR · ${dataDate('shade')} 15.00 h`;
    modeGuides.lst.copy=`Representa la temperatura de la superfície estimada per Landsat durant el pas del satèl·lit del ${dataDate('surface_temperature')}.`;
    modeGuides.shade.copy=`Estima quines superfícies queden protegides de la radiació solar directa el ${dataDate('shade')} a les 15.00 h, considerant data, hora, posició solar, relleu, edificis i arbres LiDAR.`;

    if(payload.current_fire_danger){
      D.currentFire={...(D.currentFire || {}),summary:payload.current_fire_danger.summary,weather:payload.current_fire_danger.weather};
      updateFireSummary(payload.current_fire_danger);
    }
    if(payload.assets?.current_fire_png_url && rasters.fireCurrent){
      rasters.fireCurrent.attr('href',`${payload.assets.current_fire_png_url}?checked=${encodeURIComponent(payload.fire_checked_at_utc || payload.checked_at_utc)}`);
    }
    if(payload.assets?.current_fire_cells_url){
      try{
        const response=await fetch(`${payload.assets.current_fire_cells_url}?checked=${encodeURIComponent(payload.fire_checked_at_utc || payload.checked_at_utc)}`,{cache:'no-store'});
        if(response.ok){
          const cells=await response.json();
          D.currentFire={...(D.currentFire || {}),cells};
          renderCurrentFireCells(cells);
        }
      }catch(_error){
        // La lectura i la data continuen sent remotes; només la geometria conserva la reserva empaquetada.
      }
    }
    if(historyReading){
      const selected=historyReading.value;
      drawHistory(selected);
    }
    if(activeMode in rasterLabels) root.querySelector('#eu-active-label').textContent=rasterLabels[activeMode];
    updateGuide();
  }

  async function refreshDailySnapshot(){
    const liveStatus=root.querySelector('#eu-live-status');
    if(!liveStatus) return;
    try{
      const response=await fetch('/api/daily-readings',{cache:'no-store',headers:{accept:'application/json'}});
      if(!response.ok) throw new Error(`HTTP ${response.status}`);
      await applyRemoteDailySnapshot(await response.json());
    }catch(error){
      liveStatus.className='eu-live-status is-fallback';
      liveStatus.textContent=`Consulta remota no disponible · es mostra la reserva empaquetada, comprovada ${humanDate(D.dailyReadings?.checked_at_utc)}.`;
      const checkMeta=root.querySelector('[data-live-check-meta]');
      if(checkMeta) checkMeta.textContent=`reserva · ${humanDate(D.dailyReadings?.checked_at_utc)}`;
      updateSourceChecks(D.dailyReadings?.source_checks || {});
    }
  }
  updateGuide();
  refreshDailySnapshot();
})();
</script>
"""


if __name__ == "__main__":
    main()
