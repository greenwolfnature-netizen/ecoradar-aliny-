"""Persist real observations and derive trends, confidence and alerts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "LaSeu_Urba"
CONFIG = ROOT / "config" / "urban_daily_readings.json"
CURRENT = PROJECT / "indicators" / "daily_readings.json"
XEMA = PROJECT / "raw" / "meteocat_xema" / "CD_observations.csv"
HISTORY_DIR = PROJECT / "history"
OBSERVATIONS = HISTORY_DIR / "daily_readings_observations.jsonl"
CHECKS = HISTORY_DIR / "daily_readings_checks.jsonl"
OUTPUT = PROJECT / "indicators" / "daily_history.json"
METADATA = PROJECT / "metadata" / "daily_history.json"


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc) if value else None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_jsonl(path: Path, records: list[dict]) -> None:
    if not records:
        return
    with path.open("a", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _fingerprint(reading: str, data_at: str | None, value_numeric: float | None, value: str) -> str:
    # Display formatting (decimal comma, unit wording) must not create a new observation.
    raw = json.dumps([reading, data_at], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _seed_xema(existing: list[dict], current: dict) -> list[dict]:
    if existing or not XEMA.exists():
        return []
    frame = pd.read_csv(XEMA, dtype={"codi_variable": str, "codi_estat": str})
    frame["data_lectura"] = pd.to_datetime(frame["data_lectura"], utc=True)
    frame["valor_lectura"] = pd.to_numeric(frame["valor_lectura"], errors="coerce")
    frame = frame.dropna(subset=["data_lectura", "valor_lectura"])
    cutoff = frame["data_lectura"].max() - pd.Timedelta(days=35)
    frame = frame[frame["data_lectura"] >= cutoff]
    mapping = {
        "32": ("air_temperature", "°C", 1.0),
        "33": ("relative_humidity", "%", 1.0),
        "30": ("wind", "km/h", 3.6),
    }
    records: list[dict] = []
    for code, (key, unit, factor) in mapping.items():
        rows = frame[frame["codi_variable"] == code]
        source = current["readings"][key]["source"]
        for row in rows.itertuples(index=False):
            value = round(float(row.valor_lectura) * factor, 2)
            stamp = row.data_lectura.to_pydatetime().isoformat().replace("+00:00", "Z")
            records.append({
                "reading": key, "data_at_utc": stamp, "recorded_at_utc": stamp,
                "value_numeric": value, "value": f"{value:g} {unit}", "unit": unit,
                "source": source, "quality": "validada" if str(row.codi_estat) == "V" else "provisional XEMA",
                "fingerprint": _fingerprint(key, stamp, value, f"{value:g} {unit}"), "seeded_from_verified_source": True,
            })
    pivot = frame[frame["codi_variable"].isin(["30", "32", "33"])].pivot_table(
        index="data_lectura", columns="codi_variable", values="valor_lectura", aggfunc="last"
    ).dropna()
    source = current["readings"]["thermal_comfort"]["source"]
    for stamp, row in pivot.iterrows():
        temperature, humidity, wind = float(row["32"]), float(row["33"]), float(row["30"])
        vapour = humidity / 100 * 6.105 * math.exp(17.27 * temperature / (237.7 + temperature))
        value = round(temperature + 0.33 * vapour - 0.70 * wind - 4.0, 2)
        iso = stamp.to_pydatetime().isoformat().replace("+00:00", "Z")
        label = f"{value:g} °C aparents"
        records.append({
            "reading": "thermal_comfort", "data_at_utc": iso, "recorded_at_utc": iso,
            "value_numeric": value, "value": label, "unit": "°C aparents", "source": source,
            "quality": "derivat de XEMA", "fingerprint": _fingerprint("thermal_comfort", iso, value, label),
            "seeded_from_verified_source": True,
        })
    return records


def _quality_factor(item: dict, config: dict) -> tuple[float, str]:
    quality = item.get("quality", "").lower()
    factors = config["confidence"]["quality_factors"]
    if item.get("status_code") == "unavailable":
        return factors["unavailable"], "dada no disponible"
    if "qa_" in quality or "màscara scl" in quality:
        return factors["qa_validated"], "control de qualitat satel·litari"
    if "validada" in quality and "provisional" not in quality:
        return factors["validated"], "dada validada"
    if "provisional" in quality:
        return factors["provisional"], "dada provisional"
    if "model" in quality:
        return factors["coarse_model"], "model de resolució supramunicipal"
    return factors["derived_verified"], "indicador derivat documentat"


def _confidence(item: dict, rule: dict, config: dict, checked: datetime) -> dict:
    weights = config["confidence"]["weights"]
    available = item.get("value_numeric") is not None and item.get("data_at_utc") is not None
    availability = 1.0 if available else 0.0
    quality, quality_note = _quality_factor(item, config)
    max_age = rule.get("max_age_hours")
    data_at = _dt(item.get("data_at_utc"))
    if not available or data_at is None:
        freshness, age_hours = 0.0, None
    elif max_age is None:
        freshness, age_hours = 1.0, round((checked - data_at).total_seconds() / 3600, 1)
    else:
        age_hours = max(0.0, (checked - data_at).total_seconds() / 3600)
        freshness = max(0.0, 1.0 - age_hours / max_age)
    score = round(weights["availability"] * availability + weights["freshness"] * freshness + weights["quality"] * quality)
    labels = config["confidence"]["labels"]
    label = "Alta" if score >= labels["high_min"] else "Mitjana" if score >= labels["medium_min"] else "Baixa"
    return {
        "score_pct": score, "label": label, "age_hours": age_hours,
        "components": {"availability_pct": round(availability * 100), "freshness_pct": round(freshness * 100), "quality_pct": round(quality * 100)},
        "quality_note": quality_note,
    }


def _trend(observations: list[dict], direction: str, stable_pct: float) -> dict:
    numeric = [item for item in observations if item.get("value_numeric") is not None]
    if len(numeric) < 2:
        return {"symbol": "→", "label": "sense comparació", "variation_pct": None, "previous_data_at_utc": None}
    previous, current = numeric[-2], numeric[-1]
    old, new = float(previous["value_numeric"]), float(current["value_numeric"])
    variation = None if old == 0 else round((new - old) / abs(old) * 100, 1)
    change = new - old
    stable = abs(variation) <= stable_pct if variation is not None else change == 0
    if stable:
        symbol, label = "→", "estable"
    elif direction in ("lower_is_better", "lower_is_better_heat"):
        symbol, label = ("↑", "millora") if change < 0 else ("↓", "empitjora")
    elif direction == "higher_is_better":
        symbol, label = ("↑", "millora") if change > 0 else ("↓", "empitjora")
    else:
        symbol, label = "→", "canvi sense valoració"
    return {"symbol": symbol, "label": label, "variation_pct": variation, "previous_data_at_utc": previous["data_at_utc"], "previous_value_numeric": old}


def _alerts(key: str, item: dict, rule: dict) -> list[dict]:
    value = item.get("value_numeric")
    if value is None:
        return []
    active = []
    for threshold in rule.get("alerts", []):
        if float(value) >= float(threshold["min"]):
            active.append({"reading": key, "level": threshold["level"], "label": threshold["label"], "value": item["value"], "threshold": threshold["min"], "basis": threshold["basis"], "data_at_utc": item["data_at_utc"]})
    return active


def update() -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    checked = _dt(current["checked_at_utc"]) or datetime.now(timezone.utc)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    existing = _read_jsonl(OBSERVATIONS)
    additions = _seed_xema(existing, current)
    known = {item["fingerprint"] for item in existing + additions}
    for key, item in current["readings"].items():
        if item.get("data_at_utc") is None or item.get("value_numeric") is None:
            continue
        fingerprint = _fingerprint(key, item["data_at_utc"], item["value_numeric"], item["value"])
        if fingerprint in known:
            continue
        additions.append({
            "reading": key, "data_at_utc": item["data_at_utc"], "recorded_at_utc": current["checked_at_utc"],
            "value_numeric": item["value_numeric"], "value": item["value"], "unit": item.get("unit"),
            "source": item["source"], "quality": item["quality"], "fingerprint": fingerprint,
            "seeded_from_verified_source": False,
        })
        known.add(fingerprint)
    additions.sort(key=lambda item: (item["data_at_utc"], item["reading"]))
    _append_jsonl(OBSERVATIONS, additions)
    observations = existing + additions
    checks = _read_jsonl(CHECKS)
    if not any(item["checked_at_utc"] == current["checked_at_utc"] for item in checks):
        check = {"checked_at_utc": current["checked_at_utc"], "status_counts": current["status_counts"], "observation_additions": len(additions)}
        _append_jsonl(CHECKS, [check])
        checks.append(check)
    by_reading = {key: [] for key in current["readings"]}
    for item in observations:
        if item["reading"] in by_reading:
            by_reading[item["reading"]].append(item)
    for values in by_reading.values():
        values.sort(key=lambda item: item["data_at_utc"])
    analytics, alerts = {}, []
    for key, item in current["readings"].items():
        rule = config["readings"][key]
        active_alerts = _alerts(key, item, rule)
        alerts.extend(active_alerts)
        analytics[key] = {
            "frequency": {name: rule[name] for name in ("frequency_code", "frequency_label", "trigger")},
            "trend": _trend(by_reading[key], rule["trend_direction"], config["stable_variation_pct"]),
            "confidence": _confidence(item, rule, config, checked),
            "alerts": active_alerts,
            "observation_count": len(by_reading[key]),
        }
    public_series = by_reading
    payload = {
        "schema_version": "1.0", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checked_at_utc": current["checked_at_utc"], "analytics": analytics,
        "source_checks": current.get("source_checks", {}),
        "active_alerts": alerts, "series": public_series,
        "history": {"observation_count": len(observations), "check_count": len(checks), "observations_jsonl": str(OBSERVATIONS.relative_to(ROOT)), "checks_jsonl": str(CHECKS.relative_to(ROOT)), "public_series_limit_per_reading": None},
        "methodology": "docs/data_sources/urban_daily_readings.md",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    METADATA.write_text(text, encoding="utf-8")
    return payload


def main() -> None:
    payload = update()
    print(json.dumps({"observations": payload["history"]["observation_count"], "checks": payload["history"]["check_count"], "active_alerts": len(payload["active_alerts"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
