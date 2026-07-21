"""Small immutable domain model shared by the parser and planner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    name: str
    data_type: str | None
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class TestSpec:
    name: str
    column_name: str | None


@dataclass(frozen=True)
class DbtContract:
    unique_id: str
    relation_name: str
    fields: tuple[FieldSpec, ...]
    tests: tuple[TestSpec, ...]


@dataclass(frozen=True)
class CatalogField:
    name: str
    data_type: str | None


@dataclass(frozen=True)
class CatalogAsset:
    urn: str
    name: str
    entity_type: str


@dataclass(frozen=True)
class CatalogContext:
    dataset_urn: str
    fields: tuple[CatalogField, ...]
    downstream: tuple[CatalogAsset, ...]
    owners: tuple[str, ...]


@dataclass(frozen=True)
class Risk:
    severity: str
    code: str
    subject: str
    detail: str


@dataclass(frozen=True)
class ChangePlan:
    contract: DbtContract
    catalog: CatalogContext
    risks: tuple[Risk, ...]
    plan_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
