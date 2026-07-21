"""Extract enforced contracts and explicitly contract-tagged tests from dbt artifacts."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .domain import DbtContract, FieldSpec, TestSpec


class ManifestError(ValueError):
    """Raised when a dbt manifest cannot produce an unambiguous contract."""


def _tags(node: dict[str, Any]) -> set[str]:
    values = node.get("tags") or node.get("config", {}).get("tags") or []
    return {str(value).strip().lower() for value in values}


def _relation_name(node: dict[str, Any]) -> str:
    if value := node.get("relation_name"):
        return str(value).strip('"`')
    parts = [node.get("database"), node.get("schema"), node.get("alias") or node.get("name")]
    if all(parts):
        return ".".join(str(part).strip('"`') for part in parts)
    raise ManifestError(f"{node.get('unique_id', '<unknown>')} has no resolvable relation name")


def _constraints(column: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for constraint in column.get("constraints") or []:
        if isinstance(constraint, str):
            values.append(constraint)
        elif isinstance(constraint, dict) and constraint.get("type"):
            values.append(str(constraint["type"]))
    return tuple(sorted(set(values)))


def read_contracts(path: str | Path, *, test_tag: str = "contract") -> tuple[DbtContract, ...]:
    """Read dbt ``manifest.json`` and return only enabled, enforced model contracts.

    Tests are included only when dbt marks them with ``test_tag``. This avoids silently
    turning every model test into a governance promise.
    """

    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read dbt manifest {manifest_path}: {exc}") from exc

    nodes = payload.get("nodes")
    if not isinstance(nodes, dict):
        raise ManifestError("dbt manifest must contain an object named 'nodes'")

    tagged_tests: dict[str, list[TestSpec]] = defaultdict(list)
    wanted_tag = test_tag.strip().lower()
    for node in nodes.values():
        if not isinstance(node, dict) or node.get("resource_type") != "test":
            continue
        if wanted_tag not in _tags(node):
            continue
        dependencies = node.get("depends_on", {}).get("nodes") or []
        test_metadata = node.get("test_metadata") or {}
        test_name = str(test_metadata.get("name") or node.get("name") or "unnamed_test")
        column_name = node.get("column_name") or test_metadata.get("kwargs", {}).get("column_name")
        for dependency in dependencies:
            if str(dependency).startswith("model."):
                tagged_tests[str(dependency)].append(
                    TestSpec(test_name, str(column_name) if column_name else None)
                )

    contracts: list[DbtContract] = []
    for unique_id, node in nodes.items():
        if not isinstance(node, dict) or node.get("resource_type") != "model":
            continue
        config = node.get("config") or {}
        if config.get("enabled") is False:
            continue
        contract_config = config.get("contract") or {}
        if not isinstance(contract_config, dict) or contract_config.get("enforced") is not True:
            continue

        columns = node.get("columns") or {}
        if not isinstance(columns, dict) or not columns:
            raise ManifestError(f"{unique_id} enforces a contract but declares no columns")

        fields = tuple(
            FieldSpec(
                name=str(column.get("name") or key),
                data_type=str(column["data_type"]) if column.get("data_type") else None,
                constraints=_constraints(column),
            )
            for key, column in sorted(columns.items())
            if isinstance(column, dict)
        )
        contracts.append(
            DbtContract(
                unique_id=str(unique_id),
                relation_name=_relation_name(node),
                fields=fields,
                tests=tuple(
                    sorted(
                        tagged_tests.get(str(unique_id), []),
                        key=lambda item: (item.name, item.column_name or ""),
                    )
                ),
            )
        )

    return tuple(sorted(contracts, key=lambda item: item.unique_id))
