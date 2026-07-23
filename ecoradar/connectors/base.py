"""Base connector contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectorResult:
    """Result returned by all EcoRadar connectors."""

    connector_id: str
    source_id: str | None
    status: str
    records: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class BaseConnector(ABC):
    """Minimal connector interface.

    Connectors may download and normalize official source data, but they must not
    calculate EcoRadar indicators.
    """

    connector_id: str
    source_id: str | None = None

    @abstractmethod
    def run(self, study_area: Any, **kwargs: Any) -> ConnectorResult:
        """Run the connector for a prepared study area."""

