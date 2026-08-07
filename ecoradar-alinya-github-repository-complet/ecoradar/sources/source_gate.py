"""Source inventory gate for EcoRadar connectors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ALLOWED_CONNECTOR_STATUS = "verified"


@dataclass(frozen=True)
class SourceRecord:
    """One source entry from `docs/data_sources/sources_inventory.yml`."""

    source_id: str
    domain: str
    source_name: str
    responsible_organization: str
    official_url: str | None
    connector_status: str

    @property
    def connector_allowed(self) -> bool:
        return self.connector_status == ALLOWED_CONNECTOR_STATUS


class SourceInventory:
    """Minimal reader for the EcoRadar source inventory.

    The project intentionally avoids adding a YAML dependency just to read the
    source gate. This parser reads the scalar fields needed for connector
    decisions and ignores nested lists.
    """

    def __init__(self, records: dict[str, SourceRecord]) -> None:
        self.records = records

    @classmethod
    def from_file(cls, path: str | Path = "docs/data_sources/sources_inventory.yml") -> "SourceInventory":
        source_path = Path(path)
        records: dict[str, SourceRecord] = {}
        current: dict[str, str | None] | None = None

        for raw_line in source_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            if line.startswith("  - id:"):
                if current:
                    record = _record_from_mapping(current)
                    records[record.source_id] = record
                current = {"id": _clean_value(line.split(":", 1)[1])}
                continue
            if current is None or not line.startswith("    ") or ":" not in line:
                continue
            key, value = line.strip().split(":", 1)
            if value.strip() == "":
                continue
            if key in {"domain", "source_name", "responsible_organization", "official_url", "connector_status"}:
                current[key] = _clean_value(value)

        if current:
            record = _record_from_mapping(current)
            records[record.source_id] = record
        return cls(records)

    def get(self, source_id: str) -> SourceRecord:
        try:
            return self.records[source_id]
        except KeyError as exc:
            raise KeyError(f"Unknown EcoRadar source id: {source_id}") from exc

    def connector_allowed(self, source_id: str) -> bool:
        return self.get(source_id).connector_allowed

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records.values():
            counts[record.connector_status] = counts.get(record.connector_status, 0) + 1
        return counts


def _record_from_mapping(mapping: dict[str, str | None]) -> SourceRecord:
    return SourceRecord(
        source_id=str(mapping.get("id") or ""),
        domain=str(mapping.get("domain") or ""),
        source_name=str(mapping.get("source_name") or ""),
        responsible_organization=str(mapping.get("responsible_organization") or ""),
        official_url=mapping.get("official_url"),
        connector_status=str(mapping.get("connector_status") or "pending_verification"),
    )


def _clean_value(value: str) -> str | None:
    text = value.strip().strip('"').strip("'")
    if text in {"null", "None", ""}:
        return None
    return text
