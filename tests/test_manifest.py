from __future__ import annotations

import json
from pathlib import Path

import pytest

from contract_bridge.manifest import ManifestError, read_contracts

FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_only_enforced_contract_and_tagged_tests() -> None:
    contracts = read_contracts(FIXTURES / "manifest.json")

    assert len(contracts) == 1
    contract = contracts[0]
    assert contract.relation_name == "warehouse.analytics.orders"
    assert [field.name for field in contract.fields] == ["customer_id", "net_total", "order_id"]
    assert contract.fields[2].constraints == ("not_null",)
    assert [(test.name, test.column_name) for test in contract.tests] == [("unique", "order_id")]


def test_rejects_enforced_contract_without_columns(tmp_path: Path) -> None:
    payload = {
        "nodes": {
            "model.bridge.empty": {
                "resource_type": "model",
                "unique_id": "model.bridge.empty",
                "relation_name": "warehouse.analytics.empty",
                "config": {"contract": {"enforced": True}},
                "columns": {},
            }
        }
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ManifestError, match="declares no columns"):
        read_contracts(path)
