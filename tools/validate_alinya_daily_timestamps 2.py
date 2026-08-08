"""Validate that the three public daily registries belong to the same run."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
FILES = {
    "daily_readings": PROJECT / "indicators" / "daily_readings.json",
    "daily_history": PROJECT / "indicators" / "daily_history.json",
    "current_fire_danger": PROJECT / "indicators" / "current_fire_danger.json",
}


def _instant(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise RuntimeError(f"{label} does not contain a valid checked_at_utc") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate(max_age_minutes: int, now: datetime | None = None) -> dict:
    payloads = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in FILES.items()
    }
    instants = {
        name: _instant(payload.get("checked_at_utc"), name)
        for name, payload in payloads.items()
    }
    unique = {instant.isoformat() for instant in instants.values()}
    if len(unique) != 1:
        raise RuntimeError(
            "Daily registries were not generated with the same checked_at_utc: "
            + ", ".join(f"{name}={value.isoformat()}" for name, value in instants.items())
        )
    checked_at = next(iter(instants.values()))
    age_minutes = ((now or datetime.now(timezone.utc)) - checked_at).total_seconds() / 60
    if age_minutes < -1 or age_minutes > max_age_minutes:
        raise RuntimeError(
            f"checked_at_utc is not recent: age={age_minutes:.1f} minutes, "
            f"maximum={max_age_minutes}"
        )
    if not payloads["daily_readings"].get("source_checks"):
        raise RuntimeError("daily_readings does not contain source_checks")
    return {
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "age_minutes": round(age_minutes, 2),
        "files": [str(path.relative_to(ROOT)) for path in FILES.values()],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-minutes", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(validate(args.max_age_minutes), indent=2))


if __name__ == "__main__":
    main()
