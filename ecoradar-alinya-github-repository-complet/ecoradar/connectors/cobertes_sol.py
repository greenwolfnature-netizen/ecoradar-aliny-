"""Empty test connector for land-cover architecture."""

from __future__ import annotations

from typing import Any

from .base import BaseConnector, ConnectorResult


class EmptyCobertesSolConnector(BaseConnector):
    """A no-download connector used to prove the modular architecture."""

    connector_id = "cobertes_sol_empty"
    source_id = None

    def run(self, study_area: Any, **kwargs: Any) -> ConnectorResult:
        return ConnectorResult(
            connector_id=self.connector_id,
            source_id=self.source_id,
            status="not_implemented",
            records=[],
            metadata={
                "purpose": "architecture_test",
                "downloads_data": False,
                "calculates_indicators": False,
                "study_area_name": getattr(study_area, "name", None),
                "study_area_area_ha": getattr(study_area, "area_ha", None),
            },
            warnings=(
                "Empty connector only. It does not connect to land-cover sources yet.",
            ),
        )

