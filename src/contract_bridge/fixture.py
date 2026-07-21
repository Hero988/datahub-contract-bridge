"""Deterministic DataHub context fixture used for tests and an offline demonstration."""

from __future__ import annotations

import json
from pathlib import Path

from .domain import CatalogAsset, CatalogContext, CatalogField


def read_catalog_fixture(path: str | Path, relation_name: str) -> CatalogContext:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    record = payload[relation_name]
    return CatalogContext(
        dataset_urn=record["dataset_urn"],
        fields=tuple(
            CatalogField(item["name"], item.get("data_type")) for item in record["fields"]
        ),
        downstream=tuple(
            CatalogAsset(item["urn"], item["name"], item["entity_type"])
            for item in record.get("downstream", [])
        ),
        owners=tuple(record.get("owners", [])),
    )
