"""Connector registry for EcoRadar."""

from __future__ import annotations

from .base import BaseConnector
from .cobertes_sol import EmptyCobertesSolConnector


CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    EmptyCobertesSolConnector.connector_id: EmptyCobertesSolConnector,
}


def get_connector(connector_id: str) -> BaseConnector:
    try:
        connector_class = CONNECTOR_REGISTRY[connector_id]
    except KeyError as exc:
        known = ", ".join(sorted(CONNECTOR_REGISTRY))
        raise KeyError(f"Unknown connector '{connector_id}'. Known connectors: {known}") from exc
    return connector_class()

